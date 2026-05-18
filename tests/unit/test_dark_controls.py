import ast
from pathlib import Path

import pytest
import wx

from tests._ast_helpers import (
    find_class,
    find_function,
    find_module_function,
    read_module,
)


_WX_APP = None


def _ensure_wx_app():
    global _WX_APP
    app = wx.App.Get()
    if app is None:
        _WX_APP = wx.App(False)
        app = _WX_APP
    return app


def test_dark_select_uses_fixed_width_popup_instead_of_native_menu():
    source, module = read_module("ui/dark_controls.py")
    show_menu = find_function(find_class(module, "DarkSelect"), "_show_menu")
    menu_source = ast.get_source_segment(source, show_menu)

    assert "wx.NewIdRef" not in menu_source
    assert "wx.Menu" not in menu_source
    assert "PopupMenu" not in menu_source
    assert "_DarkSelectPopup(self)" in menu_source
    assert "self._popup.popup_below_owner()" in menu_source
    assert "self._popup.dismiss_from_owner()" in menu_source
    assert "return" in menu_source


def test_dark_select_popup_is_left_aligned_below_control():
    source, module = read_module("ui/dark_controls.py")
    popup = find_class(module, "_DarkSelectPopup")
    popup_below = find_function(popup, "popup_below_owner")
    popup_size = find_function(popup, "_popup_size")
    popup_below_source = ast.get_source_segment(source, popup_below)
    popup_size_source = ast.get_source_segment(source, popup_size)
    row_height = find_function(popup, "_row_height")
    native_row_height = find_function(popup, "_native_row_height")
    best_size_row_height = find_function(popup, "_best_size_row_height")
    fallback_min_row_height = find_function(popup, "_fallback_min_row_height")
    dropdown_font = find_function(popup, "_dropdown_font")
    row_height_source = ast.get_source_segment(source, row_height)
    native_row_height_source = ast.get_source_segment(source, native_row_height)
    best_size_row_height_source = ast.get_source_segment(source, best_size_row_height)
    fallback_min_row_height_source = ast.get_source_segment(source, fallback_min_row_height)
    dropdown_font_source = ast.get_source_segment(source, dropdown_font)

    assert "ClientToScreen((0, self._owner.GetClientSize().height))" in popup_below_source
    assert "self.Move(origin)" in popup_below_source
    assert "self.Position(" not in popup_below_source
    assert "width = max(70, owner_size.width)" in popup_size_source
    assert "_DROPDOWN_MAX_VISIBLE_ITEMS" in popup_size_source
    assert "+ 2" not in popup_size_source
    assert "fallback_min_height = self._fallback_min_row_height()" in row_height_source
    assert "native_height = self._native_row_height()" in row_height_source
    assert "return max(fallback_min_height, native_height)" in row_height_source
    assert "best_height = self._best_size_row_height()" in row_height_source
    assert "return max(fallback_min_height, best_height)" in row_height_source
    assert "_fallback_min_row_height()" in row_height_source
    assert "_MSW_LB_GETITEMHEIGHT" in native_row_height_source
    assert "ctypes.windll.user32.SendMessageW" in native_row_height_source
    assert "self._list.GetBestSize().height" in best_size_row_height_source
    assert "_DROPDOWN_MIN_ROW_HEIGHT" in fallback_min_row_height_source
    assert "self._list.GetTextExtent" in fallback_min_row_height_source
    assert "_DROPDOWN_FONT_SIZE" in dropdown_font_source
    assert "Fonts.get_font(size)" in dropdown_font_source


def test_dark_select_popup_commits_mouse_clicks_explicitly():
    source, module = read_module("ui/dark_controls.py")
    popup = find_class(module, "_DarkSelectPopup")
    left_up = find_function(popup, "_on_list_left_up")
    hit_test = find_function(popup, "_index_from_mouse_event")
    left_up_source = ast.get_source_segment(source, left_up)
    hit_test_source = ast.get_source_segment(source, hit_test)

    assert "wx.CallAfter(self._commit, index)" in left_up_source
    assert "self._list.SetSelection(index)" in left_up_source
    assert "HitTest" in hit_test_source
    assert "event.GetY()" in hit_test_source


