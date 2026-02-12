"""
XGif - Python GIF/MP4 화면 녹화 프로그램
GUI 모드(wxPython)와 CLI 모드를 모두 지원
"""

import sys
import os
import time
import logging

# Windows DPI Awareness 설정 (wx import 전에 호출해야 함)
# SYSTEM_AWARE(1)로 설정: 캡처 좌표 정확도 확보 + wxPython 콤보박스 호환성 유지
# PER_MONITOR_AWARE(2)는 wxPython ComboBox 드롭다운에서 크래시 발생
if sys.platform == 'win32':
    try:
        import ctypes
        # PROCESS_SYSTEM_DPI_AWARE = 1
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except (AttributeError, OSError):
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass

# Windows 등에서 한글 print/로깅 시 UnicodeEncodeError 방지: stdout/stderr를 UTF-8로 재설정
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except (AttributeError, OSError):
    pass


# ── CLI 모드 조기 감지 (wx import 전에) ──
def _is_cli_mode() -> bool:
    """sys.argv에서 CLI 모드 여부 판단"""
    if len(sys.argv) < 2:
        return False
    cli_commands = {'record', 'convert', 'config', 'doctor'}
    return sys.argv[1] in cli_commands

if _is_cli_mode():
    # CLI 모드: wx를 import하지 않고 CLI 진입점으로 직행
    from cli.main import cli_main
    sys.exit(cli_main())

# ── 전역 예외 리포터 (console=False 빌드에서 크래시 원인 확인용) ──
def _install_startup_crash_reporter():
    """GUI 빌드에서 unhandled exception → crash.log + MessageBox 표시"""
    _orig_excepthook = sys.excepthook

    def _crash_reporter(exc_type, exc_value, exc_tb):
        import traceback
        msg = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
        # 1) crash.log 저장
        for crash_dir in [
            os.path.join(os.environ.get('APPDATA', ''), 'XGif'),
            os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None,
        ]:
            if not crash_dir:
                continue
            try:
                os.makedirs(crash_dir, exist_ok=True)
                with open(os.path.join(crash_dir, 'crash.log'), 'w', encoding='utf-8') as f:
                    f.write(msg)
                break
            except Exception:
                continue
        # 2) ctypes MessageBox (wx 없이도 동작)
        try:
            ctypes.windll.user32.MessageBoxW(
                0, msg[:2000], "XGif Startup Error", 0x10)
        except Exception:
            pass
        _orig_excepthook(exc_type, exc_value, exc_tb)

    sys.excepthook = _crash_reporter

_install_startup_crash_reporter()

# ── GUI 모드 ──
import wx

# 공통 상수
from core.utils import APP_SETTINGS_ORG, APP_SETTINGS_NAME

# 크래시 핸들러
from core.crash_handler import install_crash_handler

# 단일 인스턴스 체크용 이름
APP_UNIQUE_NAME = f"{APP_SETTINGS_NAME}_SingleInstance_Lock"

# wxPython 4.2에서는 SingleInstanceChecker를 직접 사용
try:
    from wx import SingleInstanceChecker
except ImportError:
    # 폴백: SingleInstanceChecker가 없으면 더미 클래스 사용
    class SingleInstanceChecker:
        def __init__(self, name):
            self.name = name
        def IsAnotherRunning(self):
            return False

# 로깅 설정 (안전 + 로테이션)
def setup_logging():
    """로깅 설정 (안전한 파일 핸들러 + 로그 로테이션)"""
    from logging.handlers import RotatingFileHandler
    
    handlers = [logging.StreamHandler()]
    
    try:
        appdata = os.environ.get('APPDATA', os.path.expanduser('~'))
        log_dir = os.path.join(appdata, APP_SETTINGS_NAME, 'logs')
        os.makedirs(log_dir, exist_ok=True)
        
        log_file = os.path.join(log_dir, 'app.log')
        # 로그 로테이션: 최대 5MB, 3개 파일 유지
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=5 * 1024 * 1024,  # 5MB
            backupCount=3,
            encoding='utf-8'
        )
        handlers.append(file_handler)
    except (OSError, PermissionError) as e:
        print(f"Warning: Cannot create log file: {e}")
    
    level = logging.DEBUG if os.environ.get('XGIF_DEBUG') else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )

setup_logging()
logger = logging.getLogger(__name__)


