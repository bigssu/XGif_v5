"""
E2E 인코딩 파이프라인 테스트
프레임 생성 → GIF/MP4 인코딩 → 출력 파일 검증
"""

import os
import tempfile
import shutil

import pytest
import numpy as np

from core.gif_encoder import GifEncoder


# ── 헬퍼 ──────────────────────────────────────────────

def _make_gradient_frames(count=5, width=160, height=120):
    """테스트용 그라데이션 프레임 생성 (RGBA)"""
    frames = []
    for i in range(count):
        t = i / max(count - 1, 1)
        r = np.full((height, width), int(255 * t), dtype=np.uint8)
        g = np.full((height, width), int(255 * (1 - t)), dtype=np.uint8)
        b = np.full((height, width), 128, dtype=np.uint8)
        a = np.full((height, width), 255, dtype=np.uint8)
        frame = np.stack([r, g, b, a], axis=-1)
        frames.append(frame)
    return frames


@pytest.fixture
def encoder():
    return GifEncoder()


@pytest.fixture
def tmp_dir():
    d = tempfile.mkdtemp(prefix="xgif_test_")
    yield d
    shutil.rmtree(d, ignore_errors=True)


# ── GIF 인코딩 ────────────────────────────────────────

class TestGifEncoding:
    """GIF 인코딩 파이프라인 테스트"""

    def test_encode_gif_produces_file(self, encoder, tmp_dir):
        """프레임 → GIF 파일 생성 확인"""
        frames = _make_gradient_frames(count=3)
        out = os.path.join(tmp_dir, "out.gif")

        result = encoder.encode(frames, fps=10, output_path=out)
        assert result is True
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_encode_gif_valid_format(self, encoder, tmp_dir):
        """생성된 GIF 파일이 올바른 GIF 매직 바이트를 가지는지 확인"""
        frames = _make_gradient_frames(count=3)
        out = os.path.join(tmp_dir, "out.gif")
        encoder.encode(frames, fps=10, output_path=out)

        with open(out, "rb") as f:
            magic = f.read(6)
        assert magic in (b"GIF87a", b"GIF89a")

    def test_encode_empty_frames_fails(self, encoder, tmp_dir):
        """빈 프레임 리스트 → 실패"""
        out = os.path.join(tmp_dir, "out.gif")
        result = encoder.encode([], fps=10, output_path=out)
        assert result is False

    def test_encode_invalid_fps_fails(self, encoder, tmp_dir):
        """잘못된 FPS → 실패"""
        frames = _make_gradient_frames(count=2)
        out = os.path.join(tmp_dir, "out.gif")
        assert encoder.encode(frames, fps=0, output_path=out) is False
        assert encoder.encode(frames, fps=-1, output_path=out) is False
        assert encoder.encode(frames, fps=999, output_path=out) is False

    def test_encode_single_frame(self, encoder, tmp_dir):
        """단일 프레임 GIF 인코딩"""
        frames = _make_gradient_frames(count=1)
        out = os.path.join(tmp_dir, "single.gif")
        result = encoder.encode(frames, fps=10, output_path=out)
        assert result is True
        assert os.path.getsize(out) > 0

    def test_encode_large_frame_count(self, encoder, tmp_dir):
        """30프레임 인코딩 (실제 녹화에 가까운 분량)"""
        frames = _make_gradient_frames(count=30, width=320, height=240)
        out = os.path.join(tmp_dir, "long.gif")
        result = encoder.encode(frames, fps=15, output_path=out)
        assert result is True
        assert os.path.getsize(out) > 1000  # 최소 1KB 이상

    def test_progress_callback_called(self, encoder, tmp_dir):
        """프로그레스 콜백 호출 확인"""
        progress_calls = []
        encoder.set_progress_callback(lambda cur, tot: progress_calls.append((cur, tot)))

        frames = _make_gradient_frames(count=5)
        out = os.path.join(tmp_dir, "progress.gif")
        encoder.encode(frames, fps=10, output_path=out)

        assert len(progress_calls) > 0
        # 마지막 호출에서 current == total
        last = progress_calls[-1]
        assert last[0] == last[1]


# ── MP4 인코딩 ────────────────────────────────────────

class TestMp4Encoding:
    """MP4 인코딩 파이프라인 테스트 (FFmpeg 필요)"""

    @pytest.fixture(autouse=True)
    def _skip_no_ffmpeg(self, encoder):
        if not encoder.is_ffmpeg_available():
            pytest.skip("FFmpeg not installed")

    def test_encode_mp4_produces_file(self, encoder, tmp_dir):
        """프레임 → MP4 파일 생성 확인"""
        frames = _make_gradient_frames(count=5)
        out = os.path.join(tmp_dir, "out.mp4")

        result = encoder.encode_mp4(frames, fps=10, output_path=out)
        assert result is True
        assert os.path.exists(out)
        assert os.path.getsize(out) > 0

    def test_encode_mp4_valid_format(self, encoder, tmp_dir):
        """MP4 파일이 ftyp 매직 바이트를 포함하는지 확인"""
        frames = _make_gradient_frames(count=3)
        out = os.path.join(tmp_dir, "out.mp4")
        encoder.encode_mp4(frames, fps=10, output_path=out)

        with open(out, "rb") as f:
            header = f.read(12)
        # MP4 ftyp box: offset 4에 'ftyp' 문자열
        assert b"ftyp" in header

    def test_encode_mp4_empty_frames_fails(self, encoder, tmp_dir):
        """빈 프레임 → 실패"""
        out = os.path.join(tmp_dir, "out.mp4")
        result = encoder.encode_mp4([], fps=10, output_path=out)
        assert result is False

    def test_encode_mp4_invalid_fps_fails(self, encoder, tmp_dir):
        """잘못된 FPS → 실패"""
        frames = _make_gradient_frames(count=2)
        out = os.path.join(tmp_dir, "out.mp4")
        assert encoder.encode_mp4(frames, fps=0, output_path=out) is False


# ── 인코더 상태 ───────────────────────────────────────

class TestEncoderState:
    """인코더 설정 및 상태 테스트"""

    def test_quality_setting(self, encoder):
        encoder.set_quality("high")
        # 크래시 없이 설정됨

    def test_codec_setting(self, encoder):
        encoder.set_codec("h264")
        assert encoder.get_codec() == "h264"

    def test_gpu_mode_toggle(self, encoder):
        encoder.set_gpu_mode(False)
        assert encoder.is_gpu_mode() is False
        encoder.set_gpu_mode(True)
        # GPU가 없어도 크래시하지 않음

    def test_detect_encoders(self, encoder):
        """인코더 감지가 크래시하지 않음"""
        result = encoder.detect_available_encoders()
        assert isinstance(result, dict)
