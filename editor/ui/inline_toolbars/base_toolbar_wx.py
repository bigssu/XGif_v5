"""
InlineToolbarBase - 인라인 툴바 베이스 클래스 (wxPython 버전)

모든 인라인 툴바의 공통 기능과 스타일 정의.
PropertyBar 컨테이너의 자식으로 등록되어 활성 도구에 따라 표시/숨김됩니다.
"""
import wx
from typing import TYPE_CHECKING, Optional, Callable
from contextlib import suppress
from ..style_constants_wx import Colors
from ..icon_utils_wx import IconFactory
from ...utils.wx_events import (
    ToolbarAppliedEvent, ToolbarCancelledEvent, ToolbarPreviewUpdatedEvent
)
from ...utils.frame_targeting import (
    apply_frame_processor,
    build_target_choices,
    restore_current_original_image,
    restore_original_images,
    snapshot_original_images,
)

if TYPE_CHECKING:
    from ..editor_main_window_wx import MainWindow
    from ..canvas_widget_wx import CanvasWidget


class InlineToolbarBase(wx.Panel):
    """인라인 툴바 베이스 클래스 (wxPython)

    PropertyBar 내부에 배치되어 도구별 속성 컨트롤을 제공합니다.

    Events:
        EVT_TOOLBAR_APPLIED: 변경 사항이 적용됨
        EVT_TOOLBAR_CANCELLED: 작업이 취소됨
        EVT_TOOLBAR_PREVIEW_UPDATED: 미리보기가 업데이트됨
    """

    # 툴바 기본 설정
    TOOLBAR_MIN_HEIGHT = 62
    TOOLBAR_ROW_HEIGHT = 50
    TOOLBAR_BG_COLOR = Colors.RAIL_BG_ALT

    # 서브클래스에서 False로 설정하면 Clear 버튼 비표시
    _has_clear_button = True
    _has_action_buttons = True

    def __init__(self, main_window: 'MainWindow', parent: Optional[wx.Window] = None):
        if parent is None:
            parent = main_window
        super().__init__(parent, style=wx.BORDER_NONE)
        self._main_window = main_window
        self._canvas: Optional['CanvasWidget'] = None
        self._is_active = False
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_SIZE, self._on_size)
        self._layout_sync_pending = False
        # _calculate_wrapped_height cache: maps client_width → height,
        # invalidated when children change via add_control/add_label/etc.
        self._wrapped_height_cache: dict[int, int] = {}

        # 성능 모드 설정 (저사양 모드 감지)
        self._is_low_end_mode = getattr(main_window, '_is_low_end_mode', False)
        self._preview_delay = getattr(main_window, '_preview_delay', 100)

        # 미리보기 타이머 초기화 (공통)
        self._preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

        # 기본 레이아웃 설정
        self._setup_base_ui()
        self._apply_base_style()

    def _setup_base_ui(self):
        """기본 UI 구조 설정"""
        self._main_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 컨트롤 영역 (전체 너비 사용)
        self._controls_widget = wx.Panel(self, style=wx.BORDER_NONE)
        self._controls_widget.SetBackgroundColour(Colors.RAIL_BG)
        self._controls_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self._controls_widget.SetSizer(self._controls_sizer)

        self._main_sizer.Add(self._controls_widget, 1, wx.EXPAND | wx.ALL, 7)

        self.SetSizer(self._main_sizer)

    def _apply_base_style(self):
        """기본 스타일 적용"""
        self.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.SetMinSize((-1, self.TOOLBAR_MIN_HEIGHT))

    def _on_size(self, event):
        """Recalculate wrapped-toolbar height after width changes settle."""
        self._schedule_layout_height_sync()
        event.Skip()

    def _schedule_layout_height_sync(self):
        if self._layout_sync_pending:
            return
        self._layout_sync_pending = True
        wx.CallAfter(self._run_layout_height_sync)

    def _run_layout_height_sync(self):
        self._layout_sync_pending = False
        self.sync_layout_height()

    def sync_layout_height(self, *, notify_parent: bool = True) -> int:
        """Grow the toolbar to fit all wrapped rows without clipping controls."""
        desired_height = self._calculate_wrapped_height()
        current_min = self.GetMinSize()
        if current_min.GetHeight() != desired_height:
            self.SetMinSize((-1, desired_height))

            parent = self.GetParent()
            if notify_parent and parent and hasattr(parent, "sync_active_toolbar_height"):
                parent.sync_active_toolbar_height()
            elif notify_parent and parent:
                parent.Layout()

        controls_height = max(1, desired_height - 14)
        controls_min = self._controls_widget.GetMinSize()
        if controls_min.GetHeight() != controls_height:
            self._controls_widget.SetMinSize((-1, controls_height))

        self._controls_widget.Layout()
        self.Layout()
        return desired_height

    def _calculate_wrapped_height(self) -> int:
        client_width = self.GetClientSize().GetWidth()
        if client_width <= 0:
            parent = self.GetParent()
            client_width = parent.GetClientSize().GetWidth() if parent else 0

        cached = self._wrapped_height_cache.get(client_width)
        if cached is not None:
            return cached

        available_width = max(1, client_width - 14)
        total_height = 0
        row_width = 0
        row_height = 0

        for item in self._controls_sizer.GetChildren():
            if not item.IsShown():
                continue
            min_size = item.CalcMin()
            item_width = max(1, min_size.GetWidth())
            item_height = max(1, min_size.GetHeight())

            if row_width and row_width + item_width > available_width:
                total_height += row_height
                row_width = 0
                row_height = 0

            row_width += item_width
            row_height = max(row_height, item_height)

        if row_width or row_height:
            total_height += row_height

        result = max(self.TOOLBAR_MIN_HEIGHT, total_height + 14)
        self._wrapped_height_cache[client_width] = result
        return result

    def _invalidate_wrapped_height_cache(self):
        """Drop cached wrap heights after the child set changes.

        Visibility toggles by subclasses must call this explicitly — there is
        no observer hook for Show/Hide.
        """
        self._wrapped_height_cache.clear()

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
            pad = 5
            gc.SetBrush(wx.Brush(Colors.RAIL_BG))
            gc.SetPen(wx.Pen(Colors.DIVIDER_SUBTLE, 1))
            gc.DrawRoundedRectangle(pad, pad, w - pad * 2, h - pad * 2, 12)
            gc.SetPen(wx.Pen(Colors.SURFACE_HIGHLIGHT, 1))
            gc.StrokeLine(pad + 9, pad + 1, w - pad - 9, pad + 1)
            gc.SetPen(wx.Pen(Colors.SURFACE_SHADOW, 1))
            gc.StrokeLine(pad + 9, h - pad - 1, w - pad - 9, h - pad - 1)

    def _on_destroy(self, event):
        """윈도우 파괴 시 타이머 정리"""
        if event.GetEventObject() is self:
            self._preview_timer.Stop()
        event.Skip()

    def _on_preview_timer(self, event):
        """프리뷰 타이머 이벤트"""
        self._update_preview()

    # === 공개 메서드 ===

    def activate(self):
        """툴바 활성화 (PropertyBar에서 호출)"""
        self._canvas = self._safe_get_canvas()
        self._is_active = True
        self._on_activated()
        self._schedule_layout_height_sync()

    def deactivate(self):
        """툴바 비활성화 (PropertyBar에서 호출)"""
        self._is_active = False
        self._on_deactivated()
        self._canvas = None

    def is_active(self) -> bool:
        """툴바 활성화 상태 반환"""
        return self._is_active

    @property
    def has_clear_button(self):
        """Clear 버튼 표시 여부"""
        return self._has_clear_button

    @property
    def has_action_buttons(self):
        """Apply/Cancel 공유 액션 버튼 표시 여부"""
        return self._has_action_buttons

    # === 서브클래스에서 오버라이드할 메서드 ===

    def _on_activated(self):
        """툴바가 활성화될 때 호출 (서브클래스에서 오버라이드)"""
        pass

    def _on_deactivated(self):
        """툴바가 비활성화될 때 호출 (서브클래스에서 오버라이드)"""
        pass

    def _on_clear(self, event):
        """지우기/초기화 버튼 클릭 (서브클래스에서 오버라이드)"""
        pass

    def _on_apply(self, event):
        """적용 버튼 클릭 (서브클래스에서 오버라이드)"""
        wx.PostEvent(self, ToolbarAppliedEvent())

    def _on_cancel(self, event):
        """취소 버튼 클릭"""
        wx.PostEvent(self, ToolbarCancelledEvent())

    def update_preview(self):
        """미리보기 업데이트 (서브클래스에서 오버라이드)"""
        wx.PostEvent(self, ToolbarPreviewUpdatedEvent())

    def reset_to_default(self):
        """기본값으로 초기화 (서브클래스에서 오버라이드)"""
        pass

    # === 유틸리티 메서드 ===

    def add_control(self, widget: wx.Window):
        """컨트롤 영역에 위젯 추가 (다크 테마 자동 적용)"""
        if isinstance(widget, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble, wx.ComboBox)):
            widget.SetBackgroundColour(Colors.BG_INPUT_DARK)
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
            self._use_best_control_height(widget)
        elif isinstance(widget, wx.Slider):
            widget.SetBackgroundColour(Colors.RAIL_BG)
            width, height = widget.GetMinSize()
            widget.SetMinSize((width if width > 0 else 120, height if height > 0 else -1))
        elif isinstance(widget, (wx.StaticText, wx.CheckBox)):
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
        elif isinstance(widget, wx.Choice):
            widget.SetBackgroundColour(Colors.BG_INPUT_DARK)
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
            self._use_best_control_height(widget)
        elif isinstance(widget, (wx.Button, wx.ToggleButton)):
            widget.SetBackgroundColour(Colors.BG_INPUT_DARK)
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
            self._use_best_control_height(widget, preserve_explicit_height=True)
        self._controls_sizer.Add(widget, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self._invalidate_wrapped_height_cache()

    def _use_best_control_height(self, widget: wx.Window, *, preserve_explicit_height: bool = False):
        """Keep native controls at their best height so text stays vertically centered."""
        min_size = widget.GetMinSize()
        best_size = widget.GetBestSize()
        width = min_size.GetWidth() if min_size.GetWidth() > 0 else -1
        height = min_size.GetHeight() if preserve_explicit_height and min_size.GetHeight() > 0 else -1
        if height <= 0:
            height = best_size.GetHeight() if best_size.GetHeight() > 0 else -1
        widget.SetMinSize((width, height))

    def add_icon_label(self, icon_type: str, size: int = 20, tooltip: str = None) -> wx.StaticBitmap:
        """아이콘 라벨 추가"""
        bitmap = IconFactory.create_bitmap(icon_type, size)

        label = wx.StaticBitmap(self._controls_widget, bitmap=bitmap)
        label.SetMinSize((size + 8, max(size + 8, 28)))
        label.SetBackgroundColour(Colors.RAIL_BG)
        if tooltip:
            label.SetToolTip(tooltip)

        self._controls_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 4)
        self._invalidate_wrapped_height_cache()
        return label

    def add_separator(self):
        """구분선 추가"""
        separator = wx.StaticLine(self._controls_widget, style=wx.LI_VERTICAL)
        separator.SetMinSize((1, 30))
        separator.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        self._controls_sizer.Add(separator, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 7)
        self._invalidate_wrapped_height_cache()

    def add_label(self, text: str) -> wx.StaticText:
        """라벨 추가"""
        label = wx.StaticText(self._controls_widget, label=text)
        label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._controls_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 4)
        self._invalidate_wrapped_height_cache()
        return label

    def add_target_combo(
        self,
        on_change: Callable[[], None],
        *,
        default_selection: int = 1,
        tooltip: Optional[str] = None,
    ) -> wx.ComboBox:
        """Add a normalized target combo shared by multi-frame toolbars."""
        translations = getattr(self._main_window, '_translations', None)
        target_tooltip = tooltip or (
            translations.tr("target_tooltip") if translations else "적용 대상 프레임"
        )
        self.add_icon_label("target", 20, target_tooltip)

        combo = wx.ComboBox(
            self._controls_widget,
            style=wx.CB_READONLY,
            choices=build_target_choices(translations),
        )
        combo.SetSelection(default_selection)
        combo.SetMinSize((70, -1))
        combo.SetToolTip(target_tooltip)
        combo.Bind(wx.EVT_COMBOBOX, lambda e: on_change())
        self.add_control(combo)
        return combo

    @property
    def frames(self):
        """프레임 컬렉션 반환"""
        if self._main_window is None:
            return None
        return getattr(self._main_window, '_frames', None)

    @property
    def main_window(self):
        """메인 윈도우 반환"""
        return self._main_window

    @property
    def canvas(self):
        """캔버스 반환"""
        return self._canvas

    def _safe_canvas_update(self):
        """캔버스 안전하게 업데이트"""
        try:
            if self._main_window and hasattr(self._main_window, '_canvas') and self._main_window._canvas:
                self._main_window._canvas.Refresh()
        except Exception:
            pass

    def _safe_get_canvas(self):
        """캔버스를 안전하게 가져오기"""
        try:
            if self._main_window and hasattr(self._main_window, '_canvas') and self._main_window._canvas:
                return self._main_window._canvas
        except Exception:
            pass
        return None

    def _snapshot_original_images(self):
        """Capture original frame images for preview/apply/cancel flows."""
        return snapshot_original_images(self.frames) if self.frames else []

    def _clear_original_images(self):
        """Release captured originals and stop any pending preview timer."""
        self._original_images = []
        self._preview_timer.Stop()

    def _restore_original_images(self):
        """Restore all tracked frame previews from originals."""
        if self.frames and getattr(self, '_original_images', None):
            restore_original_images(self.frames, self._original_images)

    def _restore_current_original_image(self):
        """Restore only the current frame preview from originals."""
        if self.frames and getattr(self, '_original_images', None):
            restore_current_original_image(self.frames, self._original_images)

    def _apply_frame_processor(self, target_mode: int, processor: Callable, *, preview_current: bool = False):
        """Run a shared frame-processor across toolbar targets."""
        if self.frames and getattr(self, '_original_images', None):
            apply_frame_processor(
                self.frames,
                self._original_images,
                target_mode,
                processor,
                preview_current=preview_current,
            )

    def _apply_generated_images(self, images):
        """Assign a generated image list back to frames."""
        if not self.frames:
            return
        for index, frame in enumerate(self.frames):
            if index < len(images) and images[index] is not None:
                with suppress(Exception):
                    frame._image = images[index]

    def _mark_editor_modified(self):
        """Mark the editor dirty and refresh shared UI state."""
        if hasattr(self._main_window, '_is_modified'):
            self._main_window._is_modified = True
        if hasattr(self._main_window, '_update_info_bar'):
            self._main_window._update_info_bar()

    def _finish_apply(self):
        """Finalize a successful apply with shared editor bookkeeping."""
        self._mark_editor_modified()
        self._safe_canvas_update()
        wx.PostEvent(self, ToolbarAppliedEvent())

    def _finish_cancel(self):
        """Finalize a cancel after restoring preview state."""
        self._safe_canvas_update()
        wx.PostEvent(self, ToolbarCancelledEvent())

    # === 공통 유틸리티 메서드 ===

    def update_color_button(self, button: wx.Button, color: wx.Colour):
        """색상 버튼 스타일 업데이트"""
        button.SetBackgroundColour(color)
        button.Refresh()

    def pick_color(self, current_color: wx.Colour, title: str = "Pick Color",
                   on_color_picked: Optional[Callable[[wx.Colour], None]] = None) -> Optional[wx.Colour]:
        """색상 선택 다이얼로그 표시"""
        data = wx.ColourData()
        data.SetColour(current_color)

        dlg = wx.ColourDialog(self, data)
        if dlg.ShowModal() == wx.ID_OK:
            color = dlg.GetColourData().GetColour()
            if on_color_picked:
                on_color_picked(color)
            dlg.Destroy()
            return color

        dlg.Destroy()
        return None

    def _update_preview(self):
        """미리보기 업데이트 (서브클래스에서 오버라이드)"""
        pass

    def update_texts(self, translations):
        """텍스트 업데이트 (서브클래스에서 오버라이드)"""
        pass
