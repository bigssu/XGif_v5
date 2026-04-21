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
    import subprocess as _sp

    # 1. shutil.which (표준)
    ffmpeg_path = shutil.which('ffmpeg')
    if ffmpeg_path:
        return ffmpeg_path

    # 2. where.exe 폴백 (Windows — App Execution Aliases 등 shutil.which가 못 찾는 경로 탐색)
    if os.name == 'nt':
        try:
            result = _sp.run(
                ['where', 'ffmpeg'],
                capture_output=True, text=True, timeout=5,
                creationflags=_sp.CREATE_NO_WINDOW,
            )
            if result.returncode == 0 and result.stdout.strip():
                found = result.stdout.strip().splitlines()[0]
                if os.path.isfile(found):
                    return found
        except Exception:
            pass

    return None


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

            # 다운로드 파일 무결성 검증
            self._safe_callback(self._status_callback, "파일 무결성 검증 중...")
            if not self._verify_zip_integrity(zip_path):
                self._safe_callback(self._finished_callback, False,
                                    "다운로드 파일이 손상되었습니다. 다시 시도하세요.")
                return

            self._safe_callback(self._status_callback, "압축 해제 중...")

            # ZIP 압축 해제 및 ffmpeg.exe 추출
            self._extract_ffmpeg(zip_path, ffmpeg_dir)

            # 설치 확인
            if is_ffmpeg_installed():
                logger.info("FFmpeg 설치 완료: %s", get_ffmpeg_path())
                self._safe_callback(self._finished_callback, True, "FFmpeg 설치 완료")
            else:
                logger.error("FFmpeg 설치 실패: ffmpeg.exe not found at %s", get_ffmpeg_path())
                self._safe_callback(self._finished_callback, False, "FFmpeg 설치 실패: 파일을 찾을 수 없음")

        finally:
            # 임시 파일 정리
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                pass

    def _download_file(self, url: str, dest_path: str) -> bool:
        """파일 다운로드 (진행률 표시, 전체 타임아웃 300초)"""
        try:
            import time as _dl_time
            # URL 열기
            req = urllib.request.Request(url, headers={'User-Agent': 'XGif/1.0'})
            download_start = _dl_time.monotonic()
            max_download_seconds = 300  # 전체 다운로드 타임아웃 5분

            with urllib.request.urlopen(req, timeout=30) as response:
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                chunk_size = 1024 * 1024  # 1MB
                last_progress_time = download_start

                with open(dest_path, 'wb') as f:
                    while True:
                        if self._cancelled:
                            return False

                        # 전체 다운로드 타임아웃 체크
                        now = _dl_time.monotonic()
                        if now - download_start > max_download_seconds:
                            logger.error("다운로드 전체 타임아웃 초과 (300초)")
                            return False

                        chunk = response.read(chunk_size)
                        if not chunk:
                            break

                        # 청크 수신 간 스톨 감지 (60초간 진행 없으면 중단)
                        if now - last_progress_time > 60:
                            logger.error("다운로드 스톨 감지 (60초간 진행 없음)")
                            return False
                        last_progress_time = now

                        f.write(chunk)
                        downloaded += len(chunk)

                        if total_size > 0 and self._progress_callback:
                            self._safe_callback(self._progress_callback, downloaded, total_size)

            return True

        except (urllib.error.URLError, IOError, OSError) as e:
            logger.error(f"다운로드 에러: {e}")
            return False

    @staticmethod
    def _verify_zip_integrity(zip_path: str) -> bool:
        """다운로드된 ZIP 파일 무결성 검증 (CRC + 최소 크기)"""
        try:
            # 최소 크기 검증 (FFmpeg zip은 최소 30MB 이상)
            file_size = os.path.getsize(zip_path)
            if file_size < 30 * 1024 * 1024:
                logger.warning("FFmpeg ZIP too small: %d bytes", file_size)
                return False

            # ZIP 내부 CRC 검증
            with zipfile.ZipFile(zip_path, 'r') as zf:
                bad = zf.testzip()
                if bad is not None:
                    logger.warning("Corrupt entry in FFmpeg ZIP: %s", bad)
                    return False

                # ffmpeg.exe가 포함되어 있는지 확인
                has_ffmpeg = any(n.endswith('bin/ffmpeg.exe') for n in zf.namelist())
                if not has_ffmpeg:
                    logger.warning("ffmpeg.exe not found in ZIP")
                    return False

            return True
        except (zipfile.BadZipFile, OSError) as e:
            logger.warning("FFmpeg ZIP integrity check failed: %s", e)
            return False

    def _extract_ffmpeg(self, zip_path: str, dest_dir: Path):
        """ZIP에서 ffmpeg.exe/ffprobe.exe 추출 (진행률 콜백 포함)"""
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # 추출 대상 찾기
            targets = {}  # name_in_zip -> dest_filename
            for name in zf.namelist():
                if name.endswith('bin/ffmpeg.exe'):
                    targets[name] = 'ffmpeg.exe'
                elif name.endswith('bin/ffprobe.exe'):
                    targets[name] = 'ffprobe.exe'

            if not any(v == 'ffmpeg.exe' for v in targets.values()):
                raise Exception("ZIP 파일에서 ffmpeg.exe를 찾을 수 없음")

            # 총 크기 계산 (진행률용)
            total_bytes = sum(zf.getinfo(n).file_size for n in targets)
            extracted_bytes = 0

            for name_in_zip, dest_name in targets.items():
                entry_size = zf.getinfo(name_in_zip).file_size
                dest_path = dest_dir / dest_name
                self._safe_callback(
                    self._status_callback,
                    f"압축 해제 중... {dest_name}"
                )

                with zf.open(name_in_zip) as src, open(dest_path, 'wb') as dst:
                    chunk_size = 1024 * 1024  # 1MB
                    while True:
                        chunk = src.read(chunk_size)
                        if not chunk:
                            break
                        dst.write(chunk)
                        extracted_bytes += len(chunk)
                        if total_bytes > 0 and self._progress_callback:
                            self._safe_callback(
                                self._progress_callback,
                                extracted_bytes, total_bytes,
                            )

                logger.info("추출 완료: %s (%d bytes)", dest_name, entry_size)


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
