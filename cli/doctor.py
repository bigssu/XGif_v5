"""환경 진단 (xgif doctor)"""
import os
import sys
import subprocess
import logging

from cli import EXIT_SUCCESS, EXIT_DEPENDENCY

logger = logging.getLogger(__name__)


def run_doctor(args) -> int:
    """환경 진단 실행. 반환값: 종료 코드."""
    verbose = getattr(args, "verbose", False)

    print("\n  XGif 환경 진단")
    print("  " + "─" * 40)

    # ── Python ──
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    _check("Python", py_ver, True)

    # ── wxPython ──
    try:
        import wx
        _check("wxPython", wx.__version__, True)
    except ImportError:
        _check("wxPython", "미설치 (GUI 모드 불가, CLI는 사용 가능)", False)

    # ── FFmpeg ──
    from core.ffmpeg_installer import FFmpegManager
    ffmpeg_path = FFmpegManager.get_ffmpeg_executable()
    if ffmpeg_path:
        _check("FFmpeg", ffmpeg_path, True)
        if verbose:
            _show_ffmpeg_version(ffmpeg_path)
    else:
        _check("FFmpeg", "미설치", False)
        if getattr(args, "install_ffmpeg", False):
            return _install_ffmpeg()

    # ── Pillow ──
    try:
        from PIL import Image
        import PIL
        _check("Pillow", PIL.__version__, True)
    except ImportError:
        _check("Pillow", "미설치", False)

    # ── NumPy ──
    try:
        import numpy as np
        _check("NumPy", np.__version__, True)
    except ImportError:
        _check("NumPy", "미설치", False)

    # ── 캡처 백엔드 ──
    print()
    print("  캡처 백엔드:")
    _check("GDI", "Windows 기본", True)

    try:
        import dxcam
        _check("dxcam", "설치됨", True)
    except ImportError:
        _check("dxcam", "미설치 -- 'xgif doctor --install-dxcam' 으로 설치", False)
        if getattr(args, "install_dxcam", False):
            return _install_dxcam()

    # ── GPU ──
    print()
    print("  GPU:")
    gpu_detected = False
    has_cupy = False
    try:
        from core.gpu_utils import detect_gpu, is_cupy_available
        gpu = detect_gpu()
        if gpu.gpu_name:
            gpu_detected = True
            mem_str = f" ({gpu.gpu_memory_mb}MB)" if gpu.gpu_memory_mb else ""
            _check("GPU", f"{gpu.gpu_name}{mem_str}", True)
            if gpu.driver_version:
                _check("드라이버", gpu.driver_version, True)
        else:
            _check("GPU", "NVIDIA GPU 감지 실패", False)
    except Exception as e:
        _check("GPU", f"감지 실패: {e}", False)

    # ── CuPy (GPU 가속 라이브러리) ──
    if gpu_detected:
        print()
        print("  GPU 가속:")
        try:
            import cupy as cp
            has_cupy = True
            cupy_ver = cp.__version__
            # CUDA 런타임 버전 확인
            try:
                cuda_ver_int = cp.cuda.runtime.runtimeGetVersion()
                cuda_major = cuda_ver_int // 1000
                cuda_minor = (cuda_ver_int % 1000) // 10
                cuda_ver = f"{cuda_major}.{cuda_minor}"
                _check("CuPy", f"{cupy_ver} (CUDA {cuda_ver})", True)
            except Exception:
                _check("CuPy", cupy_ver, True)

            # GPU 메모리 테스트
            try:
                test_arr = cp.zeros((100, 100), dtype=cp.float32)
                del test_arr
                _check("CUDA 연산", "정상 동작", True)
            except Exception as e:
                _check("CUDA 연산", f"실패: {e}", False)

        except ImportError:
            _check("CuPy", "미설치 -- GPU 가속 비활성", False)
            _suggest_cupy_install()
            if getattr(args, "install_cupy", False):
                return _install_cupy()

    # ── 인코더 감지 (실제 인코딩 테스트 기반) ──
    if ffmpeg_path:
        print()
        print("  인코더:")
        from core.gif_encoder import GifEncoder
        enc = GifEncoder()
        available = enc.detect_available_encoders()

        # NVENC 상태를 실제 인코더 테스트 결과로 판단
        has_nvenc_h264 = "h264_nvenc" in available.get("h264", [])
        has_nvenc_h265 = "hevc_nvenc" in available.get("h265", [])

        for codec_type in ("h264", "h265"):
            encoders = available.get(codec_type, [])
            best = available.get(f"best_{codec_type}", "")
            for encoder_name in encoders:
                label = enc.get_encoder_display_name(encoder_name)
                is_best = " (기본)" if encoder_name == best else ""
                _check(f"{codec_type.upper()} {label}", f"{encoder_name}{is_best}", True)

        # GPU가 있지만 NVENC가 안 되는 경우 안내
        if gpu_detected and not has_nvenc_h264 and not has_nvenc_h265:
            print()
            _check(
                "NVENC",
                "GPU 감지됨, 그러나 NVENC 인코딩 테스트 실패",
                False,
            )
            print("          원인: FFmpeg 빌드에 NVENC 지원이 포함되지 않았을 수 있습니다.")
            print("          해결: NVENC 지원 FFmpeg를 설치하세요:")
            print("                winget install Gyan.FFmpeg")

    # ── 디스플레이 ──
    print()
    print("  디스플레이:")
    try:
        import ctypes
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)
        h = user32.GetSystemMetrics(1)

        try:
            dpi = ctypes.windll.user32.GetDpiForSystem()
            scale = int(dpi / 96 * 100)
        except (AttributeError, OSError):
            scale = 100

        _check("해상도", f"{w}x{h} @ {scale}% DPI (SYSTEM_AWARE)", True)
    except Exception as e:
        _check("디스플레이", f"확인 실패: {e}", False)

    # ── HDR ──
    try:
        from core.hdr_utils import is_hdr_active
        hdr = is_hdr_active()
        _check("HDR", "활성" if hdr else "비활성", True)
    except Exception:
        _check("HDR", "확인 불가", False)

    # ── 오디오 ──
    print()
    print("  오디오:")
    try:
        import sounddevice
        _check("sounddevice", "설치됨 (마이크 녹음 가능)", True)
    except ImportError:
        _check("sounddevice", "미설치 (마이크 녹음 불가)", False)

    print()
    print("  " + "─" * 40)

    # ── 종합 권장사항 ──
    recommendations = []
    if gpu_detected and not has_cupy:
        recommendations.append(
            "GPU 가속을 활성화하려면: xgif doctor --install-cupy"
        )
    if not ffmpeg_path:
        recommendations.append(
            "FFmpeg를 설치하려면: xgif doctor --install-ffmpeg"
        )

    if recommendations:
        print()
        print("  권장사항:")
        for rec in recommendations:
            print(f"    → {rec}")
        print()

    print()
    return EXIT_SUCCESS


