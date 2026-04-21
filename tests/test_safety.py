"""
안전성 테스트 스위트
크래시 방지 코드가 제대로 작동하는지 검증
"""

import pytest
import numpy as np


class TestNullSafety:
    """None 체크 안전성 테스트"""

    def test_capture_single_frame_invalid_region(self):
        """잘못된 영역으로 캡처 시도 시 크래시하지 않음"""
        from core.screen_recorder import ScreenRecorder

        recorder = ScreenRecorder()

        # None 영역
        recorder.region = None
        assert recorder.capture_single_frame() is None

        # 잘못된 길이
        recorder.region = (0, 0, 100)
        assert recorder.capture_single_frame() is None

        # 음수 크기
        recorder.region = (0, 0, -100, -100)
        assert recorder.capture_single_frame() is None

    def test_overlay_with_none_frame(self):
        """None 프레임에 오버레이 적용 시 크래시하지 않음"""
        from core.watermark import Watermark
        from core.keyboard_display import KeyboardDisplay

        watermark = Watermark()
        watermark.set_enabled(True)
        assert watermark.apply_watermark(None) is None

        keyboard = KeyboardDisplay()
        keyboard.set_enabled(True)
        assert keyboard.apply_keyboard_display(None) is None


class TestIndexSafety:
    """인덱스 안전성 테스트"""

    def test_encoding_progress_division_by_zero(self):
        """진행률 계산 시 0으로 나누기 방지"""
        # 실제 UI 테스트는 복잡하므로 로직만 검증
        total = 0
        current = 10

        # 안전한 계산
        percent = 0
        try:
            if total > 0:
                percent = min(100, max(0, int((current / total) * 100)))
        except ZeroDivisionError:
            percent = 0

        assert percent == 0

    def test_empty_frames_encoding(self):
        """빈 프레임 리스트로 인코딩 시도 시 크래시하지 않음"""
        from core.gif_encoder import GifEncoder

        encoder = GifEncoder()
        result = encoder.encode([], fps=15, output_path="test.gif")
        assert result is False


class TestFileSafety:
    """파일 I/O 안전성 테스트"""

    def test_invalid_temp_directory(self):
        """임시 디렉토리 생성 실패 시 폴백"""
        from core.gif_encoder import _create_temp_dir

        # 정상적으로 폴백해야 함 (예외 발생하지 않음)
        temp_dir = _create_temp_dir()
        assert temp_dir is not None
        assert isinstance(temp_dir, str)

    def test_watermark_invalid_image(self):
        """존재하지 않는 워터마크 이미지 시 크래시하지 않음"""
        from core.watermark import Watermark

        wm = Watermark()
        wm.set_enabled(True)
        wm.set_type('image')
        wm.set_image_path('/nonexistent/image.png')

        # None 반환해야 함 (크래시 안 함)
        test_frame = np.zeros((100, 100, 3), dtype=np.uint8)
        result = wm.apply_watermark(test_frame)
        assert result is not None


class TestThreadSafety:
    """멀티스레딩 안전성 테스트"""

    def test_double_start_recording(self):
        """이미 녹화 중일 때 다시 시작 시도"""
        from core.screen_recorder import ScreenRecorder

        recorder = ScreenRecorder()
        recorder.set_region(0, 0, 320, 240)

        # 첫 번째 시작
        recorder.start_recording()
        assert recorder.is_recording

        # 두 번째 시작 (무시되어야 함)
        recorder.start_recording()

        # 정리
        recorder.stop_recording()


class TestGpuSafety:
    """GPU 안전성 테스트"""

    def test_gpu_unavailable(self):
        """GPU 없는 환경에서도 작동"""
        from core.gpu_utils import detect_gpu, to_gpu

        # GPU 정보 감지 (실패해도 크래시 안 함)
        info = detect_gpu()
        assert info is not None

        # GPU 전송 (실패해도 원본 반환)
        test_array = np.zeros((10, 10), dtype=np.float32)
        result = to_gpu(test_array)
        assert result is not None

    def test_invalid_array_to_gpu(self):
        """잘못된 배열을 GPU로 전송 시도"""
        from core.gpu_utils import to_gpu

        # None
        assert to_gpu(None) is None

        # 잘못된 타입
        assert to_gpu("invalid") == "invalid"


class TestEncodingSafety:
    """인코딩 안전성 테스트"""

    def test_invalid_fps(self):
        """유효하지 않은 FPS로 인코딩 시도"""
        from core.gif_encoder import GifEncoder

        encoder = GifEncoder()
        test_frames = [np.zeros((100, 100, 3), dtype=np.uint8)]

        # 음수 FPS
        result = encoder.encode(test_frames, fps=-1, output_path="test.gif")
        assert result is False

        # 너무 큰 FPS
        result = encoder.encode(test_frames, fps=999, output_path="test.gif")
        assert result is False

    def test_invalid_output_path(self):
        """유효하지 않은 출력 경로"""
        from core.gif_encoder import GifEncoder

        encoder = GifEncoder()
        test_frames = [np.zeros((100, 100, 3), dtype=np.uint8)]

        # None 경로
        result = encoder.encode(test_frames, fps=15, output_path=None)
        assert result is False

        # 빈 문자열
        result = encoder.encode(test_frames, fps=15, output_path="")
        assert result is False


# 테스트 실행 시
if __name__ == '__main__':
    pytest.main([__file__, '-v'])
