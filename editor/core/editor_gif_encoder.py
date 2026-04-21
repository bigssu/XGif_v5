"""
GifEncoder - GIF 파일 인코딩
pygifsicle을 사용한 GIF 최적화 지원
"""
from __future__ import annotations
from typing import Optional
from pathlib import Path
from dataclasses import dataclass
from enum import Enum
from PIL import Image
import io
import shutil

from .frame import Frame
from .frame_collection import FrameCollection
from ..utils.logger import get_logger

# 로거
_logger = get_logger()

# gifsicle 사용 가능 여부 확인
_gifsicle_available = False
_gifsicle_path = None

try:
    # pygifsicle 사용
    import pygifsicle
    _gifsicle_available = True
    _logger.info("pygifsicle 사용 가능 - GIF 최적화 지원")
except ImportError:
    # gifsicle CLI 직접 확인
    _gifsicle_path = shutil.which("gifsicle")
    if _gifsicle_path:
        _gifsicle_available = True
        _logger.info(f"gifsicle CLI 발견: {_gifsicle_path}")
    else:
        _logger.info("pygifsicle/gifsicle 없음 - GIF 최적화 비활성화")


def is_gifsicle_available() -> bool:
    """gifsicle 사용 가능 여부 반환"""
    return _gifsicle_available


class QuantizationMethod(Enum):
    """양자화 방법"""
    ADAPTIVE = "adaptive"  # PIL 기본 (ADAPTIVE)
    MEDIANCUT = "mediancut"  # Median Cut
    MAXCOVERAGE = "maxcoverage"  # Maximum Coverage
    FASTOCTREE = "fastoctree"  # Fast Octree
    LIBIMAGEQUANT = "libimagequant"  # libimagequant (LIQ)
    # NeuQuant는 별도 구현 필요


@dataclass
class EncoderSettings:
    """인코딩 설정"""
    colors: int = 256                    # 색상 수 (2-256)
    dithering: bool = True               # 디더링 사용
    loop_count: int = 0                  # 반복 횟수 (0 = 무한)
    optimize: bool = True                # 최적화
    quality: int = 85                    # 품질 (1-100, 높을수록 좋음)
    quantization: QuantizationMethod = QuantizationMethod.ADAPTIVE

    # gifsicle 최적화 옵션
    use_gifsicle: bool = True            # gifsicle 최적화 사용 여부
    lossy_level: int = 0                 # lossy 압축 레벨 (0=비활성화, 30-200 권장)
    optimization_level: int = 3          # 최적화 레벨 (1=빠름, 2=보통, 3=최대)


@dataclass
class SaveResult:
    """저장 결과"""
    success: bool = False
    error_message: str = ""
    file_size: int = 0

    @classmethod
    def error(cls, message: str) -> 'SaveResult':
        return cls(success=False, error_message=message)

    @classmethod
    def ok(cls, file_size: int = 0) -> 'SaveResult':
        return cls(success=True, file_size=file_size)


