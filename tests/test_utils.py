"""
유틸리티 함수 테스트
"""

import pytest
import numpy as np


class TestParseResolution:
    """해상도 파싱 테스트"""

    def test_standard_format(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920x1080") == (1920, 1080)

    def test_uppercase_x(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920X1080") == (1920, 1080)

    def test_unicode_multiply(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920×1080") == (1920, 1080)

    def test_asterisk(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920*1080") == (1920, 1080)

    def test_with_spaces(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920 x 1080") == (1920, 1080)

    def test_empty_string(self):
        from core.utils import parse_resolution
        assert parse_resolution("") is None

    def test_none(self):
        from core.utils import parse_resolution
        assert parse_resolution(None) is None

    def test_invalid_format(self):
        from core.utils import parse_resolution
        assert parse_resolution("invalid") is None

    def test_single_number(self):
        from core.utils import parse_resolution
        assert parse_resolution("1920") is None


class TestValidateResolution:
    """해상도 유효성 검증 테스트"""

    def test_valid_resolution(self):
        from core.utils import validate_resolution
        assert validate_resolution(1920, 1080) is True

    def test_too_small(self):
        from core.utils import validate_resolution
        assert validate_resolution(10, 10) is False

    def test_too_large(self):
        from core.utils import validate_resolution
        assert validate_resolution(5000, 5000) is False

    def test_min_boundary(self):
        from core.utils import validate_resolution
        assert validate_resolution(50, 50) is True

    def test_max_boundary(self):
        from core.utils import validate_resolution
        assert validate_resolution(3840, 3840) is True


class TestCalculateOverlayPosition:
    """오버레이 위치 계산 테스트"""

    def test_bottom_right(self):
        from core.utils import calculate_overlay_position
        x, y = calculate_overlay_position(1920, 1080, 100, 50, 'bottom-right', 10)
        assert x == 1810
        assert y == 1020

    def test_top_left(self):
        from core.utils import calculate_overlay_position
        x, y = calculate_overlay_position(1920, 1080, 100, 50, 'top-left', 10)
        assert x == 10
        assert y == 10

    def test_center(self):
        from core.utils import calculate_overlay_position
        x, y = calculate_overlay_position(1920, 1080, 100, 50, 'center', 10)
        assert x == 910
        assert y == 515

    def test_clipping(self):
        from core.utils import calculate_overlay_position
        x, y = calculate_overlay_position(100, 100, 200, 200, 'bottom-right', 10)
        assert x == 0
        assert y == 0


class TestAlphaBlend:
    """알파 블렌딩 테스트"""

    def test_rgb_overlay(self):
        from core.utils import apply_alpha_blend
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        overlay = np.full((50, 50, 3), 255, dtype=np.uint8)
        result = apply_alpha_blend(bg, overlay, 10, 10, 0.5)
        assert result is not None
        assert result.shape == (100, 100, 3)

    def test_rgba_overlay(self):
        from core.utils import apply_alpha_blend
        bg = np.zeros((100, 100, 3), dtype=np.uint8)
        overlay = np.full((50, 50, 4), 255, dtype=np.uint8)
        result = apply_alpha_blend(bg, overlay, 10, 10, 1.0)
        assert result is not None

    def test_none_background(self):
        from core.utils import apply_alpha_blend
        overlay = np.full((50, 50, 3), 255, dtype=np.uint8)
        try:
            result = apply_alpha_blend(None, overlay, 0, 0)
        except (TypeError, AttributeError):
            pass  # None 입력 시 예외 허용


class TestLoadSystemFont:
    """시스템 폰트 로드 테스트"""

    def test_default_font(self):
        from core.utils import load_system_font
        font = load_system_font(12)
        assert font is not None

    def test_custom_size(self):
        from core.utils import load_system_font
        font = load_system_font(24)
        assert font is not None

    def test_nonexistent_preferred_font(self):
        from core.utils import load_system_font
        font = load_system_font(12, ["/nonexistent/font.ttf"])
        assert font is not None


class TestSafeDeleteTimer:
    """타이머 안전 삭제 테스트"""

    def test_none_timer(self):
        from core.utils import safe_delete_timer
        safe_delete_timer(None)  # 크래시 안 해야 함

    def test_invalid_timer(self):
        from core.utils import safe_delete_timer
        safe_delete_timer("invalid")  # 크래시 안 해야 함
