"""시그널 처리 (Ctrl+C -> graceful stop)"""
import os
import signal
import sys
from typing import Callable

_original_sigint = None


def install_signal_handlers(stop_callback: Callable[[], None]):
    """Ctrl+C 시그널 핸들러 등록

    첫 번째 Ctrl+C: stop_callback 호출 (graceful stop)
    두 번째 Ctrl+C: 강제 종료
    """
    global _original_sigint
    _original_sigint = signal.getsignal(signal.SIGINT)

    _press_count = [0]

    def handler(signum, frame):
        _press_count[0] += 1

        if _press_count[0] == 1:
            print("\n녹화 중지 중... (다시 Ctrl+C를 누르면 강제 종료)")
            try:
                stop_callback()
            except Exception as e:
                print(f"\n중지 콜백 오류: {e}", file=sys.stderr)
        else:
            print("\n강제 종료")
            os._exit(1)

    signal.signal(signal.SIGINT, handler)


def restore_signal_handlers():
    """원래 시그널 핸들러 복원"""
    global _original_sigint
    if _original_sigint is not None:
        signal.signal(signal.SIGINT, _original_sigint)
        _original_sigint = None
