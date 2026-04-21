"""
AnimationEffects - 텍스트/스티커 애니메이션 효과
페이드, 슬라이드, 타이핑, 회전, 스케일 등의 애니메이션 프리셋 제공
"""
from __future__ import annotations
from typing import List, Tuple, Optional
from enum import Enum
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import math


class AnimationType(Enum):
    """애니메이션 타입"""
    NONE = "none"                   # 정적 (애니메이션 없음)
    FADE_IN = "fade_in"             # 페이드 인
    FADE_OUT = "fade_out"           # 페이드 아웃
    FADE_IN_OUT = "fade_in_out"     # 페이드 인 → 아웃
    SLIDE_LEFT = "slide_left"       # 왼쪽으로 슬라이드
    SLIDE_RIGHT = "slide_right"     # 오른쪽으로 슬라이드
    SLIDE_UP = "slide_up"           # 위로 슬라이드
    SLIDE_DOWN = "slide_down"       # 아래로 슬라이드
    BOUNCE_IN = "bounce_in"         # 바운스 인
    ZOOM_IN = "zoom_in"             # 줌 인
    ZOOM_OUT = "zoom_out"           # 줌 아웃
    ROTATE = "rotate"               # 회전
    TYPING = "typing"               # 타이핑 (텍스트 전용)
    SHAKE = "shake"                 # 흔들기
    PULSE = "pulse"                 # 펄스 (크기 변화)


@dataclass
class AnimationKeyframe:
    """애니메이션 키프레임"""
    progress: float         # 진행률 (0.0 ~ 1.0)
    x_offset: int = 0       # X 오프셋
    y_offset: int = 0       # Y 오프셋
    scale: float = 1.0      # 스케일
    rotation: float = 0.0   # 회전 (도)
    opacity: float = 1.0    # 투명도 (0.0 ~ 1.0)
    text_visible_chars: Optional[int] = None  # 타이핑용: 보이는 문자 수


class AnimationPreset:
    """애니메이션 프리셋 생성"""

    @staticmethod
    def get_keyframes(
        animation_type: AnimationType,
        num_frames: int,
        canvas_size: Tuple[int, int],
        element_size: Tuple[int, int],
        text_length: int = 0
    ) -> List[AnimationKeyframe]:
        """애니메이션 키프레임 목록 생성
        
        Args:
            animation_type: 애니메이션 타입
            num_frames: 총 프레임 수
            canvas_size: 캔버스 크기 (width, height)
            element_size: 요소 크기 (width, height)
            text_length: 텍스트 길이 (타이핑용)
        
        Returns:
            List[AnimationKeyframe]: 키프레임 리스트
        """
        keyframes = []

        for i in range(num_frames):
            progress = i / max(1, num_frames - 1)
            kf = AnimationKeyframe(progress=progress)

            if animation_type == AnimationType.NONE:
                pass  # 기본값 유지

            elif animation_type == AnimationType.FADE_IN:
                kf.opacity = progress

            elif animation_type == AnimationType.FADE_OUT:
                kf.opacity = 1.0 - progress

            elif animation_type == AnimationType.FADE_IN_OUT:
                if progress < 0.3:
                    kf.opacity = progress / 0.3
                elif progress > 0.7:
                    kf.opacity = (1.0 - progress) / 0.3
                else:
                    kf.opacity = 1.0

            elif animation_type == AnimationType.SLIDE_LEFT:
                kf.x_offset = int(canvas_size[0] * (1 - progress))

            elif animation_type == AnimationType.SLIDE_RIGHT:
                kf.x_offset = int(-canvas_size[0] * (1 - progress))

            elif animation_type == AnimationType.SLIDE_UP:
                kf.y_offset = int(canvas_size[1] * (1 - progress))

            elif animation_type == AnimationType.SLIDE_DOWN:
                kf.y_offset = int(-canvas_size[1] * (1 - progress))

            elif animation_type == AnimationType.BOUNCE_IN:
                # 이징: 바운스
                t = progress
                if t < 0.5:
                    kf.scale = t * 2 * 1.2  # 오버슈트
                else:
                    kf.scale = 1.0 + (1.0 - t) * 0.4  # 되돌아옴
                kf.scale = max(0, min(kf.scale, 1.5))
                kf.opacity = min(1.0, progress * 2)

            elif animation_type == AnimationType.ZOOM_IN:
                kf.scale = progress
                kf.opacity = progress

            elif animation_type == AnimationType.ZOOM_OUT:
                kf.scale = 1.0 + progress
                kf.opacity = 1.0 - progress

            elif animation_type == AnimationType.ROTATE:
                kf.rotation = progress * 360

            elif animation_type == AnimationType.TYPING:
                if text_length > 0:
                    kf.text_visible_chars = int(progress * text_length) + 1
                    kf.text_visible_chars = min(kf.text_visible_chars, text_length)

            elif animation_type == AnimationType.SHAKE:
                angle = progress * 4 * math.pi  # 2번 진동
                amplitude = 5 * (1 - progress)  # 점점 감소
                kf.x_offset = int(math.sin(angle) * amplitude)
                kf.y_offset = int(math.cos(angle * 1.5) * amplitude * 0.5)

            elif animation_type == AnimationType.PULSE:
                # 크기가 커졌다 작아졌다
                cycle = math.sin(progress * math.pi * 2)
                kf.scale = 1.0 + cycle * 0.15

            keyframes.append(kf)

        return keyframes

    @staticmethod
    def get_animation_names() -> List[Tuple[str, AnimationType]]:
        """UI용 애니메이션 이름 목록"""
        return [
            ("없음 (정적)", AnimationType.NONE),
            ("페이드 인", AnimationType.FADE_IN),
            ("페이드 아웃", AnimationType.FADE_OUT),
            ("페이드 인/아웃", AnimationType.FADE_IN_OUT),
            ("슬라이드 (왼쪽에서)", AnimationType.SLIDE_RIGHT),
            ("슬라이드 (오른쪽에서)", AnimationType.SLIDE_LEFT),
            ("슬라이드 (위에서)", AnimationType.SLIDE_DOWN),
            ("슬라이드 (아래에서)", AnimationType.SLIDE_UP),
            ("바운스 인", AnimationType.BOUNCE_IN),
            ("줌 인", AnimationType.ZOOM_IN),
            ("줌 아웃", AnimationType.ZOOM_OUT),
            ("회전", AnimationType.ROTATE),
            ("타이핑 (텍스트 전용)", AnimationType.TYPING),
            ("흔들기", AnimationType.SHAKE),
            ("펄스", AnimationType.PULSE),
        ]


