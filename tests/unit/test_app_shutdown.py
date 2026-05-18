from types import SimpleNamespace

from core import app_shutdown


class _FakeApp:
    def __init__(self):
        self.exit_called = False

    def ExitMainLoop(self):
        self.exit_called = True


class _FakeWindow:
    def __init__(self, shown=True, style=0):
        self.shown = shown
        self.style = style
        self.hidden = False
        self.destroyed = False

    def GetHandle(self):
        return 1

    def IsShown(self):
        return self.shown

    def GetWindowStyleFlag(self):
        return self.style

    def Hide(self):
        self.hidden = True
        self.shown = False

    def Destroy(self):
        self.destroyed = True


class CaptureOverlay(_FakeWindow):
    pass


class EditorWindow(_FakeWindow):
    pass


def _install_fake_wx(monkeypatch, windows, app):
    fake_wx = SimpleNamespace(
        FRAME_NO_TASKBAR=0x0001,
        App=SimpleNamespace(Get=lambda: app),
        GetTopLevelWindows=lambda: windows,
    )
    monkeypatch.setattr(app_shutdown, "wx", fake_wx)


def test_shutdown_reaps_capture_overlay_even_when_editor_primary_is_alive(monkeypatch):
    app = _FakeApp()
    editor = EditorWindow(shown=True)
    overlay = CaptureOverlay(shown=True)
    _install_fake_wx(monkeypatch, [editor, overlay], app)

    result = app_shutdown.ensure_exit_if_no_primary_windows("main_window_close")

    assert result is False
    assert overlay.hidden is True
    assert overlay.destroyed is True
    assert editor.destroyed is False
    assert app.exit_called is False


def test_shutdown_exits_when_only_capture_overlay_remains(monkeypatch):
    app = _FakeApp()
    overlay = CaptureOverlay(shown=True)
    _install_fake_wx(monkeypatch, [overlay], app)

    result = app_shutdown.ensure_exit_if_no_primary_windows("overlay_only")

    assert result is True
    assert overlay.hidden is True
    assert overlay.destroyed is True
    assert app.exit_called is True
