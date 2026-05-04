import ast
from pathlib import Path


def test_speed_toolbar_cancel_restores_before_finishing_cancel():
    tree = ast.parse(Path("editor/ui/inline_toolbars/speed_toolbar_wx.py").read_text(encoding="utf-8"))
    speed_toolbar = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "SpeedToolbar")
    on_cancel = next(node for node in speed_toolbar.body if isinstance(node, ast.FunctionDef) and node.name == "_on_cancel")

    calls = [
        stmt.value.func.attr
        for stmt in on_cancel.body
        if isinstance(stmt, ast.Expr)
        and isinstance(stmt.value, ast.Call)
        and isinstance(stmt.value.func, ast.Attribute)
    ]

    assert calls == ["reset_to_default", "_finish_cancel"]
