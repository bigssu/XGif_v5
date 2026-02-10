"""
고화질 GIF 인코더
FFmpeg의 palettegen + paletteuse 필터를 사용하여 원본에 가까운 품질 제공
GPU 가속: FFmpeg NVENC/hwaccel만 사용 (프레임 처리는 CPU가 더 효율적)
"""

import os
import shutil
import subprocess
import tempfile
import asyncio
import time
import stat
import gc
import uuid
import logging
import threading
from pathlib import Path
from typing import List, Optional, Callable
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from .utils import safe_rmtree, run_subprocess_silent

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
            if os.path.exists(temp_dir):
                if not safe_rmtree(temp_dir):
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
        raise RuntimeError(f"임시 디렉토리를 생성할 수 없습니다: {e}")

# GPU 유틸리티 (FFmpeg GPU 가속용)
from .gpu_utils import detect_gpu

# 이미지 I/O 최적화: imageio 우선, 폴백으로 PIL
from PIL import Image  # Pillow fallback용 (항상 필요)

try:
    import imageio
    HAS_IMAGEIO = True
except ImportError:
    HAS_IMAGEIO = False


def _save_frame_to_bmp(args):
    """프레임을 BMP로 저장 (최적화: imageio 우선 사용)"""
    idx, frame, out_dir = args
    try:
        # BGR to RGB 변환 (NumPy 뷰 연산 - 매우 빠름)
        rgb_frame = frame[:, :, ::-1]
        output_path = os.path.join(out_dir, f'{idx:06d}.bmp')
        
        if HAS_IMAGEIO:
            # imageio 사용 (더 빠름)
            imageio.imwrite(output_path, rgb_frame, format='BMP')
        else:
            # PIL 폴백
            img = Image.fromarray(rgb_frame)
            img.save(output_path, 'BMP')
    except Exception as e:
        logger.warning(f"프레임 {idx} 저장 실패: {e}")
    return idx


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
            try:
                self._progress_callback(current, total)
            except Exception:
                pass
    
    def _emit_finished(self, output_path: str):
        """완료 이벤트 발생"""
        if self._finished_callback:
            try:
                self._finished_callback(output_path)
            except Exception:
                pass
    
    def _emit_error(self, error_msg: str):
        """에러 이벤트 발생"""
        if self._error_callback:
            try:
                self._error_callback(error_msg)
            except Exception:
                pass
    
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
            if preferred and self._test_encoder(preferred):
                return preferred
        
        # 자동 선택
        available = self.detect_available_encoders()
        if codec == 'h265':
            return available.get('best_h265', 'libx265')
        else:
            return available.get('best_h264', 'libx264')
    
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
    
    def _run_ffmpeg_async(self, cmd: List[str]) -> subprocess.CompletedProcess:
        """비동기 FFmpeg 실행 (진행률 모니터링 가능)"""
        loop = None
        try:
            # asyncio를 사용한 비동기 실행
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._async_run_ffmpeg(cmd))
            return result
        except Exception as e:
            # asyncio 실패 시 동기 방식으로 폴백
            logger.warning("asyncio 실패, 동기 모드로 폴백: %s", e)
            return subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,  # 10분 타임아웃
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
        finally:
            # 이벤트 루프 안전하게 정리
            if loop is not None:
                try:
                    # 실행 중인 모든 태스크 취소
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()
                    
                    # 취소된 태스크가 완료될 때까지 대기
                    if pending:
                        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                except (RuntimeError, asyncio.CancelledError):
                    pass
                finally:
                    try:
                        loop.close()
                    except RuntimeError:
                        pass
    
    async def _async_run_ffmpeg(self, cmd: List[str], input_data: Optional[bytes] = None) -> subprocess.CompletedProcess:
        """비동기 FFmpeg 실행 (입력 데이터 지원)"""
        process = None
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE if input_data is not None else None,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            stdout, stderr = await asyncio.wait_for(
                process.communicate(input=input_data),
                timeout=600  # 10분 타임아웃
            )
            
            return subprocess.CompletedProcess(
                cmd,
                process.returncode if process.returncode is not None else -1,
                stdout=stdout.decode('utf-8', errors='ignore') if stdout else '',
                stderr=stderr.decode('utf-8', errors='ignore') if stderr else ''
            )
        except asyncio.TimeoutError:
            if process is not None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise
        except Exception as e:
            if process is not None:
                try:
                    process.kill()
                    await process.wait()
                except Exception:
                    pass
            raise

    def _write_frames_to_pipe(self, process, frames: List[np.ndarray], total_steps: int = 0):
        """FFmpeg 프로세스의 stdin으로 프레임 데이터 스트리밍
        
        Args:
            process: FFmpeg 서브프로세스
            frames: 프레임 리스트
            total_steps: 진행률 계산용 총 단계 수 (0이면 progress 미emit)
        """
        try:
            if process is None or process.stdin is None:
                logger.error("Invalid process or stdin")
                return
            
            frames_written = 0
            total_frames = len(frames)
            for i, frame in enumerate(frames):
                # 프레임 유효성 검증
                if frame is None or not isinstance(frame, np.ndarray):
                    logger.warning(f"Skipping invalid frame at index {i}")
                    continue
                
                # 프레임 크기 검증
                if frame.size == 0:
                    logger.warning(f"Skipping empty frame at index {i}")
                    continue
                
                # BGR to RGB 변환 (rawvideo는 RGB24 선호)
                # DXCam/GDI는 BGR24이므로 'bgr24' pix_fmt 설정 시 변환 불필요
                try:
                    frame_bytes = frame.tobytes()
                    process.stdin.write(frame_bytes)
                    frames_written += 1
                    
                    # 진행률 emit (MP4 인코딩 시 UI 업데이트용)
                    if total_steps > 0 and (frames_written % 10 == 0 or frames_written == total_frames):
                        self._emit_progress(frames_written, total_steps)
                    
                    # 진행 상황 로깅 (100프레임마다)
                    if (i + 1) % 100 == 0:
                        logger.debug(f"[Pipe] Written {i+1}/{total_frames} frames")
                        
                except (BrokenPipeError, OSError) as e:
                    logger.error(f"Pipe broken at frame {i}/{total_frames}: {e}")
                    break
            
            process.stdin.close()
            logger.info(f"[Pipe] Total frames written: {frames_written}/{total_frames}")
        except (IOError, OSError, ValueError) as e:
            logger.error(f"[GifEncoder] Pipe write error: {e}")
            try:
                if process and process.stdin:
                    process.stdin.close()
            except (BrokenPipeError, OSError):
                pass

    def _check_disk_space(self, output_path: str, frames: List[np.ndarray]) -> bool:
        """인코딩 전 디스크 공간 확인. 부족하면 False 반환."""
        try:
            output_dir = os.path.dirname(os.path.abspath(output_path)) or '.'
            usage = shutil.disk_usage(output_dir)
            # 예상 필요 공간: 원본 프레임 크기의 약 10% (GIF/MP4 압축 고려) + 여유 100MB
            estimated_raw = sum(f.nbytes for f in frames[:1]) * len(frames) if frames else 0
            estimated_needed = max(estimated_raw // 10, 100 * 1024 * 1024)  # 최소 100MB
            if usage.free < estimated_needed:
                free_mb = usage.free / (1024 * 1024)
                needed_mb = estimated_needed / (1024 * 1024)
                self._emit_error(f"디스크 공간 부족: {free_mb:.0f}MB 남음 (최소 {needed_mb:.0f}MB 필요)")
                return False
        except (OSError, AttributeError):
            pass  # 디스크 확인 실패 시 인코딩 계속 진행
        return True

    def encode(self, frames: List[np.ndarray], fps: int, output_path: str) -> bool:
        """프레임 리스트를 GIF로 인코딩 (Pipe 방식 우선)"""
        # 입력 검증
        if not frames:
            self._emit_error("인코딩할 프레임이 없습니다.")
            return False
        
        if fps <= 0 or fps > 120:
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

        # FFmpeg 사용 가능 시 파이프 방식으로 진행
        if self._ffmpeg_path:
            return self._encode_with_pipe(frames, output_path, fps)
        
        # FFmpeg 미설치 시 기존 BMP 방식 (Pillow) 폴백
        total_steps = len(frames) + 1
        temp_dir = _create_temp_dir(prefix='giffy_')
        frames_dir = os.path.join(temp_dir, 'frames')
        os.makedirs(frames_dir, exist_ok=True)
        
        try:
            self._save_frames_parallel(frames, frames_dir, total_steps)
            success = self._encode_with_pillow(frames_dir, output_path, fps, len(frames))
            self._emit_progress(total_steps, total_steps)
            return success
        except Exception as e:
            self._emit_error(f"Pillow 인코딩 에러: {str(e)}")
            return False
        finally:
            safe_rmtree(temp_dir)

    def _save_frames_parallel(self, frames: List[np.ndarray], frames_dir: str, total_steps: int):
        """프레임을 BMP로 병렬 저장 (Pillow 폴백용)"""
        args_list = [(i, frame, frames_dir) for i, frame in enumerate(frames)]
        max_workers = min(os.cpu_count() or 4, 8)
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            for done_idx in executor.map(_save_frame_to_bmp, args_list):
                self._emit_progress(done_idx + 1, total_steps)

    def _encode_with_pipe(self, frames: List[np.ndarray], output_path: str, fps: int) -> bool:
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
                self._ffmpeg_path, '-y',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f"{w}x{h}", '-pix_fmt', 'bgr24', '-framerate', str(fps),
                '-i', '-',
                '-vf', palettegen_filter,
                palette_path
            ]
            
            process = subprocess.Popen(
                cmd_palette, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # 프레임 스트리밍 (Pass 1) - 예외 시 프로세스 kill 보장
            try:
                self._write_frames_to_pipe(process, frames)
                _, stderr = process.communicate()
            except Exception:
                try:
                    process.kill()
                    process.communicate(timeout=5)
                except Exception:
                    pass
                raise

            if process.returncode != 0:
                self._emit_error(f"팔레트 생성 실패: {stderr.decode('utf-8', errors='ignore')}")
                return False

            self._emit_progress(total_frames, total_steps)
            
            # Pass 2: GIF Generation via Pipe
            paletteuse_opts = [f"dither={preset['dither']}"]
            if 'bayer_scale' in preset: paletteuse_opts.append(f"bayer_scale={preset['bayer_scale']}")
            if preset.get('diff_mode') and preset['diff_mode'] != 'none':
                paletteuse_opts.append(f"diff_mode={preset['diff_mode']}")
            paletteuse_filter = f"paletteuse={':'.join(paletteuse_opts)}"
            
            filter_complex = f"[0:v][1:v]{paletteuse_filter}"
            
            cmd_gif = [
                self._ffmpeg_path, '-y',
                '-f', 'rawvideo', '-vcodec', 'rawvideo',
                '-s', f"{w}x{h}", '-pix_fmt', 'bgr24', '-framerate', str(fps),
                '-i', '-',
                '-i', palette_path,
                '-lavfi', filter_complex,
                '-loop', '0',
                output_path
            ]
            
            process = subprocess.Popen(
                cmd_gif, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            # 프레임 스트리밍 (Pass 2) - 타임아웃 및 예외 시 프로세스 kill 보장
            try:
                self._write_frames_to_pipe(process, frames)
                _, stderr = process.communicate(timeout=600)  # 10분 타임아웃
            except subprocess.TimeoutExpired:
                logger.error("GIF generation timeout")
                process.kill()
                try:
                    process.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                self._emit_error("GIF 생성 시간 초과")
                return False
            except Exception:
                try:
                    process.kill()
                    process.communicate(timeout=5)
                except Exception:
                    pass
                raise
            
            if process.returncode != 0:
                error_msg = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                self._emit_error(f"GIF 생성 실패: {error_msg}")
                return False
            
            self._emit_progress(total_steps, total_steps)
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"Pipe 인코딩 에러: {str(e)}")
            return False
        finally:
            safe_rmtree(temp_dir)
    
    def _encode_with_ffmpeg(self, frames_dir: str, output_path: str, fps: int, frame_count: int) -> bool:
        """
        FFmpeg를 사용한 고화질 GIF 인코딩
        
        2-pass 방식:
        - Pass 1: palettegen으로 영상 전체에서 최적 256색 팔레트 생성
        - Pass 2: paletteuse로 팔레트 적용하여 GIF 생성
        
        GPU 가속 (NVENC 사용 가능 시):
        - hwaccel cuda로 디코딩 가속
        """
        preset = self.QUALITY_PRESETS[self.quality]
        temp_dir = os.path.dirname(frames_dir)
        palette_path = os.path.join(temp_dir, 'palette.png')
        
        # palettegen 필터 구성
        palettegen_filter = f"palettegen=max_colors={preset['max_colors']}:stats_mode={preset['stats_mode']}"
        
        # paletteuse 필터 구성
        paletteuse_opts = [f"dither={preset['dither']}"]
        if 'bayer_scale' in preset:
            paletteuse_opts.append(f"bayer_scale={preset['bayer_scale']}")
        if preset.get('diff_mode') and preset['diff_mode'] != 'none':
            paletteuse_opts.append(f"diff_mode={preset['diff_mode']}")
        paletteuse_filter = f"paletteuse={':'.join(paletteuse_opts)}"
        
        # GPU 가속 옵션
        hwaccel_opts = []
        if self._use_gpu and self._has_nvenc:
            hwaccel_opts = ['-hwaccel', 'cuda', '-hwaccel_output_format', 'cuda']
        
        total_steps = frame_count * 2 + 2
        try:
            # Pass 1: 팔레트 생성
            self._emit_progress(0, total_steps)
            cmd_palette = [
                self._ffmpeg_path,
                '-y',  # 덮어쓰기
            ]
            if hwaccel_opts:
                cmd_palette.extend(hwaccel_opts)
            cmd_palette.extend([
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
                '-vf', palettegen_filter,
                palette_path
            ])

            result = subprocess.run(
                cmd_palette,
                capture_output=True,
                text=True,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                # GPU 모드 실패 시 CPU로 재시도
                if hwaccel_opts:
                    return self._encode_with_ffmpeg_cpu(frames_dir, output_path, fps, frame_count)
                self._emit_error(f"팔레트 생성 실패: {result.stderr}")
                return False

            self._emit_progress(frame_count, total_steps)

            # Pass 2: GIF 생성
            filter_complex = f"[0:v][1:v]{paletteuse_filter}"

            cmd_gif = [
                self._ffmpeg_path,
                '-y',
            ]
            if hwaccel_opts:
                cmd_gif.extend(hwaccel_opts)
            cmd_gif.extend([
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
                '-i', palette_path,
                '-lavfi', filter_complex,
                '-loop', '0',  # 무한 반복
                output_path
            ])

            result = subprocess.run(
                cmd_gif,
                capture_output=True,
                text=True,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )

            if result.returncode != 0:
                # GPU 모드 실패 시 CPU로 재시도
                if hwaccel_opts:
                    return self._encode_with_ffmpeg_cpu(frames_dir, output_path, fps, frame_count)
                self._emit_error(f"GIF 생성 실패: {result.stderr}")
                return False

            self._emit_progress(total_steps, total_steps)
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"FFmpeg 실행 에러: {str(e)}")
            return False
    
    def _encode_with_ffmpeg_cpu(self, frames_dir: str, output_path: str, fps: int, frame_count: int) -> bool:
        """CPU 전용 FFmpeg 인코딩 (GPU 실패 시 fallback)"""
        preset = self.QUALITY_PRESETS[self.quality]
        temp_dir = os.path.dirname(frames_dir)
        palette_path = os.path.join(temp_dir, 'palette.png')

        palettegen_filter = f"palettegen=max_colors={preset['max_colors']}:stats_mode={preset['stats_mode']}"

        paletteuse_opts = [f"dither={preset['dither']}"]
        if 'bayer_scale' in preset:
            paletteuse_opts.append(f"bayer_scale={preset['bayer_scale']}")
        if preset.get('diff_mode') and preset['diff_mode'] != 'none':
            paletteuse_opts.append(f"diff_mode={preset['diff_mode']}")
        paletteuse_filter = f"paletteuse={':'.join(paletteuse_opts)}"

        total_steps = frame_count * 2 + 2
        try:
            # Pass 1: 팔레트 생성 (CPU)
            self._emit_progress(0, total_steps)
            cmd_palette = [
                self._ffmpeg_path,
                '-y',
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
                '-vf', palettegen_filter,
                palette_path
            ]
            
            result = self._run_ffmpeg_async(cmd_palette)

            if result.returncode != 0:
                self._emit_error(f"팔레트 생성 실패: {result.stderr}")
                return False

            self._emit_progress(frame_count, total_steps)

            # Pass 2: GIF 생성 (CPU)
            filter_complex = f"[0:v][1:v]{paletteuse_filter}"
            
            cmd_gif = [
                self._ffmpeg_path,
                '-y',
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
                '-i', palette_path,
                '-lavfi', filter_complex,
                '-loop', '0',
                output_path
            ]
            
            result = self._run_ffmpeg_async(cmd_gif)
            
            if result.returncode != 0:
                self._emit_error(f"GIF 생성 실패: {result.stderr}")
                return False

            self._emit_progress(total_steps, total_steps)
            self._emit_finished(output_path)
            return True

        except Exception as e:
            self._emit_error(f"FFmpeg 실행 에러: {str(e)}")
            return False

    def _encode_with_pillow(self, frames_dir: str, output_path: str, fps: int, frame_count: int) -> bool:
        """
        Pillow를 사용한 GIF 인코딩 (FFmpeg 없을 때 fallback)
        """
        try:
            # 프레임 로드
            total_steps = frame_count + 1
            images = []
            for i in range(frame_count):
                img_path = os.path.join(frames_dir, f'{i:06d}.bmp')
                # with 문으로 파일 핸들 자동 해제
                with Image.open(img_path) as img:
                    rgb_img = img.convert('RGB')

                    # 품질에 따른 양자화 설정
                    if self.quality == 'high':
                        quantized = rgb_img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
                    elif self.quality == 'medium':
                        quantized = rgb_img.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
                    else:
                        quantized = rgb_img.quantize(colors=128, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)

                    images.append(quantized.convert('P'))

                # 진행률 업데이트 (10프레임마다)
                if (i + 1) % 10 == 0 or i == frame_count - 1:
                    self._emit_progress(i + 1, total_steps)
            
            # GIF 저장
            duration = int(1000 / fps)
            images[0].save(
                output_path,
                save_all=True,
                append_images=images[1:],
                duration=duration,
                loop=0,
                optimize=True
            )
            
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"Pillow 인코딩 에러: {str(e)}")
            return False
    
    def encode_mp4(self, frames: List[np.ndarray], fps: int, output_path: str, audio_path: Optional[str] = None) -> bool:
        """프레임 리스트를 MP4로 인코딩 (Pipe 방식)"""
        # 입력 검증
        if not frames:
            self._emit_error("인코딩할 프레임이 없습니다.")
            return False
        
        if fps <= 0 or fps > 120:
            logger.error(f"Invalid FPS: {fps}")
            self._emit_error(f"유효하지 않은 FPS 값: {fps}")
            return False
        
        if not output_path or not isinstance(output_path, str):
            logger.error(f"Invalid output path: {output_path}")
            self._emit_error("유효하지 않은 출력 경로입니다.")
            return False
        
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

        # yuv420p 제약: 너비와 높이는 2의 배수여야 함
        # 홀수 크기인 경우 1픽셀 잘라내기 (크롭)
        original_h, original_w = h, w
        if w % 2 != 0:
            w = w - 1
            logger.warning(f"[MP4] Width {original_w} is odd, cropping to {w}")
        if h % 2 != 0:
            h = h - 1
            logger.warning(f"[MP4] Height {original_h} is odd, cropping to {h}")

        # 프레임 크롭이 필요한 경우
        if w != original_w or h != original_h:
            logger.info(f"[MP4] Cropping frames from {original_w}x{original_h} to {w}x{h}")
            cropped_frames = []
            for frame in frames:
                cropped_frame = frame[:h, :w]  # numpy slicing으로 크롭
                cropped_frames.append(cropped_frame)
            frames = cropped_frames

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
            
            cmd.extend(['-c:v', encoder])
            
            if encoder in ('h264_nvenc', 'hevc_nvenc'):
                cmd.extend(['-preset', 'p4', '-cq', crf])
            elif encoder in ('h264_qsv', 'hevc_qsv'):
                cmd.extend(['-preset', 'medium', '-global_quality', crf])
            elif encoder in ('h264_amf', 'hevc_amf'):
                cmd.extend(['-quality', 'balanced', '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf])
            else:
                cmd.extend(['-preset', cpu_preset, '-crf', crf])
            
            cmd.extend([
                '-r', str(fps),  # 출력 프레임레이트 (명시적으로 설정!)
                '-pix_fmt', 'yuv420p'
            ])
            
            if has_audio:
                cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-shortest'])
            
            cmd.append(output_path)
            
            # 디버깅: FFmpeg 명령어 로깅
            logger.info(f"[MP4] Encoding {total_frames} frames at {fps} FPS using {encoder}")
            logger.debug(f"[MP4] FFmpeg command: {' '.join(cmd)}")
            
            process = subprocess.Popen(
                cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            # stderr를 별도 스레드에서 읽기 (버퍼 가득 차서 블로킹 방지)
            stderr_data = []
            def read_stderr():
                """stderr를 읽어서 버퍼 블로킹 방지"""
                try:
                    for line in iter(process.stderr.readline, b''):
                        stderr_data.append(line)
                    process.stderr.close()
                except Exception as e:
                    logger.debug(f"[MP4] stderr reader error: {e}")
            
            stderr_thread = threading.Thread(target=read_stderr, daemon=True)
            stderr_thread.start()
            
            # 프레임 스트리밍 - 타임아웃 추가
            stderr_text = ""
            try:
                logger.info(f"[MP4] Writing {total_frames} frames to FFmpeg pipe...")
                self._emit_progress(0, total_steps)  # 시작 시 0% emit
                self._write_frames_to_pipe(process, frames, total_steps)

                # stderr 스레드를 먼저 join (교착 방지: stderr 버퍼가 차면 process.wait() 블로킹)
                stderr_thread.join(timeout=10)
                process.wait(timeout=600)  # 10분 타임아웃
                
                # FFmpeg 출력 로깅 (디버깅용)
                if stderr_data:
                    stderr_text = b''.join(stderr_data).decode('utf-8', errors='ignore')
                    # 프레임 정보 추출
                    import re
                    frame_matches = re.findall(r'frame=\s*(\d+)', stderr_text)
                    if frame_matches:
                        encoded_frames = frame_matches[-1]
                        logger.info(f"[MP4] FFmpeg encoded {encoded_frames} frames")
                    
                    # FPS 정보 추출
                    fps_matches = re.findall(r'fps=\s*([\d.]+)', stderr_text)
                    if fps_matches:
                        encoding_fps = fps_matches[-1]
                        logger.info(f"[MP4] Encoding FPS: {encoding_fps}")
                else:
                    stderr_text = ""
                        
            except subprocess.TimeoutExpired:
                logger.error("MP4 encoding timeout")
                process.kill()
                stderr_thread.join(timeout=2)
                self._emit_error("MP4 인코딩 시간 초과")
                return False
            except Exception:
                try:
                    process.kill()
                    stderr_thread.join(timeout=2)
                except Exception:
                    pass
                raise
            
            if process.returncode != 0:
                # 에러 코드를 signed/unsigned 모두 로깅
                signed_code = process.returncode if process.returncode < 2147483648 else process.returncode - 4294967296
                logger.error(f"[MP4] FFmpeg failed (returncode={process.returncode}, signed={signed_code})")
                if stderr_text:
                    logger.error(f"[MP4] FFmpeg stderr: {stderr_text[:1000]}")  # 처음 1000자
                else:
                    logger.error("[MP4] No stderr output from FFmpeg")

                # 사용자에게 자세한 오류 메시지 제공
                error_details = f"인코딩 실패 (코드 {process.returncode})"
                if stderr_text:
                    # stderr에서 유용한 오류 메시지 추출
                    import re
                    error_lines = [line for line in stderr_text.split('\n') if 'error' in line.lower() or 'fail' in line.lower()]
                    if error_lines:
                        error_details += f"\n\n세부사항:\n{error_lines[-1][:200]}"

                self._emit_error(error_details)
                return False
            
            logger.info(f"[MP4] Encoding completed successfully: {output_path}")
            self._emit_progress(total_steps, total_steps)
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"MP4 인코딩 에러: {str(e)}")
            return False
    
    def _encode_mp4_with_ffmpeg(self, frames_dir: str, output_path: str, fps: int, frame_count: int, audio_path: Optional[str] = None) -> bool:
        """FFmpeg를 사용한 MP4 인코딩 (H.264/H.265, NVENC/QSV/AMF 지원)"""
        try:
            # 품질 설정
            if self.quality == 'high':
                crf = '18'
                cpu_preset = 'slow'
            elif self.quality == 'medium':
                crf = '23'
                cpu_preset = 'medium'
            else:
                crf = '28'
                cpu_preset = 'fast'
            
            # 오디오 파일 존재 여부 확인
            has_audio = audio_path and os.path.exists(audio_path)
            
            # 최적 인코더 선택
            encoder = self._get_best_encoder(self._codec)
            is_hw_encoder = encoder not in ('libx264', 'libx265')
            
            logger.info("코덱: %s, 인코더: %s (%s)", self._codec.upper(), encoder, self.get_encoder_display_name(encoder))
            
            # 명령어 구성
            cmd = [
                self._ffmpeg_path,
                '-y',
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
            ]
            if has_audio:
                cmd.extend(['-i', audio_path])
            
            # 인코더별 옵션 설정
            cmd.extend(['-c:v', encoder])
            
            if encoder in ('h264_nvenc', 'hevc_nvenc'):
                # NVIDIA NVENC
                cmd.extend(['-preset', 'p4', '-cq', crf])
            elif encoder in ('h264_qsv', 'hevc_qsv'):
                # Intel QSV
                cmd.extend(['-preset', 'medium', '-global_quality', crf])
            elif encoder in ('h264_amf', 'hevc_amf'):
                # AMD AMF
                cmd.extend(['-quality', 'balanced', '-rc', 'cqp', '-qp_i', crf, '-qp_p', crf])
            else:
                # CPU (libx264/libx265)
                cmd.extend(['-preset', cpu_preset, '-crf', crf])
            
            cmd.extend(['-pix_fmt', 'yuv420p'])
            
            if has_audio:
                cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-shortest'])
            
            cmd.append(output_path)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                # 하드웨어 인코더 실패 시 CPU로 재시도
                if is_hw_encoder:
                    logger.warning("%s 실패, CPU 폴백...", encoder)
                    return self._encode_mp4_cpu_fallback(frames_dir, output_path, fps, crf, audio_path)
                self._emit_error(f"MP4 생성 실패: {result.stderr}")
                return False
            
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"FFmpeg 실행 에러: {str(e)}")
            return False
    
    def _encode_mp4_cpu_fallback(self, frames_dir: str, output_path: str, fps: int, crf: str, audio_path: Optional[str] = None) -> bool:
        """CPU 전용 MP4 인코딩 (GPU 실패 시 fallback)"""
        try:
            has_audio = audio_path and os.path.exists(audio_path)
            
            # 코덱에 따른 CPU 인코더 선택
            cpu_encoder = 'libx265' if self._codec == 'h265' else 'libx264'
            
            cmd = [
                self._ffmpeg_path,
                '-y',
                '-framerate', str(fps),
                '-i', os.path.join(frames_dir, '%06d.bmp'),
            ]
            if has_audio:
                cmd.extend(['-i', audio_path])
            
            cmd.extend([
                '-c:v', cpu_encoder,
                '-preset', 'medium',
                '-crf', crf,
                '-pix_fmt', 'yuv420p',
            ])
            if has_audio:
                cmd.extend(['-c:a', 'aac', '-b:a', '192k', '-shortest'])
            
            cmd.append(output_path)
            
            logger.info("CPU 폴백: %s", cpu_encoder)
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                env=self._ffmpeg_env,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            )
            
            if result.returncode != 0:
                self._emit_error(f"MP4 생성 실패: {result.stderr}")
                return False
            
            self._emit_finished(output_path)
            return True
            
        except Exception as e:
            self._emit_error(f"FFmpeg 실행 에러: {str(e)}")
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
