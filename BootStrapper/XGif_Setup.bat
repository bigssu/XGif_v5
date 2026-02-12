@echo off
setlocal enabledelayedexpansion
title XGif Setup
chcp 65001 >nul 2>&1

echo ================================================================
echo   XGif Setup
echo ================================================================
echo.

cd /d "%~dp0"

:: ================================================================
:: STEP 1 - SmartScreen / Zone.Identifier 제거
:: ================================================================
echo [1/3] Windows Defender SmartScreen 우회 준비...
echo ----------------------------------------

:: 모든 exe 파일의 Zone.Identifier 제거
set "UNBLOCK_COUNT=0"
for %%F in ("%~dp0*.exe") do (
    powershell.exe -Command "Remove-Item -LiteralPath '%%F' -Stream Zone.Identifier -ErrorAction SilentlyContinue" 2>nul
    set /a UNBLOCK_COUNT+=1
)
echo   [OK] !UNBLOCK_COUNT!개 exe 차단 해제 완료
echo.

:: ================================================================
:: STEP 2 - VC++ Runtime Check
:: ================================================================
echo [2/3] VC++ Runtime Check
echo ----------------------------------------

set "VCRT_OK=0"
if exist "%SystemRoot%\System32\vcruntime140.dll" (
    echo   [OK] vcruntime140.dll
    set "VCRT_OK=1"
) else (
    echo   [FAIL] vcruntime140.dll - MISSING!
)
if exist "%SystemRoot%\System32\vcruntime140_1.dll" (
    echo   [OK] vcruntime140_1.dll
) else (
    echo   [WARN] vcruntime140_1.dll - MISSING
)
echo.

if "!VCRT_OK!"=="0" (
    echo   VC++ Runtime이 설치되지 않았습니다.
    echo   자동으로 다운로드 페이지를 엽니다...
    start "" "https://aka.ms/vs/17/release/vc_redist.x64.exe"
    echo.
    echo   설치 완료 후 아무 키나 누르세요...
    pause >nul
    echo.
    if exist "%SystemRoot%\System32\vcruntime140.dll" (
        echo   [OK] VC++ Runtime 설치 확인
    ) else (
        echo   [FAIL] VC++ Runtime 여전히 없음 - 계속 진행하면 오류가 발생할 수 있습니다.
        echo.
        set /p CONT="  계속 진행하시겠습니까? (Y/N): "
        if /i not "!CONT!"=="Y" exit /b 1
    )
)

:: ================================================================
:: STEP 3 - XGif Bootstrapper 실행 (의존성 설치)
:: ================================================================
echo [3/3] XGif Bootstrapper 실행
echo ----------------------------------------

:: Bootstrap exe 찾기 (버전 포함 파일명 지원)
set "BOOTSTRAP_EXE="
for %%F in ("%~dp0XGif_Bootstrap_*.exe") do set "BOOTSTRAP_EXE=%%F"
if not defined BOOTSTRAP_EXE (
    if exist "%~dp0XGif_Bootstrap.exe" set "BOOTSTRAP_EXE=%~dp0XGif_Bootstrap.exe"
)
if not defined BOOTSTRAP_EXE (
    if exist "%~dp0XGif_Bootstrapper.exe" set "BOOTSTRAP_EXE=%~dp0XGif_Bootstrapper.exe"
)

if not defined BOOTSTRAP_EXE (
    echo   [FAIL] XGif_Bootstrap*.exe를 찾을 수 없습니다!
    echo          이 bat 파일을 XGif_Bootstrap exe와 같은 폴더에 두세요.
    pause
    exit /b 1
)

echo   [OK] !BOOTSTRAP_EXE! 발견
echo.
echo   Bootstrapper를 시작합니다...
echo   (의존성 설치가 완료되면 자동으로 XGif를 실행합니다)
echo ================================================================
echo.

"!BOOTSTRAP_EXE!" 2> "%~dp0bootstrapper_stderr.log"
set "EXIT_CODE=!errorlevel!"

if "!EXIT_CODE!"=="0" goto :launch_xgif

echo.
echo ================================================================
echo   [ERROR] Bootstrapper 비정상 종료 (code: !EXIT_CODE!)
echo ================================================================
echo.

if "!EXIT_CODE!"=="-1073741515" (
    echo   원인: DLL을 찾을 수 없음 [0xC0000135]
    echo   해결: VC++ Runtime 설치 - https://aka.ms/vs/17/release/vc_redist.x64.exe
)
if "!EXIT_CODE!"=="-1073741701" (
    echo   원인: DLL 초기화 실패 [0xC000007B] - 32/64bit 불일치
    echo   해결: VC++ Redistributable 재설치
)
if "!EXIT_CODE!"=="-1073741819" (
    echo   원인: 액세스 위반 [0xC0000005]
)

:: stderr 출력
if exist "%~dp0bootstrapper_stderr.log" (
    for %%S in ("%~dp0bootstrapper_stderr.log") do (
        if %%~zS GTR 0 (
            echo.
            echo   === stderr 출력 ===
            type "%~dp0bootstrapper_stderr.log"
        )
    )
)
echo.
pause
exit /b !EXIT_CODE!

:: ================================================================
:: Bootstrapper 성공 후 XGif 실행
:: ================================================================
:launch_xgif
echo.
echo ================================================================
echo   Setup 완료!
echo ================================================================

:: XGif exe 찾기 (버전 포함 파일명 지원, Bootstrap exe 제외)
set "XGIF_EXE="
for %%F in ("%~dp0XGif_*.exe") do (
    echo %%~nxF | findstr /i "Bootstrap Setup Debug" >nul
    if errorlevel 1 set "XGIF_EXE=%%F"
)
if not defined XGIF_EXE (
    if exist "%~dp0XGif.exe" set "XGIF_EXE=%~dp0XGif.exe"
)

if defined XGIF_EXE (
    echo.
    echo   XGif를 실행합니다...
    start "" "!XGIF_EXE!"
) else (
    echo.
    echo   [INFO] XGif exe를 찾을 수 없습니다.
    echo          XGif_*.exe를 이 폴더에 넣어주세요.
)

echo.
pause
exit /b 0
