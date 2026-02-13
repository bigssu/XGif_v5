"""마우스 커서 오버레이."""

import logging
from typing import Optional, Tuple

import numpy as np

from .pipeline import OverlayBase

logger = logging.getLogger(__name__)

try:
    import ctypes
    from ctypes import wintypes
    HAS_WIN32 = True
except ImportError:
    HAS_WIN32 = False


class CursorOverlay(OverlayBase):
    """캡처 프레임에 마우스 커서를 그리는 오버레이."""

    def __init__(self) -> None:
        super().__init__()
        self._cursor_size = 16

    def apply(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """프레임에 커서를 그린다.

        kwargs:
            capture_x, capture_y: 캡처 영역의 좌상단 좌표
        """
        if not HAS_WIN32:
            return frame

        capture_x = kwargs.get("capture_x", 0)
        capture_y = kwargs.get("capture_y", 0)

        try:
            cursor_info = _get_cursor_pos()
            if cursor_info is None:
                return frame

            cx, cy = cursor_info
            # 캡처 영역 기준 상대 좌표
            rel_x = cx - capture_x
            rel_y = cy - capture_y

            h, w = frame.shape[:2]
            if 0 <= rel_x < w and 0 <= rel_y < h:
                frame = _draw_cursor_simple(frame, rel_x, rel_y, self._cursor_size)
        except Exception as e:
            logger.debug("CursorOverlay error: %s", e)

        return frame


def _get_cursor_pos() -> Optional[Tuple[int, int]]:
    """현재 커서 위치를 반환."""
    if not HAS_WIN32:
        return None
    try:
        point = wintypes.POINT()
        ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
        return (point.x, point.y)
    except Exception:
        return None


def _draw_cursor_simple(frame: np.ndarray, x: int, y: int, size: int) -> np.ndarray:
    """간단한 커서 십자선 그리기 (외부 라이브러리 없이)."""
    h, w = frame.shape[:2]
    half = size // 2

    # 수직선
    y1 = max(0, y - half)
    y2 = min(h, y + half)
    if 0 <= x < w:
        frame[y1:y2, x] = [255, 255, 255] if frame.shape[2] >= 3 else 255

    # 수평선
    x1 = max(0, x - half)
    x2 = min(w, x + half)
    if 0 <= y < h:
        frame[y, x1:x2] = [255, 255, 255] if frame.shape[2] >= 3 else 255

    return frame
