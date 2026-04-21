# TODO — deferred work items

This file tracks deferred action items surfaced by reviews. Each item is
actionable, has an estimated priority, and explains why it was deferred.

Last updated: 2026-04-21 (deferred `core/screen_recorder.py` P1 wave executed).

## Status of prior deferrals

All P1 items previously deferred from the 2026-04-20 `core/screen_recorder.py`
review were executed on 2026-04-21:

- **P1-1 + P1-2** — `CaptureThread`, `draw_cursor_internal`,
  `draw_click_highlight_internal` extracted to `core/capture_worker.py`.
  `shm_*` kwargs renamed to `frame_*`. `screen_recorder.py` dropped from
  1,138 → 667 LOC (below 700 target, exits GOD_OBJECT status).
- **P1-4** — `CaptureBackend.warm_up()` added as ABC default no-op.
  DXCam override runs a short start→grab→stop; GDI/FastGDI override
  pre-imports PIL.ImageGrab. `screen_recorder._warmup_backend` reduced
  from a 4-level nested try/except to a single `backend.warm_up()` call
  (closes P1-8 fully).
- **P1-5** — `ScreenRecorder._draw_cursor` deleted. Single caller
  (`capture_single_frame`) now uses free `draw_cursor_internal`.
- **P1-6** — `CaptureBackend.supports_managed_color` property added.
  `backend_name == "gdi"` string compares at `capture_single_frame` and
  `CaptureThread.run` replaced with polymorphic dispatch.
- **P0-4 hardening** — `CaptureBackend.force_release()` promoted to ABC
  default no-op. `DXCamBackend` override clears `_camera` to allow GC of
  the DXGI duplicator after a failed `stop()`. Duck-typing `hasattr` in
  `CaptureThread` cleanup path removed.
- **Architecture — backend factory** — `ScreenRecorder.__init__` gained
  `backend_factory: Callable[[str], CaptureBackend] | None = None`.
  `capture_single_frame` passes the factory to `_start_backend_with_fallback`,
  which now also accepts a `factory=` kwarg. Unit tests can inject fakes
  without `monkeypatch`. Covered by new
  `test_backend_factory_injection_avoids_monkeypatch` in
  `tests/test_screen_recorder_runtime.py`.

### Module layout after the split

| File | Role | Approx LOC |
|------|------|------------|
| `core/capture_backend.py` | ABC + DXCam/GDI/FastGDI + fallback helpers | ~730 |
| `core/capture_worker.py` (new) | `CaptureThread` + drawing helpers | ~420 |
| `core/screen_recorder.py` | Facade (`ScreenRecorder`) + collector loop | ~670 |

`core/screen_recorder.py` continues to re-export `CaptureThread`,
`draw_cursor_internal`, `draw_click_highlight_internal`, and
`CLICK_HIGHLIGHT_DURATION` so existing `monkeypatch.setattr(sr, "CaptureThread", ...)`
tests keep working.

---

## Provenance

Source reviews (kept as provenance):
- `_workspace/01_style_review.md`
- `_workspace/04_architecture_review.md`
- `_workspace/05_review_summary.md`

---

## Deferred from project-wide ruff sweep

### Remaining ruff warnings (project-wide)

Count summary (unchanged from 2026-04-20):

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

- **Reason deferred:** These warnings are spread across the project, not
  limited to any single refactor target. A blanket project-wide sweep
  warrants per-cluster review to confirm intent (especially F841 which
  can hide real bugs).
- **Recommendation:** Run targeted cleanups per-module during future
  feature work; don't mass-apply unsafe auto-fixes without human review.

### Known-issue (doc-only)

**P1-10 — Frame-copy overhead.** Two `frame.copy()` / `np.copyto` copies
per frame (~720 MB/s at 1080p@60). Worker copies once, collector copies
once. Not currently user-visible; the redesign (queue.Queue-size-1
hand-off) is non-trivial. Revisit only if profiler shows collector-thread
memcpy as a bottleneck.

---

## Notes on commit history

Per-fix commits from the 2026-04-20 → 2026-04-21 review wave (newest first):

```
(2026-04-21)
<this commit>    refactor: CaptureThread 모듈 분리 + frame_* 리네임 + factory 주입
2efe3d5          refactor: CaptureBackend ABC 확장 + warm-up 흡수 (P1-4, P1-6, P1-8, P1-5)

(2026-04-20)
a3d8d23          docs: 2026-04-20 리뷰 수정 사항 및 deferred TODO 기록
056b070          style: 프로젝트 전역 ruff --fix 정리 (P2)
fd1d983          style: 모듈 상수 추출 및 안전한 P2 정리 (R1, R3, R5, R6, R7, R8, N5, D2, D3, D4)
7b408b0          refactor: dead fields/methods 제거 (P1-9)
3727bc0          refactor: except 핸들러 디버거빌리티 개선 (P1-7, P1-8, R9)
9fe789c          fix: __del__ 제거 + backend.stop() hard-kill 폴백 (P0-3, P0-4)
42fda27          fix: teardown race & _capture_thread_ref 정리 (P0-1, P1-3)
3441957          fix: 오버레이 중복 소유 제거 (P0-2)
```
