import os
import subprocess
import sys
import threading
import time

import numpy as np
import pytest
from PIL import Image

from core.gif_encoder import GifEncoder


@pytest.fixture
def encoder():
    instance = GifEncoder.__new__(GifEncoder)
    instance._ffmpeg_env = os.environ.copy()
    instance._ffmpeg_path = sys.executable
    instance._progress_callback = None
    instance._finished_callback = None
    instance._error_callback = None
    instance.quality = 'high'
    instance._codec = 'h264'
    return instance


@pytest.mark.parametrize('kind', ['gif', 'mp4'])
def test_noisy_child_does_not_block_frame_writes(encoder, monkeypatch, tmp_path, kind):
    popen = subprocess.Popen
    children = []
    watchdogs = []
    timed_out = []

    def spawn(*args, **kwargs):
        child = popen([sys.executable, '-c',
                       'import sys; sys.stderr.buffer.write(b"x" * 262144); '
                       'sys.stderr.flush(); sys.stdin.buffer.read(); '
                       'open(sys.argv[1], "wb").write(b"encoded")', args[0][-1]], **kwargs)
        children.append(child)

        def kill_stuck_child():
            timed_out.append(True)
            child.kill()

        watchdog = threading.Timer(4, kill_stuck_child)
        watchdog.start()
        watchdogs.append(watchdog)
        return child

    monkeypatch.setattr(subprocess, 'Popen', spawn)
    monkeypatch.setattr(encoder, '_get_best_encoder', lambda codec: 'libx264')
    frame = np.zeros((1024, 1024, 3), dtype=np.uint8)
    try:
        method = encoder.encode if kind == 'gif' else encoder.encode_mp4
        assert method([frame], 10, str(tmp_path / f'out.{kind}'))
        assert not timed_out
    finally:
        for watchdog in watchdogs:
            watchdog.cancel()
            watchdog.join()
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


@pytest.mark.parametrize('read_stdin', [False, True])
def test_deadline_covers_blocked_stdin_and_cleans_up(encoder, monkeypatch, read_stdin):
    popen = subprocess.Popen
    children = []

    def spawn(*args, **kwargs):
        child = popen(*args, **kwargs)
        children.append(child)
        return child

    monkeypatch.setattr(subprocess, 'Popen', spawn)
    watchdog = threading.Timer(4, lambda: [child.kill() for child in children if child.poll() is None])
    before = {thread for thread in threading.enumerate() if thread.name == 'ffmpeg-frame-writer'}
    watchdog.start()
    start = time.monotonic()
    try:
        with pytest.raises(subprocess.TimeoutExpired):
            encoder._run_streamed_ffmpeg(
                [sys.executable, '-c', 'import sys,time; ' +
                 ('sys.stdin.buffer.read(); ' if read_stdin else '') + 'time.sleep(30)'],
                [np.zeros((1024, 1024, 3), dtype=np.uint8)], timeout=0.2)
        watchdog.cancel()
        watchdog.join()
        assert time.monotonic() - start < 3
        assert children[0].poll() is not None
        assert children[0].stdin.closed
        assert not {thread for thread in threading.enumerate()
                    if thread.name == 'ffmpeg-frame-writer'} - before
    finally:
        watchdog.cancel()
        watchdog.join()
        for child in children:
            if child.poll() is None:
                child.kill()
            child.wait(timeout=5)


def test_child_error_keeps_all_stderr(encoder):
    result = encoder._run_streamed_ffmpeg(
        [sys.executable, '-c',
         'import sys; sys.stderr.buffer.write(b"x" * 262144 + b"final error"); sys.exit(7)'],
        [np.zeros((1024, 1024, 3), dtype=np.uint8)])
    assert result.returncode == 7
    assert result.stderr == b'x' * 262144 + b'final error'


@pytest.mark.parametrize('channels', [3, 4])
@pytest.mark.parametrize('kind', ['gif', 'mp4'])
def test_decoded_colors_and_frame_count(tmp_path, channels, kind):
    encoder = GifEncoder()
    if not encoder.is_ffmpeg_available():
        pytest.skip('FFmpeg not installed')
    encoder._get_best_encoder = lambda codec: 'libx264'
    frames = []
    for bgr in [(0, 0, 255), (255, 0, 0)]:
        frame = np.empty((32, 32, channels), dtype=np.uint8)
        frame[:, :, :3] = bgr
        if channels == 4:
            frame[:, :, 3] = 255
        frames.append(frame)
    output = tmp_path / f'colors.{kind}'
    method = encoder.encode if kind == 'gif' else encoder.encode_mp4
    assert method(frames, 10, str(output))
    if kind == 'gif':
        with Image.open(output) as image:
            assert image.n_frames == 2
            decoded = []
            for index in range(image.n_frames):
                image.seek(index)
                decoded.append(np.asarray(image.convert('RGB')))
    else:
        result = subprocess.run(
            [encoder._ffmpeg_path, '-v', 'error', '-i', str(output),
             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
            capture_output=True, timeout=10, check=True)
        decoded = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 32, 32, 3)
        assert len(decoded) == 2
    for frame, expected in zip(decoded, [(255, 0, 0), (0, 0, 255)], strict=True):
        assert np.max(np.abs(frame.astype(int) - expected)) < 10


