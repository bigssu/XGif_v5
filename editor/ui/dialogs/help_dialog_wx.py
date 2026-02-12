"""
HelpDialog - 앱 도움말 다이얼로그 (wxPython)

앱 소개, 핵심 기능, 단축키를 탭으로 구분하여 표시.
"""
import wx
from ..style_constants_wx import Colors, Fonts, ThemedDialog


class HelpDialog(ThemedDialog):

    def __init__(self, parent=None):
        super().__init__(parent, title="XGif 도움말",
                         style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
        self._setup_ui()
        self.SetMinSize((500, 400))
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

        # 확인 버튼
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)
        btn_sizer.AddStretchSpacer()
        ok_btn = wx.Button(self, wx.ID_OK, label="확인")
        ok_btn.SetBackgroundColour(Colors.ACCENT)
        ok_btn.SetForegroundColour(Colors.TEXT_PRIMARY)
        ok_btn.SetMinSize((80, 32))
        btn_sizer.Add(ok_btn, 0, wx.ALL, 5)
        main_sizer.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 10)

        self.SetSizer(main_sizer)

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
            "XGif는 화면의 특정 영역을 녹화하여 GIF 또는 MP4로\n"
            "저장할 수 있는 Windows 전용 화면 캡처 도구입니다.\n"
            "\n"
            "주요 특징:\n"
            "\n"
            "  - 간편한 영역 선택으로 원하는 부분만 녹화\n"
            "  - GIF와 MP4 두 가지 형식 지원\n"
            "  - 내장 에디터로 녹화 후 바로 편집 가능\n"
            "  - GPU 가속을 통한 빠른 인코딩\n"
            "  - 다크 테마 UI로 눈의 피로 감소"
        )

    @staticmethod
    def _features_text():
        return (
            "[ 레코더 ]\n"
            "\n"
            "  - 영역 녹화: 드래그로 원하는 영역을 선택하여 녹화\n"
            "  - GIF / MP4: 두 가지 출력 형식 선택 가능\n"
            "  - FPS / 해상도: 프레임 레이트와 해상도 조절\n"
            "  - 커서 녹화: 마우스 커서 포함 여부 선택\n"
            "  - 키보드 표시: 녹화 중 키 입력 오버레이\n"
            "  - 오디오 녹음: 시스템 사운드 동시 녹음 (MP4)\n"
            "  - HDR 지원: HDR 디스플레이 자동 감지 및 톤매핑\n"
            "  - GPU 인코딩: CuPy 기반 GPU 가속 GIF 인코딩\n"
            "\n"
            "[ 에디터 ]\n"
            "\n"
            "  - 프레임 편집: 개별 프레임 삭제, 복제, 순서 변경\n"
            "  - 텍스트 삽입: 프레임에 텍스트 오버레이 추가\n"
            "  - 말풍선: 다양한 스타일의 말풍선 삽입\n"
            "  - 스티커: 이미지 스티커 붙이기\n"
            "  - 펜슬: 자유 그리기 도구\n"
            "  - 자르기 / 크기 조절: 캔버스 자르기 및 리사이즈\n"
            "  - 효과: 밝기, 대비, 색조, 흐림 등 이미지 효과\n"
            "  - 속도 조절: 전체 또는 구간별 재생 속도 변경\n"
            "  - GIF 분할: 하나의 GIF를 여러 파일로 분할\n"
            "  - GIF 병합: 여러 GIF를 하나로 합치기\n"
            "  - GIF / MP4 변환: 형식 간 변환\n"
            "  - Undo / Redo: 실행 취소 및 다시 실행"
        )

    @staticmethod
    def _shortcuts_text():
        return (
            "[ 레코더 ]\n"
            "\n"
            "  F9          녹화 시작 / 일시정지\n"
            "  F10         녹화 중지\n"
            "\n"
            "[ 에디터 ]\n"
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
