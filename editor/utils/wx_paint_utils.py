"""
wxPython Painting Utilities

Provides utility functions for common painting operations in wxPython,
optimized for the XGif editor canvas and UI components.
"""

import wx
from PIL import Image
from typing import Optional


def pil_to_wx_bitmap(pil_image: Image.Image) -> wx.Bitmap:
    """
    Convert a PIL Image to a wx.Bitmap.

    Handles RGBA images with transparency correctly.

    Args:
        pil_image: PIL Image to convert

    Returns:
        wx.Bitmap object
    """
    # Convert to RGBA if needed
    if pil_image.mode != 'RGBA':
        pil_image = pil_image.convert('RGBA')

    width, height = pil_image.size

    # Create wx.Image from raw RGBA data
    wx_image = wx.Image(width, height)
    wx_image.SetData(pil_image.convert('RGB').tobytes())

    # Set alpha channel if present
    if pil_image.mode == 'RGBA':
        alpha_data = pil_image.split()[3].tobytes()
        wx_image.SetAlpha(alpha_data)

    return wx.Bitmap(wx_image)


def draw_checkerboard(dc: wx.DC, rect: wx.Rect, cell_size: int = 8,
                      color1: wx.Colour = None, color2: wx.Colour = None) -> None:
    """
    Draw a checkerboard pattern for transparent backgrounds.

    Args:
        dc: Device context to draw on
        rect: Rectangle area to fill with pattern
        cell_size: Size of each checker square (default 8px)
        color1: First checker color (default light gray)
        color2: Second checker color (default white)
    """
    if color1 is None:
        color1 = wx.Colour(200, 200, 200)
    if color2 is None:
        color2 = wx.Colour(255, 255, 255)

    # Save DC state
    dc.SetPen(wx.TRANSPARENT_PEN)

    # Calculate grid dimensions
    start_x = rect.x
    start_y = rect.y
    end_x = rect.x + rect.width
    end_y = rect.y + rect.height

    # Draw checkerboard
    for y in range(start_y, end_y, cell_size):
        for x in range(start_x, end_x, cell_size):
            # Calculate which color to use (checkerboard pattern)
            row = (y - start_y) // cell_size
            col = (x - start_x) // cell_size

            if (row + col) % 2 == 0:
                dc.SetBrush(wx.Brush(color1))
            else:
                dc.SetBrush(wx.Brush(color2))

            # Draw cell (clip to rect bounds)
            cell_rect = wx.Rect(
                x, y,
                min(cell_size, end_x - x),
                min(cell_size, end_y - y)
            )
            dc.DrawRectangle(cell_rect)


def draw_rounded_rect(dc: wx.DC, rect: wx.Rect, radius: int,
                      pen: Optional[wx.Pen] = None,
                      brush: Optional[wx.Brush] = None) -> None:
    """
    Draw a rounded rectangle.

    Args:
        dc: Device context to draw on
        rect: Rectangle bounds
        radius: Corner radius in pixels
        pen: Pen for outline (None = current pen)
        brush: Brush for fill (None = current brush)
    """
    if pen is not None:
        dc.SetPen(pen)
    if brush is not None:
        dc.SetBrush(brush)

    dc.DrawRoundedRectangle(rect.x, rect.y, rect.width, rect.height, radius)


def draw_handle(dc: wx.DC, x: int, y: int, size: int = 8,
               fill_color: wx.Colour = None,
               border_color: wx.Colour = None,
               border_width: int = 2) -> None:
    """
    Draw a resize handle (small square gizmo).

    Args:
        dc: Device context to draw on
        x: Center X coordinate
        y: Center Y coordinate
        size: Handle size in pixels (default 8)
        fill_color: Fill color (default white)
        border_color: Border color (default blue)
        border_width: Border width (default 2)
    """
    if fill_color is None:
        fill_color = wx.Colour(255, 255, 255)
    if border_color is None:
        border_color = wx.Colour(0, 120, 215)

    # Calculate handle rect (centered on x, y)
    half_size = size // 2
    handle_rect = wx.Rect(x - half_size, y - half_size, size, size)

    # Draw filled square
    dc.SetBrush(wx.Brush(fill_color))
    dc.SetPen(wx.Pen(border_color, border_width))
    dc.DrawRectangle(handle_rect)


