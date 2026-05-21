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


def test_memory_manager_method_names_match_mb_suffix():
    """
    Regression lock: `_check_memory_limit` 가 `FrameMemoryManager` 의 메서드 이름을
    `set_memory_limit_mb` / `get_memory_limit_mb` (mb 접미사 포함) 로 호출해야 한다.
    이전에 `set_memory_limit` / `get_memory_limit` 로 잘못 호출해 사용자가 메모리
    확대 다이얼로그에서 "예" 를 누르면 AttributeError 가 발생하던 회귀가 있었다.
    """
    main_src = _read("editor/ui/editor_main_window_wx.py")
    frame_src = _read("editor/core/frame.py")

    # FrameMemoryManager 가 mb 접미사 메서드만 정의
    assert "def get_memory_limit_mb" in frame_src, (
        "FrameMemoryManager.get_memory_limit_mb 정의가 사라졌습니다."
    )
    assert "def set_memory_limit_mb" in frame_src, (
        "FrameMemoryManager.set_memory_limit_mb 정의가 사라졌습니다."
    )
    # 메인 윈도우가 mb 접미사 메서드를 호출
    assert "_memory_manager.set_memory_limit_mb(" in main_src, (
        "_check_memory_limit 가 set_memory_limit_mb 를 호출하지 않습니다 — "
        "AttributeError 회귀 위험."
    )
    assert "_memory_manager.get_memory_limit_mb(" in main_src, (
        "_check_memory_limit 가 get_memory_limit_mb 를 호출하지 않습니다 — "
        "AttributeError 회귀 위험."
    )
    # mb 접미사 없는 호출이 새로 도입되지 않았는지
    assert "_memory_manager.set_memory_limit(" not in main_src, (
        "_memory_manager.set_memory_limit() 는 존재하지 않는 메서드입니다 — "
        "set_memory_limit_mb 로 호출해야 합니다."
    )
    assert "_memory_manager.get_memory_limit(" not in main_src, (
        "_memory_manager.get_memory_limit() 는 존재하지 않는 메서드입니다 — "
        "get_memory_limit_mb 로 호출해야 합니다."
    )


def test_delete_selected_frames_has_large_gif_undo_guard():
    """
    Regression lock: `delete_selected_frames` 는 대용량 GIF (메모리 100MB+) 에서
    `frames.clone()` 으로 인한 OOM/swap 을 피하기 위해 undo 등록을 생략하는 가드를
    가져야 한다. `_duplicate_frame` / `_reduce_frames` 와 동일 패턴.

    또한 "모든 프레임 선택 후 삭제" silent return 은 사용자에게 무응답으로 보이므로
    `msg_min_one_frame_body` 다이얼로그로 표면화되어야 한다.
    """
    src = _read("editor/ui/frame_list_widget_wx.py")
    tree = ast.parse(src)
    delete_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "delete_selected_frames"),
        None,
    )
    assert delete_func is not None, "delete_selected_frames 함수가 사라졌습니다."
    func_src = ast.unparse(delete_func) if hasattr(ast, "unparse") else ""

    # 100MB 임계 가드
    assert "get_memory_usage_mb" in func_src, (
        "delete_selected_frames 가 메모리 사용량을 점검하지 않습니다 — "
        "대용량 GIF 에서 undo clone OOM 위험."
    )
    assert "current_memory_mb > 100" in func_src, (
        "delete_selected_frames 가 100MB 임계 가드를 갖추지 않았습니다."
    )
    assert "msg_frame_delete_no_undo" in func_src, (
        "대용량 모드에서 사용자에게 undo 불가 알림을 표시해야 합니다."
    )
    # 모두 선택 silent return 대신 다이얼로그
    assert "msg_min_one_frame_body" in func_src, (
        "'모든 프레임 선택' 무응답을 다이얼로그로 표면화해야 합니다 — "
        "silent return 은 사용자에게 버튼이 작동하지 않는 것으로 보입니다."
    )


def test_frame_list_refresh_forces_grid_repaint():
    """
    Regression lock: `FrameListWidget.refresh()` 가 데이터 채움 직후 `ForceRefresh()`
    를 호출해야 한다. wx.grid 는 SetCellValue 만으로 자동 repaint 가 보장되지
    않아, GIF 로드 직후 그리드가 빈 화면으로 보이고 Play 를 눌러야 비로소 표시되는
    회귀가 있었다.
    """
    src = _read("editor/ui/frame_list_widget_wx.py")
    tree = ast.parse(src)
    refresh_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "refresh"),
        None,
    )
    assert refresh_func is not None, "FrameListWidget.refresh 함수가 사라졌습니다."
    func_src = ast.unparse(refresh_func) if hasattr(ast, "unparse") else ""
    assert "ForceRefresh()" in func_src, (
        "refresh() 가 ForceRefresh 를 호출하지 않습니다 — "
        "wx.grid 초기 페인트 누락 회귀에 노출됩니다."
    )


