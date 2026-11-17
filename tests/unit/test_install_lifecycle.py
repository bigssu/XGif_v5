import importlib.util
import logging
from pathlib import Path
from types import SimpleNamespace

import pytest

from cli import doctor
from core import ffmpeg_installer


@pytest.mark.parametrize("interrupted", [False, True])
def test_doctor_waits_for_terminal_install_before_return(monkeypatch, interrupted):
    calls = []

    class Downloader:
        def __init__(self, **kwargs):
            self.callback = kwargs["finished_callback"]
            self.finished = SimpleNamespace(wait=self.wait)
            self.waits = 0
            self.terminal = False

        def start(self):
            calls.append("start")

        def wait(self, timeout):
            self.waits += 1
            if self.waits == 1:
                if interrupted:
                    raise KeyboardInterrupt
                return False
            self.callback(not interrupted, "complete")
            self.terminal = True
            return True

        def cancel(self):
            calls.append("cancel")

        def join(self, timeout=None):
            assert self.terminal, "returned to join before terminal cleanup"
            calls.append("join")

    monkeypatch.setattr(ffmpeg_installer, "FFmpegDownloader", Downloader)
    assert doctor._install_ffmpeg() == (130 if interrupted else 0)
    assert calls == (["start", "cancel", "join"] if interrupted else ["start", "join"])


def test_downloader_terminal_event_is_set_even_if_failure_callback_raises(monkeypatch):
    downloader = ffmpeg_installer.FFmpegDownloader()

    def fail():
        raise OSError("install failed")

    def fail_callback(*args):
        raise ValueError("callback failed")

    monkeypatch.setattr(downloader, "_download_and_install", fail)
    monkeypatch.setattr(downloader, "_safe_callback", fail_callback)
    with pytest.raises(ValueError):
        downloader.run()
    assert downloader.finished.is_set()


def test_downloader_terminal_event_is_set_only_after_cleanup(monkeypatch):
    downloader = ffmpeg_installer.FFmpegDownloader()
    calls = []

    def install():
        try:
            assert not downloader.finished.is_set()
            calls.append("install")
        finally:
            assert not downloader.finished.is_set()
            calls.append("cleanup")

    monkeypatch.setattr(downloader, "_download_and_install", install)
    downloader.run()
    assert calls == ["install", "cleanup"]
    assert downloader.finished.is_set()


def test_encoder_availability_accepts_system_ffmpeg_without_ffprobe(tmp_path, monkeypatch):
    executable = tmp_path / "ffmpeg.exe"
    executable.write_bytes(b"encoder")
    monkeypatch.setattr(ffmpeg_installer, "check_system_ffmpeg", lambda: str(executable))
    assert ffmpeg_installer.FFmpegManager.get_ffmpeg_executable() == str(executable)
    assert ffmpeg_installer.FFmpegManager.is_available()


@pytest.fixture
def bootstrap_ui():
    source = Path(__file__).resolve().parents[2] / "BootStrapper" / "ui_main.py"
    spec = importlib.util.spec_from_file_location("bootstrap_ui_test", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("busy, worker_alive", [(True, True), (True, False), (False, True)])
def test_bootstrap_busy_close_is_vetoed_even_if_dialog_answers_yes(bootstrap_ui, monkeypatch, busy, worker_alive):
    calls = []
    frame = SimpleNamespace(_is_running=busy, _worker=SimpleNamespace(is_alive=lambda: worker_alive),
                            _cancel_auto_close=lambda: calls.append("timer_stopped"),
                            Destroy=lambda: calls.append("destroy"), _all_required_ok=False,
                            logger=logging.getLogger("lifecycle-test"))
    event = SimpleNamespace(Veto=lambda: calls.append("veto"), CanVeto=lambda: True)
    monkeypatch.setattr(bootstrap_ui.wx, "MessageBox", lambda *args: calls.append("message") or bootstrap_ui.wx.YES)
    monkeypatch.setattr(bootstrap_ui.wx, "GetApp", lambda: None)
    bootstrap_ui.BootstrapperFrame._on_window_close(frame, event)
    assert "veto" in calls
    assert "message" in calls
    assert "destroy" not in calls


@pytest.mark.parametrize("success", [False, True])
def test_bootstrap_completion_releases_busy_and_allows_close(bootstrap_ui, monkeypatch, success):
    calls = []
    button = SimpleNamespace(Enable=lambda value: None, SetLabel=lambda value: None)
    frame = SimpleNamespace(_is_running=True, _worker=SimpleNamespace(is_alive=lambda: False),
                            _btn_recheck=button, _btn_close=button, _btn_install=button,
                            _deps=[], _auto_close_timer=None, _all_required_ok=False,
                            _start_auto_close_countdown=lambda: None, _cancel_auto_close=lambda: None,
                            Destroy=lambda: calls.append("destroy"), logger=logging.getLogger("lifecycle-test"))
    monkeypatch.setattr(bootstrap_ui.wx, "GetApp", lambda: None)
    bootstrap_ui.BootstrapperFrame._on_complete_evt(frame, SimpleNamespace(success=success, error=None))
    assert not frame._is_running
    event = SimpleNamespace(Veto=lambda: calls.append("veto"), CanVeto=lambda: True)
    bootstrap_ui.BootstrapperFrame._on_window_close(frame, event)
    assert calls == ["destroy"]
