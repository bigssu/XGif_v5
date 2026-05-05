import ast
from pathlib import Path


def _module(path: str) -> ast.Module:
    return ast.parse(Path(path).read_text(encoding="utf-8"))


def _class(module: ast.Module, name: str) -> ast.ClassDef:
    return next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == name)


def _function(class_node: ast.ClassDef, name: str) -> ast.FunctionDef:
    return next(node for node in class_node.body if isinstance(node, ast.FunctionDef) and node.name == name)


def _assigned_constant(class_node: ast.ClassDef, name: str):
    for node in class_node.body:
        if not isinstance(node, ast.Assign):
            continue
        if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
            return node.value
    raise AssertionError(f"{name} assignment not found")


def test_rotate_toolbar_is_immediate_action_without_shared_buttons():
    toolbar = _class(_module("editor/ui/inline_toolbars/rotate_toolbar_wx.py"), "RotateToolbar")

    assert isinstance(_assigned_constant(toolbar, "_has_clear_button"), ast.Constant)
    assert _assigned_constant(toolbar, "_has_clear_button").value is False
    assert isinstance(_assigned_constant(toolbar, "_has_action_buttons"), ast.Constant)
    assert _assigned_constant(toolbar, "_has_action_buttons").value is False

    override_names = {node.name for node in toolbar.body if isinstance(node, ast.FunctionDef)}
    assert "_on_apply" not in override_names
    assert "_on_cancel" not in override_names


def test_rotate_toolbar_selection_applies_and_closes_once():
    toolbar = _class(_module("editor/ui/inline_toolbars/rotate_toolbar_wx.py"), "RotateToolbar")
    apply_rotate = _function(toolbar, "_apply_rotate")
    calls = [
        node.func.attr
        for node in ast.walk(apply_rotate)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    ]

    assert "_rotate_frames" in calls
    assert "_finish_apply" in calls
    assert calls.index("_rotate_frames") < calls.index("_finish_apply")


def test_main_window_hides_shared_buttons_for_instant_toolbars():
    main_window = _class(_module("editor/ui/editor_main_window_wx.py"), "MainWindow")
    show_buttons = _function(main_window, "_show_action_buttons")
    source = ast.get_source_segment(
        Path("editor/ui/editor_main_window_wx.py").read_text(encoding="utf-8"),
        show_buttons,
    )

    assert "has_action_buttons" in source
    assert "self._hide_action_buttons()" in source


def test_editor_buttons_and_override_colors_use_semantic_tokens():
    theme = Path("ui/theme.py").read_text(encoding="utf-8")
    main_window = Path("editor/ui/editor_main_window_wx.py").read_text(encoding="utf-8")
    icon_toolbar = Path("editor/ui/icon_toolbar_wx.py").read_text(encoding="utf-8")
    save_dialog = Path("editor/ui/save_dialog_wx.py").read_text(encoding="utf-8")
    ko_locale = Path("resources/i18n/ko.json").read_text(encoding="utf-8")
    en_locale = Path("resources/i18n/en.json").read_text(encoding="utf-8")

    assert "ACTION_BUTTON_PRIMARY_BG = ACCENT" in theme
    assert "LANG_TOGGLE_FG = SUCCESS" in theme
    assert "SAVE_PRIMARY = ACTION_BUTTON_PRIMARY_BG" in theme
    assert "self._create_action_button(" in main_window
    assert "wx.Colour(0, 255, 0)" not in main_window
    assert "Colors.ICON_BTN_ACTIVE" in icon_toolbar
    assert "COLOR_BUTTON_SAVE = Colors.SAVE_PRIMARY" in save_dialog
    assert '"rotate_tooltip":' in ko_locale
    assert '"rotate_angle":' in ko_locale
    assert '"rotate_tooltip":' in en_locale
    assert '"rotate_angle":' in en_locale


def test_editor_theme_follows_design_md_tokens():
    design = Path("DESIGN.md").read_text(encoding="utf-8")
    theme = Path("ui/theme.py").read_text(encoding="utf-8")
    icon_toolbar = Path("editor/ui/icon_toolbar_wx.py").read_text(encoding="utf-8")
    app_icons = Path("app_icons_wx.py").read_text(encoding="utf-8")

    assert "Figma-inspired" in design
    assert "FIGMA_LILAC = wx.Colour(197, 176, 244)" in theme
    assert "FIGMA_MAGENTA = wx.Colour(255, 61, 139)" in theme
    assert "BG_PRIMARY = wx.Colour(247, 247, 245)" in theme
    assert "BORDER = wx.Colour(230, 230, 230)" in theme
    assert "VERSION_ACCENT = FIGMA_MAGENTA" in theme
    assert "gc.SetPen(wx.Pen(border, 1))" in icon_toolbar
    assert 'OPEN_FILE = ACCENT' in app_icons