def test_frame_preserves_low_memory_modes():
    """
    Regression lock: `Frame.__init__` 가 P (인덱스 컬러) / L (그레이) / LA / RGB
    / RGBA 를 RGBA 로 강제 변환하지 않고 보존한다. 256색 GIF 가 본래 P 모드인데
    RGBA 로 풀어버리면 메모리 4× 부풀어 사용자 시나리오 (12MB GIF → 1.8GB) 의
    근본 원인이 된다.
    """
    from PIL import Image as PILImage
    from editor.core.frame import Frame

    # P 모드 보존
    p_img = PILImage.new('P', (10, 10), 0)
    p_frame = Frame(p_img, 100, lazy_load=False)
    assert p_frame.image.mode == 'P', (
        "Frame 가 P 모드 입력을 RGBA 로 강제 변환합니다 — 메모리 4× 부풀음 회귀."
    )

    # RGB 모드 보존
    rgb_img = PILImage.new('RGB', (10, 10), (255, 0, 0))
    rgb_frame = Frame(rgb_img, 100, lazy_load=False)
    assert rgb_frame.image.mode == 'RGB', (
        "Frame 가 RGB 모드 입력을 RGBA 로 강제 변환합니다."
    )

    # 화이트리스트 외 mode 는 RGBA 변환
    cmyk_img = PILImage.new('CMYK', (10, 10), (0, 0, 0, 255))
    cmyk_frame = Frame(cmyk_img, 100, lazy_load=False)
    assert cmyk_frame.image.mode == 'RGBA', (
        "Frame 가 안전 화이트리스트 외 mode (CMYK) 를 RGBA 로 정규화하지 않습니다."
    )


def test_frame_memory_usage_is_mode_aware():
    """
    Regression lock: `Frame.get_memory_usage` 가 mode 별 byte 수를 정확히 계산.
    이전 `w*h*4` 고정은 P 모드 (1 byte/픽셀) 보존 시 4× 과대 추정이었다.
    """
    from PIL import Image as PILImage
    from editor.core.frame import Frame

    p_frame = Frame(PILImage.new('P', (100, 100), 0), 100, lazy_load=False)
    rgba_frame = Frame(PILImage.new('RGBA', (100, 100), (0, 0, 0, 0)), 100, lazy_load=False)

    p_usage = p_frame.get_memory_usage()
    rgba_usage = rgba_frame.get_memory_usage()
    # P 모드는 1 byte/픽셀 + 팔레트 ~1KB, RGBA 는 4 byte/픽셀.
    # 100x100 기준 P=10000+1024=11024, RGBA=40000.
    assert p_usage < rgba_usage / 3, (
        f"get_memory_usage 가 mode-aware 가 아닙니다 (P={p_usage}, RGBA={rgba_usage}) — "
        "P 모드 보존 효과가 메모리 추정에 반영되지 않습니다."
    )


def test_gif_decoder_does_not_force_rgba_conversion():
    """
    Regression lock: GifDecoder 의 디코드 경로가 `convert('RGBA')` 를 강제하지
    않는다. PIL 이 디스포잘 합성 시 자동으로 mode 결정하도록 `copy()` 만 사용.
    """
    src = _read("editor/core/gif_decoder.py")
    # _load_gif, _load_image, load_image_sequence 모두 .convert('RGBA') 가 없어야 함
    assert "img.convert('RGBA')" not in src, (
        "GifDecoder 가 디코드 시 RGBA 강제 변환을 사용합니다 — P 모드 보존이 깨집니다."
    )
    # frame_img = img.copy() 또는 img.copy() 패턴 사용
    assert "img.copy()" in src, (
        "GifDecoder 가 `img.copy()` 로 mode 보존하지 않습니다."
    )


