"""Use an isolated wx event loop for the production recording-complete dialog."""
from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest


@pytest.mark.parametrize('command', ['escape', 'close', 'discard'])
@pytest.mark.parametrize('take_format', ['GIF', 'MP4'])
def test_only_explicit_discard_releases_take(take_format, command):
    subprocess.run([sys.executable, __file__, take_format, command],
                   cwd=Path(__file__).resolve().parents[2], check=True, timeout=35)


def check_dialog(take_format, command):
    import wx
    from ui.dark_controls import install_dark_controls

    install_dark_controls(wx)
    from ui.main_window import MainWindow
    from ui.theme import ThemedDialog

    app = wx.App(False)
    window = wx.Frame(None)
    window._take_format = take_format
    window.recorder = Mock()
    window.audio_recorder = Mock()
    window.audio_file_path = 'kept.wav'
    window._reset_ui = Mock()

    def dispatch():
        dlg = next(w for w in window.GetChildren() if isinstance(w, ThemedDialog))
        assert dlg.GetEscapeId() == wx.ID_CANCEL
        assert (dlg.FindWindow(wx.ID_NO) is not None) == (take_format == 'GIF')
        if command == 'close':
            dlg.Close()
        elif command == 'escape':
            key = wx.KeyEvent(wx.EVT_CHAR_HOOK.typeId)
            key.SetKeyCode(wx.WXK_ESCAPE)
            key.SetEventObject(dlg)
            dlg.ProcessWindowEvent(key)
        else:
            button = dlg.FindWindow(wx.ID_DELETE)
            button.ProcessWindowEvent(wx.CommandEvent(wx.EVT_BUTTON.typeId, wx.ID_DELETE))

    try:
        wx.CallAfter(dispatch)
        MainWindow._show_save_edit_dialog(window, 10)
        if command == 'discard':
            window._reset_ui.assert_called_once_with()
            window.recorder.clear_frames.assert_called_once()
            window.audio_recorder.cleanup.assert_called_once()
            assert window.audio_file_path is None
        else:
            window._reset_ui.assert_called_once_with(clear_frames=False)
            window.recorder.clear_frames.assert_not_called()
            window.audio_recorder.cleanup.assert_not_called()
            assert window.audio_file_path == 'kept.wav'
    finally:
        window.Destroy()
        app.Yield()


if __name__ == '__main__':
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    check_dialog(*sys.argv[1:])
