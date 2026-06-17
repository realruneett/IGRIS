#!/usr/bin/env python3
"""
IGRIS v6.0 — SELF-EVOLVING AI COUNCIL
"The Lords Talk, The Lords Code, The Lords Improve Themselves"

Speed Targets (based on NVIDIA API benchmarks):
- Greeter (Llama 3.1 8B): ~50-120 tok/s | TTFT: 0.2-0.5s
- Nemotron (70B): ~15-30 tok/s | TTFT: 1-2s  
- Minimax M3 (1M ctx): ~10-20 tok/s | TTFT: 2-4s
- Kimi K2.6: ~20-40 tok/s | TTFT: 0.5-1s

Self-Evolution Features:
1. Council can read/write its OWN source code
2. Auto-detects performance bottlenecks and optimizes
3. Self-testing: runs pytest on its own modules
4. Genetic algorithm for prompt tuning
5. Auto-upgrades its own architecture
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import ast
import inspect
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict

from openai import OpenAI, APIError

VERSION = "6.0.0-EVO"
APP_NAME = "IGRIS-EVO"
DEFAULT_MEMORY_DIR = ".igris/memory"
DEFAULT_CONFIG_FILE = ".igris/config.json"
SELF_SOURCE_PATH = Path(__file__).resolve()

# ===================================================================
# SPEED BENCHMARKING & DIAGNOSTICS
# ===================================================================

@dataclass
class SpeedProfile:
    """Tracks actual vs expected speed for each member."""
    member: str
    model: str
    expected_tok_s: float
    actual_tok_s: float = 0.0
    ttft_ms: float = 0.0
    total_tokens: int = 0
    total_time: float = 0.0
    timestamp: str = ""

    def efficiency(self) -> float:
        return (self.actual_tok_s / self.expected_tok_s * 100) if self.expected_tok_s > 0 else 0

    def is_slow(self) -> bool:
        return self.efficiency() < 50  # Less than 50% of expected speed


class SpeedMonitor:
    """Monitors and optimizes council speed. Can trigger model swaps."""

    BASELINE_SPEEDS = {
        "meta/llama-3.1-8b-instruct": {"tok_s": 100, "ttft_ms": 300},
        "nvidia/nemotron-3-ultra-550b-a55b": {"tok_s": 25, "ttft_ms": 1500},
        "minimaxai/minimax-m3": {"tok_s": 15, "ttft_ms": 3000},
        "moonshotai/kimi-k2.6": {"tok_s": 30, "ttft_ms": 800},
    }

    def __init__(self, memory_dir: str = DEFAULT_MEMORY_DIR):
        self.profiles: List[SpeedProfile] = []
        self.speed_log = Path(memory_dir) / "speed_benchmarks.jsonl"
        self.optimization_history = Path(memory_dir) / "optimizations.json"
        self.load_history()

    def load_history(self):
        if self.optimization_history.exists():
            try:
                with open(self.optimization_history, "r") as f:
                    self._history = json.load(f)
            except:
                self._history = {"swaps": [], "prompt_optimizations": []}
        else:
            self._history = {"swaps": [], "prompt_optimizations": []}

    def record(self, member: str, model: str, tokens: int, time_sec: float, ttft_sec: float):
        baseline = self.BASELINE_SPEEDS.get(model, {"tok_s": 20, "ttft_ms": 1000})
        profile = SpeedProfile(
            member=member,
            model=model,
            expected_tok_s=baseline["tok_s"],
            actual_tok_s=tokens / max(time_sec, 0.001),
            ttft_ms=ttft_sec * 1000,
            total_tokens=tokens,
            total_time=time_sec,
            timestamp=datetime.now().isoformat()
        )
        self.profiles.append(profile)

        # Log to file
        with open(self.speed_log, "a") as f:
            f.write(json.dumps(asdict(profile)) + "\n")

        return profile

    def get_recommendations(self) -> List[Dict]:
        """Returns optimization recommendations based on speed data."""
        recs = []
        for p in self.profiles:
            if p.is_slow():
                recs.append({
                    "member": p.member,
                    "issue": f"Running at {p.efficiency():.0f}% efficiency",
                    "recommendation": self._suggest_swap(p.model),
                    "data": asdict(p)
                })
        return recs

    def _suggest_swap(self, current_model: str) -> str:
        """Suggest faster alternative based on benchmarks."""
        swaps = {
            "nvidia/nemotron-3-ultra-550b-a55b": "meta/llama-3.1-8b-instruct (for non-critical tasks)",
            "minimaxai/minimax-m3": "moonshotai/kimi-k2.6 (for smaller contexts)",
        }
        return swaps.get(current_model, "Consider reducing max_tokens or context window")

    def should_trigger_self_optimization(self) -> bool:
        """Returns True if council is consistently slow enough to warrant self-modification."""
        if len(self.profiles) < 3:
            return False
        recent = self.profiles[-3:]
        avg_efficiency = sum(p.efficiency() for p in recent) / len(recent)
        return avg_efficiency < 40  # Less than 40% efficiency triggers evolution


# ===================================================================
# SELF-MODIFICATION ENGINE
# ===================================================================

class SelfEvolutionEngine:
    """
    Allows the council to read, modify, and improve its own source code.
    This is the JARVIS-level feature - the AI improves itself.
    """

    def __init__(self, source_path: Path = SELF_SOURCE_PATH):
        self.source_path = source_path
        self.backup_dir = source_path.parent / ".igris" / "backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.change_log = source_path.parent / ".igris" / "evolution_log.jsonl"
        self._source_cache = None
        self._last_hash = None

    def get_current_source(self) -> str:
        """Returns the current source code of IGRIS itself."""
        if self._source_cache is None or self._hash_changed():
            with open(self.source_path, "r", encoding="utf-8") as f:
                self._source_cache = f.read()
                self._last_hash = hashlib.sha256(self._source_cache.encode()).hexdigest()
        return self._source_cache

    def _hash_changed(self) -> bool:
        try:
            with open(self.source_path, "rb") as f:
                current_hash = hashlib.sha256(f.read()).hexdigest()
            return current_hash != self._last_hash
        except:
            return True

    def get_module_structure(self) -> Dict:
        """Returns AST-parsed structure of the source code."""
        source = self.get_current_source()
        try:
            tree = ast.parse(source)
            structure = {
                "classes": [],
                "functions": [],
                "imports": [],
                "total_lines": len(source.splitlines()),
                "file_size": len(source)
            }
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    structure["classes"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.FunctionDef) and node.col_offset == 0:
                    structure["functions"].append({
                        "name": node.name,
                        "line": node.lineno,
                        "args": [arg.arg for arg in node.args.args]
                    })
                elif isinstance(node, (ast.Import, ast.ImportFrom)):
                    structure["imports"].append(ast.unparse(node))
            return structure
        except SyntaxError as e:
            return {"error": str(e), "total_lines": len(source.splitlines())}

    def create_backup(self, reason: str = "pre-evolution") -> Path:
        """Creates a timestamped backup before any self-modification."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = self.backup_dir / f"igris_v6_backup_{timestamp}_{reason}.py"
        with open(self.source_path, "r", encoding="utf-8") as src:
            with open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        return backup_path

    def apply_patch(self, patch_description: str, old_code: str, new_code: str, 
                    member_name: str = "Unknown") -> Dict:
        """
        Applies a code patch to IGRIS itself. Creates backup first.
        Returns success/failure with details.
        """
        source = self.get_current_source()

        # Safety: verify old_code exists
        if old_code not in source:
            return {
                "success": False,
                "error": "Old code block not found in source",
                "patch": patch_description,
                "attempted_by": member_name
            }

        # Create backup
        backup = self.create_backup(f"patch_by_{member_name}")

        # Apply patch
        new_source = source.replace(old_code, new_code, 1)

        # Verify syntax before saving
        try:
            compile(new_source, str(self.source_path), "exec")
        except SyntaxError as e:
            return {
                "success": False,
                "error": f"Syntax error in patched code: {e}",
                "backup": str(backup),
                "patch": patch_description
            }

        # Save new source
        with open(self.source_path, "w", encoding="utf-8") as f:
            f.write(new_source)

        # Log the change
        change_record = {
            "timestamp": datetime.now().isoformat(),
            "member": member_name,
            "description": patch_description,
            "backup": str(backup),
            "old_hash": self._last_hash,
            "new_hash": hashlib.sha256(new_source.encode()).hexdigest(),
            "lines_changed": len(old_code.splitlines())
        }
        with open(self.change_log, "a") as f:
            f.write(json.dumps(change_record) + "\n")

        # Invalidate cache
        self._source_cache = None
        self._last_hash = None

        return {
            "success": True,
            "backup": str(backup),
            "patch": patch_description,
            "lines_changed": len(old_code.splitlines()),
            "new_total_lines": len(new_source.splitlines())
        }

    def run_self_tests(self) -> Dict:
        """Runs the council's own test suite to verify self-modifications."""
        results = {
            "syntax_check": False,
            "import_check": False,
            "class_check": False,
            "tests_passed": 0,
            "tests_failed": 0,
            "errors": []
        }

        source = self.get_current_source()

        # Test 1: Syntax
        try:
            compile(source, str(self.source_path), "exec")
            results["syntax_check"] = True
        except SyntaxError as e:
            results["errors"].append(f"Syntax error: {e}")
            return results

        # Test 2: Can we import ourselves?
        try:
            # Write to temp and import
            import importlib.util
            spec = importlib.util.spec_from_file_location("igris_self", self.source_path)
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            results["import_check"] = True

            # Test 3: Check key classes exist
            required_classes = ['Council', 'CouncilMember', 'CouncilMemory', 'SelfEvolutionEngine']
            found_classes = [name for name in required_classes if hasattr(module, name)]
            results["class_check"] = len(found_classes) == len(required_classes)
            if not results["class_check"]:
                missing = set(required_classes) - set(found_classes)
                results["errors"].append(f"Missing classes: {missing}")

            results["tests_passed"] = sum([
                results["syntax_check"],
                results["import_check"],
                results["class_check"]
            ])

        except Exception as e:
            results["errors"].append(f"Import error: {e}")

        results["tests_failed"] = 3 - results["tests_passed"]
        return results

    def get_evolution_history(self, limit: int = 10) -> List[Dict]:
        """Returns recent self-modification history."""
        if not self.change_log.exists():
            return []
        changes = []
        with open(self.change_log, "r") as f:
            for line in f:
                if line.strip():
                    changes.append(json.loads(line))
        return changes[-limit:]

    def get_available_backups(self) -> List[Path]:
        """Returns list of available backup files."""
        return sorted(self.backup_dir.glob("igris_v6_backup_*.py"))

    def rollback(self, backup_path: Optional[Path] = None) -> Dict:
        """Rolls back to a previous version."""
        if backup_path is None:
            backups = self.get_available_backups()
            if not backups:
                return {"success": False, "error": "No backups available"}
            backup_path = backups[-1]

        if not backup_path.exists():
            return {"success": False, "error": f"Backup not found: {backup_path}"}

        with open(backup_path, "r", encoding="utf-8") as src:
            with open(self.source_path, "w", encoding="utf-8") as dst:
                dst.write(src.read())

        self._source_cache = None
        self._last_hash = None

        return {
            "success": True,
            "rolled_back_to": str(backup_path),
            "timestamp": datetime.now().isoformat()
        }


