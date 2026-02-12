@echo off
REM XGif Bootstrapper 빌드 스크립트
REM Python 3.11 + wxPython이 설치된 환경에서 실행

echo ============================================
echo XGif Bootstrapper 빌드
echo ============================================

REM 가상환경 활성화 (있는 경우)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

REM PyInstaller 설치 확인
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo PyInstaller 설치 중...
    pip install pyinstaller
)

REM 이전 빌드 정리
if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

echo.
echo PyInstaller 빌드 시작...
echo.

REM PyInstaller 빌드 (ONEDIR 모드)
pyinstaller ^
    --noconfirm ^
    --clean ^
    --onedir ^
    --windowed ^
    --name "XGif_Bootstrapper" ^
    --icon "icon.ico" ^
    --add-data "*.py;." ^
    --hidden-import "wx" ^
    --hidden-import "wx._core" ^
    --hidden-import "wx._adv" ^
    --hidden-import "wx._html" ^
    --hidden-import "wx._xml" ^
    --collect-all "wx" ^
    app_entry.py

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패!
    pause
    exit /b 1
)

echo.
echo ============================================
echo 빌드 완료!
echo 출력 위치: dist\XGif_Bootstrapper\
echo ============================================
echo.

REM 빌드 결과 폴더 열기
explorer dist\XGif_Bootstrapper

pause
