"""파일 변환 (xgif convert)"""
import os
import re
import sys
import logging

from cli import EXIT_SUCCESS, EXIT_USER_ERROR, EXIT_DEPENDENCY, EXIT_RUNTIME_ERROR

logger = logging.getLogger(__name__)


def run_convert(args) -> int:
    """파일 변환 실행. 반환값: 종료 코드."""
    input_path = args.input

    if not os.path.exists(input_path):
        print(f"xgif: 에러: 입력 파일을 찾을 수 없습니다 -- '{input_path}'", file=sys.stderr)
        return EXIT_USER_ERROR

    # 출력 경로 결정
    output_path = args.conv_output
    if not output_path:
        base, ext = os.path.splitext(input_path)
        if ext.lower() == ".gif":
            output_path = base + ".mp4"
        else:
            output_path = base + ".gif"

    # 출력 형식 결정
    output_format = args.format
    if not output_format:
        ext = os.path.splitext(output_path)[1].lower()
        output_format = "mp4" if ext == ".mp4" else "gif"

    # 덮어쓰기 확인
    if os.path.exists(output_path) and not args.overwrite:
        print(f"xgif: 에러: 출력 파일이 이미 존재합니다 -- '{output_path}'", file=sys.stderr)
        print("       --overwrite (-y) 플래그를 추가하세요.", file=sys.stderr)
        return EXIT_USER_ERROR

    # FFmpeg 확인
    from core.ffmpeg_installer import FFmpegManager
    ffmpeg_exe = FFmpegManager.get_ffmpeg_executable()
    if not ffmpeg_exe:
        print("xgif: 에러: 변환에 FFmpeg가 필요하지만 찾을 수 없습니다.", file=sys.stderr)
        print("       해결: 'xgif doctor --install-ffmpeg' 실행", file=sys.stderr)
        return EXIT_DEPENDENCY

    # 입력 파일 크기 체크
    if os.path.getsize(input_path) == 0:
        print(f"xgif: 에러: 입력 파일이 비어 있습니다 -- '{input_path}'", file=sys.stderr)
        return EXIT_USER_ERROR

    # 리사이즈 입력 검증 (필터 인젝션 방지)
    if args.resize and not re.match(r'^\d+x\d+$', args.resize):
        print(f"xgif: 에러: 잘못된 리사이즈 형식입니다 -- '{args.resize}'", file=sys.stderr)
        print("       올바른 형식: WxH (예: 640x480)", file=sys.stderr)
        return EXIT_USER_ERROR

    # FPS 범위 검증
    if args.fps is not None:
        if not (1 <= args.fps <= 120):
            print(f"xgif: 에러: FPS는 1~120 범위여야 합니다 -- '{args.fps}'", file=sys.stderr)
            return EXIT_USER_ERROR

    # 변환 실행
    import subprocess

    cmd = [ffmpeg_exe, "-y", "-i", input_path]

    # 리사이즈 필터 (나중에 다른 필터와 결합)
    resize_filter = None
    if args.resize:
        resize_filter = f"scale={args.resize.replace('x', ':')}"

    # FPS
    if args.fps:
        cmd.extend(["-r", str(args.fps)])

    if output_format == "mp4":
        # MP4 인코딩 설정
        from core.gif_encoder import GifEncoder
        enc = GifEncoder()
        if args.encoder:
            enc.set_preferred_encoder(args.encoder)
        if args.codec:
            enc.set_codec(args.codec)
        encoder = enc._get_best_encoder(args.codec or "h264")

        crf = {"high": "18", "medium": "23", "low": "28"}.get(args.quality, "23")
        cmd.extend(["-c:v", encoder])

        if encoder in ("h264_nvenc", "hevc_nvenc"):
            cmd.extend(["-preset", "p4", "-cq", crf])
        elif encoder in ("h264_qsv", "hevc_qsv"):
            cmd.extend(["-preset", "medium", "-global_quality", crf])
        elif encoder in ("h264_amf", "hevc_amf"):
            cmd.extend(["-quality", "balanced", "-rc", "cqp", "-qp_i", crf, "-qp_p", crf])
        else:
            cmd.extend(["-preset", "medium", "-crf", crf])

        cmd.extend(["-pix_fmt", "yuv420p"])

        # MP4에서 리사이즈가 있으면 -vf 추가
        if resize_filter:
            cmd.extend(["-vf", resize_filter])
    else:
        # GIF 인코딩 (2-pass) — 리사이즈와 결합
        quality_map = {"high": 256, "medium": 256, "low": 128}
        max_colors = quality_map.get(args.quality, 256)
        palette_filter = f"split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse"
        if resize_filter:
            # 리사이즈 필터를 팔레트 필터 앞에 결합
            combined = f"{resize_filter},split[s0][s1];[s0]palettegen=max_colors={max_colors}[p];[s1][p]paletteuse"
            cmd.extend(["-vf", combined])
        else:
            cmd.extend(["-vf", palette_filter])
        cmd.extend(["-loop", "0"])

    cmd.append(output_path)

    print(f"  변환: {input_path} -> {output_path} ({output_format.upper()})")

    ffmpeg_env = FFmpegManager.get_ffmpeg_env()
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        env=ffmpeg_env,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )

    if result.returncode == 0 and os.path.exists(output_path):
        file_size = os.path.getsize(output_path)
        if file_size < 1024:
            size_str = f"{file_size} B"
        elif file_size < 1024 * 1024:
            size_str = f"{file_size / 1024:.1f} KB"
        else:
            size_str = f"{file_size / (1024 * 1024):.1f} MB"
        print(f"  완료: {output_path} ({size_str})")
        return EXIT_SUCCESS
    else:
        error_msg = result.stderr[:500] if result.stderr else "알 수 없는 오류"
        print(f"xgif: 에러: 변환 실패", file=sys.stderr)
        logger.error(f"FFmpeg error: {error_msg}")
        return EXIT_RUNTIME_ERROR