def test_icon_factory_bitmaps_keep_transparent_backgrounds():
    import wx
    from editor.ui.icon_utils_wx import IconFactory

    _app = wx.App.Get() or wx.App(False)
    IconFactory._cache.clear()

    icon_types = sorted(name.removeprefix("_draw_") for name in dir(IconFactory) if name.startswith("_draw_"))
    assert "play" in icon_types

    for icon_type in icon_types:
        bitmap = IconFactory.create_bitmap(icon_type, 39)
        image = bitmap.ConvertToImage()

        assert image.HasAlpha(), icon_type
        opaque_pixels = sum(
            1
            for y in range(image.GetHeight())
            for x in range(image.GetWidth())
            if image.GetAlpha(x, y)
        )

        assert image.GetAlpha(0, 0) == 0, icon_type
        assert opaque_pixels > 0, icon_type


def test_editor_icons_use_tabler_subset_with_limited_semantic_colors():
    from editor.ui.icon_utils_wx import IconFactory

    draw_methods = sorted(name.removeprefix("_draw_") for name in dir(IconFactory) if name.startswith("_draw_"))
    icon_dir = Path("resources/icons/tabler-outline")
    required_assets = set(IconFactory.TABLER_ICON_BY_TYPE.values())

    assert set(draw_methods) <= set(IconFactory.TABLER_ICON_BY_TYPE)
    assert required_assets
    assert (icon_dir / "LICENSE").exists()
    assert (icon_dir / "README.md").exists()
    assert all((icon_dir / f"{asset}.svg").exists() for asset in required_assets)
    assert len(set(IconFactory.ICON_COLOR_BY_TYPE.values())) <= 4


def test_shared_tabler_icons_cover_editor_and_capture_controls():
    from app_icons_wx import TABLER_ICON_BY_TYPE, create_icon_bitmap
    import wx

    _app = wx.App.Get() or wx.App(False)
    icon_dir = Path("resources/icons/tabler-outline")
    required_types = {
        "add",
        "cursor",
        "delete",
        "help",
        "pause",
        "play",
        "record",
        "region",
        "settings",
        "stop",
        "time",
    }

    assert required_types <= set(TABLER_ICON_BY_TYPE)
    for icon_type in required_types:
        assert (icon_dir / f"{TABLER_ICON_BY_TYPE[icon_type]}.svg").exists()
        image = create_icon_bitmap(icon_type, 20).ConvertToImage()
        assert image.HasAlpha(), icon_type
        assert image.GetAlpha(0, 0) == 0, icon_type
        assert any(
            image.GetAlpha(x, y)
            for y in range(image.GetHeight())
            for x in range(image.GetWidth())
        ), icon_type


def test_toolbar_icon_surfaces_do_not_use_emoji_or_manual_glyph_buttons():
    frame_list = Path("editor/ui/frame_list_widget_wx.py").read_text(encoding="utf-8")
    capture_bar = Path("ui/capture_control_bar.py").read_text(encoding="utf-8")
    forbidden = [
        chr(0x1F5D1),
        chr(0x23F1),
        chr(0x2795),
        chr(0x2699),
        chr(0x2196),
        chr(0x2B1A),
        "\u25cf REC",
        "\u25a0 STOP",
        "\u25b6 REC",
        "\u275a\u275a",
    ]

    assert all(glyph not in frame_list for glyph in forbidden)
    assert all(glyph not in capture_bar for glyph in forbidden)
    assert "IconFactory.create_bitmap(icon_type, 18)" in frame_list
    assert "create_icon_bitmap(self._icon_type, self._icon_size, icon_color)" in capture_bar
    assert 'self.rec_button.SetIcon("stop")' in capture_bar
    assert 'self.rec_button.SetIcon("record")' in capture_bar


