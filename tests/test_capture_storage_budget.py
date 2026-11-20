"""End-to-end capture budget, handoff, and failure notification checks."""

import threading

import numpy as np
import pytest

from core.recording_frames import RecordingFrames
from core.screen_recorder import ScreenRecorder


class Backend:
    supports_managed_color = True

    def __init__(self):
        self.value = 0

    def start(self, region, target_fps=30):
        return True

    def get_name(self):
        return "gdi"

    def grab(self):
        self.value += 1
        return np.full((2, 2, 3), self.value, dtype=np.uint8)

    def stop(self):
        pass


def recorder_with_budget(frame_bytes, spill=False):
    recorder = ScreenRecorder(backend_factory=lambda name: Backend())
    recorder.set_capture_backend("gdi")
    recorder.set_region(0, 0, 2, 2)
    recorder.fps = 120
    recorder.include_cursor = False
    recorder.show_click_highlight = False
    recorder.configure_frame_storage(memory_limit_mb=frame_bytes / 1024**2, spill_to_disk=spill)
    return recorder


@pytest.mark.parametrize(("budget", "count"), [(23, 1), (24, 2)])
def test_collector_budget_retains_prefix_and_notifies_once(budget, count):
    recorder = recorder_with_budget(budget)
    completed = threading.Event()
    counts = []

    def stopped():
        counts.append(len(recorder.stop_recording()))
        completed.set()

    recorder.set_recording_stopped_callback(stopped)
    recorder.start_recording()
    try:
        assert completed.wait(3)
        assert [int(frame[0, 0, 0]) for frame in recorder.stop_recording()] == list(range(1, count + 1))
        assert counts == [count]
        assert recorder.storage_stop_reason
        assert recorder.get_estimated_size_mb() * 1024**2 == count * 12
    finally:
        recorder.stop_recording()


def test_oversized_mp4_frame_stops_before_starting_worker():
    recorder = recorder_with_budget(11)
    errors = []
    recorder.set_error_occurred_callback(errors.append)
    recorder.start_recording()
    assert errors == [recorder.storage_stop_reason]
    assert not recorder.is_recording
    assert recorder._capture_thread is None
    assert len(recorder.stop_recording()) == 0


@pytest.mark.parametrize("spill", [False, True])
def test_preview_is_immutable_and_never_reads_disk(monkeypatch, spill):
    recorder = recorder_with_budget(12 if spill else 48, spill)
    backend = Backend()
    reused = np.empty((2, 2, 3), dtype=np.uint8)
    third_requested = threading.Event()
    finish = threading.Event()

    def grab():
        if backend.value == 2:
            third_requested.set()
            finish.wait(5)
        backend.value += 1
        reused[:] = (backend.value, 31, 204)
        return reused

    backend.grab = grab
    recorder._backend_factory = lambda _: backend
    recorder.set_preview_enabled(True)
    assert recorder.get_latest_preview_frame() is None
    recorder.start_recording()
    try:
        assert third_requested.wait(3)
        with monkeypatch.context() as patch:
            patch.setattr(RecordingFrames, "__getitem__", lambda *args: pytest.fail("preview used disk"))
            latest = recorder.get_latest_preview_frame()
            assert latest is recorder.get_latest_preview_frame()
        assert tuple(latest[0, 0]) == (2, 31, 204) and not latest.flags.writeable
        assert not np.shares_memory(latest, reused)
        if not spill:
            assert not np.shares_memory(latest, recorder.frames[1])
        with pytest.raises(ValueError):
            latest.setflags(write=True)
        recorder.set_preview_enabled(False)
        assert recorder.get_latest_preview_frame() is None
        finish.set()
        frames = recorder.stop_recording()
        reused.fill(0)
        assert all(np.all(f == (i, 31, 204)) for i, f in enumerate(frames, 1))
        assert tuple(latest[0, 0]) == (2, 31, 204)
    finally:
        finish.set()
        recorder.stop_recording()


def test_spool_failure_preserves_replayable_prefix(monkeypatch):
    recorder = recorder_with_budget(12, spill=True)
    original_append = RecordingFrames.append

    def fail_after_two(store, frame):
        if len(store) == 2:
            raise OSError("disk full")
        original_append(store, frame)

    monkeypatch.setattr(RecordingFrames, "append", fail_after_two)
    stopped = threading.Event()
    recorder.set_recording_stopped_callback(stopped.set)
    recorder.start_recording()
    try:
        assert stopped.wait(3)
        frames = recorder.stop_recording()
        assert recorder.get_estimated_size_mb() * 1024**2 == 12
        assert frames.disk_bytes == 12
        assert "disk full" in recorder.storage_stop_reason
        recorder.clear_frames()
        assert [int(frame[0, 0, 0]) for frame in frames] == [1, 2]
    finally:
        recorder.stop_recording()

