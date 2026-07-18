from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from .app_state import AppState


CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass(frozen=True)
class SoundToHapticResult:
    ok: bool
    changed: bool = False
    details: str = ""
    devices: tuple[str, ...] = ()


class SoundToHapticRuntime:
    """Manage the external sound-to-DualSense haptic bridge process."""

    def __init__(self, base_dir: Path | None = None):
        self.base_dir = Path(base_dir or Path(__file__).resolve().parent)
        self.project_dir = self.base_dir / "sound_to_haptic_bridge"
        self.process: subprocess.Popen | None = None

    def _exe_candidates(self) -> tuple[Path, ...]:
        return (
            self.project_dir / "bin" / "Release" / "net8.0-windows" / "DualSenseSoundToHapticBridge.exe",
            self.project_dir / "bin" / "Debug" / "net8.0-windows" / "DualSenseSoundToHapticBridge.exe",
        )

    def executable(self) -> Path | None:
        for candidate in self._exe_candidates():
            if candidate.exists():
                return candidate
        return None

    def is_running(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def list_capture_devices(self) -> SoundToHapticResult:
        exe = self.executable()
        if exe is None:
            return SoundToHapticResult(
                False,
                False,
                "Sound To Haptic bridge executable is not built yet.",
            )
        try:
            completed = subprocess.run(
                [str(exe), "--list-devices-json"],
                cwd=str(exe.parent),
                capture_output=True,
                text=True,
                timeout=8,
                creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return SoundToHapticResult(False, False, f"Device scan failed: {exc}")
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "Device scan failed.").strip()
            return SoundToHapticResult(False, False, details)
        try:
            payload = json.loads(completed.stdout or "[]")
        except json.JSONDecodeError as exc:
            return SoundToHapticResult(False, False, f"Device scan returned invalid JSON: {exc}")
        devices = tuple(str(item).strip() for item in payload if str(item).strip())
        return SoundToHapticResult(True, True, f"Found {len(devices)} playback capture device(s).", devices)

    def start(self, state: AppState) -> SoundToHapticResult:
        exe = self.executable()
        if exe is None:
            return SoundToHapticResult(
                False,
                False,
                "Sound To Haptic bridge executable is not built yet.",
            )
        capture_device = state.sound_to_haptic.capture_device.strip()
        if not capture_device:
            return SoundToHapticResult(False, False, "Select and save a capture device first.")

        self.stop()
        args = [
            str(exe),
            "--capture-name",
            capture_device,
            "--gain-percent",
            str(int(state.sound_to_haptic.master_gain)),
            "--low-cut-percent",
            str(int(state.sound_to_haptic.low_volume_cut)),
            "--low-pass-hz",
            str(int(state.sound_to_haptic.high_cut_hz)),
            "--dynamic-boost-percent",
            str(int(state.sound_to_haptic.dynamic_boost)),
        ]
        output_device = state.dualsense_device.selected_device.strip()
        if output_device:
            args.extend(["--output-name", output_device])
        try:
            self.process = subprocess.Popen(
                args,
                cwd=str(exe.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                text=True,
                creationflags=CREATE_NO_WINDOW,
            )
        except OSError as exc:
            self.process = None
            return SoundToHapticResult(False, False, f"Sound To Haptic start failed: {exc}")
        try:
            self.process.wait(timeout=0.35)
        except subprocess.TimeoutExpired:
            return SoundToHapticResult(
                True,
                True,
                f"Sound To Haptic started from: {capture_device}",
            )
        stderr = ""
        try:
            stderr = (self.process.stderr.read() if self.process.stderr is not None else "") or ""
        except OSError:
            stderr = ""
        self.process = None
        details = stderr.strip() or "Sound To Haptic bridge exited during startup."
        return SoundToHapticResult(False, False, details)

    def stop(self) -> SoundToHapticResult:
        if self.process is None:
            return SoundToHapticResult(True, False, "Sound To Haptic is already stopped.")
        process = self.process
        self.process = None
        if process.poll() is not None:
            return SoundToHapticResult(True, True, "Sound To Haptic process already exited.")
        try:
            process.terminate()
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=2)
        except OSError as exc:
            return SoundToHapticResult(False, False, f"Sound To Haptic stop failed: {exc}")
        return SoundToHapticResult(True, True, "Sound To Haptic stopped.")
