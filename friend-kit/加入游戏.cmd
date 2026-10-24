@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
rem ===== ROE 朋友端启动器 =====
rem 用法：把本文件夹放进游戏目录（和 Europa_Client.exe 同级），双击运行；
rem       或在命令行传主机 IP： 加入游戏.cmd 10.167.31.127
set "HERE=%~dp0"
set "IP=%~1"
if "%IP%"=="" if exist "%HERE%server.txt" set /p IP=<"%HERE%server.txt"
if "%IP%"=="" (
  echo 没有配置主机 IP。请把 IP 写进 server.txt，或用：加入游戏.cmd ^<IP^>
  pause
  exit /b 1
)
echo 正在连接主机 %IP% ...
powershell -NoProfile -ExecutionPolicy Bypass -File "%HERE%join.ps1" -Ip "%IP%" -Client "%HERE%."
set "CODE=%ERRORLEVEL%"
if not "%CODE%"=="0" pause
exit /b %CODE%
