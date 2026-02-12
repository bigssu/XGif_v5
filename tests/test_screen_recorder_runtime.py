"""Runtime safety tests for ScreenRecorder control flow."""

import numpy as np


class _FakeBackend:
    def __init__(self, name: str, start_ok: bool, frame):
        self._name = name
        self._start_ok = start_ok
        self._frame = frame
        self._running = False

    def start(self, region, target_fps=30):
        self._running = self._start_ok
        return self._start_ok

    def stop(self):
        self._running = False

    def grab(self):
        return self._frame

    def get_name(self):
        return self._name

    @property
    def is_running(self):
        return self._running


def test_start_recording_rejects_invalid_fps():
    from core.screen_recorder import ScreenRecorder

    recorder = ScreenRecorder()
    recorder.set_region(0, 0, 320, 240)
    recorder.fps = 0

    errors = []
    recorder.set_error_occurred_callback(errors.append)
    recorder.start_recording()

    assert recorder.is_recording is False
    assert errors
    assert "FPS" in errors[-1]


def test_capture_single_frame_falls_back_to_gdi(monkeypatch):
    import core.screen_recorder as sr
    from core.screen_recorder import ScreenRecorder

    call_order = []
    frame = np.full((8, 8, 3), 7, dtype=np.uint8)

    def fake_factory(name):
        call_order.append(name)
        if name == "dxcam":
            return _FakeBackend("dxcam", start_ok=False, frame=None)
        if name == "gdi":
            return _FakeBackend("gdi", start_ok=True, frame=frame)
        raise RuntimeError(f"unexpected backend: {name}")

    monkeypatch.setattr(sr, "create_capture_backend", fake_factory)

    recorder = ScreenRecorder()
    recorder._preferred_backend = "dxcam"
    recorder.include_cursor = False
    recorder.set_region(0, 0, 8, 8)

    captured = recorder.capture_single_frame()

    assert call_order == ["dxcam", "gdi"]
    assert captured is not None
    assert captured.shape == (8, 8, 3)
    assert np.all(captured == 7)


def test_capture_thread_failure_resets_recording_state(monkeypatch):
    import core.screen_recorder as sr
    from core.screen_recorder import ScreenRecorder

    class _FailingCaptureThread:
        def __init__(self, *args, on_failed=None, **kwargs):
            self._on_failed = on_failed
            self._alive = False
            self.dropped_frames = 0

        def start(self):
            self._alive = True
            if self._on_failed:
                self._on_failed("forced capture failure")
            self._alive = False

        def wait_for_first_frame(self, timeout=1.0):
            return False

        def is_alive(self):
            return self._alive

        def join(self, timeout=None):
            self._alive = False

    monkeypatch.setattr(sr, "CaptureThread", _FailingCaptureThread)

    recorder = ScreenRecorder()
    recorder.set_region(0, 0, 64, 64)
    recorder.fps = 15

    errors = []
    recorder.set_error_occurred_callback(errors.append)
    recorder.start_recording()

    assert recorder.is_recording is False
    assert errors
    assert "forced capture failure" in errors[-1]

    recorder.stop_recording()

