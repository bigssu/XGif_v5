import ast
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests._ast_helpers import find_class, parse_module


@pytest.fixture
def window():
    names = {
        'new_project', 'open_file', 'open_image_sequence', 'closeEvent', '_confirm_save',
        'save_file', 'save_file_as', '_save_to_path', '_save_to_path_with_settings',
        '_on_save_finished', '_on_save_finished_ui', '_on_save_error', '_on_save_error_ui',
        '_on_save_cancelled', '_finish_save', '_stop_preview_before_save', '_duplicate_frame',
    }
    cls = find_class(parse_module('editor/ui/editor_main_window_wx.py'), 'MainWindow')
    cls.bases = []
    cls.body = [node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name in names]
    wx = SimpleNamespace(**{name: i for i, name in enumerate([
        'ID_YES', 'ID_NO', 'ID_CANCEL', 'ID_OK', 'YES_NO', 'CANCEL', 'ICON_QUESTION',
        'OK', 'ICON_ERROR', 'ICON_INFORMATION', 'PD_APP_MODAL', 'PD_AUTO_HIDE',
    ])})
    wx.MessageDialog = Mock(return_value=Mock(ShowModal=Mock(return_value=wx.ID_YES)))
    wx.ProgressDialog = Mock()
    wx.MessageBox = Mock()
    wx.CallAfter = lambda fn, *args: fn(*args)
    wx.CallLater = Mock()
    manager = Mock()
    encoder = Mock()
    namespace = dict(wx=wx, os=os, Path=Path, EncoderSettings=Mock(), GifEncoder=encoder,
                     FunctionWorker=lambda fn: SimpleNamespace(func=fn, signals=Mock()),
                     get_worker_manager=lambda: manager, SaveDialog=Mock(),
                     ensure_exit_if_no_primary_windows=Mock())
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<editor methods>', 'exec'), namespace)
    obj = namespace['MainWindow']()
    obj._is_modified = True
    obj._is_playing = False
    obj._active_inline_toolbar = None
    obj._property_bar = SimpleNamespace(_toolbars={})
    obj._save_in_progress = False
    obj._pending_save_action = None
    obj._frames = Mock()
    obj._undo_manager = Mock()
    obj._current_file_path = 'original.gif'
    obj._translations = SimpleNamespace(tr=lambda key, **kwargs: key)
    for name in ['_update_title', '_update_info_bar', '_refresh_all', 'pause',
                 '_open_file_location', '_cleanup_workers', 'Close']:
        setattr(obj, name, Mock())
    obj._play_timer = Mock()
    obj._gpu_update_timer = Mock()
    return obj, namespace, manager


def finish(obj, success=True):
    obj._on_save_finished_ui(SimpleNamespace(success=success, error_message='failed', file_size=1024))


def test_new_waits_for_success(window):
    obj, _, manager = window
    obj.new_project()
    obj._frames.clear.assert_not_called()
    manager.start.assert_called_once()
    finish(obj)
    obj._frames.clear.assert_called_once()


@pytest.mark.parametrize('failure', ['result', 'exception', 'cancelled'])
def test_failed_save_keeps_document_and_drops_navigation(window, failure):
    obj, _, _ = window
    obj.new_project()
    if failure == 'result':
        finish(obj, False)
    elif failure == 'exception':
        obj._on_save_error_ui('failed', '')
    else:
        obj._on_save_cancelled()
    obj._frames.clear.assert_not_called()
    assert obj._is_modified
    assert not obj._save_in_progress
    assert obj._pending_save_action is None


def test_save_as_cancel_keeps_document(window):
    obj, namespace, manager = window
    obj._current_file_path = None
    namespace['SaveDialog'].return_value.ShowModal.return_value = namespace['wx'].ID_CANCEL
    obj.new_project()
    obj._frames.clear.assert_not_called()
    manager.start.assert_not_called()
    assert obj._pending_save_action is None


def test_open_waits_for_success(window, tmp_path):
    obj, _, _ = window
    path = tmp_path / 'next.gif'
    path.touch()
    obj._open_gif_async = Mock()
    obj.open_file(str(path))
    obj._open_gif_async.assert_not_called()
    finish(obj)
    obj._open_gif_async.assert_called_once_with(str(path))


def test_close_is_vetoed_until_save_success(window):
    obj, _, _ = window
    event = Mock()
    obj.closeEvent(event)
    event.Veto.assert_called_once()
    event.Skip.assert_not_called()
    obj._cleanup_workers.assert_not_called()
    finish(obj)
    obj.Close.assert_called_once()
    assert not obj._is_modified


def test_export_captures_snapshot_and_rejects_duplicate_actions(window):
    obj, namespace, manager = window
    frames = obj._frames
    obj.new_project()
    worker = manager.start.call_args.args[0]
    obj.save_file()
    obj.open_file('next.gif')
    manager.start.assert_called_once()
    obj._frames = Mock()
    worker.func()
    namespace['GifEncoder'].save.assert_called_once_with(frames.clone.return_value, 'original.gif',
                                                        namespace['EncoderSettings'].return_value)


