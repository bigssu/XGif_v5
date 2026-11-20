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
    from datetime import date
    from core.version import APP_DEVELOPER, APP_LAST_MODIFIED, APP_VERSION, EDITOR_VERSION

    assert EDITOR_VERSION == APP_VERSION
    assert APP_DEVELOPER == "CoreVFX 서승욱"
    assert date.fromisoformat(APP_LAST_MODIFIED)

def test_editor_help_lists_only_bound_shortcuts_in_both_languages():
    import wx
    from editor.ui.dialogs.help_dialog_wx import HelpDialog
    from ui.i18n import get_trans_manager

    app = wx.GetApp() or wx.App(False)
    manager = get_trans_manager()
    before = manager.current_lang
    try:
        for lang, save_as in [('en', 'Save as'), ('ko', '다른 이름으로 저장')]:
            manager.set_language(lang)
            dialog = HelpDialog()
            try:
                notebook = next(child for child in dialog.GetChildren() if isinstance(child, wx.Notebook))
                page = notebook.GetPage(2)
                labels = [label.GetLabel() for label, _ in dialog._page_wrap_labels[page]]
                keys = [text.split()[0] for text in labels]
                assert keys == ['Ctrl+O', 'Ctrl+S', 'Ctrl+Shift+S', 'Space', 'Left/Right',
                                'Ctrl+D', 'Ctrl+A', 'Delete']
                assert save_as in labels[2]
            finally:
                dialog.Destroy()
                app.Yield()
    finally:
        manager.set_language(before)
