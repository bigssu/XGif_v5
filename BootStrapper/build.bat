@echo off
REM XGif Bootstrapper 빌드 스크립트
REM Python 3.11 + wxPython이 설치된 환경에서 실행
REM spec 파일(XGif_Bootstrapper.spec)을 사용하여 빌드 결과를 통일

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
echo PyInstaller 빌드 시작 (spec 파일 사용)...
echo.

REM spec 파일 존재 확인
if not exist "XGif_Bootstrapper.spec" (
    echo [오류] XGif_Bootstrapper.spec 파일을 찾을 수 없습니다!
    pause
    exit /b 1
)

REM PyInstaller 빌드 — spec 파일로 통일 (certifi, wx, hidden imports 모두 포함)
pyinstaller XGif_Bootstrapper.spec --clean --noconfirm

if errorlevel 1 (
    echo.
    echo [오류] 빌드 실패!
    pause
    exit /b 1
)

echo.
echo ============================================
echo 빌드 완료!
echo 출력 위치: dist\
echo ============================================
echo.

REM 빌드 결과 폴더 열기
explorer dist

pause
