"""Gizmo — 캔버스에서 마우스로 드래그·리사이즈하는 사각형 영역의 공통 추상화.

각 편집 모드 (text, crop, sticker, mosaic, speech_bubble) 가 자체 Gizmo 인스턴스를
가지며, 캔버스의 마우스 핸들러는 활성 Gizmo 에 위임한다. 핸들 hit-test, 드래그,
리사이즈 로직이 모드별로 복제되어 5× 회귀 위험을 만들던 패턴을 제거.

이전 구조 (mode 당 별도 attr `_text_rect`, `_text_dragging`, `_text_drag_start`,
`_text_original_rect`, `_text_handle`, ... 5종 × 5 mode = 25 attribute) 는:
- 한 mode 의 수정이 다른 mode 에 전파 안 돼 회귀 5× 발생 (예: 모자이크 기즈모
  좌표가 PyQt6 시그널 잔재로 끊김, 텍스트 미리보기가 paint LRU id 재사용으로
  옛 위치 표시)
- 새 mode 추가 시 25 곳 수정 필요
- canvas_widget_wx.py 가 1600+ LOC 로 부풀어 GOD_OBJECT 위험

새 구조:
- `Gizmo` 인스턴스는 인터랙션 상태와 좌표 변환만 담당
- 렌더링 (점선 박스, 도형, bubble 이미지 등) 은 모드별 차이가 크므로 캔버스에 잔류
- 캔버스의 `_on_left_down/move/up`, `_update_cursor_for_hover` 가 활성 Gizmo 에
  단일 위임 (mode 별 분기 5개 → 1개)

이전 attr 들 (`_text_rect` 등) 은 backwards-compat 을 위해 property 로 alias.
점진적 마이그레이션 후 alias 제거 가능.
"""
from __future__ import annotations

from typing import Callable, Optional

import wx


# 4 코너 핸들만 (sticker/mosaic/speech_bubble — 도형 유지를 위해 edge 리사이즈 비허용)
CORNER_HANDLES = frozenset({'tl', 'tr', 'bl', 'br'})

# 8 핸들 모두 (text/crop — 자유 리사이즈)
ALL_HANDLES = frozenset({'tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r'})


