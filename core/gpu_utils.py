"""
GPU 감지 및 유틸리티 모듈
CUDA/CuPy/FFmpeg NVENC 지원 여부를 자동으로 감지합니다.
pynvml 우선, nvidia-smi 폴백
"""

import subprocess
import shutil
import os
import warnings
import threading
import logging
from typing import Optional, Dict, Any
from dataclasses import dataclass, field

import numpy as np

logger = logging.getLogger(__name__)

# pynvml 사용 가능 여부
try:
    import pynvml
    HAS_PYNVML = True
except ImportError:
    HAS_PYNVML = False

# 스레드 안전을 위한 락
_gpu_lock = threading.Lock()

# pynvml 초기화 상태
_pynvml_initialized = False

# CuPy 사용 가능 여부 (지연 로딩)
_cupy_available = None  # None = 아직 확인 안 함
_cp = None


@dataclass
class GpuInfo:
    """GPU 정보 데이터 클래스"""
    has_cuda: bool = False
    has_cupy: bool = False
    gpu_name: Optional[str] = None
    gpu_memory_mb: int = 0
    cuda_version: Optional[str] = None
    ffmpeg_nvenc: bool = False
    driver_version: Optional[str] = None


@dataclass
class DetailedGpuInfo:
    """상세 GPU 정보 데이터 클래스"""
    gpu_name: Optional[str] = None
    gpu_memory_total_mb: int = 0
    gpu_memory_used_mb: int = 0
    gpu_memory_free_mb: int = 0
    gpu_utilization: int = 0
    memory_utilization: int = 0
    temperature: int = 0
    power_usage: float = 0.0
    encoder_sessions: int = 0
    driver_version: Optional[str] = None


# 전역 GPU 정보 캐시 (dataclass 정의 후)
_gpu_info: Optional[GpuInfo] = None


def _init_pynvml() -> bool:
    """pynvml 초기화 (한 번만 실행)"""
    global _pynvml_initialized
    
    if not HAS_PYNVML:
        return False
    
    if _pynvml_initialized:
        return True
    
    try:
        pynvml.nvmlInit()
        
        # 초기화 성공 검증 (디바이스 카운트 조회 시도)
        try:
            device_count = pynvml.nvmlDeviceGetCount()
            if device_count < 0:
                logger.warning("Invalid device count from NVML")
                return False
        except pynvml.NVMLError as e:
            logger.warning(f"NVML device count check failed: {e}")
            return False
        
        _pynvml_initialized = True
        return True
    except (pynvml.NVMLError, OSError, AttributeError) as e:
        logger.debug(f"[gpu_utils] pynvml 초기화 실패: {e}")
        return False


def _shutdown_pynvml():
    """pynvml 종료"""
    global _pynvml_initialized
    
    if HAS_PYNVML and _pynvml_initialized:
        try:
            pynvml.nvmlShutdown()
        except Exception:
            pass  # pynvml 종료 실패 무시
        _pynvml_initialized = False


_cupy_check_lock = threading.Lock()

def _check_cupy():
    """CuPy 사용 가능 여부를 안전하게 확인 (지연 로딩, 스레드 안전)"""
    global _cupy_available, _cp

    if _cupy_available is not None:
        return _cupy_available

    with _cupy_check_lock:
        # 이중 체크 (Double-checked locking)
        if _cupy_available is not None:
            return _cupy_available

        # 환경 변수로 GPU 비활성화 옵션
        if os.environ.get('GIFFY_DISABLE_GPU', '').lower() in ('1', 'true', 'yes'):
            logger.info("GPU disabled by environment variable")
            _cupy_available = False
            return False

        _cupy_available = False

        try:
            # 경고 메시지 억제
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                import cupy as cp

                # GPU 디바이스 확인
                device_count = cp.cuda.runtime.getDeviceCount()
                if device_count <= 0:
                    logger.info("No CUDA devices found")
                    return False

                # CuPy 사용 가능으로 설정 (메모리 테스트 제거 - 느려서)
                _cupy_available = True
                _cp = cp
                logger.info(f"CuPy initialized successfully with {device_count} device(s)")

        except ImportError:
            # CuPy가 설치되지 않음
            logger.debug("CuPy not installed")
        except (RuntimeError, OSError, AttributeError) as e:
            # CUDA 드라이버 오류, 메모리 문제, DLL 충돌 등
            logger.debug(f"CuPy initialization failed: {e}")

        return _cupy_available


