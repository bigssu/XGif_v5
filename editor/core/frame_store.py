"""FrameStore — LRU 메모리 캐시 + 디스크 스왑.

대용량 GIF (100+ 프레임) 편집 시 메모리 사용량을 제한한다.
자주 접근하는 프레임은 메모리에, 나머지는 디스크에 저장.
"""

import atexit
import logging
import os
import tempfile
from collections import OrderedDict
from typing import Optional

import numpy as np

from ..utils.logger import get_logger

_logger = get_logger()


class FrameStore:
    """LRU 기반 프레임 메모리 캐시 + 디스크 스왑.

    Args:
        max_memory_frames: 메모리에 유지할 최대 프레임 수
        swap_dir: 스왑 디렉토리 (None이면 자동 생성)
    """

    def __init__(self, max_memory_frames: int = 50,
                 swap_dir: Optional[str] = None) -> None:
        self._max_frames = max_memory_frames
        self._cache: OrderedDict[int, np.ndarray] = OrderedDict()
        self._on_disk: set = set()

        if swap_dir:
            self._swap_dir = swap_dir
            os.makedirs(swap_dir, exist_ok=True)
        else:
            self._swap_dir = tempfile.mkdtemp(prefix="xgif_swap_")

        atexit.register(self.cleanup)

    # ─── 공개 API ───

    def put(self, frame_id: int, data: np.ndarray) -> None:
        """프레임을 저장한다 (캐시 우선, 초과 시 디스크)."""
        # 이미 캐시에 있으면 갱신
        if frame_id in self._cache:
            self._cache.move_to_end(frame_id)
            self._cache[frame_id] = data
            return

        # 디스크에 있었다면 제거
        if frame_id in self._on_disk:
            self._on_disk.discard(frame_id)
            disk_path = self._frame_path(frame_id)
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    pass

        # 캐시에 추가
        self._cache[frame_id] = data
        self._cache.move_to_end(frame_id)

        # 캐시 초과 시 가장 오래된 항목을 디스크로 축출
        self._evict_if_needed()

    def get(self, frame_id: int) -> Optional[np.ndarray]:
        """프레임을 반환한다 (캐시 미스 시 디스크에서 로드)."""
        # 캐시 히트
        if frame_id in self._cache:
            self._cache.move_to_end(frame_id)
            return self._cache[frame_id]

        # 디스크에서 로드
        if frame_id in self._on_disk:
            data = self._load_from_disk(frame_id)
            if data is not None:
                # 캐시로 승격
                self._cache[frame_id] = data
                self._cache.move_to_end(frame_id)
                self._on_disk.discard(frame_id)
                self._evict_if_needed()
                return data

        return None

    def remove(self, frame_id: int) -> None:
        """프레임을 삭제한다."""
        self._cache.pop(frame_id, None)
        if frame_id in self._on_disk:
            self._on_disk.discard(frame_id)
            disk_path = self._frame_path(frame_id)
            if os.path.exists(disk_path):
                try:
                    os.remove(disk_path)
                except OSError:
                    pass

    def contains(self, frame_id: int) -> bool:
        return frame_id in self._cache or frame_id in self._on_disk

    @property
    def total_count(self) -> int:
        return len(self._cache) + len(self._on_disk)

    @property
    def memory_count(self) -> int:
        return len(self._cache)

    @property
    def disk_count(self) -> int:
        return len(self._on_disk)

    def clear(self) -> None:
        """모든 프레임 삭제 (메모리 + 디스크)."""
        self._cache.clear()
        for fid in list(self._on_disk):
            path = self._frame_path(fid)
            if os.path.exists(path):
                try:
                    os.remove(path)
                except OSError:
                    pass
        self._on_disk.clear()

    def cleanup(self) -> None:
        """스왑 디렉토리 정리 (atexit에서 호출)."""
        self.clear()
        try:
            if os.path.isdir(self._swap_dir):
                import shutil
                shutil.rmtree(self._swap_dir, ignore_errors=True)
        except Exception:
            pass

    # ─── 내부 ───

    def _evict_if_needed(self) -> None:
        """캐시 크기 초과 시 가장 오래된 항목을 디스크로 축출."""
        while len(self._cache) > self._max_frames:
            oldest_id, oldest_data = self._cache.popitem(last=False)
            self._save_to_disk(oldest_id, oldest_data)
            self._on_disk.add(oldest_id)

    def _frame_path(self, frame_id: int) -> str:
        return os.path.join(self._swap_dir, f"frame_{frame_id}.npy")

    def _save_to_disk(self, frame_id: int, data: np.ndarray) -> None:
        try:
            np.save(self._frame_path(frame_id), data)
        except Exception as e:
            _logger.warning("Frame %d disk save failed: %s", frame_id, e)

    def _load_from_disk(self, frame_id: int) -> Optional[np.ndarray]:
        path = self._frame_path(frame_id)
        if not os.path.exists(path):
            return None
        try:
            return np.load(path)
        except Exception as e:
            _logger.warning("Frame %d disk load failed: %s", frame_id, e)
            return None
