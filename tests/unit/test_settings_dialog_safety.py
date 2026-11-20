import configparser
from types import SimpleNamespace
from unittest.mock import Mock

from core.utils import APP_SETTINGS_NAME
from ui.settings_dialog import SettingsDialog


def test_legacy_settings_write_failure_preserves_existing_file(tmp_path, monkeypatch):
    monkeypatch.setenv('APPDATA', str(tmp_path))
    target = tmp_path / APP_SETTINGS_NAME / 'config.ini'
    target.parent.mkdir()
    original = b'[General]\nlast_save_dir=C:/100% done\n'
    target.write_bytes(original)
    settings = configparser.ConfigParser(interpolation=None)
    settings.read_string(original.decode())
    def failed_write(stream):
        stream.write('partial')
        raise OSError('disk full')
    monkeypatch.setattr(settings, 'write', failed_write)
    window = SimpleNamespace(settings=settings, _is_app_settings=False, trans=Mock())
    window._cfg_set = lambda key, value: SettingsDialog._cfg_set(window, key, value)
    for name in ['mic_audio_cb', 'watermark_cb', 'click_highlight_cb', 'keyboard_display_cb',
                 'preview_cb', 'hdr_correction_cb']:
        setattr(window, name, SimpleNamespace(GetValue=lambda: False))
    for name in ['backend_combo', 'encoder_combo', 'codec_combo', 'memory_limit_combo', 'lang_combo']:
        setattr(window, name, SimpleNamespace(GetSelection=lambda: 0))
    window.memory_limit_combo.GetClientData = lambda idx: "1024"
    assert SettingsDialog.save_settings(window) is False
    window.trans.set_language.assert_not_called()
    assert target.read_bytes() == original
    assert list(target.parent.iterdir()) == [target]


def test_failed_or_cancelled_dialog_keeps_recorder_settings(tmp_path, monkeypatch):
    import wx
    from core.settings import AppSettings

    app = wx.App.Get() or wx.App(False)
    monkeypatch.setenv('APPDATA', str(tmp_path))
    live = AppSettings(skip_cupy_check='true')
    dialog = SettingsDialog(None, live)
    try:
        dialog._on_reset_dep_flags(None)
        assert live.skip_cupy_check == 'true'
        dialog.watermark_cb.SetValue(True)
        with monkeypatch.context() as patch:
            patch.setattr(AppSettings, 'save', Mock(side_effect=PermissionError()))
            assert not dialog.save_settings()
        assert live.watermark == 'false'
        assert dialog.save_settings()
        assert AppSettings.load().watermark == 'true'
        assert AppSettings.load().skip_cupy_check == 'false'
    finally:
        dialog.Destroy()
        app.Yield()


def test_custom_memory_limit_survives_gui_language_and_unrelated_save(tmp_path, monkeypatch):
    import wx
    from cli.config import set_config_value
    from core.settings import AppSettings

    app = wx.App.Get() or wx.App(False)
    monkeypatch.setenv('APPDATA', str(tmp_path))
    assert set_config_value('memory_limit_mb', '256')
    dialog = SettingsDialog(None, AppSettings.load())
    try:
        assert '256' in dialog.memory_limit_combo.GetStringSelection()
        dialog.retranslateUi()
        assert '256' in dialog.memory_limit_combo.GetStringSelection()
        dialog.watermark_cb.SetValue(True)
        assert dialog.save_settings()
        saved = AppSettings.load()
        assert saved.memory_limit_mb == '256' and saved.watermark == 'true'
        dialog.memory_limit_combo.SetSelection(1)
        assert dialog.save_settings()
        assert AppSettings.load().memory_limit_mb == '2048'
    finally:
        dialog.Destroy()
        app.Yield()
