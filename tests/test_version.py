"""
버전 정보 테스트
"""

import re
import tomllib
from pathlib import Path


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

    def test_app_editor_and_packaging_versions_match(self):
        from core.version import APP_VERSION, EDITOR_VERSION

        pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

        assert APP_VERSION == EDITOR_VERSION
        assert pyproject["project"]["version"] == APP_VERSION
        assert re.fullmatch(r"\d+\.\d+\.\d+", APP_VERSION)

    def test_generated_windows_version_resource_matches_app_version(self, tmp_path, monkeypatch):
        import build_optimized
        from core.version import APP_VERSION

        monkeypatch.setattr(build_optimized, "PROJECT_DIR", str(tmp_path))
        version_file = build_optimized.create_version_file()
        version_info = Path(version_file).read_text(encoding="utf-8")
        version_tuple = tuple(int(part) for part in APP_VERSION.split(".")) + (0,)

        assert f"filevers={version_tuple}" in version_info
        assert f"prodvers={version_tuple}" in version_info
        assert f"StringStruct('FileVersion', '{APP_VERSION}')" in version_info
        assert f"StringStruct('ProductVersion', '{APP_VERSION}')" in version_info


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
