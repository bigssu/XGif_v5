"""
CaptureControlBar - Windows 11 Dark Theme 스타일 녹화 컨트롤 바
플랫 디자인, #202020 다크 배경, #0078D4 Windows Blue 강조색
wxPython 버전
"""
import logging
import wx
from ui.i18n import tr, get_trans_manager
from ui.constants import THEME_MID, get_ui_font, FONT_SIZE_DEFAULT
from core.utils import parse_resolution, validate_resolution

logger = logging.getLogger(__name__)


class FlatButton(wx.Control):
    """Windows 11 스타일 플랫 버튼 (owner-draw).

    네이티브 wx.Button의 3D 베젤을 제거하고 GraphicsContext로
    라운디드 렉트를 그려 플랫한 모던 스타일을 구현합니다.
    """

    def __init__(self, parent, label="", size=wx.DefaultSize,
                 bg_color=None, fg_color=None,
                 hover_color=None, pressed_color=None,
                 corner_radius=4, id=wx.ID_ANY):
        super().__init__(parent, id, pos=wx.DefaultPosition, size=size,
                         style=wx.BORDER_NONE)
        self._label = label
        self._corner_radius = corner_radius
        self._enabled = True

        # 색상 (기본값: THEME_MID 기반)
        self._bg_color = wx.Colour(*(bg_color or THEME_MID.BG_BUTTON))
        self._fg_color = wx.Colour(*(fg_color or THEME_MID.FG_TEXT))
        self._hover_color = wx.Colour(*(hover_color or THEME_MID.BG_BUTTON_HOVER))
        self._pressed_color = wx.Colour(*(pressed_color or THEME_MID.BG_BUTTON_PRESSED))
        self._disabled_fg = wx.Colour(100, 100, 100)
        self._disabled_bg = wx.Colour(50, 50, 50)

        # 상태
        self._hovered = False
        self._pressed = False

        # 비트맵 캐시 (상태 변경 시에만 재생성)
        self._cached_bmp = None
        self._cached_state = None  # (w, h, hovered, pressed, enabled, label)

        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        # 폰트
        self.SetFont(get_ui_font(FONT_SIZE_DEFAULT))

        # 이벤트
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    # --- 공개 API (wx.Button 호환) ---

    def SetLabel(self, label):
        self._label = label
        self.Refresh()

    def GetLabel(self):
        return self._label

    def SetBackgroundColour(self, colour):
        if isinstance(colour, (tuple, list)):
            colour = wx.Colour(*colour)
        self._bg_color = colour
        self.Refresh()

    def SetForegroundColour(self, colour):
        if isinstance(colour, (tuple, list)):
            colour = wx.Colour(*colour)
        self._fg_color = colour
        self.Refresh()

    def SetHoverColour(self, colour):
        if isinstance(colour, (tuple, list)):
            colour = wx.Colour(*colour)
        self._hover_color = colour

    def SetPressedColour(self, colour):
        if isinstance(colour, (tuple, list)):
            colour = wx.Colour(*colour)
        self._pressed_color = colour

    def Enable(self, enable=True):
        self._enabled = enable
        super().Enable(enable)
        if enable:
            self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        else:
            self.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        self.Refresh()

    def Disable(self):
        self.Enable(False)

    def IsEnabled(self):
        return self._enabled

    # --- 내부 이벤트 ---

    def _on_enter(self, event):
        if self._enabled:
            self._hovered = True
            self.Refresh()

    def _on_leave(self, event):
        self._hovered = False
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
        if was_pressed and self._enabled and self._hovered:
            evt = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
            evt.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(evt)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetSize()
        if w <= 0 or h <= 0:
            return

        # 상태 키 생성 (변경 시에만 비트맵 재생성)
        state_key = (w, h, self._hovered, self._pressed, self._enabled, self._label)
        if self._cached_bmp is not None and self._cached_state == state_key:
            dc.DrawBitmap(self._cached_bmp, 0, 0, False)
            return

        bmp = wx.Bitmap(w, h)
        memdc = wx.MemoryDC(bmp)

        # 부모 배경으로 클리어
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else wx.Colour(*THEME_MID.BG_TOOLBAR)
        memdc.SetBackground(wx.Brush(parent_bg))
        memdc.Clear()

        gc = wx.GraphicsContext.Create(memdc)
        if gc:
            # 배경색 결정
            if not self._enabled:
                bg = self._disabled_bg
            elif self._pressed:
                bg = self._pressed_color
            elif self._hovered:
                bg = self._hover_color
            else:
                bg = self._bg_color

            # 라운디드 렉트 배경
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRoundedRectangle(0, 0, w, h, self._corner_radius)

            # 텍스트
            fg = self._disabled_fg if not self._enabled else self._fg_color
            gc.SetFont(self.GetFont(), fg)
            tw, th = gc.GetTextExtent(self._label)[:2]
            tx = (w - tw) / 2
            ty = (h - th) / 2
            gc.DrawText(self._label, tx, ty)

        memdc.SelectObject(wx.NullBitmap)
        # 캐시 갱신
        self._cached_bmp = bmp
        self._cached_state = state_key
        dc.DrawBitmap(bmp, 0, 0, False)


