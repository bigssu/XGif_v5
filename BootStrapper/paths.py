"""
paths.py - XGif Bootstrapper 경로 관리
"""
import os
import sys
from pathlib import Path

APP_NAME = "XGif_Bootstrapper"

def get_localappdata() -> Path:
    """LOCALAPPDATA 경로 반환"""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))

def get_app_data_dir() -> Path:
    """앱 데이터 디렉토리 (로그, 캐시 등)"""
    path = get_localappdata() / APP_NAME
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_log_dir() -> Path:
    """로그 디렉토리"""
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path

def get_log_file() -> Path:
    """메인 로그 파일 경로"""
    return get_log_dir() / "bootstrapper.log"

def get_exe_dir() -> Path:
    """실행 파일이 있는 디렉토리 (PyInstaller 호환)"""
    if getattr(sys, 'frozen', False):
        # PyInstaller로 빌드된 경우
        return Path(sys.executable).parent
    else:
        # 개발 환경
        return Path(__file__).parent

def get_target_dir() -> Path:
    """
    부트스트래퍼가 설치할 대상 폴더
    exe와 같은 폴더 또는 사용자 지정 폴더
    """
    return get_exe_dir()


def get_temp_dir() -> Path:
    """다운로드 임시 디렉토리"""
    path = get_app_data_dir() / "temp"
    path.mkdir(parents=True, exist_ok=True)
    return path


# ── Module-level path constants ─────────────────────────────────
# deps_checker / deps_installer 에서 paths.PY311_EXE 등으로 참조
_TARGET = get_target_dir()

PY311_DIR   = str(_TARGET / "python311")
PY311_EXE   = str(_TARGET / "python311" / "python.exe")

# venv: XGif 앱이 %LOCALAPPDATA%\XGif\env 에서 CuPy를 찾으므로 동일 경로 사용
_XGIF_ENV   = get_localappdata() / "XGif" / "env"
VENV_DIR    = str(_XGIF_ENV)
VENV_PYTHON = str(_XGIF_ENV / "Scripts" / "python.exe")

# ffmpeg: XGif 앱이 {exe_dir}/ffmpeg/ffmpeg.exe 를 찾으므로 bin/ 없이 플래튼
FFMPEG_DIR  = str(_TARGET / "ffmpeg")
FFMPEG_EXE  = str(_TARGET / "ffmpeg" / "ffmpeg.exe")

TEMP_DIR    = str(get_temp_dir())