class Gizmo:
    """캔버스 기즈모 영역의 인터랙션 상태 + 마우스 처리 로직."""

    def __init__(
        self,
        name: str,
        rect_cls,
        *,
        allow_resize: bool = True,
        corner_only: bool = False,
        min_size: int = 10,
        on_release: Optional[Callable[["Gizmo"], None]] = None,
    ) -> None:
        """Args:
            name: 모드 식별자 ('text' | 'crop' | 'sticker' | 'mosaic' | 'speech_bubble').
            rect_cls: RectF 클래스 — 새 빈 rect 생성 + 복제용.
            allow_resize: True 면 핸들 hit + resize 활성. False 면 드래그만.
            corner_only: True 면 4 코너 핸들만 활성. False 면 8 (corner + edge).
            min_size: 리사이즈 최소 width/height (px, 이미지 좌표).
            on_release: mouse up 시 호출되는 callback (self 전달). 보통
                wx.PostEvent 로 X_CHANGED 이벤트 발생.
        """
        self.name = name
        self._rect_cls = rect_cls
        self.allow_resize = allow_resize
        self.corner_only = corner_only
        self.min_size = min_size
        self.on_release = on_release

        self.active = False
        self.rect = rect_cls()  # 이미지 좌표
        self.dragging = False
        self.resizing = False
        self.handle: Optional[str] = None
        self.drag_start = wx.Point()
        self.original_rect = rect_cls()  # 드래그/리사이즈 시작 시 스냅샷

    # === 활성화 / 영역 갱신 ===

    @property
    def visible(self) -> bool:
        """오버레이 렌더링 + hit-test 적용 여부 — active + non-empty."""
        return self.active and not self.rect.IsEmpty()

    @property
    def interacting(self) -> bool:
        """드래그 또는 리사이즈 진행 중."""
        return self.dragging or self.resizing

    def _assign_rect(self, target, x: float, y: float, w: float, h: float) -> None:
        """rect 객체의 attribute 를 in-place 로 갱신 — 외부 alias 의 객체 동일성을
        유지하기 위해 새 RectF 를 할당하지 않는다."""
        target.x = x
        target.y = y
        target.width = w
        target.height = h

    def start(self, x: float, y: float, w: float, h: float) -> None:
        """기즈모 활성화 + 초기 영역 설정."""
        self.active = True
        self._assign_rect(self.rect, x, y, w, h)

    def stop(self) -> None:
        """기즈모 비활성화 + 상태 리셋 (rect 는 영역만 비움, 객체는 유지)."""
        self.active = False
        self.dragging = False
        self.resizing = False
        self.handle = None
        self._assign_rect(self.rect, 0, 0, 0, 0)

    def update_rect(self, x: float, y: float, w: float, h: float) -> None:
        """외부 (toolbar) 가 rect 를 명시적으로 갱신."""
        self._assign_rect(self.rect, x, y, w, h)

    # === 마우스 인터랙션 ===

    def allowed_handles(self) -> frozenset:
        return CORNER_HANDLES if self.corner_only else ALL_HANDLES

    def hit_handle(
        self, screen_rect: wx.Rect, pos: wx.Point, handle_size: int,
    ) -> Optional[str]:
        """화면 좌표에서 핸들 hit-test. allowed_handles 만 검사."""
        if not self.allow_resize or not self.visible:
            return None
        # 순환 import 방지 — paint utils 는 stable
        from ..utils.wx_paint_utils import get_handle_rects
        handles = get_handle_rects(screen_rect, handle_size)
        allowed = self.allowed_handles()
        for handle_name, handle_rect in handles.items():
            if handle_name in allowed and handle_rect.Contains(pos):
                return handle_name
        return None

    def is_point_inside(self, screen_rect: wx.Rect, pos: wx.Point) -> bool:
        if not self.visible:
            return False
        return screen_rect.Contains(pos)

    def begin_drag(self, pos: wx.Point) -> None:
        self.dragging = True
        self.drag_start = pos
        self._assign_rect(
            self.original_rect, self.rect.x, self.rect.y, self.rect.width, self.rect.height,
        )

    def begin_resize(self, pos: wx.Point, handle: str) -> None:
        self.resizing = True
        self.handle = handle
        self.drag_start = pos
        self._assign_rect(
            self.original_rect, self.rect.x, self.rect.y, self.rect.width, self.rect.height,
        )

    def apply_drag(self, current_pos: wx.Point, zoom: float) -> None:
        """마우스 이동에 따라 rect.x/y 갱신 (이미지 좌표)."""
        delta_x = (current_pos.x - self.drag_start.x) / zoom
        delta_y = (current_pos.y - self.drag_start.y) / zoom
        self.rect.x = self.original_rect.x + delta_x
        self.rect.y = self.original_rect.y + delta_y

    def apply_resize(self, current_pos: wx.Point, zoom: float) -> None:
        """핸들에 따라 rect width/height 갱신."""
        delta_x = (current_pos.x - self.drag_start.x) / zoom
        delta_y = (current_pos.y - self.drag_start.y) / zoom
        orig = self.original_rect
        rect = self.rect
        handle = self.handle

        if handle == 'tl':
            rect.x = orig.x + delta_x
            rect.y = orig.y + delta_y
            rect.width = orig.width - delta_x
            rect.height = orig.height - delta_y
        elif handle == 'tr':
            rect.y = orig.y + delta_y
            rect.width = orig.width + delta_x
            rect.height = orig.height - delta_y
        elif handle == 'bl':
            rect.x = orig.x + delta_x
            rect.width = orig.width - delta_x
            rect.height = orig.height + delta_y
        elif handle == 'br':
            rect.width = orig.width + delta_x
            rect.height = orig.height + delta_y
        elif handle == 't':
            rect.y = orig.y + delta_y
            rect.height = orig.height - delta_y
        elif handle == 'b':
            rect.height = orig.height + delta_y
        elif handle == 'l':
            rect.x = orig.x + delta_x
            rect.width = orig.width - delta_x
        elif handle == 'r':
            rect.width = orig.width + delta_x

        if rect.width < self.min_size:
            rect.width = self.min_size
        if rect.height < self.min_size:
            rect.height = self.min_size

    def end_interaction(self) -> bool:
        """드래그/리사이즈 종료. on_release 호출 + 결과 True/False 반환."""
        was_active = self.dragging or self.resizing
        was_resizing = self.resizing
        self.dragging = False
        self.resizing = False
        # handle 은 on_release 가 참조 가능하도록 잠깐 유지 후 release 안에서 reset
        if was_active and self.on_release:
            self.on_release(self)
        self.handle = None
        # 마지막 인터랙션 종류 정보 노출 (text 의 resize 폰트 크기 계산 등에 사용)
        self._last_was_resize = was_resizing
        return was_active

    @property
    def last_was_resize(self) -> bool:
        """end_interaction 직후 마지막 인터랙션이 resize 였는지."""
        return getattr(self, '_last_was_resize', False)
