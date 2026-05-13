"""Small owner-drawn controls for dark wx/MSW tool surfaces.

Architecture note: this module is a wx-only shared widget surface in `ui/`.
Both `main.py` and `editor/__main__.py` import it. The cross-package import
from `editor/` is sanctioned by `.claude/rules/architecture-boundaries.md`
("editor/ → ui/ 공유 위젯 import 정책").
"""

from __future__ import annotations

import contextlib
from collections.abc import Iterable

import wx

from ui.theme import Colors, Fonts


# msw.dark-mode value used by wx 4.2.x to opt-in to native dark frame chrome.
# Centralised here so the `wx` magic number lives in one place.
_MSW_DARK_MODE_VALUE = 2


def enable_msw_dark_mode(target_wx=wx) -> None:
    """Opt the current process into wx's MSW dark frame chrome.

    No-op on non-Windows platforms and silently tolerates wx builds that omit
    the option. Safe to call multiple times — wx coalesces the option write.
    """
    import sys
    if sys.platform != 'win32':
        return
    with contextlib.suppress(Exception):
        target_wx.SystemOptions.SetOption("msw.dark-mode", _MSW_DARK_MODE_VALUE)


class DarkSelect(wx.Control):
    """Compact read-only/selectable combo replacement.

    The native wx.ComboBox on MSW can ignore custom dark backgrounds. This
    control keeps the same small API surface used by XGif while drawing the
    closed field itself.
    """

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        value="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        choices: Iterable[str] | None = None,
        style=0,
        **_kwargs,
    ):
        if size == wx.DefaultSize:
            size = (86, 26)
        elif isinstance(size, tuple) and len(size) == 2 and size[1] == -1:
            size = (size[0], 26)
        super().__init__(parent, id, pos=pos, size=size, style=wx.BORDER_NONE)
        self._choices = [str(item) for item in (choices or [])]
        self._selection = -1
        self._value = str(value or "")
        self._editable = bool(style & wx.CB_DROPDOWN) and not bool(style & wx.CB_READONLY)
        self._hovered = False
        self._pressed = False
        self._bg = Colors.BG_INPUT_DARK
        self._fg = Colors.TEXT_PRIMARY
        self._border = Colors.BORDER
        self._cached_bmp = None
        self._cached_state = None
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))
        if self._choices and not self._value:
            self.SetSelection(0)

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _e: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)

    def SetBackgroundColour(self, colour):
        self._bg = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetForegroundColour(self, colour):
        self._fg = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetBorderColour(self, colour):
        self._border = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def Enable(self, enable=True):
        changed = super().Enable(enable)
        self._hovered = False
        self._pressed = False
        self._cached_bmp = None
        self.Refresh()
        return changed

    def Clear(self):
        self._choices.clear()
        self._selection = -1
        self._value = ""
        self._cached_bmp = None
        self.Refresh()

    def Append(self, item, *_args):
        self._choices.append(str(item))
        if self._selection < 0:
            self.SetSelection(0)
        return len(self._choices) - 1

    def AppendItems(self, items):
        for item in items:
            self.Append(item)

    def SetItems(self, items):
        self.Clear()
        self.AppendItems(items)

    def GetCount(self):
        return len(self._choices)

    def FindString(self, text):
        text = str(text)
        for idx, item in enumerate(self._choices):
            if item == text:
                return idx
        return wx.NOT_FOUND

    def SetSelection(self, index):
        if 0 <= index < len(self._choices):
            self._selection = index
            self._value = self._choices[index]
        else:
            self._selection = -1
            self._value = ""
        self._cached_bmp = None
        self.Refresh()

    def GetSelection(self):
        return self._selection

    def SetValue(self, value):
        value = str(value)
        self._value = value
        self._selection = self.FindString(value)
        self._cached_bmp = None
        self.Refresh()

    def GetValue(self):
        return self._value

    def SetStringSelection(self, value):
        idx = self.FindString(value)
        if idx == wx.NOT_FOUND:
            return False
        self.SetSelection(idx)
        return True

    def GetStringSelection(self):
        return self._value

    def GetBestSize(self):
        return wx.Size(max(70, self.GetMinSize().GetWidth()), 26)

    def _on_enter(self, _event):
        if not self.IsEnabled():
            return
        self._hovered = True
        self.Refresh()

    def _on_leave(self, _event):
        self._hovered = False
        self._pressed = False
        self.Refresh()

    def _on_left_down(self, _event):
        if not self.IsEnabled():
            return
        self._pressed = True
        self.CaptureMouse()
        self.Refresh()

    def _on_left_up(self, event):
        if not self.IsEnabled():
            return
        if self.HasCapture():
            self.ReleaseMouse()
        was_pressed = self._pressed
        self._pressed = False
        self.Refresh()
        if not was_pressed:
            return
        if self._editable and event.GetX() < max(0, self.GetSize().width - 28):
            self._edit_value()
        else:
            self._show_menu()

    def _edit_value(self):
        dlg = wx.TextEntryDialog(self, "", "", self._value)
        dlg.SetBackgroundColour(Colors.BG_PANEL)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                self.SetValue(dlg.GetValue())
                self._emit(wx.wxEVT_TEXT_ENTER)
                self._emit(wx.wxEVT_COMBOBOX)
        finally:
            dlg.Destroy()

    def _show_menu(self):
        if not self._choices:
            return
        menu = wx.Menu()
        for idx, item in enumerate(self._choices):
            menu_item = menu.Append(wx.ID_ANY, item)
            menu.Bind(
                wx.EVT_MENU,
                lambda _event, i=idx: self._choose(i),
                id=menu_item.GetId(),
            )
        self.PopupMenu(menu)
        menu.Destroy()

    def _choose(self, index):
        if index == self._selection:
            return
        self.SetSelection(index)
        self._emit(wx.wxEVT_COMBOBOX)

    def _emit(self, event_type):
        event = wx.CommandEvent(event_type, self.GetId())
        event.SetEventObject(self)
        event.SetString(self._value)
        event.SetInt(self._selection)
        self.GetEventHandler().ProcessEvent(event)

    def _on_paint(self, _event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        enabled = self.IsEnabled()
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.BG_CARD
        state_key = (
            w, h, self._hovered, self._pressed, enabled, self._value,
            self._bg.Get(), self._fg.Get(), self._border.Get(),
            parent_bg.Get() if hasattr(parent_bg, 'Get') else tuple(parent_bg),
        )
        if self._cached_bmp is not None and self._cached_state == state_key:
            dc.DrawBitmap(self._cached_bmp, 0, 0, False)
            return

        bmp = wx.Bitmap(w, h)
        mem = wx.MemoryDC(bmp)
        mem.SetBackground(wx.Brush(parent_bg))
        mem.Clear()

        gc = wx.GraphicsContext.Create(mem)
        if gc:
            bg = Colors.BG_SUNKEN if not enabled else Colors.BG_HOVER if self._hovered else self._bg
            fg = self._fg if enabled else Colors.TEXT_MUTED
            border = Colors.BORDER_HOVER if self._hovered and enabled else self._border
            if self._pressed and enabled:
                bg = Colors.BG_PRESSED
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.Pen(border, 1))
            gc.DrawRoundedRectangle(0.5, 0.5, w - 1, h - 1, 4)
            gc.SetFont(self.GetFont(), fg)
            text = self._value
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, 8, (h - th) / 2)
            pen = wx.Pen(Colors.TEXT_SECONDARY if enabled else Colors.TEXT_MUTED, 1)
            gc.SetPen(pen)
            path = gc.CreatePath()
            ax = w - 15
            ay = h / 2 + 1
            path.MoveToPoint(ax - 4, ay - 3)
            path.AddLineToPoint(ax, ay + 2)
            path.AddLineToPoint(ax + 4, ay - 3)
            gc.StrokePath(path)

        mem.SelectObject(wx.NullBitmap)
        self._cached_bmp = bmp
        self._cached_state = state_key
        dc.DrawBitmap(bmp, 0, 0, False)


