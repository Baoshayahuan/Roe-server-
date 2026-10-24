@echo off
rem Local one-click launcher (Windows). Usage: Start-Local.cmd "D:\path\to\Ring of Elysium"
setlocal
if "%~1"=="" (
  echo Usage: Start-Local.cmd "path to Ring of Elysium"
  exit /b 2
)
set "ROE_SKIP_FIREWALL=1"
call "%~dp0run-roe-2022.cmd" -Client "%~1" -Kit glider -Mode cycle -CycleScale 3 -Duration 2400 -ReliableUDP -IdleHandoff -WinterDoors -WinterWindows -DebugConsole -Target armored -LootCatalog "%~dp0config\windows-smoke-20261015.json"
exit /b %ERRORLEVEL%
