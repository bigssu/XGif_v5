"""
IconToolbar - 모던 플랫 아이콘 툴바 (wxPython)
GraphicsContext 기반 owner-draw, 8px 라운디드 코너, 호버/프레스/액티브 상태
"""
import wx
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from .main_window import MainWindow
    from ..utils.translations import Translations

try:
    from .icon_utils_wx import IconFactory, IconColors
    from .style_constants_wx import Colors, Sizes, Spacing
except ImportError:
    IconFactory = None
    IconColors = None
    Colors = None
    Sizes = None
    Spacing = None

# 라운디드 코너 반경
_CORNER_RADIUS = 8


class FlatIconButton(wx.Control):
    """모던 플랫 아이콘 버튼 (owner-draw).

    wx.GraphicsContext로 라운디드 렉트를 그려 플랫한 모던 스타일을 구현합니다.
    상태: normal / hovered / pressed / active / disabled
    """

    def __init__(self, icon_type: str, tooltip: str, parent=None, size=(62, 62)):
        super().__init__(parent, wx.ID_ANY, pos=wx.DefaultPosition, size=size,
                         style=wx.BORDER_NONE)
        self._icon_type = icon_type
        self._is_active = False
        self._is_hovered = False
        self._pressed = False
        self._enabled = True
        self._bitmap: Optional[wx.Bitmap] = None

        # 색상
        self._bg_normal = Colors.BG_PRIMARY if Colors else wx.Colour(32, 32, 32)
        self._bg_hover = Colors.ICON_BTN_HOVER if Colors else wx.Colour(55, 55, 55)
        self._bg_pressed = Colors.ICON_BTN_PRESSED if Colors else wx.Colour(42, 42, 42)
        self._bg_active = wx.Colour(0, 120, 212, 60)
        self._bg_disabled = wx.Colour(32, 32, 32)

        self.SetToolTip(tooltip)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self._skip_auto_theme = True

        # 아이콘 비트맵 생성
        self._create_icon()

        # 이벤트
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    def _create_icon(self):
        """아이콘 비트맵 생성"""
        if IconFactory:
            self._bitmap = IconFactory.create_bitmap(self._icon_type, 39)

    # --- 공개 API ---

    def set_active(self, active: bool):
        """활성 상태 설정"""
        self._is_active = active
        self.Refresh()

    def Enable(self, enable=True):
        self._enabled = enable
        super().Enable(enable)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND if enable else wx.CURSOR_ARROW))
        self.Refresh()

    def Disable(self):
        self.Enable(False)

    def IsEnabled(self):
        return self._enabled

    # --- 내부 이벤트 ---

    def _on_enter(self, event):
        if self._enabled:
            self._is_hovered = True
            self.Refresh()

    def _on_leave(self, event):
        self._is_hovered = False
        self._pressed = False
        self.Refresh()

    def _on_left_down(self, event):
        if self._enabled:
            self._pressed = True
            self.CaptureMouse()
            self.Refresh()

    def _on_left_up(self, event):
        had_capture = self.HasCapture()
        if had_capture:
            self.ReleaseMouse()
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        if was_pressed and self._enabled and self._is_hovered:
            evt = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
            evt.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(evt)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return

        bmp = wx.Bitmap(w, h)
        memdc = wx.MemoryDC(bmp)

        # 부모 배경으로 클리어
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else self._bg_normal
        memdc.SetBackground(wx.Brush(parent_bg))
        memdc.Clear()

        gc = wx.GraphicsContext.Create(memdc)
        if gc:
            # 배경색 결정
            if not self._enabled:
                bg = self._bg_disabled
            elif self._is_active:
                bg = self._bg_active
            elif self._pressed:
                bg = self._bg_pressed
            elif self._is_hovered:
                bg = self._bg_hover
            else:
                bg = self._bg_normal

            # 라운디드 렉트 배경 (약간 패딩)
            pad = 2
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRoundedRectangle(pad, pad, w - pad * 2, h - pad * 2, _CORNER_RADIUS)

            # 아이콘 그리기 (중앙)
            if self._bitmap and self._bitmap.IsOk():
                bw, bh = self._bitmap.GetWidth(), self._bitmap.GetHeight()
                ix = (w - bw) / 2
                iy = (h - bh) / 2
                if not self._enabled:
                    # 비활성화: 반투명 처리 (캐시하여 매 paint마다 재계산 방지)
                    if not hasattr(self, '_disabled_bitmap_cache') or self._disabled_bitmap_cache is None:
                        img = self._bitmap.ConvertToImage()
                        if img.HasAlpha():
                            for y_pos in range(img.GetHeight()):
                                for x_pos in range(img.GetWidth()):
                                    a = img.GetAlpha(x_pos, y_pos)
                                    img.SetAlpha(x_pos, y_pos, a // 3)
                        self._disabled_bitmap_cache = wx.Bitmap(img)
                    gc.DrawBitmap(self._disabled_bitmap_cache, ix, iy, bw, bh)
                else:
                    gc.DrawBitmap(self._bitmap, ix, iy, bw, bh)

        memdc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bmp, 0, 0, False)


