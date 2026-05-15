"""Shared wx desktop design-system primitives.

This module keeps recorder, editor, and dialogs on the same dark component
language without introducing a web-stack dependency.
"""

from __future__ import annotations

import math

import wx

from ui.theme import Colors, Fonts, Sizes, ThemedDialog


def _as_colour(value, fallback: wx.Colour) -> wx.Colour:
    if value is None:
        return fallback
    if isinstance(value, wx.Colour):
        return value
    if isinstance(value, (tuple, list)):
        return wx.Colour(*value)
    return wx.Colour(value)


def _stroke(gc: wx.GraphicsContext, colour: wx.Colour, width: float = 1.8):
    info = wx.GraphicsPenInfo(colour).Width(width).Cap(wx.CAP_ROUND).Join(wx.JOIN_ROUND)
    gc.SetPen(gc.CreatePen(info))
    gc.SetBrush(wx.NullGraphicsBrush)


def _fill(gc: wx.GraphicsContext, colour: wx.Colour):
    gc.SetPen(wx.NullGraphicsPen)
    gc.SetBrush(gc.CreateBrush(wx.Brush(colour)))


def draw_symbol_icon(gc: wx.GraphicsContext, icon_type: str, x: float, y: float, size: float, colour: wx.Colour) -> bool:
    """Draw a small monoline/fill icon into an existing graphics context."""
    cx = x + size / 2
    cy = y + size / 2
    m = max(2.0, size * 0.18)
    line = max(1.5, size / 13)

    if icon_type == "record":
        _fill(gc, colour)
        r = size * 0.28
        gc.DrawEllipse(cx - r, cy - r, r * 2, r * 2)
        return True

    if icon_type == "stop":
        _fill(gc, colour)
        side = size * 0.52
        gc.DrawRoundedRectangle(cx - side / 2, cy - side / 2, side, side, max(1.5, size * 0.08))
        return True

    if icon_type == "play":
        _fill(gc, colour)
        path = gc.CreatePath()
        path.MoveToPoint(x + size * 0.34, y + size * 0.24)
        path.AddLineToPoint(x + size * 0.34, y + size * 0.76)
        path.AddLineToPoint(x + size * 0.76, cy)
        path.CloseSubpath()
        gc.FillPath(path)
        return True

    if icon_type == "pause":
        _fill(gc, colour)
        bar_w = size * 0.16
        bar_h = size * 0.52
        gap = size * 0.13
        gc.DrawRoundedRectangle(cx - gap - bar_w, cy - bar_h / 2, bar_w, bar_h, max(1.5, bar_w / 2))
        gc.DrawRoundedRectangle(cx + gap, cy - bar_h / 2, bar_w, bar_h, max(1.5, bar_w / 2))
        return True

    if icon_type == "cursor":
        _stroke(gc, colour, line)
        path = gc.CreatePath()
        path.MoveToPoint(x + size * 0.24, y + size * 0.18)
        path.AddLineToPoint(x + size * 0.70, y + size * 0.64)
        path.MoveToPoint(x + size * 0.24, y + size * 0.18)
        path.AddLineToPoint(x + size * 0.25, y + size * 0.52)
        path.MoveToPoint(x + size * 0.24, y + size * 0.18)
        path.AddLineToPoint(x + size * 0.58, y + size * 0.18)
        gc.StrokePath(path)
        _fill(gc, colour)
        gc.DrawEllipse(x + size * 0.60, y + size * 0.58, size * 0.16, size * 0.16)
        return True

    if icon_type == "region":
        _stroke(gc, colour, line)
        r = max(2.0, size * 0.12)
        gc.DrawRoundedRectangle(x + m, y + m, size - m * 2, size - m * 2, r)
        gc.StrokeLine(x + size * 0.18, y + size * 0.50, x + size * 0.06, y + size * 0.50)
        gc.StrokeLine(x + size * 0.94, y + size * 0.50, x + size * 0.82, y + size * 0.50)
        gc.StrokeLine(x + size * 0.50, y + size * 0.18, x + size * 0.50, y + size * 0.06)
        gc.StrokeLine(x + size * 0.50, y + size * 0.94, x + size * 0.50, y + size * 0.82)
        return True

    if icon_type == "settings":
        _stroke(gc, colour, line)
        root_radius = size * 0.31
        tooth_radius = size * 0.42
        path = gc.CreatePath()
        for idx in range(16):
            angle = -math.pi / 2 + math.tau * idx / 16
            radius = tooth_radius if idx % 2 == 0 else root_radius
            px = cx + math.cos(angle) * radius
            py = cy + math.sin(angle) * radius
            if idx == 0:
                path.MoveToPoint(px, py)
            else:
                path.AddLineToPoint(px, py)
        path.CloseSubpath()
        gc.StrokePath(path)
        gc.DrawEllipse(cx - size * 0.15, cy - size * 0.15, size * 0.30, size * 0.30)
        return True

    if icon_type == "help":
        _stroke(gc, colour, line)
        gc.DrawEllipse(x + m, y + m, size - m * 2, size - m * 2)
        path = gc.CreatePath()
        path.MoveToPoint(cx - size * 0.14, cy - size * 0.14)
        path.AddCurveToPoint(cx - size * 0.10, y + size * 0.28, cx + size * 0.18, y + size * 0.28, cx + size * 0.18, cy - size * 0.04)
        path.AddCurveToPoint(cx + size * 0.18, cy + size * 0.10, cx, cy + size * 0.10, cx, cy + size * 0.20)
        gc.StrokePath(path)
        _fill(gc, colour)
        gc.DrawEllipse(cx - size * 0.035, y + size * 0.70, size * 0.07, size * 0.07)
        return True

    if icon_type == "gpu":
        _stroke(gc, colour, line)
        body = size * 0.50
        gc.DrawRoundedRectangle(cx - body / 2, cy - body / 2, body, body, size * 0.08)
        for offset in (-0.26, 0, 0.26):
            gc.StrokeLine(cx - body / 2 - size * 0.12, cy + size * offset, cx - body / 2, cy + size * offset)
            gc.StrokeLine(cx + body / 2, cy + size * offset, cx + body / 2 + size * 0.12, cy + size * offset)
            gc.StrokeLine(cx + size * offset, cy - body / 2 - size * 0.12, cx + size * offset, cy - body / 2)
            gc.StrokeLine(cx + size * offset, cy + body / 2, cx + size * offset, cy + body / 2 + size * 0.12)
        return True

    return False


