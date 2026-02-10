"""
GPU Utilities - CUDA GPU 가속 유틸리티
CuPy를 사용하여 GPU 가속 지원

사용법:
    from editor.core import gpu_utils

    # GPU 사용 가능 여부 확인
    if gpu_utils.is_gpu_available():
        print(gpu_utils.get_gpu_info())

    # GPU 가속 효과 적용
    result = gpu_utils.gpu_sepia(image_array)
"""
from typing import Optional, Tuple, Dict, Any
import numpy as np
import os
import threading

from ..utils.logger import get_logger

# 로거 초기화
_logger = get_logger()

# GPU 가속 관련 전역 상태
_gpu_available: Optional[bool] = None
_gpu_enabled: bool = True  # GPU 사용 여부 (사용자 설정)
_cupy_module = None
_gpu_init_error: Optional[str] = None  # 초기화 실패 시 에러 메시지
_gpu_lock = threading.Lock()  # 스레드 안전성을 위한 Lock



def _check_gpu() -> bool:
    """CUDA GPU 사용 가능 여부 확인
    
    Returns:
        bool: GPU 사용 가능 시 True, 아니면 False
    """
    global _cupy_module, _gpu_init_error
    
    # CUDA_VISIBLE_DEVICES 환경 변수 확인
    cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '')
    if cuda_devices == '-1':
        _gpu_init_error = "CUDA_VISIBLE_DEVICES가 -1로 설정됨 (GPU 비활성화)"
        _logger.info(f"GPU 초기화 건너뜀: {_gpu_init_error}")
        return False
    
    try:
        from core.utils import ensure_system_site_packages
        ensure_system_site_packages()
    except Exception:
        pass

    try:
        import cupy as cp

        # CUDA 런타임 버전 확인
        cuda_version = cp.cuda.runtime.runtimeGetVersion()
        _logger.info(f"CUDA 런타임 버전: {cuda_version // 1000}.{(cuda_version % 1000) // 10}")
        
        # GPU 장치 수 확인
        device_count = cp.cuda.runtime.getDeviceCount()
        if device_count == 0:
            _gpu_init_error = "사용 가능한 CUDA 장치가 없습니다"
            _logger.warning(_gpu_init_error)
            return False
        
        _logger.info(f"CUDA 장치 발견: {device_count}개")
        
        # 기본 장치 선택 및 정보 로깅
        device = cp.cuda.Device()
        props = cp.cuda.runtime.getDeviceProperties(device.id)
        device_name = props["name"].decode() if isinstance(props["name"], bytes) else props["name"]
        total_memory_mb = props["totalGlobalMem"] // (1024 * 1024)
        compute_cap = f"{props['major']}.{props['minor']}"
        
        _logger.info(f"GPU 선택됨: {device_name}")
        _logger.info(f"  - 메모리: {total_memory_mb:,} MB")
        _logger.info(f"  - Compute Capability: {compute_cap}")
        
        # GPU 메모리 할당 테스트
        test_arr = cp.array([1, 2, 3], dtype=cp.float32)
        result = test_arr.sum()
        _ = result.get()
        del test_arr, result
        cp.get_default_memory_pool().free_all_blocks()
        
        _cupy_module = cp
        _logger.info("GPU 초기화 완료 - CuPy 사용 가능")
        return True
        
    except ImportError as e:
        _gpu_init_error = f"CuPy가 설치되지 않음: {str(e)}"
        _logger.info(f"GPU 가속 사용 불가: {_gpu_init_error}")
        _logger.info("GPU 가속을 사용하려면: pip install cupy-cuda12x (CUDA 12.x) 또는 cupy-cuda11x (CUDA 11.x)")
        return False
    except Exception as e:
        _gpu_init_error = f"GPU 초기화 실패: {str(e)}"
        _logger.warning(_gpu_init_error)
        return False


