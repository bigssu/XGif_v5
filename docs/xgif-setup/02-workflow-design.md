---
phase: 3
completed: 2026-04-20T23:30:00Z
status: done
advisor_status: pending
---

# Workflow Design — XGif

## Summary

XGif is a Windows desktop app (~39,000 LOC, 137 source files) spanning three distinct
development domains: screen-recording (core capture/encoding pipeline), gif-editor
(editor/ subsystem), and bootstrapper-installer (BootStrapper/ independent app).
The workflow adopts a 7-step sequence — Explore → Implement → Test → Review → Optimize
→ Package → Release — that is entered via per-task routing through a Complexity Gate.
All four pre-installed harness-100 harnesses (code-reviewer, test-automation,
performance-optimizer, cli-tool-builder) are mapped to specific workflow steps, and no
new harnesses are proposed for Phase 5-6 beyond supplemental agents for the
screen-recording domain. The workflow is designed for solo development: user-triggered
steps are kept to a minimum (one slash command per development loop iteration), and
steps the user enters once are meant to self-chain from there.


## STEP -1: Complexity Gate (태스크 크기 분류)

**Applicability trigger**: XGif's codebase exceeds both Complexity Gate thresholds
(LOC ~39,000 > 5,000; source files 137 > 100). This gate MUST precede every
implementation task.

작업 시작 전 다음 기준으로 경로를 선택한다.

| 등급 | 기준 | 경로 |
|------|------|------|
| S (소형) | 파일 5개 이하 + 해법 자명 + 외부 API/신규 의존성 없음 | 메인 세션 직접 구현 허용 |
| M (중형) | 파일 5–15개 또는 설계 결정 1–2개 | 단축 파이프라인 (planner 병합 → implementer → QA) |
| L (대형) | 신규 기능, 외부 라이브러리 도입, 복잡 의존성, UI 재구성 | 전체 파이프라인 |

등급 판단이 애매하면 상향(S→M, M→L) 기본. 다운그레이드는 사용자 명시 요청 시에만.

Specialist Review(security/performance/architecture)는 L 등급이고 해당 플래그가
plan.md에 명시된 경우에만 트리거한다. S/M 등급에는 QA 단독으로 진행한다.


## Workflow Overview

```
[STEP -1: Complexity Gate]
         │
         ├─ S 등급 ──→ [STEP 2: Implement] ──→ [STEP 3: Test (경량)] ──→ Done
         │
         ├─ M 등급 ──→ [STEP 1: Explore] ──→ [STEP 2: Implement] ──→ [STEP 3: Test]
         │                                                         ──→ [STEP 4: Review] ──→ Done
         │
         └─ L 등급 ──→ [STEP 1: Explore] ──→ [STEP 2: Implement] ──→ [STEP 3: Test]
                                                                   ──→ [STEP 4: Review]
                                                                   ──→ [STEP 5: Optimize]  (해당 시)
                                                                   ──→ [STEP 6: Package]   (릴리스 준비 시)
                                                                   ──→ [STEP 7: Release]   (배포 시)
```

**Step 5 (Optimize)** and **Steps 6-7 (Package/Release)** are conditional branches, not
required on every iteration. Optimize is triggered when a performance flag is raised in
code review or profiling results. Package/Release are triggered explicitly when the
developer decides to cut a version.


## Domain-Specific Branches

The 7-step sequence is the same across all three domains. What differs is:
- Which modules are in scope (and therefore which rule files are enforced)
- Which test types run
- Which harnesses are active

| Domain | Primary modules | Domain-specific test concern | Active harnesses |
|--------|----------------|------------------------------|-----------------|
| screen-recording | core/, ui/ | Capture backend switching, FFmpeg process cleanup, thread safety | code-reviewer, test-automation, performance-optimizer |
| gif-editor | editor/ | Frame collection memory, Undo/Redo correctness, GPU fallback | code-reviewer, test-automation, performance-optimizer |
| bootstrapper-installer | BootStrapper/ | BAT execution, dependency download resilience, path normalization | code-reviewer, cli-tool-builder |

