"""Shared frame-targeting helpers for editor toolbars."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import Callable, Iterable, Optional

from PIL import Image


class TargetMode(IntEnum):
    ALL = 0
    SELECTED = 1
    CURRENT = 2


@dataclass(frozen=True)
class TargetState:
    selected_indices: frozenset[int]
    current_index: int


FrameProcessor = Callable[[Image.Image, int, bool], Optional[Image.Image]]


def build_target_choices(translations=None) -> list[str]:
    """Return normalized target-choice labels."""
    if translations:
        return [
            translations.tr("target_all"),
            translations.tr("target_selected"),
            translations.tr("target_current"),
        ]
    return ["모두", "선택", "현재"]


def snapshot_original_images(frames) -> list[Optional[Image.Image]]:
    """Capture immutable originals for preview/apply/cancel flows."""
    originals: list[Optional[Image.Image]] = []
    try:
        for frame in frames:
            image = getattr(frame, "image", None) if frame else None
            originals.append(image.copy() if image else None)
    except Exception:
        return []
    return originals


def resolve_target_state(frames) -> TargetState:
    """Normalize selected/current frame state for toolbar target handling."""
    selected_indices = getattr(frames, "selected_indices", set())
    if isinstance(selected_indices, set):
        normalized = selected_indices
    elif isinstance(selected_indices, (list, tuple)):
        normalized = set(selected_indices)
    else:
        try:
            normalized = set(selected_indices)
        except TypeError:
            normalized = set()

    return TargetState(
        selected_indices=frozenset(normalized),
        current_index=getattr(frames, "current_index", 0),
    )


def should_apply_to_frame(target_mode: int, index: int, state: TargetState) -> bool:
    """Return whether the target mode includes the frame index."""
    if target_mode == TargetMode.ALL:
        return True
    if target_mode == TargetMode.SELECTED:
        return index in state.selected_indices
    if target_mode == TargetMode.CURRENT:
        return index == state.current_index
    return False


def restore_original_images(frames, originals: Iterable[Optional[Image.Image]]) -> None:
    """Restore all available originals back into frame preview slots."""
    for _index, frame, original in _iter_original_frames(frames, originals):
        _set_frame_image(frame, original.copy())


def restore_current_original_image(frames, originals: Iterable[Optional[Image.Image]]) -> None:
    """Restore only the current frame from the original snapshot."""
    state = resolve_target_state(frames)
    for index, frame, original in _iter_original_frames(frames, originals):
        if index == state.current_index:
            _set_frame_image(frame, original.copy())
            return


def apply_frame_processor(
    frames,
    originals: Iterable[Optional[Image.Image]],
    target_mode: int,
    processor: FrameProcessor,
    *,
    preview_current: bool = False,
) -> None:
    """Apply a per-frame processor using normalized target semantics."""
    state = resolve_target_state(frames)
    for index, frame, original in _iter_original_frames(frames, originals):
        should_apply = should_apply_to_frame(target_mode, index, state)
        show_processed = should_apply or (preview_current and index == state.current_index)

        try:
            if show_processed:
                processed = processor(original, index, should_apply)
                _set_frame_image(frame, processed if processed is not None else original.copy())
            else:
                _set_frame_image(frame, original.copy())
        except Exception:
            pass


def _iter_original_frames(frames, originals: Iterable[Optional[Image.Image]]):
    originals_list = list(originals)
    for index, frame in enumerate(frames):
        if frame is None or index >= len(originals_list):
            continue
        original = originals_list[index]
        if original is None:
            continue
        yield index, frame, original


def _set_frame_image(frame, image: Image.Image) -> None:
    frame._image = image