class DarkSpinCtrl(wx.Control):
    """Compact owner-drawn numeric field with step buttons."""

    _double = False

    def __init__(
        self,
        parent,
        id=wx.ID_ANY,
        value="",
        pos=wx.DefaultPosition,
        size=wx.DefaultSize,
        min=0,
        max=100,
        initial=0,
        inc=1,
        **_kwargs,
    ):
        if size == wx.DefaultSize:
            size = (70, 26)
        elif isinstance(size, tuple) and len(size) == 2 and size[1] == -1:
            size = (size[0], 26)
        super().__init__(parent, id, pos=pos, size=size, style=wx.BORDER_NONE)
        self._min = min
        self._max = max
        self._inc = inc
        self._digits = 0
        self._hovered = False
        self._pressed_part = None
        self._value = self._coerce(value if value != "" else initial)
        self._bg = Colors.BG_INPUT_DARK
        self._fg = Colors.TEXT_PRIMARY
        self._border = Colors.BORDER_SOFT
        self._cached_bmp = None
        self._cached_state = None
        self.SetFont(Fonts.get_font(Fonts.SIZE_DEFAULT))
        self.SetMinSize(size)
        self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
        self.SetCursor(wx.Cursor(wx.CURSOR_HAND))

        self.Bind(wx.EVT_PAINT, self._on_paint)
        self.Bind(wx.EVT_ERASE_BACKGROUND, lambda _e: None)
        self.Bind(wx.EVT_ENTER_WINDOW, self._on_enter)
        self.Bind(wx.EVT_LEAVE_WINDOW, self._on_leave)
        self.Bind(wx.EVT_LEFT_DOWN, self._on_left_down)
        self.Bind(wx.EVT_LEFT_UP, self._on_left_up)
        self.Bind(wx.EVT_MOUSEWHEEL, self._on_wheel)

    def SetBackgroundColour(self, colour):
        self._bg = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetForegroundColour(self, colour):
        self._fg = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def SetBorderColour(self, colour):
        self._border = colour
        self._cached_bmp = None
        self.Refresh()
        return True

    def Enable(self, enable=True):
        changed = super().Enable(enable)
        self._hovered = False
        self._pressed_part = None
        self._cached_bmp = None
        self.Refresh()
        return changed

    def SetRange(self, minimum, maximum):
        self._min = minimum
        self._max = maximum
        self.SetValue(self._value)

    def SetMin(self, minimum):
        self._min = minimum
        self.SetValue(self._value)

    def SetMax(self, maximum):
        self._max = maximum
        self.SetValue(self._value)

    def GetMin(self):
        return self._min

    def GetMax(self):
        return self._max

    def SetIncrement(self, increment):
        self._inc = increment

    def SetDigits(self, digits):
        self._digits = int(digits)
        self._cached_bmp = None
        self.Refresh()

    def GetValue(self):
        return self._value if self._double else int(round(self._value))

    def SetValue(self, value):
        self._value = self._coerce(value)
        self._cached_bmp = None
        self.Refresh()

    def GetBestSize(self):
        return wx.Size(max(62, self.GetMinSize().GetWidth()), 26)

    def _coerce(self, value):
        with contextlib.suppress(TypeError, ValueError):
            number = float(value)
            number = max(self._min, min(self._max, number))
            if self._double:
                return number
            return int(round(number))
        return self._min

    def _format_value(self):
        if self._double:
            return f"{self._value:.{self._digits}f}"
        return str(int(round(self._value)))

    def _part_at(self, x, y):
        w, h = self.GetClientSize()
        if x >= w - 20:
            return "up" if y < h / 2 else "down"
        return "edit"

    def _on_enter(self, _event):
        if not self.IsEnabled():
            return
        self._hovered = True
        self.Refresh()

    def _on_leave(self, _event):
        self._hovered = False
        self._pressed_part = None
        self.Refresh()

    def _on_left_down(self, event):
        if not self.IsEnabled():
            return
        self._pressed_part = self._part_at(event.GetX(), event.GetY())
        self.CaptureMouse()
        self.Refresh()

    def _on_left_up(self, event):
        if not self.IsEnabled():
            return
        if self.HasCapture():
            self.ReleaseMouse()
        part = self._pressed_part
        self._pressed_part = None
        self.Refresh()
        if part == "up":
            self._step(1)
        elif part == "down":
            self._step(-1)
        elif part == "edit":
            self._edit_value()

    def _on_wheel(self, event):
        if not self.IsEnabled():
            return
        self._step(1 if event.GetWheelRotation() > 0 else -1)

    def _step(self, direction):
        before = self._value
        self._value = self._coerce(self._value + self._inc * direction)
        if self._value != before:
            self.Refresh()
            self._emit_change()

    def _edit_value(self):
        dlg = wx.TextEntryDialog(self, "", "", self._format_value())
        dlg.SetBackgroundColour(Colors.BG_PANEL)
        try:
            if dlg.ShowModal() == wx.ID_OK:
                before = self._value
                self._value = self._coerce(dlg.GetValue())
                self.Refresh()
                if self._value != before:
                    self._emit_change()
        finally:
            dlg.Destroy()

    def _emit_change(self):
        spin_type = wx.wxEVT_SPINCTRLDOUBLE if self._double else wx.wxEVT_SPINCTRL
        for event_type in (spin_type, wx.wxEVT_TEXT):
            event = wx.CommandEvent(event_type, self.GetId())
            event.SetEventObject(self)
            event.SetString(self._format_value())
            self.GetEventHandler().ProcessEvent(event)

    def _on_paint(self, _event):
        dc = wx.PaintDC(self)
        w, h = self.GetClientSize()
        if w <= 0 or h <= 0:
            return

        enabled = self.IsEnabled()
        parent = self.GetParent()
        parent_bg = parent.GetBackgroundColour() if parent else Colors.BG_CARD
        text = self._format_value()
        state_key = (
            w, h, self._hovered, self._pressed_part, enabled, text,
            self._bg.Get(), self._fg.Get(), self._border.Get(),
            parent_bg.Get() if hasattr(parent_bg, 'Get') else tuple(parent_bg),
        )
        if self._cached_bmp is not None and self._cached_state == state_key:
            dc.DrawBitmap(self._cached_bmp, 0, 0, False)
            return

        bmp = wx.Bitmap(w, h)
        mem = wx.MemoryDC(bmp)
        mem.SetBackground(wx.Brush(parent_bg))
        mem.Clear()

        gc = wx.GraphicsContext.Create(mem)
        if gc:
            bg = Colors.BG_SUNKEN if not enabled else Colors.BG_HOVER if self._hovered else self._bg
            fg = self._fg if enabled else Colors.TEXT_MUTED
            icon_fg = Colors.TEXT_SECONDARY if enabled else Colors.TEXT_MUTED
            gc.SetBrush(wx.Brush(bg))
            gc.SetPen(wx.Pen(Colors.BORDER_HOVER if self._hovered and enabled else self._border, 1))
            gc.DrawRoundedRectangle(0.5, 0.5, w - 1, h - 1, 4)
            gc.SetPen(wx.Pen(Colors.BORDER_SOFT, 1))
            gc.StrokeLine(w - 20, 4, w - 20, h - 4)
            gc.StrokeLine(w - 19, h / 2, w - 3, h / 2)
            gc.SetFont(self.GetFont(), fg)
            tw, th = gc.GetTextExtent(text)[:2]
            gc.DrawText(text, max(6, (w - 22 - tw) / 2), (h - th) / 2)
            gc.SetPen(wx.Pen(icon_fg, 1))
            for up in (True, False):
                cx = w - 10
                cy = h * 0.30 if up else h * 0.72
                path = gc.CreatePath()
                if up:
                    path.MoveToPoint(cx - 3, cy + 2)
                    path.AddLineToPoint(cx, cy - 2)
                    path.AddLineToPoint(cx + 3, cy + 2)
                else:
                    path.MoveToPoint(cx - 3, cy - 2)
                    path.AddLineToPoint(cx, cy + 2)
                    path.AddLineToPoint(cx + 3, cy - 2)
                gc.StrokePath(path)

        mem.SelectObject(wx.NullBitmap)
        self._cached_bmp = bmp
        self._cached_state = state_key
        dc.DrawBitmap(bmp, 0, 0, False)


class DarkSpinCtrlDouble(DarkSpinCtrl):
    _double = True


def install_dark_controls(target_wx=wx):
    """Install lightweight replacements before UI modules create controls."""
    target_wx.ComboBox = DarkSelect
    target_wx.SpinCtrl = DarkSpinCtrl
    target_wx.SpinCtrlDouble = DarkSpinCtrlDouble
