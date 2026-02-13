"""실시간 미리보기 관리."""

import logging
from typing import TYPE_CHECKING

import numpy as np
import wx

from ui.i18n import tr

if TYPE_CHECKING:
    from ui.main_window import MainWindow

logger = logging.getLogger(__name__)


class PreviewManager:
    """preview_timer, preview_widget 관리."""

    def __init__(self, window: "MainWindow") -> None:
        self._w = window

    def start_preview(self) -> None:
        """실시간 미리보기 시작."""
        w = self._w
        if not w.preview_enabled:
            return
        if not hasattr(w, "preview_widget") or not w.preview_widget:
            return

        # 기존 타이머 정리
        if w.preview_timer is not None:
            try:
                w.preview_timer.Stop()
            except (TypeError, RuntimeError, AttributeError):
                pass
            w.preview_timer = None

        w.preview_timer = wx.Timer(w)
        w.Bind(wx.EVT_TIMER, lambda e: self.update_preview(), w.preview_timer)
        w.preview_timer.Start(100)  # 10 FPS
        w.preview_widget.Show()

    def stop_preview(self) -> None:
        """실시간 미리보기 중지."""
        from core.utils import safe_delete_timer

        w = self._w
        if w.preview_timer:
            safe_delete_timer(w.preview_timer)
            w.preview_timer = None

        if hasattr(w, "preview_widget") and w.preview_widget:
            w.preview_widget.Hide()
            if hasattr(w, "preview_label") and w.preview_label:
                w.preview_label.SetLabel(tr("preview"))

    def update_preview(self) -> None:
        """미리보기 프레임 업데이트."""
        w = self._w
        try:
            if not w or w.recorder is None or not w.preview_enabled:
                return
            if not hasattr(w, "preview_label") or w.preview_label is None:
                return

            frame = w.recorder.capture_single_frame()
            if frame is None:
                return
            if not isinstance(frame, np.ndarray):
                logger.warning("Invalid frame type: %s", type(frame))
                return
            if len(frame.shape) < 2 or frame.size == 0:
                return

            frame = np.ascontiguousarray(frame, dtype=np.uint8)
            h, fw = frame.shape[:2]
            if h <= 0 or fw <= 0:
                return
            if len(frame.shape) < 3 or frame.shape[2] < 3:
                logger.warning("Invalid frame channels: %s", frame.shape)
                return
        except (AttributeError, ValueError, TypeError, RuntimeError) as e:
            logger.debug("미리보기 업데이트 실패: %s", e)
