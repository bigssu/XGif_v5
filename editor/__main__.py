"""
GIF Editor 패키지 진입점

별도 프로세스로 editor를 실행할 때 사용됩니다:
    python -m editor [file_path]
"""
import sys
import os
import logging

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)


def main():
    """메인 함수"""
    # wxPython 사용 (editor는 wxPython 기반)
    try:
        import wx
    except ImportError:
        print("Error: wxPython이 설치되어 있지 않습니다.")
        print("pip install wxPython 명령으로 설치해주세요.")
        sys.exit(1)

    from ui.dark_controls import enable_msw_dark_mode, install_dark_controls
    enable_msw_dark_mode(wx)
    install_dark_controls(wx)

    # wxPython 앱 생성
    app = wx.App()

    from editor.ui.editor_main_window_wx import MainWindow

    window = MainWindow()
    window.Show()

    # 명령줄 인자로 파일 경로가 전달된 경우 열기 — 윈도우 표시 후 wx.CallAfter 로
    # 비동기 로드해야 GIF 로딩 ProgressDialog 가 윈도우 위에 정상 표시된다.
    # 이전엔 Show() 이전에 open_file 을 호출하여 큰 GIF 의 ProgressDialog 가
    # 사용자에게 안 보이는 회귀 ("정지 상태로 보임") 가 있었다.
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            wx.CallAfter(window.open_file, file_path)

    exit_code = app.MainLoop()
    try:
        logging.shutdown()
    finally:
        # 워커 스레드 잔류 시에도 프로세스 종료를 보장
        try:
            os._exit(int(exit_code))
        except Exception:
            sys.exit(exit_code)


if __name__ == '__main__':
    main()
