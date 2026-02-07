"""
StyleConstants - wxPython용 UI 스타일 상수 정의
모든 UI 컴포넌트에서 일관된 스타일을 적용하기 위한 상수들
"""
import wx


class Colors:
    """색상 팔레트 (wxPython wx.Colour 객체) — THEME_MID 동기화"""

    # 배경색
    BG_PRIMARY = wx.Colour(32, 32, 32)       # 메인 배경 (THEME_MID.BG_MAIN)
    BG_SECONDARY = wx.Colour(28, 28, 28)     # 보조 배경 (THEME_MID.BG_STATUS)
    BG_TERTIARY = wx.Colour(55, 55, 55)      # 입력 필드, 버튼 배경 (THEME_MID.BG_BUTTON)
    BG_HOVER = wx.Colour(70, 70, 70)         # 호버 상태 (THEME_MID.BG_BUTTON_HOVER)
    BG_PRESSED = wx.Colour(45, 45, 45)       # 눌림 상태 (THEME_MID.BG_BUTTON_PRESSED)
    BG_SELECTED = wx.Colour(0, 120, 212)     # 선택 상태
    BG_TOOLBAR = wx.Colour(45, 45, 45)       # 인라인 툴바 배경 (THEME_MID.BG_TOOLBAR)
    BG_PANEL = wx.Colour(40, 40, 40)         # 패널 배경 (THEME_MID.BG_PANEL)
    BG_CANVAS = wx.Colour(50, 50, 50)        # 캔버스 배경

    # 테두리
    BORDER = wx.Colour(60, 60, 60)           # (THEME_MID.BORDER_SUBTLE)
    BORDER_HOVER = wx.Colour(80, 80, 80)
    BORDER_FOCUS = wx.Colour(0, 120, 212)

    # 텍스트
    TEXT_PRIMARY = wx.Colour(255, 255, 255)
    TEXT_SECONDARY = wx.Colour(180, 180, 180) # (THEME_MID.FG_TEXT_SECONDARY)
    TEXT_MUTED = wx.Colour(136, 136, 136)

    # 강조색
    ACCENT = wx.Colour(0, 120, 212)          # 주 강조색 (파란색)
    ACCENT_HOVER = wx.Colour(26, 145, 235)   # (THEME_MID.ACCENT_HOVER)
    SUCCESS = wx.Colour(129, 199, 132)       # 성공/적용 (녹색)
    WARNING = wx.Colour(255, 167, 38)        # 경고 (주황)
    DANGER = wx.Colour(255, 107, 107)        # 삭제/위험 (빨강)
    INFO = wx.Colour(79, 195, 247)           # 정보 (하늘색)
    VERSION_ACCENT = wx.Colour(0, 170, 255)  # 버전 라벨
    GPU_ON = wx.Colour(76, 175, 80)          # GPU 활성
    GPU_OFF = wx.Colour(136, 136, 136)       # GPU 비활성

    # 메뉴바
    BG_MENUBAR = wx.Colour(38, 38, 38)      # 메뉴바 배경
    MENU_LABEL_HOVER = wx.Colour(60, 60, 60) # 메뉴 라벨 호버

    # 툴바 버튼 (FlatIconButton)
    ICON_BTN_HOVER = wx.Colour(55, 55, 55)   # 아이콘 버튼 호버
    ICON_BTN_PRESSED = wx.Colour(42, 42, 42) # 아이콘 버튼 눌림
    ICON_BTN_ACTIVE = wx.Colour(0, 120, 212, 60)  # 활성 상태 (ACCENT 반투명)

    # 헥스 색상 문자열 (DC 그리기용)
    BG_PRIMARY_HEX = "#202020"
    BG_SECONDARY_HEX = "#1c1c1c"
    BG_TERTIARY_HEX = "#373737"
    ACCENT_HEX = "#0078d4"
    TEXT_PRIMARY_HEX = "#ffffff"


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
    SIZE_SM = 11
    SIZE_MD = 12
    SIZE_LG = 14

    @staticmethod
    def get_font(size=SIZE_MD, bold=False):
        """wxPython 폰트 생성 — Segoe UI Variable 우선, 폴백 Segoe UI"""
        weight = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
        font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight,
                       faceName=Fonts.FACE)
        if not font.IsOk() or font.GetFaceName() != Fonts.FACE:
            font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight,
                           faceName=Fonts.FACE_FALLBACK)
        return font


# wxPython에는 Qt의 스타일시트가 없으므로,
# 대신 각 위젯에서 SetBackgroundColour, SetForegroundColour 등을 직접 사용
# 필요시 유틸리티 함수를 제공

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


def apply_dark_theme(window: wx.Window):
    """윈도우 전체에 다크 테마 적용 (재귀적)"""
    window.SetBackgroundColour(Colors.BG_PRIMARY)
    window.SetForegroundColour(Colors.TEXT_PRIMARY)

    for child in window.GetChildren():
        if isinstance(child, wx.Panel):
            apply_panel_style(child)
        elif isinstance(child, wx.Button):
            apply_button_style(child)
        elif isinstance(child, wx.TextCtrl):
            apply_text_ctrl_style(child)
        elif isinstance(child, wx.ComboBox):
            apply_combobox_style(child)
        elif isinstance(child, (wx.SpinCtrl, wx.SpinCtrlDouble)):
            apply_spin_ctrl_style(child)

        # 재귀적으로 자식 위젯에도 적용
        if hasattr(child, 'GetChildren'):
            apply_dark_theme(child)