**Isolation rule for BootStrapper**: BootStrapper is an independent Python application
with its own `requirements.txt`. Tasks in this domain do not invoke the main project's
pytest suite and do not import from core/ or editor/. The cli-tool-builder harness is
the primary review vehicle because BootStrapper's interface is a BAT-driven installer.


## Work-Step Specifications

---

### STEP 1 — Explore

**Purpose**: Understand the task scope, identify affected modules, and produce a
plan.md before writing any code. Mandatory for M and L grades; skipped for S grade.

**Entry criteria**: Complexity Gate has classified the task as M or L.

**Exit criteria**: `plan.md` written at `docs/tasks/{task-name}/plan.md` describing
affected files, design decisions, and (for L grade) any `[design-review]`,
`[security-review]`, or `[performance-review]` flags.

**Inputs**:
- Task description from the user
- `XGif_Architecture_Review.txt` (73KB architecture reference — treat as the project
  code-map; read relevant sections only)
- Applicable `.claude/rules/*.md` files for the domain in scope
- Existing source files in affected modules

**Outputs**:
- `docs/tasks/{task-name}/plan.md` — scoped implementation plan
- List of files to be created or modified
- Any specialist review flags for STEP 4

**Recommended harness/skill**: No harness trigger. Main session reads source files and
produces plan.md directly. For L-grade tasks touching architecture boundaries, the
`architecture-reviewer` agent (from code-reviewer harness) may be summoned to review
the plan before implementation starts.

**Trigger**: Manual. User invokes the development loop; main session decides grade and
runs Explore if M/L.

**User-triggered**: No (internal to the loop; user triggers the overall task, not this
step individually).

---

### STEP 2 — Implement

**Purpose**: Write or modify source code according to plan.md, following all rules in
`.claude/rules/*.md` and CLAUDE.md coding standards.

**Entry criteria**:
- S grade: task received directly
- M/L grade: plan.md exists and is approved (user did not object)

**Exit criteria**: All planned files are written; ruff passes without errors; no bare
`except:` clauses introduced; wx.CallAfter() used wherever GUI is called from a
background thread; FFmpeg subprocesses wrapped in try-finally with `process.kill()`.

**Inputs**:
- plan.md (M/L grade) or task description (S grade)
- Relevant source files
- `.claude/rules/wx-patterns.md`, `ffmpeg-subprocess.md`, `architecture-boundaries.md`,
  `windows-encoding.md`

**Outputs**:
- Modified/created Python source files
- (Optional) `docs/tasks/{task-name}/impl-notes.md` for L-grade changes

**Recommended harness/skill**: No harness. Implementation is main-session or delegated
sub-agent coding work. The `optimization-engineer` agent (performance-optimizer harness)
may be summoned inline for performance-critical core/ code if the task involves capture
pipeline or encoder changes.

**Trigger**: Automatic continuation from STEP 1 (M/L), or direct (S).

**User-triggered**: No.

---

### STEP 3 — Test

**Purpose**: Verify the implementation with pytest. Ensure existing tests still pass
and add new tests for any new behavior.

**Entry criteria**: Implementation is complete and ruff passes.

**Exit criteria**:
- `pytest tests/ -v` passes (all existing tests green)
- New tests added for new public functions in core/ or cli/ (coverage target: core/ 80%+,
  CLI 90%+, editor/core/ 70%+)
- No wx-dependent code tested in core/ tests (architecture boundary enforced)

**Inputs**:
- Modified source files from STEP 2
- Existing `tests/` suite
- `.claude/rules/testing-standards.md`

**Outputs**:
- New or updated test files under `tests/`
- pytest run output (pass/fail summary)

**Recommended harness/skill**: `/test-automation` — invoke the test-automation harness.
- `test-strategist`: decides which test types (unit/integration) are needed
- `unit-tester`: writes pytest unit tests for core/ and cli/ modules
- `integration-tester`: writes integration tests for recording flow, editor load/save
- `coverage-analyst`: reports coverage gaps and prioritizes new tests
- `qa-reviewer`: final sign-off on test quality

