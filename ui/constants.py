"""
Giffy UI 상수 정의
매직 넘버를 상수로 정의하여 유지보수성 향상
"""

# ═══════════════════════════════════════════════════════════════
# 애플리케이션 정보
# ═══════════════════════════════════════════════════════════════
from core.version import APP_NAME, APP_VERSION as VERSION

# ═══════════════════════════════════════════════════════════════
# 캡처 오버레이 설정
# ═══════════════════════════════════════════════════════════════
OVERLAY_BORDER_WIDTH = 3
OVERLAY_HANDLE_SIZE = 15
OVERLAY_HANDLE_MARGIN = 3
OVERLAY_MIN_CAPTURE_SIZE = 50
OVERLAY_BOTTOM_EXTRA = 18  # 하단 텍스트 공간

# 기본 캡처 크기
DEFAULT_CAPTURE_WIDTH = 320
DEFAULT_CAPTURE_HEIGHT = 240

# ═══════════════════════════════════════════════════════════════
# 녹화 설정
# ═══════════════════════════════════════════════════════════════
DEFAULT_FPS = 15
DEFAULT_FPS_MP4 = 30
MIN_FPS = 1
MAX_FPS = 60

# FPS 프리셋 목록
FPS_PRESETS = ["1", "3", "5", "8", "10", "15", "20", "25", "30"]

# 해상도 프리셋 목록 (HD 제거, 사용자 입력 가능)
RESOLUTION_PRESETS = [
    "320 × 240",
    "640 × 480",
    "800 × 600",
    "1024 × 768",
]

# 해상도 제한
MIN_RESOLUTION = 50      # 최소 해상도
MAX_RESOLUTION = 3840    # 최대 해상도 (4K)

# 품질 설정
QUALITY_OPTIONS = ["Hi", "Mid", "Lo"]
QUALITY_MAP = ['high', 'medium', 'low']

# ═══════════════════════════════════════════════════════════════
# 인코더 설정
# ═══════════════════════════════════════════════════════════════
# 인코더 옵션 (설정 다이얼로그용)
ENCODER_OPTIONS = ["Auto", "NVENC", "QSV", "AMF", "CPU"]
ENCODER_OPTIONS_MAP = {
    "Auto": "auto",
    "NVENC": "nvenc",
    "QSV": "qsv",
    "AMF": "amf",
    "CPU": "cpu",
}

# 코덱 옵션
CODEC_OPTIONS = ["H.264", "H.265"]
CODEC_OPTIONS_MAP = {
    "H.264": "h264",
    "H.265": "h265",
}

# 캡처 백엔드 옵션 (GDI = Windows 전용, 색상 정확)
CAPTURE_BACKEND_OPTIONS = ["Auto", "dxcam", "GDI (색상 정확)"]
CAPTURE_BACKEND_OPTIONS_MAP = {
    "Auto": "auto",
    "dxcam": "dxcam",
    "GDI (색상 정확)": "gdi",
}

# GPU 모드
GPU_MODE_AUTO = "auto"
GPU_MODE_ON = "on"
GPU_MODE_OFF = "off"

# ═══════════════════════════════════════════════════════════════
# 메모리 및 타임아웃 설정
# ═══════════════════════════════════════════════════════════════
MEMORY_WARNING_THRESHOLD_MB = 500  # 메모리 경고 임계값 (MB)
MEMORY_WARNING_RATIO = 0.9  # 메모리 경고 비율 (90%)
SYSTEM_MEMORY_CRITICAL_MB = 200  # 시스템 메모리 임계값 (MB)
DEFAULT_MAX_MEMORY_MB = 1024  # 기본 최대 메모리 (1GB)
LIMIT_MAX_MEMORY_MB = 4096    # 절대 최대 메모리 상한 (4GB)
DEBOUNCE_DELAY_MS = 50  # 디바운스 지연 (밀리초)
PREVIEW_UPDATE_INTERVAL_MS = 100  # 미리보기 갱신 간격 (밀리초)
ENCODING_STATUS_CLEAR_DELAY_MS = 3000  # 인코딩 상태 메시지 제거 지연 (밀리초)

# 프로세스 및 스레드 타임아웃
CAPTURE_PROCESS_TIMEOUT_SEC = 5.0  # 캡처 프로세스 종료 대기 시간
CAPTURE_THREAD_TIMEOUT_SEC = 2.0  # 캡처 스레드 종료 대기 시간
ENCODING_THREAD_TIMEOUT_SEC = 2.0  # 인코딩 스레드 종료 대기 시간

# 화면 경계 최소 가시 영역
MIN_VISIBLE_PIXELS = 50  # 화면 밖으로 나갈 수 있는 최대 픽셀

# ═══════════════════════════════════════════════════════════════
# UI 크기
# ═══════════════════════════════════════════════════════════════
MAIN_WINDOW_MIN_WIDTH = 900
MAIN_WINDOW_MIN_HEIGHT = 160
PROGRESS_BAR_WIDTH = 280
PROGRESS_BAR_HEIGHT = 16
PREVIEW_WIDTH = 160
PREVIEW_HEIGHT = 90

