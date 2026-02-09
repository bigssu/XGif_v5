"""
env_diagnostic_ui.py — 환경 진단 다이얼로그 (wxPython)

핵심 동작:
  - wx.Dialog + ShowModal() 로 메인 앱을 완전히 차단 (Hard Gate)
  - 모든 검사·설치는 워커 스레드에서 실행 (UI 논블로킹)
  - 사용자가 '닫기' 를 명시적으로 클릭해야만 다이얼로그 종료
  - 필수 항목이 누락된 채 닫기 시 경고 → 앱 종료 또는 복귀

버튼 동작:
  - 설치:     리스트에서 선택한 항목을 설치 (워커 스레드)
  - 건너뛰기: 선택 항목이면 건너뜀 처리 (필수는 불가)
  - 다시 검사: 전체 재검사
  - 닫기:     필수 충족 시 EndModal(OK), 미충족 시 경고
"""
from __future__ import annotations

import wx
import threading
import logging
import os
import sys
from datetime import datetime
from typing import List, Optional

from .dependency_specs import (
    Dependency, DepStatus, STATUS_LABELS, APP_NAME,
    get_dependencies,
)
from .dependency_checker import check as check_dep
from .dependency_installer import install as install_dep

logger = logging.getLogger(__name__)


# ── 다크 테마 ─────────────────────────────────────────────
_BG = wx.Colour(32, 32, 32)
_BG_LIST = wx.Colour(40, 40, 40)
_BG_LOG = wx.Colour(24, 24, 24)
_TEXT = wx.Colour(255, 255, 255)
_TEXT_DIM = wx.Colour(180, 180, 180)
_ACCENT = wx.Colour(0, 120, 212)
_GREEN = wx.Colour(129, 199, 132)
_RED = wx.Colour(255, 107, 107)
_YELLOW = wx.Colour(255, 213, 79)
_BLUE = wx.Colour(79, 195, 247)

_STATUS_COLORS: dict[DepStatus, wx.Colour] = {
    DepStatus.UNCHECKED: _TEXT_DIM,
    DepStatus.CHECKING: _BLUE,
    DepStatus.PASS: _GREEN,
    DepStatus.MISSING: _RED,
    DepStatus.SKIPPED: _YELLOW,
    DepStatus.INSTALLING: _BLUE,
    DepStatus.INSTALL_OK: _GREEN,
    DepStatus.INSTALL_FAIL: _RED,
    DepStatus.ERROR: _RED,
}

_FONT_FACE = "Segoe UI Variable"
_FONT_FACE_FB = "Segoe UI"
_FONT_MONO = "Consolas"


def _font(size: int, bold: bool = False) -> wx.Font:
    w = wx.FONTWEIGHT_BOLD if bold else wx.FONTWEIGHT_NORMAL
    f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, w, faceName=_FONT_FACE)
    if not f.IsOk():
        f = wx.Font(size, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, w, faceName=_FONT_FACE_FB)
    return f


# ──────────────────────────────────────────────────────────
# EnvDiagnosticDialog
# ──────────────────────────────────────────────────────────

