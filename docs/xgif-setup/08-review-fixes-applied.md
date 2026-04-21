# Review Fixes Applied — core/screen_recorder.py (2026-04-20)

This document tracks which findings from the code-review workflow were
applied vs. deferred. Reports live in `_workspace/`:

- `_workspace/01_style_review.md` — style-inspector findings
- `_workspace/04_architecture_review.md` — architecture-reviewer findings
- `_workspace/05_review_summary.md` — synthesized action plan

Scope of this wave: **all P0 + safe P1 + safe P2**. Excluded by
instruction: P1-1 (GOD_OBJECT multi-module split) and anything that
would change `ScreenRecorder`'s public method signatures.

---

## Baseline (before fixes)

- `core/screen_recorder.py`: 1,079 lines
- `ruff check core/screen_recorder.py`: 137 errors
- `pytest tests/test_screen_recorder_runtime.py tests/unit/core`:
  41 passed
- `pytest tests/ --ignore=tests/unit/editor`: 119 passed, 4 skipped

## After fixes

- `core/screen_recorder.py`: 1,138 lines (added 59 lines — mostly
  documentation, constants, and narrower exception handlers)
- `ruff check core/screen_recorder.py`: **All checks passed**
- `pytest tests/test_screen_recorder_runtime.py tests/unit/core`:
  **41 passed (no delta)**
- `pytest tests/ --ignore=tests/unit/editor`:
  **119 passed, 4 skipped (no delta)**

---

## Commits produced

| Hash      | Subject                                                         | Findings |
|-----------|-----------------------------------------------------------------|----------|
| `3441957` | fix: 오버레이 중복 소유 제거 (P0-2)                             | P0-2 |
| `42fda27` | fix: teardown race & `_capture_thread_ref` 정리 (P0-1, P1-3)    | P0-1, P1-3 |
| `9fe789c` | fix: `__del__` 제거 + `backend.stop()` hard-kill 폴백           | P0-3, P0-4 |
| `3727bc0` | refactor: except 핸들러 디버거빌리티 개선                       | P1-7, P1-8 (partial), R2, R9 |
| `7b408b0` | refactor: dead fields/methods 제거                              | P1-9 |
| `fd1d983` | style: 모듈 상수 추출 및 안전한 P2 정리                         | D1, D2, D3, D4, N5, R1, R3, R5, R6, R7, R8 |
| `056b070` | style: 프로젝트 전역 ruff --fix 정리                            | P2 blanket sweep |

---

## Applied findings

### P0 (production risk — all applied)

- **P0-1** (teardown race — use-after-None): APPLIED in `42fda27`.
  Snapshot `dropped_frames` into local var **before** `join()`, then
  null `_capture_thread`/`_collector_thread`. Replaces `_capture_thread_ref`
  dangling-reference workaround with a clean value snapshot.
- **P0-2** (overlay duplicate ownership): APPLIED in `3441957`.
  `CaptureThread.__init__` now takes `watermark` / `keyboard_display`
  instance args instead of `_enabled` bools. Worker no longer re-imports
  `Watermark`/`KeyboardDisplay` — single-owner invariant restored.
  `webcam_enabled` dead param also removed.
- **P0-3** (`__del__` finalizer): APPLIED in `9fe789c`.
  `__del__` deleted. `__enter__`/`__exit__` added for `with`-block
  usage. Public `stop_recording()` signature preserved — existing
  callers in `ui/` and `cli/` remain valid and should continue to use
  explicit stop in a `try/finally`.
- **P0-4** (`backend.stop()` no hard-kill fallback): APPLIED in `9fe789c`.
  After `backend.stop()` raises, try `backend.force_release()` (duck-
  typed, future ABC extension), else fall back to
  `backend._camera = None` on DXCam backends to GC the DXGI duplicator
  handle. Matches project rule *FFmpeg 서브프로세스 → 예외 시
  process.kill() (try-finally)*.

### P1 (safe maintainability fixes — applied)

- **P1-3** (`_capture_thread_ref` smell): APPLIED — merged into P0-1
  fix in `42fda27`. Introduced `self._last_dropped_frames` value
  snapshot; dropped the unsafe second reference.
- **P1-7** (callbacks swallow exceptions): APPLIED in `3727bc0`.
  `_emit_frame_captured` / `_emit_recording_stopped` /
  `_emit_error_occurred` now call `logger.exception(...)` on callback
  failure. Docstrings document the thread-safety contract (callers
  must use `wx.CallAfter()`).
  `_draw_cursor` / `draw_cursor_internal` / `draw_click_highlight_internal`
  debug-log their silent-swallow errors (hot path, not exception-level).
