@echo off
setlocal

cd /d "%~dp0"
title DualSense Haptic Translator Release Build

echo ========================================
echo DualSense Haptic Translator Release Build
echo ========================================
echo.
echo This will run build_release.ps1 with -Clean.
echo Release output will be created in the release folder.
echo.

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_release.ps1" -Clean %*
set "BUILD_EXIT=%ERRORLEVEL%"

echo.
if "%BUILD_EXIT%"=="0" (
    echo Build completed successfully.
) else (
    echo Build failed with exit code %BUILD_EXIT%.
)
echo.
pause
exit /b %BUILD_EXIT%
