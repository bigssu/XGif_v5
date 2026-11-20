import errno
import gc
import os
import subprocess
import sys
import threading
from types import SimpleNamespace

import numpy as np
import pytest

from core import recording_frames
from core.recording_frames import RecordingFrames


@pytest.mark.parametrize(("budget", "ram_frames"), [(0, 0), (17, 0), (18, 1), (36, 2)])
def test_replay_keeps_exact_frames_within_budget(budget, ram_frames, tmp_path, monkeypatch):
    monkeypatch.setattr(recording_frames.tempfile, "tempdir", str(tmp_path))
    frames = RecordingFrames(budget)
    source = np.zeros((2, 3, 3), dtype=np.uint8)
    for index in range(6):
        source.fill(index)
        frames.append(source[:, ::-1])
    source.fill(99)
    assert len(frames) == 6
    assert frames.resident_bytes == ram_frames * source.nbytes <= budget
    assert frames.disk_bytes == (6 - ram_frames) * source.nbytes
    head = iter(frames)
    assert not next(head).flags.writeable
    assert [int(frame[0, 0, 0]) for frame in frames] == list(range(6))
    assert np.all(frames[-1] == 5)
    assert [int(frame[0, 0, 0]) for frame in head] == list(range(1, 6))
    with pytest.raises(IndexError):
        frames[6]
    with pytest.raises(IndexError):
        frames[-7]


def test_shape_change_and_disk_full_preserve_the_recorded_prefix(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_frames.tempfile, "tempdir", str(tmp_path))
    frames = RecordingFrames(18)
    frame = np.full((2, 3, 3), 1, dtype=np.uint8)
    frames.append(frame)
    frames.append(frame * 2)
    with pytest.raises(ValueError):
        frames.append(frame.transpose(1, 0, 2))
    with pytest.raises(ValueError):
        frames.append(frame.astype(np.float32))
    monkeypatch.setattr(recording_frames.shutil, "disk_usage", lambda _: SimpleNamespace(free=frame.nbytes))
    with pytest.raises(OSError) as error:
        frames.append(frame * 3)
    assert error.value.errno == errno.ENOSPC
    assert len(frames) == 2
    np.testing.assert_array_equal(frames[1], frame * 2)


def test_partial_append_does_not_publish_corrupt_frame(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_frames.tempfile, "tempdir", str(tmp_path))
    frames = RecordingFrames(0)
    frame = np.full((3, 3, 3), 1, dtype=np.uint8)
    frames.append(frame)
    original = frames._file

    class ShortWriter:
        def write(self, array):
            return original.write(memoryview(array).cast("B")[:3])

        def __getattr__(self, name):
            return getattr(original, name)

    frames._file = ShortWriter()
    with pytest.raises(OSError, match="Incomplete write"):
        frames.append(frame * 2)
    assert len(frames) == 1
    assert original.seek(0, os.SEEK_END) == frame.nbytes
    np.testing.assert_array_equal(frames[0], frame)
    frames._file = original
    frames.append(frame * 3)
    np.testing.assert_array_equal(frames[1], frame * 3)


def test_only_owned_temporary_files_are_released(tmp_path, monkeypatch):
    monkeypatch.setattr(recording_frames.tempfile, "tempdir", str(tmp_path))
    keep = tmp_path / "keep"
    keep.touch()
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    first, second = RecordingFrames(0), RecordingFrames(0)
    first.append(frame)
    second.append(frame * 2)
    del first
    gc.collect()
    assert np.all(second[0] == 2)
    del second
    gc.collect()
    assert list(tmp_path.iterdir()) == [keep]


def test_abrupt_process_exit_releases_tempfile(tmp_path):
    code = """
import os, sys, tempfile
import numpy as np
from core.recording_frames import RecordingFrames
tempfile.tempdir = sys.argv[1]
frames = RecordingFrames(0)
frames.append(np.ones((2, 2, 3), dtype=np.uint8))
assert frames.disk_bytes == 12
os._exit(23)
"""
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)], timeout=30)
    assert result.returncode == 23
    assert list(tmp_path.iterdir()) == []


def test_sealing_during_blocked_write_exposes_complete_replayable_prefix(monkeypatch):
    frames = RecordingFrames(12)
    frame = np.ones((2, 2, 3), dtype=np.uint8)
    frames.append(frame)
    frames.append(frame * 2)
    entered = threading.Event()
    resume = threading.Event()
    original = frames._file

    class BlockedWriter:
        def write(self, data):
            entered.set()
            assert resume.wait(3)
            return original.write(data)

        def __getattr__(self, name):
            return getattr(original, name)

    monkeypatch.setattr(frames, "_file", BlockedWriter())
    writer = threading.Thread(target=frames.append, args=(frame * 3,))
    writer.start()
    try:
        assert entered.wait(2)
        frames.seal()
        assert [int(f[0, 0, 0]) for f in frames] == [1, 2]
        np.testing.assert_array_equal(frames[1], frame * 2)
    finally:
        resume.set()
        writer.join(4)
    frames.append(frame * 4)
    assert not writer.is_alive()
    assert len(frames) == 2
    assert frames.disk_bytes == frame.nbytes
