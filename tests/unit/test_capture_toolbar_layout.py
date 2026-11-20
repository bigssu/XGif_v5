"""Exercise measured toolbar layout with the same controls installed by main.py."""
from pathlib import Path
import subprocess
import sys


def test_recording_toolbar_fits_localized_actions_and_dropdowns():
    # wx replacement installation is process-wide. Isolate it from native wx tests.
    subprocess.run([sys.executable, __file__, "--wx"], cwd=Path(__file__).resolve().parents[2],
                   check=True, timeout=45)


def check_windows():
    import wx
    from ui.dark_controls import install_dark_controls
    install_dark_controls(wx)
    from ui.capture_control_bar import CaptureControlBar
    from ui.i18n import get_trans_manager, tr

    app = wx.App()
    frame = wx.Frame(None)
    bar = CaptureControlBar(frame)
    for lang in ("en", "ko"):
        get_trans_manager().set_language(lang)
        for width in (360, 440, 700, 940):
            for scale in (1, 1.5, 2):
                for c in (bar.quality_combo, bar.gpu_status_button, bar.rec_button):
                    font = c.GetFont()
                    font.SetPointSize(round(scale * 10))
                    c.SetFont(font)
                bar._measure_choices()
                bar.set_gpu_status(False)
                bar.rec_button.SetIconType(None)
                bar.rec_button.SetLabel(tr("save_now"))
                height = bar.layout_for_width(width)
                bar.SetSize((width, height))
                bar.layout_for_width(width)
                bounds = wx.Rect(0, 0, width, height)
                rects = [child.GetRect() for child in bar.GetChildren() if child.IsShown()]
                assert all(bounds.Contains(rect) for rect in rects), (lang, width, scale, rects)
                assert not any(rect.Intersects(other) for i, rect in enumerate(rects)
                               for other in rects[i + 1:])
                for field in (bar.quality_combo, bar.fps_combo, bar.format_combo, bar.resolution_combo):
                    assert all(field.GetTextExtent(choice).width + 32 <= field.GetSize().width
                               for choice in field.GetItems())
                assert bar.rec_button.GetLabel() in ("Save", "저장")
    if sys.platform == "win32":
        check_recorder_accelerators()
    frame.Destroy()
    app.Yield()


def check_recorder_accelerators():
    from unittest.mock import patch
    import wx
    from ui.main_window import MainWindow

    recorder = wx.Frame(None)
    calls = []
    recorder._on_shortcut_rec = lambda event: calls.append("record")
    recorder._on_shortcut_stop = lambda event: calls.append("stop")
    recorder._on_shortcut_overlay = lambda event: calls.append("overlay")
    with patch.object(wx, "AcceleratorTable", wraps=wx.AcceleratorTable) as make_table:
        MainWindow._setup_shortcuts(recorder)
    entries, = make_table.call_args.args
    assert recorder.GetAcceleratorTable().IsOk()
    assert [(mods, key) for mods, key, _ in entries] == [
        (wx.ACCEL_NORMAL, key) for key in (wx.WXK_F9, wx.WXK_F10, wx.WXK_F11)
    ]
    field = wx.TextCtrl(recorder)
    # An accelerator generates a menu command. Exercise its actual wx route
    # without making the tests depend on which application has desktop focus.
    for _, _, command in entries:
        field.GetEventHandler().ProcessEvent(wx.CommandEvent(wx.EVT_MENU.typeId, command))
    recorder.Destroy()
    assert calls == ["record", "stop", "overlay"]


if __name__ == "__main__":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    check_windows()
