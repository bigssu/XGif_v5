"""
deps_specs.py – Dependency definitions (single source of truth).

Each dependency is a dict with:
    key        : unique identifier
    label      : Korean display name
    required   : bool (REQUIRED vs OPTIONAL)
    check_func : str name in deps_checker module
    install_func: str name in deps_installer module (None = manual)
"""

DEPS = [
    {
        "key": "nvidia_driver",
        "label": "NVIDIA GPU 드라이버",
        "required": False,
        "check_func": "check_nvidia_driver",
        "install_func": None,  # user must install manually
    },
    {
        "key": "python311",
        "label": "Python 3.11 (앱 내장)",
        "required": True,
        "check_func": "check_python311",
        "install_func": "install_python311",
    },
    {
        "key": "pip",
        "label": "pip (패키지 관리자)",
        "required": True,
        "check_func": "check_pip",
        "install_func": "install_pip",
    },
    {
        "key": "venv",
        "label": "가상 환경 (venv)",
        "required": True,
        "check_func": "check_venv",
        "install_func": "install_venv",
    },
    {
        "key": "cupy",
        "label": "CuPy (CUDA GPU 연산)",
        "required": False,
        "check_func": "check_cupy",
        "install_func": "install_cupy",
    },
    {
        "key": "ffmpeg",
        "label": "FFmpeg (영상 처리)",
        "required": True,
        "check_func": "check_ffmpeg",
        "install_func": "install_ffmpeg",
    },
]

# Status constants
STATUS_PASS = "설치됨"
STATUS_MISSING = "미설치"
STATUS_INSTALLING = "설치 중…"
STATUS_FAIL = "실패"
STATUS_CHECKING = "검사 중…"
STATUS_SKIP = "건너뜀"

# ── Download URLs ──────────────────────────────────────────────────
PYTHON_EMBED_URL = (
    "https://www.python.org/ftp/python/3.11.9/"
    "python-3.11.9-embed-amd64.zip"
)
GET_PIP_URL = "https://bootstrap.pypa.io/get-pip.py"

# FFmpeg: primary (BtbN GitHub) + fallback (gyan.dev) — core/ffmpeg_installer.py와 동일 전략
FFMPEG_ZIP_URL = (
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/"
    "ffmpeg-master-latest-win64-gpl.zip"
)
FFMPEG_ZIP_URL_FALLBACK = (
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"
)
