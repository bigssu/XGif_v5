"""
FFmpeg 자동 다운로드 및 설치 모듈
프로그램 폴더에 FFmpeg 바이너리를 자동으로 다운로드하여 설치
"""

import os
import sys
import zipfile
import urllib.request
import shutil
import tempfile
import logging
from pathlib import Path
import threading

logger = logging.getLogger(__name__)


# FFmpeg 다운로드 URL (BtbN의 자동 빌드 - 안정적이고 최신)
FFMPEG_DOWNLOAD_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

# 대체 URL (gyan.dev - 더 작은 빌드)
FFMPEG_DOWNLOAD_URL_ALT = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def get_ffmpeg_dir() -> Path:
    """FFmpeg 설치 디렉토리 반환"""
    # 프로그램 폴더 내 ffmpeg 디렉토리
    if getattr(sys, 'frozen', False):
        # PyInstaller로 패키징된 경우
        # --onefile 모드: sys._MEIPASS에 임시 디렉토리 경로가 있음
        if hasattr(sys, '_MEIPASS'):
            # 임시 디렉토리에서 ffmpeg 폴더 찾기
            meipass_dir = Path(sys._MEIPASS)
            bundled_ffmpeg = meipass_dir / 'ffmpeg'
            if bundled_ffmpeg.exists():
                return bundled_ffmpeg
        
        # --onedir 모드 또는 실행 파일과 같은 위치
        base_dir = Path(sys.executable).parent
        bundled_ffmpeg = base_dir / 'ffmpeg'
        if bundled_ffmpeg.exists():
            return bundled_ffmpeg
        
        # 기본값: 실행 파일과 같은 위치
        return base_dir / 'ffmpeg'
    else:
        # 일반 Python 실행
        base_dir = Path(__file__).parent.parent
        return base_dir / 'ffmpeg'


def get_ffmpeg_path() -> str:
    """FFmpeg 실행 파일 경로 반환"""
    ffmpeg_dir = get_ffmpeg_dir()
    ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
    return str(ffmpeg_exe)


def is_ffmpeg_installed() -> bool:
    """로컬 FFmpeg 설치 여부 확인"""
    ffmpeg_path = get_ffmpeg_path()
    return os.path.exists(ffmpeg_path)


def check_system_ffmpeg() -> str:
    """시스템 PATH에서 FFmpeg 찾기"""
    ffmpeg_path = shutil.which('ffmpeg')
    return ffmpeg_path


class FFmpegDownloader(threading.Thread):
    """FFmpeg 다운로드 스레드"""
    
    def __init__(self, progress_callback=None, status_callback=None, finished_callback=None):
        """
        Args:
            progress_callback: (downloaded, total) -> None
            status_callback: (message) -> None
            finished_callback: (success, message) -> None
        """
        threading.Thread.__init__(self, daemon=True)
        self._progress_callback = progress_callback
        self._status_callback = status_callback
        self._finished_callback = finished_callback
        self._cancelled = False
    
    def cancel(self):
        """다운로드 취소"""
        self._cancelled = True
    
    def _safe_callback(self, callback, *args):
        """콜백을 메인 스레드에서 안전하게 실행 (GUI: wx.CallAfter, CLI: 직접 호출)"""
        if callback:
            try:
                import wx
                if wx.App.Get() is not None:
                    wx.CallAfter(callback, *args)
                else:
                    callback(*args)
            except (ImportError, RuntimeError):
                callback(*args)

    def run(self):
        """다운로드 및 설치 실행"""
        try:
            self._download_and_install()
        except Exception as e:
            self._safe_callback(self._finished_callback, False, f"설치 실패: {str(e)}")
    
    def _download_and_install(self):
        """FFmpeg 다운로드 및 설치"""
        ffmpeg_dir = get_ffmpeg_dir()
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)

        # 임시 파일로 다운로드
        temp_dir = tempfile.mkdtemp(prefix='giffy_ffmpeg_')
        zip_path = os.path.join(temp_dir, 'ffmpeg.zip')

        try:
            self._safe_callback(self._status_callback, "FFmpeg 다운로드 중...")

            # 다운로드 (진행률 콜백 포함)
            success = self._download_file(FFMPEG_DOWNLOAD_URL, zip_path)

            if not success:
                # 대체 URL 시도
                self._safe_callback(self._status_callback, "대체 서버에서 다운로드 시도 중...")
                success = self._download_file(FFMPEG_DOWNLOAD_URL_ALT, zip_path)

            if not success or self._cancelled:
                self._safe_callback(self._finished_callback, False, "다운로드 취소됨")
                return

            self._safe_callback(self._status_callback, "압축 해제 중...")

            # ZIP 압축 해제 및 ffmpeg.exe 추출
            self._extract_ffmpeg(zip_path, ffmpeg_dir)

            # 설치 확인
            if is_ffmpeg_installed():
                self._safe_callback(self._finished_callback, True, "FFmpeg 설치 완료")
            else:
                self._safe_callback(self._finished_callback, False, "FFmpeg 설치 실패: 파일을 찾을 수 없음")

        finally:
            # 임시 파일 정리
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass
    
    def _download_file(self, url: str, dest_path: str) -> bool:
        """파일 다운로드 (진행률 표시)"""
        try:
            # URL 열기
            req = urllib.request.Request(url, headers={'User-Agent': 'GifRecoder2/1.0'})
            
            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB
                
                with open(dest_path, 'wb') as f:
                    while True:
                        if self._cancelled:
                            return False
                        
                        chunk = response.read(chunk_size)
                        if not chunk:
                            break
                        
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if total_size > 0 and self._progress_callback:
                            self._safe_callback(self._progress_callback, downloaded, total_size)
            
            return True
            
        except (urllib.error.URLError, IOError, OSError) as e:
            logger.error(f"다운로드 에러: {e}")
            return False
    
    def _extract_ffmpeg(self, zip_path: str, dest_dir: Path):
        """ZIP에서 ffmpeg.exe 추출"""
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # ffmpeg.exe 파일 찾기
            ffmpeg_files = [f for f in zf.namelist() if f.endswith('bin/ffmpeg.exe')]
            
            if not ffmpeg_files:
                raise Exception("ZIP 파일에서 ffmpeg.exe를 찾을 수 없음")
            
            ffmpeg_in_zip = ffmpeg_files[0]
            
            # 추출
            with zf.open(ffmpeg_in_zip) as src:
                dest_path = dest_dir / 'ffmpeg.exe'
                with open(dest_path, 'wb') as dst:
                    shutil.copyfileobj(src, dst)
            
            # ffprobe.exe도 추출 (있으면)
            ffprobe_files = [f for f in zf.namelist() if f.endswith('bin/ffprobe.exe')]
            if ffprobe_files:
                with zf.open(ffprobe_files[0]) as src:
                    dest_path = dest_dir / 'ffprobe.exe'
                    with open(dest_path, 'wb') as dst:
                        shutil.copyfileobj(src, dst)


