from PIL import Image
import pytest
from types import SimpleNamespace

from editor.core.frame import Frame

from editor.utils.frame_targeting import (
    TargetMode,
    apply_frame_processor,
    build_target_choices,
    resolve_target_state,
    restore_current_original_image,
    restore_original_images,
    should_apply_to_frame,
    snapshot_original_images,
)


class _Frame:
    def __init__(self, color: int):
        self.image = Image.new("RGBA", (2, 2), (color, color, color, 255))
        self._image = None

    def copy_image(self):
        return self.image.copy()

    def _invalidate_cache(self):
        pass


class _Frames(list):
    def __init__(self, frames, selected_indices=(), current_index=0):
        super().__init__(frames)
        self.selected_indices = set(selected_indices)
        self.current_index = current_index


class _Translations:
    def tr(self, key: str) -> str:
        mapping = {
            "target_all": "ALL",
            "target_selected": "SELECTED",
            "target_current": "CURRENT",
        }
        return mapping[key]


def test_build_target_choices_uses_translations_when_available():
    assert build_target_choices(_Translations()) == ["ALL", "SELECTED", "CURRENT"]


def test_snapshot_original_images_copies_source_images():
    frames = _Frames([_Frame(10), _Frame(20)])

    originals = snapshot_original_images(frames)

    assert [img.getpixel((0, 0))[0] for img in originals] == [10, 20]
    assert originals[0] is not frames[0].image
    assert originals[1] is not frames[1].image


def test_resolve_target_state_normalizes_selection():
    frames = _Frames([_Frame(10)], selected_indices=[0], current_index=3)

    state = resolve_target_state(frames)

    assert state.selected_indices == frozenset({0})
    assert state.current_index == 3


def test_should_apply_to_frame_matches_target_modes():
    state = resolve_target_state(_Frames([_Frame(10), _Frame(20)], selected_indices={1}, current_index=0))

    assert should_apply_to_frame(TargetMode.ALL, 0, state) is True
    assert should_apply_to_frame(TargetMode.SELECTED, 1, state) is True
    assert should_apply_to_frame(TargetMode.SELECTED, 0, state) is False
    assert should_apply_to_frame(TargetMode.CURRENT, 0, state) is True
    assert should_apply_to_frame(TargetMode.CURRENT, 1, state) is False


def test_restore_original_images_resets_all_frames():
    frames = _Frames([_Frame(10), _Frame(20)])
    originals = snapshot_original_images(frames)
    frames[0]._image = Image.new("RGBA", (2, 2), (99, 99, 99, 255))
    frames[1]._image = Image.new("RGBA", (2, 2), (77, 77, 77, 255))

    restore_original_images(frames, originals)

    assert frames[0]._image.getpixel((0, 0))[0] == 10
    assert frames[1]._image.getpixel((0, 0))[0] == 20


def test_restore_current_original_image_only_resets_current_frame():
    frames = _Frames([_Frame(10), _Frame(20), _Frame(30)], current_index=1)
    originals = snapshot_original_images(frames)
    for frame in frames:
        frame._image = Image.new("RGBA", (2, 2), (99, 99, 99, 255))

    restore_current_original_image(frames, originals)

    assert frames[0]._image.getpixel((0, 0))[0] == 99
    assert frames[1]._image.getpixel((0, 0))[0] == 20
    assert frames[2]._image.getpixel((0, 0))[0] == 99


def test_apply_frame_processor_honors_selected_target_and_preview_current():
    frames = _Frames([_Frame(10), _Frame(20), _Frame(30)], selected_indices={2}, current_index=0)
    originals = snapshot_original_images(frames)

    def processor(original, index, should_apply):
        base = original.copy()
        base.putpixel((0, 0), (200 + index, 0, 0, 255 if should_apply else 128))
        return base

    apply_frame_processor(
        frames,
        originals,
        TargetMode.SELECTED,
        processor,
        preview_current=True,
    )

    assert frames[0]._image.getpixel((0, 0))[0] == 200
    assert frames[1]._image is None
    assert frames[2]._image is None


