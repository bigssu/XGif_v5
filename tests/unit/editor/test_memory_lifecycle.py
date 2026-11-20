"""Bounded source residency and independent editor image ownership."""
import ast
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
import gc
from types import SimpleNamespace
from unittest.mock import Mock
import weakref

from PIL import Image
import pytest

from editor.core.frame import Frame, get_memory_manager
from editor.core.frame_collection import FrameCollection
from editor.core.editor_gif_encoder import EncoderSettings, GifEncoder
from editor.utils.frame_targeting import snapshot_original_images
from tests._ast_helpers import find_class, find_function, parse_module


def collection(count=8, mode='RGB'):
    frames = FrameCollection()
    for index in range(count):
        image = Image.new(mode, (16, 16), index)
        if mode == 'P':
            image.putpalette([value for i in range(256) for value in (i, 255-i, i)])
            image.info['transparency'] = 0
        frames.add_frame(Frame(image, delay_ms=20 + index))
    return frames


@pytest.mark.parametrize('mode', ['RGB', 'RGBA', 'P'])
def test_clone_300_lazy_frames_never_decodes_source(mode, monkeypatch):
    frames = collection(300, mode)
    decode = Mock(side_effect=AssertionError('clone must not decode valid PNG bytes'))
    monkeypatch.setattr(Frame, '_decompress_image', decode)
    clone = frames.clone()
    decode.assert_not_called()
    assert frames.get_loaded_frame_count() == clone.get_loaded_frame_count() == 0
    for original, copied in zip(frames, clone, strict=True):
        assert copied._image_bytes is original._image_bytes
        assert copied._id != original._id
        assert copied.size == original.size
        assert copied.delay_ms == original.delay_ms
        assert copied._thumbnail_cache is not original._thumbnail_cache


@pytest.mark.parametrize('mode', ['RGB', 'RGBA', 'P'])
def test_clone_pixels_palette_and_mutations_are_independent(mode):
    original = collection(1, mode).get_frame(0)
    copied = original.clone()
    assert copied.image.mode == mode
    assert copied.image.tobytes() == original.image.tobytes()
    if mode == 'P':
        assert copied.image.getpalette() == original.image.getpalette()
        assert copied.image.info['transparency'] == 0
    copied.image.putpixel((0, 0), 7)
    assert original.image.getpixel((0, 0)) != copied.image.getpixel((0, 0))
    copied.delay_ms = 99
    assert original.delay_ms == 20


def test_memory_registry_drops_weak_entries_without_another_registration():
    manager = get_memory_manager()

    class Tracked:
        pass

    item = Tracked()
    manager.register_frame(-1, item)
    assert -1 in manager._loaded_frames
    del item
    gc.collect()
    assert -1 not in manager._loaded_frames


def test_concurrent_frame_registration_releases_all_weak_entries():
    manager = get_memory_manager()
    with ThreadPoolExecutor(max_workers=4) as pool:
        frames = list(pool.map(lambda i: Frame.from_recording(None, i, (10, 10), 20), range(1000)))
    ids = {frame._id for frame in frames}
    assert len(ids) == len(frames)
    assert all(manager._loaded_frames[frame._id] is frame for frame in frames)
    frames.clear()
    gc.collect()
    assert ids.isdisjoint(manager._loaded_frames)


def test_dirty_and_source_only_clone_preserve_residency(tmp_path):
    dirty = Frame(Image.new('RGB', (4, 4), 'red'), lazy_load=False)
    clone = dirty.clone()
    assert dirty.is_loaded
    assert clone.image is not dirty.image
    clone.image.putpixel((0, 0), (0, 0, 0))
    assert dirty.image.getpixel((0, 0)) == (255, 0, 0)
    path = tmp_path / 'source.png'
    dirty.image.save(path)
    source = Frame(None, source_path=str(path))
    source._image_size = (4, 4)
    saved = source.clone()
    assert not source.is_loaded
    path.unlink()
    assert saved.image.getpixel((0, 0)) == (255, 0, 0)


@pytest.mark.parametrize('operation', ['thumbnail', 'snapshot', 'preview', 'estimate'])
def test_read_operations_restore_source_residency(operation):
    frames = collection()
    frames.get_frame(0)._ensure_image_loaded()
    baseline = frames.get_loaded_frame_count()
    if operation == 'thumbnail':
        outputs = [frame.get_thumbnail(8) for frame in frames]
        assert all(image.size == (8, 8) for image in outputs)
    elif operation == 'snapshot':
        assert len(snapshot_original_images(frames)) == frames.frame_count
    elif operation == 'preview':
        assert GifEncoder.create_preview(frames.get_frame(1), EncoderSettings()).size == (16, 16)
    else:
        assert GifEncoder.estimate_gif_size(frames, EncoderSettings()) > 0
    assert frames.get_loaded_frame_count() == baseline


