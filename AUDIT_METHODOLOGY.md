# AUDIT_METHODOLOGY.md
## Codebase Redundancy Detection & Dependency Optimization Playbook

---

## Section 1: Executive Summary & Strategic Framing

### 1.1 Purpose

This document is a **self-contained, tool-agnostic audit methodology** for detecting redundancies, optimizing dependencies, and producing a high-level summary report of any software codebase. It is designed to be executed by a single developer or small team using only standard CLI tooling available in typical development environments (Node.js, Python 3, Rust, Go, and standard Unix utilities).

**No proprietary tooling, no CI pipeline integration, no special permissions required.** Clone the target repo, open a terminal, follow the playbook.

### 1.2 Strategic Framing

Software projects accumulate three categories of drag over time:

| Drag Category | Symptom | Cost if Unaddressed |
|---------------|---------|---------------------|
| **Structural Redundancy** | Duplicate/near-duplicate functions, copy-pasted components, reimplemented utilities | Increased maintenance surface, inconsistent bug fixes, onboarding friction |
| **Dependency Bloat** | Unused packages, overlapping libraries (two HTTP clients, two date libs), version drift with CVEs | Larger attack surface, slower builds, supply-chain risk, license compliance burden |
| **Temporal Drift** | Dead code paths, stale TODO/FIXME comments, feature flags for shipped features, config for decommissioned environments | Cognitive load, false confidence in test coverage, deployment accidents |

This methodology targets all three. It produces **actionable findings**, not academic metrics. Every flagged item includes a falsification test so the auditor can prove or disprove the finding before acting.

### 1.3 Expected Outcomes

| Mode | Time Investment | Output |
|------|-----------------|--------|
| **Quick Scan** (15–30 min) | Sections 3.1–3.3, 4.1, 5.1–5.2 | File tree, language fingerprint, top 10 dependency bloat candidates, obvious dead code |
| **Standard Audit** (2–4 hr) | All sections | Full redundancy register, dependency optimization plan with effort/impact scores, deletion-safety verification log |
| **Deep Audit** (1–2 days) | Standard + custom AST rules, cross-repo analysis | Organization-wide pattern library, architectural decision records for consolidation |

### 1.4 Non-Goals

This methodology does **not**:
- Rewrite code or automate refactors (human judgment required for semantic equivalence)
- Audit runtime performance or algorithmic complexity
- Replace security scanning tools (SAST/DAST/SCA) — it complements them
- Guarantee completeness — it provides falsifiable hypotheses, not proofs

---

## Section 2: Scope Boundaries & Constraints

### 2.1 In-Scope Artifacts

| Category | Included | Detection Method |
|----------|----------|------------------|
| **Source code** | All tracked files in VCS (git/hg) | `git ls-files` / `hg manifest` |
| **Manifest files** | `package.json`, `Cargo.toml`, `pyproject.toml`, `requirements.txt`, `go.mod`, `go.sum`, `Gemfile`, `Gemfile.lock`, `pom.xml`, `build.gradle*`, `composer.json`, `mix.exs`, `pubspec.yaml` | Extension/name matching |
| **Configuration** | `.env*`, `docker-compose*.yml`, `Dockerfile*`, `.github/workflows/*`, `.gitlab-ci.yml`, `Jenkinsfile`, `Makefile*`, `justfile`, `Taskfile*` | Path/name patterns |
| **Build scripts** | `scripts/*`, `tools/*`, `build/*`, `*.sh`, `*.ps1`, `*.py` in build dirs | Heuristic + manifest cross-ref |
| **Documentation** | `README*`, `CHANGELOG*`, `CONTRIBUTING*`, `docs/*`, `*.md` in root | Extension + location |

### 2.2 Explicitly Out-of-Scope

| Category | Rationale |
|----------|-----------|
| **Build artifacts** (`node_modules/`, `target/`, `dist/`, `build/`, `*.pyc`, `__pycache__/`, `vendor/`) | Generated, not source; analyzed via manifests instead |
| **VCS internals** (`.git/`, `.hg/`) | Not part of codebase logic |
| **Secrets/credentials** (`.env.local`, `*.pem`, `*.key`, `secrets/*`) | Security boundary; audit separately |
| **Large binary assets** (>10 MB: videos, datasets, model weights) | Size-profiled in asset inventory but not redundancy-scanned |
| **Generated code** (protobuf outputs, GraphQL codegen, `*.g.dart`, `*_pb2.py`, `*.gen.go`) | Marked `derived: true`; excluded from refactor targets, included in dependency accounting |
| **Third-party vendored source** | Treated as external dependency; audit the source repo instead |

