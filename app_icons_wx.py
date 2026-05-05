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


def create_icon_bitmap(icon_type: str, size: int, color: Optional[object] = None) -> wx.Bitmap:
    bitmap = create_tabler_bitmap(icon_type, size, color)
    if bitmap is not None and bitmap.IsOk():
        return bitmap
    return create_transparent_bitmap(size, size)
