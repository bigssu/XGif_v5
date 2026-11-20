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


def test_cli_observes_collector_stop_without_discarding_frames():
    frames = [object()]
    session = CLIRecordingSession(SimpleNamespace(duration=None, quiet=True))
    session._memory_limit_mb = 64
    session._recorder = SimpleNamespace(
        is_recording=False, frames=frames,
    )
    session._progress = _Progress()
    session._wait_for_completion()
    assert session._stopped
    assert session._recorder.frames is frames
    assert not session._audio_limit_reached


@pytest.mark.parametrize(("actual_fps", "expected_fps", "storage_error"), [
    (0.1, 0.1, True), (29.7, 29.7, False), (150, 120, True),
])
def test_cli_abnormal_stop_saves_frames_and_returns_failure(monkeypatch, tmp_path, capsys, actual_fps, expected_fps, storage_error):
    import cli.recorder as module
    output = tmp_path / "capture.gif"
    frames = [object()]
    encoded = []
    session = CLIRecordingSession(SimpleNamespace(
        output=str(output), overwrite=False, quiet=True, duration=60,
    ))
    recorder = SimpleNamespace(
        is_recording=False, fps=30, actual_fps=actual_fps,
        storage_stop_reason="테스트 저장 공간 부족" if storage_error else None, clear_frames=lambda: None,
        get_capture_backend_name=lambda: "fake",
        set_region=lambda *args: None, start_recording=lambda: None,
        get_frame_count=lambda: len(frames), get_estimated_size_mb=lambda: 64,
    )
    def stop():
        recorder.is_recording = False
        return frames
    def encode(captured, fps, path, *, overwrite):
        assert overwrite is False
        encoded.append((captured, fps))
        output.write_bytes(b"test")
        return True
    recorder.stop_recording = stop
    if not storage_error:
        recorder.start_recording = lambda: session._on_recording_error("테스트 화면 입력 종료")
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
    assert session.run() == module.EXIT_RUNTIME_ERROR
    assert session._stopped
    assert encoded == [(frames, expected_fps)]
    assert output.read_bytes() == b"test"
    assert (recorder.storage_stop_reason or "테스트 화면 입력 종료") in capsys.readouterr().err


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


@pytest.mark.parametrize(("seconds", "intervals"), [(0.25, [0.25]), (1.75, [1.0, 0.75])])
def test_countdown_waits_full_fractional_delay(monkeypatch, seconds, intervals):
    import cli.recorder as module
    calls = []
    session = CLIRecordingSession(SimpleNamespace(quiet=True))
    monkeypatch.setattr(module.time, "sleep", calls.append)
    session._countdown(seconds)
    assert calls == intervals


def test_missing_monitor_stops_before_engine_start(monkeypatch, tmp_path, capsys):
    import ctypes
    from ctypes import wintypes
    import cli.recorder as module
    if module.sys.platform != "win32":
        pytest.skip("Win32 display enumeration")

    def enumerate_monitors(hdc, clip, callback, data):
        for bounds in [(-800, 0, 0, 600), (0, 0, 1024, 768)]:
            callback(None, None, ctypes.pointer(wintypes.RECT(*bounds)), None)
        return 1

    monkeypatch.setattr(ctypes.windll.user32, "EnumDisplayMonitors", enumerate_monitors)
    assert module._get_monitor_region(1) == (-800, 0, 800, 600)
    session = CLIRecordingSession(SimpleNamespace(
        output=str(tmp_path / "take.gif"), overwrite=False, quiet=True, monitor=2,
    ))
    monkeypatch.setattr(module, "load_config", lambda: {})
    monkeypatch.setattr(session, "_init_engines", lambda *_: pytest.fail("Capture initialized"))
    assert session.run() == module.EXIT_USER_ERROR
    assert "모니터 2" in capsys.readouterr().err
    assert not (tmp_path / "take.gif").exists()


def test_active_ctrl_c_preserves_existing_recording(monkeypatch, tmp_path):
    from unittest.mock import Mock
    import cli.recorder as module

    path = tmp_path / "existing.gif"
    path.write_bytes(b"previous recording")
    session = CLIRecordingSession(SimpleNamespace(output=str(path), overwrite=True, quiet=True))
    recorder = Mock(fps=20, actual_fps=20, is_recording=True)
    recorder.stop_recording.return_value = [object()]
    session._recorder = recorder
    session._audio_recorder = Mock()
    session._encoder = Mock(quality="high")
    monkeypatch.setattr(session, "_init_engines", lambda *_: None)
    monkeypatch.setattr(session, "_check_ffmpeg", lambda *_: True)
    monkeypatch.setattr(session, "_resolve_region", lambda: (0, 0, 64, 64))
    monkeypatch.setattr(module, "load_config", lambda: {})
    monkeypatch.setattr(module, "install_signal_handlers",
                        lambda callback: monkeypatch.setattr(session, "_wait_for_completion", callback))
    monkeypatch.setattr(module, "restore_signal_handlers", lambda: None)

    assert session.run() == 130
    recorder.stop_recording.assert_called_once()
    session._audio_recorder.cleanup.assert_called_once()
    session._encoder.encode.assert_not_called()
    assert path.read_bytes() == b"previous recording"