def test_dark_spin_ctrl_edits_inline_without_text_entry_dialog():
    source, module = read_module("ui/dark_controls.py")
    spin = find_class(module, "DarkSpinCtrl")
    spin_source = ast.get_source_segment(source, spin)
    left_up = find_function(spin, "_on_left_up")
    begin_edit = find_function(spin, "_begin_inline_edit")
    end_edit = find_function(spin, "_end_inline_edit")
    editor_text = find_function(spin, "_on_editor_text")
    get_value = find_function(spin, "GetValue")
    left_up_source = ast.get_source_segment(source, left_up)
    begin_edit_source = ast.get_source_segment(source, begin_edit)
    end_edit_source = ast.get_source_segment(source, end_edit)
    editor_text_source = ast.get_source_segment(source, editor_text)
    get_value_source = ast.get_source_segment(source, get_value)

    assert "wx.TextEntryDialog" not in spin_source
    assert "_begin_inline_edit()" in left_up_source
    assert "wx.TextCtrl(" in begin_edit_source
    assert "wx.TE_PROCESS_ENTER" in begin_edit_source
    assert "wx.EVT_TEXT" in begin_edit_source
    assert "wx.EVT_KILL_FOCUS" in begin_edit_source
    assert "event.StopPropagation()" in editor_text_source
    assert "event.Skip()" not in editor_text_source
    assert "_destroy_window_later(editor)" in end_edit_source
    assert "_emit_change()" in end_edit_source
    assert "_end_inline_edit(commit=True)" not in get_value_source


def test_dark_select_edits_inline_without_text_entry_dialog():
    source, module = read_module("ui/dark_controls.py")
    select = find_class(module, "DarkSelect")
    select_source = ast.get_source_segment(source, select)
    left_up = find_function(select, "_on_left_up")
    begin_edit = find_function(select, "_begin_inline_edit")
    end_edit = find_function(select, "_end_inline_edit")
    editor_text = find_function(select, "_on_editor_text")
    get_value = find_function(select, "GetValue")
    left_up_source = ast.get_source_segment(source, left_up)
    begin_edit_source = ast.get_source_segment(source, begin_edit)
    end_edit_source = ast.get_source_segment(source, end_edit)
    editor_text_source = ast.get_source_segment(source, editor_text)
    get_value_source = ast.get_source_segment(source, get_value)

    assert "wx.TextEntryDialog" not in select_source
    assert "_begin_inline_edit()" in left_up_source
    assert "wx.TextCtrl(" in begin_edit_source
    assert "wx.TE_PROCESS_ENTER" in begin_edit_source
    assert "wx.EVT_TEXT" in begin_edit_source
    assert "wx.EVT_KILL_FOCUS" in begin_edit_source
    assert "event.StopPropagation()" in editor_text_source
    assert "event.Skip()" not in editor_text_source
    assert "_destroy_window_later(editor)" in end_edit_source
    assert "wx.wxEVT_COMBOBOX" in end_edit_source
    assert "_end_inline_edit(commit=True)" not in get_value_source


def test_dark_inline_editors_defer_destroy_and_do_not_double_commit_enter():
    source, module = read_module("ui/dark_controls.py")
    assert "window.DestroyLater()" in source
    current_editor_event = find_module_function(module, "_event_belongs_to_editor")
    current_editor_event_source = ast.get_source_segment(source, current_editor_event)
    assert "event.GetEventObject() is editor" in current_editor_event_source

    for class_name in ("DarkSelect", "DarkSpinCtrl"):
        cls = find_class(module, class_name)
        begin_edit = find_function(cls, "_begin_inline_edit")
        end_edit = find_function(cls, "_end_inline_edit")
        editor_key = find_function(cls, "_on_editor_key")
        editor_enter = find_function(cls, "_on_editor_enter")
        editor_focus = find_function(cls, "_on_editor_kill_focus")
        destroy_handler = find_function(cls, "_on_destroy")
        begin_source = ast.get_source_segment(source, begin_edit)
        end_source = ast.get_source_segment(source, end_edit)
        key_source = ast.get_source_segment(source, editor_key)
        enter_source = ast.get_source_segment(source, editor_enter)
        focus_source = ast.get_source_segment(source, editor_focus)
        destroy_source = ast.get_source_segment(source, destroy_handler)

        assert "wx.EVT_TEXT_ENTER, self._on_editor_enter" in begin_source
        assert "lambda _event: self._end_inline_edit" not in begin_source
        assert "editor.Unbind" not in source
        assert "_destroy_window_later(editor)" in end_source
        assert "editor.Destroy()" not in end_source
        assert "_event_belongs_to_editor(event, self._editor)" in enter_source
        assert "_event_belongs_to_editor(event, self._editor)" in focus_source
        assert "_event_belongs_to_editor(event, self._editor)" in key_source
        assert "WXK_RETURN" not in key_source
        assert "_discard_inline_editor_for_destroy()" in destroy_source


