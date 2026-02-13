"""인코더 공통 인터페이스 (ABC)."""

from abc import ABC, abstractmethod
from typing import Callable, List, Optional

import numpy as np


class EncoderBase(ABC):
    """GIF/MP4 인코더 공통 베이스 클래스."""

    def __init__(self) -> None:
        self._progress_callback: Optional[Callable[[int, int], None]] = None
        self._finished_callback: Optional[Callable[[str], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        self._quality: str = "high"

    # ─── 콜백 설정 ───

    def set_progress_callback(self, callback: Callable[[int, int], None]) -> None:
        self._progress_callback = callback

    def set_finished_callback(self, callback: Callable[[str], None]) -> None:
        self._finished_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]) -> None:
        self._error_callback = callback

    # ─── 품질 설정 ───

    def set_quality(self, quality: str) -> None:
        """품질 설정 ('high', 'medium', 'low')."""
        self._quality = quality

    # ─── 진행률 알림 ───

    def _emit_progress(self, current: int, total: int) -> None:
        if self._progress_callback:
            self._progress_callback(current, total)

    def _emit_finished(self, output_path: str) -> None:
        if self._finished_callback:
            self._finished_callback(output_path)

    def _emit_error(self, message: str) -> None:
        if self._error_callback:
            self._error_callback(message)

    # ─── 인코딩 (추상) ───

    @abstractmethod
    def encode(self, frames: List[np.ndarray], fps: int, output_path: str) -> bool:
        """GIF 인코딩."""
        ...

    @abstractmethod
    def encode_mp4(self, frames: List[np.ndarray], fps: int,
                   output_path: str, audio_path: Optional[str] = None) -> bool:
        """MP4 인코딩."""
        ...