class ToolSeparator(wx.Control):
    """툴바 구분선 (owner-draw, 라운디드 캡)"""

    def __init__(self, parent=None):
        super().__init__(parent, wx.ID_ANY, size=(8, 50), style=wx.BORDER_NONE)
        self.SetMinSize((8, 50))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return

        bmp = wx.Bitmap(w, h)
        memdc = wx.MemoryDC(bmp)

        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else wx.Colour(32, 32, 32)
        memdc.SetBackground(wx.Brush(parent_bg))
        memdc.Clear()

        gc = wx.GraphicsContext.Create(memdc)
        if gc:
            sep_color = Colors.BORDER if Colors else wx.Colour(60, 60, 60)
            gc.SetBrush(wx.Brush(sep_color))
            gc.SetPen(wx.TRANSPARENT_PEN)
            # 세로 라운디드 바
            bar_w = 2
            bar_h = h - 12
            x = (w - bar_w) / 2
            y = 6
            gc.DrawRoundedRectangle(x, y, bar_w, bar_h, 1)

        memdc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bmp, 0, 0, False)


class IconToolbar(wx.Panel):
    """모던 플랫 아이콘 툴바"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._all_buttons = []
        self._active_button: Optional[FlatIconButton] = None
        self._setup_ui()

    def _setup_ui(self):
        """UI 초기화"""
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 스크롤 영역
        scroll_panel = wx.ScrolledWindow(self, style=wx.HSCROLL)
        scroll_panel.SetScrollRate(5, 0)
        scroll_panel.ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_NEVER)

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 배경색
        bg = Colors.BG_PRIMARY if Colors else wx.Colour(32, 32, 32)
        self.SetBackgroundColour(bg)
        scroll_panel.SetBackgroundColour(bg)
        self.SetMinSize((-1, 78))

        # 번역
        translations = getattr(self._main_window, '_translations', None)

        # === 파일 열기 ===
        open_tooltip = translations.tr("toolbar_open_file") if translations else "파일 열기 (Ctrl+O)"
        self._open_btn = FlatIconButton("open_file", open_tooltip, scroll_panel)
        self._open_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_open_file())
        button_sizer.Add(self._open_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._open_btn)

        button_sizer.Add(ToolSeparator(scroll_panel), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 2)

        # === 오버레이 그룹 ===
        text_tooltip = translations.tr("toolbar_text") if translations else "텍스트 추가 (T)"
        self._text_btn = FlatIconButton("text", text_tooltip, scroll_panel)
        self._text_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_text())
        button_sizer.Add(self._text_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._text_btn)

        sticker_tooltip = translations.tr("toolbar_sticker") if translations else "스티커/도형 추가"
        self._sticker_btn = FlatIconButton("sticker", sticker_tooltip, scroll_panel)
        self._sticker_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_sticker())
        button_sizer.Add(self._sticker_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._sticker_btn)

        pencil_tooltip = translations.tr("toolbar_pencil") if translations else "펜슬 그리기 (P)"
        self._pencil_btn = FlatIconButton("pencil", pencil_tooltip, scroll_panel)
        self._pencil_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_pencil())
        button_sizer.Add(self._pencil_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._pencil_btn)

        button_sizer.Add(ToolSeparator(scroll_panel), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 2)

        # === 편집 그룹 ===
        crop_tooltip = translations.tr("toolbar_crop") if translations else "자르기 (C)"
        self._crop_btn = FlatIconButton("crop", crop_tooltip, scroll_panel)
        self._crop_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_crop())
        button_sizer.Add(self._crop_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._crop_btn)

        resize_tooltip = translations.tr("toolbar_resize") if translations else "크기 조절 (R)"
        self._resize_btn = FlatIconButton("resize", resize_tooltip, scroll_panel)
        self._resize_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_resize())
        button_sizer.Add(self._resize_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._resize_btn)

        button_sizer.Add(ToolSeparator(scroll_panel), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 2)

        # === 효과 그룹 ===
        effects_tooltip = translations.tr("toolbar_effects") if translations else "효과/필터 (E)"
        self._effects_btn = FlatIconButton("effects", effects_tooltip, scroll_panel)
        self._effects_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_effects())
        button_sizer.Add(self._effects_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._effects_btn)

        button_sizer.Add(ToolSeparator(scroll_panel), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 2)

        # === 변환 그룹 ===
        rotate_tooltip = translations.tr("toolbar_rotate") if translations else "90° 회전"
        self._rotate_btn = FlatIconButton("rotate", rotate_tooltip, scroll_panel)
        self._rotate_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_rotate(0))
        button_sizer.Add(self._rotate_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._rotate_btn)

        flip_h_tooltip = translations.tr("toolbar_flip_h") if translations else "좌우 뒤집기"
        self._flip_h_btn = FlatIconButton("flip_h", flip_h_tooltip, scroll_panel)
        self._flip_h_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_flip('h'))
        button_sizer.Add(self._flip_h_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._flip_h_btn)

        flip_v_tooltip = translations.tr("toolbar_flip_v") if translations else "상하 뒤집기"
        self._flip_v_btn = FlatIconButton("flip_v", flip_v_tooltip, scroll_panel)
        self._flip_v_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_flip('v'))
        button_sizer.Add(self._flip_v_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._flip_v_btn)

        button_sizer.Add(ToolSeparator(scroll_panel), 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 2)

        # === 재생 그룹 ===
        reverse_tooltip = translations.tr("toolbar_reverse") if translations else "역재생"
        self._reverse_btn = FlatIconButton("reverse", reverse_tooltip, scroll_panel)
        self._reverse_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_reverse())
        button_sizer.Add(self._reverse_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._reverse_btn)

        yoyo_tooltip = translations.tr("toolbar_yoyo") if translations else "요요 효과"
        self._yoyo_btn = FlatIconButton("yoyo", yoyo_tooltip, scroll_panel)
        self._yoyo_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_yoyo())
        button_sizer.Add(self._yoyo_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._yoyo_btn)

        speed_tooltip = translations.tr("toolbar_speed") if translations else "속도 조절"
        self._speed_btn = FlatIconButton("speed", speed_tooltip, scroll_panel)
        self._speed_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_speed())
        button_sizer.Add(self._speed_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._speed_btn)

        reduce_tooltip = translations.tr("toolbar_reduce") if translations else "프레임 줄이기"
        self._reduce_btn = FlatIconButton("reduce", reduce_tooltip, scroll_panel)
        self._reduce_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_reduce_frames())
        button_sizer.Add(self._reduce_btn, 0, wx.ALL, 3)
        self._all_buttons.append(self._reduce_btn)

        button_sizer.AddStretchSpacer()

        scroll_panel.SetSizer(button_sizer)
        main_sizer.Add(scroll_panel, 1, wx.EXPAND)
        self.SetSizer(main_sizer)

    # ==================== 이벤트 핸들러 ====================

    def _on_open_file(self):
        if hasattr(self._main_window, 'open_file'):
            self._main_window.open_file()

    def _on_text(self):
        if hasattr(self._main_window, '_show_text_dialog'):
            self._main_window._show_text_dialog()

    def _on_sticker(self):
        if hasattr(self._main_window, '_show_sticker_dialog'):
            self._main_window._show_sticker_dialog()

    def _on_pencil(self):
        if hasattr(self._main_window, '_show_pencil_dialog'):
            self._main_window._show_pencil_dialog()

    def _on_crop(self):
        if hasattr(self._main_window, '_show_crop_dialog'):
            self._main_window._show_crop_dialog()

    def _on_resize(self):
        if hasattr(self._main_window, '_show_resize_dialog'):
            self._main_window._show_resize_dialog()

    def _on_effects(self):
        if hasattr(self._main_window, '_show_effects_dialog'):
            self._main_window._show_effects_dialog()

    def _on_rotate(self, angle: int):
        if hasattr(self._main_window, '_show_rotate_toolbar'):
            self._main_window._show_rotate_toolbar()

    def _on_flip(self, direction: str):
        if hasattr(self._main_window, '_flip_frames'):
            self._main_window._flip_frames(direction)

    def _on_reverse(self):
        if hasattr(self._main_window, '_reverse_frames'):
            self._main_window._reverse_frames()

    def _on_yoyo(self):
        if hasattr(self._main_window, '_apply_yoyo'):
            self._main_window._apply_yoyo()

    def _on_speed(self):
        if hasattr(self._main_window, '_show_speed_dialog'):
            self._main_window._show_speed_dialog()

    def _on_reduce_frames(self):
        if hasattr(self._main_window, '_show_reduce_toolbar'):
            self._main_window._show_reduce_toolbar()

    # ==================== 공개 메서드 ====================

    def set_edit_mode(self, active: bool, active_button: Optional[FlatIconButton] = None):
        """편집 모드 설정"""
        if active:
            self._active_button = active_button
            for btn in self._all_buttons:
                if btn != active_button:
                    btn.Enable(False)
                    btn.set_active(False)
                else:
                    btn.set_active(True)
        else:
            self._active_button = None
            for btn in self._all_buttons:
                btn.Enable(True)
                btn.set_active(False)

    def get_button_by_mode(self, mode: str) -> Optional[FlatIconButton]:
        """모드 이름으로 버튼 반환"""
        mode_map = {
            'text': self._text_btn,
            'sticker': self._sticker_btn,
            'pencil': self._pencil_btn,
            'crop': self._crop_btn,
            'resize': self._resize_btn,
            'effects': self._effects_btn,
            'speed': self._speed_btn,
            'rotate': self._rotate_btn,
        }
        return mode_map.get(mode)

    def update_texts(self, translations: 'Translations'):
        """텍스트 업데이트"""
        self._open_btn.SetToolTip(translations.tr("toolbar_open_file"))
        self._text_btn.SetToolTip(translations.tr("toolbar_text"))
        self._sticker_btn.SetToolTip(translations.tr("toolbar_sticker"))
        self._pencil_btn.SetToolTip(translations.tr("toolbar_pencil"))
        self._crop_btn.SetToolTip(translations.tr("toolbar_crop"))
        self._resize_btn.SetToolTip(translations.tr("toolbar_resize"))
        self._effects_btn.SetToolTip(translations.tr("toolbar_effects"))
        self._rotate_btn.SetToolTip(translations.tr("toolbar_rotate"))
        self._flip_h_btn.SetToolTip(translations.tr("toolbar_flip_h"))
        self._flip_v_btn.SetToolTip(translations.tr("toolbar_flip_v"))
        self._reverse_btn.SetToolTip(translations.tr("toolbar_reverse"))
        self._yoyo_btn.SetToolTip(translations.tr("toolbar_yoyo"))
        self._speed_btn.SetToolTip(translations.tr("toolbar_speed"))
        self._reduce_btn.SetToolTip(translations.tr("toolbar_reduce"))
