"""
app_entry.py — 앱 진입점

========================================
시작 차단 (Hard Gate) 동작 원리
========================================

  1) wx.App 생성
  2) EnvDiagnosticDialog.ShowModal() 호출
     → 이 시점에서 메인 앱은 완전히 차단됨
     → 사용자가 '닫기' 를 명시적으로 클릭할 때까지 대기
  3) ShowModal() 반환값 확인:
     - wx.ID_OK     → 필수 충족 → 메인 앱 실행
     - wx.ID_CANCEL → 필수 미충족 → 경고 메시지 후 종료
  4) 자동 우회, 백그라운드 실행, 숨김 건너뛰기 없음

사용법:
  python -m bootstrap.app_entry
"""
from __future__ import annotations

import sys
import os
import logging

import wx

from .env_diagnostic_ui import EnvDiagnosticDialog
from .dependency_specs import APP_NAME


# ──────────────────────────────────────────────────────────
# 로깅
# ──────────────────────────────────────────────────────────

def _get_log_dir() -> str:
    if sys.platform == "win32":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
    else:
        base = os.path.expanduser("~")
    return os.path.join(base, APP_NAME, "logs")


def _setup_logging():
    log_dir = _get_log_dir()
    os.makedirs(log_dir, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        handlers=[
            logging.FileHandler(
                os.path.join(log_dir, "env_diagnostic.log"),
                encoding="utf-8",
            ),
            logging.StreamHandler(),
        ],
    )


# ──────────────────────────────────────────────────────────
# 메인 앱 실행
# ──────────────────────────────────────────────────────────

def launch_main_app():
    """메인 앱 윈도우를 생성하고 표시합니다."""
    try:
        from ui import MainWindow
    except ImportError as e:
        logging.critical("Cannot import UI module: %s", e)
        wx.MessageBox(
            f"UI 모듈을 불러올 수 없습니다:\n{e}\n\n"
            "필요한 패키지를 설치했는지 확인하세요.",
            "시작 실패",
            wx.OK | wx.ICON_ERROR,
        )
        return

    try:
        frame = MainWindow(None)
        frame.Show()
    except Exception as e:
        logging.critical("Cannot create main window: %s", e)
        wx.MessageBox(
            f"메인 윈도우를 생성할 수 없습니다:\n{e}",
            "시작 실패",
            wx.OK | wx.ICON_ERROR,
        )


# ──────────────────────────────────────────────────────────
# 진입점
# ──────────────────────────────────────────────────────────

def run():
    """앱 실행 진입점.

    흐름:
      1) 환경 진단 다이얼로그 (모달) — 메인 앱 완전 차단
      2) 사용자가 '닫기' 클릭
      3) 필수 충족 → 메인 앱 실행
         필수 미충족 → 경고 후 앱 종료
    """
    _setup_logging()

    app = wx.App()

    # ──────────────────────────────────────────────────
    # HARD GATE: 환경 진단 모달 다이얼로그
    # ShowModal() 은 EndModal() 이 호출될 때까지 반환하지 않음.
    # → 메인 앱은 절대 먼저 실행될 수 없음.
    # ──────────────────────────────────────────────────
    dlg = EnvDiagnosticDialog()
    result = dlg.ShowModal()
    dlg.Destroy()

    if result == wx.ID_OK:
        # 모든 필수 항목 충족 → 메인 앱 실행
        launch_main_app()
        app.MainLoop()
    else:
        # 필수 항목 미충족 → 앱 종료
        wx.MessageBox(
            "필수 환경이 설치되지 않아 "
            "앱을 실행할 수 없습니다.",
            "실행 불가",
            wx.OK | wx.ICON_ERROR,
        )
        # app.MainLoop() 호출하지 않음 → 앱 즉시 종료


if __name__ == "__main__":
    run()
