"""오버레이 베이스 클래스 및 파이프라인."""

import logging
from abc import ABC, abstractmethod
from typing import List

import numpy as np

logger = logging.getLogger(__name__)


class OverlayBase(ABC):
    """프레임 오버레이 공통 인터페이스.

    각 오버레이는 `enabled` 플래그와 `apply(frame)` 메서드를 구현한다.
    """

    def __init__(self) -> None:
        self._enabled: bool = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, value: bool) -> None:
        self._enabled = value

    @abstractmethod
    def apply(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """프레임에 오버레이를 적용하고 결과를 반환.

        Args:
            frame: 입력 프레임 (BGR numpy 배열)
            **kwargs: 오버레이별 추가 인자 (capture_x, capture_y 등)

        Returns:
            오버레이가 적용된 프레임
        """
        ...


class OverlayPipeline:
    """오버레이를 순차적으로 적용하는 파이프라인.

    Usage:
        pipeline = OverlayPipeline()
        pipeline.add(CursorOverlay(...))
        pipeline.add(ClickHighlightOverlay(...))
        frame = pipeline.apply(frame, capture_x=x, capture_y=y)
    """

    def __init__(self) -> None:
        self._overlays: List[OverlayBase] = []

    def add(self, overlay: OverlayBase) -> None:
        """오버레이를 파이프라인에 추가."""
        self._overlays.append(overlay)

    def remove(self, overlay: OverlayBase) -> None:
        """오버레이를 파이프라인에서 제거."""
        try:
            self._overlays.remove(overlay)
        except ValueError:
            pass

    def apply(self, frame: np.ndarray, **kwargs) -> np.ndarray:
        """활성화된 모든 오버레이를 순차 적용."""
        for overlay in self._overlays:
            if overlay.enabled:
                try:
                    frame = overlay.apply(frame, **kwargs)
                except Exception as e:
                    logger.debug("Overlay %s failed: %s",
                                 type(overlay).__name__, e)
        return frame

    def clear(self) -> None:
        """모든 오버레이 제거."""
        self._overlays.clear()

    @property
    def overlays(self) -> List[OverlayBase]:
        return list(self._overlays)