def test_backend_failure_does_not_publish_duplicate_frame(monkeypatch):
    recorder = recorder_with_budget(24)
    original_grab = Backend.grab

    def fail_second_grab(backend):
        if backend.value:
            raise OSError("capture failed")
        return original_grab(backend)

    monkeypatch.setattr(Backend, "grab", fail_second_grab)
    failed = threading.Event()
    recorder.set_error_occurred_callback(lambda message: failed.set())
    recorder.start_recording()
    try:
        assert failed.wait(3)
        assert [int(frame[0, 0, 0]) for frame in recorder.stop_recording()] == [1]
    finally:
        recorder.stop_recording()


def test_manual_stop_drains_inflight_backend_grab(monkeypatch):
    recorder = recorder_with_budget(48, spill=True)
    grabbing_second = threading.Event()
    release_grab = threading.Event()
    original_grab = Backend.grab

    def hold_second_grab(backend):
        if backend.value == 1:
            grabbing_second.set()
            assert release_grab.wait(3)
        return original_grab(backend)

    monkeypatch.setattr(Backend, "grab", hold_second_grab)
    recorder.start_recording()
    producer = recorder._capture_thread
    try:
        assert grabbing_second.wait(3)
        stopping = threading.Thread(target=recorder.stop_recording)
        stopping.start()
        assert producer.stop_event.wait(2)
        release_grab.set()
        stopping.join(3)
        assert not stopping.is_alive()
        assert producer.frame_count == len(recorder.frames) == 2
        assert [int(f[0, 0, 0]) for f in recorder.frames] == [1, 2]
    finally:
        release_grab.set()
        recorder.stop_recording()


def test_slow_storage_waits_before_next_grab(monkeypatch):
    recorder = recorder_with_budget(48, spill=True)
    writing = threading.Event()
    original_append = RecordingFrames.append
    backend = Backend()
    recorder._backend_factory = lambda name: backend

    def slow_write(store, frame):
        writing.set()
        assert recorder._thread_stop_event.wait(15)
        original_append(store, frame)

    monkeypatch.setattr(RecordingFrames, "append", slow_write)
    recorder.start_recording()
    producer = recorder._capture_thread
    try:
        assert writing.wait(2)
        assert not producer.stop_event.wait(0.6)
        assert backend.value == producer.frame_count == 1
        recorder.stop_recording()
        assert recorder._last_dropped_frames == 0
        assert producer.frame_count == len(recorder.frames) == 1
    finally:
        recorder.stop_recording()


def test_collector_timeout_returns_stable_disk_prefix(monkeypatch):
    recorder = recorder_with_budget(12, spill=True)
    writer_blocked = threading.Event()
    release = threading.Event()
    append = RecordingFrames.append

    def hold_third_write(frames, frame):
        if len(frames) == 2:
            writer_blocked.set()
            assert release.wait(15)
        append(frames, frame)

    monkeypatch.setattr(RecordingFrames, "append", hold_third_write)
    recorder.start_recording()
    collector = recorder._collector_thread
    try:
        assert writer_blocked.wait(3)
        frames = recorder.stop_recording()
        assert recorder.recovery_state == "degraded"
        assert recorder.storage_stop_reason
        assert frames.disk_bytes == 12
        assert [int(f[0, 0, 0]) for f in frames] == [1, 2]
        release.set()
        collector.join(2)
        assert recorder.recover_resources()
        recorder.start_recording()
        assert recorder.frames is not frames
        assert [int(f[0, 0, 0]) for f in frames] == [1, 2]
    finally:
        release.set()
        recorder.stop_recording()


def test_backend_timeout_does_not_publish_to_handed_off_frames(monkeypatch):
    recorder = recorder_with_budget(48)
    blocked = threading.Event()
    release = threading.Event()
    grab = Backend.grab

    def hold_second_grab(backend):
        if backend.value == 1:
            blocked.set()
            assert release.wait(15)
        return grab(backend)

    monkeypatch.setattr(Backend, "grab", hold_second_grab)
    recorder.start_recording()
    producer = recorder._capture_thread
    collector = recorder._collector_thread
    try:
        assert blocked.wait(3)
        frames = recorder.stop_recording()
        assert recorder.recovery_state == "degraded"
        assert [int(f[0, 0, 0]) for f in frames] == [1]
        release.set()
        producer.join(2)
        collector.join(2)
        assert recorder.recover_resources()
        recorder.start_recording()
        assert frames is not recorder.frames
        assert [int(f[0, 0, 0]) for f in frames] == [1]
    finally:
        release.set()
        recorder.stop_recording()
