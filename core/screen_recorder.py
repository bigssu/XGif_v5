"""
화면 캡처 및 녹화 모듈 (파사드).

모듈 구성 (P1-1 split 이후):
    - core/capture_backend.py: 백엔드 ABC + DXCam/GDI 구현 + backend fallback 헬퍼.
    - core/capture_worker.py: CaptureThread 워커 + 드로잉 헬퍼.
    - core/screen_recorder.py (이 파일): 공개 facade ScreenRecorder.
"""

import numpy as np
import threading
import time
import logging
from collections import deque
from typing import Callable, List, Optional, Tuple

# 로깅 설정 (basicConfig는 main.py에서 1회만 호출)
logger = logging.getLogger(__name__)

# 모듈 상수
MAX_FRAME_BYTES = 100 * 1024 * 1024  # 100MB — 프레임당 최대 메모리 크기

# 타입 별칭 (N5)
Region = Tuple[int, int, int, int]  # (x, y, width, height)

# 캡처 백엔드 추상화 및 fallback 헬퍼
from .capture_backend import (
    CaptureBackend,
    create_capture_backend,
    get_available_backends,
    _start_backend_with_fallback,
)
# HDR 모니터 대응 (톤 매핑)
from .hdr_utils import apply_hdr_correction_adaptive

# P1-1 분리: CaptureThread 와 드로잉 헬퍼는 capture_worker 에서 가져온다.
# 기존 테스트는 monkeypatch.setattr(sr, "CaptureThread", ...) 로 주입하므로
# 이 모듈에서도 같은 이름으로 re-export 하여 테스트 호환성을 유지한다.
from .capture_worker import (
    CLICK_HIGHLIGHT_DURATION,
    CaptureThread,
    draw_cursor_internal,
    draw_click_highlight_internal,
)

# Windows 커서 위치 조회 — capture_single_frame 에서도 사용.
try:
    import ctypes  # noqa: F401
    from ctypes import wintypes  # noqa: F401
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False

__all__ = [
    "ScreenRecorder",
    "CaptureThread",
    "draw_cursor_internal",
    "draw_click_highlight_internal",
    "create_capture_backend",
    "get_available_backends",
    "CaptureBackend",
    "Region",
    "MAX_FRAME_BYTES",
    "CLICK_HIGHLIGHT_DURATION",
]


