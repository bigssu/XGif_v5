"""FFmpeg video loading without optional Python codec packages."""
import io
import json
import subprocess
import sys
import threading
import time
import tracemalloc

import pytest

from core.ffmpeg_installer import FFmpegManager
from editor.core.video_decoder import VideoDecoder, VideoInfo


@pytest.fixture
def video(tmp_path):
    path = tmp_path / 'clip.mp4'
    path.touch()
    return path


@pytest.fixture
def backend(monkeypatch):
    monkeypatch.setattr(FFmpegManager, 'get_ffmpeg_executable', lambda: 'ffmpeg')
    monkeypatch.setattr('shutil.which', lambda name: name)


class CountingBuffer(io.BytesIO):
    bytes_read = 0

    def read(self, size=-1):
        data = super().read(size)
        self.bytes_read += len(data)
        return data


class FakeProcess:
    def __init__(self, count):
        self.stdout = CountingBuffer(b'\x10\x20\x30' * 4 * count)
        self.returncode = None
        self.killed = False

    def poll(self):
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9

    def wait(self, timeout=None):
        if self.returncode is None:
            self.returncode = 0
        return self.returncode


@pytest.mark.parametrize('fps,duration,cap,count', [
    (24, 2, 500, 20), (5, 2, 500, 10), (24, 2, 3, 3),
    (24, 1_000_000, 3, 3),
])
def test_sampling_preserves_duration_and_bounds_reads(video, backend, monkeypatch, fps, duration, cap, count):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, fps, duration))
    process = FakeProcess(count + 1)
    commands = []

    def popen(command, **kwargs):
        commands.append(command)
        return process

    monkeypatch.setattr(subprocess, 'Popen', popen)
    progress = []
    result = VideoDecoder.load(str(video), target_fps=10, max_frames=cap,
                               progress_callback=lambda current, total: progress.append((current, total)))
    assert result.success, result.error_message
    assert result.frames.frame_count == count
    assert sum(frame.delay_ms for frame in result.frames) == round(duration * 1000)
    assert progress == [(index, count) for index in range(1, count + 1)]
    assert commands[0][commands[0].index('-frames:v') + 1] == str(count)
    assert process.stdout.bytes_read == 12 * count
    assert process.stdout.closed


@pytest.mark.parametrize('metadata', [
    {}, {'streams': []}, {'streams': [None]}, {'streams': [{'width': 0, 'height': 2}]},
    {'streams': [{'width': 2, 'height': 2, 'avg_frame_rate': '0/0', 'duration': '2'}]},
    {'streams': [{'width': 2, 'height': 2, 'avg_frame_rate': '24/1', 'duration': 'nan'}]},
])
def test_invalid_metadata_is_rejected(video, backend, monkeypatch, metadata):
    monkeypatch.setattr(VideoDecoder, '_probe', lambda *args: json.dumps(metadata))
    assert VideoDecoder.get_video_info(str(video)) is None
    result = VideoDecoder.load(str(video))
    assert not result.success


def test_probe_uses_stream_metadata_and_format_duration(video, backend, monkeypatch):
    metadata = {'streams': [{'width': 8, 'height': 6, 'avg_frame_rate': '24/1',
                              'codec_name': 'h264', 'nb_frames': '48'}], 'format': {'duration': '2'}}
    monkeypatch.setattr(VideoDecoder, '_probe', lambda *args: json.dumps(metadata))
    assert VideoDecoder.get_video_info(str(video)) == VideoInfo(8, 6, 24, 2, 48, 'h264')


@pytest.mark.parametrize('rotation_fields,size', [
    ({'side_data_list': [{'rotation': -90}]}, (6, 8)),
    ({'side_data_list': [{'rotation': 180}]}, (8, 6)),
    ({'tags': {'rotate': '270'}}, (6, 8)),
    ({'side_data_list': [{'rotation': 0}], 'tags': {'rotate': '90'}}, (8, 6)),
])
def test_probe_rotation_dimensions(video, backend, monkeypatch, rotation_fields, size):
    stream = {'width': 8, 'height': 6, 'avg_frame_rate': '24/1', 'duration': '2', **rotation_fields}
    monkeypatch.setattr(VideoDecoder, '_probe', lambda *args: json.dumps({'streams': [stream]}))
    info = VideoDecoder.get_video_info(str(video))
    assert (info.width, info.height) == size