def test_frame_collection_has_p_mode_batch_conversion():
    """
    Regression lock: `FrameCollection.convert_all_to_p_mode` + `has_non_p_mode_frames`
    API 가 존재하고 작동한다. MainWindow 의 메모리 최적화 제안 다이얼로그가 이 API
    를 호출.
    """
    from PIL import Image as PILImage
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection

    col = FrameCollection()
    col.add_frame(Frame(PILImage.new('RGBA', (100, 100), (255, 0, 0, 255)), 100, lazy_load=False))
    col.add_frame(Frame(PILImage.new('RGBA', (100, 100), (0, 255, 0, 255)), 100, lazy_load=False))

    assert col.has_non_p_mode_frames(), "RGBA 컬렉션이 has_non_p_mode_frames=True 여야 합니다."

    before_mb = col.get_memory_usage_mb()
    converted = col.convert_all_to_p_mode()
    after_mb = col.get_memory_usage_mb()

    assert converted == 2, f"두 RGBA 프레임이 변환되어야 합니다 (변환됨: {converted})."
    assert not col.has_non_p_mode_frames(), (
        "변환 후 has_non_p_mode_frames=False 여야 합니다."
    )
    assert after_mb < before_mb / 2, (
        f"P 변환이 메모리를 절반 미만으로 줄여야 합니다 (전: {before_mb}MB, 후: {after_mb}MB)."
    )
    # numpy_array 호환성 — 효과 코드들이 RGBA (H, W, 4) 가정
    arr = col[0].numpy_array
    assert arr.shape == (100, 100, 4), (
        f"P 모드 프레임의 numpy_array 가 RGBA 4채널을 반환해야 합니다 (실제: {arr.shape})."
    )


def test_main_window_offers_index_color_at_500mb():
    """
    Regression lock: `_offer_index_color_optimization` 메서드가 500MB 임계와
    `has_non_p_mode_frames` 체크, 그리고 `msg_index_color_offer_*` i18n 키를
    사용하는지 검증.
    """
    src = _read("editor/ui/editor_main_window_wx.py")
    tree = ast.parse(src)
    offer_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_offer_index_color_optimization"),
        None,
    )
    assert offer_func is not None, "_offer_index_color_optimization 메서드가 사라졌습니다."
    func_src = ast.unparse(offer_func) if hasattr(ast, "unparse") else ""

    assert "memory_mb < 500" in func_src, (
        "_offer_index_color_optimization 가 500MB 임계 가드를 갖추지 않았습니다."
    )
    assert "has_non_p_mode_frames" in func_src, (
        "이미 P 모드인 컬렉션은 변환 효과가 없으므로 has_non_p_mode_frames 체크 필요."
    )
    assert "msg_index_color_offer_body" in func_src, (
        "사용자에게 표시할 다이얼로그 본문이 누락되었습니다."
    )
    assert "convert_all_to_p_mode" in func_src, (
        "batch 변환 API 호출이 누락되었습니다."
    )
    # open_file 직후 wx.CallAfter 로 트리거되는지
    assert "_offer_index_color_optimization" in src.split("def _offer_index_color_optimization")[0], (
        "open_file 경로에서 _offer_index_color_optimization 가 호출되지 않습니다."
    )


def test_logger_wrapper_accepts_standard_logging_kwargs():
    """
    Regression lock: `editor.utils.logger.Logger` wrapper 의 모든 레벨 메서드
    (debug/info/warning/error/exception/critical/log) 가 표준 `logging.Logger`
    와 동일하게 `*args` (% format) 와 `**kwargs` (`exc_info`, `stack_info`,
    `extra`, `stacklevel`) 를 받아야 한다.

    이전엔 `(message: str)` 단독 시그니처라 코드베이스의
    `_logger.error(..., exc_info=True)` 호출 12군데가 모두 TypeError 를 던질
    수 있었고, 1.8GB GIF 로드 실패 시 그 진짜 root cause 가 logger TypeError
    ("got an unexpected keyword argument 'exc_info'") 다이얼로그로 가려졌다.
    """
    from editor.utils.logger import get_logger
    log = get_logger()

    # 1) plain message
    log.error("plain message")

    # 2) exc_info=True 키워드 — 이전 회귀 시점
    try:
        raise ValueError("test exc_info")
    except Exception as e:
        log.error(f"caught: {e}", exc_info=True)
        log.warning(f"warn: {e}", exc_info=True)
        log.exception(f"exception: {e}")

    # 3) %-format args
    log.info("format %s %d", "arg", 42)
    log.debug("debug %s", "ok")

    # 4) stack_info 등 다른 표준 kwargs
    log.warning("stack test", stack_info=False)

    # 5) critical / log 신규 메서드
    log.critical("critical test")
    import logging
    log.log(logging.WARNING, "log() test")


