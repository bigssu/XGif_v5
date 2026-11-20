"""
HelpDialog - 메인 앱 도움말 다이얼로그 (wxPython)

앱 소개, 핵심 기능, 단축키를 탭으로 구분하여 표시.
non-modal (Show) 로 사용하여 녹화 등 다른 기능을 방해하지 않음.
"""
import webbrowser
from urllib.parse import quote
import wx
from ui.theme import Colors, Fonts, ThemedDialog
from ui.i18n import get_trans_manager, tr
from core.version import APP_DEVELOPER, APP_LAST_MODIFIED, APP_VERSION

GITHUB_URL = "https://github.com/bigssu/XGif_v5"
BUG_REPORT_EMAIL = "sungwook@krafton.com"


class HelpDialog(ThemedDialog):

    def __init__(self, parent=None):
        super().__init__(parent, title=tr('help_tooltip'),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._setup_ui()
        self._translate()
        get_trans_manager().register_callback(self._translate)
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroy)
        self.Bind(wx.EVT_CLOSE, self._on_close)
        self.SetMinSize(self.FromDIP((350, 260)))
        self.SetSize(self.FromDIP((520, 520)))
        self.CenterOnParent()

    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)
        self.notebook = wx.Notebook(self)
        self.notebook.SetBackgroundColour(Colors.BG_PRIMARY)
        self.notebook.SetForegroundColour(Colors.TEXT_PRIMARY)
        self.pages = []
        for _ in range(3):
            panel = wx.Panel(self.notebook)
            panel.SetBackgroundColour(Colors.BG_PRIMARY)
            text = wx.TextCtrl(panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2
                               | wx.TE_WORDWRAP | wx.BORDER_NONE)
            text.SetBackgroundColour(Colors.BG_SECONDARY)
            text.SetDefaultStyle(wx.TextAttr(Colors.TEXT_PRIMARY, Colors.BG_SECONDARY,
                                             Fonts.get_font(Fonts.SIZE_SM)))
            columns = wx.BoxSizer(wx.VERTICAL)
            columns.Add(text, 1, wx.EXPAND | wx.ALL, 5)
            panel.SetSizer(columns)
            self.notebook.AddPage(panel, "")
            self.pages.append(text)
        main_sizer.Add(self.notebook, 1, wx.EXPAND | wx.ALL, 10)

        footer = wx.BoxSizer(wx.HORIZONTAL)
        github = wx.Button(self, label="GitHub")
        self.report = wx.Button(self)
        self.close_button = wx.Button(self, wx.ID_CLOSE)
        for button in (github, self.report, self.close_button):
            button.SetForegroundColour(Colors.TEXT_PRIMARY)
            button.SetBackgroundColour(Colors.ACCENT if button == self.close_button else Colors.BG_TERTIARY)
            if button == self.close_button:
                footer.AddStretchSpacer()
            footer.Add(button, 0, wx.ALL, 3)
        github.SetToolTip(GITHUB_URL)
        github.Bind(wx.EVT_BUTTON, self._on_github)
        self.report.SetToolTip(BUG_REPORT_EMAIL)
        self.report.Bind(wx.EVT_BUTTON, self._on_bug_report)
        self.close_button.Bind(wx.EVT_BUTTON, lambda event: self.Close())
        main_sizer.Add(footer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)
        self.SetSizer(main_sizer)

    def _translate(self, lang=None):
        self.SetTitle(tr('help_tooltip'))
        self.report.SetLabel(tr('rec_help_report'))
        self.close_button.SetLabel(tr('dep_close_btn'))
        overview = '\n\n'.join((tr('help_app_summary'), tr('help_editor_summary'),
                                '\n'.join((tr('help_sec_product_body1', v=APP_VERSION),
                                           tr('help_sec_product_body3', v=APP_LAST_MODIFIED),
                                           tr('help_sec_product_body4', v=APP_DEVELOPER))),
                                f"GitHub  {GITHUB_URL}\n{tr('rec_help_report')}  {BUG_REPORT_EMAIL}"))
        features = '\n\n'.join(tr(key) for key in ('rec_help_capture', 'rec_help_gpu', 'rec_help_hdr',
                                                   'rec_help_overlay', 'rec_help_edit'))
        shortcuts = '\n'.join((tr('rec_help_recorder_keys'), tr('rec_help_hotkeys'), '',
                               tr('rec_help_editor_keys'), tr('help_sec_sc_file_body0'),
                               tr('help_sec_sc_file_body1'), tr('rec_help_save_as'),
                               tr('help_sec_sc_file_body2'), tr('help_sec_sc_file_body3'),
                               tr('help_sec_sc_edit_body2'), tr('help_sec_sc_edit_body3'),
                               tr('rec_help_duplicate')))
        for index, (label, content) in enumerate((('help_tab_overview', overview),
                                                  ('rec_help_features', features),
                                                  ('help_tab_shortcuts', shortcuts))):
            self.notebook.SetPageText(index, tr(label))
            self.pages[index].ChangeValue(content)
            self.pages[index].ShowPosition(0)
        self.Layout()

    def _on_close(self, event):
        get_trans_manager().unregister_callback(self._translate)
        self.Destroy()

    def _on_destroy(self, event):
        if event.GetEventObject() is self:
            get_trans_manager().unregister_callback(self._translate)
        event.Skip()

    def _on_github(self, event):
        webbrowser.open(GITHUB_URL)

    def _on_bug_report(self, event):
        subject = quote(f"[XGif v{APP_VERSION}] Bug Report")
        webbrowser.open(f"mailto:{BUG_REPORT_EMAIL}?subject={subject}")