class ScreenRecorder:
    """화면 녹화기 (CPU 최적화).

    Args:
        backend_factory: 단위 테스트용 DI 훅. None 이면 create_capture_backend 로 폴백.
            fake 백엔드를 주입하면 monkeypatch 없이도 테스트 가능.
    """

    def __init__(self, backend_factory: Optional[Callable[[str], CaptureBackend]] = None):
        # Testability: 생성자 주입 factory. 단위 테스트에서 fake 백엔드를 쓰기 위함.
        self._backend_factory: Optional[Callable[[str], CaptureBackend]] = backend_factory

        # 콜백 함수들
        self._frame_captured_callback: Optional[Callable[[int], None]] = None
        self._recording_stopped_callback: Optional[Callable[[], None]] = None
        self._error_occurred_callback: Optional[Callable[[str], None]] = None

        # 녹화 설정
        self.fps = 25
        self.region = (0, 0, 800, 600)  # x, y, width, height
        self.include_cursor = True
        self.show_click_highlight = False  # 마우스 클릭 하이라이트

        # 마우스 클릭 추적
        self._last_click_pos: Optional[Tuple[int, int, float]] = None  # (x, y, timestamp)
        self._click_highlight_duration = CLICK_HIGHLIGHT_DURATION

        # 워터마크
        try:
            from .watermark import Watermark
            self.watermark = Watermark()
        except (ImportError, RuntimeError) as exc:
            logger.warning(f"워터마크 초기화 실패: {exc}")
            self.watermark = None

        # 키보드 입력 표시
        try:
            from .keyboard_display import KeyboardDisplay
            self.keyboard_display = KeyboardDisplay()
        except (ImportError, RuntimeError) as exc:
            logger.warning(f"키보드 입력 표시 초기화 실패: {exc}")
            self.keyboard_display = None

        # 상태
        self.is_recording = False
        self.is_paused = False
        self.last_error: Optional[str] = None

        # 실제 FPS 추적 (녹화 시작/종료 시간)
        self._recording_start_time: Optional[float] = None
        self._recording_end_time: Optional[float] = None
        self.actual_fps: Optional[float] = None
        self.frames: List[np.ndarray] = []

        # 마우스 클릭 감지
        self._click_lock = threading.Lock()

        # 캡처 백엔드 설정
        self._capture_backend: Optional[CaptureBackend] = None
        self._preferred_backend: str = "auto"  # "auto", "dxcam", "gdi" (auto: HDR 감지하여 자동 선택)

        # HDR 보정 수동 강제 (설정에서 켜면 자동 감지 실패 시에도 적용)
        self.hdr_correction_force: bool = False

        # 프레임 수집 스레드
        self._collector_thread: Optional[threading.Thread] = None

        # 스레드 기반 캡처 (멀티프로세싱 대신 - 공유 카메라 재사용 가능)
        self._capture_thread: Optional[CaptureThread] = None
        # P0-1/P1-3: 워커 종료 직전에 스냅샷; _capture_thread_ref 참조 보관 대신 값만 보존
        self._last_dropped_frames: int = 0
        self._frame_buffer: Optional[np.ndarray] = None

        # 스레드용 이벤트 (P1-2: shm_* → frame_* 리네임)
        self._thread_frame_ready_event: Optional[threading.Event] = None
        self._thread_frame_consumed_event: Optional[threading.Event] = None
        self._thread_stop_event: Optional[threading.Event] = None
        self._thread_pause_event: Optional[threading.Event] = None

        # Pre-warming 상태 (백엔드 미리 준비)
        self._backend_warmed_up = False

    def set_frame_captured_callback(self, callback: Callable[[int], None]):
        """프레임 캡처 콜백 설정"""
        self._frame_captured_callback = callback

    def set_recording_stopped_callback(self, callback: Callable[[], None]):
        """녹화 중지 콜백 설정"""
        self._recording_stopped_callback = callback

    def set_error_occurred_callback(self, callback: Callable[[str], None]):
        """에러 발생 콜백 설정"""
        self._error_occurred_callback = callback

    def _emit_frame_captured(self, frame_num: int):
        """프레임 캡처 이벤트 발생.

        NOTE: 콜백은 백그라운드 스레드(_frame_collector_loop_threaded)에서 호출되므로
        consumer는 wx.CallAfter() 등으로 GUI 스레드에 마샬링해야 한다.
        """
        if self._frame_captured_callback:
            try:
                self._frame_captured_callback(frame_num)
            except Exception as exc:
                # P1-7: callback 예외를 log로 surface — 무음 삼킴이 디버깅 홀을 만들었음
                logger.exception(f"frame_captured callback raised: {exc}")

    def _emit_recording_stopped(self):
        """녹화 중지 이벤트 발생.

        NOTE: 백그라운드 스레드에서 호출될 수 있음. wx.CallAfter() 사용 권장.
        """
        if self._recording_stopped_callback:
            try:
                self._recording_stopped_callback()
            except Exception as exc:
                logger.exception(f"recording_stopped callback raised: {exc}")

    def _emit_error_occurred(self, error_msg: str):
        """에러 발생 이벤트 발생.

        NOTE: 백그라운드 스레드에서 호출될 수 있음. wx.CallAfter() 사용 권장.
        """
        if self._error_occurred_callback:
            try:
                self._error_occurred_callback(error_msg)
            except Exception as exc:
                logger.exception(f"error_occurred callback raised: {exc}")

    def _handle_capture_failure(self, error_msg: str):
        """백엔드/캡처 실패 시 내부 상태를 즉시 정리."""
        self.last_error = error_msg
        self.is_recording = False
        self.is_paused = False

        if self._thread_stop_event:
            self._thread_stop_event.set()
        if self._thread_pause_event:
            self._thread_pause_event.clear()
        if self._thread_frame_consumed_event:
            self._thread_frame_consumed_event.set()
        if self._thread_frame_ready_event:
            self._thread_frame_ready_event.set()

        self._emit_error_occurred(error_msg)

    def _warmup_backend(self):
        """백엔드 미리 준비 (앱 시작 시 호출).

        워밍업 로직은 CaptureBackend.warm_up() 으로 이관되어 있어 여기서는
        데몬 스레드에서 호출하고 성공 여부만 기록한다.
        """

        def warmup_thread():
            # P1-B (2026-04-21 리뷰): 데몬 스레드 최상위에 catch-all 을 둔다.
            # warm_up() 내부가 잡지 못한 MemoryError / KeyError / AttributeError
            # 가 daemon 에서 소멸되면 GUI 에는 증거가 남지 않으므로,
            # 최상위에서 logger.exception 으로 반드시 stacktrace 를 기록한다.
            try:
                try:
                    # P2-6: create_capture_backend 의 "auto" 분기가 이미 DXCam 우선이므로
                    # preferred 변환 없이 그대로 전달한다.
                    backend = create_capture_backend(self._preferred_backend or "auto")
                except RuntimeError as exc:
                    # 해당 백엔드 자체가 사용 불가 (dxcam 미설치 / 비-Windows GDI 등)
                    logger.warning(f"Backend pre-warming skipped — unavailable: {exc}")
                    return

                if backend.warm_up():
                    self._backend_warmed_up = True
                    logger.info(f"{backend.get_name()} backend pre-warmed successfully")
            except Exception as exc:
                logger.exception(f"Backend pre-warming thread crashed: {exc}")

        try:
            threading.Thread(target=warmup_thread, daemon=True).start()
        except (RuntimeError, OSError) as exc:
            logger.warning(f"Could not start backend pre-warming: {exc}")

    # P0-3: __del__ 제거 — daemon thread 비정상 종료로 DXGI 핸들 손상 가능.
    # 호출자는 try/finally에서 stop_recording()을 명시적으로 호출하거나,
    # 아래 컨텍스트 매니저(with ScreenRecorder() as rec:) 패턴을 사용할 것.
    def __enter__(self) -> "ScreenRecorder":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        # 녹화 중이면 종료 (blocking join 포함)
        try:
            if self.is_recording:
                self.stop_recording()
        except Exception as exc:
            logger.exception(f"ScreenRecorder cleanup on __exit__ failed: {exc}")

    def set_region(self, x: int, y: int, width: int, height: int):
        """캡처 영역 설정"""
        self.region = (x, y, width, height)

    def set_capture_backend(self, backend: str = "auto"):
        """캡처 백엔드 설정

        Args:
            backend: "auto", "dxcam", "gdi" 중 선택
        """
        self._preferred_backend = backend
        # 백엔드 변경 시 워밍업 (아직 완료되지 않은 경우)
        if not self._backend_warmed_up:
            self._warmup_backend()

    def set_hdr_correction(self, force: bool):
        """HDR 보정 수동 강제 (설정에서 켜면 자동 감지 실패 시에도 적용)"""
        self.hdr_correction_force = force

    def get_capture_backend_name(self) -> str:
        """현재 캡처 백엔드 이름 반환"""
        if self._capture_backend:
            return self._capture_backend.get_name()
        return self._preferred_backend

    def get_available_backends(self) -> List[str]:
        """사용 가능한 캡처 백엔드 목록"""
        return get_available_backends()

    def capture_single_frame(self) -> Optional[np.ndarray]:
        """단일 프레임 캡처 (미리보기용)"""
        try:
            # 영역 유효성 검증
            if not self.region or len(self.region) != 4:
                logger.warning("Invalid capture region")
                return None

            x, y, w, h = self.region

            # 크기 검증
            if w <= 0 or h <= 0:
                logger.warning(f"Invalid region size: {w}x{h}")
                return None

            frame = None
            backend = None
            selected_backend = None

            # 캡처 백엔드로 단일 프레임.
            # factory 에 create_capture_backend 를 명시 전달하면 sr 모듈의 monkeypatch
            # (tests/test_screen_recorder_runtime.py) 가 영향을 미친다.
            backend, selected_backend, errors = _start_backend_with_fallback(
                self._preferred_backend,
                self.region,
                target_fps=10,
                factory=self._backend_factory or create_capture_backend,
            )
            if backend is None:
                if errors:
                    logger.error(f"Backend capture failed: {' | '.join(errors)}")
                else:
                    logger.error("Backend capture failed: no backend candidate started")
                return None

            # 선호 백엔드 실패 후 폴백된 경우 로그를 남긴다.
            preferred = (self._preferred_backend or "auto").strip().lower()
            if preferred != "auto" and selected_backend and selected_backend != preferred:
                logger.warning(
                    f"capture_single_frame fallback: preferred={preferred} -> actual={selected_backend}"
                )

            try:
                time.sleep(0.1)
                frame = backend.grab()
            finally:
                backend.stop()

            if frame is None or frame.size == 0:
                return None

            # HDR 보정: 사용자가 수동으로 켤 때만 적용.
            # P1-6: 백엔드 이름 문자열 비교 대신 polymorphic supports_managed_color 로 분기.
            if self.hdr_correction_force and not backend.supports_managed_color:
                frame = apply_hdr_correction_adaptive(frame)

            # 마우스 커서 그리기 (P1-5: _draw_cursor 메서드 제거, 자유 함수로 일원화)
            if self.include_cursor and HAS_WIN32:
                frame = draw_cursor_internal(frame, x, y)

            return frame

        except (RuntimeError, ValueError, OSError) as exc:
            logger.error(f"캡처 에러: {exc}")
            return None

    def start_recording(self):
        """녹화 시작 (스레드 기반 - 즉시 시작)"""
        if self.is_recording:
            logger.warning("Already recording, ignoring start request")
            return

        self.last_error = None

        # 이전 녹화 리소스 정리 (안전 장치)
        if self._capture_thread and self._capture_thread.is_alive():
            logger.warning("Previous capture thread still alive, stopping")
            if self._thread_stop_event:
                self._thread_stop_event.set()
            self._capture_thread.join(timeout=2.0)
            self._capture_thread = None

        if self._collector_thread and self._collector_thread.is_alive():
            logger.warning("Previous collector thread still alive, waiting")
            if self._thread_stop_event:
                self._thread_stop_event.set()
            self._collector_thread.join(timeout=2.0)
            self._collector_thread = None

        self.is_recording = True
        self.is_paused = False

        # 녹화 시작 시간 기록
        self._recording_start_time = time.perf_counter()
        self._recording_end_time = None
        self.actual_fps = None

        try:
            self.frames = []

            # 영역 설정
            x, y, w, h = self.region

            # FPS 검증
            try:
                fps = int(self.fps)
            except (TypeError, ValueError):
                self._handle_capture_failure(f"유효하지 않은 FPS 값: {self.fps}")
                return
            if fps < 1 or fps > 120:
                self._handle_capture_failure(f"FPS 범위 오류: {fps} (허용 1-120)")
                return
            self.fps = fps

            # 영역 크기 검증
            if w <= 0 or h <= 0:
                logger.error(f"Invalid region size for recording: {w}x{h}")
                self._emit_error_occurred(f"유효하지 않은 캡처 영역 크기: {w}x{h}")
                self.is_recording = False
                return

            # 메모리 크기 계산 (오버플로우 방지)
            try:
                frame_size = w * h * 3  # width * height * 3 bytes (BGR)
                if frame_size <= 0 or frame_size > MAX_FRAME_BYTES:
                    logger.error(f"Invalid frame size: {frame_size} bytes")
                    self._emit_error_occurred(f"프레임 크기가 너무 큽니다: {frame_size // (1024*1024)}MB")
                    self.is_recording = False
                    return
            except (OverflowError, MemoryError) as exc:
                logger.error(f"Frame size calculation overflow: {exc}")
                self._emit_error_occurred("메모리 계산 오류")
                self.is_recording = False
                return

            # 직접 버퍼 생성 (스레드 간 공유 - 공유 메모리 불필요)
            self._frame_buffer = np.zeros((h, w, 3), dtype=np.uint8)

            # 스레드용 이벤트 (P1-2: shm_* → frame_* 리네임)
            self._thread_frame_ready_event = threading.Event()
            self._thread_frame_consumed_event = threading.Event()
            self._thread_stop_event = threading.Event()
            self._thread_pause_event = threading.Event()

            self._thread_frame_ready_event.clear()
            self._thread_frame_consumed_event.set()  # 첫 프레임 쓰기 허용

            # 수집 스레드 시작 (스레드용 이벤트 사용)
            self._collector_thread = threading.Thread(
                target=self._frame_collector_loop_threaded,
                daemon=True
            )
            self._collector_thread.start()

            # 캡처 스레드 시작 (공유 DXCam 카메라 재사용!).
            # P0-2: 워터마크/키보드 인스턴스를 DI 로 전달하여 단일 소유권 유지.
            # P1-2: kwarg 이름이 shm_* → frame_* 로 변경.
            # P2-1: backend_factory 를 pass-through 하여 본 녹화 경로도 DI 가능.
            self._capture_thread = CaptureThread(
                region=self.region,
                fps=self.fps,
                include_cursor=self.include_cursor,
                show_click_highlight=self.show_click_highlight,
                frame_buffer=self._frame_buffer,
                stop_event=self._thread_stop_event,
                pause_event=self._thread_pause_event,
                frame_ready_event=self._thread_frame_ready_event,
                frame_consumed_event=self._thread_frame_consumed_event,
                preferred_backend=self._preferred_backend,
                watermark=self.watermark,
                keyboard_display=self.keyboard_display,
                hdr_correction_force=self.hdr_correction_force,
                on_failed=self._handle_capture_failure,
                backend_factory=self._backend_factory,
            )
            self._capture_thread.start()

            # 첫 프레임 캡처 대기 (빠른 시작)
            if self._backend_warmed_up:
                max_wait = 0.3  # pre-warmed: 300ms
                logger.info("Using pre-warmed backend - instant start expected")
            else:
                max_wait = 1.0  # 1초
                logger.info("Backend not pre-warmed, may take longer")

            if self._capture_thread.wait_for_first_frame(timeout=max_wait):
                logger.info("Recording started - first frame captured instantly!")
            else:
                if not self.is_recording:
                    logger.error("Recording startup aborted due to capture failure")
                    return
                if not self._capture_thread or not self._capture_thread.is_alive():
                    self._handle_capture_failure("캡처 스레드가 시작 직후 종료되었습니다.")
                    return
                logger.warning(f"First frame not ready after {max_wait*1000:.0f}ms, but continuing")

            logger.info("Recording started successfully")

        except Exception as exc:
            self._frame_buffer = None
            self._handle_capture_failure(f"녹화 시작 실패: {str(exc)}")
            logger.exception(f"Recording start failed: {exc}")

    def pause_recording(self):
        """녹화 일시정지"""
        if self.is_recording and not self.is_paused:
            self.is_paused = True
            if self._thread_pause_event:
                self._thread_pause_event.set()

    def resume_recording(self):
        """녹화 재개"""
        if self.is_recording and self.is_paused:
            self.is_paused = False
            if self._thread_pause_event:
                self._thread_pause_event.clear()

    def stop_recording(self) -> List[np.ndarray]:
        """녹화 중지, 프레임 반환"""
        has_active_threads = (
            (self._capture_thread is not None and self._capture_thread.is_alive()) or
            (self._collector_thread is not None and self._collector_thread.is_alive())
        )
        has_pending_resources = any(
            obj is not None
            for obj in (
                self._frame_buffer,
                self._thread_frame_ready_event,
                self._thread_frame_consumed_event,
                self._thread_stop_event,
                self._thread_pause_event,
            )
        )

        if not self.is_recording and not has_active_threads and not has_pending_resources:
            return self.frames
        was_recording = self.is_recording

        # 녹화 종료 시간 기록 및 실제 FPS 계산
        self._recording_end_time = time.perf_counter()
        if self._recording_start_time and len(self.frames) > 0:
            elapsed = self._recording_end_time - self._recording_start_time
            if elapsed > 0:
                self.actual_fps = len(self.frames) / elapsed
                logger.info(f"Recording stats: {len(self.frames)} frames in {elapsed:.2f}s = {self.actual_fps:.2f} FPS (target: {self.fps} FPS)")
            else:
                self.actual_fps = self.fps
        else:
            self.actual_fps = self.fps

        self.is_recording = False
        self.is_paused = False

        # 스레드 중지 신호
        if self._thread_stop_event:
            self._thread_stop_event.set()
        if self._thread_pause_event:
            self._thread_pause_event.clear()

        # P0-1/P1-3: 워커 통계(dropped_frames)를 join 전에 읽지 않고, join 이후
        # _capture_thread가 아직 살아있을 수 있으므로 null-처리 전에 스냅샷한다.
        # 참조(_capture_thread_ref) 보관 대신 값만 저장하여 GC/race 표면적 축소.
        capture_thread = self._capture_thread
        collector_thread = self._collector_thread

        # 캡처 스레드 종료 대기
        threads_alive = False
        if capture_thread:
            capture_thread.join(timeout=3.0)
            if capture_thread.is_alive():
                logger.warning("Capture thread did not terminate in time")
                threads_alive = True

        # 수집 스레드 종료 대기
        if collector_thread:
            collector_thread.join(timeout=2.0)
            if collector_thread.is_alive():
                logger.warning("Collector thread did not terminate in time")
                threads_alive = True

        # 스레드 통계 스냅샷 (join 후, null 처리 전)
        dropped = getattr(capture_thread, 'dropped_frames', 0) if capture_thread else 0
        self._last_dropped_frames = dropped

        # 스레드 참조 해제 (스냅샷 이후)
        self._capture_thread = None
        self._collector_thread = None

        # 버퍼/이벤트 정리 - 스레드가 아직 살아있으면 None 접근 크래시 방지를 위해 스킵
        if threads_alive:
            logger.warning("Skipping buffer/event cleanup - threads still alive")
        else:
            self._frame_buffer = None
            self._thread_frame_ready_event = None
            self._thread_frame_consumed_event = None
            self._thread_stop_event = None
            self._thread_pause_event = None

        # 드롭프레임 통보 (스냅샷된 값 사용)
        if dropped > 0:
            logger.warning(f"Recording had {dropped} dropped frames")

        logger.info(f"Recording stopped. Total frames: {len(self.frames)}")
        if was_recording or has_active_threads:
            self._emit_recording_stopped()
        return self.frames

    def _frame_collector_loop_threaded(self):
        """프레임 수집 루프 (스레드 기반 버전)."""
        frame_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 10

        loop_start = time.perf_counter()
        # P3-2: 수동 trim list → deque(maxlen=200). 의도 명시적.
        processing_times: "deque[float]" = deque(maxlen=200)

        # None 체크로 안전하게 접근 (로컬 변수로 캐싱하여 레이스 컨디션 방지).
        # P1-2: 이름이 frame_ready_event / frame_consumed_event 로 바뀌었으나 의미는 동일.
        stop_event = self._thread_stop_event
        frame_ready_event = self._thread_frame_ready_event
        frame_consumed_event = self._thread_frame_consumed_event

        # _frame_buffer를 로컬 변수로 캐싱 (메인 스레드가 None으로 설정해도 안전)
        frame_buffer = self._frame_buffer

        if (
            stop_event is None
            or frame_ready_event is None
            or frame_consumed_event is None
            or frame_buffer is None
        ):
            logger.error("Collector: Events or buffer not initialized")
            return

        while not stop_event.is_set() or frame_ready_event.is_set():
            # 프레임 이벤트 대기
            if frame_ready_event.wait(timeout=0.05):
                try:
                    process_start = time.perf_counter()
                    frame_ready_event.clear()

                    # 프레임 복사 (한 번만) - 로컬 캐싱된 버퍼 사용
                    frame_copy = frame_buffer.copy()
                    self.frames.append(frame_copy)
                    frame_count += 1
                    consecutive_errors = 0

                    # 처리 완료 알림
                    frame_consumed_event.set()

                    # 처리 시간 측정 (deque(maxlen=200) 이 자동 bounded)
                    process_time = time.perf_counter() - process_start
                    processing_times.append(process_time)

                    # UI 업데이트 (10프레임마다)
                    if frame_count % 10 == 0:
                        self._emit_frame_captured(frame_count)

                    # 성능 로깅 (100프레임마다) — deque 는 slicing 미지원이므로 list 변환.
                    if frame_count % 100 == 0 and processing_times:
                        last_100 = list(processing_times)[-100:]
                        avg_time = sum(last_100) / len(last_100)
                        elapsed = time.perf_counter() - loop_start
                        actual_fps = frame_count / elapsed if elapsed > 0 else 0
                        logger.debug(
                            f"[Collector] Frame {frame_count}, "
                            f"avg: {avg_time*1000:.2f}ms, actual FPS: {actual_fps:.1f}"
                        )

                except (ValueError, RuntimeError, MemoryError) as exc:
                    consecutive_errors += 1
                    logger.error(f"Collector error ({consecutive_errors}/{max_consecutive_errors}): {exc}")
                    frame_consumed_event.set()

                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical("Too many consecutive errors, stopping collector")
                        self._emit_error_occurred("프레임 수집 중 심각한 오류 발생")
                        break
            # wait()가 False 면 그냥 다음 iteration 으로 넘어감.

        # 최종 통계
        elapsed = time.perf_counter() - loop_start
        actual_fps = frame_count / elapsed if elapsed > 0 else 0
        logger.info(f"[Collector] Finished: {frame_count} frames in {elapsed:.1f}s ({actual_fps:.1f} FPS)")

    def clear_frames(self):
        """프레임 버퍼 초기화"""
        self.frames = []

    def get_frame_count(self) -> int:
        """현재 프레임 수"""
        return len(self.frames)

    def get_estimated_size_mb(self) -> float:
        """예상 메모리 사용량 (MB)"""
        if not self.frames:
            return 0.0

        # 첫 번째 프레임 크기 기준 (모든 프레임 크기가 동일하다고 가정)
        frame_size = self.frames[0].nbytes if self.frames else 0
        return (frame_size * len(self.frames)) / (1024 * 1024)
