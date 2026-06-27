# DualSense Haptic Translator

Forza telemetry to DualSense haptic translator.

This tool listens to Forza Horizon UDP Data Out packets, draws live graphs, and
translates telemetry into DualSense haptic audio. Adaptive trigger output is the
next planned output path.

## Run

1. In Forza Horizon, enable Data Out.
2. Set the target IP to this PC. For same-PC testing, use `127.0.0.1`.
3. Set the target port to `8800`.
4. Run `run_telemetry_grapher.bat`.

You can also run directly:

```bat
python telemetry_grapher.py --port 8800
```

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

Run `start_haptic_server.bat` first. The server lives in `dualsense_output_server` and listens for local haptic events on `127.0.0.1:18801`. It sends translated haptic output to DualSense channels 3 and 4.

Then run `run_telemetry_grapher.bat`. The grapher listens to Forza UDP on port `8800`, detects gear changes, and forwards `GEAR_SHIFT` events with rpm/throttle/torque/PI/maxRpm payload to the haptic server. The grapher also saves its window size and position to `telemetry_grapher_settings.json` when closed.





Note: maxGears is intentionally not used for gear-shift haptic classification because tuned transmissions can make it stale or misleading.

