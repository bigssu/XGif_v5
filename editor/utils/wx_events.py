"""
wxPython Custom Events

Defines custom event types to replace PyQt6 signals in the XGif editor.
Each event corresponds to a specific user action or state change.
"""

import wx
from typing import Any, Optional, List


# =============================================================================
# Event Type IDs
# =============================================================================

# Drawing events
wxEVT_DRAWING_FINISHED = wx.NewEventType()
wxEVT_DRAWING_STARTED = wx.NewEventType()
wxEVT_DRAWING_CANCELLED = wx.NewEventType()

# Text overlay events
wxEVT_TEXT_MOVED = wx.NewEventType()
wxEVT_TEXT_RESIZED = wx.NewEventType()
wxEVT_TEXT_CHANGED = wx.NewEventType()
wxEVT_TEXT_ADDED = wx.NewEventType()
wxEVT_TEXT_REMOVED = wx.NewEventType()

# Crop events
wxEVT_CROP_CHANGED = wx.NewEventType()
wxEVT_CROP_APPLIED = wx.NewEventType()
wxEVT_CROP_CANCELLED = wx.NewEventType()

# Sticker events
wxEVT_STICKER_ADDED = wx.NewEventType()
wxEVT_STICKER_CHANGED = wx.NewEventType()
wxEVT_STICKER_REMOVED = wx.NewEventType()
wxEVT_STICKER_MOVED = wx.NewEventType()
wxEVT_STICKER_RESIZED = wx.NewEventType()

# Mosaic events
wxEVT_MOSAIC_REGION_CHANGED = wx.NewEventType()
wxEVT_MOSAIC_APPLIED = wx.NewEventType()
wxEVT_MOSAIC_CANCELLED = wx.NewEventType()

# Speech bubble events
wxEVT_SPEECH_BUBBLE_CHANGED = wx.NewEventType()
wxEVT_SPEECH_BUBBLE_APPLIED = wx.NewEventType()
wxEVT_SPEECH_BUBBLE_CANCELLED = wx.NewEventType()

# Frame events
wxEVT_FRAME_SELECTED = wx.NewEventType()
wxEVT_FRAME_DELETED = wx.NewEventType()
wxEVT_FRAMES_REORDERED = wx.NewEventType()
wxEVT_FRAME_DUPLICATED = wx.NewEventType()
wxEVT_FRAME_DELAY_CHANGED = wx.NewEventType()

# Canvas events
wxEVT_ZOOM_CHANGED = wx.NewEventType()
wxEVT_PAN_CHANGED = wx.NewEventType()
wxEVT_CANVAS_MODE_CHANGED = wx.NewEventType()

# Toolbar events
wxEVT_TOOLBAR_APPLIED = wx.NewEventType()
wxEVT_TOOLBAR_CANCELLED = wx.NewEventType()
wxEVT_TOOLBAR_PREVIEW_UPDATED = wx.NewEventType()

# Effect events
wxEVT_EFFECT_APPLIED = wx.NewEventType()
wxEVT_EFFECT_PREVIEW = wx.NewEventType()

# Playback events
wxEVT_PLAYBACK_STARTED = wx.NewEventType()
wxEVT_PLAYBACK_STOPPED = wx.NewEventType()
wxEVT_PLAYBACK_FRAME_CHANGED = wx.NewEventType()


# =============================================================================
# Event Binders (for use with Bind())
# =============================================================================

EVT_DRAWING_FINISHED = wx.PyEventBinder(wxEVT_DRAWING_FINISHED, 1)
EVT_DRAWING_STARTED = wx.PyEventBinder(wxEVT_DRAWING_STARTED, 1)
EVT_DRAWING_CANCELLED = wx.PyEventBinder(wxEVT_DRAWING_CANCELLED, 1)

EVT_TEXT_MOVED = wx.PyEventBinder(wxEVT_TEXT_MOVED, 1)
EVT_TEXT_RESIZED = wx.PyEventBinder(wxEVT_TEXT_RESIZED, 1)
EVT_TEXT_CHANGED = wx.PyEventBinder(wxEVT_TEXT_CHANGED, 1)
EVT_TEXT_ADDED = wx.PyEventBinder(wxEVT_TEXT_ADDED, 1)
EVT_TEXT_REMOVED = wx.PyEventBinder(wxEVT_TEXT_REMOVED, 1)

EVT_CROP_CHANGED = wx.PyEventBinder(wxEVT_CROP_CHANGED, 1)
EVT_CROP_APPLIED = wx.PyEventBinder(wxEVT_CROP_APPLIED, 1)
EVT_CROP_CANCELLED = wx.PyEventBinder(wxEVT_CROP_CANCELLED, 1)

