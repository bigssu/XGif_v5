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
    from .style_constants_wx import Colors
except ImportError:
    IconFactory = None
    IconColors = None
    Colors = None

# 라운디드 코너 반경
_CORNER_RADIUS = 10
_ICON_SIZE_BY_TYPE = {
    "open_file": 24,
    "text": 24,
    "sticker": 24,
    "pencil": 25,
    "crop": 25,
    "resize": 25,
    "effects": 25,
    "rotate": 26,
    "flip_h": 26,
    "flip_v": 26,
    "reverse": 24,
    "yoyo": 26,
    "speed": 26,
    "reduce": 24,
    "delete": 24,
    "clear": 24,
    "add": 24,
    "time": 25,
    "play": 25,
    "pause": 25,
}
_GROUP_BUTTON_SIZE = (38, 38)
_GROUP_CARD_RADIUS = 8


class FlatIconButton(wx.Control):
    """모던 플랫 아이콘 버튼 (owner-draw).

    wx.GraphicsContext로 라운디드 렉트를 그려 플랫한 모던 스타일을 구현합니다.
    상태: normal / hovered / pressed / active / disabled
    """

    def __init__(self, icon_type: str, tooltip: str, parent=None, size=(46, 46)):
        super().__init__(parent, wx.ID_ANY, pos=wx.DefaultPosition, size=size,
                         style=wx.BORDER_NONE)
        self._icon_type = icon_type
        self._button_size = size
        self._is_active = False
        self._is_hovered = False
        self._pressed = False
        self._enabled = True
        self._bitmap: Optional[wx.Bitmap] = None
        self._active_bitmap: Optional[wx.Bitmap] = None
        self._disabled_bitmap: Optional[wx.Bitmap] = None

        # 색상
        self._bg_normal = None
        self._bg_hover = Colors.BG_RAISED if Colors else wx.Colour(35, 40, 48)
        self._bg_pressed = Colors.ICON_BTN_PRESSED if Colors else wx.Colour(42, 42, 42)
        self._bg_active = Colors.ICON_BTN_ACTIVE if Colors else wx.Colour(0, 120, 212, 60)
        self._bg_disabled = None

        self.SetToolTip(tooltip)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetMinSize(size)
        self.SetMaxSize(size)
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
            edge = min(self._button_size)
            max_icon_size = max(18, edge - 11)
            icon_size = min(_ICON_SIZE_BY_TYPE.get(self._icon_type, 25), max_icon_size)
            if edge < 42:
                icon_size = min(icon_size, 22)
            self._bitmap = IconFactory.create_bitmap(self._icon_type, icon_size)
            self._active_bitmap = IconFactory.create_bitmap(
                self._icon_type,
                icon_size,
                IconColors.ACCENT if IconColors else None,
            )
            self._disabled_bitmap = IconFactory.create_bitmap(
                self._icon_type,
                icon_size,
                IconColors.MUTED if IconColors else None,
            )

    # --- 공개 API ---

    def set_active(self, active: bool):
        """활성 상태 설정"""
        self._is_active = active
        self.Refresh()

    def set_icon_type(self, icon_type: str):
        """아이콘 타입 교체."""
        if self._icon_type == icon_type:
            return
        self._icon_type = icon_type
        self._create_icon()
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

            # 기본 상태는 투명. hover/pressed/active에서만 표면을 그린다.
            if bg is not None:
                pad = 3
                gc.SetBrush(wx.Brush(bg))
                if self._is_active:
                    gc.SetPen(wx.Pen(Colors.BORDER_FOCUS, 1))
                elif self._is_hovered:
                    gc.SetPen(wx.Pen(Colors.BORDER_HOVER, 1))
                else:
                    gc.SetPen(wx.TRANSPARENT_PEN)
                gc.DrawRoundedRectangle(pad, pad, w - pad * 2, h - pad * 2, _CORNER_RADIUS)

            # 아이콘 그리기 (중앙)
            bitmap = self._bitmap
            if not self._enabled:
                bitmap = self._disabled_bitmap or bitmap
            elif self._is_active:
                bitmap = self._active_bitmap or bitmap

            if bitmap and bitmap.IsOk():
                bw, bh = bitmap.GetWidth(), bitmap.GetHeight()
                ix = (w - bw) / 2
                iy = (h - bh) / 2
                gc.DrawBitmap(bitmap, ix, iy, bw, bh)

        memdc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bmp, 0, 0, False)