def test_missing_backend_is_unavailable(monkeypatch):
    monkeypatch.setattr(FFmpegManager, 'get_ffmpeg_executable', lambda: None)
    assert not VideoDecoder.is_available()


def test_callback_exception_terminates_decoder(video, backend, monkeypatch):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 24, 2))
    process = FakeProcess(20)
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: process)

    def cancel(current, total):
        raise RuntimeError('cancelled')

    result = VideoDecoder.load(str(video), progress_callback=cancel)
    assert not result.success
    assert 'cancelled' in result.error_message
    assert process.killed
    assert process.stdout.closed


@pytest.mark.parametrize('options', [
    {'max_frames': 0}, {'target_fps': 0}, {'start_time': -1},
    {'start_time': 3}, {'end_time': float('nan')}, {'resize': (0, 2)},
])
def test_invalid_options_do_not_start_decoder(video, backend, monkeypatch, options):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 24, 2))
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('decoder started'))
    assert not VideoDecoder.load(str(video), **options).success


def test_incomplete_stream_is_not_reported_as_success(video, backend, monkeypatch):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 24, 2))
    process = FakeProcess(1)
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: process)
    assert not VideoDecoder.load(str(video)).success
    assert process.killed
    assert process.stdout.closed


def test_large_metadata_has_bounded_python_memory(video, backend, monkeypatch):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 24, 1_000_000))
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: FakeProcess(3))
    tracemalloc.start()
    try:
        result = VideoDecoder.load(str(video), max_frames=3)
        _, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    assert result.success, result.error_message
    assert result.frames.frame_count == 3
    assert peak < 2_000_000
    print(f'1,000,000-second clip: 3 frames; Python peak allocation {peak:,} bytes')


@pytest.mark.parametrize('fps,cap,start,end,count,milliseconds', [
    (24, 500, 0, None, 20, 2000), (5, 500, 0, None, 10, 2000),
    (24, 3, 0, None, 3, 2000), (24, 500, 0.5, 1.5, 10, 1000),
])
def test_real_ffmpeg_roundtrip(tmp_path, fps, cap, start, end, count, milliseconds):
    if not VideoDecoder.is_available():
        pytest.skip('FFmpeg/FFprobe unavailable')
    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    path = tmp_path / 'synthetic.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    f'testsrc2=size=32x24:rate={fps}:duration=2', '-c:v', 'mpeg4', str(path)],
                   check=True, capture_output=True, timeout=30)
    info = VideoDecoder.get_video_info(str(path))
    assert (info.width, info.height, info.fps, info.duration) == (32, 24, fps, 2)
    result = VideoDecoder.load(str(path), target_fps=10, max_frames=cap,
                               start_time=start, end_time=end, resize=(16, 12))
    assert result.success, result.error_message
    assert result.frames.frame_count == count
    assert sum(frame.delay_ms for frame in result.frames) == milliseconds
    assert all(frame.image.size == (16, 12) for frame in result.frames)


