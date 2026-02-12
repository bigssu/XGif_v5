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
# 색상 (Windows 11 Dark Theme) — ui.theme.Colors 기반 래퍼
# ═══════════════════════════════════════════════════════════════
from ui.theme import Colors as _C, Fonts as _F


class THEME_MID:
    """Colors 기반 RGB 튜플 래퍼 (하위 호환)"""
    BG_MAIN = _C.BG_PRIMARY.Get()[:3]
    BG_STATUS = _C.BG_SECONDARY.Get()[:3]
    BG_TOOLBAR = _C.BG_TOOLBAR.Get()[:3]
    BG_PANEL = _C.BG_PANEL.Get()[:3]
    FG_TEXT = _C.TEXT_PRIMARY.Get()[:3]
    FG_TEXT_SECONDARY = _C.TEXT_SECONDARY.Get()[:3]

    ACCENT = _C.ACCENT.Get()[:3]
    ACCENT_HOVER = _C.ACCENT_HOVER.Get()[:3]
    ACCENT_PRESSED = _C.ACCENT_PRESSED.Get()[:3]

    BG_BUTTON = _C.BG_TERTIARY.Get()[:3]
    BG_BUTTON_HOVER = _C.BG_HOVER.Get()[:3]
    BG_BUTTON_PRESSED = _C.BG_PRESSED.Get()[:3]

    BORDER_SUBTLE = _C.BORDER.Get()[:3]


# 폰트 설정 (Fonts 클래스 참조)
FONT_FACE = _F.FACE
FONT_FACE_FALLBACK = _F.FACE_FALLBACK
FONT_SIZE_DEFAULT = _F.SIZE_DEFAULT
FONT_SIZE_SMALL = _F.SIZE_SMALL
FONT_SIZE_LABEL = _F.SIZE_LABEL

# ═══════════════════════════════════════════════════════════════
# 단축키
# ═══════════════════════════════════════════════════════════════
SHORTCUT_REC = "F9"
SHORTCUT_STOP = "F10"
SHORTCUT_OVERLAY_TOGGLE = "F11"

# 오버레이 키보드 이동량
OVERLAY_MOVE_SMALL = 1  # 화살표 키
OVERLAY_MOVE_LARGE = 10  # Shift + 화살표 키


def get_ui_font(size=None, bold=False):
    """UI 폰트 생성 — Fonts.get_font()으로 위임"""
    if size is None:
        size = FONT_SIZE_DEFAULT
    return _F.get_font(size, bold)