class ToolSeparator(wx.Control):
    """툴바 구분선 (owner-draw, 라운디드 캡)"""

    def __init__(self, parent=None):
        super().__init__(parent, wx.ID_ANY, size=(10, 42), style=wx.BORDER_NONE)
        self.SetMinSize((10, 42))
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
        parent_bg = parent.GetBackgroundColour() if parent else Colors.BG_PANEL
        memdc.SetBackground(wx.Brush(parent_bg))
        memdc.Clear()

        gc = wx.GraphicsContext.Create(memdc)
        if gc:
            sep_color = Colors.DIVIDER_SUBTLE if Colors else wx.Colour(40, 46, 56)
            gc.SetBrush(wx.Brush(sep_color))
            gc.SetPen(wx.TRANSPARENT_PEN)
            # 세로 라운디드 바
            bar_w = 1
            bar_h = h - 18
            x = (w - bar_w) / 2
            y = 6
            gc.DrawRoundedRectangle(x, y, bar_w, bar_h, 1)

        memdc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bmp, 0, 0, False)


class ToolbarGroupLabel(wx.StaticText):
    """Low-noise visible group label for toolbar discoverability."""

    def __init__(self, parent, label: str):
        super().__init__(parent, label=label)
        self.SetForegroundColour(Colors.TEXT_MUTED if Colors else wx.Colour(125, 138, 153))
        self.SetBackgroundColour(Colors.BG_CARD if Colors else wx.Colour(32, 40, 54))
        self.SetFont(wx.Font(7, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_BOLD))
        self.SetMinSize((-1, 12))


class ToolbarGroupCard(wx.Panel):
    """Raised toolbar group card with icons above and label below."""

    def __init__(self, parent, group: str, label: str):
        super().__init__(parent, wx.ID_ANY, style=wx.BORDER_NONE)
        self._group = group
        self._label = ToolbarGroupLabel(self, label)
        self._button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._skip_auto_theme = True
        self.SetBackgroundColour(Colors.BG_CARD if Colors else wx.Colour(32, 40, 54))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 61))

        root_sizer = wx.BoxSizer(wx.VERTICAL)
        root_sizer.Add(self._button_sizer, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP | wx.LEFT | wx.RIGHT, 4)
        root_sizer.Add(self._label, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT | wx.RIGHT | wx.BOTTOM, 6)
        self.SetSizer(root_sizer)

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)

    @property
    def group(self) -> str:
        return self._group

    @property
    def label(self) -> ToolbarGroupLabel:
        return self._label

    def add_button(self, button: FlatIconButton):
        self._button_sizer.Add(button, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 1)
        self.Layout()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.RAIL_BG
        dc.SetBackground(wx.Brush(parent_bg))
        dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return

        bg = Colors.BG_CARD if Colors else wx.Colour(32, 40, 54)
        border = Colors.BORDER_SOFT if Colors else wx.Colour(48, 60, 78)
        gc.SetBrush(wx.Brush(bg))
        gc.SetPen(wx.Pen(border, 1))
        gc.DrawRoundedRectangle(0.5, 0.5, w - 1, h - 1, _GROUP_CARD_RADIUS)

        if Colors:
            gc.SetPen(wx.Pen(Colors.SURFACE_HIGHLIGHT, 1))
            gc.StrokeLine(8, 1.5, max(8, w - 8), 1.5)
            gc.SetPen(wx.Pen(Colors.SURFACE_SHADOW, 1))
            gc.StrokeLine(8, h - 1.5, max(8, w - 8), h - 1.5)


