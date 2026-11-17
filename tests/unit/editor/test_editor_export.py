"""Editor export round trips and failure-safe replacement."""
from pathlib import Path

import pytest
from PIL import Image

from editor.core import editor_gif_encoder as encoder_module
from editor.core.editor_gif_encoder import EncoderSettings, GifEncoder, SaveResult
from editor.core.frame import Frame
from editor.core.frame_collection import FrameCollection


@pytest.fixture
def frames():
    collection = FrameCollection()
    for color, delay in zip(('red', 'green', 'blue'), (70, 130, 230), strict=True):
        collection.add_frame(Frame(Image.new('RGBA', (8, 8), color), delay_ms=delay))
    return collection


@pytest.mark.parametrize('suffix', ['.apng', '.png'])
def test_apng_keeps_every_animation_frame_and_duration(tmp_path, frames, suffix):
    output = tmp_path / f'animation{suffix}'
    result = GifEncoder.save(frames, str(output), EncoderSettings(loop_count=2))
    assert result.success, result.error_message
    assert result.file_size == output.stat().st_size
    with Image.open(output) as image:
        assert not image.info.get('default_image', False)
        assert image.n_frames == frames.frame_count
        assert image.info['loop'] == 2
        for index, frame in enumerate(frames):
            image.seek(index)
            assert image.convert('RGBA').tobytes() == frame.image.tobytes()
            assert image.info['duration'] == frame.delay_ms
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize('failure', ['result', 'exception', 'replace'])
@pytest.mark.parametrize('existing', [True, False])
def test_failed_save_preserves_existing_file(tmp_path, frames, monkeypatch, failure, existing):
    output = tmp_path / 'original.gif'
    if existing:
        output.write_bytes(b'original contents')

    def encode(collection, path, settings):
        path.write_bytes(b'partial contents')
        if failure == 'exception':
            raise OSError('encoding failed')
        if failure == 'result':
            return SaveResult.error('encoding failed')
        return SaveResult.ok(path.stat().st_size)

    def replace(source, destination):
        raise PermissionError('replacement denied')

    monkeypatch.setattr(GifEncoder, '_save_gif', encode)
    if failure == 'replace':
        monkeypatch.setattr('os.replace', replace)
    result = GifEncoder.save(frames, str(output))
    assert not result.success
    assert 'failed' in result.error_message or 'denied' in result.error_message
    if existing:
        assert output.read_bytes() == b'original contents'
    else:
        assert not output.exists()
    assert list(tmp_path.iterdir()) == ([output] if existing else [])


@pytest.mark.parametrize('suffix', ['.gif', '.webp', '.apng', '.png', '.jpg', '.jpeg', '.bmp'])
@pytest.mark.parametrize('frame_count', [1, 3])
def test_save_all_formats_replaces_destination(tmp_path, frames, suffix, frame_count):
    while frames.frame_count > frame_count:
        frames.delete_frame(frames.frame_count - 1)
    output = tmp_path / f'original{suffix}'
    output.write_bytes(b'original contents')
    result = GifEncoder.save(frames, str(output), EncoderSettings(use_gifsicle=False))
    assert result.success, result.error_message
    assert result.file_size == output.stat().st_size > 0
    with Image.open(output) as image:
        image.load()
        assert image.size == (8, 8)
    assert list(tmp_path.iterdir()) == [output]


def test_gifsicle_only_receives_staged_file(tmp_path, frames, monkeypatch):
    output = tmp_path / 'original.gif'
    output.write_bytes(b'original contents')
    seen = []

    def optimize(file_path, lossy, opt_level):
        staged = Path(file_path)
        assert staged != output
        assert staged.parent == output.parent
        assert staged.suffix == output.suffix
        assert output.read_bytes() == b'original contents'
        seen.append(staged)
        return staged.stat().st_size

    monkeypatch.setattr(encoder_module, '_gifsicle_available', True)
    monkeypatch.setattr(GifEncoder, '_optimize_with_gifsicle', optimize)
    result = GifEncoder.save(frames, str(output))
    assert result.success, result.error_message
    assert len(seen) == 1
    assert result.file_size == output.stat().st_size
    assert list(tmp_path.iterdir()) == [output]
