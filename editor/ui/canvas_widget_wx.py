"""
CanvasWidget - 프레임 편집 캔버스 (wxPython 버전)

PyQt6 QWidget을 wxPython wx.Panel로 마이그레이션
가장 복잡한 컴포넌트: 6개 편집 모드, 줌/팬, 커스텀 페인팅
"""
import wx
import math
from collections import OrderedDict
from typing import Dict, Optional, List, Tuple, TYPE_CHECKING
from PIL import Image
from .style_constants_wx import Colors, Fonts
from .canvas_gizmo import Gizmo
from ..utils.image_utils import pil_to_wx_bitmap
from ..utils.wx_paint_utils import draw_checkerboard, draw_handle, get_handle_rects, get_cursor_for_handle
from ..utils.wx_events import (
    DrawingFinishedEvent, DrawingStartedEvent,
    TextMovedEvent, TextResizedEvent,
    CropChangedEvent, StickerChangedEvent,
    MosaicRegionChangedEvent, SpeechBubbleChangedEvent,
    ZoomChangedEvent
)
from ui.i18n import tr

if TYPE_CHECKING:
    from .main_window import MainWindow


# ============================================================================
# Float 좌표를 지원하는 사각형 클래스 (RectF 대체)
# ============================================================================

class RectF:
    """Float 좌표를 지원하는 사각형 클래스"""

    def __init__(self, x: float = 0, y: float = 0, width: float = 0, height: float = 0):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

    def IsEmpty(self) -> bool:
        """비어있는지 확인"""
        return self.width <= 0 or self.height <= 0

    def GetLeft(self) -> float:
        return self.x

    def GetTop(self) -> float:
        return self.y

    def GetRight(self) -> float:
        return self.x + self.width

    def GetBottom(self) -> float:
        return self.y + self.height

    def __repr__(self):
        return f"RectF({self.x}, {self.y}, {self.width}, {self.height})"


