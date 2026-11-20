import io

import numpy as np
import pytest
from PIL import Image

from core.gif_encoder import GifEncoder, write_palette_gif


class Replay:
    """Models a recording store that loads fresh arrays and only supports integer indexing."""
    def __init__(self, count=5):
        self.count = count
        self.fail = False
        self.passes = 0

    def __len__(self):
        return self.count

    def __getitem__(self, index):
        assert isinstance(index, int)
        frame = np.zeros((20, 24, 4), dtype=np.uint8)
        frame[:, :, 0] = 255
        frame[:, :, 3] = index
        if index >= 2:
            frame[3:9, 2:10, :3] = (0, 0, 255)
        if index >= 4:
            frame[10:16, 4:12, :3] = (0, 255, 0)
        return frame

    def __iter__(self):
        self.passes += 1
        for index in range(self.count):
            if self.fail and index == 3:
                raise OSError("unreadable recording")
            yield self[index]


def decoded(source):
    result = []
    with Image.open(source) as image:
        assert image.info["loop"] == 0
        for index in range(image.n_frames):
            image.seek(index)
            result.append((image.convert("RGB").tobytes(), image.info.get("duration", 0)))
    return result


@pytest.mark.parametrize("optimize", [True, False])
def test_streamed_palettes_match_pillow_animation(optimize):
    frames = Replay()
    timings = [31, 49, 50, 70, 31]
    quantized = [Image.fromarray(bgr[:, :, 2::-1]).quantize() for bgr in frames]
    reference = io.BytesIO()
    quantized[0].save(reference, format="GIF", save_all=True, append_images=quantized[1:],
                      duration=timings, optimize=optimize, loop=0)
    actual = io.BytesIO()

    def source():
        for index, pair in enumerate(zip(quantized, timings)):
            if index == 3:
                assert actual.tell() > 0
            yield pair

    write_palette_gif(actual, source(), optimize=optimize)
    assert decoded(actual) == decoded(reference)


def test_long_still_run_spans_multiple_gif_delays():
    image = Image.new("RGB", (5, 5), "green").quantize()
    actual = io.BytesIO()
    write_palette_gif(actual, [(image, 650000), (image, 6000)])
    frames = decoded(actual)
    assert len(frames) == 2
    assert sum(delay for _, delay in frames) == 656000
    assert frames[0][0] == frames[1][0]


def test_pillow_capture_can_retry_from_same_store_without_overwriting(tmp_path):
    encoder = GifEncoder.__new__(GifEncoder)
    encoder._ffmpeg_path = None
    encoder._progress_callback = encoder._error_callback = encoder._finished_callback = None
    encoder.quality = "medium"
    recording = Replay()
    output = tmp_path / "capture.gif"
    output.write_bytes(b"earlier recording")
    recording.fail = True
    assert not encoder.encode(recording, 20, str(output))
    assert output.read_bytes() == b"earlier recording"
    assert list(tmp_path.iterdir()) == [output]
    recording.fail = False
    assert encoder.encode(recording, 20, str(output))
    expected = [(recording[index][:, :, 2::-1].tobytes(), duration)
                for index, duration in [(0, 100), (2, 100), (4, 50)]]
    assert decoded(output) == expected
    assert recording.passes == 2

def test_both_ffmpeg_passes_replay_a_disk_backed_capture(tmp_path):
    from core.recording_frames import RecordingFrames

    encoder = GifEncoder()
    if not encoder.is_ffmpeg_available():
        pytest.skip("FFmpeg not installed")
    recording = RecordingFrames(budget_bytes=0)
    for index in range(5):
        bgr = np.zeros((32, 32, 3), dtype=np.uint8)
        bgr[:, index * 4:index * 4 + 4, 2] = 255
        recording.append(bgr)
    output = tmp_path / "disk.gif"
    assert recording.disk_bytes == 5 * 32 * 32 * 3
    assert encoder.encode(recording, 10, str(output))
    expected = [(frame[:, :, ::-1].tobytes(), 100) for frame in recording]
    assert decoded(output) == expected

@pytest.mark.parametrize("optimize", [True, False])
def test_mixed_size_editor_rejects_save_and_preserves_original(tmp_path, optimize):
    from editor.core.editor_gif_encoder import EncoderSettings
    from editor.core.editor_gif_encoder import GifEncoder as EditorEncoder
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection

    source = FrameCollection()
    source.add_frame(Frame(Image.new("RGB", (8, 4), "red")))
    wider = Image.new("RGB", (16, 4), "red")
    wider.paste("blue", (8, 0, 16, 4))
    source.add_frame(Frame(wider))
    output = tmp_path / "mixed.gif"
    output.write_bytes(b"original")
    result = EditorEncoder.save(source, str(output), EncoderSettings(optimize=optimize))
    assert not result.success and "(16, 4)" in result.error_message
    assert output.read_bytes() == b"original"


