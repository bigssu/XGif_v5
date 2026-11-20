"""
paths.py - XGif Bootstrapper 경로 관리
"""
import os
import sys
from pathlib import Path

if not getattr(sys, "frozen", False):
    project_dir = str(Path(__file__).resolve().parents[1])
    if project_dir not in sys.path:
        sys.path.insert(0, project_dir)

import cupy_env

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

def get_venv_dir() -> Path:
    return cupy_env.select_cupy_env(version=(3, 11), bits=64)


def is_compatible_venv(directory: Path) -> bool:
    return cupy_env.env_matches_runtime(directory, version=(3, 11), bits=64)

# ffmpeg: XGif 앱이 {exe_dir}/ffmpeg/ffmpeg.exe 를 찾으므로 bin/ 없이 플래튼
FFMPEG_DIR  = str(get_localappdata() / "XGif" / "ffmpeg")
FFMPEG_EXE  = str(Path(FFMPEG_DIR) / "ffmpeg.exe")

TEMP_DIR    = str(get_temp_dir())
