"""
PencilDialog - 펜슬 설정 다이얼로그 (wxPython 버전)

PyQt6 QDialog를 wx.Dialog로 마이그레이션
"""
import wx
from typing import TYPE_CHECKING, Tuple
from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class PencilDialog(wx.Dialog):
    """펜슬 설정 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="펜슬 설정", size=(400, 500))
        self._main_window = main_window
        self._pencil_color = wx.Colour(255, 0, 0)  # 기본 빨간색
        self._pencil_width = 3
        self._duration = 1.0  # 초 단위
        self._target_mode = 1  # 0: 모두, 1: 선택, 2: 현재
        self._auto_animation = True

        self._setup_ui()
        self._update_preview()

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(15)

        # === 미리보기 ===
        preview_box = wx.StaticBox(self, label="미리보기")
        preview_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        preview_sizer = wx.StaticBoxSizer(preview_box, wx.VERTICAL)
        preview_sizer.AddSpacer(10)

        self._preview_panel = wx.Panel(self, size=(200, 100))
        self._preview_panel.SetBackgroundColour(wx.Colour(255, 255, 255))
        self._preview_panel.Bind(wx.EVT_PAINT, self._on_preview_paint)
        preview_sizer.Add(self._preview_panel, 0, wx.ALIGN_CENTER | wx.ALL, 10)

        main_sizer.Add(preview_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # === 색상 설정 ===
        color_box = wx.StaticBox(self, label="펜 색상")
        color_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        color_sizer = wx.StaticBoxSizer(color_box, wx.HORIZONTAL)
        color_sizer.AddSpacer(10)

        self._color_preview = wx.Panel(self, size=(40, 40))
        self._color_preview.SetBackgroundColour(self._pencil_color)
        color_sizer.Add(self._color_preview, 0, wx.ALL, 5)

        color_btn = wx.Button(self, label="색상 선택")
        color_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        color_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        color_btn.Bind(wx.EVT_BUTTON, self._select_color)
        color_sizer.Add(color_btn, 0, wx.ALL, 5)

        color_sizer.AddStretchSpacer()

        main_sizer.Add(color_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # === 두께 설정 ===
        width_box = wx.StaticBox(self, label="펜 두께")
        width_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        width_sizer = wx.StaticBoxSizer(width_box, wx.VERTICAL)
        width_sizer.AddSpacer(10)

        width_control = wx.BoxSizer(wx.HORIZONTAL)

        self._width_slider = wx.Slider(self, value=self._pencil_width,
                                      minValue=1, maxValue=20,
                                      style=wx.SL_HORIZONTAL)
        self._width_slider.SetBackgroundColour(Colors.BG_PRIMARY)
        self._width_slider.Bind(wx.EVT_SLIDER, self._on_width_changed)
        width_control.Add(self._width_slider, 1, wx.ALIGN_CENTER_VERTICAL)

        self._width_label = wx.StaticText(self, label=f"{self._pencil_width}px")
        self._width_label.SetMinSize((50, -1))
        self._width_label.SetForegroundColour(Colors.TEXT_MUTED)
        width_control.Add(self._width_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 10)

        width_sizer.Add(width_control, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(width_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # === 지속 시간 설정 ===
        duration_box = wx.StaticBox(self, label="표시 지속 시간")
        duration_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        duration_sizer = wx.StaticBoxSizer(duration_box, wx.VERTICAL)
        duration_sizer.AddSpacer(10)

        duration_row = wx.BoxSizer(wx.HORIZONTAL)
        duration_row.AddSpacer(10)

        self._duration_spin = wx.SpinCtrlDouble(self, min=0.1, max=30.0,
                                                initial=self._duration, inc=0.1)
        self._duration_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._duration_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._duration_spin.SetDigits(1)
        self._duration_spin.SetMinSize((100, 40))
        duration_row.Add(self._duration_spin, 0, wx.ALIGN_CENTER_VERTICAL)

        unit_label = wx.StaticText(self, label=" 초")
        unit_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        duration_row.Add(unit_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT, 5)

        duration_row.AddStretchSpacer()

        # 설명
        desc_label = wx.StaticText(self, label="선택한 프레임부터 지정된 시간 동안\n그린 선이 표시됩니다.")
        desc_label.SetForegroundColour(Colors.TEXT_MUTED)
        font = desc_label.GetFont()
        font.SetPointSize(9)
        desc_label.SetFont(font)
        duration_row.Add(desc_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        duration_sizer.Add(duration_row, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(duration_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # === 적용 대상/애니메이션 설정 ===
        target_box = wx.StaticBox(self, label="적용 대상")
        target_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        target_sizer = wx.StaticBoxSizer(target_box, wx.HORIZONTAL)
        target_sizer.AddSpacer(10)

        target_label = wx.StaticText(self, label="대상:")
        target_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        target_sizer.Add(target_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._target_combo = wx.ComboBox(self, style=wx.CB_READONLY,
                                        choices=["모두", "선택", "현재"])
        self._target_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._target_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._target_combo.SetSelection(self._target_mode)
        self._target_combo.SetMinSize((90, -1))
        target_sizer.Add(self._target_combo, 0, wx.ALIGN_CENTER_VERTICAL)

        target_sizer.AddStretchSpacer()

        self._auto_anim_check = wx.CheckBox(self, label="Auto Animation")
        self._auto_anim_check.SetValue(self._auto_animation)
        self._auto_anim_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        target_sizer.Add(self._auto_anim_check, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        main_sizer.Add(target_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddStretchSpacer()

        # === 버튼 ===
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        cancel_btn = wx.Button(self, wx.ID_CANCEL, label="취소")
        cancel_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        cancel_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        cancel_btn.SetMinSize((80, 32))
        button_sizer.Add(cancel_btn, 0, wx.ALL, 5)

        ok_btn = wx.Button(self, wx.ID_OK, label="그리기 시작")
        ok_btn.SetBackgroundColour(Colors.ACCENT)
        ok_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        ok_btn.SetMinSize((100, 32))
        button_sizer.Add(ok_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        self.SetSizer(main_sizer)

    def _select_color(self, event):
        """색상 선택"""
        data = wx.ColourData()
        data.SetColour(self._pencil_color)

        dlg = wx.ColourDialog(self, data)
        if dlg.ShowModal() == wx.ID_OK:
            color = dlg.GetColourData().GetColour()
            self._pencil_color = color
            self._color_preview.SetBackgroundColour(color)
            self._color_preview.Refresh()
            self._update_preview()

        dlg.Destroy()

    def _on_width_changed(self, event):
        """두께 변경"""
        value = self._width_slider.GetValue()
        self._pencil_width = value
        self._width_label.SetLabel(f"{value}px")
        self._update_preview()

    def _update_preview(self):
        """미리보기 업데이트"""
        self._preview_panel.Refresh()

    def _on_preview_paint(self, event):
        """미리보기 그리기"""
        dc = wx.PaintDC(self._preview_panel)
        dc.Clear()

        # 펜 설정
        pen = wx.Pen(self._pencil_color, self._pencil_width, wx.PENSTYLE_SOLID)
        pen.SetCap(wx.CAP_ROUND)
        pen.SetJoin(wx.JOIN_ROUND)
        dc.SetPen(pen)

        # 샘플 곡선 그리기
        dc.DrawSpline([
            wx.Point(20, 50),
            wx.Point(50, 20),
            wx.Point(100, 80),
            wx.Point(130, 50),
            wx.Point(150, 30),
            wx.Point(170, 60),
            wx.Point(180, 50)
        ])

    def get_settings(self) -> Tuple[wx.Colour, int, float, int, bool]:
        """설정 반환 (색상, 두께, 지속시간, 대상, Auto Animation)"""
        target_mode = self._target_combo.GetSelection()
        auto_anim = self._auto_anim_check.GetValue()
        return (
            self._pencil_color,
            self._pencil_width,
            self._duration_spin.GetValue(),
            target_mode,
            auto_anim
        )
