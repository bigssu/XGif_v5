"""
FFmpeg 자동 다운로드 및 설치 모듈
사용자 데이터 폴더에 FFmpeg 바이너리를 자동으로 다운로드하여 설치
"""

import http.client
import os
import sys
import subprocess
import locale
import zipfile
import urllib.request
import shutil
import tempfile
import logging
from pathlib import Path
import threading
import contextlib

logger = logging.getLogger(__name__)


# FFmpeg 다운로드 URL (BtbN의 자동 빌드 - 안정적이고 최신)
FFMPEG_DOWNLOAD_URL = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"

# 대체 URL (gyan.dev - 더 작은 빌드)
FFMPEG_DOWNLOAD_URL_ALT = "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip"


def get_ffmpeg_install_dir() -> Path:
    """Persistent user-writable destination, including for packaged apps."""
    return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "XGif" / "ffmpeg"


def _has_ffmpeg_pair(directory: Path) -> bool:
    return all((directory / name).is_file() for name in ("ffmpeg.exe", "ffprobe.exe"))


def get_ffmpeg_dir() -> Path:
    """Prefer complete installations while retaining legacy binary discovery."""
    candidates = [get_ffmpeg_install_dir()]
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            candidates.append(Path(sys._MEIPASS) / "ffmpeg")
        candidates.append(Path(sys.executable).parent / "ffmpeg")
    else:
        candidates.append(Path(__file__).resolve().parents[1] / "ffmpeg")
    for directory in candidates:
        if _has_ffmpeg_pair(directory):
            return directory
    return next((d for d in candidates if (d / "ffmpeg.exe").is_file()), candidates[0])


def get_ffmpeg_path() -> str:
    """FFmpeg 실행 파일 경로 반환"""
    ffmpeg_dir = get_ffmpeg_dir()
    ffmpeg_exe = ffmpeg_dir / 'ffmpeg.exe'
    return str(ffmpeg_exe)