# ═══════════════════════════════════════════════════════════════
# 색상 (Windows 11 Dark Theme)
# ═══════════════════════════════════════════════════════════════

# Windows 11 다크 테마 (RGB 튜플, wx.Colour(*THEME_MID.BG_MAIN) 등으로 사용)
class THEME_MID:
    """Windows 11 다크 테마. 배경 #202020, 강조 #0078D4, 텍스트 #FFFFFF."""
    BG_MAIN = (32, 32, 32)          # #202020 메인 배경
    BG_STATUS = (28, 28, 28)        # #1C1C1C 상태바
    BG_TOOLBAR = (45, 45, 45)       # #2D2D2D 툴바/콤보
    BG_PANEL = (40, 40, 40)         # #282828 설정 다이얼로그 등
    FG_TEXT = (255, 255, 255)       # #FFFFFF 기본 텍스트
    FG_TEXT_SECONDARY = (180, 180, 180)  # #B4B4B4 보조 텍스트

    # Windows Blue 강조색
    ACCENT = (0, 120, 212)          # #0078D4
    ACCENT_HOVER = (26, 145, 235)   # #1A91EB 호버
    ACCENT_PRESSED = (0, 95, 170)   # #005FAA 눌림

    # 버튼 배경
    BG_BUTTON = (55, 55, 55)        # #373737 일반 버튼
    BG_BUTTON_HOVER = (70, 70, 70)  # #464646 호버
    BG_BUTTON_PRESSED = (45, 45, 45)  # #2D2D2D 눌림

    # 보더
    BORDER_SUBTLE = (60, 60, 60)    # #3C3C3C 미세 보더

# 폰트 설정
FONT_FACE = 'Segoe UI Variable'
FONT_FACE_FALLBACK = 'Segoe UI'
FONT_SIZE_DEFAULT = 10
FONT_SIZE_SMALL = 9
FONT_SIZE_LABEL = 11

class Colors:
    """UI 색상 정의 (Windows 11 Dark Theme)"""
    # 배경색
    BACKGROUND_PRIMARY = "#202020"
    BACKGROUND_SECONDARY = "#1C1C1C"
    BACKGROUND_TOOLBAR = "#2D2D2D"

    # 테두리
    BORDER_DEFAULT = "#3C3C3C"
    BORDER_ACCENT = "#0078D4"

    # 텍스트
    TEXT_PRIMARY = "#FFFFFF"
    TEXT_SECONDARY = "#B4B4B4"
    TEXT_MUTED = "#808080"
    TEXT_SUCCESS = "#22c55e"
    TEXT_ERROR = "#e74c3c"
    TEXT_INFO = "#0078D4"

    # 버튼 색상
    BUTTON_REC_START = "#e94560"
    BUTTON_REC_END = "#e94560"
    BUTTON_PAUSE_START = "#feca57"
    BUTTON_PAUSE_END = "#ff9f43"
    BUTTON_STOP_START = "#0078D4"
    BUTTON_STOP_END = "#005FAA"
    BUTTON_DISABLED = "#4a5568"

    # GPU 상태
    GPU_ON = "#22c55e"
    GPU_OFF = "#6b7280"

    # 오버레이
    OVERLAY_BORDER = "#ff6b6b"
    OVERLAY_BORDER_RECORDING = "rgba(233, 69, 96, 77)"
    OVERLAY_HANDLE_BG = "#f5f5f5"
    OVERLAY_HANDLE_ACCENT = "#e94560"

# ═══════════════════════════════════════════════════════════════
# 단축키
# ═══════════════════════════════════════════════════════════════
SHORTCUT_REC = "F9"
SHORTCUT_STOP = "F10"
SHORTCUT_OVERLAY_TOGGLE = "F11"

# 오버레이 키보드 이동량
OVERLAY_MOVE_SMALL = 1  # 화살표 키
OVERLAY_MOVE_LARGE = 10  # Shift + 화살표 키

# ═══════════════════════════════════════════════════════════════
# 툴팁 스타일 (통일)
# ═══════════════════════════════════════════════════════════════
TOOLTIP_STYLE = """
    QToolTip {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #3c3c3c;
        border-radius: 6px;
        padding: 6px 10px;
        font-size: 12px;
        font-family: 'Segoe UI Variable', 'Segoe UI', sans-serif;
    }
"""


def get_ui_font(size=None, bold=False):
    """UI 폰트 생성 헬퍼. Segoe UI Variable 우선, 폴백 Segoe UI."""
    import wx
    if size is None:
        size = FONT_SIZE_DEFAULT
    weight = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
    font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight, faceName=FONT_FACE)
    if not font.IsOk() or font.GetFaceName() != FONT_FACE:
        font = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, weight, faceName=FONT_FACE_FALLBACK)
    return font