EVT_STICKER_ADDED = wx.PyEventBinder(wxEVT_STICKER_ADDED, 1)
EVT_STICKER_CHANGED = wx.PyEventBinder(wxEVT_STICKER_CHANGED, 1)
EVT_STICKER_REMOVED = wx.PyEventBinder(wxEVT_STICKER_REMOVED, 1)
EVT_STICKER_MOVED = wx.PyEventBinder(wxEVT_STICKER_MOVED, 1)
EVT_STICKER_RESIZED = wx.PyEventBinder(wxEVT_STICKER_RESIZED, 1)

EVT_MOSAIC_REGION_CHANGED = wx.PyEventBinder(wxEVT_MOSAIC_REGION_CHANGED, 1)
EVT_MOSAIC_APPLIED = wx.PyEventBinder(wxEVT_MOSAIC_APPLIED, 1)
EVT_MOSAIC_CANCELLED = wx.PyEventBinder(wxEVT_MOSAIC_CANCELLED, 1)

EVT_SPEECH_BUBBLE_CHANGED = wx.PyEventBinder(wxEVT_SPEECH_BUBBLE_CHANGED, 1)
EVT_SPEECH_BUBBLE_APPLIED = wx.PyEventBinder(wxEVT_SPEECH_BUBBLE_APPLIED, 1)
EVT_SPEECH_BUBBLE_CANCELLED = wx.PyEventBinder(wxEVT_SPEECH_BUBBLE_CANCELLED, 1)

EVT_FRAME_SELECTED = wx.PyEventBinder(wxEVT_FRAME_SELECTED, 1)
EVT_FRAME_DELETED = wx.PyEventBinder(wxEVT_FRAME_DELETED, 1)
EVT_FRAMES_REORDERED = wx.PyEventBinder(wxEVT_FRAMES_REORDERED, 1)
EVT_FRAME_DUPLICATED = wx.PyEventBinder(wxEVT_FRAME_DUPLICATED, 1)
EVT_FRAME_DELAY_CHANGED = wx.PyEventBinder(wxEVT_FRAME_DELAY_CHANGED, 1)

EVT_ZOOM_CHANGED = wx.PyEventBinder(wxEVT_ZOOM_CHANGED, 1)
EVT_PAN_CHANGED = wx.PyEventBinder(wxEVT_PAN_CHANGED, 1)
EVT_CANVAS_MODE_CHANGED = wx.PyEventBinder(wxEVT_CANVAS_MODE_CHANGED, 1)

EVT_TOOLBAR_APPLIED = wx.PyEventBinder(wxEVT_TOOLBAR_APPLIED, 1)
EVT_TOOLBAR_CANCELLED = wx.PyEventBinder(wxEVT_TOOLBAR_CANCELLED, 1)
EVT_TOOLBAR_PREVIEW_UPDATED = wx.PyEventBinder(wxEVT_TOOLBAR_PREVIEW_UPDATED, 1)

EVT_EFFECT_APPLIED = wx.PyEventBinder(wxEVT_EFFECT_APPLIED, 1)
EVT_EFFECT_PREVIEW = wx.PyEventBinder(wxEVT_EFFECT_PREVIEW, 1)

EVT_PLAYBACK_STARTED = wx.PyEventBinder(wxEVT_PLAYBACK_STARTED, 1)
EVT_PLAYBACK_STOPPED = wx.PyEventBinder(wxEVT_PLAYBACK_STOPPED, 1)
EVT_PLAYBACK_FRAME_CHANGED = wx.PyEventBinder(wxEVT_PLAYBACK_FRAME_CHANGED, 1)


# =============================================================================
# Event Classes
# =============================================================================

class DrawingFinishedEvent(wx.PyEvent):
    """Event fired when drawing mode is finished."""

    def __init__(self, path_data: Optional[List] = None):
        super().__init__()
        self.SetEventType(wxEVT_DRAWING_FINISHED)
        self.path_data = path_data or []


class DrawingStartedEvent(wx.PyEvent):
    """Event fired when drawing mode starts."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_DRAWING_STARTED)


class DrawingCancelledEvent(wx.PyEvent):
    """Event fired when drawing mode is cancelled."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_DRAWING_CANCELLED)


class TextMovedEvent(wx.PyEvent):
    """Event fired when a text overlay is moved."""

    def __init__(self, text_id: str, x: int, y: int):
        super().__init__()
        self.SetEventType(wxEVT_TEXT_MOVED)
        self.text_id = text_id
        self.x = x
        self.y = y


