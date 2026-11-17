import ast
import contextlib
import importlib.util
import sys
import threading
import time
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from tests._ast_helpers import find_class, parse_module


@pytest.fixture
def workers(monkeypatch):
    queue = []
    wx = SimpleNamespace(CallAfter=lambda fn, *args: queue.append((fn, args)),
                         App=SimpleNamespace(Get=lambda: None))
    monkeypatch.setitem(sys.modules, 'wx', wx)
    spec = importlib.util.spec_from_file_location('lifecycle_workers', 'editor/core/worker_wx.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, queue


def flush(queue):
    while queue:
        fn, args = queue.pop(0)
        fn(*args)


def test_worker_cancel_event_and_cancelled_result(workers):
    module, queue = workers
    load = Mock(return_value=SimpleNamespace(cancelled=True))
    worker = module.VideoLoadWorker(load, 'test.mp4')
    cancelled, finished = Mock(), Mock()
    worker.signals.connect('cancelled', cancelled)
    worker.signals.connect('finished', finished)
    worker.run()
    flush(queue)
    assert load.call_args.kwargs['cancel_event'] is worker._cancel_event
    cancelled.assert_called_once()
    finished.assert_not_called()


@pytest.mark.parametrize('kind', ['VideoLoadWorker', 'FunctionWorker'])
def test_precancel_skips_work(workers, kind):
    module, queue = workers
    load = Mock()
    args = (load, 'test.gif') if kind == 'VideoLoadWorker' else (load,)
    worker = getattr(module, kind)(*args)
    worker.cancel()
    worker.run()
    load.assert_not_called()


def test_disconnected_queued_callback_is_not_called(workers):
    module, queue = workers
    signals = module.WorkerSignals()
    callback = Mock()
    signals.connect('finished', callback)
    signals.emit_finished('done')
    signals.finished_callbacks.clear()
    flush(queue)
    callback.assert_not_called()


def test_wait_is_bounded_and_does_not_hold_manager_lock(workers):
    module, queue = workers
    release = threading.Event()
    manager = module.WorkerManager(max_threads=1)
    try:
        manager.start(module.FunctionWorker(lambda: release.wait(2)))
        start = time.monotonic()
        assert not manager.wait_for_done(30)
        assert time.monotonic() - start < .5
        assert manager._workers_lock.acquire(timeout=.1)
        manager._workers_lock.release()
        release.set()
        assert manager.wait_for_done(1000)
        flush(queue)
        assert manager.active_thread_count == 0
    finally:
        release.set()
        manager.shutdown()


@pytest.fixture
def window(workers):
    module, queue = workers
    names = {'_open_video_file', '_start_load_worker', '_poll_load_cancel', '_finish_load', '_cleanup_workers',
             '_preload_playback_window', '_on_play_timer', '_on_probe_load_finished',
             '_on_probe_load_error', '_on_probe_load_cancelled'}
    cls = find_class(parse_module('editor/ui/editor_main_window_wx.py'), 'MainWindow')
    cls.bases = []
    cls.body = [n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name in names]
    wx = SimpleNamespace(Timer=Mock(), EVT_TIMER=1, TIMER_ONE_SHOT=2,
                         ProgressDialog=Mock(), PD_APP_MODAL=1, PD_AUTO_HIDE=2, PD_CAN_ABORT=4,
                         MessageBox=Mock(), OK=1, ICON_ERROR=2)
    manager = Mock()
    ns = dict(wx=wx, get_worker_manager=lambda: manager, contextlib=contextlib,
              FunctionWorker=module.FunctionWorker, __package__='editor.ui')
    exec(compile(ast.Module(body=[cls], type_ignores=[]), '<lifecycle>', 'exec'), ns)
    obj = ns['MainWindow']()
    obj.Bind = Mock()
    obj._logger = Mock()
    obj._translations = SimpleNamespace(tr=lambda key, **kwargs: key)
    return obj, module, queue, wx, manager


def test_cancel_without_progress_stops_load_and_ignores_late_completion(window):
    obj, module, queue, wx, manager = window
    obj._video_progress = Mock(WasCancelled=Mock(return_value=True))
    progress = obj._video_progress
    obj._on_video_load_finished = Mock()
    worker = module.VideoLoadWorker(Mock(), 'test.mp4')
    obj._start_load_worker('video', worker)
    worker.signals.emit_finished(SimpleNamespace(success=True))
    obj._poll_load_cancel(None)
    flush(queue)
    assert worker.is_cancelled
    obj._on_video_load_finished.assert_not_called()
    progress.Destroy.assert_called_once()
    obj._load_cancel_timer.Stop.assert_called_once()
    obj._load_cancel_timer.Start.assert_called_once_with(100)


def test_close_cleans_gif_probe_and_drops_queued_completion(window):
    obj, module, queue, wx, manager = window
    workers = []
    for kind in ('gif', 'probe'):
        setattr(obj, f'_{kind}_progress', Mock())
        setattr(obj, f'_on_{kind}_load_finished', Mock())
        worker = module.VideoLoadWorker(Mock(), 'test.gif')
        workers.append(worker)
        obj._start_load_worker(kind, worker)
        worker.signals.emit_finished(SimpleNamespace(success=True))
    obj._closing = True
    obj._cleanup_workers()
    flush(queue)
    assert all(w.is_cancelled for w in workers)
    obj._on_gif_load_finished.assert_not_called()
    obj._on_probe_load_finished.assert_not_called()
    assert obj._gif_worker is None and obj._probe_worker is None


def test_probe_failure_closes_progress_without_fps_dialog(window):
    obj, module, queue, wx, manager = window
    obj._video_file_path = 'test.mp4'
    obj._probe_progress = Mock()
    obj._on_probe_load_finished(None)
    wx.MessageBox.assert_called_once()
    assert obj._probe_progress is None


def test_playback_wrap_bounds_decodes_and_preserves_select_all(window):
    from PIL import Image
    from editor.core.frame import Frame
    from editor.core.frame_collection import FrameCollection

    obj, module, queue, wx, manager = window
    obj._frames = FrameCollection()
    for i in range(12):
        obj._frames.add_frame(Frame(Image.new('RGB', (3, 3), (i, 0, 0))))
    obj._frames.select_all()
    selected = obj._frames.selected_indices.copy()
    obj._frames.current_index = 10
    obj._is_playing = True
    obj._update_slider = Mock()
    obj._canvas = Mock()
    obj._play_timer = Mock()
    obj._frames.preload_range(0, 11)
    for _ in range(25):
        obj._on_play_timer(None)
        index = obj._frames.current_index
        assert {i for i, frame in enumerate(obj._frames) if frame.is_loaded} == {
            (index + j) % 12 for j in range(5)}
        assert obj._frames.selected_indices == selected


def test_probe_does_not_run_on_ui_thread(window, monkeypatch):
    obj, module, queue, wx, manager = window
    probe = Mock(return_value=None)
    monkeypatch.setitem(sys.modules, 'editor.core.video_decoder',
                        SimpleNamespace(VideoDecoder=SimpleNamespace(get_video_info=probe)))
    obj._open_video_file('test.mp4')
    probe.assert_not_called()
    worker = manager.start.call_args.args[0]
    worker.run()
    probe.assert_called_once_with('test.mp4', cancel_event=worker._cancel_event)


def test_timer_cancels_running_decoder_with_no_progress(window):
    obj, module, queue, wx, manager = window
    started = threading.Event()

    def stalled(path, *, cancel_event, progress_callback):
        started.set()
        assert cancel_event.wait(2)
        return SimpleNamespace(cancelled=True)

    obj._gif_progress = Mock(WasCancelled=Mock(return_value=False))
    worker = module.VideoLoadWorker(stalled, 'stalled.gif')
    obj._start_load_worker('gif', worker)
    thread = threading.Thread(target=worker.run)
    thread.start()
    try:
        assert started.wait(1)
        obj._gif_progress.WasCancelled.return_value = True
        obj._poll_load_cancel(None)
        thread.join(1)
        assert not thread.is_alive()
        assert worker.is_cancelled
        flush(queue)
    finally:
        worker.cancel()
        thread.join(2)
