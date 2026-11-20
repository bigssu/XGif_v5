from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import numpy as np
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
    getattr(main_window.MainWindow, method)(window, object())
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
    window._recording_session = object()
    main_window.MainWindow._do_resume_recording(window, window._recording_session)
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
    window.capture_control_bar.fps_combo.Enable.assert_called_with(False)
    window.capture_control_bar.format_combo.Enable.assert_called_with(False)
    window.capture_control_bar.rec_button.SetLabel.assert_called_with(main_window.tr('save_now'))


def test_editor_receives_unsaved_recording_with_measured_timing(monkeypatch):
    from editor.ui import editor_main_window_wx as editor

    pixel = np.array([[[10, 20, 30, 0]]], dtype=np.uint8)
    recorder = Mock(actual_fps=12.5)
    window = SimpleNamespace(frames=[pixel], _take_fps=12.5, recorder=recorder, status_msg_label=Mock(), Close=Mock())
    document = Mock()
    open_unsaved_frames = editor.MainWindow.open_unsaved_frames
    document.open_unsaved_frames.side_effect = lambda frames: open_unsaved_frames(document, frames)
    monkeypatch.setattr(editor, 'MainWindow', lambda: document)

    main_window.MainWindow._open_editor_with_frames(window)

    assert document._current_file_path is None
    assert document._is_modified
    assert document._frames[0].delay_ms == 80
    assert document._frames[0].image.getpixel((0, 0)) == (30, 20, 10)
    document.Show.assert_called_once()
    window.Close.assert_called_once()
    assert window.frames == []


@pytest.mark.parametrize('failure', ['conversion', 'open', 'show'])
def test_editor_handoff_failure_preserves_recording(monkeypatch, failure):
    from editor.ui import editor_main_window_wx as editor

    frames = [None] if failure == 'conversion' else [np.zeros((1, 1, 3), dtype=np.uint8)]
    window = SimpleNamespace(frames=frames, _take_fps=10, recorder=Mock(actual_fps=10), status_msg_label=Mock(),
                             _reset_ui=Mock(), Close=Mock())
    document = Mock()
    if failure == 'open':
        document.open_unsaved_frames.side_effect = RuntimeError("editor failed")
    if failure == 'show':
        document.Show.side_effect = RuntimeError("display failed")
    monkeypatch.setattr(editor, 'MainWindow', lambda: document)
    monkeypatch.setattr(main_window.wx, 'MessageBox', Mock())
    main_window.MainWindow._open_editor_with_frames(window)
    assert window.frames is frames
    window.recorder.clear_frames.assert_not_called()
    window.Close.assert_not_called()
    window._reset_ui.assert_called_once_with(clear_frames=False)
    if failure != 'conversion':
        document.Destroy.assert_called_once()


def test_cancel_overwrite_of_normalized_recording_path_preserves_file(tmp_path, monkeypatch):
    target = tmp_path / 'take.gif'
    target.write_bytes(b'previous')
    frames = [object()]
    bar = Mock()
    bar.get_format.return_value = 'GIF'
    window = SimpleNamespace(frames=frames, _take_format="GIF", encoder=Mock(), encoding_thread=None,
                             capture_control_bar=bar, settings=Mock(), _reset_ui=Mock())
    dialog = MagicMock()
    dialog.__enter__.return_value = dialog
    dialog.ShowModal.return_value = main_window.wx.ID_OK
    dialog.GetPath.return_value = str(tmp_path / 'take.Mp4')
    monkeypatch.setattr(main_window.wx, 'FileDialog', lambda *args: dialog)
    confirm = Mock(return_value=main_window.wx.NO)
    monkeypatch.setattr(main_window.wx, 'MessageBox', confirm)
    main_window.MainWindow._save_gif(window)

    assert str(target) in confirm.call_args.args[0]
    assert target.read_bytes() == b'previous'
    assert window.frames is frames
    window._reset_ui.assert_called_once_with(clear_frames=False)
    window.encoder.set_quality.assert_not_called()


def test_close_with_retained_recording_defaults_to_keep(monkeypatch):
    frames = [object()]
    window = SimpleNamespace(frames=frames, _is_closing=False, record_state=0, STATE_READY=0)
    confirm = Mock(return_value=main_window.wx.NO)
    monkeypatch.setattr(main_window.wx, 'MessageBox', confirm)
    event = Mock()
    event.CanVeto.return_value = True
    main_window.MainWindow.OnClose(window, event)

    assert confirm.call_args.args[2] & main_window.wx.NO_DEFAULT
    event.Veto.assert_called_once()
    assert not window._is_closing
    assert window.frames is frames