class FFmpegManager:
    """FFmpeg 관리 클래스"""
    
    @staticmethod
    def get_ffmpeg_executable() -> str:
        """사용 가능한 FFmpeg 경로 반환 (시스템 PATH 우선, 없으면 포함된 ffmpeg 사용)"""
        # 1. 시스템 PATH에서 먼저 확인 (사용자가 설치한 ffmpeg 우선 사용)
        system_path = check_system_ffmpeg()
        if system_path and os.path.exists(system_path):
            return system_path
        
        # 2. 포함된 ffmpeg 확인 (빌드 시 포함된 바이너리)
        bundled_path = get_ffmpeg_path()
        if bundled_path and os.path.exists(bundled_path):
            return bundled_path
        
        return None
    
    @staticmethod
    def get_ffmpeg_env() -> dict:
        """FFmpeg 실행을 위한 환경 변수 딕셔너리 반환
        
        포함된 ffmpeg를 사용하는 경우, 해당 디렉토리를 PATH에 추가합니다.
        시스템 ffmpeg를 사용하는 경우, 기존 환경 변수를 그대로 사용합니다.
        
        Returns:
            dict: 환경 변수 딕셔너리 (subprocess 실행 시 env 파라미터로 사용)
        """
        env = os.environ.copy()
        
        # 시스템 PATH에 ffmpeg가 있는지 확인
        system_path = check_system_ffmpeg()
        if system_path and os.path.exists(system_path):
            # 시스템 ffmpeg 사용 중이면 환경 변수 변경 불필요
            return env
        
        # 포함된 ffmpeg 사용 중인 경우
        bundled_path = get_ffmpeg_path()
        if bundled_path and os.path.exists(bundled_path):
            # ffmpeg 디렉토리를 PATH에 추가
            ffmpeg_dir = Path(bundled_path).parent
            ffmpeg_dir_str = str(ffmpeg_dir)
            
            # PATH에 이미 포함되어 있지 않으면 추가
            current_path = env.get('PATH', '')
            if ffmpeg_dir_str not in current_path:
                # Windows와 Unix 모두 지원
                path_separator = os.pathsep
                env['PATH'] = ffmpeg_dir_str + path_separator + current_path
        
        return env
    
    @staticmethod
    def is_available() -> bool:
        """FFmpeg 사용 가능 여부"""
        return FFmpegManager.get_ffmpeg_executable() is not None
    
    @staticmethod
    def needs_installation() -> bool:
        """설치가 필요한지 확인"""
        return not FFmpegManager.is_available()
