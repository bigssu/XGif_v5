"""
TargetFrameHintDialog - 대상 프레임 선택 안내 팝업 (wxPython 버전)

대상 프레임 옵션이 있는 메뉴를 열 때 한 번 보여주고,
"다음 부터 안보기" 체크 시 이후에는 표시하지 않음.
"""
import wx


class TargetFrameHintDialog(wx.Dialog):
    """대상 프레임 선택 안내 다이얼로그 (wxPython)

    메시지와 "다음 부터 안보기" 체크박스를 표시하고,
    확인 시 체크 여부를 설정에 저장합니다.
    """

    SETTINGS_KEY_HIDDEN = "target_frame_hint_hidden_v2"

    def __init__(self, parent=None, settings=None, translations=None):
        super().__init__(parent, title="적용 대상 프레임", size=(400, 180))
        self._settings = settings
        self._translations = translations
        self._dont_show_checkbox = None

        self._setup_ui()

    def _tr(self, key: str) -> str:
        """번역 헬퍼"""
        if self._translations and hasattr(self._translations, 'tr'):
            return self._translations.tr(key)

        defaults = {
            "target_frame_hint_message": "왼쪽 프레임 창에서 효과가 적용되길 원하는 프레임을 여러 개 선택해 주세요.",
            "dont_show_again": "다음 부터 안보기",
        }
        return defaults.get(key, key)

    def _setup_ui(self):
        """UI 초기화"""
        self.SetBackgroundColour(wx.Colour(45, 45, 45))

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        main_sizer.AddSpacer(20)

        # 안내 메시지
        msg_label = wx.StaticText(self, label=self._tr("target_frame_hint_message"))
        msg_label.SetForegroundColour(wx.Colour(255, 255, 255))
        msg_label.Wrap(360)
        font = msg_label.GetFont()
        font.SetPointSize(11)
        msg_label.SetFont(font)
        main_sizer.Add(msg_label, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)

        main_sizer.AddSpacer(20)

        # "다음 부터 안보기" 체크박스
        self._dont_show_checkbox = wx.CheckBox(self, label=self._tr("dont_show_again"))
        self._dont_show_checkbox.SetForegroundColour(wx.Colour(200, 200, 200))
        main_sizer.Add(self._dont_show_checkbox, 0, wx.LEFT, 20)

        main_sizer.AddSpacer(20)

        # 확인 버튼
        button_sizer = wx.BoxSizer(wx.HORIZONTAL)
        button_sizer.AddStretchSpacer()

        ok_btn = wx.Button(self, wx.ID_OK, label="확인")
        ok_btn.SetBackgroundColour(wx.Colour(0, 120, 212))
        ok_btn.SetForegroundColour(wx.Colour(255, 255, 255))
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
            elif hasattr(self._settings, 'setValue'):
                self._settings.setValue(self.SETTINGS_KEY_HIDDEN, True)

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
        # PyQt6 QSettings 형식 (호환성)
        elif hasattr(settings, 'value'):
            return not settings.value(cls.SETTINGS_KEY_HIDDEN, False, type=bool)

        return True
