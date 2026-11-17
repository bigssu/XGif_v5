from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ui import main_window


def test_new_recording_is_blocked_until_encoding_callback_finishes(monkeypatch):
    monkeypatch.setattr(main_window.wx, "MessageBox", Mock())
    window = SimpleNamespace(
        record_state=0, STATE_READY=0, _encoding_in_progress=True,
        recorder=Mock(),
    )
    main_window.MainWindow._start_recording(window)
    window.recorder.start_recording.assert_not_called()
    main_window.wx.MessageBox.assert_called_once()


@pytest.mark.parametrize("method", ["_do_start_recording", "_do_resume_recording"])
@pytest.mark.parametrize("closing,state", [(True, 1), (False, 0)])
def test_delayed_recording_callbacks_do_not_restart_stopped_session(method, closing, state):
    window = SimpleNamespace(
        _is_closing=closing, record_state=state, STATE_RECORDING=1, recorder=Mock(),
    )
    getattr(main_window.MainWindow, method)(window)
    assert window.recorder.mock_calls == []


def test_pause_and_resume_include_audio():
    window = SimpleNamespace(
        recorder=Mock(), audio_recorder=Mock(), capture_overlay=None,
        STATE_PAUSED=2, STATE_RECORDING=1, record_state=1,
        _update_button_states=Mock(), status_msg_label=Mock(),
    )
    main_window.MainWindow._pause_recording(window)
    window.audio_recorder.pause.assert_called_once()
    assert window.record_state == 2
    window.record_state = 1
    main_window.MainWindow._do_resume_recording(window)
    window.audio_recorder.resume.assert_called_once()


def test_close_vetoes_while_save_is_pending(monkeypatch):
    monkeypatch.setattr(main_window.wx, "MessageBox", Mock())
    window = SimpleNamespace(_is_closing=False, _encoding_in_progress=True)
    event = Mock()
    event.CanVeto.return_value = True
    main_window.MainWindow.OnClose(window, event)
    event.Veto.assert_called_once()
    event.Skip.assert_not_called()
    assert not window._is_closing


def test_reset_after_failed_or_cancelled_save_preserves_frames():
    frames = [object()]
    window = SimpleNamespace(
        frames=frames, info_label=Mock(), status_msg_label=Mock(),
        capture_control_bar=Mock(),
    )
    main_window.MainWindow._reset_ui(window, clear_frames=False)
    assert window.frames is frames
    window.capture_control_bar.rec_button.SetLabel.assert_called_with(main_window.tr('save_now'))


def test_new_recording_offers_recovery_of_unsaved_frames():
    window = SimpleNamespace(
        record_state=0, STATE_READY=0, frames=[object()], _recover_recording=Mock(),
    )
    main_window.MainWindow._start_recording(window)
    window._recover_recording.assert_called_once()


def test_encoding_failure_keeps_recording_for_retry(monkeypatch):
    monkeypatch.setattr(main_window.wx, "MessageBox", Mock())
    monkeypatch.setattr(main_window.wx, "CallLater", Mock())
    frames = [object()]
    window = SimpleNamespace(
        frames=frames, recorder=Mock(), _encoding_in_progress=True,
        encoding_progress_bar=Mock(), encoding_status_label=Mock(),
        _clear_encoding_status=Mock(), _reset_ui=Mock(),
    )
    main_window.MainWindow._on_encoding_error(window, "disk full")
    assert window.frames is frames
    window.recorder.clear_frames.assert_not_called()
    window._reset_ui.assert_called_once_with(clear_frames=False)


@pytest.mark.parametrize("encoding", [False, True])
def test_capture_failure_keeps_retry_or_active_save_state(monkeypatch, encoding):
    monkeypatch.setattr(main_window.wx, "MessageBox", Mock())
    window = SimpleNamespace(
        record_state=1, STATE_RECORDING=1, STATE_PAUSED=2,
        _encoding_in_progress=encoding, _stop_recording=Mock(), _reset_ui=Mock(),
    )
    main_window.MainWindow._on_recording_error(window, "capture failed")
    window._stop_recording.assert_called_once()
    if encoding:
        window._reset_ui.assert_not_called()
    else:
        window._reset_ui.assert_called_once_with(clear_frames=False)


def test_queued_resize_preview_does_not_mutate_export_source():
    from editor.ui.inline_toolbars.resize_toolbar_wx import ResizeToolbar

    toolbar = SimpleNamespace(
        _main_window=SimpleNamespace(_save_in_progress=True),
        _ensure_original_images_snapshot=Mock(),
    )
    ResizeToolbar._update_preview(toolbar)
    toolbar._ensure_original_images_snapshot.assert_not_called()