def test_save_dialog_destruction_stops_deferred_previews():
    from editor.ui.save_dialog_wx import SaveDialog

    timers = [Mock() for _ in range(4)]
    dialog = SimpleNamespace(_preview_timer=timers[0], _size_timer=timers[1], _initial_previews=timers[2:])
    dialog._stop_timers = lambda: SaveDialog._stop_timers(dialog)
    event = Mock()
    event.GetEventObject.return_value = dialog
    SaveDialog._on_window_destroy(dialog, event)
    for timer in timers:
        timer.Stop.assert_called_once()
    event.Skip.assert_called_once()


def test_editor_refuses_unconfirmed_extensionless_overwrite(monkeypatch, tmp_path):
    from editor.ui.save_dialog_wx import SaveDialog

    target = tmp_path / 'take.gif'
    target.write_bytes(b'previous')
    picker = Mock()
    picker.ShowModal.return_value = main_window.wx.ID_OK
    picker.GetPath.return_value = str(target.with_suffix(''))
    picker.GetFilterIndex.return_value = 3  # All files
    monkeypatch.setattr(main_window.wx, 'FileDialog', lambda *args, **kwargs: picker)
    confirm = Mock(return_value=main_window.wx.NO)
    monkeypatch.setattr(main_window.wx, 'MessageBox', confirm)
    dialog = SimpleNamespace(_main_window=None, _file_path=None, EndModal=Mock(),
                             _get_translation=lambda key, default: default)
    SaveDialog._on_save(dialog, None)
    assert str(target) in confirm.call_args.args[0]
    assert dialog._file_path is None
    assert target.read_bytes() == b'previous'
    dialog.EndModal.assert_not_called()
    picker.Destroy.assert_called_once()


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

def test_three_saves_release_worker_source_and_reuse_only_retained_recording(monkeypatch, tmp_path):
    import gc
    import weakref
    from functools import partial
    from core.gif_encoder import GifEncoder
    from core.recording_frames import RecordingFrames

    pending = []
    monkeypatch.setattr(main_window.wx, "CallAfter", lambda cb, *args: pending.append((cb, args)))
    monkeypatch.setattr(main_window.wx, "CallLater", Mock())
    monkeypatch.setattr(main_window.wx, "MessageBox", Mock())
    monkeypatch.setattr(main_window.os, "startfile", lambda path: None)
    dialog = MagicMock()
    dialog.__enter__.return_value = dialog
    dialog.ShowModal.return_value = main_window.wx.ID_OK
    dialog.GetPath.return_value = str(tmp_path / 'recording.gif')
    monkeypatch.setattr(main_window.wx, "FileDialog", lambda *args: dialog)

    bar = Mock()
    bar.get_format.return_value = "GIF"
    bar.get_quality.return_value = 0
    bar.get_fps.return_value = 15
    encoder = GifEncoder()
    window = SimpleNamespace(
        _take_format="GIF", _take_fps=14.2, recorder=Mock(), encoder=encoder, settings=Mock(), capture_control_bar=bar,
        encoding_thread=None, encoding_progress_bar=None, encoding_status_label=None,
        status_msg_label=Mock(), _on_encoding_progress=Mock(), _reset_ui=Mock(),
        _clear_encoding_status=Mock(),
    )
    for method in ('_on_encoding_finished', '_on_encoding_error', '_cancel_encoding_status_timers'):
        setattr(window, method, partial(getattr(main_window.MainWindow, method), window))

    class IndexedFrames(RecordingFrames):
        def __iter__(self):
            raise AssertionError("The save dialog materialized all frames")

    outcomes = iter((True, False, True, True))
    def encode(source, fps, output, *, overwrite):
        assert not overwrite
        assert fps == 14.2
        assert source is reference()
        assert source[0].shape == (2, 2, 3)
        if not next(outcomes):
            encoder._emit_error("disk full")
            return False
        return True
    monkeypatch.setattr(encoder, "encode", encode)

    for i in range(3):
        window.frames = IndexedFrames(0)
        window.frames.append(np.full((2, 2, 3), i, dtype=np.uint8))
        reference = weakref.ref(window.frames)
        for attempt in range(2 if i == 1 else 1):
            main_window.MainWindow._save_gif(window)
            worker = window.encoding_thread
            worker.join(timeout=5)
            assert not worker.is_alive()
            assert worker.frames is None
            assert encoder._progress_callback is None and encoder._error_callback is None
            assert len(pending) == 1
            callback, args = pending.pop()
            callback(*args)
            assert window.encoding_thread is None
            if i == 1 and attempt == 0:
                assert window.frames is reference()
        gc.collect()
        assert reference() is None