def test_dark_select_popup_row_height_clamps_native_and_best_size_fallbacks():
    _ensure_wx_app()
    from ui.dark_controls import DarkSelect, _DarkSelectPopup

    frame = wx.Frame(None)
    try:
        combo = DarkSelect(frame, choices=[str(i) for i in range(40)], size=(80, -1), style=wx.CB_READONLY)
        popup = _DarkSelectPopup(combo)
        try:
            fallback_min = popup._fallback_min_row_height()

            popup._native_row_height = lambda: 1
            assert popup._row_height() == fallback_min

            popup._native_row_height = lambda: 0
            assert popup._best_size_row_height() < fallback_min
            assert popup._row_height() == fallback_min
        finally:
            popup.Destroy()
    finally:
        frame.Destroy()


def test_dark_select_runtime_inline_editor_event_contract():
    _ensure_wx_app()
    from ui.dark_controls import DarkSelect

    frame = wx.Frame(None)
    try:
        combo = DarkSelect(frame, choices=["640x480", "800x600"], value="640x480", style=wx.CB_DROPDOWN)
        combo.SetSize((108, 26))

        text_enter_events = []
        combo_events = []
        combo.Bind(
            wx.EVT_TEXT_ENTER,
            lambda event: text_enter_events.append((event.GetEventObject(), event.GetId(), event.GetString())),
        )
        combo.Bind(
            wx.EVT_COMBOBOX,
            lambda event: combo_events.append((event.GetEventObject(), event.GetId(), event.GetString())),
        )

        combo._begin_inline_edit()
        assert isinstance(combo._editor, wx.TextCtrl)

        combo._editor.SetValue("1024x768")
        wx.YieldIfNeeded()
        assert combo.GetValue() == "1024x768"
        assert combo._editor is not None
        assert text_enter_events == []
        assert combo_events == []

        combo._end_inline_edit(commit=True)
        wx.YieldIfNeeded()
        assert combo._editor is None
        assert combo.GetValue() == "1024x768"
        assert combo.GetSelection() == wx.NOT_FOUND
        assert text_enter_events == [(combo, combo.GetId(), "1024x768")]
        assert combo_events == [(combo, combo.GetId(), "1024x768")]
    finally:
        frame.Destroy()


def test_dark_spin_ctrl_runtime_inline_editor_event_contract():
    _ensure_wx_app()
    from ui.dark_controls import DarkSpinCtrlDouble

    frame = wx.Frame(None)
    try:
        spin = DarkSpinCtrlDouble(frame, value="0.20", min=0.01, max=10.0, initial=0.2, inc=0.01)
        spin.SetDigits(2)
        spin.SetSize((70, 26))

        text_events = []
        spin_events = []
        spin.Bind(
            wx.EVT_TEXT,
            lambda event: text_events.append((event.GetEventObject(), event.GetId(), event.GetString(), spin.GetValue())),
        )
        spin.Bind(
            wx.EVT_SPINCTRLDOUBLE,
            lambda event: spin_events.append((event.GetEventObject(), event.GetId(), event.GetString())),
        )

        spin._begin_inline_edit()
        assert isinstance(spin._editor, wx.TextCtrl)

        spin._editor.SetValue("0.30")
        wx.YieldIfNeeded()
        assert spin.GetValue() == pytest.approx(0.3)
        assert spin._editor is not None
        assert text_events == []
        assert spin_events == []

        spin._end_inline_edit(commit=True)
        wx.YieldIfNeeded()
        assert spin._editor is None
        assert spin.GetValue() == pytest.approx(0.3)
        assert text_events == [(spin, spin.GetId(), "0.30", pytest.approx(0.3))]
        assert spin_events == [(spin, spin.GetId(), "0.30")]
    finally:
        frame.Destroy()


