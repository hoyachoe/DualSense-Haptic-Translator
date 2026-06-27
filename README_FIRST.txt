DualSense Haptic Translator
===========================

Pre-release notice
------------------
This is a v0.9 pre-release shared early for users who requested access.
Some features are still being improved, tuning is ongoing, and behavior may change before v1.0.

Quick start
-----------
1. Connect your DualSense controller to Windows.
2. In Forza Horizon, enable Data Out.
3. Set Data Out IP to this PC. For same-PC use, set it to 127.0.0.1.
4. Set Data Out port to 8800.
5. Run "DualSense Haptic Translator.exe".

Notes
-----
- The app listens for Forza UDP telemetry and converts selected telemetry events into DualSense haptic output.
- The included runtime folder contains the DualSense output server used by the app.
- Logs are written to the logs folder.
- If Windows blocks the app, choose More info, then Run anyway only if you downloaded it from the official release page.

Known status
------------
- This project is not final release software yet.
- Haptic/trigger tuning may change between builds.
- HUD, presets, device routing, and compatibility behavior may still be adjusted.

Troubleshooting
---------------
- If no telemetry arrives, check Forza Data Out IP and port 8800.
- If haptics do not play, check the Windows audio output device name for DualSense / Wireless Controller.
- Close and reopen the app after changing controller/audio routing.
