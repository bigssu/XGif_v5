import ast
from pathlib import Path

import pytest

from tests._ast_helpers import (
    find_class,
    find_function,
    find_module_function,
    read_module,
)


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
    dropdown_font = find_function(popup, "_dropdown_font")
    row_height_source = ast.get_source_segment(source, row_height)
    dropdown_font_source = ast.get_source_segment(source, dropdown_font)

    assert "ClientToScreen((0, self._owner.GetClientSize().height))" in popup_below_source
    assert "self.Move(origin)" in popup_below_source
    assert "self.Position(" not in popup_below_source
    assert "width = max(70, owner_size.width)" in popup_size_source
    assert "_DROPDOWN_MAX_VISIBLE_ITEMS" in popup_size_source
    assert "_DROPDOWN_MIN_ROW_HEIGHT" in row_height_source
    assert "self._list.GetTextExtent" in row_height_source
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
