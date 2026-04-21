"""
GifDecoder - GIF/이미지/비디오 파일 디코딩
"""
from __future__ import annotations
from typing import Optional, List, Callable
from pathlib import Path
from dataclasses import dataclass
from PIL import Image
import glob
import os

from .frame import Frame
from .frame_collection import FrameCollection


@dataclass
class LoadResult:
    """로드 결과"""
    frames: Optional[FrameCollection] = None
    success: bool = False
    error_message: str = ""

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

    SUPPORTED_EXTENSIONS = {'.gif', '.png', '.jpg', '.jpeg', '.bmp', '.webp', '.tiff'}
    VIDEO_EXTENSIONS = {'.mp4', '.avi', '.webm', '.mov', '.mkv', '.wmv', '.flv', '.m4v'}

    @classmethod
    def load(cls, file_path: str,
             video_fps: int = 10,
             video_max_frames: int = 500,
             progress_callback: Optional[Callable[[int, int], None]] = None
             ) -> LoadResult:
        """GIF, 이미지 또는 비디오 파일 로드
        
        Args:
            file_path: 파일 경로
            video_fps: 비디오 파일의 경우 추출할 FPS (기본 10)
            video_max_frames: 비디오 파일의 경우 최대 프레임 수 (기본 500)
            progress_callback: 진행률 콜백 (current, total)
        
        Returns:
            LoadResult: 로드 결과
        """
        path = Path(file_path)

        if not path.exists():
            return LoadResult.error(f"파일을 찾을 수 없습니다: {file_path}")

        ext = path.suffix.lower()

        if ext == '.gif':
            return cls._load_gif(path)
        elif ext in cls.VIDEO_EXTENSIONS:
            return cls._load_video(path, video_fps, video_max_frames, progress_callback)
        elif ext in cls.SUPPORTED_EXTENSIONS:
            return cls._load_image(path)
        else:
            return LoadResult.error(f"지원하지 않는 파일 형식입니다: {ext}")

    @classmethod
    def _load_video(cls, path: Path, target_fps: int, max_frames: int,
                    progress_callback: Optional[Callable[[int, int], None]]) -> LoadResult:
        """비디오 파일 로드 (VideoDecoder 사용)"""
        try:
            from .video_decoder import VideoDecoder

            result = VideoDecoder.load(
                str(path),
                target_fps=target_fps,
                max_frames=max_frames,
                progress_callback=progress_callback
            )

            if result.success:
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
    def _load_gif(cls, path: Path) -> LoadResult:
        """GIF 파일 로드"""
        try:
            # 파일 존재 확인
            if not path.exists():
                return LoadResult.error(f"파일을 찾을 수 없습니다: {path}")

            # 파일 크기 확인 (너무 큰 파일 방지)
            file_size_mb = path.stat().st_size / (1024 * 1024)
            if file_size_mb > 500:  # 500MB 이상이면 경고
                return LoadResult.error(f"파일이 너무 큽니다 ({file_size_mb:.1f}MB). 최대 500MB까지 지원합니다.")

            collection = FrameCollection()

            # PIL로 메타데이터 읽기
            try:
                with Image.open(path) as img:
                    # 이미지 형식 확인
                    if img.format != 'GIF':
                        return LoadResult.error(f"GIF 파일이 아닙니다: {img.format}")

                    # 루프 카운트
                    loop_count = img.info.get('loop', 0)
                    collection.loop_count = loop_count

                    # 각 프레임 처리
                    frame_index = 0
                    max_frames = 10000  # 최대 프레임 수 제한 (메모리 보호)

                    try:
                        while frame_index < max_frames:
                            try:
                                img.seek(frame_index)
                            except EOFError:
                                break  # 모든 프레임 처리 완료

                            # 딜레이 가져오기 (밀리초)
                            delay = img.info.get('duration', 100)
                            if delay <= 0:
                                delay = 100

                            # RGBA로 변환
                            try:
                                frame_img = img.convert('RGBA')
                                frame = Frame(frame_img, delay)
                                collection.add_frame(frame)
                            except Exception:
                                # 개별 프레임 변환 실패 시 건너뛰기
                                frame_index += 1
                                continue

                            frame_index += 1
                    except EOFError:
                        pass  # 모든 프레임 처리 완료
                    except Exception as e:
                        # 프레임 읽기 중 오류 발생
                        if collection.is_empty:
                            return LoadResult.error(f"프레임 읽기 실패: {str(e)}")
            except Exception as e:
                return LoadResult.error(f"GIF 파일 열기 실패: {str(e)}")

            if collection.is_empty:
                return LoadResult.error("GIF 파일에서 프레임을 추출할 수 없습니다")

            return LoadResult.ok(collection)

        except MemoryError:
            return LoadResult.error("메모리 부족으로 파일을 로드할 수 없습니다")
        except Exception as e:
            return LoadResult.error(f"GIF 로드 실패: {str(e)}")

    @classmethod
    def _load_image(cls, path: Path) -> LoadResult:
        """단일 이미지 파일 로드"""
        try:
            collection = FrameCollection()

            with Image.open(path) as img:
                frame = Frame(img.convert('RGBA'), 100)
                collection.add_frame(frame)

            return LoadResult.ok(collection)

        except Exception as e:
            return LoadResult.error(f"이미지 로드 실패: {str(e)}")

    @classmethod
    def load_image_sequence(cls, file_paths: List[str],
                            default_delay: int = 100) -> LoadResult:
        """이미지 시퀀스 로드 (파일 목록)"""
        try:
            collection = FrameCollection()

            for path in file_paths:
                try:
                    with Image.open(path) as img:
                        frame = Frame(img.convert('RGBA'), default_delay)
                        collection.add_frame(frame)
                except Exception:
                    pass

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
            "모든 지원 파일 (*.gif *.png *.jpg *.mp4 *.avi *.webm *.mov);;"
            "GIF 파일 (*.gif);;"
            "이미지 파일 (*.png *.jpg *.jpeg *.bmp *.webp);;"
            "비디오 파일 (*.mp4 *.avi *.webm *.mov *.mkv);;"
            "모든 파일 (*.*)"
        )
