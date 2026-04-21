"""
화면 캡처 및 녹화 모듈
캡처 백엔드 추상화: dxcam (DXGI), GDI (색상 정확, Windows 전용)
CPU 최적화 (커서 그리기는 CPU에서 충분히 빠름)

스레드 모델 주의:
    CaptureThread는 threading.Thread (multiprocessing 아님).
    공유 DXCam 카메라 재사용을 위해 thread-in-process 설계를 선택.
    shm_* 접두어는 레거시 명칭이며 실제로는 직접 공유되는 NumPy 버퍼 +
    threading.Event 조합이다 (아직 multiprocessing.SharedMemory 미사용).
"""

import numpy as np
import threading
import time
import logging
from collections import deque
from typing import Optional, List, Tuple, Callable

# 로깅 설정 (basicConfig는 main.py에서 1회만 호출)
logger = logging.getLogger(__name__)

# 모듈 상수 (D4, D2, N5)
MAX_FRAME_BYTES = 100 * 1024 * 1024  # 100MB — 프레임당 최대 메모리 크기
CLICK_HIGHLIGHT_DURATION = 0.3       # 초 — 클릭 하이라이트 표시 시간

# 타입 별칭 (N5)
Region = Tuple[int, int, int, int]  # (x, y, width, height)

# 캡처 백엔드 추상화
from .capture_backend import (
    CaptureBackend, create_capture_backend,
    get_available_backends
)
# HDR 모니터 대응 (톤 매핑)
from .hdr_utils import apply_hdr_correction_adaptive

# Windows에서 마우스 커서 캡처를 위한 모듈
try:
    import ctypes
    from ctypes import wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def _backend_candidates(preferred: str) -> List[str]:
    """선호 백엔드를 기준으로 시도 순서를 반환."""
    normalized = (preferred or "auto").strip().lower()
    if normalized == "auto" or normalized == "dxcam":
        candidates = ["dxcam", "gdi"]
    elif normalized == "gdi":
        candidates = ["gdi", "dxcam"]
    else:
        candidates = [normalized, "dxcam", "gdi"]

    unique_candidates: List[str] = []
    for name in candidates:
        if name not in unique_candidates:
            unique_candidates.append(name)
    return unique_candidates


def _start_backend_with_fallback(
    preferred: str, region: Tuple[int, int, int, int], target_fps: int
) -> Tuple[Optional[CaptureBackend], Optional[str], List[str]]:
    """백엔드 시작을 시도하고 실패 시 우선순위대로 폴백."""
    errors: List[str] = []

    for backend_name in _backend_candidates(preferred):
        backend: Optional[CaptureBackend] = None
        started = False
        try:
            backend = create_capture_backend(backend_name)
            started = backend.start(region, target_fps=target_fps)
            if started:
                return backend, backend_name, errors
            errors.append(f"{backend_name}: start() returned False")
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append(f"{backend_name}: {exc}")
        finally:
            if backend is not None and not started:
                try:  # noqa: SIM105 — contextlib.suppress 도입은 새 import를 강제하므로 회피
                    backend.stop()
                except (RuntimeError, OSError, ValueError):
                    pass

    return None, None, errors