class XGifApp(wx.App):
    """XGif 애플리케이션 클래스"""
    
    def OnInit(self):
        """애플리케이션 초기화"""
        # 크래시 핸들러 설치 (전역 예외 포착) — self에 저장하여 GC 방지
        try:
            self._crash_handler = install_crash_handler()
            logger.info("XGif starting...")
        except Exception as e:
            print(f"Warning: Crash handler installation failed: {e}")
        
        # 앱 아이콘 설정
        try:
            from core.utils import get_resource_path
            icon_path = get_resource_path(os.path.join('resources', 'xgif_icon.ico'))
            if not os.path.exists(icon_path):
                icon_path = get_resource_path(os.path.join('resources', 'Xgif_icon.png'))
            if os.path.exists(icon_path):
                icon = wx.Icon(icon_path, wx.BITMAP_TYPE_ICO if icon_path.endswith('.ico') else wx.BITMAP_TYPE_PNG)
                self.SetTopWindow(None)  # SetTopWindow는 나중에 설정됨
                self.SetAppDisplayName(APP_SETTINGS_NAME)
        except Exception as e:
            logger.warning(f"App icon setting failed: {e}")
        
        # 단일 인스턴스 체크
        self.checker = SingleInstanceChecker(APP_UNIQUE_NAME)
        if self.checker.IsAnotherRunning():
            # 언어 설정만 미리 로드
            from ui.i18n import get_trans_manager, tr
            import configparser
            config = configparser.ConfigParser()
            config_path = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), APP_SETTINGS_NAME, 'config.ini')
            if os.path.exists(config_path):
                config.read(config_path, encoding='utf-8')
            trans = get_trans_manager()
            language = config.get('General', 'language', fallback='ko') if config.has_section('General') else 'ko'
            trans.set_language(str(language))

            dlg = wx.MessageDialog(
                None,
                tr('already_running_ask_msg'),
                tr('already_running_ask_title'),
                wx.YES_NO | wx.ICON_QUESTION | wx.NO_DEFAULT
            )
            dlg.SetYesNoLabels(tr('already_running_restart'), tr('already_running_cancel'))
            result = dlg.ShowModal()
            dlg.Destroy()

            if result != wx.ID_YES:
                return False

            # 기존 인스턴스 종료 대기 — 자기 자신의 락을 해제한 뒤 재검사
            del self.checker
            for _ in range(25):
                time.sleep(0.2)
                probe = SingleInstanceChecker(APP_UNIQUE_NAME)
                still_running = probe.IsAnotherRunning()
                del probe
                if not still_running:
                    break

            # 락 재취득
            self.checker = SingleInstanceChecker(APP_UNIQUE_NAME)
            if self.checker.IsAnotherRunning():
                wx.MessageBox(
                    tr('already_running_quit_failed'),
                    tr('already_running_ask_title'),
                    wx.OK | wx.ICON_ERROR
                )
                return False
        
        # UI 모듈 지연 로딩
        try:
            from ui import MainWindow
        except ImportError as e:
            logger.critical(f"Cannot import UI module: {e}")
            wx.MessageBox(
                f"UI 모듈을 불러올 수 없습니다:\n{e}\n\n필요한 패키지를 설치했는지 확인하세요.",
                "시작 실패",
                wx.OK | wx.ICON_ERROR
            )
            return False

        # 메인 윈도우 생성 및 표시
        try:
            window = MainWindow(None)
            window.Show()
            self.SetTopWindow(window)
            logger.info("Main window created and shown")

        except Exception as e:
            import traceback
            logger.critical(f"Cannot create main window: {e}")
            logger.critical(f"Full traceback:\n{traceback.format_exc()}")
            wx.MessageBox(
                f"메인 윈도우를 생성할 수 없습니다:\n{e}",
                "시작 실패",
                wx.OK | wx.ICON_ERROR
            )
            return False
        
        return True
    
    def OnExit(self):
        """애플리케이션 종료 시 정리"""
        logger.info("Application terminated")
        return 0


def main():
    """메인 진입점"""
    app = XGifApp(False)  # False = redirect=False (콘솔 출력)
    exit_code = app.MainLoop()
    logger.info(f"Application exiting with code {exit_code}")
    try:
        logging.shutdown()
    finally:
        # 백그라운드 스레드가 남아도 프로세스 종료를 보장
        try:
            os._exit(int(exit_code))
        except Exception:
            sys.exit(exit_code)


if __name__ == '__main__':
    try:
        main()
    except Exception:
        # sys.excepthook이 처리하지만, os._exit 이전에 잡히도록 이중 방어
        import traceback
        msg = traceback.format_exc()
        for crash_dir in [
            os.path.join(os.environ.get('APPDATA', ''), 'XGif'),
            os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else None,
        ]:
            if not crash_dir:
                continue
            try:
                os.makedirs(crash_dir, exist_ok=True)
                with open(os.path.join(crash_dir, 'crash.log'), 'w', encoding='utf-8') as f:
                    f.write(msg)
                break
            except Exception:
                continue
        try:
            ctypes.windll.user32.MessageBoxW(0, msg[:2000], "XGif Startup Error", 0x10)
        except Exception:
            pass
        sys.exit(1)