@pytest.mark.parametrize("target", list(TargetMode))
def test_preview_only_processes_current_without_copying_untouched(target, monkeypatch):
    frames = _Frames([_Frame(10), _Frame(20), _Frame(30)], selected_indices={2}, current_index=0)
    originals = snapshot_original_images(frames)
    calls = []

    def reject_copy():
        pytest.fail("untouched frame was copied")

    for image in originals[1:]:
        monkeypatch.setattr(image, "copy", reject_copy)

    def processor(original, index, selected):
        calls.append((index, selected))
        return original.copy()

    apply_frame_processor(frames, originals, target, processor, preview_current=True)
    assert calls == [(0, target != TargetMode.SELECTED)]
    assert frames[1]._image is None
    assert frames[2]._image is None


@pytest.mark.parametrize("target, expected", [(TargetMode.ALL, [99, 99, 99]),
                                             (TargetMode.SELECTED, [10, 20, 99]),
                                             (TargetMode.CURRENT, [10, 99, 30])])
def test_apply_after_preview_navigation_preserves_targets(target, expected):
    frames = _Frames([Frame(Image.new("RGB", (2, 2), (i, i, i))) for i in (10, 20, 30)],
                     selected_indices={2}, current_index=0)
    originals = snapshot_original_images(frames)
    def processor(original, index, selected):
        return Image.new("RGB", (2, 2), (99, 99, 99))
    apply_frame_processor(frames, originals, target, processor, preview_current=True)
    frames.current_index = 1
    apply_frame_processor(frames, originals, target, processor, preview_current=True)
    apply_frame_processor(frames, originals, target, processor)
    for frame in frames:
        frame.unload_image()
    assert [frame.image.getpixel((0, 0))[0] for frame in frames] == expected


def test_preview_navigation_cancel_restores_pixels_dimensions_and_thumbnail():
    frames = _Frames([Frame(Image.new("RGB", (2, 2), (i, i, i))) for i in (10, 20)])
    originals = snapshot_original_images(frames)
    for frame in frames:
        frame.get_thumbnail()
    def processor(original, index, selected):
        return Image.new("RGB", (4, 3), (99, 99, 99))
    for current in (0, 1):
        frames.current_index = current
        apply_frame_processor(frames, originals, TargetMode.ALL, processor, preview_current=True)
        frame = frames[current]
        assert (frame.width, frame.height) == (4, 3)
        assert frame.get_thumbnail().getpixel((0, 0))[0] == 99
        frame.unload_image()
        assert frame.image.getpixel((0, 0))[0] == 99
    restore_original_images(frames, originals)
    for frame, color in zip(frames, (10, 20)):
        frame.unload_image()
        assert frame.image.getpixel((0, 0))[0] == color
        assert (frame.width, frame.height) == (2, 2)
        assert frame.get_thumbnail().getpixel((0, 0))[0] == color


@pytest.mark.parametrize("operation", ["generated", "resize", "resize_restore", "text_preview"])
def test_toolbar_image_assignments_survive_unload(operation):
    from editor.ui.inline_toolbars.base_toolbar_wx import InlineToolbarBase
    from editor.ui.inline_toolbars.resize_toolbar_wx import ResizeToolbar
    from editor.ui.inline_toolbars.text_toolbar_wx import TextToolbar

    frame = Frame(Image.new("RGB", (2, 2), (10, 10, 10)))
    frame.get_thumbnail()
    image = Image.new("RGB", (4, 3), (99, 99, 99))
    toolbar = SimpleNamespace(frames=_Frames([frame]), _original_images=[image],
                              _is_low_end_mode=True, _apply_text=lambda original: original.copy(),
                              _safe_canvas_update=lambda: None, update_preview=lambda: None)
    if operation == "generated":
        InlineToolbarBase._apply_generated_images(toolbar, [image])
    elif operation == "resize":
        ResizeToolbar._apply_resized_images(toolbar, 4, 3, Image.Resampling.NEAREST)
    elif operation == "resize_restore":
        ResizeToolbar._restore_original_images_with_size(toolbar)
    else:
        TextToolbar._update_preview(toolbar)
    assert (frame.width, frame.height) == (4, 3)
    assert frame.get_thumbnail().getpixel((0, 0))[0] == 99
    frame.unload_image()
    assert frame.image.size == (4, 3)
    assert frame.image.getpixel((0, 0))[0] == 99
