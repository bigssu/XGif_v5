"""
외부 의존성 감지 엔진
Python(시스템), FFmpeg, CuPy, dxcam 설치 상태를 확인
"""

import logging
import os
import sys
import threading
from enum import Enum
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class DependencyState(Enum):
    INSTALLED = "installed"
    MISSING = "missing"
    VERSION_LOW = "version_low"
    ERROR = "error"


@dataclass
class DependencyStatus:
    name: str
    state: DependencyState
    installed_version: str = ""
    required_version: str = ""
    error_message: str = ""


def check_system_python(min_version=(3, 11)) -> DependencyStatus:
    """시스템 Python 설치 상태 확인 (frozen 앱에서 CuPy 설치용)"""
    import shutil
    import subprocess

    min_ver_str = f"{min_version[0]}.{min_version[1]}"

    if not getattr(sys, 'frozen', False):
        # 소스 실행: 현재 Python 버전 확인
        ver = sys.version_info[:2]
        if ver >= min_version:
            return DependencyStatus("Python", DependencyState.INSTALLED,
                                    f"{ver[0]}.{ver[1]}")
        else:
            return DependencyStatus("Python", DependencyState.VERSION_LOW,
                                    f"{ver[0]}.{ver[1]}", min_ver_str)

    # frozen 앱: PATH에서 시스템 Python 찾기
    python_exe = shutil.which('python') or shutil.which('python3')
    if not python_exe:
        return DependencyStatus("Python", DependencyState.MISSING,
                                "", min_ver_str)
    try:
        result = subprocess.run(
            [python_exe, '-c',
             'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        ver_str = result.stdout.strip()
        parts = ver_str.split('.')
        ver = (int(parts[0]), int(parts[1]))
        if ver >= min_version:
            return DependencyStatus("Python", DependencyState.INSTALLED, ver_str)
        else:
            return DependencyStatus("Python", DependencyState.VERSION_LOW,
                                    ver_str, min_ver_str)
    except Exception:
        return DependencyStatus("Python", DependencyState.ERROR, "", "",
                                "Python 버전 확인 실패")


def find_system_python_exe():
    """시스템 Python 실행 파일 경로 반환 (frozen 앱에서 사용)"""
    import shutil
    import subprocess

    if not getattr(sys, 'frozen', False):
        return sys.executable

    python_exe = shutil.which('python') or shutil.which('python3')
    if not python_exe:
        return None
    try:
        # 실제 경로 확인
        result = subprocess.run(
            [python_exe, '-c', 'import sys; print(sys.executable)'],
            capture_output=True, text=True, timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
        )
        path = result.stdout.strip()
        if path and os.path.exists(path):
            return path
    except Exception:
        pass
    return python_exe


def check_ffmpeg() -> DependencyStatus:
    """FFmpeg 설치 상태 확인"""
    try:
        from core.ffmpeg_installer import FFmpegManager
        if FFmpegManager.is_available():
            return DependencyStatus(
                name="FFmpeg",
                state=DependencyState.INSTALLED,
            )
        return DependencyStatus(
            name="FFmpeg",
            state=DependencyState.MISSING,
        )
    except Exception as e:
        return DependencyStatus(
            name="FFmpeg",
            state=DependencyState.ERROR,
            error_message=str(e),
        )


def _invalidate_import_cache(module_name):
    """모듈 import 캐시 초기화 — 새로 설치된 패키지를 감지하기 위해 필요"""
    import importlib
    importlib.invalidate_caches()
    # sys.modules에서 실패 캐시 제거
    for key in list(sys.modules.keys()):
        if key == module_name or key.startswith(module_name + '.'):
            del sys.modules[key]


def check_cupy(min_version="12.0") -> DependencyStatus:
    """CuPy 설치 상태 확인"""
    try:
        from core.utils import ensure_system_site_packages
        ensure_system_site_packages()
    except Exception:
        pass

    # 새로 설치된 패키지 감지를 위해 import 캐시 초기화
    _invalidate_import_cache('cupy')

    try:
        import cupy
        installed = cupy.__version__
        # 버전 비교 (tuple)
        def _ver_tuple(v):
            return tuple(int(x) for x in v.split(".")[:2])
        if _ver_tuple(installed) < _ver_tuple(min_version):
            return DependencyStatus(
                name="CuPy",
                state=DependencyState.VERSION_LOW,
                installed_version=installed,
                required_version=min_version,
            )
        return DependencyStatus(
            name="CuPy",
            state=DependencyState.INSTALLED,
            installed_version=installed,
        )
    except ImportError:
        return DependencyStatus(
            name="CuPy",
            state=DependencyState.MISSING,
            error_message="CuPy가 설치되어 있지 않습니다. GPU 가속을 사용하려면 CuPy를 설치하세요.",
        )
    except Exception as e:
        return DependencyStatus(
            name="CuPy",
            state=DependencyState.ERROR,
            error_message=f"CuPy 초기화 실패: {str(e)[:200]}. CUDA 드라이버와 호환되는 버전인지 확인하세요.",
        )


def check_dxcam() -> DependencyStatus:
    """dxcam 설치 상태 확인"""
    _invalidate_import_cache('dxcam')
    try:
        import dxcam  # noqa: F401
        return DependencyStatus(
            name="dxcam",
            state=DependencyState.INSTALLED,
        )
    except ImportError:
        return DependencyStatus(
            name="dxcam",
            state=DependencyState.MISSING,
        )
    except Exception as e:
        return DependencyStatus(
            name="dxcam",
            state=DependencyState.ERROR,
            error_message=str(e),
        )


def check_all() -> list:
    """모든 의존성 상태 확인 (동기)"""
    return [check_system_python(), check_ffmpeg(), check_cupy(), check_dxcam()]


def check_all_async(callback):
    """모든 의존성 상태를 백그라운드에서 확인 후 wx.CallAfter로 콜백 호출"""
    def _worker():
        results = check_all()
        try:
            import wx
            if wx.App.Get() is not None:
                wx.CallAfter(callback, results)
            else:
                callback(results)
        except (ImportError, RuntimeError):
            callback(results)

    t = threading.Thread(target=_worker, daemon=True)
    t.start()
    return t
