"""
외부 의존성 감지 엔진
Python(시스템), FFmpeg, CuPy, dxcam 설치 상태를 확인
"""

import logging
import sys
import threading
from enum import Enum
from dataclasses import dataclass

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
    min_ver_str = f"{min_version[0]}.{min_version[1]}"
    if getattr(sys, 'frozen', False):
        from cupy_env import PYTHON_VERSION, find_compatible_python
        version = ".".join(map(str, PYTHON_VERSION))
        if find_compatible_python():
            return DependencyStatus("Python", DependencyState.INSTALLED, version, version)
        return DependencyStatus("Python", DependencyState.MISSING, required_version=version)

    ver = sys.version_info[:2]
    state = DependencyState.INSTALLED if ver >= min_version else DependencyState.VERSION_LOW
    return DependencyStatus("Python", state, f"{ver[0]}.{ver[1]}", min_ver_str)


def check_ffmpeg() -> DependencyStatus:
    """FFmpeg 설치 상태 확인"""
    try:
        from core.ffmpeg_installer import FFmpegManager
        if not FFmpegManager.needs_installation():
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


def check_cupy(min_version="12.0", *, verify_compute=True) -> DependencyStatus:
    """Check CuPy in the interpreter that will actually use the GPU."""
    import importlib

    stage = "CuPy environment"
    try:
        from core.utils import ensure_system_site_packages
        ensure_system_site_packages()
        # Running capture/editor code can still hold references to native modules.
        importlib.invalidate_caches()
        stage = "import cupy"
        import cupy

        installed = cupy.__version__
        if tuple(map(int, installed.split(".")[:2])) < tuple(map(int, min_version.split(".")[:2])):
            message = f"CuPy {installed} (required: CuPy >= {min_version})"
            logger.info(message)
            return DependencyStatus("CuPy", DependencyState.VERSION_LOW, installed, min_version, message)

        stage = "cupy.cuda.runtime.getDeviceCount()"
        if cupy.cuda.runtime.getDeviceCount() < 1:
            raise RuntimeError("No CUDA devices found.")
        if verify_compute:
            stage = "CuPy CUDA computation"
            values = cupy.asarray([1], dtype=cupy.int32)
            if (values + 1).get().item() != 2:
                raise RuntimeError("Unexpected CUDA computation result.")
        return DependencyStatus("CuPy", DependencyState.INSTALLED, installed)
    except Exception as exc:
        missing = isinstance(exc, ModuleNotFoundError) and exc.name == "cupy" and stage == "import cupy"
        state = DependencyState.MISSING if missing else DependencyState.ERROR
        reason = exc.__cause__ or exc
        message = f"{stage}: {type(reason).__name__}: {reason}"
        logger.info("%s", message, exc_info=logger.isEnabledFor(logging.DEBUG))
        return DependencyStatus("CuPy", state, error_message=message)


def check_dxcam() -> DependencyStatus:
    """dxcam 설치 상태 확인"""
    import importlib
    importlib.invalidate_caches()
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
