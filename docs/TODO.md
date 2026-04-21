# TODO — deferred work items

리뷰에서 surfaced 된 추후 작업 항목 추적. 우선순위 + 지연 사유 명시.

Last updated: 2026-04-21 (크로스 리뷰 Action Plan 전량 수행 완료).

## 2026-04-21 현황

2026-04-20 리뷰에서 deferred 됐던 모든 P1 항목 + 2026-04-21 크로스
리뷰 Action Plan 12개 항목을 전부 실행. 현재 남은 활성 deferred 는 없음.

### 완료된 2026-04-21 리팩터 요약

#### Phase A — 2026-04-20 P1 deferred 회수 (커밋 `2efe3d5`, `d29aabf`)

- **P1-1 + P1-2** — `CaptureThread`, `draw_cursor_internal`, `draw_click_highlight_internal`
  을 `core/capture_worker.py` 로 분리. `shm_*` kwarg → `frame_*` 리네임.
  `screen_recorder.py` 1,138 → 680 LOC (< 700 목표, GOD_OBJECT 상태 탈출).
- **P1-4** — `CaptureBackend.warm_up()` ABC default no-op 추가. DXCam 은
  짧은 start→grab→stop, GDI/FastGDI 는 PIL ImageGrab 선행.
- **P1-5** — `ScreenRecorder._draw_cursor` 제거, `capture_single_frame` 이
  자유 함수 `draw_cursor_internal` 호출.
- **P1-6** — `CaptureBackend.supports_managed_color` property 추가.
  `backend_name == "gdi"` 문자열 비교 2 곳을 polymorphic 분기로 교체.
- **P1-8 (fully)** — `_warmup_backend` 의 4-level nested try/except 가
  `backend.warm_up()` 호출 한 줄로 축약.
- **P0-4 보강** — `CaptureBackend.force_release()` 를 ABC default no-op 승격.
- **Backend factory DI** — `ScreenRecorder.__init__(backend_factory=None)` 추가.

#### Phase B — 2026-04-21 크로스 리뷰 Action Plan (커밋 `2284ec7`..`f8baa1c`)

L-grade `/code-reviewer` 크로스 리뷰 (style/security/performance/architecture
4-agent 병렬 + review-synthesizer) 결과 **FLAG** 판정. High 2 + Medium 5 +
Low 3 + 문서 1 을 아래와 같이 모두 반영:

- **P1-A (High)** — `DXCamBackend.force_release()` 가 인스턴스 `_camera` 만
  정리하고 클래스 레벨 `_shared_camera` 를 손상된 채 두던 버그 수정.
  이제 `_camera_lock` 내부에서 동일 객체면 양쪽 참조를 모두 None 처리 +
  손상 카메라 stop() best-effort. 자기증폭 실패 루프 차단.
- **P1-B (High)** — `_warmup_backend` daemon thread 를 top-level
  `try/except Exception: logger.exception` 으로 감싸 unhandled 예외가
  daemon 에서 소멸되는 경로 차단. `DXCamBackend.warm_up()` 은
  try/finally 로 재작성하여 stop() 실패 시 `force_release()` 폴백.
- **P2-1** — `CaptureThread.__init__(backend_factory=...)` 추가.
  `_start_backend_with_fallback(factory=...)` 으로 전달. 본 녹화 경로도
  monkeypatch 없이 DI 가능.
- **P2-2** — `CaptureThread.run` 의 shape mismatch 분기를 warning → error 로
  격상. 연속 10회 mismatch 시 `_notify_failed()` 호출하여 사용자에게 표면화.
- **P2-3** — `DXCamBackend.stop()` 의 except 범위를 `(RuntimeError, OSError)`
  → `Exception` 으로 확장, 로그 레벨 debug → warning 격상.
- **P2-4** — `CaptureThread.run` finally 블록에 `self.stop_event.set()`
  멱등 호출 추가. `click_detection` daemon thread leak 차단.
- **P2-5** — `_backend_is_dxcam` 데드 필드 2 줄 삭제.
- **P2-6** — `_warmup_backend` 의 `"auto" → "dxcam"` 하드코딩 중복 제거.
- **P2-7** — `core/capture_backend.py` 에 `cleanup_shared_cameras()` 모듈
  레벨 파사드 추가. `ui/main_window.py` 가 구체 클래스 import 제거.
- **P3-1** — `draw_click_highlight_internal`, `CaptureThread.__init__` 의
  파라미터 타입 힌트 보강 (TYPE_CHECKING 가드로 순환 import 회피).
- **P3-2** — `processing_times` 수동 trim list → `deque(maxlen=200)` 전환.
- **P3-3** — `CaptureThread.run()` 진입 시 hot path 분기 조건을 로컬 bool
  로 캐싱 (per-frame attribute/property lookup 50-200ns 절약).
