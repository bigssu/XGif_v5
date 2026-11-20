"""
고화질 GIF 인코더
FFmpeg의 palettegen + paletteuse 필터를 사용하여 원본에 가까운 품질 제공
GPU 가속: FFmpeg NVENC/hwaccel만 사용 (프레임 처리는 CPU가 더 효율적)
"""

import os
import shutil
import subprocess
import tempfile
import contextlib
import uuid
import logging
import threading
import time
from pathlib import Path
from typing import Optional, Callable, Protocol
from collections.abc import Iterable, Iterator
import numpy as np
from PIL import GifImagePlugin, Image, ImageChops
from .utils import publish_output, safe_rmtree, run_subprocess_silent

logger = logging.getLogger(__name__)

def _create_temp_dir(prefix: str = 'giffy_') -> str:
    """안전하게 임시 디렉토리 생성 (UUID 사용)"""
    # 사용자 TEMP 디렉토리 사용
    try:
        base_temp = tempfile.gettempdir()

        # 기본 temp 디렉토리 검증
        if not os.path.exists(base_temp) or not os.path.isdir(base_temp):
            logger.error(f"Invalid temp directory: {base_temp}")
            # 폴백: 현재 디렉토리의 temp 폴더
            base_temp = os.path.join(os.getcwd(), 'temp')
            os.makedirs(base_temp, exist_ok=True)
    except (OSError, PermissionError) as e:
        logger.error(f"Cannot access temp directory: {e}")
        return tempfile.mkdtemp(prefix=prefix)

    for attempt in range(5):  # 최대 5회 시도
        unique_name = f"{prefix}{uuid.uuid4().hex[:8]}"
        temp_dir = os.path.join(base_temp, unique_name)

        try:
            # 이미 존재하면 삭제 시도
            if os.path.exists(temp_dir) and not safe_rmtree(temp_dir):
                logger.warning(f"Failed to remove existing temp dir: {temp_dir}")
                continue

            os.makedirs(temp_dir, exist_ok=True)

            # 쓰기 권한 테스트
            test_file = os.path.join(temp_dir, '.test')
            try:
                with open(test_file, 'w', encoding='utf-8') as f:
                    f.write('test')
                os.remove(test_file)
            except (IOError, OSError, PermissionError) as e:
                logger.warning(f"Temp dir write test failed: {e}")
                continue

            return temp_dir
        except (OSError, PermissionError) as e:
            logger.debug(f"Temp dir creation attempt {attempt + 1} failed: {e}")
            continue

    # 모든 시도 실패 시 기본 tempfile 사용
    logger.warning("All temp dir creation attempts failed, using fallback")
    try:
        return tempfile.mkdtemp(prefix=prefix)
    except (OSError, PermissionError) as e:
        logger.critical(f"Cannot create temp directory: {e}")
        raise RuntimeError(f"임시 디렉토리를 생성할 수 없습니다: {e}") from e

# GPU 유틸리티 (FFmpeg GPU 가속용)
from .gpu_utils import detect_gpu

class FrameSource(Protocol):
    def __len__(self) -> int: ...
    def __getitem__(self, index: int, /) -> np.ndarray: ...
    def __iter__(self) -> Iterator[np.ndarray]: ...


def _gif_ticks(frame_count, fps):
    return int(frame_count * 100 / fps + 0.5)


def gif_frame_timing(frame_count: int, fps: float) -> Iterator[tuple[int, int]]:
    """Yield source indices and delays in milliseconds, rounded on the GIF timeline."""
    if not 0 < fps <= 120:
        raise ValueError("GIF frame rate must be in (0, 120]")
    if fps > 100:
        # GIF can display at most one distinct image per centisecond.
        count = _gif_ticks(frame_count, fps)
        for step in range(count):
            index = round(step * (frame_count - 1) / (count - 1)) if count > 1 else 0
            yield index, 10
    else:
        previous = 0
        for index in range(frame_count):
            end = _gif_ticks(index + 1, fps)
            yield index, (end - previous) * 10
            previous = end


def _gif_frames(frames, fps):
    if fps <= 100:
        return frames
    return (frames[index] for index, _ in gif_frame_timing(len(frames), fps))


def _bgr_frames(frames: Iterable[np.ndarray]):
    shape = None
    for index, frame in enumerate(frames):
        if (not isinstance(frame, np.ndarray) or frame.dtype != np.uint8
                or frame.ndim != 3 or frame.shape[2] not in (3, 4)
                or (shape is not None and frame.shape[:2] != shape) or frame.size == 0):
            raise ValueError(f"Invalid BGR/BGRA frame at index {index}")
        shape = frame.shape[:2]
        yield frame[:, :, :3]


