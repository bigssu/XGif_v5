"""
diagnose.py – 부트스트래퍼 실행 문제 진단.
cmd 또는 PowerShell에서 실행:  python diagnose.py
"""
import sys
import os
import traceback

print("=" * 50)
print("  부트스트래퍼 진단 도구")
print("=" * 50)
print()
print(f"Python 실행 파일: {sys.executable}")
print(f"Python 버전: {sys.version}")
print(f"현재 디렉토리: {os.getcwd()}")
print(f"스크립트 위치: {os.path.dirname(os.path.abspath(__file__))}")
print()

# 1) Check Python version
print("[1] Python 버전 확인...")
if sys.version_info < (3, 10):
    print("  ✗ Python 3.10 이상이 필요합니다.")
else:
    print(f"  ✓ Python {sys.version_info.major}.{sys.version_info.minor}")

# 2) Check wxPython
print("[2] wxPython 확인...")
try:
    import wx
    print(f"  ✓ wxPython {wx.__version__}")
except ImportError as e:
    print(f"  ✗ wxPython 미설치: {e}")
    print()
    print("  해결 방법:")
    print("    pip install wxPython")
    print()
    print("  만약 pip가 없다면:")
    print("    python -m ensurepip --upgrade")
    print("    python -m pip install wxPython")
    input("\nEnter를 누르면 종료...")
    sys.exit(1)

# 3) Check all local imports
print("[3] 모듈 import 확인...")
script_dir = os.path.dirname(os.path.abspath(__file__))
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

modules = [
    "paths",
    "logging_setup",
    "deps_specs",
    "deps_checker",
    "deps_installer",
    "download_utils",
    "extract_utils",
    "ui_main",
]
all_ok = True
for mod_name in modules:
    try:
        __import__(mod_name)
        print(f"  ✓ {mod_name}")
    except Exception as e:
        print(f"  ✗ {mod_name}: {e}")
        traceback.print_exc()
        all_ok = False

if not all_ok:
    print("\n일부 모듈 import 실패. 위 에러를 확인하세요.")
    input("\nEnter를 누르면 종료...")
    sys.exit(1)

# 4) Try creating the wx.App
print("[4] wx.App 생성 테스트...")
try:
    from logging_setup import setup_logging
    from paths import get_log_file
    logger = setup_logging(get_log_file())

    app = wx.App(redirect=False)
    from ui_main import BootstrapperFrame
    import paths as paths_module
    frame = BootstrapperFrame(logger, paths_module)
    frame.Show()
    print("  ✓ 윈도우 생성 성공 – MainLoop 시작합니다.")
    print()
    app.MainLoop()
except Exception as e:
    print(f"  ✗ 실패: {e}")
    traceback.print_exc()
    input("\nEnter를 누르면 종료...")
    sys.exit(1)
