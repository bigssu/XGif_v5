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
# 메인 앱 스텁 — 실제 앱으로 교체하세요
# ──────────────────────────────────────────────────────────

class MainAppStub(wx.Frame):
    """메인 앱 플레이스홀더.

    TODO: 이 클래스를 삭제하고 launch_main_app() 에서
          실제 메인 윈도우를 생성하세요.
    """

    def __init__(self):
        super().__init__(None, title=f"{APP_NAME}", size=(900, 600))
        self.SetBackgroundColour(wx.Colour(32, 32, 32))

        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer()

        msg = wx.StaticText(self, label="\ud658\uacbd \uc9c4\ub2e8 \uc644\ub8cc! \uba54\uc778 \uc571\uc774 \uc2e4\ud589\ub418\uc5c8\uc2b5\ub2c8\ub2e4.")
        # 환경 진단 완료! 메인 앱이 실행되었습니다.
        msg.SetForegroundColour(wx.Colour(255, 255, 255))
        msg.SetFont(wx.Font(
            14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL, faceName="Segoe UI Variable",
        ))
        sizer.Add(msg, 0, wx.ALIGN_CENTER)

        sizer.AddStretchSpacer()
        self.SetSizer(sizer)
        self.Centre()


def launch_main_app():
    """메인 앱 윈도우를 생성하고 표시합니다.

    TODO: 아래를 실제 메인 윈도우로 교체하세요:
        from ui.main_window import MainWindow
        frame = MainWindow(None)
        frame.Show()
    """
    frame = MainAppStub()
    frame.Show()


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
            "\ud544\uc218 \ud658\uacbd\uc774 \uc124\uce58\ub418\uc9c0 \uc54a\uc544 "
            "\uc571\uc744 \uc2e4\ud589\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
            # 필수 환경이 설치되지 않아 앱을 실행할 수 없습니다.
            "\uc2e4\ud589 \ubd88\uac00",  # 실행 불가
            wx.OK | wx.ICON_ERROR,
        )
        # app.MainLoop() 호출하지 않음 → 앱 즉시 종료


if __name__ == "__main__":
    run()
