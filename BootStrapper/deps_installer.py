"""
deps_installer.py – Sequential install logic.

Each install function:
    - Returns bool (success)
    - Streams output via logging_setup.log_subprocess_output
    - Must NOT block the UI (called from worker thread)
"""

import glob
import os
import shutil
import subprocess
import sys
import threading

import paths
import deps_specs
from download_utils import download_file
from extract_utils import extract_zip
from logging_setup import log_and_ui, log_subprocess_output, get_logger

SUBPROCESS_TIMEOUT_LONG = 600  # 10 min for big pip installs


def _stream_run(cmd: list[str], timeout: int = SUBPROCESS_TIMEOUT_LONG, cwd=None) -> int:
    """
    Run a subprocess, streaming stdout/stderr line-by-line to the log.
    Returns the exit code.
    """
    logger = get_logger()
    logger.debug("Streaming: %s", " ".join(cmd))
    proc = None
    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=cwd,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )

        def _reader():
            try:
                for line in proc.stdout:
                    log_subprocess_output(line)
            except (OSError, ValueError):
                pass  # stdout closed or process terminated

        t = threading.Thread(target=_reader, daemon=True)
        t.start()
        proc.wait(timeout=timeout)
        t.join(timeout=10)
        return proc.returncode
    except subprocess.TimeoutExpired:
        if proc:
            proc.kill()
            proc.wait(timeout=5)
        log_and_ui("프로세스 시간 초과로 종료")
        return -2
    except OSError as e:
        log_and_ui(f"프로세스 실행 실패: {e}")
        return -3
    finally:
        if proc and proc.stdout:
            try:
                proc.stdout.close()
            except OSError:
                pass


