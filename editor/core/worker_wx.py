"""
Worker - Threading 기반 비동기 작업 처리 (wxPython 호환)
백그라운드에서 이미지 효과 적용, 파일 저장 등을 처리하여 UI 응답성 향상
"""
from __future__ import annotations
from typing import Callable, Optional, List, Dict
import wx
from PIL import Image
import traceback
import time
import threading
from concurrent.futures import ThreadPoolExecutor, Future


class WorkerSignals:
    """워커 시그널 정의 (콜백 기반)

    wxPython에서는 wx.CallAfter를 사용하여 메인 스레드에서 콜백 실행
    """
    def __init__(self):
        self.started_callbacks: List[Callable] = []
        self.finished_callbacks: List[Callable] = []
        self.error_callbacks: List[Callable] = []
        self.progress_callbacks: List[Callable] = []
        self.progress_message_callbacks: List[Callable] = []
        self.cancelled_callbacks: List[Callable] = []

    def connect(self, event_name: str, callback: Callable):
        """콜백 연결"""
        if event_name == 'started':
            self.started_callbacks.append(callback)
        elif event_name == 'finished':
            self.finished_callbacks.append(callback)
        elif event_name == 'error':
            self.error_callbacks.append(callback)
        elif event_name == 'progress':
            self.progress_callbacks.append(callback)
        elif event_name == 'progress_message':
            self.progress_message_callbacks.append(callback)
        elif event_name == 'cancelled':
            self.cancelled_callbacks.append(callback)

    def emit_started(self):
        """시작 이벤트 발생"""
        for callback in self.started_callbacks:
            wx.CallAfter(callback)

    def emit_finished(self, result):
        """완료 이벤트 발생"""
        for callback in self.finished_callbacks:
            wx.CallAfter(callback, result)

    def emit_error(self, msg: str, tb: str):
        """에러 이벤트 발생"""
        for callback in self.error_callbacks:
            wx.CallAfter(callback, msg, tb)

    def emit_progress(self, current: int, total: int):
        """진행률 이벤트 발생"""
        for callback in self.progress_callbacks:
            wx.CallAfter(callback, current, total)

    def emit_progress_message(self, msg: str):
        """진행 메시지 이벤트 발생"""
        for callback in self.progress_message_callbacks:
            wx.CallAfter(callback, msg)

    def emit_cancelled(self):
        """취소 이벤트 발생"""
        for callback in self.cancelled_callbacks:
            wx.CallAfter(callback)


class BaseWorker:
    """기본 워커 클래스

    모든 백그라운드 작업의 기본 클래스입니다.
    스레드 안전한 취소 메커니즘을 제공합니다.
    """

    def __init__(self):
        self.signals = WorkerSignals()
        self._cancel_event = threading.Event()  # 스레드 안전한 취소 이벤트
        self._future: Optional[Future] = None

    def cancel(self):
        """작업 취소 요청 (스레드 안전)"""
        self._cancel_event.set()
        if self._future:
            self._future.cancel()

    @property
    def is_cancelled(self) -> bool:
        """취소 여부 확인 (스레드 안전)"""
        return self._cancel_event.is_set()

    def run(self):
        """작업 실행 (서브클래스에서 오버라이드)"""
        raise NotImplementedError("서브클래스에서 run() 메서드를 구현하세요.")


class FunctionWorker(BaseWorker):
    """함수 실행 워커

    임의의 함수를 백그라운드에서 실행합니다.
    """

    def __init__(self, func: Callable, *args, **kwargs):
        super().__init__()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.signals.emit_started()

        try:
            result = self.func(*self.args, **self.kwargs)

            if self.is_cancelled:
                self.signals.emit_cancelled()
            else:
                self.signals.emit_finished(result)

        except Exception as e:
            self.signals.emit_error(str(e), traceback.format_exc())


