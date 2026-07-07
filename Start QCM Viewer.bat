@echo off
rem Double-clickable launcher for the QCM Viewer (Windows).
rem
rem First run: installs the uv package manager (one-time) and the app's
rem dependencies, then opens the viewer in your browser. After that it starts
rem in seconds. Keep this window open while you work; close it to stop the viewer.

cd /d "%~dp0"

rem Common uv install locations (Finder/Explorer launches don't load a shell
rem profile), added to PATH so a freshly-installed uv is found this session.
set "PATH=%USERPROFILE%\.local\bin;%USERPROFILE%\.cargo\bin;%PATH%"

where uv >nul 2>nul
if errorlevel 1 (
    echo Installing the uv package manager ^(one-time setup^)...
    powershell -ExecutionPolicy Bypass -NoProfile -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

echo.
echo Starting the QCM Viewer - your browser will open shortly.
echo (The first start downloads dependencies and can take a minute or two.)
echo Keep this window open while you work; close it to stop the viewer.
echo.

rem --port 0 picks a free port automatically, so an already-running viewer
rem (or anything else on the default port) never blocks startup.
uv run qcm view --port 0

rem Pause on error so the window doesn't vanish before the message is read.
if errorlevel 1 pause