def test_safe_canvas_update_invalidates_paint_lru_cache():
    """
    Regression lock: `InlineToolbarBase._safe_canvas_update` 가 caller 의 frame.image
    교체 직후 호출되므로, canvas paint LRU 캐시도 함께 invalidate 해야 한다.

    paint 캐시 key 가 `id(pil_image)` 를 포함하는데 CPython 의 id() 는 메모리
    재할당 시 재사용되므로, `_apply_text` 등이 새 PIL Image 를 만들어도 옛 id 와
    일치 → LRU hit 으로 옛 비트맵 표시. 텍스트/모자이크 기즈모 이동 시 효과가
    옛 위치에 머무는 회귀의 root cause.
    """
    src = _read("editor/ui/inline_toolbars/base_toolbar_wx.py")
    tree = ast.parse(src)
    update_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_safe_canvas_update"),
        None,
    )
    assert update_func is not None, "_safe_canvas_update 메서드가 사라졌습니다."
    func_src = ast.unparse(update_func) if hasattr(ast, "unparse") else ""
    assert "clear_bitmap_cache" in func_src, (
        "_safe_canvas_update 가 canvas.clear_bitmap_cache() 를 호출하지 않습니다 — "
        "LRU 캐시의 id() 재사용 회귀에 노출됩니다."
    )


def test_canvas_has_unified_gizmo_dispatch():
    """
    Regression lock: 캔버스 mouse handler 가 5 mode (text/crop/sticker/mosaic/
    speech_bubble) 의 인터랙션을 활성 Gizmo dispatch 로 통합한다.

    이전 구조 (mode 당 별도 분기 5×) 는 한 mode 의 회귀 (예: 모자이크 PyQt6
    시그널 잔재, 텍스트 기즈모 paint LRU 회귀) 가 다른 mode 에 전파되지 않는
    5× 패치 위험을 만들었다. Gizmo 추상화 + 단일 dispatch 로 root cause 가 단일
    출처에서만 수정되도록 강제.
    """
    src = _read("editor/ui/canvas_widget_wx.py")
    tree = ast.parse(src)

    # 5 Gizmo 인스턴스 — __init__ 안에 self._gizmos dict 정의
    assert "self._gizmos: Dict[str, Gizmo]" in src or "self._gizmos: dict" in src.lower(), (
        "CanvasWidget 가 self._gizmos 를 보유하지 않습니다."
    )
    for mode in ('text', 'crop', 'sticker', 'mosaic', 'speech_bubble'):
        assert f"'{mode}'" in src, f"Gizmo 인스턴스 '{mode}' 가 누락되었습니다."

    # _active_gizmo 와 _dispatch_gizmo_release 메서드
    for method_name in ('_active_gizmo', '_dispatch_gizmo_release'):
        func = next(
            (node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == method_name),
            None,
        )
        assert func is not None, f"{method_name} 메서드가 사라졌습니다."

    # mouse handler 가 활성 Gizmo dispatch 사용
    for handler_name in ('_on_left_down', '_on_mouse_move', '_on_left_up', '_update_cursor_for_hover'):
        handler = next(
            (node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == handler_name),
            None,
        )
        assert handler is not None, f"{handler_name} 핸들러가 사라졌습니다."
        handler_src = ast.unparse(handler) if hasattr(ast, "unparse") else ""
        assert "_active_gizmo" in handler_src, (
            f"{handler_name} 가 활성 Gizmo dispatch 패턴 (_active_gizmo) 을 사용하지 않습니다."
        )

    # mode 별 별도 분기 (5×) 가 사라졌는지 — `self._text_dragging or self._text_resizing`
    # 같은 ad-hoc 검사 패턴이 _on_left_up 에서 제거됐는지.
    up_handler = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_on_left_up"),
        None,
    )
    up_src = ast.unparse(up_handler) if hasattr(ast, "unparse") else ""
    # 5 mode 별 분기가 통합되었으므로 _on_left_up 에서 mode-specific dragging/
    # resizing flag 를 명시적으로 검사하는 패턴은 사라져야 함.
    for mode_attr in ('_text_dragging', '_crop_dragging', '_sticker_dragging',
                       '_mosaic_dragging', '_speech_bubble_dragging'):
        assert mode_attr not in up_src, (
            f"_on_left_up 에 {mode_attr} 분기가 남아 있습니다 — "
            "Gizmo dispatch 통합이 완전하지 않습니다."
        )


