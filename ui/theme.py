"""
통합 UI 테마 — 레코더 + 에디터 공용
Colors, Fonts, Sizes, Spacing 및 유틸리티 함수
"""
import wx


class Colors:
    """색상 팔레트 (wxPython wx.Colour 객체)"""

    # 배경색
    BG_PRIMARY = wx.Colour(32, 32, 32)       # 메인 배경
    BG_SECONDARY = wx.Colour(28, 28, 28)     # 보조 배경
    BG_TERTIARY = wx.Colour(55, 55, 55)      # 입력 필드, 버튼 배경
    BG_HOVER = wx.Colour(70, 70, 70)         # 호버 상태
    BG_PRESSED = wx.Colour(45, 45, 45)       # 눌림 상태
    BG_SELECTED = wx.Colour(0, 120, 212)     # 선택 상태
    BG_TOOLBAR = wx.Colour(45, 45, 45)       # 인라인 툴바 배경
    BG_PANEL = wx.Colour(40, 40, 40)         # 패널 배경
    BG_CANVAS = wx.Colour(50, 50, 50)        # 캔버스 배경

    # 테두리
    BORDER = wx.Colour(60, 60, 60)
    BORDER_HOVER = wx.Colour(80, 80, 80)
    BORDER_FOCUS = wx.Colour(0, 120, 212)

    # 텍스트
    TEXT_PRIMARY = wx.Colour(255, 255, 255)
    TEXT_SECONDARY = wx.Colour(180, 180, 180)
    TEXT_MUTED = wx.Colour(136, 136, 136)

    # 강조색
    ACCENT = wx.Colour(0, 120, 212)
    ACCENT_HOVER = wx.Colour(26, 145, 235)
    ACCENT_PRESSED = wx.Colour(0, 95, 170)
    SUCCESS = wx.Colour(129, 199, 132)
    WARNING = wx.Colour(255, 167, 38)
    DANGER = wx.Colour(255, 107, 107)
    INFO = wx.Colour(79, 195, 247)
    VERSION_ACCENT = wx.Colour(0, 170, 255)
    GPU_ON = wx.Colour(76, 175, 80)          # 에디터 GPU 활성
    GPU_OFF = wx.Colour(136, 136, 136)       # 에디터 GPU 비활성

    # 메뉴바
    BG_MENUBAR = wx.Colour(38, 38, 38)
    MENU_LABEL_HOVER = wx.Colour(60, 60, 60)

    # 툴바 버튼 (FlatIconButton)
    ICON_BTN_HOVER = wx.Colour(55, 55, 55)
    ICON_BTN_PRESSED = wx.Colour(42, 42, 42)
    ICON_BTN_ACTIVE = wx.Colour(0, 120, 212, 60)

    # 헥스 색상 문자열 (DC 그리기용)
    BG_PRIMARY_HEX = "#202020"
    BG_SECONDARY_HEX = "#1c1c1c"
    BG_TERTIARY_HEX = "#373737"
    ACCENT_HEX = "#0078d4"
    TEXT_PRIMARY_HEX = "#ffffff"

    # ── 레코더 전용 ──

    # 녹화 버튼 상태별
    REC_READY = wx.Colour(233, 69, 96)
    REC_READY_HOVER = wx.Colour(245, 90, 115)
    REC_READY_PRESSED = wx.Colour(200, 55, 80)
    REC_RECORDING = wx.Colour(107, 114, 128)
    REC_RECORDING_FG = wx.Colour(209, 213, 219)
    REC_PAUSED = wx.Colour(34, 197, 94)
    REC_PAUSED_HOVER = wx.Colour(50, 210, 110)
    REC_PAUSED_PRESSED = wx.Colour(25, 170, 80)

    # GPU 버튼 (레코더용 — 에디터 GPU_ON/OFF와 다른 값)
    GPU_BTN_ON = wx.Colour(34, 197, 94)
    GPU_BTN_ON_HOVER = wx.Colour(50, 210, 110)
    GPU_BTN_OFF = wx.Colour(107, 114, 128)
    GPU_BTN_OFF_HOVER = wx.Colour(120, 127, 141)

    # Pause 버튼
    PAUSE_BG = wx.Colour(254, 202, 87)
    PAUSE_HOVER = wx.Colour(255, 215, 110)
    PAUSE_PRESSED = wx.Colour(230, 180, 70)

    # 오버레이
    OVERLAY_BORDER = wx.Colour(255, 107, 107)
    OVERLAY_BORDER_REC = wx.Colour(233, 69, 96, 77)
    OVERLAY_INNER_BORDER = wx.Colour(233, 69, 96, 180)
    OVERLAY_BADGE_BG = wx.Colour(233, 69, 96, 230)
    OVERLAY_HANDLE_BG = wx.Colour(245, 245, 245)
    OVERLAY_HANDLE_BORDER = wx.Colour(200, 200, 200)
    OVERLAY_HANDLE_ACCENT = wx.Colour(233, 69, 96)
    OVERLAY_HANDLE_SHADOW = wx.Colour(0, 0, 0, 40)

    # 상태 시맨틱 (의존성 다이얼로그, 인코딩 상태)
    STATUS_SUCCESS = wx.Colour(34, 197, 94)
    STATUS_ERROR = wx.Colour(239, 68, 68)
    STATUS_WARNING = wx.Colour(245, 158, 11)
    STATUS_SUCCESS_ALT = wx.Colour(16, 185, 129)

    # 인코딩 상태
    ENCODING_PROGRESS = wx.Colour(52, 152, 219)
    ENCODING_COMPLETE = wx.Colour(39, 174, 96)
    ENCODING_ERROR = wx.Colour(231, 76, 60)

    # FlatButton 기본 비활성
    BTN_DISABLED_FG = wx.Colour(100, 100, 100)
    BTN_DISABLED_BG = wx.Colour(50, 50, 50)

    # 토글 스위치
    TOGGLE_OFF_TRACK = wx.Colour(80, 80, 80)
    TOGGLE_OFF_HANDLE = wx.Colour(160, 160, 160)
    TOGGLE_ON_HANDLE = wx.Colour(255, 255, 255)