def draw_handle_circle(dc: wx.DC, x: int, y: int, radius: int = 5,
                       fill_color: wx.Colour = None,
                       border_color: wx.Colour = None,
                       border_width: int = 2) -> None:
    """
    Draw a circular resize handle.

    Args:
        dc: Device context to draw on
        x: Center X coordinate
        y: Center Y coordinate
        radius: Handle radius in pixels (default 5)
        fill_color: Fill color (default white)
        border_color: Border color (default blue)
        border_width: Border width (default 2)
    """
    if fill_color is None:
        fill_color = wx.Colour(255, 255, 255)
    if border_color is None:
        border_color = wx.Colour(0, 120, 215)

    dc.SetBrush(wx.Brush(fill_color))
    dc.SetPen(wx.Pen(border_color, border_width))
    dc.DrawCircle(x, y, radius)


def calculate_text_rect(dc: wx.DC, text: str, font: Optional[wx.Font] = None) -> wx.Size:
    """
    Calculate the bounding box for text rendering.

    Args:
        dc: Device context (for font metrics)
        text: Text to measure
        font: Font to use (None = current font)

    Returns:
        wx.Size with width and height
    """
    if font is not None:
        dc.SetFont(font)

    width, height = dc.GetTextExtent(text)
    return wx.Size(width, height)


def draw_text_with_background(dc: wx.DC, text: str, x: int, y: int,
                              text_color: wx.Colour = None,
                              bg_color: wx.Colour = None,
                              padding: int = 4,
                              font: Optional[wx.Font] = None) -> wx.Rect:
    """
    Draw text with a background rectangle.

    Args:
        dc: Device context to draw on
        text: Text to draw
        x: X coordinate (top-left of background)
        y: Y coordinate (top-left of background)
        text_color: Text color (default black)
        bg_color: Background color (default white)
        padding: Padding around text (default 4px)
        font: Font to use (None = current font)

    Returns:
        wx.Rect of the drawn background rectangle
    """
    if text_color is None:
        text_color = wx.Colour(0, 0, 0)
    if bg_color is None:
        bg_color = wx.Colour(255, 255, 255)
    if font is not None:
        dc.SetFont(font)

    # Measure text
    text_size = calculate_text_rect(dc, text, font)

    # Calculate background rect
    bg_rect = wx.Rect(
        x, y,
        text_size.width + padding * 2,
        text_size.height + padding * 2
    )

    # Draw background
    dc.SetBrush(wx.Brush(bg_color))
    dc.SetPen(wx.TRANSPARENT_PEN)
    dc.DrawRectangle(bg_rect)

    # Draw text
    dc.SetTextForeground(text_color)
    dc.DrawText(text, x + padding, y + padding)

    return bg_rect


def scale_bitmap(bitmap: wx.Bitmap, width: int, height: int,
                quality: int = wx.IMAGE_QUALITY_HIGH) -> wx.Bitmap:
    """
    Scale a bitmap to new dimensions.

    Args:
        bitmap: Source bitmap
        width: Target width
        height: Target height
        quality: Scaling quality (wx.IMAGE_QUALITY_HIGH, wx.IMAGE_QUALITY_NORMAL, etc.)

    Returns:
        Scaled wx.Bitmap
    """
    image = bitmap.ConvertToImage()
    scaled_image = image.Scale(width, height, quality)
    return wx.Bitmap(scaled_image)


def create_thumbnail(bitmap: wx.Bitmap, max_size: int) -> wx.Bitmap:
    """
    Create a thumbnail from a bitmap, maintaining aspect ratio.

    Args:
        bitmap: Source bitmap
        max_size: Maximum width or height

    Returns:
        Thumbnail bitmap
    """
    width = bitmap.GetWidth()
    height = bitmap.GetHeight()

    # Calculate scaled dimensions
    if width > height:
        if width > max_size:
            new_width = max_size
            new_height = int(height * max_size / width)
        else:
            return bitmap
    else:
        if height > max_size:
            new_height = max_size
            new_width = int(width * max_size / height)
        else:
            return bitmap

    return scale_bitmap(bitmap, new_width, new_height)


def draw_selection_rect(dc: wx.DC, rect: wx.Rect,
                        color: wx.Colour = None,
                        width: int = 2,
                        dashed: bool = False) -> None:
    """
    Draw a selection rectangle (outline only).

    Args:
        dc: Device context to draw on
        rect: Rectangle to outline
        color: Border color (default blue)
        width: Border width (default 2)
        dashed: Use dashed line style
    """
    if color is None:
        color = wx.Colour(0, 120, 215)

    pen_style = wx.PENSTYLE_SHORT_DASH if dashed else wx.PENSTYLE_SOLID
    dc.SetPen(wx.Pen(color, width, pen_style))
    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    dc.DrawRectangle(rect)