class ScreenRecorder:
    """화면 녹화기 (CPU 최적화)"""

    def __init__(self):
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

        # 스레드용 이벤트
        self._thread_shm_event: Optional[threading.Event] = None
        self._thread_shm_processed_event: Optional[threading.Event] = None
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
        if self._thread_shm_processed_event:
            self._thread_shm_processed_event.set()
        if self._thread_shm_event:
            self._thread_shm_event.set()

        self._emit_error_occurred(error_msg)

    def _warmup_backend(self):
        """백엔드 미리 준비 (앱 시작 시 호출) - 실제 사용 가능한 백엔드 준비"""
        try:
            # 백그라운드 스레드로 백엔드 워밍업
            def warmup_thread():
                try:
                    # GDI 백엔드 워밍업 (PIL ImageGrab은 즉시 사용 가능)
                    if self._preferred_backend == "gdi":
                        try:
                            from PIL import ImageGrab
                            # 작은 영역으로 빠르게 테스트
                            img = ImageGrab.grab((0, 0, 100, 100))
                            if img:
                                self._backend_warmed_up = True
                                logger.info("GDI backend pre-warmed successfully (PIL ImageGrab ready)")
                                return
                        except (ImportError, OSError, RuntimeError) as exc:
                            logger.warning(f"GDI pre-warming failed: {exc}")

                    # dxcam 전역 초기화 (처음만 느림, 이후 빠름)
                    elif self._preferred_backend == "auto" or self._preferred_backend == "dxcam":
                        try:
                            from .capture_backend import DXCamBackend
                            # DXCamBackend의 공유 카메라를 사용하여 워밍업
                            # 별도 카메라를 만들지 않아 리소스 충돌 방지
                            warmup_backend = DXCamBackend()
                            if warmup_backend.start((0, 0, 100, 100), target_fps=30):
                                time.sleep(0.1)  # 100ms 워밍업 (R2: 중복 import time 제거)
                                test_frame = warmup_backend.grab()
                                warmup_backend.stop()

                                if test_frame is not None:
                                    self._backend_warmed_up = True
                                    logger.info("DXCam backend pre-warmed successfully (shared camera ready)")
                                    return
                        except (ImportError, OSError, RuntimeError) as exc:
                            logger.warning(f"DXCam pre-warming failed: {exc}")

                except (ImportError, OSError, RuntimeError) as exc:
                    logger.warning(f"Backend pre-warming failed: {exc}")

            # 데몬 스레드로 실행 (앱 종료 시 자동 정리)
            warmup_thread_obj = threading.Thread(target=warmup_thread, daemon=True)
            warmup_thread_obj.start()

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

            # 캡처 백엔드로 단일 프레임
            backend, selected_backend, errors = _start_backend_with_fallback(
                self._preferred_backend, self.region, target_fps=10
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

            # HDR 보정: 사용자가 수동으로 켤 때만 적용
            # 단, GDI 백엔드는 Windows가 자동으로 색상 관리를 처리하므로 보정 스킵
            backend_name = (selected_backend or (backend.get_name() if backend else "")).lower()
            is_gdi = backend_name == "gdi"
            if not is_gdi and self.hdr_correction_force:
                frame = apply_hdr_correction_adaptive(frame)

            # 마우스 커서 그리기
            if self.include_cursor and HAS_WIN32:
                frame = self._draw_cursor(frame, x, y)

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

            # 스레드용 이벤트 (threading.Event 사용)
            self._thread_shm_event = threading.Event()
            self._thread_shm_processed_event = threading.Event()
            self._thread_stop_event = threading.Event()
            self._thread_pause_event = threading.Event()

            self._thread_shm_event.clear()
            self._thread_shm_processed_event.set()  # 첫 프레임 쓰기 허용

            # 수집 스레드 시작 (스레드용 이벤트 사용)
            self._collector_thread = threading.Thread(
                target=self._frame_collector_loop_threaded,
                daemon=True
            )
            self._collector_thread.start()

            # 캡처 스레드 시작 (공유 DXCam 카메라 재사용!)
            # P0-2 fix: 워터마크/키보드 인스턴스를 직접 전달하여 단일 소유권 유지
            # (기존: bool만 전달 → worker가 재-import & 재-instantiate하여 twin 상태 발생)
            self._capture_thread = CaptureThread(
                region=self.region,
                fps=self.fps,
                include_cursor=self.include_cursor,
                show_click_highlight=self.show_click_highlight,
                shm_buffer=self._frame_buffer,
                stop_event=self._thread_stop_event,
                pause_event=self._thread_pause_event,
                shm_event=self._thread_shm_event,
                shm_processed_event=self._thread_shm_processed_event,
                preferred_backend=self._preferred_backend,
                watermark=self.watermark,
                keyboard_display=self.keyboard_display,
                hdr_correction_force=self.hdr_correction_force,
                on_failed=self._handle_capture_failure,
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
                self._thread_shm_event,
                self._thread_shm_processed_event,
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
            self._thread_shm_event = None
            self._thread_shm_processed_event = None
            self._thread_stop_event = None
            self._thread_pause_event = None

        # 드롭프레임 통보 (스냅샷된 값 사용)
        if dropped > 0:
            logger.warning(f"Recording had {dropped} dropped frames")

        logger.info(f"Recording stopped. Total frames: {len(self.frames)}")
        if was_recording or has_active_threads:
            self._emit_recording_stopped()
        return self.frames

    def _draw_cursor(self, frame: np.ndarray, region_x: int, region_y: int) -> np.ndarray:
        """마우스 커서를 프레임에 그리기 (NumPy 벡터화 최적화 + JIT)"""
        if not HAS_WIN32:
            return frame

        try:
            # 커서 위치 가져오기
            cursor_pos = wintypes.POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))

            # 영역 내 상대 좌표 계산
            cx = cursor_pos.x - region_x
            cy = cursor_pos.y - region_y

            # 영역 밖이면 복사 없이 원본 반환
            h, w = frame.shape[:2]
            if cx < 0 or cy < 0 or cx >= w or cy >= h:
                return frame

            # 커서 그리기 위해 복사 (여기서만 복사)
            frame = frame.copy()

            # 커서 그리기
            cursor_size = 8
            y1 = max(0, cy - cursor_size)
            y2 = min(h, cy + cursor_size + 1)
            x1 = max(0, cx - cursor_size)
            x2 = min(w, cx + cursor_size + 1)

            yy, xx = np.ogrid[y1-cy:y2-cy, x1-cx:x2-cx]
            dist_sq = xx*xx + yy*yy

            center_mask = dist_sq <= 4
            outer_mask = (dist_sq >= 36) & (dist_sq <= 64)

            roi = frame[y1:y2, x1:x2]
            roi[center_mask] = [255, 255, 255]
            roi[outer_mask] = [0, 0, 0]

            return frame

        except Exception as exc:
            # P1-7: 그리기 오류는 debug로 surface (hot path, 노이즈 최소화)
            logger.debug(f"_draw_cursor skipped due to error: {exc}")
            return frame


    def _frame_collector_loop_threaded(self):
        """프레임 수집 루프 (스레드 기반 버전)"""
        frame_count = 0
        consecutive_errors = 0
        max_consecutive_errors = 10

        loop_start = time.perf_counter()
        processing_times = []

        # None 체크로 안전하게 접근 (로컬 변수로 캐싱하여 레이스 컨디션 방지)
        stop_event = self._thread_stop_event
        shm_event = self._thread_shm_event
        processed_event = self._thread_shm_processed_event

        # _frame_buffer를 로컬 변수로 캐싱 (메인 스레드가 None으로 설정해도 안전)
        frame_buffer = self._frame_buffer

        if stop_event is None or shm_event is None or processed_event is None or frame_buffer is None:
            logger.error("Collector: Events or buffer not initialized")
            return

        while not stop_event.is_set() or shm_event.is_set():
            # 프레임 이벤트 대기
            if shm_event.wait(timeout=0.05):
                try:
                    process_start = time.perf_counter()
                    shm_event.clear()

                    # 프레임 복사 (한 번만) - 로컬 캐싱된 버퍼 사용
                    frame_copy = frame_buffer.copy()
                    self.frames.append(frame_copy)
                    frame_count += 1
                    consecutive_errors = 0

                    # 처리 완료 알림
                    processed_event.set()

                    # 처리 시간 측정
                    process_time = time.perf_counter() - process_start
                    processing_times.append(process_time)
                    if len(processing_times) > 200:
                        del processing_times[:-200]

                    # UI 업데이트 (10프레임마다)
                    if frame_count % 10 == 0:
                        self._emit_frame_captured(frame_count)

                    # 성능 로깅 (100프레임마다)
                    if frame_count % 100 == 0:
                        avg_time = sum(processing_times[-100:]) / min(100, len(processing_times))
                        elapsed = time.perf_counter() - loop_start
                        actual_fps = frame_count / elapsed if elapsed > 0 else 0
                        logger.debug(f"[Collector] Frame {frame_count}, avg: {avg_time*1000:.2f}ms, actual FPS: {actual_fps:.1f}")

                except (ValueError, RuntimeError, MemoryError) as exc:
                    consecutive_errors += 1
                    logger.error(f"Collector error ({consecutive_errors}/{max_consecutive_errors}): {exc}")
                    processed_event.set()

                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical("Too many consecutive errors, stopping collector")
                        self._emit_error_occurred("프레임 수집 중 심각한 오류 발생")
                        break
            # R6: shm_event.wait()가 False면 그냥 다음 iteration으로 넘어감 (else: continue 제거)

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



