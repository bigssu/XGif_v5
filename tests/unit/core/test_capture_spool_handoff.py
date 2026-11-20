import threading

import numpy as np

from core.capture_backend import CaptureBackend
from core.recording_frames import RecordingFrames
from core.screen_recorder import ScreenRecorder


class NumberedBackend(CaptureBackend):
    def __init__(self):
        self.count = 0
        self.second_grab = threading.Event()

    def start(self, region, target_fps=30):
        return True

    def stop(self):
        pass

    def get_name(self):
        return "numbered"

    @property
    def is_running(self):
        return True

    def grab(self):
        self.count += 1
        if self.count == 2:
            self.second_grab.set()
        return np.full((640, 640, 3), self.count, np.uint8)


def test_stop_during_slow_spill_keeps_published_frame(monkeypatch):
    backend = NumberedBackend()
    recorder = ScreenRecorder(backend_factory=lambda _: backend)
    recorder.include_cursor = False
    recorder.set_region(0, 0, 640, 640)
    recorder.fps = 120
    recorder.configure_frame_storage(memory_limit_mb=1, spill_to_disk=True)
    entered_append = threading.Event()
    finish_append = threading.Event()
    original_append = RecordingFrames.append

    def slow_append(frames, buffer):
        entered_append.set()
        assert finish_append.wait(3)
        original_append(frames, buffer)

    monkeypatch.setattr(RecordingFrames, "append", slow_append)
    recorder.start_recording()
    worker = recorder._capture_thread
    stop_event = recorder._thread_stop_event
    try:
        assert entered_append.wait(2)
        # Leave the slot occupied past multiple producer polling intervals.
        assert not backend.second_grab.wait(0.15)
        stopper = threading.Thread(target=recorder.stop_recording)
        stopper.start()
        assert stop_event.wait(2)
    finally:
        finish_append.set()
        stop_event.set()

    stopper.join(4)
    assert not stopper.is_alive()
    assert backend.count == worker.frame_count == len(recorder.frames) == 1
    assert worker.dropped_frames == 0
    assert recorder.frames.disk_bytes == 640 * 640 * 3
    assert np.all(recorder.frames[0] == 1)
