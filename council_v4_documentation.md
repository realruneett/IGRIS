# CounciL Strategic Systems — Project Love v4.0
## Interactive Agentic CLI (Claude Code-Style)

> **System Identity:** You are a core cognitive engine for CounciL Strategic Systems. We are operating a multimodal, superhuman AI architecture named **Project Love**. This council **remembers everything** — up to 1 million tokens of context. When a member's window is smaller, the council compresses history intelligently so no insight is lost. Every session is saved locally. Every mistake is logged. Every correction is injected into future deliberations. The council gets smarter every time it runs.

---

## What's New in v4.0

| Feature | Description |
|---------|-------------|
| **Interactive REPL** | Claude Code-style persistent prompt. Run multiple agendas in one session. |
| **File System Integration** | `/add` files to context, `/tree` to browse project, members can read/write files during execution. |
| **1M Context Window** | Minimax M3 natively handles 1M tokens. Auto-compression for smaller-window members. |
| **Context Budget Management** | Each member declares `context_window`. History auto-compressed when budgets are exceeded. |
| **Local Persistent Memory** | All sessions saved to `council_memory/`. |
| **Lessons Learned Database** | Living `lessons_learned.json` that grows with every session. |
| **Relevance Injection** | Past lessons matching current agenda injected into every member's system prompt. |
| **Reflection Round** | Post-execution critique. Chair extracts structured lessons and saves them. |

---

## Quick Start

```bash
# Install dependency
pip install openai

# Start the council in your project directory
python council.py --project ./my_project

# Or just start in current directory
python council.py
```

You'll see:

```
   ____                  _       _   _             _     
  / ___|___  _   _ _ __ | |_ ___| | | | ___   __ _| | __ 
 | |   / _ \| | | | '_ \| __/ __| |_| |/ _ \ / _` | |/ / 
 | |__| (_) | |_| | | | | |_\__ \  _  | (_) | (_| |   <  
  \____\___/ \__,_|_| |_|\__|___/_| |_|\___/ \__,_|_|\_\ 

  Project Love v4.0  |  NVIDIA API  |  Self-Improving Council

Type /help for commands. Type your agenda to start a council session.

council> 
```

---

## REPL Commands

| Command | Description |
|---------|-------------|
| `/add <file>` | Add a file to council context. Contents are injected into the agenda. |
| `/drop <file>` | Remove a file from context. |
| `/files` | List all files currently in context. |
| `/tree` | Show project file tree (git-aware, falls back to manual tree). |
| `/council` | Show current council members and their specs. |
| `/memory` | Show memory stats: sessions, lessons learned, corrections. |
| `/reset` | Clear session context (deliberation, assignments, outputs). Memory and lessons survive. |
| `/save` | Force save current session to disk. |
| `/rounds <n>` | Set number of deliberation rounds before task assignment (default: 2). |
| `/help` | Show this command list. |
| `/quit` or `/exit` | Leave the council. |
| **anything else** | Sent to the council as an agenda item. Triggers full deliberation → execution → synthesis → reflection → save. |

---

## Example Session

```bash
$ python council.py --project ./myapp
[CLI] Initializing Council...
[CLI] Project: /home/user/myapp
[CLI] Memory:  council_memory
[CLI] API:     NVIDIA (integrate.api.nvidia.com)

council> /add main.py
council> /add utils.py
council> /files
[Context] 2 file(s) in context:
  - main.py (2048 bytes)
  - utils.py (512 bytes)

council> Build me a web scraper that uses these utils

======================================================================
COUNCIL SESSION
Agenda: Build me a web scraper that uses these utils
Members: Nemotron, Minimax, Kimi
Memory: 3 sessions, 7 lessons
======================================================================

--- ROUND 1: OPENING STATEMENTS ---

[Nemotron]
Given the existing utils.py and main.py, we should first audit what utilities are available...
- Nemotron

[Minimax]
I see a `fetch_url()` helper in utils.py. We can build a scraper class around it...
- Minimax

[Kimi]
The current utils.py lacks error handling for timeouts. I recommend adding retry logic before building the scraper...
- Kimi

--- ROUND 2: DELIBERATION ---

[Nemotron]
Kimi raises a valid point about timeouts. Minimax, can you handle the retry logic?...
- Nemotron

[Minimax]
Agreed. I'll implement exponential backoff in utils.py and then build the scraper...
- Minimax

[Kimi]
I will verify the retry logic handles edge cases: DNS failure, 429 throttling, SSL errors...
- Kimi

--- FINAL ROUND: TASK ASSIGNMENT ---

[Nemotron]
I will handle the final synthesis and integration. Minimax will build the scraper and fix utils. Kimi will verify.
- Nemotron

[Minimax]
I claim: 1) Fix utils.py with retry logic, 2) Build scraper.py with fetch_url integration.
- Minimax