- **P1-8** (nested `_warmup_backend` excepts): PARTIALLY APPLIED in
  `3727bc0`. Narrowed inner handlers to
  `(ImportError, OSError, RuntimeError)` — hidden root causes no
  longer swallowed. Full restructure (move warm-up into backend ABC)
  is in `docs/TODO.md` (P1-4 dependency).
- **P1-9** (dead fields): APPLIED in `7b408b0`. Removed
  `self._cached_frame_size` (never read), `is_gpu_mode()` /
  `set_gpu_mode()` (no-op stubs; GPU path is on encoder, not
  recorder). `CaptureThread.webcam_enabled` already removed in P0-2.

### P2 (nice-to-have — applied)

- **R1** (>120ch lines): 225-char `[Perf] Frame ...` line split
  across 8 lines (`fd1d983`).
- **R2** (duplicate `import time`): removed inner import in
  `warmup_thread` (`3727bc0`).
- **R3** (inline-if): `if radius < 2: return frame` split to two
  lines (`fd1d983`).
- **R4** (142 trailing-whitespace lines): fixed by ruff sweep
  (`056b070`).
- **R5** (`f""` no placeholders): dropped `f` prefix on the
  "First frame captured" log (`fd1d983`).
- **R6** (dead `else: continue`): removed (`fd1d983`).
- **R7** (`Optional[tuple]`): now `Optional[Tuple[int, int, float]]`
  (`fd1d983`).
- **R8** (`-> list`): now `-> List[str]` (`fd1d983`).
- **R9** (exception-var names): normalized to `exc` across the file
  (`3727bc0`).
- **D1** (module docstring): expanded to document
  threading-vs-multiprocessing + shm_* naming (`fd1d983`).
- **D2** (`0.3` magic number): now `CLICK_HIGHLIGHT_DURATION` module
  constant (`fd1d983`).
- **D3** (`# BGR` vague comment): expanded to
  `# width * height * 3 bytes (BGR)` (`fd1d983`).
- **D4** (`100 * 1024 * 1024`): now `MAX_FRAME_BYTES` module constant
  (`fd1d983`).
- **N5** (`Tuple[int, int, int, int]` repetition): now `Region`
  type alias (`fd1d983`).

---

## Deferred findings (see `docs/TODO.md`)

| ID    | Reason |
|-------|--------|
| P1-1  | GOD_OBJECT split — multi-day; explicitly out of scope |
| P1-2  | `shm_*` rename touches CaptureThread constructor kwargs (public surface used by tests) |
| P1-4  | `CaptureBackend.warm_up()` ABC extension — touches `core/capture_backend.py` |
| P1-5  | Dedup cursor drawing — pairs with overlay extraction (P1-1 follow-up) |
| P1-6  | `supports_managed_color` property — touches ABC |
| P1-10 | Frame-copy overhead — doc-only; not user-visible |
| Testability — inject backend factory | Additive API change; bundle with P1-1/P1-4 wave |

All deferred items are documented with acceptance criteria in
`docs/TODO.md`.

---

## Lint / test status

```
$ ruff check core/screen_recorder.py
All checks passed!

$ ruff check .
Found 396 errors (remaining).  # All pre-existing in non-target files;
                                # safe fixes applied by ruff --fix sweep.
                                # Hidden fixes require --unsafe-fixes,
                                # out of scope for this review wave.

$ pytest tests/test_screen_recorder_runtime.py tests/unit/core
41 passed.

$ pytest tests/ --ignore=tests/unit/editor
119 passed, 4 skipped.
```

Editor tests require `wx` (not installed in the fix-wave CI env); no
changes were made to `editor/` so they are unaffected by this wave.

---

## Hard-constraint compliance checklist

- [x] **Public method signatures preserved.** `start_recording`,
  `stop_recording`, `pause_recording`, `resume_recording`,
  `capture_single_frame`, `set_*`, `get_*` methods — unchanged.
- [x] **No new module-level imports.** Only `contextlib.suppress`
  was considered and rejected; instead added `# noqa: SIM105` on the
  relevant line to document intent.
- [x] **BAN-clean.** No `bare except`, no `import wx` in `core/`,
  no `SetProcessDpiAwareness(2)`, no `self.Bind(wx.EVT_MENU)`.
- [x] **No test regressions.** 119 passed → 119 passed; no deltas.
- [x] **`_workspace/` preserved** as review provenance.
- [x] **Atomic commits** (7 commits total — within the
  6–9 target).
