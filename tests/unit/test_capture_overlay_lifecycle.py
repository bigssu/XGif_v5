import ast
import contextlib
import time
from pathlib import Path

import pytest
import wx

from tests._ast_helpers import find_class, find_function, read_module


_WX_APP = None


def _ensure_wx_app():
    global _WX_APP
    app = wx.App.Get()
    if app is None:
        _WX_APP = wx.App(False)
        app = _WX_APP
    return app


def _yield_for(milliseconds: int):
    deadline = time.monotonic() + milliseconds / 1000
    while time.monotonic() < deadline:
        wx.YieldIfNeeded()
        time.sleep(0.02)


def test_capture_overlay_is_owned_by_parent_window_and_dies_with_it():
    _ensure_wx_app()
    from ui.capture_overlay import CaptureOverlay

    parent = wx.Frame(None)
    overlay = None
    try:
        parent.Show()
        overlay = CaptureOverlay(parent)
        overlay.Show()
        wx.YieldIfNeeded()

        assert overlay.GetParent() is parent

        parent.Destroy()
        _yield_for(800)

        with pytest.raises(RuntimeError):
            overlay.GetHandle()
    finally:
        if overlay is not None:
            with contextlib.suppress(RuntimeError):
                overlay.Destroy()
        with contextlib.suppress(RuntimeError):
            parent.Destroy()


def test_capture_overlay_has_orphan_guard_contract():
    source = Path("ui/capture_overlay.py").read_text(encoding="utf-8")

    assert "wx.Frame.__init__(self, parent_window" in source
    assert "parent_window.Bind(wx.EVT_WINDOW_DESTROY, self._on_parent_window_destroy)" in source
    assert "self.lifecycle_timer = wx.Timer(self)" in source
    assert "ensure_exit_if_no_primary_windows(\"capture_overlay_orphan_guard\")" in source


def test_main_window_does_not_recreate_overlay_when_primary_window_is_not_live():
    source, module = read_module("ui/main_window.py")
    main_window = find_class(module, "MainWindow")
    on_overlay_closed = find_function(main_window, "_on_overlay_closed")
    recreate_guard = find_function(main_window, "_window_allows_overlay_recreate")
    on_overlay_closed_source = ast.get_source_segment(source, on_overlay_closed)
    recreate_guard_source = ast.get_source_segment(source, recreate_guard)

    assert "if not self._window_allows_overlay_recreate():" in on_overlay_closed_source
    assert "wx.CallLater(100, self._show_capture_overlay)" in on_overlay_closed_source
    assert "self.GetHandle()" in recreate_guard_source
    assert "self.IsShown()" in recreate_guard_source