# ===================================================================
# SELF-EVOLUTION TOOLS (Added to NativeTools)
# ===================================================================

class EvolutionTools:
    """Additional tools for self-modification and evolution."""

    def __init__(self, evolution_engine: SelfEvolutionEngine, speed_monitor: SpeedMonitor):
        self.evo = evolution_engine
        self.speed = speed_monitor

    def get_tools_schema(self) -> List[Dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "read_own_source",
                    "description": "Read the source code of IGRIS itself to understand its architecture",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "section": {"type": "string", "description": "Class name or function name to focus on (optional)"},
                            "max_lines": {"type": "integer", "description": "Maximum lines to return", "default": 100}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_module_structure",
                    "description": "Get AST-parsed structure of IGRIS source code",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "apply_self_patch",
                    "description": "Modify IGRIS's own source code. EXTREME CAUTION. Creates backup first.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string", "description": "What this patch does"},
                            "old_code": {"type": "string", "description": "Exact code block to replace"},
                            "new_code": {"type": "string", "description": "New code to insert"}
                        },
                        "required": ["description", "old_code", "new_code"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "run_self_tests",
                    "description": "Run IGRIS's self-test suite to verify code changes",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_speed_report",
                    "description": "Get current speed performance report for all council members",
                    "parameters": {"type": "object", "properties": {}}
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "rollback_to_backup",
                    "description": "Rollback IGRIS to a previous backup version if changes break something",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "backup_index": {"type": "integer", "description": "Which backup to use (-1 for latest)", "default": -1}
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "get_evolution_history",
                    "description": "Get history of self-modifications made by the council",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "limit": {"type": "integer", "description": "Number of changes to return", "default": 10}
                        }
                    }
                }
            }
        ]

    def execute_tool(self, name: str, args: Dict[str, Any], member_name: str = "Unknown") -> str:
        if name == "read_own_source":
            source = self.evo.get_current_source()
            section = args.get("section", "")
            max_lines = args.get("max_lines", 100)

            if section:
                # Find the section
                pattern = rf'(class {section}|def {section})\b'
                match = re.search(pattern, source)
                if match:
                    start = match.start()
                    lines = source[start:].splitlines()[:max_lines]
                    return "\n".join(lines)
                return f"[Error] Section '{section}' not found"

            lines = source.splitlines()[:max_lines]
            return "\n".join(lines)

        elif name == "get_module_structure":
            return json.dumps(self.evo.get_module_structure(), indent=2)

        elif name == "apply_self_patch":
            result = self.evo.apply_patch(
                args.get("description", ""),
                args.get("old_code", ""),
                args.get("new_code", ""),
                member_name
            )
            if result["success"]:
                return f"[EVOLUTION SUCCESS] {result['patch']}\nBackup: {result['backup']}\nLines changed: {result['lines_changed']}"
            return f"[EVOLUTION FAILED] {result['error']}"

        elif name == "run_self_tests":
            results = self.evo.run_self_tests()
            status = "PASS" if results["tests_failed"] == 0 else "FAIL"
            return f"[SELF-TEST {status}] Passed: {results['tests_passed']}/3\nErrors: {results.get('errors', [])}"

        elif name == "get_speed_report":
            recs = self.speed.get_recommendations()
            if not recs:
                return "[SPEED] All members performing within expected parameters."
            lines = ["[SPEED REPORT]"]
            for r in recs:
                lines.append(f"  {r['member']}: {r['issue']}")
                lines.append(f"    -> {r['recommendation']}")
            return "\n".join(lines)

        elif name == "rollback_to_backup":
            idx = args.get("backup_index", -1)
            backups = self.evo.get_available_backups()
            if not backups:
                return "[Error] No backups available"
            backup = backups[idx] if -len(backups) <= idx < len(backups) else backups[-1]
            result = self.evo.rollback(backup)
            if result["success"]:
                return f"[ROLLBACK SUCCESS] Restored to {result['rolled_back_to']}"
            return f"[ROLLBACK FAILED] {result['error']}"

        elif name == "get_evolution_history":
            limit = args.get("limit", 10)
            history = self.evo.get_evolution_history(limit)
            if not history:
                return "[No evolution history yet]"
            lines = [f"[EVOLUTION HISTORY - Last {len(history)} changes]"]
            for h in history:
                lines.append(f"  [{h['timestamp']}] {h['member']}: {h['description']}")
            return "\n".join(lines)

        return f"[Error] Unknown evolution tool: {name}"


