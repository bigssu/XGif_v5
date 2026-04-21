"""
Overlays - 말풍선, 스티커 등의 오버레이 요소
"""
from __future__ import annotations
from typing import Tuple, Optional, List
from enum import Enum
from dataclasses import dataclass
from PIL import Image, ImageDraw, ImageFont
import math


class BubbleStyle(Enum):
    """말풍선 스타일"""
    ROUNDED = "rounded"         # 둥근 말풍선
    CLOUD = "cloud"             # 구름형
    SHOUT = "shout"             # 외침 (톱니)
    THOUGHT = "thought"         # 생각 (작은 원들)
    RECTANGLE = "rectangle"     # 사각형
    OVAL = "oval"               # 타원형


class TailDirection(Enum):
    """꼬리 방향"""
    BOTTOM_LEFT = "bottom_left"
    BOTTOM_CENTER = "bottom_center"
    BOTTOM_RIGHT = "bottom_right"
    TOP_LEFT = "top_left"
    TOP_CENTER = "top_center"
    TOP_RIGHT = "top_right"
    LEFT_CENTER = "left_center"
    RIGHT_CENTER = "right_center"
    NONE = "none"


@dataclass
class SpeechBubbleConfig:
    """말풍선 설정"""
    style: BubbleStyle = BubbleStyle.ROUNDED
    tail_direction: TailDirection = TailDirection.BOTTOM_LEFT
    text: str = ""
    font_size: int = 20
    text_color: Tuple[int, int, int, int] = (0, 0, 0, 255)
    bg_color: Tuple[int, int, int, int] = (255, 255, 255, 255)
    border_color: Tuple[int, int, int, int] = (0, 0, 0, 255)
    border_width: int = 2
    padding: int = 15
    corner_radius: int = 20
    tail_length: int = 30