class Sizes:
    """크기 상수"""

    # 아이콘
    ICON_SM = 24
    ICON_MD = 24
    ICON_LG = 32

    # 버튼
    BUTTON_SM = 32
    BUTTON_MD = 40
    BUTTON_LG = 48

    # 색상 버튼
    COLOR_BUTTON = 32

    # 콤보박스 높이
    COMBOBOX_HEIGHT = 14

    # 입력 필드 너비
    SPINBOX_SM = 50
    SPINBOX_MD = 55
    SPINBOX_LG = 80
    COMBOBOX_SM = 55
    COMBOBOX_MD = 65
    COMBOBOX_LG = 80
    TEXT_INPUT = 80

    # 툴바
    TOOLBAR_HEIGHT = 50
    INLINE_TOOLBAR_MIN_HEIGHT = 44

    # 메뉴바
    MENUBAR_HEIGHT = 48

    # 라운디드 코너
    CORNER_RADIUS = 8

    # 슬라이더
    SLIDER_HEIGHT = 6
    SLIDER_HANDLE = 16


class Spacing:
    """간격 상수"""

    XS = 2
    SM = 4
    MD = 8
    LG = 15
    XL = 20

    # FlowLayout 간격
    FLOW_H = 12
    FLOW_V = 6

    # 아이콘과 입력 필드 사이 간격
    ICON_TO_CONTROL = 0


class Fonts:
    """폰트 관련 상수"""

    FACE = 'Segoe UI Variable'
    FACE_FALLBACK = 'Segoe UI'

    # 에디터 크기
    SIZE_SM = 11
    SIZE_MD = 12
    SIZE_LG = 14

    # 레코더 크기
    SIZE_DEFAULT = 10
    SIZE_SMALL = 9
    SIZE_LABEL = 11

    @staticmethod
    def get_font(size=None, bold=False):
        """wxPython 폰트 생성 — Segoe UI Variable 우선, 폴백 Segoe UI"""
        if size is None:
            size = Fonts.SIZE_MD
        weight = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
        font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight,
                       faceName=Fonts.FACE)
        if not font.IsOk() or font.GetFaceName() != Fonts.FACE:
            font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight,
                           faceName=Fonts.FACE_FALLBACK)
        return font