def is_gpu_available() -> bool:
    """GPU 사용 가능 여부 반환 (캐싱됨)
    
    첫 호출 시 GPU 검사를 수행하고 결과를 캐싱합니다.
    스레드 안전합니다.
    
    Returns:
        bool: GPU 사용 가능 시 True
    """
    global _gpu_available
    if _gpu_available is None:
        with _gpu_lock:
            if _gpu_available is None:  # Double-checked locking
                _gpu_available = _check_gpu()
    return _gpu_available


def is_gpu_enabled() -> bool:
    """GPU 사용 활성화 여부
    
    GPU가 사용 가능하고 사용자가 활성화했는지 확인합니다.
    
    Returns:
        bool: GPU 사용이 활성화되었으면 True
    """
    return _gpu_enabled and is_gpu_available()


def set_gpu_enabled(enabled: bool) -> None:
    """GPU 사용 설정
    
    Args:
        enabled: True면 GPU 사용 활성화, False면 비활성화
    """
    global _gpu_enabled
    _gpu_enabled = enabled
    status = "활성화" if enabled else "비활성화"
    _logger.info(f"GPU 사용 설정: {status}")


def get_gpu_init_error() -> Optional[str]:
    """GPU 초기화 실패 시 에러 메시지 반환
    
    Returns:
        str 또는 None: 에러 메시지, 성공 시 None
    """
    return _gpu_init_error


def get_gpu_info() -> Dict[str, Any]:
    """GPU 정보 반환
    
    Returns:
        dict: GPU 정보를 담은 딕셔너리
            - available: GPU 사용 가능 여부
            - enabled: GPU 사용 활성화 여부
            - name: GPU 이름
            - memory_total: 총 메모리 (MB)
            - memory_used: 사용 중인 메모리 (MB)
            - memory_free: 여유 메모리 (MB)
            - compute_capability: Compute Capability
            - cuda_version: CUDA 버전
            - cupy_version: CuPy 버전
            - error: 에러 메시지 (있을 경우)
    """
    info = {
        "available": False,
        "enabled": _gpu_enabled,
        "name": "N/A",
        "memory_total": 0,
        "memory_used": 0,
        "memory_free": 0,
        "compute_capability": "N/A",
        "cuda_version": "N/A",
        "cupy_version": "N/A"
    }
    
    if not is_gpu_available():
        if _gpu_init_error:
            info["error"] = _gpu_init_error
        return info
    
    try:
        import cupy as cp
        
        info["available"] = True
        info["cupy_version"] = cp.__version__
        
        # CUDA 버전
        cuda_version = cp.cuda.runtime.runtimeGetVersion()
        info["cuda_version"] = f"{cuda_version // 1000}.{(cuda_version % 1000) // 10}"
        
        # 장치 정보
        device = cp.cuda.Device()
        props = cp.cuda.runtime.getDeviceProperties(device.id)
        
        info["name"] = props["name"].decode() if isinstance(props["name"], bytes) else props["name"]
        info["memory_total"] = props["totalGlobalMem"] // (1024 * 1024)
        info["compute_capability"] = f"{props['major']}.{props['minor']}"
        
        # 현재 메모리 사용량
        mempool = cp.get_default_memory_pool()
        info["memory_used"] = mempool.used_bytes() // (1024 * 1024)
        info["memory_free"] = info["memory_total"] - info["memory_used"]
        
    except Exception as e:
        info["error"] = str(e)
    
    return info


def get_gpu_memory_info() -> Dict[str, int]:
    """GPU 메모리 정보 반환
    
    Returns:
        dict: 메모리 정보 (단위: MB)
            - total: 총 메모리
            - used: 사용 중
            - free: 여유
    """
    if not is_gpu_available():
        return {"total": 0, "used": 0, "free": 0}
    
    try:
        import cupy as cp
        
        device = cp.cuda.Device()
        props = cp.cuda.runtime.getDeviceProperties(device.id)
        total = props["totalGlobalMem"] // (1024 * 1024)
        
        mempool = cp.get_default_memory_pool()
        used = mempool.used_bytes() // (1024 * 1024)
        
        return {"total": total, "used": used, "free": total - used}
    except Exception:
        return {"total": 0, "used": 0, "free": 0}