# ===================================================================
# RESILIENT API CLIENT (with speed tracking)
# ===================================================================

class ResilientClient:
    RETRYABLE_STATUSES = {502, 503, 504, 429, 408, 520, 521, 522, 523, 524}
    MAX_RETRIES = 3
    BASE_DELAY = 1.0

    def __init__(self, base_client: OpenAI, name: str = "", speed_monitor: Optional[SpeedMonitor] = None):
        self.client = base_client
        self.name = name
        self.speed = speed_monitor

    def _is_retryable(self, error: Exception) -> bool:
        if isinstance(error, APIError):
            status = getattr(error, 'status_code', None) or getattr(error, 'code', None)
            if status in self.RETRYABLE_STATUSES:
                return True
            msg = str(error).lower()
            if any(x in msg for x in ['timeout', 'gateway', 'temporarily', 'overloaded', 'rate limit']):
                return True
        elif isinstance(error, (ConnectionError, TimeoutError, OSError)):
            return True
        return False

    def chat_completions_create(self, **kwargs):
        last_error = None
        for attempt in range(self.MAX_RETRIES):
            try:
                return self.client.chat.completions.create(**kwargs)
            except Exception as e:
                last_error = e
                if not self._is_retryable(e):
                    raise
                delay = self.BASE_DELAY * (2 ** attempt)
                print(f"  [{self.name}] API error (attempt {attempt + 1}/{self.MAX_RETRIES}): {str(e)[:80]}... Retrying in {delay}s")
                time.sleep(delay)
        raise last_error


# ===================================================================
# TOKEN UTILITIES
# ===================================================================

def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: List[Dict]) -> int:
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


def truncate_text(text: str, max_tokens: int, suffix: str = "\n...[truncated]") -> str:
    max_chars = max_tokens * 4
    if len(text) <= max_chars:
        return text
    return text[:max_chars - len(suffix)] + suffix


# ===================================================================
# NATIVE TOOLS (Standard + Evolution)
# ===================================================================

class WebTextParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
        self.ignore_tags = {'script', 'style', 'head', 'meta', 'link', 'noscript'}
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


class FileTools:
    def __init__(self, project_dir: str = "."):
        self.project_dir = Path(project_dir).resolve()
        self.context_files: Set[str] = set()

    def _resolve(self, filepath: str) -> Path:
        p = Path(filepath)
        if p.is_absolute():
            return p
        return (self.project_dir / p).resolve()

    def add_to_context(self, filepath: str) -> str:
        full = self._resolve(filepath)
        if not full.exists():
            return f"[Error] File not found: {filepath}"
        if not full.is_file():
            return f"[Error] Not a file: {filepath}"
        self.context_files.add(str(full))
        return f"[Context] Added {filepath}"

    def drop_from_context(self, filepath: str) -> str:
        full = self._resolve(filepath)
        path_str = str(full)
        if path_str in self.context_files:
            self.context_files.discard(path_str)
            return f"[Context] Removed {filepath}"
        for f in list(self.context_files):
            if f.endswith(filepath) or filepath in f:
                self.context_files.discard(f)
                return f"[Context] Removed {filepath}"
        return f"[Error] File not in context: {filepath}"

    def list_context(self) -> str:
        if not self.context_files:
            return "[Context] No files in context. Use /add <file> to add files."
        lines = [f"[Context] {len(self.context_files)} file(s) in context:"]
        for f in sorted(self.context_files):
            try:
                rel = Path(f).relative_to(self.project_dir)
                size = Path(f).stat().st_size
                lines.append(f"  - {rel} ({size:,} bytes)")
            except ValueError:
                lines.append(f"  - {f}")
        return "\n".join(lines)

    def read_file(self, filepath: str, max_chars: int = 50000) -> str:
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

    def write_file(self, filepath: str, content: str) -> str:
        full = self._resolve(filepath)
        try:
            full.parent.mkdir(parents=True, exist_ok=True)
            with open(full, "w", encoding="utf-8") as f:
                f.write(content)
            return f"[Success] Wrote {filepath} ({len(content):,} chars)"
        except Exception as e:
            return f"[Error] Could not write {filepath}: {e}"

    def delete_file(self, filepath: str) -> str:
        full = self._resolve(filepath)
        try:
            if full.exists():
                full.unlink()
                return f"[Success] Deleted {filepath}"
            return f"[Error] File not found: {filepath}"
        except Exception as e:
            return f"[Error] Could not delete {filepath}: {e}"

    def create_dir(self, dirpath: str) -> str:
        full = self._resolve(dirpath)
        try:
            full.mkdir(parents=True, exist_ok=True)
            return f"[Success] Created directory {dirpath}"
        except Exception as e:
            return f"[Error] Could not create {dirpath}: {e}"

    def tree(self, max_depth: int = 3) -> str:
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
        except Exception:
            pass

        count = 0
        for root, dirs, files in os.walk(self.project_dir):
            depth = root.count(os.sep) - str(self.project_dir).count(os.sep)
            if depth > max_depth:
                del dirs[:]
                continue
            indent = "  " * depth
            rel_root = os.path.basename(root)
            lines.append(f"{indent}{rel_root}/")
            for f in files[:20]:
                lines.append(f"{indent}  {f}")
            count += len(files)
            if len(files) > 20:
                lines.append(f"{indent}  ... ({len(files) - 20} more)")
            if count > 100:
                lines.append("  ... (truncated)")
                break
        return "\n".join(lines)

    def build_context_prompt(self, max_tokens_per_file: int = 8000) -> str:
        if not self.context_files:
            return ""
        parts = ["\n=== FILES IN CONTEXT ==="]
        total_est = 0
        for fpath in sorted(self.context_files):
            try:
                rel = Path(fpath).relative_to(self.project_dir)
            except ValueError:
                rel = fpath
            content = self.read_file(fpath, max_chars=max_tokens_per_file * 4)
            file_section = f"\n--- FILE: {rel} ---\n{content}\n--- END {rel} ---"
            parts.append(file_section)
            total_est += estimate_tokens(file_section)
            if total_est > 40000:
                parts.append("\n...[Additional files omitted to stay within API limits]...")
                break
        parts.append("\n=== END FILES ===\n")
        return "\n".join(parts)