def test_gizmo_class_supports_corner_only_and_all_handles():
    """
    Regression lock: Gizmo 클래스가 corner_only 옵션을 통해 sticker/mosaic/
    speech_bubble (4 코너) 와 text/crop (8 핸들) 양쪽을 모두 지원해야 한다.
    """
    from editor.ui.canvas_gizmo import Gizmo, CORNER_HANDLES, ALL_HANDLES
    from editor.ui.canvas_widget_wx import RectF

    corner_gizmo = Gizmo('sticker', RectF, corner_only=True)
    all_gizmo = Gizmo('text', RectF, corner_only=False)

    assert corner_gizmo.allowed_handles() == CORNER_HANDLES
    assert all_gizmo.allowed_handles() == ALL_HANDLES
    assert len(CORNER_HANDLES) == 4
    assert len(ALL_HANDLES) == 8


def test_progress_helper_exists_for_long_running_ops():
    """
    Regression lock: `editor/utils/progress.py` 의 `run_with_progress` 헬퍼가
    존재하고 background thread + ProgressDialog + cancel 지원의 표준 진입점을
    제공해야 한다.

    이전엔 모든 장시간 작업 (프레임 줄이기, 뒤집기, 회전, 중복 제거 등) 이 동기
    실행되어 UI 가 "정지 상태" 로 보이는 회귀가 빈번했다. 새 작업 추가 시 이
    helper 를 재활용하도록 강제하는 가드.
    """
    from editor.utils.progress import run_with_progress
    import inspect
    sig = inspect.signature(run_with_progress)
    # 표준 시그니처 검증 — work_func, total_hint, can_abort 필수 인자
    assert 'work_func' in sig.parameters
    assert 'total_hint' in sig.parameters
    assert 'can_abort' in sig.parameters


def test_long_running_frame_ops_use_progress_helper():
    """
    Regression lock: 모든 장시간 frame 변형 작업이 표준 ProgressDialog 진입점
    (`_run_undoable_with_progress` 또는 직접 `run_with_progress`) 을 사용해야 한다.

    사용자 보고 ("700→350 줄이기 중 정지 상태", "프로세스가 오래 걸릴 때 무조건
    프로그래시브 바") 의 직접 응답. 회귀 차단 대상:
        _reduce_frames / _flip_frames / _reverse_frames / _rotate_frames /
        _remove_duplicates / _apply_yoyo.
    """
    src = _read("editor/ui/editor_main_window_wx.py")
    tree = ast.parse(src)

    target_methods = (
        '_reduce_frames', '_flip_frames', '_reverse_frames',
        '_rotate_frames', '_remove_duplicates', '_apply_yoyo',
    )
    for method_name in target_methods:
        func = next(
            (node for node in ast.walk(tree)
             if isinstance(node, ast.FunctionDef) and node.name == method_name),
            None,
        )
        assert func is not None, f"{method_name} 메서드가 사라졌습니다."
        func_src = ast.unparse(func) if hasattr(ast, "unparse") else ""
        assert ("_run_undoable_with_progress" in func_src
                or "run_with_progress" in func_src), (
            f"{method_name} 가 ProgressDialog helper 를 사용하지 않습니다 — "
            "장시간 작업 중 UI 가 정지 상태로 보입니다."
        )

    # _run_undoable_with_progress 가 실제로 run_with_progress 를 호출
    helper = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_run_undoable_with_progress"),
        None,
    )
    assert helper is not None, "_run_undoable_with_progress helper 가 사라졌습니다."
    helper_src = ast.unparse(helper) if hasattr(ast, "unparse") else ""
    assert "run_with_progress" in helper_src

    # FrameCollection 의 진행률 지원 메서드들도 progress_callback 인자 보유
    fc_src = _read("editor/core/frame_collection.py")
    fc_tree = ast.parse(fc_src)
    for fc_method in ('reduce_frames', 'reverse_frames', 'apply_yoyo_effect', 'remove_duplicates'):
        method = next(
            (node for node in ast.walk(fc_tree)
             if isinstance(node, ast.FunctionDef) and node.name == fc_method),
            None,
        )
        assert method is not None, f"FrameCollection.{fc_method} 가 사라졌습니다."
        arg_names = [a.arg for a in method.args.args]
        assert "progress_callback" in arg_names, (
            f"FrameCollection.{fc_method} 에 progress_callback 인자가 없습니다."
        )