class CommandButton(wx.Control):
    """Shared owner-drawn command button with optional vector icon."""

    def __init__(
        self,
        parent,
        label: str = "",
        size=wx.DefaultSize,
        *,
        icon_type: str | None = None,
        icon_size: int = 18,
        bg_color=None,
        fg_color=None,
        hover_color=None,
        pressed_color=None,
        border_color=None,
        corner_radius: int = Sizes.CORNER_RADIUS,
        id=wx.ID_ANY,
    ):
        if size == wx.DefaultSize:
            size = (86, 32) if label else (36, 32)
        self._base_size = self._normalize_base_size(size)
        super().__init__(parent, id, pos=wx.DefaultPosition, size=size, style=wx.BORDER_NONE)
        self._label = label
        self._icon_type = icon_type
        self._icon_size = icon_size
        self._corner_radius = corner_radius
        self._enabled = True
        self._hovered = False
        self._pressed = False
        self._bg_color = _as_colour(bg_color, Colors.BG_INPUT_DARK)
        self._fg_color = _as_colour(fg_color, Colors.TEXT_PRIMARY)
        self._hover_color = _as_colour(hover_color, Colors.BG_HOVER)
        self._pressed_color = _as_colour(pressed_color, Colors.BG_PRESSED)
        self._border_color = _as_colour(border_color, Colors.BORDER_SOFT)
        self._cached_bmp = None
        self._cached_state = None
        self._skip_auto_theme = True

        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=bool(label and icon_type)))
        self._sync_min_size_to_content()

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _event: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    def SetLabel(self, label):
        self._label = str(label)
        self._cached_bmp = None
        self._sync_min_size_to_content()
        self.Refresh()

    def GetLabel(self):
        return self._label

    def SetIconType(self, icon_type: str | None):
        self._icon_type = icon_type
        self._cached_bmp = None
        self._sync_min_size_to_content()
        self.Refresh()

    def SetBackgroundColour(self, colour):
        self._bg_color = _as_colour(colour, Colors.BG_INPUT_DARK)
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetForegroundColour(self, colour):
        self._fg_color = _as_colour(colour, Colors.TEXT_PRIMARY)
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetHoverColour(self, colour):
        self._hover_color = _as_colour(colour, Colors.BG_HOVER)
        self._cached_bmp = None

    def SetPressedColour(self, colour):
        self._pressed_color = _as_colour(colour, Colors.BG_PRESSED)
        self._cached_bmp = None

    def SetBorderColour(self, colour):
        self._border_color = _as_colour(colour, Colors.BORDER_SOFT)
        self._cached_bmp = None
        self.Refresh()
        return True

    def Enable(self, enable=True):
        self._enabled = bool(enable)
        changed = super().Enable(enable)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND if enable else wx.CURSOR_ARROW))
        self._hovered = False
        self._pressed = False
        self._cached_bmp = None
        self.Refresh()
        return changed

    def Disable(self):
        self.Enable(False)

    def IsEnabled(self):
        return self._enabled

    def _normalize_base_size(self, size) -> tuple[int, int]:
        if isinstance(size, wx.Size):
            width, height = size.width, size.height
        elif isinstance(size, tuple) and len(size) == 2:
            width, height = size
        else:
            width, height = 86, 32
        return max(0, int(width)), max(1, int(height) if int(height) > 0 else 32)

    def _sync_min_size_to_content(self):
        text_w = 0
        if self._label:
            dc = wx.ClientDC(self)
            dc.SetFont(self.GetFont())
            text_w = dc.GetTextExtent(self._label).width
        icon_w = self._icon_size if self._icon_type else 0
        gap = 6 if self._icon_type and self._label else 0
        horizontal_padding = 18 if self._label else 12
        min_w = max(self._base_size[0], int(text_w + icon_w + gap + horizontal_padding))
        min_h = self._base_size[1]
        if self.GetMinSize() != wx.Size(min_w, min_h):
            self.SetMinSize((min_w, min_h))
            parent = self.GetParent()
            if parent:
                parent.Layout()

    def _on_enter(self, _event):
        if not self._enabled:
            return
        self._hovered = True
        self.Refresh()

    def _on_leave(self, _event):
        self._hovered = False
        self._pressed = False
        self.Refresh()

    def _on_left_down(self, _event):
        if not self._enabled:
            return
        self._pressed = True
        self.CaptureMouse()
        self.Refresh()

    def _on_left_up(self, _event):
        if self.HasCapture():
            self.ReleaseMouse()
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        if was_pressed and self._enabled and self._hovered:
            event = wx.CommandEvent(wx.wxEVT_COMMAND_BUTTON_CLICKED, self.GetId())
            event.SetEventObject(self)
            self.GetEventHandler().ProcessEvent(event)

    def _on_paint(self, _event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        state_key = (
            w, h, self._hovered, self._pressed, self._enabled, self._label,
            self._icon_type, self._bg_color.Get(), self._fg_color.Get(),
            self._hover_color.Get(), self._pressed_color.Get(), self._border_color.Get(),
        )
        if self._cached_bmp is not None and self._cached_state == state_key:
            dc.DrawBitmap(self._cached_bmp, 0, 0, False)
            return

        bmp = wx.Bitmap(w, h)
        mem = wx.MemoryDC(bmp)
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.BG_CARD
        mem.SetBackground(wx.Brush(parent_bg))
        mem.Clear()

        gc = wx.GraphicsContext.Create(mem)
        if gc:
            if not self._enabled:
                bg = Colors.BTN_DISABLED_BG
                fg = Colors.BTN_DISABLED_FG
            elif self._pressed:
                bg = self._pressed_color
                fg = self._fg_color
            elif self._hovered:
                bg = self._hover_color
                fg = self._fg_color
            else:
                bg = self._bg_color
                fg = self._fg_color

            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.Pen(Colors.BORDER_HOVER if self._hovered and self._enabled else self._border_color, 1))
            inset = 0.5
            gc.DrawRoundedRectangle(inset, inset, w - 1, h - 1, self._corner_radius)

            gc.SetFont(self.GetFont(), fg)
            text_w = text_h = 0
            if self._label:
                text_w, text_h = gc.GetTextExtent(self._label)[:2]
            icon_w = self._icon_size if self._icon_type else 0
            gap = 6 if self._icon_type and self._label else 0
            total_w = icon_w + gap + text_w
            start_x = (w - total_w) / 2
            if self._icon_type:
                iy = (h - self._icon_size) / 2
                draw_symbol_icon(gc, self._icon_type, start_x, iy, self._icon_size, fg)
                start_x += icon_w + gap
            if self._label:
                gc.DrawText(self._label, start_x, (h - text_h) / 2)

        mem.SelectObject(wx.NullBitmap)
        self._cached_bmp = bmp
        self._cached_state = state_key
        dc.DrawBitmap(bmp, 0, 0, False)


