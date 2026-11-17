from types import SimpleNamespace

import pytest

from cli.recorder import AUDIO_BUFFER_LIMIT_ERROR, CLIRecordingSession


class _Progress:
    def __init__(self):
        self.cleared = False
        self.recording_updates = []

    def clear_line(self):
        self.cleared = True

    def update_recording(self, elapsed, frame_count, duration):
        self.recording_updates.append((elapsed, frame_count, duration))

    def update_paused(self, elapsed, frame_count):
        self.recording_updates.append((elapsed, frame_count, "paused"))


class _Recorder:
    is_recording = True

    def get_frame_count(self):
        return 3


class _AudioRecorder:
    buffer_limit_reached = True


def test_cli_wait_stops_when_audio_buffer_limit_is_reached(capsys):
    session = CLIRecordingSession(SimpleNamespace(duration=None, quiet=True))
    session._recorder = _Recorder()
    session._audio_recorder = _AudioRecorder()
    session._progress = _Progress()

    session._wait_for_completion()

    assert session._stopped is True
    assert session._audio_limit_reached is True
    assert session._recording_error == AUDIO_BUFFER_LIMIT_ERROR
    assert session._progress.cleared is True
    assert AUDIO_BUFFER_LIMIT_ERROR in capsys.readouterr().err


def test_cli_space_pauses_and_resumes_audio_with_video(monkeypatch):
    import cli.recorder as module
    calls = []
    session = CLIRecordingSession(SimpleNamespace(duration=None, quiet=True))
    session._recorder = SimpleNamespace(
        is_recording=True, get_frame_count=lambda: 3, get_estimated_size_mb=lambda: 0,
        pause_recording=lambda: calls.append("video pause"),
        resume_recording=lambda: calls.append("video resume"),
    )
    session._audio_recorder = SimpleNamespace(
        buffer_limit_reached=False,
        pause=lambda: calls.append("audio pause"),
        resume=lambda: calls.append("audio resume"),
    )
    session._progress = _Progress()
    keys = iter([b" ", b" ", b"q"])
    monkeypatch.setattr(module, "msvcrt", SimpleNamespace(kbhit=lambda: True, getch=lambda: next(keys)))
    monkeypatch.setattr(module.time, "sleep", lambda seconds: None)
    session._wait_for_completion()
    assert calls == ["video pause", "audio pause", "video resume", "audio resume"]


def test_cli_memory_limit_stops_wait_without_discarding_frames(monkeypatch, capsys):
    import cli.recorder as module
    frames = [object()]
    session = CLIRecordingSession(SimpleNamespace(duration=None, quiet=True))
    session._memory_limit_mb = 64
    session._recorder = SimpleNamespace(
        is_recording=True, frames=frames, get_frame_count=lambda: 1,
        get_estimated_size_mb=lambda: 64,
    )
    session._progress = _Progress()
    monkeypatch.setattr(module, "msvcrt", SimpleNamespace(kbhit=lambda: True, getch=lambda: b"q"))
    session._wait_for_completion()
    assert session._stopped
    assert session._recorder.frames is frames
    assert not session._audio_limit_reached
    assert "64" in capsys.readouterr().err


@pytest.mark.parametrize(("actual_fps", "expected_fps"), [(0.1, 1), (150, 120)])
def test_cli_memory_stop_saves_frames_with_valid_fps(monkeypatch, tmp_path, actual_fps, expected_fps):
    import cli.recorder as module
    output = tmp_path / "capture.gif"
    frames = [object()]
    encoded = []
    session = CLIRecordingSession(SimpleNamespace(
        output=str(output), overwrite=False, quiet=True, duration=None,
    ))
    recorder = SimpleNamespace(
        is_recording=True, fps=30, actual_fps=actual_fps,
        get_capture_backend_name=lambda: "fake",
        set_region=lambda *args: None, start_recording=lambda: None,
        get_frame_count=lambda: len(frames), get_estimated_size_mb=lambda: 64,
    )
    def stop():
        recorder.is_recording = False
        return frames
    def encode(captured, fps, path):
        encoded.append((captured, fps))
        output.write_bytes(b"test")
        return True
    recorder.stop_recording = stop
    def init(config, output_format):
        session._recorder = recorder
        session._encoder = SimpleNamespace(
            quality="high", set_progress_callback=lambda callback: None, encode=encode,
        )
    monkeypatch.setattr(session, "_init_engines", init)
    monkeypatch.setattr(session, "_check_ffmpeg", lambda output_format: True)
    monkeypatch.setattr(session, "_resolve_region", lambda: (0, 0, 64, 64))
    monkeypatch.setattr(module, "load_config", lambda: {"memory_limit_mb": "64"})
    monkeypatch.setattr(module, "install_signal_handlers", lambda callback: None)
    monkeypatch.setattr(module, "restore_signal_handlers", lambda: None)
    monkeypatch.setattr(module, "msvcrt", SimpleNamespace(kbhit=lambda: True, getch=lambda: b"q"))
    assert session.run() == module.EXIT_SUCCESS
    assert session._stopped
    assert encoded == [(frames, expected_fps)]


def test_countdown_interrupt_never_starts_capture_or_audio(monkeypatch, tmp_path):
    import cli.recorder as module
    from core import audio_recorder
    from unittest.mock import Mock
    session = CLIRecordingSession(SimpleNamespace(
        output=str(tmp_path / "capture.mp4"), overwrite=False, quiet=True, delay=3, mic=True,
    ))
    recorder = Mock(fps=30)
    audio = Mock()
    restored = Mock()
    def init(config, output_format):
        session._recorder = recorder
        session._encoder = SimpleNamespace(quality="high")
    monkeypatch.setattr(session, "_init_engines", init)
    monkeypatch.setattr(session, "_check_ffmpeg", lambda output_format: True)
    monkeypatch.setattr(session, "_resolve_region", lambda: (0, 0, 64, 64))
    monkeypatch.setattr(module, "load_config", lambda: {})
    monkeypatch.setattr(module, "install_signal_handlers", lambda callback: None)
    monkeypatch.setattr(module, "restore_signal_handlers", restored)
    monkeypatch.setattr(module.time, "sleep", lambda seconds: session._on_stop_signal())
    monkeypatch.setattr(audio_recorder, "is_audio_available", lambda: True)
    monkeypatch.setattr(audio_recorder, "AudioRecorder", audio)
    assert session.run() == 130
    audio.assert_not_called()
    recorder.start_recording.assert_not_called()
    restored.assert_called_once()