def detect_gpu(skip_cupy: bool = False) -> GpuInfo:
    """
    GPU 정보를 감지하고 캐싱합니다.
    pynvml 우선 사용, nvidia-smi 폴백

    Args:
        skip_cupy: True이면 CuPy 초기화를 건너뛰고 하드웨어 정보만 감지 (빠름, <100ms)

    Returns:
        GpuInfo: GPU 정보 데이터 클래스
    """
    global _gpu_info

    # 스레드 안전한 접근 - 전체 함수를 락으로 보호
    with _gpu_lock:
        # 캐시가 있고, CuPy 스킵 요청이거나 이미 CuPy 정보까지 포함된 경우
        if _gpu_info is not None:
            if skip_cupy or _gpu_info.has_cupy or not _gpu_info.has_cuda:
                return _gpu_info
            # CuPy 정보가 없는데 skip_cupy=False → CuPy 확인 추가 실행

        # 환경 변수로 GPU 비활성화 옵션
        if os.environ.get('GIFFY_DISABLE_GPU', '').lower() in ('1', 'true', 'yes'):
            _gpu_info = GpuInfo()
            return _gpu_info

        # 하드웨어 정보가 아직 없으면 감지
        if _gpu_info is None:
            info = GpuInfo()

            # 1. pynvml 우선 시도
            gpu_detected = False
            if HAS_PYNVML and _init_pynvml():
                try:
                    device_count = pynvml.nvmlDeviceGetCount()
                    if device_count > 0:
                        handle = pynvml.nvmlDeviceGetHandleByIndex(0)

                        # GPU 이름
                        gpu_name = pynvml.nvmlDeviceGetName(handle)
                        info.gpu_name = gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else gpu_name

                        # GPU 메모리
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        info.gpu_memory_mb = mem_info.total // (1024 * 1024)

                        # 드라이버 버전
                        driver_ver = pynvml.nvmlSystemGetDriverVersion()
                        info.driver_version = driver_ver.decode('utf-8') if isinstance(driver_ver, bytes) else driver_ver

                        info.has_cuda = True
                        gpu_detected = True
                except (pynvml.NVMLError, AttributeError, ValueError) as e:
                    import logging
                    logging.debug(f"[gpu_utils] pynvml GPU 감지 실패: {e}")

            # 2. pynvml 실패 시 nvidia-smi 폴백
            if not gpu_detected:
                try:
                    from .utils import run_subprocess_silent
                    result = run_subprocess_silent(
                        ['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader,nounits'],
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        parts = result.stdout.strip().split(',')
                        if len(parts) >= 2:
                            info.has_cuda = True
                            info.gpu_name = parts[0].strip()
                            try:
                                info.gpu_memory_mb = int(parts[1].strip())
                            except ValueError:
                                pass
                            if len(parts) >= 3:
                                info.driver_version = parts[2].strip()
                except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
                    pass

            _gpu_info = info
        else:
            info = _gpu_info

        # CuPy 스킵 요청 시 하드웨어 정보만 반환
        if skip_cupy:
            return _gpu_info

        # 3. CuPy 확인 (GPU가 있을 때만)
        if info.has_cuda and not info.has_cupy:
            try:
                cupy_ok = _check_cupy()
                info.has_cupy = cupy_ok

                # CuPy로 CUDA 버전 얻기
                if cupy_ok and _cp is not None:
                    try:
                        version = _cp.cuda.runtime.runtimeGetVersion()
                        if isinstance(version, int):
                            major = version // 1000
                            minor = (version % 1000) // 10
                            info.cuda_version = f"{major}.{minor}"
                        elif isinstance(version, (tuple, list)):
                            info.cuda_version = '.'.join(map(str, version))
                        else:
                            info.cuda_version = str(version)
                    except (AttributeError, RuntimeError, TypeError):
                        pass
            except (ImportError, RuntimeError):
                info.has_cupy = False

        # 4. FFmpeg NVENC 지원 확인
        if not info.ffmpeg_nvenc:
            try:
                info.ffmpeg_nvenc = _check_ffmpeg_nvenc()
            except (subprocess.SubprocessError, FileNotFoundError, OSError):
                info.ffmpeg_nvenc = False

        _gpu_info = info
        return info


def _check_ffmpeg_nvenc() -> bool:
    """FFmpeg의 CUDA/NVENC 하드웨어 가속 지원 여부 확인"""
    ffmpeg_path = shutil.which('ffmpeg')
    if not ffmpeg_path:
        # 로컬 설치 확인
        try:
            from .ffmpeg_installer import FFmpegManager
            ffmpeg_path = FFmpegManager.get_ffmpeg_executable()
        except ImportError:
            pass
    
    if not ffmpeg_path:
        return False
    
    try:
        from .utils import run_subprocess_silent
        result = run_subprocess_silent([ffmpeg_path, '-hwaccels'], timeout=5)
        return 'cuda' in result.stdout.lower()
    except (subprocess.SubprocessError, FileNotFoundError):
        return False


def get_array_module():
    """
    GPU 사용 가능하면 cupy, 아니면 numpy 반환
    
    CuPy와 NumPy는 대부분의 API가 호환되므로,
    이 함수로 반환된 모듈을 사용하면 동일한 코드로
    CPU/GPU 모두 지원할 수 있습니다.
    """
    if _check_cupy() and _cp is not None:
        return _cp
    return np


def is_gpu_available() -> bool:
    """GPU(CUDA) 사용 가능 여부"""
    return detect_gpu().has_cuda


def is_cupy_available() -> bool:
    """CuPy 사용 가능 여부"""
    return _check_cupy()


def to_gpu(array: np.ndarray):
    """NumPy 배열을 GPU로 전송 (안전)"""
    if array is None or not isinstance(array, np.ndarray):
        logger.warning(f"Invalid array type for GPU transfer: {type(array)}")
        return array
    
    if _check_cupy() and _cp is not None:
        try:
            return _cp.asarray(array)
        except (_cp.cuda.memory.OutOfMemoryError, RuntimeError) as e:
            logger.error(f"GPU memory allocation failed: {e}")
            return array  # CPU로 폴백
    return array


def to_cpu(array) -> np.ndarray:
    """GPU 배열을 CPU(NumPy)로 전송 (안전)"""
    if array is None:
        return np.array([])
    
    if _check_cupy() and _cp is not None and hasattr(array, 'get'):
        try:
            return array.get()
        except (RuntimeError, ValueError) as e:
            logger.error(f"GPU to CPU transfer failed: {e}")
            # 이미 NumPy 배열이면 그대로 반환
            if isinstance(array, np.ndarray):
                return array
            return np.array([])
    
    return array if isinstance(array, np.ndarray) else np.array([])


def get_gpu_info_string() -> str:
    """GPU 정보를 사람이 읽을 수 있는 문자열로 반환"""
    info = detect_gpu()
    
    if not info.has_cuda:
        return "GPU 없음 (CPU 모드)"
    
    parts = []
    if info.gpu_name:
        parts.append(info.gpu_name)
    if info.gpu_memory_mb:
        parts.append(f"{info.gpu_memory_mb}MB")
    if info.has_cupy:
        parts.append("CuPy 활성")
    if info.ffmpeg_nvenc:
        parts.append("NVENC 지원")
    
    return ' | '.join(parts) if parts else "GPU 감지됨"


def get_detailed_gpu_info() -> DetailedGpuInfo:
    """
    상세 GPU 정보 반환 (실시간, 캐싱 안 함)
    pynvml 사용 가능 시 추가 정보 제공
    
    Returns:
        DetailedGpuInfo: 상세 GPU 정보 데이터 클래스
    """
    info = DetailedGpuInfo()
    
    if not HAS_PYNVML or not _init_pynvml():
        # pynvml 없으면 기본 정보만 반환
        basic = detect_gpu()
        info.gpu_name = basic.gpu_name
        info.gpu_memory_total_mb = basic.gpu_memory_mb
        info.driver_version = basic.driver_version
        return info
    
    try:
        handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        
        # GPU 이름
        gpu_name = pynvml.nvmlDeviceGetName(handle)
        info.gpu_name = gpu_name.decode('utf-8') if isinstance(gpu_name, bytes) else gpu_name
        
        # 메모리 정보
        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
        info.gpu_memory_total_mb = mem_info.total // (1024 * 1024)
        info.gpu_memory_used_mb = mem_info.used // (1024 * 1024)
        info.gpu_memory_free_mb = mem_info.free // (1024 * 1024)
        
        # 사용률
        try:
            util = pynvml.nvmlDeviceGetUtilizationRates(handle)
            info.gpu_utilization = util.gpu
            info.memory_utilization = util.memory
        except (pynvml.NVMLError, AttributeError):
            pass
        
        # 온도
        try:
            info.temperature = pynvml.nvmlDeviceGetTemperature(
                handle, pynvml.NVML_TEMPERATURE_GPU
            )
        except (pynvml.NVMLError, AttributeError):
            pass
        
        # 전력 사용량
        try:
            power_mw = pynvml.nvmlDeviceGetPowerUsage(handle)
            info.power_usage = power_mw / 1000.0  # mW -> W
        except (pynvml.NVMLError, AttributeError):
            pass
        
        # 인코더 세션 수
        try:
            encoder_sessions = pynvml.nvmlDeviceGetEncoderSessions(handle)
            info.encoder_sessions = len(encoder_sessions) if encoder_sessions else 0
        except (pynvml.NVMLError, AttributeError):
            pass
        
        # 드라이버 버전
        try:
            driver_ver = pynvml.nvmlSystemGetDriverVersion()
            info.driver_version = driver_ver.decode('utf-8') if isinstance(driver_ver, bytes) else driver_ver
        except (pynvml.NVMLError, AttributeError):
            pass
        
    except Exception as e:
        logger.warning("[gpu_utils] 상세 GPU 정보 조회 실패: %s", e)
    
    return info


def reset_gpu_cache():
    """GPU 정보 캐시 초기화 (재감지 필요 시 호출)"""
    global _gpu_info
    with _gpu_lock:
        _gpu_info = None


# 최소 프레임 크기 (이 크기 이하면 GPU 오버헤드가 더 클 수 있음)
MIN_GPU_FRAME_SIZE = 640 * 480


def should_use_gpu(width: int, height: int) -> bool:
    """
    주어진 프레임 크기에서 GPU 사용이 효율적인지 판단
    
    작은 프레임에서는 CPU-GPU 데이터 전송 오버헤드가
    GPU 연산 이득보다 클 수 있습니다.
    """
    if not _check_cupy():
        return False
    
    return (width * height) >= MIN_GPU_FRAME_SIZE
