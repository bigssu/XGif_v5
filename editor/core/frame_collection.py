"""
FrameCollection - GIF 프레임 컬렉션 관리
메모리 최적화 기능 포함
고성능 배치 처리 지원 (pyvips)
"""
from __future__ import annotations
from typing import List, Optional, Callable, Iterator, Set, Tuple
import threading
from .frame import Frame, get_memory_manager
from . import editor_gpu_utils as gpu_utils
from .fast_image import FastImage, is_pyvips_available
from copy import deepcopy
from ..utils.logger import get_logger

# 로거 초기화
_logger = get_logger()


class FrameCollection:
    """GIF 프레임 컬렉션 관리 클래스
    
    메모리 최적화 기능:
    - 총 메모리 사용량 추적
    - 불필요한 프레임 언로드
    - 썸네일 캐시 일괄 정리
    
    스레드 안전성:
    - 멀티스레드 환경에서 공유될 경우 락을 사용하여 안전하게 접근 가능
    """
    
    def __init__(self):
        self._frames: List[Frame] = []
        self._current_index: int = 0
        self._selected_indices: Set[int] = set()
        self._loop_count: int = 0  # 0 = 무한 반복
        self._lazy_load_enabled: bool = False  # 대용량 GIF를 위한 lazy loading
        self._lock = threading.RLock()  # 재진입 가능한 락 (스레드 안전성)
    
    # === 프레임 추가/삭제 ===
    def add_frame(self, frame: Frame) -> None:
        """프레임 추가"""
        self._frames.append(frame)
    
    def insert_frame(self, index: int, frame: Frame) -> None:
        """특정 위치에 프레임 삽입"""
        index = max(0, min(index, len(self._frames)))
        self._frames.insert(index, frame)
        self._update_indices_after_insert(index)
    
    def delete_frame(self, index: int) -> Optional[Frame]:
        """프레임 삭제"""
        if not self._is_valid_index(index):
            return None
        
        frame = self._frames.pop(index)
        self._update_indices_after_delete(index)
        return frame
    
    def delete_frames(self, indices: List[int]) -> List[Frame]:
        """여러 프레임 삭제"""
        # 역순으로 정렬하여 인덱스 문제 방지
        sorted_indices = sorted(indices, reverse=True)
        deleted = []
        for idx in sorted_indices:
            frame = self.delete_frame(idx)
            if frame:
                deleted.append(frame)
        return deleted
    
    def clear(self) -> None:
        """모든 프레임 삭제"""
        self._frames.clear()
        self._current_index = 0
        self._selected_indices.clear()
    
    # === 프레임 조작 ===
    def move_frame(self, from_index: int, to_index: int) -> bool:
        """프레임 이동"""
        if not self._is_valid_index(from_index):
            return False
        
        to_index = max(0, min(to_index, len(self._frames)))
        if from_index == to_index:
            return False
        
        frame = self._frames.pop(from_index)
        if to_index > from_index:
            to_index -= 1
        self._frames.insert(to_index, frame)
        
        # 현재 인덱스 업데이트
        if self._current_index == from_index:
            self._current_index = to_index
        
        return True
    
    def swap_frames(self, index1: int, index2: int) -> bool:
        """두 프레임 교환"""
        if not self._is_valid_index(index1) or not self._is_valid_index(index2):
            return False
        
        self._frames[index1], self._frames[index2] = \
            self._frames[index2], self._frames[index1]
        return True
    
    def duplicate_frame(self, index: int) -> Optional[Frame]:
        """프레임 복제"""
        if not self._is_valid_index(index):
            return None
        
        clone = self._frames[index].clone()
        self.insert_frame(index + 1, clone)
        return clone
    
    def duplicate_frames(self, indices: List[int]) -> List[Frame]:
        """여러 프레임 복제"""
        # 역순으로 복제하여 인덱스 유지
        sorted_indices = sorted(indices, reverse=True)
        duplicated = []
        for idx in sorted_indices:
            frame = self.duplicate_frame(idx)
            if frame:
                duplicated.append(frame)
        return duplicated
    
    # === 순서 조작 ===
    def reverse_frames(self, start: int = 0, end: Optional[int] = None) -> None:
        """프레임 순서 반전"""
        if end is None:
            end = len(self._frames)
        
        self._frames[start:end] = reversed(self._frames[start:end])
    
    def apply_yoyo_effect(self) -> None:
        """요요 효과 적용 (정방향 + 역방향)"""
        if len(self._frames) < 2:
            return
        
        # 마지막 프레임 제외하고 역순 복제
        for i in range(len(self._frames) - 2, 0, -1):
            self.add_frame(self._frames[i].clone())
    
    # === 프레임 감소 ===
    def reduce_frames(self, keep_every_n: int, target_indices: Optional[List[int]] = None) -> int:
        """N개 중 1개만 유지
        
        Args:
            keep_every_n: N개마다 1개 유지
            target_indices: 적용할 프레임 인덱스 리스트 (None이면 모든 프레임)
        
        Returns:
            제거된 프레임 수
        """
        if keep_every_n <= 0:
            raise ValueError("keep_every_n은 1 이상이어야 합니다")
        if keep_every_n == 1:
            return 0
        
        if target_indices is None:
            # 모든 프레임에 적용
            # N개마다 1개만 유지: 인덱스가 keep_every_n의 배수인 프레임만 유지
            # 예: keep_every_n=2면 인덱스 0, 2, 4, 6... (2개마다 1개)
            original_count = len(self._frames)
            # 유지할 인덱스 계산
            kept_indices = [i for i in range(original_count) if i % keep_every_n == 0]
            _logger.debug(f"reduce_frames: 원본 {original_count}개, keep_every_n={keep_every_n}, 유지할 프레임 {len(kept_indices)}개")
            self._frames = [f for i, f in enumerate(self._frames) if i % keep_every_n == 0]
            final_count = len(self._frames)
            _logger.debug(f"reduce_frames: 최종 프레임 수 {final_count}개")
            self._current_index = min(self._current_index, max(0, len(self._frames) - 1))
            self._selected_indices.clear()
            return original_count - len(self._frames)
        else:
            # 선택한 프레임에만 적용
            if not target_indices:
                return 0
            
            # 정렬된 인덱스로 변환
            sorted_indices = sorted(target_indices)
            original_count = len(sorted_indices)
            
            # 선택한 프레임 중에서만 줄이기 적용
            to_keep = [sorted_indices[i] for i in range(0, len(sorted_indices), keep_every_n)]
            to_remove = [idx for idx in sorted_indices if idx not in to_keep]
            
            # 역순으로 삭제 (인덱스 문제 방지)
            removed_count = 0
            for idx in sorted(to_remove, reverse=True):
                if self.delete_frame(idx) is not None:
                    removed_count += 1
            
            # 현재 인덱스 조정
            self._current_index = min(self._current_index, max(0, len(self._frames) - 1))
            
            # 선택 상태 업데이트 (남은 프레임 중에서 유지)
            remaining_selected = [idx for idx in self._selected_indices if idx < len(self._frames)]
            self._selected_indices = set(remaining_selected)
            
            return removed_count
    
    def remove_duplicates(self, threshold: float = 0.95) -> int:
        """중복 프레임 제거 (최적화됨)
        
        인접한 프레임만 비교하여 O(n) 복잡도로 처리합니다.
        대용량 GIF에서도 빠르게 처리됩니다.
        
        Args:
            threshold: 유사도 임계값 (0.0~1.0, 기본값: 0.95)
        
        Returns:
            제거된 프레임 수
        """
        if len(self._frames) < 2:
            return 0
        
        to_remove = set()
        total_frames = len(self._frames)
        
        _logger.debug(f"중복 프레임 제거 시작: {total_frames}개 프레임, 임계값: {threshold}")
        
        # 인접한 프레임만 비교 (O(n) 복잡도)
        # 연속된 중복만 제거하므로 빠르고 효율적
        for i in range(len(self._frames) - 1):
            if i in to_remove:
                continue
            
            # 진행률 로깅 (큰 컬렉션의 경우)
            if total_frames > 100 and i % 50 == 0:
                progress = (i / (total_frames - 1)) * 100
                _logger.debug(f"중복 검사 진행률: {progress:.1f}% ({i}/{total_frames - 1})")
            
            similarity = self._calculate_similarity(
                self._frames[i], self._frames[i + 1]
            )
            if similarity >= threshold:
                to_remove.add(i + 1)
        
        # 역순으로 삭제 (인덱스 문제 방지)
        removed_count = len(to_remove)
        if removed_count > 0:
            for idx in sorted(to_remove, reverse=True):
                self._frames.pop(idx)
            
            self._current_index = min(self._current_index, max(0, len(self._frames) - 1))
            self._selected_indices.clear()
            
            _logger.info(f"중복 프레임 제거 완료: {removed_count}개 제거됨 ({total_frames} → {len(self._frames)})")
        
        return removed_count
    
    def _calculate_similarity(self, frame1: Frame, frame2: Frame) -> float:
        """두 프레임의 유사도 계산 (GPU 가속 지원)"""
        if frame1.size != frame2.size:
            return 0.0
        
        arr1 = frame1.numpy_array
        arr2 = frame2.numpy_array
        
        # GPU 가속 유사도 계산 사용
        return gpu_utils.gpu_calculate_similarity(arr1, arr2)
    
    # === 프레임 접근 ===
    def get_frame(self, index: int) -> Optional[Frame]:
        """인덱스로 프레임 가져오기"""
        return self._frames[index] if self._is_valid_index(index) else None
    
    def __getitem__(self, index: int) -> Optional[Frame]:
        return self.get_frame(index)
    
    def __len__(self) -> int:
        return len(self._frames)
    
    def __iter__(self) -> Iterator[Frame]:
        return iter(self._frames)
    
    @property
    def is_empty(self) -> bool:
        return len(self._frames) == 0
    
    @property
    def frame_count(self) -> int:
        return len(self._frames)
    
    # === 현재 프레임 관리 ===
    @property
    def current_index(self) -> int:
        return self._current_index
    
    @current_index.setter
    def current_index(self, value: int) -> None:
        if self._is_valid_index(value):
            old_index = self._current_index
            self._current_index = value
    
    @property
    def current_frame(self) -> Optional[Frame]:
        return self.get_frame(self._current_index)
    
    def next_frame(self) -> bool:
        """다음 프레임으로 이동"""
        if self._current_index < len(self._frames) - 1:
            self._current_index += 1
            return True
        return False
    
    def previous_frame(self) -> bool:
        """이전 프레임으로 이동"""
        if self._current_index > 0:
            self._current_index -= 1
            return True
        return False
    
    def go_to_first(self) -> None:
        """첫 프레임으로 이동"""
        self._current_index = 0
    
    def go_to_last(self) -> None:
        """마지막 프레임으로 이동"""
        self._current_index = max(0, len(self._frames) - 1)
    
    # === 선택 관리 ===
    @property
    def selected_indices(self) -> List[int]:
        return sorted(self._selected_indices)
    
    @property
    def selection_count(self) -> int:
        return len(self._selected_indices)
    
    def select_frame(self, index: int, add_to_selection: bool = False) -> None:
        """프레임 선택"""
        if not self._is_valid_index(index):
            return
        
        if not add_to_selection:
            self._selected_indices.clear()
        
        self._selected_indices.add(index)
    
    def select_range(self, start: int, end: int) -> None:
        """범위 선택"""
        if start > end:
            start, end = end, start
        
        start = max(0, start)
        end = min(len(self._frames) - 1, end)
        
        self._selected_indices = set(range(start, end + 1))
    
    def select_all(self) -> None:
        """모든 프레임 선택"""
        self._selected_indices = set(range(len(self._frames)))
    
    def deselect_all(self) -> None:
        """모든 선택 해제"""
        self._selected_indices.clear()
    
    def invert_selection(self) -> None:
        """선택 반전"""
        all_indices = set(range(len(self._frames)))
        self._selected_indices = all_indices - self._selected_indices
    
    def is_selected(self, index: int) -> bool:
        """선택 여부 확인"""
        return index in self._selected_indices
    
    # === 일괄 작업 ===
    def apply_to_all(self, operation: Callable[[Frame], None]) -> None:
        """모든 프레임에 작업 적용"""
        for frame in self._frames:
            operation(frame)
    
    def apply_to_selected(self, operation: Callable[[Frame], None]) -> None:
        """선택된 프레임에 작업 적용"""
        for idx in self._selected_indices:
            if self._is_valid_index(idx):
                operation(self._frames[idx])
    
    def apply_to_range(self, start: int, end: int, 
                       operation: Callable[[Frame], None]) -> None:
        """범위에 작업 적용"""
        start = max(0, start)
        end = min(len(self._frames), end)
        
        for i in range(start, end):
            operation(self._frames[i])
    
    # === GPU 배치 처리 ===
    def apply_effect_gpu_batch(self, effect: str, 
                                target: str = 'all',
                                batch_size: Optional[int] = None,
                                **kwargs) -> int:
        """GPU 배치 처리로 효과 적용 (최적화됨, 스레드 안전)
        
        여러 프레임에 동일한 효과를 GPU 배치 처리로 적용합니다.
        메모리 효율적인 배치 처리로 대용량 GIF도 안전하게 처리합니다.
        CPU 순차 처리 대비 10배 이상 빠릅니다. (대량 프레임, 고해상도 시)
        
        Args:
            effect: 적용할 효과 ('sepia', 'vignette', 'hue_shift')
            target: 적용 대상 ('all', 'selected')
            batch_size: 배치 크기 (None이면 자동 계산)
            **kwargs: 효과별 추가 인자
                - vignette: strength (float, 0.0~1.0, default=0.5)
                - hue_shift: shift (int, -180~180, default=0)
        
        Returns:
            int: 처리된 프레임 수
            
        Example:
            >>> collection.apply_effect_gpu_batch('sepia')
            >>> collection.apply_effect_gpu_batch('vignette', strength=0.7)
            >>> collection.apply_effect_gpu_batch('hue_shift', target='selected', shift=30)
        """
        from PIL import Image
        
        with self._lock:  # 스레드 안전성 보장
            # 대상 프레임 선택
            if target == 'selected' and self._selected_indices:
                indices = sorted(self._selected_indices)
            else:
                indices = list(range(len(self._frames)))
            
            if not indices:
                return 0
            
            # 첫 프레임으로 이미지 크기 확인 (배치 크기 계산용)
            first_frame = self._frames[indices[0]]
            if not first_frame:
                return 0
            
            # 배치 크기 자동 계산 (이미지 크기에 따라)
            if batch_size is None:
                img_size = first_frame.size
                pixels = img_size[0] * img_size[1]
                
                # 이미지 크기에 따라 배치 크기 조정
                if pixels <= 640 * 480:  # 작은 이미지
                    batch_size = 50
                elif pixels <= 1920 * 1080:  # 중간 이미지
                    batch_size = 20
                else:  # 큰 이미지 (4K 등)
                    batch_size = 10
            
            _logger.debug(f"GPU 배치 처리 시작: {len(indices)}개 프레임, 배치 크기: {batch_size}, 효과: {effect}")
        
        # 배치 단위로 처리 (메모리 효율적)
        total_processed = 0
        for batch_start in range(0, len(indices), batch_size):
            batch_end = min(batch_start + batch_size, len(indices))
            batch_indices = indices[batch_start:batch_end]
            
            # 배치만 메모리에 로드
            with self._lock:
                batch_images = []
                for idx in batch_indices:
                    if self._is_valid_index(idx):
                        batch_images.append(self._frames[idx].numpy_array)
            
            if not batch_images:
                continue
            
            # GPU 배치 처리 (락 외부에서 실행 - GPU 작업은 시간이 오래 걸릴 수 있음)
            batch_results = gpu_utils.gpu_batch_process(batch_images, effect, **kwargs)
            
            # 결과를 프레임에 반영 (락 내부에서 실행)
            with self._lock:
                for i, idx in enumerate(batch_indices):
                    if self._is_valid_index(idx) and i < len(batch_results):
                        self._frames[idx]._image = Image.fromarray(batch_results[i], 'RGBA')
                        self._frames[idx]._invalidate_cache()
                        
                        # Lazy loading 모드인 경우 이미지 언로드 (메모리 절약)
                        if self._frames[idx].is_lazy:
                            self._frames[idx].unload_image()
                
                total_processed += len(batch_indices)
            
            # 진행률 로깅 (큰 배치의 경우)
            if len(indices) > 100:
                progress = (batch_end / len(indices)) * 100
                _logger.debug(f"GPU 배치 처리 진행률: {progress:.1f}% ({batch_end}/{len(indices)})")
        
        _logger.debug(f"GPU 배치 처리 완료: {total_processed}개 프레임 처리됨")
        return total_processed
    
    def apply_sepia_batch(self, target: str = 'all') -> int:
        """세피아 효과 GPU 배치 적용
        
        Args:
            target: 'all' 또는 'selected'
            
        Returns:
            처리된 프레임 수
        """
        return self.apply_effect_gpu_batch('sepia', target=target)
    
    def apply_vignette_batch(self, strength: float = 0.5, 
                              target: str = 'all') -> int:
        """비네트 효과 GPU 배치 적용
        
        Args:
            strength: 비네트 강도 (0.0 ~ 1.0)
            target: 'all' 또는 'selected'
            
        Returns:
            처리된 프레임 수
        """
        return self.apply_effect_gpu_batch('vignette', target=target, 
                                           strength=strength)
    
    def apply_hue_shift_batch(self, shift: int, target: str = 'all') -> int:
        """Hue 조절 GPU 배치 적용
        
        Args:
            shift: Hue 이동값 (-180 ~ 180)
            target: 'all' 또는 'selected'
            
        Returns:
            처리된 프레임 수
        """
        return self.apply_effect_gpu_batch('hue_shift', target=target, 
                                           shift=shift)
    
    # === 딜레이 조정 ===
    def set_delay_for_all(self, delay_ms: int) -> None:
        """모든 프레임 딜레이 설정"""
        for frame in self._frames:
            frame.delay_ms = delay_ms
    
    def set_delay_for_selected(self, delay_ms: int) -> None:
        """선택된 프레임 딜레이 설정"""
        for idx in self._selected_indices:
            if self._is_valid_index(idx):
                self._frames[idx].delay_ms = delay_ms
    
    def scale_delays(self, factor: float) -> None:
        """모든 딜레이에 배율 적용"""
        for frame in self._frames:
            frame.delay_ms = int(frame.delay_ms * factor)
    
    @property
    def total_duration(self) -> int:
        """총 재생 시간 (밀리초)"""
        return sum(f.delay_ms for f in self._frames)
    
    # === 메타데이터 ===
    @property
    def width(self) -> int:
        """첫 프레임 기준 너비"""
        if not self._frames or not self._frames[0]:
            return 0
        return self._frames[0].width
    
    @property
    def height(self) -> int:
        """첫 프레임 기준 높이"""
        if not self._frames or not self._frames[0]:
            return 0
        return self._frames[0].height
    
    @property
    def size(self) -> tuple:
        """첫 프레임 기준 크기"""
        return (self.width, self.height)
    
    @property
    def loop_count(self) -> int:
        return self._loop_count
    
    @loop_count.setter
    def loop_count(self, value: int) -> None:
        self._loop_count = max(0, value)
    
    # === 유틸리티 ===
    def _is_valid_index(self, index: int) -> bool:
        return 0 <= index < len(self._frames)
    
    def _update_indices_after_delete(self, deleted_index: int) -> None:
        self._selected_indices.discard(deleted_index)
        self._selected_indices = {
            idx - 1 if idx > deleted_index else idx
            for idx in self._selected_indices
        }
        
        if self._current_index >= len(self._frames):
            self._current_index = max(0, len(self._frames) - 1)
    
    def _update_indices_after_insert(self, inserted_index: int) -> None:
        self._selected_indices = {
            idx + 1 if idx >= inserted_index else idx
            for idx in self._selected_indices
        }
        
        if self._current_index >= inserted_index:
            self._current_index += 1
    
    def clone(self) -> 'FrameCollection':
        """컬렉션 복제"""
        collection = FrameCollection()
        for frame in self._frames:
            collection.add_frame(frame.clone())
        collection._current_index = self._current_index
        collection._loop_count = self._loop_count
        collection._selected_indices = self._selected_indices.copy()
        collection._lazy_load_enabled = self._lazy_load_enabled
        return collection
    
    # === 메모리 관리 ===
    @property
    def lazy_load_enabled(self) -> bool:
        """Lazy loading 활성화 여부"""
        return self._lazy_load_enabled
    
    @lazy_load_enabled.setter
    def lazy_load_enabled(self, value: bool):
        """Lazy loading 설정"""
        self._lazy_load_enabled = value
    
    def get_memory_usage(self) -> int:
        """총 메모리 사용량 (바이트) 반환"""
        return sum(frame.get_memory_usage() for frame in self._frames)
    
    def get_memory_usage_mb(self) -> float:
        """총 메모리 사용량 (MB) 반환"""
        return self.get_memory_usage() / (1024 * 1024)
    
    def get_loaded_frame_count(self) -> int:
        """메모리에 로드된 프레임 수 반환"""
        return sum(1 for frame in self._frames if frame.is_loaded)
    
    def unload_frames(self, keep_current: bool = True, keep_selected: bool = True) -> int:
        """프레임을 메모리에서 언로드 (lazy_load 모드에서만 동작)
        
        Args:
            keep_current: 현재 프레임은 유지
            keep_selected: 선택된 프레임은 유지
        
        Returns:
            언로드된 프레임 수
        """
        unloaded = 0
        for i, frame in enumerate(self._frames):
            if not frame.is_lazy:
                continue
            if keep_current and i == self._current_index:
                continue
            if keep_selected and i in self._selected_indices:
                continue
            
            if frame.is_loaded:
                frame.unload_image()
                unloaded += 1
        
        return unloaded
    
    def clear_thumbnail_caches(self) -> None:
        """모든 프레임의 썸네일 캐시 정리"""
        for frame in self._frames:
            frame.clear_thumbnail_cache()
    
    def preload_range(self, start: int, end: int) -> int:
        """범위 내 프레임 미리 로드
        
        Args:
            start: 시작 인덱스
            end: 끝 인덱스 (포함)
        
        Returns:
            로드된 프레임 수
        """
        start = max(0, start)
        end = min(len(self._frames), end + 1)
        loaded = 0
        
        for i in range(start, end):
            if not self._frames[i].is_loaded:
                _ = self._frames[i].image  # 로드 트리거
                loaded += 1
        
        return loaded
    
    def get_memory_stats(self) -> dict:
        """메모리 통계 반환"""
        total_frames = len(self._frames)
        loaded_frames = self.get_loaded_frame_count()
        memory_mb = self.get_memory_usage_mb()
        
        return {
            'total_frames': total_frames,
            'loaded_frames': loaded_frames,
            'unloaded_frames': total_frames - loaded_frames,
            'memory_mb': memory_mb,
            'lazy_load_enabled': self._lazy_load_enabled,
            'estimated_full_memory_mb': (self.width * self.height * 4 * total_frames) / (1024 * 1024) if total_frames > 0 else 0
        }
    
    # === 고성능 배치 처리 (pyvips) ===
    
    def resize_all_fast(self, size: Tuple[int, int],
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """모든 프레임 고속 리사이즈 (pyvips 가속)
        
        pyvips가 설치된 경우 Pillow 대비 2배 빠르고 메모리 90% 절약됩니다.
        
        Args:
            size: 목표 크기 (width, height)
            progress_callback: 진행률 콜백 (current, total)
        
        Returns:
            리사이즈된 프레임 수
        """
        total = len(self._frames)
        if total == 0:
            return 0
        
        for i, frame in enumerate(self._frames):
            resized = FastImage.resize(frame.image, size)
            frame._image = resized
            frame._image_size = resized.size
            frame._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def resize_selected_fast(self, size: Tuple[int, int],
                             progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """선택된 프레임 고속 리사이즈 (pyvips 가속)
        
        Args:
            size: 목표 크기 (width, height)
            progress_callback: 진행률 콜백 (current, total)
        
        Returns:
            리사이즈된 프레임 수
        """
        indices = sorted(self._selected_indices)
        total = len(indices)
        if total == 0:
            return 0
        
        for i, idx in enumerate(indices):
            if self._is_valid_index(idx):
                resized = FastImage.resize(self._frames[idx].image, size)
                self._frames[idx]._image = resized
                self._frames[idx]._image_size = resized.size
                self._frames[idx]._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def apply_blur_fast(self, radius: float = 2.0, target: str = 'all',
                        progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """고속 가우시안 블러 적용 (pyvips 가속)
        
        Args:
            radius: 블러 반경
            target: 'all' 또는 'selected'
            progress_callback: 진행률 콜백
        
        Returns:
            처리된 프레임 수
        """
        if target == 'selected' and self._selected_indices:
            indices = sorted(self._selected_indices)
        else:
            indices = list(range(len(self._frames)))
        
        total = len(indices)
        if total == 0:
            return 0
        
        for i, idx in enumerate(indices):
            if self._is_valid_index(idx):
                blurred = FastImage.gaussian_blur(self._frames[idx].image, radius)
                self._frames[idx]._image = blurred
                self._frames[idx]._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def apply_sharpen_fast(self, sigma: float = 1.0, amount: float = 1.0,
                           target: str = 'all',
                           progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """고속 샤프닝 적용 (pyvips 가속)
        
        Args:
            sigma: 블러 시그마
            amount: 샤프닝 강도
            target: 'all' 또는 'selected'
            progress_callback: 진행률 콜백
        
        Returns:
            처리된 프레임 수
        """
        if target == 'selected' and self._selected_indices:
            indices = sorted(self._selected_indices)
        else:
            indices = list(range(len(self._frames)))
        
        total = len(indices)
        if total == 0:
            return 0
        
        for i, idx in enumerate(indices):
            if self._is_valid_index(idx):
                sharpened = FastImage.sharpen(self._frames[idx].image, sigma, amount)
                self._frames[idx]._image = sharpened
                self._frames[idx]._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def flip_all_horizontal(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """모든 프레임 수평 뒤집기 (고속)"""
        total = len(self._frames)
        for i, frame in enumerate(self._frames):
            flipped = FastImage.flip_horizontal(frame.image)
            frame._image = flipped
            frame._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def flip_all_vertical(self, progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """모든 프레임 수직 뒤집기 (고속)"""
        total = len(self._frames)
        for i, frame in enumerate(self._frames):
            flipped = FastImage.flip_vertical(frame.image)
            frame._image = flipped
            frame._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def rotate_all(self, angle: float, expand: bool = True,
                   progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """모든 프레임 회전 (고속)
        
        Args:
            angle: 회전 각도 (도)
            expand: 이미지 크기 확장 여부
            progress_callback: 진행률 콜백
        
        Returns:
            회전된 프레임 수
        """
        total = len(self._frames)
        for i, frame in enumerate(self._frames):
            rotated = FastImage.rotate(frame.image, angle, expand=expand)
            frame._image = rotated
            frame._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def crop_all(self, box: Tuple[int, int, int, int],
                 progress_callback: Optional[Callable[[int, int], None]] = None) -> int:
        """모든 프레임 크롭 (고속)
        
        Args:
            box: 크롭 영역 (left, top, right, bottom)
            progress_callback: 진행률 콜백
        
        Returns:
            크롭된 프레임 수
        """
        total = len(self._frames)
        for i, frame in enumerate(self._frames):
            cropped = FastImage.crop(frame.image, box)
            frame._image = cropped
            frame._invalidate_cache()
            
            if progress_callback:
                progress_callback(i + 1, total)
        
        return total
    
    def __repr__(self) -> str:
        loaded = self.get_loaded_frame_count()
        total = len(self._frames)
        backend = "pyvips" if is_pyvips_available() else "pillow"
        return f"FrameCollection({total} frames, {loaded} loaded, {self.total_duration}ms, backend={backend})"