For S-grade tasks affecting only UI (ui/) or BootStrapper/, a lightweight manual pytest
run suffices without invoking the full harness.

**Trigger**: Manual slash command `/test-automation` after implementation, or automatic
call from the development loop for M/L tasks.

**User-triggered**: Yes (for standalone test expansion sessions). No (automatic within
full loop).

---

### STEP 4 — Review

**Purpose**: Multi-perspective code review covering style, security, performance hot
spots, and architecture conformance.

**Entry criteria**: Tests pass (STEP 3 completed).

**Exit criteria**: All High-severity findings resolved or explicitly deferred with a
written rationale. Medium/Low findings may be accepted as known debt.

**Inputs**:
- Changed source files (diff since last commit or since plan.md was written)
- `.claude/rules/*.md` (all 5 rule files as review checklist)
- `plan.md` (for L-grade architecture conformance check)

**Outputs**:
- Review report (surfaced in session; not written to a file unless L-grade)
- List of findings with severity and resolution actions

**Recommended harness/skill**: `/code-reviewer` — invoke the code-reviewer harness.
- `style-inspector`: ruff conformance, naming, docstrings
- `security-analyst`: Windows subprocess injection, path traversal, bare except leaks
- `performance-analyst`: frame-path hot spots, unnecessary copies, lock contention
- `architecture-reviewer`: module boundary violations (wx in core/, cli/ importing ui/)
- `review-synthesizer`: consolidated findings with priority ordering

For S-grade tasks, `style-inspector` + `architecture-reviewer` alone (skip full harness
invocation).

**Trigger**: Manual `/code-reviewer` after STEP 3.

**User-triggered**: Yes.

---

### STEP 5 — Optimize (Conditional)

**Purpose**: Address performance findings flagged in STEP 4 or user-identified
bottlenecks. Triggered only when a `[performance-review]` flag is present or when
profiling identifies a regression.

**Entry criteria**: STEP 4 complete AND (`[performance-review]` flag in plan.md OR
profiler output shows regression).

**Exit criteria**: Bottleneck addressed; benchmark comparison documented.

**Inputs**:
- Performance findings from STEP 4 review
- Profiler output (if available)
- Core capture pipeline files: `core/screen_recorder.py`, `core/capture_backend.py`,
  `core/gif_encoder.py`

**Outputs**:
- Optimized source files
- Before/after benchmark notes

**Recommended harness/skill**: `/performance-optimizer` — invoke the
performance-optimizer harness.
- `profiler`: instruments capture/encode paths with cProfile or line_profiler
- `bottleneck-analyst`: identifies frame copy overhead, lock contention, FFmpeg pipe
  throughput issues
- `optimization-engineer`: implements ring buffer, DXCam pooling, async stderr
  patterns from Architecture Review section 5
- `perf-reviewer`: validates optimization correctness (no race conditions introduced)
- `benchmark-manager`: before/after FPS, encode time, memory usage

**Trigger**: Manual `/performance-optimizer`. Skipped if no performance flag raised.

**User-triggered**: Yes.

---

### STEP 6 — Package

**Purpose**: Build a distributable artifact (PyInstaller exe + Inno Setup installer)
and verify the package boots correctly.

**Entry criteria**: All STEP 3-4 gates passed; user decides to cut a release candidate.

**Exit criteria**:
- `build_optimized.py` completes without error
- `dist/XGif_{version}.exe` launches and basic record/stop cycle completes
- Inno Setup produces `installer/XGif_Setup_{version}.exe`
- BootStrapper BAT (`BootStrapper/XGif_Setup.bat`) is tested on a clean path

**Inputs**:
- Clean source tree (no uncommitted changes)
- `core/version.py` (Single Source of Truth — version bumped before this step)
- `XGif.spec`, `build_optimized.py`, `installer/xgif_setup.iss`

**Outputs**:
- `dist/XGif_{version}.exe`
- `installer/XGif_Setup_{version}.exe`

**Recommended harness/skill**: `/cli-tool-builder` — the release-engineer and
docs-writer agents cover the build verification and changelog update tasks.
- `release-engineer`: runs `build_optimized.py`, captures build log, verifies exe
- `docs-writer`: updates `CHANGELOG.md` with the new version entry