def write_palette_gif(output_path, images: Iterable[tuple[Image.Image, float]], loop=0, optimize=True,
                      *, transparent_canvas=False):
    """Write adjacent frame differences with independent palettes and delays in ms."""
    elapsed_ms = 0
    written_ticks = 0

    def write_frame(output, tile, offset, duration):
        nonlocal elapsed_ms, written_ticks
        first = output.tell() == 0
        info = {key: tile.info[key] for key in ('transparency',) if key in tile.info}
        if first:
            header_info = info.copy() if loop is None else {"loop": loop, **info}
            if transparent_canvas:
                header_info['background'] = info['transparency']
            header, _ = GifImagePlugin.getheader(tile, info=header_info)
            output.writelines(header)
        elapsed_ms += duration
        end_tick = int((elapsed_ms + 5) // 10)
        ticks = end_tick - written_ticks
        written_ticks = end_tick
        while True:
            delay = min(ticks, 65535)
            blocks = GifImagePlugin.getdata(tile, offset=offset, duration=delay * 10,
                                            include_color_table=not first, disposal=2 if transparent_canvas else 0, **info)
            output.writelines(blocks)
            # Pillow's per-frame collector class also holds this list until cyclic GC.
            blocks.clear()
            ticks -= delay
            if not ticks:
                break
            first = False

    pending = None
    previous = None
    pending_duration = 0
    offset = (0, 0)
    with contextlib.ExitStack() as stack:
        output = output_path if hasattr(output_path, 'write') else stack.enter_context(open(output_path, 'wb'))
        for frame, duration in images:
            if frame.mode != 'P' or duration < 0:
                raise ValueError("GIF frames require a palette and a nonnegative delay")
            # Converting a transparent P image changes Pillow's internal palette to RGBA.
            # Keep the original RGB palette for the GIF color table.
            comparison_frame = frame.copy() if 'transparency' in frame.info else frame
            rgba = comparison_frame.convert('RGBA')
            if previous is None:
                tile = frame
            else:
                if rgba.size != previous.size:
                    raise ValueError(f"GIF frame sizes differ: {previous.size} / {rgba.size}")
                delta = ImageChops.difference(previous, rgba)
                bbox = delta.getbbox(alpha_only=False)
                if bbox is None:
                    pending_duration += duration
                    continue
                write_frame(output, pending, offset, pending_duration)
                if transparent_canvas:
                    # Disposal clears the full canvas between frames so pixels can become transparent.
                    pending, previous, pending_duration = frame, rgba, duration
                    continue
                offset = bbox[:2]
                tile = frame.crop(bbox)
                if optimize:
                    transparent = frame.info.get('transparency')
                    if transparent is None:
                        used = {index for _, index in frame.getcolors()}
                        transparent = next((i for i in range(256) if i not in used), None)
                    if transparent is not None:
                        # Unchanged pixels must retain the displayed canvas, which can
                        # differ from the previous source outside an earlier cropped tile.
                        palette = tile.getpalette()
                        missing = 3 * (transparent + 1) - len(palette)
                        if missing > 0:
                            tile.putpalette(palette + [0] * missing)
                        r, g, b, a = delta.crop(bbox).split()
                        changed = ImageChops.lighter(ImageChops.lighter(r, g), ImageChops.lighter(b, a))
                        tile.paste(transparent, mask=changed.point([255] + [0] * 255))
                        tile.info['transparency'] = transparent
            pending, previous, pending_duration = tile, rgba, duration
        if pending is None:
            raise ValueError("GIF contains no frames")
        write_frame(output, pending, offset, pending_duration)
        output.write(b";")


class GifEncoder:
    """FFmpeg 기반 고화질 GIF/MP4 인코더"""

    # 품질 설정 프리셋
    QUALITY_PRESETS = {
        'high': {
            'max_colors': 256,
            'stats_mode': 'full',
            'dither': 'floyd_steinberg',
            'diff_mode': 'none',
        },
        'medium': {
            'max_colors': 256,
            'stats_mode': 'diff',
            'dither': 'bayer',
            'bayer_scale': 3,
            'diff_mode': 'rectangle',
        },
        'low': {
            'max_colors': 128,
            'stats_mode': 'diff',
            'dither': 'none',
            'diff_mode': 'rectangle',
        }
    }

    # 인코더 우선순위 (H.264)
    H264_ENCODERS = [
        ('h264_nvenc', 'NVENC'),    # NVIDIA GPU
        ('h264_qsv', 'QSV'),        # Intel GPU
        ('h264_amf', 'AMF'),        # AMD GPU
        ('libx264', 'CPU'),         # CPU 폴백
    ]

    # 인코더 우선순위 (H.265/HEVC)
    H265_ENCODERS = [
        ('hevc_nvenc', 'NVENC'),    # NVIDIA GPU
        ('hevc_qsv', 'QSV'),        # Intel GPU
        ('hevc_amf', 'AMF'),        # AMD GPU
        ('libx265', 'CPU'),         # CPU 폴백
    ]

    def __init__(self):
        # 콜백 함수들
        self._progress_callback: Optional[Callable[[int, int], None]] = None
        self._finished_callback: Optional[Callable[[str], None]] = None
        self._error_callback: Optional[Callable[[str], None]] = None
        self.quality = 'high'
        self._ffmpeg_path = self._find_ffmpeg()

        # 코덱 설정 (h264 또는 h265)
        self._codec = 'h264'  # 기본값

        # 인코더 설정 ("auto" 또는 특정 인코더 이름)
        self._preferred_encoder = 'auto'

        # GPU 가속 설정 (FFmpeg NVENC/hwaccel용)
        gpu_info = detect_gpu()
        self._use_gpu = gpu_info.has_cuda
        self._has_nvenc = gpu_info.ffmpeg_nvenc

        # 사용 가능한 인코더 캐시
        self._available_encoders: Optional[dict] = None

        # FFmpeg 실행을 위한 환경 변수 (포함된 ffmpeg 사용 시 PATH에 추가)
        self._ffmpeg_env = self._get_ffmpeg_env()

    def set_progress_callback(self, callback: Callable[[int, int], None]):
        """진행률 콜백 설정"""
        self._progress_callback = callback

    def set_finished_callback(self, callback: Callable[[str], None]):
        """완료 콜백 설정"""
        self._finished_callback = callback

    def set_error_callback(self, callback: Callable[[str], None]):
        """에러 콜백 설정"""
        self._error_callback = callback

    def _emit_progress(self, current: int, total: int):
        """진행률 이벤트 발생"""
        if self._progress_callback:
            with contextlib.suppress(Exception):
                self._progress_callback(current, total)

    def _emit_finished(self, output_path: str):
        """완료 이벤트 발생"""
        if self._finished_callback:
            with contextlib.suppress(Exception):
                self._finished_callback(output_path)

    def _emit_error(self, error_msg: str):
        """에러 이벤트 발생"""
        if self._error_callback:
            with contextlib.suppress(Exception):
                self._error_callback(error_msg)

    def refresh_ffmpeg_path(self):
        """FFmpeg 경로 새로고침 (설치 후 호출)"""
        self._ffmpeg_path = self._find_ffmpeg()
        self._ffmpeg_env = self._get_ffmpeg_env()

    def _get_ffmpeg_env(self) -> dict:
        """FFmpeg 실행을 위한 환경 변수 딕셔너리 반환"""
        try:
            from .ffmpeg_installer import FFmpegManager
            return FFmpegManager.get_ffmpeg_env()
        except ImportError:
            return os.environ.copy()

    def _find_ffmpeg(self) -> Optional[str]:
        """FFmpeg 경로 찾기 (시스템 PATH 우선, 없으면 포함된 ffmpeg 사용)"""
        try:
            from .ffmpeg_installer import FFmpegManager
            # FFmpegManager가 이미 시스템 PATH 우선 확인 후 포함된 ffmpeg 확인
            ffmpeg_path = FFmpegManager.get_ffmpeg_executable()
            if ffmpeg_path and Path(ffmpeg_path).exists():
                return str(ffmpeg_path)
        except ImportError:
            pass

        # 폴백: 일반적인 Windows 설치 경로 확인
        common_paths = [
            Path('C:/ffmpeg/bin/ffmpeg.exe'),
            Path('C:/Program Files/ffmpeg/bin/ffmpeg.exe'),
            Path('C:/Program Files (x86)/ffmpeg/bin/ffmpeg.exe'),
            Path.home() / 'ffmpeg/bin/ffmpeg.exe',
        ]

        for path in common_paths:
            if path.exists():
                return str(path)

        return None

    def is_ffmpeg_available(self) -> bool:
        """FFmpeg 사용 가능 여부"""
        return self._ffmpeg_path is not None

    def set_quality(self, quality: str):
        """품질 설정 (high, medium, low)"""
        if quality in self.QUALITY_PRESETS:
            self.quality = quality

    def set_codec(self, codec: str):
        """코덱 설정 (h264 또는 h265)"""
        if codec.lower() in ('h264', 'h265', 'hevc'):
            self._codec = 'h265' if codec.lower() in ('h265', 'hevc') else 'h264'

    def get_codec(self) -> str:
        """현재 코덱 반환"""
        return self._codec

    def set_preferred_encoder(self, encoder: str):
        """선호 인코더 설정 (auto, nvenc, qsv, amf, cpu)"""
        self._preferred_encoder = encoder.lower()

    def get_preferred_encoder(self) -> str:
        """선호 인코더 반환"""
        return self._preferred_encoder

    def detect_available_encoders(self) -> dict:
        """사용 가능한 인코더 감지

        Returns:
            dict: {
                'h264': ['h264_nvenc', 'libx264', ...],
                'h265': ['hevc_nvenc', 'libx265', ...],
                'best_h264': 'h264_nvenc',
                'best_h265': 'hevc_nvenc',
            }
        """
        if self._available_encoders is not None:
            return self._available_encoders

        result = {
            'h264': [],
            'h265': [],
            'best_h264': None,
            'best_h265': None,
        }

        if not self._ffmpeg_path:
            result['h264'] = ['libx264']
            result['h265'] = ['libx265']
            result['best_h264'] = 'libx264'
            result['best_h265'] = 'libx265'
            self._available_encoders = result
            return result

        # H.264 인코더 테스트
        for encoder, _ in self.H264_ENCODERS:
            if self._test_encoder(encoder):
                result['h264'].append(encoder)
                if result['best_h264'] is None:
                    result['best_h264'] = encoder

        # H.265 인코더 테스트
        for encoder, _ in self.H265_ENCODERS:
            if self._test_encoder(encoder):
                result['h265'].append(encoder)
                if result['best_h265'] is None:
                    result['best_h265'] = encoder

        # CPU 폴백 보장
        if not result['h264']:
            result['h264'] = ['libx264']
            result['best_h264'] = 'libx264'
        if not result['h265']:
            result['h265'] = ['libx265']
            result['best_h265'] = 'libx265'

        self._available_encoders = result
        return result

    def _test_encoder(self, encoder_name: str) -> bool:
        """인코더 실제 사용 가능 여부 테스트

        짧은 테스트 인코딩을 수행하여 실제 작동 여부 확인
        (드라이버 문제 등으로 목록에는 있지만 작동 안 하는 경우 방지)
        """
        if not self._ffmpeg_path:
            return False

        try:
            # 256x256 검정 프레임으로 테스트 (NVENC는 최소 해상도 제한이 있어 64x64는 실패함)
            cmd = [
                self._ffmpeg_path,
                '-y',
                '-f', 'lavfi',
                '-i', 'color=black:s=256x256:d=0.5:r=30',
                '-c:v', encoder_name,
                '-f', 'null',
                '-'
            ]

            result = run_subprocess_silent(cmd, timeout=10)
            return result.returncode == 0

        except (subprocess.TimeoutExpired, Exception):
            return False

    def _get_best_encoder(self, codec: str = None) -> str:
        """최적 인코더 반환

        Args:
            codec: 'h264' 또는 'h265' (None이면 self._codec 사용)
        """
        if codec is None:
            codec = self._codec

        # 선호 인코더가 지정된 경우
        if self._preferred_encoder != 'auto':
            encoder_map = {
                'nvenc': 'h264_nvenc' if codec == 'h264' else 'hevc_nvenc',
                'qsv': 'h264_qsv' if codec == 'h264' else 'hevc_qsv',
                'amf': 'h264_amf' if codec == 'h264' else 'hevc_amf',
                'cpu': 'libx264' if codec == 'h264' else 'libx265',
            }
            preferred = encoder_map.get(self._preferred_encoder)
            if preferred:
                return preferred

        # 자동 선택
        available = self.detect_available_encoders()
        if codec == 'h265':
            return available.get('best_h265', 'libx265')
        else:
            return available.get('best_h264', 'libx264')

    @staticmethod
    def _is_hardware_encoder_failure(encoder, stderr):
        if not encoder.endswith(('_nvenc', '_qsv', '_amf')):
            return False
        if isinstance(stderr, bytes):
            stderr = stderr.decode('utf-8', errors='replace')
        message = stderr.lower()
        return any(marker in message for marker in (
            'initializeencoder failed', 'openencodesessionex failed',
            'no nvenc capable devices found', 'cannot load nvcuda', 'cannot load nvencodeapi',
            'driver does not support the required nvenc api version',
            'error initializing an internal mfx session', 'error initializing an mfx session',
            'error creating a mfx session',
            'amf failed to initialise', 'amf failed to initialize',
            'amf_context->init() failed', 'amf_encoder->init() failed',
            'error while opening encoder',
        ))

    @staticmethod
    def _video_encoder_options(encoder, crf, cpu_preset='medium'):
        if encoder in ('h264_nvenc', 'hevc_nvenc'):
            quality = ['-preset', 'p4', '-cq', crf]
        elif encoder in ('h264_qsv', 'hevc_qsv'):
            quality = ['-preset', 'medium', '-global_quality', crf]
        elif encoder in ('h264_amf', 'hevc_amf'):
            quality = ['-quality', 'balanced', '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf]
        else:
            quality = ['-preset', cpu_preset, '-crf', crf]
        return ['-c:v', encoder] + quality

    def get_encoder_display_name(self, encoder: str) -> str:
        """인코더 표시 이름 반환"""
        display_names = {
            'h264_nvenc': 'NVENC (NVIDIA)',
            'hevc_nvenc': 'NVENC (NVIDIA)',
            'h264_qsv': 'QSV (Intel)',
            'hevc_qsv': 'QSV (Intel)',
            'h264_amf': 'AMF (AMD)',
            'hevc_amf': 'AMF (AMD)',
            'libx264': 'x264 (CPU)',
            'libx265': 'x265 (CPU)',
        }
        return display_names.get(encoder, encoder)

    def _write_frames_to_pipe(self, process, frames: FrameSource, total_steps: int, on_frame_written):
        """Stream uint8 BGR/BGRA capture frames as bgr24, one frame at a time."""
        try:
            for i, bgr in enumerate(_bgr_frames(frames)):
                process.stdin.write(memoryview(np.ascontiguousarray(bgr)).cast("B"))
                on_frame_written()
                if total_steps > 0 and ((i + 1) % 10 == 0 or i + 1 == len(frames)):
                    self._emit_progress(i + 1, total_steps)
        finally:
            with contextlib.suppress(BrokenPipeError, OSError):
                process.stdin.close()

    def _run_streamed_ffmpeg(self, cmd, frames, total_steps=0, timeout=600):
        """Allow long encodes while bounding stalled frame writes and post-EOF finalization."""
        # A file cannot fill a stderr pipe while the child is waiting for stdin.
        with tempfile.TemporaryFile() as stderr:
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=stderr,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0,
            )
            write_errors = []
            last_write = time.monotonic()

            def mark_frame_written():
                nonlocal last_write
                last_write = time.monotonic()

            def write_frames():
                try:
                    self._write_frames_to_pipe(process, frames, total_steps, mark_frame_written)
                except (BrokenPipeError, OSError) as exc:
                    write_errors.append(exc)
                except Exception as exc:
                    write_errors.append(exc)
                    if process.poll() is None:
                        process.kill()

            writer = threading.Thread(target=write_frames, name='ffmpeg-frame-writer')
            try:
                writer.start()
                while writer.is_alive():
                    remaining = timeout - (time.monotonic() - last_write)
                    if remaining <= 0:
                        raise subprocess.TimeoutExpired(cmd, timeout)
                    writer.join(remaining)
                process.wait(timeout=timeout)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
                if writer.ident is not None:
                    writer.join()
                with contextlib.suppress(BrokenPipeError, OSError):
                    process.stdin.close()
            stderr.seek(0)
            error_output = stderr.read()
            if write_errors and (process.returncode == 0 or not isinstance(write_errors[0], OSError)):
                raise write_errors[0]
            return subprocess.CompletedProcess(cmd, process.returncode, stderr=error_output)

    def _check_disk_space(self, output_path: str, frames: FrameSource) -> bool:
        """인코딩 전 디스크 공간 확인. 부족하면 False 반환."""
        try:
            output_dir = os.path.dirname(os.path.abspath(output_path)) or '.'
            usage = shutil.disk_usage(output_dir)
            # 예상 필요 공간: 원본 프레임 크기의 약 10% (GIF/MP4 압축 고려) + 여유 100MB
            estimated_raw = frames[0].nbytes * len(frames) if frames else 0
            estimated_needed = max(estimated_raw // 10, 100 * 1024 * 1024)  # 최소 100MB
            if usage.free < estimated_needed:
                free_mb = usage.free / (1024 * 1024)
                needed_mb = estimated_needed / (1024 * 1024)
                self._emit_error(f"디스크 공간 부족: {free_mb:.0f}MB 남음 (최소 {needed_mb:.0f}MB 필요)")
                return False
        except (OSError, AttributeError):
            pass  # 디스크 확인 실패 시 인코딩 계속 진행
        return True

    def encode(self, frames: FrameSource, fps: float, output_path: str, *, overwrite=True) -> bool:
        return self._encode_atomic(self._encode_gif, frames, fps, output_path, overwrite=overwrite)

    def encode_mp4(self, frames: FrameSource, fps: float, output_path: str,
                   audio_path: Optional[str] = None, *, overwrite=True) -> bool:
        return self._encode_atomic(self._encode_mp4, frames, fps, output_path, audio_path, overwrite=overwrite)

    def _encode_atomic(self, encode, frames, fps, output_path, *args, overwrite):
        staged = None
        try:
            if not output_path or not isinstance(output_path, str):
                self._emit_error("유효하지 않은 출력 경로입니다.")
                return False
            destination = Path(output_path).absolute()
            fd, staged = tempfile.mkstemp(prefix='.xgif-', suffix=destination.suffix, dir=destination.parent)
            os.close(fd)
            if not encode(frames, fps, staged, *args):
                return False
            if os.path.getsize(staged) == 0:
                raise ValueError("인코딩 결과 파일이 비어 있습니다.")
            publish_output(staged, destination, overwrite=overwrite)
            self._emit_finished(output_path)
            return True
        except FileExistsError:
            self._emit_error(f"출력 파일이 이미 존재합니다: {output_path}")
            return False
        except Exception as exc:
            self._emit_error(f"인코딩 파일 저장 실패: {exc}")
            return False
        finally:
            if staged is not None:
                with contextlib.suppress(OSError):
                    os.remove(staged)

    def _encode_gif(self, frames: FrameSource, fps: float, output_path: str) -> bool:
        """프레임 리스트를 GIF로 인코딩 (Pipe 방식 우선)"""
        # 입력 검증
        if not frames:
            self._emit_error("인코딩할 프레임이 없습니다.")
            return False

        if not 0 < fps <= 120:
            logger.error(f"Invalid FPS: {fps}")
            self._emit_error(f"유효하지 않은 FPS 값: {fps}")
            return False

        if not output_path or not isinstance(output_path, str):
            logger.error(f"Invalid output path: {output_path}")
            self._emit_error("유효하지 않은 출력 경로입니다.")
            return False

        # 프레임 유효성 검증
        try:
            first_frame = frames[0]
            if not isinstance(first_frame, np.ndarray) or first_frame.size == 0:
                logger.error("Invalid frame format")
                self._emit_error("유효하지 않은 프레임 형식입니다.")
                return False
        except (IndexError, AttributeError) as e:
            logger.error(f"Frame validation failed: {e}")
            self._emit_error("프레임 검증 실패")
            return False

        # 디스크 공간 확인
        if not self._check_disk_space(output_path, frames):
            return False

        # The streaming Pillow writer can split holds beyond GIF's 16-bit delay field.
        if self._ffmpeg_path and fps >= 100 / 65535:
            return self._encode_with_pipe(frames, output_path, fps)

        return self._encode_with_pillow(frames, output_path, fps)

    def _encode_with_pipe(self, frames: FrameSource, output_path: str, fps: float) -> bool:
        """FFmpeg Pipe를 사용한 2-pass GIF 인코딩 (디스크 I/O 최소화)"""
        if not frames:
            logger.error("No frames to encode")
            return False

        try:
            h, w = frames[0].shape[:2]
            if h <= 0 or w <= 0:
                logger.error(f"Invalid frame dimensions: {w}x{h}")
                self._emit_error(f"유효하지 않은 프레임 크기: {w}x{h}")
                return False
        except (IndexError, AttributeError, ValueError) as e:
            logger.error(f"Frame access error: {e}")
            self._emit_error("프레임 접근 오류")
            return False
        total_frames = len(frames)
        total_steps = total_frames * 2 + 2 # Palette pass + GIF pass

        preset = self.QUALITY_PRESETS[self.quality]
        temp_dir = _create_temp_dir(prefix='giffy_pipe_')
        palette_path = os.path.join(temp_dir, 'palette.png')

        try:
            # Pass 1: Palette Generation via Pipe
            palettegen_filter = f"palettegen=max_colors={preset['max_colors']}:stats_mode={preset['stats_mode']}"
            cmd_palette = [
                self._ffmpeg_path, '-y', '-loglevel', 'error',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f"{w}x{h}", '-pix_fmt', 'bgr24', '-framerate', str(fps),
                '-i', '-',
                '-vf', palettegen_filter,
                palette_path
            ]

            try:
                process = self._run_streamed_ffmpeg(cmd_palette, frames)
                stderr = process.stderr
            except subprocess.TimeoutExpired:
                logger.error("Palette generation timeout")
                self._emit_error("팔레트 생성 시간 초과")
                return False

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                self._emit_error(f"팔레트 생성 실패: {error_msg}")
                return False

            self._emit_progress(total_frames, total_steps)

            # Pass 2: GIF Generation via Pipe
            paletteuse_opts = [f"dither={preset['dither']}"]
            if 'bayer_scale' in preset:
                paletteuse_opts.append(f"bayer_scale={preset['bayer_scale']}")
            if preset.get('diff_mode') and preset['diff_mode'] != 'none':
                paletteuse_opts.append(f"diff_mode={preset['diff_mode']}")
            paletteuse_filter = f"paletteuse={':'.join(paletteuse_opts)}"

            filter_complex = f"[0:v][1:v]{paletteuse_filter}"

            final_delay = 1 if fps > 100 else _gif_ticks(total_frames, fps) - _gif_ticks(total_frames - 1, fps)
            cmd_gif = [
                self._ffmpeg_path, '-y', '-loglevel', 'error',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f"{w}x{h}", '-pix_fmt', 'bgr24', '-framerate', str(min(fps, 100)),
                '-i', '-',
                '-i', palette_path,
                '-lavfi', filter_complex,
                '-loop', '0', '-final_delay', str(final_delay),
                output_path
            ]

            try:
                process = self._run_streamed_ffmpeg(cmd_gif, _gif_frames(frames, fps))
                stderr = process.stderr
            except subprocess.TimeoutExpired:
                logger.error("GIF generation timeout")
                self._emit_error("GIF 생성 시간 초과")
                return False

            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                self._emit_error(f"GIF 생성 실패: {error_msg}")
                return False

            self._emit_progress(total_steps, total_steps)
            return True

        except Exception as e:
            self._emit_error(f"Pipe 인코딩 에러: {str(e)}")
            return False
        finally:
            safe_rmtree(temp_dir)

    def _encode_with_pillow(self, frames: FrameSource, output_path: str, fps: float) -> bool:
        total = len(frames)
        colors = 256 if self.quality in ('high', 'medium') else 128
        dither = Image.Dither.FLOYDSTEINBERG if colors == 256 else Image.Dither.NONE

        def quantized_frames():
            timing = gif_frame_timing(total, fps)
            for (source_index, delay), bgr in zip(timing, _bgr_frames(_gif_frames(frames, fps)), strict=True):
                index = source_index + 1
                rgb = Image.fromarray(bgr[:, :, ::-1])
                yield rgb.quantize(colors=colors, method=Image.Quantize.MEDIANCUT, dither=dither), delay
                if index % 10 == 0 or index == total:
                    self._emit_progress(index, total + 1)

        try:
            write_palette_gif(output_path, quantized_frames())
            self._emit_progress(total + 1, total + 1)
            return True
        except Exception as e:
            self._emit_error(f"Pillow 인코딩 에러: {e}")
            return False

    def _encode_mp4(self, frames: FrameSource, fps: float, output_path: str, audio_path: Optional[str] = None) -> bool:
        """프레임 리스트를 MP4로 인코딩 (Pipe 방식)"""
        # 입력 검증
        if not frames:
            self._emit_error("인코딩할 프레임이 없습니다.")
            return False

        if not 0 < fps <= 120:
            logger.error(f"Invalid FPS: {fps}")
            self._emit_error(f"유효하지 않은 FPS 값: {fps}")
            return False

        if not output_path or not isinstance(output_path, str):
            logger.error(f"Invalid output path: {output_path}")
            self._emit_error("유효하지 않은 출력 경로입니다.")
            return False

        if not self._ffmpeg_path or not os.path.exists(self._ffmpeg_path):
            # 경로가 stale할 수 있으므로 재탐색 시도
            self.refresh_ffmpeg_path()
        if not self._ffmpeg_path or not os.path.exists(self._ffmpeg_path):
            logger.error("FFmpeg not found")
            self._emit_error("FFmpeg가 필요합니다. MP4 인코딩을 위해 FFmpeg를 설치하세요.")
            return False

        # 오디오 파일 검증 (선택적)
        if audio_path and not os.path.exists(audio_path):
            logger.warning(f"Audio file not found: {audio_path}")
            audio_path = None  # 오디오 없이 진행

        # 디스크 공간 확인
        if not self._check_disk_space(output_path, frames):
            return False

        h, w = frames[0].shape[:2]

        total_frames = len(frames)
        total_steps = total_frames + 1

        try:
            # 품질 및 인코더 설정
            crf = {'high': '18', 'medium': '23', 'low': '28'}.get(self.quality, '23')
            cpu_preset = {'high': 'slow', 'medium': 'medium', 'low': 'fast'}.get(self.quality, 'medium')

            has_audio = audio_path and os.path.exists(audio_path)
            encoder = self._get_best_encoder(self._codec)

            # 명령어 구성
            cmd = [
                self._ffmpeg_path, '-y',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f"{w}x{h}", '-pix_fmt', 'bgr24',
                '-r', str(fps),  # 입력 프레임레이트 (중요!)
                '-i', '-'
            ]
            if has_audio:
                cmd.extend(['-i', audio_path])

            if w % 2 or h % 2:
                # Pad the original BGR pixels before the normal encoder color conversion.
                cmd.extend(['-vf', 'format=bgr24,pad=ceil(iw/2)*2:ceil(ih/2)*2'])

            encoder_start = len(cmd)
            cmd.extend(self._video_encoder_options(encoder, crf, cpu_preset))
            encoder_end = len(cmd)

            cmd.extend([
                '-r', str(fps),  # 출력 프레임레이트 (명시적으로 설정!)
                '-pix_fmt', 'yuv420p'
            ])

            if has_audio:
                audio_filter = f'apad,atrim=duration={total_frames / fps:.9f}'
                cmd.extend(['-af', audio_filter, '-c:a', 'aac', '-b:a', '192k'])

            cmd.append(output_path)

            # 디버깅: FFmpeg 명령어 로깅
            logger.info(f"[MP4] Encoding {total_frames} frames at {fps} FPS using {encoder}")
            logger.debug(f"[MP4] FFmpeg command: {' '.join(cmd)}")

            try:
                self._emit_progress(0, total_steps)
                hardware_failure = None
                for attempt in range(2):
                    process = self._run_streamed_ffmpeg(cmd, frames, total_steps)
                    if (process.returncode == 0 or attempt == 1 or self._preferred_encoder != 'auto'
                            or not self._is_hardware_encoder_failure(encoder, process.stderr)):
                        break
                    hardware_failure = (f"{encoder} (exit {process.returncode}): "
                                        + process.stderr.decode('utf-8', errors='replace')[-1500:])
                    cpu_encoder = 'libx265' if self._codec == 'h265' else 'libx264'
                    logger.warning("%s failed (exit %s); retrying with %s. FFmpeg stderr:\n%s",
                                   encoder, process.returncode, cpu_encoder,
                                   process.stderr.decode('utf-8', errors='replace'))
                    cmd[encoder_start:encoder_end] = self._video_encoder_options(cpu_encoder, crf, cpu_preset)
                stderr_text = process.stderr.decode('utf-8', errors='replace')
            except subprocess.TimeoutExpired:
                logger.error("MP4 encoding timeout")
                self._emit_error("MP4 인코딩 시간 초과")
                return False

            if process.returncode != 0:
                # 에러 코드를 signed/unsigned 모두 로깅
                signed_code = process.returncode if process.returncode < 2147483648 else process.returncode - 4294967296
                logger.error(f"[MP4] FFmpeg failed (returncode={process.returncode}, signed={signed_code})")
                if stderr_text:
                    logger.error("[MP4] FFmpeg stderr: %s", stderr_text)
                else:
                    logger.error("[MP4] No stderr output from FFmpeg")

                # 사용자에게 자세한 오류 메시지 제공
                error_details = f"{encoder} 인코딩 실패 (코드 {process.returncode})"
                if stderr_text:
                    # stderr에서 유용한 오류 메시지 추출
                    error_lines = [line for line in stderr_text.split('\n') if 'error' in line.lower() or 'fail' in line.lower()]
                    if error_lines:
                        error_details += f"\n\n세부사항:\n{error_lines[-1][:200]}"

                if hardware_failure:
                    error_details = hardware_failure + "\nCPU retry: " + error_details
                self._emit_error(error_details)
                return False

            logger.info(f"[MP4] Encoding completed successfully: {output_path}")
            self._emit_progress(total_steps, total_steps)
            return True

        except Exception as e:
            self._emit_error(f"MP4 인코딩 에러: {str(e)}")
            return False

    def is_gpu_mode(self) -> bool:
        """GPU 모드 사용 여부 (FFmpeg NVENC)"""
        return self._use_gpu and self._has_nvenc

    def set_gpu_mode(self, enabled: bool):
        """GPU 모드 설정 (FFmpeg NVENC)"""
        gpu_info = detect_gpu()
        if enabled and gpu_info.ffmpeg_nvenc:
            self._use_gpu = True
            self._has_nvenc = True
        else:
            self._use_gpu = False

    def refresh_gpu_status(self):
        """GPU 상태 새로고침"""
        gpu_info = detect_gpu()
        self._use_gpu = gpu_info.has_cuda
        self._has_nvenc = gpu_info.ffmpeg_nvenc

    @staticmethod
    def get_ffmpeg_install_instructions() -> str:
        """FFmpeg 설치 안내 메시지"""
        return """
FFmpeg가 설치되어 있지 않습니다.

고화질 GIF 생성을 위해 FFmpeg 설치를 권장합니다.

설치 방법:
1. Windows Terminal에서: winget install ffmpeg
2. 또는 https://ffmpeg.org/download.html 에서 다운로드

설치 후 프로그램을 재시작하세요.

(FFmpeg 없이도 Pillow로 인코딩이 가능하지만, 화질이 다소 낮을 수 있습니다.)
        """.strip()