def apply_button_style(button: wx.Button, primary=False):
    """버튼에 다크 테마 스타일 적용"""
    if primary:
        button.SetBackgroundColour(Colors.ACCENT)
        button.SetForegroundColour(Colors.TEXT_PRIMARY)
    else:
        button.SetBackgroundColour(Colors.BG_TERTIARY)
        button.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_panel_style(panel: wx.Panel, bg_color=None):
    """패널에 다크 테마 배경 적용"""
    if bg_color is None:
        bg_color = Colors.BG_PRIMARY
    panel.SetBackgroundColour(bg_color)
    panel.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_text_ctrl_style(text_ctrl: wx.TextCtrl):
    """텍스트 컨트롤에 다크 테마 스타일 적용"""
    text_ctrl.SetBackgroundColour(Colors.BG_TERTIARY)
    text_ctrl.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_spin_ctrl_style(spin_ctrl):
    """스핀 컨트롤에 다크 테마 스타일 적용"""
    spin_ctrl.SetBackgroundColour(Colors.BG_TERTIARY)
    spin_ctrl.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_combobox_style(combobox: wx.ComboBox):
    """콤보박스에 다크 테마 스타일 적용"""
    combobox.SetBackgroundColour(Colors.BG_TERTIARY)
    combobox.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_static_box_style(static_box: wx.StaticBox):
    """StaticBox에 다크 테마 스타일 적용"""
    static_box.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_notebook_style(notebook: wx.Notebook):
    """Notebook에 다크 테마 스타일 적용"""
    notebook.SetBackgroundColour(Colors.BG_PRIMARY)
    notebook.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_dialog_style(dialog: wx.Dialog, bg_color=None):
    """Dialog에 다크 테마 배경+폰트 적용"""
    if bg_color is None:
        bg_color = Colors.BG_PANEL
    dialog.SetBackgroundColour(bg_color)
    dialog.SetForegroundColour(Colors.TEXT_PRIMARY)
    dialog.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))


# ── 자동 테마 적용 엔진 ──

def _is_unstyled_fg(widget: wx.Window) -> bool:
    """fg가 OS 기본 텍스트색(검정 계열)이면 True → 테마 적용 대상"""
    fg = widget.GetForegroundColour()
    return (fg.Red() + fg.Green() + fg.Blue()) < 60


def _is_system_bg(widget: wx.Window) -> bool:
    """bg가 OS 기본 밝은색이면 True → 테마 적용 대상"""
    bg = widget.GetBackgroundColour()
    return (bg.Red() + bg.Green() + bg.Blue()) > 500


def _apply_child_theme(widget: wx.Window):
    """개별 자식 위젯에 다크 테마 적용 (이미 설정된 색상은 보존)

    판정 기준:
      - fg가 검정 계열(OS 기본) → TEXT_PRIMARY/SECONDARY로 교체
      - bg가 밝은색(OS 기본) → 다크 테마 bg로 교체
      - 이미 다크 테마 색상이면 건드리지 않음
    """
    if getattr(widget, '_skip_auto_theme', False):
        return

    unstyled = _is_unstyled_fg(widget)
    sys_bg = _is_system_bg(widget)

    # 입력 위젯: bg + fg
    if isinstance(widget, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble)) or isinstance(widget, (wx.ComboBox, wx.Choice)):
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_TERTIARY)
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
    # 텍스트/라벨: fg만
    elif isinstance(widget, wx.StaticText) or isinstance(widget, wx.StaticBox):
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
    elif isinstance(widget, (wx.CheckBox, wx.RadioButton)):
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_SECONDARY)
    # 버튼: bg + fg (ACCENT 등 의도적 색상은 이미 dark → 보존됨)
    elif isinstance(widget, (wx.Button, wx.ToggleButton)):
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_TERTIARY)
    # 컨테이너
    elif isinstance(widget, wx.Notebook):
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_PRIMARY)
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
    elif isinstance(widget, wx.Panel):
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_PRIMARY)
    elif isinstance(widget, wx.ListCtrl):
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_PRIMARY)
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
    elif isinstance(widget, wx.Slider):
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_PRIMARY)
    else:
        # 기타 위젯: fg만 보정
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)

    # 재귀
    if hasattr(widget, 'GetChildren'):
        for child in widget.GetChildren():
            _apply_child_theme(child)


