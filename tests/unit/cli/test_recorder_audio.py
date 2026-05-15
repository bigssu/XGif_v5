from types import SimpleNamespace

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
