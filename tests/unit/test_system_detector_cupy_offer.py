from types import SimpleNamespace

from core.gpu_utils import GpuInfo
from core.settings import AppSettings
from ui.controllers import system_detector
from ui.controllers.system_detector import SystemDetector


class _FakeCaptureBar:
    def __init__(self):
        self.statuses = []
        self.gpu_status_button = SimpleNamespace(
            SetLabel=lambda _label: None,
            Enable=lambda _enabled: None,
        )

    def set_gpu_status(self, value):
        self.statuses.append(value)


def _make_detector():
    window = SimpleNamespace(
        settings=AppSettings(),
        capture_control_bar=_FakeCaptureBar(),
    )
    return SystemDetector(window), window


def test_auto_cuda_without_cupy_schedules_install_guide(monkeypatch):
    detector, window = _make_detector()
    scheduled = []

    def fake_call_later(delay_ms, callback, *args):
        scheduled.append((delay_ms, callback, args))

    monkeypatch.setattr(system_detector.wx, "CallLater", fake_call_later)

    detector._on_auto_gpu_detect_done(GpuInfo(has_cuda=True, has_cupy=False))

    assert window.capture_control_bar.statuses == [False]
    assert scheduled
    assert scheduled[0][1] == detector._offer_cupy_install
    assert scheduled[0][2] == ()


def test_gpu_info_click_routes_missing_cupy_to_install_flow(monkeypatch):
    detector, _window = _make_detector()
    offers = []
    messages = []

    monkeypatch.setattr(
        system_detector,
        "detect_gpu",
        lambda skip_cupy=False: GpuInfo(
            has_cuda=True,
            has_cupy=False,
            gpu_name="NVIDIA GeForce RTX 4080",
            gpu_memory_mb=16376,
            ffmpeg_nvenc=True,
            driver_version="595.79",
        ),
    )
    monkeypatch.setattr(
        detector,
        "_offer_cupy_install",
        lambda: offers.append(True) or False,
    )
    monkeypatch.setattr(system_detector.wx, "MessageBox", lambda *args, **kwargs: messages.append(args))

    detector._show_gpu_info_dialog()

    assert offers == [True]
    assert messages == []
