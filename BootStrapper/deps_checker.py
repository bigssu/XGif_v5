"""
deps_checker.py – Sequential dependency checking logic.

Every check function:
    - Returns (bool_pass, detail_str)
    - Must NOT block the UI (called from worker thread)
    - Must have a timeout for subprocess calls
"""

import os
import re
import subprocess
import paths
from cupy_env import CUPY_DEVICE_PROBE
from logging_setup import log_and_ui, get_logger

SUBPROCESS_TIMEOUT = 30  # seconds

# NVIDIA 드라이버 체크 결과 캐시 (check_cupy에서 중복 호출 방지)
_nvidia_cache: tuple[bool, str] | None = None


def _run(cmd: list[str], timeout: int = SUBPROCESS_TIMEOUT, cwd=None):
    """Run a subprocess, return (returncode, stdout, stderr)."""
    logger = get_logger()
    logger.debug("Running: %s", " ".join(cmd))
    try:
        env = os.environ.copy()
        # Ensure our ffmpeg/bin is findable if needed by subprocesses
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            errors="replace",
            timeout=timeout,
            cwd=cwd,
            env=env,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return -1, "", "File not found"
    except subprocess.TimeoutExpired:
        return -2, "", "Timeout"
    except OSError as e:
        return -3, "", str(e)


# ──────────────────────────────────────────────────────────────────
#  NVIDIA Driver
# ──────────────────────────────────────────────────────────────────
def check_nvidia_driver() -> tuple[bool, str]:
    global _nvidia_cache
    log_and_ui("NVIDIA 드라이버 확인 중…")
    rc, out, err = _run(["nvidia-smi"])
    if rc == 0:
        # Extract driver version
        m = re.search(r"Driver Version:\s*([\d.]+)", out)
        ver = m.group(1) if m else "unknown"
        log_and_ui(f"NVIDIA 드라이버 감지: {ver}")
        _nvidia_cache = (True, f"v{ver}")
        return _nvidia_cache
    else:
        log_and_ui("GPU 드라이버가 없거나 CUDA 사용이 불가능할 수 있습니다.")
        _nvidia_cache = (False, "nvidia-smi 실행 불가")
        return _nvidia_cache


# ──────────────────────────────────────────────────────────────────
#  Embedded Python 3.11
# ──────────────────────────────────────────────────────────────────
def check_python311() -> tuple[bool, str]:
    log_and_ui("Python 3.11 확인 중…")
    if not os.path.isfile(paths.PY311_EXE):
        return False, "python.exe 없음"
    rc, out, err = _run([paths.PY311_EXE, "--version"])
    if rc == 0:
        ver = out.strip() or err.strip()
        m = re.search(r"Python\s+3\.11", ver)
        if m:
            log_and_ui(f"Python 확인: {ver}")
            return True, ver.replace("Python ", "")
        return False, f"버전 불일치: {ver}"
    return False, "실행 실패"


# ──────────────────────────────────────────────────────────────────
#  pip
# ──────────────────────────────────────────────────────────────────
def check_pip() -> tuple[bool, str]:
    log_and_ui("pip 확인 중…")
    if not os.path.isfile(paths.PY311_EXE):
        return False, "Python 먼저 설치 필요"
    rc, out, err = _run([paths.PY311_EXE, "-m", "pip", "--version"])
    if rc == 0:
        ver = out.strip().split()[1] if out.strip() else "ok"
        log_and_ui(f"pip 확인: v{ver}")
        return True, f"v{ver}"
    return False, "pip 없음"


# ──────────────────────────────────────────────────────────────────
#  venv
# ──────────────────────────────────────────────────────────────────
def check_venv() -> tuple[bool, str]:
    log_and_ui("가상 환경 확인 중…")
    env_dir = paths.get_venv_dir()
    if not paths.is_compatible_venv(env_dir):
        return False, f"Python 3.11 64비트 가상 환경 필요: {env_dir}"
    python = str(env_dir / "Scripts" / "python.exe")
    rc, out, _ = _run([python, "-I", "-m", "pip", "--version"])
    if rc == 0:
        return True, out.strip()
    return False, "venv pip 없음"


# ──────────────────────────────────────────────────────────────────
#  CuPy
# ──────────────────────────────────────────────────────────────────
def check_cupy() -> tuple[bool, str]:
    log_and_ui("CuPy 확인 중…")

    # 1. GPU 드라이버 확인 (캐시된 결과 사용)
    if _nvidia_cache is not None:
        has_gpu, gpu_detail = _nvidia_cache
    else:
        has_gpu, gpu_detail = check_nvidia_driver()
    if not has_gpu:
        log_and_ui("NVIDIA GPU가 감지되지 않아 CuPy를 건너뜁니다.")
        return True, "GPU 미사용 (Skip)"

    env_dir = paths.get_venv_dir()
    if not paths.is_compatible_venv(env_dir):
        return False, f"Python 3.11 64비트 가상 환경 필요: {env_dir}"

    rc, out, err = _run([
        str(env_dir / "Scripts" / "python.exe"), "-I", "-c",
        CUPY_DEVICE_PROBE,
    ], timeout=60)
    if rc == 0 and out.strip().isdigit():
        count = int(out.strip())
        if count > 0:
            log_and_ui(f"CuPy 정상 – GPU 장치 수: {count}")
            return True, f"GPU {count}개"
        return False, "사용 가능한 CUDA 장치가 없습니다."

    detail = (err.strip() or out.strip() or "import 실패").splitlines()[-1]
    log_and_ui(f"CuPy 검증 실패: {detail}")
    return False, detail[:160]


# ──────────────────────────────────────────────────────────────────
#  FFmpeg
# ──────────────────────────────────────────────────────────────────
def check_ffmpeg(directory=None) -> tuple[bool, str]:
    log_and_ui("FFmpeg 확인 중…")
    if directory is None:
        directory = paths.FFMPEG_DIR
        legacy = paths.get_target_dir() / "ffmpeg"
        names = ("ffmpeg.exe", "ffprobe.exe")
        current_complete = all(os.path.isfile(os.path.join(directory, name)) for name in names)
        if not current_complete and all((legacy / name).is_file() for name in names):
            directory = legacy
    details = []
    for name in ("ffmpeg", "ffprobe"):
        executable = os.path.join(directory, f"{name}.exe")
        if not os.path.isfile(executable):
            return False, f"{name}.exe 없음"
        rc, out, _ = _run([executable, "-version"])
        if rc != 0:
            return False, f"{name}.exe 실행 실패"
        match = re.search(rf"{name} version\s+(\S+)", out)
        details.append(f"{name} {match.group(1) if match else 'ok'}")
    return True, ", ".join(details)
