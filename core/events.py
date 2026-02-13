"""
앱 전역 이벤트 버스 (Pub/Sub)

기존 CaptureControlBar의 set_*_callback() 수동 관리를 대체.
EventBus.emit()으로 발행, subscribe()로 구독.
GUI 스레드 안전: emit_on_main_thread() 사용 시 wx.CallAfter 자동 래핑.
"""

import logging
import threading
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class AppEvent(Enum):
    """앱 전역 이벤트 타입"""

    # --- 녹화 ---
    RECORDING_REQUESTED = auto()
    RECORDING_START = auto()
    RECORDING_STOP = auto()
    RECORDING_PAUSE = auto()
    STOP_CLICKED = auto()
    PAUSE_CLICKED = auto()

    # --- 인코딩 ---
    ENCODING_PROGRESS = auto()
    ENCODING_COMPLETE = auto()
    ENCODING_ERROR = auto()

    # --- 설정/UI 변경 ---
    SETTINGS_REQUESTED = auto()
    SETTINGS_CHANGED = auto()
    LANGUAGE_CHANGED = auto()
    REGION_CHANGED = auto()
    FORMAT_CHANGED = auto()
    FPS_CHANGED = auto()
    QUALITY_CHANGED = auto()
    RESOLUTION_CHANGED = auto()

    # --- 토글 ---
    CURSOR_TOGGLED = auto()
    REGION_TOGGLED = auto()

    # --- 시스템 ---
    GPU_STATUS_CHANGED = auto()
    GPU_CLICK = auto()
    OVERLAY_CLOSED = auto()
    SYSTEM_CAPABILITIES_DETECTED = auto()
    HELP_REQUESTED = auto()


class EventBus:
    """경량 Pub/Sub 이벤트 버스.

    스레드 안전: 내부 Lock으로 subscribe/unsubscribe/emit 동기화.
    """

    def __init__(self) -> None:
        self._subscribers: Dict[AppEvent, List[Callable]] = {}
        self._lock = threading.Lock()

    def subscribe(self, event: AppEvent, callback: Callable) -> None:
        """이벤트 구독."""
        with self._lock:
            if event not in self._subscribers:
                self._subscribers[event] = []
            if callback not in self._subscribers[event]:
                self._subscribers[event].append(callback)

    def unsubscribe(self, event: AppEvent, callback: Callable) -> None:
        """이벤트 구독 해제."""
        with self._lock:
            if event in self._subscribers:
                try:
                    self._subscribers[event].remove(callback)
                except ValueError:
                    pass

    def emit(self, event: AppEvent, *args: Any, **kwargs: Any) -> None:
        """이벤트 발행 (현재 스레드에서 콜백 실행)."""
        with self._lock:
            callbacks = list(self._subscribers.get(event, []))
        for cb in callbacks:
            try:
                cb(*args, **kwargs)
            except Exception:
                logger.exception("EventBus callback error for %s", event)

    def emit_on_main_thread(self, event: AppEvent, *args: Any, **kwargs: Any) -> None:
        """이벤트 발행 (wx 메인 스레드에서 콜백 실행).

        백그라운드 스레드에서 GUI 이벤트를 안전하게 발행할 때 사용.
        """
        try:
            import wx
            wx.CallAfter(self.emit, event, *args, **kwargs)
        except Exception:
            # wx 미사용 환경 (CLI)에서는 직접 실행
            self.emit(event, *args, **kwargs)

    def clear(self) -> None:
        """모든 구독 해제."""
        with self._lock:
            self._subscribers.clear()


# ─── 글로벌 싱글톤 ───

_bus: Optional[EventBus] = None
_bus_lock = threading.Lock()


def get_event_bus() -> EventBus:
    """앱 전역 EventBus 인스턴스 반환."""
    global _bus
    if _bus is None:
        with _bus_lock:
            if _bus is None:
                _bus = EventBus()
    return _bus
