# Forza Horizon DualSense Haptic Translator

A highly experimental Forza Horizon telemetry translator for DualSense haptic audio and adaptive trigger feedback on Windows.

This project is focused specifically on the Forza Horizon series. It listens to Forza Horizon UDP Data Out telemetry and translates selected driving events into DualSense haptic audio and adaptive trigger feedback.

Forza Horizon does not officially provide native DualSense haptic feedback, so this is an experimental compatibility project for players who want to explore DualSense-style feedback in Forza. It is not intended to compare against, replace, or claim superiority over other gamepads or force-feedback systems. Many players have strong preferences and long familiarity with their own controllers; this project is simply an experiment for people who enjoy the DualSense and want to explore what might be possible in games that do not directly support it.

This is a `v0.9.1` pre-release shared early for requested testing. It is not complete software, and correct operation is not guaranteed on every PC, controller firmware, Windows audio configuration, Forza version, or store version. Haptic tuning, trigger behavior, HUD behavior, presets, device routing, and compatibility may still change before `v1.0`.

## Quick Start For Release ZIP

For normal release users, you do not need to start the server manually. The release launcher starts the required DualSense output server automatically.

1. Connect your DualSense controller to Windows.
2. Download the release ZIP and extract it.
3. Start `DualSense Haptic Translator.exe` from the extracted release folder.
4. In the app, press `Select DualSense` and choose the actual DualSense audio output device you are using. This step is required for haptic audio output.
5. In Forza Horizon, enable Data Out.
6. Set the target IP and port:
   - IP Address: `127.0.0.1`
   - Port: `8800` by default, or the port shown in the app.

If haptic output does not work, first check that the selected Windows playback device is the DualSense audio device, then use the app's haptic test button.

## Store Version Notes

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

### Optional DS4Windows Compatibility Workaround

For Xbox App / Windows Store users, DS4Windows can also be used as a practical compatibility workaround. In this setup, DS4Windows lets the DualSense appear to the game as an Xbox 360 controller for normal game input, while this app still handles DualSense haptic audio and adaptive trigger resistance.

This is optional and is mainly intended for users whose Store/Xbox App version of Forza behaves better with Xbox-style controller input. DS4Windows is a separate third-party tool and is not included with this project.

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

## Development / Manual Run

This section is only for people running the project from source. Release ZIP users should normally use `DualSense Haptic Translator.exe` instead.

For source/development runs, use:

```bat
run_telemetry_grapher.bat
```

You can also start the pieces manually:

```bat
start_haptic_server.bat
python telemetry_grapher.py --host 0.0.0.0 --port 8800 --haptic-event-port 18801
```

The DualSense output server listens for local haptic events on `127.0.0.1:18801` and sends translated haptic output to DualSense channels 3 and 4.

## Status

This project is not final release software yet. Some features are still being improved, tuning is ongoing, and behavior may change between builds.

Normal operation is not guaranteed. The app may fail to receive telemetry, may not detect the intended DualSense audio device, or may behave differently depending on Windows audio routing, controller connection mode, Forza edition, and system configuration.

Please treat the current release as an experimental preview rather than a polished end-user product.

Note: `maxGears` is intentionally not used for gear-shift haptic classification because tuned transmissions can make it stale or misleading.

## License

This project is licensed under the MIT License. See [LICENSE](LICENSE).

