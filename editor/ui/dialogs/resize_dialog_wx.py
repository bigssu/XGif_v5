"""
ResizeDialog - 이미지 크기 조절 다이얼로그 (wxPython 버전)

PyQt6 QDialog를 wx.Dialog로 마이그레이션
"""
import wx
from PIL import Image
from typing import TYPE_CHECKING, Tuple
from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class ResizeDialog(wx.Dialog):
    """리사이즈 다이얼로그 (wxPython)"""

    # 리샘플링 방법
    RESAMPLE_METHODS = {
        "Nearest (빠름)": Image.Resampling.NEAREST,
        "Bilinear": Image.Resampling.BILINEAR,
        "Bicubic (권장)": Image.Resampling.BICUBIC,
        "Lanczos (고품질)": Image.Resampling.LANCZOS,
    }

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="크기 조절", size=(400, 380))
        self._main_window = main_window
        self._original_width = 0
        self._original_height = 0
        self._aspect_ratio = 1.0
        self._updating = False

        self._setup_ui()
        self._load_current_size()

    def _setup_ui(self):
        """UI 초기화"""
        # 배경색 설정
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        # 메인 레이아웃
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 현재 크기 표시
        self._info_label = wx.StaticText(self, label="")
        self._info_label.SetForegroundColour(Colors.TEXT_MUTED)
        font = self._info_label.GetFont()
        font.SetPointSize(10)
        self._info_label.SetFont(font)
        main_sizer.Add(self._info_label, 0, wx.ALL, 20)

        # 크기 설정 그룹
        size_box = wx.StaticBox(self, label="새 크기")
        size_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        size_sizer = wx.StaticBoxSizer(size_box, wx.VERTICAL)
        size_sizer.AddSpacer(10)

        # 너비
        width_sizer = wx.BoxSizer(wx.HORIZONTAL)
        width_label = wx.StaticText(self, label="너비:")
        width_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        width_sizer.Add(width_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._width_spin = wx.SpinCtrl(self, min=1, max=10000, initial=100)
        self._width_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._width_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._width_spin.SetSize((100, -1))
        self._width_spin.Bind(wx.EVT_SPINCTRL, self._on_width_changed)
        width_sizer.Add(self._width_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        px_label1 = wx.StaticText(self, label="px")
        px_label1.SetForegroundColour(Colors.TEXT_SECONDARY)
        width_sizer.Add(px_label1, 0, wx.ALIGN_CENTER_VERTICAL)

        size_sizer.Add(width_sizer, 0, wx.ALL, 10)

        # 높이
        height_sizer = wx.BoxSizer(wx.HORIZONTAL)
        height_label = wx.StaticText(self, label="높이:")
        height_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        height_sizer.Add(height_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._height_spin = wx.SpinCtrl(self, min=1, max=10000, initial=100)
        self._height_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._height_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._height_spin.SetSize((100, -1))
        self._height_spin.Bind(wx.EVT_SPINCTRL, self._on_height_changed)
        height_sizer.Add(self._height_spin, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 5)

        px_label2 = wx.StaticText(self, label="px")
        px_label2.SetForegroundColour(Colors.TEXT_SECONDARY)
        height_sizer.Add(px_label2, 0, wx.ALIGN_CENTER_VERTICAL)

        size_sizer.Add(height_sizer, 0, wx.ALL, 10)

        # 비율 유지 체크박스
        self._keep_ratio_check = wx.CheckBox(self, label="가로세로 비율 유지")
        self._keep_ratio_check.SetValue(True)
        self._keep_ratio_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        size_sizer.Add(self._keep_ratio_check, 0, wx.ALL, 10)

        main_sizer.Add(size_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 리샘플링 방법 그룹
        method_box = wx.StaticBox(self, label="리샘플링 방법")
        method_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        method_sizer = wx.StaticBoxSizer(method_box, wx.VERTICAL)
        method_sizer.AddSpacer(10)

        self._method_combo = wx.ComboBox(
            self, style=wx.CB_READONLY,
            choices=list(self.RESAMPLE_METHODS.keys())
        )
        self._method_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._method_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._method_combo.SetSelection(2)  # Bicubic 기본
        method_sizer.Add(self._method_combo, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(method_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 프리셋 그룹
        preset_box = wx.StaticBox(self, label="크기 프리셋")
        preset_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        preset_sizer = wx.StaticBoxSizer(preset_box, wx.VERTICAL)
        preset_sizer.AddSpacer(10)

        self._preset_combo = wx.ComboBox(
            self, style=wx.CB_READONLY,
            choices=["50%", "75%", "100%", "150%", "200%"]
        )
        self._preset_combo.SetBackgroundColour(Colors.BG_TERTIARY)
        self._preset_combo.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._preset_combo.SetSelection(2)  # 100% 기본
        self._preset_combo.Bind(wx.EVT_COMBOBOX, self._on_preset_changed)
        preset_sizer.Add(self._preset_combo, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(preset_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

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

    def _load_current_size(self):
        """현재 크기 로드"""
        try:
            frames = getattr(self._main_window, 'frames', None)
            if not frames or getattr(frames, 'is_empty', True):
                return

            self._original_width = getattr(frames, 'width', 100)
            self._original_height = getattr(frames, 'height', 100)
            self._aspect_ratio = (
                self._original_width / self._original_height
                if self._original_height > 0 else 1.0
            )

            self._info_label.SetLabel(
                f"현재 크기: {self._original_width} x {self._original_height} px"
            )

            self._updating = True
            self._width_spin.SetValue(self._original_width)
            self._height_spin.SetValue(self._original_height)
            self._updating = False
        except Exception:
            pass

    def _on_width_changed(self, event):
        """너비 변경"""
        if self._updating:
            return

        if self._keep_ratio_check.GetValue() and self._aspect_ratio > 0:
            self._updating = True
            value = self._width_spin.GetValue()
            new_height = int(value / self._aspect_ratio)
            self._height_spin.SetValue(new_height)
            self._updating = False

    def _on_height_changed(self, event):
        """높이 변경"""
        if self._updating:
            return

        if self._keep_ratio_check.GetValue():
            self._updating = True
            value = self._height_spin.GetValue()
            new_width = int(value * self._aspect_ratio)
            self._width_spin.SetValue(new_width)
            self._updating = False

    def _on_preset_changed(self, event):
        """프리셋 드롭다운 변경"""
        scales = [0.5, 0.75, 1.0, 1.5, 2.0]
        index = self._preset_combo.GetSelection()
        if 0 <= index < len(scales):
            scale = scales[index]
            self._apply_preset(scale)

    def _apply_preset(self, scale: float):
        """프리셋 적용"""
        self._updating = True
        self._width_spin.SetValue(int(self._original_width * scale))
        self._height_spin.SetValue(int(self._original_height * scale))
        self._updating = False

    def get_new_size(self) -> Tuple[int, int]:
        """새 크기 반환"""
        return (self._width_spin.GetValue(), self._height_spin.GetValue())

    def get_resample_method(self) -> Image.Resampling:
        """리샘플링 방법 반환"""
        method_name = self._method_combo.GetStringSelection()
        return self.RESAMPLE_METHODS.get(method_name, Image.Resampling.BICUBIC)
