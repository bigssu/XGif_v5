"""
CropDialog - 이미지 자르기 다이얼로그 (wxPython 버전)

간소화 버전: 스핀박스로 좌표 입력
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Tuple
from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class CropDialog(wx.Dialog):
    """크롭 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="이미지 자르기", size=(380, 400))
        self._main_window = main_window
        self._img_width = 0
        self._img_height = 0

        self._setup_ui()
        self._load_current_size()

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 현재 크기 표시
        self._info_label = wx.StaticText(self, label="")
        self._info_label.SetForegroundColour(Colors.TEXT_MUTED)
        main_sizer.Add(self._info_label, 0, wx.ALL, 20)

        # 크롭 영역 그룹
        crop_box = wx.StaticBox(self, label="크롭 영역")
        crop_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        crop_sizer = wx.StaticBoxSizer(crop_box, wx.VERTICAL)
        crop_sizer.AddSpacer(10)

        # X 좌표
        x_sizer = wx.BoxSizer(wx.HORIZONTAL)
        x_label = wx.StaticText(self, label="X:")
        x_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        x_sizer.Add(x_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self._x_spin = wx.SpinCtrl(self, min=0, max=10000, initial=0)
        x_sizer.Add(self._x_spin, 1)
        crop_sizer.Add(x_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # Y 좌표
        y_sizer = wx.BoxSizer(wx.HORIZONTAL)
        y_label = wx.StaticText(self, label="Y:")
        y_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        y_sizer.Add(y_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self._y_spin = wx.SpinCtrl(self, min=0, max=10000, initial=0)
        y_sizer.Add(self._y_spin, 1)
        crop_sizer.Add(y_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 너비
        w_sizer = wx.BoxSizer(wx.HORIZONTAL)
        w_label = wx.StaticText(self, label="너비:")
        w_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        w_sizer.Add(w_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self._w_spin = wx.SpinCtrl(self, min=1, max=10000, initial=100)
        w_sizer.Add(self._w_spin, 1)
        crop_sizer.Add(w_sizer, 0, wx.EXPAND | wx.ALL, 10)

        # 높이
        h_sizer = wx.BoxSizer(wx.HORIZONTAL)
        h_label = wx.StaticText(self, label="높이:")
        h_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        h_sizer.Add(h_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        self._h_spin = wx.SpinCtrl(self, min=1, max=10000, initial=100)
        h_sizer.Add(self._h_spin, 1)
        crop_sizer.Add(h_sizer, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(crop_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 프리셋 버튼
        preset_box = wx.StaticBox(self, label="크기 프리셋")
        preset_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        preset_sizer = wx.StaticBoxSizer(preset_box, wx.VERTICAL)
        preset_sizer.AddSpacer(10)

        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        for label in ["전체", "중앙 1/2", "중앙 3/4"]:
            btn = wx.Button(self, label=label)
            btn.SetBackgroundColour(Colors.BORDER)
            btn.SetForegroundColour(Colors.TEXT_PRIMARY)
            btn.Bind(wx.EVT_BUTTON, lambda e, l=label: self._apply_preset(l))
            btn_sizer.Add(btn, 1, wx.ALL, 3)

        preset_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.ALL, 10)
        main_sizer.Add(preset_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddStretchSpacer()

        # 버튼
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

    def _load_current_size(self):
        """현재 크기 로드"""
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return

            self._img_width = getattr(frames, 'width', 100)
            self._img_height = getattr(frames, 'height', 100)

            self._info_label.SetLabel(f"이미지 크기: {self._img_width} x {self._img_height} px")

            self._x_spin.SetMax(self._img_width)
            self._y_spin.SetMax(self._img_height)
            self._w_spin.SetMax(self._img_width)
            self._h_spin.SetMax(self._img_height)

            # 초기값: 전체
            self._w_spin.SetValue(self._img_width)
            self._h_spin.SetValue(self._img_height)
        except Exception:
            pass

    def _apply_preset(self, preset: str):
        """프리셋 적용"""
        if preset == "전체":
            self._x_spin.SetValue(0)
            self._y_spin.SetValue(0)
            self._w_spin.SetValue(self._img_width)
            self._h_spin.SetValue(self._img_height)
        elif preset == "중앙 1/2":
            w = self._img_width // 2
            h = self._img_height // 2
            self._x_spin.SetValue(self._img_width // 4)
            self._y_spin.SetValue(self._img_height // 4)
            self._w_spin.SetValue(w)
            self._h_spin.SetValue(h)
        elif preset == "중앙 3/4":
            w = self._img_width * 3 // 4
            h = self._img_height * 3 // 4
            self._x_spin.SetValue(self._img_width // 8)
            self._y_spin.SetValue(self._img_height // 8)
            self._w_spin.SetValue(w)
            self._h_spin.SetValue(h)

    def get_crop_rect(self) -> Tuple[int, int, int, int]:
        """크롭 영역 반환 (x, y, width, height)"""
        return (
            self._x_spin.GetValue(),
            self._y_spin.GetValue(),
            self._w_spin.GetValue(),
            self._h_spin.GetValue()
        )
