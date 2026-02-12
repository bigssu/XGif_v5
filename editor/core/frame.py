"""
Frame - 단일 GIF 프레임 클래스
GPU 가속 지원 (CUDA 사용 가능 시)
메모리 최적화: Lazy Loading 및 weakref 지원
"""
from __future__ import annotations
from typing import Tuple, Optional, Dict, Any
from PIL import Image
import numpy as np
from copy import deepcopy
import weakref
import io
import os
import tempfile
import threading

from . import editor_gpu_utils as gpu_utils


# 전역 메모리 관리자
class FrameMemoryManager:
    """프레임 메모리 관리자
    
    현재는 Frame의 등록/해제만 담당하며, 죽은 weakref를 정리합니다.
    get_swap_path()는 스왑 파일 경로만 반환하며, 디스크 스왑 로직은 미구현입니다.
    """
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._init_manager()
        return cls._instance
    
    def _init_manager(self):
        import atexit
        self._loaded_frames: Dict[int, weakref.ref] = {}
        self._memory_limit_mb = 1024  # 1GB 기본 제한
        self._temp_dir = tempfile.mkdtemp(prefix="gifeditor_")
        self._swap_count = 0
        self._lock = threading.Lock()  # 스레드 안전성을 위한 락
        # 프로그램 종료 시 임시 디렉토리 자동 정리
        atexit.register(self.cleanup)
    
    def get_memory_limit_mb(self) -> int:
        """현재 메모리 제한 (MB) 반환"""
        with self._lock:
            return self._memory_limit_mb
    
    def set_memory_limit_mb(self, limit_mb: int) -> None:
        """메모리 제한 설정 (MB)
        
        Args:
            limit_mb: 메모리 제한 (MB)
        """
        with self._lock:
            self._memory_limit_mb = limit_mb
    
    def register_frame(self, frame_id: int, frame: 'Frame'):
        """프레임 등록 (스레드 안전)"""
        with self._lock:
            self._loaded_frames[frame_id] = weakref.ref(frame)
            self._check_memory()
    
    def unregister_frame(self, frame_id: int):
        """프레임 등록 해제 (스레드 안전)"""
        with self._lock:
            self._loaded_frames.pop(frame_id, None)
    
    def _check_memory(self):
        """죽은 weakref 정리 (락 내부에서 호출됨). 디스크 스왑은 미구현."""
        # 죽은 참조 정리
        dead_keys = [k for k, v in self._loaded_frames.items() if v() is None]
        for k in dead_keys:
            del self._loaded_frames[k]
    
    def get_swap_path(self, frame_id: int) -> str:
        """스왑 파일 경로 반환"""
        return os.path.join(self._temp_dir, f"frame_{frame_id}.png")
    
    def cleanup(self):
        """임시 파일 정리"""
        import shutil
        try:
            if os.path.exists(self._temp_dir):
                shutil.rmtree(self._temp_dir)
        except Exception:
            pass


def get_memory_manager() -> FrameMemoryManager:
    """전역 메모리 관리자 반환"""
    return FrameMemoryManager()


