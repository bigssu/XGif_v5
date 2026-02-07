"""
SpeedDialog - 속도 조절 다이얼로그 (wxPython 버전)

PyQt6 QDialog를 wx.Dialog로 마이그레이션
"""
import wx
from typing import TYPE_CHECKING

from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class SpeedDialog(wx.Dialog):
    """속도 조절 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="속도 조절", size=(450, 320))
        self._main_window = main_window

        self._setup_ui()
        self._load_current_info()

    def _setup_ui(self):
        """UI 초기화"""
        # 배경색 설정
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        # 메인 레이아웃
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 현재 정보
        self._info_label = wx.StaticText(self, label="")
        self._info_label.SetForegroundColour(Colors.TEXT_MUTED)
        font = self._info_label.GetFont()
        font.SetPointSize(10)
        self._info_label.SetFont(font)
        main_sizer.Add(self._info_label, 0, wx.ALL | wx.EXPAND, 20)

        # 속도 배율 그룹
        speed_box = wx.StaticBox(self, label="속도 배율")
        speed_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        speed_sizer = wx.StaticBoxSizer(speed_box, wx.VERTICAL)
        speed_sizer.AddSpacer(10)

        # 슬라이더 + 스핀박스
        slider_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._speed_slider = wx.Slider(
            self, value=100, minValue=10, maxValue=400,
            style=wx.SL_HORIZONTAL
        )
        self._speed_slider.Bind(wx.EVT_SLIDER, self._on_slider_changed)
        slider_sizer.Add(self._speed_slider, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._speed_spin = wx.SpinCtrlDouble(
            self, value="1.0", min=0.1, max=4.0, inc=0.1
        )
        self._speed_spin.SetDigits(2)
        self._speed_spin.SetSize((80, -1))
        self._speed_spin.Bind(wx.EVT_SPINCTRLDOUBLE, self._on_spin_changed)
        slider_sizer.Add(self._speed_spin, 0, wx.ALIGN_CENTER_VERTICAL)

        speed_sizer.Add(slider_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 10)
        speed_sizer.AddSpacer(10)

        # 설명
        desc_label = wx.StaticText(
            self,
            label="1.0x = 원래 속도, 2.0x = 2배 빠르게, 0.5x = 2배 느리게"
        )
        desc_label.SetForegroundColour(Colors.TEXT_MUTED)
        font = desc_label.GetFont()
        font.SetPointSize(9)
        desc_label.SetFont(font)
        speed_sizer.Add(desc_label, 0, wx.ALL, 10)

        main_sizer.Add(speed_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 프리셋 버튼
        preset_sizer = wx.BoxSizer(wx.HORIZONTAL)
        preset_sizer.AddSpacer(20)

        for speed in [0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0]:
            btn = wx.Button(self, label=f"{speed}x")
            btn.SetMinSize((60, -1))
            btn.SetBackgroundColour(Colors.BORDER)
            btn.SetForegroundColour(Colors.TEXT_PRIMARY)
            btn.Bind(wx.EVT_BUTTON, lambda e, s=speed: self._apply_preset(s))
            preset_sizer.Add(btn, 0, wx.ALL, 3)

        preset_sizer.AddSpacer(20)
        main_sizer.Add(preset_sizer, 0, wx.EXPAND)
        main_sizer.AddSpacer(10)

        # 결과 예상
        self._result_label = wx.StaticText(self, label="")
        self._result_label.SetForegroundColour(Colors.INFO)
        font = self._result_label.GetFont()
        font.SetPointSize(11)
        self._result_label.SetFont(font)
        main_sizer.Add(self._result_label, 0, wx.ALL, 20)

        main_sizer.AddStretchSpacer()

        # 버튼 (적용/취소)
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        apply_btn = wx.Button(self, wx.ID_OK, label="적용")
        apply_btn.SetBackgroundColour(Colors.ACCENT)
        apply_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        apply_btn.SetMinSize((80, 32))
        button_sizer.Add(apply_btn, 0, wx.ALL, 5)

        cancel_btn = wx.Button(self, wx.ID_CANCEL, label="취소")
        cancel_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        cancel_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        cancel_btn.SetMinSize((80, 32))
        button_sizer.Add(cancel_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        self.SetSizer(main_sizer)

    def _load_current_info(self):
        """현재 정보 로드"""
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return

            total_ms = sum(f.delay_ms for f in frames)
            self._original_duration = total_ms
            frame_count = getattr(frames, 'frame_count', 0)
            self._info_label.SetLabel(
                f"현재 재생 시간: {total_ms / 1000:.2f}초 ({frame_count}프레임)"
            )
            self._update_result()
        except Exception:
            pass

    def _on_slider_changed(self, event):
        """슬라이더 변경"""
        value = self._speed_slider.GetValue()
        speed = value / 100.0

        # 스핀박스 업데이트 (이벤트 차단)
        self._speed_spin.SetValue(speed)
        self._update_result()

    def _on_spin_changed(self, event):
        """스핀박스 변경"""
        value = self._speed_spin.GetValue()

        # 슬라이더 업데이트 (이벤트 차단)
        self._speed_slider.SetValue(int(value * 100))
        self._update_result()

    def _apply_preset(self, speed: float):
        """프리셋 적용"""
        self._speed_spin.SetValue(speed)

    def _update_result(self):
        """결과 예상 업데이트"""
        try:
            if hasattr(self, '_original_duration'):
                val = self._speed_spin.GetValue()
                if val <= 0:
                    val = 1.0
                new_duration = self._original_duration / val
                self._result_label.SetLabel(
                    f"변경 후 재생 시간: {new_duration / 1000:.2f}초"
                )
        except Exception:
            pass

    def get_speed_multiplier(self) -> float:
        """속도 배율 반환"""
        return self._speed_spin.GetValue()