class EnvDiagnosticDialog(wx.Dialog):
    """환경 진단 모달 다이얼로그.

    ShowModal() 로 호출하면 메인 앱이 완전히 차단됩니다.
    EndModal(wx.ID_OK)   → 필수 충족, 메인 앱 실행
    EndModal(wx.ID_CANCEL) → 필수 미충족, 앱 종료
    """

    def __init__(self):
        super().__init__(
            None,
            title="\ud658\uacbd \uc9c4\ub2e8",   # 환경 진단
            size=(740, 680),
            style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
        )
        self._deps: List[Dependency] = get_dependencies()
        self._worker: Optional[threading.Thread] = None
        self._cancel = False

        self.SetBackgroundColour(_BG)
        self._build_ui()
        self.Centre()

        # 열자마자 자동 검사 시작
        wx.CallAfter(self._run_check_all)

    # ──────────────────────────────────────────────────────
    # UI 구성 (sizer 기반, 하드코딩 위치 없음)
    # ──────────────────────────────────────────────────────

    def _build_ui(self):
        panel = wx.Panel(self)
        panel.SetBackgroundColour(_BG)
        self._panel = panel
        root = wx.BoxSizer(wx.VERTICAL)

        # ── 제목 ──
        title = wx.StaticText(panel, label="\ud658\uacbd \uc9c4\ub2e8")
        title.SetForegroundColour(_TEXT)
        title.SetFont(_font(16, bold=True))
        root.Add(title, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)

        desc = wx.StaticText(
            panel,
            label="\uc571 \uc2e4\ud589\uc5d0 \ud544\uc694\ud55c \ud658\uacbd\uc744 "
                  "\uc9c4\ub2e8\ud569\ub2c8\ub2e4. \ubaa8\ub4e0 \ud56d\ubaa9 "
                  "\ud655\uc778 \ud6c4 '\ub2eb\uae30'\ub97c \ub20c\ub7ec\uc8fc\uc138\uc694.",
            # 앱 실행에 필요한 환경을 진단합니다. 모든 항목 확인 후 '닫기'를 눌러주세요.
        )
        desc.SetForegroundColour(_TEXT_DIM)
        desc.SetFont(_font(10))
        root.Add(desc, 0, wx.LEFT | wx.TOP | wx.RIGHT, 20)
        root.AddSpacer(12)

        # ── 의존성 리스트 (항목 | 필수 여부 | 상태 | 설명) ──
        self._list = wx.ListCtrl(
            panel, style=wx.LC_REPORT | wx.LC_SINGLE_SEL | wx.BORDER_NONE,
        )
        self._list.SetBackgroundColour(_BG_LIST)
        self._list.SetForegroundColour(_TEXT)
        self._list.SetFont(_font(10))

        self._list.InsertColumn(0, "\ud56d\ubaa9", width=180)       # 항목
        self._list.InsertColumn(1, "\ud544\uc218 \uc5ec\ubd80", width=80)  # 필수 여부
        self._list.InsertColumn(2, "\uc0c1\ud0dc", width=130)       # 상태
        self._list.InsertColumn(3, "\uc124\uba85", width=300)       # 설명

        for i, dep in enumerate(self._deps):
            idx = self._list.InsertItem(i, dep.display_name)
            self._list.SetItem(idx, 1, dep.required_label)
            self._list.SetItem(idx, 2, STATUS_LABELS[DepStatus.UNCHECKED])
            self._list.SetItem(idx, 3, dep.description)
            self._list.SetItemTextColour(idx, _TEXT_DIM)

        self._list.Bind(wx.EVT_LIST_ITEM_SELECTED, self._on_list_select)
        self._list.Bind(wx.EVT_LIST_ITEM_DESELECTED, self._on_list_deselect)

        root.Add(self._list, 1, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(8)

        # ── 프로그레스 바 ──
        self._gauge = wx.Gauge(
            panel, range=max(len(self._deps), 1),
            style=wx.GA_HORIZONTAL | wx.GA_SMOOTH,
        )
        root.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(8)

        # ── 로그 패널 (스크롤, 읽기 전용) ──
        log_label = wx.StaticText(panel, label="\ub85c\uadf8")  # 로그
        log_label.SetForegroundColour(_TEXT_DIM)
        log_label.SetFont(_font(9))
        root.Add(log_label, 0, wx.LEFT, 20)
        root.AddSpacer(2)

        self._log_text = wx.TextCtrl(
            panel, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.BORDER_NONE,
        )
        self._log_text.SetBackgroundColour(_BG_LOG)
        self._log_text.SetForegroundColour(_TEXT_DIM)
        self._log_text.SetFont(wx.Font(
            9, wx.FONTFAMILY_TELETYPE, wx.FONTSTYLE_NORMAL,
            wx.FONTWEIGHT_NORMAL, faceName=_FONT_MONO,
        ))
        self._log_text.SetMinSize((-1, 120))
        root.Add(self._log_text, 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 20)
        root.AddSpacer(12)

        # ── 버튼 바 ──
        btn_sizer = wx.BoxSizer(wx.HORIZONTAL)

        self._btn_install = wx.Button(panel, label="\uc124\uce58")      # 설치
        self._btn_skip = wx.Button(panel, label="\uac74\ub108\ub6f0\uae30")   # 건너뛰기
        self._btn_recheck = wx.Button(panel, label="\ub2e4\uc2dc \uac80\uc0ac")  # 다시 검사
        self._btn_close = wx.Button(panel, label="\ub2eb\uae30")       # 닫기

        self._btn_install.SetToolTip("\uc120\ud0dd\ud55c \ud56d\ubaa9\uc744 \uc124\uce58\ud569\ub2c8\ub2e4")
        self._btn_skip.SetToolTip("\uc120\ud0dd \ud56d\ubaa9\uc744 \uac74\ub108\ub6f1\ub2c8\ub2e4 (\ud544\uc218 \ud56d\ubaa9\uc740 \ubd88\uac00)")
        self._btn_recheck.SetToolTip("\ubaa8\ub4e0 \ud56d\ubaa9\uc744 \ub2e4\uc2dc \uac80\uc0ac\ud569\ub2c8\ub2e4")
        self._btn_close.SetToolTip("\ud658\uacbd \uc9c4\ub2e8\uc744 \ub2eb\uace0 \uc571\uc744 \uc2e4\ud589\ud569\ub2c8\ub2e4")

        self._btn_install.Enable(False)
        self._btn_skip.Enable(False)

        self._btn_install.Bind(wx.EVT_BUTTON, self._on_install)
        self._btn_skip.Bind(wx.EVT_BUTTON, self._on_skip)
        self._btn_recheck.Bind(wx.EVT_BUTTON, self._on_recheck)
        self._btn_close.Bind(wx.EVT_BUTTON, self._on_close_btn)

        btn_sizer.Add(self._btn_install, 0, wx.RIGHT, 6)
        btn_sizer.Add(self._btn_skip, 0, wx.RIGHT, 6)
        btn_sizer.Add(self._btn_recheck, 0)
        btn_sizer.AddStretchSpacer()
        btn_sizer.Add(self._btn_close, 0)

        root.Add(btn_sizer, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 20)

        panel.SetSizer(root)

        # X 버튼(창 닫기)도 동일한 검증 로직 적용
        self.Bind(wx.EVT_CLOSE, self._on_close_event)

    # ──────────────────────────────────────────────────────
    # 로그
    # ──────────────────────────────────────────────────────

    def _append_log(self, msg: str):
        """스레드 안전 로그 추가"""
        ts = datetime.now().strftime("%H:%M:%S")
        wx.CallAfter(self._log_text.AppendText, f"[{ts}] {msg}\n")

    # ──────────────────────────────────────────────────────
    # 리스트 선택 → 버튼 활성화
    # ──────────────────────────────────────────────────────

    def _on_list_select(self, event):
        self._refresh_action_buttons()

    def _on_list_deselect(self, event):
        self._btn_install.Enable(False)
        self._btn_skip.Enable(False)

    def _refresh_action_buttons(self):
        """선택된 행에 따라 설치/건너뛰기 버튼 상태 갱신"""
        idx = self._list.GetFirstSelected()
        if idx < 0 or self._is_busy():
            self._btn_install.Enable(False)
            self._btn_skip.Enable(False)
            return

        dep = self._deps[idx]

        can_install = dep.status in (
            DepStatus.MISSING, DepStatus.INSTALL_FAIL, DepStatus.ERROR,
        )
        self._btn_install.Enable(can_install)

        can_skip = (
            not dep.required
            and dep.status in (DepStatus.MISSING, DepStatus.ERROR, DepStatus.INSTALL_FAIL)
        )
        self._btn_skip.Enable(can_skip)

    # ──────────────────────────────────────────────────────
    # 전체 검사
    # ──────────────────────────────────────────────────────

    def _run_check_all(self):
        if self._is_busy():
            return
        self._set_busy(True)
        self._gauge.SetRange(len(self._deps))
        self._gauge.SetValue(0)
        self._cancel = False
        self._worker = threading.Thread(target=self._check_all_worker, daemon=True)
        self._worker.start()

    def _check_all_worker(self):
        try:
            for i, dep in enumerate(self._deps):
                if self._cancel:
                    break
                # SKIPPED 항목은 재검사하지 않음
                if dep.status == DepStatus.SKIPPED:
                    wx.CallAfter(self._gauge.SetValue, i + 1)
                    continue

                wx.CallAfter(self._update_row, i)
                dep.status = DepStatus.CHECKING
                dep.detail = ""
                wx.CallAfter(self._update_row, i)

                check_dep(dep, log_cb=self._append_log)

                wx.CallAfter(self._update_row, i)
                wx.CallAfter(self._gauge.SetValue, i + 1)
        except Exception as e:
            logger.exception("Check failed")
            self._append_log(f"검사 중 오류: {e}")
        finally:
            wx.CallAfter(self._on_work_done)

    # ──────────────────────────────────────────────────────
    # 개별 설치
    # ──────────────────────────────────────────────────────

    def _on_install(self, _event):
        idx = self._list.GetFirstSelected()
        if idx < 0 or self._is_busy():
            return
        dep = self._deps[idx]
        self._set_busy(True)
        self._worker = threading.Thread(
            target=self._install_worker, args=(idx, dep), daemon=True,
        )
        self._worker.start()

    def _install_worker(self, idx: int, dep: Dependency):
        try:
            # 1) 설치
            dep.status = DepStatus.INSTALLING
            dep.detail = "\uc124\uce58 \uc911\u2026"  # 설치 중…
            wx.CallAfter(self._update_row, idx)

            install_dep(dep, log_cb=self._append_log)
            wx.CallAfter(self._update_row, idx)

            # 2) 설치 성공 시 재검사 (CuPy: import + CUDA 확인)
            if dep.status == DepStatus.INSTALL_OK:
                self._append_log(f"설치 후 재검사: {dep.display_name}")
                dep.status = DepStatus.CHECKING
                dep.detail = ""
                wx.CallAfter(self._update_row, idx)

                check_dep(dep, log_cb=self._append_log)
                wx.CallAfter(self._update_row, idx)

        except Exception as e:
            dep.status = DepStatus.INSTALL_FAIL
            dep.detail = str(e)
            wx.CallAfter(self._update_row, idx)
        finally:
            wx.CallAfter(self._on_work_done)

    # ──────────────────────────────────────────────────────
    # 건너뛰기
    # ──────────────────────────────────────────────────────

    def _on_skip(self, _event):
        idx = self._list.GetFirstSelected()
        if idx < 0:
            return
        dep = self._deps[idx]
        if dep.required:
            wx.MessageBox(
                "\ud544\uc218 \ud56d\ubaa9\uc740 \uac74\ub108\ub6f8 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4.",
                # 필수 항목은 건너뛸 수 없습니다.
                "\uc54c\ub9bc",  # 알림
                wx.OK | wx.ICON_WARNING, self,
            )
            return
        dep.status = DepStatus.SKIPPED
        dep.detail = "\uc0ac\uc6a9\uc790\uac00 \uac74\ub108\ub6f0"  # 사용자가 건너뜀
        self._update_row(idx)
        self._refresh_action_buttons()

    # ──────────────────────────────────────────────────────
    # 다시 검사
    # ──────────────────────────────────────────────────────

    def _on_recheck(self, _event):
        # SKIPPED 이 아닌 항목 모두 초기화
        for i, dep in enumerate(self._deps):
            if dep.status != DepStatus.SKIPPED:
                dep.status = DepStatus.UNCHECKED
                dep.detail = ""
                self._update_row(i)
        self._run_check_all()

    # ──────────────────────────────────────────────────────
    # 닫기 (Hard Gate)
    # ──────────────────────────────────────────────────────

    def _on_close_btn(self, _event):
        self._try_close()

    def _on_close_event(self, event):
        """X 버튼으로 닫을 때도 동일한 검증."""
        event.Veto()  # 기본 닫기 차단 — EndModal 로만 종료
        self._try_close()

    def _try_close(self):
        """필수 항목 충족 여부를 확인하고 다이얼로그 종료.

        - 작업 중: 경고 후 복귀
        - 필수 미충족: 경고 → '예' 클릭 시 앱 종료 (ID_CANCEL)
        - 필수 충족: 정상 종료 (ID_OK)
        """
        if self._is_busy():
            wx.MessageBox(
                "\uc791\uc5c5\uc774 \uc9c4\ud589 \uc911\uc785\ub2c8\ub2e4. "
                "\uc644\ub8cc \ud6c4 \ub2e4\uc2dc \uc2dc\ub3c4\ud558\uc138\uc694.",
                # 작업이 진행 중입니다. 완료 후 다시 시도하세요.
                "\uc54c\ub9bc", wx.OK | wx.ICON_INFORMATION, self,
            )
            return

        missing = [
            d for d in self._deps
            if d.required and not d.is_satisfied
        ]

        if missing:
            names = "\n  - ".join(d.display_name for d in missing)
            answer = wx.MessageBox(
                f"\ub2e4\uc74c \ud544\uc218 \ud56d\ubaa9\uc774 \uc124\uce58\ub418\uc9c0 "
                f"\uc54a\uc558\uc2b5\ub2c8\ub2e4:\n  - {names}\n\n"
                "\uc571\uc744 \uc2e4\ud589\ud560 \uc218 \uc5c6\uc2b5\ub2c8\ub2e4. "
                "\uc885\ub8cc\ud558\uc2dc\uaca0\uc2b5\ub2c8\uae4c?",
                # 다음 필수 항목이 설치되지 않았습니다: ...
                # 앱을 실행할 수 없습니다. 종료하시겠습니까?
                "\ud544\uc218 \ud658\uacbd \ub204\ub77d",  # 필수 환경 누락
                wx.YES_NO | wx.ICON_WARNING, self,
            )
            if answer == wx.YES:
                self.EndModal(wx.ID_CANCEL)
            # answer == NO → 다이얼로그에 복귀 (닫지 않음)
        else:
            self.EndModal(wx.ID_OK)

    # ──────────────────────────────────────────────────────
    # 내부 유틸리티
    # ──────────────────────────────────────────────────────

    def _is_busy(self) -> bool:
        return self._worker is not None and self._worker.is_alive()

    def _set_busy(self, busy: bool):
        self._btn_install.Enable(not busy)
        self._btn_skip.Enable(not busy)
        self._btn_recheck.Enable(not busy)
        # 닫기 버튼은 항상 클릭 가능 (검증 로직에서 차단)

    def _on_work_done(self):
        """워커 스레드 완료 후 호출"""
        self._worker = None
        self._set_busy(False)
        self._refresh_action_buttons()

    def _update_row(self, row: int):
        """리스트 행을 dep 의 현재 상태로 갱신"""
        dep = self._deps[row]
        status = dep.status

        # 상태 레이블: MISSING 은 필수/선택에 따라 분기
        if status == DepStatus.MISSING:
            label = "\ud544\uc218 (\uc124\uce58 \ud544\uc694)" if dep.required else "\uc120\ud0dd (\ubbf8\uc124\uce58)"
            color = _RED if dep.required else _YELLOW
        else:
            label = STATUS_LABELS.get(status, status.value)
            color = _STATUS_COLORS.get(status, _TEXT)

        self._list.SetItem(row, 2, label)
        self._list.SetItem(row, 3, dep.detail)
        self._list.SetItemTextColour(row, color)
