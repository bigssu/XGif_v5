"""CLI 인자 파싱 테스트."""

from core.settings import AppSettings


class TestSettingsValidKeys:
    def test_common_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "language" in keys
        assert "capture_backend" in keys
        assert "encoder" in keys
        assert "codec" in keys
        assert "memory_limit_mb" in keys

    def test_ui_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "preview_enabled" in keys
        assert "skip_ffmpeg_check" in keys

    def test_state_keys_exist(self):
        keys = AppSettings.valid_keys()
        assert "fps" in keys
        assert "resolution_preset" in keys
        assert "last_save_dir" in keys