def draw_cursor_internal(frame: np.ndarray, region_x: int, region_y: int) -> np.ndarray:
    """마우스 커서를 프레임에 그리기 (Top-level function, in-place)"""
    if not HAS_WIN32:
        return frame

    try:
        cursor_pos = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(cursor_pos))
        cx = cursor_pos.x - region_x
        cy = cursor_pos.y - region_y
        h, w = frame.shape[:2]
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            return frame

        # read-only 배열(DXCam 등)이면 쓰기 가능한 복사본 생성
        if not frame.flags.writeable:
            frame = frame.copy()
        cursor_size = 8
        y1, y2 = max(0, cy - cursor_size), min(h, cy + cursor_size + 1)
        x1, x2 = max(0, cx - cursor_size), min(w, cx + cursor_size + 1)
        yy, xx = np.ogrid[y1-cy:y2-cy, x1-cx:x2-cx]
        dist_sq = xx*xx + yy*yy
        center_mask = dist_sq <= 4
        outer_mask = (dist_sq >= 36) & (dist_sq <= 64)
        roi = frame[y1:y2, x1:x2]
        roi[center_mask] = [255, 255, 255]
        roi[outer_mask] = [0, 0, 0]

        return frame
    except Exception as exc:
        logger.debug(f"draw_cursor_internal skipped due to error: {exc}")
        return frame