def draw_focus_rect(dc: wx.DC, rect: wx.Rect) -> None:
    """
    Draw a focus rectangle (dotted outline).

    Args:
        dc: Device context to draw on
        rect: Rectangle to outline
    """
    dc.SetPen(wx.Pen(wx.BLACK, 1, wx.PENSTYLE_DOT))
    dc.SetBrush(wx.TRANSPARENT_BRUSH)
    dc.DrawRectangle(rect)


def point_in_rect(x: int, y: int, rect: wx.Rect, tolerance: int = 0) -> bool:
    """
    Check if a point is inside a rectangle (with optional tolerance).

    Args:
        x: Point X coordinate
        y: Point Y coordinate
        rect: Rectangle to test
        tolerance: Extra pixels to expand rectangle (for easier clicking)

    Returns:
        True if point is inside rectangle
    """
    if tolerance > 0:
        rect = wx.Rect(
            rect.x - tolerance,
            rect.y - tolerance,
            rect.width + tolerance * 2,
            rect.height + tolerance * 2
        )

    return rect.Contains(wx.Point(x, y))


def get_handle_rects(rect: wx.Rect, handle_size: int = 8) -> dict:
    """
    Calculate resize handle positions for a rectangle.

    Args:
        rect: Source rectangle
        handle_size: Size of handles (default 8)

    Returns:
        Dictionary with handle positions: 'tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r'
    """
    half_size = handle_size // 2

    # Corner handles
    tl = wx.Rect(rect.x - half_size, rect.y - half_size, handle_size, handle_size)
    tr = wx.Rect(rect.GetRight() - half_size, rect.y - half_size, handle_size, handle_size)
    bl = wx.Rect(rect.x - half_size, rect.GetBottom() - half_size, handle_size, handle_size)
    br = wx.Rect(rect.GetRight() - half_size, rect.GetBottom() - half_size, handle_size, handle_size)

    # Edge handles (center of each edge)
    t = wx.Rect(rect.x + rect.width // 2 - half_size, rect.y - half_size, handle_size, handle_size)
    b = wx.Rect(rect.x + rect.width // 2 - half_size, rect.GetBottom() - half_size, handle_size, handle_size)
    l = wx.Rect(rect.x - half_size, rect.y + rect.height // 2 - half_size, handle_size, handle_size)
    r = wx.Rect(rect.GetRight() - half_size, rect.y + rect.height // 2 - half_size, handle_size, handle_size)

    return {
        'tl': tl, 'tr': tr, 'bl': bl, 'br': br,
        't': t, 'b': b, 'l': l, 'r': r
    }


def get_cursor_for_handle(handle_name: str) -> wx.Cursor:
    """
    Get the appropriate resize cursor for a handle.

    Args:
        handle_name: Handle identifier ('tl', 'tr', 'bl', 'br', 't', 'b', 'l', 'r')

    Returns:
        wx.Cursor for the handle
    """
    cursor_map = {
        'tl': wx.CURSOR_SIZENWSE,  # Top-left
        'tr': wx.CURSOR_SIZENESW,  # Top-right
        'bl': wx.CURSOR_SIZENESW,  # Bottom-left
        'br': wx.CURSOR_SIZENWSE,  # Bottom-right
        't': wx.CURSOR_SIZENS,     # Top
        'b': wx.CURSOR_SIZENS,     # Bottom
        'l': wx.CURSOR_SIZEWE,     # Left
        'r': wx.CURSOR_SIZEWE,     # Right
    }

    return wx.Cursor(cursor_map.get(handle_name, wx.CURSOR_ARROW))


def blend_color(color1: wx.Colour, color2: wx.Colour, ratio: float) -> wx.Colour:
    """
    Blend two colors together.

    Args:
        color1: First color
        color2: Second color
        ratio: Blend ratio (0.0 = color1, 1.0 = color2)

    Returns:
        Blended color
    """
    ratio = max(0.0, min(1.0, ratio))

    r = int(color1.Red() * (1 - ratio) + color2.Red() * ratio)
    g = int(color1.Green() * (1 - ratio) + color2.Green() * ratio)
    b = int(color1.Blue() * (1 - ratio) + color2.Blue() * ratio)
    a = int(color1.Alpha() * (1 - ratio) + color2.Alpha() * ratio)

    return wx.Colour(r, g, b, a)
