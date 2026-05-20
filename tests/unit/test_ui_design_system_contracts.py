from pathlib import Path
import ast
import re
import json

import wx


_WX_APP = None


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def _ensure_wx_app():
    global _WX_APP
    app = wx.App.Get()
    if app is None:
        _WX_APP = wx.App(False)
        app = _WX_APP
    return app


def test_recorder_uses_shared_vector_commands_instead_of_symbol_text_icons():
    source = _read("ui/capture_control_bar.py")
    design_system = _read("ui/design_system.py")

    assert "from ui.design_system import CommandButton, RailIcon" in source
    assert 'RailIcon(self, "cursor"' in source
    assert 'RailIcon(self, "region"' in source
    assert "CommandButton(self, label=\"REC\"" in source
    assert "style=wx.CB_DROPDOWN, size=(108, -1)" in source
    assert "SetIconType(\"stop\")" in source
    assert "SetIconType(\"play\")" in source
    assert "SetIconType(\"record\")" in source
    assert "def _sync_min_size_to_content" in design_system
    assert "self._sync_min_size_to_content()" in design_system
    assert "text_w + icon_w + gap + horizontal_padding" in design_system
    assert "root_radius = size * 0.31" in design_system
    assert "tooth_radius = size * 0.42" in design_system
    assert "math.tau * idx / 16" in design_system
    assert "math.tau * idx / 8" not in design_system

    banned_symbol_labels = [
        'label="● REC"',
        'label="■ STOP"',
        'label="▶ REC"',
        'label="❚❚"',
        'label="⚙"',
        'label="↖"',
        'label="⬚"',
    ]
    for pattern in banned_symbol_labels:
        assert pattern not in source


def test_key_dialogs_use_shared_commands_and_responsive_save_layout():
    save_dialog = _read("editor/ui/save_dialog_wx.py")
    settings_dialog = _read("ui/settings_dialog.py")
    dependency_dialogs = _read("ui/dependency_dialogs.py")

    assert "from ui.design_system import CommandButton" in save_dialog
    assert "SetMinSize((900, 550))" not in save_dialog
    assert "SetMaxSize((self.PREVIEW_WIDTH, self.PREVIEW_HEIGHT))" not in save_dialog
    assert "SetMinSize((720, 520))" in save_dialog
    assert "save_dialog_title" in save_dialog
    assert "save_dialog_colors" in save_dialog

    assert "from ui.design_system import CommandButton" in settings_dialog
    assert "HDR 모니터 보정" not in settings_dialog
    assert "hdr_correction_tooltip" in settings_dialog

    assert "ThemedProgressDialog(" in dependency_dialogs
    assert "wx.ProgressDialog(" not in dependency_dialogs


def test_editor_toolbar_has_visible_group_labels_and_i18n_keys():
    toolbar = _read("editor/ui/icon_toolbar_wx.py")
    assert "class ToolbarGroupLabel" in toolbar
    assert "class ToolbarGroupCard" in toolbar
    assert "_create_group_card" in toolbar
    assert "_create_group_button" in toolbar
    assert "root_sizer.Add(self._button_sizer" in toolbar
    assert "root_sizer.Add(self._label" in toolbar
    assert "Colors.BG_CARD" in toolbar
    assert "self._scroll_panel = scroll_panel" in toolbar
    assert "scroll_panel.Bind(wx.EVT_PAINT, self._on_scroll_paint)" in toolbar
    assert "scroll_panel.Bind(wx.EVT_SIZE, self._on_scroll_size)" in toolbar
    assert "dc.Clear()" in toolbar
    assert "toolbar_group_" in toolbar

    for locale_path in ("resources/i18n/ko.json", "resources/i18n/en.json"):
        data = json.loads(_read(locale_path))
        locale = {}
        locale.update(data.get("main", {}))
        locale.update(data.get("editor", {}))
        for key in (
            "toolbar_group_file",
            "toolbar_group_overlay",
            "toolbar_group_edit",
            "toolbar_group_effects",
            "toolbar_group_transform",
            "toolbar_group_playback",
            "hdr_correction",
            "hdr_correction_tooltip",
            "invalid_capture_area",
            "no_frames_to_encode",
            "encoder_not_initialized",
            "save_dialog_quant_desc_adaptive",
            "save_dialog_comparison_summary",
            "save_dialog_preview_failed",
        ):
            assert key in locale


