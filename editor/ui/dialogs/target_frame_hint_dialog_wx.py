"""
TargetFrameHintDialog - 대상 프레임 선택 안내 팝업 (wxPython 버전)

대상 프레임 옵션이 있는 메뉴를 열 때 한 번 보여주고,
"다음 부터 안보기" 체크 시 이후에는 표시하지 않음.
"""
import wx
from ..style_constants_wx import Colors


class TargetFrameHintDialog(wx.Dialog):
    """대상 프레임 선택 안내 다이얼로그 (wxPython)

    메시지와 "다음 부터 안보기" 체크박스를 표시하고,
    확인 시 체크 여부를 설정에 저장합니다.
    """

    SETTINGS_KEY_HIDDEN = "target_frame_hint_hidden_v2"

    def __init__(self, parent=None, settings=None, translations=None):
        super().__init__(parent, title="대상 프레임 선택", size=(440, 280),
                         style=wx.DEFAULT_DIALOG_STYLE)
        self._settings = settings
        self._translations = translations
        self._dont_show_checkbox = None

        self._setup_ui()
        self.CentreOnParent()

    def _tr(self, key: str) -> str:
        """번역 헬퍼"""
        if self._translations and hasattr(self._translations, 'tr'):
            return self._translations.tr(key)

        defaults = {
            "target_frame_hint_title": "대상 프레임 선택",
            "target_frame_hint_message": (
                "프레임 선택 안내:\n\n"
                "\u2022 현재 프레임: 현재 보고 있는 프레임에만 적용\n"
                "\u2022 선택한 프레임: 프레임 목록에서 선택한 프레임들에 적용\n"
                "\u2022 모든 프레임: 전체 프레임에 적용\n\n"
                "프레임 목록에서 Shift+클릭 또는 Ctrl+클릭으로\n"
                "여러 프레임을 선택할 수 있습니다."
            ),
            "dont_show_again": "다음부터 이 안내를 표시하지 않음",
            "ok": "확인",
        }
        return defaults.get(key, key)

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(Colors.BG_PRIMARY)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 안내 메시지
        msg_label = wx.StaticText(self, label=self._tr("target_frame_hint_message"))
        msg_label.SetForegroundColour(Colors.TEXT_PRIMARY)
        msg_label.Wrap(400)
        font = msg_label.GetFont()
        font.SetPointSize(10)
        msg_label.SetFont(font)
        main_sizer.Add(msg_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddStretchSpacer()

        # "다음부터 이 안내를 표시하지 않음" 체크박스
        self._dont_show_checkbox = wx.CheckBox(self, label=self._tr("dont_show_again"))
        self._dont_show_checkbox.SetForegroundColour(Colors.TEXT_SECONDARY)
        main_sizer.Add(self._dont_show_checkbox, 0, wx.LEFT | wx.BOTTOM, 20)

        # 확인 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        ok_btn = wx.Button(self, wx.ID_OK, label=self._tr("ok"))
        ok_btn.SetBackgroundColour(Colors.ACCENT)
        ok_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        ok_btn.SetMinSize((80, 32))
        ok_btn.Bind(wx.EVT_BUTTON, self._on_accept)
        button_sizer.Add(ok_btn, 0, wx.ALL, 5)

        main_sizer.Add(button_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        self.SetSizer(main_sizer)

    def _on_accept(self, event):
        """확인 버튼 클릭"""
        if self._settings and self._dont_show_checkbox and self._dont_show_checkbox.GetValue():
            # wx.Config에 설정 저장
            if hasattr(self._settings, 'Write'):
                self._settings.Write(self.SETTINGS_KEY_HIDDEN, "True")

        self.EndModal(wx.ID_OK)

    @classmethod
    def should_show(cls, settings) -> bool:
        """설정에 따라 안내를 표시해야 하면 True"""
        if not settings:
            return True

        # wx.Config 형식
        if hasattr(settings, 'Read'):
            value = settings.Read(cls.SETTINGS_KEY_HIDDEN, "False")
            return value.lower() != "true"

        return True