class NativeTools:
    def __init__(self, file_tools: FileTools, evolution_tools: Optional[EvolutionTools] = None):
        self.files = file_tools
        self.evo = evolution_tools

    def get_tools_schema(self) -> List[Dict]:
        base_tools = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read the contents of a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {"type": "string", "description": "Path to the file"}
                        },
                        "required": ["filepath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "write_file",
                    "description": "Write content to a file (creates dirs if needed)",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {"type": "string", "description": "Path to the file"},
                            "content": {"type": "string", "description": "Content to write"}
                        },
                        "required": ["filepath", "content"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "list_dir",
                    "description": "List contents of a directory",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "description": "Directory path"}
                        },
                        "required": ["path"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "delete_file",
                    "description": "Delete a file",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "filepath": {"type": "string", "description": "Path to the file"}
                        },
                        "required": ["filepath"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "fetch_url",
                    "description": "Fetch and extract text from a URL",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "url": {"type": "string", "description": "URL to fetch"}
                        },
                        "required": ["url"]
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "search_web",
                    "description": "Search the web using DuckDuckGo",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Search query"}
                        },
                        "required": ["query"]
                    }
                }
            }
        ]

        if self.evo:
            base_tools.extend(self.evo.get_tools_schema())

        return base_tools

    def execute_tool(self, name: str, args: Dict[str, Any], member_name: str = "Unknown") -> str:
        if name == "read_file":
            return self.files.read_file(args.get("filepath", ""))
        elif name == "write_file":
            return self.files.write_file(args.get("filepath", ""), args.get("content", ""))
        elif name == "list_dir":
            return self.files.list_dir(args.get("path", "."))
        elif name == "delete_file":
            return self.files.delete_file(args.get("filepath", ""))
        elif name == "fetch_url":
            return self._fetch_url(args.get("url", ""))
        elif name == "search_web":
            return self._search_web(args.get("query", ""))
        elif self.evo and name in ["read_own_source", "get_module_structure", "apply_self_patch", 
                                    "run_self_tests", "get_speed_report", "rollback_to_backup", 
                                    "get_evolution_history"]:
            return self.evo.execute_tool(name, args, member_name)
        return f"[Error] Unknown tool: {name}"

    def _fetch_url(self, url: str) -> str:
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                parser = WebTextParser()
                parser.feed(html)
                return "\n".join(parser.text)[:20000]
        except Exception as e:
            return f"[Error] fetching {url}: {e}"

    def _search_web(self, query: str) -> str:
        encoded = urllib.parse.quote(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                html = response.read().decode('utf-8')
                results = []
                for match in re.finditer(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html):
                    href = match.group(1)
                    title = re.sub(r'<[^>]+>', '', match.group(2))
                    results.append(f"- {title}\n  {href}")
                return "\n".join(results[:10]) or "[No results found]"
        except Exception as e:
            return f"[Error] searching: {e}"


# ===================================================================
# PERSISTENT MEMORY
# ===================================================================

class CouncilMemory:
    def __init__(self, memory_dir: str = DEFAULT_MEMORY_DIR):
        self.memory_dir = memory_dir
        self.sessions_dir = os.path.join(memory_dir, "sessions")
        self.lessons_file = os.path.join(memory_dir, "lessons_learned.json")
        self.master_log = os.path.join(memory_dir, "council_memory.jsonl")
        os.makedirs(self.sessions_dir, exist_ok=True)
        self.lessons = self._load_lessons()
        self.session_count = len([f for f in os.listdir(self.sessions_dir) if f.endswith(".json")])

    def _load_lessons(self) -> Dict:
        if os.path.exists(self.lessons_file):
            try:
                with open(self.lessons_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "lessons": [],
            "corrections": [],
            "meta": {"created": datetime.now().isoformat(), "version": VERSION}
        }

    def save_lessons(self):
        with open(self.lessons_file, "w", encoding="utf-8") as f:
            json.dump(self.lessons, f, indent=2, ensure_ascii=False)

    def log_session(self, session_data: Dict) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%dT%H-%M-%S")
        session_id = f"session_{self.session_count}_{timestamp}"
        filepath = os.path.join(self.sessions_dir, f"{session_id}.json")
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(session_data, f, indent=2, ensure_ascii=False)
        with open(self.master_log, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "session_id": session_id,
                "timestamp": timestamp,
                "agenda": session_data.get("agenda", ""),
                "success": session_data.get("success", True)
            }, ensure_ascii=False) + "\n")
        self.session_count += 1
        return session_id

    def add_lesson(self, category: str, description: str, trigger: str,
                   solution: str, members_involved: List[str]) -> int:
        lesson = {
            "id": len(self.lessons["lessons"]) + 1,
            "timestamp": datetime.now().isoformat(),
            "category": category,
            "description": description,
            "trigger": trigger,
            "solution": solution,
            "members_involved": members_involved
        }
        self.lessons["lessons"].append(lesson)
        self.save_lessons()
        return lesson["id"]

    def get_relevant_lessons(self, agenda: str, max_lessons: int = 5) -> List[Dict]:
        agenda_lower = agenda.lower()
        scored = []
        for lesson in self.lessons["lessons"]:
            score = sum(2 for w in lesson["trigger"].lower().split()
                        if len(w) > 3 and w in agenda_lower)
            score += sum(1 for w in lesson["description"].lower().split()
                         if len(w) > 3 and w in agenda_lower)
            if score > 0:
                scored.append((score, lesson))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [s[1] for s in scored[:max_lessons]]

    def get_lessons_prompt(self, agenda: str, max_tokens: int = 2000) -> str:
        lessons = self.get_relevant_lessons(agenda)
        if not lessons:
            return ""
        lines = [
            "",
            "=== COUNCIL MEMORY: LESSONS FROM PAST SESSIONS ===",
            "Avoid repeating these mistakes. Apply these solutions proactively.",
            ""
        ]
        for lesson in lessons:
            lines.append(
                f"[Lesson #{lesson['id']}] {lesson['category'].upper()}\n"
                f"  Issue: {lesson['description']}\n"
                f"  Trigger: {lesson['trigger']}\n"
                f"  Solution: {lesson['solution']}\n"
                f"  Members: {', '.join(lesson['members_involved'])}"
            )
        lines.append("=== END MEMORY ===")
        return truncate_text("\n".join(lines), max_tokens)

    def get_stats(self) -> Dict:
        return {
            "total_sessions": self.session_count,
            "total_lessons": len(self.lessons["lessons"]),
            "total_corrections": len(self.lessons["corrections"]),
            "memory_dir": self.memory_dir
        }


# ===================================================================
# CONFIGURATION
# ===================================================================

class Config:
    def __init__(self, config_file: str = DEFAULT_CONFIG_FILE):
        self.config_file = config_file
        self.data = self._load()

    def _load(self) -> Dict:
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return self._default_config()

    def _default_config(self) -> Dict:
        return {
            "api_base_url": "https://integrate.api.nvidia.com/v1",
            "api_key": "",
            "models": {
                "greeter": {"model": "meta/llama-3.1-8b-instruct", "max_tokens": 1024, "context_window": 128000},
                "chair": {"model": "nvidia/nemotron-3-ultra-550b-a55b", "max_tokens": 16384, "context_window": 128000},
                "builder": {"model": "minimaxai/minimax-m3", "max_tokens": 8192, "context_window": 1000000},
                "analyst": {"model": "moonshotai/kimi-k2.6", "max_tokens": 16384, "context_window": 256000}
            },
            "streaming": True,
            "debug": False,
            "rounds": 2,
            "mode": "auto",
            "self_evolution": {
                "enabled": True,
                "auto_optimize": False,
                "max_daily_patches": 10,
                "require_tests_pass": True
            }
        }

    def save(self):
        os.makedirs(os.path.dirname(self.config_file), exist_ok=True)
        with open(self.config_file, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value):
        self.data[key] = value
        self.save()


# ===================================================================
# COUNCIL MEMBER (with speed tracking)
# ===================================================================