def test_editor_window_is_not_hard_pinned_to_1008x840():
    src = _read("editor/ui/editor_main_window_wx.py")
    # The exact hard-pin pair must be gone:
    assert "self.SetMinSize((1008, 840))" not in src
    assert "self.SetSize((1008, 840))" not in src
    # A real interaction-floor minimum must exist:
    assert "self.SetMinSize((880, 620))" in src
    # Initial size must be screen-clamped via the shared display pattern:
    assert "wx.Display.GetFromWindow(self)" in src
    assert ".GetClientArea()" in src


def test_design_system_exposes_form_section_and_row():
    ds = _read("ui/design_system.py")
    assert "class FormSection" in ds
    assert "class FormRow" in ds


def test_form_section_instantiates_without_error():
    import wx
    from ui.design_system import FormSection
    app = wx.App()
    frame = wx.Frame(None)
    sec = FormSection(frame, "Title", "desc")
    sec.add_row("Label:", wx.TextCtrl(frame))
    assert sec.GetSizer() is not None
    frame.Destroy()
    app.Destroy()


def test_settings_dialog_uses_form_section_not_staticbox():
    src = _read("ui/settings_dialog.py")
    assert "from ui.design_system import" in src and "FormSection" in src
    assert "wx.StaticBox(" not in src
    assert "wx.StaticBoxSizer(" not in src
    assert "SetMinSize((130, -1))" not in src


def test_dead_flatbutton_removed_from_capture_control_bar():
    src = _read("ui/capture_control_bar.py")
    assert "class FlatButton(" not in src


def test_owner_drawn_buttons_click_by_pointer_position_not_stale_hover():
    _ensure_wx_app()
    from ui.design_system import CommandButton
    from editor.ui.icon_toolbar_wx import FlatIconButton

    frame = wx.Frame(None)
    try:
        command = CommandButton(frame, label="Save")
        icon = FlatIconButton("play", "Play", frame)
        for button, hover_attr in ((command, "_hovered"), (icon, "_is_hovered")):
            clicked = []
            button.Bind(wx.EVT_BUTTON, lambda event, sink=clicked: sink.append(event.GetEventObject()))
            setattr(button, hover_attr, False)
            button._pressed = True
            button._is_mouse_over = lambda: True

            button._on_left_up(None)

            assert clicked == [button]
            assert getattr(button, hover_attr) is True
    finally:
        frame.Destroy()


def test_owner_drawn_buttons_recover_from_spurious_leave_events():
    src = _read("ui/design_system.py")
    toolbar = _read("editor/ui/icon_toolbar_wx.py")

    for source, hover_name in ((src, "_hovered"), (toolbar, "_is_hovered")):
        assert "wx.EVT_MOTION" in source
        assert "wx.EVT_MOUSE_CAPTURE_LOST" in source
        assert "def _is_mouse_over" in source
        assert "inside = self._is_mouse_over()" in source
        assert f"and self.{hover_name}" not in source


def test_editor_i18n_common_keys_present_in_both_locales():
    for locale_path in ("resources/i18n/ko.json", "resources/i18n/en.json"):
        data = json.loads(_read(locale_path))
        editor = data.get("editor", {})
        for key in (
            "common_apply", "common_cancel", "common_ok", "common_reset",
            "common_add", "common_error", "common_warning", "common_notice",
            "common_done", "common_width_label", "common_height_label",
            "common_size_label", "target_current_only", "target_selected",
            "target_all", "target_all_short", "target_selected_short",
            "target_current_short", "target_selected_full", "target_all_full",
            "apply_to", "msg_out_of_memory",
            "msg_gif_open_required", "msg_undo_error",
        ):
            assert key in editor, f"{key} missing in {locale_path}"
            assert isinstance(editor[key], str) and editor[key], f"{key} empty/non-str in {locale_path}"


# ---------------------------------------------------------------------------
# A14: Korean-literal static guard — i18n regression lock
# ---------------------------------------------------------------------------
# Detection approach: AST-based (ast.Constant str nodes with Hangul).
# Excludes: docstrings, comment lines, tr(-routed lines, logger calls,
# execute_lambda undo labels, "한" toggle glyph, sentinel "in label" checks,
# class-level data constants (POSITIONS/CENSOR_TYPES), translations else-branch
# fallbacks, _tr()-helper dicts, font-name identifiers, known Korean font names.
# Allowlist: empty — all residuals handled by category heuristics.
# ---------------------------------------------------------------------------