@pytest.mark.parametrize(("limited", "encode_outcome"), [
    (True, "saved"), (True, "failed"), (True, "raised"),
    (False, "failed"), (False, "raised"), (False, "collision"), (False, "recovery_denied"),
])
def test_recording_publishes_take_or_keeps_recovery_sources(monkeypatch, tmp_path, capsys, limited, encode_outcome):
    from unittest.mock import Mock
    import numpy as np
    import cli.recorder as module

    output = tmp_path / "take.mp4"
    wav = tmp_path / "temporary.wav"
    wav.write_bytes(b"accepted audio")
    frame = np.arange(18, dtype=np.uint8).reshape(2, 3, 3)
    session = CLIRecordingSession(SimpleNamespace(output=str(output), overwrite=False, quiet=True, mic=True))
    recorder = Mock(fps=30, actual_fps=7.25, storage_stop_reason=None, is_recording=True)
    recorder.stop_recording.return_value = [frame]
    audio = Mock(buffer_limit_reached=limited)
    audio.start.return_value = SimpleNamespace(requested_mic_missing=False)
    audio.stop.return_value = str(wav)
    audio.cleanup.side_effect = lambda: wav.unlink(missing_ok=True)
    from core import audio_recorder
    monkeypatch.setattr(audio_recorder, "is_audio_available", lambda: True)
    monkeypatch.setattr(audio_recorder, "AudioRecorder", lambda **kwargs: audio)
    session._recorder = recorder
    encoder = Mock(quality="high")
    session._encoder = encoder
    monkeypatch.setattr(module, "msvcrt", SimpleNamespace(kbhit=lambda: True, getch=lambda: b"q"))
    if encode_outcome == "recovery_denied":
        def deny_recovery(*args, **kwargs):
            raise PermissionError("recovery denied")
        monkeypatch.setattr(module.tempfile, "mkdtemp", deny_recovery)

    def encode(frames, fps, path, *, audio_path, overwrite):
        assert frames[0] is frame and fps == 7.25 and audio_path == str(wav)
        assert overwrite is False
        if encode_outcome == "raised":
            raise OSError("disk full")
        if encode_outcome == "collision":
            output.write_bytes(b"another writer")
            return False
        if encode_outcome == "saved":
            output.write_bytes(b"partial video with audio")
            return True
        return False

    encoder.encode_mp4.side_effect = encode
    monkeypatch.setattr(module.tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(session, "_init_engines", lambda *_: None)
    monkeypatch.setattr(session, "_check_ffmpeg", lambda *_: True)
    monkeypatch.setattr(session, "_resolve_region", lambda: (0, 0, 64, 64))
    monkeypatch.setattr(module, "load_config", lambda: {})
    monkeypatch.setattr(module, "install_signal_handlers", lambda *_: None)
    monkeypatch.setattr(module, "restore_signal_handlers", lambda: None)
    assert session.run() == module.EXIT_RUNTIME_ERROR
    audio.set_record_system.assert_called_once_with(False)
    audio.set_record_mic.assert_called_once_with(True)
    logs = capsys.readouterr()
    if limited:
        assert module.AUDIO_BUFFER_LIMIT_ERROR in logs.err
    encoder.encode_mp4.assert_called_once()
    if encode_outcome == "recovery_denied":
        assert "recovery denied" in logs.err and str(wav) in logs.err
        assert wav.read_bytes() == b"accepted audio"
        recorder.clear_frames.assert_not_called()
        return
    if encode_outcome == "collision":
        assert output.read_bytes() == b"another writer"
    if encode_outcome == "saved":
        assert output.read_bytes() == b"partial video with audio"
        assert str(output) in logs.out and str(output) in logs.err
    else:
        recovery, = tmp_path.glob("xgif-recovery-*")
        assert str(recovery) in logs.err
        assert (recovery / "video.bgr").read_bytes() == frame.tobytes()
        assert (recovery / "audio.wav").read_bytes() == b"accepted audio"
        assert "-framerate 7.25" in (recovery / "recovery.txt").read_text()
    assert not wav.exists()


@pytest.mark.parametrize(("suffix", "fmt"), [("gif", "mp4"), ("mp4", "gif"), ("avi", None)])
def test_record_validates_output_before_capture(tmp_path, monkeypatch, suffix, fmt):
    import cli.recorder as module
    session = CLIRecordingSession(SimpleNamespace(output=str(tmp_path / f"take.{suffix}"), format=fmt, quiet=True, overwrite=False))
    monkeypatch.setattr(module, "load_config", lambda: pytest.fail("initialized before validating format"))
    assert session.run() == module.EXIT_USER_ERROR


def test_record_duration_excludes_paused_time(monkeypatch):
    from unittest.mock import Mock
    import cli.recorder as module
    session = CLIRecordingSession(SimpleNamespace(duration=3, quiet=True))
    session._recorder = Mock(is_recording=True)
    session._progress = Mock()
    clock = [0]
    monkeypatch.setattr(module.time, "monotonic", lambda: clock[0])
    monkeypatch.setattr(module.time, "time", lambda: clock[0])
    monkeypatch.setattr(module.time, "sleep", lambda _: clock.__setitem__(0, clock[0] + 1))
    monkeypatch.setattr(module, "msvcrt", SimpleNamespace(kbhit=lambda: clock[0] in (1, 6), getch=lambda: b" "))
    session._wait_for_completion()
    assert clock[0] == 8
    assert [call.args[0] for call in session._progress.update_paused.call_args_list] == [1] * 5


def test_recovery_uses_output_directory_when_temp_unwritable(monkeypatch, tmp_path, capsys):
    import cli.recorder as module
    import numpy as np
    session = CLIRecordingSession(SimpleNamespace(output=str(tmp_path / "take.gif"), quiet=True))
    monkeypatch.setattr(module.tempfile, "gettempdir", lambda: str(tmp_path / "missing-volume"))
    frame = np.arange(12, dtype=np.uint8).reshape(2, 2, 3)
    assert session._save_recovery_sources([frame], 10)
    recovery, = tmp_path.glob("xgif-recovery-*")
    assert (recovery / "video.bgr").read_bytes() == frame.tobytes()
    assert "recovered.gif" in (recovery / "recovery.txt").read_text()
    assert str(recovery) in capsys.readouterr().err