class CanvasWidget(wx.Panel):
    """프레임 편집 캔버스 (wxPython)"""

    # 핸들 크기
    HANDLE_SIZE = 8

    def __init__(self, main_window: 'MainWindow', parent=None):
        if parent is None:
            parent = main_window
        super().__init__(parent)
        self._main_window = main_window

        # 줌/팬 상태
        self._zoom = 1.0
        self._pan_offset = wx.Point(0, 0)

        # 마우스 상태
        self._last_mouse_pos = wx.Point()
        self._is_panning = False

        # 배경 색상
        self._bg_color = Colors.BG_CANVAS
        self._checker_color1 = Colors.CHECKER_LIGHT
        self._checker_color2 = Colors.CHECKER_DARK
        self._checker_size = 10

        # 펜슬 그리기 모드
        self._drawing_mode = False
        self._is_drawing = False
        self._pencil_color = wx.Colour(255, 0, 0)
        self._pencil_width = 3
        self._current_path: List[wx.Point] = []  # 현재 그리고 있는 경로
        self._drawing_paths: List[Tuple[List[wx.Point], wx.Colour, int]] = []  # 완성된 경로들

        # 펜슬 프리뷰 범위
        self._pencil_preview_start = 0
        self._pencil_preview_count = 0
        self._auto_animation_mode = False
        self._auto_animation_frames = []

        # 기즈모 영역 (text/crop/sticker/mosaic/speech_bubble) — 공통 추상화.
        # 각 모드의 mouse 인터랙션 (드래그/리사이즈/핸들 hit-test) 은 Gizmo 가
        # 담당. 이전엔 mode 당 7개 attr × 5 mode = 35 attr 가 산재하여 한
        # mode 의 회귀가 4 mode 에 전파 안 돼 패치 5× 부담을 만들었다. 이제
        # mode-specific attr (`_text_rect`, `_text_dragging`, ...) 들은 아래
        # property alias 가 Gizmo 의 state 로 라우팅하여 backwards-compat 을
        # 유지하면서 단일 진실 출처를 확립.
        self._gizmos: Dict[str, Gizmo] = {
            'text': Gizmo(
                'text', RectF, allow_resize=True, corner_only=False,
                on_release=self._dispatch_gizmo_release,
            ),
            'crop': Gizmo(
                'crop', RectF, allow_resize=True, corner_only=False,
                on_release=self._dispatch_gizmo_release,
            ),
            'sticker': Gizmo(
                'sticker', RectF, allow_resize=True, corner_only=True,
                on_release=self._dispatch_gizmo_release,
            ),
            'mosaic': Gizmo(
                'mosaic', RectF, allow_resize=True, corner_only=True,
                on_release=self._dispatch_gizmo_release,
            ),
            'speech_bubble': Gizmo(
                'speech_bubble', RectF, allow_resize=True, corner_only=True,
                on_release=self._dispatch_gizmo_release,
            ),
        }
        # text/sticker 의 폰트·스티커 크기 추적 (Gizmo 외부 — 리사이즈 시 비례 계산)
        self._text_current_size = 32
        self._text_resize_start_size = 32
        self._sticker_original_size = 80
        self._sticker_resize_start_size = 80

        # paint 결과 캐시 — LRU OrderedDict, 키: (id(pil_image), zoom, w, h),
        # 값: wx.Bitmap. 단일 캐시 항목은 zoom toggle / 인접 프레임 토글에서 매번
        # cache miss → PIL→wxImage→Scale 비용을 유발했다. LRU 6개를 유지하여
        # 정주적인 사용자 토글 (현재 zoom 2-3개 + 인접 프레임 1-2개) 의 비용을 0
        # 으로 만든다. 각 항목 메모리는 frame size × 4 byte 정도 (1920×1080 RGBA
        # ≈ 8MB, 6 항목 ≈ 48MB) — 큰 부담 없음.
        self._scaled_bitmap_cache: "OrderedDict[tuple, wx.Bitmap]" = OrderedDict()
        self._scaled_bitmap_cache_max = 6

        # 설정
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)  # 더블 버퍼링 활성화
        self._skip_auto_theme = True

        # 이벤트 바인딩
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_mouse_wheel)
        self.Bind(wx.EVT_MIDDLE_DOWN, self._on_middle_down)
        self.Bind(wx.EVT_MIDDLE_UP, self._on_middle_up)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self.Bind(wx.EVT_MOTION, self._on_mouse_move)
        self.Bind(wx.EVT_KEY_DOWN, self._on_key_down)

    # ========================================================================
    # 줌 컨트롤
    # ========================================================================

    @property
    def zoom(self) -> float:
        """현재 줌 레벨"""
        return self._zoom

    @zoom.setter
    def zoom(self, value: float):
        """줌 레벨 설정 (0.1 ~ 10.0)"""
        old_zoom = self._zoom
        self._zoom = max(0.1, min(10.0, value))

        if old_zoom != self._zoom:
            evt = ZoomChangedEvent(self._zoom)
            wx.PostEvent(self, evt)
            self.Refresh()

    def zoom_in(self):
        """줌 인 (1.25배)"""
        self.zoom *= 1.25

    def zoom_out(self):
        """줌 아웃 (0.8배)"""
        self.zoom /= 1.25

    def zoom_fit(self):
        """화면에 맞춤"""
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return

            width = getattr(frames, 'width', 0)
            height = getattr(frames, 'height', 0)

            if width <= 0 or height <= 0:
                return

            available_width = max(1, self.GetSize().GetWidth() - 40)
            available_height = max(1, self.GetSize().GetHeight() - 40)

            zoom_x = available_width / width
            zoom_y = available_height / height

            self.zoom = min(zoom_x, zoom_y)
            self._pan_offset = wx.Point(0, 0)
        except Exception:
            pass

    def zoom_actual(self):
        """원본 크기 (100%)"""
        self.zoom = 1.0
        self._pan_offset = wx.Point(0, 0)

    def clear_bitmap_cache(self) -> None:
        """paint LRU 캐시 비우기 — 메모리 압박 시 호출됨."""
        self._scaled_bitmap_cache.clear()

    # ========================================================================
    # Gizmo state property aliases (backwards-compat) — Gizmo 의 state 를 기존
    # mode-specific attr 이름으로 노출. `self._text_rect.x = ...` 같은 in-place
    # 변경은 Gizmo.rect 객체에 직접 반영되고, `self._text_rect = RectF(...)`
    # reassign 은 setter 가 객체 attribute 를 in-place 복사하여 객체 동일성을
    # 유지. 이로써 paint/start_X_mode/update_X_rect 등 기존 호출처가 깨지지
    # 않으면서 단일 진실 출처 (Gizmo) 를 확립한다.
    # ========================================================================

    @staticmethod
    def _copy_rect_into(target, value) -> None:
        """RectF reassign 을 in-place mutation 으로 변환 (객체 동일성 유지)."""
        target.x = value.x
        target.y = value.y
        target.width = value.width
        target.height = value.height

    # --- text ---
    @property
    def _text_edit_mode(self) -> bool: return self._gizmos['text'].active
    @_text_edit_mode.setter
    def _text_edit_mode(self, v: bool) -> None: self._gizmos['text'].active = v

    @property
    def _text_rect(self): return self._gizmos['text'].rect
    @_text_rect.setter
    def _text_rect(self, v) -> None: self._copy_rect_into(self._gizmos['text'].rect, v)

    @property
    def _text_dragging(self) -> bool: return self._gizmos['text'].dragging
    @_text_dragging.setter
    def _text_dragging(self, v: bool) -> None: self._gizmos['text'].dragging = v

    @property
    def _text_resizing(self) -> bool: return self._gizmos['text'].resizing
    @_text_resizing.setter
    def _text_resizing(self, v: bool) -> None: self._gizmos['text'].resizing = v

    @property
    def _resize_handle(self) -> Optional[str]: return self._gizmos['text'].handle
    @_resize_handle.setter
    def _resize_handle(self, v: Optional[str]) -> None: self._gizmos['text'].handle = v

    @property
    def _text_drag_start(self) -> wx.Point: return self._gizmos['text'].drag_start
    @_text_drag_start.setter
    def _text_drag_start(self, v: wx.Point) -> None: self._gizmos['text'].drag_start = v

    @property
    def _text_original_rect(self): return self._gizmos['text'].original_rect
    @_text_original_rect.setter
    def _text_original_rect(self, v) -> None: self._copy_rect_into(self._gizmos['text'].original_rect, v)

    # --- crop ---
    @property
    def _crop_mode(self) -> bool: return self._gizmos['crop'].active
    @_crop_mode.setter
    def _crop_mode(self, v: bool) -> None: self._gizmos['crop'].active = v

    @property
    def _crop_rect(self): return self._gizmos['crop'].rect
    @_crop_rect.setter
    def _crop_rect(self, v) -> None: self._copy_rect_into(self._gizmos['crop'].rect, v)

    @property
    def _crop_dragging(self) -> bool: return self._gizmos['crop'].dragging
    @_crop_dragging.setter
    def _crop_dragging(self, v: bool) -> None: self._gizmos['crop'].dragging = v

    @property
    def _crop_resizing(self) -> bool: return self._gizmos['crop'].resizing
    @_crop_resizing.setter
    def _crop_resizing(self, v: bool) -> None: self._gizmos['crop'].resizing = v

    @property
    def _crop_handle(self) -> Optional[str]: return self._gizmos['crop'].handle
    @_crop_handle.setter
    def _crop_handle(self, v: Optional[str]) -> None: self._gizmos['crop'].handle = v

    @property
    def _crop_drag_start(self) -> wx.Point: return self._gizmos['crop'].drag_start
    @_crop_drag_start.setter
    def _crop_drag_start(self, v: wx.Point) -> None: self._gizmos['crop'].drag_start = v

    @property
    def _crop_original_rect(self): return self._gizmos['crop'].original_rect
    @_crop_original_rect.setter
    def _crop_original_rect(self, v) -> None: self._copy_rect_into(self._gizmos['crop'].original_rect, v)

    # --- sticker ---
    @property
    def _sticker_mode(self) -> bool: return self._gizmos['sticker'].active
    @_sticker_mode.setter
    def _sticker_mode(self, v: bool) -> None: self._gizmos['sticker'].active = v

    @property
    def _sticker_rect(self): return self._gizmos['sticker'].rect
    @_sticker_rect.setter
    def _sticker_rect(self, v) -> None: self._copy_rect_into(self._gizmos['sticker'].rect, v)

    @property
    def _sticker_dragging(self) -> bool: return self._gizmos['sticker'].dragging
    @_sticker_dragging.setter
    def _sticker_dragging(self, v: bool) -> None: self._gizmos['sticker'].dragging = v

    @property
    def _sticker_resizing(self) -> bool: return self._gizmos['sticker'].resizing
    @_sticker_resizing.setter
    def _sticker_resizing(self, v: bool) -> None: self._gizmos['sticker'].resizing = v

    @property
    def _sticker_handle(self) -> Optional[str]: return self._gizmos['sticker'].handle
    @_sticker_handle.setter
    def _sticker_handle(self, v: Optional[str]) -> None: self._gizmos['sticker'].handle = v

    @property
    def _sticker_drag_start(self) -> wx.Point: return self._gizmos['sticker'].drag_start
    @_sticker_drag_start.setter
    def _sticker_drag_start(self, v: wx.Point) -> None: self._gizmos['sticker'].drag_start = v

    @property
    def _sticker_original_rect(self): return self._gizmos['sticker'].original_rect
    @_sticker_original_rect.setter
    def _sticker_original_rect(self, v) -> None: self._copy_rect_into(self._gizmos['sticker'].original_rect, v)

    # --- mosaic ---
    @property
    def _mosaic_mode(self) -> bool: return self._gizmos['mosaic'].active
    @_mosaic_mode.setter
    def _mosaic_mode(self, v: bool) -> None: self._gizmos['mosaic'].active = v

    @property
    def _mosaic_rect(self): return self._gizmos['mosaic'].rect
    @_mosaic_rect.setter
    def _mosaic_rect(self, v) -> None: self._copy_rect_into(self._gizmos['mosaic'].rect, v)

    @property
    def _mosaic_dragging(self) -> bool: return self._gizmos['mosaic'].dragging
    @_mosaic_dragging.setter
    def _mosaic_dragging(self, v: bool) -> None: self._gizmos['mosaic'].dragging = v

    @property
    def _mosaic_resizing(self) -> bool: return self._gizmos['mosaic'].resizing
    @_mosaic_resizing.setter
    def _mosaic_resizing(self, v: bool) -> None: self._gizmos['mosaic'].resizing = v

    @property
    def _mosaic_handle(self) -> Optional[str]: return self._gizmos['mosaic'].handle
    @_mosaic_handle.setter
    def _mosaic_handle(self, v: Optional[str]) -> None: self._gizmos['mosaic'].handle = v

    @property
    def _mosaic_drag_start(self) -> wx.Point: return self._gizmos['mosaic'].drag_start
    @_mosaic_drag_start.setter
    def _mosaic_drag_start(self, v: wx.Point) -> None: self._gizmos['mosaic'].drag_start = v

    @property
    def _mosaic_original_rect(self): return self._gizmos['mosaic'].original_rect
    @_mosaic_original_rect.setter
    def _mosaic_original_rect(self, v) -> None: self._copy_rect_into(self._gizmos['mosaic'].original_rect, v)

    # --- speech_bubble ---
    @property
    def _speech_bubble_mode(self) -> bool: return self._gizmos['speech_bubble'].active
    @_speech_bubble_mode.setter
    def _speech_bubble_mode(self, v: bool) -> None: self._gizmos['speech_bubble'].active = v

    @property
    def _speech_bubble_rect(self): return self._gizmos['speech_bubble'].rect
    @_speech_bubble_rect.setter
    def _speech_bubble_rect(self, v) -> None: self._copy_rect_into(self._gizmos['speech_bubble'].rect, v)

    @property
    def _speech_bubble_dragging(self) -> bool: return self._gizmos['speech_bubble'].dragging
    @_speech_bubble_dragging.setter
    def _speech_bubble_dragging(self, v: bool) -> None: self._gizmos['speech_bubble'].dragging = v

    @property
    def _speech_bubble_resizing(self) -> bool: return self._gizmos['speech_bubble'].resizing
    @_speech_bubble_resizing.setter
    def _speech_bubble_resizing(self, v: bool) -> None: self._gizmos['speech_bubble'].resizing = v

    @property
    def _speech_bubble_handle(self) -> Optional[str]: return self._gizmos['speech_bubble'].handle
    @_speech_bubble_handle.setter
    def _speech_bubble_handle(self, v: Optional[str]) -> None: self._gizmos['speech_bubble'].handle = v

    @property
    def _speech_bubble_drag_start(self) -> wx.Point: return self._gizmos['speech_bubble'].drag_start
    @_speech_bubble_drag_start.setter
    def _speech_bubble_drag_start(self, v: wx.Point) -> None: self._gizmos['speech_bubble'].drag_start = v

    @property
    def _speech_bubble_original_rect(self): return self._gizmos['speech_bubble'].original_rect
    @_speech_bubble_original_rect.setter
    def _speech_bubble_original_rect(self, v) -> None: self._copy_rect_into(self._gizmos['speech_bubble'].original_rect, v)

    # ========================================================================
    # Gizmo dispatch
    # ========================================================================

    def _active_gizmo(self) -> Optional[Gizmo]:
        """현재 활성화된 Gizmo (있으면). 최대 1개만 활성으로 가정."""
        for gizmo in self._gizmos.values():
            if gizmo.active:
                return gizmo
        return None

    def _dispatch_gizmo_release(self, gizmo: Gizmo) -> None:
        """Gizmo 의 mouse up 시 호출되는 release 콜백 — mode 별 X_CHANGED 이벤트 발생.

        text 의 resize 폰트 크기 비례 계산은 mouse_move 중에 일어나 별도 처리.
        모자이크의 event 는 (x, y, GetRight, GetBottom) 을 (x, y, width, height)
        필드에 담는 의미상 어긋남을 유지 (toolbar 가 그 시그니처로 받음).
        """
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        name = gizmo.name
        rect = gizmo.rect

        if name == 'text':
            evt = TextMovedEvent(
                "text_overlay", int(rect.x), int(rect.y),
            )
        elif name == 'crop':
            evt = CropChangedEvent(
                int(rect.x), int(rect.y), int(rect.width), int(rect.height),
            )
        elif name == 'sticker':
            evt = StickerChangedEvent(
                "sticker_overlay",
                int(rect.x), int(rect.y),
                int(rect.width), int(rect.height),
            )
        elif name == 'mosaic':
            evt = MosaicRegionChangedEvent(
                int(rect.x), int(rect.y),
                int(rect.x + rect.width), int(rect.y + rect.height),
            )
        elif name == 'speech_bubble':
            evt = SpeechBubbleChangedEvent(
                int(rect.x), int(rect.y), int(rect.width), int(rect.height),
            )
        else:
            return
        wx.PostEvent(self, evt)

    # ========================================================================
    # 좌표 변환
    # ========================================================================

    def _get_image_rect(self) -> wx.Rect:
        """이미지 사각형 계산 (화면 좌표)"""
        try:
            frames = self._main_window.frames
            if not frames or getattr(frames, 'is_empty', True):
                return wx.Rect(0, 0, 0, 0)

            frame = frames.current_frame if hasattr(frames, 'current_frame') else None
            if not frame:
                return wx.Rect(0, 0, 0, 0)
        except (AttributeError, Exception):
            return wx.Rect(0, 0, 0, 0)

        img_width = int(frame.width * self._zoom)
        img_height = int(frame.height * self._zoom)

        canvas_width = self.GetSize().GetWidth()
        canvas_height = self.GetSize().GetHeight()

        img_x = (canvas_width - img_width) // 2 + self._pan_offset.x
        img_y = (canvas_height - img_height) // 2 + self._pan_offset.y

        return wx.Rect(img_x, img_y, img_width, img_height)

    def _screen_to_image(self, screen_x: int, screen_y: int) -> Tuple[float, float]:
        """화면 좌표 → 이미지 좌표 변환"""
        img_rect = self._get_image_rect()

        img_x = (screen_x - img_rect.x) / self._zoom
        img_y = (screen_y - img_rect.y) / self._zoom

        return (img_x, img_y)

    def _image_to_screen(self, img_x: float, img_y: float) -> Tuple[int, int]:
        """이미지 좌표 → 화면 좌표 변환"""
        img_rect = self._get_image_rect()

        screen_x = int(img_rect.x + img_x * self._zoom)
        screen_y = int(img_rect.y + img_y * self._zoom)

        return (screen_x, screen_y)

    def _image_rect_to_screen(self, img_rect: RectF) -> wx.Rect:
        """이미지 사각형 → 화면 사각형 변환"""
        x1, y1 = self._image_to_screen(img_rect.GetLeft(), img_rect.GetTop())
        x2, y2 = self._image_to_screen(img_rect.GetRight(), img_rect.GetBottom())
        return wx.Rect(x1, y1, x2 - x1, y2 - y1)

    # ========================================================================
    # 페인팅
    # ========================================================================

    def _on_paint(self, event):
        """페인트 이벤트 - wx.BufferedPaintDC로 깜빡임 방지"""
        dc = wx.BufferedPaintDC(self)

        # 배경 지우기
        dc.SetBackground(wx.Brush(self._bg_color))
        dc.Clear()

        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                self._draw_empty_state(dc)
                return

            getattr(frames, 'current_index', 0)
            frame = getattr(frames, 'current_frame', None) if hasattr(frames, 'current_frame') else None
            if not frame:
                return

            img_rect = self._get_image_rect()

            # 체커보드 배경 (투명도 표시)
            draw_checkerboard(dc, img_rect, self._checker_size,
                             self._checker_color1, self._checker_color2)

            # 프레임 이미지 그리기
            self._draw_frame_image(dc, frame, img_rect)

            # 오버레이 그리기 (Phase 2.3b에서 구현)
            self._draw_overlays(dc, img_rect)

            # 펜슬 경로 그리기
            # 원본 PyQt6 로직: 재생 중일 때와 아닐 때 조건이 다름
            is_playing = getattr(self._main_window, '_is_playing', False)
            if is_playing:
                # 재생 중에는 프리뷰 범위 내에서만 표시
                show_pencil = self._should_show_pencil_preview()
            else:
                # 그리기 모드이거나 프리뷰 범위 내일 때 표시
                show_pencil = self._drawing_mode or self._should_show_pencil_preview()

            if show_pencil:
                self._draw_pencil_paths(dc, is_playing)

            # 핸들 그리기 (Phase 2.3c에서 구현)
            self._draw_handles(dc)
        except Exception as e:
            # 크래시 방지: 에러 발생 시 에러 메시지 표시
            dc.SetTextForeground(Colors.DANGER)
            error_text = f"Rendering error: {str(e)}"
            dc.DrawText(error_text, 10, 10)

    def _draw_empty_state(self, dc: wx.DC):
        """빈 캔버스 상태를 작업면 중심에 그린다."""
        size = self.GetSize()
        card_w = min(380, max(260, size.GetWidth() - 96))
        card_h = 132
        x = (size.GetWidth() - card_w) // 2
        y = (size.GetHeight() - card_h) // 2

        dc.SetPen(wx.Pen(Colors.BORDER_SOFT, 1))
        dc.SetBrush(wx.Brush(Colors.BG_CARD))
        dc.DrawRoundedRectangle(x, y, card_w, card_h, 10)

        title = tr("canvas_no_frame_title")
        detail = tr("canvas_no_frame_detail")

        dc.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        dc.SetTextForeground(Colors.TEXT_PRIMARY)
        title_w, _title_h = dc.GetTextExtent(title)
        dc.DrawText(title, x + (card_w - title_w) // 2, y + 38)

        dc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        dc.SetTextForeground(Colors.TEXT_MUTED)
        detail_w, _detail_h = dc.GetTextExtent(detail)
        dc.DrawText(detail, x + (card_w - detail_w) // 2, y + 68)

    def _draw_frame_image(self, dc: wx.DC, frame, img_rect: wx.Rect):
        """프레임 이미지 그리기"""
        try:
            # 스티커/말풍선 모드 활성화 중에는 현재 프레임을 원본 이미지로 표시
            # 이유: 프레임에 베이크된 스티커/말풍선 + 캔버스 오버레이 = 이중 출력 방지
            pil_image = None
            _active_mode_toolbar = None
            if self._sticker_mode:
                _active_mode_toolbar = getattr(self._main_window, '_sticker_toolbar', None)
            elif self._speech_bubble_mode:
                _active_mode_toolbar = getattr(self._main_window, '_speech_bubble_toolbar', None)
            if _active_mode_toolbar and hasattr(_active_mode_toolbar, '_original_images'):
                current_idx = getattr(self._main_window.frames, 'current_index', 0)
                originals = _active_mode_toolbar._original_images
                if 0 <= current_idx < len(originals) and originals[current_idx]:
                    pil_image = originals[current_idx]

            # 프레임을 PIL Image로 가져오기
            if pil_image is None:
                pil_image = frame.image
            if not pil_image:
                return

            # 표시 크기로 스케일
            scaled_width = img_rect.width
            scaled_height = img_rect.height

            if scaled_width <= 0 or scaled_height <= 0:
                return

            # 캐시 키: (프레임 ID, 줌, 표시 크기). LRU OrderedDict — hit 시 항목을
            # MRU 위치로 이동, miss 시 변환 후 LRU 제거.
            cache_key = (id(pil_image), self._zoom, scaled_width, scaled_height)
            cached = self._scaled_bitmap_cache.get(cache_key)
            if cached is not None:
                # MRU 위치로 이동 (move_to_end)
                self._scaled_bitmap_cache.move_to_end(cache_key)
                scaled_bitmap = cached
            else:
                # PIL → wx.Bitmap 변환
                wx_bitmap = pil_to_wx_bitmap(pil_image)
                if not wx_bitmap or not wx_bitmap.IsOk():
                    return

                # 비트맵 스케일 (줌 > 1.0이면 고품질)
                wx_image = wx_bitmap.ConvertToImage()
                quality = wx.IMAGE_QUALITY_HIGH if self._zoom > 1.0 else wx.IMAGE_QUALITY_NORMAL
                scaled_image = wx_image.Scale(scaled_width, scaled_height, quality)
                scaled_bitmap = wx.Bitmap(scaled_image)
                # LRU 추가 + 한도 초과 시 가장 오래된 항목 제거
                self._scaled_bitmap_cache[cache_key] = scaled_bitmap
                while len(self._scaled_bitmap_cache) > self._scaled_bitmap_cache_max:
                    self._scaled_bitmap_cache.popitem(last=False)

            # 비트맵 그리기
            dc.DrawBitmap(scaled_bitmap, img_rect.x, img_rect.y, True)

        except Exception:
            pass

    def _draw_overlays(self, dc: wx.DC, img_rect: wx.Rect):
        """모든 오버레이 그리기 (Phase 2.3b에서 구현)"""
        # 텍스트 오버레이
        if self._text_edit_mode and not self._text_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._text_rect)
            self._draw_text_overlay(dc, screen_rect)

        # 크롭 오버레이
        if self._crop_mode and not self._crop_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._crop_rect)
            self._draw_crop_overlay(dc, screen_rect, img_rect)

        # 스티커 오버레이
        if self._sticker_mode and not self._sticker_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._sticker_rect)
            self._draw_sticker_overlay(dc, screen_rect)

        # 모자이크 오버레이
        if self._mosaic_mode and not self._mosaic_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._mosaic_rect)
            self._draw_mosaic_overlay(dc, screen_rect)

        # 말풍선 오버레이
        if self._speech_bubble_mode and not self._speech_bubble_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._speech_bubble_rect)
            self._draw_speech_bubble_overlay(dc, screen_rect)

    def _draw_text_overlay(self, dc: wx.DC, screen_rect: wx.Rect):
        """텍스트 편집 오버레이."""
        dc.SetPen(wx.Pen(Colors.OVERLAY_TEXT_ACCENT, 2, wx.PENSTYLE_SHORT_DASH))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(screen_rect)

    def _draw_crop_overlay(self, dc: wx.DC, screen_rect: wx.Rect, img_rect: wx.Rect):
        """크롭 오버레이."""
        dc.SetPen(wx.Pen(Colors.CROP_ACCENT, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(screen_rect)

    def _draw_sticker_overlay(self, dc: wx.DC, screen_rect: wx.Rect):
        """스티커 오버레이 (실제 도형 + 선택 박스)

        원본 PyQt6 로직: 스티커 툴바에서 선택된 도형을 실제로 그림
        """
        # 스티커 툴바에서 정보 가져오기
        sticker_toolbar = None
        if hasattr(self._main_window, '_sticker_toolbar'):
            sticker_toolbar = self._main_window._sticker_toolbar

        if sticker_toolbar:
            try:
                # 도형 정보 가져오기
                shape_idx = sticker_toolbar._shape_combo.GetSelection()
                if 0 <= shape_idx < len(sticker_toolbar.SHAPES):
                    shape_type = sticker_toolbar.SHAPES[shape_idx][1]
                    fill_color = sticker_toolbar._fill_color
                    outline_color = wx.Colour(Colors.TEXT_PRIMARY.Red(), Colors.TEXT_PRIMARY.Green(), Colors.TEXT_PRIMARY.Blue(), 210)

                    # 도형 그리기 (원본 PyQt6 방식)
                    self._draw_sticker_shape(dc, screen_rect, shape_type, fill_color, outline_color)
            except Exception:
                pass

        # 선택 박스 그리기
        dc.SetPen(wx.Pen(Colors.DANGER, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(screen_rect)

    def _draw_sticker_shape(self, dc: wx.DC, rect: wx.Rect, shape_type: str,
                           fill_color: wx.Colour, outline_color: wx.Colour):
        """스티커 도형 실제 그리기 (원본 PyQt6 로직)"""
        x, y, w, h = rect.x, rect.y, rect.width, rect.height

        # 펜과 브러시 설정
        dc.SetPen(wx.Pen(outline_color, 2))
        dc.SetBrush(wx.Brush(fill_color))

        if shape_type == "rectangle":
            dc.DrawRectangle(x, y, w, h)

        elif shape_type == "ellipse":
            dc.DrawEllipse(x, y, w, h)

        elif shape_type == "triangle":
            points = [
                wx.Point(x + w // 2, y),
                wx.Point(x, y + h),
                wx.Point(x + w, y + h)
            ]
            dc.DrawPolygon(points)

        elif shape_type == "star":
            cx, cy = x + w / 2, y + h / 2
            outer_r = min(w, h) / 2
            inner_r = outer_r * 0.4

            points = []
            for i in range(10):
                angle = math.pi / 2 + i * math.pi / 5
                r = outer_r if i % 2 == 0 else inner_r
                px = cx + r * math.cos(angle)
                py = cy - r * math.sin(angle)
                points.append(wx.Point(int(px), int(py)))
            dc.DrawPolygon(points)

        elif shape_type == "arrow":
            points = [
                wx.Point(int(x), int(y + h / 3)),
                wx.Point(int(x + w * 2 / 3), int(y + h / 3)),
                wx.Point(int(x + w * 2 / 3), int(y)),
                wx.Point(int(x + w), int(y + h / 2)),
                wx.Point(int(x + w * 2 / 3), int(y + h)),
                wx.Point(int(x + w * 2 / 3), int(y + h * 2 / 3)),
                wx.Point(int(x), int(y + h * 2 / 3)),
            ]
            dc.DrawPolygon(points)

        elif shape_type == "heart":
            cx, cy = x + w / 2, y + h / 2
            points = []
            for t in range(0, 360, 5):
                angle = math.radians(t)
                px = 16 * (math.sin(angle) ** 3)
                py = -(13 * math.cos(angle) - 5 * math.cos(2 * angle) -
                       2 * math.cos(3 * angle) - math.cos(4 * angle))

                px_scaled = cx + px * w / 35
                py_scaled = cy + py * h / 35
                points.append(wx.Point(int(px_scaled), int(py_scaled)))
            dc.DrawPolygon(points)

    def _draw_mosaic_overlay(self, dc: wx.DC, screen_rect: wx.Rect):
        """모자이크 오버레이."""
        dc.SetPen(wx.Pen(Colors.MOSAIC_ACCENT, 2, wx.PENSTYLE_SHORT_DASH))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRectangle(screen_rect)

    def _draw_speech_bubble_overlay(self, dc: wx.DC, screen_rect: wx.Rect):
        """말풍선 오버레이 — 스티커와 동일 구조 (버블만 그림, 원본 합성 없음)"""
        toolbar = getattr(self._main_window, '_speech_bubble_toolbar', None)
        if toolbar and hasattr(toolbar, '_create_bubble'):
            try:
                bubble_img = toolbar._create_bubble()
                if bubble_img:
                    display_w = max(1, screen_rect.width)
                    display_h = max(1, screen_rect.height)
                    resized = bubble_img.resize((display_w, display_h), Image.Resampling.LANCZOS)
                    wx_bmp = pil_to_wx_bitmap(resized)
                    if wx_bmp and wx_bmp.IsOk():
                        dc.DrawBitmap(wx_bmp, screen_rect.x, screen_rect.y, True)
            except Exception:
                pass

        # 선택 박스
        dc.SetPen(wx.Pen(Colors.BUBBLE_ACCENT, 2))
        dc.SetBrush(wx.TRANSPARENT_BRUSH)
        dc.DrawRoundedRectangle(screen_rect.x, screen_rect.y,
                               screen_rect.width, screen_rect.height, 10)

    def _draw_handles(self, dc: wx.DC):
        """리사이즈 핸들 그리기 (Phase 2.3c에서 구현)"""
        handle_fill = Colors.TEXT_PRIMARY
        handle_border = Colors.BORDER_FOCUS

        # 텍스트 모드 핸들
        if self._text_edit_mode and not self._text_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._text_rect)
            handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

            for _handle_name, handle_rect in handles.items():
                draw_handle(dc,
                           handle_rect.x + handle_rect.width // 2,
                           handle_rect.y + handle_rect.height // 2,
                           self.HANDLE_SIZE,
                           fill_color=handle_fill,
                           border_color=handle_border)

        # 크롭 모드 핸들 (8개: 4 코너 + 4 엣지)
        if self._crop_mode and not self._crop_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._crop_rect)
            handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

            for _handle_name, handle_rect in handles.items():
                draw_handle(dc,
                           handle_rect.x + handle_rect.width // 2,
                           handle_rect.y + handle_rect.height // 2,
                           self.HANDLE_SIZE,
                           fill_color=handle_fill,
                           border_color=Colors.CROP_ACCENT)

        # 스티커 모드 핸들 (4개: 4 코너)
        if self._sticker_mode and not self._sticker_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._sticker_rect)
            handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

            # 스티커는 코너 핸들만 표시 (원본 PyQt6 방식)
            for handle_name, handle_rect in handles.items():
                if handle_name in ['tl', 'tr', 'bl', 'br']:
                    draw_handle(dc,
                               handle_rect.x + handle_rect.width // 2,
                               handle_rect.y + handle_rect.height // 2,
                               self.HANDLE_SIZE,
                               fill_color=handle_fill,
                               border_color=Colors.DANGER)

        # 모자이크 모드 핸들 (4개: 4 코너)
        if self._mosaic_mode and not self._mosaic_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._mosaic_rect)
            handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

            for handle_name, handle_rect in handles.items():
                if handle_name in ['tl', 'tr', 'bl', 'br']:
                    draw_handle(dc,
                               handle_rect.x + handle_rect.width // 2,
                               handle_rect.y + handle_rect.height // 2,
                               self.HANDLE_SIZE,
                               fill_color=handle_fill,
                               border_color=Colors.MOSAIC_ACCENT)

        # 말풍선 모드 핸들 (4개: 4 코너)
        if self._speech_bubble_mode and not self._speech_bubble_rect.IsEmpty():
            screen_rect = self._image_rect_to_screen(self._speech_bubble_rect)
            handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

            for handle_name, handle_rect in handles.items():
                if handle_name in ['tl', 'tr', 'bl', 'br']:
                    draw_handle(dc,
                               handle_rect.x + handle_rect.width // 2,
                               handle_rect.y + handle_rect.height // 2,
                               self.HANDLE_SIZE,
                               fill_color=handle_fill,
                               border_color=Colors.BUBBLE_ACCENT)

    def _draw_pencil_paths(self, dc: wx.DC, is_playing: bool = False):
        """펜슬 경로 그리기"""
        # Auto Animation 모드일 때는 재생 중일 때만 부분 경로 사용 (원본 PyQt6 로직)
        if self._auto_animation_mode and is_playing:
            progress = self._get_auto_animation_progress()
            paths_to_draw = self._get_partial_paths(progress)
        else:
            # 그리기 모드이거나 재생 중이 아닐 때는 모든 경로 표시
            paths_to_draw = self._drawing_paths

        # 완성된 경로들 그리기 (이미지 좌표 → 화면 좌표 변환)
        for path_points, color, width in paths_to_draw:
            if len(path_points) < 2:
                continue

            dc.SetPen(wx.Pen(color, width, wx.PENSTYLE_SOLID))

            # 연속된 점들 사이에 선 그리기
            for i in range(len(path_points) - 1):
                sx1, sy1 = self._image_to_screen(path_points[i][0], path_points[i][1])
                sx2, sy2 = self._image_to_screen(path_points[i+1][0], path_points[i+1][1])
                dc.DrawLine(sx1, sy1, sx2, sy2)

        # 현재 그리고 있는 경로 (이미 이미지 좌표)
        if self._is_drawing and len(self._current_path) > 1:
            dc.SetPen(wx.Pen(self._pencil_color, self._pencil_width))

            for i in range(len(self._current_path) - 1):
                sx1, sy1 = self._image_to_screen(self._current_path[i][0], self._current_path[i][1])
                sx2, sy2 = self._image_to_screen(self._current_path[i+1][0], self._current_path[i+1][1])
                dc.DrawLine(sx1, sy1, sx2, sy2)

    # ========================================================================
    # 마우스 이벤트
    # ========================================================================

    def _on_mouse_wheel(self, event):
        """마우스 휠로 줌"""
        rotation = event.GetWheelRotation()

        if rotation > 0:
            self.zoom_in()
        elif rotation < 0:
            self.zoom_out()

        event.Skip()

    def _on_middle_down(self, event):
        """중간 버튼으로 팬 시작"""
        self._is_panning = True
        self._last_mouse_pos = event.GetPosition()
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        event.Skip()

    def _on_middle_up(self, event):
        """중간 버튼 팬 종료"""
        self._is_panning = False
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        event.Skip()

    def _on_left_down(self, event):
        """왼쪽 버튼 클릭 — 드로잉 또는 활성 Gizmo 의 핸들/드래그 시작."""
        pos = event.GetPosition()

        # 드로잉 모드 (이미지 좌표로 저장하여 줌/패닝 후에도 정확한 위치 유지)
        if self._drawing_mode:
            self._is_drawing = True
            img_x, img_y = self._screen_to_image(pos.x, pos.y)
            self._current_path = [(img_x, img_y)]
            self.Refresh()
            return

        # 활성 Gizmo dispatch — 5 mode (text/crop/sticker/mosaic/speech_bubble) 의
        # 핸들 hit-test 와 드래그 시작 로직이 모두 여기로 통합. 이전엔 mode 당
        # 별도 분기 25줄씩, 5×25 = ~125줄이 산재하여 한 mode 의 회귀 (예: 모자이크
        # PyQt6 시그널 잔재) 가 다른 mode 에 전파되지 않았다.
        gizmo = self._active_gizmo()
        if gizmo:
            screen_rect = self._image_rect_to_screen(gizmo.rect)
            handle = gizmo.hit_handle(screen_rect, pos, self.HANDLE_SIZE)
            if handle:
                gizmo.begin_resize(pos, handle)
                # text resize 시 현재 폰트 크기 저장 — mouse_move 의 비례 계산용
                if gizmo.name == 'text':
                    self._text_resize_start_size = self._text_current_size
                self.SetCursor(get_cursor_for_handle(handle))
                return
            if gizmo.is_point_inside(screen_rect, pos):
                gizmo.begin_drag(pos)
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZING))
                return

        event.Skip()

    def _on_left_up(self, event):
        """왼쪽 버튼 릴리즈 — 드로잉 완료 또는 활성 Gizmo 의 인터랙션 종료."""
        # 드로잉 완료
        if self._is_drawing:
            self._is_drawing = False

            # 완성된 경로 저장 (이미지 좌표 튜플)
            if len(self._current_path) > 1:
                self._drawing_paths.append((
                    self._current_path.copy(),
                    wx.Colour(self._pencil_color),
                    self._pencil_width
                ))

            self._current_path = []
            self.Refresh()

            # 이벤트 발생
            evt = DrawingFinishedEvent()
            wx.PostEvent(self, evt)

        # 활성 Gizmo 인터랙션 종료 — end_interaction 이 on_release 콜백을 호출하고
        # 콜백 (`_dispatch_gizmo_release`) 이 mode 에 맞는 X_CHANGED 이벤트를 발생.
        gizmo = self._active_gizmo()
        if gizmo:
            gizmo.end_interaction()

        event.Skip()

    def _on_mouse_move(self, event):
        """마우스 이동 — 팬/드로잉/활성 Gizmo 의 드래그·리사이즈/호버 커서."""
        pos = event.GetPosition()

        # 팬 처리
        if self._is_panning and event.MiddleIsDown():
            current_pos = pos
            delta = current_pos - self._last_mouse_pos

            self._pan_offset.x += delta.x
            self._pan_offset.y += delta.y

            self._last_mouse_pos = current_pos
            self.Refresh()
            event.Skip()
            return

        # 드로잉 중 (이미지 좌표로 저장)
        if self._is_drawing and event.LeftIsDown():
            img_x, img_y = self._screen_to_image(pos.x, pos.y)
            self._current_path.append((img_x, img_y))
            self.Refresh()
            return

        # 활성 Gizmo 의 드래그/리사이즈 — 5 mode 통합. 이전엔 mode 당 ~20줄
        # 블록이 5번 (~120줄) 산재했고, 한 mode 의 회귀가 다른 mode 에 전파
        # 안 됐다. 이제 Gizmo.apply_drag/apply_resize 가 단일 출처.
        gizmo = self._active_gizmo()
        if gizmo and event.LeftIsDown():
            if gizmo.dragging:
                gizmo.apply_drag(pos, self._zoom)
                self.Refresh()
                return
            if gizmo.resizing:
                gizmo.apply_resize(pos, self._zoom)
                # text 모드는 리사이즈 시 폰트 크기 비례 계산 + TextResizedEvent
                # 발생 — 다른 mode 와 다른 유일한 부가 동작.
                if gizmo.name == 'text':
                    base_width = gizmo.original_rect.width
                    if base_width <= 0:
                        base_width = gizmo.rect.width if gizmo.rect.width > 0 else 1.0
                    scale = gizmo.rect.width / base_width
                    new_font_size = max(8, int(self._text_resize_start_size * scale))
                    self._text_current_size = new_font_size
                    evt = TextResizedEvent("text_overlay", new_font_size)
                    wx.PostEvent(self, evt)
                self.Refresh()
                return

        # 커서 변경 (호버 상태)
        self._update_cursor_for_hover(pos)

        event.Skip()

    def _apply_resize(self, current_pos: wx.Point, start_pos: wx.Point,
                     handle: str, original_rect: RectF, target_rect: RectF):
        """리사이즈 적용 (핸들에 따라)"""
        delta = current_pos - start_pos
        img_delta_x = delta.x / self._zoom
        img_delta_y = delta.y / self._zoom

        # 각 핸들에 따른 리사이즈 로직
        if handle == 'tl':  # Top-left
            target_rect.x = original_rect.x + img_delta_x
            target_rect.y = original_rect.y + img_delta_y
            target_rect.width = original_rect.width - img_delta_x
            target_rect.height = original_rect.height - img_delta_y
        elif handle == 'tr':  # Top-right
            target_rect.y = original_rect.y + img_delta_y
            target_rect.width = original_rect.width + img_delta_x
            target_rect.height = original_rect.height - img_delta_y
        elif handle == 'bl':  # Bottom-left
            target_rect.x = original_rect.x + img_delta_x
            target_rect.width = original_rect.width - img_delta_x
            target_rect.height = original_rect.height + img_delta_y
        elif handle == 'br':  # Bottom-right
            target_rect.width = original_rect.width + img_delta_x
            target_rect.height = original_rect.height + img_delta_y
        elif handle == 't':  # Top edge
            target_rect.y = original_rect.y + img_delta_y
            target_rect.height = original_rect.height - img_delta_y
        elif handle == 'b':  # Bottom edge
            target_rect.height = original_rect.height + img_delta_y
        elif handle == 'l':  # Left edge
            target_rect.x = original_rect.x + img_delta_x
            target_rect.width = original_rect.width - img_delta_x
        elif handle == 'r':  # Right edge
            target_rect.width = original_rect.width + img_delta_x

        # 최소 크기 제한
        if target_rect.width < 10:
            target_rect.width = 10
        if target_rect.height < 10:
            target_rect.height = 10

    def _update_cursor_for_hover(self, pos: wx.Point):
        """호버 상태에서 커서 업데이트 — 활성 Gizmo dispatch + 기본 커서."""
        gizmo = self._active_gizmo()
        if gizmo:
            screen_rect = self._image_rect_to_screen(gizmo.rect)
            handle = gizmo.hit_handle(screen_rect, pos, self.HANDLE_SIZE)
            if handle:
                self.SetCursor(get_cursor_for_handle(handle))
                return
            if gizmo.is_point_inside(screen_rect, pos):
                self.SetCursor(wx.Cursor(wx.CURSOR_SIZING))
                return

        # 기본 커서
        if self._drawing_mode:
            self.SetCursor(wx.Cursor(wx.CURSOR_CROSS))
        else:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))

    def _on_key_down(self, event):
        """키보드 이벤트"""
        keycode = event.GetKeyCode()

        # Esc: 현재 모드 취소
        if keycode == wx.WXK_ESCAPE:
            if self._drawing_mode:
                self.stop_drawing_mode()
            elif self._text_edit_mode:
                self.stop_text_edit_mode()
            elif self._crop_mode:
                self.stop_crop_mode()
            # ... 다른 모드들

        event.Skip()

    def _on_size(self, event):
        """크기 변경"""
        self.Refresh()
        event.Skip()

    # ========================================================================
    # 핸들 및 히트 테스트 (Phase 2.3c)
    # ========================================================================

    def _get_text_handle_at(self, pos: wx.Point) -> Optional[str]:
        """텍스트 핸들 위치 확인"""
        if not self._text_edit_mode or self._text_rect.IsEmpty():
            return None

        screen_rect = self._image_rect_to_screen(self._text_rect)
        handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

        for handle_name, handle_rect in handles.items():
            if handle_rect.Contains(pos):
                return handle_name

        return None

    def _get_crop_handle_at(self, pos: wx.Point) -> Optional[str]:
        """크롭 핸들 위치 확인 (8개: 4 코너 + 4 엣지)"""
        if not self._crop_mode or self._crop_rect.IsEmpty():
            return None

        screen_rect = self._image_rect_to_screen(self._crop_rect)
        handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)

        for handle_name, handle_rect in handles.items():
            if handle_rect.Contains(pos):
                return handle_name

        return None

    _CORNER_HANDLES = {'tl', 'tr', 'bl', 'br'}

    def _get_handle_at_corners_only(self, screen_rect, pos: wx.Point) -> Optional[str]:
        """코너 핸들(4개)만 히트테스트 (표시되는 핸들과 일치)"""
        handles = get_handle_rects(screen_rect, self.HANDLE_SIZE)
        for handle_name, handle_rect in handles.items():
            if handle_name in self._CORNER_HANDLES and handle_rect.Contains(pos):
                return handle_name
        return None

    def _get_sticker_handle_at(self, pos: wx.Point) -> Optional[str]:
        """스티커 핸들 위치 확인"""
        if not self._sticker_mode or self._sticker_rect.IsEmpty():
            return None
        screen_rect = self._image_rect_to_screen(self._sticker_rect)
        return self._get_handle_at_corners_only(screen_rect, pos)

    def _get_mosaic_handle_at(self, pos: wx.Point) -> Optional[str]:
        """모자이크 핸들 위치 확인"""
        if not self._mosaic_mode or self._mosaic_rect.IsEmpty():
            return None
        screen_rect = self._image_rect_to_screen(self._mosaic_rect)
        return self._get_handle_at_corners_only(screen_rect, pos)

    def _get_speech_bubble_handle_at(self, pos: wx.Point) -> Optional[str]:
        """말풍선 핸들 위치 확인"""
        if not self._speech_bubble_mode or self._speech_bubble_rect.IsEmpty():
            return None
        screen_rect = self._image_rect_to_screen(self._speech_bubble_rect)
        return self._get_handle_at_corners_only(screen_rect, pos)

    def _is_point_in_text_rect(self, pos: wx.Point) -> bool:
        """포인트가 텍스트 사각형 내부에 있는지 확인"""
        if not self._text_edit_mode or self._text_rect.IsEmpty():
            return False

        screen_rect = self._image_rect_to_screen(self._text_rect)
        return screen_rect.Contains(pos)

    def _is_point_in_crop_rect(self, pos: wx.Point) -> bool:
        """포인트가 크롭 사각형 내부에 있는지 확인"""
        if not self._crop_mode or self._crop_rect.IsEmpty():
            return False

        screen_rect = self._image_rect_to_screen(self._crop_rect)
        return screen_rect.Contains(pos)

    def _is_point_in_sticker_rect(self, pos: wx.Point) -> bool:
        """포인트가 스티커 사각형 내부에 있는지 확인"""
        if not self._sticker_mode or self._sticker_rect.IsEmpty():
            return False

        screen_rect = self._image_rect_to_screen(self._sticker_rect)
        return screen_rect.Contains(pos)

    def _is_point_in_mosaic_rect(self, pos: wx.Point) -> bool:
        """포인트가 모자이크 사각형 내부에 있는지 확인"""
        if not self._mosaic_mode or self._mosaic_rect.IsEmpty():
            return False

        screen_rect = self._image_rect_to_screen(self._mosaic_rect)
        return screen_rect.Contains(pos)

    def _is_point_in_speech_bubble_rect(self, pos: wx.Point) -> bool:
        """포인트가 말풍선 사각형 내부에 있는지 확인"""
        if not self._speech_bubble_mode or self._speech_bubble_rect.IsEmpty():
            return False

        screen_rect = self._image_rect_to_screen(self._speech_bubble_rect)
        return screen_rect.Contains(pos)

    # ========================================================================
    # 펜슬 그리기 모드
    # ========================================================================

    def start_drawing_mode(self, color: wx.Colour, width: int):
        """펜슬 그리기 모드 시작"""
        self._drawing_mode = True
        self._pencil_color = color
        self._pencil_width = width
        self._current_path = []
        self._drawing_paths = []
        self.SetCursor(wx.Cursor(wx.CURSOR_CROSS))

        evt = DrawingStartedEvent()
        wx.PostEvent(self, evt)

        self.Refresh()

    def update_pencil_settings(self, color: wx.Colour, width: int):
        """펜슬 설정 업데이트 (경로는 유지)"""
        self._pencil_color = color
        self._pencil_width = width
        self.Refresh()

    def stop_drawing_mode(self):
        """펜슬 그리기 모드 종료"""
        self._drawing_mode = False
        self._is_drawing = False
        self._current_path = []
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def clear_drawings(self):
        """모든 그린 선 지우기"""
        self._drawing_paths = []
        self._current_path = []
        self.Refresh()

    def get_drawing_paths(self) -> List[Tuple[List[Tuple[float, float]], Tuple[int, int, int, int], int]]:
        """그린 경로들 반환 (이미 이미지 좌표계로 저장됨)"""
        result = []
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return result

            for path_points, color, width in self._drawing_paths:
                # wx.Colour를 RGBA 튜플로 변환
                rgba = (color.Red(), color.Green(), color.Blue(), color.Alpha())
                result.append((list(path_points), rgba, width))
        except Exception:
            pass

        return result

    @property
    def is_drawing_mode(self) -> bool:
        return self._drawing_mode

    def set_pencil_preview_range(self, start_index: int, frame_count: int,
                                  auto_animation: bool = False, target_frames: list = None):
        """펜슬 프리뷰 범위 설정"""
        self._pencil_preview_start = start_index
        self._pencil_preview_count = frame_count
        self._auto_animation_mode = auto_animation

        if auto_animation and target_frames:
            self._auto_animation_frames = sorted(target_frames)
        elif auto_animation:
            self._auto_animation_frames = list(range(start_index, start_index + frame_count))
        else:
            self._auto_animation_frames = []

        self.Refresh()

    def _should_show_pencil_preview(self) -> bool:
        """현재 프레임이 펜슬 프리뷰 범위 내인지 확인"""
        try:
            if not self._drawing_paths:
                return False

            frames = getattr(self._main_window, 'frames', None)
            if not frames:
                return False

            current = getattr(frames, 'current_index', 0)

            # Auto Animation 모드
            if self._auto_animation_mode and self._auto_animation_frames:
                return current in self._auto_animation_frames

            # 일반 모드
            start = self._pencil_preview_start
            end = start + self._pencil_preview_count
            return start <= current < end
        except Exception:
            return False

    def _get_auto_animation_progress(self) -> float:
        """Auto Animation 진행률 (0.0 ~ 1.0)"""
        try:
            if not self._auto_animation_mode or not self._auto_animation_frames:
                return 1.0

            frames = getattr(self._main_window, 'frames', None)
            if not frames:
                return 1.0

            current = getattr(frames, 'current_index', 0)
            if current not in self._auto_animation_frames:
                return 0.0

            frame_idx = self._auto_animation_frames.index(current)
            num_frames = len(self._auto_animation_frames)
            progress = (frame_idx + 1) / num_frames

            return progress
        except Exception:
            return 1.0

    def _get_partial_paths(self, progress: float):
        """진행률에 따른 부분 경로 반환"""
        if progress >= 1.0:
            return self._drawing_paths

        if progress <= 0.0:
            return []

        # 총 포인트 수 계산
        total_points = sum(len(path_points) for path_points, _, _ in self._drawing_paths)
        target_points = int(total_points * progress)

        if target_points == 0:
            return []

        # 부분 경로 생성
        partial_paths = []
        accumulated_points = 0

        for path_points, color, width in self._drawing_paths:
            path_len = len(path_points)

            if accumulated_points >= target_points:
                break

            if accumulated_points + path_len <= target_points:
                # 전체 경로 포함
                partial_paths.append((path_points, color, width))
                accumulated_points += path_len
            else:
                # 일부만 포함
                remaining = target_points - accumulated_points
                if remaining > 0:
                    partial_points = path_points[:remaining]
                    partial_paths.append((partial_points, color, width))
                break

        return partial_paths

    # ========================================================================
    # 텍스트 편집 모드 (Phase 2.3b/2.3c에서 구현)
    # ========================================================================

    def start_text_edit_mode(self, x: int, y: int, width: int, height: int, font_size: int):
        """텍스트 편집 모드 시작"""
        self._text_edit_mode = True
        self._text_rect = RectF(x, y, width, height)
        self._text_current_size = font_size
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def update_text_rect(self, x: int, y: int, width: int, height: int):
        """텍스트 영역 업데이트"""
        self._text_rect = RectF(x, y, width, height)
        self.Refresh()

    def stop_text_edit_mode(self):
        """텍스트 편집 모드 종료"""
        self._text_edit_mode = False
        self._text_dragging = False
        self._text_resizing = False
        self._text_rect = RectF()
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    # ========================================================================
    # 크롭 모드 (Phase 2.3b/2.3c에서 구현)
    # ========================================================================

    def start_crop_mode(self, x: int, y: int, w: int, h: int):
        """크롭 모드 시작"""
        self._crop_mode = True
        self._crop_rect = RectF(x, y, w, h)
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def update_crop_rect(self, x: int, y: int, w: int, h: int):
        """크롭 영역 업데이트"""
        self._crop_rect = RectF(x, y, w, h)
        self.Refresh()

    def stop_crop_mode(self):
        """크롭 모드 종료"""
        self._crop_mode = False
        self._crop_dragging = False
        self._crop_resizing = False
        self._crop_rect = RectF()
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    # ========================================================================
    # 스티커 모드 (Phase 2.3b/2.3c에서 구현)
    # ========================================================================

    def start_sticker_mode(self, x: int, y: int, size: int):
        """스티커 모드 시작"""
        self._sticker_mode = True
        self._sticker_rect = RectF(x, y, size, size)
        self._sticker_original_size = size
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def update_sticker_rect(self, x: int, y: int, size: int):
        """스티커 영역 업데이트"""
        self._sticker_rect = RectF(x, y, size, size)
        self.Refresh()

    def stop_sticker_mode(self):
        """스티커 모드 종료"""
        self._sticker_mode = False
        self._sticker_dragging = False
        self._sticker_resizing = False
        self._sticker_rect = RectF()
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    # ========================================================================
    # 모자이크 모드 (Phase 2.3b/2.3c에서 구현)
    # ========================================================================

    def start_mosaic_mode(self, x1: int, y1: int, x2: int, y2: int):
        """모자이크 모드 시작"""
        self._mosaic_mode = True
        self._mosaic_rect = RectF(x1, y1, x2 - x1, y2 - y1)
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def update_mosaic_region(self, x1: int, y1: int, x2: int, y2: int):
        """모자이크 영역 업데이트"""
        self._mosaic_rect = RectF(x1, y1, x2 - x1, y2 - y1)
        self.Refresh()

    def stop_mosaic_mode(self):
        """모자이크 모드 종료"""
        self._mosaic_mode = False
        self._mosaic_dragging = False
        self._mosaic_resizing = False
        self._mosaic_rect = RectF()
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    # ========================================================================
    # 말풍선 모드 (Phase 2.3b/2.3c에서 구현)
    # ========================================================================

    def start_speech_bubble_mode(self, x: int, y: int, w: int, h: int):
        """말풍선 모드 시작"""
        self._speech_bubble_mode = True
        self._speech_bubble_rect = RectF(x, y, w, h)
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def update_speech_bubble_rect(self, x: int, y: int, w: int, h: int):
        """말풍선 영역 업데이트"""
        self._speech_bubble_rect = RectF(x, y, w, h)
        self.Refresh()

    def stop_speech_bubble_mode(self):
        """말풍선 모드 종료"""
        self._speech_bubble_mode = False
        self._speech_bubble_dragging = False
        self._speech_bubble_resizing = False
        self._speech_bubble_rect = RectF()
        self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()
