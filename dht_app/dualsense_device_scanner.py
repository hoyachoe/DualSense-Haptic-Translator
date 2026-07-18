from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .output_service_package import audit_output_service_package
from .output_service_paths import OutputServicePlan, discover_output_service


DUALSENSE_AUDIO_KEYWORDS = (
    "dualsense",
    "dual sense",
    "wireless controller",
    "playstation",
    "sony interactive",
)


@dataclass(frozen=True)
class DeviceScanResult:
    candidates: list[str]
    source: str
    details: str


def is_dualsense_audio_candidate(name: str) -> bool:
    normalized = str(name).strip().lower()
    if not normalized:
        return False
    return any(keyword in normalized for keyword in DUALSENSE_AUDIO_KEYWORDS)


def dedupe_candidates(names: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for name in names:
        clean = str(name).strip()
        if not clean:
            continue
        key = clean.casefold()
        if key in seen:
            continue
        seen.add(key)
        result.append(clean)
    return result


def filter_dualsense_audio_candidates(raw_devices: list[Any]) -> list[str]:
    candidates: list[str] = []
    for device in raw_devices:
        if isinstance(device, dict):
            name = str(device.get("name", "")).strip()
            try:
                output_channels = int(device.get("max_output_channels", 0))
            except (TypeError, ValueError):
                output_channels = 0
            if output_channels <= 0:
                continue
        else:
            name = str(device).strip()
        if is_dualsense_audio_candidate(name):
            candidates.append(name)
    return dedupe_candidates(candidates)


def filter_audio_output_devices(raw_devices: list[Any]) -> list[str]:
    devices: list[str] = []
    for device in raw_devices:
        if isinstance(device, dict):
            name = str(device.get("name", "")).strip()
            try:
                output_channels = int(device.get("max_output_channels", 0))
            except (TypeError, ValueError):
                output_channels = 0
            if output_channels <= 0:
                continue
        else:
            name = str(device).strip()
        if name:
            devices.append(name)
    return dedupe_candidates(devices)


def scan_dualsense_audio_candidates(
    fallback_candidates: list[str] | None = None,
    app_root: Path | str | None = None,
) -> DeviceScanResult:
    """Return likely DualSense playback endpoints.

    Prefer the bundled DualSense output server because it enumerates the same
    active WASAPI playback endpoints that the haptic output server will use.
    Fall back to optional `sounddevice`, then saved candidates.
    """
    fallback = dedupe_candidates(fallback_candidates or [])
    server_result = scan_dualsense_audio_candidates_from_output_service(app_root)
    if server_result.candidates:
        return server_result
    if server_result.details.startswith("Output-service listed "):
        return server_result
    server_details = server_result.details

    try:
        import sounddevice as sd  # type: ignore
    except Exception as exc:
        return DeviceScanResult(
            fallback,
            "fallback",
            (
                f"{server_details} sounddevice is not available; "
                f"kept {len(fallback)} saved candidate(s). {exc}"
            ),
        )

    try:
        raw_devices = sd.query_devices()
    except Exception as exc:
        return DeviceScanResult(
            fallback,
            "fallback",
            f"{server_details} sounddevice query failed; kept {len(fallback)} saved candidate(s). {exc}",
        )

    candidates = filter_dualsense_audio_candidates(list(raw_devices))
    if not candidates:
        return DeviceScanResult(
            fallback,
            "sounddevice",
            (
                f"{server_details} sounddevice found no DualSense playback candidates; "
                f"kept {len(fallback)} saved candidate(s)."
            ),
        )
    return DeviceScanResult(
        candidates,
        "sounddevice",
        f"{server_details} sounddevice found {len(candidates)} DualSense playback candidate(s).",
    )


def scan_audio_output_devices(
    fallback_candidates: list[str] | None = None,
    app_root: Path | str | None = None,
) -> DeviceScanResult:
    """Return active playback endpoints for optional audio-export settings."""
    fallback = dedupe_candidates(fallback_candidates or [])
    server_result = scan_audio_output_devices_from_output_service(app_root)
    if server_result.candidates:
        return _with_fallback_candidates(server_result, fallback)
    server_details = server_result.details

    try:
        import sounddevice as sd  # type: ignore
    except Exception as exc:
        powershell_result = scan_audio_output_devices_from_windows()
        if powershell_result.candidates:
            return _with_fallback_candidates(powershell_result, fallback)
        return DeviceScanResult(
            fallback,
            "fallback",
            (
                f"{server_details} {powershell_result.details} sounddevice is not available; "
                f"kept {len(fallback)} saved device(s). {exc}"
            ),
        )

    try:
        raw_devices = sd.query_devices()
    except Exception as exc:
        powershell_result = scan_audio_output_devices_from_windows()
        if powershell_result.candidates:
            return _with_fallback_candidates(powershell_result, fallback)
        return DeviceScanResult(
            fallback,
            "fallback",
            (
                f"{server_details} {powershell_result.details} sounddevice query failed; "
                f"kept {len(fallback)} saved device(s). {exc}"
            ),
        )

    devices = filter_audio_output_devices(list(raw_devices))
    if devices:
        return _with_fallback_candidates(
            DeviceScanResult(
                devices,
                "sounddevice",
                f"{server_details} sounddevice found {len(devices)} active playback device(s).",
            ),
            fallback,
        )

    powershell_result = scan_audio_output_devices_from_windows()
    if powershell_result.candidates:
        return _with_fallback_candidates(powershell_result, fallback)
    return DeviceScanResult(
        fallback,
        "fallback",
        (
            f"{server_details} sounddevice and Windows fallback found no active playback devices; "
            f"kept {len(fallback)} saved device(s)."
        ),
    )


def scan_dualsense_audio_candidates_from_output_service(
    app_root: Path | str | None = None,
) -> DeviceScanResult:
    plan = discover_output_service(Path(app_root) if app_root is not None else None)
    command = output_service_list_devices_command(plan)
    if command is None:
        return DeviceScanResult([], "output-service", f"{plan.summary} No list command is available.")
    audit = audit_output_service_package(plan)
    if not plan.execution_allowed or not audit.ok:
        return DeviceScanResult(
            [],
            "output-service",
            f"{plan.summary} {audit.summary}",
        )
    try:
        completed = subprocess.run(
            command,
            cwd=str(plan.runtime_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=4.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError as exc:
        return DeviceScanResult([], "output-service", f"Output-service device scan failed: {exc}")
    except subprocess.TimeoutExpired:
        return DeviceScanResult([], "output-service", "Output-service device scan timed out.")
    if completed.returncode != 0:
        stderr = decode_process_output(completed.stderr).strip()
        stdout = decode_process_output(completed.stdout).strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        return DeviceScanResult([], "output-service", f"Output-service device scan failed: {details}")
    stdout = decode_process_output(completed.stdout)
    raw_devices = [line.strip() for line in stdout.splitlines() if line.strip()]
    candidates = filter_dualsense_audio_candidates(raw_devices)
    if not candidates:
        raw_summary = ", ".join(raw_devices[:4])
        if len(raw_devices) > 4:
            raw_summary = f"{raw_summary}, ..."
        return DeviceScanResult(
            [],
            "output-service",
            (
                f"Output-service listed {len(raw_devices)} active playback device(s), "
                f"but no DualSense candidate matched. Devices: {raw_summary or 'none'}."
            ),
        )
    return DeviceScanResult(
        candidates,
        "output-service",
        f"Output-service found {len(candidates)} DualSense candidate(s) from {len(raw_devices)} active playback device(s).",
    )


def scan_audio_output_devices_from_output_service(
    app_root: Path | str | None = None,
) -> DeviceScanResult:
    plan = discover_output_service(Path(app_root) if app_root is not None else None)
    command = output_service_list_devices_command(plan)
    if command is None:
        return DeviceScanResult([], "output-service", f"{plan.summary} No list command is available.")
    audit = audit_output_service_package(plan)
    if not plan.execution_allowed or not audit.ok:
        return DeviceScanResult(
            [],
            "output-service",
            f"{plan.summary} {audit.summary}",
        )
    try:
        completed = subprocess.run(
            command,
            cwd=str(plan.runtime_root),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=4.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except OSError as exc:
        return DeviceScanResult([], "output-service", f"Output-service device scan failed: {exc}")
    except subprocess.TimeoutExpired:
        return DeviceScanResult([], "output-service", "Output-service device scan timed out.")
    if completed.returncode != 0:
        stderr = decode_process_output(completed.stderr).strip()
        stdout = decode_process_output(completed.stdout).strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        return DeviceScanResult([], "output-service", f"Output-service device scan failed: {details}")
    stdout = decode_process_output(completed.stdout)
    devices = dedupe_candidates([line.strip() for line in stdout.splitlines() if line.strip()])
    return DeviceScanResult(
        devices,
        "output-service",
        f"Output-service listed {len(devices)} active playback device(s).",
    )


def scan_audio_output_devices_from_windows() -> DeviceScanResult:
    script = r"""
$base = 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\MMDevices\Audio\Render'
if (Test-Path -LiteralPath $base) {
  Get-ChildItem -LiteralPath $base | ForEach-Object {
    $device = Get-ItemProperty -LiteralPath $_.PSPath
    if ($device.DeviceState -eq 1) {
      $propsPath = Join-Path $_.PSPath 'Properties'
      if (Test-Path -LiteralPath $propsPath) {
        $props = Get-ItemProperty -LiteralPath $propsPath
        $endpoint = [string]$props.'{a45c254e-df1c-4efd-8020-67d146a850e0},2'
        $deviceName = [string]$props.'{b3f8fa53-0004-438e-9003-51a46e139bfc},6'
        if (-not [string]::IsNullOrWhiteSpace($endpoint) -and -not [string]::IsNullOrWhiteSpace($deviceName)) {
          "$endpoint ($deviceName)"
        } elseif (-not [string]::IsNullOrWhiteSpace($deviceName)) {
          $deviceName
        } elseif (-not [string]::IsNullOrWhiteSpace($endpoint)) {
          $endpoint
        }
      }
    }
  }
}
Get-CimInstance Win32_SoundDevice | Where-Object { $_.Status -eq 'OK' } | ForEach-Object {
  if (-not [string]::IsNullOrWhiteSpace([string]$_.Name)) {
    [string]$_.Name
  }
}
"""
    try:
        system_root = Path(os.environ.get("SystemRoot", r"C:\WINDOWS"))
        powershell_path = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        powershell_cmd = str(powershell_path) if powershell_path.exists() else "powershell"
        completed = subprocess.run(
            [powershell_cmd, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=6.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            check=False,
        )
    except Exception as exc:
        return DeviceScanResult([], "windows", f"Windows audio-device fallback failed: {exc}")
    if completed.returncode != 0:
        stderr = decode_process_output(completed.stderr).strip()
        stdout = decode_process_output(completed.stdout).strip()
        details = stderr or stdout or f"exit code {completed.returncode}"
        return DeviceScanResult([], "windows", f"Windows audio-device fallback failed: {details}")
    devices = dedupe_candidates([line.strip() for line in decode_process_output(completed.stdout).splitlines() if line.strip()])
    return DeviceScanResult(
        devices,
        "windows",
        f"Windows fallback listed {len(devices)} active playback device(s).",
    )


def _with_fallback_candidates(result: DeviceScanResult, fallback: list[str]) -> DeviceScanResult:
    merged = dedupe_candidates([*fallback, *result.candidates])
    if merged == result.candidates:
        return result
    return DeviceScanResult(
        merged,
        result.source,
        f"{result.details} Included {len(merged) - len(result.candidates)} saved fallback device(s).",
    )


def output_service_list_devices_command(plan: OutputServicePlan) -> tuple[str, ...] | None:
    if plan.server_executable is not None:
        return (str(plan.server_executable), "--list-output-devices")
    if plan.server_dll is not None:
        return ("dotnet", str(plan.server_dll), "--list-output-devices")
    return None


def decode_process_output(data: bytes | str) -> str:
    if isinstance(data, str):
        return data
    encodings = ("utf-8", "mbcs", "cp949")
    best = ""
    for encoding in encodings:
        try:
            text = data.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            continue
        if "\ufffd" not in text:
            return text
        if not best:
            best = text
    return best or data.decode("utf-8", errors="replace")
