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
