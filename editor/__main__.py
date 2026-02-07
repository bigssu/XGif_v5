"""
GIF Editor 패키지 진입점

별도 프로세스로 editor를 실행할 때 사용됩니다:
    python -m editor [file_path]
"""
import sys
import os

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

    # wxPython 앱 생성
    app = wx.App()

    from editor.ui.editor_main_window_wx import MainWindow

    window = MainWindow()

    # 명령줄 인자로 파일 경로가 전달된 경우 열기
    if len(sys.argv) > 1:
        file_path = sys.argv[1]
        if os.path.exists(file_path):
            window.open_file(file_path)

    window.Show()
    app.MainLoop()


if __name__ == '__main__':
    main()
