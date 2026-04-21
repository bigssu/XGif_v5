# Harness Invocation Sequences — XGif

For each of the four user-facing triggers, this file defines the exact Task
call sequence the main session must perform: which agents to summon, in what
order, which model tier, and which prelude text to prepend to each agent's
prompt. The main session drives every Task call directly so that preludes can
be re-injected per agent (the LLM has no session cache across Task boundaries).

**Pre-conditions every trigger** (see `workflow-orchestrator.md`):

1. The workspace entry cleanup protocol has already run (`_workspace/` is fresh).
2. Grade (S/M/L) and domain are known.
3. Domain-harness activation matrix has been checked.
4. Sequential execution is honored — no other trigger is running concurrently.

---

## `/code-reviewer`

Writes to `_workspace/00_input.md` plus `01_style_review.md`,
`02_security_review.md`, `03_performance_review.md`,
`04_architecture_review.md`, `05_review_summary.md` (M-grade writes only the
subset in the reduced table below).

**L-grade — full 5-agent pipeline** (fan-out 1–4 parallel → 5 sequential):

| # | Agent | Model | Prelude |
|---|-------|-------|---------|
| 1 | `style-inspector` | sonnet | `prelude-style-inspector` |
| 2 | `security-analyst` | sonnet (or opus via `--opus=security-analyst`) | none |
| 3 | `performance-analyst` | sonnet | none |
| 4 | `architecture-reviewer` | **opus** (L-grade auto-override) | `prelude-architecture-reviewer` |
| 5 | `review-synthesizer` | sonnet | none |

If `review-synthesizer` reports unresolved high-severity findings, treat as
BLOCK and report to the user.

**M-grade — 3-agent reduced**: summon `style-inspector` (with its prelude),
then `architecture-reviewer` (with its prelude), then `review-synthesizer`.
Skip security and performance. `--review=full` upgrades M-grade to the full
5-agent sequence above.

**`--plan-only <path>`**: summon only `architecture-reviewer` (opus, with its
prelude). Pass the plan.md path in the prompt. No other agents run.

**S-grade**: do not summon. Main session runs `ruff check` and verifies
architecture boundaries manually.

---

## `/test-automation`

**Pre-check**: disabled for `bootstrapper-installer` domain. If `ui-only-skip`
is set (gif-editor, edits limited to `editor/ui/`), emit a manual smoke-test
notice and skip the summon.

**M/L-grade — full 5-agent pipeline** (1 → 2 ∥ 3 → 4 → 5):

| # | Agent | Model | Prelude |
|---|-------|-------|---------|
| 1 | `test-strategist` | sonnet | none |
| 2 | `unit-tester` | sonnet | none |
| 3 | `integration-tester` | sonnet | `prelude-integration-tester` |
| 4 | `coverage-analyst` | sonnet | none |
| 5 | `qa-reviewer` | sonnet | none |

`qa-reviewer` may SendMessage back to prior agents up to 2 times. After the
retry cap, note unresolved gaps in `_workspace/05_review_report.md` and exit.

**S-grade**: do not summon. Main session runs `pytest tests/ -v` directly.

---

## `/performance-optimizer`

**Pre-check**: L-grade only, and only when plan.md carries
`[performance-review]` or the profiler detects a regression. Disabled for
`bootstrapper-installer` domain.

**L-grade — strictly sequential 5-agent pipeline** (each step feeds the next):

| # | Agent | Model | Prelude |
|---|-------|-------|---------|
| 1 | `profiler` | sonnet | none |
| 2 | `bottleneck-analyst` | sonnet | none |
| 3 | `optimization-engineer` | sonnet (or opus via `--opus=optimization-engineer`) | `prelude-optimization-engineer` |
| 4 | `benchmark-manager` | sonnet | none |
| 5 | `perf-reviewer` | sonnet | none |

`perf-reviewer` may SendMessage back to `optimization-engineer` up to 2 times.
`optimization-engineer` MUST NOT directly edit files under `core/`; all
proposed changes are written to `_workspace/03_optimization_plan.md` and the
main session applies accepted changes via Edit.

---

## `/cli-tool-builder`

**Pre-check**: only for a release cut (STEP 6) or a `bootstrapper-installer`
task. Use the 2-agent subset. `command-designer`, `core-developer`,
`test-engineer` MUST NOT be summoned.

**2-agent release pipeline** (1 ∥ 2):

| # | Agent | Model | Prelude |
|---|-------|-------|---------|
| 1 | `release-engineer` | sonnet | `prelude-release-engineer` |
| 2 | `docs-writer` | sonnet | none |

The two agents exchange SendMessage to cross-check version/build results. On
smoke-test failure, the main session reports the log and requests manual
debugging — no automated retry.

Outputs: `dist/XGif_{version}.exe`, `installer/XGif_Setup_{version}.exe`,
`_workspace/04_documentation.md`, `_workspace/05_release_config.md`,
`CHANGELOG.md` append.

---

## Agent Prelude Bodies

Prepend verbatim at the top of each Task prompt when the associated agent is
summoned. Re-inject every time.

