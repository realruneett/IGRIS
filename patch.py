import re

with open("council.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add imports
imports_addition = """import argparse
import urllib.request
import urllib.parse
from html.parser import HTMLParser"""
content = content.replace("import argparse", imports_addition, 1)

# 2. Add NativeTools before FileTools
native_tools_code = """# ===================================================================
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
        return "\\n".join(items)

    def delete_file(self, filepath):
        return self.files.delete_file(filepath)
    
    def fetch_url(self, url):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                parser = WebTextParser()
                parser.feed(html)
                return "\\n".join(parser.text)[:20000]
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
                    results.append(f"URL: {link}\\nSnippet: {snippet.strip()}")
                return "\\n\\n".join(results[:5]) if results else "No results found."
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
# ==================================================================="""

content = content.replace("# ===================================================================\n# FILE SYSTEM TOOLS\n# ===================================================================", native_tools_code, 1)

# 3. Update CouncilMember __init__
init_old = """    def __init__(self, name, title, role, client, model, max_tokens, context_window, extra_body=None):
        self.name = name
        self.title = title
        self.role = role
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.extra_body = extra_body or {}
        self.resilient = ResilientClient(client, name=name, max_retries=3, base_delay=1.0)"""

init_new = """    def __init__(self, name, title, role, client, model, max_tokens, context_window, native_tools=None, extra_body=None):
        self.name = name
        self.title = title
        self.role = role
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.extra_body = extra_body or {}
        self.resilient = ResilientClient(client, name=name, max_retries=3, base_delay=1.0)
        self.native_tools = native_tools"""
content = content.replace(init_old, init_new, 1)

# 4. Update CouncilMember speak
speak_old = """    def speak(self, messages, temperature=1.0, top_p=0.95, stream=False, debug=False):
        messages = self._estimate_and_guard(messages)
        kwargs = {"model": self.model, "messages": messages, "temperature": temperature,
                  "top_p": top_p, "max_tokens": self.max_tokens, "stream": stream}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body

        if debug:
            prompt_size = estimate_messages_tokens(messages)
            print(f"  [DEBUG {self.name}] Prompt: {prompt_size:,} tokens | Model: {self.model} | Stream: {stream}")

        start_time = time.time()
        first_token_time = None

        try:
            response = self.resilient.chat_completions_create(**kwargs)
            if stream:
                return response, start_time
            else:
                result = response.choices[0].message.content
                elapsed = time.time() - start_time
                print(f"  [{self.name}] TTFT+Gen: {elapsed:.1f}s | {estimate_tokens(result)} tokens")
                return result
        except Exception as e:
            error_msg = f"[{self.name}] API call failed: {str(e)[:200]}"
            print(f"  {error_msg}")
            return f"[ERROR: {self.name} could not respond: {str(e)[:100]}]\""""

speak_new = """    def speak(self, messages, temperature=1.0, top_p=0.95, stream=False, debug=False):
        import json
        messages_copy = messages.copy()
        total_content = ""

        while True:
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
                        print(f"\\n  [{self.name} TOOL CALL] {fn_name}({fn_args[:100]}...)")
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
                    continue # self-correct loop
                
                elapsed = time.time() - start_time
                final_res = total_content or msg.content or ""
                print(f"  [{self.name}] TTFT+Gen: {elapsed:.1f}s | {estimate_tokens(final_res)} tokens")
                return final_res

            except Exception as e:
                error_msg = f"[{self.name}] API call failed: {str(e)[:200]}"
                print(f"  {error_msg}")
                return f"[ERROR: {self.name} could not respond: {str(e)[:100]}]" """
content = content.replace(speak_old, speak_new, 1)


# 5. Update CouncilMember speak_streaming
speak_streaming_old = """    def speak_streaming(self, messages, temperature=1.0, top_p=0.95, debug=False):
        messages = self._estimate_and_guard(messages)
        kwargs = {"model": self.model, "messages": messages, "temperature": temperature,
                  "top_p": top_p, "max_tokens": self.max_tokens, "stream": True}
        if self.extra_body:
            kwargs["extra_body"] = self.extra_body

        if debug:
            prompt_size = estimate_messages_tokens(messages)
            print(f"  [DEBUG {self.name}] Prompt: {prompt_size:,} tokens | Model: {self.model} | Stream: True")

        start_time = time.time()
        first_token_printed = False

        try:
            response = self.resilient.chat_completions_create(**kwargs)
            full_text = ""
            for chunk in response:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta
                content = getattr(delta, "content", None)
                if content:
                    if not first_token_printed:
                        ttft = time.time() - start_time
                        print(f"  [{self.name}] TTFT: {ttft:.2f}s", end="\\r")
                        first_token_printed = True
                    print(content, end="", flush=True)
                    full_text += content
            total_time = time.time() - start_time
            token_count = estimate_tokens(full_text)
            print(f"\\n  [{self.name}] Total: {total_time:.1f}s | {token_count} tokens | ~{token_count/max(total_time,0.1):.0f} tok/s")
            return full_text
        except Exception as e:
            print(f"  [{self.name}] Streaming failed: {str(e)[:100]}")
            return self.speak(messages, temperature, top_p, stream=False, debug=debug)"""

speak_streaming_new = """    def speak_streaming(self, messages, temperature=1.0, top_p=0.95, debug=False):
        import json
        messages_copy = messages.copy()
        session_full_text = ""

        while True:
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
                                tool_calls_buffer[idx] = {"id": tc.id, "type": "function", "function": {"name": tc.function.name or "", "arguments": ""}}
                            if getattr(tc.function, "name", None):
                                tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                            if getattr(tc.function, "arguments", None):
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments
                    
                    content = getattr(delta, "content", None)
                    if content:
                        if not first_token_printed:
                            ttft = time.time() - start_time
                            print(f"  [{self.name}] TTFT: {ttft:.2f}s", end="\\r")
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
                        print(f"\\n  [{self.name} TOOL CALL] {fn_name}({fn_args[:100]}...)")
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
                    continue # self-correct loop
                else:
                    total_time = time.time() - start_time
                    token_count = estimate_tokens(session_full_text)
                    print(f"\\n  [{self.name}] Total: {total_time:.1f}s | {token_count} tokens | ~{token_count/max(total_time,0.1):.0f} tok/s")
                    return session_full_text
            except Exception as e:
                print(f"  [{self.name}] Streaming failed: {str(e)[:100]}")
                return self.speak(messages_copy, temperature, top_p, stream=False, debug=debug)"""
content = content.replace(speak_streaming_old, speak_streaming_new, 1)

# 6. Update build_council
build_old = """def build_council(memory_dir="council_memory", project_dir="."):
    memory = CouncilMemory(memory_dir=memory_dir)
    files = FileTools(project_dir=project_dir)
    council = Council(memory=memory, file_tools=files)

    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1\""""

build_new = """def build_council(memory_dir="council_memory", project_dir="."):
    memory = CouncilMemory(memory_dir=memory_dir)
    files = FileTools(project_dir=project_dir)
    native_tools = NativeTools(files)
    council = Council(memory=memory, file_tools=files)

    NVIDIA_BASE_URL = "https://integrate.api.nvidia.com/v1\""""
content = content.replace(build_old, build_new, 1)

greeter_old = """    greeter = CouncilMember(
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
        extra_body={}  # No thinking overhead
    )"""

greeter_new = """    greeter = CouncilMember(
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
    )"""
content = content.replace(greeter_old, greeter_new, 1)

nemotron_old = """    nemotron = CouncilMember(
        name="Nemotron",
        title="Council Chair & Strategic Overseer",
        role="You facilitate the council, ensure all voices are heard, and have the final say on task assignments. "
             "You excel at long-term planning, error recovery, and maintaining thread continuity. "
             "You synthesize diverse inputs into coherent strategy and produce the final unified output.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="nvidia/nemotron-3-ultra-550b-a55b", max_tokens=16384, context_window=128000,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
    )"""

nemotron_new = """    nemotron = CouncilMember(
        name="Nemotron",
        title="Council Chair & Strategic Overseer",
        role="You facilitate the council, ensure all voices are heard, and have the final say on task assignments. "
             "You excel at long-term planning, error recovery, and maintaining thread continuity. "
             "You synthesize diverse inputs into coherent strategy and produce the final unified output.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="nvidia/nemotron-3-ultra-550b-a55b", max_tokens=16384, context_window=128000,
        native_tools=native_tools,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384}
    )"""
content = content.replace(nemotron_old, nemotron_new, 1)

minimax_old = """    minimax = CouncilMember(
        name="Minimax",
        title="Multimodal Synthesizer & Systems Builder",
        role="You handle massive codebases, complex datasets, and native image/video processing. "
             "You build dynamic systems based on the council's strategic direction. "
             "You are the council's hands - you write code, process data, and construct artifacts. "
             "Your 1-million-token context window makes you the council historian for long sessions.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="minimaxai/minimax-m3", max_tokens=8192, context_window=1000000
    )"""

minimax_new = """    minimax = CouncilMember(
        name="Minimax",
        title="Multimodal Synthesizer & Systems Builder",
        role="You handle massive codebases, complex datasets, and native image/video processing. "
             "You build dynamic systems based on the council's strategic direction. "
             "You are the council's hands - you write code, process data, and construct artifacts. "
             "Your 1-million-token context window makes you the council historian for long sessions.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="minimaxai/minimax-m3", max_tokens=8192, context_window=1000000,
        native_tools=native_tools
    )"""
content = content.replace(minimax_old, minimax_new, 1)

kimi_old = """    kimi = CouncilMember(
        name="Kimi",
        title="Chief Analyst & Logic Verifier",
        role="You provide deep analytical reasoning, critique proposals for logical consistency, "
             "and verify the soundness of plans before execution. You are the council's devil's advocate "
             "and fact-checker. You ensure no flawed logic survives deliberation.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="moonshotai/kimi-k2.6", max_tokens=16384, context_window=256000
    )"""

kimi_new = """    kimi = CouncilMember(
        name="Kimi",
        title="Chief Analyst & Logic Verifier",
        role="You provide deep analytical reasoning, critique proposals for logical consistency, "
             "and verify the soundness of plans before execution. You are the council's devil's advocate "
             "and fact-checker. You ensure no flawed logic survives deliberation.",
        client=OpenAI(base_url=NVIDIA_BASE_URL, api_key="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"),
        model="moonshotai/kimi-k2.6", max_tokens=16384, context_window=256000,
        native_tools=native_tools
    )"""
content = content.replace(kimi_old, kimi_new, 1)

# 7. Update build_system_prompt
sys_old = """                    f"You have access to the project file system. You can read files, write files, create directories, and delete files.\\n"
                    f"When you need to see a file, reference it by path.\\n\\n"
                    f"Rules of engagement:\\n"
                    f"1. Address other members by name when responding to their points.\\n"
                    f"2. Stay in your role. Do not perform another member's specialty.\\n"
                    f"3. You may propose, object, support, refine, or ask clarifying questions.\\n"
                    f"4. Be concise but thorough. End your turn with a clear position, proposal, or question.\\n"
                    f"5. During task assignment, explicitly state which tasks you claim or assign to others.\\n"
                    f"6. Maintain defense-grade precision and highly analytical reasoning.\\n"
                    f"7. Sign your name at the end of every response: - {speaker.name}")"""

sys_new = """                    f"You have FULL NATIVE TOOL ACCESS. You can use your function calling tools to read files, write files, list directories, and search the web natively!\\n"
                    f"If a tool fails, you will see the error and can try again. Do actual work dynamically during the deliberation phase.\\n\\n"
                    f"Rules of engagement:\\n"
                    f"1. Address other members by name when responding to their points.\\n"
                    f"2. Stay in your role. Do not perform another member's specialty.\\n"
                    f"3. You may propose, object, support, refine, or ask clarifying questions.\\n"
                    f"4. Be concise but thorough. End your turn with a clear position, proposal, or question.\\n"
                    f"5. During task assignment, explicitly state which tasks you claim or assign to others.\\n"
                    f"6. Maintain defense-grade precision and highly analytical reasoning.\\n"
                    f"7. Use your tools to verify facts instead of guessing.\\n"
                    f"8. Sign your name at the end of every response: - {speaker.name}")"""
content = content.replace(sys_old, sys_new, 1)

exec_old = """                           f"You have full file system access. You can:\\n"
                           f"- Write files: [WRITE: path] followed by code in triple backticks\\n"
                           f"- Read files: [READ: path]\\n"
                           f"- Create directories: [MKDIR: path]\\n"
                           f"- Delete files: [DELETE: path]\\n\\n"
                           f"Execute YOUR task now. Produce the deliverable directly. Do not discuss - just produce the work.")"""

exec_new = """                           f"You have native tools available. Use them to execute your task.\\n\\n"
                           f"Execute YOUR task now. Produce the deliverable directly. Do not discuss - just produce the work.")"""
content = content.replace(exec_old, exec_new, 1)


with open("council.py", "w", encoding="utf-8") as f:
    f.write(content)
print("Patch complete.")
