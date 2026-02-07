"""
InlineToolbarBase - 인라인 툴바 베이스 클래스 (wxPython 버전)

모든 인라인 툴바의 공통 기능과 스타일 정의
"""
import wx
from typing import TYPE_CHECKING, Optional, Callable
from ...utils.wx_events import (
    ToolbarAppliedEvent, EVT_TOOLBAR_APPLIED,
    ToolbarCancelledEvent, EVT_TOOLBAR_CANCELLED,
    ToolbarPreviewUpdatedEvent, EVT_TOOLBAR_PREVIEW_UPDATED
)

if TYPE_CHECKING:
    from ..main_window import MainWindow
    from ..canvas_widget_wx import CanvasWidget


class InlineToolbarBase(wx.Panel):
    """인라인 툴바 베이스 클래스 (wxPython)

    모든 인라인 툴바가 상속받는 기본 클래스입니다.
    공통 스타일, 적용/취소 버튼, 캔버스 연동 기능을 제공합니다.

    Events:
        EVT_TOOLBAR_APPLIED: 변경 사항이 적용됨
        EVT_TOOLBAR_CANCELLED: 작업이 취소됨
        EVT_TOOLBAR_PREVIEW_UPDATED: 미리보기가 업데이트됨
    """

    # 툴바 기본 설정
    TOOLBAR_MIN_HEIGHT = 44
    TOOLBAR_ROW_HEIGHT = 38
    TOOLBAR_BG_COLOR = wx.Colour(64, 64, 64)
    TOOLBAR_MARGIN = 10

    def __init__(self, main_window: 'MainWindow', parent: Optional[wx.Window] = None):
        if parent is None:
            parent = main_window
        super().__init__(parent, style=wx.BORDER_SIMPLE)
        self._main_window = main_window
        self._canvas: Optional['CanvasWidget'] = None
        self._is_active = False
        self._updating_position = False  # 무한 루프 방지 플래그

        # 성능 모드 설정 (저사양 모드 감지)
        self._is_low_end_mode = getattr(main_window, '_is_low_end_mode', False)
        self._preview_delay = getattr(main_window, '_preview_delay', 100)

        # 미리보기 타이머 초기화 (공통)
        self._preview_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self._on_preview_timer, self._preview_timer)

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

        self._main_sizer.Add(self._controls_widget, 1, wx.EXPAND | wx.ALL, 10)

        # 액션 버튼 위젯 (캔버스 오른쪽 하단에 별도 배치)
        self._action_buttons_widget = wx.Panel(self._main_window)
        self._action_buttons_widget.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self._buttons_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # 번역 시스템 가져오기
        translations = getattr(self._main_window, '_translations', None)

        # 지우기/초기화 버튼 (선택적)
        clear_text = translations.tr("toolbar_clear") if translations else "초기화"
        self._clear_btn = wx.Button(self._action_buttons_widget, label=clear_text)
        self._clear_btn.SetBackgroundColour(wx.Colour(64, 64, 64))
        self._clear_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        self._clear_btn.SetMinSize((70, 32))
        self._clear_btn.Bind(wx.EVT_BUTTON, self._on_clear)
        self._clear_btn.Hide()  # 기본적으로 숨김
        self._buttons_sizer.Add(self._clear_btn, 0, wx.ALL, 5)

        # 적용 버튼
        apply_text = translations.tr("toolbar_apply") if translations else "적용"
        self._apply_btn = wx.Button(self._action_buttons_widget, label=apply_text)
        self._apply_btn.SetBackgroundColour(wx.Colour(0, 120, 212))
        self._apply_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        self._apply_btn.SetMinSize((70, 32))
        self._apply_btn.Bind(wx.EVT_BUTTON, self._on_apply)
        self._buttons_sizer.Add(self._apply_btn, 0, wx.ALL, 5)

        # 취소 버튼
        cancel_text = translations.tr("toolbar_cancel") if translations else "취소"
        self._cancel_btn = wx.Button(self._action_buttons_widget, label=cancel_text)
        self._cancel_btn.SetBackgroundColour(wx.Colour(64, 64, 64))
        self._cancel_btn.SetForegroundColour(wx.Colour(255, 255, 255))
        self._cancel_btn.SetMinSize((70, 32))
        self._cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
        self._buttons_sizer.Add(self._cancel_btn, 0, wx.ALL, 5)

        self._action_buttons_widget.SetSizer(self._buttons_sizer)
        self._action_buttons_widget.Hide()  # 기본적으로 숨김

        self.SetSizer(self._main_sizer)

    def _apply_base_style(self):
        """기본 스타일 적용"""
        self.SetBackgroundColour(self.TOOLBAR_BG_COLOR)
        self.SetForegroundColour(wx.Colour(255, 255, 255))
        self.SetMinSize((-1, self.TOOLBAR_MIN_HEIGHT))

    def _on_preview_timer(self, event):
        """프리뷰 타이머 이벤트"""
        self._update_preview()

    # === 공개 메서드 ===

    def show_on_canvas(self, canvas: 'CanvasWidget'):
        """캔버스 위에 툴바 표시

        Args:
            canvas: 부모가 될 캔버스 위젯
        """
        self._canvas = canvas
        self.Reparent(canvas)
        self._update_position()
        self._is_active = True
        self.Show()

        # 액션 버튼 위젯을 캔버스 오른쪽 하단에 배치
        self._action_buttons_widget.Reparent(canvas)
        self._action_buttons_widget.Show()
        self._action_buttons_widget.Raise()  # Z-order를 최상위로

        # 위치 업데이트 (오른쪽 하단)
        wx.CallAfter(self._update_action_buttons_position)

        # 저장 버튼 비활성화 (편집 모드 진입)
        if hasattr(self._main_window, '_set_save_buttons_enabled'):
            self._main_window._set_save_buttons_enabled(False)

        self._on_activated()

    def hide_from_canvas(self):
        """캔버스에서 툴바 숨기기"""
        self._is_active = False
        self._on_deactivated()
        self.Hide()

        # 액션 버튼 위젯도 숨김
        self._action_buttons_widget.Hide()

        # 툴바 버튼 다시 활성화
        if hasattr(self._main_window, '_icon_toolbar'):
            self._main_window._icon_toolbar.set_edit_mode(False)

        # 저장 버튼 다시 활성화 (편집 모드 종료)
        if hasattr(self._main_window, '_set_save_buttons_enabled'):
            self._main_window._set_save_buttons_enabled(True)

        # main_window의 active_inline_toolbar 초기화
        if hasattr(self._main_window, '_active_inline_toolbar'):
            self._main_window._active_inline_toolbar = None

    def is_active(self) -> bool:
        """툴바 활성화 상태 반환"""
        return self._is_active

    def set_clear_button_visible(self, visible: bool):
        """지우기 버튼 표시 여부 설정"""
        if visible:
            self._clear_btn.Show()
        else:
            self._clear_btn.Hide()
        self._buttons_sizer.Layout()

    def _update_position(self):
        """캔버스 크기에 맞게 위치 업데이트"""
        if self._canvas and not self._updating_position:
            self._updating_position = True
            try:
                canvas_width = self._canvas.GetSize().width
                if canvas_width <= 0:
                    return

                toolbar_width = canvas_width - 2 * self.TOOLBAR_MARGIN

                # 프리뷰 창 상단에 정렬
                self.SetPosition((self.TOOLBAR_MARGIN, self.TOOLBAR_MARGIN))

                # 컨트롤 영역이 전체 너비 사용
                controls_width = toolbar_width - 16

                # 컨트롤 위젯 크기 설정
                self._controls_widget.SetMinSize((controls_width, -1))

                # 필요한 높이 계산
                best_size = self.GetBestSize()
                toolbar_height = max(self.TOOLBAR_MIN_HEIGHT, best_size.height)

                self.SetSize((toolbar_width, toolbar_height))

                # 액션 버튼 위치도 업데이트
                self._update_action_buttons_position()
            finally:
                self._updating_position = False

    def _update_action_buttons_position(self):
        """액션 버튼 위젯을 캔버스 오른쪽 하단에 배치"""
        if self._canvas and self._action_buttons_widget.IsShown():
            # 버튼 위젯 크기 계산
            self._action_buttons_widget.Fit()
            btn_width = self._action_buttons_widget.GetSize().width
            btn_height = self._action_buttons_widget.GetSize().height

            # 오른쪽 하단 위치 계산
            margin = self.TOOLBAR_MARGIN
            canvas_width = self._canvas.GetSize().width
            canvas_height = self._canvas.GetSize().height

            x = canvas_width - btn_width - margin
            y = canvas_height - btn_height - margin

            self._action_buttons_widget.SetPosition((x, y))

    # === 서브클래스에서 오버라이드할 메서드 ===

    def _on_activated(self):
        """툴바가 활성화될 때 호출 (서브클래스에서 오버라이드)"""
        pass

    def _on_deactivated(self):
        """툴바가 비활성화될 때 호출 (서브클래스에서 오버라이드)"""
        pass

    def _on_clear(self, event):
        """지우기/초기화 버튼 클릭 (서브클래스에서 오버라이드)"""
        print("초기화 버튼 클릭됨")
        # 서브클래스에서 오버라이드하여 구현

    def _on_apply(self, event):
        """적용 버튼 클릭 (서브클래스에서 오버라이드)"""
        print("적용 버튼 클릭됨")
        # PyQt6 원본과 동일: 이벤트만 발생, hide_from_canvas()는 서브클래스에서 호출
        wx.PostEvent(self, ToolbarAppliedEvent())

    def _on_cancel(self, event):
        """취소 버튼 클릭"""
        print("취소 버튼 클릭됨")
        wx.PostEvent(self, ToolbarCancelledEvent())
        self.hide_from_canvas()

    def update_preview(self):
        """미리보기 업데이트 (서브클래스에서 오버라이드)"""
        wx.PostEvent(self, ToolbarPreviewUpdatedEvent())

    def reset_to_default(self):
        """기본값으로 초기화 (서브클래스에서 오버라이드)"""
        pass

    # === 유틸리티 메서드 ===

    def add_control(self, widget: wx.Window):
        """컨트롤 영역에 위젯 추가"""
        self._controls_sizer.Add(widget, 0, wx.ALL, 5)

    def add_icon_label(self, icon_type: str, size: int = 20, tooltip: str = None) -> wx.StaticBitmap:
        """아이콘 라벨 추가

        Args:
            icon_type: 아이콘 타입
            size: 아이콘 크기
            tooltip: 툴팁 텍스트

        Returns:
            wx.StaticBitmap: 생성된 아이콘 라벨
        """
        # 간단한 아이콘 생성 (실제로는 IconFactory 사용)
        bitmap = wx.Bitmap(size, size)
        dc = wx.MemoryDC(bitmap)
        dc.SetBackground(wx.Brush(wx.Colour(100, 100, 100)))
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
        separator.SetMinSize((1, 30))
        separator.SetBackgroundColour(wx.Colour(85, 85, 85))
        self._controls_sizer.Add(separator, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 5)

    def add_label(self, text: str) -> wx.StaticText:
        """라벨 추가"""
        label = wx.StaticText(self._controls_widget, label=text)
        label.SetForegroundColour(wx.Colour(255, 255, 255))
        self._controls_sizer.Add(label, 0, wx.ALIGN_CENTER_VERTICAL | wx.ALL, 5)
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
        except Exception as e:
            print(f"캔버스 업데이트 오류: {e}")

    def _safe_get_canvas(self):
        """캔버스를 안전하게 가져오기"""
        try:
            if self._main_window and hasattr(self._main_window, '_canvas') and self._main_window._canvas:
                return self._main_window._canvas
        except Exception as e:
            print(f"캔버스 접근 오류: {e}")
        return None

    # === 공통 유틸리티 메서드 ===

    def update_color_button(self, button: wx.Button, color: wx.Colour):
        """색상 버튼 스타일 업데이트 (공통 메서드)

        Args:
            button: 업데이트할 버튼
            color: 표시할 색상
        """
        button.SetBackgroundColour(color)
        button.Refresh()

    def pick_color(self, current_color: wx.Colour, title: str = "색상 선택",
                   on_color_picked: Optional[Callable[[wx.Colour], None]] = None) -> Optional[wx.Colour]:
        """색상 선택 다이얼로그 표시 (공통 메서드)

        Args:
            current_color: 현재 색상
            title: 다이얼로그 제목
            on_color_picked: 색상 선택 후 호출할 콜백 함수 (선택사항)

        Returns:
            선택된 색상 또는 None (취소 시)
        """
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
        self._clear_btn.SetToolTip(translations.tr("toolbar_clear"))
        self._apply_btn.SetToolTip(translations.tr("toolbar_apply"))
        self._cancel_btn.SetToolTip(translations.tr("toolbar_cancel"))
