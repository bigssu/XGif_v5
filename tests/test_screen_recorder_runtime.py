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


def test_backend_factory_injection_avoids_monkeypatch():
    """backend_factory 생성자 주입으로 monkeypatch 없이 fake backend 사용 가능해야 한다."""
    from core.screen_recorder import ScreenRecorder

    call_order = []
    frame = np.full((4, 4, 3), 9, dtype=np.uint8)

    def injected_factory(name):
        call_order.append(name)
        if name == "dxcam":
            return _FakeBackend("dxcam", start_ok=False, frame=None)
        if name == "gdi":
            return _FakeBackend("gdi", start_ok=True, frame=frame)
        raise RuntimeError(f"unexpected backend: {name}")

    recorder = ScreenRecorder(backend_factory=injected_factory)
    recorder._preferred_backend = "dxcam"
    recorder.include_cursor = False
    recorder.set_region(0, 0, 4, 4)

    captured = recorder.capture_single_frame()

    assert call_order == ["dxcam", "gdi"]
    assert captured is not None
    assert captured.shape == (4, 4, 3)
    assert np.all(captured == 9)


def test_dxcam_force_release_clears_shared_camera():
    """P1-A 회귀 방지: force_release() 가 인스턴스 _camera + 클래스 _shared_camera 양쪽을
    정리해야 자기증폭 실패 루프가 차단된다. dxcam 미설치 환경에서도 돌도록 속성만 검증."""
    from core.capture_backend import DXCamBackend

    backend = DXCamBackend()

    # 실제 dxcam 없이도 force_release 의 공유 카메라 정리 로직만 검증하기 위한 더미.
    class _DummyCamera:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    dummy = _DummyCamera()
    backend._camera = dummy
    DXCamBackend._shared_camera = dummy  # 동일 객체 (공유 카메라)

    try:
        backend.force_release()

        assert backend._camera is None
        assert DXCamBackend._shared_camera is None, \
            "force_release must clear class-level _shared_camera when it matches instance _camera"
        assert dummy.stopped is True, "broken camera stop() must be attempted once as best-effort"
    finally:
        DXCamBackend._shared_camera = None


def test_dxcam_force_release_preserves_unrelated_shared_camera():
    """force_release() 는 공유 카메라가 다른 객체일 때는 건드리지 않아야 한다."""
    from core.capture_backend import DXCamBackend

    backend = DXCamBackend()

    class _Cam:
        def __init__(self):
            self.stopped = False

        def stop(self):
            self.stopped = True

    instance_cam = _Cam()
    other_shared = _Cam()
    backend._camera = instance_cam
    DXCamBackend._shared_camera = other_shared  # 다른 객체

    try:
        backend.force_release()

        assert backend._camera is None
        assert DXCamBackend._shared_camera is other_shared, \
            "force_release must not touch _shared_camera when it differs from instance camera"
        assert other_shared.stopped is False, "unrelated shared camera must not be stopped"
        assert instance_cam.stopped is True
    finally:
        DXCamBackend._shared_camera = None


def test_dxcam_backend_uses_numpy_processor_backend(monkeypatch):
    import core.capture_backend as cb

    created_kwargs = {}

    class _DummyCamera:
        def __init__(self):
            self._frame = np.zeros((4, 4, 3), dtype=np.uint8)

        def start(self, region=None, target_fps=30, video_mode=False):
            return None

        def stop(self):
            return None

        def get_latest_frame(self):
            return self._frame

    def fake_create(**kwargs):
        created_kwargs.update(kwargs)
        return _DummyCamera()

    monkeypatch.setattr(cb.dxcam, "create", fake_create)
    cb.DXCamBackend._shared_camera = None

    backend = cb.DXCamBackend()
    try:
        assert backend.start((0, 0, 4, 4), target_fps=30) is True
        assert created_kwargs["output_color"] == "BGR"
        assert created_kwargs["processor_backend"] == "numpy"
    finally:
        backend.stop()
        cb.DXCamBackend._shared_camera = None


def test_dxcam_backend_retries_without_processor_backend_on_legacy_dxcam(monkeypatch):
    import core.capture_backend as cb

    create_calls = []

    class _DummyCamera:
        def __init__(self):
            self._frame = np.zeros((4, 4, 3), dtype=np.uint8)

        def start(self, region=None, target_fps=30, video_mode=False):
            return None

        def stop(self):
            return None

        def get_latest_frame(self):
            return self._frame

    def fake_create(**kwargs):
        create_calls.append(dict(kwargs))
        if "processor_backend" in kwargs:
            raise TypeError("unexpected keyword argument 'processor_backend'")
        return _DummyCamera()

    monkeypatch.setattr(cb.dxcam, "create", fake_create)
    cb.DXCamBackend._shared_camera = None

    backend = cb.DXCamBackend()
    try:
        assert backend.start((0, 0, 4, 4), target_fps=30) is True
        assert create_calls == [
            {"output_color": "BGR", "processor_backend": "numpy"},
            {"output_color": "BGR"},
        ]
    finally:
        backend.stop()
        cb.DXCamBackend._shared_camera = None


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