def is_ffmpeg_installed() -> bool:
    """로컬 FFmpeg 설치 여부 확인"""
    return _has_ffmpeg_pair(get_ffmpeg_dir())


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
                capture_output=True,
                text=True,
                encoding=locale.getpreferredencoding(False),
                errors='replace',
                timeout=5,
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
        self.finished = threading.Event()

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
        finally:
            self.finished.set()

    def _download_and_install(self):
        """FFmpeg 다운로드 및 설치"""
        ffmpeg_dir = get_ffmpeg_install_dir()
        ffmpeg_dir.mkdir(parents=True, exist_ok=True)

        message = "FFmpeg 다운로드 실패"
        with tempfile.TemporaryDirectory(prefix="xgif_ffmpeg_") as temp_dir:
            zip_path = os.path.join(temp_dir, "ffmpeg.zip")
            for url in (FFMPEG_DOWNLOAD_URL, FFMPEG_DOWNLOAD_URL_ALT):
                if self._cancelled:
                    break
                self._safe_callback(self._status_callback, "FFmpeg 다운로드 중..." if url == FFMPEG_DOWNLOAD_URL
                                    else "대체 서버에서 다운로드 시도 중...")
                if not self._download_file(url, zip_path):
                    continue
                if self._cancelled:
                    break
                self._safe_callback(self._status_callback, "파일 무결성 검증 중...")
                if not self._verify_zip_integrity(zip_path):
                    message = "FFmpeg 다운로드 파일 검증 실패"
                    continue
                try:
                    self._extract_ffmpeg(zip_path, ffmpeg_dir)
                except (ValueError, zipfile.BadZipFile) as exc:
                    logger.warning("Unusable FFmpeg package from %s: %s", url, exc)
                    message = f"FFmpeg 파일 검증 실패: {exc}"
                    continue
                except OSError:
                    if self._cancelled:
                        break
                    raise
                self._safe_callback(self._finished_callback, True, "FFmpeg 설치 완료")
                return
        self._safe_callback(self._finished_callback, False, "다운로드 취소됨" if self._cancelled else message)

    def _download_file(self, url: str, dest_path: str) -> bool:
        """파일 다운로드 (진행률 표시, 전체 타임아웃 300초)"""
        temp_path = None
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

                with tempfile.NamedTemporaryFile(mode='wb', dir=os.path.dirname(os.path.abspath(dest_path)),
                                                 prefix='.download-', suffix='.part', delete=False) as f:
                    temp_path = f.name
                    while True:
                        if self._cancelled:
                            return False

                        # 전체 다운로드 타임아웃 체크
                        now = _dl_time.monotonic()
                        if now - download_start > max_download_seconds:
                            logger.error("다운로드 전체 타임아웃 초과 (300초)")
                            return False

                        chunk = response.read(chunk_size)
                        now = _dl_time.monotonic()
                        if now - download_start > max_download_seconds:
                            logger.error("다운로드 전체 타임아웃 초과 (300초)")
                            return False
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

            if self._cancelled:
                return False
            if total_size > 0 and downloaded != total_size:
                raise OSError(f"Download size mismatch: expected {total_size}, received {downloaded}")
            os.replace(temp_path, dest_path)
            return True

        except (OSError, http.client.HTTPException, ValueError) as e:
            logger.error(f"다운로드 에러: {e}")
            return False
        finally:
            if temp_path is not None:
                with contextlib.suppress(OSError):
                    os.remove(temp_path)

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

                for executable in ('ffmpeg.exe', 'ffprobe.exe'):
                    if not any(n.endswith('bin/' + executable) for n in zf.namelist()):
                        logger.warning("%s not found in ZIP", executable)
                        return False

            return True
        except (zipfile.BadZipFile, OSError) as e:
            logger.warning("FFmpeg ZIP integrity check failed: %s", e)
            return False

    @staticmethod
    def _check_staged_tool(path: Path):
        try:
            result = subprocess.run(
                [str(path), "-version"], capture_output=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise ValueError(f"{path.name} 실행 실패: {exc}") from exc
        if result.returncode or not result.stdout.lower().startswith(f"{path.stem} version ".encode()):
            raise ValueError(f"{path.name} 버전 확인 실패")

    def _extract_ffmpeg(self, zip_path: str, dest_dir: Path):
        """Stage both tools before replacing them, restoring backups on failure."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        staging = Path(tempfile.mkdtemp(prefix='.ffmpeg-', dir=dest_dir))
        backup = staging / 'backup'
        backup.mkdir()
        promoted = []
        preserve_backup = False
        try:
            with zipfile.ZipFile(zip_path, 'r') as zf:
                targets = {}
                for executable in ('ffmpeg.exe', 'ffprobe.exe'):
                    entries = [info for info in zf.infolist() if info.filename.endswith('bin/' + executable)]
                    if len(entries) != 1 or entries[0].file_size <= 0:
                        raise ValueError(f"ZIP must contain one nonempty {executable}")
                    targets[executable] = entries[0]

                total_bytes = sum(info.file_size for info in targets.values())
                extracted_bytes = 0
                for executable, info in targets.items():
                    self._safe_callback(self._status_callback, f"압축 해제 중... {executable}")
                    with zf.open(info) as src, (staging / executable).open('wb') as dst:
                        while True:
                            if self._cancelled:
                                raise OSError("설치 취소됨")
                            chunk = src.read(1024 * 1024)
                            if not chunk:
                                break
                            dst.write(chunk)
                            extracted_bytes += len(chunk)
                            self._safe_callback(self._progress_callback, extracted_bytes, total_bytes)
                    if (staging / executable).stat().st_size != info.file_size:
                        raise OSError(f"Extracted size mismatch: {executable}")

            for executable in targets:
                if self._cancelled:
                    raise OSError("설치 취소됨")
                self._check_staged_tool(staging / executable)
            for executable in targets:
                existing = dest_dir / executable
                if existing.exists():
                    shutil.copy2(existing, backup / executable)
            if self._cancelled:
                raise OSError("설치 취소됨")
            try:
                for executable in targets:
                    os.replace(staging / executable, dest_dir / executable)
                    promoted.append(executable)
            except OSError:
                for executable in reversed(promoted):
                    try:
                        if (backup / executable).exists():
                            os.replace(backup / executable, dest_dir / executable)
                        else:
                            (dest_dir / executable).unlink()
                    except OSError:
                        preserve_backup = True
                        logger.exception("Rollback failed; backup retained at %s", backup)
                raise
        finally:
            if not preserve_backup:
                shutil.rmtree(staging, ignore_errors=True)


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
    def get_ffmpeg_tools() -> tuple[str | None, str | None]:
        ffmpeg = FFmpegManager.get_ffmpeg_executable()
        if ffmpeg:
            sibling = Path(ffmpeg).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
            probe = str(sibling) if sibling.is_file() else shutil.which('ffprobe')
            if probe:
                return ffmpeg, probe
            directory = get_ffmpeg_dir()
            if _has_ffmpeg_pair(directory):
                return str(directory / 'ffmpeg.exe'), str(directory / 'ffprobe.exe')
        return ffmpeg, None

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
        return FFmpegManager.get_ffmpeg_tools()[1] is None
