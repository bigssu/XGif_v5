"""Shared wxPython icon asset loader for app UI surfaces."""

from __future__ import annotations

import os
from typing import Optional

import wx


class AppIconColors:
    """Small semantic icon palette shared by editor and capture UI."""

    COMMAND = "#1f1d3d"
    ACCENT = "#ff3d8b"
    SUCCESS = "#1ea64a"
    WARNING = "#b17600"
    DANGER = "#d32f2f"

    APPLY = SUCCESS
    CANCEL = COMMAND
    DELETE = DANGER

    CROP = COMMAND
    RESIZE = COMMAND
    EFFECTS = COMMAND
    TEXT = COMMAND
    STICKER = COMMAND
    SPEED = COMMAND
    PENCIL = COMMAND

    OPEN_FILE = ACCENT
    FRAME = COMMAND
    ROTATE = COMMAND
    FLIP = COMMAND
    REVERSE = COMMAND
    YOYO = COMMAND
    REDUCE = COMMAND
    TIME = COMMAND
    ADD = SUCCESS
    PLAY = SUCCESS
    PAUSE = WARNING


TABLER_ICON_DIR = os.path.join("resources", "icons", "tabler-outline")
TABLER_ICON_BY_TYPE = {
    "add": "plus",
    "animation": "wave-sine",
    "apply": "check",
    "blink": "sparkles",
    "cancel": "x",
    "clear": "trash",
    "clock": "clock",
    "color_palette": "palette",
    "crop": "crop",
    "cursor": "pointer",
    "delete": "trash",
    "effects": "adjustments",
    "exit": "door-exit",
    "flip_h": "flip-horizontal",
    "flip_v": "flip-vertical",
    "font_size": "text-size",
    "frame": "photo",
    "help": "help-circle",
    "open_file": "folder-open",
    "outline": "square",
    "pause": "player-pause",
    "pencil": "pencil",
    "play": "player-play",
    "position": "crosshair",
    "record": "player-record",
    "reduce": "layout-list",
    "region": "target-arrow",
    "resize": "arrows-maximize",
    "reverse": "arrow-back-up",
    "rotate": "rotate-clockwise",
    "settings": "settings",
    "speed": "gauge",
    "sticker": "star",
    "stop": "player-stop",
    "style": "brush",
    "target": "target",
    "text": "typography",
    "time": "clock",
    "width": "line-height",
    "yoyo": "arrows-exchange",
}
ICON_COLOR_BY_TYPE = {
    "add": AppIconColors.SUCCESS,
    "apply": AppIconColors.SUCCESS,
    "clear": AppIconColors.DANGER,
    "delete": AppIconColors.DANGER,
    "open_file": AppIconColors.ACCENT,
    "pause": AppIconColors.WARNING,
    "play": AppIconColors.SUCCESS,
    "record": AppIconColors.DANGER,
    "stop": AppIconColors.DANGER,
}
ICON_SIZE_CLASS_TARGETS = {
    "xs": 12,
    "sm": 16,
    "md": 18,
    "lg": 25,
    "toolbar": 30,
}
OPTICAL_ICON_SIZE_BY_CLASS = {
    "xs": {
        "add": 18,
        "animation": 14,
        "apply": 16,
        "blink": 14,
        "cancel": 20,
        "clear": 14,
        "clock": 14,
        "color_palette": 14,
        "crop": 16,
        "cursor": 14,
        "delete": 14,
        "effects": 16,
        "exit": 14,
        "flip_h": 14,
        "flip_v": 14,
        "font_size": 14,
        "frame": 14,
        "help": 14,
        "open_file": 12,
        "outline": 14,
        "pause": 16,
        "pencil": 16,
        "play": 16,
        "position": 14,
        "record": 16,
        "reduce": 14,
        "region": 14,
        "resize": 14,
        "reverse": 16,
        "rotate": 14,
        "settings": 14,
        "speed": 14,
        "sticker": 12,
        "stop": 16,
        "style": 14,
        "target": 14,
        "text": 14,
        "time": 14,
        "width": 14,
        "yoyo": 14,
    },
    "sm": {
        "add": 24,
        "animation": 18,
        "apply": 20,
        "blink": 20,
        "cancel": 26,
        "clear": 18,
        "clock": 18,
        "color_palette": 18,
        "crop": 22,
        "cursor": 20,
        "delete": 18,
        "effects": 20,
        "exit": 18,
        "flip_h": 18,
        "flip_v": 18,
        "font_size": 18,
        "frame": 18,
        "help": 18,
        "open_file": 16,
        "outline": 18,
        "pause": 22,
        "pencil": 20,
        "play": 20,
        "position": 20,
        "record": 22,
        "reduce": 20,
        "region": 18,
        "resize": 20,
        "reverse": 20,
        "rotate": 20,
        "settings": 18,
        "speed": 18,
        "sticker": 16,
        "stop": 22,
        "style": 18,
        "target": 18,
        "text": 18,
        "time": 18,
        "width": 20,
        "yoyo": 18,
    },
    "md": {
        "add": 26,
        "animation": 22,
        "apply": 24,
        "blink": 22,
        "cancel": 30,
        "clear": 20,
        "clock": 20,
        "color_palette": 20,
        "crop": 26,
        "cursor": 22,
        "delete": 20,
        "effects": 22,
        "exit": 20,
        "flip_h": 20,
        "flip_v": 22,
        "font_size": 20,
        "frame": 20,
        "help": 20,
        "open_file": 20,
        "outline": 20,
        "pause": 26,
        "pencil": 24,
        "play": 22,
        "position": 22,
        "record": 26,
        "reduce": 22,
        "region": 20,
        "resize": 22,
        "reverse": 22,
        "rotate": 22,
        "settings": 20,
        "speed": 20,
        "sticker": 20,
        "stop": 26,
        "style": 20,
        "target": 20,
        "text": 22,
        "time": 20,
        "width": 22,
        "yoyo": 20,
    },
    "lg": {
        "add": 36,
        "animation": 28,
        "apply": 36,
        "blink": 32,
        "cancel": 40,
        "clear": 28,
        "clock": 28,
        "color_palette": 28,
        "crop": 34,
        "cursor": 30,
        "delete": 28,
        "effects": 30,
        "exit": 28,
        "flip_h": 28,
        "flip_v": 28,
        "font_size": 28,
        "frame": 28,
        "help": 28,
        "open_file": 28,
        "outline": 28,
        "pause": 34,
        "pencil": 34,
        "play": 32,
        "position": 30,
        "record": 34,
        "reduce": 30,
        "region": 28,
        "resize": 30,
        "reverse": 34,
        "rotate": 30,
        "settings": 28,
        "speed": 28,
        "sticker": 26,
        "stop": 34,
        "style": 28,
        "target": 28,
        "text": 30,
        "time": 28,
        "width": 32,
        "yoyo": 28,
    },
    "toolbar": {
        "add": 44,
        "animation": 36,
        "apply": 42,
        "blink": 38,
        "cancel": 46,
        "clear": 34,
        "clock": 34,
        "color_palette": 34,
        "crop": 44,
        "cursor": 38,
        "delete": 34,
        "effects": 38,
        "exit": 34,
        "flip_h": 36,
        "flip_v": 36,
        "font_size": 34,
        "frame": 34,
        "help": 34,
        "open_file": 32,
        "outline": 34,
        "pause": 44,
        "pencil": 40,
        "play": 40,
        "position": 38,
        "record": 44,
        "reduce": 38,
        "region": 36,
        "resize": 38,
        "reverse": 42,
        "rotate": 38,
        "settings": 36,
        "speed": 34,
        "sticker": 32,
        "stop": 44,
        "style": 36,
        "target": 34,
        "text": 38,
        "time": 34,
        "width": 38,
        "yoyo": 36,
    },
}


