"""
VideoDecoder - 비디오 파일 디코딩 (MP4, AVI, WebM 등)
GIF 변환을 위한 비디오 프레임 추출
"""
from __future__ import annotations
import json
import math
import os
import shutil
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager, suppress
from fractions import Fraction
from typing import Optional, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass
from PIL import Image

from .frame import Frame
from .frame_collection import FrameCollection


def _check_interrupted(cancel_event, deadline):
    if cancel_event is not None and cancel_event.is_set():
        raise InterruptedError("작업이 취소되었습니다")
    if time.monotonic() >= deadline:
        raise TimeoutError("비디오 로드 제한시간을 초과했습니다")


@contextmanager
def _watch_process(process, cancel_event, deadline):
    """Kill a stalled child to unblock pipe reads; always reap it and join the watchdog."""
    finished = threading.Event()
    interruption = []

    def watch():
        while not finished.wait(0.05):
            try:
                _check_interrupted(cancel_event, deadline)
            except (InterruptedError, TimeoutError) as error:
                interruption.append(error)
                if process.poll() is None:
                    # The child may have exited between poll and kill.
                    with suppress(OSError):
                        process.kill()
                return

    watcher = threading.Thread(target=watch, name='video-decoder-watchdog')
    watcher.start()
    try:
        _check_interrupted(cancel_event, deadline)
        yield
    finally:
        finished.set()
        try:
            if process.poll() is None:
                process.kill()
            process.wait()
        finally:
            watcher.join()
            process.stdout.close()
        if interruption:
            raise interruption[0]
        _check_interrupted(cancel_event, deadline)


@dataclass
class VideoInfo:
    """비디오 파일 정보"""
    width: int = 0
    height: int = 0
    fps: float = 0.0
    duration: float = 0.0  # 초 단위
    frame_count: int = 0
    codec: str = ""


@dataclass
class VideoLoadResult:
    """비디오 로드 결과"""
    frames: Optional[FrameCollection] = None
    success: bool = False
    error_message: str = ""
    cancelled: bool = False

    @classmethod
    def error(cls, message: str) -> 'VideoLoadResult':
        return cls(success=False, error_message=message)

    @classmethod
    def ok(cls, frames: FrameCollection) -> 'VideoLoadResult':
        return cls(frames=frames, success=True)


