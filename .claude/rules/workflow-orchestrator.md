# Workflow Orchestrator — XGif

This rule file governs how the main session routes any development task through
the XGif workflow (Explore → Implement → Test → Review → Optimize → Package →
Release). The main session is a **router**; methodology execution is delegated
to pre-installed harness skills (`/test-automation`, `/code-reviewer`,
`/performance-optimizer`, `/cli-tool-builder`). See
`harness-invocation.md` for the exact agent chains each trigger runs.

## Main Session Role

The main session MUST only:

1. Receive the task description and affected file list.
2. Evaluate the Complexity Gate (S/M/L).
3. Detect the target domain from file-path prefixes.
4. Apply the entry cleanup protocol before any harness trigger.
5. Invoke the appropriate harness skill(s) via Task calls as specified in
   `harness-invocation.md`.
6. Report harness results back to the user.

**Do not** run the methodology directly for M/L grades (no direct `pytest`
invocation, no self-performed code review, no profiling). For S-grade tasks,
the main session is permitted to implement and lint directly without summoning
any agent.

---

## Grade Assessment (Complexity Gate)

**GOD_OBJECTS (SSoT — 3 files, any touch forces ≥ M-grade):**

```
GOD_OBJECTS = {
    "ui/main_window.py",            # 1,983 LOC, UI entry point
    "core/capture_backend.py",       # DXCam/FastGDI/GDI ABC + pool + fallback (~733 LOC)
    "core/gif_encoder.py",           # FFmpeg pipe control
}
```

> `core/screen_recorder.py` 는 2026-04-21 P1 refactor (커밋 `d29aabf`) 이후
> 680 LOC 의 파사드로 축소되었고 CaptureThread 는 `core/capture_worker.py`
> 로 분리되었다. GOD_OBJECT 목록에서 제외. 다만 `core/capture_worker.py`
> (~450 LOC) 와 `core/screen_recorder.py` 는 여전히 **CRITICAL_FILES** 로
> 간주하여 수정 시 M-grade 승격을 권고한다 (책임 밀도는 여전히 높음).

**CRITICAL_DIRS (auto-promote to ≥ M):** `editor/ui/`

**CRITICAL_FILES (권고 ≥ M, 강제 아님):**
- `core/screen_recorder.py` — facade + collector thread
- `core/capture_worker.py` — capture thread + overlay drawing

**Grade decision (upward bias — promote when in doubt):**

1. If any diff file is in `GOD_OBJECTS` or starts with `editor/ui/`
   → `min_grade = "M"`.
2. If the diff adds a new external dependency (edits to `requirements*.txt`)
   OR introduces a brand-new `core/` subsystem module → `grade = "L"`.
3. Else if `len(diff.files) <= 5` AND `max(changed_lines_per_file) <= 80`
   AND no rule files are touched AND no new test files are added
   → `grade = "S"`.
4. Else if `len(diff.files)` is in 6..15 OR 1–2 design decisions are required
   → `grade = "M"`.
5. Else → `grade = "L"`.
6. `grade = max(grade, min_grade)`.

**S-grade protection conditions** (S may remain S only for): single-file
single-function edits, trivial bug fixes (one conditional, constant tweak),
ruff auto-fix, docstring/comment cleanup. Anything broader promotes to M.

**Downgrades**: only allowed when the user explicitly passes `--grade=S`.

---

## Grade-Step Mapping

| Grade | Steps executed | Notes |
|-------|---------------|-------|
| S | STEP 2 (Implement, main session) → STEP 3 (lightweight `pytest`, main session) | No agent summoned. |
| M | STEP 1 (Explore) → STEP 2 (Implement) → STEP 3 (`/test-automation`) → STEP 4 (`/code-reviewer`, 3-agent reduced) | plan.md is a solo self-review — no automated reviewer. L-grade promotion invokes the pre-implementation plan review. |
| L | STEP 1 (Explore, with optional `architecture-reviewer` plan review) → STEP 2 (Implement, optional inline `optimization-engineer`) → STEP 3 (`/test-automation`, full 5-agent) → STEP 4 (`/code-reviewer`, full 5-agent) → STEP 5 (`/performance-optimizer`, conditional) → STEP 6 (`/cli-tool-builder`, release intent) → STEP 7 (Release, main session) |

STEP 5 runs only when plan.md carries a `[performance-review]` flag OR the
profiler flags a regression. STEP 6-7 run only when the user explicitly asks
for a release cut.

---

## Domain Detection

Detect from file-path prefixes of the affected files:

| Prefix | Domain |
|--------|--------|
| `core/` or `ui/` | `screen-recording` |
| `editor/` | `gif-editor` |
| `BootStrapper/` | `bootstrapper-installer` |
| (anything else, or multi-domain) | `screen-recording` (default, most conservative rule set) |

### Domain-Harness Activation Matrix

| Domain | Active harnesses | Disabled harnesses | Rationale |
|--------|-----------------|-------------------|-----------|
| `screen-recording` | `/test-automation`, `/code-reviewer`, `/performance-optimizer` | `/cli-tool-builder` (manual activation only on release cuts) | Default domain. |
| `gif-editor` | `/test-automation` (editor/core only), `/code-reviewer`, `/performance-optimizer` | `/cli-tool-builder` | `editor/ui/` is wxPython GUI → set `ui-only-skip` flag, which makes `/test-automation` emit a manual smoke-test notice and skip the summon. |
| `bootstrapper-installer` | `/code-reviewer`, `/cli-tool-builder` | **`/test-automation` disabled**, `/performance-optimizer` disabled | BAT-based installer, pytest is not applicable; no perf target. |