def _check(label: str, value: str, ok: bool):
    """진단 결과 한 줄 출력"""
    marker = "[OK]" if ok else "[--]"
    print(f"  {marker:>6}  {label}: {value}")


def _suggest_cupy_install():
    """cupy 설치 방법 안내"""
    print("          GPU 가속을 위해 CuPy를 설치하세요:")
    print("          → xgif doctor --install-cupy  (자동 감지 및 설치)")
    print("          또는 수동 설치:")
    print("          → pip install cupy-cuda12x     (CUDA 12.x)")
    print("          → pip install cupy-cuda11x     (CUDA 11.x)")


def _detect_cuda_version() -> str:
    """시스템의 CUDA 버전 감지 (nvidia-smi 또는 nvcc 사용)"""
    # 1. nvidia-smi로 CUDA 버전 확인
    try:
        result = subprocess.run(
            ["nvidia-smi"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            # "CUDA Version: 12.4" 패턴 찾기
            import re
            match = re.search(r"CUDA Version:\s*([\d.]+)", result.stdout)
            if match:
                return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # 2. nvcc로 확인
    try:
        result = subprocess.run(
            ["nvcc", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        if result.returncode == 0:
            import re
            match = re.search(r"release ([\d.]+)", result.stdout)
            if match:
                return match.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    return ""


def _show_ffmpeg_version(ffmpeg_path: str):
    """FFmpeg 버전 표시"""
    try:
        result = subprocess.run(
            [ffmpeg_path, "-version"],
            capture_output=True,
            text=True,
            timeout=5,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
        )
        first_line = result.stdout.split("\n")[0] if result.stdout else ""
        if first_line:
            print(f"          {first_line}")
    except Exception:
        pass


def _install_ffmpeg() -> int:
    """FFmpeg 자동 설치"""
    print("\n  FFmpeg 설치를 시작합니다...")
    from core.ffmpeg_installer import FFmpegDownloader

    done = {"success": None, "message": ""}

    def on_status(msg):
        print(f"  {msg}")

    def on_progress(downloaded, total):
        if total > 0:
            pct = int(downloaded / total * 100)
            mb = downloaded / (1024 * 1024)
            total_mb = total / (1024 * 1024)
            sys.stdout.write(f"\r  다운로드: {mb:.1f}/{total_mb:.1f} MB ({pct}%)  ")
            sys.stdout.flush()

    def on_finished(success, message):
        done["success"] = success
        done["message"] = message

    downloader = FFmpegDownloader(
        progress_callback=on_progress,
        status_callback=on_status,
        finished_callback=on_finished,
    )
    downloader.start()
    downloader.join(timeout=300)

    print()
    if done["success"]:
        print(f"  FFmpeg 설치 완료: {done['message']}")
        return EXIT_SUCCESS
    else:
        print(f"  FFmpeg 설치 실패: {done['message']}", file=sys.stderr)
        return EXIT_DEPENDENCY


def _install_dxcam() -> int:
    """dxcam pip 설치"""
    if getattr(sys, 'frozen', False):
        print("  패키징된 환경에서는 pip install을 실행할 수 없습니다.", file=sys.stderr)
        return EXIT_DEPENDENCY
    print("\n  dxcam 설치를 시작합니다...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "dxcam"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            print("  dxcam 설치 완료")
            return EXIT_SUCCESS
        else:
            print(f"  dxcam 설치 실패: {result.stderr}", file=sys.stderr)
            return EXIT_DEPENDENCY
    except Exception as e:
        print(f"  dxcam 설치 실패: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY


def _install_cupy() -> int:
    """CuPy 자동 설치 (CUDA 버전 자동 감지)"""
    if getattr(sys, 'frozen', False):
        print("  패키징된 환경에서는 pip install을 실행할 수 없습니다.", file=sys.stderr)
        return EXIT_DEPENDENCY
    print("\n  CuPy 설치를 시작합니다...")

    # CUDA 버전 감지
    cuda_ver = _detect_cuda_version()
    if cuda_ver:
        print(f"  감지된 CUDA 버전: {cuda_ver}")
        major = int(cuda_ver.split(".")[0])
        if major >= 12:
            cupy_pkg = "cupy-cuda12x"
        elif major == 11:
            cupy_pkg = "cupy-cuda11x"
        else:
            print(f"  경고: CUDA {cuda_ver}은 지원되지 않습니다. CUDA 11+ 필요.", file=sys.stderr)
            return EXIT_DEPENDENCY
    else:
        # CUDA 버전 감지 실패 — 최신(12.x) 시도
        print("  CUDA 버전 자동 감지 실패. cupy-cuda12x 설치를 시도합니다...")
        cupy_pkg = "cupy-cuda12x"

    print(f"  패키지: {cupy_pkg}")
    print(f"  설치 중... (수 분이 소요될 수 있습니다)")

    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", cupy_pkg],
            timeout=600,  # 10분
        )
        if result.returncode == 0:
            # 설치 검증 (ASCII만 사용하여 인코딩 문제 방지)
            print()
            try:
                env = os.environ.copy()
                env["PYTHONIOENCODING"] = "utf-8"
                verify = subprocess.run(
                    [sys.executable, "-c",
                     "import cupy; v=cupy.__version__; print('CuPy_OK:' + v)"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                    env=env,
                )
                if verify.returncode == 0 and "CuPy_OK:" in verify.stdout:
                    ver = verify.stdout.strip().split("CuPy_OK:")[1]
                    print(f"  CuPy {ver} 설치 완료")
                    print("  GPU 가속이 활성화되었습니다!")
                    print("  (변경사항을 적용하려면 앱을 재시작하세요)")
                    return EXIT_SUCCESS
                else:
                    # pip 성공했지만 import 실패 — CUDA 경로 문제일 수 있음
                    stderr_msg = verify.stderr[:300] if verify.stderr else ""
                    if "CUDA path" in stderr_msg or "cudart" in stderr_msg.lower():
                        print(f"  CuPy 패키지 설치 완료, 그러나 CUDA 런타임을 찾을 수 없습니다.")
                        print(f"  해결: CUDA Toolkit을 설치하거나 CUDA_PATH 환경 변수를 설정하세요.")
                        print(f"  https://developer.nvidia.com/cuda-downloads")
                        return EXIT_SUCCESS  # pip 자체는 성공
                    else:
                        print(f"  CuPy 패키지 설치 완료, 그러나 import 검증 실패", file=sys.stderr)
                        if stderr_msg:
                            logger.debug(f"Verify stderr: {stderr_msg}")
                        return EXIT_SUCCESS  # pip 자체는 성공
            except Exception:
                print("  CuPy 패키지 설치 완료")
                return EXIT_SUCCESS
        else:
            print()
            print(f"  CuPy 설치 실패 (종료 코드: {result.returncode})", file=sys.stderr)
            print(f"  수동 설치를 시도하세요: pip install {cupy_pkg}", file=sys.stderr)
            return EXIT_DEPENDENCY
    except subprocess.TimeoutExpired:
        print("\n  CuPy 설치 시간 초과 (10분)", file=sys.stderr)
        return EXIT_DEPENDENCY
    except Exception as e:
        print(f"\n  CuPy 설치 실패: {e}", file=sys.stderr)
        return EXIT_DEPENDENCY
