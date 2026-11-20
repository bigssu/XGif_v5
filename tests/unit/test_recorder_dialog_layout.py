import pytest
import wx

from core.settings import AppSettings
from ui import dependency_dialogs
from ui.design_system import CommandButton
from ui.i18n import get_trans_manager
from ui.settings_dialog import SettingsDialog


@pytest.fixture
def locale(request):
    app = wx.App.Get() or wx.App(False)
    manager = get_trans_manager()
    previous = manager.current_lang
    manager.set_language(request.param)
    yield request.param
    manager.set_language(previous)
    app.ProcessPendingEvents()


def assert_buttons_fit(buttons):
    for i, button in enumerate(buttons):
        rect = button.GetRect()
        client = button.GetParent().GetClientRect()
        assert client.Contains(rect)
        assert rect.width >= button.GetTextExtent(button.GetLabel()).width
        assert rect.height > 0
        assert all(not rect.Intersects(other.GetRect()) for other in buttons[:i])


@pytest.mark.parametrize('locale', ['ko', 'en'], indirect=True)
@pytest.mark.parametrize('font_scale', [1, 1.5, 2])
def test_settings_actions_fit_at_minimum_and_default_width(locale, font_scale):
    dialog = SettingsDialog(None, AppSettings(language=locale))
    try:
        buttons = [dialog.reset_btn, dialog.reset_dep_btn, dialog.ok_btn, dialog.cancel_btn]
        for button in buttons:
            button.SetFont(button.GetFont().Scaled(font_scale))
        for size in (dialog.GetMinSize(), dialog.FromDIP((520, 580))):
            dialog.SetSize(size)
            dialog.Layout()
            dialog.ok_btn.GetParent().Layout()
            assert_buttons_fit(buttons)
    finally:
        dialog.Destroy()
        wx.GetApp().Yield()
        assert dialog.retranslateUi not in get_trans_manager()._callbacks


@pytest.mark.parametrize('locale', ['ko', 'en'], indirect=True)
def test_gpu_guide_diagnostic_does_not_displace_actions(locale, monkeypatch):
    monkeypatch.setattr(dependency_dialogs, '_detect_nvidia_gpu_name', lambda: 'RTX 5080')
    monkeypatch.setattr(dependency_dialogs, '_detect_cuda_driver_version', lambda: (13, 5))
    dialog = dependency_dialogs.CuPyInstallGuideDialog(None, diagnostic='long diagnostic\n' * 100)
    try:
        dialog.SetSize(dialog.GetMinSize())
        dialog.Layout()
        assert_buttons_fit([w for w in dialog.Children if isinstance(w, CommandButton)])
        assert all(dialog.GetClientRect().Contains(w.GetRect()) for w in dialog.Children if w.IsShown())
    finally:
        dialog.Destroy()
