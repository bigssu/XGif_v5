"""AppSettings 직렬화/검증 테스트."""

import os
from core.settings import AppSettings


class TestAppSettingsDefaults:
    def test_default_language(self):
        s = AppSettings()
        assert s.language == "ko"

    def test_default_capture_backend(self):
        s = AppSettings()
        assert s.capture_backend == "gdi"

    def test_default_encoder(self):
        s = AppSettings()
        assert s.encoder == "auto"

    def test_all_defaults_are_strings(self):
        s = AppSettings()
        d = s.to_dict()
        for k, v in d.items():
            assert isinstance(v, str), f"{k} is {type(v)}, expected str"


class TestAppSettingsGetSet:
    def test_get_existing_key(self):
        s = AppSettings()
        assert s.get("language") == "ko"

    def test_get_nonexistent_key_returns_fallback(self):
        s = AppSettings()
        assert s.get("nonexistent", "default") == "default"

    def test_set_updates_value(self):
        s = AppSettings()
        s.set("language", "en")
        assert s.language == "en"

    def test_get_bool(self):
        s = AppSettings()
        assert s.get_bool("hdr_correction") is False
        s.set("hdr_correction", "true")
        assert s.get_bool("hdr_correction") is True

    def test_get_int(self):
        s = AppSettings()
        assert s.get_int("memory_limit_mb") == 1024

    def test_get_int_invalid_returns_default(self):
        s = AppSettings()
        s.set("memory_limit_mb", "not_a_number")
        assert s.get_int("memory_limit_mb", 512) == 512


class TestAppSettingsSerialization:
    def test_save_and_load(self, tmp_ini):
        s = AppSettings()
        s.set("language", "en")
        s.set("memory_limit_mb", "2048")
        s.save(tmp_ini)

        loaded = AppSettings.load(tmp_ini)
        assert loaded.language == "en"
        assert loaded.memory_limit_mb == "2048"
        # 다른 값들은 기본값 유지
        assert loaded.capture_backend == "gdi"

    def test_load_nonexistent_returns_defaults(self, tmp_dir):
        path = os.path.join(tmp_dir, "nonexistent.ini")
        loaded = AppSettings.load(path)
        assert loaded.language == "ko"

    def test_reset_restores_defaults(self):
        s = AppSettings()
        s.set("language", "en")
        s.set("encoder", "nvenc")
        s.reset()
        assert s.language == "ko"
        assert s.encoder == "auto"


class TestAppSettingsValidation:
    def test_valid_keys(self):
        keys = AppSettings.valid_keys()
        assert "language" in keys
        assert "capture_backend" in keys
        assert "preview_enabled" in keys

    def test_has_key(self):
        s = AppSettings()
        assert s.has_key("language")
        assert not s.has_key("nonexistent_key")

    def test_to_dict_contains_all_keys(self):
        s = AppSettings()
        d = s.to_dict()
        assert len(d) == len(AppSettings.valid_keys())


class TestAppSettingsConfigParserCompat:
    def test_has_section_always_true(self):
        s = AppSettings()
        assert s.has_section("General") is True
        assert s.has_section("Other") is True

    def test_add_section_noop(self):
        s = AppSettings()
        s.add_section("General")  # should not raise

    def test_write_to_file(self, tmp_ini):
        s = AppSettings()
        s.set("language", "en")
        with open(tmp_ini, "w", encoding="utf-8") as f:
            s.write(f)
        # Verify file was written
        assert os.path.exists(tmp_ini)
        assert os.path.getsize(tmp_ini) > 0
