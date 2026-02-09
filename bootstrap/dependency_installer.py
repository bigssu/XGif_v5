"""
dependency_installer.py — 의존성 설치 / 안내 구현

새 설치 함수를 추가하려면:
  1) _install_{id}(dep, log_cb) 함수 작성
  2) 파일 하단의 _INSTALLERS 딕셔너리에 등록
"""
from __future__ import annotations

import sys
import os
import subprocess
import webbrowser
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

def install(dep: Dependency, log_cb: LogCb = None) -> None:
    """dep 를 설치(또는 안내)하고 status 를 갱신합니다."""
    _log(log_cb, f"[설치] {dep.display_name}")

    fn = _INSTALLERS.get(dep.id)
    if fn:
        fn(dep, log_cb)
        return

    # 등록된 설치 함수가 없으면 URL 안내
    if dep.help_url:
        _log(log_cb, f"  자동 설치 불가. 다운로드 페이지를 엽니다.")
        webbrowser.open(dep.help_url)
        dep.detail = "다운로드 페이지를 열었습니다. 설치 후 '다시 검사'를 클릭하세요."
    else:
        dep.detail = "자동 설치를 지원하지 않습니다"

    # URL 안내만 한 경우 상태는 바꾸지 않음 (MISSING 유지)


# ──────────────────────────────────────────────────────────
# CuPy — pip install cupy-cuda12x (정확히 이 명령어)
# ──────────────────────────────────────────────────────────

def _install_cupy(dep: Dependency, log_cb: LogCb) -> None:
    """CuPy 설치: pip install cupy-cuda12x

    stdout/stderr 를 실시간으로 로그 패널에 스트리밍합니다.
    설치 후 상태를 INSTALL_OK 또는 INSTALL_FAIL 로 설정합니다.
    자동 재검사는 하지 않습니다 — UI 에서 별도로 처리합니다.
    """
    if _FROZEN:
        _log(log_cb, "  패키징 환경에서는 pip 설치가 불가능합니다.")
        dep.status = DepStatus.INSTALL_FAIL
        dep.detail = "패키징 환경에서는 pip 설치 불가"
        return

    cmd = [sys.executable, "-m", "pip", "install", "cupy-cuda12x"]
    _log(log_cb, f"  실행: {' '.join(cmd)}")
    dep.status = DepStatus.INSTALLING

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            creationflags=_NO_WINDOW,
        )
        for line in proc.stdout:
            _log(log_cb, f"  pip: {line.rstrip()}")

        proc.wait(timeout=600)

        if proc.returncode == 0:
            _log(log_cb, "  CuPy 설치 완료")
            dep.status = DepStatus.INSTALL_OK
            dep.detail = "설치 완료"
        else:
            dep.status = DepStatus.INSTALL_FAIL
            dep.detail = f"pip 오류 (종료 코드 {proc.returncode})"

    except subprocess.TimeoutExpired:
        proc.kill()
        dep.status = DepStatus.INSTALL_FAIL
        dep.detail = "설치 시간 초과 (10분)"
    except FileNotFoundError:
        dep.status = DepStatus.INSTALL_FAIL
        dep.detail = f"Python 실행 파일 없음: {sys.executable}"
    except Exception as e:
        dep.status = DepStatus.INSTALL_FAIL
        dep.detail = f"설치 오류: {e}"


# ──────────────────────────────────────────────────────────
# VC++ Redistributable — 다운로드 페이지 안내
# ──────────────────────────────────────────────────────────

def _install_vcredist(dep: Dependency, log_cb: LogCb) -> None:
    url = dep.help_url or "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    _log(log_cb, f"  다운로드 페이지: {url}")
    webbrowser.open(url)
    dep.detail = "다운로드 페이지를 열었습니다. 설치 후 '다시 검사'를 클릭하세요."
    # 상태는 MISSING 유지 — 사용자가 '다시 검사'로 확인해야 함


# ──────────────────────────────────────────────────────────
# 설치 함수 레지스트리
# 새 설치 함수를 추가하려면 여기에 등록하세요.
# ──────────────────────────────────────────────────────────

_INSTALLERS: dict[str, Callable] = {
    "cupy": _install_cupy,
    "vcredist": _install_vcredist,
    # python, pip 는 앱 내에서 설치 불가 → 등록하지 않음 (URL 안내로 폴백)
}
