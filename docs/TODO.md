# TODO — deferred work items

This file tracks deferred action items surfaced by reviews. Each item is
actionable, has an estimated priority, and explains why it was deferred.

Last updated: 2026-04-20 (code review of `core/screen_recorder.py`).

## Provenance

Source reviews (kept as provenance):
- `_workspace/01_style_review.md`
- `_workspace/04_architecture_review.md`
- `_workspace/05_review_summary.md`

---

## Deferred from `core/screen_recorder.py` review

### P1-1 — GOD_OBJECT split (extract `CaptureThread` to own module)

- **Priority:** P1 (maintainability)
- **Scope:** Move `CaptureThread`, `draw_cursor_internal`,
  `draw_click_highlight_internal` to `core/capture_worker.py`.
- **Estimated effort:** half-day of focused refactor work.
- **Reason deferred:** Multi-module move with test import updates;
  explicitly listed as "skip P1 GOD_OBJECT split — multi-day refactor"
  in the review-fixes task prompt. Apply in next refactor window so the
  file drops below 500 LOC and exits GOD_OBJECT status.
- **Acceptance:**
  - `core/screen_recorder.py` under 700 LOC.
  - `core/capture_worker.py` contains `CaptureThread` + draw helpers.
  - Public API of `ScreenRecorder` unchanged (tests still pass).

### P1-2 — `shm_*` naming cleanup (partial)

- **Priority:** P1
- **Scope:** Rename `shm_buffer` → `_frame_buffer`,
  `_thread_shm_event` → `_frame_ready_event`,
  `_thread_shm_processed_event` → `_frame_consumed_event` across the
  CaptureThread public API (constructor args, attribute names).
- **Status partial:** Module docstring now explains the naming (shm_*
  is legacy for threading.Event coordination, not SharedMemory). See
  commit `fd1d983` (D1 note in docstring).
- **Reason fully deferred:** The rename would change
  `CaptureThread.__init__` parameter names — borderline "public API".
  Within-file tests construct CaptureThread directly in
  `tests/test_screen_recorder_runtime.py` via `_FailingCaptureThread`
  mock which inherits the constructor signature; renaming kwargs
  forces test updates. Bundle with P1-1 (module split) to do once.
- **Acceptance:** No symbol in the codebase still contains `shm_`
  unless referring to `multiprocessing.SharedMemory`.

### P1-4 — `CaptureBackend.warm_up()` ABC extension

- **Priority:** P1
- **Scope:** Add abstract `warm_up() -> bool` method to
  `core/capture_backend.py::CaptureBackend`. Implement on `DXCamBackend`
  and `GDIBackend`. Remove concrete `DXCamBackend` import from
  `screen_recorder._warmup_backend`.
- **Reason deferred:** Changes
  `core/capture_backend.py` (ABC extension) which is outside the target
  file of this fix-wave. Close OCP violation on next refactor window.

### P1-5 — Deduplicate cursor drawing

- **Priority:** P1
- **Scope:** Remove `ScreenRecorder._draw_cursor` (L587+) and keep only
  the top-level `draw_cursor_internal`. Update `capture_single_frame`
  to call the free function. (Or extract to `core/overlays/cursor.py`.)
- **Reason deferred:** Removing the method changes an arguably-internal
  API (no external callers found via Grep, but `_draw_cursor` underscore
  prefix is only a convention). Deferring to pair with the overlay-
  dedup refactor.

### P1-6 — Add `CaptureBackend.supports_managed_color` property

- **Priority:** P1
- **Scope:** Replace string-compare `backend_name == "gdi"` HDR gating
  at `capture_single_frame` (L342) and `CaptureThread.run` (L967) with
  a polymorphic property on the backend.
- **Reason deferred:** Touches `CaptureBackend` ABC + concrete backends
  (outside target file).

### P1-8 (fully) — Warmup nested `except Exception` collapse

- **Status partial:** Inner `except Exception` narrowed to
  `(ImportError, OSError, RuntimeError)` in commit `3727bc0`.
- **Fully deferred action:** Move warm-up logic out of
  `ScreenRecorder` into the backend (`CaptureBackend.warm_up()`) so
  the 4-level nested try/except disappears entirely. Depends on P1-4.

### P1-10 — Frame-copy overhead (known issue)

- **Priority:** P1 (perf — doc only)
- **Scope:** Two `frame.copy()` / `np.copyto` copies per frame
  (~720 MB/s at 1080p@60). Worker copies once, collector copies once.
- **Reason deferred:** Acceptable today; document as known-issue.
  Revisit only if profiler shows collector-thread memcpy as a
  bottleneck. Optimization would require a `queue.Queue`-of-size-1
  frame-handoff redesign — not currently user-visible.

### Architecture — inject backend factory (testability)

- **Priority:** P1 (testing)
- **Scope:** Add `backend_factory: Callable[[str], CaptureBackend] = None`
  constructor arg on `ScreenRecorder.__init__`. Falls back to module-
  level `create_capture_backend` when None. Enables unit tests with
  fake backends to avoid monkey-patching module state.
- **Reason deferred:** Additive API change and nontrivial test
  refactor; bundle with P1-1/P1-4 refactor wave.

---

## Deferred from project-wide ruff sweep

### Remaining ruff warnings (396 issues)

Count summary after `ruff check . --fix` sweep:

| Code    | Count | Meaning |
|---------|-------|---------|
| W293    | 235   | Blank line contains whitespace (hidden/unsafe fixes only) |
| SIM105  | 85    | `contextlib.suppress` preference over try/except/pass |
| SIM102  | 17    | Collapsible `if` |
| F841    | 13    | Local variable assigned but unused |
| F401    | 10    | Unused imports |
| E741    | 9     | Ambiguous variable name (`l`, `I`, `O`) |
| B007    | 7     | Loop control variable not used in body |
| SIM101  | 5     | Multiple isinstance calls — merge |
| E731    | 5     | lambda assignment |
| Other   | —     | See `ruff check .` output |

- **Reason deferred:** These warnings are spread across the project,
  not the target file. A blanket project-wide sweep is out of scope
  for the current task (`core/screen_recorder.py` review). Each cluster
  warrants its own review to confirm intent (especially F841 which can
  hide real bugs, not just style).
- **Recommendation:** Run targeted cleanups per-module during future
  feature work; don't mass-apply unsafe auto-fixes without human review.

---

## Notes on commit history

Per-fix commits from 2026-04-20 review wave (newest first):

```
056b070 style: 프로젝트 전역 ruff --fix 정리 (P2)
fd1d983 style: 모듈 상수 추출 및 안전한 P2 정리 (R1, R3, R5, R6, R7, R8, N5, D2, D3, D4)
7b408b0 refactor: dead fields/methods 제거 (P1-9)
3727bc0 refactor: except 핸들러 디버거빌리티 개선 (P1-7, P1-8, R9)
9fe789c fix: __del__ 제거 + backend.stop() hard-kill 폴백 (P0-3, P0-4)
42fda27 fix: teardown race & _capture_thread_ref 정리 (P0-1, P1-3)
3441957 fix: 오버레이 중복 소유 제거 (P0-2)
```
