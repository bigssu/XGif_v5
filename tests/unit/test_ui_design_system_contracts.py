from pathlib import Path
import json


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


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
