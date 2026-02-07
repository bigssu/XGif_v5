"""
AI Effects - AI 기반 이미지 처리 효과
배경 제거, 노이즈 제거, 업스케일링 등

선택적 의존성:
- scikit-image: 고급 노이즈 제거
"""
from __future__ import annotations
from typing import Optional, Tuple, Callable, List
from PIL import Image
import numpy as np
import os

from ..utils.logger import get_logger

_logger = get_logger()

# 선택적 의존성 확인
_skimage_available = False

try:
    from skimage import restoration
    from skimage import filters as sk_filters
    from skimage.morphology import disk
    _skimage_available = True
    _logger.info("scikit-image 사용 가능 - 고급 노이즈 제거 지원")
except ImportError:
    _logger.info("scikit-image 없음 - 기본 노이즈 제거만 사용")

# cuCIM (GPU scikit-image) 확인
_cucim_available = False
try:
    import cucim.skimage.filters
    import cucim.skimage.restoration
    _cucim_available = True
    _logger.debug("cuCIM 사용 가능 - GPU 가속 이미지 처리 지원")
except ImportError:
    # 선택적 의존성이므로 DEBUG 레벨로만 로깅 (사용자가 실제로 사용할 때는 다른 메시지 출력)
    _logger.debug("cuCIM 없음 - 선택적 의존성 (CUDA 12.x 필요)")


def is_skimage_available() -> bool:
    """scikit-image 사용 가능 여부"""
    return _skimage_available


def is_ai_upscale_available() -> bool:
    """AI 업스케일링 사용 가능 여부 (어떤 백엔드든)"""
    return False  # 모든 AI 업스케일러 제거됨


def is_cucim_available() -> bool:
    """cuCIM (GPU scikit-image) 사용 가능 여부"""
    return _cucim_available


def get_ai_features_info() -> dict:
    """AI 기능 정보 반환"""
    return {
        'advanced_denoising': _skimage_available,
        'gpu_denoising': _cucim_available,
        'ai_upscaling': is_ai_upscale_available(),
        'cucim': _cucim_available,
    }


def get_available_upscalers() -> List[str]:
    """사용 가능한 업스케일러 목록 반환"""
    return ['lanczos']  # 기본 (항상 사용 가능)


# === 노이즈 제거 ===

def denoise_bilateral(image: Image.Image, 
                      d: int = 9,
                      sigma_color: float = 75,
                      sigma_space: float = 75) -> Image.Image:
    """양방향 필터를 사용한 노이즈 제거 (OpenCV 기반)
    
    에지를 보존하면서 노이즈를 제거합니다.
    
    Args:
        image: 원본 이미지
        d: 필터 크기 (픽셀 이웃 직경)
        sigma_color: 색상 공간 시그마
        sigma_space: 좌표 공간 시그마
    
    Returns:
        노이즈가 제거된 이미지
    """
    try:
        import cv2
        
        # PIL to OpenCV
        img_array = np.array(image)
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            bgr = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2BGR)
            alpha = img_array[:, :, 3]
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # 양방향 필터 적용
        denoised = cv2.bilateralFilter(bgr, d, sigma_color, sigma_space)
        
        # OpenCV to PIL
        if has_alpha:
            rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
            result = np.dstack([rgb, alpha])
            return Image.fromarray(result, 'RGBA')
        else:
            rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb, 'RGB')
            
    except ImportError:
        _logger.warning("OpenCV 없음 - 기본 블러 사용")
        from PIL import ImageFilter
        return image.filter(ImageFilter.GaussianBlur(radius=1))


