@echo off
setlocal
cd /d "%~dp0" || exit /b 1
python -m PyInstaller --noconfirm --clean --onedir --windowed --name "XGif_Bootstrapper" --paths .. --add-data "..\requirements-gpu.txt;." --collect-all wx app_entry.py
exit /b %errorlevel%