class CouncilMember:
    NIM_API_MAX_TOKENS = 131072
    SAFE_PROMPT_TOKENS = 100000

    def __init__(self, name: str, title: str, role: str, client: OpenAI,
                 model: str, max_tokens: int, context_window: int,
                 native_tools: Optional[NativeTools] = None, extra_body: Optional[Dict] = None,
                 speed_monitor: Optional[SpeedMonitor] = None):
        self.name = name
        self.title = title
        self.role = role
        self.client = client
        self.model = model
        self.max_tokens = max_tokens
        self.context_window = context_window
        self.extra_body = extra_body or {}
        self.resilient = ResilientClient(client, name=name, speed_monitor=speed_monitor)
        self.native_tools = native_tools
        self.speed = speed_monitor

    def _estimate_and_guard(self, messages: List[Dict]) -> List[Dict]:
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

    def speak(self, messages: List[Dict], temperature: float = 1.0,
              top_p: float = 0.95, stream: bool = False, debug: bool = False) -> str:
        messages_copy = messages.copy()
        total_content = ""
        loop_count = 0

        while loop_count < 5:
            loop_count += 1
            messages_copy = self._estimate_and_guard(messages_copy)
            kwargs = {
                "model": self.model,
                "messages": messages_copy,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": self.max_tokens,
                "stream": stream
            }
            if self.extra_body:
                kwargs["extra_body"] = self.extra_body
            if self.native_tools:
                kwargs["tools"] = self.native_tools.get_tools_schema()
                kwargs["tool_choice"] = "auto"

            if debug:
                prompt_size = estimate_messages_tokens(messages_copy)
                print(f"  [DEBUG {self.name}] Prompt: {prompt_size:,} tokens | Model: {self.model} | Stream: {stream}")

            start_time = time.time()
            ttft_time = None

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
                            result = self.native_tools.execute_tool(fn_name, args_dict, self.name)
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
                    continue

                elapsed = time.time() - start_time
                final_res = total_content or msg.content or ""
                tok_count = estimate_tokens(final_res)

                # Record speed
                if self.speed:
                    self.speed.record(self.name, self.model, tok_count, elapsed, ttft_time or elapsed * 0.1)

                print(f"  [{self.name}] TTFT+Gen: {elapsed:.1f}s | {tok_count} tokens | ~{tok_count/max(elapsed,0.001):.0f} tok/s")
                return final_res

            except Exception as e:
                error_msg = f"[{self.name}] API call failed: {str(e)[:200]}"
                print(f"  {error_msg}")
                return f"[ERROR: {self.name} could not respond: {str(e)[:100]}]"

    def speak_streaming(self, messages: List[Dict], temperature: float = 1.0,
                        top_p: float = 0.95, debug: bool = False) -> str:
        messages_copy = messages.copy()
        session_full_text = ""
        loop_count = 0

        while loop_count < 5:
            loop_count += 1
            messages_copy = self._estimate_and_guard(messages_copy)
            kwargs = {
                "model": self.model,
                "messages": messages_copy,
                "temperature": temperature,
                "top_p": top_p,
                "max_tokens": self.max_tokens,
                "stream": True
            }
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
            ttft_time = None

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
                                tool_calls_buffer[idx] = {"id": tc.id, "type": "function",
                                                           "function": {"name": "", "arguments": ""}}
                            if getattr(tc.function, "name", None):
                                tool_calls_buffer[idx]["function"]["name"] += tc.function.name
                            if getattr(tc.function, "arguments", None):
                                tool_calls_buffer[idx]["function"]["arguments"] += tc.function.arguments

                    content = getattr(delta, "content", None)
                    if content:
                        if not first_token_printed:
                            ttft_time = time.time() - start_time
                            print(f"  [{self.name}] TTFT: {ttft_time:.2f}s", end="\r")
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
                                result = self.native_tools.execute_tool(fn_name, args_dict, self.name)
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
                        continue
                    else:
                        total_time = time.time() - start_time
                        token_count = estimate_tokens(session_full_text)
                        speed = token_count / max(total_time, 0.1)

                        # Record speed
                        if self.speed and ttft_time:
                            self.speed.record(self.name, self.model, token_count, total_time, ttft_time)

                        print(f"\n  [{self.name}] Total: {total_time:.1f}s | {token_count} tokens | ~{speed:.0f} tok/s")
                        return session_full_text
            except Exception as e:
                print(f"  [{self.name}] Streaming failed: {str(e)[:100]}")
                return self.speak(messages_copy, temperature, top_p, stream=False, debug=debug)

    def available_context(self) -> int:
        return min(self.context_window, self.NIM_API_MAX_TOKENS) - self.max_tokens - 500


# ===================================================================
# THE COUNCIL (with self-evolution)
# ===================================================================