def draw_click_highlight_internal(frame: np.ndarray, region_x: int, region_y: int, last_click_pos, click_lock) -> np.ndarray:
    """마우스 클릭 하이라이트 그리기 (Top-level function)"""
    if not HAS_WIN32 or last_click_pos is None:
        return frame

    with click_lock:
        click_x, click_y, click_time = last_click_pos
        current_time = time.perf_counter()
        # D2: 매직 넘버 0.3 → CLICK_HIGHLIGHT_DURATION 상수로 치환
        if current_time - click_time > CLICK_HIGHLIGHT_DURATION:
            return frame

    try:
        cx, cy = click_x - region_x, click_y - region_y
        h, w = frame.shape[:2]
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            return frame

        # read-only 배열이면 쓰기 가능한 복사본 생성
        if not frame.flags.writeable:
            frame = frame.copy()
        elapsed = current_time - click_time
        fade_ratio = 1.0 - (elapsed / CLICK_HIGHLIGHT_DURATION)
        alpha = max(0.0, min(1.0, fade_ratio))
        radius = int(20 * alpha)
        # R3: inline if → 두 줄로 분리
        if radius < 2:
            return frame

        yy, xx = np.ogrid[cy-radius:cy+radius+1, cx-radius:cx+radius+1]
        dist_sq = (xx - cx)**2 + (yy - cy)**2
        mask = dist_sq <= radius**2
        y1, y2 = max(0, cy - radius), min(h, cy + radius + 1)
        x1, x2 = max(0, cx - radius), min(w, cx + radius + 1)

        if y2 > y1 and x2 > x1:
            mask_clipped = mask[y1-cy+radius:y2-cy+radius, x1-cx+radius:x2-cx+radius]
            roi = frame[y1:y2, x1:x2]
            highlight_color = np.array([255, 255, 0], dtype=np.uint8)
            for c in range(3):
                roi[:, :, c] = np.where(
                    mask_clipped,
                    (roi[:, :, c] * (1.0 - alpha * 0.7) + highlight_color[c] * alpha * 0.7).astype(np.uint8),
                    roi[:, :, c]
                )
        return frame
    except Exception as exc:
        logger.debug(f"draw_click_highlight_internal skipped due to error: {exc}")
        return frame