class GifEncoder:
    """GIF 파일 인코딩 클래스"""

    @classmethod
    def save(cls, collection: FrameCollection, file_path: str,
             settings: Optional[EncoderSettings] = None) -> SaveResult:
        """애니메이션 또는 이미지 파일로 저장
        
        지원 형식:
        - GIF: 애니메이션 GIF
        - WebP: 애니메이션 WebP (더 나은 압축률)
        - APNG: 애니메이션 PNG (무손실)
        - PNG/JPEG/BMP: 현재 프레임만 저장
        """
        if settings is None:
            settings = EncoderSettings()

        if collection.is_empty:
            return SaveResult.error("저장할 프레임이 없습니다")

        path = Path(file_path)
        ext = path.suffix.lower()

        try:
            if ext == '.gif':
                return cls._save_gif(collection, path, settings)
            elif ext == '.webp':
                return cls._save_webp(collection, path, settings)
            elif ext == '.apng' or (ext == '.png' and collection.frame_count > 1):
                # 다중 프레임이면 APNG로 저장
                if collection.frame_count > 1:
                    return cls._save_apng(collection, path, settings)
                else:
                    return cls._save_png(collection.current_frame, path)
            elif ext == '.png':
                return cls._save_png(collection.current_frame, path)
            elif ext in {'.jpg', '.jpeg'}:
                return cls._save_jpeg(collection.current_frame, path, settings.quality)
            elif ext == '.bmp':
                return cls._save_bmp(collection.current_frame, path)
            else:
                return SaveResult.error(f"지원하지 않는 형식입니다: {ext}")

        except Exception as e:
            return SaveResult.error(f"저장 실패: {str(e)}")

    @classmethod
    def _rgba_to_rgb(cls, img: Image.Image) -> Image.Image:
        """RGBA 이미지를 RGB로 변환 (알파 채널 제거, 흰색 배경 사용)
        
        모든 양자화 알고리즘에 대해 일관된 전처리를 제공합니다.
        """
        if img.mode == 'RGBA':
            rgb_img = Image.new('RGB', img.size, (255, 255, 255))
            rgb_img.paste(img, mask=img.split()[3])
            return rgb_img
        elif img.mode != 'RGB':
            return img.convert('RGB')
        return img

    @classmethod
    def _quantize_image(cls, img: Image.Image, settings: EncoderSettings) -> Image.Image:
        """이미지 양자화
        
        모든 양자화 알고리즘에 대해 일관된 처리를 제공합니다.
        프리뷰와 저장이 동일한 결과를 생성하도록 보장합니다.
        """
        # 원본 모드 저장
        original_mode = img.mode

        # 양자화 방법에 따른 처리
        method = settings.quantization
        colors = settings.colors
        dither = Image.Dither.FLOYDSTEINBERG if settings.dithering else Image.Dither.NONE

        try:
            if method == QuantizationMethod.LIBIMAGEQUANT:
                # libimagequant - RGBA 직접 지원
                try:
                    # RGBA를 RGB로 변환 (일관성을 위해)
                    rgb_img = cls._rgba_to_rgb(img)
                    img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.LIBIMAGEQUANT, dither=dither)
                except (AttributeError, ValueError, TypeError) as e:
                    # 지원하지 않으면 Fast Octree 사용
                    _logger.debug(f"libimagequant not available, using Fast Octree: {e}")
                    rgb_img = cls._rgba_to_rgb(img)
                    img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=dither)
            elif method == QuantizationMethod.FASTOCTREE:
                # Fast Octree - RGB로 변환하여 일관성 유지
                rgb_img = cls._rgba_to_rgb(img)
                img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=dither)
            elif method == QuantizationMethod.MEDIANCUT:
                # MEDIANCUT - RGB로 변환 후 양자화
                rgb_img = cls._rgba_to_rgb(img)
                try:
                    img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=dither)
                except (AttributeError, ValueError, TypeError):
                    # quantize()가 실패하면 convert() 사용 (ADAPTIVE 팔레트)
                    if settings.dithering:
                        img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors)
                    else:
                        img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors, dither=Image.Dither.NONE)
            elif method == QuantizationMethod.MAXCOVERAGE:
                # MAXCOVERAGE - RGB로 변환 후 양자화
                rgb_img = cls._rgba_to_rgb(img)
                try:
                    img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.MAXCOVERAGE, dither=dither)
                except (AttributeError, ValueError, TypeError) as e:
                    # quantize()가 실패하면 convert() 사용 (ADAPTIVE 팔레트)
                    _logger.debug(f"MAXCOVERAGE quantize() failed, using convert(): {e}")
                    if settings.dithering:
                        img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors)
                    else:
                        img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors, dither=Image.Dither.NONE)
            else:
                # 기본 ADAPTIVE - RGB로 변환 후 convert() 사용
                rgb_img = cls._rgba_to_rgb(img)
                if settings.dithering:
                    img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors)
                else:
                    img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors, dither=Image.Dither.NONE)
        except Exception as e:
            # 실패 시 기본 방법 사용
            _logger.warning(f"Quantization error: {e}", exc_info=True)
            try:
                # Fast Octree로 재시도
                rgb_img = cls._rgba_to_rgb(img)
                img_p = rgb_img.quantize(colors=colors, method=Image.Quantize.FASTOCTREE, dither=dither)
            except Exception:
                # 최종 폴백: convert 사용
                rgb_img = cls._rgba_to_rgb(img)
                img_p = rgb_img.convert('P', palette=Image.Palette.ADAPTIVE, colors=colors)

        return img_p

    @classmethod
    def _save_gif(cls, collection: FrameCollection, path: Path,
                  settings: EncoderSettings) -> SaveResult:
        """GIF 파일로 저장 (gifsicle 최적화 포함)"""
        try:
            # PIL로 GIF 저장
            images = []
            durations = []

            for frame in collection:
                img_p = cls._quantize_image(frame.image, settings)
                images.append(img_p)
                durations.append(frame.delay_ms)

            # 첫 번째 이미지에 나머지 이미지 추가하여 저장
            images[0].save(
                str(path),
                save_all=True,
                append_images=images[1:] if len(images) > 1 else [],
                duration=durations,
                loop=settings.loop_count,
                optimize=settings.optimize
            )

            original_size = path.stat().st_size
            final_size = original_size

            # gifsicle 최적화 적용
            if settings.use_gifsicle and _gifsicle_available:
                optimized_size = cls._optimize_with_gifsicle(
                    str(path),
                    settings.lossy_level,
                    settings.optimization_level
                )
                if optimized_size > 0:
                    final_size = optimized_size
                    reduction = (1 - final_size / original_size) * 100
                    _logger.info(f"GIF 최적화 완료: {original_size:,} → {final_size:,} 바이트 ({reduction:.1f}% 감소)")

            return SaveResult.ok(final_size)

        except Exception as e:
            return SaveResult.error(f"GIF 저장 실패: {str(e)}")

    @classmethod
    def _optimize_with_gifsicle(cls, file_path: str, lossy: int = 0,
                                  opt_level: int = 3) -> int:
        """gifsicle을 사용하여 GIF 최적화
        
        Args:
            file_path: GIF 파일 경로
            lossy: lossy 압축 레벨 (0=비활성화, 30-200)
            opt_level: 최적화 레벨 (1, 2, 3)
        
        Returns:
            최적화된 파일 크기 (바이트), 실패 시 0
        """
        try:
            import pygifsicle

            # 옵션 구성
            options = [f"-O{opt_level}"]

            if lossy > 0:
                options.append(f"--lossy={lossy}")

            # 최적화 실행 (pygifsicle)
            pygifsicle.optimize(file_path, options=options)

            return Path(file_path).stat().st_size

        except ImportError:
            # pygifsicle 없으면 CLI 사용
            return cls._optimize_with_gifsicle_cli(file_path, lossy, opt_level)
        except Exception as e:
            _logger.warning(f"gifsicle 최적화 실패: {e}")
            return 0

    @classmethod
    def _optimize_with_gifsicle_cli(cls, file_path: str, lossy: int = 0,
                                     opt_level: int = 3) -> int:
        """gifsicle CLI를 직접 사용하여 최적화"""
        import subprocess

        if not _gifsicle_path:
            return 0

        try:
            cmd = [_gifsicle_path, f"-O{opt_level}", "-b", file_path]

            if lossy > 0:
                cmd.insert(2, f"--lossy={lossy}")

            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

            if result.returncode == 0:
                return Path(file_path).stat().st_size
            else:
                _logger.warning(f"gifsicle CLI 오류: {result.stderr}")
                return 0

        except subprocess.TimeoutExpired:
            _logger.warning("gifsicle CLI 타임아웃 (60초)")
            return 0
        except Exception as e:
            _logger.warning(f"gifsicle CLI 실행 실패: {e}")
            return 0

    @classmethod
    def optimize_existing_gif(cls, file_path: str, lossy: int = 30,
                               opt_level: int = 3) -> Optional[int]:
        """기존 GIF 파일 최적화
        
        Args:
            file_path: GIF 파일 경로
            lossy: lossy 압축 레벨 (30-200 권장)
            opt_level: 최적화 레벨 (1, 2, 3)
        
        Returns:
            최적화된 파일 크기 (바이트), 실패 시 None
        """
        if not _gifsicle_available:
            _logger.warning("gifsicle이 설치되지 않았습니다")
            return None

        original_size = Path(file_path).stat().st_size
        optimized_size = cls._optimize_with_gifsicle(file_path, lossy, opt_level)

        if optimized_size > 0:
            reduction = (1 - optimized_size / original_size) * 100
            _logger.info(f"GIF 최적화: {original_size:,} → {optimized_size:,} 바이트 ({reduction:.1f}% 감소)")
            return optimized_size

        return None

    @classmethod
    def _save_webp(cls, collection: FrameCollection, path: Path,
                   settings: EncoderSettings) -> SaveResult:
        """WebP 파일로 저장 (애니메이션 지원)
        
        WebP는 GIF보다 더 나은 압축률과 색상 품질을 제공합니다.
        """
        try:
            images = []
            durations = []

            for frame in collection:
                # WebP는 RGBA를 직접 지원 (양자화 불필요)
                img = frame.image.copy()
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)
                durations.append(frame.delay_ms)

            # WebP 저장 옵션
            save_kwargs = {
                'save_all': True,
                'append_images': images[1:] if len(images) > 1 else [],
                'duration': durations,
                'loop': settings.loop_count,
                'quality': settings.quality,
                'method': 4,  # 압축 방법 (0=빠름, 6=최상)
            }

            # 손실/무손실 선택 (quality 100이면 무손실)
            if settings.quality >= 100:
                save_kwargs['lossless'] = True

            images[0].save(str(path), 'WEBP', **save_kwargs)

            file_size = path.stat().st_size
            return SaveResult.ok(file_size)

        except Exception as e:
            return SaveResult.error(f"WebP 저장 실패: {str(e)}")

    @classmethod
    def _save_apng(cls, collection: FrameCollection, path: Path,
                   settings: EncoderSettings) -> SaveResult:
        """APNG 파일로 저장 (애니메이션 PNG)
        
        APNG는 무손실 압축으로 고품질 애니메이션을 제공합니다.
        """
        try:
            images = []
            durations = []

            for frame in collection:
                img = frame.image.copy()
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                images.append(img)
                durations.append(frame.delay_ms)

            # APNG 저장
            images[0].save(
                str(path),
                format='PNG',
                save_all=True,
                append_images=images[1:] if len(images) > 1 else [],
                duration=durations,
                loop=settings.loop_count,
                default_image=True,  # 첫 프레임을 기본 이미지로
            )

            file_size = path.stat().st_size
            return SaveResult.ok(file_size)

        except Exception as e:
            return SaveResult.error(f"APNG 저장 실패: {str(e)}")

    @classmethod
    def create_preview(cls, frame: Frame, settings: EncoderSettings) -> Image.Image:
        """양자화 프리뷰 생성
        
        실제 저장 시와 동일한 방식으로 양자화를 적용하여 프리뷰를 생성합니다.
        저장 시와 정확히 동일한 과정을 거쳐 프리뷰와 저장 결과가 일치하도록 합니다.
        """
        # 원본 이미지 복사
        original_img = frame.image.copy()
        if original_img.mode != 'RGBA':
            original_img = original_img.convert('RGBA')

        # 양자화 수행 (P 모드로 변환) - 실제 저장 시와 동일한 방식
        img_p = cls._quantize_image(original_img, settings)

        # P 모드를 RGBA로 변환하여 프리뷰 표시
        # 저장된 GIF 파일을 열었을 때와 동일한 방식으로 변환합니다
        try:
            # P 모드를 RGBA로 변환 (팔레트 색상이 자동으로 적용됨)
            # 이 변환은 저장된 GIF 파일을 열었을 때와 동일한 결과를 만듭니다
            quantized_rgba = img_p.convert('RGBA')

            # 크기 확인 (양자화 과정에서 크기가 변경되지 않아야 함)
            if quantized_rgba.size != original_img.size:
                # 크기가 다르면 원본 크기로 리사이즈
                quantized_rgba = quantized_rgba.resize(original_img.size, Image.Resampling.NEAREST)

            return quantized_rgba
        except Exception:
            # 변환 실패 시 원본 반환
            return original_img

    @classmethod
    def estimate_gif_size(cls, collection: FrameCollection, settings: EncoderSettings) -> int:
        """GIF 파일 크기 추정 (바이트 단위로 메모리에서 인코딩)
        
        성능 최적화: 프레임이 많을 경우 샘플링하여 추정
        """
        if collection.is_empty:
            return 0

        try:
            frame_count = collection.frame_count

            # 프레임이 많으면 샘플링하여 성능 최적화
            # 100프레임 이하: 전체 사용
            # 100-1000프레임: 50개 샘플
            # 1000프레임 이상: 30개 샘플
            if frame_count <= 100:
                sample_indices = list(range(frame_count))
            elif frame_count <= 1000:
                step = max(1, frame_count // 50)
                sample_indices = list(range(0, frame_count, step))
                if sample_indices[-1] != frame_count - 1:
                    sample_indices.append(frame_count - 1)  # 마지막 프레임 포함
            else:
                step = max(1, frame_count // 30)
                sample_indices = list(range(0, frame_count, step))
                if sample_indices[-1] != frame_count - 1:
                    sample_indices.append(frame_count - 1)  # 마지막 프레임 포함

            images = []
            durations = []

            for idx in sample_indices:
                frame = collection.get_frame(idx)
                if frame:
                    img_p = cls._quantize_image(frame.image, settings)
                    images.append(img_p)
                    durations.append(frame.delay_ms)

            if not images:
                return 0

            # 메모리에 저장하여 크기 측정
            buffer = io.BytesIO()
            images[0].save(
                buffer,
                format='GIF',
                save_all=True,
                append_images=images[1:] if len(images) > 1 else [],
                duration=durations,
                loop=settings.loop_count,
                optimize=settings.optimize
            )

            # 샘플링된 크기를 전체 크기로 추정
            sample_size = buffer.tell()
            if len(sample_indices) < frame_count:
                # 샘플 크기를 기반으로 전체 크기 추정
                # 평균 프레임 크기 * 전체 프레임 수로 추정
                avg_frame_size = sample_size / len(sample_indices)
                estimated_size = int(avg_frame_size * frame_count)
                return estimated_size
            else:
                return sample_size
        except Exception:
            return 0

    @classmethod
    def _save_png(cls, frame: Optional[Frame], path: Path) -> SaveResult:
        """PNG 파일로 저장"""
        if frame is None:
            return SaveResult.error("저장할 프레임이 없습니다")

        try:
            frame.image.save(str(path), 'PNG')
            file_size = path.stat().st_size
            return SaveResult.ok(file_size)
        except Exception as e:
            return SaveResult.error(f"PNG 저장 실패: {str(e)}")

    @classmethod
    def _save_jpeg(cls, frame: Optional[Frame], path: Path,
                   quality: int = 85) -> SaveResult:
        """JPEG 파일로 저장"""
        if frame is None:
            return SaveResult.error("저장할 프레임이 없습니다")

        try:
            # JPEG는 알파 채널을 지원하지 않음
            rgb_image = frame.image.convert('RGB')
            rgb_image.save(str(path), 'JPEG', quality=quality)
            file_size = path.stat().st_size
            return SaveResult.ok(file_size)
        except Exception as e:
            return SaveResult.error(f"JPEG 저장 실패: {str(e)}")

    @classmethod
    def _save_bmp(cls, frame: Optional[Frame], path: Path) -> SaveResult:
        """BMP 파일로 저장"""
        if frame is None:
            return SaveResult.error("저장할 프레임이 없습니다")

        try:
            rgb_image = frame.image.convert('RGB')
            rgb_image.save(str(path), 'BMP')
            file_size = path.stat().st_size
            return SaveResult.ok(file_size)
        except Exception as e:
            return SaveResult.error(f"BMP 저장 실패: {str(e)}")

    @classmethod
    def save_image_sequence(cls, collection: FrameCollection,
                           directory: str, base_name: str,
                           format: str = 'png') -> SaveResult:
        """이미지 시퀀스로 저장"""
        if collection.is_empty:
            return SaveResult.error("저장할 프레임이 없습니다")

        try:
            dir_path = Path(directory)
            dir_path.mkdir(parents=True, exist_ok=True)

            total_size = 0
            digits = len(str(collection.frame_count))

            for i, frame in enumerate(collection):
                filename = f"{base_name}_{str(i).zfill(digits)}.{format}"
                file_path = dir_path / filename

                if format.lower() in {'jpg', 'jpeg'}:
                    frame.image.convert('RGB').save(str(file_path))
                else:
                    frame.image.save(str(file_path))

                total_size += file_path.stat().st_size

            return SaveResult.ok(total_size)

        except Exception as e:
            return SaveResult.error(f"이미지 시퀀스 저장 실패: {str(e)}")

    @classmethod
    def estimate_file_size(cls, collection: FrameCollection,
                          settings: Optional[EncoderSettings] = None) -> int:
        """예상 파일 크기 계산 (대략적)"""
        if collection.is_empty:
            return 0

        # 매우 대략적인 추정
        total_pixels = sum(f.width * f.height for f in collection)

        # GIF 압축률 가정 (약 30-50%)
        compression_ratio = 0.4

        # 헤더 및 메타데이터
        overhead = 1000

        return int(total_pixels * compression_ratio + overhead)
