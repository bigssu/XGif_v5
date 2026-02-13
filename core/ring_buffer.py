"""고정 크기 링 버퍼 — 프레임 수집용 (Lock-free SPSC 패턴).

단일 생산자(CaptureThread) → 단일 소비자(FrameCollectorThread) 구조에서
프레임 드롭 없이 고속 전달을 위한 링 버퍼.
"""

import logging
import threading
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)


class RingFrameBuffer:
    """고정 크기 numpy 프레임 링 버퍼.

    Args:
        capacity: 버퍼 슬롯 수 (프레임 개수)
        height: 프레임 높이
        width: 프레임 너비
        channels: 채널 수 (기본 3=BGR)

    Usage:
        buf = RingFrameBuffer(capacity=120, height=720, width=1280)
        buf.write(frame)       # 생산자
        frame = buf.read()     # 소비자
    """

    def __init__(self, capacity: int, height: int, width: int,
                 channels: int = 3) -> None:
        if capacity < 2:
            raise ValueError("capacity must be >= 2")
        self._capacity = capacity
        self._height = height
        self._width = width
        self._channels = channels

        # 고정 크기 numpy 배열 (사전 할당)
        self._buffer = np.zeros(
            (capacity, height, width, channels), dtype=np.uint8
        )

        # 포인터 (단일 생산자-단일 소비자에서는 원자적)
        self._write_idx = 0
        self._read_idx = 0
        self._count = 0
        self._lock = threading.Lock()

        # 통계
        self._total_written = 0
        self._total_dropped = 0

    @property
    def capacity(self) -> int:
        return self._capacity

    @property
    def count(self) -> int:
        """현재 버퍼에 있는 프레임 수."""
        return self._count

    @property
    def is_full(self) -> bool:
        return self._count >= self._capacity

    @property
    def is_empty(self) -> bool:
        return self._count == 0

    @property
    def dropped_count(self) -> int:
        """드롭된 프레임 수."""
        return self._total_dropped

    def write(self, frame: np.ndarray) -> bool:
        """프레임을 버퍼에 쓴다.

        버퍼가 가득 차면 가장 오래된 프레임을 덮어쓴다 (드롭).

        Returns:
            True=정상 기록, False=오래된 프레임 덮어씀 (드롭)
        """
        h, w = frame.shape[:2]
        if h != self._height or w != self._width:
            # 크기가 다르면 리사이즈 (드물지만 안전)
            from PIL import Image
            img = Image.fromarray(frame)
            img = img.resize((self._width, self._height), Image.NEAREST)
            frame = np.array(img)

        dropped = False
        with self._lock:
            if self._count >= self._capacity:
                # 가장 오래된 데이터 덮어쓰기 (read 포인터 전진)
                self._read_idx = (self._read_idx + 1) % self._capacity
                self._count -= 1
                self._total_dropped += 1
                dropped = True

            self._buffer[self._write_idx] = frame
            self._write_idx = (self._write_idx + 1) % self._capacity
            self._count += 1
            self._total_written += 1

        return not dropped

    def read(self) -> Optional[np.ndarray]:
        """버퍼에서 가장 오래된 프레임을 읽는다.

        Returns:
            프레임 numpy 배열 (복사본), 비어있으면 None
        """
        with self._lock:
            if self._count == 0:
                return None

            frame = self._buffer[self._read_idx].copy()
            self._read_idx = (self._read_idx + 1) % self._capacity
            self._count -= 1

        return frame

    def read_all(self) -> list:
        """버퍼의 모든 프레임을 순서대로 읽는다 (버퍼 비움)."""
        frames = []
        while True:
            frame = self.read()
            if frame is None:
                break
            frames.append(frame)
        return frames

    def clear(self) -> None:
        """버퍼를 비운다."""
        with self._lock:
            self._write_idx = 0
            self._read_idx = 0
            self._count = 0

    def get_stats(self) -> dict:
        """버퍼 통계 반환."""
        return {
            "capacity": self._capacity,
            "count": self._count,
            "total_written": self._total_written,
            "total_dropped": self._total_dropped,
            "drop_rate": (
                self._total_dropped / self._total_written * 100
                if self._total_written > 0
                else 0.0
            ),
        }
