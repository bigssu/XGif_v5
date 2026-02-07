"""
화면 캡처 및 녹화 모듈
캡처 백엔드 추상화: dxcam (DXGI), GDI (색상 정확, Windows 전용)
CPU 최적화 (커서 그리기는 CPU에서 충분히 빠름)
"""

import os
import numpy as np
import threading
import time
import logging
from typing import Optional, List, Tuple, Callable

# 로깅 설정
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# 캡처 백엔드 추상화
from .capture_backend import (
    CaptureBackend, create_capture_backend, 
    get_available_backends, is_dxcam_available
)
# HDR 모니터 대응 (톤 매핑)
from .hdr_utils import is_hdr_active, apply_hdr_correction_adaptive

# HDR 비교용 PNG 저장: XGIF_DEBUG_HDR_PNG=1 이거나 Temp\xgif_hdr_debug 폴더가 있을 때
def _is_debug_hdr_png_enabled() -> bool:
    import tempfile
    d = os.path.join(tempfile.gettempdir(), "xgif_hdr_debug")
    if os.environ.get("XGIF_DEBUG_HDR_PNG", "").strip() == "1":
        return True
    return os.path.isdir(d)


def _save_debug_hdr_png(frame_bgr: np.ndarray, name: str) -> None:
    """BGR 프레임을 PNG로 저장 (HDR 비교용). Temp\\xgif_hdr_debug 폴더를 만들어 두면 자동 활성화."""
    if not _is_debug_hdr_png_enabled() or frame_bgr is None or frame_bgr.size == 0:
        return
    import tempfile
    debug_dir = os.path.join(tempfile.gettempdir(), "xgif_hdr_debug")
    path = os.path.abspath(os.path.join(debug_dir, f"{name}.png"))
    try:
        from PIL import Image
        os.makedirs(debug_dir, exist_ok=True)
        rgb = frame_bgr[:, :, ::-1].copy()  # 연속 메모리로 복사 (PIL 호환)
        Image.fromarray(rgb).save(path)
        logger.info("[HDR 디버그] 저장됨: %s", path)
    except Exception as e:
        logger.warning("HDR 디버그 PNG 저장 실패: %s | 경로: %s", e, path)