class CustomToggleSwitch(wx.Panel):
    """커스텀 토글 스위치 - Windows 11 스타일"""

    def __init__(self, parent, id=wx.ID_ANY, checked=False):
        super().__init__(parent, id, size=(45, 22))
        self._checked = checked
        self._handle_position = 4.0 if not checked else 27.0
        self._animating = False

        # 색상 설정 (Windows 11 Dark Theme)
        self._off_track_color = wx.Colour(80, 80, 80)
        self._on_track_color = wx.Colour(*THEME_MID.ACCENT)   # #0078D4 Windows Blue
        self._off_handle_color = wx.Colour(160, 160, 160)
        self._on_handle_color = wx.Colour(255, 255, 255)

        self.SetMinSize((45, 22))
        self.SetMaxSize((45, 22))
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        self._on_changed_callback = None
        self._anim_timer = wx.Timer(self)
        self._anim_target = 4.0

        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.Bind(wx.EVT_LEFT_DOWN, self.OnClick)
        self.Bind(wx.EVT_TIMER, self.OnAnimTimer, self._anim_timer)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

    def _on_destroy(self, event):
        """위젯 파괴 시 타이머 명시적 정리 (PyDeadObjectError 방지)"""
        if self._anim_timer:
            self._anim_timer.Stop()
            self._anim_timer = None
        event.Skip()

    def set_changed_callback(self, callback):
        self._on_changed_callback = callback

    def IsChecked(self):
        return self._checked

    def SetChecked(self, checked, trigger_callback=True):
        if self._checked != checked:
            self._checked = checked
            self._animate_handle()
            if trigger_callback and self._on_changed_callback:
                self._on_changed_callback(checked)

    def _animate_handle(self):
        self._anim_target = 27.0 if self._checked else 4.0
        self._animating = True
        self._anim_timer.Start(16)

    def OnAnimTimer(self, event):
        try:
            if not self or not hasattr(self, '_anim_timer'):
                return
            diff = self._anim_target - self._handle_position
            if abs(diff) < 1.0:
                self._handle_position = self._anim_target
                if self._anim_timer:
                    self._anim_timer.Stop()
                self._animating = False
            else:
                self._handle_position += diff * 0.3
            self.Refresh()
        except (RuntimeError, AttributeError, wx.PyDeadObjectError):
            pass

    def OnClick(self, event):
        self.SetChecked(not self._checked)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        width, height = self.GetSize()

        bitmap = wx.Bitmap(width, height)
        memdc = wx.MemoryDC(bitmap)

        parent = self.GetParent()
        bg_color = parent.GetBackgroundColour() if parent else wx.Colour(*THEME_MID.BG_TOOLBAR)
        memdc.SetBackground(wx.Brush(bg_color))
        memdc.Clear()

        gc = wx.GraphicsContext.Create(memdc)
        if gc:
            track_color = self._on_track_color if self._checked else self._off_track_color
            gc.SetBrush(wx.Brush(track_color))
            gc.SetPen(wx.TRANSPARENT_PEN)
            gc.DrawRoundedRectangle(0, 0, width, height, height / 2)

            handle_color = self._on_handle_color if self._checked else self._off_handle_color
            handle_size = 14
            handle_y = (height - handle_size) / 2
            gc.SetBrush(wx.Brush(handle_color))
            gc.DrawEllipse(self._handle_position, handle_y, handle_size, handle_size)

        memdc.SelectObject(wx.NullBitmap)
        dc.DrawBitmap(bitmap, 0, 0, False)

    def __del__(self):
        if hasattr(self, '_anim_timer') and self._anim_timer:
            try:
                self._anim_timer.Stop()
            except Exception:
                pass


