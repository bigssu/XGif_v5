"""Windows chrome helpers for wx frames."""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes

import wx

from ui.theme import Colors


def _colorref(colour: wx.Colour) -> int:
    return colour.Red() | (colour.Green() << 8) | (colour.Blue() << 16)


def apply_dark_title_bar(window: wx.Window) -> None:
    """Apply dark DWM caption colors when available.

    wx.SystemOptions dark mode does not reliably affect the native titlebar on
    all Windows builds. DWM attributes are best-effort and harmless elsewhere.
    """
    if sys.platform != "win32":
        return

    hwnd = int(window.GetHandle())
    if not hwnd:
        return

    dwmapi = ctypes.windll.dwmapi

    dark = wintypes.BOOL(True)
    for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(dark),
            ctypes.sizeof(dark),
        )

    attributes = (
        (35, Colors.BG_PRIMARY),       # DWMWA_CAPTION_COLOR
        (34, Colors.BG_PRIMARY),       # DWMWA_BORDER_COLOR
        (36, Colors.TEXT_PRIMARY),     # DWMWA_TEXT_COLOR
    )
    for attribute, colour in attributes:
        value = wintypes.DWORD(_colorref(colour))
        dwmapi.DwmSetWindowAttribute(
            wintypes.HWND(hwnd),
            wintypes.DWORD(attribute),
            ctypes.byref(value),
            ctypes.sizeof(value),
        )