class IconToolbar(wx.Panel):
    """모던 플랫 아이콘 툴바"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent)
        self._main_window = main_window
        self._all_buttons = []
        self._group_cards = {}
        self._group_labels = {}
        self._scroll_panel = None
        self._active_button: Optional[FlatIconButton] = None
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._setup_ui()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        parent = self.GetParent()
        bg = parent.GetBackgroundColour() if parent else Colors.BG_PRIMARY
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        if gc:
            pad = 6
            gc.SetBrush(wx.Brush(Colors.RAIL_BG))
            gc.SetPen(wx.Pen(Colors.DIVIDER_SUBTLE, 1))
            gc.DrawRoundedRectangle(pad, pad, w - pad * 2, h - pad * 2, 13)
            gc.SetPen(wx.Pen(Colors.SURFACE_HIGHLIGHT, 1))
            gc.StrokeLine(pad + 10, pad + 1, w - pad - 10, pad + 1)
            gc.SetPen(wx.Pen(Colors.SURFACE_SHADOW, 1))
            gc.StrokeLine(pad + 10, h - pad - 1, w - pad - 10, h - pad - 1)

    def _setup_ui(self):
        """UI 초기화"""
        self.Freeze()
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 스크롤 영역
        scroll_panel = wx.ScrolledWindow(self, style=wx.HSCROLL)
        self._scroll_panel = scroll_panel
        scroll_panel.SetScrollRate(5, 0)
        scroll_panel.ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_NEVER)
        scroll_panel.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        scroll_panel.Bind(wx.EVT_PAINT, self._on_scroll_paint)
        scroll_panel.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        scroll_panel.Bind(wx.EVT_SIZE, self._on_scroll_size)
        scroll_panel.Freeze()

        button_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 배경색
        bg = Colors.RAIL_BG if Colors else wx.Colour(25, 29, 35)
        self.SetBackgroundColour(Colors.BG_PRIMARY if Colors else bg)
        scroll_panel.SetBackgroundColour(bg)
        self.SetMinSize((-1, 86))

        # 번역
        translations = getattr(self._main_window, '_translations', None)

        # === 파일 열기 ===
        file_card = self._create_group_card(button_sizer, scroll_panel, "file", translations)
        open_tooltip = translations.tr("toolbar_open_file") if translations else "파일 열기 (Ctrl+O)"
        self._open_btn = self._create_group_button(file_card, "open_file", open_tooltip)
        self._open_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_open_file())
        self._all_buttons.append(self._open_btn)

        # === 오버레이 그룹 ===
        overlay_card = self._create_group_card(button_sizer, scroll_panel, "overlay", translations)
        text_tooltip = translations.tr("toolbar_text") if translations else "텍스트 추가 (T)"
        self._text_btn = self._create_group_button(overlay_card, "text", text_tooltip)
        self._text_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_text())
        self._all_buttons.append(self._text_btn)

        sticker_tooltip = translations.tr("toolbar_sticker") if translations else "스티커/도형 추가"
        self._sticker_btn = self._create_group_button(overlay_card, "sticker", sticker_tooltip)
        self._sticker_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_sticker())
        self._all_buttons.append(self._sticker_btn)

        pencil_tooltip = translations.tr("toolbar_pencil") if translations else "펜슬 그리기 (P)"
        self._pencil_btn = self._create_group_button(overlay_card, "pencil", pencil_tooltip)
        self._pencil_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_pencil())
        self._all_buttons.append(self._pencil_btn)

        # === 편집 그룹 ===
        edit_card = self._create_group_card(button_sizer, scroll_panel, "edit", translations)
        crop_tooltip = translations.tr("toolbar_crop") if translations else "자르기 (C)"
        self._crop_btn = self._create_group_button(edit_card, "crop", crop_tooltip)
        self._crop_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_crop())
        self._all_buttons.append(self._crop_btn)

        resize_tooltip = translations.tr("toolbar_resize") if translations else "크기 조절 (R)"
        self._resize_btn = self._create_group_button(edit_card, "resize", resize_tooltip)
        self._resize_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_resize())
        self._all_buttons.append(self._resize_btn)

        # === 효과 그룹 ===
        effects_card = self._create_group_card(button_sizer, scroll_panel, "effects", translations)
        effects_tooltip = translations.tr("toolbar_effects") if translations else "효과/필터 (E)"
        self._effects_btn = self._create_group_button(effects_card, "effects", effects_tooltip)
        self._effects_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_effects())
        self._all_buttons.append(self._effects_btn)

        # === 변환 그룹 ===
        transform_card = self._create_group_card(button_sizer, scroll_panel, "transform", translations)
        rotate_tooltip = translations.tr("toolbar_rotate") if translations else "90° 회전"
        self._rotate_btn = self._create_group_button(transform_card, "rotate", rotate_tooltip)
        self._rotate_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_rotate(0))
        self._all_buttons.append(self._rotate_btn)

        flip_h_tooltip = translations.tr("toolbar_flip_h") if translations else "좌우 뒤집기"
        self._flip_h_btn = self._create_group_button(transform_card, "flip_h", flip_h_tooltip)
        self._flip_h_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_flip('h'))
        self._all_buttons.append(self._flip_h_btn)

        flip_v_tooltip = translations.tr("toolbar_flip_v") if translations else "상하 뒤집기"
        self._flip_v_btn = self._create_group_button(transform_card, "flip_v", flip_v_tooltip)
        self._flip_v_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_flip('v'))
        self._all_buttons.append(self._flip_v_btn)

        # === 재생 그룹 ===
        playback_card = self._create_group_card(button_sizer, scroll_panel, "playback", translations)
        reverse_tooltip = translations.tr("toolbar_reverse") if translations else "역재생"
        self._reverse_btn = self._create_group_button(playback_card, "reverse", reverse_tooltip)
        self._reverse_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_reverse())
        self._all_buttons.append(self._reverse_btn)

        yoyo_tooltip = translations.tr("toolbar_yoyo") if translations else "요요 효과"
        self._yoyo_btn = self._create_group_button(playback_card, "yoyo", yoyo_tooltip)
        self._yoyo_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_yoyo())
        self._all_buttons.append(self._yoyo_btn)

        speed_tooltip = translations.tr("toolbar_speed") if translations else "속도 조절"
        self._speed_btn = self._create_group_button(playback_card, "speed", speed_tooltip)
        self._speed_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_speed())
        self._all_buttons.append(self._speed_btn)

        reduce_tooltip = translations.tr("toolbar_reduce") if translations else "프레임 줄이기"
        self._reduce_btn = self._create_group_button(playback_card, "reduce", reduce_tooltip)
        self._reduce_btn.Bind(wx.EVT_BUTTON, lambda e: self._on_reduce_frames())
        self._all_buttons.append(self._reduce_btn)

        button_sizer.AddStretchSpacer()

        scroll_panel.SetSizer(button_sizer)
        main_sizer.Add(scroll_panel, 1, wx.EXPAND | wx.ALL, 10)
        self.SetSizer(main_sizer)

        scroll_panel.Thaw()
        self.Thaw()

    def _on_size(self, event):
        event.Skip()
        self.Refresh(False)
        if self._scroll_panel:
            self._scroll_panel.Refresh(False)

    def _on_scroll_size(self, event):
        event.Skip()
        event.GetEventObject().Refresh(False)

    def _on_scroll_paint(self, event):
        panel = event.GetEventObject()
        dc = wx.PaintDC(panel)
        w, h = panel.GetClientSize()
        if w <= 0 or h <= 0:
            return

        bg = Colors.RAIL_BG if Colors else wx.Colour(25, 29, 35)
        dc.SetBackground(wx.Brush(bg))
        dc.Clear()

    def _group_text(self, group: str, translations: Optional['Translations']) -> str:
        key = f"toolbar_group_{group}"
        fallback = {
            "file": "File",
            "overlay": "Overlay",
            "edit": "Edit",
            "effects": "Effects",
            "transform": "Transform",
            "playback": "Playback",
        }[group]
        return translations.tr(key) if translations else fallback

    def _create_group_card(self, sizer, parent, group: str, translations: Optional['Translations']):
        card = ToolbarGroupCard(parent, group, self._group_text(group, translations))
        self._group_cards[group] = card
        self._group_labels[group] = card.label
        sizer.Add(card, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 8)
        return card

    def _create_group_button(self, card: ToolbarGroupCard, icon_type: str, tooltip: str) -> FlatIconButton:
        button = FlatIconButton(icon_type, tooltip, card, size=_GROUP_BUTTON_SIZE)
        card.add_button(button)
        return button

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
        for group, label in self._group_labels.items():
            label.SetLabel(self._group_text(group, translations))
