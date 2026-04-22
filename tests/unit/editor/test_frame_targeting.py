from PIL import Image

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
    assert frames[1]._image.getpixel((0, 0))[0] == 20
    assert frames[2]._image.getpixel((0, 0))[0] == 202
