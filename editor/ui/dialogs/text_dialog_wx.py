"""
TextDialog - 텍스트 추가 다이얼로그 (wxPython 버전)
"""
import wx
from typing import TYPE_CHECKING, Tuple

from ..style_constants_wx import Colors

if TYPE_CHECKING:
    from ..main_window import MainWindow


class TextDialog(wx.Dialog):
    """텍스트 추가 다이얼로그 (wxPython)"""

    def __init__(self, main_window: 'MainWindow', parent=None):
        super().__init__(parent or main_window, title="텍스트 추가", size=(420, 450))
        self._main_window = main_window
        self._text_color = wx.Colour(255, 255, 255)
        self._bg_color = wx.Colour(0, 0, 0, 128)

        self._setup_ui()

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 텍스트 입력
        text_box = wx.StaticBox(self, label="텍스트")
        text_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        text_sizer = wx.StaticBoxSizer(text_box, wx.VERTICAL)
        text_sizer.AddSpacer(10)

        self._text_ctrl = wx.TextCtrl(self, style=wx.TE_MULTILINE, size=(-1, 100))
        self._text_ctrl.SetBackgroundColour(Colors.BG_TERTIARY)
        self._text_ctrl.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._text_ctrl.SetValue("텍스트를 입력하세요")
        text_sizer.Add(self._text_ctrl, 0, wx.EXPAND | wx.ALL, 10)

        main_sizer.Add(text_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 폰트 설정
        font_box = wx.StaticBox(self, label="폰트")
        font_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        font_sizer = wx.StaticBoxSizer(font_box, wx.VERTICAL)
        font_sizer.AddSpacer(10)

        # 폰트 크기
        size_sizer = wx.BoxSizer(wx.HORIZONTAL)
        size_label = wx.StaticText(self, label="크기:")
        size_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        size_sizer.Add(size_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._size_spin = wx.SpinCtrl(self, min=8, max=200, initial=32)
        self._size_spin.SetBackgroundColour(Colors.BG_TERTIARY)
        self._size_spin.SetForegroundColour(Colors.TEXT_PRIMARY)
        size_sizer.Add(self._size_spin, 0)

        font_sizer.Add(size_sizer, 0, wx.ALL, 10)

        # 폰트 스타일
        style_sizer = wx.BoxSizer(wx.HORIZONTAL)
        self._bold_check = wx.CheckBox(self, label="굵게")
        self._bold_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        style_sizer.Add(self._bold_check, 0, wx.ALL, 5)

        self._italic_check = wx.CheckBox(self, label="기울임")
        self._italic_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        style_sizer.Add(self._italic_check, 0, wx.ALL, 5)

        font_sizer.Add(style_sizer, 0, wx.ALL, 10)

        main_sizer.Add(font_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        main_sizer.AddSpacer(10)

        # 색상 설정
        color_box = wx.StaticBox(self, label="색상")
        color_box.SetForegroundColour(Colors.TEXT_PRIMARY)
        color_sizer = wx.StaticBoxSizer(color_box, wx.VERTICAL)
        color_sizer.AddSpacer(10)

        # 텍스트 색상
        text_color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        text_color_label = wx.StaticText(self, label="텍스트:")
        text_color_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        text_color_sizer.Add(text_color_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._text_color_btn = wx.ColourPickerCtrl(self, colour=self._text_color)
        text_color_sizer.Add(self._text_color_btn, 0)

        color_sizer.Add(text_color_sizer, 0, wx.ALL, 10)

        # 배경 색상
        bg_color_sizer = wx.BoxSizer(wx.HORIZONTAL)
        bg_color_label = wx.StaticText(self, label="배경:")
        bg_color_label.SetForegroundColour(Colors.TEXT_SECONDARY)
        bg_color_sizer.Add(bg_color_label, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)

        self._bg_color_btn = wx.ColourPickerCtrl(self, colour=wx.Colour(0, 0, 0))
        bg_color_sizer.Add(self._bg_color_btn, 0)

        self._bg_transparent_check = wx.CheckBox(self, label="투명")
        self._bg_transparent_check.SetForegroundColour(Colors.TEXT_SECONDARY)
        self._bg_transparent_check.SetValue(True)
        bg_color_sizer.Add(self._bg_transparent_check, 0, wx.LEFT | wx.ALIGN_CENTER_VERTICAL, 10)

        color_sizer.Add(bg_color_sizer, 0, wx.ALL, 10)

        main_sizer.Add(color_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddStretchSpacer()

        # 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        apply_btn = wx.Button(self, wx.ID_OK, label="추가")
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

    def get_text(self) -> str:
        """텍스트 반환"""
        return self._text_ctrl.GetValue()

    def get_font_size(self) -> int:
        """폰트 크기 반환"""
        return self._size_spin.GetValue()

    def get_text_color(self) -> wx.Colour:
        """텍스트 색상 반환"""
        return self._text_color_btn.GetColour()

    def get_bg_color(self) -> Tuple[wx.Colour, bool]:
        """배경 색상 및 투명 여부 반환"""
        transparent = self._bg_transparent_check.GetValue()
        color = self._bg_color_btn.GetColour()
        return (color, transparent)

    def is_bold(self) -> bool:
        """굵게 여부"""
        return self._bold_check.GetValue()

    def is_italic(self) -> bool:
        """기울임 여부"""
        return self._italic_check.GetValue()