[Kimi]
I claim: Verify all error paths in utils.py and scraper.py. Report gaps.
- Kimi

--- CHAIR: STRUCTURED ASSIGNMENTS ---

[Nemotron - ASSIGNMENTS]
{
  "consensus_summary": "Build scraper using existing utils, add retry logic, verify error handling",
  "assignments": [
    {"member": "Minimax", "task": "Implement exponential backoff in utils.py and build scraper.py", "deliverable": "Working scraper.py + updated utils.py", "rationale": "Minimax is the builder and has 1M context to hold full codebase"},
    {"member": "Kimi", "task": "Verify error handling in utils.py and scraper.py", "deliverable": "Verification report with edge cases", "rationale": "Kimi is the analyst and verifier"}
  ],
  "review_process": "Kimi reviews Minimax's code before Nemotron synthesizes final output",
  "final_output_plan": "Nemotron produces final integrated response with all files"
}

======================================================================
EXECUTION PHASE
======================================================================

--- Minimax EXECUTING: Implement exponential backoff in utils.py and build scraper.py ---

[Minimax OUTPUT]
Here is the updated utils.py with retry logic:

[WRITE: utils.py]
```python
import time
import requests
from typing import Optional

def fetch_url(url: str, retries: int = 3, backoff: float = 1.0) -> Optional[str]:
    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=10)
            resp.raise_for_status()
            return resp.text
        except requests.exceptions.RequestException as e:
            if attempt == retries - 1:
                raise
            time.sleep(backoff * (2 ** attempt))
    return None
```

And the new scraper.py:

[WRITE: scraper.py]
```python
from utils import fetch_url
from bs4 import BeautifulSoup

class WebScraper:
    def __init__(self):
        self.visited = set()

    def scrape(self, url: str):
        html = fetch_url(url)
        soup = BeautifulSoup(html, 'html.parser')
        return soup.find_all('a')
```
  [Success] Wrote utils.py (512 chars)
  [Success] Wrote scraper.py (312 chars)

--- Kimi EXECUTING: Verify error handling in utils.py and scraper.py ---

[Kimi OUTPUT]
Verification report:
1. utils.py: Exponential backoff correctly handles 429, 503, timeouts. Missing: SSL certificate verification flag.
2. scraper.py: No handling for `None` return from fetch_url. Missing: User-Agent header.

[WRITE: review_report.md]
```markdown
# Review Report
- Add `verify=True` to requests.get()
- Handle None in scraper.py before BeautifulSoup parsing
- Add headers={'User-Agent': '...'} to avoid blocks
```
  [Success] Wrote review_report.md (189 chars)

======================================================================
FINAL SYNTHESIS
======================================================================

[Nemotron - FINAL]
The council has produced:
1. **utils.py** — Updated with exponential backoff retry logic
2. **scraper.py** — New scraper class using existing utilities
3. **review_report.md** — Kimi's verification with 3 recommended improvements

Next steps: Apply Kimi's recommendations (SSL verify, None handling, User-Agent) and test against target URLs.
- Nemotron

======================================================================

[Memory] Session saved: council_memory/sessions/session_4_2026-06-15T03-04-00.json

council> /memory
[Memory] Sessions: 4 | Lessons: 7 | Corrections: 2
[Memory] Directory: council_memory