class RailIcon(wx.Control):
    """Small non-clickable rail icon used next to switches and labels."""

    def __init__(self, parent, icon_type: str, tooltip: str = "", size=(24, 24)):
        super().__init__(parent, wx.ID_ANY, size=size, style=wx.BORDER_NONE)
        self._icon_type = icon_type
        self._cached_bmp = None
        self._cached_state = None
        self._skip_auto_theme = True
        self.SetToolTip(tooltip)
        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _event: None)

    def SetToolTip(self, tooltip):  # keep a narrow wx-compatible surface for tests and callers
        return super().SetToolTip(tooltip)

    def _on_paint(self, _event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.RAIL_BG
        state_key = (w, h, parent_bg.Get(), self._icon_type)
        if self._cached_bmp is not None and self._cached_state == state_key:
            dc.DrawBitmap(self._cached_bmp, 0, 0, False)
            return
        bmp = wx.Bitmap(w, h)
        mem = wx.MemoryDC(bmp)
        mem.SetBackground(wx.Brush(parent_bg))
        mem.Clear()
        gc = wx.GraphicsContext.Create(mem)
        if gc:
            edge = min(w, h) - 4
            draw_symbol_icon(gc, self._icon_type, (w - edge) / 2, (h - edge) / 2, edge, Colors.TEXT_PRIMARY)
        mem.SelectObject(wx.NullBitmap)
        self._cached_bmp = bmp
        self._cached_state = state_key
        dc.DrawBitmap(bmp, 0, 0, False)


class StatusPill(wx.Panel):
    """Compact semantic status surface for recorder/editor status rows."""

    _PALETTE = {
        "ready": (Colors.BG_INPUT_DARK, Colors.TEXT_SECONDARY),
        "success": (Colors.SUCCESS, Colors.BG_PRIMARY),
        "warning": (Colors.WARNING, Colors.BG_PRIMARY),
        "error": (Colors.DANGER, Colors.BG_PRIMARY),
        "info": (Colors.ACCENT, Colors.BG_PRIMARY),
    }

    def __init__(self, parent, label: str = "", status: str = "ready"):
        super().__init__(parent)
        self._label = wx.StaticText(self, label=label)
        self._label.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT, bold=True))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self._label, 0, wx.ALIGN_CENTER_VERTICAL | wx.LEFT | wx.RIGHT, 10)
        self.SetSizer(sizer)
        self.SetMinSize((-1, 24))
        self.set_status(status, label)

    def set_status(self, status: str, label: str | None = None):
        bg, fg = self._PALETTE.get(status, self._PALETTE["ready"])
        if label is not None:
            self._label.SetLabel(label)
        self.SetBackgroundColour(bg)
        self._label.SetForegroundColour(fg)
        self.Layout()


