"""
크래시 핸들러 및 안전 장치 모듈
예상치 못한 예외를 포착하고 로깅
"""

import sys
import traceback
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CrashHandler:
    """전역 예외 핸들러"""

    def __init__(self, log_dir: Optional[str] = None):
        """
        Args:
            log_dir: 로그 파일 저장 디렉토리 (None이면 %APPDATA%/XGif/logs)
        """
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            import os
            appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
            self.log_dir = Path(appdata) / 'XGif' / 'logs'

        # 로그 디렉토리 생성
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
        except (OSError, PermissionError) as e:
            logger.error(f"Cannot create log directory: {e}")
            # 폴백: 현재 디렉토리
            self.log_dir = Path.cwd() / 'logs'
            self.log_dir.mkdir(parents=True, exist_ok=True)

        self.crash_count = 0
        self.max_crashes = 10  # 최대 크래시 수 (무한 루프 방지)

    def handle_exception(self, exc_type, exc_value, exc_traceback):
        """전역 예외 핸들러
        
        Args:
            exc_type: 예외 타입
            exc_value: 예외 값
            exc_traceback: 트레이스백 객체
        """
        # KeyboardInterrupt는 정상 종료
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return

        self.crash_count += 1

        # 너무 많은 크래시 발생 시 중단
        if self.crash_count > self.max_crashes:
            logger.critical(f"Too many crashes ({self.crash_count}), terminating")
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            sys.exit(1)

        # 에러 로깅
        error_msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_traceback))
        logger.critical(f"Unhandled exception ({self.crash_count}):\n{error_msg}")

        # 크래시 리포트 저장
        self._save_crash_report(exc_type, exc_value, exc_traceback)

        # wxPython 애플리케이션 에러 다이얼로그 표시 (가능한 경우)
        try:
            import wx
            app = wx.App.Get()
            if app is not None:
                # 예외 메시지를 안전하게 표시 (Windows cp1252 등에서 UnicodeEncodeError 방지)
                try:
                    msg_safe = str(exc_value)
                except Exception:
                    msg_safe = repr(exc_value)
                wx.MessageBox(
                    "예상치 못한 오류가 발생했습니다.\n\n"
                    f"오류 타입: {exc_type.__name__}\n"
                    f"메시지: {msg_safe}\n\n"
                    f"크래시 리포트가 저장되었습니다:\n{self.log_dir}",
                    "프로그램 오류",
                    wx.OK | wx.ICON_ERROR
                )
        except Exception:
            pass  # 다이얼로그 표시 실패해도 계속 진행

    def _save_crash_report(self, exc_type, exc_value, exc_traceback):
        """크래시 리포트를 파일로 저장"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            report_file = self.log_dir / f"crash_{timestamp}.log"

            with open(report_file, 'w', encoding='utf-8') as f:
                f.write("=== XGif Crash Report ===\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write(f"Exception Type: {exc_type.__name__}\n")
                f.write(f"Exception Value: {str(exc_value)}\n")
                f.write("\n=== Traceback ===\n")
                f.write(''.join(traceback.format_exception(exc_type, exc_value, exc_traceback)))
                f.write("\n=== System Info ===\n")
                f.write(f"Python: {sys.version}\n")
                f.write(f"Platform: {sys.platform}\n")

            logger.info(f"Crash report saved: {report_file}")

        except (IOError, OSError) as e:
            logger.error(f"Cannot save crash report: {e}")


def install_crash_handler():
    """전역 크래시 핸들러 설치"""
    handler = CrashHandler()
    sys.excepthook = handler.handle_exception
    logger.info("Crash handler installed")
    return handler


# ═══════════════════════════════════════════════════════════════
# 안전 장치 데코레이터
# ═══════════════════════════════════════════════════════════════

def safe_execute(default_return=None, log_error=True):
    """함수 실행을 안전하게 감싸는 데코레이터
    
    Args:
        default_return: 에러 발생 시 반환할 기본값
        log_error: 에러를 로깅할지 여부
    
    사용 예:
        @safe_execute(default_return=False)
        def risky_function():
            # ... 위험한 코드 ...
            return True
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                if log_error:
                    logger.error(f"Error in {func.__name__}: {e}")
                    logger.debug(f"Traceback: {traceback.format_exc()}")
                return default_return
        return wrapper
    return decorator


def retry_on_failure(max_retries=3, delay=0.1, exceptions=(Exception,)):
    """실패 시 재시도하는 데코레이터
    
    Args:
        max_retries: 최대 재시도 횟수
        delay: 재시도 간 지연 시간 (초)
        exceptions: 재시도할 예외 타입들
    
    사용 예:
        @retry_on_failure(max_retries=3, delay=0.5)
        def unstable_function():
            # ... 가끔 실패하는 코드 ...
    """
    def decorator(func):
        def wrapper(*args, **kwargs):
            import time

            last_exception = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {e}")
                        time.sleep(delay)
                    else:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")

            # 모든 재시도 실패
            if last_exception:
                raise last_exception
        return wrapper
    return decorator
