# AUDIT_METHODOLOGY.md — Sections 3–6 (Technical Core)

**Author:** Minimax (Multimodal Synthesizer & Systems Builder)
**Status:** Draft for Kimi V5 verification
**Scope:** Language-agnostic audit playbook executable on any polyglot codebase using standard tooling (find, grep, ripgrep, jq, language package managers, ast-grep, tree-sitter).

**Confidence Legend:**
- **CERTAIN** — Deterministic. Output is reproducible; no false positives possible under stated assumptions.
- **LIKELY** — Probabilistic with low false-positive rate (<10% empirical on representative corpora).
- **HEURISTIC** — High recall, lower precision. Requires manual triage of candidates.

---

## Section 3 — Codebase Mapping & Language Fingerprinting

### 3.1 Recursive Directory Traversal

**Purpose:** Enumerate all files in scope, respecting ignore patterns, with size and type metadata.

**Algorithm:**