@pytest.mark.parametrize('rotation', [90, 270])
def test_real_ffmpeg_rotation_preserves_dimensions_and_colors(tmp_path, rotation):
    if not VideoDecoder.is_available():
        pytest.skip('FFmpeg/FFprobe unavailable')
    ffmpeg = FFmpegManager.get_ffmpeg_executable()
    source = tmp_path / 'source.mp4'
    rotated = tmp_path / 'rotated.mp4'
    subprocess.run([ffmpeg, '-v', 'error', '-f', 'lavfi', '-i',
                    'color=red:size=32x24:rate=2:duration=1,drawbox=x=16:y=0:w=16:h=24:color=blue:t=fill',
                    '-c:v', 'mpeg4', str(source)], check=True, capture_output=True, timeout=30)
    subprocess.run([ffmpeg, '-v', 'error', '-display_rotation', str(rotation), '-i', str(source),
                    '-c', 'copy', str(rotated)], check=True, capture_output=True, timeout=30)
    info = VideoDecoder.get_video_info(str(rotated))
    assert (info.width, info.height) == (24, 32)
    for resize in (None, (12, 16)):
        result = VideoDecoder.load(str(rotated), resize=resize)
        assert result.success, result.error_message
        assert result.frames.frame_count == 2
        image = result.frames.get_frame(0).image
        width, height = resize or (24, 32)
        assert image.size == (width, height)
        top = image.getpixel((width // 2, height // 4))
        bottom = image.getpixel((width // 2, height * 3 // 4))
        red, blue = (bottom, top) if rotation == 90 else (top, bottom)
        assert red[0] > 200 and red[2] < 30
        assert blue[2] > 200 and blue[0] < 30


@pytest.mark.parametrize('stop', ['cancel', 'timeout'])
@pytest.mark.parametrize('stage', ['probe', 'decode'])
def test_stalled_pipe_stops_child_without_thread_leak(video, backend, monkeypatch, stop, stage):
    if stage == 'decode':
        monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 24, 2))
    original_popen = subprocess.Popen
    children = []
    cancel = threading.Event()
    timer = None

    def popen(command, **kwargs):
        process = original_popen([sys.executable, '-c', 'import time; time.sleep(60)'], **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(subprocess, 'Popen', popen)
    before = set(threading.enumerate())
    if stop == 'cancel':
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
    started = time.monotonic()
    try:
        result = VideoDecoder.load(str(video), cancel_event=cancel, timeout=0.35 if stop == 'timeout' else 10)
    finally:
        if timer is not None:
            timer.join()
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait()
    assert time.monotonic() - started < 3
    assert not result.success and result.frames is None
    assert result.cancelled is (stop == 'cancel')
    if stop == 'timeout':
        assert '시간' in result.error_message
    assert children and all(child.stdout.closed for child in children)
    assert set(threading.enumerate()) <= before


def test_probe_time_counts_toward_decode_deadline(video, backend, monkeypatch):
    def info(path, **kwargs):
        time.sleep(0.1)
        return VideoInfo(2, 2, 24, 2)

    monkeypatch.setattr(VideoDecoder, 'get_video_info', info)
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('expired decode started'))
    result = VideoDecoder.load(str(video), timeout=0.05)
    assert not result.success and not result.cancelled
    assert '시간' in result.error_message


def test_precancelled_video_does_not_start_child(video, backend, monkeypatch):
    event = threading.Event()
    event.set()
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: pytest.fail('cancelled decode started'))
    result = VideoDecoder.load(str(video), cancel_event=event)
    assert result.cancelled and result.frames is None


def test_real_corrupt_video_returns_no_partial_frames(video):
    video.write_bytes(b'not an MP4 container')
    result = VideoDecoder.load(str(video), timeout=10)
    assert not result.success and not result.cancelled and result.frames is None


def test_nonzero_exit_discards_decoded_frames(video, backend, monkeypatch):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 1, 1))
    process = FakeProcess(1)
    process.returncode = 1
    monkeypatch.setattr(subprocess, 'Popen', lambda *args, **kwargs: process)
    result = VideoDecoder.load(str(video))
    assert not result.success and result.frames is None
    assert process.stdout.closed


def test_deadline_covers_child_exit_after_last_frame(video, backend, monkeypatch):
    monkeypatch.setattr(VideoDecoder, 'get_video_info', lambda path, **kwargs: VideoInfo(2, 2, 1, 1))
    original_popen = subprocess.Popen
    children = []

    def popen(command, **kwargs):
        process = original_popen([sys.executable, '-c',
                                  "import os,time; os.write(1,b'012345678901'); time.sleep(60)"], **kwargs)
        children.append(process)
        return process

    monkeypatch.setattr(subprocess, 'Popen', popen)
    started = time.monotonic()
    result = VideoDecoder.load(str(video), timeout=0.35)
    assert time.monotonic() - started < 3
    assert not result.success and not result.cancelled and result.frames is None
    assert '시간' in result.error_message
    assert children[0].poll() is not None and children[0].stdout.closed
