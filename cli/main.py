"""XGif CLI 모드 진입점 + argparse 정의"""
import argparse
import sys
import os
import logging

from core.version import APP_VERSION as __version__


def build_parser() -> argparse.ArgumentParser:
    """CLI 인자 파서 생성"""
    parser = argparse.ArgumentParser(
        prog="xgif",
        description="XGif -- 화면 녹화 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
사용 예시:
  xgif record -o screen.gif                           전체 화면 GIF 녹화
  xgif record -r 0,0,800x600 -o area.gif              특정 영역 녹화
  xgif record -r 100,100,1920x1080 -f 30 -o demo.mp4  1080p 30fps MP4
  xgif record -d 10 --delay 3 -q low -o short.gif     3초 후 10초 녹화
  xgif record --no-cursor -o clean.gif                 커서 없이 녹화
  xgif doctor                                          환경 진단
  xgif config list                                     설정 확인
""",
    )
    parser.add_argument(
        "--version", "-V", action="version", version=f"XGif {__version__}"
    )
    parser.add_argument("--debug", action="store_true", help="디버그 로깅 활성화")
    parser.add_argument("--quiet", action="store_true", help="최소 출력 (에러만)")

    subparsers = parser.add_subparsers(dest="command")

    # ── record ──
    rec = subparsers.add_parser(
        "record",
        help="화면 녹화",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
녹화 중 키보드 제어:
  Enter, q     녹화 중지 및 저장
  Space        일시정지 / 재개
  Ctrl+C       녹화 취소 (저장하지 않음)

영역 지정 형식:
  --region X,Y,WxH   (예: --region 100,200,800x600)
""",
    )
    rec.add_argument(
        "output",
        nargs="?",
        default=None,
        help="출력 파일 경로 (.gif 또는 .mp4). -o로도 지정 가능",
    )
    rec.add_argument(
        "--output",
        "-o",
        dest="output_opt",
        default=None,
        help="출력 파일 경로 (.gif 또는 .mp4)",
    )
    rec.add_argument(
        "--region",
        "-r",
        type=str,
        default=None,
        help='캡처 영역 "X,Y,WxH" (예: 100,100,800x600)',
    )
    rec.add_argument(
        "--monitor", "-m", type=int, default=0, help="모니터 번호 (0=주 모니터)"
    )
    rec.add_argument("--fps", "-f", type=int, default=None, help="프레임레이트")
    rec.add_argument(
        "--duration",
        "-d",
        type=float,
        default=None,
        help="녹화 시간(초). 미지정 시 수동 중지",
    )
    rec.add_argument(
        "--format", "-F", choices=["gif", "mp4"], default=None, help="출력 형식"
    )
    rec.add_argument(
        "--quality",
        "-q",
        choices=["high", "medium", "low"],
        default="high",
        help="인코딩 품질 (기본: high)",
    )
    rec.add_argument(
        "--backend",
        "-b",
        choices=["auto", "dxcam", "gdi"],
        default=None,
        help="캡처 백엔드",
    )
    rec.add_argument(
        "--encoder",
        "-e",
        choices=["auto", "nvenc", "qsv", "amf", "cpu"],
        default=None,
        help="비디오 인코더",
    )
    rec.add_argument(
        "--codec", choices=["h264", "h265"], default=None, help="비디오 코덱 (MP4 전용)"
    )
    rec.add_argument(
        "--cursor",
        action="store_true",
        default=True,
        help="마우스 커서 포함 (기본값)",
    )
    rec.add_argument(
        "--no-cursor", dest="cursor", action="store_false", help="마우스 커서 제외"
    )
    rec.add_argument(
        "--click-highlight",
        action="store_true",
        default=False,
        help="마우스 클릭 하이라이트",
    )
    rec.add_argument(
        "--watermark", action="store_true", default=False, help="워터마크 추가"
    )
    rec.add_argument(
        "--keyboard-display",
        action="store_true",
        default=False,
        help="키보드 입력 표시",
    )
    rec.add_argument(
        "--hdr-correction",
        action="store_true",
        default=False,
        help="HDR 모니터 보정",
    )
    rec.add_argument(
        "--mic",
        action="store_true",
        default=False,
        help="마이크 오디오 녹음 (MP4 전용)",
    )
    rec.add_argument(
        "--delay", type=float, default=0, help="녹화 시작 전 카운트다운(초)"
    )
    rec.add_argument(
        "--overwrite", "-y", action="store_true", default=False, help="기존 파일 덮어쓰기"
    )

    # ── config ──
    cfg = subparsers.add_parser("config", help="설정 관리")
    cfg.add_argument(
        "config_action",
        nargs="?",
        default="list",
        choices=["list", "get", "set", "reset", "path"],
        help="설정 동작 (기본: list)",
    )
    cfg.add_argument("key", nargs="?", default=None, help="설정 키")
    cfg.add_argument("value", nargs="?", default=None, help="설정 값 (set 시)")

    # ── doctor ──
    doc = subparsers.add_parser("doctor", help="환경 진단")
    doc.add_argument(
        "--install-ffmpeg",
        action="store_true",
        default=False,
        help="FFmpeg 자동 설치",
    )
    doc.add_argument(
        "--install-dxcam",
        action="store_true",
        default=False,
        help="dxcam 패키지 설치",
    )
    doc.add_argument(
        "--install-cupy",
        action="store_true",
        default=False,
        help="CuPy 자동 설치 (GPU 가속, CUDA 버전 자동 감지)",
    )
    doc.add_argument(
        "--verbose", "-v", action="store_true", default=False, help="상세 정보"
    )

    # ── convert ──
    conv = subparsers.add_parser("convert", help="파일 변환 (GIF <-> MP4)")
    conv.add_argument("input", help="입력 파일 경로")
    conv.add_argument("conv_output", nargs="?", default=None, help="출력 파일 경로")
    conv.add_argument(
        "--format", "-F", choices=["gif", "mp4"], default=None, help="출력 형식"
    )
    conv.add_argument("--fps", "-f", type=int, default=None, help="출력 FPS")
    conv.add_argument(
        "--quality",
        "-q",
        choices=["high", "medium", "low"],
        default="high",
        help="품질",
    )
    conv.add_argument(
        "--resize", "-s", type=str, default=None, help="출력 해상도 (WxH)"
    )
    conv.add_argument(
        "--encoder",
        "-e",
        choices=["auto", "nvenc", "qsv", "amf", "cpu"],
        default=None,
        help="인코더",
    )
    conv.add_argument(
        "--codec", choices=["h264", "h265"], default=None, help="코덱 (MP4)"
    )
    conv.add_argument(
        "--overwrite", "-y", action="store_true", default=False, help="덮어쓰기"
    )

    return parser