For BootStrapper-specific packaging (the BAT/embedded Python distribution), this step
is a manual build outside the Python ecosystem; no harness is applicable.

**Trigger**: Manual. User explicitly requests a release build.

**User-triggered**: Yes.

---

### STEP 7 — Release

**Purpose**: Tag the Git commit, finalize CHANGELOG, and (optionally) produce a
GitHub release artifact.

**Entry criteria**: Package verified in STEP 6.

**Exit criteria**:
- `git tag v{version}` created on main branch
- `CHANGELOG.md` updated
- Release artifacts available for distribution (manual upload or script)

**Inputs**:
- Verified dist/ artifacts from STEP 6
- `CHANGELOG.md`

**Outputs**:
- Git tag
- Updated CHANGELOG

**Recommended harness/skill**: No harness. Manual git operations. The docs-writer agent
from cli-tool-builder harness may be used to draft CHANGELOG entries.

**Trigger**: Manual.

**User-triggered**: Yes.


## Dependencies

```
[STEP -1: Complexity Gate]
    │
    ├─ S ──→ [STEP 2: Implement] ──→ [STEP 3: Test (경량)] ──→ Done
    │
    ├─ M ──→ [STEP 1: Explore] ──→ [STEP 2: Implement] ──→ [STEP 3: Test]
    │                                      │                       │
    │                                      │                       ▼
    │                                      └──────────────→ [STEP 4: Review] ──→ Done
    │
    └─ L ──→ [STEP 1: Explore] ──→ [STEP 2: Implement] ──→ [STEP 3: Test]
                                          │                       │
                                          │                       ▼
                                          └──────────────→ [STEP 4: Review]
                                                                  │
                                              ┌───────────────────┤
                                              │ (perf flag)       │ (release intent)
                                              ▼                   ▼
                                    [STEP 5: Optimize]   [STEP 6: Package]
                                              │                   │
                                              └──────┬────────────┘
                                                     ▼
                                            [STEP 7: Release]
```

**Dependency types**:
- STEP 1 → STEP 2: Sequential (plan.md must exist before coding)
- STEP 2 → STEP 3: Sequential (code must compile/lint before testing)
- STEP 3 → STEP 4: Sequential (tests must pass before review)
- STEP 4 → STEP 5: Gate (performance flag required; otherwise skip)
- STEP 4 → STEP 6: Gate (user release intent required; otherwise stop at STEP 4)
- STEP 5 ∥ STEP 6: Parallelizable in principle (optimize and package are independent
  if separate tasks), but in practice sequential since optimize output feeds into package
- STEP 6 → STEP 7: Sequential


## Reused vs New Harnesses

| Workflow Step | Pre-installed Harness | Coverage Level | Gap / Supplement Needed |
|--------------|----------------------|----------------|------------------------|
| STEP 1 (Explore) | None | — | No harness needed; architecture-reviewer agent (from code-reviewer) usable for plan review on L-grade |
| STEP 2 (Implement) | None | — | No harness needed; optimization-engineer agent usable inline for core/ hot paths |
| STEP 3 (Test) | test-automation | Full | test-strategist, unit-tester, integration-tester, coverage-analyst, qa-reviewer all applicable. Gap: no GUI (wxPython) test agent — wx UI tests remain manual |
| STEP 4 (Review) | code-reviewer | Full | style-inspector, security-analyst, performance-analyst, architecture-reviewer, review-synthesizer all applicable. Gap: no Windows-specific security agent (subprocess injection, DLL hijack) — security-analyst covers this partially |
| STEP 5 (Optimize) | performance-optimizer | Full | profiler, bottleneck-analyst, optimization-engineer, perf-reviewer, benchmark-manager all applicable. Gap: none identified |
| STEP 6 (Package) | cli-tool-builder | Partial | release-engineer + docs-writer cover build verification and CHANGELOG. Gap: PyInstaller-specific build agent not installed — release-engineer handles generically |
| STEP 7 (Release) | cli-tool-builder | Partial | docs-writer for CHANGELOG only. Git tagging and distribution are manual |
| STEP -1 (Complexity Gate) | None | — | Gate logic runs in main session; no harness |

