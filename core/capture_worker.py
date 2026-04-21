"""
캡처 워커 스레드 및 드로잉 헬퍼.

P1-1: 원래 core/screen_recorder.py 에 함께 있던 CaptureThread 와
draw_cursor_internal / draw_click_highlight_internal 을 분리한 모듈.
P1-2: 공개 kwarg 를 shm_* → frame_* 로 리네임하여 multiprocessing.SharedMemory
미사용 사실을 네이밍에 반영 (실제로는 NumPy 버퍼 + threading.Event 조합).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Callable, Optional, Tuple

import numpy as np

from .capture_backend import _start_backend_with_fallback
from .hdr_utils import apply_hdr_correction_adaptive

logger = logging.getLogger(__name__)

# 클릭 하이라이트 표시 시간 (초). screen_recorder 와 공유되는 상수.
CLICK_HIGHLIGHT_DURATION = 0.3

# Windows 커서 캡처용 ctypes 바인딩. 비-Windows에서는 no-op.
try:
    import ctypes
    from ctypes import wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


def draw_cursor_internal(frame: np.ndarray, region_x: int, region_y: int) -> np.ndarray:
    """마우스 커서를 프레임에 그리기 (Top-level function, in-place)."""
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


def draw_click_highlight_internal(
    frame: np.ndarray,
    region_x: int,
    region_y: int,
    last_click_pos,
    click_lock,
) -> np.ndarray:
    """마우스 클릭 하이라이트 그리기 (Top-level function)."""
    if not HAS_WIN32 or last_click_pos is None:
        return frame

    with click_lock:
        click_x, click_y, click_time = last_click_pos
        current_time = time.perf_counter()
        if current_time - click_time > CLICK_HIGHLIGHT_DURATION:
            return frame

    try:
        cx, cy = click_x - region_x, click_y - region_y
        h, w = frame.shape[:2]
        if cx < 0 or cy < 0 or cx >= w or cy >= h:
            return frame

        if not frame.flags.writeable:
            frame = frame.copy()
        elapsed = current_time - click_time
        fade_ratio = 1.0 - (elapsed / CLICK_HIGHLIGHT_DURATION)
        alpha = max(0.0, min(1.0, fade_ratio))
        radius = int(20 * alpha)
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
    """스레드 기반 캡처 워커 (프로세스 대신 스레드 사용 — 공유 DXCam 카메라 재사용 가능).

    P0-2: watermark/keyboard_display 는 facade(ScreenRecorder)가 소유하는 단일
    인스턴스를 DI로 주입받는다. 워커가 별도 인스턴스를 만들지 않으므로 녹화 중
    facade에 대한 설정 변경이 워커에 반영된다.
    P1-2: frame_buffer / frame_ready_event / frame_consumed_event 로 리네임
    (구 이름: shm_buffer / shm_event / shm_processed_event. 실제 구현은
    multiprocessing.SharedMemory 가 아니라 NumPy 버퍼 + threading.Event).
    """

    def __init__(
        self,
        region: Tuple[int, int, int, int],
        fps: int,
        include_cursor: bool,
        show_click_highlight: bool,
        frame_buffer: np.ndarray,
        stop_event: threading.Event,
        pause_event: threading.Event,
        frame_ready_event: threading.Event,
        frame_consumed_event: threading.Event,
        preferred_backend: str,
        watermark=None,
        keyboard_display=None,
        hdr_correction_force: bool = False,
        on_failed: Optional[Callable[[str], None]] = None,
    ):
        super().__init__(daemon=True)

        self.region = region
        self.fps = fps
        self.include_cursor = include_cursor
        self.show_click_highlight = show_click_highlight
        self.frame_buffer = frame_buffer
        self.stop_event = stop_event
        self.pause_event = pause_event
        self.frame_ready_event = frame_ready_event
        self.frame_consumed_event = frame_consumed_event
        self.preferred_backend = preferred_backend
        # facade(ScreenRecorder)에서 주입받은 인스턴스. None일 수 있음.
        self.watermark = watermark
        self.keyboard_display = keyboard_display
        self.hdr_correction_force = hdr_correction_force
        self._on_failed = on_failed
        self._backend_is_dxcam = False

        # 통계
        self.frame_count = 0
        self.dropped_frames = 0
        self._first_frame_ready = threading.Event()

    def wait_for_first_frame(self, timeout: float = 1.0) -> bool:
        """첫 프레임이 캡처될 때까지 대기."""
        return self._first_frame_ready.wait(timeout=timeout)

    def run(self):
        """스레드에서 실행되는 캡처 루프."""
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
            timing_samples = {
                'grab': deque(maxlen=200),
                'hdr': deque(maxlen=200),
                'cursor': deque(maxlen=200),
                'overlay': deque(maxlen=200),
            }

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

                        # HDR 보정: 사용자가 수동으로 켤 때만 적용 (적응형).
                        # P1-6: backend.supports_managed_color 로 분기.
                        t2 = time.perf_counter()
                        if getattr(self, 'hdr_correction_force', False) and not backend.supports_managed_color:
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
                            logger.info(
                                f"[Perf] Frame {self.frame_count}: "
                                f"grab={avg_grab*1000:.1f}ms, "
                                f"hdr={avg_hdr*1000:.1f}ms, "
                                f"cursor={avg_cursor*1000:.1f}ms, "
                                f"overlay={avg_overlay*1000:.1f}ms, "
                                f"total={total_avg*1000:.1f}ms"
                            )

                        # 공유 버퍼에 쓰기
                        if self.frame_consumed_event.wait(timeout=0.5):
                            self.frame_consumed_event.clear()
                            if frame.shape == self.frame_buffer.shape:
                                np.copyto(self.frame_buffer, frame)
                            else:
                                logger.warning(
                                    f"[CaptureThread] Frame shape mismatch: {frame.shape} vs buffer "
                                    f"{self.frame_buffer.shape}, skipping"
                                )
                                self.dropped_frames += 1
                                self.frame_consumed_event.set()
                                continue
                            self.frame_ready_event.set()
                            self.frame_count += 1
                        else:
                            self.dropped_frames += 1
                            if self.dropped_frames % 10 == 0:
                                logger.warning(f"[CaptureThread] Dropped {self.dropped_frames} frames (backpressure)")
                    else:
                        # 프레임 없음 (화면 변화 없음 등) — 첫 프레임 전에는 재시도
                        if not first_frame_captured:
                            time.sleep(0.005)
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
                self.frame_ready_event.set()
            except Exception as set_exc:
                logger.debug(f"[CaptureThread] frame_ready_event.set() after fatal error failed: {set_exc}")
        finally:
            logger.debug("[CaptureThread] Cleaning up resources...")

            # P0-4: backend.stop() 실패 시 force_release() 폴백.
            # force_release() 는 CaptureBackend ABC 기본 구현(no-op)을 가지므로
            # 모든 백엔드에서 안전하게 호출 가능.
            if backend:
                try:
                    backend.stop()
                except Exception as exc:
                    logger.error(f"[CaptureThread] Backend stop error: {exc}")
                    try:
                        backend.force_release()
                        logger.warning("[CaptureThread] Backend force_release() invoked after stop() failure")
                    except Exception as exc2:
                        logger.error(f"[CaptureThread] Backend force_release error: {exc2}")

            # keyboard/watermark 는 facade 소유 인스턴스이므로 stop_listening() 만 호출.
            if keyboard:
                try:
                    keyboard.stop_listening()
                except Exception as exc:
                    logger.error(f"[CaptureThread] Keyboard stop error: {exc}")

            logger.debug("[CaptureThread] Cleanup complete")
