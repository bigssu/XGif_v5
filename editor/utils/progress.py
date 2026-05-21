"""표준 ProgressDialog + background thread 헬퍼.

모든 장시간 동기 작업이 동일 패턴으로 진행률을 사용자에게 노출하도록 하는
전역 재활용 helper. 이 모듈이 없을 때는 작업이 UI 스레드를 블록하여 사용자에게
"정지 상태" 로 보이는 회귀가 빈번했다 (예: 700 → 350 프레임 reduce_frames 가
응답 없음).

사용 패턴:

    def my_work(progress, *args, **kwargs):
        for i in range(total):
            if progress is not None:
                progress(i + 1, total, f"단계 {i+1}/{total}")
            # ... heavy work ...
        return result

    result, cancelled = run_with_progress(
        parent=self,
        title="작업 진행 중...",
        work_func=my_work,
        work_args=(...),
        total_hint=total,
        can_abort=True,
    )
    if cancelled:
        return
    # use result

설계 결정:
- work_func 은 별도 thread 에서 실행되어 UI 가 멈추지 않는다.
- progress_callback 은 work thread 에서 호출되지만 내부적으로 wx.CallAfter 로
  메인 스레드에 dispatch — wx 객체 접근이 항상 메인 스레드에서 일어난다.
- 메인 스레드는 `wx.YieldIfNeeded` 로 ProgressDialog Update 와 페인트만 처리.
  ProgressDialog 가 modal 이라 다른 사용자 입력은 차단되어 재진입 위험 낮음.
- 사용자가 Cancel 누르면 progress_callback 이 InterruptedError 를 던져 work_func
  이 정상 종료 가능.
"""
from __future__ import annotations

import contextlib
import threading
import time
from typing import Any, Callable, Optional, Tuple

import wx


ProgressCallback = Callable[[int, int, str], None]
WorkFunc = Callable[..., Any]


def run_with_progress(
    parent: wx.Window,
    title: str,
    work_func: WorkFunc,
    *,
    work_args: tuple = (),
    work_kwargs: Optional[dict] = None,
    total_hint: int = 100,
    can_abort: bool = True,
    message: str = "",
    poll_interval_sec: float = 0.03,
) -> Tuple[Any, bool]:
    """work_func 을 background thread 에서 실행 + ProgressDialog 표시.

    Args:
        parent: ProgressDialog 의 부모 윈도우.
        title: 다이얼로그 제목.
        work_func: 실행할 함수. 첫 인자로 progress_callback 을 받아야 한다.
            시그니처: ``work_func(progress, *work_args, **work_kwargs)``.
            progress(current: int, total: int, message: str = "") 호출 가능.
            cancel 시 InterruptedError 를 던질 수 있다.
        work_args: work_func 의 위치 인자 (progress 이후).
        work_kwargs: work_func 의 키워드 인자.
        total_hint: 다이얼로그의 최대값 (진행률 0..total_hint). work_func 이
            progress(current, total, ...) 를 호출하면 current/total 비율로 정규화.
        can_abort: True 면 Cancel 버튼 표시 + InterruptedError 전파.
        message: 다이얼로그 초기 메시지 (work_func 이 progress 의 message 인자로
            덮어쓸 수 있음).
        poll_interval_sec: 메인 스레드 event pump 주기.

    Returns:
        (result, cancelled) 튜플. cancelled=True 면 result 는 None.

    Raises:
        work_func 이 던진 임의의 예외 (단 InterruptedError 는 cancelled 로 변환).
    """
    work_kwargs = work_kwargs or {}

    style = wx.PD_APP_MODAL | wx.PD_AUTO_HIDE | wx.PD_SMOOTH
    if can_abort:
        style |= wx.PD_CAN_ABORT

    dialog = wx.ProgressDialog(
        title,
        message or " ",
        maximum=max(1, total_hint),
        parent=parent,
        style=style,
    )

    state = {
        'result': None,
        'error': None,
        'cancelled': False,
        'done': False,
    }
    state_lock = threading.Lock()

    def _update_dialog(current: int, total: int, msg: str) -> None:
        """메인 스레드에서 다이얼로그 Update 호출."""
        try:
            normalized = int(current * total_hint / total) if total > 0 else 0
            normalized = max(0, min(total_hint, normalized))
            cont, _skip = dialog.Update(normalized, msg or " ")
            if not cont:
                with state_lock:
                    state['cancelled'] = True
        except Exception:
            pass

    def _progress_cb(current: int, total: int = total_hint, msg: str = "") -> None:
        """work thread 에서 호출되는 progress callback.
        Cancel 감지 시 InterruptedError 를 던져 work_func 을 정상 종료시킨다."""
        with state_lock:
            cancelled = state['cancelled']
        if cancelled:
            raise InterruptedError("progress cancelled by user")
        wx.CallAfter(_update_dialog, current, total, msg)

    def _target() -> None:
        try:
            with state_lock:
                pass  # 진입만 동기화
            result = work_func(_progress_cb, *work_args, **work_kwargs)
            with state_lock:
                state['result'] = result
        except InterruptedError:
            with state_lock:
                state['cancelled'] = True
        except Exception as e:
            with state_lock:
                state['error'] = e
        finally:
            with state_lock:
                state['done'] = True

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    # 메인 스레드 event pump — wx.YieldIfNeeded 로 ProgressDialog Update 와 paint 처리.
    # ProgressDialog 가 modal 이라 다른 사용자 입력은 차단됨.
    while True:
        with state_lock:
            done = state['done']
        if done:
            break
        with contextlib.suppress(Exception):
            wx.YieldIfNeeded()
        time.sleep(poll_interval_sec)

    # 남은 wx.CallAfter 큐 처리 (마지막 progress update 등)
    with contextlib.suppress(Exception):
        wx.YieldIfNeeded()

    with contextlib.suppress(Exception):
        dialog.Destroy()

    with state_lock:
        if state['error'] is not None:
            raise state['error']
        return state['result'], state['cancelled']