# Windows에서 마우스 커서 캡처를 위한 모듈
try:
    import ctypes
    from ctypes import wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


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
        self._last_click_pos: Optional[tuple] = None  # (x, y, timestamp)
        self._click_highlight_duration = 0.3  # 초
        
        # 워터마크
        try:
            from .watermark import Watermark
            self.watermark = Watermark()
        except (ImportError, RuntimeError) as e:
            logger.warning(f"워터마크 초기화 실패: {e}")
            self.watermark = None
        
        # 키보드 입력 표시
        try:
            from .keyboard_display import KeyboardDisplay
            self.keyboard_display = KeyboardDisplay()
        except (ImportError, RuntimeError) as e:
            logger.warning(f"키보드 입력 표시 초기화 실패: {e}")
            self.keyboard_display = None
        
        # 상태
        self.is_recording = False
        self.is_paused = False
        
        # 실제 FPS 추적 (녹화 시작/종료 시간)
        self._recording_start_time: Optional[float] = None
        self._recording_end_time: Optional[float] = None
        self.actual_fps: Optional[float] = None
        self.frames: List[np.ndarray] = []
        self._cached_frame_size = None
        
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
        self._frame_buffer: Optional[np.ndarray] = None
        
        # 스레드용 이벤트
        self._thread_shm_event: Optional[threading.Event] = None
        self._thread_shm_processed_event: Optional[threading.Event] = None
        self._thread_stop_event: Optional[threading.Event] = None
        self._thread_pause_event: Optional[threading.Event] = None
        
        # Pre-warming 상태 (백엔드 미리 준비)
        self._backend_warmed_up = False
        self._warmup_backend()
    
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
        """프레임 캡처 이벤트 발생"""
        if self._frame_captured_callback:
            try:
                self._frame_captured_callback(frame_num)
            except Exception:
                pass
    
    def _emit_recording_stopped(self):
        """녹화 중지 이벤트 발생"""
        if self._recording_stopped_callback:
            try:
                self._recording_stopped_callback()
            except Exception:
                pass
    
    def _emit_error_occurred(self, error_msg: str):
        """에러 발생 이벤트 발생"""
        if self._error_occurred_callback:
            try:
                self._error_occurred_callback(error_msg)
            except Exception:
                pass
    
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
                        except Exception as e:
                            logger.warning(f"GDI pre-warming failed: {e}")
                    
                    # dxcam 전역 초기화 (처음만 느림, 이후 빠름)
                    elif self._preferred_backend == "auto" or self._preferred_backend == "dxcam":
                        try:
                            from .capture_backend import DXCamBackend
                            # DXCamBackend의 공유 카메라를 사용하여 워밍업
                            # 별도 카메라를 만들지 않아 리소스 충돌 방지
                            warmup_backend = DXCamBackend()
                            if warmup_backend.start((0, 0, 100, 100), target_fps=30):
                                import time
                                time.sleep(0.1)  # 100ms 워밍업
                                test_frame = warmup_backend.grab()
                                warmup_backend.stop()

                                if test_frame is not None:
                                    self._backend_warmed_up = True
                                    logger.info("DXCam backend pre-warmed successfully (shared camera ready)")
                                    return
                        except Exception as e:
                            logger.warning(f"DXCam pre-warming failed: {e}")
                    
                except Exception as e:
                    logger.warning(f"Backend pre-warming failed: {e}")
            
            # 데몬 스레드로 실행 (앱 종료 시 자동 정리)
            warmup_thread_obj = threading.Thread(target=warmup_thread, daemon=True)
            warmup_thread_obj.start()
            
        except Exception as e:
            logger.warning(f"Could not start backend pre-warming: {e}")
    
    def __del__(self):
        """소멸자: 리소스 정리"""
        try:
            # 녹화 중이면 중지 시도
            if hasattr(self, 'is_recording') and self.is_recording:
                if hasattr(self, '_thread_stop_event') and self._thread_stop_event:
                    self._thread_stop_event.set()
        except Exception:
            pass
    
    def set_region(self, x: int, y: int, width: int, height: int):
        """캡처 영역 설정"""
        self.region = (x, y, width, height)
    
    def set_capture_backend(self, backend: str = "auto"):
        """캡처 백엔드 설정
        
        Args:
            backend: "auto", "dxcam", "gdi" 중 선택
        """
        self._preferred_backend = backend

    def set_hdr_correction(self, force: bool):
        """HDR 보정 수동 강제 (설정에서 켜면 자동 감지 실패 시에도 적용)"""
        self.hdr_correction_force = force
    
    def get_capture_backend_name(self) -> str:
        """현재 캡처 백엔드 이름 반환"""
        if self._capture_backend:
            return self._capture_backend.get_name()
        return self._preferred_backend
    
    def get_available_backends(self) -> list:
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
            
            # 캡처 백엔드로 단일 프레임
            try:
                backend = create_capture_backend(self._preferred_backend)
                if backend and backend.start(self.region, target_fps=10):
                    import time
                    time.sleep(0.1)
                    frame = backend.grab()
                    backend.stop()
            except (RuntimeError, OSError) as e:
                logger.error(f"Backend capture failed: {e}")
                return None
            
            if frame is None or frame.size == 0:
                return None
            
            # HDR 비교용: 캡처 직후 원본 1장 PNG 저장 (XGIF_DEBUG_HDR_PNG=1)
            _save_debug_hdr_png(frame, "capture_frame_before_hdr")
            
            # HDR 보정: 사용자가 수동으로 켤 때만 적용
            # 단, GDI 백엔드는 Windows가 자동으로 색상 관리를 처리하므로 보정 스킵
            backend_name = (backend.get_name() if backend else "").lower()
            is_gdi = backend_name == "gdi"
            if not is_gdi and self.hdr_correction_force:
                frame = apply_hdr_correction_adaptive(frame)
            # 비교용 after PNG (보정 여부 무관하게 저장)
            _save_debug_hdr_png(frame, "capture_frame_after_hdr")
            
            # 마우스 커서 그리기
            if self.include_cursor and HAS_WIN32:
                frame = self._draw_cursor(frame, x, y)
            
            return frame
                
        except (RuntimeError, ValueError, OSError) as e:
            logger.error(f"캡처 에러: {e}")
            return None
    
    def start_recording(self):
        """녹화 시작 (스레드 기반 - 즉시 시작)"""
        if self.is_recording:
            logger.warning("Already recording, ignoring start request")
            return
        
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
            self._cached_frame_size = None
            
            # 영역 설정
            x, y, w, h = self.region
            
            # 영역 크기 검증
            if w <= 0 or h <= 0:
                logger.error(f"Invalid region size for recording: {w}x{h}")
                self._emit_error_occurred(f"유효하지 않은 캡처 영역 크기: {w}x{h}")
                self.is_recording = False
                return
            
            # 메모리 크기 계산 (오버플로우 방지)
            try:
                frame_size = w * h * 3  # BGR
                if frame_size <= 0 or frame_size > 100 * 1024 * 1024:  # 100MB 제한
                    logger.error(f"Invalid frame size: {frame_size} bytes")
                    self._emit_error_occurred(f"프레임 크기가 너무 큽니다: {frame_size // (1024*1024)}MB")
                    self.is_recording = False
                    return
            except (OverflowError, MemoryError) as e:
                logger.error(f"Frame size calculation overflow: {e}")
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
                webcam_enabled=False,
                watermark_enabled=self.watermark.enabled if self.watermark else False,
                keyboard_enabled=self.keyboard_display.enabled if self.keyboard_display else False,
                hdr_correction_force=self.hdr_correction_force,
                on_failed=lambda msg: self._emit_error_occurred(msg),
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
                logger.warning(f"First frame not ready after {max_wait*1000:.0f}ms, but continuing")
            
            logger.info("Recording started successfully")
            
        except Exception as e:
            # 에러 발생 시 상태 복원
            self.is_recording = False
            self.is_paused = False
            self._frame_buffer = None
            self._emit_error_occurred(f"녹화 시작 실패: {str(e)}")
            logger.error(f"Recording start failed: {e}")
            import traceback
            traceback.print_exc()
    
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
        if not self.is_recording:
            return self.frames
        
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
        
        # 캡처 스레드 종료 대기
        threads_alive = False
        if self._capture_thread:
            self._capture_thread.join(timeout=3.0)
            if self._capture_thread.is_alive():
                logger.warning("Capture thread did not terminate in time")
                threads_alive = True
            self._capture_thread = None

        # 수집 스레드 종료 대기
        if self._collector_thread:
            self._collector_thread.join(timeout=2.0)
            if self._collector_thread.is_alive():
                logger.warning("Collector thread did not terminate in time")
                threads_alive = True
            self._collector_thread = None

        # 버퍼 정리 - 스레드가 아직 살아있으면 None 접근 크래시 방지를 위해 스킵
        if threads_alive:
            logger.warning("Skipping buffer cleanup - threads still alive")
        else:
            self._frame_buffer = None
        self._thread_shm_event = None
        self._thread_shm_processed_event = None
        self._thread_stop_event = None
        self._thread_pause_event = None
        
        logger.info(f"Recording stopped. Total frames: {len(self.frames)}")
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
            
        except Exception:
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
                        
                except (ValueError, RuntimeError, MemoryError) as e:
                    consecutive_errors += 1
                    logger.error(f"Collector error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                    processed_event.set()
                    
                    if consecutive_errors >= max_consecutive_errors:
                        logger.critical("Too many consecutive errors, stopping collector")
                        self._emit_error_occurred("프레임 수집 중 심각한 오류 발생")
                        break
            else:
                continue
        
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
    
    def is_gpu_mode(self) -> bool:
        """GPU 모드 사용 여부 (녹화에서는 항상 CPU 사용)"""
        return False
    
    def set_gpu_mode(self, enabled: bool):
        """GPU 모드 설정 (녹화에서는 무시 - FFmpeg 인코딩에서만 GPU 사용)"""
        pass



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
        
        # 복사 없이 원본 프레임에 직접 그리기 (이미 캡처된 프레임이므로 안전)
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
    except Exception:
        return frame

def draw_click_highlight_internal(frame: np.ndarray, region_x: int, region_y: int, last_click_pos, click_lock) -> np.ndarray:
    """마우스 클릭 하이라이트 그리기 (Top-level function)"""
    if not HAS_WIN32 or last_click_pos is None:
        return frame
    
    with click_lock:
        click_x, click_y, click_time = last_click_pos
        current_time = time.perf_counter()
        if current_time - click_time > 0.3: # duration
            return frame
    
    try:
        cx, cy = click_x - region_x, click_y - region_y
        h, w = frame.shape[:2]
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            return frame
        
        frame = frame.copy()
        elapsed = current_time - click_time
        fade_ratio = 1.0 - (elapsed / 0.3)
        alpha = max(0.0, min(1.0, fade_ratio))
        radius = int(20 * alpha)
        if radius < 2: return frame
        
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
    except Exception:
        return frame

class CaptureThread(threading.Thread):
    """스레드 기반 캡처 워커 (프로세스 대신 스레드 사용 - 공유 DXCam 카메라 재사용 가능)"""
    
    def __init__(self, region: Tuple[int, int, int, int], fps: int, include_cursor: bool,
                 show_click_highlight: bool, shm_buffer: np.ndarray,
                 stop_event: threading.Event, pause_event: threading.Event,
                 shm_event: threading.Event, shm_processed_event: threading.Event,
                 preferred_backend: str, webcam_enabled: bool, watermark_enabled: bool,
                 keyboard_enabled: bool, hdr_correction_force: bool = False,
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
        self.webcam_enabled = webcam_enabled
        self.watermark_enabled = watermark_enabled
        self.keyboard_enabled = keyboard_enabled
        self.hdr_correction_force = hdr_correction_force
        self._on_failed = on_failed  # 백엔드/캡처 실패 시 메인 스레드에 알림
        self._debug_png_saved = False  # HDR 비교용 PNG 첫 프레임만 저장
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
                except Exception as cb_e:
                    logger.warning(f"[CaptureThread] on_failed callback error: {cb_e}")
        
        try:
            x, y, w, h = self.region
            
            # 백엔드 생성 (DXCam의 경우 공유 카메라 재사용됨 - 즉시 시작!)
            try:
                backend = create_capture_backend(self.preferred_backend)
                if not backend or not backend.start(self.region, target_fps=self.fps):
                    err_msg = f"캡처 백엔드 시작 실패: {self.preferred_backend}"
                    logger.error(f"[CaptureThread] {err_msg}")
                    _notify_failed(err_msg)
                    return
                logger.info(f"[CaptureThread] Backend started: {backend.get_name()}")
                name = (backend.get_name() or "").lower()
                self._backend_is_dxcam = "dxcam" in name
                self._backend_is_gdi = name == "gdi"
            except (RuntimeError, OSError) as e:
                err_msg = f"캡처 백엔드 생성/시작 실패: {e}"
                logger.error(f"[CaptureThread] Backend creation failed: {e}")
                _notify_failed(err_msg)
                return
            
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
                    except Exception as e:
                        logger.error(f"[CaptureThread] Click detection error: {e}")
                
                threading.Thread(target=click_detection, daemon=True).start()
            
            # 오버레이 초기화
            watermark = None
            if self.watermark_enabled:
                try:
                    from .watermark import Watermark
                    watermark = Watermark()
                    watermark.set_enabled(True)
                except Exception as e:
                    logger.warning(f"[CaptureThread] Watermark init failed: {e}")
            
            if self.keyboard_enabled:
                try:
                    from .keyboard_display import KeyboardDisplay
                    keyboard = KeyboardDisplay()
                    keyboard.set_enabled(True)
                    keyboard.start_listening()
                except Exception as e:
                    logger.warning(f"[CaptureThread] Keyboard init failed: {e}")
            
            frame_interval = 1.0 / self.fps
            next_capture_time = time.perf_counter()
            first_frame_captured = False
            
            # 성능 프로파일링용 타이밍 추적
            timing_samples = {'grab': [], 'hdr': [], 'cursor': [], 'overlay': []}
            
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
                        # HDR 비교용: 녹화 첫 프레임만 캡처 직전/직후 PNG 저장 (XGIF_DEBUG_HDR_PNG=1)
                        if not getattr(self, '_debug_png_saved', True):
                            _save_debug_hdr_png(frame, "recording_frame_before_hdr")
                        # 첫 프레임 캡처 성공
                        if not first_frame_captured:
                            first_frame_captured = True
                            next_capture_time = current_time
                            self._first_frame_ready.set()
                            logger.info(f"[CaptureThread] First frame captured - recording active!")
                        
                        # HDR 보정: 사용자가 수동으로 켤 때만 적용 (적응형)
                        # 단, GDI 백엔드는 Windows가 자동으로 색상 관리를 처리하므로 보정 스킵
                        t2 = time.perf_counter()
                        if not self._backend_is_gdi and getattr(self, 'hdr_correction_force', False):
                            frame = apply_hdr_correction_adaptive(frame)
                        t3 = time.perf_counter()
                        timing_samples['hdr'].append(t3 - t2)
                        
                        # 비교용 after PNG (보정 여부 무관하게 저장)
                        if not getattr(self, '_debug_png_saved', True):
                            _save_debug_hdr_png(frame, "recording_frame_after_hdr")
                            self._debug_png_saved = True
                        
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
                            avg_grab = sum(timing_samples['grab'][-100:]) / min(100, len(timing_samples['grab']))
                            avg_hdr = sum(timing_samples['hdr'][-100:]) / min(100, len(timing_samples['hdr']))
                            avg_cursor = sum(timing_samples['cursor'][-100:]) / min(100, len(timing_samples['cursor']))
                            avg_overlay = sum(timing_samples['overlay'][-100:]) / min(100, len(timing_samples['overlay']))
                            total_avg = avg_grab + avg_hdr + avg_cursor + avg_overlay
                            logger.info(f"[Perf] Frame {self.frame_count}: grab={avg_grab*1000:.1f}ms, hdr={avg_hdr*1000:.1f}ms, cursor={avg_cursor*1000:.1f}ms, overlay={avg_overlay*1000:.1f}ms, total={total_avg*1000:.1f}ms")
                            # timing 리스트 trim (메모리 무한 성장 방지)
                            for key in timing_samples:
                                if len(timing_samples[key]) > 200:
                                    del timing_samples[key][:-200]
                        
                        # 공유 버퍼에 쓰기
                        if self.shm_processed_event.wait(timeout=0.5):
                            self.shm_processed_event.clear()
                            np.copyto(self.shm_buffer, frame)
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
            
        except Exception as e:
            logger.exception(f"[CaptureThread] Fatal error: {e}")
            _notify_failed(f"녹화 캡처 오류: {e}")
        finally:
            # 항상 리소스 정리 (예외 발생해도)
            logger.debug("[CaptureThread] Cleaning up resources...")
            
            if backend:
                try:
                    backend.stop()
                except Exception as e:
                    logger.error(f"[CaptureThread] Backend stop error: {e}")
            
            if keyboard:
                try:
                    keyboard.stop_listening()
                except Exception as e:
                    logger.error(f"[CaptureThread] Keyboard stop error: {e}")
            
            logger.debug("[CaptureThread] Cleanup complete")
