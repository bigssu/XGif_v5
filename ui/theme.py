"""
통합 UI 테마 — 레코더 + 에디터 공용
Colors, Fonts, Sizes, Spacing 및 유틸리티 함수
"""
import wx


class Colors:
    """색상 팔레트 (wxPython wx.Colour 객체)"""

    # 배경색
    BG_PRIMARY = wx.Colour(8, 10, 14)        # 메인 배경
    BG_SECONDARY = wx.Colour(18, 23, 31)     # 보조 배경
    BG_TERTIARY = wx.Colour(42, 52, 68)      # 입력 필드, 버튼 배경
    BG_HOVER = wx.Colour(58, 70, 89)         # 호버 상태
    BG_PRESSED = wx.Colour(24, 30, 40)       # 눌림 상태
    BG_SELECTED = wx.Colour(76, 141, 245)    # 선택 상태
    BG_TOOLBAR = wx.Colour(25, 31, 41)       # 인라인 툴바 배경
    BG_PANEL = wx.Colour(22, 28, 38)         # 패널 배경
    BG_CANVAS = wx.Colour(5, 7, 10)          # 캔버스 배경
    BG_SUNKEN = wx.Colour(7, 9, 13)          # 안쪽 작업면
    BG_CARD = wx.Colour(32, 40, 54)          # 카드/바 기본 표면
    BG_CARD_ALT = wx.Colour(44, 55, 72)      # 한 단계 올라온 표면
    BG_RAISED = wx.Colour(53, 65, 84)        # 강조 표면
    BG_INPUT = wx.Colour(38, 48, 63)         # 입력 컨트롤
    BG_INPUT_DARK = wx.Colour(36, 45, 60)    # 드롭다운/숫자 필드

    # 테두리
    BORDER = wx.Colour(69, 84, 106)
    BORDER_SOFT = wx.Colour(48, 60, 78)
    BORDER_HOVER = wx.Colour(91, 109, 134)
    BORDER_FOCUS = wx.Colour(102, 169, 255)
    BORDER_STRONG = wx.Colour(76, 90, 108)
    DIVIDER = wx.Colour(54, 67, 86)
    DIVIDER_SUBTLE = wx.Colour(33, 42, 56)
    RAIL_BG = wx.Colour(20, 26, 35)
    RAIL_BG_ALT = wx.Colour(13, 17, 24)
    SURFACE_HIGHLIGHT = wx.Colour(79, 94, 116)
    SURFACE_SHADOW = wx.Colour(3, 5, 8)

    # 텍스트
    TEXT_PRIMARY = wx.Colour(244, 247, 250)
    TEXT_SECONDARY = wx.Colour(185, 195, 207)
    TEXT_MUTED = wx.Colour(125, 138, 153)

    # 강조색
    ACCENT = wx.Colour(94, 162, 255)
    ACCENT_HOVER = wx.Colour(116, 179, 255)
    ACCENT_PRESSED = wx.Colour(64, 132, 226)
    ACCENT_SOFT = wx.Colour(94, 162, 255, 42)
    SUCCESS = wx.Colour(86, 198, 139)
    WARNING = wx.Colour(232, 171, 74)
    DANGER = wx.Colour(239, 105, 115)
    INFO = wx.Colour(91, 196, 228)
    VERSION_ACCENT = wx.Colour(116, 179, 255)
    GPU_ON = wx.Colour(86, 198, 139)         # 에디터 GPU 활성
    GPU_OFF = wx.Colour(125, 138, 153)       # 에디터 GPU 비활성
    CROP_ACCENT = wx.Colour(232, 171, 74)
    MOSAIC_ACCENT = wx.Colour(184, 132, 255)
    BUBBLE_ACCENT = wx.Colour(86, 198, 139)
    OVERLAY_TEXT_ACCENT = wx.Colour(94, 162, 255)

    # 메뉴바
    BG_MENUBAR = wx.Colour(22, 25, 30)
    MENU_LABEL_HOVER = wx.Colour(38, 43, 51)

    # 툴바 버튼 (FlatIconButton)
    ICON_BTN_HOVER = wx.Colour(38, 45, 55)
    ICON_BTN_PRESSED = wx.Colour(25, 30, 37)
    ICON_BTN_ACTIVE = wx.Colour(94, 162, 255, 45)
    ICON_BTN_DISABLED = BG_PRIMARY

    # 에디터 액션 버튼
    ACTION_BUTTON_BG = BG_INPUT_DARK
    ACTION_BUTTON_PRIMARY_BG = ACCENT
    ACTION_BUTTON_TEXT = TEXT_PRIMARY

    # 에디터 특정 액션 semantic token
    LANG_TOGGLE_FG = SUCCESS
    LANG_TOGGLE_BG = BG_INPUT_DARK
    SAVE_PRIMARY = ACTION_BUTTON_PRIMARY_BG

    # 에디터 프레임 리스트
    FRAME_LIST_BG = wx.Colour(5, 7, 10)
    FRAME_LIST_HEADER_BG = wx.Colour(28, 36, 48)
    FRAME_LIST_ROW_BG = wx.Colour(9, 12, 17)
    FRAME_LIST_ROW_ALT_BG = wx.Colour(14, 18, 25)
    FRAME_LIST_SELECTED_BG = wx.Colour(50, 66, 86)
    FRAME_LIST_SELECTED_FG = wx.Colour(234, 240, 247)
    FRAME_LIST_GRID = wx.Colour(35, 45, 60)
    FRAME_LIST_RAIL = wx.Colour(17, 22, 30)

    # 헥스 색상 문자열 (DC 그리기용)
    BG_PRIMARY_HEX = "#080a0e"
    BG_SECONDARY_HEX = "#12171f"
    BG_TERTIARY_HEX = "#2a3444"
    ACCENT_HEX = "#5ea2ff"
    TEXT_PRIMARY_HEX = "#f4f7fa"

    # ── 레코더 전용 ──

    # 녹화 버튼 상태별
    REC_READY = wx.Colour(229, 74, 92)
    REC_READY_HOVER = wx.Colour(242, 95, 111)
    REC_READY_PRESSED = wx.Colour(199, 56, 73)
    REC_RECORDING = wx.Colour(82, 93, 108)
    REC_RECORDING_FG = wx.Colour(210, 218, 228)
    REC_PAUSED = wx.Colour(86, 198, 139)
    REC_PAUSED_HOVER = wx.Colour(105, 213, 157)
    REC_PAUSED_PRESSED = wx.Colour(65, 169, 116)

    # GPU 버튼 (레코더용 — 에디터 GPU_ON/OFF와 다른 값)
    GPU_BTN_ON = wx.Colour(47, 151, 103)
    GPU_BTN_ON_HOVER = wx.Colour(63, 174, 121)
    GPU_BTN_OFF = wx.Colour(59, 68, 81)
    GPU_BTN_OFF_HOVER = wx.Colour(72, 83, 98)

    # Pause 버튼
    PAUSE_BG = wx.Colour(217, 154, 55)
    PAUSE_HOVER = wx.Colour(232, 171, 74)
    PAUSE_PRESSED = wx.Colour(186, 128, 41)

    # 오버레이
    OVERLAY_BORDER = wx.Colour(239, 105, 115)
    OVERLAY_BORDER_REC = wx.Colour(229, 74, 92, 77)
    OVERLAY_INNER_BORDER = wx.Colour(229, 74, 92, 180)
    OVERLAY_BADGE_BG = wx.Colour(233, 69, 96, 230)
    OVERLAY_HANDLE_BG = wx.Colour(245, 245, 245)
    OVERLAY_HANDLE_BORDER = wx.Colour(208, 217, 226)
    OVERLAY_HANDLE_ACCENT = wx.Colour(229, 74, 92)
    OVERLAY_HANDLE_SHADOW = wx.Colour(0, 0, 0, 40)

    # 상태 시맨틱 (의존성 다이얼로그, 인코딩 상태)
    STATUS_SUCCESS = wx.Colour(86, 198, 139)
    STATUS_ERROR = wx.Colour(239, 105, 115)
    STATUS_WARNING = wx.Colour(232, 171, 74)
    STATUS_SUCCESS_ALT = wx.Colour(69, 184, 132)

    # 인코딩 상태
    ENCODING_PROGRESS = ACCENT
    ENCODING_COMPLETE = SUCCESS
    ENCODING_ERROR = DANGER

    # 비활성 버튼 색상 (CommandButton 등 공용)
    BTN_DISABLED_FG = wx.Colour(91, 103, 119)
    BTN_DISABLED_BG = wx.Colour(31, 36, 43)

    # 토글 스위치
    TOGGLE_OFF_TRACK = wx.Colour(62, 71, 84)
    TOGGLE_OFF_HANDLE = wx.Colour(153, 166, 181)
    TOGGLE_ON_HANDLE = wx.Colour(247, 250, 252)

    # 캔버스 / 프리뷰
    CHECKER_LIGHT = wx.Colour(210, 216, 224)
    CHECKER_DARK = wx.Colour(168, 177, 188)
    CANVAS_EMPTY_RING = wx.Colour(55, 65, 78)


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
        button.SetBackgroundColour(Colors.ACTION_BUTTON_PRIMARY_BG)
    else:
        button.SetBackgroundColour(Colors.ACTION_BUTTON_BG)
    button.SetForegroundColour(Colors.ACTION_BUTTON_TEXT)