class InlineBanner(wx.Panel):
    """Inline feedback banner for recoverable validation and status messages."""

    _BORDER = {
        "info": Colors.ACCENT,
        "warning": Colors.WARNING,
        "error": Colors.DANGER,
        "success": Colors.SUCCESS,
    }

    def __init__(self, parent, message: str = "", tone: str = "info"):
        super().__init__(parent)
        self._tone = tone
        self._message = wx.StaticText(self, label=message)
        self._message.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._message.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        sizer.Add(self._message, 1, wx.ALL | wx.ALIGN_CENTER_VERTICAL, 8)
        self.SetSizer(sizer)
        self.SetBackgroundColour(Colors.BG_PANEL)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.Bind(wx.EVT_PAINT, self._on_paint)

    def set_message(self, message: str, tone: str = "info"):
        self._tone = tone
        self._message.SetLabel(message)
        self.Refresh()
        self.Layout()

    def _on_paint(self, event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return
        gc = wx.GraphicsContext.Create(dc)
        if not gc:
            return
        gc.SetBrush(wx.Brush(Colors.BG_PANEL))
        gc.SetPen(wx.Pen(self._BORDER.get(self._tone, Colors.ACCENT), 1))
        gc.DrawRoundedRectangle(0.5, 0.5, w - 1, h - 1, Sizes.CORNER_RADIUS)


class ThemedProgressDialog(ThemedDialog):
    """Dark themed ProgressDialog-compatible surface for dependency flows."""

    def __init__(self, title: str, message: str, maximum: int = 100, parent=None, style: int = 0):
        super().__init__(parent, title=title, size=(430, 166), style=wx.DEFAULT_DIALOG_STYLE)
        self._maximum = max(1, int(maximum))
        self._value = 0
        self._cancelled = False
        self.SetBackgroundColour(Colors.BG_PANEL)

        sizer = wx.BoxSizer(wx.VERTICAL)
        self._message = wx.StaticText(self, label=message)
        self._message.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._message.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        self._message.Wrap(380)
        sizer.Add(self._message, 0, wx.EXPAND | wx.ALL, 14)

        self._gauge = wx.Gauge(self, range=self._maximum, style=wx.GA_HORIZONTAL)
        self._gauge.SetValue(0)
        sizer.Add(self._gauge, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        if style & getattr(wx, "PD_CAN_ABORT", 0):
            self._cancel_btn = CommandButton(self, label="Cancel", size=(96, 30))
            self._cancel_btn.Bind(wx.EVT_BUTTON, self._on_cancel)
            row = wx.BoxSizer(wx.HORIZONTAL)
            row.AddStretchSpacer()
            row.Add(self._cancel_btn, 0)
            sizer.Add(row, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 14)

        self.SetSizer(sizer)
        self.CenterOnParent()
        self.Show()
        self.Update()

    def _on_cancel(self, _event):
        self._cancelled = True

    def GetValue(self):
        return self._value

    def Update(self, value: int | None = None, newmsg: str | None = None):
        if value is not None:
            self._value = max(0, min(self._maximum, int(value)))
            self._gauge.SetValue(self._value)
        if newmsg is not None:
            self._message.SetLabel(str(newmsg))
            self._message.Wrap(380)
        self.Layout()
        return not self._cancelled, False

    def Pulse(self, newmsg: str | None = None):
        self._value = (self._value + 7) % self._maximum
        self._gauge.SetValue(self._value)
        if newmsg is not None:
            self._message.SetLabel(str(newmsg))
            self._message.Wrap(380)
        self.Layout()
        return not self._cancelled, False


class FormRow(wx.Panel):
    """A label + control row with consistent label column width.

    Replaces the repeated ``wx.StaticText.SetMinSize((130, -1))`` + manual
    BoxSizer pattern. The label column width is a single shared constant.
    """

    LABEL_COL_WIDTH = 140

    def __init__(self, parent, label: str, control: wx.Window):
        super().__init__(parent)
        # 생성 시점의 부모 배경을 상속. 부모 배경이 이후 바뀌면 Refresh() 필요.
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self._label_text: wx.StaticText | None = None
        sizer = wx.BoxSizer(wx.HORIZONTAL)
        if label:
            text = wx.StaticText(self, label=label)
            text.SetForegroundColour(Colors.TEXT_SECONDARY)
            text.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            text.SetMinSize((self.LABEL_COL_WIDTH, -1))
            sizer.Add(text, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
            self._label_text = text
        if control.GetParent() is not self:
            control.Reparent(self)
        sizer.Add(control, 1, wx.ALIGN_CENTER_VERTICAL)
        self.SetSizer(sizer)

    def set_label(self, text: str) -> None:
        """Update the label column text (for live retranslation)."""
        if self._label_text is not None:
            self._label_text.SetLabel(text)


class FormSection(wx.Panel):
    """A titled content group: bold section title + optional description +
    vertically stacked rows. Replaces wx.StaticBox/StaticBoxSizer chrome with
    spacing+heading hierarchy (audit P1)."""

    def __init__(self, parent, title: str, description: str = ""):
        super().__init__(parent)
        # 생성 시점의 부모 배경을 상속. 부모 배경이 이후 바뀌면 Refresh() 필요.
        self.SetBackgroundColour(parent.GetBackgroundColour())
        self._sizer = wx.BoxSizer(wx.VERTICAL)
        self._heading: wx.StaticText = wx.StaticText(self, label=title)
        self._heading.SetForegroundColour(Colors.TEXT_PRIMARY)
        self._heading.SetFont(Fonts.get_font(Fonts.SIZE_LABEL, bold=True))
        self._sizer.Add(self._heading, 0, wx.BOTTOM, 6)
        if description:
            desc = wx.StaticText(self, label=description)
            desc.SetForegroundColour(Colors.TEXT_SECONDARY)
            desc.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
            self._sizer.Add(desc, 0, wx.BOTTOM, 8)
        self.SetSizer(self._sizer)

    def set_title(self, title: str) -> None:
        """Update the section heading text (for live retranslation)."""
        self._heading.SetLabel(title)

    def add(self, window: wx.Window, *, gap: int = 6):
        """Add *window* to this section's vertical stack.

        *window* is reparented into this FormSection if it is not already a
        child. Returns *window*.
        """
        if window.GetParent() is not self:
            window.Reparent(self)
        self._sizer.Add(window, 0, wx.EXPAND | wx.BOTTOM, gap)
        return window

    def add_row(self, label: str, control: wx.Window, *, gap: int = 6) -> "FormRow":
        """Wrap *control* in a FormRow and add it to this section.

        Returns the FormRow (not *control*) — store it to call set_label() later.
        """
        row = FormRow(self, label, control)
        return self.add(row, gap=gap)