def denoise_nlmeans(image: Image.Image,
                    h: float = 10,
                    template_window_size: int = 7,
                    search_window_size: int = 21) -> Image.Image:
    """Non-local Means 노이즈 제거 (고품질)
    
    가장 효과적인 노이즈 제거 알고리즘 중 하나입니다.
    처리 시간이 오래 걸립니다.
    
    Args:
        image: 원본 이미지
        h: 필터 강도 (높을수록 노이즈 제거 강함, 디테일 손실)
        template_window_size: 템플릿 패치 크기 (홀수)
        search_window_size: 검색 윈도우 크기 (홀수)
    
    Returns:
        노이즈가 제거된 이미지
    """
    try:
        import cv2
        
        img_array = np.array(image)
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            bgr = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2BGR)
            alpha = img_array[:, :, 3]
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # NLMeans 노이즈 제거
        denoised = cv2.fastNlMeansDenoisingColored(
            bgr, None, h, h, template_window_size, search_window_size
        )
        
        if has_alpha:
            rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
            result = np.dstack([rgb, alpha])
            return Image.fromarray(result, 'RGBA')
        else:
            rgb = cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb, 'RGB')
            
    except ImportError:
        return denoise_bilateral(image)


def denoise_wavelet(image: Image.Image, 
                    sigma: Optional[float] = None,
                    mode: str = 'soft') -> Image.Image:
    """웨이블릿 기반 노이즈 제거 (scikit-image)
    
    Args:
        image: 원본 이미지
        sigma: 노이즈 표준편차 (None이면 자동 추정)
        mode: 'soft' 또는 'hard' 임계값
    
    Returns:
        노이즈가 제거된 이미지
    """
    if not _skimage_available:
        return denoise_bilateral(image)
    
    try:
        from skimage.restoration import denoise_wavelet as sk_denoise_wavelet
        
        img_array = np.array(image).astype(np.float32) / 255.0
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]
            
            denoised = sk_denoise_wavelet(
                rgb, sigma=sigma, mode=mode, 
                channel_axis=2, rescale_sigma=True
            )
            
            result = np.dstack([denoised, alpha])
            result = (np.clip(result, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, 'RGBA')
        else:
            denoised = sk_denoise_wavelet(
                img_array, sigma=sigma, mode=mode,
                channel_axis=2, rescale_sigma=True
            )
            result = (np.clip(denoised, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, image.mode)
            
    except Exception as e:
        _logger.warning(f"웨이블릿 노이즈 제거 실패: {e}")
        return denoise_bilateral(image)


# === GPU 가속 노이즈 제거 (cuCIM) ===

def denoise_bilateral_gpu(image: Image.Image,
                          sigma_color: float = 0.05,
                          sigma_spatial: float = 15) -> Image.Image:
    """GPU 가속 양방향 필터 노이즈 제거 (cuCIM)
    
    CPU 대비 10-100배 빠른 노이즈 제거를 제공합니다.
    
    Args:
        image: 원본 이미지
        sigma_color: 색상 공간 시그마 (0.0~1.0 정규화)
        sigma_spatial: 공간 시그마 (픽셀 단위)
    
    Returns:
        노이즈가 제거된 이미지
    """
    if not _cucim_available:
        _logger.info("cuCIM 없음 - CPU 폴백 사용")
        return denoise_bilateral(image, sigma_color=int(sigma_color * 255), 
                                  sigma_space=sigma_spatial)
    
    try:
        import cupy as cp
        from cucim.skimage.restoration import denoise_bilateral as cucim_bilateral
        
        img_array = np.array(image).astype(np.float32) / 255.0
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]
            
            # GPU로 전송
            rgb_gpu = cp.asarray(rgb)
            
            # GPU에서 노이즈 제거
            denoised_gpu = cucim_bilateral(
                rgb_gpu, 
                sigma_color=sigma_color,
                sigma_spatial=sigma_spatial,
                channel_axis=2
            )
            
            # CPU로 복사
            denoised = cp.asnumpy(denoised_gpu)
            
            result = np.dstack([denoised, alpha])
            result = (np.clip(result, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, 'RGBA')
        else:
            img_gpu = cp.asarray(img_array)
            denoised_gpu = cucim_bilateral(
                img_gpu,
                sigma_color=sigma_color,
                sigma_spatial=sigma_spatial,
                channel_axis=2
            )
            denoised = cp.asnumpy(denoised_gpu)
            result = (np.clip(denoised, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, image.mode)
            
    except Exception as e:
        _logger.warning(f"GPU 양방향 필터 실패: {e}")
        return denoise_bilateral(image)


def denoise_gaussian_gpu(image: Image.Image, sigma: float = 1.0) -> Image.Image:
    """GPU 가속 가우시안 노이즈 제거 (cuCIM)
    
    Args:
        image: 원본 이미지
        sigma: 가우시안 시그마
    
    Returns:
        노이즈가 제거된 이미지
    """
    if not _cucim_available:
        _logger.info("cuCIM 없음 - CPU 폴백 사용")
        from PIL import ImageFilter
        return image.filter(ImageFilter.GaussianBlur(radius=sigma))
    
    try:
        import cupy as cp
        from cucim.skimage.filters import gaussian as cucim_gaussian
        
        img_array = np.array(image).astype(np.float32) / 255.0
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]
            
            rgb_gpu = cp.asarray(rgb)
            denoised_gpu = cucim_gaussian(rgb_gpu, sigma=sigma, channel_axis=2)
            denoised = cp.asnumpy(denoised_gpu)
            
            result = np.dstack([denoised, alpha])
            result = (np.clip(result, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, 'RGBA')
        else:
            img_gpu = cp.asarray(img_array)
            denoised_gpu = cucim_gaussian(img_gpu, sigma=sigma, channel_axis=2)
            denoised = cp.asnumpy(denoised_gpu)
            result = (np.clip(denoised, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, image.mode)
            
    except Exception as e:
        _logger.warning(f"GPU 가우시안 필터 실패: {e}")
        from PIL import ImageFilter
        return image.filter(ImageFilter.GaussianBlur(radius=sigma))


def denoise_median_gpu(image: Image.Image, size: int = 3) -> Image.Image:
    """GPU 가속 미디언 필터 노이즈 제거 (cuCIM)
    
    솔트앤페퍼 노이즈에 효과적입니다.
    
    Args:
        image: 원본 이미지
        size: 필터 크기 (홀수)
    
    Returns:
        노이즈가 제거된 이미지
    """
    if not _cucim_available:
        _logger.info("cuCIM 없음 - CPU 폴백 사용")
        from PIL import ImageFilter
        return image.filter(ImageFilter.MedianFilter(size=size))
    
    try:
        import cupy as cp
        from cucim.skimage.filters import median as cucim_median
        from cucim.skimage.morphology import disk as cucim_disk
        
        img_array = np.array(image).astype(np.float32) / 255.0
        has_alpha = image.mode == 'RGBA'
        
        # footprint 생성 (GPU에서)
        footprint = cucim_disk(size // 2)
        
        if has_alpha:
            rgb = img_array[:, :, :3]
            alpha = img_array[:, :, 3]
            
            # 채널별 미디언 적용
            denoised_channels = []
            for c in range(3):
                channel_gpu = cp.asarray(rgb[:, :, c])
                filtered_gpu = cucim_median(channel_gpu, footprint=footprint)
                denoised_channels.append(cp.asnumpy(filtered_gpu))
            
            denoised = np.stack(denoised_channels, axis=2)
            result = np.dstack([denoised, alpha])
            result = (np.clip(result, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, 'RGBA')
        else:
            # 채널별 처리
            denoised_channels = []
            for c in range(img_array.shape[2] if len(img_array.shape) > 2 else 1):
                if len(img_array.shape) > 2:
                    channel = img_array[:, :, c]
                else:
                    channel = img_array
                channel_gpu = cp.asarray(channel)
                filtered_gpu = cucim_median(channel_gpu, footprint=footprint)
                denoised_channels.append(cp.asnumpy(filtered_gpu))
            
            if len(denoised_channels) == 1:
                denoised = denoised_channels[0]
            else:
                denoised = np.stack(denoised_channels, axis=2)
            
            result = (np.clip(denoised, 0, 1) * 255).astype(np.uint8)
            return Image.fromarray(result, image.mode)
            
    except Exception as e:
        _logger.warning(f"GPU 미디언 필터 실패: {e}")
        from PIL import ImageFilter
        return image.filter(ImageFilter.MedianFilter(size=size))


def denoise_auto_gpu(image: Image.Image, strength: str = 'medium') -> Image.Image:
    """자동 GPU 노이즈 제거 (최적 알고리즘 선택)
    
    cuCIM이 설치된 경우 GPU를 사용하고, 그렇지 않으면 CPU 폴백합니다.
    
    Args:
        image: 원본 이미지
        strength: 노이즈 제거 강도 ('light', 'medium', 'strong')
    
    Returns:
        노이즈가 제거된 이미지
    """
    # 강도에 따른 파라미터 설정
    params = {
        'light': {'sigma_color': 0.03, 'sigma_spatial': 10},
        'medium': {'sigma_color': 0.05, 'sigma_spatial': 15},
        'strong': {'sigma_color': 0.08, 'sigma_spatial': 20},
    }
    
    p = params.get(strength, params['medium'])
    
    if _cucim_available:
        return denoise_bilateral_gpu(image, **p)
    else:
        # CPU 폴백
        return denoise_bilateral(
            image,
            sigma_color=int(p['sigma_color'] * 255 * 3),  # OpenCV 스케일
            sigma_space=p['sigma_spatial']
        )


def denoise_batch_gpu(images: List[Image.Image],
                       method: str = 'bilateral',
                       progress_callback: Optional[Callable[[int, int], None]] = None,
                       **kwargs) -> List[Image.Image]:
    """여러 이미지 일괄 GPU 노이즈 제거
    
    Args:
        images: 이미지 목록
        method: 노이즈 제거 방법 ('bilateral', 'gaussian', 'median', 'auto')
        progress_callback: 진행률 콜백
        **kwargs: 메서드별 추가 인자
    
    Returns:
        노이즈가 제거된 이미지 목록
    """
    methods = {
        'bilateral': denoise_bilateral_gpu,
        'gaussian': denoise_gaussian_gpu,
        'median': denoise_median_gpu,
        'auto': denoise_auto_gpu,
    }
    
    denoise_func = methods.get(method, denoise_auto_gpu)
    
    results = []
    total = len(images)
    
    for i, image in enumerate(images):
        result = denoise_func(image, **kwargs)
        results.append(result)
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    return results


# === 업스케일링 ===

def upscale_lanczos(image: Image.Image, scale: float = 2.0) -> Image.Image:
    """Lanczos 업스케일링 (기본)
    
    Args:
        image: 원본 이미지
        scale: 확대 배율
    
    Returns:
        확대된 이미지
    """
    new_width = int(image.width * scale)
    new_height = int(image.height * scale)
    return image.resize((new_width, new_height), Image.Resampling.LANCZOS)


# === 통합 업스케일 함수 ===

def upscale_auto(image: Image.Image, scale: int = 2,
                  prefer: str = 'best') -> Image.Image:
    """자동 업스케일링 (최적 백엔드 자동 선택)
    
    설치된 라이브러리 중 최적의 백엔드를 자동으로 선택합니다.
    
    Args:
        image: 원본 이미지
        scale: 확대 배율
        prefer: 선호 방식 (현재는 모두 Lanczos 사용)
            - 'best': Lanczos 사용
            - 'fast': Lanczos 사용
            - 'lanczos': Lanczos만 사용
    
    Returns:
        업스케일된 이미지
    """
    # 모든 AI 업스케일러가 제거되어 항상 Lanczos 사용
    return upscale_lanczos(image, scale)


def upscale_batch(images: List[Image.Image], scale: int = 2,
                   method: str = 'auto',
                   progress_callback: Optional[Callable[[int, int], None]] = None
                   ) -> List[Image.Image]:
    """여러 이미지 일괄 업스케일링
    
    Args:
        images: 이미지 목록
        scale: 확대 배율
        method: 업스케일 방법 ('auto', 'lanczos') - 현재는 모두 Lanczos 사용
        progress_callback: 진행률 콜백
    
    Returns:
        업스케일된 이미지 목록
    """
    # 모든 AI 업스케일러가 제거되어 항상 Lanczos 사용
    upscale_func = lambda img: upscale_lanczos(img, scale)
    
    results = []
    total = len(images)
    
    for i, image in enumerate(images):
        result = upscale_func(image)
        results.append(result)
        
        if progress_callback:
            progress_callback(i + 1, total)
    
    return results


# === 히스토그램 평활화 ===

def equalize_histogram(image: Image.Image, 
                       adaptive: bool = True,
                       clip_limit: float = 2.0,
                       tile_size: Tuple[int, int] = (8, 8)) -> Image.Image:
    """히스토그램 평활화 (대비 개선)
    
    Args:
        image: 원본 이미지
        adaptive: True면 CLAHE (적응형 평활화) 사용
        clip_limit: CLAHE 클리핑 한계
        tile_size: CLAHE 타일 크기
    
    Returns:
        대비가 개선된 이미지
    """
    try:
        import cv2
        
        img_array = np.array(image)
        has_alpha = image.mode == 'RGBA'
        
        if has_alpha:
            bgr = cv2.cvtColor(img_array[:, :, :3], cv2.COLOR_RGB2BGR)
            alpha = img_array[:, :, 3]
        else:
            bgr = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # LAB 색공간으로 변환
        lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
        l, a, b = cv2.split(lab)
        
        if adaptive:
            # CLAHE 적용
            clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=tile_size)
            l = clahe.apply(l)
        else:
            # 일반 히스토그램 평활화
            l = cv2.equalizeHist(l)
        
        # 다시 합치기
        lab = cv2.merge([l, a, b])
        result_bgr = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
        
        if has_alpha:
            rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
            result = np.dstack([rgb, alpha])
            return Image.fromarray(result, 'RGBA')
        else:
            rgb = cv2.cvtColor(result_bgr, cv2.COLOR_BGR2RGB)
            return Image.fromarray(rgb, 'RGB')
            
    except ImportError:
        # OpenCV 없으면 PIL 자동 대비 사용
        from PIL import ImageOps
        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            rgb = Image.merge('RGB', (r, g, b))
            rgb = ImageOps.autocontrast(rgb)
            r, g, b = rgb.split()
            return Image.merge('RGBA', (r, g, b, a))
        return ImageOps.autocontrast(image)


# === 유틸리티 ===

def apply_ai_effect(image: Image.Image, effect: str, **kwargs) -> Image.Image:
    """AI 효과 적용
    
    Args:
        image: 원본 이미지
        effect: 효과 이름
            - 'denoise_bilateral': 양방향 노이즈 제거 (CPU)
            - 'denoise_nlmeans': NLMeans 노이즈 제거
            - 'denoise_wavelet': 웨이블릿 노이즈 제거
            - 'denoise_bilateral_gpu': GPU 양방향 노이즈 제거 (cuCIM)
            - 'denoise_gaussian_gpu': GPU 가우시안 노이즈 제거
            - 'denoise_median_gpu': GPU 미디언 노이즈 제거
            - 'denoise_auto': 자동 노이즈 제거 (GPU 우선)
            - 'upscale': 자동 업스케일링 (Lanczos 사용)
            - 'upscale_lanczos': Lanczos 업스케일링
            - 'equalize': 히스토그램 평활화
        **kwargs: 효과별 추가 인자
    
    Returns:
        처리된 이미지
    """
    effects = {
        'denoise_bilateral': denoise_bilateral,
        'denoise_nlmeans': denoise_nlmeans,
        'denoise_wavelet': denoise_wavelet,
        'denoise_bilateral_gpu': denoise_bilateral_gpu,
        'denoise_gaussian_gpu': denoise_gaussian_gpu,
        'denoise_median_gpu': denoise_median_gpu,
        'denoise_auto': denoise_auto_gpu,
        'upscale': upscale_auto,
        'upscale_lanczos': upscale_lanczos,
        'equalize': equalize_histogram,
    }
    
    if effect not in effects:
        raise ValueError(f"알 수 없는 효과: {effect}. 가능한 효과: {list(effects.keys())}")
    
    return effects[effect](image, **kwargs)