council> /quit
[Goodbye] Council session ended.
```

---

## How It Works

### 1. Interactive REPL
Unlike the old fire-and-run script, v4.0 stays alive. You can:
- Add files to context incrementally
- Run multiple agendas in one session
- Check memory stats between runs
- Reset context without losing lessons

### 2. File System Integration
**For you:**
- `/add src/main.py` — injects file contents into the next agenda
- `/tree` — see what files exist in the project
- `/files` — see what's currently loaded

**For council members:**
- Members can output `[WRITE: path]` followed by a code block to create files
- Members can output `[READ: path]` to read files during execution
- The orchestrator parses these directives and executes them on your local filesystem

### 3. 1M Context with Auto-Compression

| Member | Context Window | Output (max_tokens) | Available Input |
|--------|---------------|---------------------|-----------------|
| **Minimax M3** | **1,000,000** | 8,192 | ~991,000 |
| Nemotron 3 Ultra | 128,000 | 16,384 | ~111,000 |
| Kimi K2.6 | 256,000 | 16,384 | ~239,000 |

When deliberation history exceeds a member's budget:
1. **Minimax M3** (the historian with 1M window) reads the full raw history
2. Summarizes old rounds into dense context (preserving decisions, objections, assignments)
3. Keeps the **last 2 rounds in full detail**
4. Sends the compressed pack to the member with the smaller window

### 4. Self-Correction Loop

```
Session N:          Session N+1:
  /add files            /add files
  Agenda ->             Load relevant lessons
  Deliberate  ->        Deliberate (with injected wisdom)
  Execute     ->        Execute (avoiding past mistakes)
  Finalize    ->        Finalize
  Reflect     ->        Reflect
  Save        ->        Save
```

After every session:
- Every member critiques what went wrong
- Chair extracts structured lessons
- Saved to `lessons_learned.json`
- Before the next session, matching lessons are injected into all system prompts

---

## Directory Structure

```
your_project/
├── council_memory/              # Auto-created
│   ├── sessions/
│   │   ├── session_0_2026-06-15T02-35-00.json
│   │   └── ...
│   ├── lessons_learned.json     # Living wisdom database
│   └── council_memory.jsonl     # Append-only master log
├── council.py                   # This script
├── utils.py                     # Your files
├── scraper.py
└── review_report.md
```

---

## CLI Options

```bash
python council.py --help

Options:
  --project, -p     Project directory (default: current dir)
  --memory-dir, -m  Memory directory (default: council_memory)
  --rounds, -r      Default deliberation rounds (default: 2)
```

---

## Adding a 4th (or Nth) Model

```python
gemini = CouncilMember(
    name="Gemini",
    title="Real-Time Data Specialist",
    role="You specialize in real-time information retrieval...",
    client=OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key="nvapi-..."),
    model="google/gemini-...",
    max_tokens=8192,
    context_window=1000000
)
council.add_member(gemini)
```

The REPL, memory system, reflection round, and auto-compressor work for any number of members automatically.

---

## Multimodal Inputs (Minimax M3)

Minimax M3 accepts images and video. When the council assigns Minimax a visual task, the member can use:

```python
# In execution output:
[READ: image.png]
```

Or manually construct multimodal messages in the `speak()` method if you extend the code.

---

## API Notes

- **Endpoint:** `https://integrate.api.nvidia.com/v1`
- **Keys:** NVIDIA API keys (format: `nvapi-...`)
- **Library:** `openai` Python package used purely as an HTTP client for the OpenAI-compatible format
- **You are NOT calling OpenAI's servers.** You are calling NVIDIA's API.

---

## Why Sequential > Concurrent

| Concurrent | Sequential Council |
|------------|-------------------|
| All models fire at once, no cross-talk | Models see each other's reasoning, build on it |
| No task ownership | Explicit assignment with rationale |
| Risk of redundant/conflicting outputs | Debate resolves conflicts before execution |
| No quality gate | Kimi (Analyst) vets plans before Minimax (Builder) executes |
| Faster wall-clock | Slower but higher-quality, coherent, defensible output |

This is a **council**, not a cluster.

---

*CounciL Strategic Systems — Project Love v4.0 (Interactive Agentic CLI)*
