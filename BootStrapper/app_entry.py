"""
app_entry.py - XGif Bootstrapper 메인 진입점
PyInstaller로 빌드될 때 이 파일이 실행됩니다.
"""
import sys
import os

def main():
    # 경로 설정 (PyInstaller 호환)
    if getattr(sys, 'frozen', False):
        # PyInstaller 빌드된 exe에서 실행
        app_dir = os.path.dirname(sys.executable)
    else:
        # 개발 환경
        app_dir = os.path.dirname(os.path.abspath(__file__))
    
    # 모듈 경로 추가
    if app_dir not in sys.path:
        sys.path.insert(0, app_dir)
    
    # 로깅 초기화 (wxPython import 전에!)
    import paths
    from logging_setup import setup_logging
    
    log_file = paths.get_log_file()
    logger = setup_logging(log_file)
    
    logger.info(f"실행 경로: {app_dir}")
    logger.info(f"Python 버전: {sys.version}")
    logger.info(f"Frozen: {getattr(sys, 'frozen', False)}")
    
    try:
        # wxPython 임포트 (무거운 작업이므로 여기서)
        logger.info("wxPython 로딩 중...")
        import wx
        logger.info(f"wxPython 버전: {wx.version()}")
        
        # UI 생성 및 실행
        from ui_main import create_app
        app = create_app(logger, paths)

        logger.info("메인 루프 시작")
        app.MainLoop()

        # 필수 의존성 충족 여부에 따라 종료 코드 결정
        setup_success = getattr(app, '_setup_success', False)
        exit_code = 0 if setup_success else 1
        logger.info(f"종료 코드: {exit_code} (setup_success={setup_success})")
        sys.exit(exit_code)
        
    except ImportError as e:
        logger.error(f"모듈 임포트 실패: {e}")
        # GUI 없이 에러 표시
        if os.name == 'nt':
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                0,
                f"필수 모듈을 불러올 수 없습니다:\n{e}",
                "XGif Bootstrapper 오류",
                0x10  # MB_ICONERROR
            )
        sys.exit(1)
        
    except Exception as e:
        logger.error(f"예상치 못한 오류: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
