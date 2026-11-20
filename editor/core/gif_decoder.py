"""
GifDecoder - GIF/이미지/비디오 파일 디코딩
"""
from __future__ import annotations
from typing import Optional, List, Callable
from pathlib import Path
from dataclasses import dataclass
from PIL import Image, PngImagePlugin, __version__ as pillow_version
import glob
import os
import math
import threading
import time

from .frame import Frame
from .frame_collection import FrameCollection


def _load_animation_frame(image: Image.Image) -> None:
    # Pillow 13.0.0 blends into the buffer it later uses for PREVIOUS disposal.
    # Preserve that canvas for this decoder instance (python-pillow/Pillow#10400).
    if (pillow_version == "13.0.0" and isinstance(image, PngImagePlugin.PngImageFile)
            and image.info.get("disposal") == PngImagePlugin.Disposal.OP_PREVIOUS
            and image.info.get("blend") == PngImagePlugin.Blend.OP_OVER
            and image._prev_im is not None):
        previous = image._prev_im.copy()
        image.load()
        image._prev_im = previous
    else:
        image.load()


@dataclass
class LoadResult:
    """로드 결과"""
    frames: Optional[FrameCollection] = None
    success: bool = False
    error_message: str = ""
    cancelled: bool = False

    @classmethod
    def error(cls, message: str) -> 'LoadResult':
        return cls(success=False, error_message=message)

    @classmethod
    def ok(cls, frames: FrameCollection) -> 'LoadResult':
        return cls(frames=frames, success=True)


@dataclass
class GifInfo:
    """GIF 파일 정보"""
    width: int = 0
    height: int = 0
    frame_count: int = 0
    total_duration: int = 0
    loop_count: int = 0