class TextResizedEvent(wx.PyEvent):
    """Event fired when a text overlay is resized."""

    def __init__(self, text_id: str, font_size: int):
        super().__init__()
        self.SetEventType(wxEVT_TEXT_RESIZED)
        self.text_id = text_id
        self.font_size = font_size


class TextChangedEvent(wx.PyEvent):
    """Event fired when text content or properties change."""

    def __init__(self, text_id: str, text: str, font_size: Optional[int] = None,
                 color: Optional[wx.Colour] = None):
        super().__init__()
        self.SetEventType(wxEVT_TEXT_CHANGED)
        self.text_id = text_id
        self.text = text
        self.font_size = font_size
        self.color = color


class TextAddedEvent(wx.PyEvent):
    """Event fired when a new text overlay is added."""

    def __init__(self, text_id: str, x: int, y: int, text: str):
        super().__init__()
        self.SetEventType(wxEVT_TEXT_ADDED)
        self.text_id = text_id
        self.x = x
        self.y = y
        self.text = text


class TextRemovedEvent(wx.PyEvent):
    """Event fired when a text overlay is removed."""

    def __init__(self, text_id: str):
        super().__init__()
        self.SetEventType(wxEVT_TEXT_REMOVED)
        self.text_id = text_id


class CropChangedEvent(wx.PyEvent):
    """Event fired when crop region changes."""

    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_CROP_CHANGED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class CropAppliedEvent(wx.PyEvent):
    """Event fired when crop is applied."""

    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_CROP_APPLIED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class CropCancelledEvent(wx.PyEvent):
    """Event fired when crop is cancelled."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_CROP_CANCELLED)


class StickerAddedEvent(wx.PyEvent):
    """Event fired when a sticker is added."""

    def __init__(self, sticker_id: str, x: int, y: int, sticker_path: str):
        super().__init__()
        self.SetEventType(wxEVT_STICKER_ADDED)
        self.sticker_id = sticker_id
        self.x = x
        self.y = y
        self.sticker_path = sticker_path


class StickerChangedEvent(wx.PyEvent):
    """Event fired when a sticker's properties change."""

    def __init__(self, sticker_id: str, x: int, y: int, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_STICKER_CHANGED)
        self.sticker_id = sticker_id
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class StickerRemovedEvent(wx.PyEvent):
    """Event fired when a sticker is removed."""

    def __init__(self, sticker_id: str):
        super().__init__()
        self.SetEventType(wxEVT_STICKER_REMOVED)
        self.sticker_id = sticker_id


class StickerMovedEvent(wx.PyEvent):
    """Event fired when a sticker is moved."""

    def __init__(self, sticker_id: str, x: int, y: int):
        super().__init__()
        self.SetEventType(wxEVT_STICKER_MOVED)
        self.sticker_id = sticker_id
        self.x = x
        self.y = y


class StickerResizedEvent(wx.PyEvent):
    """Event fired when a sticker is resized."""

    def __init__(self, sticker_id: str, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_STICKER_RESIZED)
        self.sticker_id = sticker_id
        self.width = width
        self.height = height


