"""MainWindow 실시간 프리뷰 회귀 테스트."""

from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
from unittest.mock import Mock

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


def test_preview_bitmap_matches_original_wx_scaling():
    subprocess.run([sys.executable, "-c",
                    "from tests.unit.test_main_window_preview import check_bitmap_pixels; check_bitmap_pixels()"],
                   cwd=Path(__file__).resolve().parents[2], check=True, timeout=25)


def check_bitmap_pixels():
    import wx
    app = wx.App(False)
    color = np.random.default_rng(5).integers(256, size=(181, 323, 4), dtype=np.uint8)
    for frame in (color, color[..., 2], color[..., :3], color[..., :3].copy(),
                  color[::2, ::-2, :3], color.astype(np.int16) - 20, color[:1, :3, :3]):
        frame.flags.writeable = False
        rgb = main_window._preview_frame_to_rgb(frame)
        h, w = rgb.shape[:2]
        size = main_window._fit_preview_size(w, h)
        old = wx.Image(w, h)
        old.SetData(rgb.tobytes())
        old = wx.Bitmap(old.Scale(*size, wx.IMAGE_QUALITY_HIGH)).ConvertToImage()
        new = main_window._create_preview_bitmap(frame).ConvertToImage()
        assert tuple(new.GetSize()) == size
        assert new.GetData() == old.GetData()
        assert new.HasAlpha() == old.HasAlpha()
    assert main_window._create_preview_bitmap(np.empty((2, 1, 2))) is None
    assert app is wx.App.Get()


def preview_window(state):
    return SimpleNamespace(STATE_READY=0, record_state=state, _last_preview_frame=None,
                           _is_closing=False, recorder=Mock(), preview_enabled=True,
                           preview_bitmap=Mock(), preview_label=Mock())


def test_recording_and_pause_reuse_latest_frame_without_recapturing(monkeypatch):
    frame = np.arange(6, dtype=np.uint8).reshape(1, 2, 3)
    window = preview_window(1)
    window.recorder.get_latest_preview_frame.return_value = frame
    bitmap = Mock(return_value=object())
    monkeypatch.setattr(main_window, "_create_preview_bitmap", bitmap)
    main_window.MainWindow._update_preview(window)
    window.record_state = 2
    main_window.MainWindow._update_preview(window)
    bitmap.assert_called_once_with(frame)
    window.preview_bitmap.SetBitmap.assert_called_once_with(bitmap.return_value)
    assert "2x1" in window.preview_label.SetLabel.call_args.args[0]
    window.recorder.capture_single_frame.assert_not_called()


def test_idle_preview_shows_fresh_frame_and_releases_cached_take(monkeypatch):
    window = preview_window(0)
    window._last_preview_frame = object()
    frame = np.zeros((3, 2, 3), dtype=np.uint8)
    window.recorder.capture_single_frame.return_value = frame
    bitmap = Mock(return_value=object())
    monkeypatch.setattr(main_window, "_create_preview_bitmap", bitmap)
    main_window.MainWindow._update_preview(window)
    bitmap.assert_called_once_with(frame)
    window.recorder.get_latest_preview_frame.assert_not_called()
    assert window._last_preview_frame is None


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

        def set_recording_stopped_callback(self, callback):
            self.stopped = callback

        def set_error_occurred_callback(self, callback):
            self.error = callback

        def configure_frame_storage(self, memory_limit_mb, spill_to_disk):
            self.storage = (memory_limit_mb, spill_to_disk)

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

        def set_record_system(self, enabled):
            self.record_system = enabled

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
    window._take_format = "MP4"
    window._take_mic = True
    window.STATE_RECORDING = main_window.MainWindow.STATE_RECORDING
    window.recorder = FakeRecorder()
    window.settings = FakeSettings()
    window.capture_control_bar = FakeCaptureControlBar()
    window.audio_recorder = FakeAudioRecorder()
    window.status_msg_label = FakeLabel()
    window.record_timer = None
    window.record_elapsed = 0
    window.record_state = window.STATE_RECORDING
    window._get_memory_limit_mb = lambda: 1024
    window._get_audio_buffer_limit_mb = lambda: 256
    window._on_record_timer = lambda event: None

    window._update_button_states = Mock()
    window._recording_session = object()
    main_window.MainWindow._do_start_recording(window, window._recording_session)

    assert messages
    assert messages[0][0] == main_window.tr("audio_recording_unavailable")
    assert window.status_msg_label.labels[0] == main_window.tr("audio_recording_unavailable")
    assert window.audio_recorder.record_system is False
    assert window.audio_recorder.record_mic is True
    assert window.audio_recorder.max_buffer_mb == 256
    assert window.recorder.storage == (1024, False)


def test_idle_preview_waits_only_for_background_capture_backend(monkeypatch):
    import core.screen_recorder as sr

    pixels = np.arange(60, dtype=np.uint8).reshape(4, 5, 3)
    for preference, active_name, expected_waits in (
        ("gdi", "gdi", []), ("dxcam", "gdi", []), ("dxcam", "dxcam", [0.1])
    ):
        attempts, waits, captures, releases = [], [], [], []
        def factory(name):
            attempts.append(name)
            return SimpleNamespace(start=lambda region, target_fps: name == active_name,
                                   grab=lambda: captures.append(name) or pixels,
                                   get_name=lambda: name, stop=lambda: releases.append(name))
        recorder = sr.ScreenRecorder(backend_factory=factory)
        recorder._preferred_backend = preference
        recorder.include_cursor = False
        recorder.set_region(0, 0, 5, 4)
        with monkeypatch.context() as m:
            m.setattr(sr, 'time', SimpleNamespace(sleep=waits.append))
            frame = recorder.capture_single_frame()
        assert waits == expected_waits
        assert captures == [active_name] and releases == attempts
        assert np.array_equal(frame, pixels)
