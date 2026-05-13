import ast
from pathlib import Path


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    return next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == name)


def _function(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name)


def test_dark_select_uses_menu_owned_ids_for_popup_items():
    source = Path("ui/dark_controls.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    show_menu = _function(_class(module, "DarkSelect"), "_show_menu")
    menu_source = ast.get_source_segment(source, show_menu)

    assert "wx.NewIdRef" not in menu_source
    assert "menu.Append(wx.ID_ANY" in menu_source


def test_property_bar_syncs_height_from_wrapped_toolbar():
    source = Path("editor/ui/property_bar_wx.py").read_text(encoding="utf-8")
    module = ast.parse(source)
    property_bar = _class(module, "PropertyBar")
    method_names = {node.name for node in property_bar.body if isinstance(node, ast.FunctionDef)}
    show_toolbar = _function(property_bar, "show_toolbar")
    show_source = ast.get_source_segment(source, show_toolbar)

    assert "sync_active_toolbar_height" in method_names
    assert "self.sync_active_toolbar_height()" in show_source