@pytest.mark.parametrize('frame', [
    np.zeros((4, 4), dtype=np.uint8),
    np.zeros((4, 4, 2), dtype=np.uint8),
    np.zeros((4, 4, 3), dtype=np.float32),
    np.zeros((2, 4, 3), dtype=np.uint8),
])
def test_invalid_frame_is_rejected_without_leaking_writer(encoder, frame):
    before = {thread for thread in threading.enumerate() if thread.name == 'ffmpeg-frame-writer'}
    with pytest.raises(ValueError, match='Invalid BGR/BGRA frame'):
        encoder._run_streamed_ffmpeg(
            [sys.executable, '-c', 'import sys; sys.stdin.buffer.read()'],
            [np.zeros((4, 4, 3), dtype=np.uint8), frame], timeout=2)
    assert not {thread for thread in threading.enumerate()
                    if thread.name == 'ffmpeg-frame-writer'} - before

@pytest.mark.parametrize('kind', ['gif', 'mp4'])
@pytest.mark.parametrize('failure', ['encode', 'replace'])
def test_failed_export_preserves_existing_destination(encoder, monkeypatch, tmp_path, kind, failure):
    output = tmp_path / f'existing.{kind}'
    output.write_bytes(b'original')
    finished = []
    encoder.set_finished_callback(finished.append)

    attempted = []

    def partial(frames, fps, output_path, *args):
        attempted.append(output_path)
        from pathlib import Path
        Path(output_path).write_bytes(b'partial')
        return failure == 'replace'

    monkeypatch.setattr(encoder, '_encode_gif' if kind == 'gif' else '_encode_mp4', partial, raising=False)
    if failure == 'replace':
        def fail_replace(*args):
            raise PermissionError('destination locked')
        monkeypatch.setattr(os, 'replace', fail_replace)
    method = encoder.encode if kind == 'gif' else encoder.encode_mp4
    assert not method([np.zeros((4, 4, 3), dtype=np.uint8)], 10, str(output))
    assert len(attempted) == 1
    assert output.read_bytes() == b'original'
    assert not finished
    assert list(tmp_path.iterdir()) == [output]


@pytest.mark.parametrize('kind', ['gif', 'mp4'])
def test_finished_callback_observes_committed_output(encoder, monkeypatch, tmp_path, kind):
    output = tmp_path / f'existing.{kind}'
    output.write_bytes(b'original')
    finished = []
    encoder.set_finished_callback(lambda path: finished.append((path, output.read_bytes())))

    def complete(frames, fps, output_path, *args):
        from pathlib import Path
        assert Path(output_path).parent == output.parent
        assert output_path != str(output)
        Path(output_path).write_bytes(b'complete')
        return True

    monkeypatch.setattr(encoder, '_encode_gif' if kind == 'gif' else '_encode_mp4', complete, raising=False)
    method = encoder.encode if kind == 'gif' else encoder.encode_mp4
    assert method([np.zeros((4, 4, 3), dtype=np.uint8)], 10, str(output))
    assert finished == [(str(output), b'complete')]
    assert list(tmp_path.iterdir()) == [output]


def test_child_exit_zero_before_reading_all_frames_is_not_success(encoder):
    with pytest.raises(OSError):
        encoder._run_streamed_ffmpeg(
            [sys.executable, '-c', 'pass'],
            [np.zeros((1024, 1024, 3), dtype=np.uint8)], timeout=2)



def test_deadline_cleanup_allows_unrelated_timer_to_finish(encoder, monkeypatch):
    release_timer = threading.Event()
    timer = threading.Timer(0, release_timer.wait)
    timer.start()
    write_frames = encoder._write_frames_to_pipe

    def write_after_timer_finishes(*args, **kwargs):
        release_timer.set()
        timer.join()
        return write_frames(*args, **kwargs)

    monkeypatch.setattr(encoder, '_write_frames_to_pipe', write_after_timer_finishes)
    try:
        assert timer.is_alive()
        test_deadline_covers_blocked_stdin_and_cleans_up(encoder, monkeypatch, False)
        assert not timer.is_alive()
    finally:
        release_timer.set()
        timer.join()

