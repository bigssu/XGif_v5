"""Public decoder cancellation must never return partially loaded success."""
import threading
import time

import pytest
from PIL import Image

from editor.core.gif_decoder import GifDecoder
from editor.core.video_decoder import VideoDecoder, VideoLoadResult


@pytest.fixture
def gif(tmp_path):
    path = tmp_path / 'animation.gif'
    images = [Image.new('RGB', (8, 8), color) for color in ('red', 'blue', 'green')]
    images[0].save(path, save_all=True, append_images=images[1:], duration=100)
    return path


@pytest.mark.parametrize('method', ['event', 'callback'])
def test_gif_cancel_discards_partial_frames(gif, method):
    event = threading.Event()

    def progress(current, total):
        if method == 'event':
            event.set()
        else:
            raise InterruptedError('cancelled')

    result = GifDecoder.load(str(gif), cancel_event=event, progress_callback=progress)
    assert result.cancelled and not result.success
    assert result.frames is None


def test_precancelled_gif_never_opens_image(gif, monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(Image, 'open', lambda *args: pytest.fail('opened image'))
    assert GifDecoder.load(str(gif), cancel_event=event).cancelled


def test_video_dispatch_forwards_controls_and_cancelled_result(tmp_path, monkeypatch):
    path = tmp_path / 'clip.mp4'
    path.touch()
    event = threading.Event()

    def load(file_path, **kwargs):
        assert kwargs['cancel_event'] is event
        assert kwargs['timeout'] == 12
        return VideoLoadResult(cancelled=True)

    monkeypatch.setattr(VideoDecoder, 'load', load)
    result = GifDecoder.load(str(path), cancel_event=event, timeout=12)
    assert result.cancelled and not result.success and result.frames is None


def test_gif_deadline_discards_partial_frames(gif):
    result = GifDecoder.load(str(gif), timeout=0.02,
                             progress_callback=lambda *args: time.sleep(0.04))
    assert not result.success and not result.cancelled and result.frames is None
    assert '시간' in result.error_message
