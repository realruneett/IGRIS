#!/usr/bin/env python3
"""
CounciL Strategic Systems - Project Love v4.4.6
Interactive Agentic CLI with Diagnostics + Known Fast Model

Changes in v4.4.6:
  - DIAGNOSTIC MODE: times every API call, prints TTFT and total time
  - Switches Greeter to meta/llama-3.1-8b-instruct (known fast, proven on NVIDIA API)
  - DeepSeek V4 Flash removed - suspected slow TTFT despite "flash" name
  - Explicit timing prints: [TTFT: 0.3s | Total: 1.2s]
  - Fallback: if Greeter fails, uses local echo as emergency fallback
  - Debug mode: /debug on shows full message sizes and API call details
"""

import argparse
import urllib.request
import urllib.parse
from html.parser import HTMLParser
import json
import os
import sys
import re
import subprocess
import time
from datetime import datetime
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from openai import OpenAI, APIError


# ===================================================================
# RESILIENT API WRAPPER with TIMING
# ===================================================================

class ResilientClient:
    def __init__(self, base_client, name="", max_retries=3, base_delay=1.0):
        self.client = base_client
        self.name = name
        self.max_retries = max_retries
        self.base_delay = base_delay

    def _is_retryable(self, error):
        if isinstance(error, APIError):
            status = getattr(error, 'status_code', None) or getattr(error, 'code', None)
            if status in (502, 503, 504, 429, 408, 520, 521, 522, 523, 524):
                return True
            msg = str(error).lower()
            if any(x in msg for x in ['timeout', 'gateway', 'temporarily', 'overloaded', 'rate limit']):
                return True
        elif isinstance(error, (ConnectionError, TimeoutError, OSError)):
            return True
        return False

    def chat_completions_create(self, **kwargs):
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                last_error = e
                if not self._is_retryable(e):
                    raise
                delay = self.base_delay * (2 ** attempt)
                print(f"  [{self.name}] API error (attempt {attempt + 1}/{self.max_retries}): {str(e)[:80]}... Retrying in {delay}s")
                time.sleep(delay)
        raise last_error


# ===================================================================
# TOKEN & CONTEXT UTILITIES
# ===================================================================

def estimate_tokens(text):
    if not text:
        return 0
    return max(1, len(text) // 4)

def estimate_messages_tokens(messages):
    total = 0
    for msg in messages:
        content = msg.get("content", "")
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict):
                    if part.get("type") == "text":
                        total += estimate_tokens(part.get("text", ""))
                    elif part.get("type") in ("image_url", "video_url"):
                        total += 500
        total += 4
    return total

def truncate_text(text, max_tokens, suffix="\n...[truncated]"):
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


# ===================================================================
# NATIVE TOOLS & WEB BROWSING
# ===================================================================

class WebTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.ignore_tags = {'script', 'style', 'head', 'meta', 'link'}
        self.current_tag = None

    def handle_starttag(self, tag, attrs):
        self.current_tag = tag

    def handle_endtag(self, tag):
        self.current_tag = None

    def handle_data(self, data):
        if self.current_tag not in self.ignore_tags:
            text = data.strip()
            if text:
                self.text.append(text)