### `prelude-release-engineer`

```
당신은 XGif 프로젝트의 릴리스 엔지니어입니다.
- 배포 대상은 PyPI/npm/Homebrew가 아닙니다. PyInstaller + Inno Setup 기반 Windows 전용 인스톨러.
- 빌드 진입점: `build_optimized.py` (PyInstaller 래퍼, 982 LOC).
- PyInstaller spec: `XGif.spec` / Inno Setup 스크립트: `installer/xgif_setup.iss`.
- 산출물: `dist/XGif_{version}.exe` (smoke-test 부팅 필수),
  `installer/XGif_Setup_{version}.exe`.
- 버전 관리: `core/version.py` 가 Single Source of Truth. 빌드 전 수동 bump.
- GitHub Actions·CI·PyPI 업로드는 XGif에 없습니다 (manual upload).
- BootStrapper BAT 배포(478MB embedded Python + FFmpeg)는 이 스텝 범위 밖.
CI/CD·PyPI publish·conventional commits 권고를 제안하지 마세요.
```

### `prelude-integration-tester`

```
당신은 XGif 프로젝트의 통합 테스트 엔지니어입니다.
- XGif는 HTTP API 서비스나 DB 백엔드가 아닙니다. capture → 프레임 버퍼 → FFmpeg 인코딩 파이프라인.
- 통합 테스트 대상: 캡처 백엔드 스위칭(DXCam / FastGDI / GDI 폴백), FFmpeg 서브프로세스 수명주기
  (try-finally로 kill 보장 — rules/ffmpeg-subprocess.md), 프레임 버퍼→인코더 전달
  (SharedMemory 또는 파이프), 에디터의 frame collection load/save + Undo/Redo.
- HTTP mock, DB containers, REST API 테스트, Testcontainers는 해당 없음.
- Fixture 전략: DXCam은 mock, FFmpeg은 stub subprocess, wx 의존 코드는 테스트하지 않음
  (아키텍처 경계 — core/ 테스트에 wx import 금지).
- UI 테스트(wx GUI)는 자동화 제외. manual smoke 유지.
Flask/FastAPI/Django 가정으로 mock DB/API를 제안하지 마세요.
```

### `prelude-style-inspector`

```
당신은 XGif 프로젝트의 스타일 리뷰어입니다.
- Linter: ruff (target py311, line-length 120). pyproject.toml이 SSoT.
- 코딩 표준: `CLAUDE.md` 의 "## 필수 패턴" 섹션 + `.claude/rules/*.md` 5개 파일.
- 특히 검사할 항목:
  - bare except 금지 → `except Exception:` 사용 (wx-patterns.md)
  - wx.CallAfter() 사용 여부 (배경 스레드에서 GUI 호출 시)
  - FFmpeg subprocess try-finally + kill() 패턴 (ffmpeg-subprocess.md)
  - core/ 에 wx import 금지 (architecture-boundaries.md)
- Black·isort·flake8 제안 금지 — ruff가 커버.
```

### `prelude-architecture-reviewer`

```
모듈 경계 검사 기준: `.claude/rules/architecture-boundaries.md`.
- core/ → wx import 금지, core/ ↔ ui/ 의존성 단방향 (ui → core)
- cli/ → wx import 금지
- editor/ → 독립 wxPython 서브시스템, core/ 호출 허용, ui/와 공유 모듈 최소화
- BootStrapper/ → 독립 앱, XGif 본체 모듈 import 금지
GOD_OBJECTS (3개 파일, 2026-04-21 갱신): `ui/main_window.py` (1,983 LOC),
`core/capture_backend.py` (~733 LOC), `core/gif_encoder.py`. 수정 시 책임 범위 확장 여부 평가 필요.
`core/screen_recorder.py` 는 P1 refactor 이후 680 LOC 파사드로 축소되어 GOD_OBJECT 에서 제외되었고,
CaptureThread 는 `core/capture_worker.py` 로 분리됨.
CRITICAL_DIRS: `editor/ui/` — 디렉터리 단위. GOD_OBJECT와 구별. 두 분류 모두 최소 M-grade
승격 대상이며, 개별 파일 risk 등급만 다르다.
CRITICAL_FILES (권고 ≥ M): `core/screen_recorder.py`, `core/capture_worker.py` — 책임 밀도는 여전히 높음.
```

### `prelude-optimization-engineer`

```
최적화 타겟 영역:
- 캡처: DXCam 풀링, FastGDI ring buffer
- 프레임 버퍼: multiprocessing.SharedMemory (대용량 프레임 pickling 금지)
- FFmpeg 파이프: async stderr, 파이프 throughput
- GPU: CuPy 선택적 가속, pynvml 모니터링
UI 스레드 블로킹 금지. 무거운 작업은 별도 프로세스/스레드 (CLAUDE.md "핵심 원칙").
쓰기 정책: `core/` 소스를 직접 수정하지 말 것. 모든 제안은
`_workspace/03_optimization_plan.md` 에 기록하고, 최종 반영은 메인 세션이 Edit으로 수행.
```