def color_to_css(color: Optional[object]) -> str:
    """Return a CSS hex color for wx.Colour, RGB tuples, or string colors."""
    if color is None:
        return AppIconColors.COMMAND
    if isinstance(color, wx.Colour):
        return "#{:02x}{:02x}{:02x}".format(color.Red(), color.Green(), color.Blue())
    if isinstance(color, (tuple, list)) and len(color) >= 3:
        return "#{:02x}{:02x}{:02x}".format(int(color[0]), int(color[1]), int(color[2]))
    return str(color)


def icon_color(icon_type: str, color: Optional[object] = None) -> str:
    return color_to_css(color or ICON_COLOR_BY_TYPE.get(icon_type, AppIconColors.COMMAND))


def icon_size_class_for_nominal(size: int) -> str:
    if size <= 15:
        return "xs"
    if size <= 18:
        return "sm"
    if size <= 24:
        return "md"
    if size <= 32:
        return "lg"
    return "toolbar"


def optical_icon_size(icon_type: str, size_class: Optional[str] = None, nominal_size: Optional[int] = None) -> int:
    if size_class is None:
        if nominal_size is None:
            raise ValueError("size_class or nominal_size is required")
        size_class = icon_size_class_for_nominal(nominal_size)

    class_sizes = OPTICAL_ICON_SIZE_BY_CLASS.get(size_class)
    if class_sizes is None:
        raise ValueError(f"unknown icon size class: {size_class}")
    fallback = nominal_size or max(ICON_SIZE_CLASS_TARGETS.get(size_class, 18), 2)
    return class_sizes.get(icon_type, fallback)


def tabler_icon_path(tabler_icon: str) -> str:
    from core.utils import get_resource_path

    return get_resource_path(os.path.join(TABLER_ICON_DIR, f"{tabler_icon}.svg"))


def create_transparent_bitmap(width: int, height: int) -> wx.Bitmap:
    return wx.Bitmap.FromRGBA(width, height, 0, 0, 0, 0)


def create_tabler_bitmap(icon_type: str, size: int, color: Optional[object] = None) -> Optional[wx.Bitmap]:
    tabler_icon = TABLER_ICON_BY_TYPE.get(icon_type)
    if not tabler_icon:
        return None

    icon_path = tabler_icon_path(tabler_icon)
    if not os.path.exists(icon_path):
        return None

    try:
        import wx.svg

        with open(icon_path, "r", encoding="utf-8") as icon_file:
            svg_text = icon_file.read()
        svg_text = svg_text.replace("currentColor", icon_color(icon_type, color))
        svg = wx.svg.SVGimage.CreateFromBytes(svg_text.encode("utf-8"))
        return svg.ConvertToScaledBitmap((size, size))
    except Exception:
        return None


def create_icon_bitmap(
    icon_type: str,
    size: int,
    color: Optional[object] = None,
    *,
    size_class: Optional[str] = None,
) -> wx.Bitmap:
    render_size = optical_icon_size(icon_type, size_class=size_class, nominal_size=size)
    bitmap = create_tabler_bitmap(icon_type, render_size, color)
    if bitmap is not None and bitmap.IsOk():
        return bitmap
    return create_transparent_bitmap(render_size, render_size)
