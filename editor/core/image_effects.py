"""
ImageEffects - 이미지 효과 처리 클래스
GPU 가속 지원 (CUDA 사용 가능 시)
OpenCV 가속 지원 (opencv-python 설치 시)
"""
from PIL import Image, ImageEnhance, ImageFilter, ImageOps
import numpy as np
from typing import Tuple

from . import editor_gpu_utils as gpu_utils

# OpenCV 사용 가능 여부 확인
_cv2_available = False
try:
    import cv2
    _cv2_available = True
except ImportError:
    cv2 = None


def is_opencv_available() -> bool:
    """OpenCV 사용 가능 여부 반환"""
    return _cv2_available


def pil_to_cv2(image: Image.Image) -> np.ndarray:
    """PIL Image를 OpenCV 형식 (BGR)으로 변환"""
    if cv2 is None:
        raise ImportError("OpenCV not available")
    if image.mode == 'RGBA':
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGBA2BGRA)
    elif image.mode == 'RGB':
        return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    else:
        return np.array(image)


def cv2_to_pil(cv_image: np.ndarray, has_alpha: bool = False) -> Image.Image:
    """OpenCV 이미지를 PIL Image로 변환"""
    if cv2 is None:
        raise ImportError("OpenCV not available")
    if has_alpha:
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGRA2RGBA))
    else:
        return Image.fromarray(cv2.cvtColor(cv_image, cv2.COLOR_BGR2RGB))


