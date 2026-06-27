# DualSense Haptic Translator

DualSense Haptic Translator is a highly experimental project for bringing DualSense-style haptic audio and adaptive trigger feedback to the Forza Horizon series on Windows.

Forza Horizon does not officially provide native DualSense haptic feedback, so this project listens to Forza UDP telemetry and translates selected driving events into DualSense output. It is not meant to compete with, replace, or claim superiority over other gamepads or force-feedback experiences. Many players have strong preferences and long familiarity with their own controllers; this project is simply an experiment for people who enjoy the DualSense and want to explore what might be possible in games that do not directly support it.

This is a `v0.9` pre-release shared early for requested testing. It is not complete software, and correct operation is not guaranteed on every PC, controller firmware, Windows audio configuration, Forza version, or store version. Haptic tuning, trigger behavior, HUD behavior, presets, device routing, and compatibility may still change before `v1.0`.

## Quick Start

1. Connect your DualSense controller to Windows.
2. Download the release ZIP and extract it.
3. Start `DualSense Haptic Translator.exe` from the extracted release folder.
4. In the app, press `Select DualSense` and choose the actual DualSense audio output device you are using. This step is required for haptic audio output.
5. In Forza Horizon, enable Data Out.
6. Set the target IP and port:
   - IP Address: `127.0.0.1`
   - Port: `8800` by default, or the port shown in the app.

For source/development runs, use:

```bat
run_telemetry_grapher.bat
```

You can also run directly:

```bat
python telemetry_grapher.py --host 0.0.0.0 --port 8800 --haptic-event-port 18801
```

## Steam vs Xbox App / Windows Store

Steam versions of Forza Horizon usually work with `127.0.0.1` Data Out without extra Windows setup.

Xbox App / Windows Store versions can run inside an AppContainer. In that case, Windows may block loopback traffic from the game to a local app. If Forza Data Out is enabled but this app receives no telemetry, add a loopback exemption for the Forza package.

Open PowerShell as Administrator and list current loopback exemptions:

```powershell
CheckNetIsolation LoopbackExempt -s
```

For a working Forza Horizon package, you may see an entry like:

```text
[3] -----------------------------------------------------------------
    Name: microsoft.sunrisebasegame_8wekyb3d8bbwe
```

If the Forza package is not listed, add it:

```powershell
CheckNetIsolation LoopbackExempt -a -n=Microsoft.SunriseBaseGame_8wekyb3d8bbwe
```

Then restart Forza and use these Forza Data Out settings:

```text
DATA OUT: ON
IP ADDRESS: 127.0.0.1
PORT: 8800, or the telemetry port shown in the app
```

If `127.0.0.1` still does not work, try setting the Forza Data Out IP address to this PC's IPv4 address from `ipconfig`.

The telemetry listener should bind to all interfaces, not loopback only. In C#, that would look like:

```csharp
var udp = new UdpClient(new IPEndPoint(IPAddress.Any, port));
```

This app's telemetry listener is started with `--host 0.0.0.0`, which follows the same idea and keeps LAN/IP testing possible.

## What To Watch First

- `rpm_ratio`: engine intensity and pitch source.
- `speed_kmh`: road/air intensity source.
- `gear`: shift event detection.
- `accel` / `brake`: input-based intensity.
- `slip_combined_max`: wheel slip, drift, tire scrub.
- `surface_rumble_max`: kerb/gravel/road texture.
- `smashable_vel_diff`: object impact candidate.
- `accel_g`: collision and body shock candidate.

## DualSense Output Server

The release launcher starts the DualSense output server automatically. The server listens for local haptic events on `127.0.0.1:18801` and sends translated haptic output to DualSense channels 3 and 4.

For development runs, you can still start the pieces manually:

```bat
start_haptic_server.bat
run_telemetry_grapher.bat
```

## Status

This project is not final release software yet. Some features are still being improved, tuning is ongoing, and behavior may change between builds.

Normal operation is not guaranteed. The app may fail to receive telemetry, may not detect the intended DualSense audio device, or may behave differently depending on Windows audio routing, controller connection mode, Forza edition, and system configuration.

Please treat the current release as an experimental preview rather than a polished end-user product.

Note: `maxGears` is intentionally not used for gear-shift haptic classification because tuned transmissions can make it stale or misleading.