### 2.3 Environment Assumptions

| Tool | Minimum Version | Purpose |
|------|----------------|---------|
| `git` | 2.30+ | File enumeration, history queries |
| `find` / `fd` | any | Recursive traversal |
| `grep` / `rg` (ripgrep) | 13+ | Pattern search |
| `jq` | 1.6+ | JSON manifest parsing |
| `yq` | 4+ | YAML/TOML manifest parsing |
| `node` / `npm` / `npx` | 18+ | JS/TS ecosystem analysis |
| `python3` / `pip` | 3.10+ | Python ecosystem analysis |
| `cargo` | 1.70+ | Rust ecosystem analysis |
| `go` | 1.21+ | Go ecosystem analysis |
| `ast-grep` / `tree-sitter` CLI | latest | Structural code search (optional but recommended) |

**If a tool is missing**, the corresponding language track is skipped with a warning. The methodology degrades gracefully — no single tool is a hard dependency for the whole audit.

### 2.4 Polyglot Handling

- Each detected language gets an **independent scan pass** with language-specific heuristics
- Cross-language redundancy (e.g., same business logic in Python service + TS client) is flagged as **semantic redundancy candidates** requiring manual review
- Shared configuration (Docker, CI, Make) is analyzed once and attributed to all relevant languages

---

## Section 7: Prioritization Matrix, Final Assembly & User Handoff

### 7.1 Prioritization Matrix: Effort vs. Impact Scoring Rubric

Every finding from Sections 4–6 is scored on two axes:

#### Impact Score (1–5)

| Score | Label | Definition |
|-------|-------|------------|
| 5 | **Critical** | Security exposure (CVE in transitive dep), production outage risk, legal/license violation |
| 4 | **High** | Measurable build time reduction (>10%), bundle size reduction (>5%), developer velocity blocker |
| 3 | **Medium** | Code clarity improvement, maintenance burden reduction, test reliability gain |
| 2 | **Low** | Cosmetic consistency, minor DRY violation, outdated comment |
| 1 | **Negligible** | Whitespace, style nits, deprecated-but-harmless pattern |

#### Effort Score (1–5) — *Lower is easier*

| Score | Label | Definition |
|-------|-------|------------|
| 1 | **Trivial** | Single-file delete, version pin bump, unused import removal (<5 min) |
| 2 | **Easy** | Multi-file pattern replace with codemod/ast-grep, dead config removal (<30 min) |
| 3 | **Moderate** | Cross-module refactor requiring semantic verification, test updates (1–4 hr) |
| 4 | **Hard** | Architecture-level consolidation (e.g., two HTTP clients → one), migration plan (1–3 days) |
| 5 | **Epic** | Multi-repo coordination, breaking API changes, stakeholder alignment (weeks) |

#### Priority Classification

| Impact \ Effort | 1 Trivial | 2 Easy | 3 Moderate | 4 Hard | 5 Epic |
|-----------------|-----------|--------|------------|--------|--------|
| **5 Critical** | **P0 – Do Now** | **P0 – Do Now** | **P1 – This Sprint** | **P1 – This Quarter** | **P2 – Roadmap** |
| **4 High** | **P0 – Do Now** | **P1 – This Sprint** | **P1 – This Sprint** | **P2 – This Quarter** | **P3 – Backlog** |
| **3 Medium** | **P1 – This Sprint** | **P1 – This Sprint** | **P2 – This Quarter** | **P3 – Backlog** | **P4 – Icebox** |
| **2 Low** | **P2 – This Quarter** | **P3 – Backlog** | **P3 – Backlog** | **P4 – Icebox** | **P4 – Icebox** |
| **1 Negligible** | **P4 – Icebox** | **P4 – Icebox** | **P4 – Icebox** | **P4 – Icebox** | **P4 – Icebox** |

**P0** = Execute immediately, no approval needed  
**P1** = Schedule in current sprint/iteration  
**P2** = Plan for next quarter  
**P3** = Backlog, revisit at planning  
**P4** = Icebox, unlikely to act

#### Scoring Procedure

1. **Impact** is assessed by the auditor using the definitions above + project context (e.g., a 5% bundle reduction is High for a mobile app, Medium for a backend service)
2. **Effort** is estimated using the deletion-safety checklist (Section 6) — each unchecked gate adds +1 effort
3. **Both scores are recorded** in the findings register (Appendix A template)
4. **Disputes** are resolved by the team lead or designated architect — documented in `SCORING_NOTES.md`

### 7.2 Report Assembly Template

The final deliverable is a single markdown file: `AUDIT_REPORT_<repo>_<YYYYMMDD>.md`

