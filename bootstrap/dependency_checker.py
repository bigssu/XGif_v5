"""
dependency_checker.py — 의존성 검사 구현

새 검사를 추가하려면:
  1) _check_{id}(dep, log_cb) 함수 작성
  2) 파일 하단의 _CHECKERS 딕셔너리에 등록
"""
from __future__ import annotations

import sys
import os
import subprocess
import logging
from typing import Optional, Callable

from .dependency_specs import Dependency, DepStatus

logger = logging.getLogger(__name__)

LogCb = Optional[Callable[[str], None]]

_FROZEN = getattr(sys, "frozen", False)
_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def _log(cb: LogCb, msg: str):
    logger.info(msg)
    if cb:
        cb(msg)


# ──────────────────────────────────────────────────────────
# 공개 API
# ──────────────────────────────────────────────────────────

def check(dep: Dependency, log_cb: LogCb = None) -> None:
    """dep 의 status / detail 을 갱신합니다.

    _CHECKERS 에 등록된 함수가 있으면 호출하고,
    없으면 ERROR 로 설정합니다.
    """
    _log(log_cb, f"[검사] {dep.display_name}")

    fn = _CHECKERS.get(dep.id)
    if fn:
        fn(dep, log_cb)
    else:
        dep.status = DepStatus.ERROR
        dep.detail = "검사 방법이 정의되지 않았습니다"

    _log(log_cb, f"  \u2192 {dep.status.value}: {dep.detail}")


# ──────────────────────────────────────────────────────────
# Python 런타임
# ──────────────────────────────────────────────────────────

def _check_python(dep: Dependency, log_cb: LogCb) -> None:
    vi = sys.version_info
    ver = f"{vi.major}.{vi.minor}.{vi.micro}"
    if vi.major == 3 and vi.minor >= 11:
        dep.status = DepStatus.PASS
        dep.detail = f"Python {ver}"
    else:
        dep.status = DepStatus.MISSING
        dep.detail = f"Python {ver} (3.11 이상 필요)"


# ──────────────────────────────────────────────────────────
# pip
# ──────────────────────────────────────────────────────────

def _check_pip(dep: Dependency, log_cb: LogCb) -> None:
    if _FROZEN:
        dep.status = DepStatus.PASS
        dep.detail = "패키징 환경 (pip 불필요)"
        return
    try:
        r = subprocess.run(
            [sys.executable, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=15,
            creationflags=_NO_WINDOW,
        )
        if r.returncode == 0:
            ver = r.stdout.strip().split()[1]
            dep.status = DepStatus.PASS
            dep.detail = f"pip {ver}"
        else:
            dep.status = DepStatus.MISSING
            dep.detail = "pip 실행 실패"
    except FileNotFoundError:
        dep.status = DepStatus.MISSING
        dep.detail = "Python 실행 파일 없음"
    except subprocess.TimeoutExpired:
        dep.status = DepStatus.ERROR
        dep.detail = "pip 응답 시간 초과"
    except Exception as e:
        dep.status = DepStatus.ERROR
        dep.detail = str(e)


# ──────────────────────────────────────────────────────────
# VC++ Redistributable (x64, 2015-2022)
# ──────────────────────────────────────────────────────────

def _check_vcredist(dep: Dependency, log_cb: LogCb) -> None:
    """레지스트리 키 → DLL 존재 순서로 확인"""
    if sys.platform != "win32":
        dep.status = DepStatus.PASS
        dep.detail = "Windows 외 환경"
        return

    try:
        import winreg

        key_paths = [
            r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            r"SOFTWARE\WOW6432Node\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
        ]
        for kp in key_paths:
            try:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, kp) as key:
                    val, _ = winreg.QueryValueEx(key, "Installed")
                    if val == 1:
                        dep.status = DepStatus.PASS
                        dep.detail = _read_vcredist_ver(key)
                        return
            except FileNotFoundError:
                continue

        # DLL 직접 확인
        sys32 = os.path.join(
            os.environ.get("SystemRoot", r"C:\Windows"), "System32",
        )
        if os.path.isfile(os.path.join(sys32, "vcruntime140.dll")):
            dep.status = DepStatus.PASS
            dep.detail = "vcruntime140.dll 확인됨"
            return

        dep.status = DepStatus.MISSING
        dep.detail = "VC++ Redistributable 미설치"

    except Exception as e:
        dep.status = DepStatus.ERROR
        dep.detail = f"레지스트리 검사 오류: {e}"


def _read_vcredist_ver(key) -> str:
    import winreg
    try:
        maj, _ = winreg.QueryValueEx(key, "Major")
        mi, _ = winreg.QueryValueEx(key, "Minor")
        bld, _ = winreg.QueryValueEx(key, "Bld")
        return f"VC++ {maj}.{mi}.{bld}"
    except OSError:
        return "VC++ 설치 확인됨"


# ──────────────────────────────────────────────────────────
# CuPy — subprocess 방식 (설치 직후 재검사에서도 동작)
# ──────────────────────────────────────────────────────────

def _check_cupy(dep: Dependency, log_cb: LogCb) -> None:
    """subprocess 로 import cupy + CUDA 디바이스 수 확인.

    pip install 직후에도 정확한 결과를 얻기 위해
    별도 프로세스에서 검사합니다.
    """
    python = sys.executable
    script = (
        "import cupy; "
        "print(cupy.__version__); "
        "print(cupy.cuda.runtime.getDeviceCount())"
    )

    try:
        r = subprocess.run(
            [python, "-c", script],
            capture_output=True, text=True, timeout=30,
            creationflags=_NO_WINDOW,
        )
        if r.returncode == 0:
            lines = r.stdout.strip().split("\n")
            ver = lines[0].strip()
            devices = int(lines[1].strip()) if len(lines) > 1 else 0
            if devices > 0:
                dep.status = DepStatus.PASS
                dep.detail = f"CuPy {ver}, CUDA 디바이스 {devices}개"
            else:
                dep.status = DepStatus.ERROR
                dep.detail = f"CuPy {ver} 설치됨, CUDA 디바이스 없음"
        else:
            stderr = r.stderr.strip()
            if "No module named" in stderr or "ModuleNotFoundError" in stderr:
                dep.status = DepStatus.MISSING
                dep.detail = "CuPy 미설치"
            else:
                dep.status = DepStatus.ERROR
                dep.detail = f"검사 오류: {stderr[-120:]}"

    except subprocess.TimeoutExpired:
        dep.status = DepStatus.ERROR
        dep.detail = "CuPy 검사 시간 초과 (30초)"
    except Exception as e:
        dep.status = DepStatus.ERROR
        dep.detail = str(e)


# ──────────────────────────────────────────────────────────
# 검사 함수 레지스트리
# 새 검사를 추가하려면 여기에 "id": _check_함수 를 등록하세요.
# ──────────────────────────────────────────────────────────

_CHECKERS: dict[str, Callable] = {
    "python": _check_python,
    "pip": _check_pip,
    "vcredist": _check_vcredist,
    "cupy": _check_cupy,
}
