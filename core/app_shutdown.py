"""wx 앱 종료 보조 유틸리티."""

from __future__ import annotations

import logging
from typing import List

import wx
import contextlib

logger = logging.getLogger(__name__)


def _get_live_top_windows() -> List[wx.Window]:
    """파괴되지 않은 최상위 윈도우 목록을 반환."""
    live_windows: List[wx.Window] = []
    for win in wx.GetTopLevelWindows():
        if win is None:
            continue
        try:
            if not win.GetHandle():
                continue
        except Exception:
            continue
        live_windows.append(win)
    return live_windows


def _is_primary_window(win: wx.Window) -> bool:
    """앱 유지가 필요한 주요 창인지 판별."""
    try:
        if not win.IsShown():
            return False
    except Exception:
        return False

    try:
        style = win.GetWindowStyleFlag()
    except Exception:
        style = 0

    # 캡처 오버레이/툴 윈도우는 앱 생존의 기준 창으로 취급하지 않는다.
    if style & wx.FRAME_NO_TASKBAR:
        return False
    return win.__class__.__name__ != "CaptureOverlay"


def _is_capture_overlay(win: wx.Window) -> bool:
    """CaptureOverlay 창인지 판별."""
    return win.__class__.__name__ == "CaptureOverlay"


def destroy_capture_overlays(windows: List[wx.Window] | None = None) -> int:
    """독립/잔류 CaptureOverlay 창을 전역으로 회수."""
    if windows is None:
        windows = _get_live_top_windows()

    destroyed = 0
    for win in windows:
        if not _is_capture_overlay(win):
            continue
        with contextlib.suppress(Exception):
            win.Hide()
        with contextlib.suppress(Exception):
            win.Destroy()
            destroyed += 1
    return destroyed


def ensure_exit_if_no_primary_windows(reason: str = "") -> bool:
    """주요 창이 모두 닫혔다면 잔여 창을 정리하고 MainLoop를 종료."""
    app = wx.App.Get()
    if app is None:
        return False

    live_windows = _get_live_top_windows()
    destroyed_overlays = destroy_capture_overlays(live_windows)
    if destroyed_overlays:
        logger.info(
            "Destroyed %d capture overlay window(s) during shutdown check (reason=%s)",
            destroyed_overlays,
            reason or "shutdown_check",
        )

    primary_windows = [win for win in live_windows if _is_primary_window(win)]

    if primary_windows:
        return False

    for win in live_windows:
        with contextlib.suppress(Exception):
            win.Hide()
        with contextlib.suppress(Exception):
            win.Destroy()

    try:
        app.ExitMainLoop()
    except Exception as exc:
        logger.debug("ExitMainLoop failed (%s): %s", reason, exc)
        return False

    logger.info("Application shutdown requested (reason=%s)", reason or "no_primary_window")
    return True

