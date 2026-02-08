"""
InlineToolbarBase - 인라인 툴바 베이스 클래스 (wxPython 버전)

모든 인라인 툴바의 공통 기능과 스타일 정의.
PropertyBar 컨테이너의 자식으로 등록되어 활성 도구에 따라 표시/숨김됩니다.
"""
import wx
from typing import TYPE_CHECKING, Optional, Callable
from ..style_constants_wx import Colors
from ...utils.wx_events import (
    ToolbarAppliedEvent, EVT_TOOLBAR_APPLIED,
    ToolbarCancelledEvent, EVT_TOOLBAR_CANCELLED,
    ToolbarPreviewUpdatedEvent, EVT_TOOLBAR_PREVIEW_UPDATED
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
    TOOLBAR_MIN_HEIGHT = 88
    TOOLBAR_ROW_HEIGHT = 76
    TOOLBAR_BG_COLOR = Colors.BG_TOOLBAR

    # 서브클래스에서 False로 설정하면 Clear 버튼 비표시
    _has_clear_button = True

    def __init__(self, main_window: 'MainWindow', parent: Optional[wx.Window] = None):
        if parent is None:
            parent = main_window
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self._main_window = main_window
        self._canvas: Optional['CanvasWidget'] = None
        self._is_active = False

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
        self._controls_widget = wx.Panel(self)
        self._controls_widget.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self._controls_sizer = wx.WrapSizer(wx.HORIZONTAL)
        self._controls_widget.SetSizer(self._controls_sizer)

        self._main_sizer.Add(self._controls_widget, 1, wx.EXPAND | wx.ALL, 16)

        self.SetSizer(self._main_sizer)

    def _apply_base_style(self):
        """기본 스타일 적용"""
        self.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.SetMinSize((-1, self.TOOLBAR_MIN_HEIGHT))

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
        """컨트롤 영역에 위젯 추가"""
        self._controls_sizer.Add(widget, 0, wx.ALL, 8)

    def add_icon_label(self, icon_type: str, size: int = 20, tooltip: str = None) -> wx.StaticBitmap:
        """아이콘 라벨 추가"""
        bitmap = wx.Bitmap(size, size)
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(Colors.BORDER))
        dc.Clear()
        dc.SelectObject(wx.NullBitmap)

        label = wx.StaticBitmap(self._controls_widget, bitmap=bitmap)
        label.SetMinSize((size + 8, size + 8))
        if tooltip:
            label.SetToolTip(tooltip)

        self._controls_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)
        return label

    def add_separator(self):
        """구분선 추가"""
        separator = wx.StaticLine(self._controls_widget, style=wx.LI_VERTICAL)
        separator.SetMinSize((1, 50))
        separator.SetBackgroundColour(Colors.BORDER)
        self._controls_sizer.Add(separator, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)

    def add_label(self, text: str) -> wx.StaticText:
        """라벨 추가"""
        label = wx.StaticText(self._controls_widget, label=text)
        label.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._controls_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 8)
        return label

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

    # === 공통 유틸리티 메서드 ===

    def update_color_button(self, button: wx.Button, color: wx.Colour):
        """색상 버튼 스타일 업데이트"""
        button.SetBackgroundColour(color)
        button.Refresh()

    def pick_color(self, current_color: wx.Colour, title: str = "색상 선택",
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