**Summary**: All four installed harnesses are utilized. No new harnesses are proposed
for Phase 5-6. The only uncovered gap is wxPython GUI automated testing (ui/ and
editor/ UI layer) — this is explicitly excluded as it requires a running Windows display
and is not automatable with the current pytest setup. Manual smoke-testing covers this
gap for now.


## Operational Guard Sections

Not applicable. XGif is not an agent-pipeline project. Workflow steps are short-lived
IDE operations or one-shot build/test scripts that complete within a single session.
No cross-session state handoff is required; each step produces concrete file artifacts
(plan.md, test files, source files) that are durable in the repository. Advisor Dim 13
may skip this section.


## Session Recovery Protocol

단일 세션 완결 워크플로우 — 복구 프로토콜 미필요.

Each workflow step produces committed or committable file artifacts. If a session is
interrupted, the developer can restart from the last completed step by reading the
most recent `docs/tasks/{task-name}/plan.md` (if it exists) to determine which step
was last completed.


## Rejected Alternatives

**Strict Coding 6-Step workflow**: Considered (signals: 137 files, ~39K LOC, pytest
config — 2/7 signals hit). Rejected per user decision in Escalation Resolution:
"솔로 개발자 + 기존 CLAUDE.md 코딩 표준으로 충분." Solo developer with well-defined
CLAUDE.md rules does not benefit from the full 6-step research/research-review gate
overhead.

**Separate workflows per domain**: Considered splitting screen-recording, gif-editor,
and bootstrapper into three independent top-level workflows. Rejected because all three
share the same Implement → Test → Review loop. Domain-specific variation is better
expressed as branch conditions within a single workflow (different modules in scope,
different test targets) rather than three separate workflow orchestrations.

**No Complexity Gate**: Considered omitting the gate for simplicity (solo developer).
Rejected because the codebase exceeds both LOC and file-count thresholds where
even small patches in a 1,983-LOC God Object (main_window.py) can cascade unexpectedly.
The gate directly prevents full-pipeline overhead for S-grade tasks (e.g., a 4-line
bug fix in gif_encoder.py).

**Deploy step**: Considered adding a Deploy step (e.g., GitHub Releases automation).
Rejected because XGif is distributed as a self-contained installer (BAT + exe), not
through a CI-driven pipeline. Distribution is currently a manual upload. A Deploy step
would be premature until a GitHub Actions workflow is established.

**Explore always required**: Considered requiring STEP 1 for every task. Rejected
because it adds unnecessary friction for well-understood S-grade changes (e.g., fixing
a known bug in a single function). S-grade tasks go directly to Implement.


## Context for Next Phase

**For Phase 4 (pipeline-design)**: the pipeline will translate each workflow step into
an agent execution chain. The following information is required:

### Step list with user-trigger flag

| Step | Name | User-triggered | Grade applies |
|------|------|----------------|---------------|
| -1 | Complexity Gate | Yes (implicit, at task start) | All |
| 1 | Explore | No (internal) | M, L |
| 2 | Implement | No (internal) | All |
| 3 | Test | Yes (standalone) / No (internal loop) | All |
| 4 | Review | Yes | M, L |
| 5 | Optimize | Yes (conditional) | L with perf flag |
| 6 | Package | Yes | Release intent only |
| 7 | Release | Yes | Release intent only |

### Multi-agent vs single-agent per step

| Step | Agent execution | Notes |
|------|----------------|-------|
| STEP -1 | Single (main session) | Grade assessment only; no sub-agent |
| STEP 1 | Single (main session) | architecture-reviewer optionally summoned for L |
| STEP 2 | Single (main session) | optimization-engineer optionally summoned for core/ |
| STEP 3 | Multi-agent (test-automation harness — 5 agents) | Full harness for M/L; lightweight for S |
| STEP 4 | Multi-agent (code-reviewer harness — 5 agents) | Full harness for L; partial (2 agents) for S/M |
| STEP 5 | Multi-agent (performance-optimizer harness — 5 agents) | Full harness |
| STEP 6 | Multi-agent (cli-tool-builder harness — 2 agents: release-engineer, docs-writer) | Partial harness |
| STEP 7 | Single (main session) | docs-writer optionally for CHANGELOG |

