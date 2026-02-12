"""
Logger - 로깅 유틸리티
파일 로깅 및 로그 로테이션 지원
"""
import io
import logging
import logging.handlers
import os
import sys
from pathlib import Path
from typing import Optional
from datetime import datetime


def _ensure_utf8_streams():
    """stdout/stderr가 UTF-8로 출력되도록 래핑 (에디터 단독 실행 시 UnicodeEncodeError 방지)"""
    for name, stream in [("stdout", sys.stdout), ("stderr", sys.stderr)]:
        if stream is None:
            continue
        buf = getattr(stream, "buffer", None)
        enc = getattr(stream, "encoding", None) or ""
        if buf is not None and enc.lower() != "utf-8":
            try:
                wrapper = io.TextIOWrapper(buf, encoding="utf-8", errors="replace")
                setattr(sys, name, wrapper)
            except Exception:
                pass


class Logger:
    """애플리케이션 로거"""
    
    _instance: Optional['Logger'] = None
    _logger: Optional[logging.Logger] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._setup()
        return cls._instance
    
    def _setup(self):
        """로거 설정"""
        _ensure_utf8_streams()
        self._logger = logging.getLogger('GifEditor')
        self._logger.setLevel(logging.DEBUG)
        
        # 기존 핸들러 제거 (중복 방지)
        self._logger.handlers.clear()
        
        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        self._logger.addHandler(console_handler)
        
        # 파일 핸들러 (로그 로테이션)
        try:
            log_dir = Path(os.environ.get('APPDATA', str(Path.home()))) / "XGif" / "editor_logs"
            log_dir.mkdir(parents=True, exist_ok=True)
            log_file = log_dir / f"editor_{datetime.now().strftime('%Y%m%d')}.log"
            
            file_handler = logging.handlers.RotatingFileHandler(
                str(log_file),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=5,  # 최대 5개 백업 파일 유지
                encoding='utf-8'
            )
            file_handler.setLevel(logging.DEBUG)
            file_format = logging.Formatter(
                '%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_format)
            self._logger.addHandler(file_handler)
            self._logger.info(f"파일 로깅 시작: {log_file}")
        except Exception as e:
            # 파일 로깅 실패 시 콘솔에만 로깅
            self._logger.warning(f"파일 로깅 초기화 실패: {e}")
    
    def set_file_output(self, path: str):
        """파일 출력 설정"""
        file_handler = logging.FileHandler(path, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        file_handler.setFormatter(file_format)
        self._logger.addHandler(file_handler)
    
    def debug(self, message: str):
        self._logger.debug(message)
    
    def info(self, message: str):
        self._logger.info(message)
    
    def warning(self, message: str):
        self._logger.warning(message)
    
    def error(self, message: str):
        self._logger.error(message)
    
    def exception(self, message: str):
        self._logger.exception(message)


def get_logger() -> Logger:
    """로거 인스턴스 반환"""
    return Logger()
