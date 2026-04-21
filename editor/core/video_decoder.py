"""
VideoDecoder - 비디오 파일 디코딩 (MP4, AVI, WebM 등)
GIF 변환을 위한 비디오 프레임 추출
"""
from __future__ import annotations
from typing import Optional, Tuple, Callable
from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import numpy as np

from .frame import Frame
from .frame_collection import FrameCollection


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

    @classmethod
    def error(cls, message: str) -> 'VideoLoadResult':
        return cls(success=False, error_message=message)

    @classmethod
    def ok(cls, frames: FrameCollection) -> 'VideoLoadResult':
        return cls(frames=frames, success=True)


class VideoDecoder:
    """비디오 파일 디코딩 클래스
    
    MP4, AVI, WebM, MOV 등의 비디오 파일을 GIF 프레임으로 변환합니다.
    imageio-ffmpeg 또는 PyAV를 사용합니다.
    """

    SUPPORTED_EXTENSIONS = {'.mp4', '.avi', '.webm', '.mov', '.mkv', '.wmv', '.flv', '.m4v'}

    @classmethod
    def is_available(cls) -> bool:
        """비디오 디코딩 가능 여부 확인 (시스템 FFmpeg 또는 imageio-ffmpeg)"""
        # imageio가 시스템 FFmpeg를 사용하도록 환경변수 설정
        cls._setup_ffmpeg_env()
        try:
            import imageio.v3 as iio
            return True
        except ImportError:
            return False

    @classmethod
    def _setup_ffmpeg_env(cls):
        """imageio가 시스템 FFmpeg를 찾을 수 있도록 환경변수 설정"""
        import os
        if os.environ.get('IMAGEIO_FFMPEG_EXE'):
            return  # 이미 설정됨
        try:
            from core.ffmpeg_installer import FFmpegManager
            ffmpeg_path = FFmpegManager.get_ffmpeg_executable()
            if ffmpeg_path:
                os.environ['IMAGEIO_FFMPEG_EXE'] = str(ffmpeg_path)
        except Exception:
            pass

    @classmethod
    def load(cls, file_path: str,
             target_fps: int = 10,
             max_frames: int = 500,
             start_time: float = 0.0,
             end_time: Optional[float] = None,
             resize: Optional[Tuple[int, int]] = None,
             progress_callback: Optional[Callable[[int, int], None]] = None
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
        
        Returns:
            VideoLoadResult: 로드 결과
        """
        path = Path(file_path)

        if not path.exists():
            return VideoLoadResult.error(f"파일을 찾을 수 없습니다: {file_path}")

        ext = path.suffix.lower()
        if ext not in cls.SUPPORTED_EXTENSIONS:
            return VideoLoadResult.error(f"지원하지 않는 비디오 형식입니다: {ext}")

        # imageio로 로드 시도
        try:
            cls._setup_ffmpeg_env()
            return cls._load_with_imageio(
                path, target_fps, max_frames,
                start_time, end_time, resize, progress_callback
            )
        except ImportError:
            return VideoLoadResult.error(
                "비디오 디코딩을 위해 FFmpeg가 필요합니다.\n"
                "설치: winget install ffmpeg 또는 설정 > FFmpeg 다운로드"
            )
        except Exception as e:
            return VideoLoadResult.error(f"비디오 로드 실패: {str(e)}")

    @classmethod
    def _load_with_imageio(cls, path: Path, target_fps: int, max_frames: int,
                           start_time: float, end_time: Optional[float],
                           resize: Optional[Tuple[int, int]],
                           progress_callback: Optional[Callable[[int, int], None]]
                           ) -> VideoLoadResult:
        """imageio를 사용하여 비디오 로드"""
        import imageio.v3 as iio

        collection = FrameCollection()

        # 비디오 메타데이터 읽기
        meta = iio.immeta(str(path), plugin="pyav")
        video_fps = meta.get('fps', 30)
        duration = meta.get('duration', 0)

        # 종료 시간 설정
        if end_time is None or end_time > duration:
            end_time = duration

        # 프레임 간격 계산 (target_fps에 맞게 샘플링)
        target_fps = max(1, target_fps)  # 0 방지
        frame_interval = max(1, int(video_fps / target_fps))

        # GIF 프레임 딜레이 (밀리초)
        delay_ms = int(1000 / target_fps)

        # 프레임 읽기 (스트리밍 방식 — 전체를 메모리에 로드하지 않음)
        start_frame = int(start_time * video_fps)
        end_frame = int(end_time * video_fps)

        # 샘플링할 프레임 인덱스 계산
        total_estimated = int(duration * video_fps) if duration > 0 else end_frame
        sample_indices = set(range(start_frame, min(end_frame, total_estimated), frame_interval))

        # 최대 프레임 수 제한
        if len(sample_indices) > max_frames:
            sorted_indices = sorted(sample_indices)
            step = len(sorted_indices) // max_frames
            sample_indices = set(sorted_indices[::step][:max_frames])

        # 프레임 스트리밍 (한 번에 하나씩 읽기)
        collected = 0
        total_to_collect = len(sample_indices)
        for frame_idx, frame_data in enumerate(iio.imiter(str(path), plugin="pyav")):
            if frame_idx > end_frame:
                break

            if frame_idx not in sample_indices:
                continue

            # RGB → RGBA
            if frame_data.ndim == 3:
                if frame_data.shape[2] == 3:
                    alpha = np.full((*frame_data.shape[:2], 1), 255, dtype=np.uint8)
                    frame_data = np.concatenate([frame_data, alpha], axis=2)

            img = Image.fromarray(frame_data, 'RGBA')

            # 리사이즈
            if resize:
                img = img.resize(resize, Image.Resampling.LANCZOS)

            frame = Frame(img, delay_ms)
            collection.add_frame(frame)
            collected += 1

            # 진행률 콜백
            if progress_callback:
                progress_callback(collected, total_to_collect)

        if collection.is_empty:
            return VideoLoadResult.error("비디오에서 프레임을 추출할 수 없습니다")

        return VideoLoadResult.ok(collection)

    @classmethod
    def get_video_info(cls, file_path: str) -> Optional[VideoInfo]:
        """비디오 파일 정보만 읽기"""
        try:
            import imageio.v3 as iio

            path = Path(file_path)
            if not path.exists():
                return None

            meta = iio.immeta(str(path), plugin="pyav")

            info = VideoInfo()
            info.width = meta.get('size', [0, 0])[0]
            info.height = meta.get('size', [0, 0])[1]
            info.fps = meta.get('fps', 0)
            info.duration = meta.get('duration', 0)
            info.codec = meta.get('codec', '')

            # 프레임 수 계산
            if info.fps > 0 and info.duration > 0:
                info.frame_count = int(info.fps * info.duration)

            return info

        except Exception:
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