class CaptureControlBar(wx.Panel):
    """Windows 11 Dark Theme 스타일 녹화 컨트롤 바

    플랫 버튼, #202020 다크 배경, 최소 10px 여백.
    커서 포함, 영역 표시 토글과 녹화/설정 버튼을 제공합니다.
    """

    def __init__(self, parent):
        super().__init__(parent)
        self.trans = get_trans_manager()
        self.trans.register_callback(self.retranslateUi)

        # 윈도우 파괴 시 번역 콜백 해제
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)

        # 콜백 함수들
        self._on_recording_requested = None
        self._on_stop_requested = None
        self._on_settings_requested = None
        self._on_cursor_toggled = None
        self._on_region_toggled = None
        self._on_format_changed = None
        self._on_fps_changed = None
        self._on_resolution_changed = None
        self._on_quality_changed = None
        self._on_pause_clicked = None
        self._on_stop_clicked = None

        # 배경색 (Windows 11 Dark)
        self.SetBackgroundColour(wx.Colour(*THEME_MID.BG_TOOLBAR))

        # 메인 레이아웃 (inner_panel 없이 직접 배치 — 패널 중첩 크래시 방지)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add((8, 0))  # 좌측 패딩
        self.SetSizer(main_sizer)

        # 기본 폰트
        default_font = get_ui_font(FONT_SIZE_DEFAULT)

        # ═══════════════════════════════════════════════════════════════
        # 왼쪽 섹션: 드롭다운 설정들
        # ═══════════════════════════════════════════════════════════════

        # 포맷 선택 (GIF/MP4)
        self.format_combo = wx.ComboBox(self, choices=["GIF", "MP4"],
                                        style=wx.CB_READONLY, size=(65, -1))
        self.format_combo.SetSelection(0)
        self.format_combo.SetToolTip(tr('output_format_tooltip'))
        self.format_combo.Bind(wx.EVT_COMBOBOX, self._on_format_combo_changed)
        self._style_combobox(self.format_combo)
        self.format_combo.SetFont(default_font)
        main_sizer.Add(self.format_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # FPS 라벨
        self.fps_label = wx.StaticText(self, label=tr('fps'))
        self.fps_label.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT_SECONDARY))
        self.fps_label.SetFont(get_ui_font(FONT_SIZE_DEFAULT, bold=True))
        self.fps_label.SetToolTip(tr('fps_label_tooltip'))
        main_sizer.Add(self.fps_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # FPS 콤보박스
        self.fps_combo = wx.ComboBox(self, choices=["1", "3", "5", "8", "10", "15", "20", "25", "30"],
                                     style=wx.CB_READONLY, size=(60, -1))
        self.fps_combo.SetSelection(5)  # 15 FPS
        self.fps_combo.SetToolTip(tr('fps_tooltip'))
        self.fps_combo.Bind(wx.EVT_COMBOBOX, self._on_fps_combo_changed)
        self._style_combobox(self.fps_combo)
        self.fps_combo.SetFont(default_font)
        main_sizer.Add(self.fps_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 해상도 선택 (사용자 입력 가능)
        self.resolution_combo = wx.ComboBox(self,
                                            choices=["320 × 240", "640 × 480", "800 × 600", "1024 × 768"],
                                            style=wx.CB_DROPDOWN, size=(115, -1))
        self.resolution_combo.SetSelection(0)
        self.resolution_combo.SetToolTip(tr('resolution_tooltip_custom'))
        self.resolution_combo.Bind(wx.EVT_COMBOBOX, self._on_resolution_combo_changed)
        self.resolution_combo.Bind(wx.EVT_TEXT_ENTER, self._on_resolution_combo_changed)
        self._style_combobox(self.resolution_combo)
        self.resolution_combo.SetFont(default_font)
        main_sizer.Add(self.resolution_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 품질 선택
        self.quality_combo = wx.ComboBox(self, choices=[tr('high'), tr('medium'), tr('low')],
                                         style=wx.CB_READONLY, size=(55, -1))
        self.quality_combo.SetSelection(0)
        self.quality_combo.SetToolTip(tr('quality_tooltip'))
        self.quality_combo.Bind(wx.EVT_COMBOBOX, self._on_quality_combo_changed)
        self._style_combobox(self.quality_combo)
        self.quality_combo.SetFont(default_font)
        main_sizer.Add(self.quality_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 구분선 1 (커스텀 패널로 색상 제어)
        sep1 = wx.Panel(self, size=(1, 24))
        sep1.SetBackgroundColour(wx.Colour(*THEME_MID.BORDER_SUBTLE))
        main_sizer.Add(sep1, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 12)

        # ═══════════════════════════════════════════════════════════════
        # 중앙 섹션: 토글 스위치들
        # ═══════════════════════════════════════════════════════════════

        # 커서 아이콘
        self.cursor_icon = wx.StaticText(self, label="↖")
        self.cursor_icon.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT))
        self.cursor_icon.SetBackgroundColour(wx.Colour(*THEME_MID.BG_TOOLBAR))
        self.cursor_icon.SetFont(get_ui_font(12))
        self.cursor_icon.SetToolTip(tr('cursor_tooltip'))
        main_sizer.Add(self.cursor_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # 커서 토글 스위치
        self.cursor_toggle = CustomToggleSwitch(self, checked=True)
        self.cursor_toggle.SetToolTip(tr('cursor_tooltip'))
        self.cursor_toggle.set_changed_callback(self._on_cursor_toggle_changed)
        main_sizer.Add(self.cursor_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 영역 아이콘
        self.region_icon = wx.StaticText(self, label="⬚")
        self.region_icon.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT))
        self.region_icon.SetBackgroundColour(wx.Colour(*THEME_MID.BG_TOOLBAR))
        self.region_icon.SetFont(get_ui_font(14))
        self.region_icon.SetToolTip(tr('click_highlight_icon_tooltip'))
        main_sizer.Add(self.region_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # 영역 토글 스위치
        self.region_toggle = CustomToggleSwitch(self, checked=False)
        self.region_toggle.SetToolTip(tr('click_highlight_icon_tooltip'))
        self.region_toggle.set_changed_callback(self._on_region_toggle_changed)
        main_sizer.Add(self.region_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 구분선 2
        sep2 = wx.Panel(self, size=(1, 24))
        sep2.SetBackgroundColour(wx.Colour(*THEME_MID.BORDER_SUBTLE))
        main_sizer.Add(sep2, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 12)

        # ═══════════════════════════════════════════════════════════════
        # 오른쪽 섹션: 플랫 버튼들
        # ═══════════════════════════════════════════════════════════════

        # GPU 상태 버튼 (초기 중립 상태 — 클릭 시 GPU 정보 확인)
        self.gpu_status_button = FlatButton(self, label="GPU", size=(55, 28),
                                            bg_color=(107, 114, 128), fg_color=(255, 255, 255),
                                            hover_color=(120, 127, 141))
        self.gpu_status_button.SetToolTip(tr('gpu_status_tooltip'))
        self.gpu_status_button.Bind(wx.EVT_BUTTON, self._on_gpu_button_clicked)
        self._on_gpu_click_callback = None
        main_sizer.Add(self.gpu_status_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # REC 버튼
        self.rec_button = FlatButton(self, label="● REC", size=(72, 28),
                                     bg_color=(233, 69, 96), fg_color=(255, 255, 255),
                                     hover_color=(245, 90, 115), pressed_color=(200, 55, 80))
        self.rec_button.SetToolTip(tr('rec_tooltip'))
        self.rec_button.Bind(wx.EVT_BUTTON, self._on_rec_button_clicked)
        main_sizer.Add(self.rec_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        # Pause 버튼
        self.pause_btn = FlatButton(self, label="❚❚", size=(34, 28),
                                    bg_color=(254, 202, 87), fg_color=(255, 255, 255),
                                    hover_color=(255, 215, 110), pressed_color=(230, 180, 70))
        self.pause_btn.SetToolTip(tr('pause_tooltip'))
        self.pause_btn.Enable(False)
        self.pause_btn.Bind(wx.EVT_BUTTON, self._on_pause_button_clicked)
        main_sizer.Add(self.pause_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # Stop 버튼
        self.stop_btn = FlatButton(self, label="■", size=(34, 28),
                                   bg_color=THEME_MID.ACCENT, fg_color=(255, 255, 255),
                                   hover_color=THEME_MID.ACCENT_HOVER,
                                   pressed_color=THEME_MID.ACCENT_PRESSED)
        self.stop_btn.SetToolTip(tr('stop_tooltip'))
        self.stop_btn.Enable(False)
        self.stop_btn.Bind(wx.EVT_BUTTON, self._on_stop_button_clicked)
        main_sizer.Add(self.stop_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 설정 버튼 (아이콘 2배 크기)
        self.settings_button = FlatButton(self, label="⚙", size=(48, 40),
                                          bg_color=THEME_MID.BG_BUTTON,
                                          fg_color=THEME_MID.FG_TEXT,
                                          hover_color=THEME_MID.BG_BUTTON_HOVER)
        self.settings_button.SetFont(get_ui_font(FONT_SIZE_DEFAULT * 2))
        self.settings_button.SetToolTip(tr('settings_tooltip'))
        self.settings_button.Bind(wx.EVT_BUTTON, self._on_settings_button_clicked)
        main_sizer.Add(self.settings_button, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add((8, 0))  # 우측 패딩

        self.Layout()

        self.Bind(wx.EVT_SIZE, self._on_control_bar_size)

        # 초기 상태
        self._recording_state = False
        self._paused_state = False
        self._pause_enabled = False
        self._stop_enabled = False

    def _on_control_bar_size(self, event):
        event.Skip()
        self.Refresh(True)

    def _style_combobox(self, combo):
        """콤보박스 스타일 (Windows 11 Dark)"""
        combo.SetBackgroundColour(wx.Colour(*THEME_MID.BG_TOOLBAR))
        combo.SetForegroundColour(wx.Colour(*THEME_MID.FG_TEXT))

    def _style_gpu_button(self, btn, enabled):
        """GPU 버튼 색상 업데이트"""
        if enabled:
            btn.SetBackgroundColour(wx.Colour(34, 197, 94))
            btn.SetHoverColour(wx.Colour(50, 210, 110))
        else:
            btn.SetBackgroundColour(wx.Colour(107, 114, 128))
            btn.SetHoverColour(wx.Colour(120, 127, 141))
        btn.SetForegroundColour(wx.Colour(255, 255, 255))

    def _apply_ready_style(self):
        """준비 상태 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(wx.Colour(233, 69, 96))
        self.rec_button.SetHoverColour(wx.Colour(245, 90, 115))
        self.rec_button.SetPressedColour(wx.Colour(200, 55, 80))
        self.rec_button.SetForegroundColour(wx.Colour(255, 255, 255))

    def _apply_recording_style(self):
        """녹화 중 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(wx.Colour(107, 114, 128))
        self.rec_button.SetHoverColour(wx.Colour(107, 114, 128))
        self.rec_button.SetForegroundColour(wx.Colour(209, 213, 219))

    def _apply_paused_style(self):
        """일시정지 중 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(wx.Colour(34, 197, 94))
        self.rec_button.SetHoverColour(wx.Colour(50, 210, 110))
        self.rec_button.SetPressedColour(wx.Colour(25, 170, 80))
        self.rec_button.SetForegroundColour(wx.Colour(255, 255, 255))

    # ═══════════════════════════════════════════════════════════════
    # 콜백 설정 메서드
    # ═══════════════════════════════════════════════════════════════

    def set_recording_requested_callback(self, callback):
        self._on_recording_requested = callback

    def set_stop_requested_callback(self, callback):
        self._on_stop_requested = callback

    def set_settings_requested_callback(self, callback):
        self._on_settings_requested = callback

    def set_cursor_toggled_callback(self, callback):
        self._on_cursor_toggled = callback

    def set_region_toggled_callback(self, callback):
        self._on_region_toggled = callback

    def set_format_changed_callback(self, callback):
        self._on_format_changed = callback

    def set_fps_changed_callback(self, callback):
        self._on_fps_changed = callback

    def set_resolution_changed_callback(self, callback):
        self._on_resolution_changed = callback

    def set_quality_changed_callback(self, callback):
        self._on_quality_changed = callback

    def set_pause_clicked_callback(self, callback):
        self._on_pause_clicked = callback

    def set_stop_clicked_callback(self, callback):
        self._on_stop_clicked = callback

    def set_gpu_click_callback(self, callback):
        self._on_gpu_click_callback = callback

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 핸들러
    # ═══════════════════════════════════════════════════════════════

    def _on_cursor_toggle_changed(self, checked):
        if self._on_cursor_toggled:
            self._on_cursor_toggled(checked)

    def _on_region_toggle_changed(self, checked):
        if self._on_region_toggled:
            self._on_region_toggled(checked)

    def _on_rec_button_clicked(self, event):
        if self._on_recording_requested:
            self._on_recording_requested()

    def _on_pause_button_clicked(self, event):
        if self._on_pause_clicked:
            self._on_pause_clicked()

    def _on_stop_button_clicked(self, event):
        if self._on_stop_clicked:
            self._on_stop_clicked()

    def _on_gpu_button_clicked(self, event):
        if self._on_gpu_click_callback:
            self._on_gpu_click_callback()

    def _on_settings_button_clicked(self, event):
        if self._on_settings_requested:
            self._on_settings_requested()

    def _on_format_combo_changed(self, event):
        if self._on_format_changed:
            self._on_format_changed(self.format_combo.GetValue())

    def _on_fps_combo_changed(self, event):
        fps_value = self.fps_combo.GetValue().strip()
        try:
            fps_int = int(fps_value)
            if 1 <= fps_int <= 60:
                if self._on_fps_changed:
                    self._on_fps_changed(fps_value)
        except ValueError:
            pass

    def _on_resolution_combo_changed(self, event):
        text = self.resolution_combo.GetValue()
        if not text or not text.strip():
            return
        # EVT_COMBOBOX 핸들러 내에서 콤보박스/윈도우 조작 시 크래시 방지
        # → CallAfter로 이벤트 처리 완료 후 실행
        wx.CallAfter(self._apply_resolution_text, text)

    def _apply_resolution_text(self, text):
        """해상도 텍스트 파싱 및 적용 (CallAfter에서 호출)"""
        resolution = parse_resolution(text)
        if resolution:
            width, height = resolution
            from ui.constants import MIN_RESOLUTION, MAX_RESOLUTION
            if validate_resolution(width, height, MIN_RESOLUTION, MAX_RESOLUTION):
                normalized = f"{width} × {height}"
                self.resolution_combo.SetValue(normalized)
                if self._on_resolution_changed:
                    self._on_resolution_changed(normalized)
            else:
                logger.warning(f"유효하지 않은 해상도: {width}x{height}")
        else:
            if self._on_resolution_changed:
                self._on_resolution_changed(text)

    def _on_quality_combo_changed(self, event):
        if self._on_quality_changed:
            self._on_quality_changed(self.quality_combo.GetSelection())

    # ═══════════════════════════════════════════════════════════════
    # 공개 메서드
    # ═══════════════════════════════════════════════════════════════

    def retranslateUi(self, lang=None):
        """언어 변경 시 UI 업데이트"""
        self.format_combo.SetToolTip(tr('output_format_tooltip'))
        self.fps_label.SetLabel(tr('fps'))
        self.fps_label.SetToolTip(tr('fps_label_tooltip'))
        self.fps_combo.SetToolTip(tr('fps_tooltip'))
        self.resolution_combo.SetToolTip(tr('resolution_tooltip_custom'))
        self.quality_combo.SetToolTip(tr('quality_tooltip'))

        curr_idx = self.quality_combo.GetSelection()
        self.quality_combo.Clear()
        self.quality_combo.Append(tr('high'))
        self.quality_combo.Append(tr('medium'))
        self.quality_combo.Append(tr('low'))
        self.quality_combo.SetSelection(curr_idx)

        self.cursor_icon.SetToolTip(tr('cursor_tooltip'))
        self.cursor_toggle.SetToolTip(tr('cursor_tooltip'))
        self.region_icon.SetToolTip(tr('click_highlight_icon_tooltip'))
        self.region_toggle.SetToolTip(tr('click_highlight_icon_tooltip'))

        self.gpu_status_button.SetToolTip(tr('gpu_status_tooltip'))
        self.rec_button.SetToolTip(tr('rec_tooltip'))
        self.pause_btn.SetToolTip(tr('pause_tooltip'))
        self.stop_btn.SetToolTip(tr('stop_tooltip'))
        self.settings_button.SetToolTip(tr('settings_tooltip'))

    def _on_destroy(self, event):
        """윈도우 파괴 시 번역 콜백 해제"""
        if event.GetEventObject() is self:
            try:
                self.trans.unregister_callback(self.retranslateUi)
            except Exception:
                pass
        event.Skip()

    def set_recording_state(self, is_recording, is_paused=False):
        """녹화 상태에 따라 UI 업데이트"""
        self._recording_state = is_recording
        self._paused_state = is_paused

        if is_recording:
            self.rec_button.SetLabel("● REC")
            self.rec_button.Enable(False)
            self._apply_recording_style()
            self.set_pause_enabled(True)
            self.set_stop_enabled(True)
        elif is_paused:
            self.rec_button.SetLabel("▶ REC")
            self.rec_button.Enable(True)
            self._apply_paused_style()
            self.set_pause_enabled(False)
            self.set_stop_enabled(True)
        else:
            self.rec_button.SetLabel("● REC")
            self.rec_button.Enable(True)
            self._apply_ready_style()
            self.set_pause_enabled(False)
            self.set_stop_enabled(False)

    def set_cursor_enabled(self, enabled):
        self.cursor_toggle.SetChecked(enabled, trigger_callback=False)

    def set_region_visible(self, visible):
        self.region_toggle.SetChecked(visible, trigger_callback=False)

    def set_pause_enabled(self, enabled):
        self._pause_enabled = enabled
        self.pause_btn.Enable(enabled)

    def set_stop_enabled(self, enabled):
        self._stop_enabled = enabled
        self.stop_btn.Enable(enabled)

    def set_format(self, format_text):
        index = 0 if format_text == "GIF" else 1
        self.format_combo.SetSelection(index)

    def set_fps(self, fps):
        fps_text = str(fps)
        index = self.fps_combo.FindString(fps_text)
        if index != wx.NOT_FOUND:
            self.fps_combo.SetSelection(index)

    def set_resolution(self, resolution):
        if "×" not in resolution:
            resolution = resolution.replace(" x ", " × ").replace("x", " × ")
        index = self.resolution_combo.FindString(resolution)
        if index != wx.NOT_FOUND:
            self.resolution_combo.SetSelection(index)
        else:
            self.resolution_combo.SetValue(resolution)

    def set_quality(self, quality):
        self.quality_combo.SetSelection(quality)

    def set_gpu_status(self, enabled):
        if enabled:
            self.gpu_status_button.SetLabel("GPU On")
        else:
            self.gpu_status_button.SetLabel("GPU Off")
        self._style_gpu_button(self.gpu_status_button, enabled)

    def get_format(self):
        return self.format_combo.GetValue()

    def get_fps(self):
        try:
            return int(self.fps_combo.GetValue())
        except ValueError:
            return 15

    def get_resolution(self):
        return self.resolution_combo.GetValue()

    def get_quality(self):
        return self.quality_combo.GetSelection()