_HANGUL = re.compile(r"[가-힣ᄀ-ᇿ㄰-㆏ꥠ-꥿ힰ-퟿]")

# Latin font names that coexist with Korean aliases in the font picker list.
_LATIN_FONT_NAMES = frozenset({
    "Arial", "Malgun Gothic", "Gulim", "Dotum", "Batang", "NanumGothic",
    "NanumBarunGothic", "Noto Sans KR", "Noto Sans CJK KR", "AppleGothic",
    "Helvetica", "Times New Roman", "Verdana", "Tahoma", "Georgia",
    "Comic Sans MS", "Impact", "Courier New",
})

# Korean names of Windows system fonts — font identifiers, not UI display text.
_KOREAN_FONT_NAMES = frozenset({
    "맑은 고딕", "굴림", "돋움", "바탕", "나눔고딕", "나눔바른고딕",
})

# Allowlist: empty — all known residuals are excluded by category heuristics above.
_KOREAN_GUARD_ALLOWLIST: dict = {}


def _guard_docstring_lines(tree: ast.AST) -> set:
    lines: set = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.body
            and isinstance(node.body[0], ast.Expr)
            and isinstance(node.body[0].value, ast.Constant)
            and isinstance(node.body[0].value.value, str)
        ):
            ds = node.body[0]
            for ln in range(ds.lineno, ds.end_lineno + 1):
                lines.add(ln)
    return lines


def _guard_parent_map(tree: ast.AST) -> dict:
    parent: dict = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node
    return parent


def _guard_in_class_scope(node: ast.Constant, parent_map: dict) -> bool:
    """True if node is in a class-level assignment (not inside a function)."""
    cur = node
    while id(cur) in parent_map:
        p = parent_map[id(cur)]
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return False
        if isinstance(p, ast.ClassDef):
            return True
        cur = p
    return False


def _guard_in_translations_else(node: ast.Constant, parent_map: dict) -> bool:
    """True if node is in the else-branch of an if-translations or if-Module guard."""
    cur = node
    while id(cur) in parent_map:
        p = parent_map[id(cur)]
        if isinstance(p, ast.If) and cur in p.orelse:
            test_src = ast.unparse(p.test) if hasattr(ast, "unparse") else ""
            if "translations" in test_src or isinstance(p.test, ast.Name):
                return True
        cur = p
    return False


def _guard_in_tr_helper_dict(node: ast.Constant, parent_map: dict, src_lines: list) -> bool:
    """True if node is a value in a helper dict whose enclosing function calls tr()."""
    cur = node
    while id(cur) in parent_map:
        p = parent_map[id(cur)]
        if isinstance(p, (ast.FunctionDef, ast.AsyncFunctionDef)):
            func_src = "\n".join(src_lines[p.lineno - 1: p.end_lineno])
            return "tr(" in func_src
        cur = p
    return False


def _guard_is_font_name_context(node: ast.Constant, parent_map: dict) -> bool:
    """True if node is a Korean font name in a list/dict alongside Latin font names."""
    val = node.value
    cur = node
    while id(cur) in parent_map:
        p = parent_map[id(cur)]
        if isinstance(p, ast.List):
            siblings = {
                e.value for e in p.elts
                if isinstance(e, ast.Constant) and isinstance(e.value, str)
            }
            if siblings & _LATIN_FONT_NAMES:
                return True
        if isinstance(p, ast.Dict):
            for k, v in zip(p.keys, p.values):
                if (
                    isinstance(k, ast.Constant) and k.value == val
                    and isinstance(v, ast.Constant) and isinstance(v.value, str)
                    and any(v.value.endswith(ext) for ext in (".ttf", ".ttc", ".otf"))
                ):
                    return True
                if isinstance(k, ast.Constant) and k.value in _LATIN_FONT_NAMES:
                    return True
        cur = p
    return False


def _guard_is_logger(line: str) -> bool:
    return bool(re.search(
        r"\._logger\s*\.|logging\b|\blogger\b|\blog\b\.|self\._log\b|get_logger\(\)",
        line,
    ))