def apply_dark_theme(window: wx.Window):
    """윈도우 전체에 다크 테마 적용 (재귀적)

    이미 명시적으로 색상이 설정된 위젯은 건너뛰므로,
    ACCENT 버튼이나 TEXT_MUTED 라벨 등 의도적 오버라이드가 보존됩니다.
    """
    if _is_system_bg(window):
        window.SetBackgroundColour(Colors.BG_PRIMARY)
    if _is_unstyled_fg(window):
        window.SetForegroundColour(Colors.TEXT_PRIMARY)

    for child in window.GetChildren():
        _apply_child_theme(child)


# ── 테마 베이스 클래스 ──

class ThemedDialog(wx.Dialog):
    """다크 테마 자동 적용 Dialog 베이스 클래스

    사용법 (신규 다이얼로그):
        class MyDialog(ThemedDialog):
            def __init__(self, parent):
                super().__init__(parent, title="제목", size=(400, 300))
                label = wx.StaticText(self, label="텍스트")   # 색상 설정 불필요
                btn = wx.Button(self, label="확인")            # 색상 설정 불필요
                btn.SetBackgroundColour(Colors.ACCENT)         # 의도적 오버라이드만

    ShowModal()/Show() 호출 시 미설정 위젯에 다크 테마가 자동 적용됩니다.
    이미 색상이 설정된 위젯(ACCENT, TEXT_MUTED 등)은 보존됩니다.
    """

    def __init__(self, parent, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.SetBackgroundColour(Colors.BG_PRIMARY)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._theme_applied = False

    def apply_theme(self):
        """다크 테마를 모든 자식 위젯에 즉시 적용"""
        apply_dark_theme(self)
        self._theme_applied = True

    def fit_to_content(self, min_width=300, min_height=150, margin=40):
        """콘텐츠에 맞게 창 크기 자동 조절

        Sizer가 계산한 최적 크기를 기준으로, 지정 size=()보다
        콘텐츠가 클 경우 자동으로 확장합니다.
        """
        self.Layout()
        sizer = self.GetSizer()
        if not sizer:
            return
        best = sizer.ComputeFittingWindowSize(self)
        cur = self.GetSize()
        new_w = max(cur.width, best.width + margin, min_width)
        new_h = max(cur.height, best.height + margin, min_height)
        # 화면 크기 제한
        display_idx = wx.Display.GetFromWindow(self)
        display = wx.Display(display_idx if display_idx >= 0 else 0)
        screen = display.GetClientArea()
        new_w = min(new_w, screen.width - 40)
        new_h = min(new_h, screen.height - 40)
        self.SetSize(new_w, new_h)

    def ShowModal(self):
        if not self._theme_applied:
            apply_dark_theme(self)
        self.fit_to_content()
        return super().ShowModal()

    def Show(self, show=True):
        if show and not self._theme_applied:
            apply_dark_theme(self)
        if show:
            self.fit_to_content()
        return super().Show(show)


class ThemedPanel(wx.Panel):
    """다크 테마 자동 적용 Panel 베이스 클래스

    사용법:
        class MyPanel(ThemedPanel):
            def __init__(self, parent):
                super().__init__(parent, bg_color=Colors.BG_SECONDARY)
                label = wx.StaticText(self, label="텍스트")   # 색상 설정 불필요
    """

    def __init__(self, parent, *args, **kwargs):
        bg_color = kwargs.pop('bg_color', None)
        super().__init__(parent, *args, **kwargs)
        self.SetBackgroundColour(bg_color or Colors.BG_PRIMARY)
        self.SetForegroundColour(Colors.TEXT_PRIMARY)

    def apply_theme(self):
        """다크 테마를 모든 자식 위젯에 적용"""
        for child in self.GetChildren():
            _apply_child_theme(child)