def clear_gpu_memory() -> None:
    """GPU 메모리 정리
    
    사용하지 않는 GPU 메모리 블록을 해제합니다.
    """
    if not is_gpu_available():
        return
    
    try:
        import cupy as cp
        
        mempool = cp.get_default_memory_pool()
        pinned_mempool = cp.get_default_pinned_memory_pool()
        
        before_used = mempool.used_bytes() // (1024 * 1024)
        
        mempool.free_all_blocks()
        pinned_mempool.free_all_blocks()
        
        after_used = mempool.used_bytes() // (1024 * 1024)
        freed = before_used - after_used
        
        if freed > 0:
            _logger.debug(f"GPU 메모리 정리: {freed} MB 해제됨")
    except Exception as e:
        _logger.warning(f"GPU 메모리 정리 실패: {e}")


def to_gpu(arr: np.ndarray) -> 'cp.ndarray':
    """NumPy 배열을 GPU로 전송
    
    Args:
        arr: NumPy 배열
        
    Returns:
        CuPy 배열 (GPU 메모리에 위치)
        
    Raises:
        RuntimeError: GPU가 비활성화된 경우
    """
    if not is_gpu_enabled():
        raise RuntimeError("GPU가 활성화되지 않았습니다. is_gpu_enabled()를 먼저 확인하세요.")
    import cupy as cp
    return cp.asarray(arr)


def to_cpu(arr) -> np.ndarray:
    """GPU 배열을 CPU로 전송
    
    Args:
        arr: CuPy 배열 또는 NumPy 배열
        
    Returns:
        NumPy 배열 (CPU 메모리에 위치)
    """
    if hasattr(arr, 'get'):
        return arr.get()
    return np.asarray(arr)


def get_array_module(arr):
    """배열에 맞는 모듈 반환 (numpy 또는 cupy)
    
    CuPy의 get_array_module을 래핑하여 안전하게 사용합니다.
    
    Args:
        arr: 배열 (NumPy 또는 CuPy)
        
    Returns:
        numpy 또는 cupy 모듈
    """
    if is_gpu_enabled():
        try:
            import cupy as cp
            return cp.get_array_module(arr)
        except Exception:
            pass
    return np


def should_use_gpu(image_size: Tuple[int, int], frame_count: int = 1) -> bool:
    """GPU 사용 권장 여부 판단
    
    이미지 크기와 프레임 수를 기반으로 GPU 사용이 유리한지 판단합니다.
    작은 이미지나 적은 프레임에서는 CPU가 더 빠를 수 있습니다.
    
    Args:
        image_size: (width, height) 튜플
        frame_count: 처리할 프레임 수
        
    Returns:
        bool: GPU 사용을 권장하면 True
    """
    if not is_gpu_enabled():
        return False
    
    width, height = image_size
    pixels = width * height
    
    # 임계값: 약 300x300 픽셀 이상, 또는 10프레임 이상
    MIN_PIXELS = 90000  # 300 * 300
    MIN_FRAMES_FOR_BATCH = 10
    
    # 단일 이미지: 픽셀 수가 충분히 커야 함
    if frame_count == 1:
        return pixels >= MIN_PIXELS
    
    # 배치 처리: 총 연산량이 충분히 커야 함
    total_pixels = pixels * frame_count
    return total_pixels >= MIN_PIXELS * MIN_FRAMES_FOR_BATCH or frame_count >= MIN_FRAMES_FOR_BATCH


# === GPU 가속 이미지 처리 함수들 ===

