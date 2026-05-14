"""MainWindow 실시간 프리뷰 회귀 테스트."""

import numpy as np

from ui import main_window


def test_preview_frame_to_rgb_converts_bgr_to_rgb():
    frame = np.array([[[1, 2, 3], [4, 5, 6]]], dtype=np.uint8)

    rgb = main_window._preview_frame_to_rgb(frame)

    assert rgb.tolist() == [[[3, 2, 1], [6, 5, 4]]]
    assert rgb.flags.c_contiguous


def test_preview_frame_to_rgb_handles_gray_and_rejects_invalid_channels():
    gray = np.array([[7, 8]], dtype=np.uint8)
    invalid = np.zeros((1, 2, 2), dtype=np.uint8)

    assert main_window._preview_frame_to_rgb(gray).tolist() == [[[7, 7, 7], [8, 8, 8]]]
    assert main_window._preview_frame_to_rgb(invalid) is None


def test_fit_preview_size_preserves_aspect_ratio():
    assert main_window._fit_preview_size(320, 180) == (160, 90)
    assert main_window._fit_preview_size(90, 180) == (45, 90)
    assert main_window._fit_preview_size(0, 0) == (1, 1)


def test_update_preview_sets_bitmap_and_label(monkeypatch):
    frame = np.array([[[10, 20, 30], [40, 50, 60]]], dtype=np.uint8)
    expected_bitmap = object()
    captured_frames = []

    def fake_create_preview_bitmap(rgb_frame):
        captured_frames.append(rgb_frame.copy())
        return expected_bitmap

    class FakeRecorder:
        def capture_single_frame(self):
            return frame

    class FakeBitmapTarget:
        def __init__(self):
            self.bitmap = None

        def SetBitmap(self, bitmap):
            self.bitmap = bitmap

    class FakeLabel:
        def __init__(self):
            self.label = ""

        def SetLabel(self, label):
            self.label = label

    monkeypatch.setattr(main_window, "_create_preview_bitmap", fake_create_preview_bitmap)

    class FakeWindow:
        pass

    window = FakeWindow()
    window.recorder = FakeRecorder()
    window.preview_enabled = True
    window.preview_bitmap = FakeBitmapTarget()
    window.preview_label = FakeLabel()

    main_window.MainWindow._update_preview(window)

    assert captured_frames[0].tolist() == [[[30, 20, 10], [60, 50, 40]]]
    assert window.preview_bitmap.bitmap is expected_bitmap
    assert "2x1" in window.preview_label.label


def test_mp4_mic_start_failure_is_visible(monkeypatch):
    messages = []

    class FakeTimer:
        def __init__(self, owner):
            self.owner = owner
            self.started = False

        def Start(self, interval):
            self.started = True
            self.interval = interval

    class FakeRecorder:
        watermark = None
        keyboard_display = None
        is_recording = False

        def set_capture_backend(self, backend):
            self.backend = backend

        def start_recording(self):
            self.is_recording = True

    class FakeSettings:
        def get(self, key, fallback=None):
            return {
                "capture_backend": "gdi",
                "mic_audio": "true",
                "memory_limit_mb": "1024",
            }.get(key, fallback)

    class FakeCaptureControlBar:
        def get_format(self):
            return "MP4"

    class FakeAudioRecorder:
        def __init__(self):
            self.max_buffer_mb = None
            self.record_mic = False

        def set_max_buffer_mb(self, max_buffer_mb):
            self.max_buffer_mb = max_buffer_mb

        def set_record_mic(self, enabled):
            self.record_mic = enabled

        def start(self):
            return False

    class FakeLabel:
        def __init__(self):
            self.labels = []

        def SetLabel(self, label):
            self.labels.append(label)

    class FakeWindow:
        def Bind(self, *args, **kwargs):
            self.bound = (args, kwargs)

    monkeypatch.setattr(main_window.wx, "Timer", FakeTimer)
    monkeypatch.setattr(main_window.wx, "CallLater", lambda delay, fn: None)
    monkeypatch.setattr(
        main_window.wx,
        "MessageBox",
        lambda message, title, flags: messages.append((message, title, flags)),
    )

    window = FakeWindow()
    window.STATE_RECORDING = main_window.MainWindow.STATE_RECORDING
    window.recorder = FakeRecorder()
    window.settings = FakeSettings()
    window.capture_control_bar = FakeCaptureControlBar()
    window.audio_recorder = FakeAudioRecorder()
    window.status_msg_label = FakeLabel()
    window.record_timer = None
    window.record_elapsed = 0
    window.record_state = window.STATE_RECORDING
    window._get_audio_buffer_limit_mb = lambda: 256
    window._on_record_timer = lambda event: None

    main_window.MainWindow._do_start_recording(window)

    assert messages
    assert messages[0][0] == main_window.tr("audio_recording_unavailable")
    assert window.status_msg_label.labels[0] == main_window.tr("audio_recording_unavailable")
    assert window.audio_recorder.record_mic is True
    assert window.audio_recorder.max_buffer_mb == 256