def test_dark_spin_ctrl_kill_focus_commits_without_synchronous_destroy():
    _ensure_wx_app()
    from ui.dark_controls import DarkSpinCtrlDouble

    class FakeFocusEvent:
        def __init__(self, event_object):
            self._event_object = event_object
            self.skipped = False

        def GetEventObject(self):
            return self._event_object

        def Skip(self):
            self.skipped = True

    frame = wx.Frame(None)
    try:
        spin = DarkSpinCtrlDouble(frame, value="0.20", min=0.01, max=10.0, initial=0.2, inc=0.01)
        spin.SetDigits(2)
        spin.SetSize((70, 26))
        spin_events = []
        spin.Bind(wx.EVT_SPINCTRLDOUBLE, lambda event: spin_events.append(event.GetString()))

        spin._begin_inline_edit()
        editor = spin._editor
        editor.SetValue("0.06")
        event = FakeFocusEvent(editor)
        spin._on_editor_kill_focus(event)

        assert event.skipped is True
        assert spin._editor is None
        assert spin.GetValue() == pytest.approx(0.06)
        assert spin_events == ["0.06"]
        assert editor is not None
        wx.YieldIfNeeded()
    finally:
        frame.Destroy()


def test_dark_spin_ctrl_accepts_leading_decimal_inline_input():
    _ensure_wx_app()
    from ui.dark_controls import DarkSpinCtrlDouble

    class FakeFocusEvent:
        def __init__(self, event_object):
            self._event_object = event_object

        def GetEventObject(self):
            return self._event_object

        def Skip(self):
            pass

    frame = wx.Frame(None)
    try:
        spin = DarkSpinCtrlDouble(frame, value="0.20", min=0.01, max=10.0, initial=0.2, inc=0.01)
        spin.SetDigits(2)
        spin.SetSize((70, 26))
        spin_events = []
        spin.Bind(wx.EVT_SPINCTRLDOUBLE, lambda event: spin_events.append(event.GetString()))

        spin._begin_inline_edit()
        editor = spin._editor
        editor.SetValue(".1")
        spin._on_editor_kill_focus(FakeFocusEvent(editor))

        assert spin._editor is None
        assert spin.GetValue() == pytest.approx(0.1)
        assert spin_events == ["0.10"]
        wx.YieldIfNeeded()
    finally:
        frame.Destroy()


def test_dark_spin_ctrl_ignores_retired_editor_events_after_close():
    _ensure_wx_app()
    from ui.dark_controls import DarkSpinCtrlDouble

    class FakeEnterEvent:
        def __init__(self, event_object):
            self._event_object = event_object

        def GetEventObject(self):
            return self._event_object

    frame = wx.Frame(None)
    try:
        spin = DarkSpinCtrlDouble(frame, value="0.20", min=0.01, max=10.0, initial=0.2, inc=0.01)
        spin.SetDigits(2)
        spin.SetSize((70, 26))

        spin._begin_inline_edit()
        editor = spin._editor
        editor.SetValue("0.12")
        spin._end_inline_edit(commit=True)
        spin._on_editor_enter(FakeEnterEvent(editor))

        assert spin._editor is None
        assert spin.GetValue() == pytest.approx(0.12)
        wx.YieldIfNeeded()
    finally:
        frame.Destroy()


def test_property_bar_syncs_height_from_wrapped_toolbar():
    source, module = read_module("editor/ui/property_bar_wx.py")
    property_bar = find_class(module, "PropertyBar")
    method_names = {node.name for node in property_bar.body if isinstance(node, ast.FunctionDef)}
    show_toolbar = find_function(property_bar, "show_toolbar")
    show_source = ast.get_source_segment(source, show_toolbar)

    assert "sync_active_toolbar_height" in method_names
    assert "self.sync_active_toolbar_height()" in show_source


