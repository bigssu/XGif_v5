"""
외부 의존성 감지 엔진
FFmpeg, CuPy, dxcam 설치 상태를 확인
"""

import logging
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


def check_cupy(min_version="12.0") -> DependencyStatus:
    """CuPy 설치 상태 확인"""
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
        )
    except Exception as e:
        return DependencyStatus(
            name="CuPy",
            state=DependencyState.ERROR,
            error_message=str(e),
        )


def check_dxcam() -> DependencyStatus:
    """dxcam 설치 상태 확인"""
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
    return [check_ffmpeg(), check_cupy(), check_dxcam()]


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