@pytest.mark.parametrize('method', ['adaptive', 'mediancut', 'maxcoverage', 'fastoctree', 'libimagequant'])
def test_editor_indexed_transparency_survives_quantization(tmp_path, method):
    from editor.core.editor_gif_encoder import EncoderSettings, QuantizationMethod
    from editor.core.editor_gif_encoder import GifEncoder as EditorEncoder
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection

    image = Image.new('P', (4, 4), 0)
    image.putpalette([50, 100, 200, 90, 10, 30])
    image.info['transparency'] = 0
    image.putpixel((1, 1), 1)
    collection = FrameCollection()
    collection.add_frame(Frame(image))
    output = tmp_path / 'indexed.gif'
    settings = EncoderSettings(quantization=QuantizationMethod(method), use_gifsicle=False)
    assert EditorEncoder.save(collection, str(output), settings).success
    with Image.open(output) as actual:
        assert actual.convert('RGBA').getpixel((0, 0))[3] == 0
        assert actual.convert('RGBA').getpixel((1, 1)) == (90, 10, 30, 255)

def test_progressing_ffmpeg_pass_can_exceed_idle_timeout(tmp_path):
    import os
    import sys
    import time

    class SlowReplay(Replay):
        def __iter__(self):
            for index in range(len(self)):
                time.sleep(0.1)
                yield self[index]

    encoder = GifEncoder.__new__(GifEncoder)
    encoder._ffmpeg_env = os.environ.copy()
    capture = SlowReplay(count=15)
    cmd = [sys.executable, '-c', 'import sys; sys.stdin.buffer.read()']
    start = time.monotonic()
    assert encoder._run_streamed_ffmpeg(cmd, capture, timeout=1).returncode == 0
    assert time.monotonic() - start >= 1


@pytest.mark.parametrize("backend", ["ffmpeg", "pillow"])
@pytest.mark.parametrize("fps,count", [(15, 15), (29.97, 37), (60, 60), (120, 120), (120, 1)])
def test_gif_preserves_motion_and_cumulative_duration(tmp_path, fps, count, backend):
    from core.gif_encoder import gif_frame_timing

    encoder = GifEncoder()
    if backend == "ffmpeg" and not encoder.is_ffmpeg_available():
        pytest.skip("FFmpeg not installed")
    if backend == "pillow":
        encoder._ffmpeg_path = None
    frames = [np.zeros((16, 16, 3), dtype=np.uint8) for _ in range(count)]
    for index, frame in enumerate(frames):
        frame[index // 16, index % 16] = 255
    output = tmp_path / "timing.gif"
    assert encoder.encode(frames, fps, str(output))
    actual = decoded(output)
    expected = list(gif_frame_timing(count, fps))
    assert expected[0][0] == 0 and expected[-1][0] == count - 1
    assert sum(delay for _, delay in actual) == int(count * 100 / fps + 0.5) * 10
    assert all(delay >= 10 for _, delay in actual)
    assert actual == [(frames[index].tobytes(), delay) for index, delay in expected]


@pytest.mark.parametrize("fmt", ["gif", "mp4"])
def test_output_created_mid_encode_survives_no_overwrite(tmp_path, monkeypatch, fmt):
    from pathlib import Path

    encoder = GifEncoder()
    destination = tmp_path / ("capture." + fmt)

    def concurrent_save(frames, fps, staged, *args):
        destination.write_bytes(b"other process")
        Path(staged).write_bytes(b"encoded")
        return True

    monkeypatch.setattr(encoder, "_encode_" + fmt, concurrent_save)
    encode = encoder.encode if fmt == "gif" else encoder.encode_mp4
    assert not encode([], 15, str(destination), overwrite=False)
    assert destination.read_bytes() == b"other process"
    assert list(tmp_path.iterdir()) == [destination]


def test_slow_capture_splits_holds_exceeding_gif_delay_limit(tmp_path):
    encoder = GifEncoder()
    output = tmp_path / "slow.gif"
    frames = [np.zeros((4, 4, 3), dtype=np.uint8)]
    assert encoder.encode(frames, 0.001, str(output))
    assert [duration for _, duration in decoded(output)] == [655350, 344650]


@pytest.mark.parametrize("loop", [None, 0, 3])
def test_editor_loop_and_fractional_delays_roundtrip(loop):
    frames = [Image.new("RGB", (2, 2), (red, 0, 0)).quantize() for red in range(15)]
    output = io.BytesIO()
    write_palette_gif(output, ((frame, 67) for frame in frames), loop=loop)
    with Image.open(output) as actual:
        assert actual.info.get("loop") == loop
        durations = []
        for index in range(actual.n_frames):
            actual.seek(index)
            durations.append(actual.info["duration"])
        assert sum(durations) == 1010
