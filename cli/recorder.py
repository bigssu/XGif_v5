"""CLI 녹화 세션 관리 -- core/ 엔진을 직접 제어"""
import os
import sys
import time
import logging

if sys.platform == 'win32':
    import msvcrt
else:
    msvcrt = None
from typing import Optional, Tuple

from cli import EXIT_SUCCESS, EXIT_USER_ERROR, EXIT_DEPENDENCY, EXIT_RUNTIME_ERROR
from cli.config import load_config
from cli.progress import TerminalProgress
from cli.signal_handler import install_signal_handlers, restore_signal_handlers

logger = logging.getLogger(__name__)


def _get_monitor_region(monitor_index: int = 0) -> Tuple[int, int, int, int]:
    """모니터 전체 영역 반환 (ctypes로 직접 조회, wx 불필요)"""
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    if monitor_index == 0:
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return (0, 0, w, h)

    # 다중 모니터: EnumDisplayMonitors
    monitors = []

    MONITORENUMPROC = ctypes.WINFUNCTYPE(
        ctypes.c_bool,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.POINTER(wintypes.RECT),
        ctypes.c_void_p,
    )

    def callback(hMonitor, hdcMonitor, lprcMonitor, dwData):
        rect = lprcMonitor.contents
        monitors.append(
            (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        )
        return True

    # ctypes 콜백을 로컬 변수에 보관하여 GC에 의한 해제 방지
    cb = MONITORENUMPROC(callback)
    user32.EnumDisplayMonitors(None, None, cb, 0)

    if monitor_index < len(monitors):
        return monitors[monitor_index]

    print(
        f"xgif: 경고: 모니터 {monitor_index}을 찾을 수 없습니다. 주 모니터를 사용합니다.",
        file=sys.stderr,
    )
    return monitors[0] if monitors else (0, 0, 1920, 1080)


def _parse_region_string(region_str: str) -> Optional[Tuple[int, int, int, int]]:
    """'X,Y,WxH' 형식 파싱"""
    try:
        parts = region_str.split(",")
        x, y = int(parts[0]), int(parts[1])
        wh = parts[2].lower().split("x")
        w, h = int(wh[0]), int(wh[1])
        if w < 50 or h < 50:
            print(
                f"xgif: 에러: 캡처 영역이 너무 작습니다 ({w}x{h}). 최소 50x50 필요.",
                file=sys.stderr,
            )
            return None
        return (x, y, w, h)
    except (ValueError, IndexError):
        print(
            f"xgif: 에러: 영역 형식이 올바르지 않습니다: '{region_str}'",
            file=sys.stderr,
        )
        print("       올바른 형식: X,Y,WxH (예: 100,100,800x600)", file=sys.stderr)
        return None


class CLIRecordingSession:
    """CLI 모드 녹화 세션"""

    def __init__(self, args):
        self.args = args
        self._recorder = None
        self._encoder = None
        self._audio_recorder = None
        self._audio_path = None
        self._recording_error: Optional[str] = None
        self._stopped = False
        self._paused = False
        self._progress = TerminalProgress(quiet=getattr(args, "quiet", False))

    def run(self) -> int:
        """녹화 실행. 반환값: 종료 코드"""
        # 1. 출력 포맷 결정
        output_path = self.args.output
        output_format = self._detect_format(output_path)

        # 2. 출력 디렉토리 존재 확인
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)

        # 3. 파일 덮어쓰기 확인
        if os.path.exists(output_path) and not self.args.overwrite:
            print(
                f"xgif: 에러: 출력 파일이 이미 존재합니다 -- '{output_path}'",
                file=sys.stderr,
            )
            print(
                "       해결: 다른 파일명을 사용하거나 --overwrite (-y) 플래그를 추가하세요.",
                file=sys.stderr,
            )
            return EXIT_USER_ERROR

        # 4. 설정 로드 및 CLI 인자 병합
        config = load_config()

        # 5. FFmpeg 확인
        if not self._check_ffmpeg(output_format):
            return EXIT_DEPENDENCY

        # 6. 엔진 초기화
        self._init_engines(config, output_format)

        # 7. 캡처 영역 결정
        region = self._resolve_region()
        if not region:
            return EXIT_USER_ERROR

        # 8. 시그널 핸들러 등록
        install_signal_handlers(self._on_stop_signal)

        # 9. 녹화 정보 표시
        x, y, w, h = region
        self._progress.print("\n  XGif CLI -- 화면 녹화\n")
        self._progress.print(f"  영역:     ({x}, {y}) {w}x{h}")
        self._progress.print(
            f"  백엔드:   {self._recorder.get_capture_backend_name()}"
        )
        self._progress.print(f"  FPS:      {self._recorder.fps}")
        self._progress.print(f"  포맷:     {output_format.upper()}")
        self._progress.print(f"  품질:     {self._encoder.quality}")
        self._progress.print(f"  출력:     {output_path}")

        # 10. 시작 딜레이
        delay = getattr(self.args, "delay", 0)
        if delay > 0:
            self._countdown(delay)

        if not getattr(self.args, "quiet", False):
            duration = getattr(self.args, "duration", None)
            if duration:
                print(f"\n  {duration}초간 녹화합니다...")
            else:
                print(
                    "\n  녹화를 시작합니다. (Enter/q=중지, Space=일시정지, Ctrl+C=취소)"
                )
            print()

        # 11. 오디오 녹음 시작 (MP4 + --mic)
        if getattr(self.args, "mic", False) and output_format == "mp4":
            try:
                from core.audio_recorder import AudioRecorder, is_audio_available
                if is_audio_available():
                    self._audio_recorder = AudioRecorder()
                    self._audio_recorder.set_record_mic(True)
                    if self._audio_recorder.start():
                        self._progress.print("  오디오: 마이크 녹음 활성화")
                    else:
                        self._progress.print("  오디오: 마이크 녹음 시작 실패 (비디오만 녹화)")
                        self._audio_recorder = None
                else:
                    self._progress.print(
                        "  오디오: sounddevice 미설치 (pip install sounddevice soundfile)"
                    )
            except Exception as e:
                logger.warning(f"Audio recorder init failed: {e}")
                self._audio_recorder = None

        # 12. 녹화 시작
        self._recorder.set_region(*region)

        try:
            self._recorder.start_recording()
            if not self._recorder.is_recording:
                err_msg = self._recording_error or "녹화를 시작하지 못했습니다."
                print(f"\nxgif: 에러: {err_msg}", file=sys.stderr)
                restore_signal_handlers()
                return EXIT_RUNTIME_ERROR

            # 13. 녹화 대기
            self._wait_for_completion()

            # 14. 오디오 녹음 중지
            if self._audio_recorder:
                self._audio_path = self._audio_recorder.stop()

            # 15. 녹화 중지 및 프레임 수집
            self._progress.clear_line()
            frames = self._recorder.stop_recording()

            if not frames:
                if self._recording_error:
                    print(f"\nxgif: 녹화 오류: {self._recording_error}", file=sys.stderr)
                print("\nxgif: 에러: 캡처된 프레임이 없습니다.", file=sys.stderr)
                restore_signal_handlers()
                return EXIT_RUNTIME_ERROR

            actual_fps = self._recorder.actual_fps or self._recorder.fps
            elapsed = len(frames) / actual_fps if actual_fps > 0 else 0
            self._progress.print(
                f"\n  녹화 완료: {len(frames)} 프레임 ({elapsed:.1f}초)"
            )

            # 16. 인코딩
            self._progress.print(f"  인코딩 중: {output_path}")
            self._encoder.set_progress_callback(self._on_encoding_progress)

            encode_start = time.time()
            fps_int = round(actual_fps)
            if output_format == "mp4":
                audio_path = getattr(self, "_audio_path", None)
                success = self._encoder.encode_mp4(
                    frames, fps_int, output_path, audio_path=audio_path
                )
            else:
                success = self._encoder.encode(frames, fps_int, output_path)
            encode_time = time.time() - encode_start

            restore_signal_handlers()

            # 오디오 임시 파일 정리
            if self._audio_recorder:
                self._audio_recorder.cleanup()

            if success and os.path.exists(output_path):
                file_size = os.path.getsize(output_path)
                size_str = self._format_size(file_size)
                self._progress.clear_line()
                self._progress.print(f"\n  저장 완료: {output_path} ({size_str})")
                self._progress.print(
                    f"  경과 시간: 녹화 {elapsed:.1f}초 + 인코딩 {encode_time:.1f}초"
                )

                # quiet 모드: 파일 경로만 stdout
                if getattr(self.args, "quiet", False):
                    print(output_path)
                return EXIT_SUCCESS
            else:
                print("\nxgif: 에러: 인코딩 실패", file=sys.stderr)
                return EXIT_RUNTIME_ERROR
        except KeyboardInterrupt:
            # Ctrl+C: 리소스 정리 후 관례적 종료 코드 130 반환
            return 130
        except SystemExit:
            return EXIT_RUNTIME_ERROR
        except Exception as e:
            logger.error(f"Recording session error: {e}")
            print(f"\nxgif: 에러: {e}", file=sys.stderr)
            return EXIT_RUNTIME_ERROR
        finally:
            # 리소스 정리 보장 (예외 발생 시에도)
            try:
                if self._recorder and self._recorder.is_recording:
                    self._recorder.stop_recording()
            except Exception:
                pass
            try:
                if self._audio_recorder:
                    self._audio_recorder.cleanup()
            except Exception:
                pass
            try:
                restore_signal_handlers()
            except Exception:
                pass

    def _detect_format(self, output_path: str) -> str:
        """출력 파일 확장자로 포맷 결정"""
        fmt = getattr(self.args, "format", None)
        if fmt:
            return fmt

        ext = os.path.splitext(output_path)[1].lower()
        if ext == ".mp4":
            return "mp4"
        return "gif"

    def _check_ffmpeg(self, output_format: str) -> bool:
        """FFmpeg 사용 가능 여부 확인"""
        from core.ffmpeg_installer import FFmpegManager

        if FFmpegManager.is_available():
            return True

        if output_format == "mp4":
            print(
                "xgif: 에러: MP4 인코딩에 FFmpeg가 필요하지만 찾을 수 없습니다.",
                file=sys.stderr,
            )
            print(
                "       해결: 'xgif doctor --install-ffmpeg' 또는 'winget install ffmpeg'",
                file=sys.stderr,
            )
            return False

        # GIF는 Pillow 폴백 가능
        print(
            "xgif: 경고: FFmpeg 미설치 -- Pillow 폴백 (품질이 다소 낮을 수 있음)",
            file=sys.stderr,
        )
        return True

    def _init_engines(self, config: dict, output_format: str):
        """녹화/인코딩 엔진 초기화"""
        from core.screen_recorder import ScreenRecorder
        from core.gif_encoder import GifEncoder

        self._recorder = ScreenRecorder()
        self._encoder = GifEncoder()
        self._recording_error = None

        # FPS 결정 (검증 포함)
        fps = getattr(self.args, "fps", None)
        if fps:
            if fps < 1 or fps > 120:
                print(f"xgif: 경고: FPS {fps}는 유효 범위(1-120)를 벗어남, 기본값 사용", file=sys.stderr)
                fps = 30 if output_format == "mp4" else 15
            self._recorder.fps = fps
        else:
            self._recorder.fps = 30 if output_format == "mp4" else 15

        # 캡처 백엔드
        backend = getattr(self.args, "backend", None) or config.get(
            "capture_backend", "gdi"
        )
        self._recorder.set_capture_backend(backend)
        self._recorder.set_error_occurred_callback(self._on_recording_error)

        # 커서
        self._recorder.include_cursor = getattr(self.args, "cursor", True)

        # 클릭 하이라이트
        self._recorder.show_click_highlight = getattr(
            self.args, "click_highlight", False
        )

        # HDR 보정
        hdr = getattr(self.args, "hdr_correction", False) or config.get(
            "hdr_correction", "false"
        ) == "true"
        self._recorder.set_hdr_correction(hdr)

        # 워터마크
        if self._recorder.watermark:
            wm = getattr(self.args, "watermark", False) or config.get(
                "watermark", "false"
            ) == "true"
            self._recorder.watermark.set_enabled(wm)

        # 키보드 표시
        if self._recorder.keyboard_display:
            kb = getattr(self.args, "keyboard_display", False) or config.get(
                "keyboard_display", "false"
            ) == "true"
            self._recorder.keyboard_display.set_enabled(kb)

        # 인코더 설정
        quality = getattr(self.args, "quality", None) or "high"
        self._encoder.set_quality(quality)

        encoder = getattr(self.args, "encoder", None) or config.get("encoder", "auto")
        self._encoder.set_preferred_encoder(encoder)

        codec = getattr(self.args, "codec", None) or config.get("codec", "h264")
        self._encoder.set_codec(codec)

    def _resolve_region(self) -> Optional[Tuple[int, int, int, int]]:
        """캡처 영역 결정"""
        region_str = getattr(self.args, "region", None)
        monitor = getattr(self.args, "monitor", 0)

        if region_str:
            return _parse_region_string(region_str)
        else:
            # 기본값: 주 모니터 전체
            return _get_monitor_region(monitor)

    def _countdown(self, seconds: float):
        """녹화 시작 전 카운트다운"""
        for i in range(int(seconds), 0, -1):
            self._progress.print(f"  녹화 시작까지 {i}...")
            time.sleep(1)

    def _wait_for_completion(self):
        """녹화 완료 대기 (duration 또는 키 입력 또는 Ctrl+C)"""
        start_time = time.time()
        duration = getattr(self.args, "duration", None)

        while not self._stopped:
            if self._recorder and not self._recorder.is_recording:
                self._stopped = True
                break

            elapsed = time.time() - start_time
            frame_count = self._recorder.get_frame_count()

            # duration 초과 확인
            if duration and elapsed >= duration:
                break

            # 진행률 표시
            if self._paused:
                self._progress.update_paused(elapsed, frame_count)
            else:
                self._progress.update_recording(elapsed, frame_count, duration)

            # 키 입력 확인 (non-blocking, Windows msvcrt)
            if msvcrt and msvcrt.kbhit():
                key = msvcrt.getch()
                if key in (b"\r", b"\n", b"q", b"Q"):
                    # Enter 또는 q: 녹화 중지
                    break
                elif key == b" ":
                    # Space: 일시정지/재개
                    if self._paused:
                        self._paused = False
                        self._recorder.resume_recording()
                    else:
                        self._paused = True
                        self._recorder.pause_recording()

            time.sleep(0.05)

    def _on_stop_signal(self):
        """Ctrl+C 시그널 핸들러 콜백"""
        self._stopped = True

    def _on_recording_error(self, error_msg: str):
        """녹화 에러 콜백"""
        self._recording_error = error_msg
        self._stopped = True
        self._progress.clear_line()
        print(f"\nxgif: 녹화 오류: {error_msg}", file=sys.stderr)

    def _on_encoding_progress(self, current: int, total: int):
        """인코딩 진행률 콜백"""
        self._progress.update_encoding(current, total)

    @staticmethod
    def _format_size(size_bytes: int) -> str:
        """파일 크기를 읽기 쉬운 형식으로"""
        if size_bytes < 1024:
            return f"{size_bytes} B"
        elif size_bytes < 1024 * 1024:
            return f"{size_bytes / 1024:.1f} KB"
        else:
            return f"{size_bytes / (1024 * 1024):.1f} MB"