class VideoDecoder:
    """비디오 파일 디코딩 클래스

    MP4, AVI, WebM, MOV 등의 비디오 파일을 GIF 프레임으로 변환합니다.
    설치된 FFmpeg와 FFprobe를 사용합니다.
    """

    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.webm', '.mov', '.mkv', '.wmv', '.flv', '.m4v'}

    @classmethod
    def _ffmpeg_tools(cls):
        from core.ffmpeg_installer import FFmpegManager

        ffmpeg = FFmpegManager.get_ffmpeg_executable()
        if not ffmpeg:
            raise FileNotFoundError("FFmpeg가 설치되어 있지 않습니다")
        sibling = Path(ffmpeg).with_name('ffprobe.exe' if os.name == 'nt' else 'ffprobe')
        ffprobe = str(sibling) if sibling.is_file() else shutil.which('ffprobe')
        if not ffprobe:
            raise FileNotFoundError("FFprobe가 설치되어 있지 않습니다")
        return ffmpeg, ffprobe

    @classmethod
    def is_available(cls) -> bool:
        """설치된 FFmpeg와 FFprobe 사용 가능 여부."""
        try:
            cls._ffmpeg_tools()
            return True
        except OSError:
            return False

    @classmethod
    def load(cls, file_path: str,
             target_fps: int = 10,
             max_frames: int = 500,
             start_time: float = 0.0,
             end_time: Optional[float] = None,
             resize: Optional[Tuple[int, int]] = None,
             progress_callback: Optional[Callable[[int, int], None]] = None,
             cancel_event: Optional[threading.Event] = None,
             timeout: float = 3600.0
             ) -> VideoLoadResult:
        """비디오 파일을 프레임 컬렉션으로 로드

        Args:
            file_path: 비디오 파일 경로
            target_fps: 추출할 FPS (기본 10fps - GIF에 적합)
            max_frames: 최대 프레임 수 (메모리 보호)
            start_time: 시작 시간 (초)
            end_time: 종료 시간 (초, None이면 끝까지)
            resize: 리사이즈 크기 (width, height), None이면 원본
            progress_callback: 진행률 콜백 (current, total)
            cancel_event: 설정 시 읽기 대기 중에도 디코더를 중단합니다.
            timeout: 메타데이터 조회부터 디코딩 종료까지의 제한시간(초).

        Returns:
            VideoLoadResult: 로드 결과
        """
        path = Path(file_path)

        if not path.exists():
            return VideoLoadResult.error(f"파일을 찾을 수 없습니다: {file_path}")

        ext = path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            return VideoLoadResult.error(f"지원하지 않는 비디오 형식입니다: {ext}")

        try:
            if not math.isfinite(timeout) or timeout <= 0:
                return VideoLoadResult.error("제한시간은 양의 유한한 값이어야 합니다")
            deadline = time.monotonic() + timeout
            _check_interrupted(cancel_event, deadline)
            return cls._load_with_ffmpeg(
                path, target_fps, max_frames,
                start_time, end_time, resize, progress_callback, cancel_event, deadline
            )
        except InterruptedError as e:
            return VideoLoadResult(cancelled=True, error_message=str(e))
        except ImportError:
            return VideoLoadResult.error(
                "비디오 디코딩을 위해 FFmpeg가 필요합니다.\n"
                "설치: winget install ffmpeg 또는 설정 > FFmpeg 다운로드"
            )
        except Exception as e:
            return VideoLoadResult.error(f"비디오 로드 실패: {str(e)}")

    @classmethod
    def _load_with_ffmpeg(cls, path: Path, target_fps: int, max_frames: int,
                          start_time: float, end_time: Optional[float],
                          resize: Optional[Tuple[int, int]],
                          progress_callback: Optional[Callable[[int, int], None]],
                          cancel_event, deadline
                          ) -> VideoLoadResult:
        ffmpeg, _ = cls._ffmpeg_tools()
        info = cls.get_video_info(str(path), cancel_event=cancel_event,
                                  timeout=max(0.001, deadline - time.monotonic()))
        _check_interrupted(cancel_event, deadline)
        if info is None:
            return VideoLoadResult.error("비디오 메타데이터를 읽을 수 없습니다")
        if (not math.isfinite(target_fps) or target_fps <= 0
                or not isinstance(max_frames, int) or max_frames <= 0
                or not math.isfinite(start_time) or start_time < 0
                or (end_time is not None and not math.isfinite(end_time))):
            return VideoLoadResult.error("잘못된 비디오 추출 범위 또는 프레임 수입니다")
        stop = min(info.duration, end_time) if end_time is not None else info.duration
        duration = stop - start_time
        if duration <= 0:
            return VideoLoadResult.error("비디오 추출 범위가 비어 있습니다")
        width, height = resize if resize is not None else (info.width, info.height)
        if any(not isinstance(value, int) or value <= 0 for value in (width, height)):
            return VideoLoadResult.error("잘못된 이미지 크기입니다")

        # Uniform output timestamps bound memory and keep the whole selected clip's duration.
        duration_ms = round(duration * 1000)
        count = min(max_frames, max(1, math.ceil(duration * min(target_fps, info.fps))),
                    max(1, duration_ms // 10))
        filters = f'fps={count / duration:.12g}:start_time=0'
        if resize is not None:
            filters += f',scale={width}:{height}:flags=lanczos'
        command = [ffmpeg, '-v', 'error', '-nostdin', '-ss', str(start_time), '-i', str(path),
                   '-t', str(duration), '-map', '0:v:0', '-an', '-sn', '-dn',
                   '-vf', filters, '-frames:v', str(count), '-pix_fmt', 'rgb24',
                   '-f', 'rawvideo', 'pipe:1']
        collection = FrameCollection()
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            with _watch_process(process, cancel_event, deadline):
                frame_size = width * height * 3
                for index in range(count):
                    _check_interrupted(cancel_event, deadline)
                    data = process.stdout.read(frame_size)
                    if len(data) != frame_size:
                        raise ValueError("비디오 프레임 데이터가 불완전합니다")
                    image = Image.frombytes('RGB', (width, height), data)
                    delay = round((index + 1) * duration_ms / count) - round(index * duration_ms / count)
                    collection.add_frame(Frame(image, delay))
                    if progress_callback:
                        progress_callback(index + 1, count)
                if process.wait() != 0:
                    errors.seek(0)
                    raise ValueError(errors.read(4096).decode('utf-8', errors='replace'))
        return VideoLoadResult.ok(collection)

    @classmethod
    def _probe(cls, file_path, cancel_event, deadline):
        _, ffprobe = cls._ffmpeg_tools()
        command = [ffprobe, '-v', 'error', '-select_streams', 'v:0',
                   '-show_entries', 'stream=width,height,avg_frame_rate,r_frame_rate,duration,nb_frames,codec_name:stream_side_data=rotation:stream_tags=rotate:format=duration',
                   '-of', 'json', str(file_path)]
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
            with _watch_process(process, cancel_event, deadline):
                output = process.stdout.read()
                if process.wait() != 0:
                    raise ValueError("비디오 메타데이터를 읽을 수 없습니다")
                return output.decode('utf-8')

    @classmethod
    def get_video_info(cls, file_path: str, cancel_event: Optional[threading.Event] = None,
                       timeout: float = 30.0) -> Optional[VideoInfo]:
        """FFprobe JSON 메타데이터를 읽고 사용할 수 없는 값은 거부합니다."""
        try:
            if not Path(file_path).is_file():
                return None
            if not math.isfinite(timeout) or timeout <= 0:
                raise ValueError("제한시간은 양의 유한한 값이어야 합니다")
            deadline = time.monotonic() + timeout
            _check_interrupted(cancel_event, deadline)
            meta = json.loads(cls._probe(file_path, cancel_event, deadline))
            stream = meta['streams'][0]
            if not isinstance(stream, dict):
                return None
            rate = stream.get('avg_frame_rate')
            if rate in (None, '0/0', '0/1', 'N/A'):
                rate = stream.get('r_frame_rate', '0')
            fps = float(Fraction(rate))
            duration_value = stream.get('duration')
            if duration_value in (None, 'N/A'):
                duration_value = meta.get('format', {}).get('duration')
            count_value = stream.get('nb_frames')
            count = int(count_value) if count_value not in (None, 'N/A') else 0
            duration = float(duration_value) if duration_value is not None else count / fps
            width, height = int(stream['width']), int(stream['height'])
            rotation = next((entry['rotation'] for entry in stream.get('side_data_list', [])
                             if 'rotation' in entry), stream.get('tags', {}).get('rotate', 0))
            # FFmpeg autorotates before emitting raw pixels, so use display dimensions.
            if math.isclose(float(rotation) % 180, 90, abs_tol=0.01):
                width, height = height, width
            if (width <= 0 or height <= 0 or not math.isfinite(fps) or fps <= 0
                    or not math.isfinite(duration) or duration <= 0):
                return None
            return VideoInfo(width, height, fps, duration, count or round(duration * fps),
                             stream.get('codec_name', ''))
        except (InterruptedError, TimeoutError):
            raise
        except (OSError, ValueError, TypeError, KeyError, IndexError, ZeroDivisionError, subprocess.SubprocessError):
            return None

    @classmethod
    def is_supported_file(cls, file_path: str) -> bool:
        """지원되는 비디오 파일인지 확인"""
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS

    @classmethod
    def get_file_filter(cls) -> str:
        """파일 대화상자용 필터 문자열"""
        return "Video Files (*.mp4 *.avi *.webm *.mov *.mkv)"

    @classmethod
    def estimate_gif_frames(cls, video_info: VideoInfo, target_fps: int = 10) -> int:
        """GIF로 변환 시 예상 프레임 수"""
        if video_info.duration <= 0:
            return 0
        return int(video_info.duration * target_fps)

    @classmethod
    def estimate_memory_usage(cls, video_info: VideoInfo, target_fps: int = 10) -> int:
        """예상 메모리 사용량 (바이트)"""
        frame_count = cls.estimate_gif_frames(video_info, target_fps)
        # RGBA 이미지 기준
        return video_info.width * video_info.height * 4 * frame_count
