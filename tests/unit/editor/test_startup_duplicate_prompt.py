import ast
import json
from pathlib import Path


SOURCE_PATH = Path("editor/ui/editor_main_window_wx.py")


def _module() -> ast.Module:
    return ast.parse(SOURCE_PATH.read_text(encoding="utf-8"))


def _main_window() -> ast.ClassDef:
    return next(node for node in _module().body if isinstance(node, ast.ClassDef) and node.name == "MainWindow")


def _function(name: str) -> ast.FunctionDef:
    return next(node for node in _main_window().body if isinstance(node, ast.FunctionDef) and node.name == name)


def _source(name: str) -> str:
    return ast.get_source_segment(SOURCE_PATH.read_text(encoding="utf-8"), _function(name)) or ""


def test_startup_duplicate_prompt_is_initialized_once_per_editor_window():
    init_source = _source("__init__")

    assert "self._startup_duplicate_prompt_pending = True" in init_source


def test_startup_duplicate_prompt_is_queued_after_supported_file_loads():
    open_file_source = _source("open_file")
    video_finished_source = _source("_on_video_load_finished")

    assert "self._refresh_all()" in open_file_source
    assert "self._maybe_offer_startup_duplicate_removal()" in open_file_source
    assert open_file_source.index("self._refresh_all()") < open_file_source.index(
        "self._maybe_offer_startup_duplicate_removal()"
    )

    assert "wx.MessageBox" in video_finished_source
    assert "self._maybe_offer_startup_duplicate_removal()" in video_finished_source
    assert video_finished_source.index("wx.MessageBox") < video_finished_source.index(
        "self._maybe_offer_startup_duplicate_removal()"
    )


def test_startup_duplicate_prompt_is_one_shot_and_reuses_existing_action():
    maybe_source = _source("_maybe_offer_startup_duplicate_removal")
    prompt_source = _source("_show_startup_duplicate_removal_prompt")

    assert "if not self._startup_duplicate_prompt_pending" in maybe_source
    assert "self._startup_duplicate_prompt_pending = False" in maybe_source
    assert "wx.CallAfter(self._show_startup_duplicate_removal_prompt)" in maybe_source
    assert "dlg.ShowModal() == wx.ID_YES" in prompt_source
    assert "self._remove_duplicates()" in prompt_source


def test_duplicate_removal_noop_does_not_mark_file_modified():
    remove_source = _source("_remove_duplicates")

    assert "new_frames.remove_duplicates()" in remove_source
    assert "if removed <= 0:" in remove_source
    assert "return 0" in remove_source
    assert "if removed > 0:\n                    self._is_modified = True" in remove_source
    assert remove_source.index("return 0") < remove_source.rindex("self._is_modified = True")


def test_startup_duplicate_prompt_locale_keys_exist():
    for locale_path in [Path("resources/i18n/en.json"), Path("resources/i18n/ko.json")]:
        editor_locale = json.loads(locale_path.read_text(encoding="utf-8"))["editor"]
        for key in [
            "startup_duplicate_prompt_title",
            "startup_duplicate_prompt_message",
            "startup_duplicate_prompt_yes",
            "startup_duplicate_prompt_no",
            "msg_duplicate_none",
        ]:
            assert editor_locale[key]
