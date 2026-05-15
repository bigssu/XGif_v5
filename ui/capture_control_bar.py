"""
CaptureControlBar - XGif 다크 테마 녹화 컨트롤 바
wxPython 버전
"""
import logging
import wx
from ui.i18n import tr, get_trans_manager
from ui.theme import Colors, Fonts
from ui.design_system import CommandButton, RailIcon
from core.utils import parse_resolution, validate_resolution
from core.events import AppEvent, get_event_bus
import contextlib

logger = logging.getLogger(__name__)


class CustomToggleSwitch(wx.Panel):
    """커스텀 토글 스위치 - Windows 11 스타일"""

    def __init__(self, parent, id=wx.ID_ANY, checked=False):
        super().__init__(parent, id, size=(45, 22))
        self._checked = checked
        self._handle_position = 4.0 if not checked else 27.0
        self._animating = False

        # 색상 설정 (Windows 11 Dark Theme)
        self._off_track_color = Colors.TOGGLE_OFF_TRACK
        self._on_track_color = Colors.ACCENT
        self._off_handle_color = Colors.TOGGLE_OFF_HANDLE
        self._on_handle_color = Colors.TOGGLE_ON_HANDLE

        self.SetMinSize((45, 22))
        self.SetMaxSize((45, 22))
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)

        # apply_dark_theme()가 이 커스텀 위젯의 색상을 덮어쓰지 않도록 표시
        self._skip_auto_theme = True

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
        except (RuntimeError, AttributeError):
            pass

    def OnClick(self, event):
        self.SetChecked(not self._checked)

    def OnPaint(self, event):
        dc = wx.PaintDC(self)
        width, height = self.GetSize()

        bitmap = wx.Bitmap(width, height)
        memdc = wx.MemoryDC(bitmap)

        parent = self.GetParent()
        bg_color = parent.GetBackgroundColour() if parent else Colors.BG_CARD
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
            with contextlib.suppress(Exception):
                self._anim_timer.Stop()


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
        self._on_help_requested = None

        # 배경색
        self.SetBackgroundColour(Colors.RAIL_BG)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetMinSize((-1, 66))
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda e: None)

        # 버튼 다수 생성 중 개별 Refresh 방지 — 완료 후 한 번에 갱신
        self.Freeze()

        # 메인 레이아웃 (inner_panel 없이 직접 배치 — 패널 중첩 크래시 방지)
        main_sizer = wx.BoxSizer(wx.HORIZONTAL)
        main_sizer.Add((20, 0))  # 좌측 패딩
        self.SetSizer(main_sizer)

        # 기본 폰트
        default_font = Fonts.get_font(Fonts.SIZE_DEFAULT)

        # ═══════════════════════════════════════════════════════════════
        # 왼쪽 섹션: 드롭다운 설정들
        # ═══════════════════════════════════════════════════════════════

        # 포맷 선택 (GIF/MP4)
        self.format_combo = wx.ComboBox(self, choices=["GIF", "MP4"],
                                        style=wx.CB_READONLY, size=(70, -1))
        self.format_combo.SetSelection(0)
        self.format_combo.SetToolTip(tr('output_format_tooltip'))
        self.format_combo.Bind(wx.EVT_COMBOBOX, self._on_format_combo_changed)
        self._style_combobox(self.format_combo)
        self.format_combo.SetFont(default_font)
        main_sizer.Add(self.format_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # FPS 라벨
        self.fps_label = wx.StaticText(self, label=tr('fps'))
        self.fps_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        self.fps_label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
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
        main_sizer.Add(self.fps_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # 해상도 선택 (사용자 입력 가능)
        self.resolution_combo = wx.ComboBox(self,
                                            choices=["320 × 240", "640 × 480", "800 × 600", "1024 × 768"],
                                            style=wx.CB_DROPDOWN, size=(108, -1))
        self.resolution_combo.SetSelection(0)
        self.resolution_combo.SetToolTip(tr('resolution_tooltip_custom'))
        self.resolution_combo.Bind(wx.EVT_COMBOBOX, self._on_resolution_combo_changed)
        self.resolution_combo.Bind(wx.EVT_TEXT_ENTER, self._on_resolution_combo_changed)
        self._style_combobox(self.resolution_combo)
        self.resolution_combo.SetFont(default_font)
        main_sizer.Add(self.resolution_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # 품질 선택
        self.quality_combo = wx.ComboBox(self, choices=[tr('high'), tr('medium'), tr('low')],
                                         style=wx.CB_READONLY, size=(68, -1))
        self.quality_combo.SetSelection(0)
        self.quality_combo.SetToolTip(tr('quality_tooltip'))
        self.quality_combo.Bind(wx.EVT_COMBOBOX, self._on_quality_combo_changed)
        self._style_combobox(self.quality_combo)
        self.quality_combo.SetFont(default_font)
        main_sizer.Add(self.quality_combo, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 12)

        # 구분선 1 (커스텀 패널로 색상 제어)
        sep1 = wx.Panel(self, size=(1, 28))
        sep1.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        main_sizer.Add(sep1, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 14)

        # ═══════════════════════════════════════════════════════════════
        # 중앙 섹션: 토글 스위치들
        # ═══════════════════════════════════════════════════════════════

        # 커서 아이콘
        self.cursor_icon = RailIcon(self, "cursor", tr('cursor_tooltip'), size=(24, 24))
        self.cursor_icon.SetToolTip(tr('cursor_tooltip'))
        main_sizer.Add(self.cursor_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # 커서 토글 스위치
        self.cursor_toggle = CustomToggleSwitch(self, checked=True)
        self.cursor_toggle.SetToolTip(tr('cursor_tooltip'))
        self.cursor_toggle.set_changed_callback(self._on_cursor_toggle_changed)
        main_sizer.Add(self.cursor_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 영역 아이콘
        self.region_icon = RailIcon(self, "region", tr('click_highlight_icon_tooltip'), size=(24, 24))
        self.region_icon.SetToolTip(tr('click_highlight_icon_tooltip'))
        main_sizer.Add(self.region_icon, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # 영역 토글 스위치
        self.region_toggle = CustomToggleSwitch(self, checked=False)
        self.region_toggle.SetToolTip(tr('click_highlight_icon_tooltip'))
        self.region_toggle.set_changed_callback(self._on_region_toggle_changed)
        main_sizer.Add(self.region_toggle, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 구분선 2
        sep2 = wx.Panel(self, size=(1, 28))
        sep2.SetBackgroundColour(Colors.DIVIDER_SUBTLE)
        main_sizer.Add(sep2, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 14)

        # ═══════════════════════════════════════════════════════════════
        # 오른쪽 섹션: 플랫 버튼들
        # ═══════════════════════════════════════════════════════════════

        # GPU 상태 버튼 (초기 중립 상태 — 클릭 시 GPU 정보 확인)
        self.gpu_status_button = CommandButton(self, label="GPU", size=(64, 30), icon_type="gpu",
                                               bg_color=Colors.GPU_BTN_OFF,
                                               fg_color=Colors.TEXT_PRIMARY,
                                               hover_color=Colors.GPU_BTN_OFF_HOVER,
                                               border_color=Colors.BORDER_SOFT)
        self.gpu_status_button.SetToolTip(tr('gpu_status_tooltip'))
        self.gpu_status_button.Bind(wx.EVT_BUTTON, self._on_gpu_button_clicked)
        self._on_gpu_click_callback = None
        main_sizer.Add(self.gpu_status_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # REC 버튼
        self.rec_button = CommandButton(self, label="REC", size=(76, 30), icon_type="record",
                                        bg_color=Colors.REC_READY,
                                        fg_color=Colors.TEXT_PRIMARY,
                                        hover_color=Colors.REC_READY_HOVER,
                                        pressed_color=Colors.REC_READY_PRESSED,
                                        border_color=Colors.REC_READY_PRESSED)
        self.rec_button.SetToolTip(tr('rec_tooltip'))
        self.rec_button.Bind(wx.EVT_BUTTON, self._on_rec_button_clicked)
        main_sizer.Add(self.rec_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        # Pause 버튼
        self.pause_btn = CommandButton(self, size=(36, 30), icon_type="pause",
                                       bg_color=Colors.PAUSE_BG,
                                       fg_color=Colors.TEXT_PRIMARY,
                                       hover_color=Colors.PAUSE_HOVER,
                                       pressed_color=Colors.PAUSE_PRESSED,
                                       border_color=Colors.PAUSE_PRESSED)
        self.pause_btn.SetToolTip(tr('pause_tooltip'))
        self.pause_btn.Enable(False)
        self.pause_btn.Bind(wx.EVT_BUTTON, self._on_pause_button_clicked)
        main_sizer.Add(self.pause_btn, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        # 설정 버튼 (아이콘 2배 크기)
        self.settings_button = CommandButton(self, size=(42, 36), icon_type="settings", icon_size=21,
                                             bg_color=Colors.BG_INPUT_DARK,
                                             fg_color=Colors.TEXT_PRIMARY,
                                             hover_color=Colors.BG_HOVER,
                                             border_color=Colors.BORDER)
        self.settings_button.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        self.settings_button.SetToolTip(tr('settings_tooltip'))
        self.settings_button.Bind(wx.EVT_BUTTON, self._on_settings_button_clicked)
        main_sizer.Add(self.settings_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 4)

        # 도움말 버튼
        self.help_button = CommandButton(self, size=(38, 36), icon_type="help", icon_size=21,
                                         bg_color=Colors.BG_INPUT_DARK,
                                         fg_color=Colors.TEXT_PRIMARY,
                                         hover_color=Colors.BG_HOVER,
                                         border_color=Colors.BORDER)
        self.help_button.SetFont(Fonts.get_font(Fonts.SIZE_LG, bold=True))
        self.help_button.SetToolTip(tr('help_tooltip'))
        self.help_button.Bind(wx.EVT_BUTTON, self._on_help_button_clicked)
        main_sizer.Add(self.help_button, 0, wx.ALIGN_CENTER_VERTICAL)

        main_sizer.Add((20, 0))  # 우측 패딩

        self.Layout()
        self.Thaw()  # Freeze() 해제 — 이제 한 번에 화면 갱신

        self.Bind(wx.EVT_SIZE, self._on_control_bar_size)

        # 초기 상태
        self._recording_state = False
        self._paused_state = False
        self._pause_enabled = False
        self._stop_enabled = False

    def _on_control_bar_size(self, event):
        event.Skip()
        self.Refresh(True)

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.BG_PRIMARY
        dc.SetBackground(wx.Brush(parent_bg))
        dc.Clear()

        gc = wx.GraphicsContext.Create(dc)
        if gc:
            pad_x = 8
            pad_y = 5
            gc.SetBrush(wx.Brush(Colors.RAIL_BG))
            gc.SetPen(wx.Pen(Colors.DIVIDER_SUBTLE, 1))
            gc.DrawRoundedRectangle(pad_x, pad_y, w - pad_x * 2, h - pad_y * 2, 9)
            gc.SetPen(wx.Pen(Colors.SURFACE_HIGHLIGHT, 1))
            gc.StrokeLine(pad_x + 10, pad_y + 1, w - pad_x - 10, pad_y + 1)
            gc.SetPen(wx.Pen(Colors.SURFACE_SHADOW, 1))
            gc.StrokeLine(pad_x + 10, h - pad_y - 1, w - pad_x - 10, h - pad_y - 1)

    def _style_combobox(self, combo):
        """콤보박스 스타일"""
        combo.SetBackgroundColour(Colors.BG_INPUT_DARK)
        combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        if hasattr(combo, 'SetBorderColour'):
            combo.SetBorderColour(Colors.BORDER)

    def _style_gpu_button(self, btn, enabled):
        """GPU 버튼 색상 업데이트"""
        if enabled:
            btn.SetBackgroundColour(Colors.GPU_BTN_ON)
            btn.SetHoverColour(Colors.GPU_BTN_ON_HOVER)
        else:
            btn.SetBackgroundColour(Colors.GPU_BTN_OFF)
            btn.SetHoverColour(Colors.GPU_BTN_OFF_HOVER)
        btn.SetForegroundColour(Colors.TEXT_PRIMARY)

    def _apply_ready_style(self):
        """준비 상태 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(Colors.REC_READY)
        self.rec_button.SetHoverColour(Colors.REC_READY_HOVER)
        self.rec_button.SetPressedColour(Colors.REC_READY_PRESSED)
        self.rec_button.SetForegroundColour(Colors.TEXT_PRIMARY)

    def _apply_recording_style(self):
        """녹화 중 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(Colors.REC_RECORDING)
        self.rec_button.SetHoverColour(Colors.REC_RECORDING)
        self.rec_button.SetForegroundColour(Colors.REC_RECORDING_FG)

    def _apply_paused_style(self):
        """일시정지 중 REC 버튼 스타일"""
        self.rec_button.SetBackgroundColour(Colors.REC_PAUSED)
        self.rec_button.SetHoverColour(Colors.REC_PAUSED_HOVER)
        self.rec_button.SetPressedColour(Colors.REC_PAUSED_PRESSED)
        self.rec_button.SetForegroundColour(Colors.TEXT_PRIMARY)

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

    def set_help_requested_callback(self, callback):
        self._on_help_requested = callback

    # ═══════════════════════════════════════════════════════════════
    # 이벤트 핸들러
    # ═══════════════════════════════════════════════════════════════

    def _on_cursor_toggle_changed(self, checked):
        get_event_bus().emit(AppEvent.CURSOR_TOGGLED, checked)
        if self._on_cursor_toggled:
            self._on_cursor_toggled(checked)

    def _on_region_toggle_changed(self, checked):
        get_event_bus().emit(AppEvent.REGION_TOGGLED, checked)
        if self._on_region_toggled:
            self._on_region_toggled(checked)

    def _on_rec_button_clicked(self, event):
        # 녹화 중이면 Stop 동작
        if self._recording_state and not self._paused_state:
            get_event_bus().emit(AppEvent.STOP_CLICKED)
            if self._on_stop_clicked:
                self._on_stop_clicked()
            return
        get_event_bus().emit(AppEvent.RECORDING_REQUESTED)
        if self._on_recording_requested:
            self._on_recording_requested()

    def _on_pause_button_clicked(self, event):
        get_event_bus().emit(AppEvent.PAUSE_CLICKED)
        if self._on_pause_clicked:
            self._on_pause_clicked()

    def _on_stop_button_clicked(self, event):
        get_event_bus().emit(AppEvent.STOP_CLICKED)
        if self._on_stop_clicked:
            self._on_stop_clicked()

    def _on_gpu_button_clicked(self, event):
        get_event_bus().emit(AppEvent.GPU_CLICK)
        if self._on_gpu_click_callback:
            self._on_gpu_click_callback()

    def _on_settings_button_clicked(self, event):
        get_event_bus().emit(AppEvent.SETTINGS_REQUESTED)
        if self._on_settings_requested:
            self._on_settings_requested()

    def _on_help_button_clicked(self, event):
        get_event_bus().emit(AppEvent.HELP_REQUESTED)
        if self._on_help_requested:
            self._on_help_requested()

    def _on_format_combo_changed(self, event):
        fmt = self.format_combo.GetValue()
        get_event_bus().emit(AppEvent.FORMAT_CHANGED, fmt)
        if self._on_format_changed:
            self._on_format_changed(fmt)

    def _on_fps_combo_changed(self, event):
        fps_value = self.fps_combo.GetValue().strip()
        try:
            fps_int = int(fps_value)
            if 1 <= fps_int <= 60:
                get_event_bus().emit(AppEvent.FPS_CHANGED, fps_value)
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
                get_event_bus().emit(AppEvent.RESOLUTION_CHANGED, normalized)
                if self._on_resolution_changed:
                    self._on_resolution_changed(normalized)
            else:
                logger.warning(f"유효하지 않은 해상도: {width}x{height}")
        else:
            get_event_bus().emit(AppEvent.RESOLUTION_CHANGED, text)
            if self._on_resolution_changed:
                self._on_resolution_changed(text)

    def _on_quality_combo_changed(self, event):
        quality_idx = self.quality_combo.GetSelection()
        get_event_bus().emit(AppEvent.QUALITY_CHANGED, quality_idx)
        if self._on_quality_changed:
            self._on_quality_changed(quality_idx)

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
        self.settings_button.SetToolTip(tr('settings_tooltip'))
        self.help_button.SetToolTip(tr('help_tooltip'))

    def _on_destroy(self, event):
        """윈도우 파괴 시 번역 콜백 해제"""
        if event.GetEventObject() is self:
            with contextlib.suppress(Exception):
                self.trans.unregister_callback(self.retranslateUi)
        event.Skip()

    def set_recording_state(self, is_recording, is_paused=False):
        """녹화 상태에 따라 UI 업데이트"""
        self._recording_state = is_recording
        self._paused_state = is_paused

        if is_recording:
            # 녹화 중 → REC 버튼이 STOP 역할
            self.rec_button.SetIconType("stop")
            self.rec_button.SetLabel("STOP")
            self.rec_button.Enable(True)
            self.rec_button.SetBackgroundColour(Colors.ACCENT)
            self.rec_button.SetHoverColour(Colors.ACCENT_HOVER)
            self.rec_button.SetPressedColour(Colors.ACCENT_PRESSED)
            self.rec_button.SetForegroundColour(Colors.TEXT_PRIMARY)
            self.set_pause_enabled(True)
        elif is_paused:
            # 일시정지 → REC 버튼이 재개 역할
            self.rec_button.SetIconType("play")
            self.rec_button.SetLabel("REC")
            self.rec_button.Enable(True)
            self._apply_paused_style()
            self.set_pause_enabled(False)
        else:
            # 준비 상태
            self.rec_button.SetIconType("record")
            self.rec_button.SetLabel("REC")
            self.rec_button.Enable(True)
            self._apply_ready_style()
            self.set_pause_enabled(False)

    def set_cursor_enabled(self, enabled):
        self.cursor_toggle.SetChecked(enabled, trigger_callback=False)

    def set_region_visible(self, visible):
        self.region_toggle.SetChecked(visible, trigger_callback=False)

    def set_pause_enabled(self, enabled):
        self._pause_enabled = enabled
        self.pause_btn.Enable(enabled)

    def set_stop_enabled(self, enabled):
        """호환성 유지용 no-op (Stop 버튼이 REC 토글로 통합됨)"""
        pass

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