class SpeechBubble:
    """말풍선 생성 클래스"""

    @staticmethod
    def create(width: int, height: int, config: SpeechBubbleConfig,
               font_path: Optional[str] = None) -> Image.Image:
        """말풍선 이미지 생성
        
        Args:
            width: 말풍선 너비
            height: 말풍선 높이
            config: 말풍선 설정
            font_path: 폰트 경로 (None이면 기본 폰트)
        
        Returns:
            말풍선 이미지 (RGBA)
        """
        # 꼬리 공간 확보 — 캔버스 크기는 입력 크기(width × height) 고정
        tail_space = config.tail_length if config.tail_direction != TailDirection.NONE else 0

        canvas_w = width
        canvas_h = height

        img = Image.new('RGBA', (canvas_w, canvas_h), (0, 0, 0, 0))
        draw = ImageDraw.Draw(img)

        # 말풍선 본체 위치/크기 계산 (꼬리 공간만큼 본체 축소)
        bubble_x, bubble_y = 0, 0
        bubble_w, bubble_h = width, height

        if config.tail_direction in [TailDirection.BOTTOM_LEFT, TailDirection.BOTTOM_CENTER, TailDirection.BOTTOM_RIGHT]:
            bubble_h = height - tail_space
        elif config.tail_direction in [TailDirection.TOP_LEFT, TailDirection.TOP_CENTER, TailDirection.TOP_RIGHT]:
            bubble_y = tail_space
            bubble_h = height - tail_space
        elif config.tail_direction == TailDirection.LEFT_CENTER:
            bubble_x = tail_space
            bubble_w = width - tail_space
        elif config.tail_direction == TailDirection.RIGHT_CENTER:
            bubble_w = width - tail_space

        # 스타일별 말풍선 그리기
        if config.style == BubbleStyle.ROUNDED:
            SpeechBubble._draw_rounded(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)
        elif config.style == BubbleStyle.CLOUD:
            SpeechBubble._draw_cloud(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)
        elif config.style == BubbleStyle.SHOUT:
            SpeechBubble._draw_shout(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)
        elif config.style == BubbleStyle.THOUGHT:
            SpeechBubble._draw_thought(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)
        elif config.style == BubbleStyle.RECTANGLE:
            SpeechBubble._draw_rectangle(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)
        elif config.style == BubbleStyle.OVAL:
            SpeechBubble._draw_oval(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)

        # 꼬리 그리기
        if config.tail_direction != TailDirection.NONE:
            SpeechBubble._draw_tail(draw, bubble_x, bubble_y, bubble_w, bubble_h, config)

        # 텍스트 그리기
        if config.text:
            SpeechBubble._draw_text(draw, bubble_x, bubble_y, bubble_w, bubble_h, config, font_path)

        return img

    @staticmethod
    def _draw_rounded(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                      config: SpeechBubbleConfig):
        """둥근 말풍선"""
        r = config.corner_radius
        draw.rounded_rectangle(
            [x, y, x + w - 1, y + h - 1],
            radius=r,
            fill=config.bg_color,
            outline=config.border_color,
            width=config.border_width
        )

    @staticmethod
    def _draw_cloud(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                    config: SpeechBubbleConfig):
        """구름형 말풍선"""
        # 여러 개의 원을 합쳐서 구름 형태 생성
        bump_radius = min(w, h) // 6
        num_bumps_x = max(3, w // (bump_radius * 2))
        num_bumps_y = max(2, h // (bump_radius * 2))

        # 배경 채우기
        draw.rounded_rectangle(
            [x + bump_radius//2, y + bump_radius//2,
             x + w - bump_radius//2 - 1, y + h - bump_radius//2 - 1],
            radius=bump_radius,
            fill=config.bg_color
        )

        # 상단 범프
        for i in range(num_bumps_x):
            cx = x + bump_radius + i * ((w - bump_radius * 2) // max(1, num_bumps_x - 1))
            cy = y + bump_radius // 2
            draw.ellipse([cx - bump_radius, cy - bump_radius//2,
                         cx + bump_radius, cy + bump_radius//2 + bump_radius],
                        fill=config.bg_color)

        # 하단 범프
        for i in range(num_bumps_x):
            cx = x + bump_radius + i * ((w - bump_radius * 2) // max(1, num_bumps_x - 1))
            cy = y + h - bump_radius // 2
            draw.ellipse([cx - bump_radius, cy - bump_radius//2 - bump_radius,
                         cx + bump_radius, cy + bump_radius//2],
                        fill=config.bg_color)

        # 테두리
        draw.rounded_rectangle(
            [x + bump_radius//2, y + bump_radius//2,
             x + w - bump_radius//2 - 1, y + h - bump_radius//2 - 1],
            radius=bump_radius,
            outline=config.border_color,
            width=config.border_width
        )

    @staticmethod
    def _draw_shout(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                    config: SpeechBubbleConfig):
        """외침(톱니) 말풍선"""
        spike_size = 15
        num_spikes = max(4, (w + h) // 40)

        points = []
        # 외곽선을 따라 톱니 생성
        for i in range(num_spikes * 4):
            progress = i / (num_spikes * 4)

            if progress < 0.25:  # 상단
                t = progress / 0.25
                bx = x + t * w
                by = y
            elif progress < 0.5:  # 우측
                t = (progress - 0.25) / 0.25
                bx = x + w
                by = y + t * h
            elif progress < 0.75:  # 하단
                t = (progress - 0.5) / 0.25
                bx = x + w - t * w
                by = y + h
            else:  # 좌측
                t = (progress - 0.75) / 0.25
                bx = x
                by = y + h - t * h

            # 중심 방향 오프셋
            cx, cy = x + w/2, y + h/2
            dx, dy = bx - cx, by - cy
            dist = math.sqrt(dx*dx + dy*dy) or 1

            # 짝수/홀수로 안/바깥 결정
            if i % 2 == 0:
                points.append((bx - dx/dist * spike_size, by - dy/dist * spike_size))
            else:
                points.append((bx, by))

        draw.polygon(points, fill=config.bg_color, outline=config.border_color, width=config.border_width)

    @staticmethod
    def _draw_thought(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                      config: SpeechBubbleConfig):
        """생각 말풍선 (타원)"""
        draw.ellipse([x, y, x + w - 1, y + h - 1],
                    fill=config.bg_color, outline=config.border_color, width=config.border_width)

    @staticmethod
    def _draw_rectangle(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                        config: SpeechBubbleConfig):
        """사각형 말풍선"""
        draw.rectangle([x, y, x + w - 1, y + h - 1],
                      fill=config.bg_color, outline=config.border_color, width=config.border_width)

    @staticmethod
    def _draw_oval(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                   config: SpeechBubbleConfig):
        """타원형 말풍선"""
        draw.ellipse([x, y, x + w - 1, y + h - 1],
                    fill=config.bg_color, outline=config.border_color, width=config.border_width)

    @staticmethod
    def _draw_tail(draw: ImageDraw.Draw, bx: int, by: int, bw: int, bh: int,
                   config: SpeechBubbleConfig):
        """말풍선 꼬리 그리기"""
        tail_len = config.tail_length
        tail_width = 20

        direction = config.tail_direction

        # 꼬리 시작점과 끝점 계산
        if direction == TailDirection.BOTTOM_LEFT:
            p1 = (bx + bw // 4 - tail_width//2, by + bh - config.border_width)
            p2 = (bx + bw // 4 + tail_width//2, by + bh - config.border_width)
            p3 = (bx + bw // 6, by + bh + tail_len)
        elif direction == TailDirection.BOTTOM_CENTER:
            p1 = (bx + bw // 2 - tail_width//2, by + bh - config.border_width)
            p2 = (bx + bw // 2 + tail_width//2, by + bh - config.border_width)
            p3 = (bx + bw // 2, by + bh + tail_len)
        elif direction == TailDirection.BOTTOM_RIGHT:
            p1 = (bx + bw * 3 // 4 - tail_width//2, by + bh - config.border_width)
            p2 = (bx + bw * 3 // 4 + tail_width//2, by + bh - config.border_width)
            p3 = (bx + bw * 5 // 6, by + bh + tail_len)
        elif direction == TailDirection.TOP_LEFT:
            p1 = (bx + bw // 4 - tail_width//2, by + config.border_width)
            p2 = (bx + bw // 4 + tail_width//2, by + config.border_width)
            p3 = (bx + bw // 6, by - tail_len)
        elif direction == TailDirection.TOP_CENTER:
            p1 = (bx + bw // 2 - tail_width//2, by + config.border_width)
            p2 = (bx + bw // 2 + tail_width//2, by + config.border_width)
            p3 = (bx + bw // 2, by - tail_len)
        elif direction == TailDirection.TOP_RIGHT:
            p1 = (bx + bw * 3 // 4 - tail_width//2, by + config.border_width)
            p2 = (bx + bw * 3 // 4 + tail_width//2, by + config.border_width)
            p3 = (bx + bw * 5 // 6, by - tail_len)
        elif direction == TailDirection.LEFT_CENTER:
            p1 = (bx + config.border_width, by + bh // 2 - tail_width//2)
            p2 = (bx + config.border_width, by + bh // 2 + tail_width//2)
            p3 = (bx - tail_len, by + bh // 2)
        elif direction == TailDirection.RIGHT_CENTER:
            p1 = (bx + bw - config.border_width, by + bh // 2 - tail_width//2)
            p2 = (bx + bw - config.border_width, by + bh // 2 + tail_width//2)
            p3 = (bx + bw + tail_len, by + bh // 2)
        else:
            return

        # 생각 말풍선은 작은 원들로 꼬리 표현
        if config.style == BubbleStyle.THOUGHT:
            num_circles = 3
            for i in range(num_circles):
                t = (i + 1) / (num_circles + 1)
                cx = p1[0] + (p3[0] - p1[0]) * t
                cy = p1[1] + (p3[1] - p1[1]) * t
                r = 8 - i * 2
                draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                            fill=config.bg_color, outline=config.border_color, width=config.border_width)
        else:
            # 삼각형 꼬리
            draw.polygon([p1, p2, p3], fill=config.bg_color)
            # 테두리 (양쪽 선만)
            draw.line([p1, p3], fill=config.border_color, width=config.border_width)
            draw.line([p2, p3], fill=config.border_color, width=config.border_width)

    @staticmethod
    def _draw_text(draw: ImageDraw.Draw, x: int, y: int, w: int, h: int,
                   config: SpeechBubbleConfig, font_path: Optional[str]):
        """텍스트 그리기"""
        # 폰트 로드
        try:
            if font_path:
                font = ImageFont.truetype(font_path, config.font_size)
            else:
                font = ImageFont.truetype("arial.ttf", config.font_size)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", config.font_size)
            except (OSError, IOError):
                font = ImageFont.load_default()

        # 텍스트 영역
        text_area = (
            x + config.padding,
            y + config.padding,
            x + w - config.padding,
            y + h - config.padding
        )

        # 텍스트 중앙 정렬
        bbox = draw.textbbox((0, 0), config.text, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]

        text_x = x + (w - text_w) // 2
        text_y = y + (h - text_h) // 2

        draw.text((text_x, text_y), config.text, font=font, fill=config.text_color)

    @staticmethod
    def get_style_names() -> List[Tuple[str, BubbleStyle]]:
        """UI용 스타일 이름 목록"""
        return [
            ("둥근 말풍선", BubbleStyle.ROUNDED),
            ("구름형", BubbleStyle.CLOUD),
            ("외침 (톱니)", BubbleStyle.SHOUT),
            ("생각", BubbleStyle.THOUGHT),
            ("사각형", BubbleStyle.RECTANGLE),
            ("타원형", BubbleStyle.OVAL),
        ]

    @staticmethod
    def get_tail_directions() -> List[Tuple[str, TailDirection]]:
        """UI용 꼬리 방향 목록"""
        return [
            ("아래 왼쪽", TailDirection.BOTTOM_LEFT),
            ("아래 중앙", TailDirection.BOTTOM_CENTER),
            ("아래 오른쪽", TailDirection.BOTTOM_RIGHT),
            ("위 왼쪽", TailDirection.TOP_LEFT),
            ("위 중앙", TailDirection.TOP_CENTER),
            ("위 오른쪽", TailDirection.TOP_RIGHT),
            ("왼쪽", TailDirection.LEFT_CENTER),
            ("오른쪽", TailDirection.RIGHT_CENTER),
            ("없음", TailDirection.NONE),
        ]
