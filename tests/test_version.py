"""
버전 정보 테스트
"""



class TestVersion:
    """버전 모듈 테스트"""

    def test_app_name(self):
        from core.version import APP_NAME
        assert APP_NAME == "XGif"

    def test_app_version_format(self):
        from core.version import APP_VERSION
        assert isinstance(APP_VERSION, str)
        assert len(APP_VERSION) > 0
        # 숫자와 점으로 구성
        for ch in APP_VERSION:
            assert ch.isdigit() or ch == '.', f"잘못된 버전 문자: {ch}"

    def test_editor_version_format(self):
        from core.version import EDITOR_VERSION
        assert isinstance(EDITOR_VERSION, str)
        assert len(EDITOR_VERSION) > 0

    def test_version_not_empty(self):
        from core.version import APP_VERSION, EDITOR_VERSION
        assert APP_VERSION.strip() != ""
        assert EDITOR_VERSION.strip() != ""


class TestResourcePath:
    """리소스 경로 테스트"""

    def test_get_resource_path(self):
        from core.utils import get_resource_path
        path = get_resource_path('resources')
        assert path is not None
        assert len(path) > 0

    def test_resource_path_absolute(self):
        import os
        from core.utils import get_resource_path
        path = get_resource_path('resources/xgif_icon.ico')
        assert os.path.isabs(path)

    def test_icon_file_exists(self):
        import os
        from core.utils import get_resource_path
        ico_path = get_resource_path('resources/xgif_icon.ico')
        png_path = get_resource_path('resources/Xgif_icon.png')
        assert os.path.exists(ico_path) or os.path.exists(png_path)