- **P3-5** — `capture_worker.py` 모듈/클래스 docstring 이력 마커 축약.
- **문서** — `.claude/rules/workflow-orchestrator.md` 와
  `harness-invocation.md` 의 GOD_OBJECTS 목록에서 `core/screen_recorder.py`
  제거, CRITICAL_FILES 카테고리 신설.

### Module layout (2026-04-21 최종)

| File | Role | Approx LOC |
|------|------|------------|
| `core/capture_backend.py` | ABC + DXCam/FastGDI/GDI + pool + fallback 헬퍼 + `cleanup_shared_cameras()` 파사드 | ~745 |
| `core/capture_worker.py` | `CaptureThread` + 드로잉 헬퍼 (P1-1 분리) | ~465 |
| `core/screen_recorder.py` | `ScreenRecorder` 파사드 + collector loop | ~680 |

`core/screen_recorder.py` 는 `CaptureThread` / `draw_cursor_internal` /
`draw_click_highlight_internal` / `CLICK_HIGHLIGHT_DURATION` 을 re-export
하여 기존 `monkeypatch.setattr(sr, "CaptureThread", ...)` 테스트 호환.

---

## Provenance

이번 리뷰 웨이브의 소스 문서 (retain):

- `_workspace/00_input.md` — 크로스 리뷰 입력 정의
- `_workspace/01_style_review.md` — style-inspector (BAN-clean)
- `_workspace/02_security_review.md` — security-analyst (High 2, Medium 3, Low 2)
- `_workspace/03_performance_review.md` — performance-analyst (No regression)
- `_workspace/04_architecture_review.md` — architecture-reviewer, opus (Improved)
- `_workspace/05_review_summary.md` — review-synthesizer (FLAG)
- `_workspace.prev-20260421-220000/` — 2026-04-20 원본 리뷰

---

## 유지된 Known-issue (문서 전용)

### 프로젝트 전반 ruff 경고 (~396 건)

| Code    | Count | Meaning |
|---------|-------|---------|
| W293    | 235   | Blank line contains whitespace |
| SIM105  | 85    | `contextlib.suppress` preference |
| SIM102  | 17    | Collapsible `if` |
| F841    | 13    | Unused local |
| F401    | 10    | Unused imports |
| E741    | 9     | Ambiguous variable name |
| B007    | 7     | Loop control unused |
| SIM101  | 5     | Merge isinstance |
| E731    | 5     | lambda assignment |

- **이유:** 프로젝트 전반 산재. 일괄 auto-fix 금지 (F841 은 진짜 버그 은폐 가능).
- **정책:** 모듈별 작업 중 targeted cleanup 으로 소진.

### P1-10 — Frame copy overhead (~720 MB/s at 1080p@60)

- 워커가 1회, 컬렉터가 1회 copy. User-visible 영향 없음.
- 재설계 (queue.Queue size=1 hand-off) 는 non-trivial.
- 프로파일러가 collector-thread memcpy 를 bottleneck 으로 지목할 때만 재방문.

---

## 커밋 히스토리 (최신 → 과거)

```
(2026-04-21 Phase B — 크로스 리뷰 후속)
f8baa1c   perf: hot path lookup 캐싱 + processing_times deque (P3-2, P3-3)
35e3ff1   refactor: cleanup_shared_cameras 파사드 + UI 경계 정리 (P2-7)
75f55a9   fix: shape mismatch 표면화 + stop_event finally 멱등 (P2-2, P2-4)
85928aa   fix: warmup 가시성 + stop 실패 시 force_release 폴백 (P1-B, P2-6)
2284ec7   fix: force_release 공유 카메라 정리 + ABC DI pass-through + stop 예외 범위 확장 (P1-A, P2-1, P2-3, P2-5, P3-1)

(2026-04-21 Phase A — deferred 회수)
d29aabf   refactor: CaptureThread 모듈 분리 + frame_* 리네임 + factory 주입 (P1-1, P1-2, testability)
2efe3d5   refactor: CaptureBackend ABC 확장 + warm-up 흡수 (P1-4, P1-6, P1-8, P1-5)

(2026-04-20)
a3d8d23   docs: 2026-04-20 리뷰 수정 사항 및 deferred TODO 기록
056b070   style: 프로젝트 전역 ruff --fix 정리 (P2)
fd1d983   style: 모듈 상수 추출 및 안전한 P2 정리
7b408b0   refactor: dead fields/methods 제거 (P1-9)
3727bc0   refactor: except 핸들러 디버거빌리티 개선 (P1-7, P1-8, R9)
9fe789c   fix: __del__ 제거 + backend.stop() hard-kill 폴백 (P0-3, P0-4)
42fda27   fix: teardown race & _capture_thread_ref 정리 (P0-1, P1-3)
3441957   fix: 오버레이 중복 소유 제거 (P0-2)
```
