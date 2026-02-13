"""마우스 클릭 하이라이트 오버레이."""

import logging
import time
from typing import Optional, Tuple

import numpy as np

from .pipeline import OverlayBase

logger = logging.getLogger(__name__)


class ClickHighlightOverlay(OverlayBase):
    """마우스 클릭 시 시각적 하이라이트를 표시하는 오버레이."""

    def __init__(self, duration: float = 0.3, radius: int = 20,
                 color: Tuple[int, int, int] = (255, 255, 0)) -> None:
        super().__init__()
        self._duration = duration
        self._radius = radius
        self._color = color
        self._last_click_pos: Optional[Tuple[int, int]] = None
        self._last_click_time: float = 0.0

    def register_click(self, x: int, y: int) -> None:
        """클릭 위치 등록."""
        self._last_click_pos = (x, y)
        self._last_click_time = time.time()

    def apply(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """클릭 하이라이트를 프레임에 그린다."""
        if self._last_click_pos is None:
            return frame

        elapsed = time.time() - self._last_click_time
        if elapsed > self._duration:
            self._last_click_pos = None
            return frame

        capture_x = kwargs.get("capture_x", 0)
        capture_y = kwargs.get("capture_y", 0)

        cx, cy = self._last_click_pos
        rel_x = cx - capture_x
        rel_y = cy - capture_y

        h, w = frame.shape[:2]
        if not (0 <= rel_x < w and 0 <= rel_y < h):
            return frame

        # 페이드아웃 알파
        alpha = max(0.0, 1.0 - (elapsed / self._duration))
        r = int(self._radius * (1.0 + (1.0 - alpha) * 0.5))

        try:
            frame = _draw_highlight_circle(frame, rel_x, rel_y, r, self._color, alpha)
        except Exception as e:
            logger.debug("ClickHighlight draw error: %s", e)

        return frame


def _draw_highlight_circle(
    frame: np.ndarray, cx: int, cy: int, radius: int,
    color: Tuple[int, int, int], alpha: float,
) -> np.ndarray:
    """프레임에 반투명 원을 그린다 (numpy only)."""
    h, w = frame.shape[:2]

    y1 = max(0, cy - radius)
    y2 = min(h, cy + radius + 1)
    x1 = max(0, cx - radius)
    x2 = min(w, cx + radius + 1)

    if y2 <= y1 or x2 <= x1:
        return frame

    # 원 마스크 생성
    yy, xx = np.ogrid[y1 - cy:y2 - cy, x1 - cx:x2 - cx]
    mask = (xx * xx + yy * yy) <= radius * radius

    roi = frame[y1:y2, x1:x2]
    color_arr = np.array(color, dtype=np.uint8)

    blended = (roi * (1.0 - alpha * 0.4) + color_arr * alpha * 0.4).astype(np.uint8)
    roi[mask] = blended[mask]

    return frame
