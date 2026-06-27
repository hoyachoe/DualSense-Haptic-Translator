@echo off
setlocal

chcp 65001 >nul
cd /d "%~dp0"
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0run_telemetry_grapher.ps1"
if errorlevel 1 (
  echo.
  echo Telemetry grapher failed.
  pause
)