class ImageEffects:
    """이미지 효과 처리 (OpenCV 가속 지원)"""

    @staticmethod
    def adjust_brightness(image: Image.Image, factor: float) -> Image.Image:
        """
        밝기 조절 (OpenCV 가속)
        factor: 0.0 (검정) ~ 1.0 (원본) ~ 2.0 (밝게)
        """
        if _cv2_available and factor != 1.0:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                # 알파 채널 분리
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                # 밝기 조절 (beta = (factor - 1) * 255)
                adjusted = cv2.convertScaleAbs(bgr, alpha=factor, beta=0)
                result = np.dstack([adjusted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                adjusted = cv2.convertScaleAbs(cv_img, alpha=factor, beta=0)
                return cv2_to_pil(adjusted)

        # Pillow 폴백
        enhancer = ImageEnhance.Brightness(image)
        return enhancer.enhance(factor)

    @staticmethod
    def adjust_contrast(image: Image.Image, factor: float) -> Image.Image:
        """
        대비 조절 (OpenCV 가속)
        factor: 0.0 (회색) ~ 1.0 (원본) ~ 2.0 (높은 대비)
        """
        if _cv2_available and factor != 1.0:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                # LAB 색공간에서 대비 조절
                lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                # CLAHE 적용
                clahe = cv2.createCLAHE(clipLimit=factor * 2.0, tileGridSize=(8, 8))
                l = clahe.apply(l)
                lab = cv2.merge([l, a, b])
                adjusted = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
                result = np.dstack([adjusted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                lab = cv2.cvtColor(cv_img, cv2.COLOR_BGR2LAB)
                l, a, b = cv2.split(lab)
                clahe = cv2.createCLAHE(clipLimit=factor * 2.0, tileGridSize=(8, 8))
                l = clahe.apply(l)
                lab = cv2.merge([l, a, b])
                adjusted = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)
                return cv2_to_pil(adjusted)

        # Pillow 폴백
        enhancer = ImageEnhance.Contrast(image)
        return enhancer.enhance(factor)

    @staticmethod
    def adjust_saturation(image: Image.Image, factor: float) -> Image.Image:
        """
        채도 조절 (OpenCV 가속)
        factor: 0.0 (흑백) ~ 1.0 (원본) ~ 2.0 (선명)
        """
        if _cv2_available and factor != 1.0:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV).astype(np.float32)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
                hsv = hsv.astype(np.uint8)
                adjusted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                result = np.dstack([adjusted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV).astype(np.float32)
                hsv[:, :, 1] = np.clip(hsv[:, :, 1] * factor, 0, 255)
                hsv = hsv.astype(np.uint8)
                adjusted = cv2.cvtColor(hsv, cv2.COLOR_HSV2BGR)
                return cv2_to_pil(adjusted)

        # Pillow 폴백
        enhancer = ImageEnhance.Color(image)
        return enhancer.enhance(factor)

    @staticmethod
    def adjust_sharpness(image: Image.Image, factor: float) -> Image.Image:
        """
        선명도 조절 (OpenCV 가속)
        factor: 0.0 (블러) ~ 1.0 (원본) ~ 2.0 (선명)
        """
        if _cv2_available and factor != 1.0:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
            else:
                bgr = cv_img

            if factor < 1.0:
                # 블러 방향
                sigma = (1.0 - factor) * 3.0
                blurred = cv2.GaussianBlur(bgr, (0, 0), sigma)
                adjusted = cv2.addWeighted(bgr, factor, blurred, 1.0 - factor, 0)
            else:
                # 샤프 방향 (언샵 마스크)
                blurred = cv2.GaussianBlur(bgr, (0, 0), 1.0)
                amount = factor - 1.0
                adjusted = cv2.addWeighted(bgr, 1.0 + amount, blurred, -amount, 0)

            if has_alpha:
                result = np.dstack([adjusted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                return cv2_to_pil(adjusted)

        # Pillow 폴백
        enhancer = ImageEnhance.Sharpness(image)
        return enhancer.enhance(factor)

    @staticmethod
    def apply_grayscale(image: Image.Image) -> Image.Image:
        """그레이스케일 변환 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
                gray_bgr = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                result = np.dstack([gray_bgr, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
                return Image.fromarray(gray)

        # Pillow 폴백
        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            gray = ImageOps.grayscale(image.convert('RGB'))
            return Image.merge('RGBA', (gray, gray, gray, a))
        return ImageOps.grayscale(image).convert(image.mode)

    @staticmethod
    def apply_sepia(image: Image.Image) -> Image.Image:
        """세피아 톤 적용 (GPU/OpenCV 가속 지원)"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # GPU 가속 우선
        img_array = np.array(image)
        result_array = gpu_utils.gpu_sepia(img_array)
        return Image.fromarray(result_array, 'RGBA')

    @staticmethod
    def apply_blur(image: Image.Image, radius: int = 2) -> Image.Image:
        """블러 효과 (OpenCV 가속 - 5배 빠름)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            # 커널 크기는 홀수여야 함
            ksize = radius * 2 + 1

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                blurred = cv2.GaussianBlur(bgr, (ksize, ksize), 0)
                result = np.dstack([blurred, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                blurred = cv2.GaussianBlur(cv_img, (ksize, ksize), 0)
                return cv2_to_pil(blurred)

        # Pillow 폴백
        return image.filter(ImageFilter.GaussianBlur(radius=radius))

    @staticmethod
    def apply_sharpen(image: Image.Image) -> Image.Image:
        """샤픈 효과 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            # 언샵 마스크 커널
            kernel = np.array([[-1, -1, -1],
                               [-1,  9, -1],
                               [-1, -1, -1]])

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                sharpened = cv2.filter2D(bgr, -1, kernel)
                result = np.dstack([sharpened, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                sharpened = cv2.filter2D(cv_img, -1, kernel)
                return cv2_to_pil(sharpened)

        # Pillow 폴백
        return image.filter(ImageFilter.SHARPEN)

    @staticmethod
    def apply_edge_enhance(image: Image.Image) -> Image.Image:
        """엣지 강조 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
            else:
                bgr = cv_img

            # 엣지 검출
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Laplacian(gray, cv2.CV_8U)
            edges_bgr = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)

            # 원본과 엣지 합성
            enhanced = cv2.addWeighted(bgr, 1.0, edges_bgr, 0.5, 0)

            if has_alpha:
                result = np.dstack([enhanced, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                return cv2_to_pil(enhanced)

        # Pillow 폴백
        return image.filter(ImageFilter.EDGE_ENHANCE)

    @staticmethod
    def apply_emboss(image: Image.Image) -> Image.Image:
        """엠보스 효과 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            # 엠보스 커널
            kernel = np.array([[-2, -1, 0],
                               [-1,  1, 1],
                               [ 0,  1, 2]])

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                embossed = cv2.filter2D(bgr, -1, kernel) + 128
                embossed = np.clip(embossed, 0, 255).astype(np.uint8)
                result = np.dstack([embossed, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                embossed = cv2.filter2D(cv_img, -1, kernel) + 128
                embossed = np.clip(embossed, 0, 255).astype(np.uint8)
                return cv2_to_pil(embossed)

        # Pillow 폴백
        return image.filter(ImageFilter.EMBOSS)

    @staticmethod
    def apply_contour(image: Image.Image) -> Image.Image:
        """윤곽선 효과 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
            else:
                bgr = cv_img

            # 캐니 엣지 검출
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            edges = cv2.Canny(gray, 100, 200)
            contour = cv2.cvtColor(255 - edges, cv2.COLOR_GRAY2BGR)

            if has_alpha:
                result = np.dstack([contour, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                return cv2_to_pil(contour)

        # Pillow 폴백
        return image.filter(ImageFilter.CONTOUR)

    @staticmethod
    def apply_invert(image: Image.Image) -> Image.Image:
        """색상 반전 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                inverted = cv2.bitwise_not(bgr)
                result = np.dstack([inverted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                inverted = cv2.bitwise_not(cv_img)
                return cv2_to_pil(inverted)

        # Pillow 폴백
        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            rgb = Image.merge('RGB', (r, g, b))
            inverted = ImageOps.invert(rgb)
            r, g, b = inverted.split()
            return Image.merge('RGBA', (r, g, b, a))
        return ImageOps.invert(image)

    @staticmethod
    def apply_posterize(image: Image.Image, bits: int = 4) -> Image.Image:
        """포스터화 효과 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            # 비트 감소를 위한 마스크 계산
            shift = 8 - bits

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                posterized = (bgr >> shift) << shift
                result = np.dstack([posterized, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                posterized = (cv_img >> shift) << shift
                return cv2_to_pil(posterized)

        # Pillow 폴백
        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            rgb = Image.merge('RGB', (r, g, b))
            posterized = ImageOps.posterize(rgb, bits)
            r, g, b = posterized.split()
            return Image.merge('RGBA', (r, g, b, a))
        return ImageOps.posterize(image, bits)

    @staticmethod
    def apply_solarize(image: Image.Image, threshold: int = 128) -> Image.Image:
        """솔라라이즈 효과 (OpenCV 가속)"""
        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                # threshold 이상인 픽셀 반전
                mask = bgr >= threshold
                solarized = bgr.copy()
                solarized[mask] = 255 - solarized[mask]
                result = np.dstack([solarized, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                mask = cv_img >= threshold
                solarized = cv_img.copy()
                solarized[mask] = 255 - solarized[mask]
                return cv2_to_pil(solarized)

        # Pillow 폴백
        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            rgb = Image.merge('RGB', (r, g, b))
            solarized = ImageOps.solarize(rgb, threshold)
            r, g, b = solarized.split()
            return Image.merge('RGBA', (r, g, b, a))
        return ImageOps.solarize(image, threshold)

    @staticmethod
    def adjust_gamma(image: Image.Image, gamma: float) -> Image.Image:
        """
        감마 조절 (OpenCV 가속)
        gamma: < 1.0 (밝게), 1.0 (원본), > 1.0 (어둡게)
        """
        # gamma가 0이거나 1이면 원본 반환
        if gamma <= 0 or gamma == 1.0:
            return image

        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)

            # 룩업 테이블 생성
            inv_gamma = 1.0 / gamma
            table = np.array([((i / 255.0) ** inv_gamma) * 255
                              for i in range(256)]).astype(np.uint8)

            if has_alpha:
                bgr = cv_img[:, :, :3]
                alpha = cv_img[:, :, 3]
                adjusted = cv2.LUT(bgr, table)
                result = np.dstack([adjusted, alpha])
                return cv2_to_pil(result, has_alpha=True)
            else:
                adjusted = cv2.LUT(cv_img, table)
                return cv2_to_pil(adjusted)

        # Pillow 폴백
        inv_gamma = 1.0 / gamma

        if image.mode == 'RGBA':
            r, g, b, a = image.split()
            lut = [int((i / 255.0) ** inv_gamma * 255) for i in range(256)]
            r = r.point(lut)
            g = g.point(lut)
            b = b.point(lut)
            return Image.merge('RGBA', (r, g, b, a))
        else:
            lut = [int((i / 255.0) ** inv_gamma * 255) for i in range(256)]
            return image.point(lut * len(image.getbands()))

    @staticmethod
    def apply_vignette(image: Image.Image, strength: float = 0.5) -> Image.Image:
        """비네트 효과 (GPU 가속 지원)"""
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # GPU 가속 사용
        img_array = np.array(image)
        result_array = gpu_utils.gpu_vignette(img_array, strength)
        return Image.fromarray(result_array, 'RGBA')

    @staticmethod
    def adjust_hue(image: Image.Image, shift: int) -> Image.Image:
        """
        색조 조절 (GPU 가속 지원)
        shift: -180 ~ 180
        """
        if image.mode != 'RGBA':
            image = image.convert('RGBA')

        # GPU 가속 사용
        img_array = np.array(image)
        result_array = gpu_utils.gpu_hue_shift(img_array, shift)
        return Image.fromarray(result_array, 'RGBA')

    @staticmethod
    def apply_mosaic(image: Image.Image, region: Tuple[int, int, int, int],
                     block_size: int = 10) -> Image.Image:
        """모자이크/검열 효과 적용 (OpenCV 가속)
        
        Args:
            image: 원본 이미지
            region: 모자이크 영역 (x1, y1, x2, y2)
            block_size: 모자이크 블록 크기 (픽셀)
        
        Returns:
            모자이크가 적용된 이미지
        """
        x1, y1, x2, y2 = region

        # 영역 유효성 검사
        x1 = max(0, min(x1, image.width))
        y1 = max(0, min(y1, image.height))
        x2 = max(0, min(x2, image.width))
        y2 = max(0, min(y2, image.height))

        if x2 <= x1 or y2 <= y1:
            return image.copy()

        w, h = x2 - x1, y2 - y1
        if w <= 0 or h <= 0:
            return image.copy()

        block_size = max(2, block_size)

        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)
            result = cv_img.copy()

            # 영역 추출
            roi = result[y1:y2, x1:x2]

            # 축소 후 확대 (픽셀화)
            small_w = max(1, w // block_size)
            small_h = max(1, h // block_size)

            small = cv2.resize(roi, (small_w, small_h), interpolation=cv2.INTER_NEAREST)
            pixelated = cv2.resize(small, (w, h), interpolation=cv2.INTER_NEAREST)

            # 결과에 붙여넣기
            result[y1:y2, x1:x2] = pixelated

            return cv2_to_pil(result, has_alpha=has_alpha)

        # Pillow 폴백
        result = image.copy()
        cropped = result.crop((x1, y1, x2, y2))

        small_w = max(1, w // block_size)
        small_h = max(1, h // block_size)

        small = cropped.resize((small_w, small_h), Image.Resampling.NEAREST)
        pixelated = small.resize((w, h), Image.Resampling.NEAREST)

        result.paste(pixelated, (x1, y1))
        return result

    @staticmethod
    def apply_mosaic_full(image: Image.Image, block_size: int = 10) -> Image.Image:
        """전체 이미지에 모자이크 효과 적용
        
        Args:
            image: 원본 이미지
            block_size: 모자이크 블록 크기 (픽셀)
        
        Returns:
            모자이크가 적용된 이미지
        """
        return ImageEffects.apply_mosaic(
            image,
            (0, 0, image.width, image.height),
            block_size
        )

    @staticmethod
    def apply_blur_region(image: Image.Image, region: Tuple[int, int, int, int],
                          radius: int = 10) -> Image.Image:
        """영역에 블러 효과 적용 (검열용, OpenCV 가속)
        
        Args:
            image: 원본 이미지
            region: 블러 영역 (x1, y1, x2, y2)
            radius: 블러 반경
        
        Returns:
            블러가 적용된 이미지
        """
        x1, y1, x2, y2 = region

        # 영역 유효성 검사
        x1 = max(0, min(x1, image.width))
        y1 = max(0, min(y1, image.height))
        x2 = max(0, min(x2, image.width))
        y2 = max(0, min(y2, image.height))

        if x2 <= x1 or y2 <= y1:
            return image.copy()

        if _cv2_available:
            has_alpha = image.mode == 'RGBA'
            cv_img = pil_to_cv2(image)
            result = cv_img.copy()

            # 영역 추출
            roi = result[y1:y2, x1:x2]

            # 가우시안 블러 (커널 크기는 홀수)
            ksize = radius * 2 + 1
            blurred = cv2.GaussianBlur(roi, (ksize, ksize), 0)

            # 결과에 붙여넣기
            result[y1:y2, x1:x2] = blurred

            return cv2_to_pil(result, has_alpha=has_alpha)

        # Pillow 폴백
        result = image.copy()
        cropped = result.crop((x1, y1, x2, y2))
        blurred = cropped.filter(ImageFilter.GaussianBlur(radius=radius))
        result.paste(blurred, (x1, y1))
        return result

    @staticmethod
    def apply_black_bar(image: Image.Image, region: Tuple[int, int, int, int],
                        color: Tuple[int, int, int] = (0, 0, 0)) -> Image.Image:
        """영역에 검정/색상 바 적용 (검열용)
        
        Args:
            image: 원본 이미지
            region: 검열 영역 (x1, y1, x2, y2)
            color: 바 색상 (R, G, B)
        
        Returns:
            검열 바가 적용된 이미지
        """
        from PIL import ImageDraw

        result = image.copy()
        if result.mode != 'RGBA':
            result = result.convert('RGBA')

        draw = ImageDraw.Draw(result)
        x1, y1, x2, y2 = region

        # RGBA 색상으로 변환
        fill_color = (*color, 255)

        draw.rectangle([x1, y1, x2, y2], fill=fill_color)

        return result

    @staticmethod
    def apply_all_effects(
        image: Image.Image,
        brightness: float = 1.0,
        contrast: float = 1.0,
        saturation: float = 1.0,
        sharpness: float = 1.0,
        gamma: float = 1.0
    ) -> Image.Image:
        """모든 기본 효과 적용"""
        result = image

        if brightness != 1.0:
            result = ImageEffects.adjust_brightness(result, brightness)

        if contrast != 1.0:
            result = ImageEffects.adjust_contrast(result, contrast)

        if saturation != 1.0:
            result = ImageEffects.adjust_saturation(result, saturation)

        if sharpness != 1.0:
            result = ImageEffects.adjust_sharpness(result, sharpness)

        if gamma != 1.0:
            result = ImageEffects.adjust_gamma(result, gamma)

        return result