class MosaicRegionChangedEvent(wx.PyEvent):
    """Event fired when mosaic region changes."""

    def __init__(self, x: int, y: int, width: int, height: int, intensity: int):
        super().__init__()
        self.SetEventType(wxEVT_MOSAIC_REGION_CHANGED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.intensity = intensity


class MosaicAppliedEvent(wx.PyEvent):
    """Event fired when mosaic is applied."""

    def __init__(self, x: int, y: int, width: int, height: int, intensity: int):
        super().__init__()
        self.SetEventType(wxEVT_MOSAIC_APPLIED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.intensity = intensity


class MosaicCancelledEvent(wx.PyEvent):
    """Event fired when mosaic is cancelled."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_MOSAIC_CANCELLED)


class SpeechBubbleChangedEvent(wx.PyEvent):
    """Event fired when speech bubble region changes."""

    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_SPEECH_BUBBLE_CHANGED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class SpeechBubbleAppliedEvent(wx.PyEvent):
    """Event fired when speech bubble is applied."""

    def __init__(self, x: int, y: int, width: int, height: int):
        super().__init__()
        self.SetEventType(wxEVT_SPEECH_BUBBLE_APPLIED)
        self.x = x
        self.y = y
        self.width = width
        self.height = height


class SpeechBubbleCancelledEvent(wx.PyEvent):
    """Event fired when speech bubble is cancelled."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_SPEECH_BUBBLE_CANCELLED)


class FrameSelectedEvent(wx.PyEvent):
    """Event fired when frame(s) are selected."""

    def __init__(self, frame_indices: List[int]):
        super().__init__()
        self.SetEventType(wxEVT_FRAME_SELECTED)
        self.frame_indices = frame_indices


class FrameDeletedEvent(wx.PyEvent):
    """Event fired when frame(s) are deleted."""

    def __init__(self, frame_indices: List[int]):
        super().__init__()
        self.SetEventType(wxEVT_FRAME_DELETED)
        self.frame_indices = frame_indices


class FramesReorderedEvent(wx.PyEvent):
    """Event fired when frames are reordered."""

    def __init__(self, old_index: int, new_index: int):
        super().__init__()
        self.SetEventType(wxEVT_FRAMES_REORDERED)
        self.old_index = old_index
        self.new_index = new_index


class FrameDuplicatedEvent(wx.PyEvent):
    """Event fired when a frame is duplicated."""

    def __init__(self, source_index: int, new_index: int):
        super().__init__()
        self.SetEventType(wxEVT_FRAME_DUPLICATED)
        self.source_index = source_index
        self.new_index = new_index


class FrameDelayChangedEvent(wx.PyEvent):
    """Event fired when frame delay is changed."""

    def __init__(self, frame_index: int, delay_ms: int):
        super().__init__()
        self.SetEventType(wxEVT_FRAME_DELAY_CHANGED)
        self.frame_index = frame_index
        self.delay_ms = delay_ms


class ZoomChangedEvent(wx.PyEvent):
    """Event fired when canvas zoom changes."""

    def __init__(self, zoom_level: float):
        super().__init__()
        self.SetEventType(wxEVT_ZOOM_CHANGED)
        self.zoom_level = zoom_level


class PanChangedEvent(wx.PyEvent):
    """Event fired when canvas pan offset changes."""

    def __init__(self, offset_x: int, offset_y: int):
        super().__init__()
        self.SetEventType(wxEVT_PAN_CHANGED)
        self.offset_x = offset_x
        self.offset_y = offset_y


class CanvasModeChangedEvent(wx.PyEvent):
    """Event fired when canvas mode changes (text, crop, sticker, etc.)."""

    def __init__(self, mode: str):
        super().__init__()
        self.SetEventType(wxEVT_CANVAS_MODE_CHANGED)
        self.mode = mode


class ToolbarAppliedEvent(wx.PyEvent):
    """Event fired when toolbar Apply button is clicked."""

    def __init__(self, data: Optional[dict] = None):
        super().__init__()
        self.SetEventType(wxEVT_TOOLBAR_APPLIED)
        self.data = data or {}


class ToolbarCancelledEvent(wx.PyEvent):
    """Event fired when toolbar Cancel button is clicked."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_TOOLBAR_CANCELLED)


class ToolbarPreviewUpdatedEvent(wx.PyEvent):
    """Event fired when toolbar preview should update."""

    def __init__(self, data: Optional[dict] = None):
        super().__init__()
        self.SetEventType(wxEVT_TOOLBAR_PREVIEW_UPDATED)
        self.data = data or {}


class EffectAppliedEvent(wx.PyEvent):
    """Event fired when an effect is applied."""

    def __init__(self, effect_name: str, parameters: dict):
        super().__init__()
        self.SetEventType(wxEVT_EFFECT_APPLIED)
        self.effect_name = effect_name
        self.parameters = parameters


class EffectPreviewEvent(wx.PyEvent):
    """Event fired when effect preview is requested."""

    def __init__(self, effect_name: str, parameters: dict):
        super().__init__()
        self.SetEventType(wxEVT_EFFECT_PREVIEW)
        self.effect_name = effect_name
        self.parameters = parameters


class PlaybackStartedEvent(wx.PyEvent):
    """Event fired when GIF playback starts."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_PLAYBACK_STARTED)


class PlaybackStoppedEvent(wx.PyEvent):
    """Event fired when GIF playback stops."""

    def __init__(self):
        super().__init__()
        self.SetEventType(wxEVT_PLAYBACK_STOPPED)


class PlaybackFrameChangedEvent(wx.PyEvent):
    """Event fired when playback advances to a new frame."""

    def __init__(self, frame_index: int):
        super().__init__()
        self.SetEventType(wxEVT_PLAYBACK_FRAME_CHANGED)
        self.frame_index = frame_index


# =============================================================================
# Utility Functions
# =============================================================================

def post_event(window: wx.Window, event: wx.PyEvent) -> None:
    """
    Post an event to a window's event queue.

    Args:
        window: Target window
        event: Event to post
    """
    wx.PostEvent(window, event)


def send_event(window: wx.Window, event: wx.PyEvent) -> bool:
    """
    Send an event to a window immediately (synchronous).

    Args:
        window: Target window
        event: Event to send

    Returns:
        True if event was processed
    """
    return window.GetEventHandler().ProcessEvent(event)
