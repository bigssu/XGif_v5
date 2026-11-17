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
    assert SettingsDialog.save_settings(window) is False
    assert target.read_bytes() == original
    assert list(target.parent.iterdir()) == [target]
