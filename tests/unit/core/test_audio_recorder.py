import numpy as np

from core import audio_recorder


def test_derive_audio_buffer_limit_clamps_to_release_safe_bounds():
    assert audio_recorder.derive_audio_buffer_limit_mb("1024") == 256
    assert audio_recorder.derive_audio_buffer_limit_mb("4096") == 512
    assert audio_recorder.derive_audio_buffer_limit_mb("128") == 64
    assert audio_recorder.derive_audio_buffer_limit_mb("not-a-number") == 256


def test_audio_recorder_defaults_to_bounded_buffer(monkeypatch):
    monkeypatch.setattr(audio_recorder, "HAS_AUDIO", False)

    recorder = audio_recorder.AudioRecorder()

    assert recorder._max_buffer_bytes == (
        audio_recorder.DEFAULT_AUDIO_BUFFER_LIMIT_MB * 1024 * 1024
    )


def test_audio_callback_stops_appending_after_buffer_limit(monkeypatch):
    monkeypatch.setattr(audio_recorder, "HAS_AUDIO", False)

    recorder = audio_recorder.AudioRecorder(max_buffer_mb=4 / (1024 * 1024))
    recorder.recording = True
    recorder.record_system = True

    chunk = np.zeros((1, 1), dtype=np.float32)
    recorder._system_audio_callback(chunk, None, None, None)
    recorder._system_audio_callback(chunk, None, None, None)

    assert recorder.buffer_limit_reached is True
    assert len(recorder.system_audio_data) == 1


def test_stop_clears_buffers_when_merge_fails(monkeypatch):
    monkeypatch.setattr(audio_recorder, "HAS_AUDIO", False)

    recorder = audio_recorder.AudioRecorder()
    recorder.recording = True
    recorder.system_audio_data = [np.zeros((1, 1), dtype=np.float32)]
    recorder.mic_audio_data = [np.zeros((1, 1), dtype=np.float32)]
    recorder._audio_buffer_total_bytes = 8
    recorder._buffer_limit_reached = True
    monkeypatch.setattr(recorder, "_merge_audio", lambda: None)

    assert recorder.stop() is None
    assert recorder.system_audio_data == []
    assert recorder.mic_audio_data == []
    assert recorder._audio_buffer_total_bytes == 0
    assert recorder.buffer_limit_reached is False
