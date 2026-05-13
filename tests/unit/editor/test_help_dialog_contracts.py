import ast
from pathlib import Path

from tests._ast_helpers import find_class, find_function, parse_module


def test_editor_about_uses_custom_dialog_not_native_about_box():
    source = Path("editor/ui/editor_main_window_wx.py").read_text(encoding="utf-8")
    main_window = find_class(parse_module("editor/ui/editor_main_window_wx.py"), "MainWindow")
    about = find_function(main_window, "_show_about_dialog")
    about_source = ast.get_source_segment(source, about)

    assert "AboutDialog" in about_source
    assert "wx.adv.AboutBox" not in about_source
    assert "AboutDialogInfo" not in about_source


def test_editor_help_exposes_current_product_metadata():
    help_source = Path("editor/ui/dialogs/help_dialog_wx.py").read_text(encoding="utf-8")

    assert "class AboutDialog" in help_source
    assert "APP_DEVELOPER" in help_source
    assert "APP_LAST_MODIFIED" in help_source
    assert "EDITOR_VERSION" in help_source
    assert "접힘 영역 텍스트 겹침" not in help_source


def test_version_metadata_is_current_release_identity():
    from core.version import APP_DEVELOPER, APP_LAST_MODIFIED, APP_VERSION, EDITOR_VERSION

    assert APP_VERSION == "2.1.0"
    assert EDITOR_VERSION == "2.1.0"
    assert APP_DEVELOPER == "CoreVFX 서승욱"
    assert APP_LAST_MODIFIED == "2026-05-13"