### Harness-to-step mapping (for pipeline agent chain design)

| Harness | Skill trigger | Steps it covers |
|---------|--------------|-----------------|
| code-reviewer | `/code-reviewer` | STEP 4; STEP 1 (architecture-reviewer only) |
| test-automation | `/test-automation` | STEP 3 |
| performance-optimizer | `/performance-optimizer` | STEP 5 |
| cli-tool-builder | `/cli-tool-builder` | STEP 6 (partial) |

### Completion conditions (for pipeline gate design)

- STEP 1: plan.md written to `docs/tasks/{task-name}/plan.md`
- STEP 2: ruff passes; no rule violations from `.claude/rules/*.md`
- STEP 3: `pytest tests/ -v` all green; new tests committed
- STEP 4: No High-severity unresolved findings
- STEP 5: Benchmark delta documented; no regression in STEP 3
- STEP 6: `dist/XGif_{version}.exe` verified bootable
- STEP 7: Git tag created; CHANGELOG updated

### Grade routing for pipeline

- S grade: 0 sub-agent invocations; main session only
- M grade: ≤ 3 sub-agent invocations (Explore optionally, Test harness, Review partial)
- L grade: full pipeline (all steps, full harness invocations)

### Domain branch signal for pipeline

The pipeline should detect domain from the primary file paths being modified:
- `core/` or `ui/`: screen-recording domain
- `editor/`: gif-editor domain
- `BootStrapper/`: bootstrapper-installer domain (cli-tool-builder harness preferred;
  test-automation harness not applicable to BAT-based installer)

### Session recovery requirement

Not applicable. Standard file-artifact checkpointing through git is sufficient.


## Files Generated

- `D:\ProjectX\XGif_v5\docs\xgif-setup\02-workflow-design.md` — this file (Phase 3 workflow design artifact)


## Escalations

[NOTE] Complexity Gate thresholds — the default thresholds (S: ≤5 files; M: 5–15 files;
L: >15 files or new external dependency) are proposed based on XGif's complexity profile.
These are recommendations; the user may adjust them in the workflow rule that Phase 4
will produce.

[NOTE] wxPython GUI test gap — no harness covers automated UI testing of wx windows
(ui/, editor/ui/). This is a known gap. The test-automation harness will cover core/
and cli/ unit/integration tests only. GUI testing remains manual smoke-testing until
a wx-compatible test framework (e.g., wx automation via pywinauto) is established.

[NOTE] code-navigation rule — `XGif_Architecture_Review.txt` (73KB) is treated as the
de-facto code map. The formal `code-navigation.md` rule was deferred to user preference
(Phase 1-2 Escalation Resolution). If the user wants the rule installed, it can be
added in Phase 7-8 (hooks/rules installation).

[NOTE] BootStrapper packaging step — STEP 6 covers only Python-side packaging
(PyInstaller + Inno Setup). The BootStrapper BAT distribution (478MB embedded Python +
FFmpeg) is a separate manual build process not covered by any installed harness. If
BootStrapper release automation is needed, a cli-tool-builder extension would be
appropriate.


## Next Steps

Phase 4: pipeline-design — summon `phase-pipeline` to translate this workflow into
concrete agent execution chains. Phase 4 needs to produce:
1. The D-1 main session routing logic (Complexity Gate → step selection)
2. Agent invocation sequences for STEP 3 (test-automation), STEP 4 (code-reviewer),
   STEP 5 (performance-optimizer), STEP 6 (cli-tool-builder partial)
3. Skill entry points for user-triggered steps (which slash commands map to which
   harness triggers)
4. The workflow orchestrator rule file that encodes the grade routing and domain
   branch detection logic

---

## Advisor Resolutions (2026-04-20, 자율 모드)