def gpu_sepia(img_array: np.ndarray) -> np.ndarray:
    """GPU 가속 세피아 효과
    
    Args:
        img_array: RGBA 이미지 배열 (H, W, 4)
    
    Returns:
        세피아 효과가 적용된 이미지 배열
    """
    # 입력 검증
    if img_array is None:
        raise ValueError("이미지 배열이 None입니다")
    
    if not isinstance(img_array, np.ndarray):
        raise TypeError(f"numpy 배열이 필요합니다. 받은 타입: {type(img_array)}")
    
    if len(img_array.shape) != 3 or img_array.shape[2] < 3:
        raise ValueError(f"이미지 배열 shape이 올바르지 않습니다. 예상: (H, W, 3+) 받음: {img_array.shape}")
    
    if img_array.size == 0:
        raise ValueError("빈 이미지 배열입니다")
    
    if not is_gpu_enabled():
        return cpu_sepia(img_array)
    
    try:
        import cupy as cp
        
        # GPU로 전송
        gpu_arr = cp.asarray(img_array, dtype=cp.float32)
        
        # 세피아 매트릭스
        sepia_matrix = cp.array([
            [0.393, 0.769, 0.189],
            [0.349, 0.686, 0.168],
            [0.272, 0.534, 0.131]
        ], dtype=cp.float32)
        
        # RGB 채널만 추출
        rgb = gpu_arr[:, :, :3]
        
        # 행렬 연산
        sepia = cp.dot(rgb, sepia_matrix.T)
        sepia = cp.clip(sepia, 0, 255)
        
        # 결과 합성
        result = gpu_arr.copy()
        result[:, :, :3] = sepia
        
        # CPU로 반환
        return cp.asnumpy(result).astype(np.uint8)
    
    except MemoryError:
        _logger.warning("GPU 메모리 부족 - CPU로 폴백")
        return cpu_sepia(img_array)
    except Exception as e:
        _logger.warning(f"GPU 처리 실패 - CPU로 폴백: {e}")
        # 실패 시 CPU 폴백
        return cpu_sepia(img_array)


def cpu_sepia(img_array: np.ndarray) -> np.ndarray:
    """CPU 세피아 효과 (NumPy)"""
    return _numpy_sepia(img_array)


def _numpy_sepia(img_array: np.ndarray) -> np.ndarray:
    """NumPy 기반 세피아 효과 (기본 폴백)"""
    arr = img_array.astype(np.float32)
    
    sepia_matrix = np.array([
        [0.393, 0.769, 0.189],
        [0.349, 0.686, 0.168],
        [0.272, 0.534, 0.131]
    ])
    
    rgb = arr[:, :, :3]
    sepia = np.dot(rgb, sepia_matrix.T)
    sepia = np.clip(sepia, 0, 255)
    
    result = arr.copy()
    result[:, :, :3] = sepia
    
    return result.astype(np.uint8)