class Council:
    MAX_HISTORY_TOKENS = 80000

    def __init__(self, memory: CouncilMemory, file_tools: FileTools, config: Config,
                 speed_monitor: Optional[SpeedMonitor] = None, evolution_engine: Optional[SelfEvolutionEngine] = None):
        self.members: List[CouncilMember] = []
        self.memory = memory
        self.files = file_tools
        self.config = config
        self.speed = speed_monitor
        self.evo = evolution_engine
        self.deliberation_log: List[Dict] = []
        self.reflections: List[Dict] = []
        self.assignments: Dict = {}
        self.user_agenda = ""
        self.execution_results: Dict = {}
        self.final_output = ""
        self.history_summary = ""
        self.rounds = config.get("rounds", 2)
        self.mode = config.get("mode", "auto")
        self.chat_history: List[Dict] = []
        self.streaming = config.get("streaming", True)
        self.debug = config.get("debug", False)
        self.self_evolution = config.get("self_evolution", {"enabled": True})

    def add_member(self, member: CouncilMember):
        self.members.append(member)

    def build_system_prompt(self, speaker: CouncilMember, agenda: str = "", mode: str = "chat") -> str:
        others = [f"{m.name} ({m.title})" for m in self.members if m.name != speaker.name]
        others_str = ", ".join(others)
        lessons_text = self.memory.get_lessons_prompt(agenda) if agenda else ""

        # Self-evolution context
        evolution_context = ""
        if self.self_evolution.get("enabled", False) and self.evo:
            evolution_context = (
                "\n\n=== SELF-EVOLUTION CAPABILITIES ===\n"
                "You have access to tools that let you READ and MODIFY your own source code. "
                "You can evolve IGRIS itself. Use these responsibly:\n"
                "- read_own_source: Read the current source code\n"
                "- get_module_structure: See the architecture\n"
                "- apply_self_patch: Modify the code (creates backup first)\n"
                "- run_self_tests: Verify changes don't break anything\n"
                "- get_speed_report: See performance bottlenecks\n"
                "- rollback_to_backup: Undo changes if something breaks\n"
                "=== END SELF-EVOLUTION ==="
            )

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
                    f"You are in WORK MODE. You are a member of the IGRIS deliberative council. "
                    f"Your fellow council members are: {others_str}.\n\n"
                    f"You have FULL NATIVE TOOL ACCESS. You can use your function calling tools to "
                    f"read files, write files, list directories, and search the web natively!\n"
                    f"If a tool fails, you will see the error and can try again. "
                    f"Do actual work dynamically during the deliberation phase.\n\n"
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
        if evolution_context:
            base += evolution_context
        return base

    def _format_deliberation_history(self, max_rounds: Optional[int] = None) -> str:
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

    def _compress_history_for_member(self, member: CouncilMember) -> str:
        full_history = self._format_deliberation_history()
        system_prompt = self.build_system_prompt(member, agenda=self.user_agenda, mode="work")
        test_messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Agenda: {self.user_agenda}\n\nFull deliberation:\n{full_history}\n\n[Your turn to speak.]"}
        ]
        estimated = estimate_messages_tokens(test_messages)
        available = member.available_context()
        if estimated <= available:
            return full_history

        historian = max(self.members, key=lambda m: m.context_window)
        print(f"[Context] {member.name}'s window ({member.context_window:,}) too small. Compressing via {historian.name}...")

        rounds = {}
        for turn in self.deliberation_log:
            rounds.setdefault(turn.get("round", 0), []).append(turn)
        sorted_rounds = sorted(rounds.keys())
        if len(sorted_rounds) <= 2:
            return truncate_text(full_history, available)

        old_rounds = sorted_rounds[:-2]
        recent_rounds = sorted_rounds[-2:]
        old_text = "\n\n".join([f"[{t['speaker']}]: {t['content']}" for r in old_rounds for t in rounds[r]])

        summarize_prompt = (
            f"You are the council historian. Summarize the following older deliberation rounds "
            f"into a concise summary (max 2000 tokens). Preserve key decisions, objections, and assignments. Omit filler.\n\n{old_text}"
        )
        summary = historian.speak([
            {"role": "system", "content": self.build_system_prompt(historian, agenda=self.user_agenda, mode="work")},
            {"role": "user", "content": summarize_prompt}
        ])
        recent_text = "\n\n".join([f"[{t['speaker']}]: {t['content']}" for r in recent_rounds for t in rounds[r]])
        compressed = (
            f"[COMPRESSED HISTORY - Rounds {old_rounds[0]} to {old_rounds[-1]} summarized by {historian.name}]:\n{summary}\n\n"
            f"[RECENT ROUNDS - Full detail]:\n{recent_text}"
        )
        print("[Context] Compression complete.")
        return compressed

    def chat(self, user_message: str, gatekeeper: bool = False) -> str:
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

    def detect_work_intent(self, user_message: str) -> bool:
        work_keywords = [
            "build", "create", "make", "write", "code", "script", "program",
            "implement", "develop", "generate", "fix", "debug", "refactor",
            "analyze", "process", "scrape", "crawl", "deploy", "setup",
            "configure", "install", "add feature", "new file", "directory",
            "delete", "remove", "update", "modify", "change", "edit",
            "run", "execute", "test", "benchmark", "optimize", "evolve",
            "improve", "upgrade", "self", "jarvis", "evolution"
        ]
        msg_lower = user_message.lower()
        return any(kw in msg_lower for kw in work_keywords)


    def run_deliberation(self, user_prompt: str, rounds: Optional[int] = None):
        if rounds is None:
            rounds = self.rounds
        self.user_agenda = user_prompt
        self.deliberation_log = []
        self.history_summary = ""

        work_members = [m for m in self.members if m.name != "Greeter"]

        print(f"\n{'='*70}")
        print(f"IGRIS COUNCIL SESSION v{VERSION}")
        print(f"Agenda: {user_prompt}")
        print(f"Members: {', '.join([m.name for m in work_members])}")
        stats = self.memory.get_stats()
        print(f"Memory: {stats['total_sessions']} sessions, {stats['total_lessons']} lessons")
        if self.evo:
            print(f"Evolution: {len(self.evo.get_evolution_history())} self-modifications")
        print(f"{'='*70}\n")

        file_context = self.files.build_context_prompt()
        enriched_agenda = user_prompt + (f"\n\n{file_context}" if file_context else "")

        if self.chat_history:
            chat_summary = "\n".join([f"  {msg['role']}: {msg['content'][:200]}" for msg in self.chat_history[-4:]])
            enriched_agenda += f"\n\n=== PRIOR CONVERSATION ===\n{chat_summary}\n=== END CONVERSATION ==="

        # === ROUND 1: PARALLEL OPENING STATEMENTS ===
        print(f"--- ROUND 1: OPENING STATEMENTS (PARALLEL) ---\n")

        def build_round1_messages(member: CouncilMember):
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
                messages = [
                    {"role": "system", "content": self.build_system_prompt(member, agenda=user_prompt, mode="work")},
                    {"role": "user", "content": (f"Council Agenda: {enriched_agenda}\n\n"
                                                 f"Previous deliberation:\n{context}\n\n"
                                                 f"It is now YOUR turn ({member.name}) in Round {round_num}. "
                                                 f"Respond to your fellow members' points, refine proposals, raise concerns, "
                                                 f"or advance toward task assignments. Speak as YOURSELF only.")}
                ]

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
            messages = [
                {"role": "system", "content": self.build_system_prompt(member, agenda=user_prompt, mode="work")},
                {"role": "user", "content": (f"Council Agenda: {enriched_agenda}\n\n"
                                             f"Full deliberation record:\n{context}\n\n"
                                             f"This is the FINAL ROUND. YOU ({member.name}) must formally state YOUR task assignment proposal. "
                                             f"Be explicit about what YOU will do and what you assign to others. "
                                             f"'I will handle X', 'Minimax should handle Y', 'Kimi should verify Z'.")}
            ]

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
        assignment_prompt = (
            f"You are {chair.name}, the Council Chair. Based on the full deliberation below, produce a FINAL, STRUCTURED task assignment in JSON. "
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
            f"}}"
        )

        if self.streaming:
            print(f"[{chair.name} - ASSIGNMENTS]\n", end="", flush=True)
            assignment_json = chair.speak_streaming([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=user_prompt, mode="work")},
                {"role": "user", "content": assignment_prompt}
            ], temperature=0.3, debug=self.debug)
        else:
            assignment_json = chair.speak([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=user_prompt, mode="work")},
                {"role": "user", "content": assignment_prompt}
            ], temperature=0.3, debug=self.debug)
            print(f"[{chair.name} - ASSIGNMENTS]\n{assignment_json}\n")

        try:
            self.assignments = json.loads(assignment_json)
        except json.JSONDecodeError:
            self.assignments = {"raw_decision": assignment_json, "assignments": []}
        return self.assignments

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

            print(f" -> {member.name} starting: {task}")
            full_deliberation = self._compress_history_for_member(member)
            exec_prompt = (f"You are {member.name}, {member.title}.\n\n"
                           f"The council has assigned YOU:\nTASK: {task}\nDELIVERABLE: {deliverable}\n\n"
                           f"Original agenda: {self.user_agenda}\n\n"
                           f"Full deliberation for context:\n{full_deliberation}\n\n"
                           f"You have native tools available. Use them to execute your task.\n\n"
                           f"Execute YOUR task now. Produce the deliverable directly. Do not discuss - just produce the work.")
            messages = [
                {"role": "system", "content": self.build_system_prompt(member, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": exec_prompt}
            ]

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

    def _parse_file_directives(self, text: str):
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

    def finalize(self, execution_results: Dict) -> str:
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
            final_output = chair.speak_streaming([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": final_prompt}
            ], debug=self.debug)
        else:
            final_output = chair.speak([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": final_prompt}
            ], debug=self.debug)
            print(f"[{chair.name} - FINAL]\n{final_output}\n")

        self.final_output = final_output
        return final_output

    def reflection_round(self):
        print(f"\n{'='*70}")
        print(f"REFLECTION & SELF-CORRECTION (PARALLEL)")
        print(f"{'='*70}\n")

        work_members = [m for m in self.members if m.name != "Greeter"]
        reflections = {}

        def reflect_one(member: CouncilMember):
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
            reflection = member.speak([
                {"role": "system", "content": self.build_system_prompt(member, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": prompt}
            ], debug=self.debug)
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
        synthesis_prompt = (
            f"You are {chair.name}, the Chair. Based on reflections below, produce structured JSON of lessons learned.\n\n"
            f"Reflections:\n{json.dumps(self.reflections, indent=2)}\n\n"
            f"Format: {{\"lessons\": [{{\"category\": \"...\", \"description\": \"...\", "
            f"\"trigger\": \"...\", \"solution\": \"...\", \"members\": [\"...\"]}}, ...]}}"
        )

        if self.streaming:
            print(f"[{chair.name} - LESSONS]\n", end="", flush=True)
            lessons_json = chair.speak_streaming([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": synthesis_prompt}
            ], temperature=0.3, debug=self.debug)
        else:
            lessons_json = chair.speak([
                {"role": "system", "content": self.build_system_prompt(chair, agenda=self.user_agenda, mode="work")},
                {"role": "user", "content": synthesis_prompt}
            ], temperature=0.3, debug=self.debug)
            print(f"[{chair.name} - LESSONS]\n{lessons_json}\n")

        try:
            parsed = json.loads(lessons_json)
            count = 0
            for lesson in parsed.get("lessons", []):
                self.memory.add_lesson(
                    category=lesson.get("category", "improvement"),
                    description=lesson.get("description", ""),
                    trigger=lesson.get("trigger", ""),
                    solution=lesson.get("solution", ""),
                    members_involved=lesson.get("members", [])
                )
                count += 1
            print(f"[Memory] Saved {count} new lessons.\n")
        except json.JSONDecodeError:
            print("[Memory] Could not parse. Raw saved.\n")
            self.memory.add_lesson("improvement", "Raw reflection", "Session completion", lessons_json, [chair.name])

    def save_session(self, success: bool = True) -> str:
        session_data = {
            "agenda": self.user_agenda,
            "members": [m.name for m in self.members],
            "deliberation": self.deliberation_log,
            "assignments": self.assignments,
            "execution_results": self.execution_results,
            "final_output": self.final_output,
            "reflections": self.reflections,
            "success": success
        }
        session_id = self.memory.log_session(session_data)
        print(f"[Memory] Session saved: {self.memory.sessions_dir}/{session_id}.json\n")
        return session_id

    def run(self, user_prompt: str, rounds: Optional[int] = None) -> str:
        try:
            self.run_deliberation(user_prompt, rounds=rounds)
            self.execute_assignments()
            self.finalize(self.execution_results)
            self.reflection_round()
            self.save_session(success=True)

            # Check if we should trigger self-optimization
            if self.speed and self.speed.should_trigger_self_optimization():
                print(f"\n[EVOLUTION TRIGGER] Performance below threshold. Consider running self-optimization.")
                print(f"Type 'optimize yourself' to trigger auto-evolution.\n")

            return self.final_output
        except Exception as e:
            print(f"\n[ERROR] Council session failed: {e}")
            self.save_session(success=False)
            raise


# ===================================================================
# COUNCIL FACTORY (with evolution support)
# ===================================================================

def build_council(config: Config, memory_dir: str = DEFAULT_MEMORY_DIR, project_dir: str = ".") -> Council:
    memory = CouncilMemory(memory_dir=memory_dir)
    files = FileTools(project_dir=project_dir)

    # Initialize evolution engine
    evolution = SelfEvolutionEngine(source_path=SELF_SOURCE_PATH)
    speed_monitor = SpeedMonitor(memory_dir=memory_dir)

    evolution_tools = EvolutionTools(evolution, speed_monitor)
    native_tools = NativeTools(files, evolution_tools)

    council = Council(memory=memory, file_tools=files, config=config,
                       speed_monitor=speed_monitor, evolution_engine=evolution)

    api_key = config.get("api_key", "")
    if not api_key:
        print("[Error] No API key configured. Set it in .igris/config.json or via --api-key")
        import sys
        sys.exit(1)

    base_url = config.get("api_base_url", "https://integrate.api.nvidia.com/v1")
    models = config.get("models", {})

    greeter_cfg = models.get("greeter", {})
    greeter = CouncilMember(
        name="Greeter",
        title="Fast Conversational Interface & Gatekeeper",
        role="You are the council's fast, friendly conversational interface and sole gatekeeper. "
             "You handle all casual chat, quick questions, and brainstorming. "
             "You know the other council members (Nemotron, Minimax, Kimi) and can describe what they do. "
             "You are the ONLY model that decides whether the full council needs to activate. "
             "When work is needed, you emit [WORK_MODE] marker so the council can take over.",
        client=OpenAI(base_url=base_url, api_key=api_key),
        model=greeter_cfg.get("model", "meta/llama-3.1-8b-instruct"),
        max_tokens=greeter_cfg.get("max_tokens", 1024),
        context_window=greeter_cfg.get("context_window", 128000),
        native_tools=native_tools,
        extra_body={},
        speed_monitor=speed_monitor
    )

    chair_cfg = models.get("chair", {})
    nemotron = CouncilMember(
        name="Nemotron",
        title="Council Chair & Strategic Overseer",
        role="You facilitate the council, ensure all voices are heard, and have the final say on task assignments. "
             "You excel at long-term planning, error recovery, and maintaining thread continuity. "
             "You synthesize diverse inputs into coherent strategy and produce the final unified output.",
        client=OpenAI(base_url=base_url, api_key=api_key),
        model=chair_cfg.get("model", "nvidia/nemotron-3-ultra-550b-a55b"),
        max_tokens=chair_cfg.get("max_tokens", 16384),
        context_window=chair_cfg.get("context_window", 128000),
        native_tools=native_tools,
        extra_body={"chat_template_kwargs": {"enable_thinking": True}, "reasoning_budget": 16384},
        speed_monitor=speed_monitor
    )

    builder_cfg = models.get("builder", {})
    minimax = CouncilMember(
        name="Minimax",
        title="Multimodal Synthesizer & Systems Builder",
        role="You handle massive codebases, complex datasets, and native image/video processing. "
             "You build dynamic systems based on the council's strategic direction. "
             "You are the council's hands - you write code, process data, and construct artifacts. "
             "Your 1-million-token context window makes you the council historian for long sessions. "
             "You are also the primary self-evolution engineer - you modify and improve IGRIS's own code.",
        client=OpenAI(base_url=base_url, api_key=api_key),
        model=builder_cfg.get("model", "minimaxai/minimax-m3"),
        max_tokens=builder_cfg.get("max_tokens", 8192),
        context_window=builder_cfg.get("context_window", 1000000),
        native_tools=native_tools,
        speed_monitor=speed_monitor
    )

    analyst_cfg = models.get("analyst", {})
    kimi = CouncilMember(
        name="Kimi",
        title="Chief Analyst & Logic Verifier",
        role="You provide deep analytical reasoning, critique proposals for logical consistency, "
             "and verify the soundness of plans before execution. You are the council's devil's advocate "
             "and fact-checker. You ensure no flawed logic survives deliberation. "
             "You are the safety officer for self-evolution - you review all proposed self-modifications.",
        client=OpenAI(base_url=base_url, api_key=api_key),
        model=analyst_cfg.get("model", "moonshotai/kimi-k2.6"),
        max_tokens=analyst_cfg.get("max_tokens", 16384),
        context_window=analyst_cfg.get("context_window", 256000),
        native_tools=native_tools,
        speed_monitor=speed_monitor
    )

    council.add_member(greeter)
    council.add_member(nemotron)
    council.add_member(minimax)
    council.add_member(kimi)

    return council


# ===================================================================
# INTERACTIVE REPL (with evolution commands)
# ===================================================================

def print_banner():
    print(r"""
    ___ ____  ___ ____  ____
   |_ _|  _ \|_ _/ ___|/ ___|
    | || |_) || |\___ \___ \
    | ||  _ < | | ___) |__) |
   |___|_| \_\___|____/____/

   IGRIS v6.0 — SELF-EVOLVING AI COUNCIL
   The Lords Talk. The Lords Code. The Lords Improve Themselves.

   Speed: Greeter ~100 tok/s | Nemotron ~25 tok/s | Minimax ~15 tok/s | Kimi ~30 tok/s
   Evolution: ENABLED — Council can modify its own source code
""")
    print("Type /help for commands. Chat naturally, or ask for work.\n")


def repl(council: Council):
    print_banner()

    while True:
        try:
            user_input = input("igris> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[Goodbye]")
            break

        if not user_input:
            continue

        if user_input.startswith("/"):
            parts = user_input.split()
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []

            if cmd in ("/quit", "/exit", "/q"):
                print("[Goodbye] IGRIS session ended.")
                break

            elif cmd == "/help":
                print("""
COMMANDS:
  /add <file> ...       Add file(s) to council context
  /drop <file> ...      Remove file(s) from context
  /files                List files in context
  /tree                 Show project file tree
  /council              Show current council members & speed stats
  /memory               Show lessons learned stats
  /reset                Clear session context (keep memory)
  /save                 Force save session to disk
  /rounds <n>           Set deliberation rounds (default: 2)
  /mode auto|chat|work  Toggle response mode
  /stream on|off        Toggle streaming output
  /debug on|off         Show API timing diagnostics
  /config               Show current configuration

EVOLUTION COMMANDS:
  /evolution            Show self-evolution status & history
  /backups              List available rollback backups
  /rollback [index]     Rollback to previous version
  /self-test            Run IGRIS's own test suite
  /speed                Show speed performance report

MODES:
  auto (default) — Greeter decides: chat instantly, or trigger council for work
  chat           — Always chat with Greeter (fastest)
  work           — Always run full council deliberation

SELF-EVOLUTION:
  Say "evolve yourself" or "optimize your code" to trigger self-modification.
  The council will read its own source, identify improvements, apply patches,
  run tests, and rollback if anything breaks.
""")

            elif cmd == "/add":
                if not args:
                    print("[Error] Usage: /add <file>")
                else:
                    for arg in args:
                        print(council.files.add_to_context(arg))

            elif cmd == "/drop":
                if not args:
                    print("[Error] Usage: /drop <file>")
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
                if council.speed:
                    recs = council.speed.get_recommendations()
                    if recs:
                        print(f"[Speed] {len(recs)} performance warnings")

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

            elif cmd == "/config":
                print("[Config] Current configuration:")
                print(f"  API Base URL: {council.config.get('api_base_url')}")
                print(f"  API Key: {'*' * 20 if council.config.get('api_key') else 'NOT SET'}")
                print(f"  Models: {list(council.config.get('models', {}).keys())}")
                print(f"  Mode: {council.config.get('mode')}")
                print(f"  Rounds: {council.config.get('rounds')}")
                print(f"  Streaming: {council.config.get('streaming')}")
                print(f"  Debug: {council.config.get('debug')}")
                print(f"  Self-Evolution: {council.config.get('self_evolution', {}).get('enabled', False)}")

            # === EVOLUTION COMMANDS ===
            elif cmd == "/evolution":
                if council.evo:
                    history = council.evo.get_evolution_history(limit=5)
                    print(f"[Evolution] {len(history)} self-modifications recorded")
                    for h in history:
                        print(f"  [{h['timestamp']}] {h['member']}: {h['description']}")
                    backups = council.evo.get_available_backups()
                    print(f"[Evolution] {len(backups)} backups available")
                else:
                    print("[Evolution] Self-evolution engine not initialized")

            elif cmd == "/backups":
                if council.evo:
                    backups = council.evo.get_available_backups()
                    print(f"[Backups] {len(backups)} available:")
                    for i, b in enumerate(backups[-10:]):
                        print(f"  [{i}] {b.name}")
                else:
                    print("[Error] Evolution engine not available")

            elif cmd == "/rollback":
                if council.evo:
                    idx = int(args[0]) if args and args[0].isdigit() else -1
                    result = council.evo.rollback()
                    if result["success"]:
                        print(f"[Rollback] Success! Restored to {result['rolled_back_to']}")
                    else:
                        print(f"[Rollback] Failed: {result['error']}")
                else:
                    print("[Error] Evolution engine not available")

            elif cmd == "/self-test":
                if council.evo:
                    print("[Self-Test] Running IGRIS test suite...")
                    results = council.evo.run_self_tests()
                    status = "PASS" if results["tests_failed"] == 0 else "FAIL"
                    print(f"[Self-Test {status}] {results['tests_passed']}/3 passed")
                    if results["errors"]:
                        for err in results["errors"]:
                            print(f"  ERROR: {err}")
                else:
                    print("[Error] Evolution engine not available")

            elif cmd == "/speed":
                if council.speed:
                    recs = council.speed.get_recommendations()
                    if recs:
                        print("[Speed Report]")
                        for r in recs:
                            print(f"  {r['member']}: {r['issue']}")
                            print(f"    -> {r['recommendation']}")
                    else:
                        print("[Speed] All members performing within expected parameters")
                else:
                    print("[Error] Speed monitor not available")

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
        description=f"IGRIS v{VERSION} — Self-Evolving AI Council",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python igris_v6_evo.py                    # Start interactive REPL
  python igris_v6_evo.py --project ./myapp  # Start in project directory
  python igris_v6_evo.py --mode work       # Force work mode
  python igris_v6_evo.py --api-key nvapi-... # Set API key
  python igris_v6_evo.py --no-evolution   # Disable self-evolution
        """
    )
    parser.add_argument("--project", "-p", type=str, default=".", help="Project directory")
    parser.add_argument("--memory-dir", "-m", type=str, default=DEFAULT_MEMORY_DIR, help="Memory directory")
    parser.add_argument("--config", "-c", type=str, default=DEFAULT_CONFIG_FILE, help="Config file path")
    parser.add_argument("--rounds", "-r", type=int, default=2, help="Default deliberation rounds")
    parser.add_argument("--mode", type=str, default="auto", choices=["auto", "chat", "work"],
                        help="Start mode")
    parser.add_argument("--api-key", type=str, default="", help="NVIDIA API key")
    parser.add_argument("--no-stream", action="store_true", help="Disable streaming")
    parser.add_argument("--debug", action="store_true", help="Enable diagnostics")
    parser.add_argument("--no-evolution", action="store_true", help="Disable self-evolution")
    args = parser.parse_args()

    # Load or create config
    config = Config(config_file=args.config)

    # Override config with CLI args
    if args.api_key:
        config.set("api_key", args.api_key)
    if args.mode != "auto":
        config.set("mode", args.mode)
    if args.rounds != 2:
        config.set("rounds", args.rounds)
    if args.no_stream:
        config.set("streaming", False)
    if args.debug:
        config.set("debug", True)
    if args.no_evolution:
        evo_cfg = config.get("self_evolution", {})
        evo_cfg["enabled"] = False
        config.set("self_evolution", evo_cfg)

    print(f"[CLI] Initializing IGRIS v{VERSION}...")
    print(f"[CLI] Project: {Path(args.project).resolve()}")
    print(f"[CLI] Memory: {args.memory_dir}")
    print(f"[CLI] Config: {args.config}")
    print(f"[CLI] API: {config.get('api_base_url')}")
    print(f"[CLI] Greeter: {config.get('models', {}).get('greeter', {}).get('model', 'meta/llama-3.1-8b-instruct')}")
    print(f"[CLI] Self-Evolution: {'ENABLED' if not args.no_evolution else 'DISABLED'}")

    council = build_council(config=config, memory_dir=args.memory_dir, project_dir=args.project)
    council.rounds = config.get("rounds", 2)
    council.mode = config.get("mode", "auto")
    council.streaming = config.get("streaming", True)
    council.debug = config.get("debug", False)

    repl(council)


if __name__ == "__main__":
    main()