def apply_panel_style(panel: wx.Panel, bg_color=None):
    """패널에 다크 테마 배경 적용"""
    if bg_color is None:
        bg_color = Colors.BG_PRIMARY
    panel.SetBackgroundColour(bg_color)
    panel.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_text_ctrl_style(text_ctrl: wx.TextCtrl):
    """텍스트 컨트롤에 다크 테마 스타일 적용"""
    text_ctrl.SetBackgroundColour(Colors.BG_INPUT_DARK)
    text_ctrl.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_spin_ctrl_style(spin_ctrl):
    """스핀 컨트롤에 다크 테마 스타일 적용"""
    spin_ctrl.SetBackgroundColour(Colors.BG_INPUT_DARK)
    spin_ctrl.SetForegroundColour(Colors.TEXT_PRIMARY)


def apply_combobox_style(combobox: wx.ComboBox):
    """콤보박스에 다크 테마 스타일 적용"""
    combobox.SetBackgroundColour(Colors.BG_INPUT_DARK)
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
    if isinstance(widget, (wx.TextCtrl, wx.SpinCtrl, wx.SpinCtrlDouble, wx.ComboBox, wx.Choice)):
        if sys_bg:
            widget.SetBackgroundColour(Colors.BG_INPUT_DARK)
        if unstyled:
            widget.SetForegroundColour(Colors.TEXT_PRIMARY)
    # 텍스트/라벨: fg만
    elif isinstance(widget, (wx.StaticText, wx.StaticBox)):
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