def test_worker_start_failure_keeps_document(window):
    obj, _, manager = window
    manager.start.side_effect = RuntimeError('executor unavailable')
    obj.new_project()
    obj._frames.clear.assert_not_called()
    assert obj._is_modified
    assert not obj._save_in_progress
    assert obj._pending_save_action is None


def test_close_success_resumes_normal_cleanup(window, monkeypatch):
    import sys

    obj, namespace, _ = window
    shutdown = Mock()
    monkeypatch.setitem(sys.modules, 'editor.core.worker_wx',
                        SimpleNamespace(shutdown_worker_manager=shutdown))
    namespace['__package__'] = 'editor.ui'
    event = Mock()
    obj.Close.side_effect = lambda: obj.closeEvent(event)
    obj.closeEvent(Mock())
    shutdown.assert_not_called()
    finish(obj)
    event.Skip.assert_called_once()
    event.Veto.assert_not_called()
    obj._cleanup_workers.assert_called_once()
    shutdown.assert_called_once()


@pytest.mark.parametrize('method', [
    '_duplicate_frame', '_run_undoable_with_progress',
    '_on_merge_gif_finished', '_on_insert_gif_finished',
])
def test_undo_snapshot_survives_repeated_redo(method):
    import copy

    cls = find_class(parse_module('editor/ui/editor_main_window_wx.py'), 'MainWindow')
    outer = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == method)
    undo = next(node for node in ast.walk(outer) if isinstance(node, ast.FunctionDef) and node.name == 'undo')

    class Collection:
        def __init__(self):
            self.frames = [[1], [2]]

        def clone(self):
            return copy.deepcopy(self)

    snapshot = Collection()
    obj = SimpleNamespace(_frames=Collection(), _refresh_all=Mock())
    namespace = {'self': obj, 'old_frames': snapshot}
    exec(compile(ast.Module(body=[undo], type_ignores=[]), '<undo closure>', 'exec'), namespace)
    for _ in range(3):
        namespace['undo']()
        assert obj._frames.frames == [[1], [2]]
        obj._frames.frames.append([3])
        obj._frames.frames[0][0] = 99
    assert snapshot.frames == [[1], [2]]


def test_new_project_clears_previous_undo_history(window):
    obj, _, _ = window
    obj._is_modified = False
    obj._undo_manager = Mock()
    obj.new_project()
    obj._undo_manager.clear.assert_called_once()


def test_mixed_delete_duplicate_undo_redo(window):
    from PIL import Image
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection
    from editor.core.undo_manager import UndoManager

    obj, _, _ = window
    obj._frames = FrameCollection()
    for delay in [10, 20, 30]:
        obj._frames.add_frame(Frame(Image.new('RGB', (2, 2)), delay))
    obj._undo_manager = UndoManager()
    cls = find_class(parse_module('editor/ui/frame_list_widget_wx.py'), 'FrameListWidget')
    outer = next(node for node in cls.body if isinstance(node, ast.FunctionDef) and node.name == 'delete_selected_frames')
    methods = [node for node in ast.walk(outer) if isinstance(node, ast.FunctionDef) and node.name in {'execute', 'undo'}]
    namespace = {'self': SimpleNamespace(_main_window=obj), 'frames': obj._frames,
                 'old_frames': obj._frames.clone(), 'selected_rows_copy': [1]}
    exec(compile(ast.Module(body=methods, type_ignores=[]), '<delete closures>', 'exec'), namespace)
    # The widget accesses the same current collection via the public property.
    type(obj).frames = property(lambda self: self._frames)
    obj._undo_manager.execute_lambda('delete', namespace['execute'], namespace['undo'], 0)
    obj._duplicate_frame()
    for _ in range(3):
        assert [f.delay_ms for f in obj._frames] == [10, 10, 30]
        obj._undo_manager.undo()
        assert [f.delay_ms for f in obj._frames] == [10, 30]
        obj._undo_manager.undo()
        assert [f.delay_ms for f in obj._frames] == [10, 20, 30]
        obj._undo_manager.redo()
        assert [f.delay_ms for f in obj._frames] == [10, 30]
        obj._undo_manager.redo()


def test_snapshot_clone_runs_only_in_worker(window):
    obj, _, manager = window
    frames = obj._frames
    obj.save_file()
    frames.clone.assert_not_called()
    manager.start.call_args.args[0].func()
    frames.clone.assert_called_once()


def test_save_stops_all_preview_timers_and_settles_active_preview(window):
    obj, _, manager = window
    active, inactive = Mock(), Mock()
    active._preview_timer.IsRunning.return_value = True
    obj._active_inline_toolbar = active
    obj._property_bar._toolbars = {'active': active, 'inactive': inactive}
    calls = Mock()
    calls.attach_mock(active._preview_timer.Stop, 'stop_active')
    calls.attach_mock(inactive._preview_timer.Stop, 'stop_inactive')
    calls.attach_mock(active._update_preview, 'settle')
    calls.attach_mock(manager.start, 'start')
    obj.save_file()
    active._preview_timer.Stop.assert_called_once()
    inactive._preview_timer.Stop.assert_called_once()
    active._update_preview.assert_called_once()
    assert [call[0] for call in calls.mock_calls] == ['stop_active', 'stop_inactive', 'settle', 'start']