class Frame:
    """단일 GIF 프레임을 나타내는 클래스
    
    메모리 최적화 기능:
    - Lazy Loading: 이미지를 필요할 때만 메모리에 로드
    - 압축 저장: 메모리에 PNG 바이트로 압축 저장 (옵션)
    - 썸네일 캐싱: 크기별 썸네일 캐시
    """
    
    _next_id = 0  # 프레임 ID 생성용
    _id_lock = threading.Lock()  # 스레드 안전한 ID 생성
    
    def __init__(self, image: Image.Image, delay_ms: int = 100,
                 lazy_load: bool = True, source_path: Optional[str] = None):
        """
        Args:
            image: PIL Image 객체 (RGBA 모드로 변환됨)
            delay_ms: 프레임 표시 시간 (밀리초)
            lazy_load: True면 이미지를 압축하여 저장 (메모리 절약)
            source_path: 원본 파일 경로 (lazy loading 시 사용)
        """
        # 프레임 ID 할당 (스레드 안전)
        with Frame._id_lock:
            self._id = Frame._next_id
            Frame._next_id += 1
        
        # 지연 로딩 설정
        self._lazy_load = lazy_load
        self._source_path = source_path
        
        # 이미지 저장 (모드에 따라 다르게)
        self._image: Optional[Image.Image] = None
        self._image_bytes: Optional[bytes] = None
        self._image_size: Tuple[int, int] = (0, 0)
        
        if image is not None:
            # RGBA 모드로 변환
            if image.mode != 'RGBA':
                image = image.convert('RGBA')
            
            self._image_size = image.size
            
            if lazy_load:
                # 압축하여 바이트로 저장
                self._compress_image(image)
            else:
                self._image = image.copy()
        
        self._delay_ms = max(10, delay_ms)  # 최소 10ms
        self._thumbnail_cache: Dict[int, Image.Image] = {}
        
        # 메모리 관리자에 등록
        get_memory_manager().register_frame(self._id, self)
    
    def _compress_image(self, image: Image.Image):
        """이미지를 PNG 바이트로 압축"""
        buffer = io.BytesIO()
        image.save(buffer, format='PNG', compress_level=1)  # 빠른 압축
        self._image_bytes = buffer.getvalue()
        self._image = None
    
    def _decompress_image(self) -> Image.Image:
        """압축된 이미지 복원"""
        if self._image_bytes is None:
            raise ValueError("압축된 이미지 데이터가 없습니다")
        buffer = io.BytesIO(self._image_bytes)
        return Image.open(buffer).convert('RGBA')
    
    def _load_from_source(self) -> Image.Image:
        """원본 파일에서 이미지 로드"""
        if self._source_path is None:
            raise ValueError("원본 파일 경로가 없습니다")
        return Image.open(self._source_path).convert('RGBA')
    
    def _ensure_image_loaded(self):
        """이미지가 메모리에 로드되어 있는지 확인하고 필요시 로드"""
        if self._image is not None:
            return
        
        if self._image_bytes is not None:
            self._image = self._decompress_image()
        elif self._source_path is not None:
            self._image = self._load_from_source()
        else:
            raise ValueError("이미지를 로드할 수 없습니다")
    
    def unload_image(self):
        """이미지를 메모리에서 해제 (lazy_load 모드에서만)"""
        if self._lazy_load and self._image is not None:
            if self._image_bytes is None:
                self._compress_image(self._image)
            self._image = None
    
    def get_memory_usage(self) -> int:
        """현재 메모리 사용량 (바이트) 반환"""
        usage = 0
        if self._image is not None:
            usage += self._image_size[0] * self._image_size[1] * 4
        if self._image_bytes is not None:
            usage += len(self._image_bytes)
        for thumb in self._thumbnail_cache.values():
            usage += thumb.size[0] * thumb.size[1] * 4
        return usage
    
    @classmethod
    def create_empty(cls, width: int, height: int, 
                     color: Tuple[int, int, int, int] = (255, 255, 255, 255),
                     delay_ms: int = 100) -> 'Frame':
        """빈 프레임 생성"""
        image = Image.new('RGBA', (width, height), color)
        return cls(image, delay_ms)
    
    @classmethod
    def from_file(cls, path: str, delay_ms: int = 100, 
                  lazy_load: bool = False) -> 'Frame':
        """파일에서 프레임 로드
        
        Args:
            path: 이미지 파일 경로
            delay_ms: 딜레이 (밀리초)
            lazy_load: True면 파일 경로만 저장하고 필요 시 로드
        """
        if lazy_load:
            # 크기만 먼저 확인
            with Image.open(path) as img:
                size = img.size
            frame = cls.__new__(cls)
            # 스레드 안전한 ID 할당
            with Frame._id_lock:
                frame._id = Frame._next_id
                Frame._next_id += 1
            frame._lazy_load = True
            frame._source_path = path
            frame._image = None
            frame._image_bytes = None
            frame._image_size = size
            frame._delay_ms = max(10, delay_ms)
            frame._thumbnail_cache = {}
            get_memory_manager().register_frame(frame._id, frame)
            return frame
        else:
            # 파일 핸들 누수 방지: with 문 사용
            with Image.open(path) as img:
                image = img.copy()
            return cls(image, delay_ms, source_path=path)
    
    # === 속성 ===
    @property
    def width(self) -> int:
        return self._image_size[0]
    
    @property
    def height(self) -> int:
        return self._image_size[1]
    
    @property
    def size(self) -> Tuple[int, int]:
        return self._image_size
    
    @property
    def delay_ms(self) -> int:
        return self._delay_ms
    
    @delay_ms.setter
    def delay_ms(self, value: int):
        self._delay_ms = max(10, value)
    
    @property
    def image(self) -> Image.Image:
        """PIL Image 객체 반환 (lazy loading 시 자동 로드)"""
        try:
            self._ensure_image_loaded()
            if self._image is None:
                raise ValueError("이미지를 로드할 수 없습니다")
            return self._image
        except Exception:
            # 이미지 로드 실패 시 빈 이미지 반환 (크래시 방지)
            from PIL import Image as PILImage
            return PILImage.new('RGBA', (self._image_size[0] if self._image_size[0] > 0 else 100, 
                                         self._image_size[1] if self._image_size[1] > 0 else 100), 
                               (255, 255, 255, 0))
    
    @property
    def numpy_array(self) -> np.ndarray:
        """numpy 배열로 반환 (H, W, 4) RGBA"""
        try:
            self._ensure_image_loaded()
            return np.array(self._image)
        except Exception:
            # 이미지 로드 실패 시 빈 배열 반환 (배치 처리 크래시 방지)
            w = self._image_size[0] if self._image_size[0] > 0 else 100
            h = self._image_size[1] if self._image_size[1] > 0 else 100
            return np.zeros((h, w, 4), dtype=np.uint8)
    
    @property
    def is_loaded(self) -> bool:
        """이미지가 메모리에 로드되어 있는지 확인"""
        return self._image is not None
    
    @property
    def is_lazy(self) -> bool:
        """Lazy loading 모드인지 확인"""
        return self._lazy_load
    
    # === 변환 연산 ===
    def resize(self, width: int, height: int, 
               keep_aspect: bool = False,
               resample: int = Image.Resampling.LANCZOS) -> None:
        """크기 조정"""
        self._ensure_image_loaded()
        
        if keep_aspect:
            if self.height == 0:
                raise ValueError("이미지 높이가 0일 수 없습니다.")
            if height == 0:
                raise ValueError("목표 높이가 0일 수 없습니다.")
            aspect = self.width / self.height
            new_aspect = width / height
            if new_aspect > aspect:
                width = int(height * aspect)
            else:
                height = int(width / aspect)
        
        self._image = self._image.resize((width, height), resample)
        self._image_size = self._image.size
        self._invalidate_cache()
    
    def crop(self, x: int, y: int, width: int, height: int) -> None:
        """이미지 자르기"""
        self._ensure_image_loaded()
        
        # 경계 확인
        x = max(0, x)
        y = max(0, y)
        right = min(x + width, self.width)
        bottom = min(y + height, self.height)
        
        self._image = self._image.crop((x, y, right, bottom))
        self._image_size = self._image.size
        self._invalidate_cache()
    
    def rotate(self, angle: int) -> None:
        """각도 회전 (90, 180, 270)"""
        self._ensure_image_loaded()
        
        if angle == 90:
            self._image = self._image.rotate(-90, expand=True)
        elif angle == 180:
            self._image = self._image.rotate(180, expand=True)
        elif angle == 270:
            self._image = self._image.rotate(90, expand=True)
        self._image_size = self._image.size
        self._invalidate_cache()
    
    def rotate_90_cw(self) -> None:
        """시계 방향 90도 회전"""
        self._ensure_image_loaded()
        self._image = self._image.rotate(-90, expand=True)
        self._image_size = self._image.size
        self._invalidate_cache()
    
    def rotate_90_ccw(self) -> None:
        """반시계 방향 90도 회전"""
        self._ensure_image_loaded()
        self._image = self._image.rotate(90, expand=True)
        self._image_size = self._image.size
        self._invalidate_cache()
    
    def rotate_180(self) -> None:
        """180도 회전"""
        self._ensure_image_loaded()
        self._image = self._image.rotate(180)
        self._invalidate_cache()
    
    def flip_horizontal(self) -> None:
        """수평 뒤집기"""
        self._ensure_image_loaded()
        self._image = self._image.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
        self._invalidate_cache()
    
    def flip_vertical(self) -> None:
        """수직 뒤집기"""
        self._ensure_image_loaded()
        self._image = self._image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
        self._invalidate_cache()
    
    # === 색상 조정 ===
    def adjust_brightness(self, factor: float) -> None:
        """밝기 조정 (factor: 0.0 ~ 2.0, 1.0 = 원본)"""
        self._ensure_image_loaded()
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Brightness(self._image)
        self._image = enhancer.enhance(factor)
        self._invalidate_cache()
    
    def adjust_contrast(self, factor: float) -> None:
        """대비 조정 (factor: 0.0 ~ 2.0, 1.0 = 원본)"""
        self._ensure_image_loaded()
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(self._image)
        self._image = enhancer.enhance(factor)
        self._invalidate_cache()
    
    def adjust_saturation(self, factor: float) -> None:
        """채도 조정 (factor: 0.0 ~ 2.0, 1.0 = 원본)"""
        self._ensure_image_loaded()
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Color(self._image)
        self._image = enhancer.enhance(factor)
        self._invalidate_cache()
    
    def grayscale(self) -> None:
        """흑백 변환"""
        self._ensure_image_loaded()
        gray = self._image.convert('L')
        self._image = gray.convert('RGBA')
        self._invalidate_cache()
    
    def invert(self) -> None:
        """색상 반전"""
        self._ensure_image_loaded()
        from PIL import ImageOps
        # Alpha 채널 분리
        r, g, b, a = self._image.split()
        rgb = Image.merge('RGB', (r, g, b))
        inverted = ImageOps.invert(rgb)
        r, g, b = inverted.split()
        self._image = Image.merge('RGBA', (r, g, b, a))
        self._invalidate_cache()
    
    def apply_sepia(self) -> None:
        """세피아 효과 (GPU 가속 지원)"""
        arr = self.numpy_array  # 자동 로드
        result = gpu_utils.gpu_sepia(arr)
        self._image = Image.fromarray(result, 'RGBA')
        self._invalidate_cache()
    
    def apply_vignette(self, strength: float = 0.5) -> None:
        """비네트 효과 (GPU 가속 지원)
        
        Args:
            strength: 비네트 강도 (0.0 ~ 1.0)
        """
        arr = self.numpy_array  # 자동 로드
        result = gpu_utils.gpu_vignette(arr, strength)
        self._image = Image.fromarray(result, 'RGBA')
        self._invalidate_cache()
    
    def adjust_hue(self, shift: int) -> None:
        """색조 조절 (GPU 가속 지원)
        
        Args:
            shift: Hue 이동값 (-180 ~ 180)
        """
        arr = self.numpy_array  # 자동 로드
        result = gpu_utils.gpu_hue_shift(arr, shift)
        self._image = Image.fromarray(result, 'RGBA')
        self._invalidate_cache()
    
    # === 필터/효과 ===
    def apply_blur(self, radius: int = 2) -> None:
        """블러 효과"""
        self._ensure_image_loaded()
        from PIL import ImageFilter
        self._image = self._image.filter(ImageFilter.GaussianBlur(radius))
        self._invalidate_cache()
    
    def apply_sharpen(self, factor: float = 1.5) -> None:
        """샤프닝 효과"""
        self._ensure_image_loaded()
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Sharpness(self._image)
        self._image = enhancer.enhance(factor)
        self._invalidate_cache()
    
    def apply_pixelate(self, block_size: int = 10, 
                       region: Optional[Tuple[int, int, int, int]] = None) -> None:
        """픽셀화 (모자이크) 효과"""
        self._ensure_image_loaded()
        
        if block_size <= 0:
            raise ValueError("block_size는 1 이상이어야 합니다.")
        
        if region:
            x, y, w, h = region
            cropped = self._image.crop((x, y, x + w, y + h))
            small = cropped.resize((max(1, w // block_size), max(1, h // block_size)), 
                                   Image.Resampling.NEAREST)
            pixelated = small.resize((w, h), Image.Resampling.NEAREST)
            self._image.paste(pixelated, (x, y))
        else:
            w, h = self.size
            small = self._image.resize((max(1, w // block_size), max(1, h // block_size)), 
                                       Image.Resampling.NEAREST)
            self._image = small.resize((w, h), Image.Resampling.NEAREST)
        
        self._invalidate_cache()
    
    # === 펜슬 그리기 ===
    def draw_lines(self, paths: list) -> None:
        """선 그리기
        
        Args:
            paths: 경로 목록 [(점들, RGBA튜플, 두께), ...]
                   점들: [(x1, y1), (x2, y2), ...]
                   RGBA튜플: (R, G, B, A)
                   두께: int
        """
        self._ensure_image_loaded()
        from PIL import ImageDraw
        
        draw = ImageDraw.Draw(self._image)
        
        for points, rgba, width in paths:
            if len(points) < 2:
                continue
            
            # 연속된 점들 사이에 선 그리기
            for i in range(len(points) - 1):
                x1, y1 = points[i]
                x2, y2 = points[i + 1]
                
                # 선 그리기 (joint='curve' 옵션 미지원으로 직선으로 연결)
                draw.line([(x1, y1), (x2, y2)], fill=rgba, width=width)
                
                # 선 끝을 둥글게 처리 (원 그리기)
                r = width // 2
                if r > 0:
                    draw.ellipse([x1 - r, y1 - r, x1 + r, y1 + r], fill=rgba)
                    draw.ellipse([x2 - r, y2 - r, x2 + r, y2 + r], fill=rgba)
        
        self._invalidate_cache()
    
    # === 썸네일 ===
    def get_thumbnail(self, max_size: int = 80) -> Image.Image:
        """썸네일 반환 (크기별 캐싱)
        
        Args:
            max_size: 썸네일 최대 크기
        
        Returns:
            썸네일 이미지
        """
        if max_size not in self._thumbnail_cache:
            self._ensure_image_loaded()
            thumb = self._image.copy()
            thumb.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            self._thumbnail_cache[max_size] = thumb
        return self._thumbnail_cache[max_size]
    
    def _invalidate_cache(self) -> None:
        """모든 캐시 무효화 (썸네일, 압축 이미지 등)"""
        self._thumbnail_cache.clear()
        self._image_bytes = None  # 압축 캐시도 무효화
    
    def clear_thumbnail_cache(self) -> None:
        """썸네일 캐시만 정리 (메모리 절약)"""
        self._thumbnail_cache.clear()
    
    # === 복제 ===
    def clone(self) -> 'Frame':
        """프레임 복제"""
        self._ensure_image_loaded()
        return Frame(self._image.copy(), self._delay_ms, lazy_load=self._lazy_load)
    
    def __copy__(self) -> 'Frame':
        return self.clone()
    
    def __deepcopy__(self, memo) -> 'Frame':
        return self.clone()
    
    # === 저장 ===
    def save(self, path: str, format: Optional[str] = None) -> None:
        """이미지 파일로 저장"""
        self._ensure_image_loaded()
        self._image.save(path, format=format)
    
    def __repr__(self) -> str:
        loaded = "loaded" if self.is_loaded else "unloaded"
        return f"Frame({self.width}x{self.height}, {self.delay_ms}ms, {loaded})"
    
    def __del__(self):
        """소멸자: 메모리 관리자에서 등록 해제"""
        try:
            get_memory_manager().unregister_frame(self._id)
        except Exception:
            pass