def _collect_korean_offenders(editor_ui: Path) -> list:
    offenders = []
    for fpath in sorted(editor_ui.rglob("*.py")):
        src = fpath.read_text(encoding="utf-8")
        src_lines = src.splitlines()
        try:
            tree = ast.parse(src, filename=str(fpath))
        except SyntaxError:
            continue

        docstring_lines = _guard_docstring_lines(tree)
        parent_map = _guard_parent_map(tree)

        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if not _HANGUL.search(node.value):
                continue

            lineno = node.lineno
            if lineno in docstring_lines:
                continue

            line = src_lines[lineno - 1] if lineno <= len(src_lines) else ""
            if line.lstrip().startswith("#"):
                continue

            # Routed via tr()
            if "tr(" in line:
                continue
            # Language-toggle glyph
            if node.value == "한":
                continue
            # Logger / diagnostic output
            if _guard_is_logger(line):
                continue
            # Undo-history label (execute_lambda)
            if "execute_lambda(" in line:
                continue
            # Sentinel string comparison or raise
            if '" in label' in line or "' in label" in line:
                continue
            if re.search(r"\braise\b", line):
                continue
            # Class-level data constant (POSITIONS, CENSOR_TYPES, …)
            if _guard_in_class_scope(node, parent_map):
                continue
            # translations else-branch fallback / import-guard else-branch
            if _guard_in_translations_else(node, parent_map):
                continue
            # _tr()-helper dict (values routed via tr() inside the same function)
            if _guard_in_tr_helper_dict(node, parent_map, src_lines):
                continue
            # Font-name identifier in list/dict alongside Latin font names
            if _guard_is_font_name_context(node, parent_map):
                continue
            # Known Korean system font names (FindString / font-map lookups)
            if node.value in _KOREAN_FONT_NAMES:
                continue

            path_str = fpath.as_posix()
            key = f"{path_str}::{lineno}"
            if key in _KOREAN_GUARD_ALLOWLIST:
                continue

            offenders.append((path_str, lineno, line.strip()[:120]))

    return offenders


def test_no_pyqt6_signal_pattern_in_inline_toolbars():
    """
    Regression lock: 인라인 툴바는 wxPython 이벤트 바인딩 패턴
    `canvas.Bind(EVT_*_CHANGED, handler)` 만 사용해야 한다.
    PyQt6 잔재인 `canvas.X_changed.connect(...)` / `.disconnect(...)` 패턴은
    wxPython 캔버스에서 그 속성이 존재하지 않아 `hasattr` 가드와 결합되면
    연결이 조용히 건너뛰어지고, 그 결과 기즈모 드래그가 툴바 상태에 전파되지
    못해 효과가 초기 위치에 고정되는 버그를 만든다. (실제로 모자이크 툴바에서
    `_region_x1..y2` 가 중앙값에 고정되는 회귀가 있었다.)
    """
    toolbars_dir = Path("editor/ui/inline_toolbars")
    offenders = []

    for fpath in sorted(toolbars_dir.rglob("*.py")):
        if fpath.name == "__init__.py":
            continue
        src = fpath.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(fpath))
        except SyntaxError:
            continue

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute):
                continue
            if node.func.attr not in ("connect", "disconnect"):
                continue
            outer = node.func.value
            if not isinstance(outer, ast.Attribute):
                continue
            if not outer.attr.endswith("_changed"):
                continue
            base_repr = ast.unparse(outer.value) if hasattr(ast, "unparse") else ""
            if "canvas" not in base_repr.lower():
                continue
            snippet = ast.unparse(node) if hasattr(ast, "unparse") else ""
            offenders.append((fpath.as_posix(), node.lineno, snippet[:140]))

    assert offenders == [], (
        f"\n{len(offenders)} PyQt6-style canvas signal call(s) in inline_toolbars — "
        "use `canvas.Bind(EVT_*_CHANGED, handler)` (wxPython) instead:\n"
        + "\n".join(f"  {p}:{ln}: {snip}" for p, ln, snip in offenders)
    )


def test_mosaic_toolbar_binds_region_changed_event():
    """
    Regression lock: 모자이크 툴바는 활성화 시 `EVT_MOSAIC_REGION_CHANGED` 를
    캔버스에 바인딩해야 한다. 이 바인딩이 없으면 사용자가 기즈모를 드래그해도
    툴바의 `_region_x*/_region_y*` 가 갱신되지 않아 효과가 초기 위치에 머문다.
    """
    src = _read("editor/ui/inline_toolbars/mosaic_toolbar_wx.py")
    assert "EVT_MOSAIC_REGION_CHANGED" in src, (
        "mosaic_toolbar_wx.py 가 EVT_MOSAIC_REGION_CHANGED 를 import 하지 않습니다."
    )
    assert "canvas.Bind(EVT_MOSAIC_REGION_CHANGED" in src, (
        "mosaic_toolbar_wx.py 의 _on_activated 에서 "
        "canvas.Bind(EVT_MOSAIC_REGION_CHANGED, ...) 호출이 사라졌습니다."
    )


