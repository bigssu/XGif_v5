@echo off
setlocal
cd /d "%~dp0" || exit /b 1
if exist "venv\Scripts\activate.bat" call "venv\Scripts\activate.bat"
if not exist "XGif_Bootstrapper.spec" (
    call build_simple.bat
    exit /b
)
python -m PyInstaller --noconfirm --clean XGif_Bootstrapper.spec
exit /b %errorlevel%
