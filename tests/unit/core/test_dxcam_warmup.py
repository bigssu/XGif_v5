import threading

import numpy as np

import core.capture_backend as cb


class Camera:
    def __init__(self):
        self.is_capturing = False
        self.starts = []
        self.stops = 0

    def start(self, **kwargs):
        if self.is_capturing:
            raise RuntimeError('Capture is already running. Call stop() first.')
        self.is_capturing = True
        self.starts.append(kwargs['region'])

    def stop(self):
        self.is_capturing = False
        self.stops += 1

    def get_latest_frame(self):
        return np.zeros((4, 4, 3), dtype=np.uint8)


def test_recording_waits_until_shared_camera_initialization_finishes(monkeypatch):
    camera = Camera()
    warming = threading.Event()
    release_warmup = threading.Event()
    recording_done = threading.Event()
    def create_camera():
        warming.set()
        assert release_warmup.wait(2)
        return camera

    monkeypatch.setattr(cb, '_create_dxcam_camera', create_camera)
    monkeypatch.setattr(cb, 'HAS_DXCAM', True)
    monkeypatch.setattr(cb.DXCamBackend, '_shared_camera', None)
    warmup, recording = cb.DXCamBackend(), cb.DXCamBackend()
    results = {}
    warm_thread = threading.Thread(target=lambda: results.update(warm=warmup.warm_up()),
                                   name='test-dxcam-warmup')

    def start_recording():
        results['record'] = recording.start((0, 0, 128, 128), target_fps=10)
        recording_done.set()

    record_thread = threading.Thread(target=start_recording)
    try:
        warm_thread.start()
        assert warming.wait(2)
        record_thread.start()
        assert not recording_done.wait(0.05)
        release_warmup.set()
        warm_thread.join(2)
        record_thread.join(2)
        assert results == {'warm': True, 'record': True}
        assert camera.is_capturing
        assert camera.starts == [(0, 0, 128, 128)]
        assert camera.stops == 0
    finally:
        release_warmup.set()
        warm_thread.join(2)
        if record_thread.ident is not None:
            record_thread.join(2)
        recording.stop()


def test_late_warmup_leaves_active_recording_alone(monkeypatch):
    camera = Camera()
    monkeypatch.setattr(cb, 'HAS_DXCAM', True)
    monkeypatch.setattr(cb.DXCamBackend, '_shared_camera', camera)
    recording, warmup = cb.DXCamBackend(), cb.DXCamBackend()
    try:
        assert recording.start((0, 0, 128, 128), target_fps=10)
        stops = camera.stops
        assert warmup.warm_up()
        assert camera.is_capturing
        assert camera.stops == stops
        assert camera.starts == [(0, 0, 128, 128)]
    finally:
        recording.stop()