def test_frame_list_has_explicit_selection_tracker():
    """
    Regression lock: 프레임 리스트 위젯은 wx.grid 의 GetSelected* API 가
    wxMSW + Ctrl+클릭 비연속 선택에서 일관성 없는 결과를 반환하는 회귀에 대비해
    `_tracked_selection` 집합을 직접 유지해야 한다.

    - 다중 프레임 선택 후 '한 프레임만 삭제' 증상이 이 추적자 부재로 발생했다.
    - `_on_range_select` 가 Selecting/!Selecting 양쪽에서 갱신해야 한다.
    - `delete_selected_frames` 호출 시 보류된 selection 타이머를 정지하여
      포커스 전환과의 race 를 차단해야 한다.
    """
    src = _read("editor/ui/frame_list_widget_wx.py")
    assert "self._tracked_selection" in src, (
        "FrameListWidget 가 _tracked_selection 집합을 유지하지 않습니다 — "
        "wx.grid Ctrl+클릭 회귀에 노출됩니다."
    )
    # _on_range_select 가 양방향 갱신을 수행
    assert "self._tracked_selection.add(row)" in src
    assert "self._tracked_selection.discard(row)" in src
    # _get_selected_rows 가 IsInSelection 기반인지
    assert "IsInSelection(row, 0)" in src, (
        "_get_selected_rows 가 IsInSelection 으로 행을 점검해야 합니다 — "
        "GetSelectedRows/GetSelectionBlock* 만으로는 wxMSW 회귀를 회피하지 못합니다."
    )
    # delete_selected_frames 가 타이머를 정지 — 함수 본문 전체를 AST 로 추출하여
    # 길이가 늘어나도 false negative 가 발생하지 않게 한다.
    tree = ast.parse(src)
    delete_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "delete_selected_frames"),
        None,
    )
    assert delete_func is not None, "delete_selected_frames 함수가 사라졌습니다."
    func_src = ast.unparse(delete_func) if hasattr(ast, "unparse") else ""
    assert "self._selection_timer.Stop()" in func_src, (
        "delete_selected_frames 가 보류된 selection 타이머를 정지하지 않아 "
        "버튼 클릭과의 race 가 발생할 수 있습니다."
    )

    # select_frame() 공개 API 도 _tracked_selection 을 동기화해야 한다 — _updating
    # 가드 동안 EVT_GRID_RANGE_SELECT 가 추적자를 갱신하지 못하므로.
    select_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "select_frame"),
        None,
    )
    assert select_func is not None, "select_frame 함수가 사라졌습니다."
    select_src = ast.unparse(select_func) if hasattr(ast, "unparse") else ""
    assert "self._tracked_selection = {index}" in select_src, (
        "select_frame() 가 _tracked_selection 을 동기화하지 않습니다 — "
        "외부 호출 후 즉시 delete 시 이전 선택이 잔존할 수 있습니다."
    )


def test_no_hardcoded_korean_in_editor_ui_implementation():
    """
    Regression lock: no bare user-facing Korean string literals may remain in
    editor/ui/**/*.py after A2–A13 i18n work. Any new bare Korean literal added
    to these files will be caught here and must be routed through tr().

    Excluded (by category heuristic, not allowlist):
      i.   logger / get_logger diagnostic strings
      ii.  execute_lambda() undo-history description labels
      iii. "한" language-toggle button glyph
      iv.  sentinel "in label" comparisons; raise expressions
      iv.  class-level data constants (POSITIONS, CENSOR_TYPES)
      iv.  translations else-branch fallbacks (if translations: tr() else: "KO")
      iv.  _tr()-helper dict values (routed via tr() in same function)
      iv.  Korean system font names in font-picker list/dict/FindString contexts
    """
    editor_ui = Path("editor/ui")
    offenders = _collect_korean_offenders(editor_ui)

    assert offenders == [], (
        f"\n{len(offenders)} hardcoded Korean UI literal(s) found in editor/ui — "
        "route each through tr(key, fallback) or add a justified allowlist entry:\n"
        + "\n".join(f"  {p}:{ln}: {snip}" for p, ln, snip in offenders)
    )
