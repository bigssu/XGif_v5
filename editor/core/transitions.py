"""
Transitions - 프레임 간 전환 효과
페이드, 슬라이드, 디졸브, 와이프 등의 전환 효과 제공
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from enum import Enum
from PIL import Image
import numpy as np

from .frame import Frame
from .frame_collection import FrameCollection


class TransitionType(Enum):
    """전환 효과 타입"""
    FADE = "fade"                   # 페이드 인/아웃
    DISSOLVE = "dissolve"           # 디졸브 (크로스페이드)
    SLIDE_LEFT = "slide_left"       # 왼쪽으로 슬라이드
    SLIDE_RIGHT = "slide_right"     # 오른쪽으로 슬라이드
    SLIDE_UP = "slide_up"           # 위로 슬라이드
    SLIDE_DOWN = "slide_down"       # 아래로 슬라이드
    WIPE_LEFT = "wipe_left"         # 왼쪽으로 와이프
    WIPE_RIGHT = "wipe_right"       # 오른쪽으로 와이프
    WIPE_UP = "wipe_up"             # 위로 와이프
    WIPE_DOWN = "wipe_down"         # 아래로 와이프
    ZOOM_IN = "zoom_in"             # 줌 인
    ZOOM_OUT = "zoom_out"           # 줌 아웃
    IRIS_IN = "iris_in"             # 아이리스 인 (원형 닫힘)
    IRIS_OUT = "iris_out"           # 아이리스 아웃 (원형 열림)


class TransitionEffect:
    """전환 효과 생성 클래스"""
    
    @staticmethod
    def create_transition(
        frame1: Frame,
        frame2: Frame,
        transition_type: TransitionType,
        num_frames: int = 5,
        delay_ms: int = 50
    ) -> List[Frame]:
        """두 프레임 사이의 전환 효과 프레임들을 생성
        
        Args:
            frame1: 시작 프레임
            frame2: 끝 프레임
            transition_type: 전환 효과 타입
            num_frames: 전환 프레임 수 (기본 5)
            delay_ms: 각 프레임의 딜레이 (기본 50ms)
        
        Returns:
            List[Frame]: 전환 효과 프레임 리스트
        """
        # 크기 맞추기 (두 프레임이 다른 크기일 경우)
        img1 = frame1.image.copy()
        img2 = frame2.image.copy()
        
        if img1.size != img2.size:
            # 더 큰 크기에 맞춤
            max_w = max(img1.width, img2.width)
            max_h = max(img1.height, img2.height)
            
            if img1.size != (max_w, max_h):
                img1 = img1.resize((max_w, max_h), Image.Resampling.LANCZOS)
            if img2.size != (max_w, max_h):
                img2 = img2.resize((max_w, max_h), Image.Resampling.LANCZOS)
        
        # 전환 효과별 프레임 생성
        transition_map = {
            TransitionType.FADE: TransitionEffect._fade,
            TransitionType.DISSOLVE: TransitionEffect._dissolve,
            TransitionType.SLIDE_LEFT: lambda i1, i2, n: TransitionEffect._slide(i1, i2, n, 'left'),
            TransitionType.SLIDE_RIGHT: lambda i1, i2, n: TransitionEffect._slide(i1, i2, n, 'right'),
            TransitionType.SLIDE_UP: lambda i1, i2, n: TransitionEffect._slide(i1, i2, n, 'up'),
            TransitionType.SLIDE_DOWN: lambda i1, i2, n: TransitionEffect._slide(i1, i2, n, 'down'),
            TransitionType.WIPE_LEFT: lambda i1, i2, n: TransitionEffect._wipe(i1, i2, n, 'left'),
            TransitionType.WIPE_RIGHT: lambda i1, i2, n: TransitionEffect._wipe(i1, i2, n, 'right'),
            TransitionType.WIPE_UP: lambda i1, i2, n: TransitionEffect._wipe(i1, i2, n, 'up'),
            TransitionType.WIPE_DOWN: lambda i1, i2, n: TransitionEffect._wipe(i1, i2, n, 'down'),
            TransitionType.ZOOM_IN: TransitionEffect._zoom_in,
            TransitionType.ZOOM_OUT: TransitionEffect._zoom_out,
            TransitionType.IRIS_IN: TransitionEffect._iris_in,
            TransitionType.IRIS_OUT: TransitionEffect._iris_out,
        }
        
        func = transition_map.get(transition_type, TransitionEffect._dissolve)
        images = func(img1, img2, num_frames)
        
        return [Frame(img, delay_ms) for img in images]
    
    @staticmethod
    def _fade(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """페이드 효과 (밝기 감소 후 증가)"""
        results = []
        
        # 최소 2 프레임 보장
        if num_frames < 2:
            num_frames = 2
        
        half_frames = max(1, num_frames // 2)
        second_half = max(1, num_frames - half_frames)
        
        # 첫 번째 이미지에서 검정으로 페이드 아웃
        for i in range(half_frames):
            progress = i / half_frames
            # 검정 이미지와 블렌드
            black = Image.new('RGBA', img1.size, (0, 0, 0, 255))
            blended = Image.blend(img1, black, progress)
            results.append(blended)
        
        # 검정에서 두 번째 이미지로 페이드 인
        for i in range(second_half):
            progress = i / second_half
            black = Image.new('RGBA', img2.size, (0, 0, 0, 255))
            blended = Image.blend(black, img2, progress)
            results.append(blended)
        
        return results
    
    @staticmethod
    def _dissolve(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """디졸브 (크로스페이드) 효과"""
        results = []
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            blended = Image.blend(img1, img2, progress)
            results.append(blended)
        
        return results
    
    @staticmethod
    def _slide(img1: Image.Image, img2: Image.Image, num_frames: int, 
               direction: str) -> List[Image.Image]:
        """슬라이드 효과"""
        results = []
        w, h = img1.size
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            
            # 새 캔버스
            canvas = Image.new('RGBA', (w, h), (0, 0, 0, 0))
            
            if direction == 'left':
                offset1 = int(-w * progress)
                offset2 = int(w * (1 - progress))
                canvas.paste(img1, (offset1, 0))
                canvas.paste(img2, (offset2, 0))
            elif direction == 'right':
                offset1 = int(w * progress)
                offset2 = int(-w * (1 - progress))
                canvas.paste(img1, (offset1, 0))
                canvas.paste(img2, (offset2, 0))
            elif direction == 'up':
                offset1 = int(-h * progress)
                offset2 = int(h * (1 - progress))
                canvas.paste(img1, (0, offset1))
                canvas.paste(img2, (0, offset2))
            elif direction == 'down':
                offset1 = int(h * progress)
                offset2 = int(-h * (1 - progress))
                canvas.paste(img1, (0, offset1))
                canvas.paste(img2, (0, offset2))
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def _wipe(img1: Image.Image, img2: Image.Image, num_frames: int,
              direction: str) -> List[Image.Image]:
        """와이프 효과"""
        results = []
        w, h = img1.size
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            
            # 기본은 img1, 부분적으로 img2로 덮음
            canvas = img1.copy()
            
            if direction == 'left':
                crop_w = int(w * progress)
                if crop_w > 0:
                    region = img2.crop((0, 0, crop_w, h))
                    canvas.paste(region, (0, 0))
            elif direction == 'right':
                crop_w = int(w * progress)
                if crop_w > 0:
                    region = img2.crop((w - crop_w, 0, w, h))
                    canvas.paste(region, (w - crop_w, 0))
            elif direction == 'up':
                crop_h = int(h * progress)
                if crop_h > 0:
                    region = img2.crop((0, 0, w, crop_h))
                    canvas.paste(region, (0, 0))
            elif direction == 'down':
                crop_h = int(h * progress)
                if crop_h > 0:
                    region = img2.crop((0, h - crop_h, w, h))
                    canvas.paste(region, (0, h - crop_h))
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def _zoom_in(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """줌 인 효과 (img2가 작은 상태에서 커짐)"""
        results = []
        w, h = img1.size
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            
            # img2를 작은 크기에서 원래 크기로 확대
            scale = 0.3 + (0.7 * progress)  # 30% → 100%
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            scaled_img2 = img2.resize((new_w, new_h), Image.Resampling.LANCZOS)
            
            # 중앙에 배치
            canvas = img1.copy()
            alpha = int(255 * progress)
            
            # 알파 블렌딩을 위한 처리
            x = (w - new_w) // 2
            y = (h - new_h) // 2
            
            # 마스크 생성
            mask = Image.new('L', (new_w, new_h), alpha)
            canvas.paste(scaled_img2, (x, y), mask)
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def _zoom_out(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """줌 아웃 효과 (img1이 작아지면서 img2가 나타남)"""
        results = []
        w, h = img1.size
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            
            # img1을 원래 크기에서 작은 크기로 축소
            scale = 1.0 - (0.7 * progress)  # 100% → 30%
            new_w = int(w * scale)
            new_h = int(h * scale)
            
            canvas = img2.copy()
            
            if new_w > 0 and new_h > 0:
                scaled_img1 = img1.resize((new_w, new_h), Image.Resampling.LANCZOS)
                
                # 중앙에 배치
                x = (w - new_w) // 2
                y = (h - new_h) // 2
                
                alpha = int(255 * (1 - progress))
                mask = Image.new('L', (new_w, new_h), alpha)
                canvas.paste(scaled_img1, (x, y), mask)
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def _iris_in(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """아이리스 인 효과 (원형으로 닫힘)"""
        results = []
        w, h = img1.size
        center_x, center_y = w // 2, h // 2
        max_radius = int(np.sqrt(center_x**2 + center_y**2))
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            radius = int(max_radius * (1 - progress))
            
            # 원형 마스크 생성
            mask = Image.new('L', (w, h), 0)
            mask_array = np.array(mask)
            
            y_coords, x_coords = np.ogrid[:h, :w]
            dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
            mask_array[dist <= radius] = 255
            
            mask = Image.fromarray(mask_array)
            
            # 합성
            canvas = img2.copy()
            canvas.paste(img1, (0, 0), mask)
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def _iris_out(img1: Image.Image, img2: Image.Image, num_frames: int) -> List[Image.Image]:
        """아이리스 아웃 효과 (원형으로 열림)"""
        results = []
        w, h = img1.size
        center_x, center_y = w // 2, h // 2
        max_radius = int(np.sqrt(center_x**2 + center_y**2))
        
        for i in range(num_frames):
            progress = (i + 1) / (num_frames + 1)
            radius = int(max_radius * progress)
            
            # 원형 마스크 생성
            mask = Image.new('L', (w, h), 0)
            mask_array = np.array(mask)
            
            y_coords, x_coords = np.ogrid[:h, :w]
            dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
            mask_array[dist <= radius] = 255
            
            mask = Image.fromarray(mask_array)
            
            # 합성
            canvas = img1.copy()
            canvas.paste(img2, (0, 0), mask)
            
            results.append(canvas)
        
        return results
    
    @staticmethod
    def get_transition_names() -> List[Tuple[str, TransitionType]]:
        """UI용 전환 효과 이름 목록"""
        return [
            ("페이드", TransitionType.FADE),
            ("디졸브 (크로스페이드)", TransitionType.DISSOLVE),
            ("슬라이드 왼쪽", TransitionType.SLIDE_LEFT),
            ("슬라이드 오른쪽", TransitionType.SLIDE_RIGHT),
            ("슬라이드 위", TransitionType.SLIDE_UP),
            ("슬라이드 아래", TransitionType.SLIDE_DOWN),
            ("와이프 왼쪽", TransitionType.WIPE_LEFT),
            ("와이프 오른쪽", TransitionType.WIPE_RIGHT),
            ("와이프 위", TransitionType.WIPE_UP),
            ("와이프 아래", TransitionType.WIPE_DOWN),
            ("줌 인", TransitionType.ZOOM_IN),
            ("줌 아웃", TransitionType.ZOOM_OUT),
            ("아이리스 인", TransitionType.IRIS_IN),
            ("아이리스 아웃", TransitionType.IRIS_OUT),
        ]


def insert_transition(
    collection: FrameCollection,
    frame_index: int,
    transition_type: TransitionType,
    num_frames: int = 5,
    delay_ms: int = 50
) -> bool:
    """프레임 컬렉션에 전환 효과 삽입
    
    Args:
        collection: 프레임 컬렉션
        frame_index: 전환 효과를 삽입할 프레임 인덱스 (이 프레임과 다음 프레임 사이)
        transition_type: 전환 효과 타입
        num_frames: 전환 프레임 수
        delay_ms: 각 프레임의 딜레이
    
    Returns:
        bool: 성공 여부
    """
    if frame_index < 0 or frame_index >= len(collection) - 1:
        return False
    
    frame1 = collection[frame_index]
    frame2 = collection[frame_index + 1]
    
    if frame1 is None or frame2 is None:
        return False
    
    # 전환 프레임 생성
    transition_frames = TransitionEffect.create_transition(
        frame1, frame2, transition_type, num_frames, delay_ms
    )
    
    # 프레임 삽입 (역순으로 삽입해야 인덱스가 밀리지 않음)
    for i, frame in enumerate(transition_frames):
        collection.insert_frame(frame_index + 1 + i, frame)
    
    return True
