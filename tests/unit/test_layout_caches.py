"""AST 회귀 테스트 — 인라인 툴바/다이얼로그/타이틀바 캐시.

wx 없이 정적 계약만 검증. 캐시 누락이 다시 들어오면 즉시 실패한다.
"""
import ast

from tests._ast_helpers import find_class, find_function, function_source, read_module


# --- base_toolbar_wx: _calculate_wrapped_height 캐시 ---


def test_base_toolbar_caches_wrapped_height():
    source, module = read_module("editor/ui/inline_toolbars/base_toolbar_wx.py")
    base = find_class(module, "InlineToolbarBase")
    init = function_source(source, find_function(base, "__init__"))
    calc = function_source(source, find_function(base, "_calculate_wrapped_height"))

    assert "_wrapped_height_cache" in init, "InlineToolbarBase.__init__ 가 캐시 dict를 초기화하지 않음"
    assert "self._wrapped_height_cache.get(client_width)" in calc, \
        "_calculate_wrapped_height 가 캐시 조회를 누락"
    assert "self._wrapped_height_cache[client_width] = result" in calc, \
        "_calculate_wrapped_height 가 결과를 캐시에 저장하지 않음"


def test_base_toolbar_invalidates_cache_on_add_methods():
    source, module = read_module("editor/ui/inline_toolbars/base_toolbar_wx.py")
    base = find_class(module, "InlineToolbarBase")
    method_names = {n.name for n in base.body if isinstance(n, ast.FunctionDef)}
    assert "_invalidate_wrapped_height_cache" in method_names, \
        "InlineToolbarBase 에 _invalidate_wrapped_height_cache 메서드가 없음"

    for method in ("add_control", "add_icon_label", "add_label", "add_separator"):
        body = function_source(source, find_function(base, method))
        assert "_invalidate_wrapped_height_cache" in body, \
            f"{method} 가 캐시를 무효화하지 않음 (자식 추가 후 stale 캐시 위험)"


# --- help_dialog_wx: page-별 라벨 인덱스 + last_wrap_width ---


def test_help_dialog_uses_per_page_index_and_last_width():
    source, module = read_module("editor/ui/dialogs/help_dialog_wx.py")
    cls = find_class(module, "HelpDialog")
    init = function_source(source, find_function(cls, "__init__"))
    wrap_visible = function_source(source, find_function(cls, "_wrap_visible_labels"))
    wrap_all = function_source(source, find_function(cls, "_wrap_all_labels"))

    assert "_page_wrap_labels" in init, "HelpDialog 가 page-별 라벨 dict 를 초기화하지 않음"
    assert "_last_wrap_widths" in init, "HelpDialog 가 last_wrap_width 캐시를 초기화하지 않음"

    # 부모 체인 워크는 page-별 dict 로 대체되어야 함
    assert "_is_descendant_of" not in wrap_visible, \
        "_wrap_visible_labels 가 여전히 _is_descendant_of 부모 체인을 워크함 (O(L·D))"
    assert "_page_wrap_labels" in wrap_visible, \
        "_wrap_visible_labels 가 page-별 라벨 인덱스를 사용하지 않음"
    assert "_last_wrap_widths" in wrap_visible, \
        "_wrap_visible_labels 가 last_width 가드를 누락"

    assert "_last_wrap_widths" in wrap_all, "_wrap_all_labels 가 last_width 가드를 누락"


def test_help_dialog_drops_descendant_walk_helper():
    """더 이상 사용되지 않는 _is_descendant_of 헬퍼는 제거되어야 한다."""
    _source, module = read_module("editor/ui/dialogs/help_dialog_wx.py")
    cls = find_class(module, "HelpDialog")
    method_names = {n.name for n in cls.body if isinstance(n, ast.FunctionDef)}
    assert "_is_descendant_of" not in method_names, \
        "_is_descendant_of 가 남아 있음 — 캐시 도입 후 dead code"


# --- window_chrome.apply_dark_title_bar 멱등성 ---


def test_apply_dark_title_bar_is_idempotent():
    source, module = read_module("ui/window_chrome.py")
    func = next(n for n in module.body if isinstance(n, ast.FunctionDef) and n.name == "apply_dark_title_bar")
    body = function_source(source, func)

    # 시그니처 캐시 attribute 가 있어야 한다
    assert "_APPLIED_ATTR" in source, "window_chrome 이 멱등성 시그니처 키를 정의하지 않음"
    # 호출 시 시그니처 비교로 조기 반환
    assert "getattr(window, _APPLIED_ATTR" in body, \
        "apply_dark_title_bar 가 사전 시그니처 체크 없이 ctypes 호출"
    assert "setattr(window, _APPLIED_ATTR" in body, \
        "apply_dark_title_bar 가 적용 후 시그니처를 저장하지 않음"