@pytest.mark.parametrize('codec', ['h264', 'h265'])
@pytest.mark.parametrize('mode', ['auto', 'explicit', 'cpu_failure'])
def test_mp4_auto_retries_hardware_failure_once(encoder, monkeypatch, tmp_path, codec, mode, caplog):
    from pathlib import Path

    encoder._codec = codec
    encoder._preferred_encoder = 'nvenc' if mode == 'explicit' else 'auto'
    hardware = 'h264_nvenc' if codec == 'h264' else 'hevc_nvenc'
    cpu = 'libx264' if codec == 'h264' else 'libx265'
    monkeypatch.setattr(encoder, '_get_best_encoder', lambda codec: hardware)
    output = tmp_path / 'out.mp4'
    output.write_bytes(b'original')
    frames = [np.zeros((48, 64, 3), dtype=np.uint8)]
    errors, finished, attempts = [], [], []
    encoder.set_error_callback(errors.append)
    encoder.set_finished_callback(finished.append)

    def run(cmd, submitted, total_steps):
        assert not errors and not finished
        assert submitted is frames
        selected = cmd[cmd.index('-c:v') + 1]
        attempts.append(selected)
        Path(cmd[-1]).write_bytes(b'partial' if selected == hardware else b'complete')
        if selected == cpu:
            assert '-cq' not in cmd and '-crf' in cmd
        return subprocess.CompletedProcess(cmd, 7 if selected == hardware else 9 if mode == 'cpu_failure' else 0,
                                           stderr=b'InitializeEncoder failed' if selected == hardware else b'CPU error')

    monkeypatch.setattr(encoder, '_run_streamed_ffmpeg', run)
    assert encoder.encode_mp4(frames, 10, str(output)) is (mode == 'auto')
    assert attempts == ([hardware] if mode == 'explicit' else [hardware, cpu])
    assert output.read_bytes() == (b'complete' if mode == 'auto' else b'original')
    assert finished == ([str(output)] if mode == 'auto' else [])
    assert len(errors) == (0 if mode == 'auto' else 1)
    if mode == 'cpu_failure':
        assert 'exit 7' in caplog.text and 'InitializeEncoder failed' in caplog.text
        assert 'returncode=9' in caplog.text and 'CPU error' in caplog.text
        assert 'exit 7' in errors[0] and 'InitializeEncoder failed' in errors[0] and 'CPU error' in errors[0]
    assert list(tmp_path.iterdir()) == [output]


def test_real_small_frame_auto_mp4(tmp_path):
    encoder = GifEncoder()
    if not encoder.is_ffmpeg_available():
        pytest.skip('FFmpeg not installed')
    frame = np.zeros((48, 64, 3), dtype=np.uint8)
    frame[:, :, 2] = 255
    output = tmp_path / 'small.mp4'
    assert encoder.encode_mp4([frame], 10, str(output))
    result = subprocess.run([encoder._ffmpeg_path, '-v', 'error', '-i', str(output),
                             '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                            capture_output=True, check=True, timeout=10)
    pixels = np.frombuffer(result.stdout, dtype=np.uint8).reshape(-1, 48, 64, 3)
    assert len(pixels) == 1
    assert np.max(np.abs(pixels.astype(int) - (255, 0, 0))) < 10


@pytest.mark.parametrize('message', [b'No space left on device', b'Invalid data found when processing input',
                                   b'Error opening output file: Permission denied'])
def test_mp4_does_not_retry_nonencoder_errors(encoder, monkeypatch, tmp_path, message):
    encoder._preferred_encoder = 'auto'
    monkeypatch.setattr(encoder, '_get_best_encoder', lambda codec: 'h264_nvenc')
    attempts = []

    def run(cmd, frames, total_steps):
        attempts.append(cmd)
        return subprocess.CompletedProcess(cmd, 77, stderr=message)

    monkeypatch.setattr(encoder, '_run_streamed_ffmpeg', run)
    output = tmp_path / 'out.mp4'
    output.write_bytes(b'original')
    assert not encoder.encode_mp4([np.zeros((48, 64, 3), dtype=np.uint8)], 10, str(output))
    assert len(attempts) == 1
    assert output.read_bytes() == b'original'


@pytest.mark.parametrize(('encoder_name', 'message'), [
    ('h264_nvenc', 'InitializeEncoder failed: Frame Dimension less than the minimum'),
    ('hevc_nvenc', 'No NVENC capable devices found'),
    ('h264_qsv', 'Error initializing an internal MFX session: unsupported'),
    ('hevc_amf', 'AMF failed to initialise'),
])
def test_hardware_initialization_errors_are_retryable(encoder_name, message):
    assert GifEncoder._is_hardware_encoder_failure(encoder_name, message)
