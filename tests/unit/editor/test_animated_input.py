"""Animations opened for editing must survive normal save without silent truncation."""
import pytest
from PIL import Image
from PIL.GifImagePlugin import getdata, getheader

from editor.core.editor_gif_encoder import GifEncoder
from editor.core.gif_decoder import GifDecoder


@pytest.mark.parametrize("suffix,fmt", [("png", "PNG"), ("apng", "PNG"), ("webp", "WEBP"), ("gif", "GIF")])
def test_open_then_save_preserves_animation(tmp_path, suffix, fmt):
    path = tmp_path / f"source.{suffix}"
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    delays = [40, 80, 130] if fmt == "GIF" else [3, 80, 130]
    images = [Image.new("RGB", (5, 4), c) for c in colors]
    images[0].save(path, fmt, save_all=True, append_images=images[1:], duration=delays,
                   loop=2, lossless=True)
    assert GifDecoder.is_supported_file(str(path))
    result = GifDecoder.load(str(path))
    assert result.success, result.error_message
    assert [f.delay_ms for f in result.frames] == delays
    assert [f.copy_image().convert("RGB").getpixel((0, 0)) for f in result.frames] == colors
    saved = GifEncoder.save(result.frames.clone(), str(path))
    assert saved.success, saved.error_message
    reopened = GifDecoder.load(str(path))
    assert reopened.success and reopened.frames.loop_count == 2
    assert [f.delay_ms for f in reopened.frames] == delays
    for frame, expected in zip(reopened.frames, colors, strict=True):
        pixel = frame.copy_image().convert("RGB").getpixel((0, 0))
        assert max(abs(a - b) for a, b in zip(pixel, expected)) <= 5


@pytest.mark.parametrize("affected_width", [1, 2])
def test_apng_previous_over_restores_canvas_before_next_frame(tmp_path, affected_width):
    path = tmp_path / "restore.png"
    base = Image.new("RGBA", (2, 1), "lime")
    overlay = base.copy()
    overlay.paste("red", (0, 0, affected_width, 1))
    last = Image.new("RGBA", (2, 1), (0, 0, 0, 0))
    last.putpixel((1, 0), (0, 0, 255, 255))
    base.save(path, save_all=True, append_images=[overlay, last], duration=[10, 20, 30],
              disposal=[0, 2, 0], blend=[0, 1, 1])

    result = GifDecoder.load(str(path))
    assert result.success, result.error_message
    expected_last = base.copy()
    expected_last.putpixel((1, 0), (0, 0, 255, 255))
    assert [frame.copy_image().tobytes() for frame in result.frames] == [
        base.tobytes(), overlay.tobytes(), expected_last.tobytes()
    ]
    assert [frame.delay_ms for frame in result.frames] == [10, 20, 30]


def test_apng_poster_separate_from_single_timed_frame(tmp_path):
    path = tmp_path / "poster.png"
    poster, frame = [Image.new("RGB", (3, 3), c) for c in ("black", "white")]
    poster.save(path, save_all=True, append_images=[frame], default_image=True, loop=3, duration=[1000 / 60])
    loaded = GifDecoder.load(str(path))
    assert loaded.success and len(loaded.frames) == 1
    assert GifEncoder.save(loaded.frames.clone(), str(path)).success
    with Image.open(path) as image:
        assert image.n_frames == 2 and image.info["default_image"]
        assert image.convert("RGB").tobytes() == poster.tobytes()
        image.seek(1)
        assert image.convert("RGB").tobytes() == frame.tobytes()
        assert image.info["duration"] == pytest.approx(1000 / 60) and image.info["loop"] == 3


def test_gif_without_loop_extension_still_plays_once(tmp_path):
    path = tmp_path / "once.gif"
    frames = [Image.new("RGB", (2, 2), c) for c in ("red", "green")]
    frames[0].save(path, save_all=True, append_images=frames[1:], duration=70)
    loaded = GifDecoder.load(str(path))
    assert loaded.success and loaded.frames.loop_count is None
    assert GifEncoder.save(loaded.frames.clone(), str(path)).success
    with Image.open(path) as image:
        assert "loop" not in image.info and image.n_frames == 2


def test_gif_10001_frames_rejected_without_returning_partial_document(tmp_path):
    path = tmp_path / "large.gif"
    frame = Image.new("P", (1, 1))
    frame.putpalette(bytes(range(256)) * 3)
    header, _ = getheader(frame)
    raw = b"".join(header) + b"".join(getdata(frame)) * 10001 + b";"
    path.write_bytes(raw)
    result = GifDecoder.load(str(path))
    assert not result.success and result.frames is None and "10,001" in result.error_message
    assert path.read_bytes() == raw


def test_corruption_during_second_frame_discards_whole_load(tmp_path, monkeypatch):
    from editor.core import gif_decoder

    path = tmp_path / "second.gif"
    images = [Image.new("RGB", (3, 3), c) for c in ("red", "green")]
    images[0].save(path, save_all=True, append_images=images[1:])
    raw = path.read_bytes()
    original = gif_decoder.Frame
    calls = []

    def read_frame(image, delay):
        calls.append(None)
        if len(calls) == 2:
            raise OSError("bad frame")
        return original(image, delay)

    monkeypatch.setattr(gif_decoder, "Frame", read_frame)
    result = GifDecoder.load(str(path))
    assert not result.success and result.frames is None and "bad frame" in result.error_message
    assert path.read_bytes() == raw


