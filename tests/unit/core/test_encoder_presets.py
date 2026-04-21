"""인코더 프리셋 테스트."""

import pytest
from core.encoder.presets import QUALITY_PRESETS, ENCODER_TYPE_MAP


class TestQualityPresets:
    def test_all_presets_exist(self):
        assert "high" in QUALITY_PRESETS
        assert "medium" in QUALITY_PRESETS
        assert "low" in QUALITY_PRESETS

    def test_high_has_max_colors(self):
        assert QUALITY_PRESETS["high"].colors == 256

    def test_low_has_fewer_colors(self):
        assert QUALITY_PRESETS["low"].colors < QUALITY_PRESETS["high"].colors

    def test_preset_is_frozen(self):
        with pytest.raises(AttributeError):
            QUALITY_PRESETS["high"].colors = 128


class TestEncoderTypeMap:
    def test_known_types(self):
        assert "auto" in ENCODER_TYPE_MAP
        assert "nvenc" in ENCODER_TYPE_MAP
        assert "cpu" in ENCODER_TYPE_MAP
