"""
logging_setup.py - XGif Bootstrapper 로깅 설정
"""
import logging
import logging.handlers
import sys
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

_ui_callback: Optional[Callable[[str], None]] = None
_logger: Optional[logging.Logger] = None

class UIHandler(logging.Handler):
    """UI에 로그를 전달하는 커스텀 핸들러"""
    
    def emit(self, record):
        if _ui_callback:
            try:
                msg = self.format(record)
                _ui_callback(msg)
            except Exception:
                pass

def setup_logging(log_file: Path, level: int = logging.INFO) -> logging.Logger:
    """로깅 초기화"""
    global _logger
    
    if _logger is not None:
        return _logger
    
    # 로그 디렉토리 생성
    log_file.parent.mkdir(parents=True, exist_ok=True)
    
    # 포맷터
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    
    # 루트 로거 설정
    _logger = logging.getLogger("XGifBootstrapper")
    _logger.setLevel(level)
    _logger.handlers.clear()
    
    # 파일 핸들러 (RotatingFileHandler: 2MB × 2 백업)
    file_handler = logging.handlers.RotatingFileHandler(
        log_file, maxBytes=2 * 1024 * 1024, backupCount=2, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)
    _logger.addHandler(file_handler)
    
    # 콘솔 핸들러 (개발용)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)
    _logger.addHandler(console_handler)
    
    # UI 핸들러
    ui_handler = UIHandler()
    ui_handler.setFormatter(logging.Formatter("%(asctime)s %(message)s", "%H:%M:%S"))
    ui_handler.setLevel(level)
    _logger.addHandler(ui_handler)
    
    _logger.info("=" * 50)
    _logger.info(f"XGif Bootstrapper 시작 - {datetime.now()}")
    _logger.info("=" * 50)
    
    return _logger

def get_logger() -> logging.Logger:
    """로거 인스턴스 반환"""
    global _logger
    if _logger is None:
        from paths import get_log_file
        return setup_logging(get_log_file())
    return _logger

def set_ui_callback(callback: Callable[[str], None]):
    """UI 업데이트 콜백 등록"""
    global _ui_callback
    _ui_callback = callback

def log_and_ui(msg: str):
    """로그 기록 + UI 콜백 전달 (워커 스레드에서 안전하게 호출 가능)"""
    logger = get_logger()
    logger.info(msg)


def log_subprocess_output(line: str):
    """서브프로세스 출력 한 줄을 DEBUG 레벨로 기록"""
    line = line.rstrip()
    if line:
        logger = get_logger()
        logger.debug(line)


def read_recent_logs(log_file: Path, lines: int = 30) -> list[str]:
    """최근 로그 N줄 읽기"""
    if not log_file.exists():
        return []
    
    try:
        with open(log_file, "r", encoding="utf-8") as f:
            all_lines = f.readlines()
            return all_lines[-lines:] if len(all_lines) > lines else all_lines
    except Exception:
        return []