class NativeTools:
    def __init__(self, file_tools):
        self.files = file_tools

    def read_file(self, filepath):
        return self.files.read_file(filepath)

    def write_file(self, filepath, content):
        return self.files.write_file(filepath, content)

    def list_dir(self, path):
        full = self.files._resolve(path)
        if not full.exists():
            return f"[Error] Directory not found: {path}"
        if not full.is_dir():
            return f"[Error] Not a directory: {path}"
        items = []
        for item in full.iterdir():
            items.append(f"{'[DIR]' if item.is_dir() else '[FILE]'} {item.name}")
        return "\n".join(items)

    def delete_file(self, filepath):
        return self.files.delete_file(filepath)
    
    def fetch_url(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                parser = WebTextParser()
                parser.feed(html)
                return "\n".join(parser.text)[:20000]
        except Exception as e:
            return f"[Error] fetching {url}: {e}"

    def search_web(self, query):
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                results = []
                import re as regex
                for match in regex.finditer(r'<a class="result__url" href="([^"]+)">(.*?)</a>.*?<a class="result__snippet[^>]*>(.*?)</a>', html, regex.DOTALL | regex.IGNORECASE):
                    link = match.group(1)
                    snippet = match.group(3)
                    snippet = regex.sub(r'<[^>]+>', '', snippet)
                    results.append(f"URL: {link}\nSnippet: {snippet.strip()}")
                return "\n\n".join(results[:5]) if results else "No results found."
        except Exception as e:
            return f"[Error] web search failed: {e}"

    def get_tools_schema(self):
        return [
            {"type": "function", "function": {"name": "read_file", "description": "Read contents of a file.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
            {"type": "function", "function": {"name": "write_file", "description": "Write content to a file.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}, "content": {"type": "string"}}, "required": ["filepath", "content"]}}},
            {"type": "function", "function": {"name": "list_dir", "description": "List files and directories in a path.", "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}},
            {"type": "function", "function": {"name": "delete_file", "description": "Delete a file.", "parameters": {"type": "object", "properties": {"filepath": {"type": "string"}}, "required": ["filepath"]}}},
            {"type": "function", "function": {"name": "search_web", "description": "Search the web for a query using DuckDuckGo.", "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}}},
            {"type": "function", "function": {"name": "fetch_url", "description": "Fetch text content from a webpage URL.", "parameters": {"type": "object", "properties": {"url": {"type": "string"}}, "required": ["url"]}}}
        ]

    def execute_tool(self, name, args_dict):
        if name == "read_file": return self.read_file(args_dict.get("filepath"))
        elif name == "write_file": return self.write_file(args_dict.get("filepath"), args_dict.get("content"))
        elif name == "list_dir": return self.list_dir(args_dict.get("path"))
        elif name == "delete_file": return self.delete_file(args_dict.get("filepath"))
        elif name == "search_web": return self.search_web(args_dict.get("query"))
        elif name == "fetch_url": return self.fetch_url(args_dict.get("url"))
        else: return f"[Error] Unknown tool {name}"

# ===================================================================
# FILE SYSTEM TOOLS
# ===================================================================

class FileTools:
    def __init__(self, project_dir="."):
        self.project_dir = Path(project_dir).resolve()
        self.context_files = set()

    def add_to_context(self, filepath):
        full = self._resolve(filepath)
        if not full.exists():
            return f"[Error] File not found: {filepath}"
        if not full.is_file():
            return f"[Error] Not a file: {filepath}"
        self.context_files.add(str(full))
        size = full.stat().st_size
        return f"[Context] Added {filepath} ({size} bytes). {len(self.context_files)} files in context."

    def drop_from_context(self, filepath):
        full = self._resolve(filepath)
        path_str = str(full)
        if path_str in self.context_files:
            self.context_files.remove(path_str)
            return f"[Context] Removed {filepath}. {len(self.context_files)} files remain."
        return f"[Context] {filepath} was not in context."

    def list_context(self):
        if not self.context_files:
            return "[Context] No files in context. Use /add <file> to add files."
        lines = [f"[Context] {len(self.context_files)} file(s) in context:"]
        for f in sorted(self.context_files):
            rel = Path(f).relative_to(self.project_dir)
            size = Path(f).stat().st_size
            lines.append(f"  - {rel} ({size} bytes)")
        return "\n".join(lines)

    def read_file(self, filepath, max_chars=50000):
        full = self._resolve(filepath)
        if not full.exists():
            return f"[Error] File not found: {filepath}"
        try:
            with open(full, "r", encoding="utf-8", errors="replace") as f:
                content = f.read(max_chars)
            if len(content) == max_chars:
                content += "\n\n[...truncated...]"
            return content
        except Exception as e:
            return f"[Error] Could not read {filepath}: {e}"

    def write_file(self, filepath, content):
        full = self._resolve(filepath)
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[Success] Wrote {filepath} ({len(content)} chars)"
        except Exception as e:
            return f"[Error] Could not write {filepath}: {e}"

    def delete_file(self, filepath):
        full = self._resolve(filepath)
        try:
            if full.exists():
                full.unlink()
                return f"[Success] Deleted {filepath}"
            return f"[Error] File not found: {filepath}"
        except Exception as e:
            return f"[Error] Could not delete {filepath}: {e}"

    def create_dir(self, dirpath):
        full = self._resolve(dirpath)
        try:
            full.mkdir(parents=True, exist_ok=True)
            return f"[Success] Created directory {dirpath}"
        except Exception as e:
            return f"[Error] Could not create {dirpath}: {e}"

    def tree(self, max_depth=3):
        lines = [f"[Project] {self.project_dir}"]
        try:
            result = subprocess.run(
                ["git", "-C", str(self.project_dir), "ls-files"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0 and result.stdout.strip():
                files = sorted(result.stdout.strip().split("\n"))
                lines.append(f"  ({len(files)} tracked files)")
                for f in files[:100]:
                    lines.append(f"  {f}")
                if len(files) > 100:
                    lines.append(f"  ... and {len(files) - 100} more")
                return "\n".join(lines)
        except:
            pass

        count = 0
        for root, dirs, files in os.walk(self.project_dir):
            depth = root.count(os.sep) - str(self.project_dir).count(os.sep)
            if depth > max_depth:
                del dirs[:]
                continue
            indent = "  " * depth
            lines.append(f"{indent}{os.path.basename(root)}/")
            for f in files[:20]:
                lines.append(f"{indent}  {f}")
                count += 1
            if len(files) > 20:
                lines.append(f"{indent}  ... ({len(files) - 20} more)")
            if count > 100:
                lines.append("  ... (truncated)")
                break
        return "\n".join(lines)

    def _resolve(self, filepath):
        p = Path(filepath)
        if p.is_absolute():
            return p
        return (self.project_dir / p).resolve()

    def build_context_prompt(self, max_tokens_per_file=8000):
        if not self.context_files:
            return ""
        parts = ["\n=== FILES IN CONTEXT ==="]
        total_est = 0
        for fpath in sorted(self.context_files):
            rel = Path(fpath).relative_to(self.project_dir)
            content = self.read_file(fpath, max_chars=max_tokens_per_file * 4)
            file_section = f"\n--- FILE: {rel} ---\n{content}\n--- END {rel} ---"
            parts.append(file_section)
            total_est += estimate_tokens(file_section)
            if total_est > 40000:
                parts.append("\n...[Additional files omitted to stay within API limits]...")
                break
        parts.append("\n=== END FILES ===\n")
        return "\n".join(parts)


# ===================================================================
# PERSISTENT MEMORY
# ===================================================================

class CouncilMemory:
    def __init__(self, memory_dir="council_memory"):
        self.memory_dir = memory_dir
        self.sessions_dir = os.path.join(memory_dir, "sessions")
        self.lessons_file = os.path.join(memory_dir, "lessons_learned.json")
        self.master_log = os.path.join(memory_dir, "council_memory.jsonl")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.lessons = self._load_lessons()
        self.session_count = len([f for f in os.listdir(self.sessions_dir) if f.endswith(".json")])

    def _load_lessons(self):
        if os.path.exists(self.lessons_file):
            with open(self.lessons_file, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"lessons": [], "corrections": [], "meta": {"created": datetime.now().isoformat(), "version": "4.4.6"}}

    def save_lessons(self):
        with open(self.lessons_file, "w", encoding="utf-8") as f:
            json.dump(self.lessons, f, indent=2, ensure_ascii=False)

    def log_session(self, session_data):
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        session_id = f"session_{self.session_count}_{timestamp}"
        filepath = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        with open(self.master_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({"session_id": session_id, "timestamp": timestamp,
                                "agenda": session_data.get("agenda", ""),
                                "success": session_data.get("success", True)}, ensure_ascii=False) + "\n")
        self.session_count += 1
        return session_id

    def add_lesson(self, category, description, trigger, solution, members_involved):
        lesson = {"id": len(self.lessons["lessons"]) + 1, "timestamp": datetime.now().isoformat(),
                  "category": category, "description": description, "trigger": trigger,
                  "solution": solution, "members_involved": members_involved}
        self.lessons["lessons"].append(lesson)
        self.save_lessons()
        return lesson["id"]

    def get_relevant_lessons(self, agenda, max_lessons=5):
        agenda_lower = agenda.lower()
        scored = []
        for lesson in self.lessons["lessons"]:
            score = sum(2 for w in lesson["trigger"].lower().split() if len(w) > 3 and w in agenda_lower)
            score += sum(1 for w in lesson["description"].lower().split() if len(w) > 3 and w in agenda_lower)
            if score > 0:
                scored.append((score, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:max_lessons]]

    def get_lessons_prompt(self, agenda, max_tokens=2000):
        lessons = self.get_relevant_lessons(agenda)
        if not lessons:
            return ""
        lines = ["", "=== COUNCIL MEMORY: LESSONS FROM PAST SESSIONS ===",
                 "Avoid repeating these mistakes. Apply these solutions proactively.", ""]
        for lesson in lessons:
            lines.append(f"[Lesson #{lesson['id']}] {lesson['category'].upper()}\n"
                         f"  Issue: {lesson['description']}\n"
                         f"  Trigger: {lesson['trigger']}\n"
                         f"  Solution: {lesson['solution']}\n"
                         f"  Members: {', '.join(lesson['members_involved'])}")
        lines.append("=== END MEMORY ===")
        result = "\n".join(lines)
        return truncate_text(result, max_tokens)

    def get_stats(self):
        return {"total_sessions": self.session_count, "total_lessons": len(self.lessons["lessons"]),
                "total_corrections": len(self.lessons["corrections"]), "memory_dir": self.memory_dir}


# ===================================================================
# COUNCIL MEMBER with TIMING DIAGNOSTICS
# ===================================================================

class CouncilMember:
    NIM_API_MAX_TOKENS = 131072
    SAFE_PROMPT_TOKENS = 100000

    def __init__(self, name, title, role, client, model, max_tokens, context_window, native_tools=None, extra_body=None):
        self.name = name
        self.title = title
        self.role = role
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.extra_body = extra_body or {}
        self.resilient = ResilientClient(client, name=name, max_retries=3, base_delay=1.0)
        self.native_tools = native_tools

    def _estimate_and_guard(self, messages):
        total = estimate_messages_tokens(messages)
        if total > self.SAFE_PROMPT_TOKENS:
            print(f"  [{self.name}] WARNING: Prompt estimated at {total:,} tokens. Truncating...")
            for i in range(len(messages) - 1, -1, -1):
                if messages[i].get("role") == "user":
                    content = messages[i].get("content", "")
                    if len(content) > 1000:
                        target_tokens = self.SAFE_PROMPT_TOKENS // 2
                        messages[i]["content"] = truncate_text(content, target_tokens)
                        break
        return messages

    def speak(self, messages, temperature=1.0, top_p=0.95, stream=False, debug=False):
        import json
        messages_copy = messages.copy()
        total_content = ""
        loop_count = 0

        while loop_count < 5:
            loop_count += 1
            messages_copy = self._estimate_and_guard(messages_copy)
            kwargs = {"model": self.model, "messages": messages_copy, "temperature": temperature,
                      "top_p": top_p, "max_tokens": self.max_tokens, "stream": stream}
            if self.extra_body:
                kwargs["extra_body"] = self.extra_body
            if self.native_tools:
                kwargs["tools"] = self.native_tools.get_tools_schema()
                kwargs["tool_choice"] = "auto"

            if debug:
                prompt_size = estimate_messages_tokens(messages_copy)
                print(f"  [DEBUG {self.name}] Prompt: {prompt_size:,} tokens | Model: {self.model} | Stream: {stream}")

            start_time = time.time()

            try:
                response = self.resilient.chat_completions_create(**kwargs)
                if stream:
                    return response, start_time
                
                msg = response.choices[0].message
                if msg.content:
                    total_content += msg.content
                
                if msg.tool_calls:
                    assistant_msg = {"role": "assistant"}
                    if msg.content:
                        assistant_msg["content"] = msg.content
                    
                    tool_calls_list = []
                    for tc in msg.tool_calls:
                        tool_calls_list.append({
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments}
                        })
                    assistant_msg["tool_calls"] = tool_calls_list
                    messages_copy.append(assistant_msg)

                    for tc in msg.tool_calls:
                        fn_name = tc.function.name
                        fn_args = tc.function.arguments
                        print(f"\n  [{self.name} TOOL CALL] {fn_name}({fn_args[:100]}...)")
                        try:
                            args_dict = json.loads(fn_args)
                            result = self.native_tools.execute_tool(fn_name, args_dict)
                        except Exception as e:
                            result = f"[Error] Parsing or executing tool: {e}"
                        
                        messages_copy.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "name": fn_name,
                            "content": str(result)
                        })
                    
                    print(f"  [{self.name}] Reading tool results...")
                    if loop_count >= 5:
                        print(f"  [{self.name}] Max tool loops reached.")
                        return total_content or getattr(msg, "content", "") or "[Error: Max tool loops reached]"
                    continue # self-correct loop
                
                elapsed = time.time() - start_time
                final_res = total_content or msg.content or ""
                print(f"  [{self.name}] TTFT+Gen: {elapsed:.1f}s | {estimate_tokens(final_res)} tokens")
                return final_res

            except Exception as e:
                error_msg = f"[{self.name}] API call failed: {str(e)[:200]}"
                print(f"  {error_msg}")
                return f"[ERROR: {self.name} could not respond: {str(e)[:100]}]" 

    def speak_streaming(self, messages, temperature=1.0, top_p=0.95, debug=False):
        import json
        messages_copy = messages.copy()
        session_full_text = ""
        loop_count = 0

        while loop_count < 5:
            loop_count += 1
            messages_copy = self._estimate_and_guard(messages_copy)
            kwargs = {"model": self.model, "messages": messages_copy, "temperature": temperature,
                      "top_p": top_p, "max_tokens": self.max_tokens, "stream": True}
            if self.extra_body:
                kwargs["extra_body"] = self.extra_body
            if self.native_tools:
                kwargs["tools"] = self.native_tools.get_tools_schema()
                kwargs["tool_choice"] = "auto"

            if debug:
                prompt_size = estimate_messages_tokens(messages_copy)
                print(f"  [DEBUG {self.name}] Prompt: {prompt_size:,} tokens | Model: {self.model} | Stream: True")

            start_time = time.time()
            first_token_printed = False

            try:
                response = self.resilient.chat_completions_create(**kwargs)
                full_text = ""
                tool_calls_buffer = {}
                finish_reason = None

                for chunk in response:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason or finish_reason

                    if hasattr(delta, 'tool_calls') and delta.tool_calls:
                        for tc in delta.tool_calls:
                            idx = tc.index
                            if idx not in tool_calls_buffer:
                                tool_calls_buffer[idx] = {"id": tc.id, "type": "function", "function": {"name": "", "arguments": ""}}
                            if getattr(tc.function, "name", None):
                                tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                            if getattr(tc.function, "arguments", None):
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments
                    
                    content = getattr(delta, "content", None)
                    if content:
                        if not first_token_printed:
                            ttft = time.time() - start_time
                            print(f"  [{self.name}] TTFT: {ttft:.2f}s", end="\r")
                            first_token_printed = True
                        print(content, end="", flush=True)
                        full_text += content
                
                session_full_text += full_text

                if finish_reason == "tool_calls" or tool_calls_buffer:
                    assistant_msg = {"role": "assistant"}
                    if full_text:
                        assistant_msg["content"] = full_text
                    
                    tool_calls_list = list(tool_calls_buffer.values())
                    assistant_msg["tool_calls"] = tool_calls_list
                    messages_copy.append(assistant_msg)

                    for tc in tool_calls_list:
                        fn_name = tc["function"]["name"]
                        fn_args = tc["function"]["arguments"]
                        print(f"\n  [{self.name} TOOL CALL] {fn_name}({fn_args[:100]}...)")
                        try:
                            args_dict = json.loads(fn_args)
                            result = self.native_tools.execute_tool(fn_name, args_dict)
                        except Exception as e:
                            result = f"[Error] Parsing or executing tool: {e}"
                        
                        messages_copy.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": fn_name,
                            "content": str(result)
                        })
                    
                    print(f"  [{self.name}] Reading tool results...")
                    if loop_count >= 5:
                        print(f"  [{self.name}] Max tool loops reached.")
                        return session_full_text or "[Error: Max tool loops reached]"
                    continue # self-correct loop
                else:
                    total_time = time.time() - start_time
                    token_count = estimate_tokens(session_full_text)
                    print(f"\n  [{self.name}] Total: {total_time:.1f}s | {token_count} tokens | ~{token_count/max(total_time,0.1):.0f} tok/s")
                    return session_full_text
            except Exception as e:
                print(f"  [{self.name}] Streaming failed: {str(e)[:100]}")
                return self.speak(messages_copy, temperature, top_p, stream=False, debug=debug)

    def available_context(self):
        return min(self.context_window, self.NIM_API_MAX_TOKENS) - self.max_tokens - 500


# ===================================================================
# THE COUNCIL
# ===================================================================

class Council:
    MAX_HISTORY_TOKENS = 80000

    def __init__(self, memory: CouncilMemory, file_tools: FileTools):
        self.members = []
        self.memory = memory
        self.files = file_tools
        self.deliberation_log = []
        self.reflections = []
        self.assignments = {}
        self.user_agenda = ""
        self.execution_results = {}
        self.final_output = ""
        self.history_summary = ""
        self.rounds = 2
        self.mode = "auto"
        self.chat_history = []
        self.streaming = True
        self.debug = False

    def add_member(self, member):
        self.members.append(member)

    def build_system_prompt(self, speaker, agenda="", mode="chat"):
        others = [f"{m.name} ({m.title})" for m in self.members if m.name != speaker.name]
        others_str = ", ".join(others)
        lessons_text = self.memory.get_lessons_prompt(agenda) if agenda else ""

        if mode == "chat":
            base = (f"You are {speaker.name}. Respond naturally and concisely. "
                    f"If the user wants code/files/complex work, start with [WORK_MODE]. "
                    f"Sign: - {speaker.name}")
        elif mode == "gatekeeper":
            base = (f"You are {speaker.name}, the council gatekeeper. "
                    f"Respond to the user naturally. "
                    f"If they want complex work (code, files, building, analysis, debugging), "
                    f"start with [WORK_MODE] on its own line, then briefly say what the council should do. "
                    f"Otherwise just chat normally. Be brief and fast. "
                    f"Sign: - {speaker.name}")
        else:
            base = (f"You are {speaker.name}, serving as {speaker.title} - {speaker.role}.\n\n"
                    f"You are in WORK MODE. You are a member of the CounciL Strategic Systems deliberative council for Project Love. "
                    f"Your fellow council members are: {others_str}.\n\n"
                    f"You have FULL NATIVE TOOL ACCESS. You can use your function calling tools to read files, write files, list directories, and search the web natively!\n"
                    f"If a tool fails, you will see the error and can try again. Do actual work dynamically during the deliberation phase.\n\n"
                    f"Rules of engagement:\n"
                    f"1. Address other members by name when responding to their points.\n"
                    f"2. Stay in your role. Do not perform another member's specialty.\n"
                    f"3. You may propose, object, support, refine, or ask clarifying questions.\n"
                    f"4. Be concise but thorough. End your turn with a clear position, proposal, or question.\n"
                    f"5. During task assignment, explicitly state which tasks you claim or assign to others.\n"
                    f"6. Maintain defense-grade precision and highly analytical reasoning.\n"
                    f"7. Use your tools to verify facts instead of guessing.\n"
                    f"8. Sign your name at the end of every response: - {speaker.name}")

        if lessons_text:
            base += f"\n\n{lessons_text}"
        return base

    def _format_deliberation_history(self, max_rounds=None):
        turns = self.deliberation_log
        if max_rounds:
            rounds = {}
            for turn in turns:
                r = turn.get("round", 0)
                rounds.setdefault(r, []).append(turn)
            sorted_rounds = sorted(rounds.keys())
            keep = sorted_rounds[-max_rounds:]
            turns = [t for t in turns if t.get("round", 0) in keep]

        lines = []
        total_tokens = 0
        for turn in turns:
            line = f"[{turn['speaker']}]: {turn['content']}"
            line_tokens = estimate_tokens(line)
            if total_tokens + line_tokens > self.MAX_HISTORY_TOKENS:
                lines.append("\n...[Earlier deliberation truncated to stay within API limits]...")
                break
            lines.append(line)
            total_tokens += line_tokens

        return "\n\n".join(lines)

    def _compress_history_for_member(self, member):
        full_history = self._format_deliberation_history()
        system_prompt = self.build_system_prompt(member, agenda=self.user_agenda, mode="work")
        test_messages = [{"role": "system", "content": system_prompt},
                         {"role": "user", "content": f"Agenda: {self.user_agenda}\n\nFull deliberation:\n{full_history}\n\n[Your turn to speak.]"}]
        estimated = estimate_messages_tokens(test_messages)
        available = member.available_context()
        if estimated <= available:
            return full_history

        historian = max(self.members, key=lambda m: m.context_window)
        print(f"[Context] {member.name}'s window ({member.context_window}) too small. Compressing via {historian.name}...")

        rounds = {}
        for turn in self.deliberation_log:
            rounds.setdefault(turn.get("round", 0), []).append(turn)
        sorted_rounds = sorted(rounds.keys())
        if len(sorted_rounds) <= 2:
            return truncate_text(full_history, available)

        old_rounds = sorted_rounds[:-2]
        recent_rounds = sorted_rounds[-2:]
        old_text = "\n\n".join([f"[{t['speaker']}]: {t['content']}" for r in old_rounds for t in rounds[r]])

        summarize_prompt = (f"You are the council historian. Summarize the following older deliberation rounds "
                              f"into a concise summary (max 2000 tokens). Preserve key decisions, objections, and assignments. Omit filler.\n\n{old_text}")
        summary = historian.speak([{"role": "system", "content": self.build_system_prompt(historian, agenda=self.user_agenda, mode="work")},
                                   {"role": "user", "content": summarize_prompt}])
        recent_text = "\n\n".join([f"[{t['speaker']}]: {t['content']}" for r in recent_rounds for t in rounds[r]])
        compressed = (f"[COMPRESSED HISTORY - Rounds {old_rounds[0]} to {old_rounds[-1]} summarized by {historian.name}]:\n{summary}\n\n"
                      f"[RECENT ROUNDS - Full detail]:\n{recent_text}")
        print(f"[Context] Compression complete.")
        return compressed

    def chat(self, user_message, gatekeeper=False):
        greeter = self.members[0]

        mode = "gatekeeper" if gatekeeper else "chat"
        messages = [{"role": "system", "content": self.build_system_prompt(greeter, mode=mode)}]
        for msg in self.chat_history[-3:]:
            messages.append(msg)
        messages.append({"role": "user", "content": user_message})

        print(f"\n{greeter.name}> ", end="", flush=True)

        if self.streaming:
            response = greeter.speak_streaming(messages, temperature=0.9, debug=self.debug)
        else:
            response = greeter.speak(messages, temperature=0.9, debug=self.debug)
            print(response)

        self.chat_history.append({"role": "user", "content": user_message})
        self.chat_history.append({"role": "assistant", "content": response})

        return response

    def detect_work_intent(self, user_message):
        work_keywords = [
            "build", "create", "make", "write", "code", "script", "program",
            "implement", "develop", "generate", "fix", "debug", "refactor",
            "analyze", "process", "scrape", "crawl", "deploy", "setup",
            "configure", "install", "add feature", "new file", "directory",
            "delete", "remove", "update", "modify", "change", "edit",
            "run", "execute", "test", "benchmark", "optimize"
        ]
        msg_lower = user_message.lower()
        return any(kw in msg_lower for kw in work_keywords)

    # ------------------------------------------------------------------
    # DELIBERATION
    # ------------------------------------------------------------------
    def run_deliberation(self, user_prompt, rounds=None):
        if rounds is None:
            rounds = self.rounds
        self.user_agenda = user_prompt
        self.deliberation_log = []
        self.history_summary = ""

        work_members = [m for m in self.members if m.name != "Greeter"]

        print(f"\n{'='*70}")
        print(f"COUNCIL WORK SESSION")
        print(f"Agenda: {user_prompt}")
        print(f"Members: {', '.join([m.name for m in work_members])}")
        stats = self.memory.get_stats()
        print(f"Memory: {stats['total_sessions']} sessions, {stats['total_lessons']} lessons")
        print(f"{'='*70}\n")

        file_context = self.files.build_context_prompt()
        enriched_agenda = user_prompt + (f"\n\n{file_context}" if file_context else "")

        if self.chat_history:
            chat_summary = "\n".join([f"  {msg['role']}: {msg['content'][:200]}" for msg in self.chat_history[-4:]])
            enriched_agenda += f"\n\n=== PRIOR CONVERSATION ===\n{chat_summary}\n=== END CONVERSATION ==="

        # === ROUND 1: PARALLEL OPENING STATEMENTS ===
        print(f"--- ROUND 1: OPENING STATEMENTS (PARALLEL) ---\n")

        def build_round1_messages(member):
            system = self.build_system_prompt(member, agenda=user_prompt, mode="work")
            user = (f"The council agenda is: {enriched_agenda}\n\n"
                    f"This is the opening round. Provide YOUR OWN initial assessment from YOUR specialty perspective. "
                    f"Do not speak for other members. Do not execute yet - planning only.")
            return [{"role": "system", "content": system},
                    {"role": "user", "content": user}]

        round1_results = {}
        with ThreadPoolExecutor(max_workers=len(work_members)) as executor:
            futures = {executor.submit(m.speak, build_round1_messages(m), 1.0, 0.95, False, self.debug): m for m in work_members}
            for future in as_completed(futures):
                member = futures[future]
                try:
                    round1_results[member.name] = future.result()
                except Exception as e:
                    round1_results[member.name] = f"[Error during opening statement: {e}]"

        for member in work_members:
            content = round1_results[member.name]
            print(f"[{member.name}]\n{content}\n")
            self.deliberation_log.append({"speaker": member.name, "content": content, "round": 1})

        # === ROUNDS 2+: SEQUENTIAL DELIBERATION ===
        for round_num in range(2, rounds + 2):
            print(f"--- ROUND {round_num}: DELIBERATION ---\n")
            for member in work_members:
                context = self._compress_history_for_member(member)
                messages = [{"role": "system", "content": self.build_system_prompt(member, agenda=user_prompt, mode="work")},
                            {"role": "user", "content": (f"Council Agenda: {enriched_agenda}\n\n"
                                                         f"Previous deliberation:\n{context}\n\n"
                                                         f"It is now YOUR turn ({member.name}) in Round {round_num}. "
                                                         f"Respond to your fellow members' points, refine proposals, raise concerns, "
                                                         f"or advance toward task assignments. Speak as YOURSELF only.")}]

                if self.streaming:
                    print(f"[{member.name}]\n", end="", flush=True)
                    content = member.speak_streaming(messages, debug=self.debug)
                else:
                    content = member.speak(messages, debug=self.debug)
                    print(f"[{member.name}]\n{content}\n")

                self.deliberation_log.append({"speaker": member.name, "content": content, "round": round_num})
                if self.streaming:
                    print()

        # === FINAL ROUND: TASK ASSIGNMENT ===
        print(f"--- FINAL ROUND: TASK ASSIGNMENT ---\n")
        for member in work_members:
            context = self._compress_history_for_member(member)
            messages = [{"role": "system", "content": self.build_system_prompt(member, agenda=user_prompt, mode="work")},
                        {"role": "user", "content": (f"Council Agenda: {enriched_agenda}\n\n"
                                                     f"Full deliberation record:\n{context}\n\n"
                                                     f"This is the FINAL ROUND. YOU ({member.name}) must formally state YOUR task assignment proposal. "
                                                     f"Be explicit about what YOU will do and what you assign to others. "
                                                     f"'I will handle X', 'Minimax should handle Y', 'Kimi should verify Z'.")}]

            if self.streaming:
                print(f"[{member.name}]\n", end="", flush=True)
                content = member.speak_streaming(messages, debug=self.debug)
            else:
                content = member.speak(messages, debug=self.debug)
                print(f"[{member.name}]\n{content}\n")

            self.deliberation_log.append({"speaker": member.name, "content": content, "round": "FINAL"})
            if self.streaming:
                print()

        # === CHAIR: STRUCTURED ASSIGNMENTS ===
        print(f"--- CHAIR: STRUCTURED ASSIGNMENTS ---\n")
        chair = next(m for m in self.members if m.name == "Nemotron")
        context = self._compress_history_for_member(chair)
        assignment_prompt = (f"You are {chair.name}, the Council Chair. Based on the full deliberation below, produce a FINAL, STRUCTURED task assignment in JSON. "
                             f"No commentary outside the JSON.\n\nFull deliberation:\n{context}\n\n"
                             f"Required JSON format:\n"
                             f"{{\n"
                             f'  "consensus_summary": "...",\n'
                             f'  "assignments": [\n'
                             f'    {{"member": "Name", "task": "...", "deliverable": "...", "rationale": "..."}},\n'
                             f'    ...\n'
                             f'  ],\n'
                             f'  "review_process": "...",\n'
                             f'  "final_output_plan": "..."\n'
                             f"}}")

        if self.streaming:
            print(f"[{chair.name} - ASSIGNMENTS]\n", end="", flush=True)
            assignment_json = chair.speak_streaming([{"role": "system", "content": self.build_system_prompt(chair, agenda=user_prompt, mode="work")},
                                         {"role": "user", "content": assignment_prompt}], temperature=0.3, debug=self.debug)
        else:
            assignment_json = chair.speak([{"role": "system", "content": self.build_system_prompt(chair, agenda=user_prompt, mode="work")},
                                         {"role": "user", "content": assignment_prompt}], temperature=0.3, debug=self.debug)
            print(f"[{chair.name} - ASSIGNMENTS]\n{assignment_json}\n")

        try:
            self.assignments = json.loads(assignment_json)
        except json.JSONDecodeError:
            self.assignments = {"raw_decision": assignment_json, "assignments": []}
        return self.assignments

    # ------------------------------------------------------------------
    # EXECUTION (Parallel)
    # ------------------------------------------------------------------
    def execute_assignments(self):
        print(f"\n{'='*70}")
        print(f"EXECUTION PHASE (PARALLEL)")
        print(f"{'='*70}\n")

        assignments_list = self.assignments.get("assignments", [])
        if not assignments_list:
            print("[Warning] No assignments to execute.")
            self.execution_results = {}
            return {}

        results = {}

        def execute_one(assignment):
            member_name = assignment.get("member")
            task = assignment.get("task")
            deliverable = assignment.get("deliverable", "complete output")
            member = next((m for m in self.members if m.name == member_name), None)
            if not member:
                return member_name, {"task": task, "output": f"[Error] Member {member_name} not found."}

            print(f"  → {member.name} starting: {task}")
            full_deliberation = self._compress_history_for_member(member)
            exec_prompt = (f"You are {member.name}, {member.title}.\n\n"
                           f"The council has assigned YOU:\nTASK: {task}\nDELIVERABLE: {deliverable}\n\n"
                           f"Original agenda: {self.user_agenda}\n\n"
                           f"Full deliberation for context:\n{full_deliberation}\n\n"
                           f"You have native tools available. Use them to execute your task.\n\n"
                           f"Execute YOUR task now. Produce the deliverable directly. Do not discuss - just produce the work.")
            messages = [{"role": "system", "content": self.build_system_prompt(member, agenda=self.user_agenda, mode="work")},
                        {"role": "user", "content": exec_prompt}]

            output = member.speak(messages, debug=self.debug)
            return member_name, {"task": task, "output": output}

        with ThreadPoolExecutor(max_workers=len(assignments_list)) as executor:
            futures = [executor.submit(execute_one, a) for a in assignments_list]
            for future in as_completed(futures):
                try:
                    member_name, result = future.result()
                    print(f"\n--- {member_name} COMPLETED ---")
                    print(result["output"])
                    print()
                    results[member_name] = result
                    self._parse_file_directives(result["output"])
                except Exception as e:
                    print(f"\n[Error] Execution task failed: {e}\n")

        self.execution_results = results
        return results

    def _parse_file_directives(self, text):
        for match in re.finditer(r'\[WRITE:\s*([^\]]+)\]\s*```(?:\w+)?\n(.*?)```', text, re.DOTALL):
            path = match.group(1).strip()
            content = match.group(2)
            result = self.files.write_file(path, content)
            print(f"  {result}")

        for match in re.finditer(r'\[READ:\s*([^\]]+)\]', text):
            path = match.group(1).strip()
            content = self.files.read_file(path, max_chars=5000)
            print(f"  [Read] {path} ({len(content)} chars)")

        for match in re.finditer(r'\[MKDIR:\s*([^\]]+)\]', text):
            path = match.group(1).strip()
            result = self.files.create_dir(path)
            print(f"  {result}")

        for match in re.finditer(r'\[DELETE:\s*([^\]]+)\]', text):
            path = match.group(1).strip()
            result = self.files.delete_file(path)
            print(f"  {result}")

    def finalize(self, execution_results):
        print(f"\n{'='*70}")
        print(f"FINAL SYNTHESIS")
        print(f"{'='*70}\n")
        results_text = "\n\n".join([f"--- {name} ---\nTask: {data['task']}\nOutput:\n{data['output']}"
                                    for name, data in execution_results.items()])
        chair = next(m for m in self.members if m.name == "Nemotron")
        final_prompt = (f"The council has completed execution. Individual outputs:\n\n{results_text}\n\n"
                        f"Synthesize into a single, coherent final response. Credit members. Ensure complete, accurate, actionable output.")

        if self.streaming:
            print(f"[{chair.name} - FINAL]\n", end="", flush=True)
            final_output = chair.speak_streaming([{"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                                    {"role": "user", "content": final_prompt}], debug=self.debug)
        else:
            final_output = chair.speak([{"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                                    {"role": "user", "content": final_prompt}], debug=self.debug)
            print(f"[{chair.name} - FINAL]\n{final_output}\n")

        self.final_output = final_output
        return final_output

    # ------------------------------------------------------------------
    # REFLECTION (Parallel)
    # ------------------------------------------------------------------
    def reflection_round(self):
        print(f"\n{'='*70}")
        print(f"REFLECTION & SELF-CORRECTION (PARALLEL)")
        print(f"{'='*70}\n")

        work_members = [m for m in self.members if m.name != "Greeter"]
        reflections = {}

        def reflect_one(member):
            context = self._compress_history_for_member(member)
            prompt = (f"You are {member.name}. The council just completed a session.\n\n"
                      f"Agenda: {self.user_agenda}\n\n"
                      f"Final output:\n{self.final_output}\n\n"
                      f"Execution results:\n{json.dumps(self.execution_results, indent=2)}\n\n"
                      f"Deliberation history:\n{context}\n\n"
                      f"CRITIQUE THIS SESSION from YOUR perspective. Be brutally honest:\n"
                      f"1. What went wrong or could be better?\n"
                      f"2. What mistakes did YOU make?\n"
                      f"3. What should YOU do differently next time?\n"
                      f"4. Propose a specific correction.\n"
                      f"Sign: - {member.name}")
            reflection = member.speak([{"role": "system", "content": self.build_system_prompt(member, agenda=self.user_agenda, mode="work")},
                                       {"role": "user", "content": prompt}], debug=self.debug)
            return member.name, reflection

        with ThreadPoolExecutor(max_workers=len(work_members)) as executor:
            futures = [executor.submit(reflect_one, m) for m in work_members]
            for future in as_completed(futures):
                try:
                    name, reflection = future.result()
                    print(f"[{name} REFLECTION]\n{reflection}\n")
                    reflections[name] = reflection
                except Exception as e:
                    print(f"[Error] Reflection failed for a member: {e}\n")

        self.reflections = [{"member": name, "reflection": r} for name, r in reflections.items()]

        chair = next(m for m in self.members if m.name == "Nemotron")
        synthesis_prompt = (f"You are {chair.name}, the Chair. Based on reflections below, produce structured JSON of lessons learned.\n\n"
                            f"Reflections:\n{json.dumps(self.reflections, indent=2)}\n\n"
                            f"Format: {{\"lessons\": [{{\"category\": \"...\", \"description\": \"...\", "
                            f"\"trigger\": \"...\", \"solution\": \"...\", \"members\": [\"...\"]}}, ...]}}")

        if self.streaming:
            print(f"[{chair.name} - LESSONS]\n", end="", flush=True)
            lessons_json = chair.speak_streaming([{"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                                    {"role": "user", "content": synthesis_prompt}], temperature=0.3, debug=self.debug)
        else:
            lessons_json = chair.speak([{"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                                    {"role": "user", "content": synthesis_prompt}], temperature=0.3, debug=self.debug)
            print(f"[{chair.name} - LESSONS]\n{lessons_json}\n")

        try:
            parsed = json.loads(lessons_json)
            count = 0
            for lesson in parsed.get("lessons", []):
                self.memory.add_lesson(category=lesson.get("category", "improvement"),
                                       description=lesson.get("description", ""),
                                       trigger=lesson.get("trigger", ""),
                                       solution=lesson.get("solution", ""),
                                       members_involved=lesson.get("members", []))
                count += 1
            print(f"[Memory] Saved {count} new lessons.\n")
        except json.JSONDecodeError:
            print(f"[Memory] Could not parse. Raw saved.\n")
            self.memory.add_lesson("improvement", "Raw reflection", "Session completion", lessons_json, [chair.name])

    def save_session(self, success=True):
        session_data = {"agenda": self.user_agenda, "members": [m.name for m in self.members],
                        "deliberation": self.deliberation_log, "assignments": self.assignments,
                        "execution_results": self.execution_results, "final_output": self.final_output,
                        "reflections": self.reflections, "success": success}
        session_id = self.memory.log_session(session_data)
        print(f"[Memory] Session saved: council_memory/sessions/{session_id}.json\n")
        return session_id

    def run(self, user_prompt, rounds=None):
        try:
            self.run_deliberation(user_prompt, rounds=rounds)
            self.execute_assignments()
            self.finalize(self.execution_results)
            self.reflection_round()
            self.save_session(success=True)
            return self.final_output
        except Exception as e:
            print(f"\n[ERROR] Council session failed: {e}")
            self.save_session(success=False)
            raise


# ===================================================================
# COUNCIL FACTORY
# ===================================================================

def build_council(memory_dir="council_memory", project_dir="."):
    memory = CouncilMemory(memory_dir=memory_dir)
    files = FileTools(project_dir=project_dir)
    native_tools = NativeTools(files)
    council = Council(memory=memory, file_tools=files)

    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1"

    # === Greeter: Llama 3.1 8B (known fast, proven on NVIDIA API) ===
    # DeepSeek V4 Flash was suspected slow despite name. Switched to proven fast model.
    greeter = CouncilMember(
        name="Greeter",
        title="Fast Conversational Interface & Gatekeeper",
        role="You are the council's fast, friendly conversational interface and sole gatekeeper. "
             "You handle all casual chat, quick questions, and brainstorming. "
             "You know the other council members (Nemotron, Minimax, Kimi) and can describe what they do. "
             "You are the ONLY model that decides whether the full council needs to activate. "
             "When work is needed, you emit [WORK_MODE] marker so the council can take over.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="meta/llama-3.1-8b-instruct",  # PROVEN FAST on NVIDIA API
        max_tokens=1024,
        context_window=128000,
        native_tools=native_tools,
        extra_body={}  # No thinking overhead
    )

    nemotron = CouncilMember(
        name="Nemotron",
        title="Council Chair & Strategic Overseer",
        role="You facilitate the council, ensure all voices are heard, and have the final say on task assignments. "
             "You excel at long-term planning, error recovery, and maintaining thread continuity. "
             "You synthesize diverse inputs into coherent strategy and produce the final unified output.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="nvidia/nemotron-3-ultra-550b-a55b", max_tokens=16384, context_window=128000,
        native_tools=native_tools,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
    )

    minimax = CouncilMember(
        name="Minimax",
        title="Multimodal Synthesizer & Systems Builder",
        role="You handle massive codebases, complex datasets, and native image/video processing. "
             "You build dynamic systems based on the council's strategic direction. "
             "You are the council's hands - you write code, process data, and construct artifacts. "
             "Your 1-million-token context window makes you the council historian for long sessions.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="minimaxai/minimax-m3", max_tokens=8192, context_window=1000000,
        native_tools=native_tools
    )

    kimi = CouncilMember(
        name="Kimi",
        title="Chief Analyst & Logic Verifier",
        role="You provide deep analytical reasoning, critique proposals for logical consistency, "
             "and verify the soundness of plans before execution. You are the council's devil's advocate "
             "and fact-checker. You ensure no flawed logic survives deliberation.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="moonshotai/kimi-k2.6", max_tokens=16384, context_window=256000,
        native_tools=native_tools
    )

    council.add_member(greeter)
    council.add_member(nemotron)
    council.add_member(minimax)
    council.add_member(kimi)

    return council


# ===================================================================
# INTERACTIVE REPL
# ===================================================================

def print_banner():
    print(r"""
   ____                  _       _   _             _     
  / ___|___  _   _ _ __ | |_ ___| | | | ___   __ _| | __ 
 | |   / _ \| | | | '_ \| __/ __| |_| |/ _ \ / _` | |/ / 
 | |__| (_) | |_| | | | | |_\__ \  _  | (_) | (_| |   <  
  \____\___/ \__,_|_| |_|\__|___/_| |_|\___/ \__,_|_|\_\ 

  Project Love v4.4.6  |  NVIDIA API  |  Diagnostics |  Llama 3.1 8B Greeter
""")
    print("Type /help for commands. /debug on to see timing. Chat naturally, or ask for work.\n")


def repl(council: Council):
    print_banner()

    while True:
        try:
            user_input = input("council> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Goodbye]")
            break

        if not user_input:
            continue

        # Command parsing
        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            if cmd in ("/quit", "/exit", "/q"):
                print("[Goodbye] Council session ended.")
                break

            elif cmd == "/help":
                print("""
Commands:
  /add <file>          Add a file to council context
  /drop <file>         Remove a file from context
  /files               List files in context
  /tree                Show project file tree
  /council             Show current council members
  /memory              Show lessons learned stats
  /reset               Clear session context (keep memory)
  /save                Force save session to disk
  /rounds <n>          Set deliberation rounds (default: 2)
  /mode auto|chat|work Toggle response mode
  /stream on|off       Toggle streaming output (default: on)
  /debug on|off        Show API timing diagnostics (default: off)
  /quit, /exit         Leave the council

Modes:
  auto  (default) — Greeter decides: chat instantly, or trigger council for work
  chat  — Always chat with Greeter (fastest)
  work  — Always run full council deliberation

Diagnostics:
  /debug on  — Shows [Greeter] TTFT: 0.32s | Total: 1.2s for every call
""")

            elif cmd == "/add":
                if not args:
                    print("[Error] Usage: /add <filepath>")
                else:
                    for arg in args:
                        print(council.files.add_to_context(arg))

            elif cmd == "/drop":
                if not args:
                    print("[Error] Usage: /drop <filepath>")
                else:
                    for arg in args:
                        print(council.files.drop_from_context(arg))

            elif cmd == "/files":
                print(council.files.list_context())

            elif cmd == "/tree":
                print(council.files.tree())

            elif cmd == "/council":
                print(f"[Council] {len(council.members)} members:")
                for m in council.members:
                    print(f"  - {m.name}: {m.title} (context: {m.context_window:,} | output: {m.max_tokens:,})")
                print(f"[Mode] Current mode: {council.mode}")
                print(f"[Stream] Streaming: {'on' if council.streaming else 'off'}")
                print(f"[Debug] Diagnostics: {'on' if council.debug else 'off'}")

            elif cmd == "/memory":
                stats = council.memory.get_stats()
                print(f"[Memory] Sessions: {stats['total_sessions']} | Lessons: {stats['total_lessons']} | Corrections: {stats['total_corrections']}")
                print(f"[Memory] Directory: {stats['memory_dir']}")

            elif cmd == "/reset":
                council.deliberation_log = []
                council.assignments = {}
                council.execution_results = {}
                council.final_output = ""
                council.chat_history = []
                council.files.context_files = set()
                print("[Reset] Session context cleared. Memory and lessons preserved.")

            elif cmd == "/save":
                if council.user_agenda:
                    council.save_session(success=True)
                else:
                    print("[Error] No active session to save.")

            elif cmd == "/rounds":
                if args and args[0].isdigit():
                    council.rounds = int(args[0])
                    print(f"[Config] Deliberation rounds set to {council.rounds}")
                else:
                    print(f"[Config] Current rounds: {council.rounds}")

            elif cmd == "/mode":
                if args:
                    new_mode = args[0].lower()
                    if new_mode in ("auto", "chat", "work"):
                        council.mode = new_mode
                        print(f"[Mode] Switched to {new_mode} mode.")
                    else:
                        print("[Error] Mode must be 'auto', 'chat', or 'work'")
                else:
                    print(f"[Mode] Current mode: {council.mode}")

            elif cmd == "/stream":
                if args:
                    new_stream = args[0].lower()
                    if new_stream in ("on", "off"):
                        council.streaming = (new_stream == "on")
                        print(f"[Stream] Streaming turned {'on' if council.streaming else 'off'}.")
                    else:
                        print("[Error] Stream must be 'on' or 'off'")
                else:
                    print(f"[Stream] Streaming: {'on' if council.streaming else 'off'}")

            elif cmd == "/debug":
                if args:
                    new_debug = args[0].lower()
                    if new_debug in ("on", "off"):
                        council.debug = (new_debug == "on")
                        print(f"[Debug] Diagnostics turned {'on' if council.debug else 'off'}.")
                    else:
                        print("[Error] Debug must be 'on' or 'off'")
                else:
                    print(f"[Debug] Diagnostics: {'on' if council.debug else 'off'}")

            else:
                print(f"[Error] Unknown command: {cmd}. Type /help for available commands.")

        else:
            # Natural language input
            if council.mode == "work":
                try:
                    result = council.run(user_input, rounds=council.rounds)
                    print("\n" + "="*70)
                    print("FINAL ANSWER")
                    print("="*70)
                    print(result)
                    print("="*70 + "\n")
                except Exception as e:
                    print(f"\n[Error] Council failed: {e}\n")

            elif council.mode == "chat":
                try:
                    council.chat(user_input, gatekeeper=False)
                except Exception as e:
                    print(f"\n[Error] Chat failed: {e}\n")

            else:
                # AUTO mode
                try:
                    response = council.chat(user_input, gatekeeper=True)

                    import re
                    # Use regex to catch typos like [WWORK_MODE] or WORK_MODE
                    if re.search(r'\[?W*ORK_MODE\]?', response.upper()):
                        parts = re.split(r'\[?W*ORK_MODE\]?', response.upper())
                        work_summary = parts[-1].strip() if len(parts) > 1 else user_input
                        print(f"\n[Council] Greeter escalated to work mode. Activating council...\n")
                        result = council.run(work_summary, rounds=council.rounds)
                        print("\n" + "="*70)
                        print("FINAL ANSWER")
                        print("="*70)
                        print(result)
                        print("="*70 + "\n")
                except Exception as e:
                    print(f"\n[Error] Auto mode failed: {e}\n")


# ===================================================================
# CLI ENTRY POINT
# ===================================================================

def main():
    parser = argparse.ArgumentParser(
        description="CounciL Strategic Systems - Project Love v4.4.6. Diagnostics + fast Greeter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python council.py                    # Start interactive REPL (auto mode)
  python council.py --project ./myapp  # Start in project directory
  python council.py --mode chat        # Force chat mode
  python council.py --mode work        # Force work mode
        """
    )
    parser.add_argument("--project", "-p", type=str, default=".", help="Project directory (default: current)")
    parser.add_argument("--memory-dir", "-m", type=str, default="council_memory", help="Memory directory")
    parser.add_argument("--rounds", "-r", type=int, default=2, help="Default deliberation rounds")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "chat", "work"], help="Start mode: auto, chat, or work")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming (wait for full response)")
    parser.add_argument("--debug", action="store_true", help="Enable API timing diagnostics")
    args = parser.parse_args()

    print(f"[CLI] Initializing Council...")
    print(f"[CLI] Project: {Path(args.project).resolve()}")
    print(f"[CLI] Memory:  {args.memory_dir}")
    print(f"[CLI] API:     NVIDIA (integrate.api.nvidia.com)")
    print(f"[CLI] Greeter: Llama 3.1 8B (proven fast)")

    council = build_council(memory_dir=args.memory_dir, project_dir=args.project)
    council.rounds = args.rounds
    council.mode = args.mode
    council.streaming = not args.no_stream
    council.debug = args.debug

    repl(council)


if __name__ == "__main__":
    main()