def setup_cli_logging(debug=False, quiet=False):
    """CLI 모드 로깅 설정"""
    from logging.handlers import RotatingFileHandler

    appdata = os.environ.get("APPDATA", os.path.expanduser("~"))
    log_dir = os.path.join(appdata, "XGif", "logs")
    os.makedirs(log_dir, exist_ok=True)

    handlers = []

    # 파일 핸들러
    try:
        file_handler = RotatingFileHandler(
            os.path.join(log_dir, "cli.log"),
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(logging.DEBUG)
        handlers.append(file_handler)
    except (OSError, PermissionError):
        pass

    # 콘솔 핸들러
    console_handler = logging.StreamHandler()
    if quiet:
        console_handler.setLevel(logging.ERROR)
    elif debug:
        console_handler.setLevel(logging.DEBUG)
    else:
        console_handler.setLevel(logging.WARNING)
    handlers.append(console_handler)

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=handlers,
    )


def _resolve_output(args) -> str:
    """record 서브커맨드의 출력 경로 결정"""
    # -o 옵션 우선, 없으면 위치 인자
    output = getattr(args, "output_opt", None) or getattr(args, "output", None)
    # --format 인자에 따라 기본 확장자 결정
    fmt = getattr(args, "format", None) or "gif"
    default_ext = f".{fmt}"
    if not output:
        # 기본 파일명 생성
        from datetime import datetime

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"recording_{timestamp}{default_ext}"
    # 확장자 없으면 포맷에 맞는 확장자 추가
    _, ext = os.path.splitext(output)
    if not ext:
        output += default_ext
    return output


def cli_main(argv=None) -> int:
    """CLI 모드 메인 함수. 반환값: 종료 코드.

    종료 코드:
        0 - 성공
        1 - 일반 에러 (잘못된 인자, 파일 접근 실패 등)
        2 - 의존성 누락 (FFmpeg, dxcam 등)
        3 - 녹화/인코딩 실패
        130 - 사용자 중단 (Ctrl+C)
    """
    # comtypes 경고 억제 (dxcam 내부 문제)
    import warnings
    warnings.filterwarnings("ignore", message=".*comtypes.*")

    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 0

    # 로깅 설정
    setup_cli_logging(
        debug=getattr(args, "debug", False), quiet=getattr(args, "quiet", False)
    )

    if args.command == "record":
        args.output = _resolve_output(args)
        from cli.recorder import CLIRecordingSession

        session = CLIRecordingSession(args)
        return session.run()

    elif args.command == "config":
        from cli.config import handle_config_command

        return handle_config_command(args)

    elif args.command == "doctor":
        from cli.doctor import run_doctor

        return run_doctor(args)

    elif args.command == "convert":
        from cli.converter import run_convert

        return run_convert(args)

    else:
        parser.print_help()
        return 0