def test_reduce_toolbar_uses_progress_helper():
    """
    Regression lock: `ReduceToolbar._on_apply` 가 메인 윈도우의 표준 helper
    (`_run_undoable_with_progress`) 를 위임해야 한다.

    이전엔 `execute_lambda` 동기 호출이 700→350 reduce 케이스에서 6~8초 UI
    블록을 유발했다 (사용자 보고: "줄이는 동안 화면이 정지 상태"). helper 위임으로
    background thread + ProgressDialog 자동 표시.
    """
    src = _read("editor/ui/inline_toolbars/reduce_toolbar_wx.py")
    tree = ast.parse(src)
    apply_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_on_apply"),
        None,
    )
    assert apply_func is not None
    func_src = ast.unparse(apply_func) if hasattr(ast, "unparse") else ""
    assert "_run_undoable_with_progress" in func_src, (
        "ReduceToolbar._on_apply 가 _run_undoable_with_progress 를 위임하지 "
        "않습니다 — UI 블록 회귀 위험."
    )
    # 이전의 execute_lambda 동기 패턴이 제거됐는지
    assert "execute_lambda" not in func_src, (
        "_on_apply 에 execute_lambda 동기 호출이 남아 있습니다 — "
        "background thread 로 마이그레이션이 완전하지 않습니다."
    )


def test_editor_main_shows_window_before_load():
    """
    Regression lock: `editor/__main__.py` 가 윈도우를 먼저 Show 한 후 wx.CallAfter
    로 GIF 를 로드해야 한다.

    이전엔 `window.open_file(path)` 가 `window.Show()` 이전 호출 → 큰 GIF 의
    GIF 로드 ProgressDialog 가 보이지 않는 윈도우 위에서 생성되어 사용자에게
    "에디터가 안 뜨고 정지 상태" 로 보이는 회귀가 있었다.
    """
    src = _read("editor/__main__.py")
    tree = ast.parse(src)
    main_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "main"),
        None,
    )
    assert main_func is not None
    func_src = ast.unparse(main_func) if hasattr(ast, "unparse") else ""
    show_idx = func_src.find("window.Show()")
    open_idx = func_src.find("window.open_file")
    callafter_idx = func_src.find("wx.CallAfter(window.open_file")
    assert show_idx >= 0, "window.Show() 가 main() 에 없습니다."
    if open_idx >= 0:
        assert show_idx < open_idx, (
            "window.Show() 가 open_file 호출 이전에 실행되어야 합니다 — "
            "ProgressDialog 가 표시되지 않습니다."
        )
    assert callafter_idx >= 0, (
        "open_file 호출이 wx.CallAfter 로 감싸지지 않았습니다 — "
        "Show() 직후 동기 호출은 ProgressDialog 가 안 보일 수 있습니다."
    )


def test_slider_does_not_overwrite_user_selection():
    """
    Regression lock: `_on_slider_changed` 는 navigation 만 담당하고 사용자의
    `selected_indices` (모자이크/효과 적용 대상 선택) 를 보존해야 한다.

    이전엔 슬라이더 클릭 시 `deselect_all + select_frame(value)` 로 선택을 덮어써,
    사용자가 모자이크 적용을 위해 여러 프레임을 선택해둔 상태에서 슬라이더로
    리뷰하려는 순간 모든 선택이 사라지는 회귀가 있었다. "선택과 하이라이트는
    달라야" (사용자 보고).
    """
    src = _read("editor/ui/editor_main_window_wx.py")
    tree = ast.parse(src)
    slider_func = next(
        (node for node in ast.walk(tree)
         if isinstance(node, ast.FunctionDef) and node.name == "_on_slider_changed"),
        None,
    )
    assert slider_func is not None, "_on_slider_changed 메서드가 사라졌습니다."
    func_src = ast.unparse(slider_func) if hasattr(ast, "unparse") else ""
    # 사용자 선택을 덮어쓰는 패턴이 제거됐는지
    assert "deselect_all" not in func_src, (
        "_on_slider_changed 가 deselect_all() 을 호출합니다 — "
        "사용자 선택 보존이 깨집니다."
    )
    assert "select_frame" not in func_src, (
        "_on_slider_changed 가 select_frame() 을 호출합니다 — "
        "사용자 선택이 슬라이더 위치로 덮어쓰입니다."
    )
    # current_index 만 변경 (navigation)
    assert "current_index" in func_src


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
