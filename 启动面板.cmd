@echo off
rem Start the ROE control panel (no console window) and open it as an app window.
setlocal
set "ROOT=%~dp0"
set "PYW=%ROOT%.tools\python\pythonw.exe"
if not exist "%PYW%" set "PYW=%ROOT%.tools\python\python.exe"

rem Panel already listening? Just reopen the window.
powershell -NoProfile -Command "if (Test-NetConnection 127.0.0.1 -Port 8770 -InformationLevel Quiet -WarningAction SilentlyContinue) { exit 0 } else { exit 1 }"
if not errorlevel 1 goto open

start "" "%PYW%" -X utf8 -B -u "%ROOT%control\app.py"
timeout /t 2 /nobreak >nul

:open
start "" "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe" --app=http://127.0.0.1:8770/ --window-size=1520,960
exit /b 0