def test_timer_reports_only_resident_capture_bytes(monkeypatch):
    monkeypatch.setattr(main_window, 'HAS_PSUTIL', False)
    recorder = Mock()
    recorder.get_frame_count.side_effect = [10, 1000]
    recorder.get_estimated_size_mb.return_value = 5
    window = SimpleNamespace(STATE_RECORDING=1, record_state=1, record_elapsed=0, recorder=recorder,
                             info_label=Mock(), _get_memory_limit_mb=lambda: 10, _stop_recording=Mock())
    for _ in range(2):
        main_window.MainWindow._update_record_time(window)
    assert '1000f | 5.0MB' in window.info_label.SetLabel.call_args.args[0]
    window._stop_recording.assert_not_called()


def test_storage_warning_after_stop_offers_salvaged_frames(monkeypatch):
    order = []
    frames = [object()]
    recorder = Mock(storage_stop_reason='disk full', actual_fps=0)
    def stop():
        order.append('stop')
        return frames
    recorder.stop_recording.side_effect = stop
    monkeypatch.setattr(main_window.wx, 'MessageBox', lambda message, *args: order.append(message))
    window = SimpleNamespace(record_timer=None, _take_format="GIF", record_state=1, STATE_READY=0, recorder=recorder,
                             capture_overlay=None, audio_recorder=None, _update_button_states=Mock(),
                             _show_save_edit_dialog=lambda count: order.append(count))
    main_window.MainWindow._stop_recording(window)
    assert window.frames is frames
    assert order == ['stop', 'disk full', 1]


def test_disk_recording_editor_handoff_reads_only_requested_frame(monkeypatch):
    from core.recording_frames import RecordingFrames
    from editor.ui import editor_main_window_wx as editor

    reads = []
    class TrackedFrames(RecordingFrames):
        def __getitem__(self, index):
            reads.append(index)
            return super().__getitem__(index)

    source = TrackedFrames(0)
    for i in range(10):
        source.append(np.array([[[10, 20, i]]], dtype=np.uint8))
    window = SimpleNamespace(frames=source, _take_fps=10, recorder=Mock(actual_fps=10), status_msg_label=Mock(), Close=Mock())
    document = Mock()
    open_document = editor.MainWindow.open_unsaved_frames
    document.open_unsaved_frames.side_effect = lambda frames: open_document(document, frames)
    monkeypatch.setattr(editor, 'MainWindow', lambda: document)

    main_window.MainWindow._open_editor_with_frames(window)
    assert window.frames == []
    window.recorder.clear_frames.assert_called_once()
    assert document._frames.lazy_load_enabled
    assert reads == [0]
    assert document._frames[8].image.getpixel((0, 0)) == (8, 20, 10)
    assert reads == [0, 8]

@pytest.mark.parametrize("codec, encoder_name", [("h265", "nvenc"), ("h264", "auto")])
@pytest.mark.parametrize("existing", [True, False])
def test_mp4_retry_preserves_capture_mode_timing_and_audio(monkeypatch, tmp_path, codec, encoder_name, existing):
    frames = [object()]
    dialog = MagicMock()
    dialog.__enter__.return_value = dialog
    dialog.ShowModal.return_value = main_window.wx.ID_OK
    dialog.GetPath.return_value = str(tmp_path / "retry.gif")
    monkeypatch.setattr(main_window.wx, "FileDialog", lambda *args: dialog)
    if existing:
        (tmp_path / 'retry.mp4').write_bytes(b'existing recording')
    confirm = Mock(return_value=main_window.wx.YES)
    monkeypatch.setattr(main_window.wx, 'MessageBox', confirm)
    worker = Mock()
    monkeypatch.setattr(main_window, "EncodingThread", worker)
    bar = Mock()
    bar.get_format.return_value = "GIF"
    bar.get_fps.return_value = 60
    bar.get_quality.return_value = 0
    settings = Mock()
    settings.get.side_effect = lambda key, fallback: {"codec": codec, "encoder": encoder_name}.get(key, fallback)
    window = SimpleNamespace(
        _take_format="MP4", _take_fps=12.34, audio_file_path="accepted.wav", frames=frames,
        capture_control_bar=bar, encoder=Mock(), settings=settings, encoding_thread=None,
        _cancel_encoding_status_timers=Mock(), encoding_progress_bar=None, encoding_status_label=None,
        status_msg_label=Mock(), _on_encoding_progress=Mock(), _on_encoding_finished=Mock(), _on_encoding_error=Mock(),
    )
    main_window.MainWindow._save_gif(window)
    assert worker.call_args.args == (window.encoder, frames, 12.34, str(tmp_path / "retry.mp4"), "mp4", "accepted.wav")
    assert worker.call_args.kwargs["overwrite"] is existing
    assert confirm.call_count == int(existing)
    window.encoder.set_codec.assert_called_once_with(codec)
    window.encoder.set_preferred_encoder.assert_called_once_with(encoder_name)
    bar.get_format.assert_not_called()
    bar.get_fps.assert_not_called()