@pytest.mark.parametrize('suffix', ['gif', 'webp', 'apng', 'png', 'jpg', 'bmp', 'sequence'])
def test_export_source_peak_is_baseline_plus_one(tmp_path, monkeypatch, suffix):
    frames = collection()
    frames.get_frame(0)._ensure_image_loaded()
    frames.get_frame(2)._ensure_image_loaded()
    baseline = frames.get_loaded_frame_count()
    peak = baseline
    original = Frame._ensure_image_loaded

    def tracked(frame):
        nonlocal peak
        original(frame)
        peak = max(peak, frames.get_loaded_frame_count())

    monkeypatch.setattr(Frame, '_ensure_image_loaded', tracked)
    if suffix == 'sequence':
        result = GifEncoder.save_image_sequence(frames, str(tmp_path), 'frame')
    else:
        result = GifEncoder.save(frames, str(tmp_path / f'out.{suffix}'), EncoderSettings(use_gifsicle=False))
    assert result.success, result.error_message
    assert peak <= baseline + 1
    assert frames.get_loaded_frame_count() == baseline


def test_export_failure_restores_source_residency(tmp_path, monkeypatch):
    frames = collection()
    monkeypatch.setattr(GifEncoder, '_quantize_image', Mock(side_effect=ValueError('bad quantizer')))
    result = GifEncoder.save(frames, str(tmp_path / 'out.gif'))
    assert not result.success
    assert frames.get_loaded_frame_count() == 0


def test_copy_failure_restores_unloaded_source(monkeypatch):
    frame = collection(1).get_frame(0)
    monkeypatch.setattr(Image.Image, 'copy', Mock(side_effect=MemoryError('copy failed')))
    with pytest.raises(MemoryError):
        frame.copy_image()
    assert not frame.is_loaded


def test_canvas_cache_retains_identity_and_evicts_at_six():
    cls = find_class(parse_module('editor/ui/canvas_widget_wx.py'), 'CanvasWidget')
    method = find_function(cls, '_draw_frame_image')
    wx = SimpleNamespace(DC=object, Rect=object, IMAGE_QUALITY_HIGH=1, IMAGE_QUALITY_NORMAL=0,
                         Bitmap=Mock(side_effect=lambda image: object()))
    converter = Mock(return_value=Mock(IsOk=Mock(return_value=True)))
    namespace = {'wx': wx, 'pil_to_wx_bitmap': converter}
    exec(compile(ast.Module(body=[method], type_ignores=[]), '<canvas draw>', 'exec'), namespace)
    canvas = SimpleNamespace(_sticker_mode=False, _speech_bubble_mode=False, _zoom=1,
                             _scaled_bitmap_cache=OrderedDict(), _scaled_bitmap_cache_max=6)
    rect = SimpleNamespace(width=8, height=8, x=0, y=0)
    frame = Frame(Image.new('RGB', (16, 16), 'red'))
    image_ref = weakref.ref(frame.image)
    draw = namespace['_draw_frame_image']
    draw(canvas, Mock(), frame, rect)
    draw(canvas, Mock(), frame, rect)
    assert converter.call_count == 1
    frame.unload_image()
    converter.reset_mock()
    gc.collect()
    assert image_ref() is not None
    for color in range(6):
        draw(canvas, Mock(), Frame(Image.new('RGB', (16, 16), color)), rect)
    gc.collect()
    assert len(canvas._scaled_bitmap_cache) == 6
    assert image_ref() is None


@pytest.mark.parametrize('operation', ['thumbnail', 'snapshot', 'clone'])
def test_read_failure_does_not_leave_source_loaded(operation, monkeypatch):
    frame = collection(1).get_frame(0)
    if operation == 'clone':
        # Source-only fallback must restore residency even if pixel copy fails.
        frame._source_path = 'unused.png'
        frame._image_bytes = None
        monkeypatch.setattr(frame, '_load_from_source', lambda: Image.new('RGB', (16, 16)))
    monkeypatch.setattr(Image.Image, 'copy', Mock(side_effect=MemoryError('copy failed')))
    if operation == 'snapshot':
        assert snapshot_original_images([frame]) == []
    else:
        with pytest.raises(MemoryError):
            frame.get_thumbnail() if operation == 'thumbnail' else frame.clone()
    assert not frame.is_loaded