def test_corrupt_numbered_sequence_names_file_and_returns_no_partial_document(tmp_path):
    Image.new('RGB', (4, 3), 'red').save(tmp_path / '001.png')
    (tmp_path / '002.png').write_bytes(b'broken PNG')
    Image.new('RGB', (4, 3), 'blue').save(tmp_path / '003.png')
    result = GifDecoder.load_from_folder(str(tmp_path), pattern='*')
    assert not result.success and result.frames is None and '002.png' in result.error_message


@pytest.mark.parametrize('opaque_first', [True, False])
def test_transparent_animation_clears_previous_displayed_pixels(tmp_path, opaque_first):
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection

    frames = FrameCollection()
    input_images = []
    for i in range(3):
        image = Image.new('RGBA', (6, 4), 'green' if opaque_first and i == 0 else (0, 0, 0, 0))
        image.putpixel((i, 1), (255, 0, 0, 255))
        frames.add_frame(Frame(image, 50))
        input_images.append(image)
    path = tmp_path / 'movement.gif'
    assert GifEncoder.save(frames, str(path)).success
    reopened = GifDecoder.load(str(path))
    assert GifEncoder.save(reopened.frames, str(path)).success
    with Image.open(path) as saved:
        assert saved.n_frames == len(input_images)
        for i, expected in enumerate(input_images):
            saved.seek(i)
            actual = saved.convert('RGBA')
            assert actual.getchannel('A').tobytes() == expected.getchannel('A').tobytes()
            assert actual.getpixel((i, 1)) == expected.getpixel((i, 1))


def test_speed_undo_restores_sub_10ms_and_fractional_frame_delays():
    from types import SimpleNamespace
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection
    from editor.core.undo_manager import UndoManager
    from editor.ui.editor_main_window_wx import MainWindow
    from editor.ui.inline_toolbars.speed_toolbar_wx import SpeedToolbar
    from unittest.mock import Mock

    frames = FrameCollection()
    for delay in [3, 1000 / 60]:
        frames.add_frame(Frame(Image.new('RGB', (2, 2)), delay))
    window = SimpleNamespace(_frames=frames, _undo_manager=UndoManager(), _refresh_all=lambda: None)
    window._scale_speed = MainWindow._scale_speed.__get__(window)
    toolbar = SpeedToolbar.__new__(SpeedToolbar)
    toolbar._main_window = window
    toolbar._original_delays = [f.duration_ms for f in frames]
    toolbar._speed_spin = Mock()
    toolbar._speed_spin.GetValue.return_value = 2
    toolbar._finish_apply = Mock()
    toolbar._update_result_label = Mock()
    toolbar.update_preview = Mock()
    toolbar._update_preview()
    assert [f.duration_ms for f in frames] == [1.5, 500 / 60]
    toolbar._on_apply(None)
    assert [f.duration_ms for f in frames] == [1.5, 500 / 60]
    assert window._undo_manager.undo()
    assert [frame.duration_ms for frame in frames] == [3, 1000 / 60]


def test_crop_and_undo_transform_apng_poster_with_timeline(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from unittest.mock import Mock
    from editor.core.undo_manager import UndoManager
    from editor.ui.editor_main_window_wx import MainWindow
    from editor.ui.inline_toolbars.base_toolbar_wx import InlineToolbarBase
    from editor.ui.inline_toolbars.crop_toolbar_wx import CropToolbar
    from editor.utils import progress

    poster = Image.new('RGB', (16, 8), 'green')
    poster.paste('red', (0, 0, 8, 8))
    path = tmp_path / 'poster.png'
    poster.save(path, save_all=True, append_images=[Image.new('RGB', poster.size, 'blue')],
                default_image=True, duration=100)
    window = SimpleNamespace(_frames=GifDecoder.load(str(path)).frames, _undo_manager=UndoManager(),
                             _refresh_all=Mock(), _translations=Mock())
    window._run_undoable_with_progress = MainWindow._run_undoable_with_progress.__get__(window)
    monkeypatch.setattr(progress, 'run_with_progress', lambda **kw: (kw['work_func'](Mock()), False))
    monkeypatch.setattr(InlineToolbarBase, '_on_apply', lambda *args: None)
    toolbar = CropToolbar.__new__(CropToolbar)
    toolbar._main_window = window
    toolbar._on_deactivated = lambda: None
    toolbar.get_crop_rect = lambda: (8, 0, 8, 8)
    toolbar._on_apply(None)
    assert GifEncoder.save(window._frames, str(path)).success
    with Image.open(path) as saved:
        assert saved.size == (8, 8) and saved.convert('RGB').getcolors() == [(64, (0, 128, 0))]
    assert window._undo_manager.undo()
    assert window._frames.default_image.copy_image().convert('RGB').tobytes() == poster.tobytes()
    assert window._undo_manager.redo() and window._frames.default_image.size == (8, 8)
