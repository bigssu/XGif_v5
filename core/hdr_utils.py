"""
HDR 모니터 대응 모듈
Windows HDR 감지 및 GPU 가속 톤 매핑 (SDR 변환)
"""

import logging
import os
import sys
from typing import Optional

import numpy as np

logger = logging.getLogger(__name__)

# Windows HDR 감지 (ctypes)
_hdr_active_cached: Optional[bool] = None
_hdr_cache_time: float = 0
_HDR_CACHE_SEC = 2.0


def _is_hdr_active_win32() -> bool:
    """Windows DisplayConfig API로 HDR 활성화 여부 확인 (주 모니터)"""
    if sys.platform != "win32":
        return False
    try:
        import ctypes
        from ctypes import wintypes

        # DisplayConfig API (Windows 10 1703+)
        QDC_ONLY_ACTIVE_PATHS = 0x00000002
        DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO = 9

        class LUID(ctypes.Structure):
            _fields_ = [("LowPart", wintypes.DWORD), ("HighPart", wintypes.LONG)]

        class DISPLAYCONFIG_DEVICE_INFO_HEADER(ctypes.Structure):
            _fields_ = [
                ("type", wintypes.UINT),
                ("size", wintypes.UINT),
                ("adapterId", LUID),
                ("id", wintypes.UINT),
            ]

        class DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO(ctypes.Structure):
            _fields_ = [
                ("header", DISPLAYCONFIG_DEVICE_INFO_HEADER),
                ("value", wintypes.UINT),  # bit 0: advancedColorSupported, bit 1: advancedColorEnabled
            ]

        # DISPLAYCONFIG_PATH_INFO 구조체 정의 (ctypes.sizeof로 안전한 크기 계산)
        class DISPLAYCONFIG_SOURCE_INFO(ctypes.Structure):
            _fields_ = [
                ("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("statusFlags", wintypes.UINT),
            ]

        class DISPLAYCONFIG_TARGET_INFO(ctypes.Structure):
            _fields_ = [
                ("adapterId", LUID),
                ("id", wintypes.UINT),
                ("modeInfoIdx", wintypes.UINT),
                ("outputTechnology", wintypes.UINT),
                ("rotation", wintypes.UINT),
                ("scaling", wintypes.UINT),
                ("refreshRate_numerator", wintypes.UINT),
                ("refreshRate_denominator", wintypes.UINT),
                ("scanLineOrdering", wintypes.UINT),
                ("targetAvailable", wintypes.BOOL),
                ("statusFlags", wintypes.UINT),
            ]

        class DISPLAYCONFIG_PATH_INFO(ctypes.Structure):
            _fields_ = [
                ("sourceInfo", DISPLAYCONFIG_SOURCE_INFO),
                ("targetInfo", DISPLAYCONFIG_TARGET_INFO),
                ("flags", wintypes.UINT),
            ]

        class DISPLAYCONFIG_MODE_INFO(ctypes.Structure):
            _fields_ = [
                ("infoType", wintypes.UINT),
                ("id", wintypes.UINT),
                ("adapterId", LUID),
                ("modeInfo", ctypes.c_byte * 48),  # union: targetMode/sourceMode
            ]

        num_path = wintypes.UINT()
        num_mode = wintypes.UINT()
        ret = ctypes.windll.user32.GetDisplayConfigBufferSizes(
            QDC_ONLY_ACTIVE_PATHS, ctypes.byref(num_path), ctypes.byref(num_mode)
        )
        if ret != 0 or num_path.value == 0:
            return False

        path_array = (DISPLAYCONFIG_PATH_INFO * num_path.value)()
        mode_array = (DISPLAYCONFIG_MODE_INFO * num_mode.value)()

        ret = ctypes.windll.user32.QueryDisplayConfig(
            QDC_ONLY_ACTIVE_PATHS,
            ctypes.byref(num_path),
            path_array,
            ctypes.byref(num_mode),
            mode_array,
            None,
        )
        if ret != 0:
            return False

        # 첫 번째 경로(주 모니터)의 target에 대해 Advanced Color 조회
        first_path = path_array[0]
        adapter_low = first_path.targetInfo.adapterId.LowPart
        adapter_high = first_path.targetInfo.adapterId.HighPart
        target_id = first_path.targetInfo.id

        info = DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO()
        info.header.type = DISPLAYCONFIG_DEVICE_INFO_GET_ADVANCED_COLOR_INFO
        info.header.size = ctypes.sizeof(DISPLAYCONFIG_GET_ADVANCED_COLOR_INFO)
        info.header.adapterId.LowPart = adapter_low
        info.header.adapterId.HighPart = adapter_high
        info.header.id = target_id

        ret = ctypes.windll.user32.DisplayConfigGetDeviceInfo(ctypes.byref(info))
        if ret != 0:
            return False
        # bit 1 = advancedColorEnabled (HDR on)
        return bool(info.value & 2)

    except Exception as e:
        logger.debug("HDR detection failed: %s", e)
        return False


def is_hdr_active(use_cache: bool = True) -> bool:
    """
    주 모니터 HDR 활성화 여부.
    Windows에서만 동작하며, 캐시로 2초간 재사용 가능.
    """
    global _hdr_active_cached, _hdr_cache_time
    import time
    now = time.time()
    if use_cache and _hdr_active_cached is not None and (now - _hdr_cache_time) < _HDR_CACHE_SEC:
        return _hdr_active_cached
    out = _is_hdr_active_win32()
    _hdr_active_cached = out
    _hdr_cache_time = now
    return out


def clear_hdr_cache():
    """HDR 캐시 무효화 (설정 변경 시 호출)"""
    global _hdr_active_cached
    _hdr_active_cached = None


# sRGB OETF: 선형 [0,1] -> sRGB [0,1] (IEC 61966-2-1)
_LINEAR_TO_SRGB_THRESHOLD = 0.0031308
_LINEAR_TO_SRGB_LOW_SCALE = 12.92
_LINEAR_TO_SRGB_GAMMA = 1.0 / 2.4
_LINEAR_TO_SRGB_HIGH_A = 1.055
_LINEAR_TO_SRGB_HIGH_B = 0.055

# PQ (ST.2084) EOTF 역변환: PQ 인코딩 [0,1] -> 선형 휘도 [0, 10000] nits (ITU-R BT.2100)
_PQ_M1 = 2610.0 / 16384.0
_PQ_M2 = 2523.0 / 128.0
_PQ_C1 = 3424.0 / 4096.0
_PQ_C2 = 2413.0 / 128.0
_PQ_C3 = 2392.0 / 128.0
_PQ_MAX_NITS = 10000.0

# BT.2020 (linear) -> BT.709/sRGB (linear) 3x3 행렬 (RGB 채널 순)
# R_709 = 1.6605*R_2020 - 0.5876*G_2020 - 0.0728*B_2020 ...
_MAT_BT2020_TO_BT709 = np.array([
    [1.6605, -0.5876, -0.0728],
    [-0.1246, 1.1329, -0.0083],
    [-0.0182, -0.1006, 1.1187],
], dtype=np.float32)


def _pq_to_linear(v: np.ndarray, xp) -> np.ndarray:
    """PQ(ST.2084) 인코딩 [0,1] -> 선형 휘도 [0, 10000] nits. v는 0~1."""
    v = xp.clip(v.astype(xp.float32), 1e-7, 1.0)
    v_pow = xp.power(v, 1.0 / _PQ_M2)
    num = xp.maximum(v_pow - _PQ_C1, 0.0)
    den = _PQ_C2 - _PQ_C3 * v_pow
    den = xp.maximum(den, 1e-10)
    l_linear = xp.power(num / den, 1.0 / _PQ_M1)
    return l_linear * _PQ_MAX_NITS


def _linear_bt2020_to_bt709(rgb: np.ndarray, xp) -> np.ndarray:
    """Linear BT.2020 RGB (H,W,3) -> Linear BT.709 RGB. rgb는 (...,3) 마지막 축 RGB."""
    # (H,W,3) @ (3,3).T -> (H,W,3)
    mat = xp.asarray(_MAT_BT2020_TO_BT709, dtype=xp.float32)
    return xp.dot(rgb, mat.T)


def linear_to_srgb(linear: np.ndarray) -> np.ndarray:
    """
    선형 광도 [0,1] (또는 HDR 시 >1) 를 sRGB [0,1]로 인코딩.
    입력: float 배열, 채널별 선형값. 출력: 동일 shape float [0,1].
    """
    xp = _get_array_module()
    L = xp.asarray(linear, dtype=xp.float32)
    # HDR 구간은 Reinhard로 압축 후 sRGB (선택)
    L = xp.minimum(L, 1.0)  # 먼저 1 초과만 clamp (또는 2*L/(1+L) 톤매핑 가능)
    low = L <= _LINEAR_TO_SRGB_THRESHOLD
    high = ~low
    out = xp.empty_like(L)
    out[low] = L[low] * _LINEAR_TO_SRGB_LOW_SCALE
    out[high] = _LINEAR_TO_SRGB_HIGH_A * (L[high] ** _LINEAR_TO_SRGB_GAMMA) - _LINEAR_TO_SRGB_HIGH_B
    return xp.clip(out, 0.0, 1.0)


# OBS Studio 방식: SDR white level (보통 80 nits)
_HDR_SDR_WHITE_NITS = 80.0
_HDR_MAX_NITS = 10000.0
_HDR_SDR_WHITE_SCALE = _HDR_SDR_WHITE_NITS / _HDR_MAX_NITS  # 0.008


def _st2084_to_linear_simple(rgb: np.ndarray, xp) -> np.ndarray:
    """ST.2084 (PQ) → 선형 변환 (간단 버전, OBS color.effect 기반)"""
    # OBS의 st2084_to_linear_channel 구현
    c = xp.power(xp.abs(rgb), 1.0 / 78.84375)
    linear = xp.power(xp.abs(xp.maximum(c - 0.8359375, 0.0) / xp.maximum(18.8515625 - 18.6875 * c, 1e-10)), 1.0 / 0.1593017578)
    return linear * _HDR_MAX_NITS  # nits로 변환


def analyze_dxcam_output(frame: np.ndarray) -> dict:
    """DXCam 출력 형식 자동 진단 (픽셀값 통계 분석)"""
    if frame is None or frame.size == 0:
        return {'diagnosis': 'invalid'}
    
    stats = {
        'mean': float(np.mean(frame)),
        'median': float(np.median(frame)),
        'max': int(np.max(frame)),
        'min': int(np.min(frame)),
        'std': float(np.std(frame)),
        'bright_pixels_pct': float(np.sum(frame > 200) / frame.size * 100),
        'dark_pixels_pct': float(np.sum(frame < 50) / frame.size * 100),
        'saturated_pct': float(np.sum(frame >= 255) / frame.size * 100),
    }
    
    # 진단 로직
    if stats['mean'] > 180 and stats['bright_pixels_pct'] > 50:
        # 평균 매우 밝고 밝은 픽셀 많음 → 선형 데이터 가능성
        stats['diagnosis'] = 'over_bright_linear'
    elif stats['mean'] > 150 and stats['saturated_pct'] < 5:
        # 밝지만 포화 안 됨 → 감마 보정 필요
        stats['diagnosis'] = 'needs_gamma'
    elif 100 <= stats['mean'] <= 150 and stats['max'] == 255:
        # 정상 범위, 다이나믹 레인지 충분 → sRGB 가능성
        stats['diagnosis'] = 'likely_srgb'
    else:
        stats['diagnosis'] = 'unknown'
    
    logger.info(f"[DXCam Analysis] mean={stats['mean']:.1f}, max={stats['max']}, bright_pct={stats['bright_pixels_pct']:.1f}%, diagnosis={stats['diagnosis']}")
    return stats


import threading as _hdr_threading
_hdr_mode_lock = _hdr_threading.Lock()


def reset_hdr_mode():
    """HDR 모드 캐시 리셋 (녹화 시작 시 호출하여 모드 재평가)"""
    with _hdr_mode_lock:
        if hasattr(apply_hdr_correction_adaptive, '_mode'):
            del apply_hdr_correction_adaptive._mode


def apply_hdr_correction_adaptive(frame: np.ndarray) -> np.ndarray:
    """
    DXCam 출력 형식을 자동 감지하여 적절한 보정 적용 (적응형).
    첫 프레임 분석 후 최적 모드 선택, 이후 캐시 사용.

    입력/출력: BGR, uint8, shape (H, W, 3).
    """
    if frame is None or frame.size == 0 or frame.dtype != np.uint8:
        return frame

    # 첫 프레임만 분석 (캐시, 스레드 안전) — reset_hdr_mode()로 재평가 가능
    if not hasattr(apply_hdr_correction_adaptive, '_mode'):
        with _hdr_mode_lock:
            if not hasattr(apply_hdr_correction_adaptive, '_mode'):
                stats = analyze_dxcam_output(frame)
                diagnosis = stats.get('diagnosis', 'unknown')

                if diagnosis == 'over_bright_linear':
                    apply_hdr_correction_adaptive._mode = 'linear_to_srgb'
                elif diagnosis == 'needs_gamma':
                    apply_hdr_correction_adaptive._mode = 'gamma_down'
                elif diagnosis == 'likely_srgb':
                    apply_hdr_correction_adaptive._mode = 'passthrough'
                else:
                    # 기본: OBS 방식
                    apply_hdr_correction_adaptive._mode = 'obs'

                logger.info(f"[HDR] Auto-detected mode: {apply_hdr_correction_adaptive._mode} (diagnosis: {diagnosis})")

    mode = apply_hdr_correction_adaptive._mode
    
    # 모드별 처리
    if mode == 'passthrough':
        return frame
    
    elif mode == 'linear_to_srgb':
        # 선형 → sRGB 감마 (2.2)
        try:
            v = frame.astype(np.float32) / 255.0
            corrected = np.power(v, 1.0/2.2)
            return (corrected * 255).clip(0, 255).astype(np.uint8)
        except Exception as e:
            logger.debug(f"linear_to_srgb failed: {e}")
            return frame
    
    elif mode == 'gamma_down':
        # 감마 다운 (밝기 감소)
        try:
            v = frame.astype(np.float32) / 255.0
            corrected = np.power(v, 1.8)
            return (corrected * 255).clip(0, 255).astype(np.uint8)
        except Exception as e:
            logger.debug(f"gamma_down failed: {e}")
            return frame
    
    elif mode == 'obs':
        # 기존 OBS 방식
        return apply_hdr_correction_obs(frame)
    
    else:
        # 알 수 없는 모드
        return frame


def apply_hdr_correction_obs(frame: np.ndarray) -> np.ndarray:
    """
    HDR/선형 캡처 프레임을 SDR sRGB로 변환 (OBS Studio 방식, GPU 가속).
    DXGI Desktop Duplication API는 HDR에서 PQ 인코딩 또는 선형 스케일 문제가 있을 수 있음.
    OBS 방식: PQ → 선형 (EETF) → BT.2020 → BT.709 → 톤매핑 → sRGB
    
    입력/출력: BGR, uint8, shape (H, W, 3).
    """
    if frame is None or frame.size == 0 or frame.dtype != np.uint8:
        return frame
    
    # 작은 프레임은 CPU 사용 (GPU 오버헤드 방지)
    h, w = frame.shape[:2]
    use_gpu = (h * w) >= 640 * 480  # 640x480 이상만 GPU 사용
    
    try:
        xp = _get_array_module() if use_gpu else np
        v = xp.asarray(frame, dtype=xp.float32) / 255.0

        # 선형 입력 가정: OBS 방식 - BT.2020 가정 → BT.709 → 톤매핑 → sRGB
        # DXGI가 선형 데이터를 반환하지만 스케일이 잘못되었을 수 있음
        # BGR → RGB
        rgb_linear = xp.stack([v[:, :, 2], v[:, :, 1], v[:, :, 0]], axis=-1)

        # 스케일 다운 (HDR 선형 값이 0-1 범위를 초과할 수 있음)
        # OBS는 sdr_white_nits_over_maximum을 곱함 (80/10000 = 0.008)
        rgb_linear = rgb_linear * _HDR_SDR_WHITE_SCALE

        # BT.2020 → BT.709 (색역 변환, OBS는 항상 적용)
        rgb_709 = _linear_bt2020_to_bt709(rgb_linear, xp)

        # 톤매핑: Reinhard (OBS 방식)
        rgb_709 = rgb_709 / (1.0 + rgb_709)
        rgb_709 = xp.clip(rgb_709, 0.0, 1.0)

        # 선형 → sRGB OETF
        srgb = linear_to_srgb(rgb_709)

        # RGB → BGR
        out_bgr = xp.stack([srgb[:, :, 2], srgb[:, :, 1], srgb[:, :, 0]], axis=-1)

        out = (out_bgr * 255.0).clip(0, 255).astype(np.uint8)
        if hasattr(out, "get"):
            out = out.get()
        return out
    except Exception as e:
        logger.debug("HDR correction failed: %s", e)
        return frame


def _get_array_module():
    """CuPy 사용 가능 시 cupy, 아니면 numpy 반환"""
    try:
        from .gpu_utils import get_array_module
        return get_array_module()
    except ImportError:
        return np