@pytest.mark.parametrize('suffix', ['gif', 'webp', 'apng', 'png', 'jpg', 'bmp', 'sequence'])
def test_export_copy_failure_preserves_source_loaded_set(tmp_path, monkeypatch, suffix):
    frames = collection()
    frames.get_frame(3)._ensure_image_loaded()
    originally_loaded = [frame.is_loaded for frame in frames]
    monkeypatch.setattr(Image.Image, 'copy', Mock(side_effect=MemoryError('copy failed')))
    if suffix == 'sequence':
        result = GifEncoder.save_image_sequence(frames, str(tmp_path), 'frame')
    else:
        result = GifEncoder.save(frames, str(tmp_path / f'out.{suffix}'))
    assert not result.success
    assert [frame.is_loaded for frame in frames] == originally_loaded


def test_dirty_lazy_clone_captures_current_pixels_without_unloading_source():
    frame = Frame(Image.new('RGB', (8, 8), 'red'))
    frame._image = Image.new('RGB', (8, 8), 'blue')
    frame._invalidate_cache()
    clone = frame.clone()
    assert frame.is_loaded
    assert not clone.is_loaded
    assert clone.image.getpixel((0, 0)) == (0, 0, 255)
    frame._image.putpixel((0, 0), (1, 2, 3))
    assert clone.image.getpixel((0, 0)) == (0, 0, 255)


def test_clone_captures_direct_public_image_mutation():
    frame = Frame(Image.new('RGB', (8, 8), 'red'))
    frame.image.putpixel((0, 0), (0, 0, 255))
    clone = frame.clone()
    assert clone.image.getpixel((0, 0)) == (0, 0, 255)
    assert frame.is_loaded
    clone.image.putpixel((0, 0), (0, 255, 0))
    assert frame.image.getpixel((0, 0)) == (0, 0, 255)


def test_recording_editor_clone_edits_and_spool_lifetime(tmp_path):
    import numpy as np
    from core.recording_frames import RecordingFrames

    source = RecordingFrames(0)
    source_ref = weakref.ref(source)
    source.append(np.full((3, 4, 3), (4, 32, 190), dtype=np.uint8))
    frame = Frame.from_recording(source, 0, (4, 3), 70)
    clone = frame.clone()
    del source
    assert not frame.is_loaded and not clone.is_loaded
    assert frame.get_thumbnail().getpixel((0, 0)) == (190, 32, 4)
    assert not frame.is_loaded
    frames = FrameCollection()
    frames.add_frame(frame)
    clone.image.putpixel((0, 0), (1, 2, 3))
    clone.unload_image()
    frames.add_frame(clone)
    path = tmp_path / 'recording.gif'
    settings = EncoderSettings(use_gifsicle=False, loop_count=2)
    result = GifEncoder.save(frames, str(path), settings)
    assert result.success, result.error_message
    assert GifEncoder.estimate_gif_size(frames, settings) == path.stat().st_size
    with Image.open(path) as gif:
        assert gif.info['loop'] == 2 and gif.n_frames == 2
        for index, pixel in enumerate(((190, 32, 4), (1, 2, 3))):
            gif.seek(index)
            assert gif.info['duration'] == 70
            assert gif.convert('RGB').getpixel((0, 0)) == pixel
    assert not frame.is_loaded and not clone.is_loaded
    del frames, frame
    assert source_ref() is None


def test_recording_playback_evicts_to_source_and_clone_preserves_edits():
    import numpy as np
    from core.recording_frames import RecordingFrames
    from editor.core.frame_collection import FrameCollection

    source = RecordingFrames(0)
    frames = FrameCollection()
    for index in range(32):
        source.append(np.full((8, 8, 3), index, dtype=np.uint8))
        frames.add_frame(Frame.from_recording(source, index, (8, 8), 50))
    owner = weakref.ref(source)
    del source
    for _ in range(2):
        for index, frame in enumerate(frames):
            frames.preload_range(index, index)
            assert frame.display_image().getpixel((0, 0)) == (index,) * 3
            if index == 7:
                clone = frame.clone()
            frame.unload_image()
            assert frame.get_memory_usage() == 0
    frames.clear()
    del frame
    assert owner() is not None
    assert clone.display_image().getpixel((0, 0)) == (7, 7, 7)
    clone.image.putpixel((0, 0), (6, 5, 4))
    assert owner() is None
    clone.unload_image()
    assert clone.display_image().getpixel((0, 0)) == (6, 5, 4)
    clone.image.putpixel((0, 0), (1, 2, 3))
    clone.unload_image()
    assert clone.display_image().getpixel((0, 0)) == (1, 2, 3)