Phase 3 red-team advisor returned **PASS-WITH-NOTES** with two [ASK] items. 자율 모드
지침(`feedback_autonomous_mode.md`)에 따라 합리적 기본값으로 확정했다. Phase 4 pipeline
설계는 이 결정을 반영해야 한다.

### ASK-1: `_workspace/` 네임스페이스 충돌 → **harness별 서브디렉터리 채택**

- 문제: 4개 harness-100 하네스 모두 프로젝트 루트 `_workspace/`에 `00_input.md` ~
  `05_*.md` 동일 파일명으로 기록. 연속 실행 시 앞선 산출물 덮어씀 / 잘못된 재사용 위험.
- **결정**: 각 하네스가 자기 이름의 서브디렉터리만 사용하도록 고정.
  - `/test-automation` → `_workspace/test/`
  - `/code-reviewer` → `_workspace/review/`
  - `/performance-optimizer` → `_workspace/perf/`
  - `/cli-tool-builder` → `_workspace/cli/`
- **구현 책임**: Phase 4가 workflow orchestrator rule file에 경로 치환 규칙을 기록하여,
  하네스 skill.md의 `_workspace/` 참조가 실행 시 `_workspace/{harness-alias}/`로
  리다이렉트되도록 한다. 또는 각 스킬 호출 직전 main session이 해당 서브디렉터리로
  `cd` 또는 명시적 경로 인자를 주입한다.
- **gitignore**: `_workspace/` 루트 전체를 `.gitignore`에 추가 (Phase 7-8 단계에서 반영).
  산출물은 참고용이며 장기 보존 대상 아님.

### ASK-2: M-grade STEP 4(Review)의 manual trigger 약화 방지 → **commit-time 리마인더 훅**

- 문제: M-grade 경로에서 STEP 4가 user-triggered. 솔로 고속 반복 시 implement → commit
  습관으로 리뷰가 조용히 생략될 가능성.
- **결정**: STEP 4는 **mandatory gate로 승격하지 않는다** (솔로 개발자 속도 존중). 대신
  **Phase 7-8 훅 단계**에서 PreCommit 훅으로 "M-grade 작업입니다: `/code-reviewer` 실행을
  권장합니다" 알림만 띄우는 non-blocking 리마인더를 구현한다.
- **구현 책임**: Phase 4는 이 결정을 orchestrator rule file에 기록. Phase 7-8 훅 에이전트가
  `.claude/hooks/precommit-m-grade-reminder.sh` 등을 생성. 훅은 차단하지 않음 — 출력만.
- **탐지 기준**: 커밋 대상 파일이 2개 이상 OR 최근 편집된 파일이 M-grade 규모 키워드를
  포함(e.g., 새 함수 정의 ≥ 3개, 새 import ≥ 1개)할 때만 발동. 정확도보다 잡음 억제 우선.

### NOTE 처리 요약

| Advisor NOTE | 처리 |
|--------------|------|
| cli-tool-builder scope mismatch (Dim 1) | Phase 5에서 release-engineer 소환 시 "PyInstaller + Inno Setup 배포 대상" 컨텍스트를 명시적으로 주입하도록 agent team 프롬프트에 규정. |
| God Object 파일 grade under-classification (Dim 4) | Phase 4에서 Complexity Gate 규칙에 "지정 파일 목록(`ui/main_window.py`, `editor/ui/*`, `core/screen_recorder.py`) 수정 시 기본 등급 상향" 추가. |
| integration-tester API/DB 가정 (Dim 7) | Phase 5에서 integration-tester 소환 시 "XGif는 capture→encode 파이프라인, HTTP/DB 아님" 컨텍스트 주입. |
| Session Recovery not applicable (Dim 13) | 조치 없음 — 이미 문서화됨. |

### Phase 4 지시 변경점

Phase 4는 상기 **ASK-1 / ASK-2 결정을 orchestrator rule file에 반영**해야 한다. 추가로
**Phase 5에 전달할 agent-invocation 컨텍스트 주입 요구사항**(cli-tool-builder PyInstaller
컨텍스트, integration-tester capture 파이프라인 컨텍스트)을 Phase 5 입력 문서에 명시해야
한다.