def gpu_vignette(img_array: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """GPU 가속 비네트 효과
    
    Args:
        img_array: RGBA 이미지 배열 (H, W, 4)
        strength: 비네트 강도 (0.0 ~ 1.0)
    
    Returns:
        비네트 효과가 적용된 이미지 배열
    """
    # 입력 검증
    if img_array is None:
        raise ValueError("이미지 배열이 None입니다")
    
    if not isinstance(img_array, np.ndarray):
        raise TypeError(f"numpy 배열이 필요합니다. 받은 타입: {type(img_array)}")
    
    if len(img_array.shape) != 3 or img_array.shape[2] < 3:
        raise ValueError(f"이미지 배열 shape이 올바르지 않습니다. 예상: (H, W, 3+) 받음: {img_array.shape}")
    
    if img_array.size == 0:
        raise ValueError("빈 이미지 배열입니다")
    
    # strength 범위 검증
    strength = max(0.0, min(1.0, float(strength)))
    
    if not is_gpu_enabled():
        return cpu_vignette(img_array, strength)
    
    try:
        import cupy as cp
        
        height, width = img_array.shape[:2]
        
        if height == 0 or width == 0:
            raise ValueError(f"이미지 크기가 유효하지 않습니다: {height}x{width}")
        
        # GPU에서 마스크 생성
        x = cp.linspace(-1, 1, width, dtype=cp.float32)
        y = cp.linspace(-1, 1, height, dtype=cp.float32)
        X, Y = cp.meshgrid(x, y)
        
        # 거리 계산
        distance = cp.sqrt(X**2 + Y**2)
        
        # 비네트 마스크
        vignette = 1 - (distance * strength)
        vignette = cp.clip(vignette, 0, 1)
        
        # 이미지를 GPU로 전송
        gpu_arr = cp.asarray(img_array, dtype=cp.float32)
        
        # RGB 채널에 적용
        for i in range(3):
            gpu_arr[:, :, i] *= vignette
        
        gpu_arr = cp.clip(gpu_arr, 0, 255)
        
        return cp.asnumpy(gpu_arr).astype(np.uint8)
    
    except MemoryError:
        _logger.warning("GPU 메모리 부족 - CPU로 폴백")
        return cpu_vignette(img_array, strength)
    except Exception as e:
        _logger.warning(f"GPU 처리 실패 - CPU로 폴백: {e}")
        return cpu_vignette(img_array, strength)


def cpu_vignette(img_array: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """CPU 비네트 효과 (NumPy)"""
    return _numpy_vignette(img_array, strength)


def _numpy_vignette(img_array: np.ndarray, strength: float = 0.5) -> np.ndarray:
    """NumPy 기반 비네트 효과 (기본 폴백)"""
    height, width = img_array.shape[:2]
    
    x = np.linspace(-1, 1, width)
    y = np.linspace(-1, 1, height)
    X, Y = np.meshgrid(x, y)
    
    distance = np.sqrt(X**2 + Y**2)
    vignette = 1 - (distance * strength)
    vignette = np.clip(vignette, 0, 1)
    
    arr = img_array.astype(np.float32)
    for i in range(3):
        arr[:, :, i] *= vignette
    
    return np.clip(arr, 0, 255).astype(np.uint8)




def gpu_hue_shift(img_array: np.ndarray, shift: int) -> np.ndarray:
    """GPU 가속 Hue 조절
    
    Args:
        img_array: RGBA 이미지 배열 (H, W, 4)
        shift: Hue 이동값 (-180 ~ 180)
    
    Returns:
        Hue가 조절된 이미지 배열
    """
    # 입력 검증
    if img_array is None:
        raise ValueError("이미지 배열이 None입니다")
    
    if not isinstance(img_array, np.ndarray):
        raise TypeError(f"numpy 배열이 필요합니다. 받은 타입: {type(img_array)}")
    
    if len(img_array.shape) != 3 or img_array.shape[2] < 3:
        raise ValueError(f"이미지 배열 shape이 올바르지 않습니다. 예상: (H, W, 3+) 받음: {img_array.shape}")
    
    if img_array.size == 0:
        raise ValueError("빈 이미지 배열입니다")
    
    # shift 범위 검증
    shift = max(-180, min(180, int(shift)))
    
    if not is_gpu_enabled():
        return cpu_hue_shift(img_array, shift)
    
    try:
        import cupy as cp
        
        # GPU로 전송
        gpu_arr = cp.asarray(img_array, dtype=cp.float32)
        
        # RGB를 HSV로 변환 (GPU에서)
        r = gpu_arr[:, :, 0] / 255.0
        g = gpu_arr[:, :, 1] / 255.0
        b = gpu_arr[:, :, 2] / 255.0
        
        max_c = cp.maximum(cp.maximum(r, g), b)
        min_c = cp.minimum(cp.minimum(r, g), b)
        diff = max_c - min_c
        
        # Hue 계산
        h = cp.zeros_like(max_c)
        
        # diff가 0이 아닌 곳만 계산
        mask = diff > 0
        
        # R이 max인 경우
        r_max = (max_c == r) & mask
        h[r_max] = (60 * ((g[r_max] - b[r_max]) / diff[r_max]) + 360) % 360
        
        # G가 max인 경우
        g_max = (max_c == g) & mask
        h[g_max] = (60 * ((b[g_max] - r[g_max]) / diff[g_max]) + 120) % 360
        
        # B가 max인 경우
        b_max = (max_c == b) & mask
        h[b_max] = (60 * ((r[b_max] - g[b_max]) / diff[b_max]) + 240) % 360
        
        # Saturation, Value
        s = cp.where(max_c > 0, diff / max_c, 0)
        v = max_c
        
        # Hue 이동
        h = (h + shift) % 360
        
        # HSV를 RGB로 변환
        c = v * s
        x = c * (1 - cp.abs((h / 60) % 2 - 1))
        m = v - c
        
        h_i = (h / 60).astype(cp.int32) % 6
        
        r_new = cp.zeros_like(h)
        g_new = cp.zeros_like(h)
        b_new = cp.zeros_like(h)
        
        for i, (r_v, g_v, b_v) in enumerate([
            (c, x, 0), (x, c, 0), (0, c, x),
            (0, x, c), (x, 0, c), (c, 0, x)
        ]):
            mask_i = h_i == i
            if isinstance(r_v, (int, float)):
                r_new[mask_i] = r_v
            else:
                r_new[mask_i] = r_v[mask_i]
            if isinstance(g_v, (int, float)):
                g_new[mask_i] = g_v
            else:
                g_new[mask_i] = g_v[mask_i]
            if isinstance(b_v, (int, float)):
                b_new[mask_i] = b_v
            else:
                b_new[mask_i] = b_v[mask_i]
        
        r_new = (r_new + m) * 255
        g_new = (g_new + m) * 255
        b_new = (b_new + m) * 255
        
        result = gpu_arr.copy()
        result[:, :, 0] = cp.clip(r_new, 0, 255)
        result[:, :, 1] = cp.clip(g_new, 0, 255)
        result[:, :, 2] = cp.clip(b_new, 0, 255)
        
        return cp.asnumpy(result).astype(np.uint8)
    
    except MemoryError:
        _logger.warning("GPU 메모리 부족 - CPU로 폴백")
        return cpu_hue_shift(img_array, shift)
    except Exception as e:
        _logger.warning(f"GPU 처리 실패 - CPU로 폴백: {e}")
        return cpu_hue_shift(img_array, shift)


def cpu_hue_shift(img_array: np.ndarray, shift: int) -> np.ndarray:
    """CPU Hue 조절 (폴백용) - PIL 사용"""
    from PIL import Image
    
    img = Image.fromarray(img_array, 'RGBA')
    r, g, b, a = img.split()
    rgb = Image.merge('RGB', (r, g, b))
    
    hsv = rgb.convert('HSV')
    h, s, v = hsv.split()
    
    h_array = np.array(h, dtype=np.int32)
    # PIL HSV의 H는 0-255 범위. shift를 0-360 기준에서 0-255 기준으로 변환하여 GPU 경로와 일치시킴
    shift_normalized = int(round(shift * 256 / 360)) if abs(shift) > 0 else 0
    h_array = (h_array + shift_normalized) % 256
    h = Image.fromarray(h_array.astype(np.uint8))
    
    hsv = Image.merge('HSV', (h, s, v))
    rgb = hsv.convert('RGB')
    r, g, b = rgb.split()
    
    result = Image.merge('RGBA', (r, g, b, a))
    return np.array(result)


def gpu_calculate_similarity(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """GPU 가속 이미지 유사도 계산
    
    Args:
        arr1: 첫 번째 이미지 배열 (H, W, C)
        arr2: 두 번째 이미지 배열 (H, W, C)
    
    Returns:
        유사도 (0.0 ~ 1.0)
    """
    if arr1.shape != arr2.shape:
        return 0.0
    
    if not is_gpu_enabled():
        return cpu_calculate_similarity(arr1, arr2)
    
    try:
        import cupy as cp
        
        # GPU로 전송
        gpu_arr1 = cp.asarray(arr1[:, :, :3], dtype=cp.float32)
        gpu_arr2 = cp.asarray(arr2[:, :, :3], dtype=cp.float32)
        
        # 차이 계산
        diff = cp.abs(gpu_arr1 - gpu_arr2).mean()
        
        return float(1.0 - (diff / 255.0))
    
    except Exception:
        return cpu_calculate_similarity(arr1, arr2)


def cpu_calculate_similarity(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """CPU 이미지 유사도 계산 (NumPy)"""
    if arr1.shape != arr2.shape:
        return 0.0
    return _numpy_similarity(arr1, arr2)


def _numpy_similarity(arr1: np.ndarray, arr2: np.ndarray) -> float:
    """NumPy 기반 이미지 유사도 계산 (기본 폴백)"""
    a1 = arr1[:, :, :3].astype(np.float32)
    a2 = arr2[:, :, :3].astype(np.float32)
    
    # 샘플링으로 성능 최적화
    step = max(1, min(a1.shape[0], a1.shape[1]) // 50)
    a1 = a1[::step, ::step]
    a2 = a2[::step, ::step]
    
    diff = np.abs(a1 - a2).mean()
    return 1.0 - (diff / 255.0)




def gpu_batch_process(images: list, operation: str, **kwargs) -> list:
    """GPU 배치 이미지 처리
    
    여러 이미지에 동일한 효과를 적용합니다.
    GPU 메모리를 효율적으로 관리하면서 배치 처리합니다.
    
    Args:
        images: 이미지 배열 리스트 (numpy.ndarray)
        operation: 적용할 효과 ('sepia', 'vignette', 'hue_shift')
        **kwargs: 연산별 추가 인자
            - vignette: strength (float, 0.0~1.0)
            - hue_shift: shift (int, -180~180)
    
    Returns:
        처리된 이미지 배열 리스트
        
    Example:
        >>> images = [frame.numpy_array for frame in frames]
        >>> results = gpu_batch_process(images, 'sepia')
        >>> results = gpu_batch_process(images, 'vignette', strength=0.7)
    """
    if not images:
        return []
    
    operations = {
        'sepia': lambda img, **kw: gpu_sepia(img),
        'vignette': lambda img, **kw: gpu_vignette(img, kw.get('strength', 0.5)),
        'hue_shift': lambda img, **kw: gpu_hue_shift(img, kw.get('shift', 0)),
    }
    
    if operation not in operations:
        _logger.warning(f"알 수 없는 GPU 연산: {operation}. 원본 이미지 반환.")
        return images
    
    op_func = operations[operation]
    results = []
    
    # GPU 사용 권장 여부 확인
    if images and is_gpu_enabled():
        height, width = images[0].shape[:2]
        use_gpu = should_use_gpu((width, height), len(images))
        
        if use_gpu:
            _logger.debug(f"GPU 배치 처리 시작: {len(images)}개 이미지, 연산: {operation}")
        else:
            _logger.debug(f"CPU 배치 처리 시작: {len(images)}개 이미지 (GPU 사용 불필요)")
    
    # 배치 처리 (이미지 크기에 따라 동적 조정)
    # gpu_batch_process는 이미 배치 단위로 호출되므로 여기서는 작은 배치로 세분화
    # (apply_effect_gpu_batch에서 큰 배치로 나누고, 여기서는 GPU 메모리 관리를 위해 작은 단위로 처리)
    internal_batch_size = 10  # GPU 메모리 관리를 위한 내부 배치 크기
    for i in range(0, len(images), internal_batch_size):
        batch = images[i:i + internal_batch_size]
        batch_results = [op_func(img, **kwargs) for img in batch]
        results.extend(batch_results)
        
        # 배치 처리 후 GPU 메모리 정리 (마지막 배치가 아니면)
        if is_gpu_enabled() and (i + internal_batch_size) < len(images):
            clear_gpu_memory()
    
    if is_gpu_enabled():
        clear_gpu_memory()

    _logger.debug(f"배치 처리 완료: {len(results)}개 이미지")
    return results


# === 초기화 및 진단 유틸리티 ===

def initialize_gpu(force: bool = False) -> bool:
    """GPU 초기화
    
    명시적으로 GPU 초기화를 수행합니다.
    보통은 자동으로 초기화되지만, 진단 목적으로 수동 호출할 수 있습니다.
    
    Args:
        force: True면 캐시된 결과를 무시하고 재검사
        
    Returns:
        bool: GPU 사용 가능 여부
    """
    global _gpu_available, _gpu_init_error
    
    if force:
        _gpu_available = None
        _gpu_init_error = None
        _logger.info("GPU 상태 재검사 시작...")
    
    return is_gpu_available()


def get_diagnostic_info() -> str:
    """GPU 진단 정보 문자열 반환

    디버깅 및 지원 목적으로 상세한 GPU 정보를 반환합니다.

    Returns:
        str: 포맷된 진단 정보
    """
    lines = [
        "=== 가속 진단 정보 ===",
        "",
        "--- GPU (CuPy) ---",
        f"GPU 사용 가능: {is_gpu_available()}",
        f"GPU 사용 활성화: {_gpu_enabled}",
    ]

    if _gpu_init_error:
        lines.append(f"초기화 에러: {_gpu_init_error}")

    if is_gpu_available():
        info = get_gpu_info()
        lines.extend([
            f"GPU 이름: {info.get('name', 'N/A')}",
            f"CUDA 버전: {info.get('cuda_version', 'N/A')}",
            f"CuPy 버전: {info.get('cupy_version', 'N/A')}",
            f"Compute Capability: {info.get('compute_capability', 'N/A')}",
            f"총 메모리: {info.get('memory_total', 0):,} MB",
            f"사용 중: {info.get('memory_used', 0):,} MB",
            f"여유: {info.get('memory_free', 0):,} MB",
        ])

    # 환경 변수 정보
    lines.extend([
        "",
        "--- 환경 ---",
    ])
    cuda_devices = os.environ.get('CUDA_VISIBLE_DEVICES', '(설정되지 않음)')
    lines.append(f"CUDA_VISIBLE_DEVICES: {cuda_devices}")

    lines.append("=" * 25)
    return "\n".join(lines)


# === NVIDIA GPU / CUDA 감지 (CuPy 없이) ===

def has_nvidia_gpu_hardware() -> bool:
    """NVIDIA GPU 하드웨어 존재 여부 확인 (pynvml 사용, CuPy 불필요)

    Returns:
        bool: NVIDIA GPU가 1개 이상 감지되면 True
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        count = pynvml.nvmlDeviceGetCount()
        pynvml.nvmlShutdown()
        return count > 0
    except Exception:
        return False


def detect_cuda_driver_version() -> Optional[Tuple[int, int]]:
    """CUDA 드라이버 버전 감지 (pynvml 사용, CuPy 불필요)

    Returns:
        (major, minor) 튜플 또는 None (감지 실패 시)
    """
    try:
        import pynvml
        pynvml.nvmlInit()
        try:
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion_v2()
        except AttributeError:
            cuda_ver = pynvml.nvmlSystemGetCudaDriverVersion()
        pynvml.nvmlShutdown()
        major = cuda_ver // 1000
        minor = (cuda_ver % 1000) // 10
        return (major, minor)
    except Exception:
        return None


def get_cupy_package_name() -> Optional[str]:
    """CUDA 드라이버 버전에 맞는 CuPy 패키지명 반환

    Returns:
        패키지명 (예: 'cupy-cuda12x') 또는 None (감지 실패/미지원)
    """
    version = detect_cuda_driver_version()
    if version is None:
        return None
    major, _ = version
    if major >= 12:
        return "cupy-cuda12x"
    elif major >= 11:
        return "cupy-cuda11x"
    else:
        return None