class BatchEffectWorker(BaseWorker):
    """배치 효과 적용 워커

    여러 프레임에 효과를 순차적으로 적용합니다.
    """

    def __init__(self, images: List[Image.Image], effect_func: Callable[[Image.Image], Image.Image]):
        super().__init__()
        self.images = images
        self.effect_func = effect_func

    def run(self):
        self.signals.emit_started()
        total = len(self.images)

        try:
            for i in range(total):
                if self.is_cancelled:
                    self.signals.emit_cancelled()
                    return

                # 효과 적용 후 원본을 교체하여 메모리 누적 방지
                old_img = self.images[i]
                self.images[i] = self.effect_func(old_img)
                if old_img is not self.images[i]:
                    del old_img

                # 진행률 업데이트
                self.signals.emit_progress(i + 1, total)

            self.signals.emit_finished(self.images)

        except Exception as e:
            self.signals.emit_error(str(e), traceback.format_exc())


class FrameEffectWorker(BaseWorker):
    """프레임 효과 적용 워커"""

    def __init__(self, frames: list, effect_func: Callable, **kwargs):
        super().__init__()
        self.frames = frames
        self.effect_func = effect_func
        self.kwargs = kwargs

    def run(self):
        self.signals.emit_started()
        total = len(self.frames)
        processed = 0

        try:
            for i, frame in enumerate(self.frames):
                if self.is_cancelled:
                    self.signals.emit_cancelled()
                    return

                # 효과 적용
                self.effect_func(frame, **self.kwargs)
                processed += 1

                # 진행률 업데이트
                self.signals.emit_progress(processed, total)

            self.signals.emit_finished(processed)

        except Exception as e:
            self.signals.emit_error(str(e), traceback.format_exc())


class SaveWorker(BaseWorker):
    """파일 저장 워커"""

    def __init__(self, save_func: Callable, file_path: str, *args, **kwargs):
        super().__init__()
        self.save_func = save_func
        self.file_path = file_path
        self.args = args
        self.kwargs = kwargs

    def run(self):
        self.signals.emit_started()
        self.signals.emit_progress_message(f"저장 중: {self.file_path}")

        try:
            result = self.save_func(self.file_path, *self.args, **self.kwargs)

            if self.is_cancelled:
                self.signals.emit_cancelled()
            else:
                self.signals.emit_finished(result)

        except Exception as e:
            self.signals.emit_error(str(e), traceback.format_exc())


class VideoLoadWorker(BaseWorker):
    """비디오 로드 워커"""

    def __init__(self, load_func: Callable, file_path: str, **kwargs):
        super().__init__()
        self.load_func = load_func
        self.file_path = file_path
        self.kwargs = kwargs

    def _progress_callback(self, current: int, total: int):
        """내부 진행률 콜백"""
        if self.is_cancelled:
            raise InterruptedError("작업이 취소되었습니다")
        self.signals.emit_progress(current, total)

    def run(self):
        self.signals.emit_started()
        self.signals.emit_progress_message(f"비디오 로드 중: {self.file_path}")

        try:
            # 진행률 콜백 주입
            self.kwargs['progress_callback'] = self._progress_callback
            result = self.load_func(self.file_path, **self.kwargs)

            if self.is_cancelled:
                self.signals.emit_cancelled()
            else:
                self.signals.emit_finished(result)

        except InterruptedError:
            self.signals.emit_cancelled()
        except Exception as e:
            self.signals.emit_error(str(e), traceback.format_exc())


