"""EventBus subscribe/emit/unsubscribe 테스트."""

from core.events import AppEvent, EventBus, get_event_bus


class TestEventBus:
    def test_subscribe_and_emit(self):
        bus = EventBus()
        results = []
        bus.subscribe(AppEvent.RECORDING_START, lambda: results.append("start"))
        bus.emit(AppEvent.RECORDING_START)
        assert results == ["start"]

    def test_emit_with_args(self):
        bus = EventBus()
        results = []
        bus.subscribe(AppEvent.FPS_CHANGED, lambda fps: results.append(fps))
        bus.emit(AppEvent.FPS_CHANGED, "30")
        assert results == ["30"]

    def test_unsubscribe(self):
        bus = EventBus()
        results = []
        cb = lambda: results.append("x")
        bus.subscribe(AppEvent.RECORDING_STOP, cb)
        bus.unsubscribe(AppEvent.RECORDING_STOP, cb)
        bus.emit(AppEvent.RECORDING_STOP)
        assert results == []

    def test_multiple_subscribers(self):
        bus = EventBus()
        results = []
        bus.subscribe(AppEvent.FORMAT_CHANGED, lambda f: results.append(f"a:{f}"))
        bus.subscribe(AppEvent.FORMAT_CHANGED, lambda f: results.append(f"b:{f}"))
        bus.emit(AppEvent.FORMAT_CHANGED, "MP4")
        assert results == ["a:MP4", "b:MP4"]

    def test_emit_unregistered_event_is_noop(self):
        bus = EventBus()
        bus.emit(AppEvent.ENCODING_COMPLETE)  # should not raise

    def test_callback_error_does_not_stop_others(self):
        bus = EventBus()
        results = []
        bus.subscribe(AppEvent.ENCODING_ERROR, lambda: (_ for _ in ()).throw(RuntimeError("test")))
        bus.subscribe(AppEvent.ENCODING_ERROR, lambda: results.append("ok"))
        bus.emit(AppEvent.ENCODING_ERROR)
        assert results == ["ok"]

    def test_clear(self):
        bus = EventBus()
        results = []
        bus.subscribe(AppEvent.RECORDING_START, lambda: results.append("x"))
        bus.clear()
        bus.emit(AppEvent.RECORDING_START)
        assert results == []

    def test_no_duplicate_subscribe(self):
        bus = EventBus()
        results = []
        cb = lambda: results.append("x")
        bus.subscribe(AppEvent.RECORDING_START, cb)
        bus.subscribe(AppEvent.RECORDING_START, cb)
        bus.emit(AppEvent.RECORDING_START)
        assert results == ["x"]  # only once


class TestGetEventBus:
    def test_singleton(self):
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2