class AnimatedOverlay:
    """애니메이션이 적용된 오버레이 생성"""

    @staticmethod
    def apply_text_animation(
        base_images: List[Image.Image],
        text: str,
        position: Tuple[int, int],
        font: ImageFont.FreeTypeFont,
        color: Tuple[int, int, int, int],
        animation_type: AnimationType,
        start_frame: int = 0,
        duration_frames: Optional[int] = None,
        outline_color: Optional[Tuple[int, int, int, int]] = None,
        outline_width: int = 0
    ) -> List[Image.Image]:
        """기본 이미지 목록에 애니메이션 텍스트 적용
        
        Args:
            base_images: 기본 이미지 리스트
            text: 텍스트
            position: 텍스트 위치 (x, y)
            font: 폰트
            color: 텍스트 색상 (RGBA)
            animation_type: 애니메이션 타입
            start_frame: 시작 프레임
            duration_frames: 애니메이션 지속 프레임 수 (None이면 끝까지)
            outline_color: 테두리 색상
            outline_width: 테두리 두께
        
        Returns:
            List[Image.Image]: 애니메이션이 적용된 이미지 리스트
        """
        if not base_images:
            return []

        result = [img.copy() for img in base_images]
        canvas_size = base_images[0].size

        # 텍스트 크기 측정
        temp_img = Image.new('RGBA', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 애니메이션 범위 계산
        end_frame = len(base_images)
        if duration_frames is not None:
            end_frame = min(start_frame + duration_frames, len(base_images))

        anim_frames = end_frame - start_frame
        if anim_frames <= 0:
            return result

        # 키프레임 생성
        keyframes = AnimationPreset.get_keyframes(
            animation_type,
            anim_frames,
            canvas_size,
            (text_width, text_height),
            len(text)
        )

        # 각 프레임에 텍스트 적용
        for i, kf in enumerate(keyframes):
            frame_idx = start_frame + i
            if frame_idx >= len(result):
                break

            # 표시할 텍스트 결정 (타이핑 애니메이션)
            display_text = text
            if kf.text_visible_chars is not None:
                display_text = text[:kf.text_visible_chars]

            if not display_text or kf.opacity <= 0:
                continue

            # 텍스트 이미지 생성
            text_img = AnimatedOverlay._create_text_image(
                display_text, font, color,
                outline_color, outline_width,
                kf.scale, kf.rotation
            )

            # 투명도 적용
            if kf.opacity < 1.0:
                alpha = text_img.split()[3]
                alpha = alpha.point(lambda x: int(x * kf.opacity))
                text_img.putalpha(alpha)

            # 위치 계산
            x = position[0] + kf.x_offset
            y = position[1] + kf.y_offset

            # 스케일 적용 시 중심 보정
            if kf.scale != 1.0:
                scaled_w = text_img.width
                scaled_h = text_img.height
                x = x - (scaled_w - text_width) // 2
                y = y - (scaled_h - text_height) // 2

            # 합성
            result[frame_idx] = AnimatedOverlay._composite(
                result[frame_idx], text_img, (x, y)
            )

        return result

    @staticmethod
    def apply_sticker_animation(
        base_images: List[Image.Image],
        sticker: Image.Image,
        position: Tuple[int, int],
        animation_type: AnimationType,
        start_frame: int = 0,
        duration_frames: Optional[int] = None,
        target_size: Optional[Tuple[int, int]] = None
    ) -> List[Image.Image]:
        """기본 이미지 목록에 애니메이션 스티커 적용
        
        Args:
            base_images: 기본 이미지 리스트
            sticker: 스티커 이미지
            position: 스티커 위치 (x, y)
            animation_type: 애니메이션 타입
            start_frame: 시작 프레임
            duration_frames: 애니메이션 지속 프레임 수
            target_size: 목표 크기 (width, height)
        
        Returns:
            List[Image.Image]: 애니메이션이 적용된 이미지 리스트
        """
        if not base_images:
            return []

        result = [img.copy() for img in base_images]
        canvas_size = base_images[0].size

        # 스티커 크기 조정
        if target_size:
            sticker = sticker.resize(target_size, Image.Resampling.LANCZOS)

        sticker_size = sticker.size

        # 애니메이션 범위 계산
        end_frame = len(base_images)
        if duration_frames is not None:
            end_frame = min(start_frame + duration_frames, len(base_images))

        anim_frames = end_frame - start_frame
        if anim_frames <= 0:
            return result

        # 키프레임 생성
        keyframes = AnimationPreset.get_keyframes(
            animation_type,
            anim_frames,
            canvas_size,
            sticker_size
        )

        # 각 프레임에 스티커 적용
        for i, kf in enumerate(keyframes):
            frame_idx = start_frame + i
            if frame_idx >= len(result):
                break

            if kf.opacity <= 0 or kf.scale <= 0:
                continue

            # 스티커 변환
            transformed = sticker.copy()

            # 스케일 적용
            if kf.scale != 1.0:
                new_w = int(sticker_size[0] * kf.scale)
                new_h = int(sticker_size[1] * kf.scale)
                if new_w > 0 and new_h > 0:
                    transformed = transformed.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # 회전 적용
            if kf.rotation != 0:
                transformed = transformed.rotate(
                    -kf.rotation,
                    resample=Image.Resampling.BICUBIC,
                    expand=True
                )

            # 투명도 적용
            if kf.opacity < 1.0:
                if transformed.mode == 'RGBA':
                    alpha = transformed.split()[3]
                    alpha = alpha.point(lambda x: int(x * kf.opacity))
                    transformed.putalpha(alpha)

            # 위치 계산
            x = position[0] + kf.x_offset
            y = position[1] + kf.y_offset

            # 스케일/회전 적용 시 중심 보정
            if kf.scale != 1.0 or kf.rotation != 0:
                x = x - (transformed.width - sticker_size[0]) // 2
                y = y - (transformed.height - sticker_size[1]) // 2

            # 합성
            result[frame_idx] = AnimatedOverlay._composite(
                result[frame_idx], transformed, (x, y)
            )

        return result

    @staticmethod
    def _create_text_image(
        text: str,
        font: ImageFont.FreeTypeFont,
        color: Tuple[int, int, int, int],
        outline_color: Optional[Tuple[int, int, int, int]],
        outline_width: int,
        scale: float,
        rotation: float
    ) -> Image.Image:
        """텍스트 이미지 생성"""
        # 텍스트 크기 측정
        temp_img = Image.new('RGBA', (1, 1))
        temp_draw = ImageDraw.Draw(temp_img)
        bbox = temp_draw.textbbox((0, 0), text, font=font)

        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        # 여백 추가
        padding = outline_width * 2 + 10
        img_width = text_width + padding * 2
        img_height = text_height + padding * 2

        # 텍스트 이미지 생성
        text_img = Image.new('RGBA', (img_width, img_height), (0, 0, 0, 0))
        draw = ImageDraw.Draw(text_img)

        x = padding - bbox[0]
        y = padding - bbox[1]

        # 테두리 그리기
        if outline_color and outline_width > 0:
            for dx in range(-outline_width, outline_width + 1):
                for dy in range(-outline_width, outline_width + 1):
                    if dx * dx + dy * dy <= outline_width * outline_width:
                        draw.text((x + dx, y + dy), text, font=font, fill=outline_color)

        # 텍스트 그리기
        draw.text((x, y), text, font=font, fill=color)

        # 스케일 적용
        if scale != 1.0:
            new_w = max(1, int(img_width * scale))
            new_h = max(1, int(img_height * scale))
            text_img = text_img.resize((new_w, new_h), Image.Resampling.LANCZOS)

        # 회전 적용
        if rotation != 0:
            text_img = text_img.rotate(
                -rotation,
                resample=Image.Resampling.BICUBIC,
                expand=True
            )

        return text_img

    @staticmethod
    def _composite(base: Image.Image, overlay: Image.Image,
                   position: Tuple[int, int]) -> Image.Image:
        """이미지 합성"""
        result = base.copy()

        if result.mode != 'RGBA':
            result = result.convert('RGBA')
        if overlay.mode != 'RGBA':
            overlay = overlay.convert('RGBA')

        # 위치가 이미지 범위 밖이면 클리핑
        x, y = position

        # 경계 처리
        if x >= result.width or y >= result.height:
            return result
        if x + overlay.width <= 0 or y + overlay.height <= 0:
            return result

        # 합성
        result.paste(overlay, (x, y), overlay)

        return result