class WorkerManager:
    """워커 관리자 (ThreadPoolExecutor 기반)"""

    def __init__(self, max_threads: Optional[int] = None, timeout_seconds: int = 300):
        """
        Args:
            max_threads: 최대 스레드 수
            timeout_seconds: 워커 타임아웃 시간 (초)
        """
        self._max_workers = max_threads or 4
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
        self._active_workers: List[BaseWorker] = []
        self._worker_timeouts: Dict[BaseWorker, float] = {}
        self._workers_lock = threading.Lock()
        self._timeout_seconds = timeout_seconds

        # 타임아웃 체크 타이머 (wx.App 존재 시에만 생성)
        self._timer_handler = None
        self._timeout_timer = None
        if wx.App.Get() is not None:
            self._timer_handler = wx.EvtHandler()
            self._timeout_timer = wx.Timer(self._timer_handler)
            self._timer_handler.Bind(wx.EVT_TIMER, lambda e: self._cleanup_timeout_workers(), self._timeout_timer)
            self._timeout_timer.Start(30000)

    @property
    def thread_count(self) -> int:
        """사용 가능한 스레드 수"""
        return self._executor._max_workers

    @property
    def active_thread_count(self) -> int:
        """현재 활성 스레드 수"""
        with self._workers_lock:
            return len(self._active_workers)

    def start(self, worker: BaseWorker, priority: int = 0) -> None:
        """워커 시작"""
        current_time = time.time()
        timeout_time = current_time + self._timeout_seconds

        with self._workers_lock:
            self._active_workers.append(worker)
            self._worker_timeouts[worker] = timeout_time

        # 완료 시 목록에서 제거
        def cleanup_worker():
            with self._workers_lock:
                if worker in self._active_workers:
                    self._active_workers.remove(worker)
                self._worker_timeouts.pop(worker, None)

        def on_finished(result):
            cleanup_worker()

        def on_error(msg, tb):
            cleanup_worker()

        def on_cancelled():
            cleanup_worker()

        worker.signals.connect('finished', on_finished)
        worker.signals.connect('error', on_error)
        worker.signals.connect('cancelled', on_cancelled)

        # ThreadPoolExecutor로 실행
        worker._future = self._executor.submit(worker.run)

    def cancel_all(self) -> None:
        """모든 활성 워커 취소"""
        with self._workers_lock:
            for worker in self._active_workers:
                worker.cancel()

    def wait_for_done(self, timeout_ms: int = -1) -> bool:
        """모든 작업 완료 대기"""
        try:
            with self._workers_lock:
                self._executor.shutdown(wait=True, cancel_futures=False)
                self._executor = ThreadPoolExecutor(max_workers=self._max_workers)
            return True
        except Exception:
            return False

    def clear(self) -> None:
        """대기 중인 모든 작업 제거"""
        with self._workers_lock:
            for worker in self._active_workers:
                worker.cancel()
            self._active_workers.clear()
            self._worker_timeouts.clear()

    def _cleanup_timeout_workers(self) -> None:
        """타임아웃된 워커 정리"""
        current_time = time.time()
        timed_out_workers = []

        with self._workers_lock:
            for worker, timeout_time in list(self._worker_timeouts.items()):
                if current_time > timeout_time:
                    timed_out_workers.append(worker)

            for worker in timed_out_workers:
                try:
                    worker.cancel()
                    if worker in self._active_workers:
                        self._active_workers.remove(worker)
                    self._worker_timeouts.pop(worker, None)
                except Exception:
                    self._active_workers = [w for w in self._active_workers if w != worker]
                    self._worker_timeouts.pop(worker, None)

    def shutdown(self) -> None:
        """워커 매니저 종료 (타이머 정리 + executor 종료)"""
        if self._timeout_timer is not None:
            try:
                self._timeout_timer.Stop()
            except Exception:
                pass
        self.cancel_all()
        try:
            self._executor.shutdown(wait=False, cancel_futures=True)
        except Exception:
            pass


# 전역 워커 매니저 인스턴스
_global_manager: Optional[WorkerManager] = None


def get_worker_manager() -> WorkerManager:
    """전역 워커 매니저 반환"""
    global _global_manager
    if _global_manager is None:
        _global_manager = WorkerManager()
    return _global_manager


def shutdown_worker_manager() -> None:
    """전역 워커 매니저 종료 (앱 종료 시 호출)"""
    global _global_manager
    if _global_manager is not None:
        _global_manager.shutdown()
        _global_manager = None


def run_in_background(func: Callable, *args,
                      on_finished: Optional[Callable] = None,
                      on_error: Optional[Callable] = None,
                      on_progress: Optional[Callable] = None,
                      **kwargs) -> FunctionWorker:
    """함수를 백그라운드에서 실행하는 유틸리티 함수"""
    worker = FunctionWorker(func, *args, **kwargs)

    if on_finished:
        worker.signals.connect('finished', on_finished)
    if on_error:
        worker.signals.connect('error', on_error)
    if on_progress:
        worker.signals.connect('progress', on_progress)

    get_worker_manager().start(worker)
    return worker
