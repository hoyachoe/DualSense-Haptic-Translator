@echo off
setlocal
cd /d "%~dp0"
set DHT_DEVELOPER_MODE=
set DHT_ENABLE_REAL_OUTPUT_TEST=
echo.
echo DualSense Haptic Translator - public mode
echo.
py -3.10 -c "import sounddevice" >nul 2>nul
if errorlevel 1 (
  echo Warning: sounddevice is not installed for Python 3.10.
  echo DualSense audio scanning may use saved fallback candidates only.
  echo Install for local testing if needed:
  echo py -3.10 -m pip install sounddevice
  echo.
)
py -3.10 main.py
if errorlevel 1 (
  echo.
  echo Failed to start DualSense Haptic Translator.
  echo Install PySide6 if needed:
  echo py -3.10 -m pip install PySide6 sounddevice
  echo.
  pause
)