class GifDecoder:
    """GIF/이미지/비디오 파일 디코딩 클래스"""

    SUPPORTED_EXTENSIONS = {'.gif', '.apng', '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.webm', '.mov', '.mkv', '.wmv', '.flv', '.m4v'}

    @classmethod
    def load(cls, file_path: str,
             video_fps: int = 10,
             video_max_frames: int = 500,
             progress_callback: Optional[Callable[[int, int], None]] = None,
             cancel_event: Optional[threading.Event] = None,
             timeout: float = 3600.0
             ) -> LoadResult:
        """GIF, 이미지 또는 비디오 파일 로드

        Args:
            file_path: 파일 경로
            video_fps: 비디오 파일의 경우 추출할 FPS (기본 10)
            video_max_frames: 비디오 파일의 경우 최대 프레임 수 (기본 500)
            progress_callback: 진행률 콜백 (current, total)
            cancel_event: GIF 프레임 사이 또는 비디오 읽기 대기 중 취소 신호.
            timeout: 로드 제한시간(초); Pillow 처리는 프레임 사이에 확인합니다.

        Returns:
            LoadResult: 로드 결과
        """
        path = Path(file_path)

        if not path.exists():
            return LoadResult.error(f"파일을 찾을 수 없습니다: {file_path}")

        ext = path.suffix.lower()

        if not math.isfinite(timeout) or timeout <= 0:
            return LoadResult.error("제한시간은 양의 유한한 값이어야 합니다")
        deadline = time.monotonic() + timeout

        def check():
            if cancel_event is not None and cancel_event.is_set():
                raise InterruptedError("작업이 취소되었습니다")
            if time.monotonic() >= deadline:
                raise TimeoutError("이미지 로드 제한시간을 초과했습니다")

        def progress(current, total):
            check()
            if progress_callback is not None:
                progress_callback(current, total)
            check()

        try:
            check()
            if ext in cls.VIDEO_EXTENSIONS:
                return cls._load_video(path, video_fps, video_max_frames, progress_callback,
                                       cancel_event, timeout)
            elif ext in cls.SUPPORTED_EXTENSIONS:
                result = cls._load_image(path, progress)
            else:
                return LoadResult.error(f"지원하지 않는 파일 형식입니다: {ext}")
            check()
            return result
        except InterruptedError as e:
            return LoadResult(cancelled=True, error_message=str(e))
        except TimeoutError as e:
            return LoadResult.error(str(e))

    @classmethod
    def _load_video(cls, path: Path, target_fps: int, max_frames: int,
                    progress_callback: Optional[Callable[[int, int], None]],
                    cancel_event=None, timeout: float = 3600.0) -> LoadResult:
        """비디오 파일 로드 (VideoDecoder 사용)"""
        try:
            from .video_decoder import VideoDecoder

            result = VideoDecoder.load(
                str(path),
                target_fps=target_fps,
                max_frames=max_frames,
                progress_callback=progress_callback,
                cancel_event=cancel_event,
                timeout=timeout,
            )

            if result.cancelled:
                return LoadResult(cancelled=True, error_message=result.error_message)
            elif result.success:
                return LoadResult.ok(result.frames)
            else:
                return LoadResult.error(result.error_message)

        except ImportError:
            return LoadResult.error(
                "비디오 디코딩을 위해 FFmpeg가 필요합니다.\n"
                "설치: winget install ffmpeg 또는 설정 > FFmpeg 다운로드"
            )
        except Exception as e:
            return LoadResult.error(f"비디오 로드 실패: {str(e)}")

    @classmethod
    def _load_image(cls, path: Path, progress_callback) -> LoadResult:
        """Read every timed frame before making the document available for editing."""
        try:
            if path.suffix.lower() == '.gif':
                if path.stat().st_size > 500 * 1024 * 1024:
                    return LoadResult.error("GIF 파일은 최대 500MB까지 지원합니다.")
                with path.open('rb') as stream:
                    stream.seek(-1, os.SEEK_END)
                    if stream.read(1) != b';':
                        return LoadResult.error("GIF 종료 표시가 없습니다. 파일이 손상되었을 수 있습니다.")

            collection = FrameCollection()
            with Image.open(path) as img:
                if path.suffix.lower() == '.gif' and img.format != 'GIF':
                    return LoadResult.error(f"GIF 파일이 아닙니다: {img.format}")
                has_poster = img.format == 'PNG' and img.info.get('default_image', False)
                start = int(has_poster)
                total = getattr(img, 'n_frames', 1) - start
                if not 1 <= total <= 10000:
                    return LoadResult.error(f"이미지 프레임 수 {total:,}개는 지원 범위(1~10,000개)를 벗어납니다.")
                collection.loop_count = img.info.get('loop', None if img.format == 'GIF' else 0)
                if has_poster:
                    collection.default_image = Frame(img.copy())
                for current in range(total):
                    img.seek(start + current)
                    _load_animation_frame(img)
                    delay = img.info.get('duration', 100)
                    collection.add_frame(Frame(img.copy(), delay))
                    progress_callback(current + 1, total)
            return LoadResult.ok(collection)
        except (InterruptedError, TimeoutError):
            raise
        except MemoryError:
            return LoadResult.error("메모리 부족으로 파일을 로드할 수 없습니다")
        except Exception as exc:
            return LoadResult.error(f"이미지 로드 실패: {exc}")

    @classmethod
    def load_image_sequence(cls, file_paths: List[str],
                            default_delay: int = 100) -> LoadResult:
        """이미지 시퀀스 로드 (파일 목록)"""
        try:
            collection = FrameCollection()

            for path in file_paths:
                try:
                    with Image.open(path) as img:
                        # mode 보존 — Frame 이 안전 화이트리스트로 검증
                        img.load()
                        frame = Frame(img.copy(), default_delay)
                        collection.add_frame(frame)
                except (OSError, ValueError) as exc:
                    return LoadResult.error(f"이미지 시퀀스 로드 실패: {path}: {exc}")

            if collection.is_empty:
                return LoadResult.error("이미지를 로드할 수 없습니다")

            return LoadResult.ok(collection)

        except Exception as e:
            return LoadResult.error(f"이미지 시퀀스 로드 실패: {str(e)}")

    @classmethod
    def load_from_folder(cls, folder_path: str,
                         pattern: str = "*.png",
                         default_delay: int = 100,
                         sort_by_name: bool = True) -> LoadResult:
        """폴더에서 이미지 시퀀스 로드

        Args:
            folder_path: 폴더 경로
            pattern: 파일 패턴 (예: "*.png", "frame_*.jpg")
            default_delay: 기본 프레임 딜레이 (밀리초)
            sort_by_name: 파일명으로 정렬 여부

        Returns:
            LoadResult: 로드 결과
        """
        try:
            folder = Path(folder_path)

            if not folder.exists():
                return LoadResult.error(f"폴더를 찾을 수 없습니다: {folder_path}")

            if not folder.is_dir():
                return LoadResult.error(f"폴더가 아닙니다: {folder_path}")

            # 지원하는 모든 이미지 패턴 검색
            if pattern == "*":
                patterns = ["*.png", "*.jpg", "*.jpeg", "*.bmp", "*.gif", "*.webp"]
                files = []
                for p in patterns:
                    files.extend(glob.glob(os.path.join(folder_path, p)))
            else:
                files = glob.glob(os.path.join(folder_path, pattern))

            if not files:
                return LoadResult.error(f"폴더에서 이미지를 찾을 수 없습니다: {pattern}")

            # 정렬
            if sort_by_name:
                files = sorted(files, key=lambda x: Path(x).stem)

            return cls.load_image_sequence(files, default_delay)

        except Exception as e:
            return LoadResult.error(f"폴더 로드 실패: {str(e)}")

    @classmethod
    def get_gif_info(cls, file_path: str) -> Optional[GifInfo]:
        """GIF 파일 정보만 읽기"""
        try:
            path = Path(file_path)
            if not path.exists():
                return None

            info = GifInfo()

            with Image.open(path) as img:
                info.width = img.width
                info.height = img.height
                info.loop_count = img.info.get('loop', 0)

                frame_count = 0
                total_duration = 0

                try:
                    while True:
                        img.seek(frame_count)
                        total_duration += img.info.get('duration', 100)
                        frame_count += 1
                except EOFError:
                    pass

                info.frame_count = frame_count
                info.total_duration = total_duration

            return info

        except Exception:
            return None

    @classmethod
    def is_supported_file(cls, file_path: str) -> bool:
        """지원되는 파일인지 확인 (이미지 및 비디오)"""
        ext = Path(file_path).suffix.lower()
        return ext in cls.SUPPORTED_EXTENSIONS or ext in cls.VIDEO_EXTENSIONS

    @classmethod
    def is_video_file(cls, file_path: str) -> bool:
        """비디오 파일인지 확인"""
        ext = Path(file_path).suffix.lower()
        return ext in cls.VIDEO_EXTENSIONS

    @classmethod
    def get_file_filter(cls) -> str:
        """파일 대화상자용 필터 문자열"""
        return (
            "모든 지원 파일 (*.gif *.apng *.png *.jpg *.jpeg *.bmp *.webp *.tiff *.mp4 *.avi *.webm *.mov *.mkv *.wmv *.flv *.m4v);;"
            "GIF 파일 (*.gif);;"
            "이미지 파일 (*.apng *.png *.jpg *.jpeg *.bmp *.webp *.tiff);;"
            "비디오 파일 (*.mp4 *.avi *.webm *.mov *.mkv *.wmv *.flv *.m4v);;"
            "모든 파일 (*.*)"
        )