@pytest.mark.parametrize('fmt', ['gif', 'mp4'])
@pytest.mark.parametrize('approved', [False, True])
def test_recording_worker_only_replaces_after_approval(tmp_path, fmt, approved):
    from core.utils import publish_output

    target = tmp_path / f'take.{fmt}'
    target.write_bytes(b'competing save')
    staged = tmp_path / f'temp.{fmt}'
    staged.write_bytes(b'new capture')
    encoder = Mock()
    def encode(frames, fps, path, *audio, overwrite):
        publish_output(staged, path, overwrite=overwrite)
        return True
    encoder.encode.side_effect = encoder.encode_mp4.side_effect = encode
    main_window.EncodingThread(encoder, [], 15, target, fmt, overwrite=approved).run()
    assert target.read_bytes() == (b'new capture' if approved else b'competing save')


def test_f11_preserves_user_position_and_click_highlight_setting_applies():
    from core.settings import AppSettings

    window = Mock()
    overlay = window.capture_overlay
    overlay.IsShown.side_effect = (True, False)
    for _ in range(2):
        main_window.MainWindow._on_shortcut_overlay(window)
    overlay.Hide.assert_called_once()
    overlay.Show.assert_called_once()
    window._position_overlay_below_window.assert_not_called()
    window.settings = AppSettings(click_highlight='true')
    window.preview_enabled = False
    main_window.MainWindow._apply_settings(window)
    window.capture_control_bar.set_region_visible.assert_called_once_with(True)

def test_pause_during_delayed_start_leaves_recording_armed():
    window = SimpleNamespace(recorder=Mock(is_recording=False), audio_recorder=Mock(),
                             capture_overlay=None, STATE_PAUSED=2, record_state=1,
                             _update_button_states=Mock(), status_msg_label=Mock())
    main_window.MainWindow._pause_recording(window)
    assert window.record_state == 1
    window.recorder.pause_recording.assert_not_called()
    window.audio_recorder.pause.assert_not_called()


@pytest.mark.parametrize("method", ["_do_start_recording", "_do_resume_recording"])
def test_previous_session_callbacks_ignore_new_recording(method):
    current = object()
    window = SimpleNamespace(_recording_session=current, record_state=1, STATE_RECORDING=1,
                             _is_closing=False, recorder=Mock())
    getattr(main_window.MainWindow, method)(window, object())
    assert window.recorder.mock_calls == []


def test_paused_capture_area_stays_locked():
    window = SimpleNamespace(recorder=Mock(is_recording=True), audio_recorder=None,
                             capture_overlay=Mock(), STATE_PAUSED=2, record_state=1,
                             _update_button_states=Mock(), status_msg_label=Mock())
    main_window.MainWindow._pause_recording(window)
    window.capture_overlay.set_movable.assert_called_once_with(False)


def test_restart_assigns_distinct_token_and_old_start_never_touches_new_take(monkeypatch):
    window = SimpleNamespace(record_state=0, STATE_READY=0, STATE_RECORDING=1, STATE_PAUSED=2,
                             frames=[], _recording_session=None, _is_closing=False, recorder=Mock(),
                             capture_overlay=Mock(), _cancel_encoding_status_timers=Mock(),
                             _update_button_states=Mock())
    window.capture_overlay.get_capture_region.return_value = window.recorder.region = (1, 2, 16, 12)
    window._do_start_recording = lambda session: main_window.MainWindow._do_start_recording(window, session)
    scheduled = []
    monkeypatch.setattr(main_window.wx, "CallLater", lambda delay, fn, *args: scheduled.append((fn, args)))
    main_window.MainWindow._start_recording(window)
    window._recording_session = None
    window.record_state = window.STATE_READY
    main_window.MainWindow._start_recording(window)
    assert scheduled[0][1][0] is not scheduled[1][1][0]
    scheduled[0][0](*scheduled[0][1])
    window.recorder.start_recording.assert_not_called()
    window.recorder.set_capture_backend.assert_not_called()
