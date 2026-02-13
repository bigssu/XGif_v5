"""FFmpeg 프로세스 관리 공통 유틸리티."""

import logging
import os
import subprocess
import threading
from typing import Callable, List, Optional

logger = logging.getLogger(__name__)


def find_ffmpeg() -> Optional[str]:
    """FFmpeg 실행 파일 경로 탐색.

    1. core.ffmpeg_installer.FFmpegManager 경로
    2. PATH에서 탐색
    3. 없으면 None
    """
    try:
        from core.ffmpeg_installer import FFmpegManager
        path = FFmpegManager.get_ffmpeg_path()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass

    # PATH에서 탐색
    import shutil
    path = shutil.which("ffmpeg")
    if path:
        return path

    return None


def run_ffmpeg(
    args: List[str],
    progress_callback: Optional[Callable[[str], None]] = None,
    timeout: int = 600,
) -> subprocess.CompletedProcess:
    """FFmpeg 프로세스를 실행하고 stderr를 실시간 모니터링.

    Args:
        args: FFmpeg 인자 리스트 (ffmpeg 경로 포함)
        progress_callback: stderr 라인마다 호출되는 콜백
        timeout: 타임아웃(초)

    Returns:
        CompletedProcess
    """
    creation_flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=creation_flags,
    )

    stderr_lines: List[str] = []

    def _read_stderr():
        for raw_line in process.stderr:
            line = raw_line.decode("utf-8", errors="replace").strip()
            if line:
                stderr_lines.append(line)
                if progress_callback:
                    try:
                        progress_callback(line)
                    except Exception:
                        pass

    reader = threading.Thread(target=_read_stderr, daemon=True)
    reader.start()

    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        process.kill()
        raise
    finally:
        reader.join(timeout=5)

    return subprocess.CompletedProcess(
        args=args,
        returncode=process.returncode,
        stdout=process.stdout.read() if process.stdout else b"",
        stderr="\n".join(stderr_lines),
    )


def kill_process_safe(process: Optional[subprocess.Popen]) -> None:
    """서브프로세스를 안전하게 종료."""
    if process is None:
        return
    try:
        process.kill()
    except (OSError, ProcessLookupError):
        pass
    try:
        process.wait(timeout=5)
    except (subprocess.TimeoutExpired, OSError):
        pass