# --- 2.1.2 LSP / 캐시 / 헬퍼 회귀 ---


@pytest.mark.parametrize("class_name", ["DarkSelect", "DarkSpinCtrl"])
@pytest.mark.parametrize("setter", ["SetBackgroundColour", "SetForegroundColour", "SetBorderColour"])
def test_color_setters_mutate_instance_state(class_name, setter):
    """LSP: 색상 setter 는 인스턴스 필드를 갱신하고 페인트 캐시를 무효화해야 한다.

    DarkSpinCtrl 의 이전 구현은 인자를 무시(`_colour`)하여 silent no-op 였음.
    """
    source, module = read_module("ui/dark_controls.py")
    target = find_function(find_class(module, class_name), setter)
    body_source = ast.get_source_segment(source, target)

    # 파라미터 이름이 underscore-only 면 그 인자는 의도적으로 버려진 것 — LSP 위반의 신호
    arg_name = target.args.args[1].arg  # self 다음 인자
    assert not arg_name.startswith("_"), f"{class_name}.{setter} 가 인자({arg_name!r}) 를 받지 않고 폐기"

    # 색상 인스턴스 필드 중 하나는 반드시 할당되어야 한다
    assert "self._bg" in body_source or "self._fg" in body_source or "self._border" in body_source, \
        f"{class_name}.{setter} 가 색상 인스턴스 필드를 갱신하지 않음"

    # 캐시 무효화가 필수
    assert "self._cached_bmp = None" in body_source, \
        f"{class_name}.{setter} 가 페인트 캐시를 무효화하지 않음"


@pytest.mark.parametrize("class_name", ["DarkSelect", "DarkSpinCtrl"])
def test_paint_caches_bitmap_by_state(class_name):
    """페인트 비트맵은 state_key 캐시를 사용해야 한다 (FlatButton 패턴 일관)."""
    source, module = read_module("ui/dark_controls.py")
    on_paint = find_function(find_class(module, class_name), "_on_paint")
    body = ast.get_source_segment(source, on_paint)

    assert "state_key" in body, f"{class_name}._on_paint 가 state_key 캐시 키를 만들지 않음"
    assert "self._cached_bmp" in body and "self._cached_state" in body, \
        f"{class_name}._on_paint 가 인스턴스 캐시 필드를 사용하지 않음"
    assert "self._cached_state == state_key" in body, \
        f"{class_name}._on_paint 의 캐시 hit 조건이 누락"


def test_enable_msw_dark_mode_helper_exists():
    """msw.dark-mode 매직 넘버는 헬퍼로만 노출되어야 한다."""
    source, module = read_module("ui/dark_controls.py")
    helper = find_module_function(module, "enable_msw_dark_mode")
    helper_source = ast.get_source_segment(source, helper)

    assert "_MSW_DARK_MODE_VALUE" in source, "헬퍼가 매직 넘버를 모듈 상수로 캡슐화하지 않음"
    assert "msw.dark-mode" in helper_source, "헬퍼가 실제 wx 옵션 키를 사용하지 않음"
    assert "win32" in helper_source, "헬퍼가 플랫폼 가드를 누락"


@pytest.mark.parametrize("entry_point", ["main.py", "editor/__main__.py"])
def test_entry_points_use_dark_mode_helper(entry_point):
    """진입점은 헬퍼 호출만 하고 msw.dark-mode 매직 넘버를 직접 쓰지 않아야 한다."""
    source = Path(entry_point).read_text(encoding="utf-8")
    assert "enable_msw_dark_mode" in source, f"{entry_point} 가 헬퍼를 호출하지 않음"
    # 매직 넘버 직접 호출은 헬퍼 한 곳으로 모이지 않으면 DRY 위반
    assert 'SetOption("msw.dark-mode"' not in source, \
        f"{entry_point} 가 wx.SystemOptions 매직 넘버를 직접 호출"
