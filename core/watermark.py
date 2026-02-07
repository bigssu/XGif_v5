"""
워터마크 모듈
텍스트 또는 이미지 워터마크를 프레임에 적용
"""

import os
import logging
from typing import Optional
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from .utils import calculate_overlay_position, apply_alpha_blend, load_system_font

logger = logging.getLogger(__name__)


class Watermark:
    """워터마크 처리"""
    
    def __init__(self):
        self.enabled = False
        self.type = 'text'  # 'text' or 'image'
        self.text = "GifRecoder2"
        self.image_path: Optional[str] = None
        self.position = 'bottom-right'  # 'top-left', 'top-right', 'bottom-left', 'bottom-right', 'center'
        self.opacity = 0.7  # 0.0 ~ 1.0
        self.font_size = 24
        self.text_color = (255, 255, 255)  # RGB
        self.bg_color: Optional[tuple] = None  # None이면 배경 없음
        
        # 캐시
        self._cached_text_image: Optional[np.ndarray] = None
        self._cached_image: Optional[np.ndarray] = None
    
    def set_enabled(self, enabled: bool):
        """워터마크 활성화/비활성화"""
        self.enabled = enabled
    
    def set_type(self, wm_type: str):
        """워터마크 타입 설정 ('text' or 'image')"""
        self.type = wm_type
        self._cached_text_image = None
        self._cached_image = None
    
    def set_text(self, text: str):
        """텍스트 워터마크 설정"""
        if self.text != text:
            self.text = text
            self._cached_text_image = None
    
    def set_image_path(self, path: str):
        """이미지 워터마크 경로 설정"""
        if self.image_path != path:
            self.image_path = path
            self._cached_image = None
    
    def set_position(self, position: str):
        """위치 설정"""
        self.position = position
    
    def set_opacity(self, opacity: float):
        """투명도 설정 (0.0 ~ 1.0)"""
        self.opacity = max(0.0, min(1.0, opacity))
    
    def set_font_size(self, size: int):
        """폰트 크기 설정"""
        if self.font_size != size:
            self.font_size = size
            self._cached_text_image = None
    
    def set_text_color(self, r: int, g: int, b: int):
        """텍스트 색상 설정"""
        if self.text_color != (r, g, b):
            self.text_color = (r, g, b)
            self._cached_text_image = None
    
    def set_bg_color(self, r: Optional[int], g: Optional[int], b: Optional[int]):
        """배경 색상 설정 (None이면 배경 없음)"""
        bg = (r, g, b) if r is not None and g is not None and b is not None else None
        if self.bg_color != bg:
            self.bg_color = bg
            self._cached_text_image = None
    
    def _create_text_image(self) -> Optional[np.ndarray]:
        """텍스트 이미지 생성 (캐싱)"""
        if self._cached_text_image is not None:
            return self._cached_text_image
        
        try:
            # 공통 유틸리티로 폰트 로드
            font = load_system_font(
                self.font_size,
                preferred_fonts=["C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/calibri.ttf"]
            )
            
            # 텍스트 크기 측정
            temp_img = Image.new('RGB', (1, 1))
            draw = ImageDraw.Draw(temp_img)
            bbox = draw.textbbox((0, 0), self.text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            
            # 패딩 추가
            padding = 10
            img_width = text_width + padding * 2
            img_height = text_height + padding * 2
            
            # 이미지 생성
            if self.bg_color:
                img = Image.new('RGB', (img_width, img_height), self.bg_color)
            else:
                img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
            
            draw = ImageDraw.Draw(img)
            draw.text((padding, padding), self.text, font=font, fill=self.text_color)
            
            # NumPy 배열로 변환
            img_array = np.array(img)
            self._cached_text_image = img_array
            return img_array
            
        except (OSError, ValueError) as e:
            logger.error(f"텍스트 워터마크 생성 실패: {e}")
            return None
    
    def _load_image(self) -> Optional[np.ndarray]:
        """이미지 로드 (캐싱)"""
        if not self.image_path:
            return None
        
        # 파일 존재 및 읽기 권한 확인
        if not os.path.exists(self.image_path):
            logger.warning(f"Watermark image not found: {self.image_path}")
            return None
        
        if not os.path.isfile(self.image_path):
            logger.warning(f"Watermark path is not a file: {self.image_path}")
            return None
        
        # 파일 크기 검증 (너무 크면 메모리 문제 발생 가능)
        try:
            file_size = os.path.getsize(self.image_path)
            if file_size > 10 * 1024 * 1024:  # 10MB 초과
                logger.error(f"Watermark image too large: {file_size} bytes")
                return None
        except OSError as e:
            logger.error(f"Cannot check file size: {e}")
            return None
        
        if self._cached_image is not None:
            return self._cached_image
        
        try:
            img = Image.open(self.image_path)
            # RGBA로 변환
            if img.mode != 'RGBA':
                img = img.convert('RGBA')
            
            img_array = np.array(img)
            self._cached_image = img_array
            return img_array
        except (IOError, OSError, ValueError) as e:
            logger.error(f"이미지 워터마크 로드 실패: {e}")
            return None
    
    def apply_watermark(self, frame: np.ndarray) -> np.ndarray:
        """프레임에 워터마크 적용"""
        # 안전 검증
        if not self.enabled:
            return frame
        
        if frame is None or not isinstance(frame, np.ndarray) or frame.size == 0:
            return frame
        
        try:
            h, w = frame.shape[:2]
            
            # 워터마크 이미지 가져오기
            if self.type == 'text':
                watermark_img = self._create_text_image()
            else:  # image
                watermark_img = self._load_image()
            
            if watermark_img is None:
                return frame
            
            wm_h, wm_w = watermark_img.shape[:2]
            
            # 공통 유틸리티로 위치 계산 및 알파 블렌딩
            x, y = calculate_overlay_position(w, h, wm_w, wm_h, self.position, margin=10)
            frame = apply_alpha_blend(frame, watermark_img, x, y, self.opacity)
            
            return frame
        except (ValueError, IndexError) as e:
            logger.error(f"워터마크 적용 실패: {e}")
            return frame
