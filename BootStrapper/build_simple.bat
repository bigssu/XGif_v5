@echo off
REM XGif Bootstrapper Build Script
echo XGif Bootstrapper Building...

pyinstaller --noconfirm --clean --onedir --windowed --name "XGif_Bootstrapper" --collect-all wx app_entry.py

echo.
echo Done! Check dist\XGif_Bootstrapper\ folder
pause