# ──────────────────────────────────────────────────────────────────
#  Python 3.11 embedded
# ──────────────────────────────────────────────────────────────────
def install_python311(progress_cb=None) -> bool:
    log_and_ui("Python 3.11 다운로드 중…")
    zip_dest = os.path.join(paths.TEMP_DIR, "python311_embed.zip")

    ok = download_file(deps_specs.PYTHON_EMBED_URL, zip_dest, progress_cb=progress_cb)
    if not ok:
        return False

    log_and_ui("Python 3.11 압축 해제 중…")
    ok = extract_zip(
        zip_dest,
        paths.PY311_DIR,
        expected_file="python.exe",
        flatten_single_root=False,
        progress_cb=progress_cb,
    )
    if not ok:
        return False

    # ── CRITICAL: Enable pip in embedded Python ───────────────────
    # The embeddable Python ships with python311._pth that blocks
    # site-packages and pip. We must modify it to allow "import site".
    pth_files = glob.glob(os.path.join(paths.PY311_DIR, "python*._pth"))
    for pth in pth_files:
        log_and_ui(f"._pth 파일 수정: {os.path.basename(pth)}")
        
        with open(pth, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        new_lines = []
        found_import_site = False
        
        for line in lines:
            stripped = line.strip()
            # Uncomment if commented
            if stripped.startswith("#"):
                 if stripped.lstrip("#").strip() == "import site":
                     new_lines.append("import site\n")
                     found_import_site = True
                     continue
            
            # Keep existing if already uncommented
            if stripped == "import site":
                found_import_site = True
                new_lines.append(line)
                continue
                
            new_lines.append(line)
        
        # If not found, append it
        if not found_import_site:
            if new_lines and not new_lines[-1].endswith("\n"):
                new_lines.append("\n")
            new_lines.append("import site\n")
            
        with open(pth, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

    # Cleanup
    try:
        os.remove(zip_dest)
    except OSError:
        pass

    log_and_ui("Python 3.11 설치 완료")
    return True


# ──────────────────────────────────────────────────────────────────
#  pip (via get-pip.py)
# ──────────────────────────────────────────────────────────────────
def install_pip(progress_cb=None) -> bool:
    log_and_ui("pip 설치 중…")
    get_pip = os.path.join(paths.TEMP_DIR, "get-pip.py")

    ok = download_file(deps_specs.GET_PIP_URL, get_pip, progress_cb=progress_cb)
    if not ok:
        return False

    rc = _stream_run([paths.PY311_EXE, get_pip])
    if rc != 0:
        log_and_ui("get-pip.py 실행 실패")
        return False

    # Cleanup
    try:
        os.remove(get_pip)
    except OSError:
        pass

    log_and_ui("pip 설치 완료")
    return True


# ──────────────────────────────────────────────────────────────────
#  venv
# ──────────────────────────────────────────────────────────────────
def _is_venv_healthy() -> bool:
    """venv가 존재하고 python/pip가 정상 작동하는지 확인"""
    if not os.path.isfile(paths.VENV_PYTHON):
        return False
    try:
        result = subprocess.run(
            [paths.VENV_PYTHON, "-m", "pip", "--version"],
            capture_output=True, text=True, timeout=15,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return result.returncode == 0
    except Exception:
        return False


def install_venv(progress_cb=None, force: bool = False) -> bool:
    log_and_ui("가상 환경 확인 중…")

    # 기존 venv가 정상이면 pip 업그레이드만 수행 (CuPy 등 기존 패키지 보존)
    if not force and _is_venv_healthy():
        log_and_ui("기존 가상 환경이 정상입니다 — pip만 업그레이드합니다.")
        rc = _stream_run([
            paths.VENV_PYTHON, "-m", "pip", "install",
            "--upgrade", "pip>=24.0", "--quiet",
        ])
        if rc != 0:
            log_and_ui("pip 업그레이드 실패 (계속 진행)")
        log_and_ui("가상 환경 확인 완료")
        return True

    log_and_ui("가상 환경 생성 중…")

    # Use the embedded Python's pip to install virtualenv,
    # then create the venv. (Embedded Python does not ship with venv module.)
    # Step 1: install virtualenv into the embedded python
    rc = _stream_run([paths.PY311_EXE, "-m", "pip", "install", "virtualenv", "--quiet"])
    if rc != 0:
        log_and_ui("virtualenv 설치 실패")
        return False

    # Step 2: create venv (기존 venv가 있으면 삭제)
    if os.path.exists(paths.VENV_DIR):
        log_and_ui("손상된 기존 venv를 삭제합니다…")
        shutil.rmtree(paths.VENV_DIR, ignore_errors=True)

    rc = _stream_run([paths.PY311_EXE, "-m", "virtualenv", paths.VENV_DIR])
    if rc != 0:
        log_and_ui("가상 환경 생성 실패")
        return False

    # Step 3: upgrade pip inside venv to 24.x
    log_and_ui("venv 내 pip 업그레이드 중…")
    rc = _stream_run([
        paths.VENV_PYTHON, "-m", "pip", "install",
        "--upgrade", "pip>=24.0", "--quiet",
    ])
    if rc != 0:
        log_and_ui("pip 업그레이드 실패 (계속 진행)")

    log_and_ui("가상 환경 생성 완료")
    return True


# ──────────────────────────────────────────────────────────────────
#  CuPy
# ──────────────────────────────────────────────────────────────────
def install_cupy(progress_cb=None) -> bool:
    log_and_ui("CuPy 설치 중… (시간이 다소 소요됩니다)")
    log_and_ui("인터넷 연결이 필요합니다.")

    rc = _stream_run(
        [
            paths.VENV_PYTHON, "-m", "pip", "install",
            "cupy-cuda12x",
            "--no-cache-dir",
        ],
        timeout=SUBPROCESS_TIMEOUT_LONG,
    )
    if rc != 0:
        log_and_ui("CuPy 설치 실패")
        return False

    log_and_ui("CuPy 패키지 설치 완료 – 검증은 재검사에서 수행됩니다.")
    return True


# ──────────────────────────────────────────────────────────────────
#  FFmpeg
# ──────────────────────────────────────────────────────────────────
def install_ffmpeg(progress_cb=None) -> bool:
    log_and_ui("FFmpeg 다운로드 중…")
    log_and_ui("인터넷 연결이 필요합니다.")

    zip_dest = os.path.join(paths.TEMP_DIR, "ffmpeg.zip")

    ok = download_file(deps_specs.FFMPEG_ZIP_URL, zip_dest, progress_cb=progress_cb)
    if not ok:
        # fallback URL 시도
        fallback_url = getattr(deps_specs, "FFMPEG_ZIP_URL_FALLBACK", None)
        if fallback_url:
            log_and_ui("대체 서버에서 FFmpeg 다운로드 시도 중…")
            ok = download_file(fallback_url, zip_dest, progress_cb=progress_cb)
        if not ok:
            return False

    log_and_ui("FFmpeg 압축 해제 중… (파일이 많아 시간이 걸릴 수 있습니다)")

    ok = extract_zip(
        zip_dest,
        paths.FFMPEG_DIR,
        expected_file=os.path.join("bin", "ffmpeg.exe"),
        flatten_single_root=True,
        progress_cb=progress_cb,
    )

    # XGif 앱은 {ffmpeg_dir}/ffmpeg.exe 를 기대하므로 bin/ 내용을 상위로 이동
    bin_dir = os.path.join(paths.FFMPEG_DIR, "bin")
    if os.path.isdir(bin_dir):
        for fname in os.listdir(bin_dir):
            src = os.path.join(bin_dir, fname)
            dst = os.path.join(paths.FFMPEG_DIR, fname)
            if os.path.isfile(src):
                shutil.move(src, dst)
        shutil.rmtree(bin_dir, ignore_errors=True)
        log_and_ui("FFmpeg bin → ffmpeg 폴더로 플래튼 완료")
        ok = os.path.isfile(paths.FFMPEG_EXE)

    if not ok:
        # Fallback: ffmpeg.exe를 재귀 탐색
        for root, dirs, files in os.walk(paths.FFMPEG_DIR):
            if "ffmpeg.exe" in files:
                src = os.path.join(root, "ffmpeg.exe")
                dst = os.path.join(paths.FFMPEG_DIR, "ffmpeg.exe")
                if src != dst:
                    shutil.move(src, dst)
                    log_and_ui("FFmpeg 재배치 완료")
                ok = True
                break
    if not ok:
        return False

    # Cleanup zip
    try:
        os.remove(zip_dest)
    except OSError:
        pass

    log_and_ui("FFmpeg 설치 완료")
    return True