class CaptureThread(threading.Thread):
    """스레드 기반 캡처 워커 (프로세스 대신 스레드 사용 - 공유 DXCam 카메라 재사용 가능)

    P0-2 fix: watermark/keyboard_display는 facade(ScreenRecorder)가 소유하는
    단일 인스턴스를 DI로 주입받는다. 워커가 별도 인스턴스를 만들지 않으므로
    녹화 중 facade에 대한 설정 변경이 워커에 반영된다.
    """

    def __init__(self, region: Tuple[int, int, int, int], fps: int, include_cursor: bool,
                 show_click_highlight: bool, shm_buffer: np.ndarray,
                 stop_event: threading.Event, pause_event: threading.Event,
                 shm_event: threading.Event, shm_processed_event: threading.Event,
                 preferred_backend: str,
                 watermark=None, keyboard_display=None,
                 hdr_correction_force: bool = False,
                 on_failed: Optional[Callable[[str], None]] = None):
        super().__init__(daemon=True)

        self.region = region
        self.fps = fps
        self.include_cursor = include_cursor
        self.show_click_highlight = show_click_highlight
        self.shm_buffer = shm_buffer
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.shm_event = shm_event
        self.shm_processed_event = shm_processed_event
        self.preferred_backend = preferred_backend
        # facade(ScreenRecorder)에서 주입받은 인스턴스. None일 수 있음.
        self.watermark = watermark
        self.keyboard_display = keyboard_display
        self.hdr_correction_force = hdr_correction_force
        self._on_failed = on_failed  # 백엔드/캡처 실패 시 메인 스레드에 알림
        self._backend_is_dxcam = False  # run()에서 실제 백엔드로 설정
        self._backend_is_gdi = False    # GDI 사용 시 HDR 보정 스킵

        # 통계
        self.frame_count = 0
        self.dropped_frames = 0
        self._first_frame_ready = threading.Event()

    def wait_for_first_frame(self, timeout: float = 1.0) -> bool:
        """첫 프레임이 캡처될 때까지 대기"""
        return self._first_frame_ready.wait(timeout=timeout)

    def run(self):
        """스레드에서 실행되는 캡처 루프"""
        backend = None
        keyboard = None

        def _notify_failed(msg: str) -> None:
            if self._on_failed:
                try:
                    self._on_failed(msg)
                except Exception as exc:
                    logger.warning(f"[CaptureThread] on_failed callback error: {exc}")

        try:
            x, y, w, h = self.region

            if self.fps <= 0:
                err_msg = f"유효하지 않은 FPS 값: {self.fps}"
                logger.error(f"[CaptureThread] {err_msg}")
                _notify_failed(err_msg)
                return

            # 백엔드 생성 (실패 시 우선순위대로 폴백)
            backend, selected_backend, backend_errors = _start_backend_with_fallback(
                self.preferred_backend, self.region, target_fps=self.fps
            )
            if backend is None:
                details = " | ".join(backend_errors) if backend_errors else "unknown error"
                err_msg = f"캡처 백엔드 시작 실패: {details}"
                logger.error(f"[CaptureThread] {err_msg}")
                _notify_failed(err_msg)
                return

            preferred = (self.preferred_backend or "auto").strip().lower()
            if preferred != "auto" and selected_backend and selected_backend != preferred:
                logger.warning(
                    f"[CaptureThread] backend fallback: preferred={preferred} -> actual={selected_backend}"
                )

            logger.info(f"[CaptureThread] Backend started: {backend.get_name()}")
            name = (selected_backend or backend.get_name() or "").lower()
            self._backend_is_dxcam = "dxcam" in name
            self._backend_is_gdi = name == "gdi"

            # 마우스 클릭 감지
            last_click_pos = None
            click_lock = threading.Lock()

            if self.show_click_highlight and HAS_WIN32:
                def click_detection():
                    nonlocal last_click_pos
                    try:
                        user32 = ctypes.windll.user32
                        last_state = False
                        while not self.stop_event.is_set():
                            current_state = user32.GetAsyncKeyState(0x01) & 0x8000 != 0
                            if current_state and not last_state:
                                cursor_pos = wintypes.POINT()
                                user32.GetCursorPos(ctypes.byref(cursor_pos))
                                with click_lock:
                                    last_click_pos = (cursor_pos.x, cursor_pos.y, time.perf_counter())
                            last_state = current_state
                            time.sleep(0.01)
                    except Exception as exc:
                        logger.error(f"[CaptureThread] Click detection error: {exc}")

                threading.Thread(target=click_detection, daemon=True).start()

            # 오버레이 초기화 — facade가 주입한 인스턴스를 그대로 사용 (DI)
            # P0-2 fix: 재-import & 재-instantiate 대신 facade 소유 인스턴스 사용
            watermark = self.watermark if (self.watermark and self.watermark.enabled) else None

            if self.keyboard_display and self.keyboard_display.enabled:
                keyboard = self.keyboard_display
                try:
                    keyboard.start_listening()
                except Exception as exc:
                    logger.warning(f"[CaptureThread] Keyboard start_listening failed: {exc}")
                    keyboard = None

            frame_interval = 1.0 / self.fps
            next_capture_time = time.perf_counter()
            first_frame_captured = False

            # 성능 프로파일링용 타이밍 추적
            timing_samples = {'grab': deque(maxlen=200), 'hdr': deque(maxlen=200), 'cursor': deque(maxlen=200), 'overlay': deque(maxlen=200)}

            logger.info(f"[CaptureThread] Starting capture at {self.fps} FPS")

            while not self.stop_event.is_set():
                if self.pause_event.is_set():
                    time.sleep(0.05)
                    next_capture_time = time.perf_counter()
                    continue

                current_time = time.perf_counter()

                # 첫 프레임은 즉시 캡처 시도 (타이밍 무시)
                if current_time >= next_capture_time or not first_frame_captured:
                    t0 = time.perf_counter()
                    frame = backend.grab()
                    t1 = time.perf_counter()
                    timing_samples['grab'].append(t1 - t0)

                    if frame is not None:
                        # 첫 프레임 캡처 성공
                        if not first_frame_captured:
                            first_frame_captured = True
                            next_capture_time = current_time
                            self._first_frame_ready.set()
                            logger.info("[CaptureThread] First frame captured - recording active!")

                        # HDR 보정: 사용자가 수동으로 켤 때만 적용 (적응형)
                        # 단, GDI 백엔드는 Windows가 자동으로 색상 관리를 처리하므로 보정 스킵
                        t2 = time.perf_counter()
                        if not self._backend_is_gdi and getattr(self, 'hdr_correction_force', False):
                            frame = apply_hdr_correction_adaptive(frame)
                        t3 = time.perf_counter()
                        timing_samples['hdr'].append(t3 - t2)

                        # 오버레이 필요 시 단일 writable 복사 (이후 모든 처리 in-place)
                        needs_overlay = ((self.include_cursor and HAS_WIN32)
                                        or self.show_click_highlight
                                        or watermark or keyboard)
                        if needs_overlay and not frame.flags.writeable:
                            frame = frame.copy()

                        # 커서 그리기
                        t4 = time.perf_counter()
                        if self.include_cursor and HAS_WIN32:
                            frame = draw_cursor_internal(frame, x, y)
                        t5 = time.perf_counter()
                        timing_samples['cursor'].append(t5 - t4)

                        # 클릭 하이라이트
                        if self.show_click_highlight:
                            frame = draw_click_highlight_internal(frame, x, y, last_click_pos, click_lock)

                        # 오버레이 적용
                        t6 = time.perf_counter()
                        if watermark:
                            frame = watermark.apply_watermark(frame)
                        if keyboard:
                            frame = keyboard.apply_keyboard_display(frame)
                        t7 = time.perf_counter()
                        timing_samples['overlay'].append(t7 - t6)

                        # 성능 로깅 (100프레임마다)
                        if self.frame_count > 0 and self.frame_count % 100 == 0:
                            avg_grab = sum(timing_samples['grab']) / max(1, len(timing_samples['grab']))
                            avg_hdr = sum(timing_samples['hdr']) / max(1, len(timing_samples['hdr']))
                            avg_cursor = sum(timing_samples['cursor']) / max(1, len(timing_samples['cursor']))
                            avg_overlay = sum(timing_samples['overlay']) / max(1, len(timing_samples['overlay']))
                            total_avg = avg_grab + avg_hdr + avg_cursor + avg_overlay
                            # R1: 225ch 로그 라인을 여러 라인으로 분할
                            logger.info(
                                f"[Perf] Frame {self.frame_count}: "
                                f"grab={avg_grab*1000:.1f}ms, "
                                f"hdr={avg_hdr*1000:.1f}ms, "
                                f"cursor={avg_cursor*1000:.1f}ms, "
                                f"overlay={avg_overlay*1000:.1f}ms, "
                                f"total={total_avg*1000:.1f}ms"
                            )

                        # 공유 버퍼에 쓰기
                        if self.shm_processed_event.wait(timeout=0.5):
                            self.shm_processed_event.clear()
                            if frame.shape == self.shm_buffer.shape:
                                np.copyto(self.shm_buffer, frame)
                            else:
                                logger.warning(f"[CaptureThread] Frame shape mismatch: {frame.shape} vs buffer {self.shm_buffer.shape}, skipping")
                                self.dropped_frames += 1
                                self.shm_processed_event.set()
                                continue
                            self.shm_event.set()
                            self.frame_count += 1
                        else:
                            self.dropped_frames += 1
                            if self.dropped_frames % 10 == 0:
                                logger.warning(f"[CaptureThread] Dropped {self.dropped_frames} frames (backpressure)")
                    else:
                        # 프레임 없음 (화면 변화 없음 등) - 첫 프레임 전에는 재시도
                        if not first_frame_captured:
                            time.sleep(0.005)  # 5ms 후 재시도
                            continue

                    next_capture_time += frame_interval

                    # 타이머 드리프트 보정
                    drift = current_time - next_capture_time
                    if drift > frame_interval * 3:
                        next_capture_time = current_time + frame_interval
                else:
                    remaining = next_capture_time - current_time
                    if remaining > 0.001:
                        time.sleep(remaining * 0.5)

            # 통계 로깅
            logger.info(f"[CaptureThread] Finished: {self.frame_count} frames, {self.dropped_frames} dropped")
            if self.dropped_frames > 0 and (self.frame_count + self.dropped_frames) > 0:
                drop_rate = self.dropped_frames / (self.frame_count + self.dropped_frames) * 100
                logger.warning(f"[CaptureThread] Drop rate: {drop_rate:.1f}%")

        except Exception as exc:
            logger.exception(f"[CaptureThread] Fatal error: {exc}")
            _notify_failed(f"녹화 캡처 오류: {exc}")
            # 수집 스레드가 대기 중일 수 있으므로 이벤트 해제
            try:
                self.shm_event.set()
            except Exception as set_exc:
                logger.debug(f"[CaptureThread] shm_event.set() after fatal error failed: {set_exc}")
        finally:
            # 항상 리소스 정리 (예외 발생해도)
            logger.debug("[CaptureThread] Cleaning up resources...")

            # P0-4: backend.stop() 실패 시 강제 해제 폴백 시도.
            # FFmpeg 서브프로세스 패턴(process.kill())과 동일한 guarantee 제공.
            # CaptureBackend ABC에 force_release()가 없어도 duck typing으로 안전하게 호출.
            if backend:
                stop_failed = False
                try:
                    backend.stop()
                except Exception as exc:
                    stop_failed = True
                    logger.error(f"[CaptureThread] Backend stop error: {exc}")

                if stop_failed:
                    force_release = getattr(backend, 'force_release', None)
                    if callable(force_release):
                        try:
                            force_release()
                            logger.warning("[CaptureThread] Backend force_release() invoked after stop() failure")
                        except Exception as exc:
                            logger.error(f"[CaptureThread] Backend force_release error: {exc}")
                    else:
                        # ABC에 force_release 미구현 백엔드의 경우: 내부 핸들 해제를 최대한 시도
                        # (현재 DXCamBackend 구조상 _camera 속성을 None 처리하면 DXGI 핸들 GC 대상)
                        try:
                            if hasattr(backend, '_camera'):
                                backend._camera = None
                                logger.warning("[CaptureThread] Backend._camera = None fallback applied after stop() failure")
                        except Exception as exc:
                            logger.error(f"[CaptureThread] Backend _camera fallback error: {exc}")

            # P0-2 fix: keyboard/watermark는 facade가 소유하는 인스턴스이므로
            # 워커에서는 stop_listening()만 호출 (인스턴스 자체는 facade가 재사용).
            # 캐시는 facade 측 set_* 호출 시 무효화되므로 여기서 건드리지 않는다.
            if keyboard:
                try:
                    keyboard.stop_listening()
                except Exception as exc:
                    logger.error(f"[CaptureThread] Keyboard stop error: {exc}")

            logger.debug("[CaptureThread] Cleanup complete")
