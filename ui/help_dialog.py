"""
HelpDialog - 메인 앱 도움말 다이얼로그 (wxPython)

앱 소개, 핵심 기능, 단축키를 탭으로 구분하여 표시.
non-modal (Show) 로 사용하여 녹화 등 다른 기능을 방해하지 않음.
"""
import webbrowser
import wx
from ui.theme import Colors, Fonts, ThemedDialog
from ui.i18n import tr
from core.version import APP_VERSION

GITHUB_URL = "https://github.com/bigssu/XGif_v5"
BUG_REPORT_EMAIL = "sungwook@krafton.com"


class HelpDialog(ThemedDialog):

    def __init__(self, parent=None):
        super().__init__(parent, title=tr('help_tooltip'),
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._setup_ui()
        self.SetMinSize((520, 460))
        self.SetSize((520, 520))
        self.CenterOnParent()

    def _setup_ui(self):
        main_sizer = wx.BoxSizer(wx.VERTICAL)

        # 노트북 (탭)
        notebook = wx.Notebook(self)
        notebook.SetBackgroundColour(Colors.BG_PRIMARY)
        notebook.SetForegroundColour(Colors.TEXT_PRIMARY)

        notebook.AddPage(self._create_tab(notebook, self._intro_text()), "앱 소개")
        notebook.AddPage(self._create_tab(notebook, self._features_text()), "핵심 기능")
        notebook.AddPage(self._create_tab(notebook, self._shortcuts_text()), "단축키")

        main_sizer.Add(notebook, 1, wx.EXPAND | wx.ALL, 10)

        # 하단 버튼 영역
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        # GitHub 버튼
        github_btn = wx.Button(self, label="GitHub")
        github_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        github_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        github_btn.SetMinSize((80, 32))
        github_btn.SetToolTip(GITHUB_URL)
        github_btn.Bind(wx.EVT_BUTTON, self._on_github)
        btn_sizer.Add(github_btn, 0, wx.ALL, 5)

        # 버그 신고 버튼
        bug_btn = wx.Button(self, label="버그 신고")
        bug_btn.SetBackgroundColour(Colors.BG_TERTIARY)
        bug_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        bug_btn.SetMinSize((80, 32))
        bug_btn.SetToolTip(BUG_REPORT_EMAIL)
        bug_btn.Bind(wx.EVT_BUTTON, self._on_bug_report)
        btn_sizer.Add(bug_btn, 0, wx.ALL, 5)

        btn_sizer.AddStretchSpacer()

        # 닫기 버튼
        close_btn = wx.Button(self, wx.ID_CLOSE, label="닫기")
        close_btn.SetBackgroundColour(Colors.ACCENT)
        close_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        close_btn.SetMinSize((80, 32))
        close_btn.Bind(wx.EVT_BUTTON, lambda e: self.Close())
        btn_sizer.Add(close_btn, 0, wx.ALL, 5)

        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(main_sizer)

    def _on_github(self, event):
        webbrowser.open(GITHUB_URL)

    def _on_bug_report(self, event):
        subject = f"[XGif v{APP_VERSION}] Bug Report"
        webbrowser.open(f"mailto:{BUG_REPORT_EMAIL}?subject={subject}")

    def _create_tab(self, parent, text):
        panel = wx.Panel(parent)
        panel.SetBackgroundColour(Colors.BG_PRIMARY)
        sizer = wx.BoxSizer(wx.VERTICAL)

        tc = wx.TextCtrl(panel,
                         style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2 | wx.BORDER_NONE)
        tc.SetBackgroundColour(Colors.BG_SECONDARY)
        tc.SetDefaultStyle(wx.TextAttr(
            Colors.TEXT_PRIMARY, Colors.BG_SECONDARY,
            Fonts.get_font(Fonts.SIZE_SM)))
        tc.SetValue(text)
        sizer.Add(tc, 1, wx.EXPAND | wx.ALL, 5)

        panel.SetSizer(sizer)
        return panel

    @staticmethod
    def _intro_text():
        return (
            "XGif - Windows용 GIF/MP4 화면 녹화 프로그램\n"
            "\n"
            "화면의 특정 영역을 녹화하여 GIF 또는 MP4로 저장하는\n"
            "Windows 전용 캡처 도구입니다.\n"
            "\n"
            "주요 특징:\n"
            "\n"
            "  • 드래그로 원하는 영역만 선택하여 녹화\n"
            "  • GIF / MP4 두 가지 형식 지원\n"
            "  • 내장 에디터로 녹화 직후 바로 편집\n"
            "  • CuPy 기반 GPU 가속 GIF 인코딩\n"
            "  • 다크 테마 UI\n"
            "\n"
            f"GitHub: {GITHUB_URL}\n"
            f"버그 신고: {BUG_REPORT_EMAIL}\n"
            "\n"
            f"v{APP_VERSION}  by 서승욱"
        )

    @staticmethod
    def _features_text():
        return (
            "[ 레코더 — 5대 특이 기능 ]\n"
            "\n"
            "  1. GPU 가속 인코딩\n"
            "     CuPy + NVENC으로 GIF/MP4 인코딩 속도를 대폭 향상.\n"
            "     GPU가 없으면 자동으로 CPU 폴백.\n"
            "\n"
            "  2. HDR 자동 톤매핑\n"
            "     HDR 모니터를 감지하면 캡처 백엔드를 GDI로 전환하여\n"
            "     색상 정확도를 유지합니다.\n"
            "\n"
            "  3. 클릭 하이라이트 & 키보드 오버레이\n"
            "     마우스 클릭 위치에 시각적 효과를 표시하고,\n"
            "     키보드 입력을 화면에 텍스트로 오버레이합니다.\n"
            "\n"
            "  4. 일시정지 중 영역 이동\n"
            "     녹화 일시정지 상태에서 캡처 영역을 드래그하여\n"
            "     위치를 옮길 수 있습니다 (크기 변경은 불가).\n"
            "\n"
            "  5. 녹화 → 편집 원스텝 전환\n"
            "     녹화 완료 후 '편집' 버튼 하나로 내장 에디터에\n"
            "     프레임을 전달하여 바로 편집을 시작합니다."
        )

    @staticmethod
    def _shortcuts_text():
        return (
            "[ 레코더 단축키 ]\n"
            "\n"
            "  F9          녹화 시작 / 일시정지\n"
            "  F10         녹화 중지\n"
            "\n"
            "[ 에디터 단축키 ]\n"
            "\n"
            "  Ctrl+O      파일 열기\n"
            "  Ctrl+S      파일 저장\n"
            "  Ctrl+Z      실행 취소\n"
            "  Ctrl+Y      다시 실행\n"
            "  Ctrl+A      전체 프레임 선택\n"
            "  Space       재생 / 일시정지\n"
            "  Delete      선택한 프레임 삭제\n"
            "  T           텍스트 도구\n"
            "  P           펜슬 도구\n"
            "  C           자르기 도구\n"
            "  R           크기 조절 도구\n"
            "  E           효과 도구"
        )