---

## Slash Command Mapping

| Trigger | When to invoke | Maps to workflow step(s) |
|---------|---------------|--------------------------|
| `/code-reviewer` | M/L STEP 4; standalone PR review; L STEP 1 plan-review (via `architecture-reviewer`) | STEP 4 (+ STEP 1 L-grade plan check) |
| `/test-automation` | M/L STEP 3; standalone test-expansion session | STEP 3 |
| `/performance-optimizer` | L STEP 5 when `[performance-review]` flag set or regression detected | STEP 5 |
| `/cli-tool-builder` | STEP 6 release cut; BootStrapper domain tasks | STEP 6 |

For each trigger, the full Task-call sequence (agent roster, model, prelude
text, output files) is defined in `harness-invocation.md`.

---

## Workspace Entry Cleanup Protocol

Every `/code-reviewer`, `/test-automation`, `/performance-optimizer`, and
`/cli-tool-builder` invocation MUST be preceded by this cleanup. It is not
optional and runs **before** any agent is summoned.

1. If `_workspace/` exists, rename it to `_workspace.prev-{YYYYMMDD-HHMMSS}/`.
   (Rename — not delete — so the user can re-inspect the previous run.)
2. If there are more than 3 `_workspace.prev-*` folders, delete the oldest
   ones until at most 3 remain.
3. Create a fresh empty `_workspace/`.
4. Enter the harness skill.

**Sequential execution is mandatory.** Never invoke two of the four triggers
in parallel. Starting a second trigger before the first has finished will
clobber the shared `_workspace/` root.

**gitignore ownership**: `_workspace/` and `_workspace.prev-*` are both
expected to sit under `.gitignore` (installed separately from this rule file).

---

## Review Mode Flags

| Flag | Effect |
|------|--------|
| `--review=full` | Forces M-grade STEP 4 into the 5-agent full pipeline (adds `security-analyst` + `performance-analyst`). No effect on L-grade (already full). |
| `--opus={agent-name}` | Overrides the model for one agent in the current invocation to `opus` (e.g., `/code-reviewer --opus=security-analyst`). The default is `sonnet` for every agent except `architecture-reviewer` on L-grade, which auto-overrides to `opus`. |
| `--grade=S` | User-forced downgrade. The only way to escape auto-promotion from GOD_OBJECTS / CRITICAL_DIRS. Use sparingly. |
| `--plan-only <path>` | `/code-reviewer` runs only `architecture-reviewer` against the supplied plan.md. Used for manual pre-implementation plan review on M-grade. |

---

## Optimization Write Policy

`optimization-engineer` MUST NOT write directly to source files under `core/`.
`optimization-engineer` MUST write every proposed change as a suggestion inside
`_workspace/03_optimization_plan.md`. Direct source edits to `core/` require
explicit main-session confirmation and are performed by the main session using
Edit, not by `optimization-engineer`. This rule survives all grade paths.

Other write-scope conventions (text-only policy, not hook-enforced):

| Agent role | Permitted writes |
|-----------|------------------|
| All harness agents | `_workspace/` (current session only) |
| `unit-tester` / `integration-tester` | + `tests/`, `tests/integration/` |
| `benchmark-manager` | + `tests/benchmarks/` (if present) |
| `docs-writer` | + `CHANGELOG.md` |
| `release-engineer` | + build-log output only (never source edits) |

Violations are detected at `git diff` review, not at tool-invocation time.

---

## Retry Policy & Timeout

| Pipeline | max_retries | On retry-exhaustion | Timeout |
|----------|------------|--------------------|---------|
| STEP 1 Explore | 2 (main session self-retry) | Ask user to narrow the task | 15 min |
| STEP 2 Implement | 3 (2 auto lint-fix + 1 manual) | Report diff to user | User-paced |
| STEP 3 `/test-automation` | 2 (qa-reviewer SendMessage loop) | Note the gap in `_workspace/05_review_report.md` and continue | 10 min per agent / 40 min chain |
| STEP 4 `/code-reviewer` | 2 (review-synthesizer re-analysis loop) | Leave unresolved findings listed in the summary | 10 min per agent / 50 min chain (parallel 4-way fan-out) |
| STEP 5 `/performance-optimizer` | 2 (perf-reviewer SendMessage loop) | Report benchmarks + unresolved regressions | 15 min per agent / 60 min chain |
| STEP 6 `/cli-tool-builder` | 1 (build rebuild is deterministic; inspect log instead) | Report build log, request manual debug | 10 min |
| STEP 7 Release | 0 (manual) | — | — |

Retry counters run **independently** of reviewer BLOCK rounds. A pipeline can
exhaust retries while separately accruing BLOCK rounds; both count in parallel.

---

## Hook Invocation Hints

A pre-commit reminder hook (`precommit-m-grade-reminder`) is expected under
`.claude/hooks/` (installed separately). It is non-blocking and prints a
suggestion to run `/code-reviewer` when any of these hold:

- `git diff --cached` touches ≥ 2 files
- ≥ 3 new `def ` lines added
- ≥ 1 new `import` / `from ... import` line added
- Diff touches any file in `GOD_OBJECTS` or under `editor/ui/`

The reminder never blocks the commit. If false-positive noise becomes
distracting, raise the thresholds in the hook config (not in this rule file).
