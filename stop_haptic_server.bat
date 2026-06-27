@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop_haptic_server.ps1"
if errorlevel 1 (
  echo.
  echo Haptic server stop failed.
  pause
)
