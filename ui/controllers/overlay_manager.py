"""캡처 오버레이 라이프사이클 관리."""

import logging
from typing import TYPE_CHECKING

import wx

from ui.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class OverlayManager:
    """CaptureOverlay 생성/위치/닫힘 관리."""

    def __init__(self, window: "MainWindow") -> None:
        self._w = window

    def show_capture_overlay(self) -> None:
        """캡처 오버레이 표시."""
        from ui.capture_overlay import CaptureOverlay

        w = self._w
        if w._is_closing:
            return

        try:
            if not w or not w.GetHandle():
                return
        except RuntimeError:
            return

        if w.capture_overlay is None:
            w.capture_overlay = CaptureOverlay(w)
            w.capture_overlay.set_region_changed_callback(w._on_region_changed)
            w.capture_overlay.set_closed_callback(self.on_overlay_closed)

            saved_resolution = w.settings.get("resolution_preset", "320 × 240")
            try:
                clean = saved_resolution.replace("×", "x").replace(" ", "").lower()
                if "x" in clean:
                    parts = clean.split("x")
                    ww, hh = int(parts[0]), int(parts[1])
                    w.capture_overlay.set_capture_size(ww, hh)
                else:
                    w.capture_overlay.set_capture_size(320, 240)
            except (ValueError, IndexError):
                w.capture_overlay.set_capture_size(320, 240)

        self.position_overlay_below_window()
        w.capture_overlay.Show()
        w.capture_overlay.Raise()

    def position_overlay_below_window(self) -> None:
        """캡처 오버레이를 메인 윈도우 하단에 위치."""
        w = self._w
        if w.capture_overlay:
            main_rect = w.GetRect()
            new_x = main_rect.x
            new_y = main_rect.y + main_rect.height + 5
            w.capture_overlay.SetPosition((new_x, new_y))

    def on_overlay_closed(self) -> None:
        """오버레이 창 닫힘 처리."""
        w = self._w
        w.capture_overlay = None

        if w._is_closing:
            return
        if w._editor_mode:
            return
        if w.record_state == w.STATE_READY:
            wx.CallLater(100, self.show_capture_overlay)

    def on_window_move(self, current_pos) -> None:
        """메인 윈도우 이동 시 오버레이 델타 이동."""
        w = self._w
        if w._last_pos is None:
            w._last_pos = current_pos
            return
        if w.capture_overlay and w.capture_overlay.IsShown():
            if w.record_state == w.STATE_READY:
                dx = current_pos.x - w._last_pos.x
                dy = current_pos.y - w._last_pos.y
                if dx != 0 or dy != 0:
                    overlay_pos = w.capture_overlay.GetPosition()
                    w.capture_overlay.SetPosition((overlay_pos.x + dx, overlay_pos.y + dy))
        w._last_pos = current_pos