def test_text_toolbar_icon_is_centered_in_its_bitmap():
    import wx
    from editor.ui.icon_utils_wx import IconFactory

    _app = wx.App.Get() or wx.App(False)
    IconFactory._cache.clear()
    image = IconFactory.create_bitmap("text", 39).ConvertToImage()
    pixels = [
        (x, y)
        for y in range(image.GetHeight())
        for x in range(image.GetWidth())
        if image.GetAlpha(x, y)
    ]

    assert pixels
    min_x = min(x for x, _y in pixels)
    max_x = max(x for x, _y in pixels)
    min_y = min(y for _x, y in pixels)
    max_y = max(y for _x, y in pixels)

    center_x = (min_x + max_x) / 2
    center_y = (min_y + max_y) / 2
    assert abs(center_x - 19) <= 2
    assert abs(center_y - 19) <= 2


def test_inline_toolbar_icon_labels_use_shared_icon_factory():
    inline_paths = Path("editor/ui/inline_toolbars").glob("*_toolbar_wx.py")
    icon_types = set()
    for path in inline_paths:
        module = _module(str(path))
        for node in ast.walk(module):
            if not isinstance(node, ast.Call):
                continue
            if not isinstance(node.func, ast.Attribute) or node.func.attr != "add_icon_label":
                continue
            if node.args and isinstance(node.args[0], ast.Constant):
                icon_types.add(node.args[0].value)

    icon_factory = _class(_module("editor/ui/icon_utils_wx.py"), "IconFactory")
    draw_methods = {node.name.removeprefix("_draw_") for node in icon_factory.body if isinstance(node, ast.FunctionDef)}
    base_toolbar = Path("editor/ui/inline_toolbars/base_toolbar_wx.py").read_text(encoding="utf-8")

    assert icon_types
    assert icon_types <= draw_methods
    assert "IconFactory.create_bitmap(icon_type, size)" in base_toolbar
    assert "wx.Bitmap(size, size)" not in base_toolbar
    assert "wx.WrapSizer" not in base_toolbar
    assert "wx.ScrolledWindow" in base_toolbar
    assert "wx.BoxSizer(wx.HORIZONTAL)" in base_toolbar
    assert "wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT" in base_toolbar
    assert "self._controls_sizer.Add(widget, 0, wx.ALL, 8)" not in base_toolbar
    assert "ShowScrollbars(wx.SHOW_SB_NEVER, wx.SHOW_SB_NEVER)" in base_toolbar
    assert "_bind_toolbar_drag_scroll(self._controls_widget)" in base_toolbar
    assert "self._bind_toolbar_drag_scroll(label)" in base_toolbar
    assert "self._bind_toolbar_drag_scroll(separator)" in base_toolbar


def test_inline_toolbar_icon_label_renders_a_real_transparent_icon():
    import wx
    from editor.ui.inline_toolbars.base_toolbar_wx import InlineToolbarBase

    _app = wx.App.Get() or wx.App(False)
    frame = wx.Frame(None)
    try:
        toolbar = InlineToolbarBase(frame, frame)
        label = toolbar.add_icon_label("text", 20)
        image = label.GetBitmap().ConvertToImage()

        assert image.HasAlpha()
        assert image.GetAlpha(0, 0) == 0
        assert any(
            image.GetAlpha(x, y)
            for y in range(image.GetHeight())
            for x in range(image.GetWidth())
        )
    finally:
        frame.Destroy()


def test_text_inline_toolbar_controls_share_a_vertical_centerline():
    import wx
    from editor.ui.inline_toolbars.text_toolbar_wx import TextToolbar

    class _FakeMainWindow(wx.Frame):
        def __init__(self):
            super().__init__(None)
            self._translations = None
            self._is_low_end_mode = False
            self._preview_delay = 100
            self._frames = None
            self._canvas = None

    _app = wx.App.Get() or wx.App(False)
    frame = _FakeMainWindow()
    try:
        frame.SetSize((1100, 200))
        toolbar = TextToolbar(frame, frame)
        toolbar.SetSize((1080, 88))
        frame.Show()
        frame.Layout()
        toolbar.Layout()
        toolbar._controls_widget.Layout()

        centers = []
        for child in toolbar._controls_widget.GetChildren():
            if not child.IsShown():
                continue
            size = child.GetSize()
            if size.width <= 1 or size.height <= 1:
                continue
            pos = child.GetPosition()
            centers.append(pos.y + size.height / 2)

        assert centers
        assert max(centers) - min(centers) <= 1
    finally:
        frame.Destroy()
