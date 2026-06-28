"""Live Forza Horizon UDP telemetry grapher.

This is intentionally small and dependency-free. It is a first test bench for
learning which telemetry channels are useful before we bind them to DualSense
haptic audio samples, generated waveforms, and trigger effects.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import queue
import re
import socket
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
from tkinter import messagebox
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


def enable_windows_dpi_awareness() -> None:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        try:
            user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
            return
        except (AttributeError, OSError):
            pass
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
            return
        except (AttributeError, OSError):
            pass
        try:
            user32.SetProcessDPIAware()
        except (AttributeError, OSError):
            pass
    except Exception:
        pass


enable_windows_dpi_awareness()


PACKET_SIZE = 324
DEFAULT_PORT = 8800
DEFAULT_HAPTIC_EVENT_PORT = 18801
DEFAULT_TRIGGER_STATUS_PORT = 18802
DEFAULT_DSX_HOST = "127.0.0.1"
DEFAULT_DSX_PORT = 6969
DSX_CONTROLLER_INDEX = 0
DSX_TRIGGER_UPDATE = 1
DSX_TRIGGER_LEFT = 1
DSX_TRIGGER_RIGHT = 2
DSX_MODE_NORMAL = 0
DSX_MODE_RESISTANCE = 13
DSX_MODE_V3_VIBRATION = 23
MAX_REALTIME_PACKET_AGE_S = 0.25
TRANSIENT_GEAR_VALUE = 11
GRAPH_SECONDS = 12.0
OUTPUT_GRAPH_SECONDS = GRAPH_SECONDS
UI_FPS_MS = 33
RPM_HUD_FPS_MS = 16
MAX_GRAPH_DRAW_POINTS = 240
BASE_WINDOW_WIDTH = 1180
BASE_WINDOW_HEIGHT = 860
UI_FONT_SCALE = 0.50
VALUE_FONT_SCALE = 0.70
HUD_FONT_SCALE = 0.50
MAIN_UI_FONT_SCALE_PERCENT = 100
HUD_FONT_SCALE_PERCENT = 100
DISPLAY_SCALE_PERCENT = 100
HUD_SCALE_PRESETS = (100, 150, 200)
MAIN_UI_SCALE_PRESETS = (100, 150, 200)
DISPLAY_SCALE_PRESETS = (100, 125, 150, 200)
CONFIG_PRESET_NAMES = ("Base", "Soft", "Strong", "User 1", "User 2")
CONFIG_REFERENCE_PRESET_NAMES = ("Base", "Soft", "Strong")
CONFIG_LOCK_REFERENCE_PRESETS = True
CONFIG_PRESET_SETTING_KEYS = (
    "effects",
    "trigger_effects",
)
HUD_SNAP_PIXELS = 10
HUD_SNAP_PIXEL_MIN = 1
HUD_SNAP_PIXEL_MAX = 200
BRAKE_DYNAMIC_LEARNING_SLIP_THRESHOLD = 1.4
BRAKE_DYNAMIC_MIN_LEARNING_BRAKE_PERCENT = 30.0
BRAKE_DYNAMIC_LEARNING_WALL_MARGIN = 5.0
def running_frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def executable_dir() -> Path:
    if running_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def app_work_dir() -> Path:
    try:
        return Path.cwd().resolve()
    except OSError:
        return executable_dir()


def user_data_dir() -> Path:
    if running_frozen():
        return executable_dir() / "user_data"
    return Path(__file__).resolve().parent


def package_root_candidates() -> list[Path]:
    candidates = [
        app_work_dir(),
        executable_dir(),
        executable_dir().parent,
        Path(__file__).resolve().parent,
        Path(__file__).resolve().parent.parent,
    ]
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            resolved = candidate
        key = str(resolved).lower()
        if key in seen:
            continue
        seen.add(key)
        unique.append(resolved)
    return unique


def packaged_file_candidates(*parts: str) -> list[Path]:
    return [root.joinpath(*parts) for root in package_root_candidates()]


DATA_DIR = user_data_dir()
SETTINGS_PATH = DATA_DIR / "telemetry_grapher_settings.json"
SETTINGS_BACKUP_PATH = DATA_DIR / "telemetry_grapher_settings.backup.json"
CONFIG_PRESET_DIR = DATA_DIR / "config_presets" if running_frozen() else Path(__file__).with_name("config_presets")
LOG_DIR = DATA_DIR / "logs"
RELEASE_SETTINGS_PATH = Path(__file__).with_name("telemetry_grapher_release_settings.json")
LOCAL_ONLY_SETTING_KEYS = {
    "window_geometry",
    "window_resize_unlocked",
    "hud_scale_percent",
    "main_ui_scale_percent",
    "display_scale_percent",
    "hud_standby_hide",
    "graph_fields",
    "graph_hidden",
    "selected_output_effect",
    "selected_trigger_effect",
    "selected_detail_type",
    "trigger_mode_test",
    "current_preset",
    "haptic_audio_device",
    "haptic_audio_device_verified",
    "dsx_udp_enabled",
    "dsx_audio_export_enabled",
    "dsx_audio_device",
}
LOCAL_ONLY_SETTING_SUFFIXES = (
    "_geometry",
    "_hud_active",
)
LOCAL_ONLY_SETTING_PATTERNS = (
    re.compile(r".*_geometry_\d+$"),
)


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS_PATH.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}

def preset_detail_setting_keys() -> set[str]:
    keys = set(CONFIG_PRESET_SETTING_KEYS)
    for global_name in ("DEFAULT_EFFECT_SETTINGS", "DEFAULT_TRIGGER_SETTINGS"):
        data = globals().get(global_name)
        if isinstance(data, dict):
            keys.update(str(key) for key in data.keys())
    return keys


def save_settings(settings: dict, make_backup: bool = False, force: bool = False) -> None:
    if not force:
        settings["_unsaved_changes"] = True
        return
    try:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        settings.pop("_unsaved_changes", None)
        if make_backup and SETTINGS_PATH.exists():
            SETTINGS_BACKUP_PATH.write_bytes(SETTINGS_PATH.read_bytes())
        common_settings = json.loads(json.dumps(settings))
        for key in preset_detail_setting_keys():
            common_settings.pop(key, None)
        common_settings.pop("config_presets", None)
        SETTINGS_PATH.write_text(json.dumps(common_settings, indent=2), encoding="utf-8")
    except OSError:
        pass


def is_local_only_setting_key(key: str) -> bool:
    if key in LOCAL_ONLY_SETTING_KEYS:
        return True
    if any(key.endswith(suffix) for suffix in LOCAL_ONLY_SETTING_SUFFIXES):
        return True
    return any(pattern.match(key) for pattern in LOCAL_ONLY_SETTING_PATTERNS)


def release_settings_snapshot(settings: dict) -> dict:
    snapshot = json.loads(json.dumps(settings))
    snapshot.pop("_unsaved_changes", None)
    snapshot.pop("config_presets", None)
    for key in preset_detail_setting_keys():
        snapshot.pop(key, None)
    for key in list(snapshot.keys()):
        if is_local_only_setting_key(str(key)):
            snapshot.pop(key, None)
    return snapshot


def export_release_settings(output_path: Path | None = None) -> Path:
    output_path = output_path or RELEASE_SETTINGS_PATH
    settings = load_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(release_settings_snapshot(settings), indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path


def valid_geometry(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    if re.match(r"^\d+x\d+[+-]\d+[+-]\d+$", value) is None:
        return None
    return value


def geometry_size(value: object) -> tuple[int, int] | None:
    geometry = valid_geometry(value)
    if geometry is None:
        return None
    match = re.match(r"^(\d+)x(\d+)[+-]\d+[+-]\d+$", geometry)
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def geometry_size_compatible(value: object, reference: object, tolerance: float = 0.25) -> bool:
    size = geometry_size(value)
    reference_size = geometry_size(reference)
    if size is None or reference_size is None:
        return False
    width, height = size
    ref_width, ref_height = reference_size
    if ref_width <= 0 or ref_height <= 0:
        return False
    return (
        abs(width - ref_width) / ref_width <= tolerance
        and abs(height - ref_height) / ref_height <= tolerance
    )


def normalized_main_ui_scale_value(value: object, default: int = 100) -> int:
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = default
    return min(MAIN_UI_SCALE_PRESETS, key=lambda preset: abs(preset - percent))


def normalized_hud_scale_value(value: object, default: int = 100) -> int:
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = default
    return min(HUD_SCALE_PRESETS, key=lambda preset: abs(preset - percent))


def normalized_display_scale_value(value: object, default: int = 100) -> int:
    try:
        percent = int(value)
    except (TypeError, ValueError):
        percent = default
    return min(DISPLAY_SCALE_PRESETS, key=lambda preset: abs(preset - percent))


def normalized_config_preset_name(value: object, default: str = "Base") -> str:
    text = str(value).strip() if value is not None else ""
    for preset in CONFIG_PRESET_NAMES:
        if text.lower() == preset.lower():
            return preset
    return default if default in CONFIG_PRESET_NAMES else "Base"


def detect_windows_dpi_percent(default: int = 100) -> int:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        dpi = 0
        try:
            dpi = int(user32.GetDpiForSystem())
        except (AttributeError, OSError):
            try:
                dpi = int(user32.GetDpiForWindow(user32.GetDesktopWindow()))
            except (AttributeError, OSError):
                dpi = 0
        if dpi > 0:
            return max(50, min(400, int(round(dpi / 96.0 * 100.0))))
    except Exception:
        pass
    return default


def recommended_display_scale_value() -> int:
    dpi_percent = detect_windows_dpi_percent()
    # The UI artwork was tuned on a 200% Windows-scaled display. On a 100% display,
    # use 200% app display scale to preserve the same perceived size.
    target = 20000.0 / max(50.0, float(dpi_percent))
    return normalized_display_scale_value(target)


def connected_monitor_count(default: int = 1) -> int:
    try:
        import ctypes

        return max(1, int(ctypes.windll.user32.GetSystemMetrics(80)))
    except Exception:
        return default


def windows_monitor_work_areas() -> list[tuple[int, int, int, int]]:
    try:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32

        class MonitorInfo(ctypes.Structure):
            _fields_ = [
                ("cbSize", wintypes.DWORD),
                ("rcMonitor", wintypes.RECT),
                ("rcWork", wintypes.RECT),
                ("dwFlags", wintypes.DWORD),
            ]

        areas: list[tuple[int, int, int, int]] = []

        def callback(monitor, _hdc, _rect, _data):
            info = MonitorInfo()
            info.cbSize = ctypes.sizeof(MonitorInfo)
            if user32.GetMonitorInfoW(monitor, ctypes.byref(info)):
                work = info.rcWork
                areas.append((int(work.left), int(work.top), int(work.right), int(work.bottom)))
            return True

        monitor_enum_proc = ctypes.WINFUNCTYPE(
            wintypes.BOOL,
            wintypes.HMONITOR,
            wintypes.HDC,
            ctypes.POINTER(wintypes.RECT),
            wintypes.LPARAM,
        )
        user32.EnumDisplayMonitors(0, 0, monitor_enum_proc(callback), 0)
        return sorted(set(areas), key=lambda area: (area[0], area[1]))
    except Exception:
        return []


def display_scale_factor() -> float:
    return normalized_display_scale_value(DISPLAY_SCALE_PERCENT) / 100.0


def main_ui_window_size(scale_percent: object = 100) -> tuple[int, int]:
    scale = normalized_main_ui_scale_value(scale_percent) / 100.0
    return int(round(BASE_WINDOW_WIDTH * scale)), int(round(BASE_WINDOW_HEIGHT * scale))


def base_window_geometry(value: object, scale_percent: object = 100) -> str:
    width, height = main_ui_window_size(scale_percent)
    base_geometry = f"{width}x{height}"
    geometry = valid_geometry(value)
    if geometry is None:
        return base_geometry
    match = re.match(r"^\d+x\d+([+-]\d+[+-]\d+)$", geometry)
    if not match:
        return base_geometry
    return f"{base_geometry}{match.group(1)}"


def scaled_font(family: str, size: int | float, *styles: str, scale: float = UI_FONT_SCALE) -> tuple:
    return (family, max(4, int(round(float(size) * scale))), *styles)


def main_ui_scale_factor() -> float:
    return MAIN_UI_FONT_SCALE_PERCENT / 100.0


def main_ui_font_scale_factor() -> float:
    return main_ui_scale_factor() * display_scale_factor()


def ui_px(value: int | float, minimum: int = 1) -> int:
    return max(minimum, int(round(float(value) * main_ui_scale_factor())))


def ui_font(family: str, size: int | float, *styles: str) -> tuple:
    return scaled_font(family, size, *styles, scale=UI_FONT_SCALE * main_ui_font_scale_factor())


def value_font(family: str, size: int | float, *styles: str) -> tuple:
    return scaled_font(family, size, *styles, scale=VALUE_FONT_SCALE * main_ui_font_scale_factor())


def hud_scale_factor() -> float:
    return max(0.1, HUD_FONT_SCALE_PERCENT / 100.0)


def hud_display_scale_factor() -> float:
    return display_scale_factor()


def hud_px(value: int | float, minimum: int = 1) -> int:
    return max(minimum, int(round(float(value) * hud_scale_factor())))


def hud_font(family: str, size: int | float, *styles: str) -> tuple:
    return scaled_font(family, size, *styles, scale=HUD_FONT_SCALE * hud_display_scale_factor())


def hud_fixed_font(family: str, size: int | float, *styles: str) -> tuple:
    return scaled_font(family, size, *styles, scale=HUD_FONT_SCALE * hud_scale_factor() * hud_display_scale_factor())


def _float(packet: bytes, offset: int) -> float:
    return struct.unpack_from("<f", packet, offset)[0]


def _int(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<i", packet, offset)[0]


def _uint(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<I", packet, offset)[0]


def _short(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<H", packet, offset)[0]


def _sbyte(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<b", packet, offset)[0]


def parse_packet(packet: bytes) -> dict[str, float | int | bool]:
    """Parse Forza Data Out dash-format packets.

    The layout follows the 324-byte Forza Horizon / Motorsport Data Out packet
    commonly used by FH4/FH5-era tools. Some newer title fields may be zero or
    noisy depending on the game version.
    """
    if len(packet) != PACKET_SIZE:
        raise ValueError(f"expected {PACKET_SIZE} bytes, got {len(packet)}")

    return {
        "on": _int(packet, 0) != 0,
        "timestamp_ms": _uint(packet, 4),
        "max_rpm": _float(packet, 8),
        "idle_rpm": _float(packet, 12),
        "rpm": _float(packet, 16),
        "accel_x": _float(packet, 20),
        "accel_y": _float(packet, 24),
        "accel_z": _float(packet, 28),
        "velocity_x": _float(packet, 32),
        "velocity_y": _float(packet, 36),
        "velocity_z": _float(packet, 40),
        "angular_velocity_x": _float(packet, 44),
        "angular_velocity_y": _float(packet, 48),
        "angular_velocity_z": _float(packet, 52),
        "yaw": _float(packet, 56),
        "pitch": _float(packet, 60),
        "roll": _float(packet, 64),
        "norm_suspension_travel_fl": _float(packet, 68),
        "norm_suspension_travel_fr": _float(packet, 72),
        "norm_suspension_travel_rl": _float(packet, 76),
        "norm_suspension_travel_rr": _float(packet, 80),
        "tire_slip_ratio_fl": _float(packet, 84),
        "tire_slip_ratio_fr": _float(packet, 88),
        "tire_slip_ratio_rl": _float(packet, 92),
        "tire_slip_ratio_rr": _float(packet, 96),
        "wheel_rotation_speed_fl": _float(packet, 100),
        "wheel_rotation_speed_fr": _float(packet, 104),
        "wheel_rotation_speed_rl": _float(packet, 108),
        "wheel_rotation_speed_rr": _float(packet, 112),
        "wheel_on_rumble_strip_fl": _int(packet, 116),
        "wheel_on_rumble_strip_fr": _int(packet, 120),
        "wheel_on_rumble_strip_rl": _int(packet, 124),
        "wheel_on_rumble_strip_rr": _int(packet, 128),
        "wheel_in_puddle_fl": _int(packet, 132),
        "wheel_in_puddle_fr": _int(packet, 136),
        "wheel_in_puddle_rl": _int(packet, 140),
        "wheel_in_puddle_rr": _int(packet, 144),
        "surface_rumble_fl": _float(packet, 148),
        "surface_rumble_fr": _float(packet, 152),
        "surface_rumble_rl": _float(packet, 156),
        "surface_rumble_rr": _float(packet, 160),
        "tire_slip_angle_fl": _float(packet, 164),
        "tire_slip_angle_fr": _float(packet, 168),
        "tire_slip_angle_rl": _float(packet, 172),
        "tire_slip_angle_rr": _float(packet, 176),
        "tire_combined_slip_fl": _float(packet, 180),
        "tire_combined_slip_fr": _float(packet, 184),
        "tire_combined_slip_rl": _float(packet, 188),
        "tire_combined_slip_rr": _float(packet, 192),
        "suspension_travel_meters_fl": _float(packet, 196),
        "suspension_travel_meters_fr": _float(packet, 200),
        "suspension_travel_meters_rl": _float(packet, 204),
        "suspension_travel_meters_rr": _float(packet, 208),
        "car_ordinal": _int(packet, 212),
        "car_class": _int(packet, 216),
        "car_performance_index": _int(packet, 220),
        "drive_train": _int(packet, 224),
        "num_cylinders": _int(packet, 228),
        "car_group": _uint(packet, 232),
        "smashable_vel_diff": _float(packet, 236),
        "smashable_mass": _float(packet, 240),
        "position_x": _float(packet, 244),
        "position_y": _float(packet, 248),
        "position_z": _float(packet, 252),
        "speed_kmh": _float(packet, 256) * 3.6,
        "power": _float(packet, 260),
        "torque": _float(packet, 264),
        "tire_temp_fl": _float(packet, 268),
        "tire_temp_fr": _float(packet, 272),
        "tire_temp_rl": _float(packet, 276),
        "tire_temp_rr": _float(packet, 280),
        "boost": _float(packet, 284),
        "fuel": _float(packet, 288),
        "distance_traveled": _float(packet, 292),
        "best_lap_time": _float(packet, 296),
        "last_lap_time": _float(packet, 300),
        "current_lap_time": _float(packet, 304),
        "current_race_time": _float(packet, 308),
        "lap_number": _short(packet, 312),
        "race_position": packet[314],
        "accel": packet[315],
        "brake": packet[316],
        "clutch": packet[317],
        "handbrake": packet[318],
        "gear": packet[319],
        "steer": _sbyte(packet, 320),
        "normalized_driving_line": _sbyte(packet, 321),
        "normalized_ai_brake_difference": _sbyte(packet, 322),
    }


def max_abs(t: dict[str, float | int | bool], prefix: str) -> float:
    return max(abs(float(t[f"{prefix}_{wheel}"])) for wheel in ("fl", "fr", "rl", "rr"))


def derived_signals(t: dict[str, float | int | bool]) -> dict[str, float]:
    max_rpm = max(float(t["max_rpm"]), 1.0)
    accel_g = math.sqrt(
        float(t["accel_x"]) ** 2 + float(t["accel_y"]) ** 2 + float(t["accel_z"]) ** 2
    )
    return {
        "rpm_ratio": max(0.0, min(1.3, float(t["rpm"]) / max_rpm)),
        "speed_kmh": max(0.0, float(t["speed_kmh"])),
        "accel": float(t["accel"]),
        "brake": float(t["brake"]),
        "gear": float(t["gear"]),
        "slip_ratio_max": max_abs(t, "tire_slip_ratio"),
        "slip_combined_max": max_abs(t, "tire_combined_slip"),
        "surface_rumble_max": max_abs(t, "surface_rumble"),
        "smashable_vel_diff": max(0.0, float(t["smashable_vel_diff"])),
        "accel_g": accel_g,
    }


def parse_packet_field_names() -> list[str]:
    sample = bytes(PACKET_SIZE)
    return list(parse_packet(sample).keys())


def derived_field_names() -> list[str]:
    sample = parse_packet(bytes(PACKET_SIZE))
    return list(derived_signals(sample).keys())


@dataclass(frozen=True)
class GraphSpec:
    name: str
    scale: float
    color: str


DEFAULT_GRAPH_FIELDS = ["rpm_ratio", "speed_kmh", "brake"]
GRAPH_COLORS = ["#e74c3c", "#3498db", "#2ecc71"]
EFFECT_GEAR_SHIFT_CORE = "Gear Shift Bite - Core"
EFFECT_GEAR_SHIFT_HIGH_HZ = "Gear Shift Bite - High Hz"
EFFECT_GEAR_SHIFT_PARTICLES = "Gear Shift Bite - Particles"
EFFECT_REV_LIMIT = "Rev limit"
EFFECT_RUMBLE_KERBS = "Rumble Kerbs"
EFFECT_TIRE_LIMIT_LOAD = "Tire Limit Load"
EFFECT_WHEELSPIN_BUZZ = "Wheelspin Buzz"
EFFECT_ROAD_BUMPS = "Road Bumps"
EFFECT_IMPACTS = "Impacts"
EFFECT_IMPACT_SIDE = "Impact - Side"
EFFECT_IMPACT_SMASHABLE = "Impact - Smashable"
TRIGGER_BRAKE_PRESSURE = "Brake Pressure"
TRIGGER_BRAKE_RESISTANCE = "Brake Resistance"
TRIGGER_BRAKE_RESISTANCE_DYNAMIC = "Brake Resistance - Dynamic"
TRIGGER_BRAKE_RESISTANCE_PREDICTIVE = "Brake Resistance - Predictive"
TRIGGER_THROTTLE_PRESSURE = "Throttle Pressure"
TRIGGER_THROTTLE_TRACTION_LIMIT = "Throttle Resistance - Traction"
TRIGGER_GEAR_SHIFT_KICK = "Gear Shift Kick"
TRIGGER_COLLISION_KICK = "Collision Kick"
TRIGGER_KERB_BUZZ = "Kerb Wave"
TRIGGER_RPM_REV_LIMIT = "RPM Rev Limit"
TRIGGER_IMPACT_TICK = "Impact Tick"
TRIGGER_MODE_TEST = "Trigger Mode Test"
BRAKE_TRIGGER_GROUP = (
    TRIGGER_BRAKE_PRESSURE,
    TRIGGER_BRAKE_RESISTANCE,
    TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
    TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
)
R2_TRIGGER_GROUP = (
    TRIGGER_THROTTLE_PRESSURE,
    TRIGGER_THROTTLE_TRACTION_LIMIT,
    TRIGGER_RPM_REV_LIMIT,
    TRIGGER_IMPACT_TICK,
)
BOTH_TRIGGER_GROUP = (
    TRIGGER_GEAR_SHIFT_KICK,
    TRIGGER_COLLISION_KICK,
    TRIGGER_KERB_BUZZ,
)
SLIP_RESPONSE_OFF = "Off"
SLIP_RESPONSE_FULL_OFF = "Full Off"
SLIP_RESPONSE_DROP = "Drop"
SLIP_RESPONSE_PULSE = "Pulse"
SLIP_RESPONSE_MODES = (
    SLIP_RESPONSE_OFF,
    SLIP_RESPONSE_FULL_OFF,
    SLIP_RESPONSE_DROP,
    SLIP_RESPONSE_PULSE,
)
SLIP_PULSE_RATE_MAX = 120
SLIP_PULSE_START_DEFAULT = 85
SLIP_PULSE_END_DEFAULT = 100
SLIP_RUMBLE_AMPLITUDE_DEFAULT = 80
SLIP_RUMBLE_RATE_DEFAULT = 80
SLIP_PULSE_STYLE_PULSE_KICK = "Pulse Kick"
SLIP_PULSE_STYLE_RUMBLE = "Rumble"
SLIP_PULSE_STYLE_WAVE = "Wave"
SLIP_PULSE_STYLE_DSX_VIBRATION_LEGACY = "DSX Vib"
SLIP_PULSE_STYLES = (SLIP_PULSE_STYLE_PULSE_KICK, SLIP_PULSE_STYLE_RUMBLE, SLIP_PULSE_STYLE_WAVE)
HIDDEN_TRIGGER_EFFECTS = {TRIGGER_BRAKE_RESISTANCE_DYNAMIC}
BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH = 8.0
DRIFT_RELIEF_WHEELSPIN_GAIN = 0.20
DRIFT_SCORE_DECAY_PER_SECOND = 0.28
DRIFT_RELIEF_TRIGGER_SCORE = 0.70
DRIFT_RELIEF_TRIGGER_RELEASE_SCORE = 0.55
DRIFT_RELIEF_TRIGGER_HOLD_SECONDS = 2.0


def normalize_slip_pulse_style(style: object, trigger_name: str | None = None) -> str:
    value = str(style).strip()
    if value == SLIP_PULSE_STYLE_DSX_VIBRATION_LEGACY:
        value = SLIP_PULSE_STYLE_WAVE
    if value not in SLIP_PULSE_STYLES:
        value = SLIP_PULSE_STYLE_PULSE_KICK
    wave_trigger_names = {
        TRIGGER_BRAKE_RESISTANCE,
        TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
        TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
        TRIGGER_THROTTLE_TRACTION_LIMIT,
        TRIGGER_RPM_REV_LIMIT,
    }
    if trigger_name in wave_trigger_names and value == SLIP_PULSE_STYLE_PULSE_KICK:
        return SLIP_PULSE_STYLE_WAVE
    if trigger_name not in wave_trigger_names and value == SLIP_PULSE_STYLE_WAVE:
        return SLIP_PULSE_STYLE_PULSE_KICK
    return value


def normalize_trigger_sides(value: object, default: str = "Right") -> str:
    raw = str(value).strip().lower().replace(" ", "")
    left = raw in {"left", "l", "both", "lr", "rl", "left|right", "right|left", "l|r", "r|l"}
    right = raw in {"right", "r", "both", "lr", "rl", "left|right", "right|left", "l|r", "r|l"}
    if not left and not right:
        if str(value).strip() == str(default).strip():
            return "Right"
        return normalize_trigger_sides(default, "Right")
    if left and right:
        return "Both"
    return "Left" if left else "Right"


LEGACY_EFFECT_NAMES = {
    "Road Bumps": EFFECT_ROAD_BUMPS,
    "Road Bumps - Offroad": EFFECT_ROAD_BUMPS,
    "Road Bumps - Offroad 2": EFFECT_ROAD_BUMPS,
    "Road Bumps - Asphalt": EFFECT_ROAD_BUMPS,
}
LEGACY_TRIGGER_NAMES = {
    "Kerb Buzz": TRIGGER_KERB_BUZZ,
    "Throttle Resistance - Traction Limit": TRIGGER_THROTTLE_TRACTION_LIMIT,
}
DEFAULT_EFFECT_SETTINGS = {
    EFFECT_GEAR_SHIFT_CORE: {"enabled": True, "volume": 10},
    EFFECT_GEAR_SHIFT_HIGH_HZ: {"enabled": True, "volume": 10},
    EFFECT_GEAR_SHIFT_PARTICLES: {"enabled": True, "volume": 10},
    EFFECT_REV_LIMIT: {"enabled": True, "volume": 10, "pan": 5},
    EFFECT_RUMBLE_KERBS: {"enabled": True, "volume": 10.0},
    EFFECT_TIRE_LIMIT_LOAD: {"enabled": True, "volume": 10.0},
    EFFECT_WHEELSPIN_BUZZ: {"enabled": True, "volume": 10.0, "pan": 5},
    EFFECT_ROAD_BUMPS: {"enabled": True, "volume": 10.0},
    EFFECT_IMPACTS: {"enabled": True, "volume": 10.0},
    EFFECT_IMPACT_SIDE: {"enabled": True, "volume": 10.0},
    EFFECT_IMPACT_SMASHABLE: {"enabled": True, "volume": 10.0},
}
DEFAULT_TRIGGER_SETTINGS = {
    TRIGGER_BRAKE_PRESSURE: {
        "enabled": True,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 45,
        "slip_off": False,
        "slip_threshold": 1.6,
        "slip_response_mode": SLIP_RESPONSE_OFF,
        "slip_pulse_enabled": False,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_drop_low_percent": 0,
        "slip_low_percent": 10,
        "slip_pulse_high_percent": 35,
        "slip_pulse_start_percent": SLIP_PULSE_START_DEFAULT,
        "slip_pulse_end_percent": SLIP_PULSE_END_DEFAULT,
        "slip_pulse_rate": 12,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
        "strength": 180,
        "smooth_start_ms": 80,
    },
    TRIGGER_BRAKE_RESISTANCE: {
        "enabled": True,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 70,
        "sustain_percent": 8,
        "slip_off": False,
        "slip_threshold": 1.6,
        "slip_response_mode": SLIP_RESPONSE_OFF,
        "slip_pulse_enabled": False,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_drop_low_percent": 0,
        "slip_low_percent": 10,
        "slip_pulse_high_percent": 35,
        "slip_pulse_start_percent": SLIP_PULSE_START_DEFAULT,
        "slip_pulse_end_percent": SLIP_PULSE_END_DEFAULT,
        "slip_pulse_rate": 12,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
        "strength": 180,
        "smooth_start_ms": 80,
    },
    TRIGGER_BRAKE_RESISTANCE_DYNAMIC: {
        "enabled": False,
        "curve": 0,
        "start_percent": 75,
        "max_percent": 55,
        "force_percent": 2,
        "wall_percent": 20,
        "gate_range": 10,
        "slip_off": False,
        "slip_threshold": 1.6,
        "slip_response_mode": SLIP_RESPONSE_OFF,
        "slip_pulse_enabled": False,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_drop_low_percent": 0,
        "slip_low_percent": 10,
        "slip_pulse_high_percent": 35,
        "slip_pulse_start_percent": SLIP_PULSE_START_DEFAULT,
        "slip_pulse_end_percent": SLIP_PULSE_END_DEFAULT,
        "slip_pulse_rate": 12,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
        "strength": 180,
        "smooth_start_ms": 0,
        "pulse_strength": 45,
        "pulse_start_percent": 40,
        "pulse_offset": 5,
        "pulse_timing_offset": -5,
        "haptic_pulse_hz": 70,
        "haptic_pulse_strength": 0,
        "haptic_pulse_start_margin": 25,
        "haptic_pulse_end_margin": 0,
        "pulse_rate": 80,
    },
    TRIGGER_BRAKE_RESISTANCE_PREDICTIVE: {
        "enabled": False,
        "curve": 0,
        "start_percent": 75,
        "max_percent": 55,
        "force_percent": 2,
        "wall_percent": 20,
        "gate_range": 10,
        "slip_off": False,
        "slip_threshold": 1.6,
        "slip_response_mode": SLIP_RESPONSE_OFF,
        "slip_pulse_enabled": False,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_drop_low_percent": 0,
        "slip_low_percent": 10,
        "slip_pulse_high_percent": 35,
        "slip_pulse_start_percent": SLIP_PULSE_START_DEFAULT,
        "slip_pulse_end_percent": SLIP_PULSE_END_DEFAULT,
        "slip_pulse_rate": 12,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
        "strength": 180,
        "smooth_start_ms": 0,
        "pulse_strength": 45,
        "pulse_start_percent": 40,
        "pulse_offset": 16,
        "pulse_timing_offset": -5,
        "haptic_pulse_start_margin": 0,
        "haptic_pulse_end_margin": -16,
        "pulse_rate": 80,
    },
    TRIGGER_THROTTLE_PRESSURE: {
        "enabled": True,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 35,
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 90,
        "smooth_start_ms": 80,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
    },
    TRIGGER_THROTTLE_TRACTION_LIMIT: {
        "enabled": False,
        "curve": 0,
        "start_percent": 100,
        "max_percent": 45,
        "force_percent": 35,
        "wall_percent": 35,
        "gate_range": 10,
        "slip_off": False,
        "slip_threshold": 1.6,
        "slip_end_threshold": 2.2,
        "slip_pulse_enabled": False,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_drop_low_percent": 0,
        "slip_low_percent": 10,
        "slip_pulse_high_percent": 35,
        "slip_pulse_start_percent": SLIP_PULSE_START_DEFAULT,
        "slip_pulse_end_percent": SLIP_PULSE_END_DEFAULT,
        "slip_pulse_rate": 12,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "strength": 90,
        "smooth_start_ms": 0,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
    },
    TRIGGER_GEAR_SHIFT_KICK: {
        "enabled": False,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 55,
        "side": "Right",
        "upshift_strength_percent": 55,
        "upshift_duration_ms": 45,
        "downshift_strength_percent": 55,
        "downshift_duration_ms": 45,
        "upshift_sides": "Right",
        "downshift_sides": "Left",
        "early_input_soft_zone": 35,
        "kick_late_position": 35,
        "kick_softness": 7,
        "release_duration_ms": 45,
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 140,
        "smooth_start_ms": 45,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
    },
    TRIGGER_COLLISION_KICK: {
        "enabled": False,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 60,
        "side": "Both",
        "upshift_strength_percent": 60,
        "upshift_duration_ms": 120,
        "downshift_strength_percent": 60,
        "downshift_duration_ms": 120,
        "upshift_sides": "Both",
        "downshift_sides": "Both",
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 153,
        "smooth_start_ms": 140,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
    },
    TRIGGER_KERB_BUZZ: {
        "enabled": False,
        "curve": 0,
        "start_percent": 20,
        "max_percent": 100,
        "force_percent": 0,
        "side": "Both",
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 0,
        "smooth_start_ms": 0,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 24,
        "slip_dsx_vibration_margin": 0,
        "kerb_l_enabled": True,
        "kerb_r_enabled": True,
        "kerb_l_start_percent": 20,
        "kerb_r_start_percent": 20,
        "kerb_low_hz": 12,
        "kerb_high_hz": 40,
        "kerb_l_low_hz": 12,
        "kerb_l_high_hz": 40,
        "kerb_r_low_hz": 12,
        "kerb_r_high_hz": 40,
        "kerb_l_low_amp": 1,
        "kerb_l_high_amp": 2,
        "kerb_r_low_amp": 1,
        "kerb_r_high_amp": 2,
    },
    TRIGGER_RPM_REV_LIMIT: {
        "enabled": False,
        "curve": 0,
        "start_percent": 94,
        "max_percent": 100,
        "force_percent": 40,
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 100,
        "smooth_start_ms": 40,
        "pulse_strength": 45,
        "pulse_offset": 0,
        "pulse_rate": 12,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 2,
        "slip_dsx_vibration_frequency": 40,
        "slip_dsx_vibration_margin": 0,
    },
    TRIGGER_IMPACT_TICK: {
        "enabled": False,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 40,
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 102,
        "smooth_start_ms": 80,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
        "slip_pulse_style": SLIP_PULSE_STYLE_WAVE,
        "slip_rumble_amplitude": SLIP_RUMBLE_AMPLITUDE_DEFAULT,
        "slip_rumble_rate": SLIP_RUMBLE_RATE_DEFAULT,
        "slip_dsx_vibration_amplitude": 4,
        "slip_dsx_vibration_frequency": 1,
        "slip_dsx_vibration_margin": 1,
    },
    TRIGGER_MODE_TEST: {
        "enabled": False,
        "curve": 0,
        "start_percent": 0,
        "max_percent": 100,
        "force_percent": 0,
        "slip_off": False,
        "slip_threshold": 1.6,
        "strength": 0,
        "smooth_start_ms": 0,
        "pulse_strength": 0,
        "pulse_offset": 0,
        "pulse_rate": 8,
    },
}
TRIGGER_RELEASE_MARGIN_PERCENT = 4.0
PAN_EFFECTS = {
    EFFECT_REV_LIMIT,
    EFFECT_WHEELSPIN_BUZZ,
}
FIELD_DEFAULT_SCALES = {
    "rpm_ratio": 1.2,
    "speed_kmh": 360.0,
    "accel": 255.0,
    "brake": 255.0,
    "clutch": 255.0,
    "handbrake": 255.0,
    "gear": 12.0,
    "steer": 127.0,
    "slip_ratio_max": 5.0,
    "slip_combined_max": 5.0,
    "surface_rumble_max": 2.0,
    "smashable_vel_diff": 50.0,
    "accel_g": 50.0,
    "car_class": 7.0,
    "car_group": 10.0,
    "car_performance_index": 1000.0,
    "rpm": 10000.0,
    "max_rpm": 10000.0,
    "torque": 1200.0,
    "power": 800000.0,
}


OFFICIAL_FIELD_ALIASES = {
    "IsRaceOn": "on",
    "TimestampMS": "timestamp_ms",
    "EngineMaxRpm": "max_rpm",
    "EngineIdleRpm": "idle_rpm",
    "CurrentEngineRpm": "rpm",
    "AccelerationX": "accel_x",
    "AccelerationY": "accel_y",
    "AccelerationZ": "accel_z",
    "VelocityX": "velocity_x",
    "VelocityY": "velocity_y",
    "VelocityZ": "velocity_z",
    "AngularVelocityX": "angular_velocity_x",
    "AngularVelocityY": "angular_velocity_y",
    "AngularVelocityZ": "angular_velocity_z",
    "Yaw": "yaw",
    "Pitch": "pitch",
    "Roll": "roll",
    "NormalizedSuspensionTravelFrontLeft": "norm_suspension_travel_fl",
    "NormalizedSuspensionTravelFrontRight": "norm_suspension_travel_fr",
    "NormalizedSuspensionTravelRearLeft": "norm_suspension_travel_rl",
    "NormalizedSuspensionTravelRearRight": "norm_suspension_travel_rr",
    "TireSlipRatioFrontLeft": "tire_slip_ratio_fl",
    "TireSlipRatioFrontRight": "tire_slip_ratio_fr",
    "TireSlipRatioRearLeft": "tire_slip_ratio_rl",
    "TireSlipRatioRearRight": "tire_slip_ratio_rr",
    "WheelRotationSpeedFrontLeft": "wheel_rotation_speed_fl",
    "WheelRotationSpeedFrontRight": "wheel_rotation_speed_fr",
    "WheelRotationSpeedRearLeft": "wheel_rotation_speed_rl",
    "WheelRotationSpeedRearRight": "wheel_rotation_speed_rr",
    "WheelOnRumbleStripFrontLeft": "wheel_on_rumble_strip_fl",
    "WheelOnRumbleStripFrontRight": "wheel_on_rumble_strip_fr",
    "WheelOnRumbleStripRearLeft": "wheel_on_rumble_strip_rl",
    "WheelOnRumbleStripRearRight": "wheel_on_rumble_strip_rr",
    "WheelInPuddleFrontLeft": "wheel_in_puddle_fl",
    "WheelInPuddleFrontRight": "wheel_in_puddle_fr",
    "WheelInPuddleRearLeft": "wheel_in_puddle_rl",
    "WheelInPuddleRearRight": "wheel_in_puddle_rr",
    "SurfaceRumbleFrontLeft": "surface_rumble_fl",
    "SurfaceRumbleFrontRight": "surface_rumble_fr",
    "SurfaceRumbleRearLeft": "surface_rumble_rl",
    "SurfaceRumbleRearRight": "surface_rumble_rr",
    "TireSlipAngleFrontLeft": "tire_slip_angle_fl",
    "TireSlipAngleFrontRight": "tire_slip_angle_fr",
    "TireSlipAngleRearLeft": "tire_slip_angle_rl",
    "TireSlipAngleRearRight": "tire_slip_angle_rr",
    "TireCombinedSlipFrontLeft": "tire_combined_slip_fl",
    "TireCombinedSlipFrontRight": "tire_combined_slip_fr",
    "TireCombinedSlipRearLeft": "tire_combined_slip_rl",
    "TireCombinedSlipRearRight": "tire_combined_slip_rr",
    "SuspensionTravelMetersFrontLeft": "suspension_travel_meters_fl",
    "SuspensionTravelMetersFrontRight": "suspension_travel_meters_fr",
    "SuspensionTravelMetersRearLeft": "suspension_travel_meters_rl",
    "SuspensionTravelMetersRearRight": "suspension_travel_meters_rr",
    "CarOrdinal": "car_ordinal",
    "CarClass": "car_class",
    "CarPerformanceIndex": "car_performance_index",
    "DrivetrainType": "drive_train",
    "NumCylinders": "num_cylinders",
    "CarGroup": "car_group",
    "SmashableVelDiff": "smashable_vel_diff",
    "SmashableMass": "smashable_mass",
    "PositionX": "position_x",
    "PositionY": "position_y",
    "PositionZ": "position_z",
    "Speed": "speed_kmh",
    "Power": "power",
    "Torque": "torque",
    "TireTempFrontLeft": "tire_temp_fl",
    "TireTempFrontRight": "tire_temp_fr",
    "TireTempRearLeft": "tire_temp_rl",
    "TireTempRearRight": "tire_temp_rr",
    "Boost": "boost",
    "Fuel": "fuel",
    "DistanceTraveled": "distance_traveled",
    "BestLap": "best_lap_time",
    "LastLap": "last_lap_time",
    "CurrentLap": "current_lap_time",
    "CurrentRaceTime": "current_race_time",
    "LapNumber": "lap_number",
    "RacePosition": "race_position",
    "Accel": "accel",
    "Brake": "brake",
    "Clutch": "clutch",
    "HandBrake": "handbrake",
    "Gear": "gear",
    "Steer": "steer",
    "NormalizedDrivingLine": "normalized_driving_line",
    "NormalizedAIBrakeDifference": "normalized_ai_brake_difference",
}


def alias_key(value: str) -> str:
    return "".join(ch for ch in value.lower() if ch.isalnum())


def build_alias_map() -> dict[str, str]:
    aliases: dict[str, str] = {}
    for official, internal in OFFICIAL_FIELD_ALIASES.items():
        aliases[alias_key(official)] = internal
        aliases[alias_key(internal)] = internal
    for name in FIELD_DEFAULT_SCALES:
        aliases[alias_key(name)] = name
    return aliases


FIELD_ALIASES = build_alias_map()


class UDPWorker(threading.Thread):
    def __init__(self, host: str, port: int, out_queue: queue.Queue):
        super().__init__(daemon=True)
        self.host = host
        self.port = port
        self.out_queue = out_queue
        self.stop_event = threading.Event()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
        try:
            sock.bind((self.host, self.port))
        except OSError as exc:
            self.out_queue.put(("bind_error", time.monotonic(), f"{self.host}:{self.port}", str(exc)))
            sock.close()
            return
        sock.settimeout(0.5)

        while not self.stop_event.is_set():
            try:
                packet, addr = sock.recvfrom(1500)
            except socket.timeout:
                continue

            sock.setblocking(False)
            try:
                while True:
                    packet, addr = sock.recvfrom(1500)
            except (BlockingIOError, OSError):
                pass
            finally:
                sock.setblocking(True)
                sock.settimeout(0.5)

            try:
                parsed = parse_packet(packet)
            except ValueError as exc:
                self.out_queue.put(("bad_packet", time.monotonic(), str(exc)))
                continue

            self.out_queue.put(("packet", time.monotonic(), addr, parsed, derived_signals(parsed)))

        sock.close()


class TriggerStatusWorker(threading.Thread):
    def __init__(self, port: int, out_queue: queue.Queue):
        super().__init__(daemon=True)
        self.port = port
        self.out_queue = out_queue
        self.stop_event = threading.Event()

    def run(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.bind(("127.0.0.1", self.port))
        except OSError as exc:
            self.out_queue.put(("trigger_status_error", time.monotonic(), str(exc)))
            sock.close()
            return
        sock.settimeout(0.5)

        while not self.stop_event.is_set():
            try:
                packet, _addr = sock.recvfrom(512)
            except socket.timeout:
                continue
            try:
                message = packet.decode("ascii", errors="ignore").strip()
            except UnicodeDecodeError:
                continue
            values: dict[str, float] = {}
            parts = message.split("|")
            if not parts or parts[0] != "DUALSENSE_INPUT":
                continue
            for part in parts[1:]:
                key, sep, value = part.partition("=")
                if not sep:
                    continue
                try:
                    values[key] = float(value)
                except ValueError:
                    pass
            if values:
                self.out_queue.put(("trigger_status", time.monotonic(), values))

        sock.close()


class TelemetryApp:
    def __init__(self, host: str, port: int, haptic_event_port: int):
        self.launch_host = host
        self.launch_port = int(port)
        self.launch_haptic_event_port = int(haptic_event_port)
        self.root = tk.Tk()
        self.root.title("Forza Telemetry Grapher - DualSense Haptic Translator")
        self.settings = load_settings()
        self.window_resize_unlocked = tk.BooleanVar(value=False)
        self.hud_scale_percent = tk.IntVar(value=self.normalized_hud_scale_percent(self.settings.get("hud_scale_percent", 100)))
        self.main_ui_scale_percent = tk.IntVar(value=self.normalized_main_ui_scale_percent(self.settings.get("main_ui_scale_percent", 100)))
        self.display_scale_percent = tk.IntVar(
            value=self.normalized_display_scale_percent(
                self.settings.get("display_scale_percent", recommended_display_scale_value())
            )
        )
        self.hud_snap_enabled = tk.BooleanVar(value=bool(self.settings.get("hud_snap_enabled", True)))
        self.hud_snap_pixels = tk.IntVar(
            value=self.clamp_int(
                self.settings.get("hud_snap_pixels", HUD_SNAP_PIXELS),
                HUD_SNAP_PIXEL_MIN,
                HUD_SNAP_PIXEL_MAX,
            )
        )
        self.hud_snap_pixel_text = tk.StringVar(value=str(self.hud_snap_pixels.get()))
        self.hud_scale_text = tk.StringVar()
        self.main_ui_scale_text = tk.StringVar()
        self.display_scale_text = tk.StringVar()
        self.current_preset_name = tk.StringVar(value=normalized_config_preset_name(self.settings.get("current_preset", "Base")))
        self.load_startup_config_preset()
        self.apply_scale_globals()
        self.root.geometry(base_window_geometry(self.settings.get("window_geometry"), self.main_ui_scale_percent.get()))
        window_width, window_height = main_ui_window_size(self.main_ui_scale_percent.get())
        self.root.minsize(window_width, window_height)
        self.root.configure(bg="#121417")
        self.apply_window_resize_state()
        self.telemetry_host = host
        self.telemetry_port = self.normalized_udp_port(self.settings.get("udp_port", port), port)

        self.queue: queue.Queue = queue.Queue()
        self.worker = UDPWorker(host, self.telemetry_port, self.queue)
        self.worker.start()
        self.trigger_status_worker = TriggerStatusWorker(DEFAULT_TRIGGER_STATUS_PORT, self.queue)
        self.trigger_status_worker.start()
        self.haptic_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.haptic_addr = ("127.0.0.1", haptic_event_port)
        self.dsx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.dsx_udp_enabled = tk.BooleanVar(value=bool(self.settings.get("dsx_udp_enabled", False)))
        self.dsx_host_text = tk.StringVar(value=str(self.settings.get("dsx_host", DEFAULT_DSX_HOST)))
        self.dsx_port_text = tk.StringVar(
            value=str(self.normalized_udp_port(self.settings.get("dsx_port", DEFAULT_DSX_PORT), DEFAULT_DSX_PORT))
        )
        self.dsx_audio_export_enabled = tk.BooleanVar(value=bool(self.settings.get("dsx_audio_export_enabled", False)))
        self.dsx_audio_device_text = tk.StringVar(value=str(self.settings.get("dsx_audio_device", "")))
        self.haptic_audio_device_text = tk.StringVar(
            value=str(self.settings.get("haptic_audio_device", self.settings.get("dsx_audio_device", "")))
        )
        self.haptic_device_popup: tk.Toplevel | None = None
        self.haptic_device_listbox: tk.Listbox | None = None
        self.haptic_device_loading = False
        self.haptic_device_status_text = tk.StringVar(value="")
        self.haptic_server_status_text = "not selected"
        self.haptic_server_action_running = False
        self.haptic_server_action_result: tuple[str, bool, str, bool] | None = None
        self.haptic_server_process: subprocess.Popen | None = None
        dsx_audio_volume_percent = self.clamp_int(self.settings.get("dsx_audio_volume_percent", 100), 0, 100)
        self.dsx_audio_volume_step = tk.IntVar(value=self.clamp_int(round(dsx_audio_volume_percent / 10), 0, 10))
        self.dsx_audio_volume_text = tk.StringVar(value=f"{self.dsx_audio_volume_step.get() * 10}%")
        self.dsx_audio_device_choices: list[str] = []
        self.dsx_status_text = tk.StringVar(value="DSX UDP off")
        self.dsx_sent_count = 0
        self.dsx_last_error = ""
        self.dsx_base_state = {
            DSX_TRIGGER_LEFT: (DSX_MODE_NORMAL, []),
            DSX_TRIGGER_RIGHT: (DSX_MODE_NORMAL, []),
        }
        self.dsx_overlay_state: dict[int, tuple[float, int, list[int], int, str]] = {}
        self.dsx_overlay_token = 0

        self.started_at = time.monotonic()
        self.last_packet_at = 0.0
        self.packet_count = 0
        self.haptic_event_count = 0
        self.last_error = ""
        self.udp_bind_failed = False
        self.previous_gear: int | None = None
        self.latest_raw: dict[str, float | int | bool] = {}
        self.latest_values: dict[str, float] = {}
        self.drift_relief_enabled = tk.BooleanVar(value=bool(self.settings.get("drift_relief_enabled", True)))
        self.drift_relief_status_text = tk.StringVar(value="standby")
        self.drift_mode_active = False
        self.drift_mode_score = 0.0
        self.drift_mode_score_last_update = 0.0
        self.drift_mode_hold_until = 0.0
        self.drift_relief_high_score_since = 0.0
        self.drift_relief_trigger_suppressed = False
        self.drift_oversteer_component = 0.0
        self.drift_mode_components: dict[str, float] = {
            "over": 0.0,
            "angle": 0.0,
            "drive": 0.0,
            "wheel": 0.0,
            "grip": 0.0,
        }
        self.previous_impact_raw: dict[str, float | int | bool] | None = None
        self.previous_impact_at = 0.0
        self.last_impact_at = 0.0
        self.last_side_impact_at = 0.0
        self.last_smashable_impact_at = 0.0
        self.tire_limit_prev_left = 0.0
        self.tire_limit_prev_right = 0.0
        self.tire_limit_freq_prev_left = 0.0
        self.tire_limit_freq_prev_right = 0.0
        self.tire_limit_entry_until_left = 0.0
        self.tire_limit_entry_until_right = 0.0
        self.tire_limit_gx_smooth = 0.0
        self.tire_limit_gz_smooth = 0.0
        self.latest_tire_limit_levels = (0.0, 0.0, 35.0, 35.0)
        self.wheelspin_left_level = 0.0
        self.wheelspin_right_level = 0.0
        self.latest_wheelspin_levels = (0.0, 0.0)
        self.previous_bump_raw: dict[str, float | int | bool] | None = None
        self.previous_bump_at = 0.0
        self.road_bump_left_level = 0.0
        self.road_bump_right_level = 0.0
        self.road_bump_left_hold_until = 0.0
        self.road_bump_right_hold_until = 0.0
        self.road_bump2_left_level = 0.0
        self.road_bump2_right_level = 0.0
        self.asphalt_bump_left_level = 0.0
        self.asphalt_bump_right_level = 0.0
        self.asphalt_bump_left_hold_until = 0.0
        self.asphalt_bump_right_hold_until = 0.0
        self.latest_road_bump_offroad_levels = (0.0, 0.0, 90.0)
        self.latest_road_bump_offroad2_levels = (0.0, 0.0, 90.0)
        self.latest_road_bump_asphalt_levels = (0.0, 0.0, 90.0)
        self.steer_history: deque[tuple[float, float]] = deque()
        self.active_output_events: list[dict[str, float | str]] = []
        self.effect_output_samples: dict[str, deque[tuple[float, float]]] = {
            name: deque() for name in DEFAULT_EFFECT_SETTINGS
        }
        self.trigger_output_samples: dict[str, deque[tuple[float, float]]] = {
            name: deque() for name in DEFAULT_TRIGGER_SETTINGS
        }
        self.current_log_analysis: dict[str, float | int | str | bool] = {}
        self.log_file = None
        self.log_writer: csv.DictWriter | None = None
        self.log_started_at = 0.0
        self.log_row_count = 0
        self.log_path: Path | None = None
        self.log_rec_text = tk.StringVar(value="● Log Rec")
        self.log_rec_fg = "#8a949f"
        configured_fields = self.settings.get("graph_fields")
        if not isinstance(configured_fields, list) or len(configured_fields) != len(DEFAULT_GRAPH_FIELDS):
            configured_fields = DEFAULT_GRAPH_FIELDS
        self.graph_inputs = [tk.StringVar(value=str(name)) for name in configured_fields]
        configured_hidden = self.settings.get("graph_hidden")
        if not isinstance(configured_hidden, list) or len(configured_hidden) != len(DEFAULT_GRAPH_FIELDS):
            configured_hidden = [False for _ in DEFAULT_GRAPH_FIELDS]
        self.graph_hidden_vars = [tk.BooleanVar(value=bool(value)) for value in configured_hidden]
        self.graph_hidden_at = [time.monotonic() if bool(value) else 0.0 for value in configured_hidden]
        self.graph_hide_buttons: list[tk.Canvas] = []
        self.graph_hide_led_ids: list[int] = []
        self.graph_entries: list[tk.Entry] = []
        self.graph_field_popup: tk.Toplevel | None = None
        self.graph_field_listbox: tk.Listbox | None = None
        self.effect_controls = {}
        self.effect_name_labels = {}
        self.effect_lock_widgets: dict[str, list[tk.Widget]] = {}
        self.effects_lock_overlay: tk.Frame | None = None
        self.detail_lock_overlay: tk.Frame | None = None
        for effect_name in DEFAULT_EFFECT_SETTINGS:
            effect_settings = self.effect_settings(effect_name)
            controls = {
                "enabled": tk.BooleanVar(value=bool(effect_settings["enabled"])),
                "volume": tk.IntVar(value=int(effect_settings["volume"])),
                "volume_text": tk.StringVar(value=self.format_volume(effect_settings["volume"])),
            }
            if effect_name in PAN_EFFECTS:
                controls["pan"] = tk.IntVar(value=int(effect_settings["pan"]))
                controls["pan_text"] = tk.StringVar(value=self.format_pan(effect_settings["pan"]))
            self.effect_controls[effect_name] = controls
        self.trigger_controls = {}
        self.trigger_name_labels = {}
        self.trigger_lock_widgets: dict[str, list[tk.Widget]] = {}
        self.trigger_lock_overlay: tk.Frame | None = None
        self.drift_relief_lock_widgets: list[tk.Widget] = []
        self.trigger_brake_active = {name: False for name in DEFAULT_TRIGGER_SETTINGS}
        self.trigger_smoothed_force = {name: 0.0 for name in DEFAULT_TRIGGER_SETTINGS}
        self.trigger_smooth_bypass = {name: False for name in DEFAULT_TRIGGER_SETTINGS}
        self.trigger_force_last_time = 0.0
        self.last_trigger_clear_at = 0.0
        self.brake_dynamic_gate_smoothed = float(
            DEFAULT_TRIGGER_SETTINGS[TRIGGER_BRAKE_RESISTANCE_DYNAMIC]["wall_percent"]
        )
        self.brake_dynamic_base_force_smoothed = 0.0
        self.brake_dynamic_base_force_last_time = 0.0
        self.brake_dynamic_pulse_zone_active = False
        self.brake_dynamic_pulse_level_value = 0.0
        self.brake_dynamic_server_pulse = 0
        self.brake_dynamic_server_pulse_rate = 0
        self.brake_server_vibration_amplitude = 0
        self.brake_server_vibration_frequency = 0
        self.brake_server_vibration_start_zone = 0
        self.throttle_server_pulse = 0
        self.throttle_server_pulse_rate = 0
        self.throttle_server_vibration_amplitude = 0
        self.throttle_server_vibration_frequency = 0
        self.throttle_server_vibration_start_zone = 0
        self.brake_dynamic_server_pulse_smoothed = 0.0
        self.brake_dynamic_server_pulse_last_time = 0.0
        self.brake_dynamic_pulse_gate_active = False
        self.brake_dynamic_pulse_hold_until = 0.0
        self.brake_resistance_release_hold_force = 0.0
        self.brake_dynamic_release_hold_force = 0.0
        self.brake_dynamic_wall_start_percent = -1.0
        self.brake_predictive_trigger_mode_active = False
        self.brake_predictive_trigger_end_percent = -1.0
        self.brake_predictive_wall_smoothed = -1.0
        self.throttle_traction_wall_start_percent = -1.0
        self.throttle_traction_wall_smoothed = -1.0
        self.throttle_traction_debug = "thr --"
        self.last_car_ordinal = 0
        self.brake_dynamic_cache = self.default_brake_dynamic_cache()
        self.brake_dynamic_event_active = False
        self.brake_dynamic_event_speed_bucket = 0
        self.brake_dynamic_event_wall = 80.0
        self.brake_dynamic_event_peak_brake = 0.0
        self.brake_dynamic_event_peak_limit = 0.0
        self.brake_dynamic_event_first_slip_brake: float | None = None
        self.brake_dynamic_event_slip_off_latched = False
        self.brake_predictive_debug = "pred --"
        self.brake_dynamic_cache_text = tk.StringVar(value="")
        self.brake_dynamic_strength_limited_ui = False
        for trigger_name in DEFAULT_TRIGGER_SETTINGS:
            trigger_settings = self.trigger_settings(trigger_name)
            self.trigger_controls[trigger_name] = {
                "enabled": tk.BooleanVar(value=bool(trigger_settings["enabled"])),
                "curve": tk.IntVar(value=int(trigger_settings["curve"])),
                "curve_text": tk.StringVar(value=str(int(trigger_settings["curve"]))),
                "start_percent": tk.IntVar(value=int(trigger_settings["start_percent"])),
                "start_text": tk.StringVar(value=str(int(trigger_settings["start_percent"]))),
                "max_percent": tk.IntVar(value=int(trigger_settings["max_percent"])),
                "max_text": tk.StringVar(value=str(int(trigger_settings["max_percent"]))),
                "force_percent": tk.IntVar(value=int(trigger_settings["force_percent"])),
                "force_text": tk.StringVar(value=str(int(trigger_settings["force_percent"]))),
                "upshift_strength_percent": tk.IntVar(value=int(trigger_settings.get("upshift_strength_percent", trigger_settings["force_percent"]))),
                "upshift_strength_text": tk.StringVar(value=str(int(trigger_settings.get("upshift_strength_percent", trigger_settings["force_percent"])))),
                "upshift_duration_ms": tk.IntVar(value=int(trigger_settings.get("upshift_duration_ms", trigger_settings["smooth_start_ms"]))),
                "upshift_duration_text": tk.StringVar(value=str(int(trigger_settings.get("upshift_duration_ms", trigger_settings["smooth_start_ms"])))),
                "downshift_strength_percent": tk.IntVar(value=int(trigger_settings.get("downshift_strength_percent", trigger_settings["force_percent"]))),
                "downshift_strength_text": tk.StringVar(value=str(int(trigger_settings.get("downshift_strength_percent", trigger_settings["force_percent"])))),
                "downshift_duration_ms": tk.IntVar(value=int(trigger_settings.get("downshift_duration_ms", trigger_settings["smooth_start_ms"]))),
                "downshift_duration_text": tk.StringVar(value=str(int(trigger_settings.get("downshift_duration_ms", trigger_settings["smooth_start_ms"])))),
                "sustain_percent": tk.IntVar(value=int(trigger_settings.get("sustain_percent", 0))),
                "sustain_text": tk.StringVar(value=str(int(trigger_settings.get("sustain_percent", 0)))),
                "wall_percent": tk.IntVar(value=int(trigger_settings.get("wall_percent", 53))),
                "wall_text": tk.StringVar(value=str(int(trigger_settings.get("wall_percent", 53)))),
                "gate_range": tk.IntVar(value=int(trigger_settings.get("gate_range", 15))),
                "gate_range_text": tk.StringVar(value=str(int(trigger_settings.get("gate_range", 15)))),
                "side": tk.StringVar(value=str(trigger_settings.get("side", "Right"))),
                "upshift_sides": tk.StringVar(value=normalize_trigger_sides(trigger_settings.get("upshift_sides", "Right"), "Right")),
                "downshift_sides": tk.StringVar(value=normalize_trigger_sides(trigger_settings.get("downshift_sides", "Left"), "Left")),
                "early_input_soft_zone": tk.IntVar(value=int(trigger_settings.get("early_input_soft_zone", 35))),
                "early_input_soft_zone_text": tk.StringVar(value=str(int(trigger_settings.get("early_input_soft_zone", 35)))),
                "kick_late_position": tk.IntVar(value=int(trigger_settings.get("kick_late_position", 35))),
                "kick_late_position_text": tk.StringVar(value=str(int(trigger_settings.get("kick_late_position", 35)))),
                "kick_softness": tk.IntVar(value=int(trigger_settings.get("kick_softness", 7))),
                "kick_softness_text": tk.StringVar(value=str(int(trigger_settings.get("kick_softness", 7)))),
                "release_duration_ms": tk.IntVar(value=int(trigger_settings.get("release_duration_ms", 45))),
                "release_duration_text": tk.StringVar(value=str(int(trigger_settings.get("release_duration_ms", 45)))),
                "slip_off": tk.BooleanVar(value=bool(trigger_settings["slip_off"])),
                "slip_threshold": tk.IntVar(value=int(round(float(trigger_settings["slip_threshold"]) * 10))),
                "slip_threshold_text": tk.StringVar(value=f"{float(trigger_settings['slip_threshold']):.1f}"),
                "slip_end_threshold": tk.IntVar(value=int(round(float(trigger_settings.get("slip_end_threshold", 2.2)) * 10))),
                "slip_end_threshold_text": tk.StringVar(value=f"{float(trigger_settings.get('slip_end_threshold', 2.2)):.1f}"),
                "slip_response_mode": tk.StringVar(value=str(trigger_settings.get("slip_response_mode", SLIP_RESPONSE_OFF))),
                "slip_pulse_enabled": tk.BooleanVar(value=bool(trigger_settings.get("slip_pulse_enabled", False))),
                "slip_pulse_style": tk.StringVar(
                    value=normalize_slip_pulse_style(
                        trigger_settings.get("slip_pulse_style", SLIP_PULSE_STYLE_PULSE_KICK),
                        trigger_name,
                    )
                ),
                "slip_drop_low_percent": tk.IntVar(value=int(trigger_settings.get("slip_drop_low_percent", 0))),
                "slip_drop_low_text": tk.StringVar(value=str(int(trigger_settings.get("slip_drop_low_percent", 0)))),
                "slip_low_percent": tk.IntVar(value=int(trigger_settings.get("slip_low_percent", 10))),
                "slip_low_text": tk.StringVar(value=str(int(trigger_settings.get("slip_low_percent", 10)))),
                "slip_pulse_high_percent": tk.IntVar(value=int(trigger_settings.get("slip_pulse_high_percent", 35))),
                "slip_pulse_high_text": tk.StringVar(value=str(int(trigger_settings.get("slip_pulse_high_percent", 35)))),
                "slip_pulse_start_percent": tk.IntVar(value=int(trigger_settings.get("slip_pulse_start_percent", SLIP_PULSE_START_DEFAULT))),
                "slip_pulse_start_text": tk.StringVar(value=str(int(trigger_settings.get("slip_pulse_start_percent", SLIP_PULSE_START_DEFAULT)))),
                "slip_pulse_end_percent": tk.IntVar(value=int(trigger_settings.get("slip_pulse_end_percent", SLIP_PULSE_END_DEFAULT))),
                "slip_pulse_end_text": tk.StringVar(value=str(int(trigger_settings.get("slip_pulse_end_percent", SLIP_PULSE_END_DEFAULT)))),
                "slip_pulse_rate": tk.IntVar(value=int(trigger_settings.get("slip_pulse_rate", 12))),
                "slip_pulse_rate_text": tk.StringVar(value=str(int(trigger_settings.get("slip_pulse_rate", 12)))),
                "slip_rumble_amplitude": tk.IntVar(value=int(trigger_settings.get("slip_rumble_amplitude", SLIP_RUMBLE_AMPLITUDE_DEFAULT))),
                "slip_rumble_amplitude_text": tk.StringVar(value=str(int(trigger_settings.get("slip_rumble_amplitude", SLIP_RUMBLE_AMPLITUDE_DEFAULT)))),
                "slip_rumble_rate": tk.IntVar(value=int(trigger_settings.get("slip_rumble_rate", SLIP_RUMBLE_RATE_DEFAULT))),
                "slip_rumble_rate_text": tk.StringVar(value=str(int(trigger_settings.get("slip_rumble_rate", SLIP_RUMBLE_RATE_DEFAULT)))),
                "slip_dsx_vibration_amplitude": tk.IntVar(value=int(trigger_settings.get("slip_dsx_vibration_amplitude", 2))),
                "slip_dsx_vibration_amplitude_text": tk.StringVar(value=str(int(trigger_settings.get("slip_dsx_vibration_amplitude", 2)))),
                "slip_dsx_vibration_frequency": tk.IntVar(value=int(trigger_settings.get("slip_dsx_vibration_frequency", 40))),
                "slip_dsx_vibration_frequency_text": tk.StringVar(value=str(int(trigger_settings.get("slip_dsx_vibration_frequency", 40)))),
                "slip_dsx_vibration_margin": tk.IntVar(value=int(trigger_settings.get("slip_dsx_vibration_margin", 0))),
                "slip_dsx_vibration_margin_text": tk.StringVar(value=str(int(trigger_settings.get("slip_dsx_vibration_margin", 0)))),
                "kerb_low_hz": tk.IntVar(value=int(trigger_settings.get("kerb_low_hz", 12))),
                "kerb_low_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_low_hz", 12)))),
                "kerb_high_hz": tk.IntVar(value=int(trigger_settings.get("kerb_high_hz", 40))),
                "kerb_high_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_high_hz", 40)))),
                "kerb_l_enabled": tk.BooleanVar(value=bool(trigger_settings.get("kerb_l_enabled", True))),
                "kerb_r_enabled": tk.BooleanVar(value=bool(trigger_settings.get("kerb_r_enabled", True))),
                "kerb_l_start_percent": tk.IntVar(value=int(trigger_settings.get("kerb_l_start_percent", trigger_settings["start_percent"]))),
                "kerb_l_start_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_l_start_percent", trigger_settings["start_percent"])))),
                "kerb_r_start_percent": tk.IntVar(value=int(trigger_settings.get("kerb_r_start_percent", trigger_settings["start_percent"]))),
                "kerb_r_start_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_r_start_percent", trigger_settings["start_percent"])))),
                "kerb_l_low_hz": tk.IntVar(value=int(trigger_settings.get("kerb_l_low_hz", trigger_settings.get("kerb_low_hz", 12)))),
                "kerb_l_low_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_l_low_hz", trigger_settings.get("kerb_low_hz", 12))))),
                "kerb_l_high_hz": tk.IntVar(value=int(trigger_settings.get("kerb_l_high_hz", trigger_settings.get("kerb_high_hz", 40)))),
                "kerb_l_high_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_l_high_hz", trigger_settings.get("kerb_high_hz", 40))))),
                "kerb_r_low_hz": tk.IntVar(value=int(trigger_settings.get("kerb_r_low_hz", trigger_settings.get("kerb_low_hz", 12)))),
                "kerb_r_low_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_r_low_hz", trigger_settings.get("kerb_low_hz", 12))))),
                "kerb_r_high_hz": tk.IntVar(value=int(trigger_settings.get("kerb_r_high_hz", trigger_settings.get("kerb_high_hz", 40)))),
                "kerb_r_high_hz_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_r_high_hz", trigger_settings.get("kerb_high_hz", 40))))),
                "kerb_l_low_amp": tk.IntVar(value=int(trigger_settings.get("kerb_l_low_amp", 1))),
                "kerb_l_low_amp_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_l_low_amp", 1)))),
                "kerb_l_high_amp": tk.IntVar(value=int(trigger_settings.get("kerb_l_high_amp", trigger_settings.get("slip_dsx_vibration_amplitude", 2)))),
                "kerb_l_high_amp_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_l_high_amp", trigger_settings.get("slip_dsx_vibration_amplitude", 2))))),
                "kerb_r_low_amp": tk.IntVar(value=int(trigger_settings.get("kerb_r_low_amp", 1))),
                "kerb_r_low_amp_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_r_low_amp", 1)))),
                "kerb_r_high_amp": tk.IntVar(value=int(trigger_settings.get("kerb_r_high_amp", trigger_settings.get("slip_dsx_vibration_amplitude", 2)))),
                "kerb_r_high_amp_text": tk.StringVar(value=str(int(trigger_settings.get("kerb_r_high_amp", trigger_settings.get("slip_dsx_vibration_amplitude", 2))))),
                "strength": tk.IntVar(value=int(trigger_settings["strength"])),
                "strength_text": tk.StringVar(value=str(int(trigger_settings["strength"]))),
                "smooth_start_ms": tk.IntVar(value=int(trigger_settings["smooth_start_ms"])),
                "smooth_start_text": tk.StringVar(value=str(int(trigger_settings["smooth_start_ms"]))),
                "pulse_strength": tk.IntVar(value=int(trigger_settings.get("pulse_strength", 0))),
                "pulse_strength_text": tk.StringVar(value=str(int(trigger_settings.get("pulse_strength", 0)))),
                "pulse_start_percent": tk.IntVar(value=int(trigger_settings.get("pulse_start_percent", 0))),
                "pulse_start_text": tk.StringVar(value=str(int(trigger_settings.get("pulse_start_percent", 0)))),
                "pulse_offset": tk.IntVar(value=int(trigger_settings.get("pulse_offset", 0))),
                "pulse_offset_text": tk.StringVar(value=str(int(trigger_settings.get("pulse_offset", 0)))),
                "pulse_timing_offset": tk.IntVar(value=int(trigger_settings.get("pulse_timing_offset", 0))),
                "pulse_timing_offset_text": tk.StringVar(value=str(int(trigger_settings.get("pulse_timing_offset", 0)))),
                "haptic_pulse_hz": tk.IntVar(value=int(trigger_settings.get("haptic_pulse_hz", 70))),
                "haptic_pulse_hz_text": tk.StringVar(value=str(int(trigger_settings.get("haptic_pulse_hz", 70)))),
                "haptic_pulse_strength": tk.IntVar(value=int(trigger_settings.get("haptic_pulse_strength", 0))),
                "haptic_pulse_strength_text": tk.StringVar(value=str(int(trigger_settings.get("haptic_pulse_strength", 0)))),
                "haptic_pulse_start_margin": tk.IntVar(value=int(trigger_settings.get("haptic_pulse_start_margin", 25))),
                "haptic_pulse_start_margin_text": tk.StringVar(value=str(int(trigger_settings.get("haptic_pulse_start_margin", 25)))),
                "haptic_pulse_end_margin": tk.IntVar(value=int(trigger_settings.get("haptic_pulse_end_margin", 0))),
                "haptic_pulse_end_margin_text": tk.StringVar(value=str(int(trigger_settings.get("haptic_pulse_end_margin", 0)))),
                "pulse_rate": tk.IntVar(value=int(trigger_settings.get("pulse_rate", 8))),
                "pulse_rate_text": tk.StringVar(value=str(int(trigger_settings.get("pulse_rate", 8)))),
            }
        trigger_test_settings = self.settings.get("trigger_mode_test")
        if not isinstance(trigger_test_settings, dict):
            trigger_test_settings = {}
        self.trigger_mode_test_count = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("count", 8), 1, 30))
        self.trigger_mode_test_count_text = tk.StringVar(value=str(self.trigger_mode_test_count.get()))
        self.trigger_mode_test_on_ms = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("on_ms", 160), 20, 1000))
        self.trigger_mode_test_on_ms_text = tk.StringVar(value=str(self.trigger_mode_test_on_ms.get()))
        self.trigger_mode_test_off_ms = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("off_ms", 120), 0, 1000))
        self.trigger_mode_test_off_ms_text = tk.StringVar(value=str(self.trigger_mode_test_off_ms.get()))
        self.trigger_mode_test_hz = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("hz", 80), 1, 255))
        self.trigger_mode_test_hz_text = tk.StringVar(value=str(self.trigger_mode_test_hz.get()))
        self.trigger_mode_test_amp = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("amp", 80), 1, 255))
        self.trigger_mode_test_amp_text = tk.StringVar(value=str(self.trigger_mode_test_amp.get()))
        self.trigger_mode_test_wall_start = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("wall_start", 40), 0, 100))
        self.trigger_mode_test_wall_start_text = tk.StringVar(value=str(self.trigger_mode_test_wall_start.get()))
        self.trigger_mode_test_wall_end = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("wall_end", 80), 0, 100))
        self.trigger_mode_test_wall_end_text = tk.StringVar(value=str(self.trigger_mode_test_wall_end.get()))
        self.trigger_mode_test_wall_strength = tk.IntVar(value=self.clamp_int(trigger_test_settings.get("wall_strength", 0), 0, 255))
        self.trigger_mode_test_wall_strength_text = tk.StringVar(value=str(self.trigger_mode_test_wall_strength.get()))
        self.trigger_mode_test_status = tk.StringVar(value="")
        self.trigger_mode_test_after_ids: list[str] = []
        self.trigger_mode_test_window: tk.Toplevel | None = None
        selected_effect = LEGACY_EFFECT_NAMES.get(str(self.settings.get("selected_output_effect")), self.settings.get("selected_output_effect"))
        if selected_effect not in DEFAULT_EFFECT_SETTINGS:
            selected_effect = next(iter(DEFAULT_EFFECT_SETTINGS))
        self.selected_output_effect = tk.StringVar(value=str(selected_effect))
        selected_trigger = str(self.settings.get("selected_trigger_effect", TRIGGER_BRAKE_RESISTANCE))
        selected_trigger = LEGACY_TRIGGER_NAMES.get(selected_trigger, selected_trigger)
        if selected_trigger not in DEFAULT_TRIGGER_SETTINGS:
            selected_trigger = next(iter(DEFAULT_TRIGGER_SETTINGS))
        if selected_trigger in HIDDEN_TRIGGER_EFFECTS:
            selected_trigger = TRIGGER_BRAKE_RESISTANCE_PREDICTIVE
        self.selected_trigger_effect = tk.StringVar(value=selected_trigger)
        self.selected_detail_type = tk.StringVar(value=str(self.settings.get("selected_detail_type", "haptic")))
        self.enforce_brake_resistance_exclusive(prefer=selected_trigger)
        self.samples: dict[str, deque[tuple[float, float]]] = {}

        self.status = tk.StringVar(value=f"Packets: 0   Haptic events: 0")
        self.udp_port_text = tk.StringVar(value=str(self.telemetry_port))
        self.udp_state_text = tk.StringVar(value="UDP waiting")
        self.udp_receiving = False
        self.hud_standby_hide_enabled = tk.BooleanVar(value=bool(self.settings.get("hud_standby_hide", False)))
        self.value_text = tk.StringVar(value="Waiting for Forza UDP packets...")
        self.top_debug_text = tk.StringVar(value="pred --")
        self.dualsense_input_text = "DualSense L2/R2 --/--"
        self.last_dualsense_input_at = 0.0
        self.dualsense_left_pct = 0.0
        self.dualsense_right_pct = 0.0
        self.hud_window: tk.Toplevel | None = None
        self.hud_canvas: tk.Canvas | None = None
        self.hud_drag_offset = (0, 0)
        self.gforce_hud_window: tk.Toplevel | None = None
        self.gforce_hud_canvas: tk.Canvas | None = None
        self.gforce_hud_drag_offset = (0, 0)
        self.hud_gforce_points: deque[tuple[float, float]] = deque(maxlen=4)
        self.hud_gforce_previous_vector: tuple[float, float] | None = None
        self.hud_gforce_impact_markers: deque[tuple[float, float, float]] = deque(maxlen=6)
        self.tire_hud_window: tk.Toplevel | None = None
        self.tire_hud_canvas: tk.Canvas | None = None
        self.tire_hud_drag_offset = (0, 0)
        self.steer_hud_window: tk.Toplevel | None = None
        self.steer_hud_canvas: tk.Canvas | None = None
        self.steer_hud_drag_offset = (0, 0)
        self.steer_hud_stable_balance = 0.0
        self.steer_hud_last_sign = 0
        self.steer_hud_last_sign_changed_at = 0.0
        self.steer_hud_pending_sign = 0
        self.steer_hud_pending_count = 0
        self.applied_steer_hud_window: tk.Toplevel | None = None
        self.applied_steer_hud_canvas: tk.Canvas | None = None
        self.applied_steer_hud_drag_offset = (0, 0)
        self.applied_steer_estimate_value = 0.0
        self.applied_steer_last_update = 0.0
        self.applied_steer_hold_until = 0.0
        self.applied_steer_hold_value = 0.0
        self.applied_steer_last_speed_kmh = 0.0
        self.applied_steer_last_input_abs = 0.0
        self.rpm_hud_window: tk.Toplevel | None = None
        self.rpm_hud_canvas: tk.Canvas | None = None
        self.rpm_hud_drag_offset = (0, 0)
        self.rpm_hud_needle_angles: deque[float] = deque(maxlen=4)
        self.rpm_hud_display_rpm: float | None = None
        self.rpm_hud_zero_dropouts = 0
        self.engine_hud_window: tk.Toplevel | None = None
        self.engine_hud_canvas: tk.Canvas | None = None
        self.engine_hud_drag_offset = (0, 0)
        self.engine_hud_boost_peak_by_car: dict[int, float] = {}
        self.engine_hud_boost_display_by_car: dict[int, float] = {}
        self.engine_hud_torque_peak_by_car: dict[int, float] = {}
        self.engine_hud_torque_min_by_car: dict[int, float] = {}
        self.engine_hud_torque_display_by_car: dict[int, float] = {}
        self.engine_hud_torque_needle_angles: deque[float] = deque(maxlen=4)
        self.engine_hud_vacuum_needle_angles: deque[float] = deque(maxlen=4)
        self.drift_debug_hud_window: tk.Toplevel | None = None
        self.drift_debug_hud_canvas: tk.Canvas | None = None
        self.drift_debug_hud_drag_offset = (0, 0)
        self.graph_standby_key: tuple[int, int, str] | None = None
        self.udp_visual_state: str | None = None
        self.save_button_dirty_visual: bool | None = None
        self.options_window: tk.Toplevel | None = None
        self.hud_settings_popup: tk.Toplevel | None = None
        self.hud_scale_popup: tk.Toplevel | None = None
        self.main_ui_scale_popup: tk.Toplevel | None = None
        self.display_scale_popup: tk.Toplevel | None = None
        self.preset_popup: tk.Toplevel | None = None
        self.preset_popup_buttons: dict[str, tk.Button] = {}
        self.preset_copy_button: tk.Button | None = None
        self.preset_copy_mode = False
        self.save_preset_popup: tk.Toplevel | None = None
        self.options_section = tk.StringVar(value="backup")
        self.layout_after_ids: dict[str, str] = {}
        self.pending_canvas_widths: dict[str, int] = {}
        self.pending_value_frame_width = 0

        top_status = tk.Frame(self.root, bg="#121417")
        top_status.pack(fill="x", padx=14, pady=(8, 3))
        top_status.grid_columnconfigure(0, weight=0)
        top_status.grid_columnconfigure(1, weight=0)
        top_status.grid_columnconfigure(2, weight=1)
        top_status.grid_columnconfigure(3, weight=0)

        udp_frame = tk.Frame(top_status, bg="#121417")
        udp_frame.grid(row=0, column=0, sticky="w")
        tk.Label(
            udp_frame,
            text="UDP",
            bg="#121417",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 8, "bold"),
        ).pack(side="left", padx=(0, 4))
        udp_entry = tk.Entry(
            udp_frame,
            textvariable=self.udp_port_text,
            bg="#1d232a",
            fg="#f1c40f",
            insertbackground="#d6dde5",
            relief="flat",
            font=value_font("Consolas", 9, "bold"),
            width=6,
            justify="center",
        )
        udp_entry.pack(side="left", ipady=2)
        udp_entry.bind("<Return>", self.on_udp_port_entered)
        udp_entry.bind("<FocusOut>", self.on_udp_port_entered)
        self.udp_status_led = tk.Canvas(
            udp_frame,
            width=15,
            height=15,
            bg="#121417",
            highlightthickness=0,
            bd=0,
        )
        self.udp_status_led.pack(side="left", padx=(8, 4))
        self.udp_status_led_id = self.udp_status_led.create_rectangle(2, 2, 13, 13, fill="#f1c40f", outline="#f7dc6f", width=1)
        tk.Label(
            udp_frame,
            textvariable=self.udp_state_text,
            bg="#121417",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
            width=9,
        ).pack(side="left")

        hud_controls = tk.Frame(top_status, bg="#121417")
        hud_controls.grid(row=0, column=1, sticky="w", padx=(2, 0))
        self.build_top_separator(hud_controls, padx=(0, 9))
        self.hud_all_button = tk.Button(
            hud_controls,
            text="HUD",
            command=self.toggle_all_huds,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=5,
            pady=2,
        )
        self.hud_all_button.pack(side="left", padx=(0, 8))
        self.hud_settings_button = tk.Button(
            hud_controls,
            text="⚙",
            command=self.show_hud_settings_popup,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            width=2,
            padx=3,
            pady=2,
        )
        self.hud_settings_button.pack(side="left", padx=(0, 4))
        self.hud_standby_hide_button = tk.Checkbutton(
            hud_controls,
            text="Standby Hide",
            variable=self.hud_standby_hide_enabled,
            command=self.on_hud_standby_hide_changed,
            indicatoron=False,
            selectcolor="#252c35",
            bg="#1b2027",
            fg="#8b96a3",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#3b4652",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=3,
            pady=2,
        )
        self.hud_standby_hide_button.pack(side="left", padx=(4, 0))
        self.build_top_separator(hud_controls, padx=(5, 5))
        self.build_top_scale_controls(
            hud_controls,
            "HUD Scale",
            self.hud_scale_text,
            lambda: self.adjust_hud_scale(-1),
            lambda: self.adjust_hud_scale(1),
        )
        self.build_top_separator(hud_controls, padx=(5, 5))
        self.build_top_scale_controls(
            hud_controls,
            "Main UI Scale",
            self.main_ui_scale_text,
            lambda: self.adjust_main_ui_scale(-1),
            lambda: self.adjust_main_ui_scale(1),
        )
        self.build_top_separator(hud_controls, padx=(5, 5))
        self.build_top_display_scale_control(hud_controls)
        self.move_display_button = tk.Button(
            hud_controls,
            text="Move Display",
            command=self.move_window_to_other_display,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 7, "bold"),
            padx=5,
            pady=2,
        )
        self.move_display_button.pack(side="left", padx=(5, 0))
        self.build_top_separator(hud_controls, padx=(5, 0))
        self.update_hud_button()
        self.update_hud_gforce_button()
        self.update_hud_tire_button()
        self.update_hud_steer_button()
        self.update_hud_rpm_button()
        self.update_hud_engine_button()
        self.update_hud_all_button()
        self.update_hud_standby_hide_button()
        tk.Frame(top_status, bg="#121417").grid(row=0, column=2, sticky="ew")

        save_controls = tk.Frame(top_status, bg="#121417")
        save_controls.grid(row=0, column=3, sticky="e", padx=(12, 0))
        self.preset_button = tk.Button(
            save_controls,
            text="Preset",
            command=self.show_preset_popup,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=7,
            pady=2,
        )
        self.preset_button.pack(side="left", padx=(0, 4))
        self.current_preset_label = tk.Label(
            save_controls,
            textvariable=self.current_preset_name,
            bg="#121417",
            fg="#d6dde5",
            font=value_font("Consolas", 8, "bold"),
            width=7,
            anchor="w",
        )
        self.current_preset_label.pack(side="left", padx=(0, 7))
        self.save_settings_button = tk.Button(
            save_controls,
            text="SAVE",
            command=self.manual_save_settings,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=9,
            pady=2,
        )
        self.save_settings_button.pack(side="left", padx=(0, 5))
        self.options_button = tk.Button(
            save_controls,
            text="Options",
            command=self.show_options_window,
            bg="#1f6feb",
            fg="#eef3ff",
            activebackground="#2f81f7",
            activeforeground="#ffffff",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#7db2ff",
            highlightcolor="#eef3ff",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=8,
            pady=2,
        )
        self.options_button.pack(side="left")
        self.update_save_button_state()

        main_frame = tk.Frame(self.root, bg="#121417")
        main_frame.pack(fill="both", expand=True, padx=14, pady=8)
        main_frame.grid_columnconfigure(0, weight=47, uniform="main")
        main_frame.grid_columnconfigure(1, weight=25, uniform="main")
        main_frame.grid_columnconfigure(2, weight=28, uniform="main")
        main_frame.grid_rowconfigure(0, weight=1)

        graph_frame = tk.Frame(main_frame, bg="#121417")
        graph_frame.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        graph_frame.grid_rowconfigure(1, weight=5, uniform="graph_stack")
        graph_frame.grid_rowconfigure(2, weight=5, uniform="graph_stack")
        graph_frame.grid_columnconfigure(0, weight=1)

        control_frame = tk.Frame(graph_frame, bg="#121417")
        control_frame.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        for idx, var in enumerate(self.graph_inputs):
            hidden = bool(self.graph_hidden_vars[idx].get())
            hide_button = tk.Canvas(
                control_frame,
                width=15,
                height=15,
                bg="#121417",
                highlightthickness=0,
                bd=0,
                cursor="hand2",
            )
            hide_button.pack(side="left", padx=(0, 5))
            led_id = hide_button.create_rectangle(
                2,
                2,
                13,
                13,
                fill="#2a3139" if hidden else "#f1c40f",
                outline="#3a434d" if hidden else "#f7dc6f",
                width=1,
            )
            hide_button.bind("<Button-1>", lambda _event, index=idx: self.toggle_graph_hidden(index))
            self.graph_hide_buttons.append(hide_button)
            self.graph_hide_led_ids.append(led_id)
            entry = tk.Entry(
                control_frame,
                textvariable=var,
                bg="#1d232a",
                fg=self.graph_entry_color(idx),
                insertbackground="#d6dde5",
                relief="flat",
                font=ui_font("Consolas", 10, "bold"),
                width=15,
            )
            entry.pack(side="left", padx=(0, 8), ipady=4)
            self.graph_entries.append(entry)
            entry.bind("<Return>", self.on_graph_fields_changed)
            entry.bind("<FocusOut>", self.on_graph_fields_changed)
            entry.bind("<Button-1>", lambda event, index=idx: self.show_graph_field_popup(index, event))

        self.canvas = tk.Canvas(graph_frame, bg="#171b20", highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky="nsew")

        self.message_frame = tk.Frame(graph_frame, bg="#171b20", highlightthickness=1, highlightbackground="#252c35")
        self.message_frame.grid(row=2, column=0, sticky="nsew", pady=(8, 0))
        self.build_effect_detail_panel()

        self.effects_frame = tk.Frame(main_frame, bg="#171b20", highlightthickness=1, highlightbackground="#252c35")
        self.effects_frame.grid(row=0, column=1, sticky="nsew", padx=(0, 8))
        self.build_effects_panel()

        self.trigger_frame = tk.Frame(main_frame, bg="#171b20", highlightthickness=1, highlightbackground="#252c35")
        self.trigger_frame.grid(row=0, column=2, sticky="nsew")
        self.build_trigger_panel()

        self.value_frame = tk.Frame(self.root, bg="#101316", highlightthickness=1, highlightbackground="#252c35")
        self.value_frame.configure(height=52)
        self.value_frame.pack(side="bottom", fill="x", padx=14, pady=(0, 8), before=main_frame)
        self.value_frame.pack_propagate(False)
        self.value_frame.grid_columnconfigure(0, weight=1)
        self.value_frame.grid_columnconfigure(1, weight=0)
        self.value_frame.grid_rowconfigure(0, weight=1)
        value_text_frame = tk.Frame(self.value_frame, bg="#101316")
        value_text_frame.grid(row=0, column=0, sticky="nsew", padx=(9, 7), pady=(2, 2))
        self.log_rec_button = tk.Button(
            self.value_frame,
            textvariable=self.log_rec_text,
            command=self.toggle_log_recording,
            bg="#252c35",
            fg=self.log_rec_fg,
            activebackground="#303946",
            activeforeground=self.log_rec_fg,
            relief="flat",
            font=ui_font("Segoe UI", 7, "bold"),
            padx=4,
            pady=1,
        )
        self.log_rec_button.grid(row=0, column=1, sticky="e", padx=(0, 10), pady=(0, 0))
        self.value_debug_label = tk.Label(
            value_text_frame,
            textvariable=self.top_debug_text,
            bg="#101316",
            fg="#f1c40f",
            font=value_font("Consolas", 7, "bold"),
            justify="left",
            anchor="nw",
            wraplength=1100,
            height=1,
        )
        self.value_debug_label.pack(fill="x")
        self.value_label = tk.Label(
            value_text_frame,
            textvariable=self.value_text,
            bg="#101316",
            fg="#aeb8c4",
            font=value_font("Consolas", 7),
            justify="left",
            anchor="nw",
            wraplength=1100,
            height=1,
        )
        self.value_label.pack(fill="x")
        self.status_label = tk.Label(
            value_text_frame,
            textvariable=self.status,
            bg="#101316",
            fg="#aeb8c4",
            font=value_font("Consolas", 7),
            justify="left",
            anchor="nw",
            wraplength=1100,
            height=1,
        )
        self.status_label.pack(fill="x")
        self.value_frame.bind("<Configure>", self.on_value_frame_configure)

        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind_all("/", self.on_log_record_shortcut)
        self.root.bind_all("<ButtonPress-1>", self.on_global_popup_click, add="+")
        self.restore_hud_active_states()
        self.update_dsx_status_text()
        self.root.after(UI_FPS_MS, self.tick)
        self.root.after(RPM_HUD_FPS_MS, self.rpm_hud_tick)
        self.root.after(650, self.auto_start_haptic_server_for_saved_device)

    def close(self) -> None:
        self.save_window_state()
        self.shutdown_runtime()
        self.root.destroy()

    def shutdown_runtime(self) -> None:
        self.stop_log_recording()
        self.close_hud(mark_dirty=False)
        self.close_gforce_hud(mark_dirty=False)
        self.close_tire_hud(mark_dirty=False)
        self.close_steer_hud(mark_dirty=False)
        self.close_applied_steer_hud(mark_dirty=False)
        self.close_rpm_hud(mark_dirty=False)
        self.close_engine_hud(mark_dirty=False)
        self.close_drift_debug_hud()
        self.close_hud_settings_popup()
        self.close_scale_popup("hud_scale_popup")
        self.close_scale_popup("main_ui_scale_popup")
        self.close_scale_popup("display_scale_popup")
        self.close_preset_popup()
        self.close_save_preset_popup()
        self.stop_haptic_server_async()
        self.worker.stop_event.set()
        self.trigger_status_worker.stop_event.set()
        for worker in (self.worker, self.trigger_status_worker):
            try:
                worker.join(timeout=0.8)
            except RuntimeError:
                pass
        self.haptic_sock.close()
        self.dsx_send_off()
        self.dsx_sock.close()

    def run(self) -> None:
        self.root.mainloop()

    @staticmethod
    def normalized_scale_percent(value, default: int = 100) -> int:
        try:
            percent = int(value)
        except (TypeError, ValueError):
            percent = default
        return max(50, min(200, percent))

    @staticmethod
    def normalized_hud_scale_percent(value, default: int = 100) -> int:
        return normalized_hud_scale_value(value, default)

    @staticmethod
    def normalized_main_ui_scale_percent(value, default: int = 100) -> int:
        return normalized_main_ui_scale_value(value, default)

    @staticmethod
    def normalized_display_scale_percent(value, default: int = 100) -> int:
        return normalized_display_scale_value(value, default)

    def apply_scale_globals(self) -> None:
        global HUD_FONT_SCALE_PERCENT, MAIN_UI_FONT_SCALE_PERCENT, DISPLAY_SCALE_PERCENT
        HUD_FONT_SCALE_PERCENT = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        MAIN_UI_FONT_SCALE_PERCENT = self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get())
        DISPLAY_SCALE_PERCENT = self.normalized_display_scale_percent(self.display_scale_percent.get())
        self.update_scale_texts()

    def update_scale_texts(self) -> None:
        if hasattr(self, "hud_scale_text"):
            self.hud_scale_text.set(f"{self.normalized_hud_scale_percent(self.hud_scale_percent.get())}%")
        if hasattr(self, "main_ui_scale_text"):
            self.main_ui_scale_text.set(f"{self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get())}%")
        if hasattr(self, "display_scale_text"):
            self.display_scale_text.set(f"{self.normalized_display_scale_percent(self.display_scale_percent.get())}%")

    def build_top_separator(self, parent, padx=(8, 8)) -> None:
        tk.Frame(parent, bg="#27313a", width=1, height=18).pack(side="left", padx=padx, pady=2)

    def build_top_scale_popup_control(
        self,
        parent,
        label_text: str,
        percent_text: tk.StringVar,
        button_attr: str,
        command,
    ) -> None:
        button = tk.Button(
            parent,
            text=label_text,
            command=command,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 7, "bold"),
            padx=5,
            pady=2,
        )
        setattr(self, button_attr, button)
        button.pack(side="left", padx=(0, 3))
        tk.Label(
            parent,
            textvariable=percent_text,
            bg="#121417",
            fg="#d6dde5",
            font=value_font("Consolas", 8, "bold"),
            width=4,
            anchor="w",
        ).pack(side="left", padx=(1, 0))

    def build_top_scale_controls(
        self,
        parent,
        label_text: str,
        percent_text: tk.StringVar,
        minus_command,
        plus_command,
    ) -> None:
        button_attr = {
            "HUD Scale": "hud_scale_button",
            "Main UI Scale": "main_ui_scale_button",
        }.get(label_text, "scale_button")
        command = self.show_hud_scale_popup if label_text == "HUD Scale" else self.show_main_ui_scale_popup
        self.build_top_scale_popup_control(parent, label_text, percent_text, button_attr, command)

    def build_top_display_scale_control(self, parent) -> None:
        self.build_top_scale_popup_control(
            parent,
            "Display Scale",
            self.display_scale_text,
            "display_scale_button",
            self.show_display_scale_popup,
        )

    def show_scale_popup(
        self,
        popup_attr: str,
        button_attr: str,
        presets: tuple[int, ...],
        current: int,
        select_command,
        extra_buttons: tuple[tuple[str, bool, object], ...] = (),
    ) -> None:
        existing = getattr(self, popup_attr, None)
        if existing is not None:
            try:
                if existing.winfo_exists():
                    existing.destroy()
            except tk.TclError:
                pass
            setattr(self, popup_attr, None)
            return
        self.close_hud_scale_popups(except_attr=popup_attr)
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        button_count = max(1, len(presets) + len(extra_buttons))
        width = ui_px(54 * button_count + 12)
        height = ui_px(52)
        preferred_x = None
        preferred_y = None
        if hasattr(self, button_attr):
            try:
                button = getattr(self, button_attr)
                preferred_x = button.winfo_rootx()
                preferred_y = button.winfo_rooty() + button.winfo_height() + ui_px(4)
            except tk.TclError:
                preferred_x = None
                preferred_y = None
        x, y = self.popup_position_near_root(width, height, preferred_x=preferred_x, preferred_y=preferred_y)
        popup.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(popup, bg="#171b20")
        body.pack(fill="both", expand=True, padx=ui_px(6), pady=ui_px(6))
        for column, percent in enumerate(presets):
            selected = percent == current
            tk.Button(
                body,
                text=f"{percent}",
                command=lambda value=percent: select_command(value),
                bg="#f1c40f" if selected else "#252c35",
                fg="#101316" if selected else "#d6dde5",
                activebackground="#f7dc6f" if selected else "#303946",
                activeforeground="#101316" if selected else "#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#8a7a2a" if selected else "#53606c",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=value_font("Consolas", 8, "bold"),
                width=4,
                padx=ui_px(4),
                pady=ui_px(3),
            ).grid(row=0, column=column, sticky="ew", padx=(0, ui_px(4)))
        for offset, (label, selected, command) in enumerate(extra_buttons):
            column = len(presets) + offset
            tk.Button(
                body,
                text=label,
                command=command,
                bg="#f1c40f" if selected else "#252c35",
                fg="#101316" if selected else "#d6dde5",
                activebackground="#f7dc6f" if selected else "#303946",
                activeforeground="#101316" if selected else "#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#8a7a2a" if selected else "#53606c",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=value_font("Consolas", 8, "bold"),
                width=4,
                padx=ui_px(4),
                pady=ui_px(3),
            ).grid(row=0, column=column, sticky="ew", padx=(0, ui_px(4)))
        setattr(self, popup_attr, popup)
        self.bind_popup_hover_autoclose(popup, lambda attr=popup_attr: self.close_scale_popup(attr))
        popup.focus_force()

    def show_hud_scale_popup(self) -> None:
        self.show_scale_popup(
            "hud_scale_popup",
            "hud_scale_button",
            HUD_SCALE_PRESETS,
            self.normalized_hud_scale_percent(self.hud_scale_percent.get()),
            self.select_hud_scale_from_popup,
        )

    def select_hud_scale_from_popup(self, percent: int) -> None:
        self.close_scale_popup("hud_scale_popup")
        self.set_hud_scale(percent)

    def show_main_ui_scale_popup(self) -> None:
        self.show_scale_popup(
            "main_ui_scale_popup",
            "main_ui_scale_button",
            MAIN_UI_SCALE_PRESETS,
            self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get()),
            self.select_main_ui_scale_from_popup,
        )

    def select_main_ui_scale_from_popup(self, percent: int) -> None:
        self.close_scale_popup("main_ui_scale_popup")
        self.set_main_ui_scale(percent)

    def show_display_scale_popup(self) -> None:
        auto_percent = recommended_display_scale_value()
        current = self.normalized_display_scale_percent(self.display_scale_percent.get())
        self.show_scale_popup(
            "display_scale_popup",
            "display_scale_button",
            DISPLAY_SCALE_PRESETS,
            current,
            self.select_display_scale_from_popup,
            (("Auto", auto_percent == current, self.select_auto_display_scale_from_popup),),
        )

    def select_display_scale_from_popup(self, percent: int) -> None:
        self.close_scale_popup("display_scale_popup")
        self.set_display_scale(percent)

    def select_auto_display_scale_from_popup(self) -> None:
        self.close_scale_popup("display_scale_popup")
        self.set_auto_display_scale()

    def close_display_scale_popup(self) -> None:
        self.close_scale_popup("display_scale_popup")

    def move_window_to_other_display(self) -> None:
        work_areas = windows_monitor_work_areas()
        if len(work_areas) < 2:
            self.value_text.set("Move Display skipped: single display detected.")
            return
        try:
            self.root.update_idletasks()
            win_x = int(self.root.winfo_x())
            win_y = int(self.root.winfo_y())
            win_w = max(1, int(self.root.winfo_width()))
            win_h = max(1, int(self.root.winfo_height()))
        except tk.TclError:
            self.value_text.set("Move Display failed: window unavailable.")
            return

        center_x = win_x + win_w / 2.0
        center_y = win_y + win_h / 2.0

        def contains(area: tuple[int, int, int, int]) -> bool:
            left, top, right, bottom = area
            return left <= center_x < right and top <= center_y < bottom

        current_index = next((idx for idx, area in enumerate(work_areas) if contains(area)), -1)
        if current_index < 0:
            def distance(area: tuple[int, int, int, int]) -> float:
                left, top, right, bottom = area
                area_x = (left + right) / 2.0
                area_y = (top + bottom) / 2.0
                return (area_x - center_x) ** 2 + (area_y - center_y) ** 2

            current_index = min(range(len(work_areas)), key=lambda idx: distance(work_areas[idx]))

        current_area = work_areas[current_index]
        target_area = work_areas[(current_index + 1) % len(work_areas)]

        cur_left, cur_top, cur_right, cur_bottom = current_area
        tgt_left, tgt_top, tgt_right, tgt_bottom = target_area
        cur_span_x = max(1, cur_right - cur_left - win_w)
        cur_span_y = max(1, cur_bottom - cur_top - win_h)
        x_ratio = max(0.0, min(1.0, (win_x - cur_left) / cur_span_x))
        y_ratio = max(0.0, min(1.0, (win_y - cur_top) / cur_span_y))
        tgt_span_x = max(0, tgt_right - tgt_left - win_w)
        tgt_span_y = max(0, tgt_bottom - tgt_top - win_h)
        new_x = int(round(tgt_left + tgt_span_x * x_ratio))
        new_y = int(round(tgt_top + tgt_span_y * y_ratio))
        new_x = max(tgt_left, min(new_x, max(tgt_left, tgt_right - win_w)))
        new_y = max(tgt_top, min(new_y, max(tgt_top, tgt_bottom - win_h)))

        try:
            self.root.geometry(f"{win_w}x{win_h}+{new_x}+{new_y}")
            self.root.update_idletasks()
            self.settings["window_geometry"] = base_window_geometry(self.root.geometry(), self.main_ui_scale_percent.get())
            self.value_text.set(f"Move Display: {current_index + 1} -> {(current_index + 1) % len(work_areas) + 1}")
        except tk.TclError as exc:
            self.value_text.set(f"Move Display failed: {exc}")

    def close_scale_popup(self, popup_attr: str) -> None:
        popup = getattr(self, popup_attr, None)
        setattr(self, popup_attr, None)
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass

    def close_hud_scale_popups(self, except_attr: str | None = None) -> None:
        if except_attr != "hud_settings_popup":
            self.close_hud_settings_popup()
        for popup_attr in ("hud_scale_popup", "main_ui_scale_popup", "display_scale_popup"):
            if popup_attr != except_attr:
                self.close_scale_popup(popup_attr)

    def on_global_popup_click(self, event) -> None:
        try:
            widget = event.widget
        except AttributeError:
            return
        popup_attrs = ("hud_settings_popup", "hud_scale_popup", "main_ui_scale_popup", "display_scale_popup")
        open_popups = []
        for popup_attr in popup_attrs:
            popup = getattr(self, popup_attr, None)
            try:
                if popup is not None and popup.winfo_exists():
                    open_popups.append(popup)
            except tk.TclError:
                pass
        if not open_popups:
            return

        widget_path = str(widget)
        for popup in open_popups:
            if widget_path.startswith(str(popup)):
                return

        for opener_attr in ("hud_button", "hud_scale_button", "main_ui_scale_button", "display_scale_button"):
            opener = getattr(self, opener_attr, None)
            try:
                if opener is not None and opener.winfo_exists() and widget_path.startswith(str(opener)):
                    return
            except tk.TclError:
                pass

        self.close_hud_scale_popups()

    def bind_popup_hover_autoclose(self, popup: tk.Toplevel, close_callback, delay_ms: int = 1000) -> None:
        state = {"armed": False, "after_id": None}

        def pointer_inside() -> bool:
            try:
                widget = popup.winfo_containing(popup.winfo_pointerx(), popup.winfo_pointery())
                return widget is not None and str(widget).startswith(str(popup))
            except tk.TclError:
                return False

        def cancel_timer() -> None:
            after_id = state.get("after_id")
            if after_id is not None:
                try:
                    self.root.after_cancel(after_id)
                except tk.TclError:
                    pass
                state["after_id"] = None

        def close_if_still_outside() -> None:
            state["after_id"] = None
            if state["armed"] and not pointer_inside():
                close_callback()

        def on_enter(_event=None) -> None:
            state["armed"] = True
            cancel_timer()

        def on_leave(_event=None) -> None:
            if not state["armed"]:
                return
            cancel_timer()
            state["after_id"] = self.root.after(delay_ms, close_if_still_outside)

        def bind_tree(widget) -> None:
            try:
                widget.bind("<Enter>", on_enter, add="+")
                widget.bind("<Leave>", on_leave, add="+")
                for child in widget.winfo_children():
                    bind_tree(child)
            except tk.TclError:
                pass

        bind_tree(popup)

        def arm_if_initially_inside() -> None:
            if pointer_inside():
                on_enter()

        try:
            self.root.after(80, arm_if_initially_inside)
        except tk.TclError:
            pass

    def show_preset_popup(self) -> None:
        if self.preset_popup is not None:
            self.close_preset_popup()
            return
        current = normalized_config_preset_name(self.current_preset_name.get())
        can_copy_to_current = current in ("User 1", "User 2")
        width = ui_px(164)
        height = ui_px(46 * len(CONFIG_PRESET_NAMES) + (72 if can_copy_to_current else 28))
        preferred_x = None
        preferred_y = None
        if hasattr(self, "preset_button"):
            try:
                preferred_x = self.preset_button.winfo_rootx()
                preferred_y = self.preset_button.winfo_rooty() + self.preset_button.winfo_height() + ui_px(4)
            except tk.TclError:
                preferred_x = None
                preferred_y = None
        x, y = self.popup_position_near_root(width, height, preferred_x=preferred_x, preferred_y=preferred_y)
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        popup.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(popup, bg="#171b20")
        body.pack(fill="both", expand=True, padx=ui_px(6), pady=ui_px(6))
        self.preset_popup_buttons = {}
        self.preset_copy_button = None
        self.preset_copy_mode = False
        for row, preset in enumerate(CONFIG_PRESET_NAMES):
            button = tk.Button(
                body,
                text=preset,
                command=lambda value=preset: self.on_preset_popup_button_clicked(value),
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="w",
                padx=ui_px(8),
                pady=ui_px(4),
            )
            button.grid(row=row, column=0, sticky="ew", pady=(0, ui_px(5)))
            button.bind("<Enter>", lambda _event, value=preset: self.on_preset_popup_button_hover(value, True), add="+")
            button.bind("<Leave>", lambda _event, value=preset: self.on_preset_popup_button_hover(value, False), add="+")
            self.preset_popup_buttons[preset] = button
        next_row = len(CONFIG_PRESET_NAMES)
        if can_copy_to_current:
            tk.Frame(body, bg="#27313a", height=1).grid(row=next_row, column=0, sticky="ew", pady=(ui_px(4), ui_px(7)))
            next_row += 1
            self.preset_copy_button = tk.Button(
                body,
                text="Copy preset",
                command=self.enter_preset_copy_mode,
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#58a6ff",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#53606c",
                highlightcolor="#58a6ff",
                overrelief="raised",
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="center",
                padx=ui_px(8),
                pady=ui_px(4),
            )
            self.preset_copy_button.grid(row=next_row, column=0, sticky="ew")
        body.grid_columnconfigure(0, weight=1)
        self.preset_popup = popup
        self.update_preset_popup_button_styles()
        self.bind_popup_hover_autoclose(popup, self.close_preset_popup)
        popup.focus_force()

    def close_preset_popup(self) -> None:
        popup = self.preset_popup
        self.preset_popup = None
        self.preset_popup_buttons = {}
        self.preset_copy_button = None
        self.preset_copy_mode = False
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass

    def on_preset_popup_button_clicked(self, preset: str) -> None:
        if self.preset_copy_mode:
            self.copy_config_preset_to_current_user(preset)
            return
        self.select_config_preset(preset)

    def enter_preset_copy_mode(self) -> None:
        current = normalized_config_preset_name(self.current_preset_name.get())
        if current not in ("User 1", "User 2"):
            self.value_text.set("Copy preset is available only while User 1 or User 2 is selected.")
            return
        self.preset_copy_mode = True
        if self.preset_copy_button is not None:
            self.preset_copy_button.configure(
                text="Select source preset",
                bg="#1d2a3a",
                fg="#58a6ff",
                activeforeground="#101316",
                activebackground="#58a6ff",
                highlightbackground="#2f81f7",
            )
        self.update_preset_popup_button_styles()
        self.value_text.set(f"Copy mode: choose a source preset to copy into {current}.")

    def on_preset_popup_button_hover(self, preset: str, hovered: bool) -> None:
        if not self.preset_copy_mode:
            return
        current = normalized_config_preset_name(self.current_preset_name.get())
        button = self.preset_popup_buttons.get(preset)
        if button is None:
            return
        if hovered and preset != current:
            button.configure(
                bg="#2f81f7",
                fg="#eef6ff",
                activebackground="#58a6ff",
                activeforeground="#101316",
                highlightbackground="#58a6ff",
            )
            return
        self.update_preset_popup_button_style(preset, button)

    def update_preset_popup_button_styles(self) -> None:
        for preset, button in self.preset_popup_buttons.items():
            self.update_preset_popup_button_style(preset, button)

    def update_preset_popup_button_style(self, preset: str, button: tk.Button) -> None:
        current = normalized_config_preset_name(self.current_preset_name.get())
        selected = preset == current
        if self.preset_copy_mode and selected:
            button.configure(
                bg="#8a7520",
                fg="#f1d989",
                activebackground="#8a7520",
                activeforeground="#f1d989",
                highlightbackground="#6f632d",
            )
        elif selected:
            button.configure(
                bg="#303946",
                fg="#d6dde5",
                activebackground="#364251",
                activeforeground="#d6dde5",
                highlightbackground="#53606c",
            )
        else:
            button.configure(
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
                highlightbackground="#53606c",
            )

    def copy_config_preset_to_current_user(self, source_preset: str) -> None:
        source_preset = normalized_config_preset_name(source_preset)
        target_preset = normalized_config_preset_name(self.current_preset_name.get())
        if target_preset not in ("User 1", "User 2"):
            self.value_text.set("Copy target must be User 1 or User 2.")
            self.close_preset_popup()
            return
        if source_preset == target_preset:
            self.value_text.set("Choose a different source preset to copy.")
            self.update_preset_popup_button_styles()
            return
        data = self.load_config_preset_data(source_preset)
        if not isinstance(data, dict):
            self.value_text.set(f"Copy failed: {source_preset} preset has no saved data.")
            return
        for key in CONFIG_PRESET_SETTING_KEYS:
            if key in data:
                self.settings[key] = json.loads(json.dumps(data[key]))
        self.settings["current_preset"] = target_preset
        self.current_preset_name.set(target_preset)
        try:
            self.write_config_preset_data(target_preset, self.config_preset_snapshot())
            self.apply_loaded_settings_to_controls()
            save_settings(self.settings, make_backup=True, force=True)
            self.update_save_button_state()
            self.close_preset_popup()
            self.value_text.set(f"Copied {source_preset} preset into {target_preset}.")
        except OSError as exc:
            self.value_text.set(f"Preset copy failed: {exc}")

    def show_save_preset_popup(self) -> None:
        if self.save_preset_popup is not None:
            self.close_save_preset_popup()
            return
        width = ui_px(184)
        height = ui_px(36 * len(CONFIG_PRESET_NAMES) + 48)
        preferred_x = None
        preferred_y = None
        if hasattr(self, "save_settings_button"):
            try:
                preferred_x = self.save_settings_button.winfo_rootx() - ui_px(70)
                preferred_y = self.save_settings_button.winfo_rooty() + self.save_settings_button.winfo_height() + ui_px(4)
            except tk.TclError:
                preferred_x = None
                preferred_y = None
        x, y = self.popup_position_near_root(width, height, preferred_x=preferred_x, preferred_y=preferred_y)
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        popup.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(popup, bg="#171b20")
        body.pack(fill="both", expand=True, padx=ui_px(7), pady=ui_px(7))
        tk.Label(
            body,
            text="Save Current Effect Settings To",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", pady=(0, ui_px(6)))
        current = normalized_config_preset_name(self.current_preset_name.get())
        for row, preset in enumerate(CONFIG_PRESET_NAMES, start=1):
            selected = preset == current
            tk.Button(
                body,
                text=preset,
                command=lambda value=preset: self.save_settings_to_config_preset(value),
                bg="#f1c40f" if selected else "#252c35",
                fg="#101316" if selected else "#d6dde5",
                activebackground="#f7dc6f" if selected else "#303946",
                activeforeground="#101316" if selected else "#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#8a7a2a" if selected else "#53606c",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="w",
                padx=ui_px(8),
                pady=ui_px(4),
            ).grid(row=row, column=0, sticky="ew", pady=(0, ui_px(3)))
        body.grid_columnconfigure(0, weight=1)
        self.save_preset_popup = popup
        popup.bind("<Escape>", lambda _event: self.close_save_preset_popup())
        self.bind_popup_hover_autoclose(popup, self.close_save_preset_popup)
        popup.focus_force()

    def close_save_preset_popup(self) -> None:
        popup = self.save_preset_popup
        self.save_preset_popup = None
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass

    def config_preset_effects_locked(self) -> bool:
        preset = normalized_config_preset_name(self.current_preset_name.get())
        return CONFIG_LOCK_REFERENCE_PRESETS and preset in CONFIG_REFERENCE_PRESET_NAMES

    def haptic_audio_device_configured(self) -> bool:
        return bool(self.haptic_audio_device_text.get().strip())

    def haptic_effects_locked(self) -> bool:
        return self.config_preset_effects_locked() or not self.haptic_audio_device_configured()

    def locked_preset_message(self) -> str:
        return "Editable in User presets only"

    def haptic_lock_message(self) -> str:
        if not self.haptic_audio_device_configured():
            return "Select DualSense audio device first"
        return self.locked_preset_message()

    def create_preset_lock_overlay(self, parent: tk.Widget) -> tk.Frame:
        overlay = tk.Frame(
            parent,
            bg="#202732",
            highlightthickness=1,
            highlightbackground="#66717e",
            highlightcolor="#66717e",
        )
        message_label = tk.Label(
            overlay,
            text=self.locked_preset_message(),
            bg="#202732",
            fg="#c6d0db",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="center",
            justify="center",
        )
        message_label.pack(padx=ui_px(18), pady=ui_px(10))
        overlay.message_label = message_label
        return overlay

    @staticmethod
    def set_preset_lock_overlay_visible(overlay: tk.Frame | None, visible: bool) -> None:
        if overlay is None:
            return
        if visible:
            overlay.place(relx=0.5, rely=0.5, anchor="center")
            overlay.lift()
        else:
            overlay.place_forget()

    @staticmethod
    def set_preset_lock_overlay_message(overlay: tk.Frame | None, message: str) -> None:
        if overlay is None:
            return
        label = getattr(overlay, "message_label", None)
        if label is not None:
            try:
                label.configure(text=message)
            except tk.TclError:
                pass

    def select_config_preset(self, preset: str) -> None:
        preset = normalized_config_preset_name(preset)
        self.current_preset_name.set(preset)
        self.settings["current_preset"] = preset
        loaded = self.load_config_preset(preset)
        self.update_preset_lock_state()
        save_settings(self.settings, force=True)
        self.update_save_button_state()
        self.close_preset_popup()
        self.value_text.set(f"Effect preset loaded: {preset}" if loaded else f"Effect preset selected: {preset}")

    @staticmethod
    def config_preset_file_name(preset: str) -> str:
        safe_name = normalized_config_preset_name(preset).lower().replace(" ", "_")
        return f"{safe_name}.json"

    def config_preset_path(self, preset: str) -> Path:
        return CONFIG_PRESET_DIR / self.config_preset_file_name(preset)

    def packaged_config_preset_path(self, preset: str) -> Path | None:
        file_name = self.config_preset_file_name(preset)
        for path in packaged_file_candidates("config_presets", file_name):
            if path.exists():
                return path
        return None

    def load_config_preset_data(self, preset: str) -> dict | None:
        path = self.config_preset_path(preset)
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(data, dict):
                return data
        except (OSError, json.JSONDecodeError):
            pass

        packaged_path = self.packaged_config_preset_path(preset)
        if packaged_path is not None:
            try:
                data = json.loads(packaged_path.read_text(encoding="utf-8-sig"))
                if isinstance(data, dict):
                    return data
            except (OSError, json.JSONDecodeError):
                pass

        legacy_presets = self.settings.get("config_presets")
        if isinstance(legacy_presets, dict):
            legacy_data = legacy_presets.get(preset)
            if isinstance(legacy_data, dict):
                try:
                    self.write_config_preset_data(preset, legacy_data)
                except OSError:
                    pass
                return legacy_data
        return None

    def write_config_preset_data(self, preset: str, data: dict) -> Path:
        CONFIG_PRESET_DIR.mkdir(parents=True, exist_ok=True)
        path = self.config_preset_path(preset)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        self.settings.pop("config_presets", None)
        return path

    def config_preset_snapshot(self) -> dict:
        snapshot: dict = {}
        for key in CONFIG_PRESET_SETTING_KEYS:
            if key in self.settings:
                snapshot[key] = json.loads(json.dumps(self.settings[key]))
        return snapshot

    def sync_effect_trigger_settings_from_controls(self, mark_dirty: bool = False) -> None:
        if hasattr(self, "effect_controls"):
            self.save_effect_settings(mark_dirty=mark_dirty)
        if hasattr(self, "trigger_controls"):
            self.save_trigger_settings(mark_dirty=mark_dirty)

    def load_startup_config_preset(self) -> None:
        preset = normalized_config_preset_name(self.current_preset_name.get())
        data = self.load_config_preset_data(preset)
        if isinstance(data, dict):
            for key in CONFIG_PRESET_SETTING_KEYS:
                if key in data:
                    self.settings[key] = json.loads(json.dumps(data[key]))
            self.settings["current_preset"] = preset
            return
        if any(key in self.settings for key in CONFIG_PRESET_SETTING_KEYS):
            try:
                self.write_config_preset_data(preset, self.config_preset_snapshot())
            except OSError:
                pass

    def save_current_config_preset(self, preset: str | None = None) -> str:
        preset = normalized_config_preset_name(preset if preset is not None else self.current_preset_name.get())
        self.sync_effect_trigger_settings_from_controls(mark_dirty=False)
        self.current_preset_name.set(preset)
        self.settings["current_preset"] = preset
        self.write_config_preset_data(preset, self.config_preset_snapshot())
        return preset

    def save_settings_to_config_preset(self, preset: str) -> None:
        preset = normalized_config_preset_name(preset)
        if CONFIG_LOCK_REFERENCE_PRESETS and preset in CONFIG_REFERENCE_PRESET_NAMES:
            self.close_save_preset_popup()
            save_settings(self.settings, make_backup=True, force=True)
            self.update_save_button_state()
            self.value_text.set(f"Common UI settings saved. {preset} effect preset is locked.")
            return
        try:
            saved_preset = self.save_current_config_preset(preset)
            save_settings(self.settings, make_backup=True, force=True)
            self.update_save_button_state()
            self.close_save_preset_popup()
            self.value_text.set(f"Effect preset saved: {saved_preset}. Backup: {SETTINGS_BACKUP_PATH.name}")
        except OSError as exc:
            self.value_text.set(f"Settings save failed: {exc}")

    def load_config_preset(self, preset: str) -> bool:
        data = self.load_config_preset_data(preset)
        if not isinstance(data, dict):
            return False
        for key in CONFIG_PRESET_SETTING_KEYS:
            if key in data:
                self.settings[key] = json.loads(json.dumps(data[key]))
        self.settings["current_preset"] = preset
        self.apply_loaded_settings_to_controls()
        return True

    def adjust_hud_scale(self, direction: int) -> None:
        current = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        index = HUD_SCALE_PRESETS.index(current)
        next_index = max(0, min(len(HUD_SCALE_PRESETS) - 1, index + (1 if direction > 0 else -1)))
        percent = HUD_SCALE_PRESETS[next_index]
        if percent == current:
            self.update_scale_texts()
            return
        self.set_hud_scale(percent)

    def set_hud_scale(self, percent: int) -> None:
        old_percent = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        percent = self.normalized_hud_scale_percent(percent)
        if percent == old_percent:
            self.update_scale_texts()
            return
        self.save_current_hud_geometries(old_percent)
        self.hud_scale_percent.set(percent)
        self.settings["hud_scale_percent"] = percent
        self.apply_scale_globals()
        self.scale_hud_geometries(old_percent, percent)
        save_settings(self.settings, force=True)
        self.update_save_button_state()
        self.value_text.set(f"HUD Scale applied: {percent}%")

    def scale_hud_geometries(self, old_percent: int, new_percent: int) -> None:
        if old_percent <= 0 or new_percent <= 0 or old_percent == new_percent:
            return
        ratio = float(new_percent) / float(old_percent)
        for key, default_geometry, hud, min_width, min_height in self.hud_geometry_specs():
            target_geometry = self.saved_hud_geometry_for_scale(key, default_geometry, new_percent)
            if hud is not None and self.hud_window_exists(hud):
                current_geometry = self.normalized_hud_geometry_for_scale(key, default_geometry, hud.geometry(), old_percent)
                if target_geometry is None:
                    target_geometry = self.scaled_hud_geometry(current_geometry, ratio, min_width, min_height)
                hud.geometry(target_geometry)
                try:
                    hud.update_idletasks()
                except tk.TclError:
                    pass
                self.set_hud_geometry(key, target_geometry, new_percent)
            else:
                if target_geometry is None:
                    current_geometry = self.normalized_hud_geometry_for_scale(
                        key,
                        default_geometry,
                        self.get_hud_geometry(key, default_geometry, old_percent),
                        old_percent,
                    )
                    target_geometry = self.scaled_hud_geometry(current_geometry, ratio, min_width, min_height)
                self.set_hud_geometry(key, target_geometry, new_percent)
        self.schedule_hud_redraw_after_scale()

    def hud_geometry_specs(self) -> tuple[tuple[str, str, tk.Toplevel | None, int, int], ...]:
        return (
            ("pedal_hud_geometry", "54x160+80+120", self.hud_window, 36, 90),
            ("gforce_hud_geometry", "160x160+150+120", self.gforce_hud_window, 90, 90),
            ("tire_hud_geometry", "112x160+320+120", self.tire_hud_window, 80, 120),
            ("steer_hud_geometry", "68x160+450+120", self.steer_hud_window, 48, 120),
            ("rpm_hud_geometry", "160x160+540+120", self.rpm_hud_window, 90, 90),
            ("engine_hud_geometry", "76x160+720+120", self.engine_hud_window, 76, 160),
        )

    def hud_display_move_specs(self) -> dict[str, tuple[str, str, str, tk.Toplevel | None, int, int]]:
        return {
            "pedal": ("Pedal", "pedal_hud_geometry", "54x160+80+120", self.hud_window, 36, 90),
            "gforce": ("G-force", "gforce_hud_geometry", "160x160+150+120", self.gforce_hud_window, 90, 90),
            "tire": ("Tire", "tire_hud_geometry", "112x160+320+120", self.tire_hud_window, 80, 120),
            "steer": ("Steer", "steer_hud_geometry", "68x160+450+120", self.steer_hud_window, 48, 120),
            "rpm": ("RPM", "rpm_hud_geometry", "160x160+540+120", self.rpm_hud_window, 90, 90),
            "engine": ("Engine", "engine_hud_geometry", "76x160+720+120", self.engine_hud_window, 76, 160),
            "drift": ("Drift", "drift_debug_hud_geometry", "360x236+1040+120", self.drift_debug_hud_window, 330, 220),
        }

    def hud_geometry_key(self, key: str, percent: int | None = None) -> str:
        if percent is None:
            percent = self.hud_scale_percent.get()
        return f"{key}_{self.normalized_hud_scale_percent(percent)}"

    def hud_reference_geometry(self, default_geometry: str, percent: int | None = None) -> str:
        if percent is None:
            percent = self.hud_scale_percent.get()
        ratio = self.normalized_hud_scale_percent(percent) / 100.0
        return self.scaled_hud_geometry(default_geometry, ratio, 1, 1)

    @staticmethod
    def geometry_with_reference_size(geometry: str, reference: str) -> str:
        geometry_match = re.match(r"^\d+x\d+([+-]\d+[+-]\d+)$", geometry)
        reference_match = re.match(r"^(\d+)x(\d+)[+-]\d+[+-]\d+$", reference)
        if not geometry_match or not reference_match:
            return reference
        return f"{reference_match.group(1)}x{reference_match.group(2)}{geometry_match.group(1)}"

    def normalized_hud_geometry_for_scale(
        self,
        key: str,
        default_geometry: str,
        geometry: object,
        percent: int | None = None,
    ) -> str:
        normalized_percent = self.normalized_hud_scale_percent(
            self.hud_scale_percent.get() if percent is None else percent
        )
        reference = self.hud_reference_geometry(default_geometry, normalized_percent)
        candidate = valid_geometry(geometry)
        if candidate is None:
            return reference
        if geometry_size_compatible(candidate, reference):
            return candidate
        return self.geometry_with_reference_size(candidate, reference)

    def hud_default_geometry_for_key(self, key: str) -> str | None:
        for spec_key, default_geometry, _hud, _min_width, _min_height in self.hud_geometry_specs():
            if spec_key == key:
                return default_geometry
        return None

    def saved_hud_geometry_for_scale(self, key: str, default_geometry: str, percent: int | None = None) -> str | None:
        scaled = valid_geometry(self.settings.get(self.hud_geometry_key(key, percent)))
        if scaled is not None:
            return self.normalized_hud_geometry_for_scale(key, default_geometry, scaled, percent)
        return None

    def get_hud_geometry(self, key: str, default_geometry: str, percent: int | None = None) -> str:
        if percent is None:
            percent = self.hud_scale_percent.get()
        normalized_percent = self.normalized_hud_scale_percent(percent)
        reference = self.hud_reference_geometry(default_geometry, normalized_percent)
        scaled = self.saved_hud_geometry_for_scale(key, default_geometry, normalized_percent)
        if scaled is not None:
            return scaled
        legacy = valid_geometry(self.settings.get(key))
        if normalized_percent == 100 and legacy is not None:
            return self.normalized_hud_geometry_for_scale(key, default_geometry, legacy, normalized_percent)
        return reference

    def set_hud_geometry(self, key: str, geometry: str, percent: int | None = None) -> None:
        geometry = valid_geometry(geometry) or geometry
        if percent is None:
            percent = self.hud_scale_percent.get()
        normalized_percent = self.normalized_hud_scale_percent(percent)
        default_geometry = self.hud_default_geometry_for_key(key)
        if default_geometry is not None:
            geometry = self.normalized_hud_geometry_for_scale(key, default_geometry, geometry, normalized_percent)
        self.settings[self.hud_geometry_key(key, normalized_percent)] = geometry
        if normalized_percent == 100:
            self.settings[key] = geometry

    def save_current_hud_geometries(self, percent: int | None = None) -> None:
        for key, _default_geometry, hud, _min_width, _min_height in self.hud_geometry_specs():
            if hud is not None and self.hud_window_exists(hud):
                self.set_hud_geometry(key, hud.geometry(), percent)

    @staticmethod
    def moved_geometry_to_next_work_area(
        geometry: str,
        work_areas: list[tuple[int, int, int, int]],
        min_width: int,
        min_height: int,
    ) -> tuple[str, int, int] | None:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry)
        if not match or len(work_areas) < 2:
            return None
        width = max(min_width, int(match.group(1)))
        height = max(min_height, int(match.group(2)))
        win_x = int(match.group(3))
        win_y = int(match.group(4))
        center_x = win_x + width / 2.0
        center_y = win_y + height / 2.0

        def contains(area: tuple[int, int, int, int]) -> bool:
            left, top, right, bottom = area
            return left <= center_x < right and top <= center_y < bottom

        current_index = next((idx for idx, area in enumerate(work_areas) if contains(area)), -1)
        if current_index < 0:
            def distance(area: tuple[int, int, int, int]) -> float:
                left, top, right, bottom = area
                area_x = (left + right) / 2.0
                area_y = (top + bottom) / 2.0
                return (area_x - center_x) ** 2 + (area_y - center_y) ** 2

            current_index = min(range(len(work_areas)), key=lambda idx: distance(work_areas[idx]))

        current_area = work_areas[current_index]
        target_index = (current_index + 1) % len(work_areas)
        target_area = work_areas[target_index]
        cur_left, cur_top, cur_right, cur_bottom = current_area
        tgt_left, tgt_top, tgt_right, tgt_bottom = target_area
        cur_span_x = max(1, cur_right - cur_left - width)
        cur_span_y = max(1, cur_bottom - cur_top - height)
        x_ratio = max(0.0, min(1.0, (win_x - cur_left) / cur_span_x))
        y_ratio = max(0.0, min(1.0, (win_y - cur_top) / cur_span_y))
        tgt_span_x = max(0, tgt_right - tgt_left - width)
        tgt_span_y = max(0, tgt_bottom - tgt_top - height)
        new_x = int(round(tgt_left + tgt_span_x * x_ratio))
        new_y = int(round(tgt_top + tgt_span_y * y_ratio))
        new_x = max(tgt_left, min(new_x, max(tgt_left, tgt_right - width)))
        new_y = max(tgt_top, min(new_y, max(tgt_top, tgt_bottom - height)))
        return f"{width}x{height}{new_x:+d}{new_y:+d}", current_index, target_index

    @staticmethod
    def scaled_hud_geometry(geometry: str, ratio: float, min_width: int, min_height: int) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)$", geometry)
        if not match:
            return geometry
        width = max(min_width, int(round(int(match.group(1)) * ratio)))
        height = max(min_height, int(round(int(match.group(2)) * ratio)))
        return f"{width}x{height}{match.group(3)}"

    @staticmethod
    def scaled_hud_reset_geometry(geometry: str, ratio: float, min_width: int, min_height: int) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+)([+-]\d+)$", geometry)
        if not match:
            return geometry
        width = max(min_width, int(round(int(match.group(1)) * ratio)))
        height = max(min_height, int(round(int(match.group(2)) * ratio)))
        x = int(round(int(match.group(3)) * ratio))
        y = int(round(int(match.group(4)) * ratio))
        return f"{width}x{height}{x:+d}{y:+d}"

    def engine_hud_min_size(self, percent: int | None = None) -> tuple[int, int]:
        if percent is None:
            percent = self.hud_scale_percent.get()
        ratio = self.normalized_hud_scale_percent(percent) / 100.0
        return max(76, int(round(76 * ratio))), max(160, int(round(160 * ratio)))

    def normalized_engine_hud_geometry(self, geometry: str, percent: int | None = None) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)$", geometry)
        if not match:
            return geometry
        min_width, min_height = self.engine_hud_min_size(percent)
        width = max(min_width, int(match.group(1)))
        height = max(min_height, int(match.group(2)))
        return f"{width}x{height}{match.group(3)}"

    def draw_all_huds(self) -> None:
        self.draw_hud()
        self.draw_gforce_hud()
        self.draw_tire_hud()
        self.draw_steer_hud()
        self.draw_applied_steer_hud()
        self.draw_rpm_hud()
        self.draw_engine_hud()

    def settle_hud_windows_after_scale(self) -> None:
        for _key, _default_geometry, hud, _min_width, _min_height in self.hud_geometry_specs():
            if hud is not None and self.hud_window_exists(hud):
                try:
                    hud.update_idletasks()
                except tk.TclError:
                    pass
        self.draw_all_huds()

    def schedule_hud_redraw_after_scale(self) -> None:
        try:
            if self.rpm_hud_window is not None and self.rpm_hud_window.winfo_exists():
                self.rpm_hud_needle_angles.clear()
                self.rpm_hud_display_rpm = None
                self.rpm_hud_zero_dropouts = 0
            self.root.after_idle(self.settle_hud_windows_after_scale)
            self.root.after(80, self.settle_hud_windows_after_scale)
            self.root.after(180, self.settle_hud_windows_after_scale)
            self.root.after(360, self.settle_hud_windows_after_scale)
        except tk.TclError:
            pass

    def adjust_main_ui_scale(self, direction: int) -> None:
        current = self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get())
        index = MAIN_UI_SCALE_PRESETS.index(current)
        next_index = max(0, min(len(MAIN_UI_SCALE_PRESETS) - 1, index + (1 if direction > 0 else -1)))
        self.set_main_ui_scale(MAIN_UI_SCALE_PRESETS[next_index])

    def adjust_display_scale(self, direction: int) -> None:
        current = self.normalized_display_scale_percent(self.display_scale_percent.get())
        index = DISPLAY_SCALE_PRESETS.index(current)
        next_index = max(0, min(len(DISPLAY_SCALE_PRESETS) - 1, index + (1 if direction > 0 else -1)))
        self.set_display_scale(DISPLAY_SCALE_PRESETS[next_index])

    def set_main_ui_scale(self, percent: int) -> None:
        percent = self.normalized_main_ui_scale_percent(percent)
        current = self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get())
        if percent == current:
            self.update_scale_texts()
            return
        accepted = messagebox.askokcancel(
            "UI Scale",
            f"UI Scale {percent}% 적용을 위해 프로그램이 잠시 닫혔다가 재실행됩니다.\n동의합니까?",
            parent=self.root,
        )
        if not accepted:
            self.update_scale_texts()
            return
        self.main_ui_scale_percent.set(percent)
        self.settings["main_ui_scale_percent"] = percent
        self.settings["window_geometry"] = base_window_geometry(self.root.geometry(), percent)
        save_settings(self.settings, force=True)
        self.update_scale_texts()
        self.update_save_button_state()
        self.value_text.set("Main UI Scale preset saved. Restarting...")
        self.root.after(150, lambda selected_percent=percent: self.restart_for_main_ui_scale(selected_percent))

    def relaunch_command(self) -> list[str]:
        return [
            sys.executable,
            "--host",
            str(self.launch_host),
            "--port",
            str(self.launch_port),
            "--haptic-event-port",
            str(self.launch_haptic_event_port),
        ]

    def relaunch_cwd(self) -> Path:
        if running_frozen():
            return executable_dir()
        return Path(__file__).resolve().parent

    def restart_for_main_ui_scale(self, percent: int) -> None:
        percent = self.normalized_main_ui_scale_percent(percent)
        self.main_ui_scale_percent.set(percent)
        self.save_window_state()
        self.settings["main_ui_scale_percent"] = percent
        self.settings["window_geometry"] = base_window_geometry(self.root.geometry(), percent)
        save_settings(self.settings, make_backup=True, force=True)
        self.shutdown_runtime()
        time.sleep(0.25)
        subprocess.Popen(
            self.relaunch_command(),
            cwd=str(self.relaunch_cwd()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        self.root.destroy()

    def set_display_scale(self, percent: int) -> None:
        percent = self.normalized_display_scale_percent(percent)
        current = self.normalized_display_scale_percent(self.display_scale_percent.get())
        if percent == current:
            self.update_scale_texts()
            return
        parent = self.options_window if self.options_window is not None else self.root
        accepted = messagebox.askokcancel(
            "Display Scale",
            f"Display Scale {percent}% 적용을 위해 프로그램이 잠시 닫혔다가 재실행됩니다.\n동의합니까?",
            parent=parent,
        )
        if not accepted:
            self.update_scale_texts()
            return
        self.save_window_state()
        self.display_scale_percent.set(percent)
        self.settings["display_scale_percent"] = percent
        self.settings["window_geometry"] = base_window_geometry(self.root.geometry(), self.main_ui_scale_percent.get())
        save_settings(self.settings, force=True)
        self.update_scale_texts()
        self.update_save_button_state()
        self.value_text.set("Display Scale preset saved. Restarting...")
        self.root.after(150, lambda selected_percent=percent: self.restart_for_display_scale(selected_percent))

    def set_auto_display_scale(self) -> None:
        percent = recommended_display_scale_value()
        current = self.normalized_display_scale_percent(self.display_scale_percent.get())
        if percent == current:
            self.update_scale_texts()
            self.value_text.set(f"Display Scale already matches Auto {percent}% from Windows {detect_windows_dpi_percent()}%.")
            return
        self.set_display_scale(percent)

    def restart_for_display_scale(self, percent: int) -> None:
        percent = self.normalized_display_scale_percent(percent)
        self.display_scale_percent.set(percent)
        self.settings["display_scale_percent"] = percent
        self.settings["window_geometry"] = base_window_geometry(self.root.geometry(), self.main_ui_scale_percent.get())
        save_settings(self.settings, make_backup=True, force=True)
        self.shutdown_runtime()
        time.sleep(0.25)
        subprocess.Popen(
            self.relaunch_command(),
            cwd=str(self.relaunch_cwd()),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
        )
        self.root.destroy()

    def schedule_layout_update(self, key: str, callback, delay_ms: int = 70) -> None:
        after_id = self.layout_after_ids.pop(key, None)
        if after_id is not None:
            try:
                self.root.after_cancel(after_id)
            except tk.TclError:
                pass

        def run_callback() -> None:
            self.layout_after_ids.pop(key, None)
            callback()

        self.layout_after_ids[key] = self.root.after(delay_ms, run_callback)

    def toggle_window_resize(self) -> None:
        self.window_resize_unlocked.set(not bool(self.window_resize_unlocked.get()))
        self.settings["window_resize_unlocked"] = bool(self.window_resize_unlocked.get())
        save_settings(self.settings)
        self.apply_window_resize_state()

    def apply_window_resize_state(self) -> None:
        unlocked = bool(self.window_resize_unlocked.get())
        if unlocked:
            self.root.minsize(980, 560)
            self.root.maxsize(self.root.winfo_screenwidth(), self.root.winfo_screenheight())
        else:
            window_width, window_height = main_ui_window_size(self.main_ui_scale_percent.get())
            self.root.geometry(base_window_geometry(self.root.geometry(), self.main_ui_scale_percent.get()))
            self.root.minsize(window_width, window_height)
            self.root.maxsize(window_width, window_height)
        self.root.resizable(unlocked, unlocked)
        self.update_window_resize_button()

    def update_window_resize_button(self) -> None:
        if not hasattr(self, "window_resize_button"):
            return
        unlocked = bool(self.window_resize_unlocked.get())
        self.window_resize_button.configure(
            text="Resize ON" if unlocked else "Resize",
            bg="#f1c40f" if unlocked else "#252c35",
            fg="#101316" if unlocked else "#d6dde5",
            activebackground="#f7dc6f" if unlocked else "#303946",
            activeforeground="#101316" if unlocked else "#f1c40f",
        )

    def on_value_frame_configure(self, event) -> None:
        self.pending_value_frame_width = event.width
        self.schedule_layout_update("value_frame", self.apply_value_frame_wraplength)

    def apply_value_frame_wraplength(self) -> None:
        width = self.pending_value_frame_width
        button_width = 0
        if hasattr(self, "log_rec_button"):
            try:
                button_width = self.log_rec_button.winfo_reqwidth() + 32
            except tk.TclError:
                button_width = 0
        wrap_width = max(260, width - button_width - 34)
        if hasattr(self, "value_debug_label"):
            self.value_debug_label.configure(wraplength=wrap_width)
        if hasattr(self, "value_label"):
            self.value_label.configure(wraplength=wrap_width)
        if hasattr(self, "status_label"):
            self.status_label.configure(wraplength=wrap_width)

    def show_hud_settings_popup(self) -> None:
        if self.hud_settings_popup is not None:
            try:
                if self.hud_settings_popup.winfo_exists():
                    self.hud_settings_popup.destroy()
            except tk.TclError:
                pass
            self.hud_settings_popup = None
            return

        self.close_hud_scale_popups(except_attr="hud_settings_popup")
        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        width = ui_px(220)
        height = ui_px(410)
        x = self.root.winfo_rootx() + ui_px(190)
        y = self.root.winfo_rooty() + ui_px(44)
        x, y = self.popup_position_near_root(width, height, preferred_x=x, preferred_y=y)
        popup.geometry(f"{width}x{height}+{x}+{y}")

        body = tk.Frame(popup, bg="#171b20")
        body.pack(fill="both", expand=True, padx=ui_px(10), pady=ui_px(10))
        tk.Label(
            body,
            text="HUD Settings",
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, ui_px(8)))
        tk.Button(
            body,
            text="HUD Location Reset",
            command=self.reset_hud_locations,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            overrelief="raised",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=ui_px(8),
            pady=ui_px(4),
        ).pack(fill="x", pady=(0, ui_px(8)))
        snap_row = tk.Frame(body, bg="#171b20")
        snap_row.pack(fill="x", pady=(0, ui_px(8)))
        self.hud_snap_button = tk.Button(
            snap_row,
            command=self.toggle_hud_snap,
            relief="raised",
            bd=1,
            highlightthickness=1,
            overrelief="raised",
            font=ui_font("Segoe UI", 7, "bold"),
            padx=ui_px(5),
            pady=ui_px(3),
        )
        self.hud_snap_button.grid(row=0, column=0, sticky="w")
        tk.Label(
            snap_row,
            text="Snap Pixel",
            bg="#171b20",
            fg="#8b96a3",
            font=ui_font("Segoe UI", 7, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(ui_px(5), ui_px(3)))
        validate_digits = (self.root.register(self.validate_hud_snap_pixel_text), "%P")
        self.hud_snap_pixel_entry = tk.Entry(
            snap_row,
            textvariable=self.hud_snap_pixel_text,
            width=4,
            bg="#101316",
            fg="#f1c40f",
            insertbackground="#f1c40f",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#53606c",
            highlightcolor="#f1c40f",
            font=value_font("Consolas", 8, "bold"),
            justify="right",
            validate="key",
            validatecommand=validate_digits,
        )
        self.hud_snap_pixel_entry.grid(row=0, column=2, sticky="w")
        self.hud_snap_pixel_entry.bind("<Return>", lambda _event: self.apply_hud_snap_pixel_text())
        self.hud_snap_pixel_entry.bind("<FocusOut>", lambda _event: self.apply_hud_snap_pixel_text())
        for column, text, delta in ((3, "-", -1), (4, "+", 1)):
            tk.Button(
                snap_row,
                text=text,
                command=lambda value=delta: self.adjust_hud_snap_pixels(value),
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#53606c",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=ui_font("Segoe UI", 7, "bold"),
                width=2,
                padx=0,
                pady=ui_px(3),
            ).grid(row=0, column=column, sticky="w", padx=(ui_px(3), 0))
        self.update_hud_snap_controls()
        tk.Frame(body, bg="#27313a", height=1).pack(fill="x", pady=(0, ui_px(8)))
        tk.Label(
            body,
            text="Active HUD",
            bg="#171b20",
            fg="#8b96a3",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(fill="x", pady=(0, ui_px(5)))

        self.hud_settings_buttons = {}
        for label, command, key in (
            ("Pedal", self.toggle_hud, "pedal"),
            ("G-force", self.toggle_gforce_hud, "gforce"),
            ("Tire", self.toggle_tire_hud, "tire"),
            ("Steer", self.toggle_steer_hud, "steer"),
            ("RPM", self.toggle_rpm_hud, "rpm"),
            ("Engine", self.toggle_engine_hud, "engine"),
            ("Drift", self.toggle_drift_debug_hud, "drift"),
        ):
            row = tk.Frame(body, bg="#171b20")
            row.pack(fill="x", pady=(0, ui_px(3)))
            row.grid_columnconfigure(0, weight=0)
            row.grid_columnconfigure(1, weight=1)
            button = tk.Button(
                row,
                text=label,
                command=command,
                bg="#1b2027",
                fg="#8b96a3",
                activebackground="#303946",
                activeforeground="#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#3b4652",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="w",
                width=8,
                padx=ui_px(5),
                pady=ui_px(3),
            )
            button.grid(row=0, column=0, sticky="w")
            tk.Button(
                row,
                text="Move Display",
                command=lambda hud_key=key: self.move_hud_to_next_display(hud_key),
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#53606c",
                highlightcolor="#f1c40f",
                overrelief="raised",
                font=ui_font("Segoe UI", 7, "bold"),
                padx=ui_px(5),
                pady=ui_px(3),
            ).grid(row=0, column=1, sticky="e", padx=(ui_px(4), 0))
            self.hud_settings_buttons[key] = button

        self.hud_settings_popup = popup
        self.update_hud_settings_popup_buttons()
        self.bind_popup_hover_autoclose(popup, self.close_hud_settings_popup)
        popup.focus_force()

    def close_hud_settings_popup(self) -> None:
        popup = self.hud_settings_popup
        self.hud_settings_popup = None
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass

    def update_hud_settings_popup_buttons(self) -> None:
        buttons = getattr(self, "hud_settings_buttons", None)
        if not buttons:
            return
        states = {
            "pedal": self.hud_window_exists(self.hud_window),
            "gforce": self.hud_window_exists(self.gforce_hud_window),
            "tire": self.hud_window_exists(self.tire_hud_window),
            "steer": self.hud_window_exists(self.steer_hud_window),
            "rpm": self.hud_window_exists(self.rpm_hud_window),
            "engine": self.hud_window_exists(self.engine_hud_window),
            "drift": self.hud_window_exists(self.drift_debug_hud_window),
        }
        for key, button in list(buttons.items()):
            try:
                if not button.winfo_exists():
                    continue
                active = states.get(key, False)
                button.configure(
                    bg="#252c35" if active else "#1b2027",
                    fg="#f1c40f" if active else "#8b96a3",
                    activeforeground="#f1c40f" if active else "#8b96a3",
                )
            except tk.TclError:
                continue

    def validate_hud_snap_pixel_text(self, proposed: str) -> bool:
        return proposed == "" or proposed.isdigit()

    def current_hud_snap_pixels(self) -> int:
        return self.clamp_int(self.hud_snap_pixels.get(), HUD_SNAP_PIXEL_MIN, HUD_SNAP_PIXEL_MAX)

    def update_hud_snap_controls(self) -> None:
        if not hasattr(self, "hud_snap_button"):
            return
        enabled = bool(self.hud_snap_enabled.get())
        try:
            self.hud_snap_button.configure(
                text="Snap HUD ON" if enabled else "Snap HUD OFF",
                bg="#f1c40f" if enabled else "#252c35",
                fg="#101316" if enabled else "#d6dde5",
                activebackground="#f7dc6f" if enabled else "#303946",
                activeforeground="#101316" if enabled else "#f1c40f",
                highlightbackground="#8a7a2a" if enabled else "#53606c",
                highlightcolor="#101316" if enabled else "#f1c40f",
            )
            if hasattr(self, "hud_snap_pixel_entry"):
                self.hud_snap_pixel_entry.configure(fg="#f1c40f" if enabled else "#8b96a3")
        except tk.TclError:
            pass

    def toggle_hud_snap(self) -> None:
        enabled = not bool(self.hud_snap_enabled.get())
        self.hud_snap_enabled.set(enabled)
        self.settings["hud_snap_enabled"] = enabled
        save_settings(self.settings, force=True)
        self.update_hud_snap_controls()
        self.value_text.set(f"Snap HUD {'ON' if enabled else 'OFF'}")

    def set_hud_snap_pixels(self, value: object) -> None:
        pixels = self.clamp_int(value, HUD_SNAP_PIXEL_MIN, HUD_SNAP_PIXEL_MAX)
        self.hud_snap_pixels.set(pixels)
        self.hud_snap_pixel_text.set(str(pixels))
        self.settings["hud_snap_pixels"] = pixels
        save_settings(self.settings, force=True)
        self.value_text.set(f"Snap Pixel: {pixels}px")

    def apply_hud_snap_pixel_text(self) -> None:
        text = self.hud_snap_pixel_text.get().strip()
        self.set_hud_snap_pixels(text if text else self.hud_snap_pixels.get())

    def adjust_hud_snap_pixels(self, delta: int) -> None:
        self.set_hud_snap_pixels(self.current_hud_snap_pixels() + int(delta))

    def move_hud_to_next_display(self, hud_key: str) -> None:
        work_areas = windows_monitor_work_areas()
        if len(work_areas) < 2:
            self.value_text.set("HUD Display skipped: single display detected.")
            return
        specs = self.hud_display_move_specs()
        spec = specs.get(hud_key)
        if spec is None:
            self.value_text.set("HUD Display failed: unknown HUD.")
            return
        label, geometry_key, default_geometry, hud, min_width, min_height = spec
        try:
            if hud is not None and self.hud_window_exists(hud):
                hud.update_idletasks()
                geometry = hud.geometry()
            else:
                geometry = self.get_hud_geometry(geometry_key, default_geometry)
            moved = self.moved_geometry_to_next_work_area(geometry, work_areas, min_width, min_height)
            if moved is None:
                self.value_text.set(f"{label} HUD Display failed: invalid geometry.")
                return
            new_geometry, current_index, target_index = moved
            if geometry_key == "engine_hud_geometry":
                new_geometry = self.normalized_engine_hud_geometry(new_geometry)
            elif geometry_key == "drift_debug_hud_geometry":
                new_geometry = self.normalized_drift_debug_hud_geometry(new_geometry)
            self.set_hud_geometry(geometry_key, new_geometry)
            if hud is not None and self.hud_window_exists(hud):
                hud.geometry(new_geometry)
                hud.update_idletasks()
            save_settings(self.settings, force=True)
            self.update_save_button_state()
            self.value_text.set(f"{label} HUD Display: {current_index + 1} -> {target_index + 1}")
        except tk.TclError as exc:
            self.value_text.set(f"{label} HUD Display failed: {exc}")

    def toggle_hud(self) -> None:
        if self.hud_window is not None and self.hud_window.winfo_exists():
            self.close_hud()
        else:
            self.open_hud()
        self.update_hud_button()
        self.mark_hud_active_settings_changed()

    def open_drift_debug_hud(self) -> None:
        self.close_drift_debug_hud()
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.86)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.normalized_drift_debug_hud_geometry(
            self.get_hud_geometry("drift_debug_hud_geometry", "360x236+1040+120")
        )
        hud.geometry(geometry)
        hud.minsize(330, 220)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_drift_debug_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_drift_debug_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_drift_debug_hud())
        canvas.bind("<ButtonPress-1>", self.on_drift_debug_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_drift_debug_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_drift_debug_hud())
        self.drift_debug_hud_window = hud
        self.drift_debug_hud_canvas = canvas
        self.draw_drift_debug_hud()
        self.update_hud_settings_popup_buttons()

    def close_drift_debug_hud(self) -> None:
        hud = self.drift_debug_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("drift_debug_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.drift_debug_hud_window = None
        self.drift_debug_hud_canvas = None
        self.update_hud_settings_popup_buttons()

    @staticmethod
    def normalized_drift_debug_hud_geometry(geometry: str) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)$", geometry)
        if not match:
            return "360x236+1040+120"
        width = max(330, int(match.group(1)))
        height = max(220, int(match.group(2)))
        return f"{width}x{height}{match.group(3)}"

    def on_drift_debug_hud_drag_start(self, event) -> None:
        self.drift_debug_hud_drag_offset = (
            event.x_root - self.drift_debug_hud_window.winfo_x(),
            event.y_root - self.drift_debug_hud_window.winfo_y(),
        ) if self.drift_debug_hud_window else (0, 0)

    def on_drift_debug_hud_drag_motion(self, event) -> None:
        if self.drift_debug_hud_window is None:
            return
        offset_x, offset_y = self.drift_debug_hud_drag_offset
        self.drift_debug_hud_window.geometry(f"+{int(event.x_root - offset_x)}+{int(event.y_root - offset_y)}")

    def draw_drift_debug_hud(self) -> None:
        canvas = self.drift_debug_hud_canvas
        if canvas is None or self.drift_debug_hud_window is None or not self.drift_debug_hud_window.winfo_exists():
            return
        width = max(330, canvas.winfo_width())
        height = max(220, canvas.winfo_height())
        canvas.delete("all")
        bg = "#10161c"
        line = "#27313a"
        text = "#d6dde5"
        accent = "#f1c40f"
        active = bool(self.drift_mode_active)
        title_color = "#ff33cc" if active else accent
        canvas.create_rectangle(1, 1, width - 2, height - 2, fill=bg, outline=line, width=1)
        title = "DRIFT" if active else "drift monitor"
        canvas.create_text(14, 12, text=title, fill=title_color, font=hud_font("Segoe UI", 17, "bold"), anchor="nw")
        canvas.create_text(
            width - 14,
            13,
            text=f"{self.drift_mode_score:.2f}",
            fill=title_color,
            font=hud_font("Consolas", 18, "bold"),
            anchor="ne",
        )
        y = 54
        self.draw_drift_debug_bar(canvas, 14, y, width - 14, "score", self.drift_mode_score, active)
        y += 27
        components = self.drift_mode_components
        for label, key in (
            ("over", "over"),
            ("angle", "angle"),
            ("drive", "drive"),
            ("wheel", "wheel"),
            ("grip", "grip"),
        ):
            self.draw_drift_debug_bar(canvas, 14, y, width - 14, label, components.get(key, 0.0), False)
            y += 22
        if self.drift_relief_trigger_suppression_active():
            status = "relief R2 OFF"
        elif self.drift_relief_active():
            status = "relief ON"
        elif self.drift_relief_enabled.get():
            status = "relief armed"
        else:
            status = "relief off"
        canvas.create_text(14, height - 14, text=status, fill="#7f8b96", font=hud_font("Segoe UI", 12, "bold"), anchor="sw")

    def draw_drift_debug_bar(self, canvas: tk.Canvas, x0: int, y: int, x1: int, label: str, value: float, hot: bool) -> None:
        value = max(0.0, min(1.0, float(value)))
        label_w = 74
        bar_x0 = x0 + label_w
        bar_h = 11
        fill = "#ff33cc" if hot else "#f1c40f"
        canvas.create_text(x0, y + 6, text=label, fill="#aeb8c4", font=hud_font("Segoe UI", 11, "bold"), anchor="w")
        canvas.create_rectangle(bar_x0, y, x1 - 52, y + bar_h, fill="#252c35", outline="")
        canvas.create_rectangle(bar_x0, y, bar_x0 + (x1 - 52 - bar_x0) * value, y + bar_h, fill=fill, outline="")
        canvas.create_text(x1, y + 6, text=f"{value:.2f}", fill="#d6dde5", font=hud_font("Consolas", 11, "bold"), anchor="e")

    def toggle_gforce_hud(self) -> None:
        if self.gforce_hud_window is not None and self.gforce_hud_window.winfo_exists():
            self.close_gforce_hud()
        else:
            self.open_gforce_hud()
        self.update_hud_gforce_button()
        self.mark_hud_active_settings_changed()

    def toggle_tire_hud(self) -> None:
        if self.tire_hud_window is not None and self.tire_hud_window.winfo_exists():
            self.close_tire_hud()
        else:
            self.open_tire_hud()
        self.update_hud_tire_button()
        self.mark_hud_active_settings_changed()

    def toggle_steer_hud(self) -> None:
        if self.steer_hud_window is not None and self.steer_hud_window.winfo_exists():
            self.close_steer_hud()
        else:
            self.open_steer_hud()
        self.update_hud_steer_button()
        self.mark_hud_active_settings_changed()

    def toggle_applied_steer_hud(self) -> None:
        if self.applied_steer_hud_window is not None and self.applied_steer_hud_window.winfo_exists():
            self.close_applied_steer_hud()
        else:
            self.open_applied_steer_hud()
        self.update_hud_applied_steer_button()
        self.mark_hud_active_settings_changed()

    def toggle_rpm_hud(self) -> None:
        if self.rpm_hud_window is not None and self.rpm_hud_window.winfo_exists():
            self.close_rpm_hud()
        else:
            self.open_rpm_hud()
        self.update_hud_rpm_button()
        self.mark_hud_active_settings_changed()

    def toggle_engine_hud(self) -> None:
        if self.engine_hud_window is not None and self.engine_hud_window.winfo_exists():
            self.close_engine_hud()
        else:
            self.open_engine_hud()
        self.update_hud_engine_button()
        self.mark_hud_active_settings_changed()

    def toggle_drift_debug_hud(self) -> None:
        if self.drift_debug_hud_window is not None and self.drift_debug_hud_window.winfo_exists():
            self.close_drift_debug_hud()
        else:
            self.open_drift_debug_hud()
        self.mark_hud_active_settings_changed()

    def toggle_all_huds(self) -> None:
        all_active = all(
            self.hud_window_exists(hud)
            for hud in (
                self.hud_window,
                self.gforce_hud_window,
                self.tire_hud_window,
                self.steer_hud_window,
                self.rpm_hud_window,
                self.engine_hud_window,
            )
        )
        if all_active:
            self.close_hud()
            self.close_gforce_hud()
            self.close_tire_hud()
            self.close_steer_hud()
            self.close_rpm_hud()
            self.close_engine_hud()
        else:
            if not self.hud_window_exists(self.hud_window):
                self.open_hud()
            if not self.hud_window_exists(self.gforce_hud_window):
                self.open_gforce_hud()
            if not self.hud_window_exists(self.tire_hud_window):
                self.open_tire_hud()
            if not self.hud_window_exists(self.steer_hud_window):
                self.open_steer_hud()
            if not self.hud_window_exists(self.rpm_hud_window):
                self.open_rpm_hud()
            if not self.hud_window_exists(self.engine_hud_window):
                self.open_engine_hud()
            self.update_hud_visibility_for_udp()
        self.update_hud_button()
        self.update_hud_gforce_button()
        self.update_hud_tire_button()
        self.update_hud_steer_button()
        self.update_hud_rpm_button()
        self.update_hud_engine_button()
        self.update_hud_all_button()
        self.mark_hud_active_settings_changed()

    def restore_hud_active_states(self) -> None:
        if bool(self.settings.get("pedal_hud_active", False)):
            self.open_hud()
        if bool(self.settings.get("gforce_hud_active", False)):
            self.open_gforce_hud()
        if bool(self.settings.get("tire_hud_active", False)):
            self.open_tire_hud()
        if bool(self.settings.get("steer_hud_active", False)):
            self.open_steer_hud()
        if bool(self.settings.get("rpm_hud_active", False)):
            self.open_rpm_hud()
        if bool(self.settings.get("engine_hud_active", False)):
            self.open_engine_hud()
        if bool(self.settings.get("drift_debug_hud_active", False)):
            self.open_drift_debug_hud()
        self.update_hud_active_settings()
        self.update_all_hud_buttons()

    def update_hud_active_settings(self) -> None:
        self.settings["pedal_hud_active"] = self.hud_window_exists(self.hud_window)
        self.settings["gforce_hud_active"] = self.hud_window_exists(self.gforce_hud_window)
        self.settings["tire_hud_active"] = self.hud_window_exists(self.tire_hud_window)
        self.settings["steer_hud_active"] = self.hud_window_exists(self.steer_hud_window)
        self.settings["applied_steer_hud_active"] = False
        self.settings["rpm_hud_active"] = self.hud_window_exists(self.rpm_hud_window)
        self.settings["engine_hud_active"] = self.hud_window_exists(self.engine_hud_window)
        self.settings["drift_debug_hud_active"] = self.hud_window_exists(self.drift_debug_hud_window)

    def update_all_hud_buttons(self) -> None:
        self.update_hud_button()
        self.update_hud_gforce_button()
        self.update_hud_tire_button()
        self.update_hud_steer_button()
        self.update_hud_rpm_button()
        self.update_hud_engine_button()
        self.update_hud_all_button()
        self.update_hud_settings_popup_buttons()

    def mark_hud_active_settings_changed(self) -> None:
        self.update_hud_active_settings()
        save_settings(self.settings)
        self.update_all_hud_buttons()

    @staticmethod
    def hud_window_exists(hud: tk.Toplevel | None) -> bool:
        try:
            return hud is not None and bool(hud.winfo_exists())
        except tk.TclError:
            return False

    def update_hud_all_button(self) -> None:
        if not hasattr(self, "hud_all_button"):
            return
        any_active = any(
            self.hud_window_exists(hud)
            for hud in (
                self.hud_window,
                self.gforce_hud_window,
                self.tire_hud_window,
                self.steer_hud_window,
                self.applied_steer_hud_window,
                self.rpm_hud_window,
                self.engine_hud_window,
            )
        )
        self.hud_all_button.configure(
            bg="#252c35" if any_active else "#1b2027",
            fg="#f1c40f" if any_active else "#8b96a3",
            activeforeground="#f1c40f" if any_active else "#8b96a3",
        )

    def on_hud_standby_hide_changed(self) -> None:
        self.settings["hud_standby_hide"] = bool(self.hud_standby_hide_enabled.get())
        save_settings(self.settings)
        self.update_hud_standby_hide_button()
        self.update_hud_visibility_for_udp()

    def update_hud_standby_hide_button(self) -> None:
        if not hasattr(self, "hud_standby_hide_button"):
            return
        active = bool(self.hud_standby_hide_enabled.get())
        self.hud_standby_hide_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )

    def update_hud_rpm_button(self) -> None:
        if not hasattr(self, "hud_rpm_button"):
            return
        active = self.rpm_hud_window is not None and self.rpm_hud_window.winfo_exists()
        self.hud_rpm_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_engine_button(self) -> None:
        if not hasattr(self, "hud_engine_button"):
            return
        active = self.engine_hud_window is not None and self.engine_hud_window.winfo_exists()
        self.hud_engine_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_steer_button(self) -> None:
        if not hasattr(self, "hud_steer_button"):
            return
        active = self.steer_hud_window is not None and self.steer_hud_window.winfo_exists()
        self.hud_steer_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_applied_steer_button(self) -> None:
        if not hasattr(self, "hud_applied_steer_button"):
            return
        active = self.applied_steer_hud_window is not None and self.applied_steer_hud_window.winfo_exists()
        self.hud_applied_steer_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_tire_button(self) -> None:
        if not hasattr(self, "hud_tire_button"):
            return
        active = self.tire_hud_window is not None and self.tire_hud_window.winfo_exists()
        self.hud_tire_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_gforce_button(self) -> None:
        if not hasattr(self, "hud_gforce_button"):
            return
        active = self.gforce_hud_window is not None and self.gforce_hud_window.winfo_exists()
        self.hud_gforce_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def update_hud_button(self) -> None:
        if not hasattr(self, "hud_button"):
            return
        active = self.hud_window is not None and self.hud_window.winfo_exists()
        self.hud_button.configure(
            bg="#252c35" if active else "#1b2027",
            fg="#f1c40f" if active else "#8b96a3",
            activeforeground="#f1c40f" if active else "#8b96a3",
        )
        self.update_hud_all_button()

    def open_hud(self) -> None:
        self.close_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.78)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.get_hud_geometry("pedal_hud_geometry", "54x160+80+120")
        hud.geometry(geometry)
        hud.minsize(36, 90)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_hud())
        canvas.bind("<ButtonPress-1>", self.on_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_hud())
        self.hud_window = hud
        self.hud_canvas = canvas
        self.update_hud_button()
        self.draw_hud()
        self.update_hud_visibility_for_udp()

    def close_hud(self, mark_dirty: bool = True) -> None:
        hud = self.hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("pedal_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.hud_window = None
        self.hud_canvas = None
        self.update_hud_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_hud_drag_start(self, event) -> None:
        self.hud_drag_offset = (event.x_root - self.hud_window.winfo_x(), event.y_root - self.hud_window.winfo_y()) if self.hud_window else (0, 0)

    def on_hud_drag_motion(self, event) -> None:
        if self.hud_window is None:
            return
        offset_x, offset_y = self.hud_drag_offset
        self.move_hud_window_snapped(self.hud_window, event.x_root - offset_x, event.y_root - offset_y)

    def move_hud_window_snapped(self, hud: tk.Toplevel, x: int | float, y: int | float) -> None:
        try:
            width = max(1, hud.winfo_width())
            height = max(1, hud.winfo_height())
        except tk.TclError:
            return
        if bool(self.hud_snap_enabled.get()):
            snap = self.current_hud_snap_pixels()
            snapped_x = int(round(float(x) / snap) * snap)
            snapped_y = int(round(float(y) / snap) * snap)
        else:
            snapped_x = int(round(float(x)))
            snapped_y = int(round(float(y)))
        work_areas = windows_monitor_work_areas()
        if work_areas:
            center_x = snapped_x + width / 2.0
            center_y = snapped_y + height / 2.0

            def distance(area: tuple[int, int, int, int]) -> float:
                left, top, right, bottom = area
                area_x = (left + right) / 2.0
                area_y = (top + bottom) / 2.0
                return (area_x - center_x) ** 2 + (area_y - center_y) ** 2

            area = min(work_areas, key=distance)
            left, top, right, bottom = area
            snapped_x = max(left, min(snapped_x, max(left, right - width)))
            snapped_y = max(top, min(snapped_y, max(top, bottom - height)))
        else:
            try:
                screen_w = hud.winfo_screenwidth()
                screen_h = hud.winfo_screenheight()
            except tk.TclError:
                return
            snapped_x = max(0, min(snapped_x, max(0, screen_w - width)))
            snapped_y = max(0, min(snapped_y, max(0, screen_h - height)))
        hud.geometry(f"+{snapped_x}+{snapped_y}")

    def draw_hud(self) -> None:
        canvas = self.hud_canvas
        if canvas is None or self.hud_window is None or not self.hud_window.winfo_exists():
            return
        width = max(36, canvas.winfo_width())
        height = max(90, canvas.winfo_height())
        canvas.delete("all")
        pad = 0
        gap = 6
        bar_width = max(12, (width - pad * 2 - gap) // 2)
        bar_height = max(70, height)
        top = 0
        bottom = top + bar_height
        brake = max(0.0, min(1.0, float(self.latest_raw.get("brake", 0.0)) / 255.0)) if self.latest_raw else 0.0
        throttle = max(0.0, min(1.0, float(self.latest_raw.get("accel", 0.0)) / 255.0)) if self.latest_raw else 0.0
        recommended_brake = self.hud_recommended_brake(brake)
        recommended_throttle = self.hud_recommended_throttle(throttle)

        brake_x0 = pad
        brake_x1 = brake_x0 + bar_width
        throttle_x0 = brake_x1 + gap
        throttle_x1 = throttle_x0 + bar_width
        self.draw_hud_split_bar(canvas, brake_x0, top, brake_x1, bottom, brake, recommended_brake, "#BD1051")
        self.draw_hud_throttle_bar(canvas, throttle_x0, top, throttle_x1, bottom, throttle, recommended_throttle)

    def open_gforce_hud(self) -> None:
        self.close_gforce_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.78)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.get_hud_geometry("gforce_hud_geometry", "160x160+150+120")
        hud.geometry(geometry)
        hud.minsize(90, 90)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_gforce_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_gforce_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_gforce_hud())
        canvas.bind("<ButtonPress-1>", self.on_gforce_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_gforce_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_gforce_hud())
        self.gforce_hud_window = hud
        self.gforce_hud_canvas = canvas
        self.draw_gforce_hud()
        self.update_hud_visibility_for_udp()

    def close_gforce_hud(self, mark_dirty: bool = True) -> None:
        hud = self.gforce_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("gforce_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.gforce_hud_window = None
        self.gforce_hud_canvas = None
        self.update_hud_gforce_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_gforce_hud_drag_start(self, event) -> None:
        self.gforce_hud_drag_offset = (
            event.x_root - self.gforce_hud_window.winfo_x(),
            event.y_root - self.gforce_hud_window.winfo_y(),
        ) if self.gforce_hud_window else (0, 0)

    def on_gforce_hud_drag_motion(self, event) -> None:
        if self.gforce_hud_window is None:
            return
        offset_x, offset_y = self.gforce_hud_drag_offset
        self.move_hud_window_snapped(self.gforce_hud_window, event.x_root - offset_x, event.y_root - offset_y)

    def draw_gforce_hud(self) -> None:
        canvas = self.gforce_hud_canvas
        if canvas is None or self.gforce_hud_window is None or not self.gforce_hud_window.winfo_exists():
            return
        width = max(90, canvas.winfo_width())
        height = max(90, canvas.winfo_height())
        canvas.delete("all")
        size = min(width, height)
        x0 = (width - size) / 2.0
        y0 = (height - size) / 2.0
        self.draw_hud_gforce_box(canvas, x0, y0, x0 + size, y0 + size)

    def open_tire_hud(self) -> None:
        self.close_tire_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.82)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.normalized_tire_hud_geometry(self.get_hud_geometry("tire_hud_geometry", "112x160+320+120"))
        hud.geometry(geometry)
        hud.minsize(80, 120)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_tire_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_tire_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_tire_hud())
        canvas.bind("<ButtonPress-1>", self.on_tire_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_tire_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_tire_hud())
        self.tire_hud_window = hud
        self.tire_hud_canvas = canvas
        self.update_hud_tire_button()
        self.draw_tire_hud()
        self.update_hud_visibility_for_udp()

    def close_tire_hud(self, mark_dirty: bool = True) -> None:
        hud = self.tire_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("tire_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.tire_hud_window = None
        self.tire_hud_canvas = None
        self.update_hud_tire_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_tire_hud_drag_start(self, event) -> None:
        self.tire_hud_drag_offset = (
            event.x_root - self.tire_hud_window.winfo_x(),
            event.y_root - self.tire_hud_window.winfo_y(),
        ) if self.tire_hud_window else (0, 0)

    def on_tire_hud_drag_motion(self, event) -> None:
        if self.tire_hud_window is None:
            return
        offset_x, offset_y = self.tire_hud_drag_offset
        self.move_hud_window_snapped(self.tire_hud_window, event.x_root - offset_x, event.y_root - offset_y)

    @staticmethod
    def normalized_tire_hud_geometry(geometry: str) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)$", geometry)
        if not match:
            return "112x160+320+120"
        width = int(match.group(1))
        height = int(match.group(2))
        position = match.group(3)
        scale = max(1.0, HUD_FONT_SCALE_PERCENT / 100.0)
        max_height = int(round(160 * scale))
        min_width = int(round(80 * scale))
        if height <= max_height:
            return geometry
        height_scale = max_height / max(1.0, float(height))
        return f"{max(min_width, int(round(width * height_scale)))}x{max_height}{position}"

    def draw_tire_hud(self) -> None:
        canvas = self.tire_hud_canvas
        if canvas is None or self.tire_hud_window is None or not self.tire_hud_window.winfo_exists():
            return
        width = max(100, canvas.winfo_width())
        height = max(130, canvas.winfo_height())
        canvas.delete("all")

        gap_x = max(18.0, width * 0.22)
        gap_y = max(14.0, height * 0.10)
        outer_pad_y = 2.0
        outer_pad_x = 6.0
        tire_w = max(24.0, (width - gap_x - outer_pad_x * 2.0) / 2.0)
        tire_h = max(52.0, (height - gap_y - outer_pad_y * 2.0) / 2.0)
        tire_w = min(tire_w, tire_h * 0.50)
        start_x = (width - tire_w * 2.0 - gap_x) / 2.0
        start_y = outer_pad_y
        positions = (
            ("fl", start_x, start_y),
            ("fr", start_x + tire_w + gap_x, start_y),
            ("rl", start_x, start_y + tire_h + gap_y),
            ("rr", start_x + tire_w + gap_x, start_y + tire_h + gap_y),
        )
        for side, x, y in positions:
            self.draw_hud_tire(canvas, side, x, y, x + tire_w, y + tire_h)

    def open_steer_hud(self) -> None:
        self.close_steer_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.82)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.get_hud_geometry("steer_hud_geometry", "68x160+450+120")
        hud.geometry(geometry)
        hud.minsize(48, 120)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_steer_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_steer_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_steer_hud())
        canvas.bind("<ButtonPress-1>", self.on_steer_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_steer_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_steer_hud())
        self.steer_hud_window = hud
        self.steer_hud_canvas = canvas
        self.update_hud_steer_button()
        self.draw_steer_hud()
        self.update_hud_visibility_for_udp()

    def close_steer_hud(self, mark_dirty: bool = True) -> None:
        hud = self.steer_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("steer_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.steer_hud_window = None
        self.steer_hud_canvas = None
        self.update_hud_steer_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_steer_hud_drag_start(self, event) -> None:
        self.steer_hud_drag_offset = (
            event.x_root - self.steer_hud_window.winfo_x(),
            event.y_root - self.steer_hud_window.winfo_y(),
        ) if self.steer_hud_window else (0, 0)

    def on_steer_hud_drag_motion(self, event) -> None:
        if self.steer_hud_window is None:
            return
        offset_x, offset_y = self.steer_hud_drag_offset
        self.move_hud_window_snapped(self.steer_hud_window, event.x_root - offset_x, event.y_root - offset_y)

    def draw_steer_hud(self) -> None:
        canvas = self.steer_hud_canvas
        if canvas is None or self.steer_hud_window is None or not self.steer_hud_window.winfo_exists():
            return
        width = max(48, canvas.winfo_width())
        height = max(120, canvas.winfo_height())
        canvas.delete("all")
        x0 = 0
        y0 = 0
        x1 = width
        y1 = height
        canvas.create_rectangle(x0, y0, x1, y1, fill="#151a20", outline="")
        balance, grip_loss = self.current_oversteer_balance()
        color = "#7f332f" if balance > 0.0 else "#2f5e73"
        magnitude = min(1.0, abs(balance))
        center_y = height * 0.5
        half_height = max(1.0, height * 0.5 - 1.0)
        bar_count = 20
        bar_width = width / float(bar_count)
        center_position = (bar_count - 1) / 2.0
        factors = tuple(
            self.steer_hud_bar_shape_factor(index, center_position, grip_loss)
            for index in range(bar_count)
        )
        for index, factor in enumerate(factors):
            level = magnitude * factor
            bx0 = x0 + bar_width * index
            bx1 = x0 + bar_width * (index + 1)
            if level <= 0.015:
                continue
            if balance > 0.0:
                top = center_y - half_height * level
                canvas.create_rectangle(bx0, top, bx1, center_y, fill=color, outline="")
            else:
                bottom = center_y + half_height * level
                canvas.create_rectangle(bx0, center_y, bx1, bottom, fill=color, outline="")
        right = x1 - 1
        bottom = y1 - 1
        line_width = hud_px(1)
        canvas.create_line(x0, center_y, right, center_y, fill="#252c35", width=line_width)
        canvas.create_line(x0, y0, right, y0, right, bottom, x0, bottom, x0, y0, fill="#252c35", width=line_width)
        canvas.create_text(
            width * 0.5,
            center_y - half_height * 0.80,
            text="OVER",
            fill="#9a5a56",
            font=hud_font("Segoe UI", max(6, int(height * 0.055)), "bold"),
            anchor="center",
        )
        canvas.create_text(
            width * 0.5,
            center_y + half_height * 0.80,
            text="UNDER",
            fill="#5c8292",
            font=hud_font("Segoe UI", max(6, int(height * 0.055)), "bold"),
            anchor="center",
        )

    @staticmethod
    def steer_hud_bar_shape_factor(index: int, center_position: float, grip_loss: float) -> float:
        grip_loss = max(0.0, min(1.0, grip_loss))
        distance = abs(index - center_position) / max(1.0, center_position)
        shape_loss = max(0.0, min(1.0, (grip_loss - 0.18) / 0.82))
        focus_power = 1.35 + shape_loss * 4.2
        focused_peak = max(0.0, 1.0 - distance) ** focus_power
        flat_shape = 1.0 - 0.08 * distance
        edge_floor = 0.012 + 0.12 * (1.0 - shape_loss)
        return max(edge_floor, flat_shape * (1.0 - shape_loss) + focused_peak * shape_loss)

    def current_oversteer_balance(self) -> tuple[float, float]:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return 0.0, 0.0
        raw_balance, grip_loss = self.raw_oversteer_balance(raw)
        return self.stabilized_steer_hud_balance(raw_balance, grip_loss), grip_loss

    def raw_oversteer_balance(self, raw: dict[str, float | int | bool]) -> tuple[float, float]:
        front_angle = (
            abs(float(raw.get("tire_slip_angle_fl", 0.0)))
            + abs(float(raw.get("tire_slip_angle_fr", 0.0)))
        ) * 0.5
        rear_angle = (
            abs(float(raw.get("tire_slip_angle_rl", 0.0)))
            + abs(float(raw.get("tire_slip_angle_rr", 0.0)))
        ) * 0.5
        diff = rear_angle - front_angle
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        speed_gate = self.smoothstep(12.0, 62.0, speed_kmh)
        high_speed_gain = 1.0 + 0.22 * self.smoothstep(95.0, 180.0, speed_kmh)
        speed_scale = (0.18 + 0.82 * speed_gate) * high_speed_gain
        magnitude = self.smoothstep(0.04, 0.85, abs(diff)) * speed_scale
        magnitude = max(0.0, min(1.0, magnitude))
        slip_max = max(
            abs(float(raw.get("tire_combined_slip_fl", 0.0))),
            abs(float(raw.get("tire_combined_slip_fr", 0.0))),
            abs(float(raw.get("tire_combined_slip_rl", 0.0))),
            abs(float(raw.get("tire_combined_slip_rr", 0.0))),
        )
        throttle = max(0.0, min(1.0, float(raw.get("accel", 0.0)) / 255.0))
        brake = max(0.0, min(1.0, float(raw.get("brake", 0.0)) / 255.0))
        lateral_g = abs(float(raw.get("accel_x", 0.0))) / 9.80665
        drive_load = max(throttle, brake)
        coasting_steer = self.smoothstep(0.0, 0.18, 0.18 - drive_load)
        slip_start = 0.95 + 0.38 * coasting_steer
        slip_end = 2.65 + 0.35 * coasting_steer
        grip_loss = self.smoothstep(slip_start, slip_end, slip_max)
        load_gate = max(
            self.smoothstep(0.05, 0.38, drive_load),
            self.smoothstep(0.45, 1.15, lateral_g),
        )
        grip_loss *= 0.35 + 0.65 * load_gate
        if magnitude <= 0.0:
            return 0.0, grip_loss
        raw_balance = magnitude if diff > 0.0 else -magnitude
        return raw_balance, grip_loss

    def update_drift_mode_state(self, now: float, raw: dict[str, float | int | bool]) -> None:
        if not bool(raw.get("on", False)):
            self.drift_mode_active = False
            self.drift_mode_score = 0.0
            self.drift_mode_score_last_update = 0.0
            self.drift_mode_hold_until = 0.0
            self.drift_relief_high_score_since = 0.0
            self.drift_relief_trigger_suppressed = False
            self.drift_oversteer_component = 0.0
            self.update_drift_relief_status_text()
            return

        score = self.smoothed_drift_mode_score(now, self.compute_drift_mode_score(raw))
        self.drift_mode_score = score
        if score >= 0.50:
            self.drift_mode_active = True
            self.drift_mode_hold_until = now + 2.20
        elif score <= 0.18 and now >= self.drift_mode_hold_until:
            self.drift_mode_active = False
        self.update_drift_relief_trigger_suppression(now, score)
        self.update_drift_relief_status_text()

    def compute_drift_mode_score(self, raw: dict[str, float | int | bool]) -> float:
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        speed_gate = self.smoothstep(18.0, 55.0, speed_kmh)
        if speed_gate <= 0.0:
            self.drift_oversteer_component = 0.0
            self.drift_mode_components = {
                "over": 0.0,
                "angle": 0.0,
                "drive": 0.0,
                "wheel": 0.0,
                "grip": 0.0,
            }
            return 0.0

        raw_balance, grip_loss = self.raw_oversteer_balance(raw)
        oversteer_gate = self.smoothed_drift_oversteer_component(
            self.drift_oversteer_signal(raw, raw_balance, grip_loss)
        )
        grip_gate = self.smoothstep(0.18, 0.65, grip_loss)
        slip_angle_gate = self.smoothstep(0.16, 0.55, abs(self.hud_slip_angle_value(raw)))
        driven_ratio, driven_combined = self.throttle_driven_slip_values(raw)
        driven_slip_gate = max(
            self.smoothstep(1.10, 1.95, driven_ratio),
            self.smoothstep(0.70, 1.65, driven_combined),
        )
        wheel_over_gate = self.driven_wheel_overrotation_gate(raw)
        yaw_gate = self.smoothstep(0.30, 1.10, abs(float(raw.get("angular_velocity_y", 0.0))))
        drive_gate = max(driven_slip_gate, wheel_over_gate)
        drift_shape = max(oversteer_gate * 0.45, slip_angle_gate * 0.92, yaw_gate * 0.68)
        drift_context = max(grip_gate * 0.80, slip_angle_gate * 0.72, drive_gate * 0.62)
        sustained_drift_score = (
            slip_angle_gate * 0.34
            + grip_gate * 0.30
            + drive_gate * 0.26
            + oversteer_gate * 0.10
        )
        score = max(
            drift_shape * drift_context,
            sustained_drift_score,
            oversteer_gate * grip_gate * 0.55,
        )
        self.drift_mode_components = {
            "over": oversteer_gate,
            "angle": slip_angle_gate,
            "drive": driven_slip_gate,
            "wheel": wheel_over_gate,
            "grip": grip_gate,
        }
        return max(0.0, min(1.0, score * speed_gate))

    def drift_oversteer_signal(self, raw: dict[str, float | int | bool], raw_balance: float, grip_loss: float) -> float:
        rear_bias_gate = self.smoothstep(0.05, 1.25, max(0.0, raw_balance))
        slip_angle_gate = self.smoothstep(0.10, 0.55, abs(self.hud_slip_angle_value(raw)))
        yaw_gate = self.smoothstep(0.20, 1.05, abs(float(raw.get("angular_velocity_y", 0.0))))
        lateral_g = abs(float(raw.get("accel_x", 0.0))) / 9.80665
        lateral_gate = self.smoothstep(0.25, 1.05, lateral_g)
        steer_gate = self.smoothstep(0.06, 0.46, abs(float(raw.get("steer", 0.0))) / 127.0)
        sustained_rotation_gate = yaw_gate * max(slip_angle_gate, lateral_gate * 0.70) * max(0.55, steer_gate)
        sliding_context_gate = max(grip_loss * 0.62, lateral_gate * 0.42, steer_gate * 0.28)
        body_slip_gate = slip_angle_gate * max(0.45, sliding_context_gate)
        return max(0.0, min(1.0, max(rear_bias_gate, sustained_rotation_gate, body_slip_gate)))

    def smoothed_drift_oversteer_component(self, target: float) -> float:
        target = max(0.0, min(1.0, float(target)))
        previous = self.drift_oversteer_component
        alpha = 0.34 if target > previous else 0.16
        value = previous + (target - previous) * alpha
        if target < 0.025 and value < 0.035:
            value = 0.0
        self.drift_oversteer_component = max(0.0, min(1.0, value))
        return self.drift_oversteer_component

    def smoothed_drift_mode_score(self, now: float, target: float) -> float:
        target = max(0.0, min(1.0, float(target)))
        previous = max(0.0, min(1.0, float(getattr(self, "drift_mode_score", 0.0))))
        last_update = float(getattr(self, "drift_mode_score_last_update", 0.0))
        dt = 0.0 if last_update <= 0.0 else max(0.0, min(0.2, now - last_update))
        self.drift_mode_score_last_update = now
        if target >= previous:
            alpha = 0.55 if dt <= 0.0 else min(0.85, 0.45 + dt * 3.0)
            value = previous + (target - previous) * alpha
        else:
            value = max(target, previous - DRIFT_SCORE_DECAY_PER_SECOND * max(dt, 1.0 / 120.0))
        if target < 0.025 and value < 0.035:
            value = 0.0
        return max(0.0, min(1.0, value))

    def driven_wheel_overrotation_gate(self, raw: dict[str, float | int | bool]) -> float:
        drive_train = int(raw.get("drive_train", 1))
        front = (
            abs(float(raw.get("wheel_rotation_speed_fl", 0.0)))
            + abs(float(raw.get("wheel_rotation_speed_fr", 0.0)))
        ) * 0.5
        rear = (
            abs(float(raw.get("wheel_rotation_speed_rl", 0.0)))
            + abs(float(raw.get("wheel_rotation_speed_rr", 0.0)))
        ) * 0.5
        if drive_train == 0:
            driven = front
            reference = rear
        else:
            driven = rear
            reference = front
        if reference < 0.1:
            return 0.0
        return self.smoothstep(1.12, 1.55, driven / reference)

    def drift_relief_active(self) -> bool:
        return bool(self.drift_relief_enabled.get()) and self.drift_mode_active

    def update_drift_relief_trigger_suppression(self, now: float, score: float) -> None:
        if not bool(self.drift_relief_enabled.get()) or not self.drift_mode_active:
            self.drift_relief_high_score_since = 0.0
            self.drift_relief_trigger_suppressed = False
            return
        if score < DRIFT_RELIEF_TRIGGER_RELEASE_SCORE:
            self.drift_relief_high_score_since = 0.0
            self.drift_relief_trigger_suppressed = False
            return
        if score < DRIFT_RELIEF_TRIGGER_SCORE:
            if not self.drift_relief_trigger_suppressed:
                self.drift_relief_high_score_since = 0.0
            return
        if score >= DRIFT_RELIEF_TRIGGER_SCORE:
            if self.drift_relief_high_score_since <= 0.0:
                self.drift_relief_high_score_since = now
            if now - self.drift_relief_high_score_since >= DRIFT_RELIEF_TRIGGER_HOLD_SECONDS:
                self.drift_relief_trigger_suppressed = True

    def drift_relief_trigger_suppression_active(self) -> bool:
        return bool(self.drift_relief_enabled.get()) and bool(self.drift_relief_trigger_suppressed)

    def update_drift_relief_status_text(self) -> None:
        if not bool(self.drift_relief_enabled.get()):
            self.drift_relief_status_text.set("off")
        elif self.drift_relief_trigger_suppression_active():
            self.drift_relief_status_text.set("R2 OFF")
        elif self.drift_mode_active:
            self.drift_relief_status_text.set("DRIFT")
        else:
            self.drift_relief_status_text.set("armed")

    def stabilized_steer_hud_balance(self, raw_balance: float, grip_loss: float) -> float:
        now = time.monotonic()
        raw_sign = 1 if raw_balance > 0.025 else -1 if raw_balance < -0.025 else 0
        current_sign = self.steer_hud_last_sign
        high_slip = grip_loss >= 0.38

        if raw_sign == 0:
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance *= 0.72
            if abs(self.steer_hud_stable_balance) < 0.015:
                self.steer_hud_stable_balance = 0.0
                self.steer_hud_last_sign = 0
            return self.steer_hud_stable_balance

        if current_sign == 0 or raw_sign == current_sign:
            self.steer_hud_last_sign = raw_sign
            self.steer_hud_last_sign_changed_at = now if current_sign != raw_sign else self.steer_hud_last_sign_changed_at
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance = self.steer_hud_stable_balance * 0.35 + raw_balance * 0.65
            return self.steer_hud_stable_balance

        if self.steer_hud_pending_sign == raw_sign:
            self.steer_hud_pending_count += 1
        else:
            self.steer_hud_pending_sign = raw_sign
            self.steer_hud_pending_count = 1

        hold_seconds = 0.18 if high_slip else 0.08
        elapsed = now - self.steer_hud_last_sign_changed_at if self.steer_hud_last_sign_changed_at else hold_seconds
        stronger_opposite = abs(raw_balance) >= max(0.18, abs(self.steer_hud_stable_balance) * (1.18 if high_slip else 1.05))
        persistent_opposite = self.steer_hud_pending_count >= (3 if high_slip else 2)
        if elapsed >= hold_seconds and (stronger_opposite or persistent_opposite):
            self.steer_hud_last_sign = raw_sign
            self.steer_hud_last_sign_changed_at = now
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance = self.steer_hud_stable_balance * 0.25 + raw_balance * 0.75
        else:
            decay = 0.92 if high_slip else 0.80
            self.steer_hud_stable_balance *= decay
        return self.steer_hud_stable_balance

    def open_applied_steer_hud(self) -> None:
        self.close_applied_steer_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.82)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.normalized_applied_steer_hud_geometry(
            self.get_hud_geometry("applied_steer_hud_geometry", "220x140+530+120")
        )
        hud.geometry(geometry)
        hud.minsize(150, 95)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_applied_steer_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_applied_steer_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_applied_steer_hud())
        canvas.bind("<ButtonPress-1>", self.on_applied_steer_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_applied_steer_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_applied_steer_hud())
        self.applied_steer_hud_window = hud
        self.applied_steer_hud_canvas = canvas
        self.update_hud_applied_steer_button()
        self.draw_applied_steer_hud()
        self.update_hud_visibility_for_udp()

    def close_applied_steer_hud(self, mark_dirty: bool = True) -> None:
        hud = self.applied_steer_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("applied_steer_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.applied_steer_hud_window = None
        self.applied_steer_hud_canvas = None
        self.update_hud_applied_steer_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_applied_steer_hud_drag_start(self, event) -> None:
        self.applied_steer_hud_drag_offset = (
            event.x_root - self.applied_steer_hud_window.winfo_x(),
            event.y_root - self.applied_steer_hud_window.winfo_y(),
        ) if self.applied_steer_hud_window else (0, 0)

    def on_applied_steer_hud_drag_motion(self, event) -> None:
        if self.applied_steer_hud_window is None:
            return
        offset_x, offset_y = self.applied_steer_hud_drag_offset
        x = int(round(event.x_root - offset_x))
        y = int(round(event.y_root - offset_y))
        try:
            screen_w = self.applied_steer_hud_window.winfo_screenwidth()
            screen_h = self.applied_steer_hud_window.winfo_screenheight()
            width = max(1, self.applied_steer_hud_window.winfo_width())
            height = max(1, self.applied_steer_hud_window.winfo_height())
            x = max(0, min(screen_w - width, x))
            y = max(0, min(screen_h - height, y))
        except tk.TclError:
            pass
        self.applied_steer_hud_window.geometry(f"+{x}+{y}")

    @staticmethod
    def normalized_applied_steer_hud_geometry(geometry: str) -> str:
        match = re.match(r"^(\d+)x(\d+)([+-]\d+[+-]\d+)$", geometry)
        if not match:
            return "220x140+530+120"
        width = int(match.group(1))
        height = int(match.group(2))
        position = match.group(3)
        scale = max(1.0, HUD_FONT_SCALE_PERCENT / 100.0)
        min_width = int(round(220 * scale))
        min_height = int(round(140 * scale))
        if width >= min_width and height >= min_height:
            return geometry
        return f"{max(width, min_width)}x{max(height, min_height)}{position}"

    def draw_applied_steer_hud(self) -> None:
        canvas = self.applied_steer_hud_canvas
        if canvas is None or self.applied_steer_hud_window is None or not self.applied_steer_hud_window.winfo_exists():
            return
        width = max(150, canvas.winfo_width())
        height = max(95, canvas.winfo_height())
        canvas.delete("all")
        self.draw_hud_applied_steer_gauge(canvas, 0, 0, width, height)

    def draw_hud_applied_steer_gauge(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        width = x1 - x0
        height = y1 - y0
        center_x = (x0 + x1) / 2.0
        center_y = y0 + height * 0.96
        outer_radius = min(width * 0.50 - hud_px(2), height * 0.92)
        ring_width = max(hud_px(24), min(hud_px(34), outer_radius * 0.32))
        inner_radius = max(1.0, outer_radius - ring_width)
        start_angle = -120.0
        end_angle = 120.0
        self.draw_hud_ring_segment(
            canvas,
            center_x,
            center_y,
            inner_radius,
            outer_radius,
            start_angle,
            end_angle,
            fill="#151a20",
            outline="#252c35",
            width=hud_px(1),
        )
        canvas.create_line(center_x, center_y - outer_radius, center_x, center_y - inner_radius, fill="#252c35", width=hud_px(1))

        applied = self.current_applied_steer_estimate()
        marker_angle = max(-90.0, min(90.0, applied * 90.0))
        marker_mid_radius = (inner_radius + outer_radius) * 0.5
        marker_degrees = math.degrees(max(0.08, 30.0 / max(1.0, marker_mid_radius))) * 0.5
        marker_start = max(start_angle, marker_angle - marker_degrees)
        marker_end = min(end_angle, marker_angle + marker_degrees)
        marker_color = "#ff00cc"
        self.draw_hud_ring_segment(
            canvas,
            center_x,
            center_y,
            inner_radius + hud_px(1),
            outer_radius - hud_px(1),
            marker_start,
            marker_end,
            fill=marker_color,
            outline="",
            width=0,
        )
        text_color = "#7f8790"
        canvas.create_text(
            center_x,
            y0 + hud_px(5),
            text=f"{applied:+.2f}",
            fill=text_color,
            font=hud_fixed_font("Consolas", 8, "bold"),
            anchor="n",
        )

    def current_applied_steer_estimate(self) -> float:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            self.applied_steer_estimate_value = 0.0
            self.applied_steer_last_update = 0.0
            self.applied_steer_hold_until = 0.0
            self.applied_steer_last_speed_kmh = 0.0
            self.applied_steer_last_input_abs = 0.0
            return 0.0
        steer_input = max(-1.0, min(1.0, float(raw.get("steer", 0.0)) / 127.0))
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        throttle_input = max(0.0, min(1.0, float(raw.get("accel", 0.0)) / 255.0))
        brake_input = max(0.0, min(1.0, float(raw.get("brake", 0.0)) / 255.0))
        speed_limit = self.applied_steer_speed_limit(speed_kmh)
        target = max(-1.0, min(1.0, steer_input * speed_limit))
        return self.damped_applied_steer_value(target, steer_input, throttle_input, brake_input, speed_kmh)

    def damped_applied_steer_value(
        self,
        target: float,
        steer_input: float,
        throttle_input: float,
        brake_input: float,
        speed_kmh: float,
    ) -> float:
        now = time.monotonic()
        previous = self.applied_steer_estimate_value
        if self.applied_steer_last_update <= 0.0:
            self.applied_steer_last_update = now
            self.applied_steer_estimate_value = target
            self.applied_steer_last_speed_kmh = speed_kmh
            self.applied_steer_last_input_abs = abs(steer_input)
            return target
        dt = max(0.0, min(0.12, now - self.applied_steer_last_update))
        self.applied_steer_last_update = now

        input_abs = abs(steer_input)
        input_held = input_abs >= 0.82
        if abs(steer_input) < 0.08 and abs(target) < abs(previous):
            rate = 8.0
        elif previous * target < 0.0:
            rate = 7.0
        elif abs(target) > abs(previous):
            speed_mix = self.smoothstep(20.0, 110.0, speed_kmh)
            low_speed_rate = 3.2 if input_held else 2.8
            high_speed_rate = 1.7 if input_held else 1.35
            rate = low_speed_rate + (high_speed_rate - low_speed_rate) * speed_mix
        else:
            rate = 4.7
        delta = target - previous
        step = math.copysign(min(abs(delta), rate * dt), delta)
        value = previous + step
        if abs(steer_input) < 0.02 and abs(value) < 0.01:
            value = 0.0
        self.applied_steer_estimate_value = max(-1.0, min(1.0, value))
        self.applied_steer_last_speed_kmh = speed_kmh
        self.applied_steer_last_input_abs = input_abs
        return self.applied_steer_estimate_value

    def applied_steer_speed_limit(self, speed_kmh: float) -> float:
        speed = max(0.0, float(speed_kmh))
        samples = (
            (0.0, 1.0),
            (30.0, 1.0),
            (40.0, 50.0 / 90.0),
            (60.0, 33.0 / 90.0),
            (80.0, 26.0 / 90.0),
            (100.0, 21.0 / 90.0),
            (120.0, 20.0 / 90.0),
            (140.0, 18.0 / 90.0),
            (160.0, 16.8 / 90.0),
            (180.0, 16.5 / 90.0),
            (200.0, 16.3 / 90.0),
            (250.0, 16.0 / 90.0),
        )
        if speed <= samples[0][0]:
            return samples[0][1]
        for (speed0, limit0), (speed1, limit1) in zip(samples, samples[1:]):
            if speed <= speed1:
                mix = self.smoothstep(speed0, speed1, speed)
                return limit0 + (limit1 - limit0) * mix
        return samples[-1][1]

    @staticmethod
    def draw_hud_ring_segment(
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        inner_radius: float,
        outer_radius: float,
        start_angle: float,
        end_angle: float,
        fill: str,
        outline: str = "",
        width: int = 1,
    ) -> None:
        if end_angle < start_angle:
            start_angle, end_angle = end_angle, start_angle
        span = max(1.0, end_angle - start_angle)
        steps = max(8, int(span / 4.0))
        outer_points = []
        inner_points = []
        for index in range(steps + 1):
            angle = start_angle + span * (index / steps)
            radians = math.radians(angle)
            outer_points.append((center_x + math.sin(radians) * outer_radius, center_y - math.cos(radians) * outer_radius))
            inner_points.append((center_x + math.sin(radians) * inner_radius, center_y - math.cos(radians) * inner_radius))
        points = [coord for point in outer_points + list(reversed(inner_points)) for coord in point]
        canvas.create_polygon(points, fill=fill, outline=outline, width=width, smooth=False)

    def open_rpm_hud(self) -> None:
        self.close_rpm_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.82)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        geometry = self.get_hud_geometry("rpm_hud_geometry", "160x160+540+120")
        hud.geometry(geometry)
        hud.minsize(90, 90)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_rpm_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_rpm_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_rpm_hud())
        canvas.bind("<ButtonPress-1>", self.on_rpm_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_rpm_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_rpm_hud())
        self.rpm_hud_window = hud
        self.rpm_hud_canvas = canvas
        self.update_hud_rpm_button()
        self.draw_rpm_hud()
        self.update_hud_visibility_for_udp()

    def close_rpm_hud(self, mark_dirty: bool = True) -> None:
        hud = self.rpm_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("rpm_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.rpm_hud_window = None
        self.rpm_hud_canvas = None
        self.rpm_hud_needle_angles.clear()
        self.rpm_hud_display_rpm = None
        self.rpm_hud_zero_dropouts = 0
        self.update_hud_rpm_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_rpm_hud_drag_start(self, event) -> None:
        self.rpm_hud_drag_offset = (
            event.x_root - self.rpm_hud_window.winfo_x(),
            event.y_root - self.rpm_hud_window.winfo_y(),
        ) if self.rpm_hud_window else (0, 0)

    def on_rpm_hud_drag_motion(self, event) -> None:
        if self.rpm_hud_window is None:
            return
        offset_x, offset_y = self.rpm_hud_drag_offset
        self.move_hud_window_snapped(self.rpm_hud_window, event.x_root - offset_x, event.y_root - offset_y)

    def draw_rpm_hud(self) -> None:
        canvas = self.rpm_hud_canvas
        if canvas is None or self.rpm_hud_window is None or not self.rpm_hud_window.winfo_exists():
            return
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        if width < 90 or height < 90:
            try:
                self.rpm_hud_window.update_idletasks()
                width = max(width, self.rpm_hud_window.winfo_width(), canvas.winfo_width())
                height = max(height, self.rpm_hud_window.winfo_height(), canvas.winfo_height())
            except tk.TclError:
                pass
        width = max(90, width)
        height = max(90, height)
        canvas.delete("all")
        size = min(width, height)
        x0 = (width - size) / 2.0
        y0 = (height - size) / 2.0
        self.draw_hud_rpm_gauge(canvas, x0, y0, x0 + size, y0 + size)

    def open_engine_hud(self) -> None:
        self.close_engine_hud(mark_dirty=False)
        hud = tk.Toplevel(self.root)
        hud.overrideredirect(True)
        hud.attributes("-topmost", True)
        hud.attributes("-alpha", 0.82)
        hud.configure(bg="#050607")
        try:
            hud.attributes("-transparentcolor", "#050607")
        except tk.TclError:
            pass
        percent = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        min_width, min_height = self.engine_hud_min_size(percent)
        default_geometry = "76x160+720+120"
        geometry = self.normalized_engine_hud_geometry(
            self.get_hud_geometry("engine_hud_geometry", default_geometry),
            percent,
        )
        hud.geometry(geometry)
        hud.minsize(min_width, min_height)
        canvas = tk.Canvas(hud, bg="#050607", highlightthickness=0, bd=0)
        canvas.pack(fill="both", expand=True)
        hud.bind("<ButtonPress-1>", self.on_engine_hud_drag_start)
        hud.bind("<B1-Motion>", self.on_engine_hud_drag_motion)
        hud.bind("<Button-3>", lambda _event: self.close_engine_hud())
        canvas.bind("<ButtonPress-1>", self.on_engine_hud_drag_start)
        canvas.bind("<B1-Motion>", self.on_engine_hud_drag_motion)
        canvas.bind("<Button-3>", lambda _event: self.close_engine_hud())
        self.engine_hud_window = hud
        self.engine_hud_canvas = canvas
        self.update_hud_engine_button()
        self.draw_engine_hud()
        self.update_hud_visibility_for_udp()

    def close_engine_hud(self, mark_dirty: bool = True) -> None:
        hud = self.engine_hud_window
        if hud is not None:
            try:
                if hud.winfo_exists():
                    self.set_hud_geometry("engine_hud_geometry", hud.geometry())
                    hud.destroy()
            except tk.TclError:
                pass
        self.engine_hud_window = None
        self.engine_hud_canvas = None
        self.engine_hud_torque_needle_angles.clear()
        self.engine_hud_vacuum_needle_angles.clear()
        self.update_hud_engine_button()
        if mark_dirty:
            self.mark_hud_active_settings_changed()

    def on_engine_hud_drag_start(self, event) -> None:
        self.engine_hud_drag_offset = (
            event.x_root - self.engine_hud_window.winfo_x(),
            event.y_root - self.engine_hud_window.winfo_y(),
        ) if self.engine_hud_window else (0, 0)

    def on_engine_hud_drag_motion(self, event) -> None:
        if self.engine_hud_window is None:
            return
        offset_x, offset_y = self.engine_hud_drag_offset
        self.move_hud_window_snapped(self.engine_hud_window, event.x_root - offset_x, event.y_root - offset_y)

    def draw_engine_hud(self) -> None:
        canvas = self.engine_hud_canvas
        if canvas is None or self.engine_hud_window is None or not self.engine_hud_window.winfo_exists():
            return
        width = max(1, canvas.winfo_width())
        height = max(1, canvas.winfo_height())
        if width < 60 or height < 120:
            try:
                self.engine_hud_window.update_idletasks()
                width = max(width, self.engine_hud_window.winfo_width(), canvas.winfo_width())
                height = max(height, self.engine_hud_window.winfo_height(), canvas.winfo_height())
            except tk.TclError:
                pass
        width = max(60, width)
        height = max(120, height)
        canvas.delete("all")
        gap = max(4.0, min(10.0, height * 0.05))
        diameter = min(width, (height - gap) / 2.0)
        left = (width - diameter) / 2.0
        torque_y = 0.0
        boost_y = diameter + gap
        self.draw_torque_meter(canvas, left, torque_y, left + diameter, torque_y + diameter)
        self.draw_boost_meter(canvas, left, boost_y, left + diameter, boost_y + diameter)

    def draw_engine_meter_shell(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        label: str = "",
        tick_angles: tuple[float, ...] = (0.0, 180.0, 270.0),
    ) -> tuple[float, float, float, float]:
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        pad = max(1.0, diameter * 0.03)
        outer_x0 = center_x - diameter / 2.0 + pad
        outer_y0 = center_y - diameter / 2.0 + pad
        outer_x1 = center_x + diameter / 2.0 - pad
        outer_y1 = center_y + diameter / 2.0 - pad
        radius = (outer_x1 - outer_x0) / 2.0
        inner_radius = radius * 0.58
        line_width = hud_px(1)
        canvas.create_oval(outer_x0, outer_y0, outer_x1, outer_y1, fill="#151a20", outline="#252c35", width=line_width)
        canvas.create_oval(
            center_x - inner_radius,
            center_y - inner_radius,
            center_x + inner_radius,
            center_y + inner_radius,
            outline="#252c35",
            width=line_width,
        )
        for angle in tick_angles:
            radians = math.radians(angle)
            tick_outer = radius * 0.94
            tick_inner = radius * 0.80
            canvas.create_line(
                center_x + math.sin(radians) * tick_inner,
                center_y - math.cos(radians) * tick_inner,
                center_x + math.sin(radians) * tick_outer,
                center_y - math.cos(radians) * tick_outer,
                fill="#d6dde5",
                width=line_width,
            )
        if label:
            canvas.create_text(
                center_x,
                center_y,
                text=label,
                fill="#5f6872",
                font=hud_fixed_font("Consolas", max(6, int(diameter * 0.14)), "bold"),
                anchor="center",
        )
        return center_x, center_y, radius, inner_radius

    def draw_torque_meter(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        raw = self.latest_raw or {}
        raw_torque = float(raw.get("torque", 0.0))
        car_ordinal = int(raw.get("car_ordinal", 0)) if raw else 0
        key = car_ordinal if car_ordinal > 0 else 0
        positive_peak = max(self.engine_hud_torque_peak_by_car.get(key, 0.0), raw_torque)
        negative_peak = min(self.engine_hud_torque_min_by_car.get(key, 0.0), raw_torque)
        self.engine_hud_torque_peak_by_car[key] = positive_peak
        self.engine_hud_torque_min_by_car[key] = negative_peak
        torque = self.smoothed_engine_hud_torque(car_ordinal, raw_torque)
        positive_max = max(1.0, positive_peak)
        negative_min = min(-1.0, negative_peak)
        positive_ratio = max(0.0, min(1.0, torque / positive_max)) if torque >= 0.0 else 0.0
        negative_ratio = max(0.0, min(1.0, abs(torque / negative_min))) if torque < 0.0 else 0.0
        zero_angle = 0.0
        positive_sweep_degrees = 120.0
        negative_sweep_degrees = 120.0
        arc_start = 90.0
        center_x, center_y, radius, _inner_radius = self.draw_engine_meter_shell(
            canvas,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(zero_angle - negative_sweep_degrees, zero_angle, zero_angle + positive_sweep_degrees),
        )
        track_radius = radius * 0.86
        track_width = hud_px(3)
        track_box = (
            center_x - track_radius,
            center_y - track_radius,
            center_x + track_radius,
            center_y + track_radius,
        )
        negative_color = "#CE1982"
        positive_color = "#119C8E"
        needle_color = "#13C9B4"
        value_color = negative_color if torque < 0.0 else positive_color
        active_extent = (
            negative_sweep_degrees * negative_ratio
            if torque < 0.0
            else -positive_sweep_degrees * positive_ratio
        )
        canvas.create_arc(*track_box, start=arc_start, extent=negative_sweep_degrees, style=tk.ARC, outline="#252c35", width=track_width)
        canvas.create_arc(*track_box, start=arc_start, extent=-positive_sweep_degrees, style=tk.ARC, outline="#252c35", width=track_width)
        if abs(active_extent) >= 3.0:
            canvas.create_arc(
                *track_box,
                start=arc_start,
                extent=active_extent,
                style=tk.ARC,
                outline=negative_color if torque < 0.0 else positive_color,
                width=track_width,
            )
        needle_angle = zero_angle + (positive_sweep_degrees * positive_ratio if torque >= 0.0 else -negative_sweep_degrees * negative_ratio)
        radians = math.radians(needle_angle)
        needle_outer = radius * 0.68
        trail_inner = cap_radius = max(2.0, radius * 0.07)
        self.engine_hud_torque_needle_angles.append(needle_angle)
        self.draw_engine_needle_motion_blur(
            canvas,
            center_x,
            center_y,
            trail_inner,
            needle_outer,
            list(self.engine_hud_torque_needle_angles),
            ("#073b34", "#0a6f60", needle_color),
        )
        canvas.create_line(
            center_x,
            center_y,
            center_x + math.sin(radians) * needle_outer,
            center_y - math.cos(radians) * needle_outer,
            fill=needle_color,
            width=hud_px(3),
        )
        canvas.create_oval(
            center_x - cap_radius,
            center_y - cap_radius,
            center_x + cap_radius,
            center_y + cap_radius,
            fill=needle_color,
            outline="",
        )
        canvas.create_text(
            center_x,
            center_y - radius * 0.42 - 4.0,
            text="Nm",
            fill="#8b96a3",
            font=hud_fixed_font("Consolas", max(5, int((x1 - x0) * 0.083)), "bold"),
            anchor="center",
        )
        canvas.create_text(
            center_x,
            center_y + 24.0,
            text=f"{torque:.0f}",
            fill=value_color,
            font=hud_fixed_font("Consolas", max(5, int((x1 - x0) * 0.105)), "bold"),
            anchor="center",
        )

    def draw_boost_meter(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        raw = self.latest_raw or {}
        raw_boost = float(raw.get("boost", 0.0))
        car_ordinal = int(raw.get("car_ordinal", 0)) if raw else 0
        if car_ordinal:
            peak = max(self.engine_hud_boost_peak_by_car.get(car_ordinal, 0.0), raw_boost)
            self.engine_hud_boost_peak_by_car[car_ordinal] = peak
        else:
            peak = max(0.0, raw_boost)
        boost = self.smoothed_engine_hud_boost(car_ordinal, raw_boost)
        if not self.engine_hud_should_show_boost_meter(peak, raw_boost):
            self.draw_vacuum_meter(canvas, x0, y0, x1, y1, boost)
            return
        self.engine_hud_vacuum_needle_angles.clear()
        positive_max = self.boost_display_positive_max(peak)
        negative_min = -18.0
        positive_ratio = 0.0 if positive_max <= 0.0 else max(0.0, min(1.0, boost / positive_max))
        negative_ratio = 0.0 if boost >= 0.0 else max(0.0, min(1.0, abs(boost / negative_min)))
        zero_angle = 0.0
        positive_sweep_degrees = 120.0
        negative_sweep_degrees = 120.0
        arc_start = 90.0
        center_x, center_y, radius, _inner_radius = self.draw_engine_meter_shell(
            canvas,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(zero_angle - negative_sweep_degrees, zero_angle, zero_angle + positive_sweep_degrees),
        )
        track_radius = radius * 0.86
        track_width = hud_px(3)
        track_box = (
            center_x - track_radius,
            center_y - track_radius,
            center_x + track_radius,
            center_y + track_radius,
        )
        gauge_color = "#f1c40f"
        value_color = "#2ea8ff" if boost < 0.0 else gauge_color
        arc_color = "#2f5e73" if boost < 0.0 else gauge_color
        active_extent = (
            negative_sweep_degrees * negative_ratio
            if boost < 0.0
            else -positive_sweep_degrees * positive_ratio
        )
        canvas.create_arc(*track_box, start=arc_start, extent=negative_sweep_degrees, style=tk.ARC, outline="#252c35", width=track_width)
        canvas.create_arc(*track_box, start=arc_start, extent=-positive_sweep_degrees, style=tk.ARC, outline="#252c35", width=track_width)
        if abs(active_extent) >= 3.0:
            canvas.create_arc(
                *track_box,
                start=arc_start,
                extent=active_extent,
                style=tk.ARC,
                outline=arc_color,
                width=track_width,
            )
        needle_angle = zero_angle + (positive_sweep_degrees * positive_ratio if boost >= 0.0 else -negative_sweep_degrees * negative_ratio)
        radians = math.radians(needle_angle)
        needle_outer = radius * 0.68
        canvas.create_line(
            center_x,
            center_y,
            center_x + math.sin(radians) * needle_outer,
            center_y - math.cos(radians) * needle_outer,
            fill=gauge_color,
            width=hud_px(3),
        )
        cap_radius = max(2.0, radius * 0.07)
        canvas.create_oval(
            center_x - cap_radius,
            center_y - cap_radius,
            center_x + cap_radius,
            center_y + cap_radius,
            fill=gauge_color,
            outline="",
        )
        canvas.create_text(
            center_x,
            center_y - radius * 0.42 - 4.0,
            text="psi",
            fill="#8b96a3",
            font=hud_fixed_font("Consolas", max(5, int((x1 - x0) * 0.083)), "bold"),
            anchor="center",
        )
        canvas.create_text(
            center_x,
            center_y + 23.0,
            text=f"{boost:.0f}",
            fill=value_color,
            font=hud_fixed_font("Consolas", max(5, int((x1 - x0) * 0.105)), "bold"),
            anchor="center",
        )

    @staticmethod
    def boost_display_positive_max(peak: float) -> float:
        if peak <= 0.0:
            return 0.0
        return max(1.0, peak)

    @staticmethod
    def engine_hud_should_show_boost_meter(peak: float, current_boost: float) -> bool:
        return max(peak, current_boost) >= 1.0

    def smoothed_engine_hud_boost(self, car_ordinal: int, boost: float) -> float:
        key = car_ordinal if car_ordinal > 0 else 0
        previous = self.engine_hud_boost_display_by_car.get(key)
        if previous is None or abs(boost - previous) > 35.0:
            smoothed = boost
        else:
            alpha = 0.35 if abs(boost) > abs(previous) else 0.20
            smoothed = previous + (boost - previous) * alpha
        self.engine_hud_boost_display_by_car[key] = smoothed
        return smoothed

    def smoothed_engine_hud_torque(self, car_ordinal: int, torque: float) -> float:
        key = car_ordinal if car_ordinal > 0 else 0
        previous = self.engine_hud_torque_display_by_car.get(key)
        if previous is None or abs(torque - previous) > 2000.0:
            smoothed = torque
        else:
            alpha = 0.35 if abs(torque) > abs(previous) else 0.20
            smoothed = previous + (torque - previous) * alpha
        self.engine_hud_torque_display_by_car[key] = smoothed
        return smoothed

    def draw_vacuum_meter(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        boost: float,
    ) -> None:
        vacuum_min = -15.0
        vacuum_psi = max(vacuum_min, min(0.0, boost))
        vacuum_ratio = max(0.0, min(1.0, (vacuum_psi - vacuum_min) / abs(vacuum_min)))
        start_angle = 210.0
        max_angle = 360.0
        arc_start = 240.0
        sweep_degrees = 150.0
        center_x, center_y, radius, _inner_radius = self.draw_engine_meter_shell(
            canvas,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(start_angle, max_angle),
        )
        track_radius = radius * 0.86
        track_width = hud_px(3)
        track_box = (
            center_x - track_radius,
            center_y - track_radius,
            center_x + track_radius,
            center_y + track_radius,
        )
        gauge_color = "#2f5e73"
        value_color = "#2ea8ff"
        active_extent = -sweep_degrees * vacuum_ratio
        canvas.create_arc(*track_box, start=arc_start, extent=-sweep_degrees, style=tk.ARC, outline="#252c35", width=track_width)
        if abs(active_extent) >= 3.0:
            canvas.create_arc(
                *track_box,
                start=arc_start,
                extent=active_extent,
                style=tk.ARC,
                outline=gauge_color,
                width=track_width,
            )
        needle_angle = start_angle + sweep_degrees * vacuum_ratio
        radians = math.radians(needle_angle)
        needle_outer = radius * 0.68
        trail_inner = cap_radius = max(2.0, radius * 0.07)
        self.engine_hud_vacuum_needle_angles.append(needle_angle)
        self.draw_engine_needle_motion_blur(
            canvas,
            center_x,
            center_y,
            trail_inner,
            needle_outer,
            list(self.engine_hud_vacuum_needle_angles),
            ("#173542", "#234f63", gauge_color),
        )
        canvas.create_line(
            center_x,
            center_y,
            center_x + math.sin(radians) * needle_outer,
            center_y - math.cos(radians) * needle_outer,
            fill=gauge_color,
            width=hud_px(3),
        )
        canvas.create_oval(
            center_x - cap_radius,
            center_y - cap_radius,
            center_x + cap_radius,
            center_y + cap_radius,
            fill=gauge_color,
            outline="",
        )
        canvas.create_text(
            center_x,
            center_y - radius * 0.42 - 4.0,
            text="psi",
            fill="#8b96a3",
            font=hud_fixed_font("Consolas", max(4, int((x1 - x0) * 0.075)), "bold"),
            anchor="center",
        )
        canvas.create_text(
            center_x + radius * 0.38 + hud_px(22),
            center_y + radius * 0.05 - hud_px(3, minimum=0),
            text=f"{vacuum_psi:.0f}",
            fill=value_color,
            font=hud_fixed_font("Consolas", max(5, int((x1 - x0) * 0.105)), "bold"),
            anchor="e",
        )

    @staticmethod
    def draw_engine_needle_motion_blur(
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angles: list[float],
        blur_colors: tuple[str, str, str],
    ) -> None:
        if len(angles) < 2:
            return
        segments = list(zip(angles[:-1], angles[1:]))[-len(blur_colors):]
        color_offset = len(blur_colors) - len(segments)
        for index, (previous_angle, current_angle) in enumerate(segments):
            delta = current_angle - previous_angle
            if abs(delta) < 0.35:
                continue
            if abs(delta) > 42.0:
                previous_angle = current_angle - math.copysign(42.0, delta)
                delta = current_angle - previous_angle
            steps = max(2, min(10, int(abs(delta) / 4.0) + 2))
            outer_points: list[tuple[float, float]] = []
            inner_points: list[tuple[float, float]] = []
            for step in range(steps + 1):
                angle = previous_angle + delta * step / steps
                radians = math.radians(angle)
                outer_points.append((
                    center_x + math.sin(radians) * needle_outer,
                    center_y - math.cos(radians) * needle_outer,
                ))
                inner_points.append((
                    center_x + math.sin(radians) * needle_inner,
                    center_y - math.cos(radians) * needle_inner,
                ))
            points: list[float] = []
            for point in outer_points:
                points.extend(point)
            for point in reversed(inner_points):
                points.extend(point)
            canvas.create_polygon(points, fill=blur_colors[color_offset + index], outline="")

    def draw_hud_rpm_gauge(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        raw = self.latest_raw or {}
        raw_rpm = max(0.0, float(raw.get("rpm", 0.0)))
        max_rpm = max(1.0, float(raw.get("max_rpm", 0.0)))
        idle_rpm = max(0.0, float(raw.get("idle_rpm", 0.0)))
        gear = int(raw.get("gear", 0)) if raw else 0
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        rpm = self.stable_rpm_hud_value(raw_rpm, idle_rpm, speed_kmh, bool(raw.get("on", False)))
        display_max_rpm = self.rpm_display_max_rpm(max_rpm)
        ratio = max(0.0, min(1.0, rpm / display_max_rpm))
        shift_start_ratio = max(0.0, min(1.0, (max_rpm * 0.85) / display_max_rpm))
        red_start_ratio = max(shift_start_ratio, min(1.0, (max_rpm * 0.96) / display_max_rpm))
        red_end_ratio = 1.0
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        outer_pad = 2.0
        outer_x0 = center_x - diameter / 2.0 + outer_pad
        outer_y0 = center_y - diameter / 2.0 + outer_pad
        outer_x1 = center_x + diameter / 2.0 - outer_pad
        outer_y1 = center_y + diameter / 2.0 - outer_pad
        outer_radius = (outer_x1 - outer_x0) / 2.0
        inner_radius = outer_radius * 0.48
        line_width = hud_px(1)
        canvas.create_oval(outer_x0, outer_y0, outer_x1, outer_y1, fill="#151a20", outline="#252c35", width=line_width)
        self.draw_rpm_active_range_zone(canvas, center_x, center_y, outer_radius, shift_start_ratio)
        self.draw_rpm_shift_zone(canvas, outer_x0, outer_y0, outer_x1, outer_y1, shift_start_ratio, red_start_ratio)
        self.draw_rpm_red_zone(canvas, outer_x0, outer_y0, outer_x1, outer_y1, red_start_ratio, red_end_ratio)
        self.draw_rpm_sweep_design_line(canvas, center_x, center_y, outer_radius, inner_radius)
        self.draw_rpm_ticks(canvas, center_x, center_y, outer_radius, display_max_rpm)
        needle_angle = self.rpm_angle_degrees(ratio)
        needle_inner = max(0.0, inner_radius * 0.68 - hud_px(5))
        needle_outer = outer_radius * 0.92
        canvas.create_oval(
            center_x - inner_radius,
            center_y - inner_radius,
            center_x + inner_radius,
            center_y + inner_radius,
            fill="#050607",
            outline="#252c35",
            width=line_width,
        )
        self.rpm_hud_needle_angles.append(needle_angle)
        recent_angles = list(self.rpm_hud_needle_angles)
        self.draw_rpm_needle_motion_blur(canvas, center_x, center_y, inner_radius, needle_outer, recent_angles)
        self.draw_rpm_needle(
            canvas,
            center_x,
            center_y,
            needle_inner,
            needle_outer,
            needle_angle,
            "#f1c40f",
            hud_px(4),
        )
        self.draw_outlined_text(
            canvas,
            center_x,
            center_y,
            self.format_gear_for_hud(gear),
            hud_font("Consolas", max(18, int(outer_radius * 0.38)), "bold"),
            self.rpm_gear_color(rpm, max_rpm, idle_rpm),
            "#11161c",
            thickness=hud_px(2),
        )
        self.draw_rpm_speed_text(canvas, center_x, center_y, outer_radius, speed_kmh, unit="km")

    def stable_rpm_hud_value(self, rpm: float, idle_rpm: float, speed_kmh: float, is_on: bool) -> float:
        previous = self.rpm_hud_display_rpm
        if previous is None:
            self.rpm_hud_display_rpm = rpm
            return rpm

        idle_floor = max(450.0, idle_rpm * 0.55)
        if is_on and speed_kmh > 1.0 and rpm <= 100.0 and previous > idle_floor:
            self.rpm_hud_zero_dropouts += 1
            if self.rpm_hud_zero_dropouts <= 2:
                return previous
        else:
            self.rpm_hud_zero_dropouts = 0

        if abs(rpm - previous) > 6000.0:
            smoothed = rpm
        else:
            alpha = 0.45 if rpm > previous else 0.30
            smoothed = previous + (rpm - previous) * alpha
        self.rpm_hud_display_rpm = smoothed
        return smoothed

    def draw_rpm_needle_motion_blur(
        self,
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angles: list[float],
    ) -> None:
        if len(angles) < 2:
            return
        blur_colors = ("#3a3008", "#5c4a0b", "#f1c40f")
        segments = list(zip(angles[:-1], angles[1:]))[-len(blur_colors):]
        color_offset = len(blur_colors) - len(segments)
        for index, (previous_angle, current_angle) in enumerate(segments):
            delta = current_angle - previous_angle
            if abs(delta) < 0.35:
                continue
            if abs(delta) > 42.0:
                previous_angle = current_angle - math.copysign(42.0, delta)
                delta = current_angle - previous_angle
            steps = max(2, min(10, int(abs(delta) / 4.0) + 2))
            outer_points: list[tuple[float, float]] = []
            inner_points: list[tuple[float, float]] = []
            for step in range(steps + 1):
                angle = previous_angle + delta * step / steps
                radians = math.radians(angle)
                outer_points.append((
                    center_x + math.cos(radians) * needle_outer,
                    center_y - math.sin(radians) * needle_outer,
                ))
                inner_points.append((
                    center_x + math.cos(radians) * needle_inner,
                    center_y - math.sin(radians) * needle_inner,
                ))
            points: list[float] = []
            for point in outer_points:
                points.extend(point)
            for point in reversed(inner_points):
                points.extend(point)
            canvas.create_polygon(points, fill=blur_colors[color_offset + index], outline="")

    @staticmethod
    def draw_rpm_needle(
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angle: float,
        color: str,
        width: int,
    ) -> None:
        radians = math.radians(angle)
        canvas.create_line(
            center_x + math.cos(radians) * needle_inner,
            center_y - math.sin(radians) * needle_inner,
            center_x + math.cos(radians) * needle_outer,
            center_y - math.sin(radians) * needle_outer,
            fill=color,
            width=width,
        )

    @staticmethod
    def rpm_angle_degrees(ratio: float) -> float:
        return 240.0 - max(0.0, min(1.0, ratio)) * 240.0

    @staticmethod
    def rpm_display_max_rpm(max_rpm: float) -> float:
        if max_rpm <= 1000.0:
            return 1000.0
        return max(1000.0, math.ceil(max_rpm / 1000.0) * 1000.0)

    def draw_rpm_red_zone(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        start_ratio: float,
        end_ratio: float,
    ) -> None:
        if end_ratio <= start_ratio:
            return
        start_angle = self.rpm_angle_degrees(start_ratio)
        end_angle = self.rpm_angle_degrees(end_ratio) - 7.0
        canvas.create_arc(
            x0,
            y0,
            x1,
            y1,
            start=start_angle,
            extent=end_angle - start_angle,
            style=tk.PIESLICE,
            fill="#8C0437",
            outline="",
        )

    def draw_rpm_shift_zone(
        self,
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        start_ratio: float,
        end_ratio: float,
    ) -> None:
        if end_ratio <= start_ratio:
            return
        start_angle = self.rpm_angle_degrees(start_ratio)
        end_angle = self.rpm_angle_degrees(end_ratio)
        canvas.create_arc(
            x0,
            y0,
            x1,
            y1,
            start=start_angle,
            extent=end_angle - start_angle,
            style=tk.PIESLICE,
            fill="#805200",
            outline="",
        )

    def draw_rpm_active_range_zone(
        self,
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        outer_radius: float,
        red_start_ratio: float,
    ) -> None:
        start_angle = self.rpm_angle_degrees(0.0) + 5.0
        end_angle = self.rpm_angle_degrees(red_start_ratio)
        inner_radius = outer_radius * 0.86
        outer_radians = [
            math.radians(start_angle + (end_angle - start_angle) * step / 36.0)
            for step in range(37)
        ]
        inner_radians = list(reversed(outer_radians))
        points: list[float] = []
        for radians in outer_radians:
            points.extend((
                center_x + math.cos(radians) * outer_radius,
                center_y - math.sin(radians) * outer_radius,
            ))
        for radians in inner_radians:
            points.extend((
                center_x + math.cos(radians) * inner_radius,
                center_y - math.sin(radians) * inner_radius,
            ))
        canvas.create_polygon(points, fill="#20272f", outline="")

    def draw_rpm_sweep_design_line(
        self,
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
    ) -> None:
        radius = inner_radius + (outer_radius - inner_radius) * 0.27
        canvas.create_arc(
            center_x - radius,
            center_y - radius,
            center_x + radius,
            center_y + radius,
            start=0,
            extent=240,
            style=tk.ARC,
            outline="#252c35",
            width=hud_px(1),
        )

    def draw_rpm_ticks(
        self,
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        radius: float,
        display_max_rpm: float,
    ) -> None:
        if display_max_rpm <= 1.0:
            return
        max_tick = int(display_max_rpm // 1000) * 1000
        ticks = list(range(0, max_tick + 1, 1000))
        for tick_rpm in ticks:
            ratio = max(0.0, min(1.0, tick_rpm / display_max_rpm))
            angle = self.rpm_angle_degrees(ratio)
            radians = math.radians(angle)
            tick_outer = radius * 0.97
            tick_inner = radius * 0.88
            canvas.create_line(
                center_x + math.cos(radians) * tick_inner,
                center_y - math.sin(radians) * tick_inner,
                center_x + math.cos(radians) * tick_outer,
                center_y - math.sin(radians) * tick_outer,
                fill="#eef3f4",
                width=hud_px(1),
            )
            label_radius = radius * 0.80
            label = str(int(tick_rpm / 1000.0))
            canvas.create_text(
                center_x + math.cos(radians) * label_radius,
                center_y - math.sin(radians) * label_radius,
                text=label,
                fill="#eef3f4",
                font=hud_fixed_font("Consolas", 8, "bold"),
                anchor="center",
            )

    @staticmethod
    def format_gear_for_hud(gear: int) -> str:
        if gear == 0:
            return "R"
        if gear == 11:
            return "-"
        return str(max(0, gear))

    @staticmethod
    def rpm_gear_color(rpm: float, max_rpm: float, idle_rpm: float) -> str:
        ratio = max(0.0, min(1.0, rpm / max(max_rpm, 1.0)))
        low_limit = max(0.22, min(0.36, (idle_rpm / max(max_rpm, 1.0)) + 0.11))
        if ratio >= 0.85:
            return "#f1c40f"
        if ratio <= low_limit:
            return "#2ea8ff"
        return "#eef3f4"

    def draw_rpm_speed_text(
        self,
        canvas: tk.Canvas,
        center_x: float,
        center_y: float,
        radius: float,
        speed_kmh: float,
        unit: str = "km",
    ) -> None:
        speed_value = self.convert_hud_speed(speed_kmh, unit)
        speed_text = str(max(0, min(999, int(round(speed_value)))))
        x_ratio = self.clamp_float(float(self.settings.get("rpm_hud_speed_x_ratio", 0.61)), 0.20, 1.10)
        y_ratio = self.clamp_float(float(self.settings.get("rpm_hud_speed_y_ratio", 0.82)), 0.20, 1.10)
        x = center_x + radius * x_ratio - hud_px(7)
        y = center_y + radius * y_ratio + hud_px(3)
        unit_x_offset = self.clamp_float(float(self.settings.get("rpm_hud_speed_unit_x_offset", 0.0)), -0.50, 0.50)
        unit_y_offset = self.clamp_float(float(self.settings.get("rpm_hud_speed_unit_y_offset", -0.31)), -0.80, 0.20)
        canvas.create_text(
            x + radius * unit_x_offset,
            y + radius * unit_y_offset,
            text=self.hud_speed_unit_label(unit),
            fill="#9aa4af",
            font=hud_fixed_font("Consolas", 7, "bold"),
            anchor="se",
        )
        canvas.create_text(
            x,
            y,
            text=speed_text,
            fill="#eef3f4",
            font=hud_font("Consolas", max(13, int(radius * 0.245)), "bold"),
            anchor="se",
        )

    @staticmethod
    def convert_hud_speed(speed_kmh: float, unit: str) -> float:
        if unit == "mph":
            return speed_kmh * 0.621371
        return speed_kmh

    @staticmethod
    def hud_speed_unit_label(unit: str) -> str:
        return "mph" if unit == "mph" else "km"

    @staticmethod
    def draw_outlined_text(
        canvas: tk.Canvas,
        x: float,
        y: float,
        text: str,
        font: tuple,
        fill: str,
        outline: str,
        thickness: int = 1,
    ) -> None:
        offsets = []
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy <= thickness * thickness:
                    offsets.append((dx, dy))
        for dx, dy in offsets:
            canvas.create_text(x + dx, y + dy, text=text, fill=outline, font=font, anchor="center")
        canvas.create_text(x, y, text=text, fill=fill, font=font, anchor="center")

    def draw_hud_tire(self, canvas: tk.Canvas, side: str, x0: float, y0: float, x1: float, y1: float) -> None:
        raw = self.latest_raw or {}
        temp_f = float(raw.get(f"tire_temp_{side}", 0.0))
        temp_c = (temp_f - 32.0) * (5.0 / 9.0) if temp_f > 0.0 else 0.0
        slip = abs(float(raw.get(f"tire_combined_slip_{side}", 0.0)))
        temp_colors = self.tire_temperature_segment_colors(raw, side, temp_f)
        display_colors = (
            (temp_colors["outer"], temp_colors["center"], temp_colors["inner"])
            if side in ("fl", "rl")
            else (temp_colors["inner"], temp_colors["center"], temp_colors["outer"])
        )
        notch = max(4.0, min(x1 - x0, y1 - y0) * 0.15)
        self.create_pixel_cut_tire_segments(canvas, x0, y0, x1, y1, notch, display_colors)

        slip_level = max(0.0, min(1.0, slip / 2.0))
        if slip_level > 0.015:
            slip_y = y1 - (y1 - y0) * slip_level
            self.create_pixel_cut_tire_fill(canvas, x0, slip_y, x1, y1, notch, "#a84800", tire_top=y0)
        self.create_pixel_cut_tire_outline(canvas, x0, y0, x1, y1, notch, "#252c35")
        third = (x1 - x0) / 3.0
        for line_x in (x0 + third, x0 + third * 2.0):
            canvas.create_line(line_x, y0 + 1, line_x, y1 - 1, fill="#252c35", width=hud_px(1))

        font_size = max(9, min(18, int((y1 - y0) * 0.21)))
        temp_text = "--" if temp_f <= 0.0 else f"{temp_c:.0f}"
        canvas.create_text(
            (x0 + x1) / 2.0,
            y0 + (y1 - y0) * 0.28,
            text=temp_text,
            fill="#eef3f4",
            font=hud_font("Consolas", font_size, "bold"),
            anchor="center",
        )

    def tire_temperature_segment_colors(self, raw: dict[str, float | int | bool], side: str, fallback_f: float) -> dict[str, str]:
        temperatures = {}
        for segment in ("inner", "center", "outer"):
            temp_f = self.read_optional_tire_temperature(raw, side, segment, fallback_f)
            temp_c = (temp_f - 32.0) * (5.0 / 9.0) if temp_f > 0.0 else 0.0
            temperatures[segment] = self.tire_temperature_color(temp_c)
        return temperatures

    @staticmethod
    def read_optional_tire_temperature(
        raw: dict[str, float | int | bool],
        side: str,
        segment: str,
        fallback_f: float,
    ) -> float:
        candidates = (
            f"tire_temp_{segment}_{side}",
            f"tire_temp_{side}_{segment}",
            f"tire_{segment}_temp_{side}",
            f"tire_{side}_temp_{segment}",
        )
        for key in candidates:
            if key in raw:
                return float(raw.get(key, fallback_f))
        return fallback_f

    @staticmethod
    def create_pixel_cut_tire_segments(
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        notch: float,
        fills: tuple[str, str, str],
    ) -> None:
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
        third = (x1 - x0) / 3.0
        first_x1 = x0 + third
        second_x0 = first_x1
        second_x1 = x0 + third * 2.0
        third_x0 = second_x1
        left_points = (
            x0 + notch, y0,
            first_x1, y0,
            first_x1, y1,
            x0 + notch, y1,
            x0 + notch, y1 - notch,
            x0, y1 - notch,
            x0, y0 + notch,
            x0 + notch, y0 + notch,
        )
        center_points = (
            second_x0, y0,
            second_x1, y0,
            second_x1, y1,
            second_x0, y1,
        )
        right_points = (
            third_x0, y0,
            x1 - notch, y0,
            x1 - notch, y0 + notch,
            x1, y0 + notch,
            x1, y1 - notch,
            x1 - notch, y1 - notch,
            x1 - notch, y1,
            third_x0, y1,
        )
        canvas.create_polygon(left_points, fill=fills[0], outline="")
        canvas.create_polygon(center_points, fill=fills[1], outline="")
        canvas.create_polygon(right_points, fill=fills[2], outline="")

    @staticmethod
    def create_pixel_cut_tire_outline(
        canvas: tk.Canvas,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        notch: float,
        outline: str,
    ) -> None:
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
        points = (
            x0 + notch, y0,
            x1 - notch, y0,
            x1 - notch, y0 + notch,
            x1, y0 + notch,
            x1, y1 - notch,
            x1 - notch, y1 - notch,
            x1 - notch, y1,
            x0 + notch, y1,
            x0 + notch, y1 - notch,
            x0, y1 - notch,
            x0, y0 + notch,
            x0 + notch, y0 + notch,
            x0 + notch, y0,
        )
        canvas.create_line(*points, fill=outline, width=hud_px(1))

    @staticmethod
    def create_pixel_cut_tire_fill(
        canvas: tk.Canvas,
        x0: float,
        fill_y0: float,
        x1: float,
        y1: float,
        notch: float,
        fill: str,
        tire_top: float | None = None,
    ) -> None:
        tire_y0 = fill_y0 if tire_top is None else tire_top
        fill_y0 = max(tire_y0, min(y1, fill_y0))
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - tire_y0) / 2.0))
        if fill_y0 <= tire_y0:
            points = (
                x0 + notch, tire_y0,
                x1 - notch, tire_y0,
                x1 - notch, tire_y0 + notch,
                x1, tire_y0 + notch,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
                x0, tire_y0 + notch,
                x0 + notch, tire_y0 + notch,
            )
        elif fill_y0 < tire_y0 + notch:
            points = (
                x0 + notch, fill_y0,
                x1 - notch, fill_y0,
                x1 - notch, tire_y0 + notch,
                x1, tire_y0 + notch,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
                x0, tire_y0 + notch,
                x0 + notch, tire_y0 + notch,
            )
        elif fill_y0 <= y1 - notch:
            points = (
                x0, fill_y0,
                x1, fill_y0,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
            )
        else:
            points = (
                x0 + notch, fill_y0,
                x1 - notch, fill_y0,
                x1 - notch, y1,
                x0 + notch, y1,
            )
        canvas.create_polygon(points, fill=fill, outline="")

    @staticmethod
    def mix_hex_color(start: str, end: str, amount: float) -> str:
        amount = max(0.0, min(1.0, amount))
        sr, sg, sb = int(start[1:3], 16), int(start[3:5], 16), int(start[5:7], 16)
        er, eg, eb = int(end[1:3], 16), int(end[3:5], 16), int(end[5:7], 16)
        r = int(sr + (er - sr) * amount)
        g = int(sg + (eg - sg) * amount)
        b = int(sb + (eb - sb) * amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    def tire_temperature_color(self, temp_c: float) -> str:
        stops = (
            (20.0, "#151a20"),
            (55.0, "#004548"),
            (95.0, "#4f8700"),
            (140.0, "#b8ad00"),
        )
        if temp_c <= stops[0][0]:
            return stops[0][1]
        for index in range(1, len(stops)):
            low_temp, low_color = stops[index - 1]
            high_temp, high_color = stops[index]
            if temp_c <= high_temp:
                mix = self.smoothstep(low_temp, high_temp, temp_c)
                return self.mix_hex_color(low_color, high_color, mix)
        return stops[-1][1]

    @staticmethod
    def draw_hud_split_bar(
        canvas: tk.Canvas,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        level: float,
        recommended: float,
        base_color: str,
    ) -> None:
        level = max(0.0, min(1.0, level))
        recommended = max(0.0, min(1.0, recommended))
        canvas.create_rectangle(x0, y0, x1, y1, fill="#151a20", outline="")
        height = y1 - y0
        base_level = level if level <= recommended else recommended
        if base_level > 0.0:
            base_top = y1 - height * base_level
            canvas.create_rectangle(x0, base_top, x1, y1, fill=base_color, outline="")
        if level > recommended:
            yellow_top = y1 - height * level
            yellow_bottom = y1 - height * recommended
            canvas.create_rectangle(x0, yellow_top, x1, yellow_bottom, fill="#AD8300", outline="")
            boundary_width = max(2, hud_px(2))
            canvas.create_line(
                x0 + 1,
                yellow_bottom,
                x1 - 1,
                yellow_bottom,
                fill="#eef3f4",
                width=boundary_width,
            )
        center_y = y0 + height * 0.5
        right = x1 - 1
        bottom = y1 - 1
        line_width = hud_px(1)
        canvas.create_line(x0, center_y, right, center_y, fill="#252c35", width=line_width)
        canvas.create_line(x0, y0, right, y0, right, bottom, x0, bottom, x0, y0, fill="#252c35", width=line_width)

    @staticmethod
    def draw_hud_throttle_bar(
        canvas: tk.Canvas,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        throttle: float,
        recommended: float,
    ) -> None:
        TelemetryApp.draw_hud_split_bar(canvas, x0, y0, x1, y1, throttle, recommended, "#13AC96")

    def draw_hud_gforce_box(self, canvas: tk.Canvas, x0: int, y0: int, x1: int, y1: int) -> None:
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        outer_pad = 2.0
        outer_x0 = center_x - diameter / 2.0 + outer_pad
        outer_y0 = center_y - diameter / 2.0 + outer_pad
        outer_x1 = center_x + diameter / 2.0 - outer_pad
        outer_y1 = center_y + diameter / 2.0 - outer_pad
        outer_radius = (outer_x1 - outer_x0) / 2.0
        inner_radius = outer_radius * 0.5
        line_width = hud_px(1)
        canvas.create_oval(outer_x0, outer_y0, outer_x1, outer_y1, fill="#151a20", outline="#252c35", width=line_width)
        self.draw_hud_slip_angle_arc(canvas, outer_x0, outer_y0, outer_x1, outer_y1)
        self.draw_hud_slip_angle_text(canvas, outer_x0, outer_y0, outer_x1, outer_y1)
        canvas.create_oval(
            center_x - inner_radius,
            center_y - inner_radius,
            center_x + inner_radius,
            center_y + inner_radius,
            fill="#151a20",
            outline="#252c35",
            width=line_width,
        )
        canvas.create_line(center_x, center_y - outer_radius, center_x, center_y + outer_radius, fill="#252c35", width=line_width)
        canvas.create_line(center_x - outer_radius, center_y, center_x + outer_radius, center_y, fill="#252c35", width=line_width)

        point_data = self.current_hud_gforce_point(outer_x0, outer_y0, outer_x1, outer_y1)
        if point_data is None:
            self.hud_gforce_points.clear()
            self.hud_gforce_previous_vector = None
            return
        point, g_vector = point_data
        self.update_hud_gforce_impact_markers(point, g_vector)
        self.draw_hud_gforce_impact_markers(canvas)
        self.hud_gforce_points.append(point)
        canvas.create_line(center_x, center_y, point[0], point[1], fill="#b89512", width=hud_px(3))
        colors = ("#3a3008", "#5c4a0b", "#9b7d0d", "#f1c40f")
        points = list(self.hud_gforce_points)
        start_color = len(colors) - len(points)
        for index, (px, py) in enumerate(points):
            color = colors[start_color + index]
            radius = hud_px(3) if index < len(points) - 1 else hud_px(4)
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill=color, outline="")

    def current_hud_gforce_point(self, x0: int, y0: int, x1: int, y1: int) -> tuple[tuple[float, float], tuple[float, float]] | None:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return None
        lateral_g = float(raw.get("accel_x", 0.0)) / 9.80665
        longitudinal_g = -float(raw.get("accel_z", 0.0)) / 9.80665
        max_g = 2.0
        x_ratio = max(-1.0, min(1.0, lateral_g / max_g))
        y_ratio = max(-1.0, min(1.0, longitudinal_g / max_g))
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        radius = max(1.0, min(x1 - x0, y1 - y0) / 2.0 - 7.0)
        return (center_x + x_ratio * radius, center_y - y_ratio * radius), (lateral_g, longitudinal_g)

    def draw_hud_slip_angle_arc(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        slip_angle = self.current_hud_slip_angle_degrees()
        if abs(slip_angle) < 0.4:
            return
        display_angle = max(-175.0, min(175.0, slip_angle))
        color = "#7f332f" if display_angle < 0.0 else "#2f5e73"
        edge_color = "#d45a50" if display_angle < 0.0 else "#4aa4c7"
        extent = abs(display_angle)
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        outer_radius = max(1.0, (x1 - x0) / 2.0)
        inner_radius = outer_radius * 0.5
        edge_angle = 90.0 + extent if display_angle < 0.0 else 90.0 - extent
        edge_radians = math.radians(edge_angle)
        edge_inner_x = center_x + math.cos(edge_radians) * inner_radius
        edge_inner_y = center_y - math.sin(edge_radians) * inner_radius
        edge_outer_x = center_x + math.cos(edge_radians) * outer_radius
        edge_outer_y = center_y - math.sin(edge_radians) * outer_radius
        if display_angle < 0.0:
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=extent, style=tk.PIESLICE, fill=color, outline="")
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=extent, style=tk.ARC, outline=edge_color, width=hud_px(1))
        else:
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=-extent, style=tk.PIESLICE, fill=color, outline="")
            canvas.create_arc(x0, y0, x1, y1, start=90, extent=-extent, style=tk.ARC, outline=edge_color, width=hud_px(1))
        canvas.create_line(edge_inner_x, edge_inner_y, edge_outer_x, edge_outer_y, fill=edge_color, width=hud_px(1))

    def draw_hud_slip_angle_text(self, canvas: tk.Canvas, x0: float, y0: float, x1: float, y1: float) -> None:
        slip_angle = self.current_hud_slip_angle_value()
        inactive_color = "#5f6872"
        left_color = "#7f332f" if slip_angle < -0.025 else inactive_color
        right_color = "#2f5e73" if slip_angle > 0.025 else inactive_color
        left_text = f"{slip_angle:.2f}" if slip_angle < -0.025 else "-0.00"
        right_text = f"+{slip_angle:.2f}" if slip_angle > 0.025 else "+0.00"
        canvas.create_text(
            x0 + 4,
            y0 + 3,
            text=left_text,
            fill=left_color,
            font=hud_fixed_font("Consolas", 9, "bold"),
            anchor="nw",
        )
        canvas.create_text(
            x1 - 4,
            y0 + 3,
            text=right_text,
            fill=right_color,
            font=hud_fixed_font("Consolas", 9, "bold"),
            anchor="ne",
        )

    def current_hud_slip_angle_degrees(self) -> float:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return 0.0
        return self.hud_slip_angle_degrees(raw)

    def current_hud_slip_angle_value(self) -> float:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return 0.0
        return self.hud_slip_angle_value(raw)

    @staticmethod
    def hud_slip_angle_value(raw: dict[str, float | int | bool]) -> float:
        speed = float(raw.get("speed_kmh", 0.0))
        if speed < 3.0:
            return 0.0
        tire_slip_angle = (
            float(raw.get("tire_slip_angle_fl", 0.0))
            + float(raw.get("tire_slip_angle_fr", 0.0))
            + float(raw.get("tire_slip_angle_rl", 0.0))
            + float(raw.get("tire_slip_angle_rr", 0.0))
        ) * 0.25
        if abs(tire_slip_angle) < 0.025:
            return 0.0
        return -tire_slip_angle

    @staticmethod
    def hud_slip_angle_degrees(raw: dict[str, float | int | bool]) -> float:
        # Forza exports normalized tire slip angle, not degrees. Scale it into
        # the HUD's visual angle units so |1.0| appears near 20 on the gauge.
        return TelemetryApp.hud_slip_angle_value(raw) * 20.0

    def update_hud_gforce_impact_markers(self, point: tuple[float, float], g_vector: tuple[float, float]) -> None:
        previous = self.hud_gforce_previous_vector
        self.hud_gforce_previous_vector = g_vector
        if previous is None:
            return
        delta_x = g_vector[0] - previous[0]
        delta_y = g_vector[1] - previous[1]
        delta_g = math.sqrt(delta_x * delta_x + delta_y * delta_y)
        if delta_g >= 0.75:
            self.hud_gforce_impact_markers.append((point[0], point[1], time.monotonic()))

    def draw_hud_gforce_impact_markers(self, canvas: tk.Canvas) -> None:
        now = time.monotonic()
        keep_seconds = 0.90
        while self.hud_gforce_impact_markers and now - self.hud_gforce_impact_markers[0][2] > keep_seconds:
            self.hud_gforce_impact_markers.popleft()
        for px, py, created_at in self.hud_gforce_impact_markers:
            age = max(0.0, min(1.0, (now - created_at) / keep_seconds))
            radius = hud_px(6 - age * 2.0)
            color = "#e74c3c" if age < 0.45 else "#8f2c2c"
            canvas.create_oval(px - radius, py - radius, px + radius, py + radius, fill=color, outline="")

    def hud_recommended_brake(self, brake: float) -> float:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return brake
        brake = max(0.0, min(1.0, brake))
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        if brake < 0.03 or speed_kmh < 8.0:
            return brake

        slip_threshold = 1.4
        for trigger_name in (
            TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
            TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
            TRIGGER_BRAKE_RESISTANCE,
        ):
            controls_state = self.trigger_controls.get(trigger_name)
            if controls_state and "slip_threshold" in controls_state:
                slip_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
                break

        front_ratio, front_combined = self.brake_slip_off_values(raw)
        ratio_start = max(0.06, slip_threshold * 0.22)
        ratio_risk = self.smoothstep(ratio_start, slip_threshold, front_ratio)
        combined_risk = self.smoothstep(0.18, max(0.74, slip_threshold * 1.25), front_combined) * 0.85
        decel_g = max(0.0, -float(raw.get("accel_z", 0.0)) / 9.80665)
        brake_gate = self.smoothstep(8.0, 55.0, brake * 100.0)
        decel_gate = self.smoothstep(0.08, 0.60, decel_g)
        risk = max(ratio_risk, combined_risk) * max(brake_gate, decel_gate * 0.65)
        risk = max(0.0, min(1.0, risk))
        if risk <= 0.02:
            return brake

        severe_slip = self.smoothstep(slip_threshold, slip_threshold * 1.75, front_ratio) * 0.16
        reduction = max(0.0, min(0.72, risk * 0.46 + severe_slip))
        recommended = brake * (1.0 - reduction)
        if brake - recommended < 0.02:
            return brake
        return max(0.0, min(brake, recommended))

    def hud_recommended_throttle(self, throttle: float) -> float:
        raw = self.latest_raw
        if not raw or not bool(raw.get("on", False)):
            return throttle
        throttle = max(0.0, min(1.0, throttle))
        speed_kmh = max(0.0, float(raw.get("speed_kmh", 0.0)))
        if throttle < 0.03 or speed_kmh < 4.0:
            return throttle

        slip_threshold = 1.4
        controls_state = self.trigger_controls.get(TRIGGER_THROTTLE_TRACTION_LIMIT)
        if controls_state and "slip_threshold" in controls_state:
            slip_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)

        driven_slip, driven_combined = self.throttle_driven_slip_values(raw)
        throttle_gate = self.smoothstep(12.0, 60.0, throttle * 100.0)
        speed_gate = 1.0 - self.smoothstep(210.0, 270.0, speed_kmh)
        ratio_start = max(0.25, slip_threshold * 0.55)
        ratio_risk = self.smoothstep(ratio_start, slip_threshold, driven_slip)
        combined_risk = self.smoothstep(0.35, max(0.75, slip_threshold * 0.85), driven_combined) * 0.55
        risk = max(ratio_risk, combined_risk) * throttle_gate * speed_gate
        risk = max(0.0, min(1.0, risk))
        if risk <= 0.02:
            return throttle

        severe_slip = self.smoothstep(slip_threshold, slip_threshold * 1.80, driven_slip) * 0.15
        reduction = max(0.0, min(0.70, risk * 0.45 + severe_slip))
        recommended = throttle * (1.0 - reduction)
        if throttle - recommended < 0.02:
            return throttle
        return max(0.0, min(throttle, recommended))

    @staticmethod
    def normalized_udp_port(value, fallback: int = DEFAULT_PORT) -> int:
        try:
            numeric = int(str(value).strip())
        except (TypeError, ValueError):
            numeric = int(fallback)
        return max(1, min(65535, numeric))

    def on_udp_port_entered(self, _event=None) -> None:
        new_port = self.normalized_udp_port(self.udp_port_text.get(), self.telemetry_port)
        self.udp_port_text.set(str(new_port))
        if new_port == self.telemetry_port:
            self.settings["udp_port"] = new_port
            save_settings(self.settings)
            return
        self.restart_udp_worker(new_port)

    def restart_udp_worker(self, new_port: int) -> None:
        try:
            self.worker.stop_event.set()
            self.worker.join(timeout=0.8)
        except RuntimeError:
            pass
        self.telemetry_port = self.normalized_udp_port(new_port, DEFAULT_PORT)
        self.settings["udp_port"] = self.telemetry_port
        save_settings(self.settings)
        self.last_packet_at = 0.0
        self.udp_bind_failed = False
        self.last_error = ""
        self.worker = UDPWorker(self.telemetry_host, self.telemetry_port, self.queue)
        self.worker.start()
        self.update_udp_status("waiting")

    def update_udp_status(self, state: str) -> None:
        if not hasattr(self, "udp_status_led"):
            return
        if self.udp_visual_state == state:
            self.udp_receiving = state == "live"
            return
        was_receiving = self.udp_receiving
        self.udp_visual_state = state
        if state == "live":
            fill, outline, text = "#2ecc71", "#7ff0a4", "receiving"
        elif state == "error":
            fill, outline, text = "#e74c3c", "#ff9a91", "port error"
        elif state == "stale":
            fill, outline, text = "#e74c3c", "#ff9a91", "no packets"
        else:
            fill, outline, text = "#f1c40f", "#f7dc6f", "waiting"
        self.udp_receiving = state == "live"
        if was_receiving and not self.udp_receiving:
            self.clear_trigger_output_state(force=True)
        self.udp_status_led.itemconfigure(self.udp_status_led_id, fill=fill, outline=outline)
        self.udp_state_text.set(text)
        self.update_hud_visibility_for_udp()

    def update_hud_visibility_for_udp(self) -> None:
        hide_standby = bool(self.hud_standby_hide_enabled.get()) and not self.udp_receiving
        for hud in (
            self.hud_window,
            self.gforce_hud_window,
            self.tire_hud_window,
            self.steer_hud_window,
            self.applied_steer_hud_window,
            self.rpm_hud_window,
            self.engine_hud_window,
        ):
            if hud is None:
                continue
            try:
                if not hud.winfo_exists():
                    continue
                if hide_standby:
                    hud.withdraw()
                else:
                    hud.deiconify()
                    hud.attributes("-topmost", True)
            except tk.TclError:
                continue

    def should_draw_hud_windows(self) -> bool:
        return self.udp_receiving or not bool(self.hud_standby_hide_enabled.get())

    def save_window_state(self) -> None:
        self.root.update_idletasks()
        self.settings["window_geometry"] = self.root.geometry()
        self.settings["window_resize_unlocked"] = False
        self.settings["hud_scale_percent"] = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        self.settings["main_ui_scale_percent"] = self.normalized_main_ui_scale_percent(self.main_ui_scale_percent.get())
        self.settings["display_scale_percent"] = self.normalized_display_scale_percent(self.display_scale_percent.get())
        self.update_hud_active_settings()
        self.settings["hud_standby_hide"] = bool(self.hud_standby_hide_enabled.get())
        self.save_current_hud_geometries()
        self.settings["graph_fields"] = [var.get().strip() for var in self.graph_inputs]
        self.settings["graph_hidden"] = [bool(var.get()) for var in self.graph_hidden_vars]
        self.settings["selected_output_effect"] = self.selected_output_effect.get()
        self.settings["selected_trigger_effect"] = self.selected_trigger_effect.get()
        self.settings["selected_detail_type"] = self.selected_detail_type.get()
        self.settings["udp_port"] = self.normalized_udp_port(self.udp_port_text.get(), self.telemetry_port)
        self.settings["drift_relief_enabled"] = bool(self.drift_relief_enabled.get())
        self.settings["haptic_audio_device"] = self.haptic_audio_device_text.get().strip()
        self.save_dsx_options()
        if self.drift_debug_hud_window is not None and self.hud_window_exists(self.drift_debug_hud_window):
            self.set_hud_geometry("drift_debug_hud_geometry", self.drift_debug_hud_window.geometry())
        self.save_effect_settings()
        self.save_trigger_settings()
        save_settings(self.settings)

    def manual_save_settings(self) -> None:
        try:
            self.save_window_state()
            preset = normalized_config_preset_name(self.current_preset_name.get())
            self.save_settings_to_config_preset(preset)
        except OSError as exc:
            self.value_text.set(f"Settings save failed: {exc}")

    def show_options_window(self) -> None:
        if self.options_window is not None:
            try:
                if self.options_window.winfo_exists():
                    self.close_options_window()
                    return
            except tk.TclError:
                pass

        window = tk.Toplevel(self.root)
        window.title("Options")
        window.configure(bg="#121417")
        window.transient(self.root)
        window_width = ui_px(620)
        window_height = ui_px(470)
        window.minsize(ui_px(520), ui_px(360))
        x, y = self.popup_position_near_root(window_width, window_height, anchor="center")
        window.geometry(f"{window_width}x{window_height}+{x}+{y}")
        window.protocol("WM_DELETE_WINDOW", self.close_options_window)

        body = tk.Frame(window, bg="#121417")
        body.pack(fill="both", expand=True, padx=ui_px(14), pady=ui_px(14))
        body.grid_columnconfigure(0, weight=0)
        body.grid_columnconfigure(1, weight=1)
        body.grid_rowconfigure(1, weight=1)

        title = tk.Label(
            body,
            text="Options",
            bg="#121417",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 14, "bold"),
            anchor="w",
        )
        title.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, ui_px(12)))

        nav = tk.Frame(body, bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        nav.grid(row=1, column=0, sticky="ns", padx=(0, ui_px(12)))
        nav.grid_columnconfigure(0, weight=1)
        self.options_nav_buttons = {}

        detail = tk.Frame(body, bg="#171b20", highlightthickness=1, highlightbackground="#27313a")
        detail.grid(row=1, column=1, sticky="nsew")
        detail.grid_columnconfigure(0, weight=1)
        self.options_detail_frame = detail

        for row, (section, label) in enumerate((
            ("backup", "Backup"),
            ("port_forward", "Port Forward"),
            ("dsx_udp", "DSX UDP Bridge"),
        )):
            button = tk.Button(
                nav,
                text=label,
                command=lambda value=section: self.select_options_section(value),
                bg="#1b2027",
                fg="#d6dde5",
                activebackground="#252c35",
                activeforeground="#f1c40f",
                relief="flat",
                font=ui_font("Segoe UI", 9, "bold"),
                anchor="w",
                padx=ui_px(12),
                pady=ui_px(8),
                width=ui_px(15),
            )
            button.grid(row=row, column=0, sticky="ew", padx=ui_px(8), pady=(ui_px(8) if row == 0 else 0, 0))
            self.options_nav_buttons[section] = button

        self.options_window = window
        self.select_options_section(self.options_section.get())

    def close_options_window(self) -> None:
        window = self.options_window
        self.options_window = None
        if window is not None:
            try:
                if window.winfo_exists():
                    window.destroy()
            except tk.TclError:
                pass

    def popup_position_near_root(
        self,
        width: int,
        height: int,
        preferred_x: int | None = None,
        preferred_y: int | None = None,
        anchor: str = "pointer",
    ) -> tuple[int, int]:
        self.root.update_idletasks()
        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_w = max(1, self.root.winfo_width())
        root_h = max(1, self.root.winfo_height())
        if anchor == "center":
            x = root_x + (root_w - width) // 2
            y = root_y + (root_h - height) // 2
        else:
            x = preferred_x if preferred_x is not None else root_x + 24
            y = preferred_y if preferred_y is not None else root_y + 24
        min_x = root_x + 8
        min_y = root_y + 8
        max_x = root_x + max(8, root_w - width - 8)
        max_y = root_y + max(8, root_h - height - 8)
        return max(min_x, min(x, max_x)), max(min_y, min(y, max_y))

    def select_options_section(self, section: str) -> None:
        if section not in {"backup", "port_forward", "dsx_udp"}:
            section = "backup"
        self.options_section.set(section)
        for key, button in getattr(self, "options_nav_buttons", {}).items():
            selected = key == section
            button.configure(
                bg="#1f6feb" if selected else "#1b2027",
                fg="#ffffff" if selected else "#d6dde5",
                activebackground="#2f81f7" if selected else "#252c35",
            )
        self.render_options_section(section)

    def render_options_section(self, section: str) -> None:
        detail = getattr(self, "options_detail_frame", None)
        if detail is None:
            return
        for child in detail.winfo_children():
            child.destroy()
        if section == "backup":
            self.render_backup_options(detail)
        elif section == "port_forward":
            self.render_placeholder_options(
                detail,
                "Port Forward",
                "Forza UDP input, forwarding, and bridge ports will be configured here.",
            )
        elif section == "dsx_udp":
            self.render_dsx_udp_options(detail)

    def render_backup_options(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Backup",
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=ui_px(16), pady=(ui_px(16), ui_px(8)))
        tk.Label(
            parent,
            text=f"Restore saved settings from {SETTINGS_BACKUP_PATH.name}.",
            bg="#171b20",
            fg="#9aa4af",
            font=ui_font("Segoe UI", 9),
            anchor="w",
            justify="left",
        ).grid(row=1, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(14)))
        tk.Button(
            parent,
            text="Load Backup",
            command=self.load_settings_backup,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 9, "bold"),
            padx=ui_px(12),
            pady=ui_px(5),
        ).grid(row=2, column=0, sticky="w", padx=ui_px(16))

    def render_dsx_udp_options(self, parent: tk.Frame) -> None:
        parent.grid_columnconfigure(0, weight=1)
        tk.Label(
            parent,
            text="DSX Output",
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=ui_px(16), pady=(ui_px(16), ui_px(6)))
        tk.Label(
            parent,
            text=(
                "Send adaptive trigger commands to DSX over UDP. "
                "Audio export sends the selected source to the chosen playback device."
            ),
            bg="#171b20",
            fg="#9aa4af",
            font=ui_font("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=ui_px(390),
        ).grid(row=1, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(12)))

        toggle_row = tk.Frame(parent, bg="#171b20")
        toggle_row.grid(row=2, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(10)))
        toggle_row.grid_columnconfigure(1, weight=1)
        tk.Button(
            toggle_row,
            text="ON" if self.dsx_udp_enabled.get() else "OFF",
            command=self.toggle_dsx_udp_enabled,
            bg="#2ecc71" if self.dsx_udp_enabled.get() else "#252c35",
            fg="#ffffff" if self.dsx_udp_enabled.get() else "#d6dde5",
            activebackground="#3ae384" if self.dsx_udp_enabled.get() else "#303946",
            activeforeground="#101216" if self.dsx_udp_enabled.get() else "#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 9, "bold"),
            padx=ui_px(14),
            pady=ui_px(5),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            toggle_row,
            text="DSX Trigger UDP Bridge",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="ew", padx=(ui_px(10), 0))

        fields = tk.Frame(parent, bg="#171b20")
        fields.grid(row=3, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(10)))
        fields.grid_columnconfigure(1, weight=1)
        for row, (label, variable) in enumerate((
            ("Host", self.dsx_host_text),
            ("Port", self.dsx_port_text),
        )):
            tk.Label(
                fields,
                text=label,
                bg="#171b20",
                fg="#aeb8c4",
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="w",
            ).grid(row=row, column=0, sticky="w", pady=(0, ui_px(6)))
            entry = tk.Entry(
                fields,
                textvariable=variable,
                bg="#1b2027",
                fg="#f1c40f" if label == "Port" else "#d6dde5",
                insertbackground="#f1c40f",
                relief="flat",
                font=value_font("Consolas", 9, "bold" if label == "Port" else "normal"),
            )
            entry.grid(row=row, column=1, sticky="ew", padx=(ui_px(12), 0), pady=(0, ui_px(6)))
            entry.bind("<Return>", self.on_dsx_options_entered)
            entry.bind("<FocusOut>", self.on_dsx_options_entered)

        audio_row = tk.Frame(parent, bg="#171b20")
        audio_row.grid(row=4, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(10)))
        audio_row.grid_columnconfigure(1, weight=1)
        tk.Button(
            audio_row,
            text="ON" if self.dsx_audio_export_enabled.get() else "OFF",
            command=self.toggle_dsx_audio_export_enabled,
            bg="#2f81f7" if self.dsx_audio_export_enabled.get() else "#252c35",
            fg="#ffffff" if self.dsx_audio_export_enabled.get() else "#d6dde5",
            activebackground="#58a6ff" if self.dsx_audio_export_enabled.get() else "#303946",
            activeforeground="#101216" if self.dsx_audio_export_enabled.get() else "#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 9, "bold"),
            padx=ui_px(14),
            pady=ui_px(5),
        ).grid(row=0, column=0, sticky="w")
        tk.Label(
            audio_row,
            text="Audio Export Mode",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=1, sticky="w", padx=(ui_px(10), 0))

        self.refresh_dsx_audio_device_choices()
        audio_fields = tk.Frame(audio_row, bg="#171b20")
        audio_fields.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(ui_px(10), 0))
        audio_fields.grid_columnconfigure(1, weight=1)
        audio_fields.grid_columnconfigure(2, weight=0)
        audio_fields.grid_columnconfigure(3, weight=0)
        tk.Label(
            audio_fields,
            text="Audio Output Device",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", pady=(0, ui_px(6)))
        device_choices = self.dsx_audio_device_choices or [self.dsx_audio_device_text.get().strip() or "DualSense"]
        device_menu = tk.OptionMenu(
            audio_fields,
            self.dsx_audio_device_text,
            *device_choices,
            command=self.on_dsx_audio_device_selected,
        )
        device_menu.configure(
            bg="#1b2027",
            fg="#d6dde5",
            activebackground="#252c35",
            activeforeground="#f1c40f",
            relief="flat",
            highlightthickness=0,
            font=value_font("Consolas", 9, "bold"),
        )
        device_menu["menu"].configure(
            bg="#1b2027",
            fg="#d6dde5",
            activebackground="#252c35",
            activeforeground="#f1c40f",
            font=value_font("Consolas", 9),
        )
        device_menu.grid(row=0, column=1, sticky="ew", padx=(ui_px(12), ui_px(6)), pady=(0, ui_px(6)))
        tk.Button(
            audio_fields,
            text="Refresh",
            command=self.refresh_dsx_audio_devices_and_render,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=ui_px(8),
            pady=ui_px(4),
        ).grid(row=0, column=2, sticky="e", pady=(0, ui_px(6)))

        tk.Label(
            audio_fields,
            text="Haptic Audio Volume",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).grid(row=1, column=0, sticky="w", pady=(ui_px(4), 0))
        tk.Scale(
            audio_fields,
            from_=0,
            to=10,
            orient="horizontal",
            variable=self.dsx_audio_volume_step,
            command=self.on_dsx_audio_volume_changed,
            showvalue=False,
            bg="#f1c40f",
            fg="#d6dde5",
            troughcolor="#2a323c",
            activebackground="#f1c40f",
            highlightthickness=0,
            bd=0,
            length=ui_px(210),
            sliderlength=ui_px(18),
            sliderrelief="flat",
        ).grid(row=1, column=1, sticky="ew", padx=(ui_px(12), ui_px(6)), pady=(ui_px(4), 0))
        tk.Label(
            audio_fields,
            textvariable=self.dsx_audio_volume_text,
            bg="#1b2027",
            fg="#d6dde5",
            font=value_font("Consolas", 9, "bold"),
            width=ui_px(5),
            anchor="center",
        ).grid(row=1, column=2, sticky="e", pady=(ui_px(4), 0))
        tk.Button(
            audio_fields,
            text="Apply",
            command=self.apply_dsx_audio_volume,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=ui_px(8),
            pady=ui_px(4),
        ).grid(row=1, column=3, sticky="e", padx=(ui_px(6), 0), pady=(ui_px(4), 0))

        tk.Label(
            parent,
            textvariable=self.dsx_status_text,
            bg="#171b20",
            fg="#f1c40f" if self.dsx_udp_enabled.get() else "#9aa4af",
            font=value_font("Consolas", 9, "bold"),
            anchor="w",
        ).grid(row=6, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(12)))

    def save_dsx_options(self) -> None:
        self.settings["dsx_udp_enabled"] = bool(self.dsx_udp_enabled.get())
        self.settings["dsx_host"] = self.dsx_host_text.get().strip() or DEFAULT_DSX_HOST
        self.settings["dsx_port"] = self.normalized_udp_port(self.dsx_port_text.get(), DEFAULT_DSX_PORT)
        self.settings["dsx_audio_export_enabled"] = bool(self.dsx_audio_export_enabled.get())
        self.settings["dsx_audio_device"] = self.dsx_audio_device_text.get().strip()
        self.settings["dsx_audio_volume_percent"] = self.dsx_audio_volume_percent_value()

    def toggle_dsx_udp_enabled(self) -> None:
        self.dsx_udp_enabled.set(not bool(self.dsx_udp_enabled.get()))
        self.on_dsx_options_entered()
        if not self.dsx_udp_enabled.get():
            self.dsx_send_off()
        self.render_options_section("dsx_udp")

    def toggle_dsx_audio_export_enabled(self) -> None:
        self.dsx_audio_export_enabled.set(not bool(self.dsx_audio_export_enabled.get()))
        self.on_dsx_options_entered()
        self.render_options_section("dsx_udp")

    def on_dsx_audio_device_selected(self, _value=None) -> None:
        self.on_dsx_options_entered()

    def on_dsx_audio_volume_changed(self, value: str) -> None:
        step = self.clamp_int(value, 0, 10)
        self.dsx_audio_volume_step.set(step)
        self.dsx_audio_volume_text.set(f"{step * 10}%")
        self.on_dsx_options_entered()

    def dsx_audio_volume_percent_value(self) -> int:
        return self.clamp_int(self.dsx_audio_volume_step.get(), 0, 10) * 10

    def apply_dsx_audio_volume(self) -> None:
        percent = self.dsx_audio_volume_percent_value()
        self.dsx_audio_volume_text.set(f"{percent}%")
        self.on_dsx_options_entered()
        self.send_haptic_master_gain(percent)

    def show_haptic_device_popup(self) -> None:
        if self.haptic_device_popup is not None:
            self.close_haptic_device_popup()
            return
        width = ui_px(546)
        height = ui_px(416)
        try:
            self.root.update_idletasks()
            x = self.root.winfo_rootx() + max(0, (self.root.winfo_width() - width) // 2)
            y = self.root.winfo_rooty() + max(0, (self.root.winfo_height() - height) // 2)
        except tk.TclError:
            x, y = self.popup_position_near_root(width, height)

        popup = tk.Toplevel(self.root)
        popup.overrideredirect(True)
        popup.attributes("-topmost", True)
        popup.configure(bg="#171b20", highlightthickness=1, highlightbackground="#53606c")
        popup.geometry(f"{width}x{height}+{x}+{y}")
        body = tk.Frame(popup, bg="#171b20")
        body.pack(fill="both", expand=True, padx=ui_px(12), pady=ui_px(12))
        body.grid_columnconfigure(0, weight=1)
        body.grid_rowconfigure(2, weight=1)

        tk.Label(
            body,
            text="Select DualSense Audio Device",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 11, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            body,
            text="Select the Windows playback device that exposes DualSense haptic channels 3/4.",
            bg="#171b20",
            fg="#8b96a3",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
            wraplength=max(220, width - ui_px(28)),
        ).grid(row=1, column=0, sticky="ew", pady=(ui_px(4), ui_px(8)))

        listbox = tk.Listbox(
            body,
            bg="#1b2027",
            fg="#d6dde5",
            selectbackground="#f1c40f",
            selectforeground="#101316",
            activestyle="none",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#303946",
            font=value_font("Consolas", 9),
        )
        listbox.grid(row=2, column=0, sticky="nsew")
        listbox.insert("end", "Finding devices, please wait...")
        listbox.selection_set(0)
        self.haptic_device_listbox = listbox

        status_label = tk.Label(
            body,
            textvariable=self.haptic_device_status_text,
            bg="#171b20",
            fg="#f1c40f",
            font=ui_font("Segoe UI", 10, "bold"),
            anchor="w",
            relief="flat",
            bd=0,
            padx=ui_px(4),
            pady=ui_px(12),
            wraplength=max(220, width - ui_px(28)),
        )
        status_label.grid(row=3, column=0, sticky="ew", pady=(ui_px(8), 0))

        controls = tk.Frame(body, bg="#171b20")
        controls.grid(row=4, column=0, sticky="ew", pady=(ui_px(8), 0))
        controls.grid_columnconfigure(0, weight=1)
        tk.Button(
            controls,
            text="Test & Save",
            command=self.test_selected_haptic_device,
            bg="#1d2a3a",
            fg="#58a6ff",
            activebackground="#2f81f7",
            activeforeground="#eef6ff",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#2f81f7",
            font=ui_font("Segoe UI", 8, "bold"),
            padx=ui_px(8),
            pady=ui_px(4),
        ).grid(row=0, column=0, sticky="w")
        for text, command, column, bg, fg in (
            ("Refresh", self.refresh_haptic_device_popup, 1, "#252c35", "#d6dde5"),
            ("Save Device", self.apply_haptic_device_selection, 2, "#f1c40f", "#101316"),
            ("Cancel", self.close_haptic_device_popup, 3, "#252c35", "#d6dde5"),
        ):
            tk.Button(
                controls,
                text=text,
                command=command,
                bg=bg,
                fg=fg,
                    activebackground="#f7dc6f" if text == "Save Device" else "#303946",
                    activeforeground="#101316" if text == "Save Device" else "#f1c40f",
                relief="raised",
                bd=1,
                highlightthickness=1,
                    highlightbackground="#8a7a2a" if text == "Save Device" else "#53606c",
                font=ui_font("Segoe UI", 8, "bold"),
                padx=ui_px(8),
                pady=ui_px(4),
            ).grid(row=0, column=column, sticky="e", padx=(ui_px(6), 0))

        listbox.bind("<Double-Button-1>", lambda _event: self.apply_haptic_device_selection())
        popup.bind("<Escape>", lambda _event: self.close_haptic_device_popup())
        self.haptic_device_popup = popup
        self.haptic_device_loading = True
        self.haptic_device_status_text.set("Finding devices, please wait...")
        popup.focus_force()
        try:
            popup.update_idletasks()
            self.root.after(80, self.populate_haptic_device_popup)
        except tk.TclError:
            pass

    @staticmethod
    def sorted_haptic_audio_devices(devices: list[str]) -> list[str]:
        unique = []
        seen = set()
        for device in devices:
            name = str(device).strip()
            if not name or name in seen:
                continue
            seen.add(name)
            unique.append(name)
        return sorted(unique, key=lambda name: (0 if "dualsense" in name.lower() else 1, name.lower()))

    def populate_haptic_device_popup(self) -> None:
        listbox = self.haptic_device_listbox
        popup = self.haptic_device_popup
        if listbox is None or popup is None:
            return
        try:
            devices = self.sorted_haptic_audio_devices(self.enumerate_audio_output_devices(force=True))
            current = self.haptic_audio_device_text.get().strip()
            if current and current not in devices:
                devices.insert(0, current)
            if not devices:
                devices = ["DualSense"]
            listbox.delete(0, "end")
            for device in devices:
                listbox.insert("end", device)
            index = devices.index(current) if current and current in devices else 0
            listbox.selection_clear(0, "end")
            listbox.selection_set(index)
            listbox.see(index)
            self.haptic_device_status_text.set("")
        except tk.TclError:
            return
        finally:
            self.haptic_device_loading = False

    def refresh_haptic_device_popup(self) -> None:
        popup = self.haptic_device_popup
        if popup is not None:
            self.close_haptic_device_popup()
            self.show_haptic_device_popup()

    def selected_haptic_device_from_popup(self) -> str:
        if self.haptic_device_loading:
            return ""
        listbox = self.haptic_device_listbox
        if listbox is None:
            return ""
        selection = listbox.curselection()
        if not selection:
            return ""
        device = str(listbox.get(selection[0])).strip()
        if device == "Finding devices, please wait...":
            return ""
        return device

    def save_haptic_audio_device_selection(self, device: str) -> bool:
        if not device:
            return False
        self.haptic_audio_device_text.set(device)
        self.settings["haptic_audio_device"] = device
        self.settings["dsx_audio_device"] = device
        if self.settings.get("haptic_audio_device_verified") != device:
            self.settings.pop("haptic_audio_device_verified", None)
        self.dsx_audio_device_text.set(device)
        save_settings(self.settings, make_backup=True, force=True)
        self.update_save_button_state()
        self.update_preset_lock_state()
        return True

    def apply_haptic_device_selection(self) -> None:
        if self.haptic_device_loading:
            self.value_text.set("Finding devices, please wait...")
            return
        device = self.selected_haptic_device_from_popup()
        if not self.save_haptic_audio_device_selection(device):
            return
        self.close_haptic_device_popup()
        self.value_text.set("DualSense audio device saved. Use Test & Save to verify and start output.")

    def test_selected_haptic_device(self) -> None:
        if self.haptic_device_loading:
            self.value_text.set("Finding devices, please wait...")
            return
        if self.haptic_server_action_running:
            self.value_text.set("Connecting DualSense device. This can take a few seconds; please wait.")
            return
        device = self.selected_haptic_device_from_popup()
        if not self.save_haptic_audio_device_selection(device):
            self.value_text.set("Select a DualSense audio device before testing.")
            return
        self.start_haptic_server_for_device(
            device,
            action="test",
            send_test=True,
            validate_saved_device=False,
            status_message="Connecting DualSense device. This can take a few seconds; please wait.",
        )

    @staticmethod
    def powershell_single_quote(value: Path | str) -> str:
        return "'" + str(value).replace("'", "''") + "'"

    @staticmethod
    def is_likely_dualsense_audio_device(device: str) -> bool:
        name = str(device).lower()
        return "dualsense" in name or "wireless controller" in name

    def auto_start_haptic_server_for_saved_device(self) -> None:
        device = self.haptic_audio_device_text.get().strip()
        if not device:
            self.haptic_server_status_text = "select device"
            return
        if self.haptic_server_action_running:
            return
        self.start_haptic_server_for_device(
            device,
            action="auto",
            send_test=False,
            validate_saved_device=True,
            status_message="Checking DualSense audio device...",
        )

    def haptic_server_powershell(self) -> str:
        system_root = Path(os.environ.get("SystemRoot", r"C:\Windows"))
        powershell_path = system_root / "System32" / "WindowsPowerShell" / "v1.0" / "powershell.exe"
        return str(powershell_path if powershell_path.exists() else "powershell.exe")

    def haptic_server_executable_path(self) -> Path | None:
        for path in packaged_file_candidates("runtime", "DualSenseOutputServer.exe"):
            if path.exists():
                return path
        return None

    def haptic_server_debug_dll_path(self) -> Path | None:
        for path in packaged_file_candidates(
            "dualsense_output_server",
            "bin",
            "Debug",
            "net8.0-windows",
            "DualSenseOutputServer.dll",
        ):
            if path.exists():
                return path
        return None

    def haptic_server_script_path(self) -> Path | None:
        for path in packaged_file_candidates("start_haptic_server.ps1"):
            if path.exists():
                return path
        return None

    def haptic_server_logs_dir(self) -> Path:
        for root in package_root_candidates():
            if (root / "runtime").exists():
                return root / "logs"
        return LOG_DIR

    def haptic_server_launch_command(self, device: str) -> tuple[list[str], Path] | None:
        master_gain = self.dsx_audio_volume_percent_value()
        args = [
            "--event-port",
            str(DEFAULT_HAPTIC_EVENT_PORT),
            "--no-keys",
            "--no-startup-pulse",
            "--output-device",
            device,
            "--master-gain-percent",
            str(master_gain),
        ]
        if self.dsx_udp_enabled.get():
            args.append("--no-trigger-hid")

        server_exe = self.haptic_server_executable_path()
        if server_exe is not None:
            return [str(server_exe), *args], server_exe.parent

        debug_dll = self.haptic_server_debug_dll_path()
        if debug_dll is not None:
            return ["dotnet", str(debug_dll), *args], debug_dll.parent

        return None

    def stop_existing_haptic_server_blocking(self) -> None:
        try:
            subprocess.run(
                [
                    self.haptic_server_powershell(),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    self.haptic_server_stop_command(),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=5,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                check=False,
            )
        except Exception:
            pass

    def start_haptic_server_process_blocking(self, device: str) -> tuple[bool, str]:
        launch = self.haptic_server_launch_command(device)
        if launch is None:
            return False, "haptic server executable not found"
        command, cwd = launch
        logs_dir = self.haptic_server_logs_dir()
        try:
            logs_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            pass
        out_log = logs_dir / "haptic_server_latest.out.log"
        err_log = logs_dir / "haptic_server_latest.err.log"
        try:
            stdout = out_log.open("w", encoding="utf-8", errors="replace")
            stderr = err_log.open("w", encoding="utf-8", errors="replace")
        except OSError as exc:
            return False, f"log open failed: {exc}"
        try:
            process = subprocess.Popen(
                command,
                cwd=str(cwd),
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError as exc:
            stdout.close()
            stderr.close()
            return False, str(exc)
        self.haptic_server_process = process
        time.sleep(1.5)
        if process.poll() is not None:
            stdout.close()
            stderr.close()
            return False, f"server exited with code {process.returncode}"
        return True, ""

    def haptic_server_stop_command(self) -> str:
        return "\n".join(
            [
                "$ErrorActionPreference = 'SilentlyContinue'",
                "$serverDllName = 'DualSenseOutputServer.dll'",
                "$serverExeName = 'DualSenseOutputServer.exe'",
                "$running = Get-CimInstance Win32_Process | Where-Object {",
                "    ($_.Name -eq 'dotnet.exe' -and $_.CommandLine -like \"*$serverDllName*\") -or $_.Name -eq $serverExeName",
                "}",
                "foreach ($proc in $running) { Stop-Process -Id $proc.ProcessId -Force }",
            ]
        )

    def start_haptic_server_for_device(
        self,
        device: str,
        action: str,
        send_test: bool = False,
        validate_saved_device: bool = False,
        status_message: str = "Starting haptic server...",
    ) -> None:
        if self.haptic_server_action_running:
            return
        device = str(device).strip()
        if not device:
            self.haptic_server_status_text = "select device"
            return
        self.haptic_server_action_running = True
        self.haptic_server_action_result = None
        self.haptic_server_status_text = "starting"
        self.value_text.set(status_message)

        def worker() -> None:
            try:
                if validate_saved_device:
                    devices = self.sorted_haptic_audio_devices(self.enumerate_audio_output_devices(force=True))
                    if device not in devices:
                        self.haptic_server_action_result = (action, False, "saved device not present", send_test)
                        return
                    verified_device = str(self.settings.get("haptic_audio_device_verified", "")).strip()
                    if verified_device != device and not self.is_likely_dualsense_audio_device(device):
                        self.haptic_server_action_result = (action, False, "saved device needs confirmation", send_test)
                        return
                self.stop_existing_haptic_server_blocking()
                success, start_message = self.start_haptic_server_process_blocking(device)
                if success:
                    self.haptic_server_action_result = (action, True, "", send_test)
                else:
                    self.haptic_server_action_result = (action, False, start_message, send_test)
            except OSError as exc:
                self.haptic_server_action_result = (action, False, str(exc), send_test)
            except Exception as exc:
                self.haptic_server_action_result = (action, False, f"{type(exc).__name__}: {exc}", send_test)

        threading.Thread(target=worker, daemon=True).start()
        try:
            self.root.after(350, self.poll_haptic_server_action)
        except tk.TclError:
            pass

    def poll_haptic_server_action(self) -> None:
        result = self.haptic_server_action_result
        if result is None:
            message = "Connecting DualSense device. This can take a few seconds; please wait."
            self.value_text.set(message)
            try:
                self.haptic_device_status_text.set(message)
            except tk.TclError:
                pass
            try:
                self.root.after(350, self.poll_haptic_server_action)
            except tk.TclError:
                pass
            return
        self.haptic_server_action_running = False
        self.haptic_server_action_result = None
        action, success, message, send_test = result
        if success:
            self.haptic_server_status_text = "ready"
            if send_test:
                device = self.haptic_audio_device_text.get().strip()
                if device:
                    self.settings["haptic_audio_device_verified"] = device
                    save_settings(self.settings, make_backup=True, force=True)
                self.send_selected_device_haptic_test()
                message = "Haptic test sent: 80Hz haptic, L2 pulse, then R2 pulse."
                self.value_text.set(message)
                try:
                    self.haptic_device_status_text.set(message)
                except tk.TclError:
                    pass
            else:
                self.value_text.set("Haptic server ready.")
            return
        self.haptic_server_status_text = "select device" if action == "auto" else "failed"
        if action == "test":
            self.last_error = f"haptic server selected-device test failed: {message}"
            self.value_text.set("Selected device failed haptic test. Choose a DualSense audio device.")
            try:
                self.haptic_device_status_text.set("Selected device failed. Choose a DualSense audio device.")
            except tk.TclError:
                pass
        else:
            self.value_text.set("Select DualSense audio device before haptic output.")

    def stop_haptic_server_async(self) -> None:
        try:
            subprocess.Popen(
                [
                    self.haptic_server_powershell(),
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-Command",
                    self.haptic_server_stop_command(),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
        except OSError:
            pass

    def send_selected_device_haptic_test(self) -> None:
        self.send_soft_haptic_test()
        self.send_soft_trigger_test()

    def send_soft_haptic_test(self) -> None:
        self.send_haptic_event(
            "HAPTIC_TEST|hz=80|amp=40|durationMs=1500",
            count=False,
        )

    def send_soft_trigger_test(self) -> None:
        left_payload = (
            "TRIGGER_MODE_TEST|side=L|preset=rigid_wall_50|count=1|onMs=240|offMs=0|hz=80|amp=153"
            "|wallStart=0|wallEnd=0|wallStrength=0"
        )
        right_payload = (
            "TRIGGER_MODE_TEST|side=R|preset=rigid_wall_50|count=1|onMs=240|offMs=0|hz=80|amp=153"
            "|wallStart=0|wallEnd=0|wallStrength=0"
        )
        self.send_haptic_event(left_payload, count=False)
        try:
            self.root.after(420, lambda: self.send_haptic_event(right_payload, count=False))
        except tk.TclError:
            self.send_haptic_event(right_payload, count=False)

    def send_soft_gear_shift_haptic_test(self) -> None:
        try:
            self.root.after(120, lambda: self.send_gear_shift_haptic_test(core_volume=3, high_hz_volume=2, particles_volume=2, second_pulse=False))
        except tk.TclError:
            self.send_gear_shift_haptic_test(core_volume=3, high_hz_volume=2, particles_volume=2, second_pulse=False)

    def send_gear_shift_haptic_test(
        self,
        core_volume: int = 10,
        high_hz_volume: int = 10,
        particles_volume: int = 10,
        second_pulse: bool = True,
    ) -> None:
        def send_once(direction: int) -> None:
            fields = {
                "dir": direction,
                "rpmRatio": 0.82,
                "throttle": 0.70,
                "torque": 0.55,
                "pi": 800,
                "carClass": 5,
                "carGroup": 0,
                "maxRpm": 8000,
                "coreVolume": core_volume,
                "highHzVolume": high_hz_volume,
                "particlesVolume": particles_volume,
                "coreLeft": 1.0,
                "coreRight": 1.0,
                "highHzLeft": 1.0,
                "highHzRight": 1.0,
                "particlesLeft": 1.0,
                "particlesRight": 1.0,
            }
            payload = "GEAR_SHIFT|" + "|".join(f"{key}={value}" for key, value in fields.items())
            self.send_haptic_event(payload)

        send_once(1)
        if not second_pulse:
            return
        try:
            self.root.after(260, lambda: send_once(-1))
        except tk.TclError:
            send_once(-1)

    def close_haptic_device_popup(self) -> None:
        popup = self.haptic_device_popup
        self.haptic_device_popup = None
        self.haptic_device_listbox = None
        self.haptic_device_loading = False
        if popup is not None:
            try:
                if popup.winfo_exists():
                    popup.destroy()
            except tk.TclError:
                pass

    def send_haptic_master_gain(self, percent: int | None = None) -> None:
        if percent is None:
            percent = self.dsx_audio_volume_percent_value()
        self.send_haptic_event(f"MASTER_GAIN|percent={self.clamp_int(percent, 0, 100)}", count=False)

    def refresh_dsx_audio_devices_and_render(self) -> None:
        self.dsx_audio_device_choices = self.enumerate_audio_output_devices(force=True)
        if self.dsx_audio_device_choices and not self.dsx_audio_device_text.get().strip():
            self.dsx_audio_device_text.set(self.dsx_audio_device_choices[0])
        self.on_dsx_options_entered()
        self.render_options_section("dsx_udp")

    def refresh_dsx_audio_device_choices(self) -> None:
        if not self.dsx_audio_device_choices:
            self.dsx_audio_device_choices = self.enumerate_audio_output_devices(force=False)
        current = self.dsx_audio_device_text.get().strip()
        if current and current not in self.dsx_audio_device_choices:
            self.dsx_audio_device_choices.insert(0, current)
        if not self.dsx_audio_device_choices:
            self.dsx_audio_device_choices = ["DualSense"]

    def enumerate_audio_output_devices(self, force: bool = False) -> list[str]:
        if self.dsx_audio_device_choices and not force:
            return list(self.dsx_audio_device_choices)
        server_devices = self.enumerate_audio_output_devices_from_output_server()
        if server_devices:
            return server_devices
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
          \"$endpoint ($deviceName)\"
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
            result = subprocess.run(
                [powershell_cmd, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
                capture_output=True,
                timeout=6.0,
                check=False,
            )
        except Exception:
            return []
        stdout = self.decode_subprocess_output(result.stdout)
        devices: list[str] = []
        seen: set[str] = set()
        for line in stdout.splitlines():
            name = line.strip()
            if not name or name in seen:
                continue
            seen.add(name)
            devices.append(name)
        return devices

    def enumerate_audio_output_devices_from_output_server(self) -> list[str]:
        runtime_server = self.haptic_server_executable_path()
        if runtime_server is not None:
            devices = self.try_enumerate_audio_output_devices([str(runtime_server), "--list-output-devices"], runtime_server.parent)
            if devices:
                return devices

        app_dir = Path(__file__).resolve().parent
        server_dir = app_dir / "dualsense_output_server"
        server_project = server_dir / "DualSenseOutputServer.csproj"
        if not server_project.exists():
            return []
        server_dll = server_dir / "bin" / "Debug" / "net8.0-windows" / "DualSenseOutputServer.dll"
        commands: list[list[str]] = []
        try:
            source_mtime = max(
                server_project.stat().st_mtime,
                (server_dir / "Program.cs").stat().st_mtime,
            )
            if server_dll.exists() and server_dll.stat().st_mtime >= source_mtime:
                commands.append(["dotnet", str(server_dll), "--list-output-devices"])
        except OSError:
            pass
        commands.append([
            "dotnet",
            "run",
            "--project",
            str(server_project),
            "--no-launch-profile",
            "--",
            "--list-output-devices",
        ])
        for command in commands:
            devices = self.try_enumerate_audio_output_devices(command, app_dir)
            if devices:
                return devices
        return []

    def try_enumerate_audio_output_devices(self, command: list[str], cwd: Path) -> list[str]:
        try:
            result = subprocess.run(
                command,
                cwd=str(cwd),
                capture_output=True,
                timeout=10.0,
                check=False,
            )
        except Exception:
            return []
        if result.returncode != 0:
            return []
        stdout = self.decode_subprocess_output(result.stdout)
        devices: list[str] = []
        seen: set[str] = set()
        for line in stdout.splitlines():
            name = line.strip()
            if not name or name.startswith(("Determining projects", "Restore", "Build")):
                continue
            if name in seen:
                continue
            seen.add(name)
            devices.append(name)
        return devices

    def decode_subprocess_output(self, data) -> str:
        if isinstance(data, str):
            return data
        for encoding in ("utf-8-sig", "cp949", "mbcs"):
            try:
                return data.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return data.decode(errors="replace")

    def on_dsx_options_entered(self, _event=None) -> None:
        port = self.normalized_udp_port(self.dsx_port_text.get(), DEFAULT_DSX_PORT)
        self.dsx_port_text.set(str(port))
        if not self.dsx_host_text.get().strip():
            self.dsx_host_text.set(DEFAULT_DSX_HOST)
        self.save_dsx_options()
        save_settings(self.settings)
        self.update_dsx_status_text()

    def render_hud_options(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="HUD",
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=ui_px(16), pady=(ui_px(16), ui_px(8)))
        tk.Label(
            parent,
            text="Restore all HUD windows to their default locations and default sizes for each HUD scale preset.",
            bg="#171b20",
            fg="#9aa4af",
            font=ui_font("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=ui_px(390),
        ).grid(row=1, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(14)))
        tk.Button(
            parent,
            text="HUD Location Reset",
            command=self.reset_hud_locations,
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#303946",
            activeforeground="#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 9, "bold"),
            padx=ui_px(12),
            pady=ui_px(5),
        ).grid(row=2, column=0, sticky="w", padx=ui_px(16))

    def render_display_options(self, parent: tk.Frame) -> None:
        tk.Label(
            parent,
            text="Display Scale",
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=ui_px(16), pady=(ui_px(16), ui_px(8)))
        tk.Label(
            parent,
            text=(
                "Use this when Windows display scaling makes text too small or too large. "
                f"Auto: {recommended_display_scale_value()}% from Windows {detect_windows_dpi_percent()}%. "
                "Changing it saves settings, closes the app, then relaunches it. Layout size is controlled by Main UI Scale."
            ),
            bg="#171b20",
            fg="#9aa4af",
            font=ui_font("Segoe UI", 9),
            anchor="w",
            justify="left",
            wraplength=ui_px(390),
        ).grid(row=1, column=0, sticky="ew", padx=ui_px(16), pady=(0, ui_px(14)))
        controls = tk.Frame(parent, bg="#171b20")
        controls.grid(row=2, column=0, sticky="w", padx=ui_px(16), pady=(0, ui_px(12)))
        for column, percent in enumerate(DISPLAY_SCALE_PRESETS):
            selected = percent == self.normalized_display_scale_percent(self.display_scale_percent.get())
            tk.Button(
                controls,
                text=f"{percent}%",
                command=lambda value=percent: self.set_display_scale(value),
                bg="#f1c40f" if selected else "#252c35",
                fg="#101216" if selected else "#d6dde5",
                activebackground="#f7d84a" if selected else "#303946",
                activeforeground="#101216" if selected else "#f1c40f",
                relief="flat",
                font=ui_font("Segoe UI", 9, "bold"),
                padx=ui_px(12),
                pady=ui_px(5),
            ).grid(row=0, column=column, sticky="w", padx=(0, ui_px(6)))
        auto_percent = recommended_display_scale_value()
        auto_selected = auto_percent == self.normalized_display_scale_percent(self.display_scale_percent.get())
        tk.Button(
            controls,
            text="Auto",
            command=self.set_auto_display_scale,
            bg="#f1c40f" if auto_selected else "#252c35",
            fg="#101216" if auto_selected else "#d6dde5",
            activebackground="#f7d84a" if auto_selected else "#303946",
            activeforeground="#101216" if auto_selected else "#f1c40f",
            relief="flat",
            font=ui_font("Segoe UI", 9, "bold"),
            padx=ui_px(12),
            pady=ui_px(5),
        ).grid(row=0, column=len(DISPLAY_SCALE_PRESETS), sticky="w", padx=(ui_px(2), 0))
        tk.Label(
            parent,
            textvariable=self.display_scale_text,
            bg="#171b20",
            fg="#f1c40f",
            font=value_font("Consolas", 12, "bold"),
            anchor="w",
        ).grid(row=3, column=0, sticky="w", padx=ui_px(16))

    def reset_hud_locations(self) -> None:
        current_percent = self.normalized_hud_scale_percent(self.hud_scale_percent.get())
        for key, default_geometry, hud, min_width, min_height in self.hud_geometry_specs():
            for percent in HUD_SCALE_PRESETS:
                geometry = self.scaled_hud_reset_geometry(
                    default_geometry,
                    percent / 100.0,
                    min_width,
                    min_height,
                )
                if key == "engine_hud_geometry":
                    geometry = self.normalized_engine_hud_geometry(geometry, percent)
                self.set_hud_geometry(key, geometry, percent)
            current_geometry = self.settings.get(self.hud_geometry_key(key, current_percent))
            if hud is not None and self.hud_window_exists(hud) and isinstance(current_geometry, str):
                try:
                    hud.geometry(current_geometry)
                except tk.TclError:
                    pass
        save_settings(self.settings, force=True)
        self.update_save_button_state()
        self.value_text.set("HUD locations reset.")

    def render_placeholder_options(self, parent: tk.Frame, title: str, text: str) -> None:
        tk.Label(
            parent,
            text=title,
            bg="#171b20",
            fg="#eef3f4",
            font=ui_font("Segoe UI", 13, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew", padx=ui_px(16), pady=(ui_px(16), ui_px(8)))
        tk.Label(
            parent,
            text=text,
            bg="#171b20",
            fg="#9aa4af",
            font=ui_font("Segoe UI", 9),
            anchor="nw",
            justify="left",
            wraplength=ui_px(360),
        ).grid(row=1, column=0, sticky="ew", padx=ui_px(16))

    def load_settings_backup(self) -> None:
        if not SETTINGS_BACKUP_PATH.exists():
            self.value_text.set(f"No backup found: {SETTINGS_BACKUP_PATH.name}")
            return
        try:
            loaded = json.loads(SETTINGS_BACKUP_PATH.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.value_text.set(f"Backup load failed: {exc}")
            return
        if not isinstance(loaded, dict):
            self.value_text.set("Backup load failed: invalid settings format")
            return
        self.settings = loaded
        self.apply_loaded_settings_to_controls()
        save_settings(self.settings, force=True)
        self.update_save_button_state()
        self.value_text.set(f"Backup loaded: {SETTINGS_BACKUP_PATH.name}")

    def update_save_button_state(self) -> None:
        if not hasattr(self, "save_settings_button"):
            return
        dirty = bool(self.settings.get("_unsaved_changes", False))
        if self.save_button_dirty_visual == dirty:
            return
        self.save_button_dirty_visual = dirty
        if dirty:
            self.save_settings_button.configure(
                bg="#f1c40f",
                fg="#101316",
                activebackground="#f7dc6f",
                activeforeground="#101316",
            )
        else:
            self.save_settings_button.configure(
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
            )

    def apply_loaded_settings_to_controls(self) -> None:
        configured_fields = self.settings.get("graph_fields")
        if isinstance(configured_fields, list):
            for var, value in zip(self.graph_inputs, configured_fields):
                var.set(str(value))
        configured_hidden = self.settings.get("graph_hidden")
        if isinstance(configured_hidden, list):
            now = time.monotonic()
            for idx, value in enumerate(configured_hidden[: len(self.graph_hidden_vars)]):
                hidden = bool(value)
                self.graph_hidden_vars[idx].set(hidden)
                self.graph_hidden_at[idx] = now if hidden and self.graph_hidden_at[idx] <= 0.0 else (self.graph_hidden_at[idx] if hidden else 0.0)
        self.update_graph_visibility_buttons()
        self.current_preset_name.set(normalized_config_preset_name(self.settings.get("current_preset", self.current_preset_name.get())))
        self.telemetry_port = self.normalized_udp_port(self.settings.get("udp_port", self.telemetry_port), self.telemetry_port)
        self.udp_port_text.set(str(self.telemetry_port))
        self.drift_relief_enabled.set(bool(self.settings.get("drift_relief_enabled", self.drift_relief_enabled.get())))
        self.update_drift_relief_status_text()
        self.dsx_udp_enabled.set(bool(self.settings.get("dsx_udp_enabled", self.dsx_udp_enabled.get())))
        self.dsx_host_text.set(str(self.settings.get("dsx_host", DEFAULT_DSX_HOST)))
        self.dsx_port_text.set(str(self.normalized_udp_port(self.settings.get("dsx_port", DEFAULT_DSX_PORT), DEFAULT_DSX_PORT)))
        self.dsx_audio_export_enabled.set(bool(self.settings.get("dsx_audio_export_enabled", self.dsx_audio_export_enabled.get())))
        self.dsx_audio_device_text.set(str(self.settings.get("dsx_audio_device", self.dsx_audio_device_text.get())))
        self.haptic_audio_device_text.set(str(self.settings.get("haptic_audio_device", self.haptic_audio_device_text.get())))
        dsx_audio_volume_percent = self.clamp_int(self.settings.get("dsx_audio_volume_percent", self.dsx_audio_volume_percent_value()), 0, 100)
        self.dsx_audio_volume_step.set(self.clamp_int(round(dsx_audio_volume_percent / 10), 0, 10))
        self.dsx_audio_volume_text.set(f"{self.dsx_audio_volume_step.get() * 10}%")
        self.update_dsx_status_text()

        effects = self.settings.get("effects", {})
        if isinstance(effects, dict):
            for effect_name, controls_state in self.effect_controls.items():
                effect_settings = effects.get(effect_name)
                if not isinstance(effect_settings, dict):
                    continue
                if "enabled" in effect_settings:
                    controls_state["enabled"].set(bool(effect_settings["enabled"]))
                if "volume" in effect_settings:
                    volume = self.clamp_volume(effect_settings["volume"])
                    controls_state["volume"].set(volume)
                    controls_state["volume_text"].set(self.format_volume(volume))
                if effect_name in PAN_EFFECTS and "pan" in controls_state and "pan" in effect_settings:
                    pan = self.clamp_pan(effect_settings["pan"])
                    controls_state["pan"].set(pan)
                    controls_state["pan_text"].set(self.format_pan(pan))

        triggers = self.settings.get("trigger_effects", {})
        if isinstance(triggers, dict):
            for trigger_name, controls_state in self.trigger_controls.items():
                trigger_settings = triggers.get(trigger_name)
                if not isinstance(trigger_settings, dict):
                    continue
                self.apply_loaded_trigger_settings(trigger_name, controls_state, trigger_settings)

        self.selected_output_effect.set(str(self.settings.get("selected_output_effect", self.selected_output_effect.get())))
        selected_trigger = str(self.settings.get("selected_trigger_effect", self.selected_trigger_effect.get()))
        if selected_trigger in HIDDEN_TRIGGER_EFFECTS:
            selected_trigger = TRIGGER_BRAKE_RESISTANCE_PREDICTIVE
        self.selected_trigger_effect.set(selected_trigger)
        self.selected_detail_type.set(str(self.settings.get("selected_detail_type", self.selected_detail_type.get())))
        self.window_resize_unlocked.set(False)
        self.hud_scale_percent.set(self.normalized_hud_scale_percent(self.settings.get("hud_scale_percent", self.hud_scale_percent.get())))
        self.main_ui_scale_percent.set(self.normalized_main_ui_scale_percent(self.settings.get("main_ui_scale_percent", self.main_ui_scale_percent.get())))
        self.display_scale_percent.set(self.normalized_display_scale_percent(self.settings.get("display_scale_percent", self.display_scale_percent.get())))
        self.apply_scale_globals()
        self.apply_window_resize_state()
        self.hud_standby_hide_enabled.set(bool(self.settings.get("hud_standby_hide", self.hud_standby_hide_enabled.get())))
        self.update_hud_standby_hide_button()
        self.update_hud_visibility_for_udp()
        self.enforce_brake_resistance_exclusive(prefer=selected_trigger)
        self.normalize_dynamic_brake_strength()
        self.normalize_trigger_ranges()
        self.update_effect_label_styles()
        self.update_trigger_label_styles()
        self.update_slip_pulse_option_styles()
        self.refresh_effect_detail_panel()
        self.update_preset_lock_state()

    def apply_loaded_trigger_settings(
        self,
        trigger_name: str,
        controls_state: dict[str, tk.Variable],
        trigger_settings: dict,
    ) -> None:
        int_fields = {
            "curve": "curve_text",
            "start_percent": "start_text",
            "max_percent": "max_text",
            "force_percent": "force_text",
            "upshift_strength_percent": "upshift_strength_text",
            "upshift_duration_ms": "upshift_duration_text",
            "downshift_strength_percent": "downshift_strength_text",
            "downshift_duration_ms": "downshift_duration_text",
            "early_input_soft_zone": "early_input_soft_zone_text",
            "kick_late_position": "kick_late_position_text",
            "kick_softness": "kick_softness_text",
            "release_duration_ms": "release_duration_text",
            "sustain_percent": "sustain_text",
            "wall_percent": "wall_text",
            "gate_range": "gate_range_text",
            "slip_drop_low_percent": "slip_drop_low_text",
            "slip_low_percent": "slip_low_text",
            "slip_pulse_high_percent": "slip_pulse_high_text",
            "slip_pulse_start_percent": "slip_pulse_start_text",
            "slip_pulse_end_percent": "slip_pulse_end_text",
            "slip_pulse_rate": "slip_pulse_rate_text",
            "slip_rumble_amplitude": "slip_rumble_amplitude_text",
            "slip_rumble_rate": "slip_rumble_rate_text",
            "slip_dsx_vibration_amplitude": "slip_dsx_vibration_amplitude_text",
            "slip_dsx_vibration_frequency": "slip_dsx_vibration_frequency_text",
            "slip_dsx_vibration_margin": "slip_dsx_vibration_margin_text",
            "kerb_low_hz": "kerb_low_hz_text",
            "kerb_high_hz": "kerb_high_hz_text",
            "kerb_l_start_percent": "kerb_l_start_text",
            "kerb_r_start_percent": "kerb_r_start_text",
            "kerb_l_low_hz": "kerb_l_low_hz_text",
            "kerb_l_high_hz": "kerb_l_high_hz_text",
            "kerb_r_low_hz": "kerb_r_low_hz_text",
            "kerb_r_high_hz": "kerb_r_high_hz_text",
            "kerb_l_low_amp": "kerb_l_low_amp_text",
            "kerb_l_high_amp": "kerb_l_high_amp_text",
            "kerb_r_low_amp": "kerb_r_low_amp_text",
            "kerb_r_high_amp": "kerb_r_high_amp_text",
            "strength": "strength_text",
            "smooth_start_ms": "smooth_start_text",
            "pulse_strength": "pulse_strength_text",
            "pulse_start_percent": "pulse_start_text",
            "pulse_offset": "pulse_offset_text",
            "pulse_timing_offset": "pulse_timing_offset_text",
            "haptic_pulse_hz": "haptic_pulse_hz_text",
            "haptic_pulse_strength": "haptic_pulse_strength_text",
            "haptic_pulse_start_margin": "haptic_pulse_start_margin_text",
            "haptic_pulse_end_margin": "haptic_pulse_end_margin_text",
            "pulse_rate": "pulse_rate_text",
        }
        bool_fields = ("enabled", "slip_off", "slip_pulse_enabled", "kerb_l_enabled", "kerb_r_enabled")
        string_fields = ("side", "upshift_sides", "downshift_sides", "slip_response_mode", "slip_pulse_style")

        for key in bool_fields:
            if key in controls_state and key in trigger_settings:
                controls_state[key].set(bool(trigger_settings[key]))
        for key in string_fields:
            if key in controls_state and key in trigger_settings:
                value = str(trigger_settings[key])
                if key == "slip_pulse_style":
                    value = normalize_slip_pulse_style(value, trigger_name)
                controls_state[key].set(value)
        for key, text_key in int_fields.items():
            if key in controls_state and key in trigger_settings:
                value = self.clamp_int(trigger_settings[key], -9999, 9999)
                controls_state[key].set(value)
                if text_key in controls_state:
                    controls_state[text_key].set(str(value))
        for key, text_key in (
            ("slip_threshold", "slip_threshold_text"),
            ("slip_end_threshold", "slip_end_threshold_text"),
        ):
            if key in controls_state and key in trigger_settings:
                value = self.clamp_float(trigger_settings[key], 0.1, 5.0)
                scaled = int(round(value * 10))
                controls_state[key].set(scaled)
                if text_key in controls_state:
                    controls_state[text_key].set(f"{scaled / 10.0:.1f}")
        self.update_slip_pulse_style_buttons(controls_state)

    def on_graph_fields_changed(self, _event=None) -> None:
        self.settings["graph_fields"] = [var.get().strip() for var in self.graph_inputs]
        self.settings["graph_hidden"] = [bool(var.get()) for var in self.graph_hidden_vars]
        save_settings(self.settings)

    def graph_entry_color(self, index: int) -> str:
        base = GRAPH_COLORS[index]
        if self.graph_hidden_vars[index].get():
            return self.mix_hex_color(base, "#171b20", 0.62)
        return base

    def toggle_graph_hidden(self, index: int) -> None:
        if index < 0 or index >= len(self.graph_hidden_vars):
            return
        hidden = not bool(self.graph_hidden_vars[index].get())
        self.graph_hidden_vars[index].set(hidden)
        self.graph_hidden_at[index] = time.monotonic() if hidden else 0.0
        self.settings["graph_hidden"] = [bool(var.get()) for var in self.graph_hidden_vars]
        save_settings(self.settings)
        self.update_graph_visibility_buttons()
        if self.udp_receiving:
            self.draw_live_graphs(max(1, self.canvas.winfo_width()), max(1, self.canvas.winfo_height()), time.monotonic())

    def update_graph_visibility_buttons(self) -> None:
        for idx, button in enumerate(getattr(self, "graph_hide_buttons", [])):
            hidden = bool(self.graph_hidden_vars[idx].get())
            led_ids = getattr(self, "graph_hide_led_ids", [])
            led_id = led_ids[idx] if idx < len(led_ids) else None
            if led_id is not None:
                button.itemconfigure(
                    led_id,
                    fill="#2a3139" if hidden else "#f1c40f",
                    outline="#3a434d" if hidden else "#f7dc6f",
                )
        for idx, entry in enumerate(getattr(self, "graph_entries", [])):
            entry.configure(fg=self.graph_entry_color(idx))

    def graph_field_choices(self) -> list[str]:
        choices = set(parse_packet_field_names())
        choices.update(derived_field_names())
        choices.update(FIELD_DEFAULT_SCALES.keys())
        choices.update(OFFICIAL_FIELD_ALIASES.keys())
        return sorted(choices)

    def show_graph_field_popup(self, graph_index: int, event=None) -> None:
        self.close_graph_field_popup()
        popup = tk.Toplevel(self.root)
        popup.title("Telemetry")
        popup.configure(bg="#171b20")
        popup.resizable(False, False)
        popup.transient(self.root)
        popup.attributes("-topmost", True)

        popup_w = ui_px(260)
        popup_h = ui_px(320)
        preferred_x = event.x_root if event is not None else self.root.winfo_pointerx()
        preferred_y = (event.y_root + ui_px(24)) if event is not None else self.root.winfo_pointery()
        x, y = self.popup_position_near_root(popup_w, popup_h, preferred_x, preferred_y)
        popup.geometry(f"{popup_w}x{popup_h}+{x}+{y}")

        tk.Label(
            popup,
            text="Telemetry Field",
            bg="#171b20",
            fg="#f1c40f",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(fill="x", padx=ui_px(8), pady=(ui_px(7), ui_px(4)))

        shell = tk.Frame(popup, bg="#171b20")
        shell.pack(fill="both", expand=True, padx=ui_px(8), pady=(0, ui_px(8)))
        scrollbar = tk.Scrollbar(shell, orient="vertical", width=max(10, ui_px(12)))
        listbox = tk.Listbox(
            shell,
            bg="#101316",
            fg="#d6dde5",
            selectbackground="#f1c40f",
            selectforeground="#101316",
            activestyle="none",
            relief="flat",
            highlightthickness=1,
            highlightbackground="#252c35",
            font=value_font("Consolas", 9),
            yscrollcommand=scrollbar.set,
            exportselection=False,
        )
        scrollbar.configure(command=listbox.yview)
        listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        choices = self.graph_field_choices()
        current = self.graph_inputs[graph_index].get().strip()
        selected_index = 0
        for idx, choice in enumerate(choices):
            listbox.insert("end", choice)
            if choice == current:
                selected_index = idx
        if choices:
            listbox.selection_set(selected_index)
            listbox.see(selected_index)

        def apply_selection(_event=None) -> str:
            selection = listbox.curselection()
            if selection:
                self.graph_inputs[graph_index].set(str(listbox.get(selection[0])))
                self.on_graph_fields_changed()
            self.close_graph_field_popup()
            return "break"

        listbox.bind("<Double-Button-1>", apply_selection)
        listbox.bind("<Return>", apply_selection)
        listbox.bind("<ButtonRelease-1>", apply_selection)
        popup.bind("<Escape>", lambda _event: self.close_graph_field_popup())
        popup.bind("<FocusOut>", lambda _event: self.root.after(120, self.close_graph_field_popup_if_unfocused))
        listbox.focus_set()
        self.graph_field_popup = popup
        self.graph_field_listbox = listbox
        self.bind_popup_hover_autoclose(popup, self.close_graph_field_popup)

    def close_graph_field_popup_if_unfocused(self) -> None:
        popup = self.graph_field_popup
        if popup is None or not popup.winfo_exists():
            return
        focus = self.root.focus_get()
        if focus is None:
            return
        if str(focus).startswith(str(popup)):
            return
        self.close_graph_field_popup()

    def close_graph_field_popup(self) -> None:
        popup = self.graph_field_popup
        self.graph_field_popup = None
        self.graph_field_listbox = None
        if popup is not None:
            try:
                popup.destroy()
            except tk.TclError:
                pass

    def effect_settings(self, name: str) -> dict[str, float | int | bool]:
        all_settings = self.settings.get("effects")
        if not isinstance(all_settings, dict):
            all_settings = {}
        defaults = DEFAULT_EFFECT_SETTINGS[name]
        current = all_settings.get(name)
        if not isinstance(current, dict):
            for legacy_name, current_name in LEGACY_EFFECT_NAMES.items():
                if current_name == name and isinstance(all_settings.get(legacy_name), dict):
                    current = all_settings.get(legacy_name)
                    break
        if not isinstance(current, dict):
            current = {}
        enabled = current.get("enabled", defaults["enabled"])
        volume = self.clamp_volume(current.get("volume", defaults["volume"]))
        pan = self.clamp_pan(current.get("pan", defaults.get("pan", 5)))
        return {"enabled": bool(enabled), "volume": volume, "pan": pan}

    def trigger_settings(self, name: str) -> dict[str, float | int | bool | str]:
        all_settings = self.settings.get("trigger_effects")
        if not isinstance(all_settings, dict):
            all_settings = {}
        defaults = DEFAULT_TRIGGER_SETTINGS[name]
        current = all_settings.get(name)
        if not isinstance(current, dict):
            for legacy_name, current_name in LEGACY_TRIGGER_NAMES.items():
                if current_name == name and isinstance(all_settings.get(legacy_name), dict):
                    current = all_settings.get(legacy_name)
                    break
        if not isinstance(current, dict):
            current = {}
        if "force_percent" in current:
            force_percent = self.clamp_int(current.get("force_percent"), 0, 100)
        elif "strength" in current:
            force_percent = self.clamp_int(float(current.get("strength")) / 255.0 * 100.0, 0, 100)
        else:
            force_percent = self.clamp_int(defaults["force_percent"], 0, 100)
        pulse_brake_trigger = name in (TRIGGER_BRAKE_RESISTANCE_DYNAMIC, TRIGGER_BRAKE_RESISTANCE_PREDICTIVE)
        if pulse_brake_trigger:
            pulse_offset = self.clamp_int(current.get("pulse_offset", defaults.get("pulse_offset", 5)), 0, 40)
        elif "pulse_offset" in current:
            pulse_offset = self.clamp_int(current.get("pulse_offset"), -30, 30)
        else:
            pulse_offset = self.clamp_int(defaults.get("pulse_offset", 0), -30, 30)
        pulse_rate_max = 255 if pulse_brake_trigger else 30
        pulse_strength_max = 255 if name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE else 100
        start_max = 100
        wall_percent = self.clamp_int(current.get("wall_percent", defaults.get("wall_percent", 53)), 0, 100)
        gate_range = self.clamp_int(current.get("gate_range", defaults.get("gate_range", 15)), 0, 30)
        smooth_start_ms = self.clamp_int(current.get("smooth_start_ms", defaults["smooth_start_ms"]), 0, 300)
        haptic_pulse_start_default = defaults.get("haptic_pulse_start_margin", 25)
        haptic_pulse_end_default = defaults.get("haptic_pulse_end_margin", 0)
        haptic_pulse_start_current = current.get("haptic_pulse_start_margin", haptic_pulse_start_default)
        haptic_pulse_end_current = current.get("haptic_pulse_end_margin", haptic_pulse_end_default)
        if (
            name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE
            and self.clamp_int(haptic_pulse_start_current, -20, 25) == 25
            and self.clamp_int(haptic_pulse_end_current, -20, 25) == 0
        ):
            haptic_pulse_start_current = haptic_pulse_start_default
            haptic_pulse_end_current = haptic_pulse_end_default
        slip_response_mode = str(current.get("slip_response_mode", "")).strip()
        if slip_response_mode not in SLIP_RESPONSE_MODES:
            slip_response_mode = SLIP_RESPONSE_FULL_OFF if bool(current.get("slip_off", defaults.get("slip_off", False))) else defaults.get("slip_response_mode", SLIP_RESPONSE_OFF)
        if slip_response_mode not in SLIP_RESPONSE_MODES:
            slip_response_mode = SLIP_RESPONSE_OFF
        slip_pulse_enabled = bool(current.get("slip_pulse_enabled", slip_response_mode == SLIP_RESPONSE_PULSE))
        slip_pulse_style = normalize_slip_pulse_style(
            current.get("slip_pulse_style", defaults.get("slip_pulse_style", SLIP_PULSE_STYLE_PULSE_KICK)),
            name,
        )
        slip_response_mode = SLIP_RESPONSE_PULSE if slip_pulse_enabled else SLIP_RESPONSE_DROP
        start_percent = self.clamp_int(current.get("start_percent", defaults["start_percent"]), 0, start_max)
        if name == TRIGGER_THROTTLE_TRACTION_LIMIT:
            start_percent = 100
        kerb_low_hz = self.clamp_int(current.get("kerb_low_hz", defaults.get("kerb_low_hz", 12)), 1, 40)
        kerb_high_hz = self.clamp_int(current.get("kerb_high_hz", defaults.get("kerb_high_hz", 40)), 1, 40)
        if kerb_low_hz > kerb_high_hz:
            kerb_low_hz, kerb_high_hz = kerb_high_hz, kerb_low_hz
        kerb_l_low_hz = self.clamp_int(current.get("kerb_l_low_hz", kerb_low_hz), 1, 40)
        kerb_l_high_hz = self.clamp_int(current.get("kerb_l_high_hz", kerb_high_hz), 1, 40)
        kerb_r_low_hz = self.clamp_int(current.get("kerb_r_low_hz", kerb_low_hz), 1, 40)
        kerb_r_high_hz = self.clamp_int(current.get("kerb_r_high_hz", kerb_high_hz), 1, 40)
        if kerb_l_low_hz > kerb_l_high_hz:
            kerb_l_low_hz, kerb_l_high_hz = kerb_l_high_hz, kerb_l_low_hz
        if kerb_r_low_hz > kerb_r_high_hz:
            kerb_r_low_hz, kerb_r_high_hz = kerb_r_high_hz, kerb_r_low_hz
        old_amp = self.clamp_int(current.get("slip_dsx_vibration_amplitude", defaults.get("slip_dsx_vibration_amplitude", 2)), 1, 8)
        kerb_l_low_amp = self.clamp_int(current.get("kerb_l_low_amp", max(1, old_amp - 1)), 1, 8)
        kerb_l_high_amp = self.clamp_int(current.get("kerb_l_high_amp", old_amp), 1, 8)
        kerb_r_low_amp = self.clamp_int(current.get("kerb_r_low_amp", max(1, old_amp - 1)), 1, 8)
        kerb_r_high_amp = self.clamp_int(current.get("kerb_r_high_amp", old_amp), 1, 8)
        if kerb_l_low_amp > kerb_l_high_amp:
            kerb_l_low_amp, kerb_l_high_amp = kerb_l_high_amp, kerb_l_low_amp
        if kerb_r_low_amp > kerb_r_high_amp:
            kerb_r_low_amp, kerb_r_high_amp = kerb_r_high_amp, kerb_r_low_amp
        return {
            "enabled": bool(current.get("enabled", defaults["enabled"])),
            "curve": self.clamp_int(current.get("curve", defaults["curve"]), 0, 9),
            "start_percent": start_percent,
            "max_percent": self.clamp_int(current.get("max_percent", defaults["max_percent"]), 0, 100),
            "force_percent": force_percent,
            "upshift_strength_percent": self.clamp_int(
                current.get("upshift_strength_percent", defaults.get("upshift_strength_percent", force_percent)),
                0,
                100,
            ),
            "upshift_duration_ms": self.clamp_int(
                current.get("upshift_duration_ms", defaults.get("upshift_duration_ms", smooth_start_ms)),
                20,
                180,
            ),
            "downshift_strength_percent": self.clamp_int(
                current.get("downshift_strength_percent", defaults.get("downshift_strength_percent", force_percent)),
                0,
                100,
            ),
            "downshift_duration_ms": self.clamp_int(
                current.get("downshift_duration_ms", defaults.get("downshift_duration_ms", smooth_start_ms)),
                20,
                180,
            ),
            "sustain_percent": self.clamp_int(current.get("sustain_percent", defaults.get("sustain_percent", 0)), 0, 100),
            "wall_percent": wall_percent,
            "gate_range": gate_range,
            "side": "Left" if str(current.get("side", defaults.get("side", "Right"))).strip().lower().startswith("l") else "Right",
            "upshift_sides": normalize_trigger_sides(
                current.get("upshift_sides", defaults.get("upshift_sides", "Right")),
                "Right",
            ),
            "downshift_sides": normalize_trigger_sides(
                current.get("downshift_sides", defaults.get("downshift_sides", "Left")),
                "Left",
            ),
            "early_input_soft_zone": self.clamp_int(
                current.get("early_input_soft_zone", defaults.get("early_input_soft_zone", 35)),
                0,
                60,
            ),
            "kick_late_position": self.clamp_int(
                current.get("kick_late_position", defaults.get("kick_late_position", 35)),
                0,
                100,
            ),
            "kick_softness": self.clamp_int(
                current.get("kick_softness", defaults.get("kick_softness", 7)),
                0,
                10,
            ),
            "release_duration_ms": self.clamp_int(
                current.get("release_duration_ms", defaults.get("release_duration_ms", 45)),
                0,
                120,
            ),
            "slip_off": bool(current.get("slip_off", defaults["slip_off"])),
            "slip_threshold": self.clamp_float(current.get("slip_threshold", defaults["slip_threshold"]), 0.1, 5.0),
            "slip_end_threshold": self.clamp_float(current.get("slip_end_threshold", defaults.get("slip_end_threshold", 2.2)), 0.1, 5.0),
            "slip_response_mode": slip_response_mode,
            "slip_pulse_enabled": slip_pulse_enabled,
            "slip_pulse_style": slip_pulse_style,
            "slip_drop_low_percent": self.clamp_int(current.get("slip_drop_low_percent", defaults.get("slip_drop_low_percent", 0)), 0, 100),
            "slip_low_percent": self.clamp_int(current.get("slip_low_percent", defaults.get("slip_low_percent", 10)), 0, 100),
            "slip_pulse_high_percent": self.clamp_int(current.get("slip_pulse_high_percent", defaults.get("slip_pulse_high_percent", 35)), 0, 100),
            "slip_pulse_start_percent": self.clamp_int(
                current.get("slip_pulse_start_percent", defaults.get("slip_pulse_start_percent", SLIP_PULSE_START_DEFAULT)),
                10,
                99,
            ),
            "slip_pulse_end_percent": self.clamp_int(
                current.get("slip_pulse_end_percent", defaults.get("slip_pulse_end_percent", SLIP_PULSE_END_DEFAULT)),
                100,
                150,
            ),
            "slip_pulse_rate": self.clamp_int(current.get("slip_pulse_rate", defaults.get("slip_pulse_rate", 12)), 1, SLIP_PULSE_RATE_MAX),
            "slip_rumble_amplitude": self.clamp_int(
                current.get("slip_rumble_amplitude", defaults.get("slip_rumble_amplitude", SLIP_RUMBLE_AMPLITUDE_DEFAULT)),
                1,
                255,
            ),
            "slip_rumble_rate": self.clamp_int(
                current.get("slip_rumble_rate", defaults.get("slip_rumble_rate", SLIP_RUMBLE_RATE_DEFAULT)),
                1,
                255,
            ),
            "slip_dsx_vibration_amplitude": self.clamp_int(
                current.get("slip_dsx_vibration_amplitude", defaults.get("slip_dsx_vibration_amplitude", 2)),
                1,
                8,
            ),
            "slip_dsx_vibration_frequency": self.clamp_int(
                current.get("slip_dsx_vibration_frequency", defaults.get("slip_dsx_vibration_frequency", 40)),
                1,
                40,
            ),
            "slip_dsx_vibration_margin": self.clamp_int(
                current.get("slip_dsx_vibration_margin", defaults.get("slip_dsx_vibration_margin", 0)),
                0,
                9,
            ),
            "kerb_low_hz": kerb_low_hz,
            "kerb_high_hz": kerb_high_hz,
            "kerb_l_enabled": bool(current.get("kerb_l_enabled", defaults.get("kerb_l_enabled", True))),
            "kerb_r_enabled": bool(current.get("kerb_r_enabled", defaults.get("kerb_r_enabled", True))),
            "kerb_l_start_percent": self.clamp_int(current.get("kerb_l_start_percent", start_percent), 0, 100),
            "kerb_r_start_percent": self.clamp_int(current.get("kerb_r_start_percent", start_percent), 0, 100),
            "kerb_l_low_hz": kerb_l_low_hz,
            "kerb_l_high_hz": kerb_l_high_hz,
            "kerb_r_low_hz": kerb_r_low_hz,
            "kerb_r_high_hz": kerb_r_high_hz,
            "kerb_l_low_amp": kerb_l_low_amp,
            "kerb_l_high_amp": kerb_l_high_amp,
            "kerb_r_low_amp": kerb_r_low_amp,
            "kerb_r_high_amp": kerb_r_high_amp,
            "strength": self.clamp_int(force_percent / 100.0 * 255.0, 0, 255),
            "smooth_start_ms": smooth_start_ms,
            "pulse_strength": self.normalized_dynamic_pulse_strength(
                self.clamp_int(current.get("pulse_strength", defaults.get("pulse_strength", 0)), 0, pulse_strength_max)
            ) if name == TRIGGER_BRAKE_RESISTANCE_DYNAMIC else self.clamp_int(
                current.get("pulse_strength", defaults.get("pulse_strength", 0)),
                0,
                pulse_strength_max,
            ),
            "pulse_start_percent": self.clamp_int(current.get("pulse_start_percent", defaults.get("pulse_start_percent", 0)), 0, 100),
            "pulse_offset": pulse_offset,
            "pulse_timing_offset": self.clamp_int(
                current.get("pulse_timing_offset", defaults.get("pulse_timing_offset", 0)),
                -5,
                5,
            ),
            "haptic_pulse_hz": self.clamp_int(current.get("haptic_pulse_hz", defaults.get("haptic_pulse_hz", 70)), 20, 160),
            "haptic_pulse_strength": self.clamp_int(current.get("haptic_pulse_strength", defaults.get("haptic_pulse_strength", 0)), 0, 10),
            "haptic_pulse_start_margin": self.clamp_int(
                haptic_pulse_start_current,
                -20,
                25,
            ),
            "haptic_pulse_end_margin": self.clamp_int(
                haptic_pulse_end_current,
                -20,
                25,
            ),
            "pulse_rate": self.clamp_int(current.get("pulse_rate", defaults.get("pulse_rate", 8)), 1, pulse_rate_max),
        }

    def build_effects_panel(self) -> None:
        self.effects_frame.grid_rowconfigure(0, weight=0)
        self.effects_frame.grid_rowconfigure(1, weight=1)
        self.effects_frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.effects_frame, bg="#171b20")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))

        tk.Label(
            header,
            text="Haptic Effects",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        self.select_dualsense_button = tk.Button(
            header,
            text="Select DualSense",
            command=self.show_haptic_device_popup,
            bg="#1f6feb",
            fg="#eef3ff",
            activebackground="#2f81f7",
            activeforeground="#ffffff",
            relief="raised",
            bd=1,
            highlightthickness=1,
            highlightbackground="#7db2ff",
            highlightcolor="#eef3ff",
            overrelief="raised",
            font=ui_font("Segoe UI", 7, "bold"),
            padx=ui_px(6),
            pady=ui_px(2),
        )
        self.select_dualsense_button.pack(side="right", padx=(ui_px(8), 0))

        scroll_shell = tk.Frame(self.effects_frame, bg="#171b20")
        scroll_shell.grid(row=1, column=0, sticky="nsew")
        scroll_shell.grid_rowconfigure(0, weight=1)
        scroll_shell.grid_columnconfigure(0, weight=1)
        self.effects_canvas = tk.Canvas(scroll_shell, bg="#171b20", highlightthickness=0, bd=0)
        self.effects_scrollbar = tk.Canvas(scroll_shell, bg="#171b20", width=ui_px(10), highlightthickness=0, bd=0)
        self.effects_scrollbar_thumb = None
        self.effects_canvas.configure(yscrollcommand=self.on_effects_scroll)
        self.effects_canvas.grid(row=0, column=0, sticky="nsew")
        self.effects_scrollbar.grid(row=0, column=1, sticky="ns", padx=(1, 0))
        self.effects_scrollbar.bind("<Button-1>", self.on_effects_scrollbar_click)
        self.effects_scrollbar.bind("<B1-Motion>", self.on_effects_scrollbar_click)
        self.effects_scrollbar.bind("<Configure>", lambda _event: self.schedule_layout_update("effects_scrollbar", self.update_effects_scrollbar))

        self.effects_list_frame = tk.Frame(self.effects_canvas, bg="#171b20")
        self.effects_window = self.effects_canvas.create_window((0, 0), window=self.effects_list_frame, anchor="nw")
        self.effects_list_frame.bind("<Configure>", self.on_effects_list_configure)
        self.effects_canvas.bind("<Configure>", self.on_effects_canvas_configure)
        self.effects_canvas.bind("<Enter>", self.bind_effects_mousewheel)
        self.effects_canvas.bind("<Leave>", self.unbind_effects_mousewheel)
        self.effects_list_frame.bind("<Enter>", self.bind_effects_mousewheel)
        self.effects_list_frame.bind("<Leave>", self.unbind_effects_mousewheel)
        self.effects_lock_overlay = self.create_preset_lock_overlay(self.effects_frame)

        self.build_effect_group_label("Haptic Strength")
        for effect_name in DEFAULT_EFFECT_SETTINGS:
            self.build_effect_row(effect_name)
        self.update_effect_label_styles()
        self.update_preset_lock_state()

    def build_trigger_panel(self) -> None:
        self.trigger_frame.grid_rowconfigure(0, weight=0)
        self.trigger_frame.grid_rowconfigure(1, weight=1)
        self.trigger_frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.trigger_frame, bg="#171b20")
        header.grid(row=0, column=0, sticky="ew", padx=12, pady=(12, 8))
        tk.Label(
            header,
            text="Trigger Effects",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        body = tk.Frame(self.trigger_frame, bg="#171b20")
        body.grid(row=1, column=0, sticky="nsew", padx=(8, 6), pady=(0, 10))
        body.grid_rowconfigure(0, weight=1)
        body.grid_columnconfigure(0, weight=1)
        self.trigger_canvas = tk.Canvas(body, bg="#171b20", highlightthickness=0, bd=0)
        self.trigger_scrollbar = tk.Canvas(body, bg="#171b20", width=ui_px(10), highlightthickness=0, bd=0)
        self.trigger_scrollbar_thumb = None
        self.trigger_canvas.configure(yscrollcommand=self.on_trigger_scroll)
        self.trigger_canvas.grid(row=0, column=0, sticky="nsew")
        self.trigger_scrollbar.grid(row=0, column=1, sticky="ns", padx=(1, 0))
        self.trigger_scrollbar.bind("<Button-1>", self.on_trigger_scrollbar_click)
        self.trigger_scrollbar.bind("<B1-Motion>", self.on_trigger_scrollbar_click)
        self.trigger_scrollbar.bind("<Configure>", lambda _event: self.schedule_layout_update("trigger_scrollbar", self.update_trigger_scrollbar))

        self.trigger_list_frame = tk.Frame(self.trigger_canvas, bg="#171b20")
        self.trigger_window = self.trigger_canvas.create_window((0, 0), window=self.trigger_list_frame, anchor="nw")
        self.trigger_list_frame.bind("<Configure>", self.on_trigger_list_configure)
        self.trigger_canvas.bind("<Configure>", self.on_trigger_canvas_configure)
        self.trigger_canvas.bind("<Enter>", self.bind_trigger_mousewheel)
        self.trigger_canvas.bind("<Leave>", self.unbind_trigger_mousewheel)
        self.trigger_list_frame.bind("<Enter>", self.bind_trigger_mousewheel)
        self.trigger_list_frame.bind("<Leave>", self.unbind_trigger_mousewheel)
        self.trigger_lock_overlay = self.create_preset_lock_overlay(self.trigger_frame)
        self.build_drift_relief_row()
        trigger_sections = (
            ("L2 Triggers", [name for name in BRAKE_TRIGGER_GROUP if name in DEFAULT_TRIGGER_SETTINGS]),
            ("L2R2 Triggers", [name for name in BOTH_TRIGGER_GROUP if name in DEFAULT_TRIGGER_SETTINGS]),
            ("R2 Triggers", [name for name in R2_TRIGGER_GROUP if name in DEFAULT_TRIGGER_SETTINGS]),
            ("Tools", [TRIGGER_MODE_TEST] if TRIGGER_MODE_TEST in DEFAULT_TRIGGER_SETTINGS else []),
        )
        for section_name, trigger_names in trigger_sections:
            visible_names = [name for name in trigger_names if name not in HIDDEN_TRIGGER_EFFECTS]
            if not visible_names:
                continue
            self.build_trigger_group_label(section_name)
            for trigger_name in visible_names:
                self.build_trigger_row(trigger_name)
        for trigger_name in DEFAULT_TRIGGER_SETTINGS:
            if trigger_name in HIDDEN_TRIGGER_EFFECTS:
                continue
            if any(trigger_name in names for _section, names in trigger_sections):
                continue
            self.build_trigger_row(trigger_name)
        self.update_trigger_label_styles()
        self.update_trigger_scrollbar()
        self.update_preset_lock_state()

    def build_drift_relief_row(self) -> None:
        row = tk.Frame(self.trigger_list_frame, bg="#141a20", highlightthickness=1, highlightbackground="#27313a")
        row.pack(fill="x", padx=(8, 8), pady=(0, 10), ipady=4)
        name_line = tk.Frame(row, bg="#141a20")
        name_line.pack(fill="x", padx=ui_px(6), pady=(ui_px(3), ui_px(2)))
        tk.Label(
            name_line,
            text="Drift Relief",
            bg="#141a20",
            fg="#f1c40f",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Checkbutton(
            name_line,
            text="ON",
            variable=self.drift_relief_enabled,
            command=self.on_drift_relief_changed,
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=4,
        )
        drift_toggle = name_line.winfo_children()[-1]
        drift_toggle.pack(side="right", ipady=2)
        self.drift_relief_lock_widgets = [drift_toggle]
        status_line = tk.Frame(row, bg="#141a20")
        status_line.pack(fill="x", padx=ui_px(6), pady=(0, ui_px(2)))
        tk.Label(
            status_line,
            text="softens wheelspin and throttle traction while drifting",
            bg="#141a20",
            fg="#7f8b96",
            font=ui_font("Segoe UI", 7, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            status_line,
            textvariable=self.drift_relief_status_text,
            bg="#141a20",
            fg="#f1c40f",
            font=value_font("Consolas", 8, "bold"),
            anchor="e",
            width=9,
        ).pack(side="right")

    def build_trigger_group_label(self, text: str) -> None:
        group = tk.Frame(self.trigger_list_frame, bg="#171b20")
        group.pack(fill="x", padx=(8, 4), pady=(2, 6))
        tk.Label(
            group,
            text=text,
            bg="#171b20",
            fg="#7f8b96",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Frame(group, bg="#27313a", height=1).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def build_effect_group_label(self, text: str) -> None:
        group = tk.Frame(self.effects_list_frame, bg="#171b20")
        group.pack(fill="x", padx=(6, 4), pady=(2, 6))
        tk.Label(
            group,
            text=text,
            bg="#171b20",
            fg="#7f8b96",
            font=ui_font("Segoe UI", 8, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        tk.Frame(group, bg="#27313a", height=1).pack(side="left", fill="x", expand=True, padx=(8, 0))

    def build_trigger_row(self, trigger_name: str) -> None:
        controls_state = self.trigger_controls[trigger_name]
        row_bg = "#192028" if trigger_name in BRAKE_TRIGGER_GROUP else "#171b20"
        row = tk.Frame(self.trigger_list_frame, bg=row_bg)
        row.pack(fill="x", padx=(8, 8), pady=(0, 9), ipady=3)
        name_line = tk.Frame(row, bg=row_bg)
        name_line.pack(fill="x", pady=(0, 4))
        badge_area = tk.Frame(name_line, bg=row_bg, width=ui_px(42), height=ui_px(18))
        badge_area.pack(side="left", padx=(0, 5))
        badge_area.pack_propagate(False)
        badge_area.bind("<Button-1>", lambda _event, name=trigger_name: self.select_trigger_effect(name))
        badges = self.trigger_side_badges(trigger_name)
        badge_gap = ui_px(4) if len(badges) > 1 and main_ui_scale_factor() > 1.0 else 1
        for index, (text, color) in enumerate(badges):
            badge = tk.Label(
                badge_area,
                text=text,
                bg=row_bg,
                fg=color,
                font=ui_font("Segoe UI", 8, "bold"),
                anchor="w",
                cursor="hand2",
            )
            badge.pack(side="left", padx=(0, badge_gap if index == 0 else 0))
            badge.bind("<Button-1>", lambda _event, name=trigger_name: self.select_trigger_effect(name))
        label = tk.Label(
            name_line,
            text=trigger_name,
            bg=row_bg,
            fg="#d6dde5",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
            cursor="hand2",
        )
        label.pack(side="left", fill="x", expand=True)
        label.bind("<Button-1>", lambda _event, name=trigger_name: self.select_trigger_effect(name))
        self.trigger_name_labels[trigger_name] = label
        tk.Checkbutton(
            name_line,
            text="ON",
            variable=controls_state["enabled"],
            command=lambda name=trigger_name: self.on_trigger_setting_changed(name),
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=4,
        )
        trigger_toggle = name_line.winfo_children()[-1]
        trigger_toggle.pack(side="right", ipady=2)
        self.trigger_lock_widgets[trigger_name] = [trigger_toggle]
        tk.Frame(row, bg="#222932", height=1).pack(fill="x", pady=(7, 0))

    @staticmethod
    def trigger_side_badges(trigger_name: str) -> tuple[tuple[str, str], ...]:
        left = ("L2", "#FF3399")
        right = ("R2", "#9900FF")
        if trigger_name in BRAKE_TRIGGER_GROUP:
            return (left,)
        if trigger_name in R2_TRIGGER_GROUP:
            return (right,)
        if trigger_name in BOTH_TRIGGER_GROUP:
            return (left, right)
        return ()

    def build_effect_detail_panel(self) -> None:
        self.message_frame.grid_rowconfigure(1, weight=1)
        self.message_frame.grid_columnconfigure(0, weight=1)

        header = tk.Frame(self.message_frame, bg="#171b20")
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(10, 6))
        tk.Label(
            header,
            text="Setting",
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 11, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        detail_shell = tk.Frame(self.message_frame, bg="#171b20")
        detail_shell.grid(row=1, column=0, sticky="nsew", padx=(14, 4), pady=(0, 12))
        detail_shell.grid_rowconfigure(0, weight=1)
        detail_shell.grid_columnconfigure(0, weight=1)
        self.detail_canvas = tk.Canvas(detail_shell, bg="#171b20", highlightthickness=0, bd=0)
        self.detail_scrollbar = tk.Canvas(detail_shell, bg="#171b20", width=ui_px(10), highlightthickness=0, bd=0)
        self.detail_scrollbar_thumb = None
        self.detail_canvas.configure(yscrollcommand=self.on_detail_scroll)
        self.detail_canvas.grid(row=0, column=0, sticky="nsew")
        self.detail_scrollbar.grid(row=0, column=1, sticky="ns", padx=(2, 1))
        self.detail_scrollbar.bind("<Button-1>", self.on_detail_scrollbar_click)
        self.detail_scrollbar.bind("<B1-Motion>", self.on_detail_scrollbar_click)
        self.detail_scrollbar.bind("<Configure>", lambda _event: self.schedule_layout_update("detail_scrollbar", self.update_detail_scrollbar))

        self.effect_detail_body = tk.Frame(self.detail_canvas, bg="#171b20")
        self.detail_window = self.detail_canvas.create_window((0, 0), window=self.effect_detail_body, anchor="nw")
        self.effect_detail_body.bind("<Configure>", self.on_detail_body_configure)
        self.detail_canvas.bind("<Configure>", self.on_detail_canvas_configure)
        self.detail_canvas.bind("<Enter>", self.bind_detail_mousewheel)
        self.detail_canvas.bind("<Leave>", self.unbind_detail_mousewheel)
        self.effect_detail_body.bind("<Enter>", self.bind_detail_mousewheel)
        self.effect_detail_body.bind("<Leave>", self.unbind_detail_mousewheel)
        self.detail_lock_overlay = self.create_preset_lock_overlay(self.message_frame)
        self.refresh_effect_detail_panel()

    def refresh_effect_detail_panel(self) -> None:
        for child in self.effect_detail_body.winfo_children():
            child.destroy()
        self.slip_pulse_option_widgets = {
            "shared": [],
            "wave": [],
            "rumble": [],
            "dsx_vibration": [],
        }

        if self.selected_detail_type.get() == "trigger":
            self.refresh_trigger_detail_panel()
            self.update_slip_pulse_option_styles()
            self.apply_detail_lock_state()
            return

        effect_name = self.selected_output_effect.get()
        controls_state = self.effect_controls.get(effect_name)
        if not controls_state:
            return

        self.effect_detail_body.grid_columnconfigure(0, weight=1)
        title_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        title_row.grid(row=0, column=0, sticky="ew")
        tk.Label(
            title_row,
            text=effect_name,
            bg="#171b20",
            fg="#f5f7fa",
            font=ui_font("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)

        row_index = 1
        volume_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        volume_row.grid(row=row_index, column=0, sticky="ew", pady=(12, 0))
        volume_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            volume_row,
            text="Volume",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=8,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Scale(
            volume_row,
            from_=0,
            to=10,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=controls_state["volume"],
            command=lambda value, name=effect_name: self.on_effect_slider_changed(name, value),
            bg="#f1c40f",
            fg="#aeb8c4",
            troughcolor="#2a3139",
            activebackground="#f1c40f",
            highlightthickness=0,
            length=ui_px(294),
            sliderlength=ui_px(18),
            sliderrelief="flat",
            bd=0,
            width=ui_px(10),
        ).grid(row=0, column=1, sticky="w", padx=(8, 3))
        entry = tk.Entry(
            volume_row,
            textvariable=controls_state["volume_text"],
            bg="#1d232a",
            fg="#d6dde5",
            insertbackground="#d6dde5",
            relief="flat",
            font=value_font("Consolas", 9, "bold"),
            width=3,
            justify="center",
        )
        entry.grid(row=0, column=2, ipady=2)
        entry.bind("<Return>", lambda event, name=effect_name: self.on_effect_volume_entered(name, event))
        entry.bind("<FocusOut>", lambda event, name=effect_name: self.on_effect_volume_entered(name, event))

        if effect_name in PAN_EFFECTS and "pan" in controls_state:
            pan_row = tk.Frame(self.effect_detail_body, bg="#171b20")
            pan_row.grid(row=row_index + 1, column=0, sticky="ew", pady=(10, 0))
            pan_row.grid_columnconfigure(3, weight=1)
            tk.Label(
                pan_row,
                text="L/R",
                bg="#171b20",
                fg="#aeb8c4",
                font=ui_font("Segoe UI", 9, "bold"),
                width=8,
                anchor="w",
            ).grid(row=0, column=0, sticky="w")
            tk.Label(
                pan_row,
                text="L",
                bg="#171b20",
                fg="#7f8a96",
                font=ui_font("Segoe UI", 8, "bold"),
            ).grid(row=0, column=1, sticky="w", padx=(8, 0))
            tk.Scale(
                pan_row,
                from_=0,
                to=10,
                orient="horizontal",
                resolution=1,
                showvalue=False,
                variable=controls_state["pan"],
                command=lambda value, name=effect_name: self.on_effect_pan_changed(name, value),
                bg="#f1c40f",
                fg="#aeb8c4",
                troughcolor="#2a3139",
                activebackground="#f1c40f",
                highlightthickness=0,
                length=ui_px(294),
                sliderlength=ui_px(18),
                sliderrelief="flat",
                bd=0,
                width=ui_px(10),
            ).grid(row=0, column=1, sticky="w", padx=(26, 26))
            tk.Label(
                pan_row,
                text="R",
                bg="#171b20",
                fg="#7f8a96",
                font=ui_font("Segoe UI", 8, "bold"),
            ).grid(row=0, column=1, sticky="e", padx=(0, 8))
            tk.Label(
                pan_row,
                textvariable=controls_state["pan_text"],
                bg="#1d232a",
                fg="#d6dde5",
                font=value_font("Consolas", 9, "bold"),
                width=3,
                anchor="center",
            ).grid(row=0, column=2, ipady=2)
        self.apply_detail_lock_state()

    def refresh_trigger_detail_panel(self) -> None:
        trigger_name = self.selected_trigger_effect.get()
        controls_state = self.trigger_controls.get(trigger_name)
        if not controls_state:
            return

        self.effect_detail_body.grid_columnconfigure(0, weight=1)
        title_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        title_row.grid(row=0, column=0, sticky="ew")
        tk.Label(
            title_row,
            text=trigger_name,
            bg="#171b20",
            fg="#f5f7fa",
            font=ui_font("Segoe UI", 12, "bold"),
            anchor="w",
        ).pack(side="left", fill="x", expand=True)
        if trigger_name == TRIGGER_BRAKE_PRESSURE:
            self.build_trigger_int_control(1, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Resistance Start Position", controls_state["start_percent"], controls_state["start_text"], 0, 100)
            self.build_trigger_int_control(3, "Resistance Max Position", controls_state["max_percent"], controls_state["max_text"], 0, 100)
            return

        if trigger_name == TRIGGER_THROTTLE_PRESSURE:
            self.build_trigger_int_control(1, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Resistance Start Position", controls_state["start_percent"], controls_state["start_text"], 0, 100)
            self.build_trigger_int_control(3, "Resistance Max Position", controls_state["max_percent"], controls_state["max_text"], 0, 100)
            self.build_trigger_int_control(4, "Smooth Start", controls_state["smooth_start_ms"], controls_state["smooth_start_text"], 0, 300)
            return

        if trigger_name == TRIGGER_BRAKE_RESISTANCE_DYNAMIC:
            self.build_brake_dynamic_preset_row(1, controls_state)
            self.brake_dynamic_strength_limited_ui = False
            self.build_trigger_int_control(2, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(3, "Base Wall Position", controls_state["start_percent"], controls_state["start_text"], 40, 100)
            self.build_trigger_int_control(4, "Minimum Wall Position", controls_state["max_percent"], controls_state["max_text"], 30, 95)
            self.build_trigger_int_control(5, "Prediction Strength", controls_state["wall_percent"], controls_state["wall_text"], 0, 40)
            self.build_trigger_int_control(6, "Pulse Strength", controls_state["pulse_strength"], controls_state["pulse_strength_text"], 0, 100)
            self.build_trigger_int_control(7, "Pulse Start Position", controls_state["pulse_start_percent"], controls_state["pulse_start_text"], 0, 100)
            self.build_trigger_int_control(8, "Pulse Timing Offset", controls_state["pulse_timing_offset"], controls_state["pulse_timing_offset_text"], -5, 5)
            self.build_trigger_int_control(9, "Pulse Rate", controls_state["pulse_rate"], controls_state["pulse_rate_text"], 1, 255)
            self.build_trigger_int_control(10, "Pulse Haptic Hz", controls_state["haptic_pulse_hz"], controls_state["haptic_pulse_hz_text"], 20, 160)
            self.build_trigger_int_control(11, "Pulse Haptic Strength", controls_state["haptic_pulse_strength"], controls_state["haptic_pulse_strength_text"], 0, 10)
            self.build_trigger_haptic_zone_control(
                12,
                "Pulse Haptic Zone",
                controls_state["haptic_pulse_start_margin"],
                controls_state["haptic_pulse_start_margin_text"],
                controls_state["haptic_pulse_end_margin"],
                controls_state["haptic_pulse_end_margin_text"],
                -20,
                25,
            )
            self.build_trigger_scaled_control(
                13,
                "Slip Off Threshold",
                controls_state["slip_threshold"],
                controls_state["slip_threshold_text"],
                1,
                50,
                10.0,
            )
            self.build_trigger_int_control(14, "Slip Drop Low Resistance", controls_state["slip_drop_low_percent"], controls_state["slip_drop_low_text"], 0, 100)
            self.build_trigger_slip_response_mode_row(15, controls_state)
            self.build_trigger_int_control(16, "Slip Pulse Start Level", controls_state["slip_pulse_start_percent"], controls_state["slip_pulse_start_text"], 10, 99, "shared")
            self.build_trigger_int_control(17, "Slip Pulse End Level", controls_state["slip_pulse_end_percent"], controls_state["slip_pulse_end_text"], 100, 150, "shared")
            self.build_trigger_separator(22)
            self.build_trigger_int_control(23, "Slip Pulse Rumble Amplitude", controls_state["slip_rumble_amplitude"], controls_state["slip_rumble_amplitude_text"], 1, 255, "rumble")
            self.build_trigger_int_control(24, "Slip Pulse Rumble Rate", controls_state["slip_rumble_rate"], controls_state["slip_rumble_rate_text"], 1, 255, "rumble")
            self.build_trigger_separator(25)
            self.build_trigger_int_control(26, "Slip Pulse Wave Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8, "dsx_vibration")
            self.build_trigger_int_control(27, "Slip Pulse Wave Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40, "dsx_vibration")
            self.build_trigger_int_control(28, "Slip Pulse Wave Zone Margin", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9, "dsx_vibration")
            return

        if trigger_name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE:
            self.build_trigger_int_control(1, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Base Wall Position", controls_state["start_percent"], controls_state["start_text"], 40, 100)
            self.build_trigger_int_control(3, "Minimum Wall Position", controls_state["max_percent"], controls_state["max_text"], 30, 95)
            self.build_trigger_int_control(4, "Prediction Strength", controls_state["wall_percent"], controls_state["wall_text"], 0, 40)
            self.build_trigger_scaled_control(
                5,
                "Slip Off Threshold",
                controls_state["slip_threshold"],
                controls_state["slip_threshold_text"],
                1,
                50,
                10.0,
            )
            self.build_trigger_int_control(6, "Slip Drop Low Resistance", controls_state["slip_drop_low_percent"], controls_state["slip_drop_low_text"], 0, 100)
            self.build_trigger_slip_response_mode_row(7, controls_state)
            self.build_trigger_int_control(8, "Slip Pulse Start Level", controls_state["slip_pulse_start_percent"], controls_state["slip_pulse_start_text"], 10, 99, "shared")
            self.build_trigger_int_control(9, "Slip Pulse End Level", controls_state["slip_pulse_end_percent"], controls_state["slip_pulse_end_text"], 100, 150, "shared")
            self.build_trigger_separator(14)
            self.build_trigger_int_control(15, "Slip Pulse Rumble Amplitude", controls_state["slip_rumble_amplitude"], controls_state["slip_rumble_amplitude_text"], 1, 255, "rumble")
            self.build_trigger_int_control(16, "Slip Pulse Rumble Rate", controls_state["slip_rumble_rate"], controls_state["slip_rumble_rate_text"], 1, 255, "rumble")
            self.build_trigger_separator(17)
            self.build_trigger_int_control(18, "Slip Pulse Wave Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8, "dsx_vibration")
            self.build_trigger_int_control(19, "Slip Pulse Wave Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40, "dsx_vibration")
            self.build_trigger_int_control(20, "Slip Pulse Wave Zone Margin", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9, "dsx_vibration")
            return

        if trigger_name == TRIGGER_RPM_REV_LIMIT:
            self.build_trigger_rev_limit_style_row(1, controls_state)
            self.build_trigger_int_control(2, "Pulse Start Position", controls_state["start_percent"], controls_state["start_text"], 80, 100)
            self.build_trigger_separator(3)
            self.build_trigger_int_control(4, "Rumble Amplitude", controls_state["slip_rumble_amplitude"], controls_state["slip_rumble_amplitude_text"], 1, 255, "rumble")
            self.build_trigger_int_control(5, "Rumble Rate", controls_state["slip_rumble_rate"], controls_state["slip_rumble_rate_text"], 1, 255, "rumble")
            self.build_trigger_separator(6)
            self.build_trigger_int_control(7, "Wave Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8, "dsx_vibration")
            self.build_trigger_int_control(8, "Wave Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40, "dsx_vibration")
            self.build_trigger_int_control(9, "Wave Start Zone", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9, "dsx_vibration")
            return

        if trigger_name == TRIGGER_MODE_TEST:
            self.build_trigger_mode_test_controls()
            return

        if trigger_name == TRIGGER_THROTTLE_TRACTION_LIMIT:
            self.build_trigger_int_control(1, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Minimum Wall Position", controls_state["max_percent"], controls_state["max_text"], 20, 95)
            self.build_trigger_int_control(3, "Prediction Strength", controls_state["wall_percent"], controls_state["wall_text"], 0, 60)
            self.build_trigger_scaled_control(
                4,
                "Slip Threshold",
                controls_state["slip_threshold"],
                controls_state["slip_threshold_text"],
                1,
                50,
                10.0,
            )
            self.build_trigger_scaled_control(
                5,
                "Slip Off End",
                controls_state["slip_end_threshold"],
                controls_state["slip_end_threshold_text"],
                1,
                50,
                10.0,
            )
            self.build_trigger_int_control(6, "Slip Off Resistance", controls_state["slip_drop_low_percent"], controls_state["slip_drop_low_text"], 0, 100)
            self.build_trigger_slip_response_mode_row(7, controls_state)
            self.build_trigger_int_control(8, "Slip Pulse Start Level", controls_state["slip_pulse_start_percent"], controls_state["slip_pulse_start_text"], 10, 99, "shared")
            self.build_trigger_int_control(9, "Slip Pulse End Level", controls_state["slip_pulse_end_percent"], controls_state["slip_pulse_end_text"], 100, 150, "shared")
            self.build_trigger_separator(14)
            self.build_trigger_int_control(15, "Slip Pulse Rumble Amplitude", controls_state["slip_rumble_amplitude"], controls_state["slip_rumble_amplitude_text"], 1, 255, "rumble")
            self.build_trigger_int_control(16, "Slip Pulse Rumble Rate", controls_state["slip_rumble_rate"], controls_state["slip_rumble_rate_text"], 1, 255, "rumble")
            self.build_trigger_separator(17)
            self.build_trigger_int_control(18, "Slip Pulse Wave Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8, "dsx_vibration")
            self.build_trigger_int_control(19, "Slip Pulse Wave Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40, "dsx_vibration")
            self.build_trigger_int_control(20, "Slip Pulse Wave Zone Margin", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9, "dsx_vibration")
            return

        if trigger_name == TRIGGER_GEAR_SHIFT_KICK:
            self.build_trigger_int_control(1, "Upshift Kick Strength", controls_state["upshift_strength_percent"], controls_state["upshift_strength_text"], 0, 100)
            self.build_trigger_int_control(2, "Upshift Kick Duration", controls_state["upshift_duration_ms"], controls_state["upshift_duration_text"], 20, 180)
            self.build_trigger_multi_side_control(3, "Upshift Side", controls_state["upshift_sides"], "Right")
            self.build_trigger_separator(4)
            self.build_trigger_int_control(5, "Downshift Kick Strength", controls_state["downshift_strength_percent"], controls_state["downshift_strength_text"], 0, 100)
            self.build_trigger_int_control(6, "Downshift Kick Duration", controls_state["downshift_duration_ms"], controls_state["downshift_duration_text"], 20, 180)
            self.build_trigger_multi_side_control(7, "Downshift Side", controls_state["downshift_sides"], "Left")
            self.build_trigger_int_control(8, "Early Input Soft Zone", controls_state["early_input_soft_zone"], controls_state["early_input_soft_zone_text"], 0, 60)
            self.build_trigger_int_control(9, "Kick Late Position", controls_state["kick_late_position"], controls_state["kick_late_position_text"], 0, 100)
            self.build_trigger_int_control(10, "Kick Softness", controls_state["kick_softness"], controls_state["kick_softness_text"], 0, 10)
            self.build_trigger_int_control(11, "Kick Release Duration", controls_state["release_duration_ms"], controls_state["release_duration_text"], 0, 120)
            return

        if trigger_name == TRIGGER_COLLISION_KICK:
            self.build_trigger_int_control(1, "Kick Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Kick Duration", controls_state["smooth_start_ms"], controls_state["smooth_start_text"], 40, 300)
            return

        if trigger_name == TRIGGER_KERB_BUZZ:
            self.build_trigger_toggle_row(1, "L Active", controls_state["kerb_l_enabled"])
            self.build_trigger_int_control(2, "L2 Trigger Start Position", controls_state["kerb_l_start_percent"], controls_state["kerb_l_start_text"], 0, 100)
            self.build_trigger_range_control(
                3,
                "L2 Speed Frequency Range",
                controls_state["kerb_l_low_hz"],
                controls_state["kerb_l_low_hz_text"],
                controls_state["kerb_l_high_hz"],
                controls_state["kerb_l_high_hz_text"],
                1,
                40,
            )
            self.build_trigger_range_control(
                4,
                "L2 Speed Wave Amplitude Range",
                controls_state["kerb_l_low_amp"],
                controls_state["kerb_l_low_amp_text"],
                controls_state["kerb_l_high_amp"],
                controls_state["kerb_l_high_amp_text"],
                1,
                8,
            )
            self.build_trigger_separator(5)
            self.build_trigger_toggle_row(6, "R Active", controls_state["kerb_r_enabled"])
            self.build_trigger_int_control(7, "R2 Trigger Start Position", controls_state["kerb_r_start_percent"], controls_state["kerb_r_start_text"], 0, 100)
            self.build_trigger_range_control(
                8,
                "R2 Speed Frequency Range",
                controls_state["kerb_r_low_hz"],
                controls_state["kerb_r_low_hz_text"],
                controls_state["kerb_r_high_hz"],
                controls_state["kerb_r_high_hz_text"],
                1,
                40,
            )
            self.build_trigger_range_control(
                9,
                "R2 Speed Wave Amplitude Range",
                controls_state["kerb_r_low_amp"],
                controls_state["kerb_r_low_amp_text"],
                controls_state["kerb_r_high_amp"],
                controls_state["kerb_r_high_amp_text"],
                1,
                8,
            )
            return

        if trigger_name == TRIGGER_IMPACT_TICK:
            self.build_trigger_int_control(1, "Tick Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8)
            self.build_trigger_int_control(2, "Tick Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40)
            self.build_trigger_int_control(3, "Tick Start Zone", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9)
            self.build_trigger_int_control(4, "Tick Duration", controls_state["smooth_start_ms"], controls_state["smooth_start_text"], 40, 300)
            return

        if trigger_name == TRIGGER_BRAKE_RESISTANCE:
            self.build_trigger_int_control(1, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
            self.build_trigger_int_control(2, "Resistance Start Position", controls_state["start_percent"], controls_state["start_text"], 0, 100)
            self.build_trigger_scaled_control(
                3,
                "Slip Threshold",
                controls_state["slip_threshold"],
                controls_state["slip_threshold_text"],
                1,
                50,
                10.0,
            )
            self.build_trigger_int_control(4, "Slip Drop Low Resistance", controls_state["slip_drop_low_percent"], controls_state["slip_drop_low_text"], 0, 100)
            self.build_trigger_slip_response_mode_row(5, controls_state)
            self.build_trigger_int_control(6, "Slip Pulse Start Level", controls_state["slip_pulse_start_percent"], controls_state["slip_pulse_start_text"], 10, 99, "shared")
            self.build_trigger_int_control(7, "Slip Pulse End Level", controls_state["slip_pulse_end_percent"], controls_state["slip_pulse_end_text"], 100, 150, "shared")
            self.build_trigger_separator(12)
            self.build_trigger_int_control(13, "Slip Pulse Rumble Amplitude", controls_state["slip_rumble_amplitude"], controls_state["slip_rumble_amplitude_text"], 1, 255, "rumble")
            self.build_trigger_int_control(14, "Slip Pulse Rumble Rate", controls_state["slip_rumble_rate"], controls_state["slip_rumble_rate_text"], 1, 255, "rumble")
            self.build_trigger_separator(15)
            self.build_trigger_int_control(16, "Slip Pulse Wave Amplitude", controls_state["slip_dsx_vibration_amplitude"], controls_state["slip_dsx_vibration_amplitude_text"], 1, 8, "dsx_vibration")
            self.build_trigger_int_control(17, "Slip Pulse Wave Frequency", controls_state["slip_dsx_vibration_frequency"], controls_state["slip_dsx_vibration_frequency_text"], 1, 40, "dsx_vibration")
            self.build_trigger_int_control(18, "Slip Pulse Wave Zone Margin", controls_state["slip_dsx_vibration_margin"], controls_state["slip_dsx_vibration_margin_text"], 0, 9, "dsx_vibration")
            return

        self.build_trigger_int_control(1, "Curve", controls_state["curve"], controls_state["curve_text"], 0, 9)
        self.build_trigger_int_control(2, "Resistance Start Position", controls_state["start_percent"], controls_state["start_text"], 0, 100)
        self.build_trigger_int_control(3, "Resistance Max Position", controls_state["max_percent"], controls_state["max_text"], 0, 100)
        self.build_trigger_int_control(4, "Resistance Strength", controls_state["force_percent"], controls_state["force_text"], 0, 100)
        self.build_trigger_int_control(5, "Smooth Start", controls_state["smooth_start_ms"], controls_state["smooth_start_text"], 0, 300)
        self.build_trigger_scaled_control(
            6,
            "Slip Threshold",
            controls_state["slip_threshold"],
            controls_state["slip_threshold_text"],
            1,
            50,
            10.0,
        )

        self.build_trigger_slip_response_mode_row(7, controls_state)

    def build_trigger_slip_off_row(self, row: int, controls_state: dict[str, tk.Variable]) -> None:
        slip_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        slip_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        tk.Label(
            slip_row,
            text="Resistance Off On Slip",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=26,
            anchor="w",
        ).pack(side="left")
        tk.Checkbutton(
            slip_row,
            text="ON",
            variable=controls_state["slip_off"],
            command=self.on_trigger_setting_changed,
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=5,
        ).pack(side="left", ipady=2)

    def build_trigger_rev_limit_style_row(self, row: int, controls_state: dict[str, tk.Variable]) -> None:
        mode_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        mode_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        tk.Label(
            mode_row,
            text="Mode",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=26,
            anchor="w",
        ).pack(side="left")

        spacer = tk.Frame(mode_row, bg="#171b20", width=108)
        spacer.pack(side="left")
        spacer.pack_propagate(False)

        style_buttons: dict[str, tk.Button] = {}
        available_styles = (
            SLIP_PULSE_STYLE_WAVE,
            SLIP_PULSE_STYLE_RUMBLE,
        )
        for style in available_styles:
            button = tk.Button(
                mode_row,
                text=style,
                command=lambda selected=style: self.on_slip_pulse_style_selected(controls_state, selected),
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=ui_font("Segoe UI", 8, "bold"),
                width=7,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0 if style == available_styles[0] else 4, 0), ipady=2)
            style_buttons[style] = button
        controls_state["_slip_pulse_style_trigger_name"] = TRIGGER_RPM_REV_LIMIT
        controls_state["_slip_pulse_style_buttons"] = style_buttons
        self.update_slip_pulse_style_buttons(controls_state)

    def build_trigger_slip_response_mode_row(self, row: int, controls_state: dict[str, tk.Variable]) -> None:
        pulse_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        pulse_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        tk.Label(
            pulse_row,
            text="Slip Pulse",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=26,
            anchor="w",
        ).pack(side="left")
        tk.Checkbutton(
            pulse_row,
            text="ON",
            variable=controls_state["slip_pulse_enabled"],
            command=self.on_trigger_setting_changed,
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=5,
        ).pack(side="left", ipady=2)

        spacer = tk.Frame(pulse_row, bg="#171b20", width=108)
        spacer.pack(side="left")
        spacer.pack_propagate(False)

        style_buttons: dict[str, tk.Button] = {}
        selected_trigger = self.selected_trigger_effect.get()
        wave_trigger_names = {
            TRIGGER_BRAKE_RESISTANCE,
            TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
            TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
            TRIGGER_THROTTLE_TRACTION_LIMIT,
        }
        available_styles = (
            SLIP_PULSE_STYLE_WAVE,
            SLIP_PULSE_STYLE_RUMBLE,
        ) if selected_trigger in wave_trigger_names else (
            SLIP_PULSE_STYLE_PULSE_KICK,
            SLIP_PULSE_STYLE_RUMBLE,
        )
        for style in available_styles:
            button = tk.Button(
                pulse_row,
                text=style,
                command=lambda selected=style: self.on_slip_pulse_style_selected(controls_state, selected),
                relief="flat",
                bd=0,
                highlightthickness=0,
                font=ui_font("Segoe UI", 8, "bold"),
                width=7,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0 if style == available_styles[0] else 4, 0), ipady=2)
            style_buttons[style] = button
        controls_state["_slip_pulse_style_trigger_name"] = selected_trigger
        controls_state["_slip_pulse_style_buttons"] = style_buttons
        self.update_slip_pulse_style_buttons(controls_state)

    def on_slip_pulse_style_selected(self, controls_state: dict[str, tk.Variable], style: str) -> None:
        trigger_name = str(controls_state.get("_slip_pulse_style_trigger_name", self.selected_trigger_effect.get()))
        style = normalize_slip_pulse_style(style, trigger_name)
        controls_state["slip_pulse_style"].set(style)
        self.update_slip_pulse_style_buttons(controls_state)
        self.update_slip_pulse_option_styles()
        self.on_trigger_setting_changed()

    def update_slip_pulse_style_buttons(self, controls_state: dict[str, tk.Variable]) -> None:
        buttons = controls_state.get("_slip_pulse_style_buttons")
        if not isinstance(buttons, dict):
            return
        trigger_name = str(controls_state.get("_slip_pulse_style_trigger_name", self.selected_trigger_effect.get()))
        enabled = True if trigger_name == TRIGGER_RPM_REV_LIMIT else bool(controls_state["slip_pulse_enabled"].get())
        selected_style = normalize_slip_pulse_style(
            controls_state["slip_pulse_style"].get(),
            trigger_name,
        )
        if selected_style not in buttons:
            selected_style = next(iter(buttons.keys()), SLIP_PULSE_STYLE_PULSE_KICK)
            controls_state["slip_pulse_style"].set(selected_style)
        for style, button in buttons.items():
            selected = style == selected_style
            if selected and enabled:
                bg, fg = "#f1c40f", "#101316"
            elif selected:
                bg, fg = "#6f5d14", "#c7ccd2"
            elif enabled:
                bg, fg = "#252c35", "#d6dde5"
            else:
                bg, fg = "#20252c", "#6f7780"
            button.configure(
                bg=bg,
                fg=fg,
                activebackground=bg,
                activeforeground=fg,
                disabledforeground=fg,
                state="normal" if enabled else "disabled",
            )

    def update_slip_pulse_option_styles(self) -> None:
        groups = getattr(self, "slip_pulse_option_widgets", {})
        if not groups:
            return
        trigger_name = self.selected_trigger_effect.get()
        controls_state = self.trigger_controls.get(trigger_name)
        pulse_enabled = False
        selected_style = SLIP_PULSE_STYLE_PULSE_KICK
        if controls_state is not None:
            pulse_enabled = True if trigger_name == TRIGGER_RPM_REV_LIMIT else bool(controls_state["slip_pulse_enabled"].get())
            selected_style = normalize_slip_pulse_style(
                controls_state["slip_pulse_style"].get(),
                trigger_name,
            )
        group_active = {
            "shared": pulse_enabled,
            "wave": pulse_enabled and selected_style == SLIP_PULSE_STYLE_PULSE_KICK,
            "rumble": pulse_enabled and selected_style == SLIP_PULSE_STYLE_RUMBLE,
            "dsx_vibration": pulse_enabled and selected_style == SLIP_PULSE_STYLE_WAVE,
        }
        for group, widgets in groups.items():
            active = bool(group_active.get(group, True))
            label_color = "#aeb8c4" if active else "#6f7780"
            widget_state = "normal" if active else "disabled"
            slider_color = "#f1c40f" if active else "#6f5d14"
            for widget in widgets:
                try:
                    if isinstance(widget, tk.Label):
                        widget.configure(fg=label_color)
                    elif isinstance(widget, tk.Scale):
                        widget.configure(
                            state=widget_state,
                            bg=slider_color,
                            activebackground=slider_color,
                            troughcolor="#2a3139",
                        )
                    elif isinstance(widget, tk.Entry):
                        widget.configure(
                            state=widget_state,
                            bg="#1d232a",
                            disabledbackground="#1d232a",
                            disabledforeground="#6f7780",
                        )
                    else:
                        widget.configure(state=widget_state)
                except tk.TclError:
                    pass

    def build_trigger_haptic_zone_control(
        self,
        row: int,
        label_text: str,
        start_var: tk.IntVar,
        start_text_var: tk.StringVar,
        end_var: tk.IntVar,
        end_text_var: tk.StringVar,
        minimum: int,
        maximum: int,
    ) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        canvas = tk.Canvas(
            control_row,
            width=ui_px(210),
            height=ui_px(24),
            bg="#171b20",
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        canvas.grid(row=0, column=1, sticky="w", padx=(8, 3))
        value_label = tk.Label(
            control_row,
            bg="#1d232b",
            fg="#d6dde5",
            font=value_font("Consolas", 9, "bold"),
            width=6,
            anchor="center",
        )
        value_label.grid(row=0, column=2, sticky="w", ipady=2)

        drag_state = {"handle": "", "last_value": 0}

        def normalized_values() -> tuple[int, int]:
            start = self.clamp_int(start_var.get(), minimum, maximum)
            end = self.clamp_int(end_var.get(), minimum, maximum)
            if start < end:
                start = end
            start_var.set(start)
            end_var.set(end)
            start_text_var.set(str(start))
            end_text_var.set(str(end))
            return start, end

        def value_to_x(value: int, width: int) -> float:
            pad = 0.0
            span = max(1.0, width - pad * 2.0)
            ratio = (maximum - value) / max(1.0, maximum - minimum)
            return pad + span * max(0.0, min(1.0, ratio))

        def x_to_value(x: float, width: int) -> int:
            pad = 0.0
            span = max(1.0, width - pad * 2.0)
            ratio = max(0.0, min(1.0, (x - pad) / span))
            return self.clamp_int(round(maximum - ratio * (maximum - minimum)), minimum, maximum)

        def draw(_event=None) -> None:
            width = max(210, canvas.winfo_width())
            start, end = normalized_values()
            start_x = value_to_x(start, width)
            end_x = value_to_x(end, width)
            y = 12
            bar_height = 10
            canvas.delete("all")
            canvas.create_rectangle(0, y - bar_height // 2, width, y + bar_height // 2, fill="#2b333d", outline="")
            canvas.create_rectangle(start_x, y - bar_height // 2, end_x, y + bar_height // 2, fill="#f1c40f", outline="")
            value_label.configure(text=f"{start}-{end}")

        def save_and_draw() -> None:
            draw()
            self.normalize_dynamic_brake_strength()
            self.normalize_trigger_ranges()
            self.save_trigger_settings()

        def on_press(event) -> None:
            width = max(210, canvas.winfo_width())
            start, end = normalized_values()
            start_x = value_to_x(start, width)
            end_x = value_to_x(end, width)
            edge_grab = 12
            if start_x + edge_grab < event.x < end_x - edge_grab:
                drag_state["handle"] = "range"
                drag_state["last_value"] = x_to_value(event.x, width)
                return
            drag_state["handle"] = "start" if abs(event.x - start_x) <= abs(event.x - end_x) else "end"
            on_drag(event)

        def on_drag(event) -> None:
            width = max(210, canvas.winfo_width())
            value = x_to_value(event.x, width)
            if drag_state["handle"] == "start":
                value = max(value, self.clamp_int(end_var.get(), minimum, maximum))
                start_var.set(value)
                start_text_var.set(str(value))
            elif drag_state["handle"] == "range":
                previous_value = int(drag_state.get("last_value", value))
                delta = value - previous_value
                start = self.clamp_int(start_var.get(), minimum, maximum)
                end = self.clamp_int(end_var.get(), minimum, maximum)
                new_start = start + delta
                new_end = end + delta
                if new_start > maximum:
                    delta -= new_start - maximum
                if new_end < minimum:
                    delta += minimum - new_end
                new_start = self.clamp_int(start + delta, minimum, maximum)
                new_end = self.clamp_int(end + delta, minimum, maximum)
                if new_start >= new_end:
                    start_var.set(new_start)
                    end_var.set(new_end)
                    start_text_var.set(str(new_start))
                    end_text_var.set(str(new_end))
                drag_state["last_value"] = value
            else:
                value = min(value, self.clamp_int(start_var.get(), minimum, maximum))
                end_var.set(value)
                end_text_var.set(str(value))
            save_and_draw()

        canvas.bind("<Configure>", draw)
        canvas.bind("<Button-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        draw()

    def build_trigger_toggle_row(self, row: int, label_text: str, enabled_var: tk.BooleanVar) -> None:
        toggle_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        toggle_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        tk.Label(
            toggle_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).pack(side="left")
        tk.Checkbutton(
            toggle_row,
            text="ON",
            variable=enabled_var,
            command=self.on_trigger_setting_changed,
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=5,
        ).pack(side="left", ipady=2)

    def build_trigger_range_control(
        self,
        row: int,
        label_text: str,
        low_var: tk.IntVar,
        low_text_var: tk.StringVar,
        high_var: tk.IntVar,
        high_text_var: tk.StringVar,
        minimum: int,
        maximum: int,
    ) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        canvas = tk.Canvas(
            control_row,
            width=ui_px(210),
            height=ui_px(24),
            bg="#171b20",
            highlightthickness=0,
            bd=0,
            cursor="hand2",
        )
        canvas.grid(row=0, column=1, sticky="w", padx=(8, 3))
        value_label = tk.Label(
            control_row,
            bg="#1d232b",
            fg="#d6dde5",
            font=value_font("Consolas", 9, "bold"),
            width=6,
            anchor="center",
        )
        value_label.grid(row=0, column=2, sticky="w", ipady=2)

        drag_state = {"handle": "", "last_value": 0}

        def normalized_values() -> tuple[int, int]:
            low = self.clamp_int(low_var.get(), minimum, maximum)
            high = self.clamp_int(high_var.get(), minimum, maximum)
            if low > high:
                low, high = high, low
            low_var.set(low)
            high_var.set(high)
            low_text_var.set(str(low))
            high_text_var.set(str(high))
            return low, high

        def value_to_x(value: int, width: int) -> float:
            span = max(1.0, float(width))
            ratio = (value - minimum) / max(1.0, maximum - minimum)
            return span * max(0.0, min(1.0, ratio))

        def x_to_value(x: float, width: int) -> int:
            span = max(1.0, float(width))
            ratio = max(0.0, min(1.0, x / span))
            return self.clamp_int(round(minimum + ratio * (maximum - minimum)), minimum, maximum)

        def draw(_event=None) -> None:
            width = max(210, canvas.winfo_width())
            low, high = normalized_values()
            low_x = value_to_x(low, width)
            high_x = value_to_x(high, width)
            y = 12
            bar_height = 10
            canvas.delete("all")
            canvas.create_rectangle(0, y - bar_height // 2, width, y + bar_height // 2, fill="#2b333d", outline="")
            canvas.create_rectangle(low_x, y - bar_height // 2, high_x, y + bar_height // 2, fill="#f1c40f", outline="")
            value_label.configure(text=f"{low}-{high}")

        def save_and_draw() -> None:
            draw()
            self.save_trigger_settings()

        def on_press(event) -> None:
            width = max(210, canvas.winfo_width())
            low, high = normalized_values()
            low_x = value_to_x(low, width)
            high_x = value_to_x(high, width)
            edge_grab = 12
            if low_x + edge_grab < event.x < high_x - edge_grab:
                drag_state["handle"] = "range"
                drag_state["last_value"] = x_to_value(event.x, width)
                return
            drag_state["handle"] = "low" if abs(event.x - low_x) <= abs(event.x - high_x) else "high"
            on_drag(event)

        def on_drag(event) -> None:
            width = max(210, canvas.winfo_width())
            value = x_to_value(event.x, width)
            if drag_state["handle"] == "low":
                value = min(value, self.clamp_int(high_var.get(), minimum, maximum))
                low_var.set(value)
                low_text_var.set(str(value))
            elif drag_state["handle"] == "range":
                previous_value = int(drag_state.get("last_value", value))
                delta = value - previous_value
                low = self.clamp_int(low_var.get(), minimum, maximum)
                high = self.clamp_int(high_var.get(), minimum, maximum)
                new_low = low + delta
                new_high = high + delta
                if new_low < minimum:
                    delta += minimum - new_low
                if new_high > maximum:
                    delta -= new_high - maximum
                new_low = self.clamp_int(low + delta, minimum, maximum)
                new_high = self.clamp_int(high + delta, minimum, maximum)
                if new_low <= new_high:
                    low_var.set(new_low)
                    high_var.set(new_high)
                    low_text_var.set(str(new_low))
                    high_text_var.set(str(new_high))
                drag_state["last_value"] = value
            else:
                value = max(value, self.clamp_int(low_var.get(), minimum, maximum))
                high_var.set(value)
                high_text_var.set(str(value))
            save_and_draw()

        canvas.bind("<Configure>", draw)
        canvas.bind("<Button-1>", on_press)
        canvas.bind("<B1-Motion>", on_drag)
        draw()

    def build_brake_dynamic_preset_row(self, row: int, controls_state: dict[str, tk.Variable]) -> None:
        preset_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        preset_row.grid(row=row, column=0, sticky="ew", pady=(8, 0))
        tk.Label(
            preset_row,
            text="Preset",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=26,
            anchor="w",
        ).pack(side="left")
        tk.Button(
            preset_row,
            text="Soft",
            command=lambda: self.apply_brake_dynamic_preset("soft", controls_state),
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#f1c40f",
            activeforeground="#101316",
            relief="flat",
            bd=0,
            padx=14,
            pady=4,
            font=ui_font("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="left")

    def build_brake_dynamic_cache_row(self, row: int) -> None:
        self.update_brake_dynamic_cache_text()
        cache_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        cache_row.grid(row=row, column=0, sticky="ew", pady=(14, 0))
        cache_row.grid_columnconfigure(0, weight=1)
        tk.Label(
            cache_row,
            text="Asphalt Wall Cache",
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="ew")
        tk.Label(
            cache_row,
            textvariable=self.brake_dynamic_cache_text,
            bg="#11161b",
            fg="#f1c40f",
            font=value_font("Consolas", 9),
            justify="left",
            anchor="nw",
            padx=8,
            pady=7,
        ).grid(row=1, column=0, sticky="ew", pady=(5, 0))

    def update_brake_dynamic_cache_text(self) -> None:
        ranges = ("0-60", "60-120", "120-200", "200+")
        current = float(getattr(self, "brake_dynamic_wall_start_percent", -1.0))
        if current >= 0.0:
            current_raw = self.wall_position_percent_to_start_byte(current) / 255.0 * 100.0
            current_text = f"current wall: {current:0.1f}% raw {current_raw:0.1f}%"
        else:
            current_text = "current wall: --"

        margin = 0
        pulse_margin = 0
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE_DYNAMIC)
        if controls_state:
            margin = self.clamp_int(controls_state["start_percent"].get(), 0, 40)
            pulse_margin = self.clamp_int(controls_state["pulse_offset"].get(), 0, 40)

        latch = " slip-off" if bool(getattr(self, "brake_dynamic_event_slip_off_latched", False)) else ""
        lines = [
            f"{current_text}   wall margin: {margin}%   pulse margin: {pulse_margin}%   learn slip th: {BRAKE_DYNAMIC_LEARNING_SLIP_THRESHOLD:.1f}"
            f"   learn brake >= {BRAKE_DYNAMIC_MIN_LEARNING_BRAKE_PERCENT:.0f}%   learn margin: {BRAKE_DYNAMIC_LEARNING_WALL_MARGIN:.0f}%{latch}"
        ]
        for index, label in enumerate(ranges):
            cache = self.brake_dynamic_cache[index]
            wall = float(cache["wall"])
            applied = max(5.0, min(95.0, wall - margin))
            pulse_at = max(1.0, min(95.0, wall - pulse_margin))
            samples = int(cache["samples"])
            confidence = float(cache["confidence"]) * 100.0
            speed = float(self.latest_values.get("speed_kmh", 0.0)) if self.latest_values else 0.0
            marker = " <" if current >= 0.0 and index == self.brake_dynamic_speed_bucket(speed) else ""
            lines.append(f"{label:>7} km/h  cache {wall:5.1f}%  wall {applied:5.1f}%  pulse {pulse_at:5.1f}%  n={samples:<2d}  conf={confidence:3.0f}%{marker}")
        self.brake_dynamic_cache_text.set("\n".join(lines))

    def build_trigger_mode_test_controls(self) -> None:
        tk.Button(
            self.effect_detail_body,
            text="Open Trigger Test Console",
            command=self.open_trigger_mode_test_window,
            bg="#f1c40f",
            fg="#101316",
            activebackground="#f1c40f",
            activeforeground="#101316",
            relief="flat",
            bd=0,
            padx=10,
            pady=7,
            font=ui_font("Segoe UI", 10, "bold"),
            cursor="hand2",
        ).grid(row=1, column=0, sticky="ew", pady=(12, 0))
        tk.Label(
            self.effect_detail_body,
            textvariable=self.trigger_mode_test_status,
            bg="#171b20",
            fg="#f1c40f",
            font=ui_font("Segoe UI", 10, "bold"),
            anchor="w",
        ).grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def trigger_mode_test_presets(self) -> list[tuple[str, str]]:
        return [
            ("Off", "off"),
            ("Rigid Soft", "rigid_soft"),
            ("Rigid Medium", "rigid_medium"),
            ("Rigid Hard", "rigid_hard"),
            ("Rigid Late Position", "rigid_late"),
            ("Rigid Zones Wall", "rigid_zones_wall"),
            ("Rigid Zones Mid", "rigid_zones_mid"),
            ("Rigid Wall 30", "rigid_wall_30"),
            ("Vibrate Wall 30", "vibrate_wall_30"),
            ("Rigid Wall 40", "rigid_wall_40"),
            ("Vibrate Wall 40", "vibrate_wall_40"),
            ("Rigid Wall 50", "rigid_wall_50"),
            ("Vibrate Wall 50", "vibrate_wall_50"),
            ("Rigid Wall 55", "rigid_wall_55"),
            ("Vibrate Wall 55", "vibrate_wall_55"),
            ("Vibrate Zones Wall", "vibrate_zones_wall"),
            ("Vibrate Zones Buzz", "vibrate_zones_buzz"),
            ("Vibrate Pos 10", "vibrate_at_10"),
            ("Vibrate Pos 15", "vibrate_at_15"),
            ("Vibrate Pos 20", "vibrate_at_20"),
            ("Vibrate Pos 25", "vibrate_at_25"),
            ("Vibrate Pos 30", "vibrate_at_30"),
            ("Vibrate Pos 35", "vibrate_at_35"),
            ("Vibrate Pos 40", "vibrate_at_40"),
            ("Vibrate Pos 45", "vibrate_at_45"),
            ("Vibrate Pos 50", "vibrate_at_50"),
            ("Vibrate Pos 55", "vibrate_at_55"),
            ("Pulse Slow", "pulse_slow"),
            ("Pulse Fast", "pulse_fast"),
            ("Pulse Sweep", "pulse_sweep"),
        ]

    def open_trigger_mode_test_window(self) -> None:
        if self.trigger_mode_test_window is not None and self.trigger_mode_test_window.winfo_exists():
            self.trigger_mode_test_window.lift()
            self.trigger_mode_test_window.focus_force()
            return

        window = tk.Toplevel(self.root)
        self.trigger_mode_test_window = window
        window.title("Trigger Mode Test Console")
        window.configure(bg="#121417")
        window.geometry("640x620")
        window.protocol("WM_DELETE_WINDOW", self.close_trigger_mode_test_window)

        body = tk.Frame(window, bg="#171b20", padx=14, pady=14)
        body.pack(fill="both", expand=True, padx=12, pady=12)
        body.grid_columnconfigure(0, weight=1)

        self.build_trigger_mode_test_int_control(
            0, "Wall Start", self.trigger_mode_test_wall_start, self.trigger_mode_test_wall_start_text, 0, 100, parent=body
        )
        self.build_trigger_mode_test_int_control(
            1, "Wall End", self.trigger_mode_test_wall_end, self.trigger_mode_test_wall_end_text, 0, 100, parent=body
        )
        self.build_trigger_mode_test_int_control(
            2, "Wall Strength", self.trigger_mode_test_wall_strength, self.trigger_mode_test_wall_strength_text, 0, 255, parent=body
        )
        self.build_trigger_separator(3, parent=body)
        self.build_trigger_mode_test_int_control(
            4, "Repeat Count", self.trigger_mode_test_count, self.trigger_mode_test_count_text, 1, 30, parent=body
        )
        self.build_trigger_mode_test_int_control(
            5, "On Time", self.trigger_mode_test_on_ms, self.trigger_mode_test_on_ms_text, 20, 1000, parent=body
        )
        self.build_trigger_mode_test_int_control(
            6, "Off Time", self.trigger_mode_test_off_ms, self.trigger_mode_test_off_ms_text, 0, 1000, parent=body
        )
        self.build_trigger_mode_test_int_control(
            7, "Firmware Hz", self.trigger_mode_test_hz, self.trigger_mode_test_hz_text, 1, 255, parent=body
        )
        self.build_trigger_mode_test_int_control(
            8, "Firmware Amplitude", self.trigger_mode_test_amp, self.trigger_mode_test_amp_text, 1, 255, parent=body
        )

        grid = tk.Frame(body, bg="#171b20")
        grid.grid(row=9, column=0, sticky="ew", pady=(16, 0))
        for column in range(3):
            grid.grid_columnconfigure(column, weight=1)

        for index, (label, preset) in enumerate(self.trigger_mode_test_presets()):
            tk.Button(
                grid,
                text=label,
                command=lambda value=preset: self.send_trigger_mode_test(value),
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#f1c40f",
                activeforeground="#101316",
                relief="flat",
                bd=0,
                padx=8,
                pady=5,
                font=ui_font("Segoe UI", 9, "bold"),
                cursor="hand2",
            ).grid(row=index // 3, column=index % 3, sticky="ew", padx=4, pady=4)

        tk.Label(
            body,
            textvariable=self.trigger_mode_test_status,
            bg="#171b20",
            fg="#f1c40f",
            font=ui_font("Segoe UI", 10, "bold"),
            anchor="w",
        ).grid(row=10, column=0, sticky="ew", pady=(12, 0))

    def close_trigger_mode_test_window(self) -> None:
        if self.trigger_mode_test_window is not None:
            self.trigger_mode_test_window.destroy()
        self.trigger_mode_test_window = None

    def build_trigger_mode_test_int_control(
        self,
        row: int,
        label_text: str,
        var: tk.IntVar,
        text_var: tk.StringVar,
        minimum: int,
        maximum: int,
        parent: tk.Widget | None = None,
    ) -> None:
        parent = parent or self.effect_detail_body
        control_row = tk.Frame(parent, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Scale(
            control_row,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=var,
            command=lambda _value: self.on_trigger_mode_test_slider_changed(var, text_var),
            bg="#f1c40f",
            fg="#aeb8c4",
            troughcolor="#2a3139",
            activebackground="#f1c40f",
            highlightthickness=0,
            relief="flat",
            sliderrelief="flat",
            width=ui_px(10),
            length=ui_px(190),
        ).grid(row=0, column=1, sticky="w")
        entry = tk.Entry(
            control_row,
            textvariable=text_var,
            width=5,
            bg="#101316",
            fg="#f5f7fa",
            insertbackground="#f5f7fa",
            relief="flat",
            justify="center",
            font=value_font("Consolas", 9),
        )
        entry.grid(row=0, column=2, sticky="w", padx=(10, 0), ipady=3)
        entry.bind(
            "<Return>",
            lambda event: self.on_trigger_mode_test_entry_changed(var, text_var, minimum, maximum, event),
        )
        entry.bind(
            "<FocusOut>",
            lambda event: self.on_trigger_mode_test_entry_changed(var, text_var, minimum, maximum, event),
        )

    def build_trigger_int_control(
        self,
        row: int,
        label_text: str,
        var: tk.IntVar,
        text_var: tk.StringVar,
        minimum: int,
        maximum: int,
        slip_pulse_group: str | None = None,
    ) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        label = tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        )
        label.grid(row=0, column=0, sticky="w")
        scale = tk.Scale(
            control_row,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=var,
            command=lambda _value: self.on_trigger_slider_changed(var, text_var),
            bg="#f1c40f",
            fg="#aeb8c4",
            troughcolor="#2a3139",
            activebackground="#f1c40f",
            highlightthickness=0,
            length=ui_px(210),
            sliderlength=ui_px(18),
            sliderrelief="flat",
            bd=0,
            width=ui_px(10),
        )
        scale.grid(row=0, column=1, sticky="w", padx=(8, 3))
        entry = tk.Entry(
            control_row,
            textvariable=text_var,
            bg="#1d232a",
            fg="#d6dde5",
            insertbackground="#d6dde5",
            relief="flat",
            font=value_font("Consolas", 9, "bold"),
            width=4,
            justify="center",
        )
        entry.grid(row=0, column=2, ipady=2)
        entry.bind("<Return>", lambda event: self.on_trigger_entry_changed(var, text_var, minimum, maximum, event))
        entry.bind("<FocusOut>", lambda event: self.on_trigger_entry_changed(var, text_var, minimum, maximum, event))
        if slip_pulse_group:
            groups = getattr(self, "slip_pulse_option_widgets", None)
            if isinstance(groups, dict):
                groups.setdefault(slip_pulse_group, []).extend([label, scale, entry])

    def build_trigger_side_control(self, row: int, label_text: str, side_var: tk.StringVar) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        button_frame = tk.Frame(control_row, bg="#171b20")
        button_frame.grid(row=0, column=1, sticky="w", padx=(8, 3))
        buttons: dict[str, tk.Button] = {}

        def refresh() -> None:
            selected = "Left" if str(side_var.get()).lower().startswith("l") else "Right"
            side_var.set(selected)
            for side, button in buttons.items():
                is_selected = side == selected
                bg = "#f1c40f" if is_selected else "#252c35"
                fg = "#101316" if is_selected else "#d6dde5"
                button.configure(
                    bg=bg,
                    fg=fg,
                    activebackground="#f7dc6f" if is_selected else "#303946",
                    activeforeground=fg,
                    relief="sunken" if is_selected else "raised",
                    highlightbackground="#f7dc6f" if is_selected else "#3a434d",
                )

        def choose(side: str) -> None:
            side_var.set(side)
            refresh()
            self.on_trigger_setting_changed()

        for side, text in (("Left", "L"), ("Right", "R")):
            button = tk.Button(
                button_frame,
                text=text,
                command=lambda selected=side: choose(selected),
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
                relief="raised",
                overrelief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#3a434d",
                highlightcolor="#f1c40f",
                font=ui_font("Segoe UI", 8, "bold"),
                width=5,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 4), ipady=2)
            buttons[side] = button
        refresh()

    def build_trigger_multi_side_control(
        self,
        row: int,
        label_text: str,
        sides_var: tk.StringVar,
        default: str,
    ) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        button_frame = tk.Frame(control_row, bg="#171b20")
        button_frame.grid(row=0, column=1, sticky="w", padx=(8, 3))
        buttons: dict[str, tk.Button] = {}

        def selected_set() -> set[str]:
            value = normalize_trigger_sides(sides_var.get(), default)
            if value == "Both":
                return {"Left", "Right"}
            return {value}

        def write_selected(selected: set[str]) -> None:
            if not selected:
                selected = {"Right"} if default == "Right" else {"Left"}
            if selected == {"Left", "Right"}:
                sides_var.set("Both")
            elif "Left" in selected:
                sides_var.set("Left")
            else:
                sides_var.set("Right")

        def refresh() -> None:
            selected = selected_set()
            write_selected(selected)
            for side, button in buttons.items():
                is_selected = side in selected
                bg = "#f1c40f" if is_selected else "#252c35"
                fg = "#101316" if is_selected else "#d6dde5"
                button.configure(
                    bg=bg,
                    fg=fg,
                    activebackground="#f7dc6f" if is_selected else "#303946",
                    activeforeground=fg,
                    relief="sunken" if is_selected else "raised",
                    highlightbackground="#f7dc6f" if is_selected else "#3a434d",
                )

        def toggle(side: str) -> None:
            selected = selected_set()
            if side in selected:
                selected.remove(side)
            else:
                selected.add(side)
            write_selected(selected)
            refresh()
            self.on_trigger_setting_changed()

        for side, text in (("Left", "L"), ("Right", "R")):
            button = tk.Button(
                button_frame,
                text=text,
                command=lambda selected=side: toggle(selected),
                bg="#252c35",
                fg="#d6dde5",
                activebackground="#303946",
                activeforeground="#f1c40f",
                relief="raised",
                overrelief="raised",
                bd=1,
                highlightthickness=1,
                highlightbackground="#3a434d",
                highlightcolor="#f1c40f",
                font=ui_font("Segoe UI", 8, "bold"),
                width=5,
                cursor="hand2",
            )
            button.pack(side="left", padx=(0, 4), ipady=2)
            buttons[side] = button
        refresh()

    def build_trigger_separator(self, row: int, parent: tk.Widget | None = None) -> None:
        parent = parent or self.effect_detail_body
        separator = tk.Frame(parent, bg="#2a3139", height=1)
        separator.grid(row=row, column=0, sticky="ew", pady=(12, 2))

    def build_trigger_scaled_control(
        self,
        row: int,
        label_text: str,
        var: tk.IntVar,
        text_var: tk.StringVar,
        minimum: int,
        maximum: int,
        divisor: float,
    ) -> None:
        control_row = tk.Frame(self.effect_detail_body, bg="#171b20")
        control_row.grid(row=row, column=0, sticky="ew", pady=(10, 0))
        control_row.grid_columnconfigure(3, weight=1)
        tk.Label(
            control_row,
            text=label_text,
            bg="#171b20",
            fg="#aeb8c4",
            font=ui_font("Segoe UI", 9, "bold"),
            width=31,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")
        tk.Scale(
            control_row,
            from_=minimum,
            to=maximum,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=var,
            command=lambda _value: self.on_trigger_scaled_slider_changed(var, text_var, divisor),
            bg="#f1c40f",
            fg="#aeb8c4",
            troughcolor="#2a3139",
            activebackground="#f1c40f",
            highlightthickness=0,
            length=ui_px(210),
            sliderlength=ui_px(18),
            sliderrelief="flat",
            bd=0,
            width=ui_px(10),
        ).grid(row=0, column=1, sticky="w", padx=(8, 3))
        entry = tk.Entry(
            control_row,
            textvariable=text_var,
            bg="#1d232a",
            fg="#d6dde5",
            insertbackground="#d6dde5",
            relief="flat",
            font=value_font("Consolas", 9, "bold"),
            width=4,
            justify="center",
        )
        entry.grid(row=0, column=2, ipady=2)
        entry.bind("<Return>", lambda event: self.on_trigger_scaled_entry_changed(var, text_var, minimum, maximum, divisor, event))
        entry.bind("<FocusOut>", lambda event: self.on_trigger_scaled_entry_changed(var, text_var, minimum, maximum, divisor, event))

    def on_detail_body_configure(self, _event=None) -> None:
        self.schedule_layout_update("detail_body", self.apply_detail_body_configure)

    def apply_detail_body_configure(self) -> None:
        self.detail_canvas.configure(scrollregion=self.detail_canvas.bbox("all"))
        self.update_detail_scrollbar()

    def on_detail_canvas_configure(self, event) -> None:
        self.pending_canvas_widths["detail"] = event.width
        self.schedule_layout_update("detail_canvas", self.apply_detail_canvas_configure)

    def apply_detail_canvas_configure(self) -> None:
        width = self.pending_canvas_widths.get("detail")
        if width is not None:
            self.detail_canvas.itemconfigure(self.detail_window, width=width)
        self.update_detail_scrollbar()

    def bind_detail_mousewheel(self, _event=None) -> None:
        self.detail_canvas.bind_all("<MouseWheel>", self.on_detail_mousewheel)

    def unbind_detail_mousewheel(self, _event=None) -> None:
        self.detail_canvas.unbind_all("<MouseWheel>")

    def on_detail_mousewheel(self, event) -> str:
        self.scroll_canvas_by_mousewheel(self.detail_canvas, event)
        return "break"

    def on_detail_scroll(self, first: str, last: str) -> None:
        self.update_detail_scrollbar(float(first), float(last))

    def update_detail_scrollbar(self, first: float | None = None, last: float | None = None) -> None:
        if first is None or last is None:
            first, last = self.detail_canvas.yview()
        height = max(1, self.detail_scrollbar.winfo_height())
        width = max(1, self.detail_scrollbar.winfo_width())
        self.detail_scrollbar.delete("all")
        self.detail_scrollbar.create_rectangle(
            width // 2 - 3,
            4,
            width // 2 + 3,
            height - 4,
            fill="#2a3139",
            outline="",
        )
        if last - first >= 0.999:
            return
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        max_first = max(0.001, 1.0 - (last - first))
        scroll_progress = max(0.0, min(1.0, first / max_first))
        thumb_top = 4 + travel * scroll_progress
        thumb_bottom = thumb_top + thumb_height
        self.detail_scrollbar_thumb = self.detail_scrollbar.create_rectangle(
            width // 2 - 4,
            thumb_top,
            width // 2 + 4,
            thumb_bottom,
            fill="#f1c40f",
            outline="",
        )

    def on_detail_scrollbar_click(self, event) -> str:
        height = max(1, self.detail_scrollbar.winfo_height())
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        progress = max(0.0, min(1.0, (event.y - 4 - thumb_height / 2) / travel))
        first, last = self.detail_canvas.yview()
        max_first = max(0.0, 1.0 - (last - first))
        self.detail_canvas.yview_moveto(progress * max_first)
        return "break"

    def on_effects_list_configure(self, _event=None) -> None:
        self.schedule_layout_update("effects_list", self.apply_effects_list_configure)

    def apply_effects_list_configure(self) -> None:
        self.effects_canvas.configure(scrollregion=self.effects_canvas.bbox("all"))
        self.update_effects_scrollbar()

    def on_effects_canvas_configure(self, event) -> None:
        self.pending_canvas_widths["effects"] = event.width
        self.schedule_layout_update("effects_canvas", self.apply_effects_canvas_configure)

    def apply_effects_canvas_configure(self) -> None:
        width = self.pending_canvas_widths.get("effects")
        if width is not None:
            self.effects_canvas.itemconfigure(self.effects_window, width=width)
        self.update_effects_scrollbar()

    def bind_effects_mousewheel(self, _event=None) -> None:
        self.effects_canvas.bind_all("<MouseWheel>", self.on_effects_mousewheel)

    def unbind_effects_mousewheel(self, _event=None) -> None:
        self.effects_canvas.unbind_all("<MouseWheel>")

    def on_effects_mousewheel(self, event) -> str:
        self.scroll_canvas_by_mousewheel(self.effects_canvas, event)
        return "break"

    def on_effects_scroll(self, first: str, last: str) -> None:
        self.update_effects_scrollbar(float(first), float(last))

    def update_effects_scrollbar(self, first: float | None = None, last: float | None = None) -> None:
        if first is None or last is None:
            first, last = self.effects_canvas.yview()
        height = max(1, self.effects_scrollbar.winfo_height())
        width = max(1, self.effects_scrollbar.winfo_width())
        self.effects_scrollbar.delete("all")
        self.effects_scrollbar.create_rectangle(
            width // 2 - 3,
            4,
            width // 2 + 3,
            height - 4,
            fill="#2a3139",
            outline="",
        )
        if last - first >= 0.999:
            return
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        max_first = max(0.001, 1.0 - (last - first))
        scroll_progress = max(0.0, min(1.0, first / max_first))
        thumb_top = 4 + travel * scroll_progress
        thumb_bottom = thumb_top + thumb_height
        self.effects_scrollbar_thumb = self.effects_scrollbar.create_rectangle(
            width // 2 - 4,
            thumb_top,
            width // 2 + 4,
            thumb_bottom,
            fill="#f1c40f",
            outline="",
        )

    def on_effects_scrollbar_click(self, event) -> str:
        height = max(1, self.effects_scrollbar.winfo_height())
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        progress = max(0.0, min(1.0, (event.y - 4 - thumb_height / 2) / travel))
        first, last = self.effects_canvas.yview()
        max_first = max(0.0, 1.0 - (last - first))
        self.effects_canvas.yview_moveto(progress * max_first)
        return "break"

    def on_trigger_list_configure(self, _event=None) -> None:
        self.schedule_layout_update("trigger_list", self.apply_trigger_list_configure)

    def apply_trigger_list_configure(self) -> None:
        self.trigger_canvas.configure(scrollregion=self.trigger_canvas.bbox("all"))
        self.update_trigger_scrollbar()

    def on_trigger_canvas_configure(self, event) -> None:
        self.pending_canvas_widths["trigger"] = event.width
        self.schedule_layout_update("trigger_canvas", self.apply_trigger_canvas_configure)

    def apply_trigger_canvas_configure(self) -> None:
        width = self.pending_canvas_widths.get("trigger")
        if width is not None:
            self.trigger_canvas.itemconfigure(self.trigger_window, width=width)
        self.update_trigger_scrollbar()

    def bind_trigger_mousewheel(self, _event=None) -> None:
        self.trigger_canvas.bind_all("<MouseWheel>", self.on_trigger_mousewheel)

    def unbind_trigger_mousewheel(self, _event=None) -> None:
        self.trigger_canvas.unbind_all("<MouseWheel>")

    def on_trigger_mousewheel(self, event) -> str:
        self.scroll_canvas_by_mousewheel(self.trigger_canvas, event)
        return "break"

    @staticmethod
    def scroll_canvas_by_mousewheel(canvas: tk.Canvas, event, pixels_per_notch: float = 8.0) -> None:
        first, last = canvas.yview()
        visible_fraction = max(0.0, min(1.0, last - first))
        if visible_fraction >= 0.999:
            return
        bbox = canvas.bbox("all")
        if not bbox:
            return
        total_height = max(1.0, float(bbox[3] - bbox[1]))
        steps = max(1.0, abs(float(getattr(event, "delta", 0))) / 120.0)
        direction = -1.0 if getattr(event, "delta", 0) > 0 else 1.0
        max_first = max(0.0, 1.0 - visible_fraction)
        next_first = first + direction * pixels_per_notch * steps / total_height
        canvas.yview_moveto(max(0.0, min(max_first, next_first)))

    def on_trigger_scroll(self, first: str, last: str) -> None:
        self.update_trigger_scrollbar(float(first), float(last))

    def update_trigger_scrollbar(self, first: float | None = None, last: float | None = None) -> None:
        if first is None or last is None:
            first, last = self.trigger_canvas.yview()
        height = max(1, self.trigger_scrollbar.winfo_height())
        width = max(1, self.trigger_scrollbar.winfo_width())
        self.trigger_scrollbar.delete("all")
        self.trigger_scrollbar.create_rectangle(
            width // 2 - 3,
            4,
            width // 2 + 3,
            height - 4,
            fill="#2a3139",
            outline="",
        )
        if last - first >= 0.999:
            return
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        max_first = max(0.001, 1.0 - (last - first))
        scroll_progress = max(0.0, min(1.0, first / max_first))
        thumb_top = 4 + travel * scroll_progress
        thumb_bottom = thumb_top + thumb_height
        self.trigger_scrollbar_thumb = self.trigger_scrollbar.create_rectangle(
            width // 2 - 4,
            thumb_top,
            width // 2 + 4,
            thumb_bottom,
            fill="#f1c40f",
            outline="",
        )

    def on_trigger_scrollbar_click(self, event) -> str:
        height = max(1, self.trigger_scrollbar.winfo_height())
        thumb_height = min(34, max(20, height - 8))
        travel = max(1, height - 8 - thumb_height)
        progress = max(0.0, min(1.0, (event.y - 4 - thumb_height / 2) / travel))
        first, last = self.trigger_canvas.yview()
        max_first = max(0.0, 1.0 - (last - first))
        self.trigger_canvas.yview_moveto(progress * max_first)
        return "break"

    def build_effect_row(self, effect_name: str) -> None:
        controls_state = self.effect_controls[effect_name]
        row = tk.Frame(self.effects_list_frame, bg="#171b20")
        row.pack(fill="x", padx=(6, 2), pady=(0, 9))

        name_line = tk.Frame(row, bg="#171b20")
        name_line.pack(fill="x", pady=(0, 1))
        label = tk.Label(
            name_line,
            text=effect_name,
            bg="#171b20",
            fg="#d6dde5",
            font=ui_font("Segoe UI", 9, "bold"),
            anchor="w",
            cursor="hand2",
        )
        label.pack(side="left", fill="x", expand=True)
        label.bind("<Button-1>", lambda _event, name=effect_name: self.select_output_effect(name))
        self.effect_name_labels[effect_name] = label

        controls = tk.Frame(row, bg="#171b20")
        controls.pack(fill="x")
        scale = tk.Scale(
            controls,
            from_=0,
            to=10,
            orient="horizontal",
            resolution=1,
            showvalue=False,
            variable=controls_state["volume"],
            command=lambda value, name=effect_name: self.on_effect_slider_changed(name, value),
            bg="#f1c40f",
            fg="#aeb8c4",
            troughcolor="#2a3139",
            activebackground="#f1c40f",
            highlightthickness=0,
            length=ui_px(154),
            sliderlength=ui_px(18),
            sliderrelief="flat",
            bd=0,
            width=ui_px(10),
        )
        scale.pack(side="left", padx=(0, 3))

        toggle = tk.Checkbutton(
            controls,
            text="ON",
            variable=controls_state["enabled"],
            command=self.on_effect_toggle_changed,
            indicatoron=False,
            selectcolor="#2ecc71",
            bg="#252c35",
            fg="#d6dde5",
            activebackground="#2ecc71",
            activeforeground="#101316",
            relief="flat",
            font=ui_font("Segoe UI", 8, "bold"),
            width=4,
        )
        toggle.pack(side="right", ipady=2, padx=(0, 8))

        entry = tk.Entry(
            controls,
            textvariable=controls_state["volume_text"],
            bg="#1d232a",
            fg="#d6dde5",
            insertbackground="#d6dde5",
            relief="flat",
            font=value_font("Consolas", 9, "bold"),
            width=3,
            justify="center",
        )
        entry.pack(side="right", ipady=2, padx=(0, 28))
        entry.bind("<Return>", lambda event, name=effect_name: self.on_effect_volume_entered(name, event))
        entry.bind("<FocusOut>", lambda event, name=effect_name: self.on_effect_volume_entered(name, event))
        self.effect_lock_widgets[effect_name] = [scale, toggle, entry]
        tk.Frame(row, bg="#222932", height=1).pack(fill="x", pady=(7, 0))

    def on_effect_slider_changed(self, effect_name: str, value: str) -> None:
        volume = self.clamp_volume(value)
        self.effect_controls[effect_name]["volume_text"].set(self.format_volume(volume))
        self.save_effect_settings()

    def on_effect_volume_entered(self, effect_name: str, _event=None) -> None:
        controls_state = self.effect_controls[effect_name]
        volume = self.clamp_volume(controls_state["volume_text"].get())
        controls_state["volume"].set(volume)
        controls_state["volume_text"].set(self.format_volume(volume))
        self.save_effect_settings()

    def on_effect_pan_changed(self, effect_name: str, value: str) -> None:
        pan = self.clamp_pan(value)
        self.effect_controls[effect_name]["pan"].set(pan)
        self.effect_controls[effect_name]["pan_text"].set(self.format_pan(pan))
        self.save_effect_settings()

    def on_effect_toggle_changed(self) -> None:
        self.save_effect_settings()

    def select_output_effect(self, effect_name: str) -> None:
        self.selected_detail_type.set("haptic")
        self.selected_output_effect.set(effect_name)
        self.on_output_effect_selected()
        self.update_effect_label_styles()
        self.update_trigger_label_styles()
        self.refresh_effect_detail_panel()
        self.update_preset_lock_state()

    def on_output_effect_selected(self) -> None:
        self.settings["selected_output_effect"] = self.selected_output_effect.get()
        save_settings(self.settings)

    def update_effect_label_styles(self) -> None:
        selected = self.selected_output_effect.get()
        locked = self.haptic_effects_locked()
        for effect_name, label in self.effect_name_labels.items():
            active = self.selected_detail_type.get() == "haptic" and effect_name == selected
            if locked:
                label.configure(fg="#8b96a3" if active else "#5f6872")
            else:
                label.configure(fg="#f1c40f" if active else "#d6dde5")

    def select_trigger_effect(self, trigger_name: str) -> None:
        if trigger_name in HIDDEN_TRIGGER_EFFECTS:
            trigger_name = TRIGGER_BRAKE_RESISTANCE_PREDICTIVE
        self.selected_detail_type.set("trigger")
        self.selected_trigger_effect.set(trigger_name)
        self.settings["selected_trigger_effect"] = trigger_name
        self.settings["selected_detail_type"] = "trigger"
        save_settings(self.settings)
        self.update_effect_label_styles()
        self.update_trigger_label_styles()
        self.refresh_effect_detail_panel()
        self.update_preset_lock_state()

    def update_trigger_label_styles(self) -> None:
        selected = self.selected_trigger_effect.get()
        locked = self.config_preset_effects_locked()
        for trigger_name, label in self.trigger_name_labels.items():
            active = self.selected_detail_type.get() == "trigger" and trigger_name == selected
            if locked:
                label.configure(fg="#8b96a3" if active else "#5f6872")
            else:
                label.configure(fg="#f1c40f" if active else "#d6dde5")

    def update_preset_lock_state(self) -> None:
        preset_locked = self.config_preset_effects_locked()
        haptic_locked = self.haptic_effects_locked()
        effect_state = tk.DISABLED if haptic_locked else tk.NORMAL
        for effect_name, widgets in self.effect_lock_widgets.items():
            for widget in widgets:
                self.configure_widget_state(widget, effect_state)
        trigger_state = tk.DISABLED if preset_locked else tk.NORMAL
        for trigger_name, widgets in self.trigger_lock_widgets.items():
            for widget in widgets:
                self.configure_widget_state(widget, trigger_state)
        for widget in getattr(self, "drift_relief_lock_widgets", []):
            self.configure_widget_state(widget, trigger_state)
        self.set_preset_lock_overlay_message(getattr(self, "effects_lock_overlay", None), self.haptic_lock_message())
        self.set_preset_lock_overlay_message(getattr(self, "trigger_lock_overlay", None), self.locked_preset_message())
        detail_locked = preset_locked or (self.selected_detail_type.get() == "haptic" and haptic_locked)
        detail_message = self.haptic_lock_message() if self.selected_detail_type.get() == "haptic" else self.locked_preset_message()
        self.set_preset_lock_overlay_message(getattr(self, "detail_lock_overlay", None), detail_message)
        self.set_preset_lock_overlay_visible(getattr(self, "effects_lock_overlay", None), haptic_locked)
        self.set_preset_lock_overlay_visible(getattr(self, "trigger_lock_overlay", None), preset_locked)
        self.set_preset_lock_overlay_visible(getattr(self, "detail_lock_overlay", None), detail_locked)
        self.update_effect_label_styles()
        self.update_trigger_label_styles()
        self.apply_detail_lock_state()

    def apply_detail_lock_state(self) -> None:
        if not hasattr(self, "effect_detail_body"):
            return
        locked = self.config_preset_effects_locked()
        if self.selected_detail_type.get() == "haptic":
            locked = locked or self.haptic_effects_locked()
        state = tk.DISABLED if locked else tk.NORMAL
        for child in self.effect_detail_body.winfo_children():
            self.configure_widget_tree_state(child, state)

    def configure_widget_tree_state(self, widget: tk.Widget, state: str) -> None:
        self.configure_widget_state(widget, state)
        for child in widget.winfo_children():
            self.configure_widget_tree_state(child, state)

    def configure_widget_state(self, widget: tk.Widget, state: str) -> None:
        try:
            if isinstance(widget, (tk.Button, tk.Checkbutton, tk.Entry, tk.Scale, tk.Radiobutton)):
                widget.configure(state=state)
            if isinstance(widget, tk.Entry) and state == tk.DISABLED:
                try:
                    widget.configure(
                        disabledbackground=widget.cget("bg"),
                        disabledforeground="#7b858f",
                    )
                except tk.TclError:
                    pass
            if isinstance(widget, tk.Checkbutton) and str(widget.cget("text")).strip().upper() == "ON":
                if state == tk.DISABLED:
                    widget.configure(
                        bg="#20262d",
                        fg="#69737e",
                        activebackground="#20262d",
                        activeforeground="#69737e",
                        disabledforeground="#59636f",
                        selectcolor="#343b44",
                    )
                else:
                    widget.configure(
                        bg="#252c35",
                        fg="#d6dde5",
                        activebackground="#2ecc71",
                        activeforeground="#101316",
                        selectcolor="#2ecc71",
                    )
        except tk.TclError:
            pass

    def on_trigger_slider_changed(self, var: tk.IntVar, text_var: tk.StringVar) -> None:
        text_var.set(str(int(var.get())))
        self.normalize_dynamic_brake_strength()
        self.normalize_trigger_ranges()
        self.save_trigger_settings()

    def on_trigger_entry_changed(self, var: tk.IntVar, text_var: tk.StringVar, minimum: int, maximum: int, _event=None) -> None:
        value = self.clamp_int(text_var.get(), minimum, maximum)
        var.set(value)
        text_var.set(str(value))
        self.normalize_dynamic_brake_strength()
        self.normalize_trigger_ranges()
        self.save_trigger_settings()

    def on_trigger_mode_test_slider_changed(self, var: tk.IntVar, text_var: tk.StringVar) -> None:
        text_var.set(str(int(var.get())))
        self.save_trigger_mode_test_settings()

    def on_trigger_mode_test_entry_changed(self, var: tk.IntVar, text_var: tk.StringVar, minimum: int, maximum: int, _event=None) -> None:
        value = self.clamp_int(text_var.get(), minimum, maximum)
        var.set(value)
        text_var.set(str(value))
        self.save_trigger_mode_test_settings()

    def on_trigger_scaled_slider_changed(self, var: tk.IntVar, text_var: tk.StringVar, divisor: float) -> None:
        text_var.set(f"{var.get() / divisor:.1f}")
        self.save_trigger_settings()

    def on_trigger_scaled_entry_changed(
        self,
        var: tk.IntVar,
        text_var: tk.StringVar,
        minimum: int,
        maximum: int,
        divisor: float,
        _event=None,
    ) -> None:
        value = self.clamp_float(text_var.get(), minimum / divisor, maximum / divisor)
        scaled = self.clamp_int(round(value * divisor), minimum, maximum)
        var.set(scaled)
        text_var.set(f"{scaled / divisor:.1f}")
        self.save_trigger_settings()

    def on_trigger_setting_changed(self, trigger_name: str | None = None) -> None:
        for name, controls_state in self.trigger_controls.items():
            self.sync_slip_response_mode(controls_state, name)
            self.update_slip_pulse_style_buttons(controls_state)
        self.update_slip_pulse_option_styles()
        self.enforce_brake_resistance_exclusive(prefer=trigger_name)
        self.save_trigger_settings()

    def on_drift_relief_changed(self) -> None:
        self.settings["drift_relief_enabled"] = bool(self.drift_relief_enabled.get())
        if not bool(self.drift_relief_enabled.get()):
            self.drift_relief_high_score_since = 0.0
            self.drift_relief_trigger_suppressed = False
            self.clear_drift_relief_r2_outputs()
        self.update_drift_relief_status_text()
        save_settings(self.settings)
        self.update_save_button_state()

    def sync_slip_response_mode(self, controls_state: dict[str, tk.Variable], trigger_name: str | None = None) -> str:
        mode_var = controls_state.get("slip_response_mode")
        pulse_var = controls_state.get("slip_pulse_enabled")
        pulse_enabled = bool(pulse_var.get()) if pulse_var is not None else False
        style_var = controls_state.get("slip_pulse_style")
        if style_var is not None:
            style_var.set(normalize_slip_pulse_style(style_var.get(), trigger_name))
        mode = SLIP_RESPONSE_PULSE if pulse_enabled else SLIP_RESPONSE_DROP
        if mode_var is not None:
            mode_var.set(mode)
        if "slip_off" in controls_state and trigger_name != TRIGGER_THROTTLE_TRACTION_LIMIT:
            controls_state["slip_off"].set(True)
        return mode

    def normalize_dynamic_brake_strength(self) -> None:
        for trigger_name in (TRIGGER_BRAKE_RESISTANCE_DYNAMIC, TRIGGER_BRAKE_RESISTANCE_PREDICTIVE):
            controls_state = self.trigger_controls.get(trigger_name)
            if not controls_state:
                continue
            pulse_max = 255 if trigger_name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE else 100
            raw_pulse = self.clamp_int(controls_state["pulse_strength"].get(), -9999, 9999)
            pulse = self.clamp_int(raw_pulse, 0, pulse_max)
            normalized_pulse = pulse if trigger_name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE else self.normalized_dynamic_pulse_strength(pulse)
            if normalized_pulse != raw_pulse:
                pulse = normalized_pulse
                controls_state["pulse_strength"].set(pulse)
                controls_state["pulse_strength_text"].set(str(pulse))
            force = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
            controls_state["force_percent"].set(force)
            controls_state["force_text"].set(str(force))

    @staticmethod
    def normalized_dynamic_pulse_strength(value: int) -> int:
        return max(0, min(100, int(value)))

    def apply_brake_dynamic_preset(self, preset: str, controls_state: dict[str, tk.Variable]) -> None:
        if preset != "soft":
            return
        values = {
            "force_percent": 2,
            "force_text": "2",
            "start_percent": 75,
            "start_text": "75",
            "max_percent": 55,
            "max_text": "55",
            "wall_percent": 20,
            "wall_text": "20",
            "gate_range": 10,
            "gate_range_text": "10",
            "smooth_start_ms": 0,
            "smooth_start_text": "0",
            "pulse_strength": 50,
            "pulse_strength_text": "50",
            "pulse_start_percent": 40,
            "pulse_start_text": "40",
            "pulse_timing_offset": -5,
            "pulse_timing_offset_text": "-5",
            "haptic_pulse_hz": 70,
            "haptic_pulse_hz_text": "70",
            "haptic_pulse_strength": 0,
            "haptic_pulse_strength_text": "0",
            "haptic_pulse_start_margin": 25,
            "haptic_pulse_start_margin_text": "25",
            "haptic_pulse_end_margin": 0,
            "haptic_pulse_end_margin_text": "0",
            "pulse_rate": 80,
            "pulse_rate_text": "80",
            "slip_threshold": 14,
            "slip_threshold_text": "1.4",
        }
        for key, value in values.items():
            if key in controls_state:
                controls_state[key].set(value)
        self.normalize_trigger_ranges()
        self.save_trigger_settings()

    def enforce_brake_resistance_exclusive(self, prefer: str | None = None) -> None:
        if prefer not in BRAKE_TRIGGER_GROUP:
            active_brakes = [
                name for name in BRAKE_TRIGGER_GROUP
                if self.trigger_controls.get(name) and self.trigger_controls[name]["enabled"].get()
            ]
            prefer = active_brakes[0] if len(active_brakes) > 1 else None
        if prefer not in BRAKE_TRIGGER_GROUP:
            return

        preferred = self.trigger_controls.get(prefer)
        if not preferred or not preferred["enabled"].get():
            return

        for name in BRAKE_TRIGGER_GROUP:
            if name == prefer:
                continue
            controls_state = self.trigger_controls.get(name)
            if controls_state and controls_state["enabled"].get():
                controls_state["enabled"].set(False)
                self.trigger_brake_active[name] = False
                self.trigger_smoothed_force[name] = 0.0
                if name == TRIGGER_BRAKE_RESISTANCE:
                    self.reset_brake_resistance_release_hold()
                elif name in (TRIGGER_BRAKE_RESISTANCE_DYNAMIC, TRIGGER_BRAKE_RESISTANCE_PREDICTIVE):
                    self.reset_brake_dynamic_release_hold()

    def normalize_trigger_ranges(self) -> None:
        for trigger_name, controls_state in self.trigger_controls.items():
            if trigger_name in (TRIGGER_BRAKE_RESISTANCE_DYNAMIC, TRIGGER_BRAKE_RESISTANCE_PREDICTIVE):
                start = self.clamp_int(controls_state["start_percent"].get(), 40, 95)
                end = self.clamp_int(controls_state["max_percent"].get(), 30, 90)
                end = min(end, max(30, start - 1))
                controls_state["start_percent"].set(start)
                controls_state["start_text"].set(str(start))
                controls_state["max_percent"].set(end)
                controls_state["max_text"].set(str(end))
                if trigger_name == TRIGGER_BRAKE_RESISTANCE_DYNAMIC:
                    haptic_start = self.clamp_int(controls_state["haptic_pulse_start_margin"].get(), -20, 25)
                    haptic_end = self.clamp_int(controls_state["haptic_pulse_end_margin"].get(), -20, 25)
                    if haptic_start < haptic_end:
                        haptic_start = haptic_end
                    controls_state["haptic_pulse_start_margin"].set(haptic_start)
                    controls_state["haptic_pulse_start_margin_text"].set(str(haptic_start))
                    controls_state["haptic_pulse_end_margin"].set(haptic_end)
                    controls_state["haptic_pulse_end_margin_text"].set(str(haptic_end))
                continue
            if trigger_name == TRIGGER_THROTTLE_TRACTION_LIMIT:
                start = 100
                end = self.clamp_int(controls_state["max_percent"].get(), 20, 95)
                end = min(end, max(20, start - 1))
                slip_start = self.clamp_int(controls_state["slip_threshold"].get(), 1, 50)
                slip_end = self.clamp_int(controls_state["slip_end_threshold"].get(), 1, 50)
                slip_end = max(slip_start + 1, slip_end)
                controls_state["start_percent"].set(start)
                controls_state["start_text"].set(str(start))
                controls_state["max_percent"].set(end)
                controls_state["max_text"].set(str(end))
                controls_state["smooth_start_ms"].set(0)
                controls_state["smooth_start_text"].set("0")
                controls_state["slip_end_threshold"].set(slip_end)
                controls_state["slip_end_threshold_text"].set(f"{slip_end / 10.0:.1f}")
                continue
            start = self.clamp_int(controls_state["start_percent"].get(), 0, 100)
            end = self.clamp_int(controls_state["max_percent"].get(), 0, 100)
            if end <= start:
                end = min(100, start + 1)
                if end <= start:
                    start = max(0, end - 1)
            controls_state["start_percent"].set(start)
            controls_state["start_text"].set(str(start))
            controls_state["max_percent"].set(end)
            controls_state["max_text"].set(str(end))

    def save_effect_settings(self, mark_dirty: bool = True) -> None:
        if mark_dirty and self.haptic_effects_locked():
            return
        self.settings.setdefault("effects", {})
        for effect_name, controls_state in self.effect_controls.items():
            self.settings["effects"][effect_name] = {
                "enabled": bool(controls_state["enabled"].get()),
                "volume": self.clamp_volume(controls_state["volume"].get()),
            }
            if effect_name in PAN_EFFECTS and "pan" in controls_state:
                self.settings["effects"][effect_name]["pan"] = self.clamp_pan(controls_state["pan"].get())
        if mark_dirty:
            save_settings(self.settings)
            self.update_save_button_state()

    def save_trigger_settings(self, mark_dirty: bool = True) -> None:
        if mark_dirty and self.config_preset_effects_locked():
            return
        self.settings.setdefault("trigger_effects", {})
        for trigger_name, controls_state in self.trigger_controls.items():
            pulse_brake_trigger = trigger_name in (TRIGGER_BRAKE_RESISTANCE_DYNAMIC, TRIGGER_BRAKE_RESISTANCE_PREDICTIVE)
            pulse_rate_max = 255 if pulse_brake_trigger else 30
            pulse_offset_min = 0 if pulse_brake_trigger else -30
            pulse_offset_max = 40 if pulse_brake_trigger else 30
            pulse_strength_max = 255 if trigger_name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE else 100
            pulse_strength = self.clamp_int(controls_state["pulse_strength"].get(), 0, pulse_strength_max)
            if trigger_name == TRIGGER_BRAKE_RESISTANCE_DYNAMIC:
                pulse_strength = self.normalized_dynamic_pulse_strength(pulse_strength)
                controls_state["pulse_strength"].set(pulse_strength)
                controls_state["pulse_strength_text"].set(str(pulse_strength))
            elif trigger_name == TRIGGER_BRAKE_RESISTANCE_PREDICTIVE:
                controls_state["pulse_strength"].set(pulse_strength)
                controls_state["pulse_strength_text"].set(str(pulse_strength))
            force_percent = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
            strength_percent = force_percent
            slip_response_mode = self.sync_slip_response_mode(controls_state, trigger_name)
            kerb_low_hz = self.clamp_int(controls_state["kerb_low_hz"].get(), 1, 40)
            kerb_high_hz = self.clamp_int(controls_state["kerb_high_hz"].get(), 1, 40)
            if kerb_low_hz > kerb_high_hz:
                kerb_low_hz, kerb_high_hz = kerb_high_hz, kerb_low_hz
            kerb_l_low_hz = self.clamp_int(controls_state["kerb_l_low_hz"].get(), 1, 40)
            kerb_l_high_hz = self.clamp_int(controls_state["kerb_l_high_hz"].get(), 1, 40)
            kerb_r_low_hz = self.clamp_int(controls_state["kerb_r_low_hz"].get(), 1, 40)
            kerb_r_high_hz = self.clamp_int(controls_state["kerb_r_high_hz"].get(), 1, 40)
            kerb_l_low_amp = self.clamp_int(controls_state["kerb_l_low_amp"].get(), 1, 8)
            kerb_l_high_amp = self.clamp_int(controls_state["kerb_l_high_amp"].get(), 1, 8)
            kerb_r_low_amp = self.clamp_int(controls_state["kerb_r_low_amp"].get(), 1, 8)
            kerb_r_high_amp = self.clamp_int(controls_state["kerb_r_high_amp"].get(), 1, 8)
            if kerb_l_low_hz > kerb_l_high_hz:
                kerb_l_low_hz, kerb_l_high_hz = kerb_l_high_hz, kerb_l_low_hz
            if kerb_r_low_hz > kerb_r_high_hz:
                kerb_r_low_hz, kerb_r_high_hz = kerb_r_high_hz, kerb_r_low_hz
            if kerb_l_low_amp > kerb_l_high_amp:
                kerb_l_low_amp, kerb_l_high_amp = kerb_l_high_amp, kerb_l_low_amp
            if kerb_r_low_amp > kerb_r_high_amp:
                kerb_r_low_amp, kerb_r_high_amp = kerb_r_high_amp, kerb_r_low_amp
            self.settings["trigger_effects"][trigger_name] = {
                "enabled": bool(controls_state["enabled"].get()),
                "curve": self.clamp_int(controls_state["curve"].get(), 0, 9),
                "start_percent": self.clamp_int(controls_state["start_percent"].get(), 0, 100),
                "max_percent": self.clamp_int(controls_state["max_percent"].get(), 0, 100),
                "force_percent": force_percent,
                "upshift_strength_percent": self.clamp_int(controls_state["upshift_strength_percent"].get(), 0, 100),
                "upshift_duration_ms": self.clamp_int(controls_state["upshift_duration_ms"].get(), 20, 180),
                "downshift_strength_percent": self.clamp_int(controls_state["downshift_strength_percent"].get(), 0, 100),
                "downshift_duration_ms": self.clamp_int(controls_state["downshift_duration_ms"].get(), 20, 180),
                "sustain_percent": self.clamp_int(controls_state["sustain_percent"].get(), 0, 100),
                "wall_percent": self.clamp_int(controls_state["wall_percent"].get(), 0, 100),
                "gate_range": self.clamp_int(controls_state["gate_range"].get(), 0, 30),
                "side": "Left" if str(controls_state["side"].get()).strip().lower().startswith("l") else "Right",
                "upshift_sides": normalize_trigger_sides(controls_state["upshift_sides"].get(), "Right"),
                "downshift_sides": normalize_trigger_sides(controls_state["downshift_sides"].get(), "Left"),
                "early_input_soft_zone": self.clamp_int(controls_state["early_input_soft_zone"].get(), 0, 60),
                "kick_late_position": self.clamp_int(controls_state["kick_late_position"].get(), 0, 100),
                "kick_softness": self.clamp_int(controls_state["kick_softness"].get(), 0, 10),
                "release_duration_ms": self.clamp_int(controls_state["release_duration_ms"].get(), 0, 120),
                "slip_off": bool(controls_state["slip_off"].get()),
                "slip_threshold": self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0),
                "slip_end_threshold": self.clamp_float(controls_state["slip_end_threshold"].get() / 10.0, 0.1, 5.0),
                "slip_response_mode": slip_response_mode,
                "slip_pulse_enabled": bool(controls_state["slip_pulse_enabled"].get()),
                "slip_pulse_style": normalize_slip_pulse_style(controls_state["slip_pulse_style"].get(), trigger_name),
                "slip_drop_low_percent": self.clamp_int(controls_state["slip_drop_low_percent"].get(), 0, 100),
                "slip_low_percent": self.clamp_int(controls_state["slip_low_percent"].get(), 0, 100),
                "slip_pulse_high_percent": self.clamp_int(controls_state["slip_pulse_high_percent"].get(), 0, 100),
                "slip_pulse_start_percent": self.clamp_int(controls_state["slip_pulse_start_percent"].get(), 10, 99),
                "slip_pulse_end_percent": self.clamp_int(controls_state["slip_pulse_end_percent"].get(), 100, 150),
                "slip_pulse_rate": self.clamp_int(controls_state["slip_pulse_rate"].get(), 1, SLIP_PULSE_RATE_MAX),
                "slip_rumble_amplitude": self.clamp_int(controls_state["slip_rumble_amplitude"].get(), 1, 255),
                "slip_rumble_rate": self.clamp_int(controls_state["slip_rumble_rate"].get(), 1, 255),
                "slip_dsx_vibration_amplitude": self.clamp_int(controls_state["slip_dsx_vibration_amplitude"].get(), 1, 8),
                "slip_dsx_vibration_frequency": self.clamp_int(controls_state["slip_dsx_vibration_frequency"].get(), 1, 40),
                "slip_dsx_vibration_margin": self.clamp_int(controls_state["slip_dsx_vibration_margin"].get(), 0, 9),
                "kerb_low_hz": kerb_low_hz,
                "kerb_high_hz": kerb_high_hz,
                "kerb_l_enabled": bool(controls_state["kerb_l_enabled"].get()),
                "kerb_r_enabled": bool(controls_state["kerb_r_enabled"].get()),
                "kerb_l_start_percent": self.clamp_int(controls_state["kerb_l_start_percent"].get(), 0, 100),
                "kerb_r_start_percent": self.clamp_int(controls_state["kerb_r_start_percent"].get(), 0, 100),
                "kerb_l_low_hz": kerb_l_low_hz,
                "kerb_l_high_hz": kerb_l_high_hz,
                "kerb_r_low_hz": kerb_r_low_hz,
                "kerb_r_high_hz": kerb_r_high_hz,
                "kerb_l_low_amp": kerb_l_low_amp,
                "kerb_l_high_amp": kerb_l_high_amp,
                "kerb_r_low_amp": kerb_r_low_amp,
                "kerb_r_high_amp": kerb_r_high_amp,
                "strength": self.clamp_int(strength_percent / 100.0 * 255.0, 0, 255),
                "smooth_start_ms": self.clamp_int(controls_state["smooth_start_ms"].get(), 0, 300),
                "pulse_strength": pulse_strength,
                "pulse_start_percent": self.clamp_int(controls_state["pulse_start_percent"].get(), 0, 100),
                "pulse_offset": self.clamp_int(controls_state["pulse_offset"].get(), pulse_offset_min, pulse_offset_max),
                "pulse_timing_offset": self.clamp_int(controls_state["pulse_timing_offset"].get(), -5, 5),
                "haptic_pulse_hz": self.clamp_int(controls_state["haptic_pulse_hz"].get(), 20, 160),
                "haptic_pulse_strength": self.clamp_int(controls_state["haptic_pulse_strength"].get(), 0, 10),
                "haptic_pulse_start_margin": self.clamp_int(controls_state["haptic_pulse_start_margin"].get(), -20, 25),
                "haptic_pulse_end_margin": self.clamp_int(controls_state["haptic_pulse_end_margin"].get(), -20, 25),
                "pulse_rate": self.clamp_int(controls_state["pulse_rate"].get(), 1, pulse_rate_max),
            }
        self.settings["selected_trigger_effect"] = self.selected_trigger_effect.get()
        self.settings["selected_detail_type"] = self.selected_detail_type.get()
        if mark_dirty:
            save_settings(self.settings)
            self.update_save_button_state()

    def save_trigger_mode_test_settings(self) -> None:
        self.settings["trigger_mode_test"] = {
            "count": self.clamp_int(self.trigger_mode_test_count.get(), 1, 30),
            "on_ms": self.clamp_int(self.trigger_mode_test_on_ms.get(), 20, 1000),
            "off_ms": self.clamp_int(self.trigger_mode_test_off_ms.get(), 0, 1000),
            "hz": self.clamp_int(self.trigger_mode_test_hz.get(), 1, 255),
            "amp": self.clamp_int(self.trigger_mode_test_amp.get(), 1, 255),
            "wall_start": self.clamp_int(self.trigger_mode_test_wall_start.get(), 0, 100),
            "wall_end": self.clamp_int(self.trigger_mode_test_wall_end.get(), 0, 100),
            "wall_strength": self.clamp_int(self.trigger_mode_test_wall_strength.get(), 0, 255),
        }
        save_settings(self.settings)

    def effect_volume(self, name: str) -> float:
        controls_state = self.effect_controls.get(name)
        if not controls_state or not controls_state["enabled"].get():
            return 0.0
        return self.clamp_volume(controls_state["volume"].get())

    def effect_pan_gains(self, name: str) -> tuple[float, float]:
        controls_state = self.effect_controls.get(name)
        if not controls_state or name not in PAN_EFFECTS or "pan" not in controls_state:
            return 1.0, 1.0
        pan = self.clamp_pan(controls_state["pan"].get())
        left = 1.0 if pan <= 5 else max(0.0, (10 - pan) / 5.0)
        right = 1.0 if pan >= 5 else max(0.0, pan / 5.0)
        return left, right

    @staticmethod
    def clamp_volume(value) -> int:
        try:
            numeric = round(float(value))
        except (TypeError, ValueError):
            numeric = 0
        return max(0, min(10, int(numeric)))

    @staticmethod
    def clamp_pan(value) -> int:
        try:
            numeric = round(float(value))
        except (TypeError, ValueError):
            numeric = 5
        return max(0, min(10, int(numeric)))

    @staticmethod
    def clamp_int(value, minimum: int, maximum: int) -> int:
        try:
            numeric = round(float(value))
        except (TypeError, ValueError):
            numeric = minimum
        return max(minimum, min(maximum, int(numeric)))

    @staticmethod
    def clamp_float(value, minimum: float, maximum: float) -> float:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            numeric = minimum
        return max(minimum, min(maximum, numeric))

    @staticmethod
    def dynamic_pulse_recommendation(force_percent) -> int:
        try:
            force = float(force_percent)
        except (TypeError, ValueError):
            force = 0.0
        force = max(0.0, min(80.0, force))
        if force <= 0.0:
            return 0
        if force <= 30.0:
            return int(round(force + 10.0))
        return int(round(40.0 + (force - 30.0) * (60.0 / 50.0)))

    @staticmethod
    def format_volume(value) -> str:
        volume = TelemetryApp.clamp_volume(value)
        return str(volume)

    @staticmethod
    def format_pan(value) -> str:
        pan = TelemetryApp.clamp_pan(value) - 5
        return "0" if pan == 0 else f"{pan:+d}"

    @staticmethod
    def format_graph_number(value: float) -> str:
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return "--"
        if not math.isfinite(numeric):
            return "--"
        abs_value = abs(numeric)
        if abs_value >= 1000.0:
            return f"{numeric:.0f}"
        if abs_value >= 100.0:
            return f"{numeric:.1f}".rstrip("0").rstrip(".")
        if abs_value >= 10.0:
            return f"{numeric:.2f}".rstrip("0").rstrip(".")
        return f"{numeric:.3f}".rstrip("0").rstrip(".")

    def resolve_field_name(self, value: str) -> str | None:
        key = alias_key(value.strip())
        if not key:
            return None
        return FIELD_ALIASES.get(key, value.strip())

    def signal_map(self) -> dict[str, float]:
        data: dict[str, float] = {}
        for source in (self.latest_raw, self.latest_values):
            for key, value in source.items():
                if isinstance(value, bool):
                    data[key] = 1.0 if value else 0.0
                else:
                    try:
                        data[key] = float(value)
                    except (TypeError, ValueError):
                        pass
        return data

    def graph_specs(self) -> list[GraphSpec]:
        specs = []
        for idx, var in enumerate(self.graph_inputs):
            label = var.get().strip() or DEFAULT_GRAPH_FIELDS[idx]
            key = self.resolve_field_name(label) or label
            scale = FIELD_DEFAULT_SCALES.get(key, 1.0)
            specs.append(GraphSpec(key, scale, GRAPH_COLORS[idx]))
        return specs

    def dynamic_scale(self, spec: GraphSpec, history: deque[tuple[float, float]]) -> float:
        if spec.name in FIELD_DEFAULT_SCALES:
            return max(0.001, spec.scale)
        if not history:
            return max(0.001, spec.scale)
        max_value = max(abs(value) for _ts, value in history)
        if max_value <= 0:
            return max(0.001, spec.scale)
        return max(0.001, max_value * 1.15)

    def tick(self) -> None:
        udp_state = "waiting"
        try:
            processed_items = self.drain_queue()
            now = time.monotonic()
            state, udp_state = self.udp_state_snapshot(now)
            self.update_save_button_state()
            width = max(1, self.canvas.winfo_width())
            height = max(1, self.canvas.winfo_height())
            standby_key = (width, height, state)
            should_draw = (
                udp_state == "live"
                or processed_items > 0
                or self.udp_visual_state != udp_state
                or (udp_state != "live" and self.graph_standby_key != standby_key)
            )
            if should_draw:
                self.trim_samples()
                self.update_brake_dynamic_cache_text()
                self.draw(now=now, state=state, udp_state=udp_state)
        except Exception as exc:
            self.last_error = f"UI tick failed: {type(exc).__name__}: {exc}"
            try:
                self.draw()
            except Exception:
                pass
        finally:
            delay = UI_FPS_MS if udp_state == "live" else 100
            self.root.after(delay, self.tick)

    def rpm_hud_tick(self) -> None:
        try:
            if self.udp_receiving and self.should_draw_hud_windows():
                self.draw_rpm_hud()
                self.draw_engine_hud()
        except Exception as exc:
            self.last_error = f"Fast HUD tick failed: {type(exc).__name__}: {exc}"
        finally:
            self.root.after(RPM_HUD_FPS_MS, self.rpm_hud_tick)

    def drain_queue(self) -> int:
        processed_items = 0
        while True:
            try:
                item = self.queue.get_nowait()
            except queue.Empty:
                return processed_items
            processed_items += 1

            if item[0] == "bad_packet":
                self.last_error = item[2]
                continue
            if item[0] == "bind_error":
                self.last_error = f"Port bind failed on {item[2]}: {item[3]}"
                self.udp_bind_failed = True
                self.update_udp_status("error")
                continue
            if item[0] == "trigger_status_error":
                self.last_error = f"Trigger status bind failed: {item[2]}"
                continue
            if item[0] == "trigger_status":
                _, now, values = item
                self.last_dualsense_input_at = now
                left = values.get("leftPct", 0.0)
                right = values.get("rightPct", 0.0)
                self.dualsense_left_pct = max(0.0, min(100.0, left))
                self.dualsense_right_pct = max(0.0, min(100.0, right))
                raw_left = int(values.get("left", 0.0))
                raw_right = int(values.get("right", 0.0))
                self.dualsense_input_text = (
                    f"DualSense L2 {left:4.1f}% ({raw_left:3d})  "
                    f"R2 {right:4.1f}% ({raw_right:3d})"
                )
                continue

            _, now, _addr, raw, values = item
            self.udp_bind_failed = False
            self.packet_count += 1
            self.last_packet_at = now
            if time.monotonic() - now > MAX_REALTIME_PACKET_AGE_S:
                self.clear_trigger_output_state()
                continue
            self.handle_car_ordinal_change(raw)
            self.latest_raw = raw
            self.latest_values = values
            self.update_drift_mode_state(now, raw)
            data = self.signal_map()
            for idx, spec in enumerate(self.graph_specs()):
                if idx < len(self.graph_hidden_vars) and self.graph_hidden_vars[idx].get():
                    continue
                if spec.name in data:
                    self.samples.setdefault(spec.name, deque()).append((now, float(data[spec.name])))
            try:
                self.prepare_log_analysis(now, raw, values)
                self.detect_haptic_events(raw)
                self.send_rev_limit_state(raw)
                self.send_rumble_kerbs_state(raw)
                self.send_tire_limit_load_state(raw)
                self.send_wheelspin_buzz_state(raw)
                self.send_road_bumps_state(now, raw)
                self.send_brake_resistance_state(now, raw, values)
                self.detect_side_impact_event(now, raw)
                self.detect_smashable_impact_event(now, raw)
                self.detect_impact_event(now, raw, values)
                self.update_effect_output_samples(now, raw)
                self.write_log_row(now, raw, values)
            except Exception as exc:
                self.last_error = f"packet effect failed: {type(exc).__name__}: {exc}"

    def detect_haptic_events(self, raw: dict[str, float | int | bool]) -> None:
        if not bool(raw["on"]):
            return

        gear = int(raw["gear"])
        # Forza can briefly report 11 during clutch/shift transition. Treat it
        # as a transient, not as a real gear, so one physical shift produces
        # one haptic event instead of two.
        if gear == TRANSIENT_GEAR_VALUE:
            return

        if self.previous_gear is not None and gear != self.previous_gear:
            self.send_gear_shift_event(raw, gear - self.previous_gear)
        self.previous_gear = gear

    def send_gear_shift_event(self, raw: dict[str, float | int | bool], gear_delta: int) -> None:
        self.current_log_analysis["event_gear_shift"] = 1
        self.current_log_analysis["event_gear_shift_dir"] = 1 if gear_delta > 0 else -1
        max_rpm = max(float(raw["max_rpm"]), 1.0)
        shift_left, shift_right = self.gear_shift_direction_gains(gear_delta)
        fields = {
            "dir": 1 if gear_delta > 0 else -1,
            "rpmRatio": max(0.0, min(1.0, float(raw["rpm"]) / max_rpm)),
            "throttle": max(0.0, min(1.0, float(raw["accel"]) / 255.0)),
            "torque": max(0.0, min(1.0, abs(float(raw["torque"])) / 900.0)),
            "pi": int(raw["car_performance_index"]),
            "carClass": int(raw["car_class"]),
            "carGroup": int(raw["car_group"]),
            "maxRpm": int(max_rpm),
            "coreVolume": self.effect_volume(EFFECT_GEAR_SHIFT_CORE),
            "highHzVolume": self.effect_volume(EFFECT_GEAR_SHIFT_HIGH_HZ),
            "particlesVolume": self.effect_volume(EFFECT_GEAR_SHIFT_PARTICLES),
            "coreLeft": shift_left,
            "coreRight": shift_right,
            "highHzLeft": shift_left,
            "highHzRight": shift_right,
            "particlesLeft": shift_left,
            "particlesRight": shift_right,
        }
        payload = "GEAR_SHIFT|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload)
        self.send_gear_shift_trigger_event(gear_delta)
        time_scale = self.shift_time_scale(raw)
        direction = 1 if gear_delta > 0 else -1
        self.trigger_effect_output(EFFECT_GEAR_SHIFT_CORE, 10.0, 0.36 * time_scale, direction)
        self.trigger_effect_output(EFFECT_GEAR_SHIFT_HIGH_HZ, 10.0, 0.50 * time_scale, direction)
        self.trigger_effect_output(EFFECT_GEAR_SHIFT_PARTICLES, 10.0, 0.58 * time_scale, direction)

    @staticmethod
    def gear_shift_direction_gains(gear_delta: int) -> tuple[float, float]:
        if gear_delta > 0:
            return 0.30, 0.70
        return 0.70, 0.30

    def send_gear_shift_trigger_event(self, gear_delta: int) -> None:
        controls_state = self.trigger_controls.get(TRIGGER_GEAR_SHIFT_KICK)
        if not controls_state or not controls_state["enabled"].get():
            return
        is_upshift = gear_delta > 0
        strength_var = "upshift_strength_percent" if is_upshift else "downshift_strength_percent"
        duration_var = "upshift_duration_ms" if is_upshift else "downshift_duration_ms"
        strength = self.clamp_int(controls_state[strength_var].get(), 0, 100)
        if strength <= 0:
            return
        duration_ms = self.clamp_int(controls_state[duration_var].get(), 20, 180)
        sides_value = (
            controls_state["upshift_sides"].get()
            if is_upshift
            else controls_state["downshift_sides"].get()
        )
        sides = normalize_trigger_sides(sides_value, "Right" if is_upshift else "Left")
        if sides == "Both":
            side = "both"
        else:
            side = "left" if sides == "Left" else "right"
        soft_zone = self.clamp_int(controls_state["early_input_soft_zone"].get(), 0, 60)
        late_position = self.clamp_int(controls_state["kick_late_position"].get(), 0, 100)
        start_byte = self.wall_position_percent_to_start_byte(float(late_position)) if late_position > 0 else -1
        kick_softness = self.clamp_int(controls_state["kick_softness"].get(), 0, 10)
        release_ms = self.clamp_int(controls_state["release_duration_ms"].get(), 0, 120)
        strength = self.gear_shift_softened_strength(strength, sides, soft_zone)
        if strength <= 0:
            return
        fields = {
            "side": side,
            "strength": strength,
            "durationMs": duration_ms,
            "start": start_byte,
            "softness": kick_softness,
            "releaseMs": release_ms,
            "dir": 1 if is_upshift else -1,
        }
        payload = self.trigger_payload("TRIGGER_GEAR_SHIFT", fields)
        self.send_haptic_event(payload, count=False)
        self.seed_trigger_output_preview(
            TRIGGER_GEAR_SHIFT_KICK,
            time.monotonic(),
            strength / 10.0,
            duration_ms / 1000.0,
        )

    def gear_shift_softened_strength(self, strength: int, sides: str, soft_zone: int) -> int:
        if soft_zone <= 0:
            return strength
        if time.monotonic() - self.last_dualsense_input_at > 1.0:
            return strength
        if sides == "Left":
            trigger_pct = self.dualsense_left_pct
        elif sides == "Right":
            trigger_pct = self.dualsense_right_pct
        else:
            trigger_pct = max(self.dualsense_left_pct, self.dualsense_right_pct)
        mix = max(0.0, min(1.0, trigger_pct / max(1.0, float(soft_zone))))
        multiplier = 0.35 + 0.65 * mix
        return self.clamp_int(round(strength * multiplier), 0, 100)

    def send_collision_kick_trigger_event(
        self,
        power: float,
        side_hint: float,
        impact_score: float | None = None,
        dvel: float | None = None,
        accel_x_delta: float | None = None,
        angular_y_delta: float | None = None,
    ) -> None:
        controls_state = self.trigger_controls.get(TRIGGER_COLLISION_KICK)
        if not controls_state or not controls_state["enabled"].get():
            return
        if power < 0.14:
            return
        if impact_score is not None:
            strong_edge = (
                (dvel is not None and dvel >= 1.55)
                or (accel_x_delta is not None and accel_x_delta >= 4.8)
                or (angular_y_delta is not None and angular_y_delta >= 0.18)
            )
            if (impact_score < 0.22 and power < 0.20) or not strong_edge:
                return
        strength = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
        if strength <= 0:
            return
        duration_ms = self.clamp_int(controls_state["smooth_start_ms"].get(), 40, 300)
        side = "left" if side_hint < 0 else "right"
        fields = {
            "side": side,
            "strength": max(1, min(100, int(round(strength * max(0.20, min(1.0, power)))))),
            "durationMs": duration_ms,
        }
        payload = self.trigger_payload("TRIGGER_COLLISION_KICK", fields)
        self.send_haptic_event(payload, count=False)
        self.seed_trigger_output_preview(
            TRIGGER_COLLISION_KICK,
            time.monotonic(),
            fields["strength"] / 10.0,
            duration_ms / 1000.0,
        )

    def send_impact_tick_trigger_event(self, power: float) -> None:
        controls_state = self.trigger_controls.get(TRIGGER_IMPACT_TICK)
        if not controls_state or not controls_state["enabled"].get():
            return
        if power < 0.08:
            return
        base_amp = self.clamp_int(controls_state["slip_dsx_vibration_amplitude"].get(), 1, 8)
        amp = max(1, min(8, int(round(base_amp * max(0.15, min(1.0, power))))))
        fields = {
            "amp": amp,
            "freq": self.clamp_int(controls_state["slip_dsx_vibration_frequency"].get(), 1, 40),
            "startZone": self.clamp_int(controls_state["slip_dsx_vibration_margin"].get(), 0, 9),
            "durationMs": self.clamp_int(controls_state["smooth_start_ms"].get(), 40, 300),
        }
        payload = self.trigger_payload("TRIGGER_IMPACT_TICK", fields)
        self.send_haptic_event(payload, count=False)
        self.seed_trigger_output_preview(
            TRIGGER_IMPACT_TICK,
            time.monotonic(),
            amp / 8.0 * 10.0,
            fields["durationMs"] / 1000.0,
        )

    def seed_trigger_output_preview(
        self,
        trigger_name: str,
        started_at: float,
        peak_level: float,
        duration_s: float,
    ) -> None:
        history = self.trigger_output_samples.setdefault(trigger_name, deque())
        peak = max(0.0, min(10.0, float(peak_level)))
        duration = max(0.001, float(duration_s))
        sample_count = max(8, min(32, int(duration * 240)))
        for idx in range(sample_count + 1):
            mix = idx / max(1, sample_count)
            if mix < 0.18:
                level = peak * (mix / 0.18)
            else:
                level = peak * max(0.0, 1.0 - (mix - 0.18) / 0.82)
            history.append((started_at + mix * duration, level))

    def shift_time_scale(self, raw: dict[str, float | int | bool]) -> float:
        max_rpm = max(float(raw["max_rpm"]), 1.0)
        engine_type = max(0.0, min(1.0, (max_rpm - 5500.0) / 4500.0))
        pi_factor = max(0.0, min(1.0, (float(raw["car_performance_index"]) - 500.0) / 400.0))
        throttle = max(0.0, min(1.0, float(raw["accel"]) / 255.0))
        torque = max(0.0, min(1.0, abs(float(raw["torque"])) / 900.0))
        load = max(0.0, min(1.0, torque * 0.65 + throttle * 0.35))
        fast_score = max(0.0, min(1.0, engine_type * 0.50 + pi_factor * 0.35 + (1 - load) * 0.15))
        slow_score = max(0.0, min(1.0, (1 - engine_type) * 0.50 + (1 - pi_factor) * 0.30 + load * 0.20))
        fast_class = 1.0 if fast_score >= 0.62 else 0.0
        slow_class = 1.0 if slow_score >= 0.62 else 0.0
        return 1.0 + slow_class * 0.22 - fast_class * 0.18

    def send_rev_limit_state(self, raw: dict[str, float | int | bool]) -> None:
        left, right = self.effect_pan_gains(EFFECT_REV_LIMIT)
        fields = {
            "rpm": max(0.0, float(raw["rpm"])),
            "maxRpm": max(0.0, float(raw["max_rpm"])),
            "idleRpm": max(0.0, float(raw["idle_rpm"])),
            "volume": self.effect_volume(EFFECT_REV_LIMIT) if bool(raw["on"]) else 0.0,
            "left": left,
            "right": right,
        }
        payload = "REV_LIMIT|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)

    def send_rumble_kerbs_state(self, raw: dict[str, float | int | bool]) -> None:
        fl_level, fr_level, hz = self.rumble_kerbs_levels(raw)
        volume = self.effect_volume(EFFECT_RUMBLE_KERBS) if bool(raw["on"]) else 0.0
        fields = {
            "fl": fl_level,
            "fr": fr_level,
            "hz": hz,
            "speed": max(0.0, float(raw["speed_kmh"])),
            "volume": volume,
        }
        payload = "RUMBLE_KERBS|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)
        self.send_kerb_buzz_trigger_state(raw, fl_level, fr_level)

    def send_kerb_buzz_trigger_state(self, raw: dict[str, float | int | bool], fl_level: float, fr_level: float) -> None:
        controls_state = self.trigger_controls.get(TRIGGER_KERB_BUZZ)
        if not controls_state:
            return
        enabled = bool(controls_state["enabled"].get()) and bool(raw["on"])
        kerb_level = max(0.0, float(fl_level), float(fr_level))
        kerb_on = enabled and kerb_level > 0.0
        left_on = kerb_on and bool(controls_state["kerb_l_enabled"].get())
        right_on = kerb_on and bool(controls_state["kerb_r_enabled"].get())
        speed = max(0.0, float(raw["speed_kmh"]))
        left_freq = self.kerb_buzz_frequency(
            speed,
            self.clamp_int(controls_state["kerb_l_low_hz"].get(), 1, 40),
            self.clamp_int(controls_state["kerb_l_high_hz"].get(), 1, 40),
        )
        right_freq = self.kerb_buzz_frequency(
            speed,
            self.clamp_int(controls_state["kerb_r_low_hz"].get(), 1, 40),
            self.clamp_int(controls_state["kerb_r_high_hz"].get(), 1, 40),
        )
        left_amp = self.kerb_buzz_amplitude(
            speed,
            self.clamp_int(controls_state["kerb_l_low_amp"].get(), 1, 8),
            self.clamp_int(controls_state["kerb_l_high_amp"].get(), 1, 8),
        )
        right_amp = self.kerb_buzz_amplitude(
            speed,
            self.clamp_int(controls_state["kerb_r_low_amp"].get(), 1, 8),
            self.clamp_int(controls_state["kerb_r_high_amp"].get(), 1, 8),
        )
        left_start_zone = self.trigger_start_percent_to_zone(controls_state["kerb_l_start_percent"].get())
        right_start_zone = self.trigger_start_percent_to_zone(controls_state["kerb_r_start_percent"].get())
        fields = {
            "left": 1 if left_on else 0,
            "right": 1 if right_on else 0,
            "leftAmp": left_amp if left_on else 0,
            "leftFreq": left_freq if left_on else 0,
            "leftStartZone": left_start_zone,
            "rightAmp": right_amp if right_on else 0,
            "rightFreq": right_freq if right_on else 0,
            "rightStartZone": right_start_zone,
        }
        payload = "TRIGGER_KERB_BUZZ|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)
        preview_amp = max(left_amp if left_on else 0, right_amp if right_on else 0)
        preview_level = (preview_amp / 8.0 * 10.0) if (left_on or right_on) else 0.0
        self.kerb_buzz_output_force = preview_level / 10.0 * 255.0
        self.trigger_output_samples.setdefault(TRIGGER_KERB_BUZZ, deque()).append((time.monotonic(), preview_level))

    def rumble_kerbs_levels(self, raw: dict[str, float | int | bool]) -> tuple[float, float, float]:
        if not bool(raw["on"]):
            return 0.0, 0.0, 18.0
        speed = max(0.0, float(raw["speed_kmh"]))
        speed_gain = 1.0
        fl_on = self.is_rumble_kerb_on(float(raw["surface_rumble_fl"]), int(raw["wheel_on_rumble_strip_fl"]), 0.21, 0.25)
        fr_on = self.is_rumble_kerb_on(float(raw["surface_rumble_fr"]), int(raw["wheel_on_rumble_strip_fr"]), 0.20, 0.29)
        return (speed_gain if fl_on else 0.0, speed_gain if fr_on else 0.0, self.rumble_kerbs_frequency(speed))

    @staticmethod
    def is_rumble_kerb_on(surface_rumble: float, wheel_on_rumble: int, low: float, high: float) -> bool:
        rumble = abs(surface_rumble)
        return low <= rumble <= high or wheel_on_rumble != 0

    @staticmethod
    def rumble_kerbs_frequency(speed_kmh: float) -> float:
        low_speed_hz = 18.0
        high_speed_hz = 82.0
        low_speed_kmh = 5.0
        high_speed_kmh = 330.0
        x = max(0.0, min(1.0, (speed_kmh - low_speed_kmh) / max(high_speed_kmh - low_speed_kmh, 1.0)))
        speed_mix = x * x * (3.0 - 2.0 * x)
        return max(low_speed_hz, min(high_speed_hz, low_speed_hz + (high_speed_hz - low_speed_hz) * speed_mix))

    @staticmethod
    def kerb_buzz_frequency(speed_kmh: float, low_hz: int, high_hz: int) -> int:
        low_speed_kmh = 5.0
        high_speed_kmh = 330.0
        low = max(1, min(40, int(low_hz)))
        high = max(1, min(40, int(high_hz)))
        if low > high:
            low, high = high, low
        x = max(0.0, min(1.0, (speed_kmh - low_speed_kmh) / max(high_speed_kmh - low_speed_kmh, 1.0)))
        speed_mix = x * x * (3.0 - 2.0 * x)
        return max(1, min(40, int(round(low + (high - low) * speed_mix))))

    @staticmethod
    def kerb_buzz_amplitude(speed_kmh: float, low_amp: int, high_amp: int) -> int:
        low = max(1, min(8, int(low_amp)))
        high = max(1, min(8, int(high_amp)))
        if low > high:
            low, high = high, low
        low_speed_kmh = 5.0
        high_speed_kmh = 330.0
        x = max(0.0, min(1.0, (speed_kmh - low_speed_kmh) / max(high_speed_kmh - low_speed_kmh, 1.0)))
        speed_mix = x * x * (3.0 - 2.0 * x)
        return max(1, min(8, int(round(low + (high - low) * speed_mix))))

    def trigger_start_percent_to_zone(self, start_percent) -> int:
        start = self.clamp_int(start_percent, 0, 100)
        return max(0, min(9, int(round(start / 100.0 * 9.0))))

    def send_tire_limit_load_state(self, raw: dict[str, float | int | bool]) -> None:
        left, right, left_hz, right_hz = self.tire_limit_load_levels(raw)
        self.latest_tire_limit_levels = (left, right, left_hz, right_hz)
        volume = self.effect_volume(EFFECT_TIRE_LIMIT_LOAD) if bool(raw["on"]) else 0.0
        fields = {
            "left": left,
            "right": right,
            "leftHz": left_hz,
            "rightHz": right_hz,
            "volume": volume,
        }
        payload = "TIRE_LIMIT_LOAD|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)

    def tire_limit_load_levels(self, raw: dict[str, float | int | bool]) -> tuple[float, float, float, float]:
        if not bool(raw["on"]):
            self.tire_limit_prev_left = 0.0
            self.tire_limit_prev_right = 0.0
            return 0.0, 0.0, 35.0, 35.0

        speed_ms = max(0.0, float(raw["speed_kmh"]) / 3.6)
        steer = float(raw["steer"])
        yaw_rate = abs(float(raw["angular_velocity_y"]))
        abs_steer = abs(steer)

        fl_angle = abs(float(raw["tire_slip_angle_fl"]))
        fr_angle = abs(float(raw["tire_slip_angle_fr"]))
        rl_angle = abs(float(raw["tire_slip_angle_rl"]))
        rr_angle = abs(float(raw["tire_slip_angle_rr"]))
        fl_combined = abs(float(raw["tire_combined_slip_fl"]))
        fr_combined = abs(float(raw["tire_combined_slip_fr"]))
        rl_combined = abs(float(raw["tire_combined_slip_rl"]))
        rr_combined = abs(float(raw["tire_combined_slip_rr"]))
        fl_ratio = abs(float(raw["tire_slip_ratio_fl"]))
        fr_ratio = abs(float(raw["tire_slip_ratio_fr"]))

        front_angle = (fl_angle + fr_angle) * 0.5
        rear_angle = (rl_angle + rr_angle) * 0.5
        front_combined = (fl_combined + fr_combined) * 0.5
        rear_combined = (rl_combined + rr_combined) * 0.5
        front_slip_ratio = (fl_ratio + fr_ratio) * 0.5

        body_slip = abs(math.atan2(float(raw["velocity_x"]), max(abs(float(raw["velocity_z"])), 0.1)))
        speed_gate = self.smoothstep(7.0, 14.0, speed_ms)
        steer_gate = self.smoothstep(35.0, 115.0, abs_steer)

        gx = -float(raw["accel_x"]) / 9.80665
        gz = float(raw["accel_z"]) / 9.80665
        self.tire_limit_gx_smooth += (gx - self.tire_limit_gx_smooth) * 0.40
        self.tire_limit_gz_smooth += (gz - self.tire_limit_gz_smooth) * 0.45
        gx_smooth = self.tire_limit_gx_smooth
        gz_smooth = self.tire_limit_gz_smooth
        abs_lateral_g = abs(gx_smooth)

        decel_load = self.smoothstep(0.03, 1.00, -gz_smooth)
        accel_unload = self.smoothstep(0.03, 0.30, gz_smooth)
        longitudinal_load = max(0.45, min(1.40, 1.0 + decel_load * 0.40 - accel_unload * 0.45))
        accel_limit_suppress = max(0.15, min(1.0, 1.0 - accel_unload * 0.90))
        lateral_gate = self.smoothstep(0.04, 1.20, abs_lateral_g)
        straight_brake_gate = decel_load
        load_intent_gate = max(lateral_gate, straight_brake_gate)

        front_limit_window = self.smoothstep(0.75, 1.45, front_angle) * (1.0 - self.smoothstep(2.55, 3.90, front_angle))
        combined_window = self.smoothstep(0.25, 0.85, front_combined) * (1.0 - self.smoothstep(2.65, 3.95, front_combined))
        brake_ratio_window = self.smoothstep(0.06, 0.32, front_slip_ratio) * (1.0 - self.smoothstep(1.45, 2.55, front_slip_ratio))
        brake_combined_window = self.smoothstep(0.18, 0.70, front_combined) * (1.0 - self.smoothstep(2.65, 3.95, front_combined))
        straight_brake_limit_window = max(brake_ratio_window, brake_combined_window * 0.70)

        rear_angle_cut = 1.0 - self.smoothstep(1.55, 3.05, rear_angle)
        rear_combined_cut = 1.0 - self.smoothstep(2.25, 3.80, rear_combined)
        body_slip_cut = 1.0 - self.smoothstep(0.75, 1.35, body_slip)
        spin_cut = 1.0 - self.smoothstep(3.0, 4.8, yaw_rate)

        global_limit = (
            front_limit_window
            * combined_window
            * speed_gate
            * load_intent_gate
            * rear_angle_cut
            * rear_combined_cut
            * body_slip_cut
            * spin_cut
            * accel_limit_suppress
        )

        left = self.tire_limit_side_level(
            -1,
            fl_angle,
            fl_combined,
            global_limit,
            straight_brake_gate,
            straight_brake_limit_window,
            speed_gate,
            rear_angle_cut,
            rear_combined_cut,
            body_slip_cut,
            spin_cut,
            longitudinal_load,
            gx_smooth,
            abs_lateral_g,
        )
        right = self.tire_limit_side_level(
            1,
            fr_angle,
            fr_combined,
            global_limit,
            straight_brake_gate,
            straight_brake_limit_window,
            speed_gate,
            rear_angle_cut,
            rear_combined_cut,
            body_slip_cut,
            spin_cut,
            longitudinal_load,
            gx_smooth,
            abs_lateral_g,
        )

        timestamp_ms = float(raw["timestamp_ms"])
        left_hz = self.tire_limit_frequency(left * 100.0, timestamp_ms, "left")
        right_hz = self.tire_limit_frequency(right * 100.0, timestamp_ms, "right")
        return left, right, left_hz, right_hz

    def tire_limit_side_level(
        self,
        output_side: int,
        side_front_angle: float,
        side_front_combined: float,
        global_limit: float,
        straight_brake_gate: float,
        straight_brake_limit_window: float,
        speed_gate: float,
        rear_angle_cut: float,
        rear_combined_cut: float,
        body_slip_cut: float,
        spin_cut: float,
        longitudinal_load: float,
        gx_smooth: float,
        abs_lateral_g: float,
    ) -> float:
        side_limit_window = self.smoothstep(0.65, 1.40, side_front_angle) * (1.0 - self.smoothstep(2.45, 3.60, side_front_angle))
        side_combined_window = self.smoothstep(0.25, 0.85, side_front_combined) * (1.0 - self.smoothstep(2.65, 3.95, side_front_combined))
        side_lateral_g = -gx_smooth if output_side < 0 else gx_smooth
        lateral_side = self.smoothstep(0.04, 1.20, side_lateral_g)
        brake_bias = self.smoothstep(0.06, 1.00, abs_lateral_g) * 0.30
        brake_side_share = 0.50 + brake_bias if side_lateral_g >= 0 else 0.50 - brake_bias
        brake_side_load = straight_brake_gate * brake_side_share * 1.30
        side_load = max(lateral_side, brake_side_load)
        side_load_blend = 0.08 + 0.92 * side_load

        side_limit = (
            side_limit_window
            * side_combined_window
            * speed_gate
            * max(lateral_side, straight_brake_gate)
            * rear_angle_cut
            * rear_combined_cut
            * body_slip_cut
            * spin_cut
        )
        corner_raw = ((global_limit * 0.40) + (side_limit * 0.60)) * side_load_blend
        straight_brake_raw = (
            straight_brake_gate
            * straight_brake_limit_window
            * brake_side_share
            * speed_gate
            * rear_angle_cut
            * rear_combined_cut
            * body_slip_cut
            * spin_cut
            * 1.30
        )
        raw = max(corner_raw, straight_brake_raw) * longitudinal_load
        target = (max(0.0, min(1.0, raw)) ** 0.85)
        prev = self.tire_limit_prev_left if output_side < 0 else self.tire_limit_prev_right
        alpha = 0.42 if target > prev else 0.62
        out = prev + (target - prev) * alpha
        if output_side < 0:
            self.tire_limit_prev_left = out
        else:
            self.tire_limit_prev_right = out
        return max(0.0, min(1.0, out))

    def tire_limit_frequency(self, value_0_100: float, timestamp_ms: float, side: str) -> float:
        v = max(0.0, min(100.0, value_0_100))
        entry_trigger = 10.0
        entry_hold_ms = 160.0
        force_loaded_at = 40.0
        if side == "left":
            prev = self.tire_limit_freq_prev_left
            if prev < entry_trigger <= v:
                self.tire_limit_entry_until_left = timestamp_ms + entry_hold_ms
            if v < entry_trigger:
                self.tire_limit_entry_until_left = 0.0
            entry_until = self.tire_limit_entry_until_left
            self.tire_limit_freq_prev_left = v
        else:
            prev = self.tire_limit_freq_prev_right
            if prev < entry_trigger <= v:
                self.tire_limit_entry_until_right = timestamp_ms + entry_hold_ms
            if v < entry_trigger:
                self.tire_limit_entry_until_right = 0.0
            entry_until = self.tire_limit_entry_until_right
            self.tire_limit_freq_prev_right = v

        # Entry high-Hz cue is intentionally muted while tuning Tire Limit Load.
        # Keep the entry timer state above so it can be restored easily.
        loaded_mix = self.smoothstep(force_loaded_at, 100.0, v)
        return 40.0 + (15.0 - 40.0) * loaded_mix

    def send_wheelspin_buzz_state(self, raw: dict[str, float | int | bool]) -> None:
        left, right = self.wheelspin_buzz_levels(raw)
        if self.drift_relief_active():
            left *= DRIFT_RELIEF_WHEELSPIN_GAIN
            right *= DRIFT_RELIEF_WHEELSPIN_GAIN
        pan_left, pan_right = self.effect_pan_gains(EFFECT_WHEELSPIN_BUZZ)
        left *= pan_left
        right *= pan_right
        self.latest_wheelspin_levels = (left, right)
        volume = self.effect_volume(EFFECT_WHEELSPIN_BUZZ) if bool(raw["on"]) else 0.0
        fields = {
            "left": left,
            "right": right,
            "hz": 70.0,
            "volume": volume,
        }
        payload = "WHEELSPIN_BUZZ|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)

    def wheelspin_buzz_levels(self, raw: dict[str, float | int | bool]) -> tuple[float, float]:
        if not bool(raw["on"]):
            self.wheelspin_left_level = 0.0
            self.wheelspin_right_level = 0.0
            return 0.0, 0.0

        throttle = max(0.0, min(1.0, float(raw["accel"]) / 255.0))
        speed = max(0.0, float(raw["speed_kmh"]))
        drive_train = int(raw["drive_train"])
        if drive_train == 0:
            left_slip = max(0.0, float(raw["tire_slip_ratio_fl"]))
            right_slip = max(0.0, float(raw["tire_slip_ratio_fr"]))
        else:
            left_slip = max(0.0, float(raw["tire_slip_ratio_rl"]))
            right_slip = max(0.0, float(raw["tire_slip_ratio_rr"]))

        throttle_gate = self.smoothstep(0.18, 0.55, throttle)
        speed_gate = 1.0 - self.smoothstep(185.0, 245.0, speed)
        left_target = self.wheelspin_side_level(left_slip, throttle_gate, speed_gate)
        right_target = self.wheelspin_side_level(right_slip, throttle_gate, speed_gate)

        self.wheelspin_left_level = self.wheelspin_envelope(self.wheelspin_left_level, left_target)
        self.wheelspin_right_level = self.wheelspin_envelope(self.wheelspin_right_level, right_target)
        return self.wheelspin_left_level, self.wheelspin_right_level

    def wheelspin_side_level(self, slip_ratio: float, throttle_gate: float, speed_gate: float) -> float:
        slip_on = self.smoothstep(1.3, 1.9, slip_ratio)
        slip_cut = 1.0 - self.smoothstep(2.1, 2.85, slip_ratio)
        level = slip_on * slip_cut * throttle_gate * speed_gate
        return max(0.0, min(1.0, level))

    @staticmethod
    def wheelspin_envelope(previous: float, target: float) -> float:
        if target > previous:
            floor = 0.18 if target > 0.05 else 0.0
            return max(floor, previous + (target - previous) * 0.62)
        return max(0.0, previous * 0.82 + target * 0.08)

    def send_road_bumps_state(self, now: float, raw: dict[str, float | int | bool]) -> None:
        left, right, hz, volume = self.road_bumps_levels(now, raw)
        fields = {
            "left": left,
            "right": right,
            "hz": hz,
            "volume": volume,
        }
        payload = "ROAD_BUMPS|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload, count=False)

    def send_brake_resistance_state(self, now: float, raw: dict[str, float | int | bool], values: dict[str, float]) -> None:
        if self.trigger_force_last_time <= 0:
            dt = 0.0
        else:
            dt = max(0.0, min(0.1, now - self.trigger_force_last_time))
        self.trigger_force_last_time = now
        self.reset_brake_dynamic_server_pulse()
        self.reset_throttle_server_pulse()
        pressure = self.smooth_trigger_force(TRIGGER_BRAKE_PRESSURE, self.brake_pressure_force(raw), dt)
        resistance = self.smooth_trigger_force(TRIGGER_BRAKE_RESISTANCE, self.brake_resistance_force(now, raw, values), dt)
        dynamic_target = self.brake_resistance_dynamic_force(now, raw, values)
        dynamic = self.smooth_trigger_force(
            TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
            dynamic_target,
            dt,
        )
        predictive_controls = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE_PREDICTIVE)
        if predictive_controls and predictive_controls["enabled"].get():
            predictive_target = self.brake_resistance_predictive_force(now, raw, values)
        else:
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE_PREDICTIVE] = False
            self.brake_predictive_trigger_mode_active = False
            self.brake_predictive_trigger_end_percent = -1.0
            self.brake_predictive_wall_smoothed = -1.0
            predictive_target = 0
        predictive = self.smooth_trigger_force(
            TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
            predictive_target,
            dt,
        )
        if self.drift_relief_trigger_suppression_active():
            self.clear_drift_relief_r2_outputs()
            throttle_pressure = 0
            throttle_traction = 0
            rpm_rev_limit = 0
        else:
            throttle_pressure = self.smooth_trigger_force(TRIGGER_THROTTLE_PRESSURE, self.throttle_pressure_force(raw), dt)
            throttle_traction = self.smooth_trigger_force(
                TRIGGER_THROTTLE_TRACTION_LIMIT,
                self.throttle_traction_limit_force(raw),
                dt,
            )
            rpm_rev_limit = self.rpm_rev_limit_force(now, raw)
        throttle = max(0, min(255, throttle_pressure + throttle_traction + rpm_rev_limit))
        force = max(0, min(255, pressure + resistance + dynamic + predictive))
        brake_vibration_display = self.clamp_int(getattr(self, "brake_server_vibration_amplitude", 0), 0, 8) / 8.0 * 255.0
        resistance_display = max(0, min(255, max(resistance, brake_vibration_display)))
        dynamic_display = max(
            0,
            min(
                255,
                max(
                    dynamic,
                    self.clamp_int(getattr(self, "brake_dynamic_server_pulse", 0), 0, 255),
                    brake_vibration_display,
                ),
            ),
        )
        predictive_display = max(
            0,
            min(
                255,
                max(
                    predictive,
                    self.clamp_int(getattr(self, "brake_dynamic_server_pulse", 0), 0, 255),
                    brake_vibration_display,
                ),
            ),
        )
        throttle_traction_display = max(
            throttle_traction,
            self.clamp_int(getattr(self, "throttle_server_pulse", 0), 0, 255),
            self.clamp_int(getattr(self, "throttle_server_vibration_amplitude", 0), 0, 8) / 8.0 * 255.0,
        )
        self.update_trigger_output_samples(
            now,
            {
                TRIGGER_BRAKE_PRESSURE: pressure,
                TRIGGER_BRAKE_RESISTANCE: resistance_display,
                TRIGGER_BRAKE_RESISTANCE_DYNAMIC: dynamic_display,
                TRIGGER_BRAKE_RESISTANCE_PREDICTIVE: predictive_display,
                TRIGGER_THROTTLE_PRESSURE: throttle_pressure,
                TRIGGER_THROTTLE_TRACTION_LIMIT: throttle_traction_display,
                TRIGGER_RPM_REV_LIMIT: rpm_rev_limit,
                TRIGGER_KERB_BUZZ: getattr(self, "kerb_buzz_output_force", 0.0),
            },
        )
        pulse = self.clamp_int(getattr(self, "brake_dynamic_server_pulse", 0), 0, 255)
        pulse_rate = self.clamp_int(getattr(self, "brake_dynamic_server_pulse_rate", 0), 0, 255)
        brake_fields: dict[str, int] = {"force": force}
        brake_start = self.brake_wall_start_byte(resistance, dynamic, predictive)
        if brake_start >= 0:
            brake_fields["start"] = brake_start
        brake_fields["pulse"] = pulse
        brake_fields["pulseRate"] = pulse_rate
        brake_vibration_amp = self.clamp_int(getattr(self, "brake_server_vibration_amplitude", 0), 0, 8)
        brake_vibration_freq = self.clamp_int(getattr(self, "brake_server_vibration_frequency", 0), 0, 40)
        brake_vibration_zone = self.clamp_int(getattr(self, "brake_server_vibration_start_zone", 0), 0, 9)
        brake_fields["vibrateAmp"] = brake_vibration_amp
        brake_fields["vibrateFreq"] = brake_vibration_freq
        brake_fields["vibrateStartZone"] = brake_vibration_zone
        self.send_haptic_event(self.trigger_payload("TRIGGER_BRAKE", brake_fields), count=False)
        throttle_fields: dict[str, int] = {"force": throttle}
        throttle_start = self.throttle_wall_start_byte(throttle_traction)
        if throttle_start >= 0:
            throttle_fields["start"] = throttle_start
        throttle_pulse = self.clamp_int(getattr(self, "throttle_server_pulse", 0), 0, 255)
        throttle_pulse_rate = self.clamp_int(getattr(self, "throttle_server_pulse_rate", 0), 0, 255)
        throttle_fields["pulse"] = throttle_pulse
        throttle_fields["pulseRate"] = throttle_pulse_rate
        throttle_vibration_amp = self.clamp_int(getattr(self, "throttle_server_vibration_amplitude", 0), 0, 8)
        throttle_vibration_freq = self.clamp_int(getattr(self, "throttle_server_vibration_frequency", 0), 0, 40)
        throttle_vibration_zone = self.clamp_int(getattr(self, "throttle_server_vibration_start_zone", 0), 0, 9)
        throttle_fields["vibrateAmp"] = throttle_vibration_amp
        throttle_fields["vibrateFreq"] = throttle_vibration_freq
        throttle_fields["vibrateStartZone"] = throttle_vibration_zone
        self.send_haptic_event(self.trigger_payload("TRIGGER_THROTTLE", throttle_fields), count=False)

    def update_trigger_output_samples(self, now: float, trigger_forces: dict[str, float]) -> None:
        for trigger_name in DEFAULT_TRIGGER_SETTINGS:
            force = max(0.0, min(255.0, float(trigger_forces.get(trigger_name, 0.0))))
            level = max(0.0, min(10.0, force / 255.0 * 10.0))
            self.trigger_output_samples.setdefault(trigger_name, deque()).append((now, level))

    def brake_wall_start_byte(self, resistance_force: int, dynamic_force: int, predictive_force: int = 0) -> int:
        if dynamic_force > 0 or predictive_force > 0:
            start_percent = float(getattr(self, "brake_dynamic_wall_start_percent", -1.0))
            if start_percent >= 0.0:
                return self.wall_position_percent_to_start_byte(start_percent)
        return self.brake_resistance_start_byte(resistance_force)

    def throttle_wall_start_byte(self, traction_force: int) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_THROTTLE_TRACTION_LIMIT)
        if not controls_state or not controls_state["enabled"].get() or traction_force <= 0:
            return -1
        start_percent = float(getattr(self, "throttle_traction_wall_start_percent", -1.0))
        if start_percent < 0.0:
            return -1
        return self.wall_position_percent_to_start_byte(start_percent)

    def brake_resistance_start_byte(self, resistance_force: int) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE)
        if not controls_state or not controls_state["enabled"].get() or resistance_force <= 0:
            return -1
        start_percent = self.clamp_int(controls_state["start_percent"].get(), 0, 100)
        return self.wall_position_percent_to_start_byte(float(start_percent))

    def wall_position_percent_to_start_byte(self, position_percent: float) -> int:
        """Map desired perceived wall position to DualSense RigidAt start byte.

        Clean calibration was measured with Forza in-game dead zones set to 0.
        Raw 80 already reaches displayed input 100%, with a little physical
        travel still remaining, so higher raw values are intentionally unused.
        """
        desired = max(0.0, min(100.0, float(position_percent)))
        calibration = (
            (0.0, 0.0),
            (31.0, 40.0),
            (42.0, 45.0),
            (53.0, 50.0),
            (65.0, 55.0),
            (69.0, 60.0),
            (80.0, 65.0),
            (88.0, 70.0),
            (96.0, 75.0),
            (100.0, 80.0),
        )
        raw_percent = calibration[-1][1]
        for index in range(1, len(calibration)):
            prev_perceived, prev_raw = calibration[index - 1]
            next_perceived, next_raw = calibration[index]
            if desired <= next_perceived:
                span = max(next_perceived - prev_perceived, 0.001)
                mix = (desired - prev_perceived) / span
                raw_percent = prev_raw + (next_raw - prev_raw) * mix
                break
        raw_percent = max(0.0, min(80.0, raw_percent))
        return self.clamp_int(round(raw_percent / 100.0 * 255.0), 0, 255)

    def smooth_trigger_force(self, trigger_name: str, target_force: int, dt: float) -> int:
        target = float(max(0, min(255, target_force)))
        current = float(self.trigger_smoothed_force.get(trigger_name, 0.0))
        controls_state = self.trigger_controls.get(trigger_name)
        if self.trigger_smooth_bypass.get(trigger_name, False):
            self.trigger_smoothed_force[trigger_name] = target
            return int(round(target))
        if target <= current or not controls_state:
            self.trigger_smoothed_force[trigger_name] = target
            return int(round(target))

        smooth_ms = self.clamp_int(controls_state["smooth_start_ms"].get(), 0, 300)
        if smooth_ms <= 0:
            self.trigger_smoothed_force[trigger_name] = target
            return int(round(target))

        step = max(1.0, target * dt / (smooth_ms / 1000.0))
        current = min(target, current + step)
        self.trigger_smoothed_force[trigger_name] = current
        return int(round(current))

    def brake_pressure_force(self, raw: dict[str, float | int | bool]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_PRESSURE)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_BRAKE_PRESSURE] = False
            return 0
        brake_percent = max(0.0, min(100.0, float(raw["brake"]) / 255.0 * 100.0))
        start = self.clamp_int(controls_state["start_percent"].get(), 0, 100)
        end = self.clamp_int(controls_state["max_percent"].get(), 0, 100)
        if end <= start:
            end = min(100, start + 1)
        active, ramp_start = self.brake_trigger_hysteresis(TRIGGER_BRAKE_PRESSURE, brake_percent, start)
        if not active:
            return 0
        mix = max(0.0, min(1.0, (brake_percent - ramp_start) / max(1.0, end - ramp_start)))
        max_force = 255.0 * self.clamp_int(controls_state["force_percent"].get(), 0, 100) / 100.0
        return max(0, min(255, int(round(max_force * mix))))

    def throttle_pressure_force(self, raw: dict[str, float | int | bool]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_THROTTLE_PRESSURE)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_THROTTLE_PRESSURE] = False
            return 0
        throttle_percent = max(0.0, min(100.0, float(raw["accel"]) / 255.0 * 100.0))
        start = self.clamp_int(controls_state["start_percent"].get(), 0, 100)
        end = self.clamp_int(controls_state["max_percent"].get(), 0, 100)
        if end <= start:
            end = min(100, start + 1)
        active, ramp_start = self.brake_trigger_hysteresis(TRIGGER_THROTTLE_PRESSURE, throttle_percent, start)
        if not active:
            return 0
        mix = max(0.0, min(1.0, (throttle_percent - ramp_start) / max(1.0, end - ramp_start)))
        max_force = 255.0 * self.clamp_int(controls_state["force_percent"].get(), 0, 100) / 100.0
        return max(0, min(255, int(round(max_force * mix))))

    def throttle_traction_limit_force(self, raw: dict[str, float | int | bool]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_THROTTLE_TRACTION_LIMIT)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_THROTTLE_TRACTION_LIMIT] = False
            self.throttle_traction_wall_start_percent = -1.0
            self.throttle_traction_wall_smoothed = -1.0
            self.throttle_traction_debug = "thr off"
            return 0

        throttle_percent = max(0.0, min(100.0, float(raw["accel"]) / 255.0 * 100.0))
        speed_kmh = max(0.0, float(raw["speed_kmh"]))
        if throttle_percent < 3.0 or speed_kmh < 4.0:
            self.trigger_brake_active[TRIGGER_THROTTLE_TRACTION_LIMIT] = False
            self.throttle_traction_wall_start_percent = -1.0
            self.throttle_traction_debug = "thr idle"
            return 0
        if self.drift_relief_trigger_suppression_active():
            self.clear_drift_relief_r2_outputs()
            return 0

        base_wall = 100
        min_wall = self.clamp_int(controls_state["max_percent"].get(), 20, 95)
        min_wall = min(min_wall, max(20, base_wall - 1))
        prediction_strength = self.clamp_int(controls_state["wall_percent"].get(), 0, 60)
        slip_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
        slip_end_threshold = self.clamp_float(controls_state["slip_end_threshold"].get() / 10.0, 0.1, 5.0)
        slip_end_threshold = max(slip_threshold + 0.1, slip_end_threshold)

        driven_slip, driven_combined = self.throttle_driven_slip_values(raw)
        throttle_gate = self.smoothstep(12.0, 60.0, throttle_percent)
        speed_gate = 1.0 - self.smoothstep(210.0, 270.0, speed_kmh)
        ratio_start = max(0.25, slip_threshold * 0.55)
        ratio_risk = self.smoothstep(ratio_start, slip_threshold, driven_slip)
        combined_risk = self.smoothstep(0.35, max(0.75, slip_threshold * 0.85), driven_combined) * 0.55
        risk = max(ratio_risk, combined_risk) * throttle_gate * speed_gate
        risk = max(0.0, min(1.0, risk))

        wall_target = max(float(min_wall), min(100.0, float(base_wall) - prediction_strength * risk))
        previous_wall = float(getattr(self, "throttle_traction_wall_smoothed", -1.0))
        if previous_wall < 0.0:
            wall_position = wall_target
        else:
            alpha = 0.30 if wall_target < previous_wall else 0.12
            wall_position = previous_wall + (wall_target - previous_wall) * alpha
        wall_position = max(float(min_wall), min(100.0, wall_position))
        self.throttle_traction_wall_smoothed = wall_position
        self.throttle_traction_wall_start_percent = wall_position

        max_force = 255.0 * self.clamp_int(controls_state["force_percent"].get(), 0, 100) / 100.0
        if driven_slip >= slip_end_threshold:
            drop_force = 255.0 * self.clamp_int(controls_state["slip_drop_low_percent"].get(), 0, 100) / 100.0
            self.throttle_traction_debug = (
                f"thr offEnd throttle={throttle_percent:4.1f}% "
                f"wall={wall_position:4.1f}% slip={driven_slip:.2f}/{driven_combined:.2f} "
                f"end={slip_end_threshold:.1f} force={drop_force:.0f}"
            )
            return max(0, min(255, int(round(drop_force))))
        force_gate = max(0.18, risk) if throttle_percent >= max(8.0, wall_position - 18.0) else risk
        force = max_force * max(0.0, min(1.0, force_gate))
        pulse_style = normalize_slip_pulse_style(
            controls_state["slip_pulse_style"].get(),
            TRIGGER_THROTTLE_TRACTION_LIMIT,
        )
        pulse_enabled = bool(controls_state["slip_pulse_enabled"].get())
        slip_level = driven_slip / max(0.1, slip_threshold)
        pulse_start_level = self.clamp_int(controls_state["slip_pulse_start_percent"].get(), 10, 99) / 100.0
        pulse_end_level = self.clamp_int(controls_state["slip_pulse_end_percent"].get(), 100, 150) / 100.0
        pulse_active = pulse_enabled and pulse_start_level <= slip_level < pulse_end_level
        if pulse_active and pulse_style == SLIP_PULSE_STYLE_PULSE_KICK:
            low_percent = self.clamp_int(controls_state["slip_low_percent"].get(), 0, 100)
            high_percent = self.clamp_int(controls_state["slip_pulse_high_percent"].get(), 0, 100)
            low_force = 255.0 * low_percent / 100.0
            high_force = 255.0 * high_percent / 100.0
            rate = self.clamp_int(controls_state["slip_pulse_rate"].get(), 1, SLIP_PULSE_RATE_MAX)
            phase = (time.perf_counter() * rate) % 1.0
            force = high_force if phase < 0.5 else low_force
        elif pulse_active and pulse_style == SLIP_PULSE_STYLE_RUMBLE:
            self.throttle_server_pulse = self.clamp_int(controls_state["slip_rumble_amplitude"].get(), 1, 255)
            self.throttle_server_pulse_rate = self.clamp_int(controls_state["slip_rumble_rate"].get(), 1, 255)
        elif pulse_active and pulse_style == SLIP_PULSE_STYLE_WAVE:
            self.throttle_server_vibration_amplitude = self.clamp_int(
                controls_state["slip_dsx_vibration_amplitude"].get(),
                1,
                8,
            )
            self.throttle_server_vibration_frequency = self.clamp_int(
                controls_state["slip_dsx_vibration_frequency"].get(),
                1,
                40,
            )
            self.throttle_server_vibration_start_zone = self.throttle_vibration_start_zone(
                wall_position,
                self.clamp_int(controls_state["slip_dsx_vibration_margin"].get(), 0, 9),
            )
        self.throttle_traction_debug = (
            f"thr throttle={throttle_percent:4.1f}% risk={risk:.3f} "
            f"wall={wall_position:4.1f}% slip={driven_slip:.2f}/{driven_combined:.2f} "
            f"th={slip_threshold:.1f} end={slip_end_threshold:.1f} "
            f"pulse={pulse_style if pulse_active else 'off'}"
        )
        return max(0, min(255, int(round(force))))

    def throttle_vibration_start_zone(self, wall_position: float, margin: int) -> int:
        wall = max(0.0, min(100.0, float(wall_position)))
        zone = int(wall // 10.0)
        zone = max(0, min(9, zone))
        return max(0, min(9, zone - max(0, min(9, int(margin)))))

    def throttle_driven_slip_values(self, raw: dict[str, float | int | bool]) -> tuple[float, float]:
        drive_train = int(raw.get("drive_train", 1))
        if drive_train == 0:
            ratio_keys = ("tire_slip_ratio_fl", "tire_slip_ratio_fr")
            combined_keys = ("tire_combined_slip_fl", "tire_combined_slip_fr")
        else:
            ratio_keys = ("tire_slip_ratio_rl", "tire_slip_ratio_rr")
            combined_keys = ("tire_combined_slip_rl", "tire_combined_slip_rr")
        driven_ratio = max(0.0, *(max(0.0, float(raw.get(key, 0.0))) for key in ratio_keys))
        driven_combined = max(0.0, *(abs(float(raw.get(key, 0.0))) for key in combined_keys))
        return driven_ratio, driven_combined

    def rpm_rev_limit_force(self, now: float, raw: dict[str, float | int | bool]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_RPM_REV_LIMIT)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            return 0
        max_rpm = max(1.0, float(raw["max_rpm"]))
        rpm_ratio = max(0.0, min(1.25, float(raw["rpm"]) / max_rpm))
        throttle_gate = self.smoothstep(0.08, 0.30, max(0.0, min(1.0, float(raw["accel"]) / 255.0)))
        start_ratio = self.clamp_int(controls_state["start_percent"].get(), 80, 99) / 100.0
        limit_gate = self.smoothstep(start_ratio, 1.00, rpm_ratio) * throttle_gate
        if limit_gate <= 0:
            return 0
        pulse_style = normalize_slip_pulse_style(
            controls_state["slip_pulse_style"].get(),
            TRIGGER_RPM_REV_LIMIT,
        )
        if pulse_style == SLIP_PULSE_STYLE_RUMBLE:
            amplitude = self.clamp_int(controls_state["slip_rumble_amplitude"].get(), 1, 255)
            rate = self.clamp_int(controls_state["slip_rumble_rate"].get(), 1, 255)
            self.throttle_server_pulse = max(1, min(255, int(round(amplitude * limit_gate))))
            self.throttle_server_pulse_rate = rate
            return max(0, min(255, int(round(amplitude * limit_gate))))

        amplitude = self.clamp_int(controls_state["slip_dsx_vibration_amplitude"].get(), 1, 8)
        frequency = self.clamp_int(controls_state["slip_dsx_vibration_frequency"].get(), 1, 40)
        start_zone = self.clamp_int(controls_state["slip_dsx_vibration_margin"].get(), 0, 9)
        self.throttle_server_vibration_amplitude = max(1, min(8, int(round(amplitude * limit_gate))))
        self.throttle_server_vibration_frequency = frequency
        self.throttle_server_vibration_start_zone = start_zone
        return max(0, min(255, int(round(255.0 * amplitude / 8.0 * limit_gate))))

    def brake_resistance_force(self, now: float, raw: dict[str, float | int | bool], values: dict[str, float]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE] = False
            self.reset_brake_resistance_release_hold()
            return 0

        brake_percent = max(0.0, min(100.0, float(raw["brake"]) / 255.0 * 100.0))
        speed_kmh = max(0.0, float(raw["speed_kmh"]))
        slip_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
        slip_release_gate = brake_percent >= 10.0 and speed_kmh >= BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH

        max_force = 255.0 * self.clamp_int(controls_state["force_percent"].get(), 0, 100) / 100.0
        slip_level = self.brake_resistance_slip_off_level(raw, slip_threshold) if slip_release_gate else 0.0
        force, _mode = self.apply_brake_slip_response(
            controls_state,
            max_force,
            slip_level,
            now,
            TRIGGER_BRAKE_RESISTANCE,
            self.clamp_int(controls_state["start_percent"].get(), 0, 100),
        )
        return force

    def update_brake_resistance_release_hold(self, controls_state: dict[str, tk.Variable], force: int) -> None:
        sustain_percent = self.clamp_int(controls_state["sustain_percent"].get(), 0, 100)
        if sustain_percent <= 0 or force <= 0:
            self.brake_resistance_release_hold_force = 0.0
            return
        sustain_force = 255.0 * sustain_percent / 100.0
        self.brake_resistance_release_hold_force = min(float(force), sustain_force)

    def reset_brake_resistance_release_hold(self) -> None:
        self.brake_resistance_release_hold_force = 0.0

    def update_brake_dynamic_release_hold(self, force: float) -> None:
        if force <= 0.5:
            return
        hold_force = max(4.0, min(28.0, float(force) * 0.18))
        self.brake_dynamic_release_hold_force = hold_force

    def reset_brake_dynamic_release_hold(self) -> None:
        self.brake_dynamic_release_hold_force = 0.0

    def brake_resistance_predictive_force(self, now: float, raw: dict[str, float | int | bool], values: dict[str, float]) -> int:
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE_PREDICTIVE)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE_PREDICTIVE] = False
            self.brake_dynamic_wall_start_percent = -1.0
            self.brake_predictive_trigger_mode_active = False
            self.brake_predictive_trigger_end_percent = -1.0
            self.brake_predictive_wall_smoothed = -1.0
            self.reset_brake_dynamic_server_pulse()
            self.brake_predictive_debug = "pred off"
            return 0

        if int(raw.get("handbrake", 0)) > 0:
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE_PREDICTIVE] = False
            self.brake_dynamic_wall_start_percent = -1.0
            self.brake_predictive_trigger_mode_active = False
            self.brake_predictive_trigger_end_percent = -1.0
            self.brake_predictive_wall_smoothed = -1.0
            self.reset_brake_dynamic_pulse_zone()
            self.reset_brake_dynamic_server_pulse()
            self.brake_predictive_debug = "pred handbrake"
            return 0

        brake_percent = max(0.0, min(100.0, float(raw["brake"]) / 255.0 * 100.0))
        speed_kmh = max(0.0, float(raw["speed_kmh"]))
        base_wall = self.clamp_int(controls_state["start_percent"].get(), 40, 100)
        min_wall = self.clamp_int(controls_state["max_percent"].get(), 30, 95)
        min_wall = min(min_wall, max(30, base_wall - 1))
        prediction_strength = self.clamp_int(controls_state["wall_percent"].get(), 0, 40)
        risk = self.brake_predictive_risk(raw)

        moving_wall_target = max(float(min_wall), min(100.0, float(base_wall) - prediction_strength * risk))
        previous_wall = float(getattr(self, "brake_predictive_wall_smoothed", -1.0))
        if previous_wall < 0.0:
            moving_wall = moving_wall_target
        else:
            alpha = 0.24 if moving_wall_target < previous_wall else 0.10
            moving_wall = previous_wall + (moving_wall_target - previous_wall) * alpha
        moving_wall = max(float(min_wall), min(100.0, moving_wall))
        self.brake_predictive_wall_smoothed = moving_wall

        wall_position = moving_wall

        slip_off_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
        slip_level = (
            self.brake_resistance_slip_off_level(raw, slip_off_threshold)
            if speed_kmh >= BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH and brake_percent >= max(3.0, wall_position - 2.0)
            else 0.0
        )

        force_percent = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
        base_force = 255.0 * force_percent / 100.0
        self.reset_brake_dynamic_server_pulse()
        response_force, response_mode = self.apply_brake_slip_response(
            controls_state,
            base_force,
            slip_level,
            now,
            TRIGGER_BRAKE_RESISTANCE_PREDICTIVE,
            wall_position,
        )
        self.brake_dynamic_wall_start_percent = wall_position
        self.brake_predictive_trigger_mode_active = False
        self.brake_predictive_trigger_end_percent = -1.0
        slip_ratio, slip_combined = self.brake_slip_off_values(raw)

        self.brake_predictive_debug = (
            f"pred brake={brake_percent:4.1f}% risk={risk:.3f} "
            f"target={moving_wall_target:4.1f}% wall={wall_position:4.1f}% "
            f"raw={self.wall_position_percent_to_start_byte(wall_position) / 255.0 * 100.0:4.1f}% "
            f"slipOff={slip_ratio:.2f}/{slip_combined:.2f} th={slip_off_threshold:.1f} "
            f"slipLevel={slip_level:.2f} mode={response_mode} force={int(round(response_force))}"
        )
        return response_force

    def brake_predictive_risk(self, raw: dict[str, float | int | bool]) -> float:
        limit_level = self.brake_dynamic_limit_level(raw)
        brake_percent = max(0.0, min(100.0, float(raw["brake"]) / 255.0 * 100.0))
        speed_kmh = max(0.0, float(raw["speed_kmh"]))
        brake_gate = self.smoothstep(4.0, 42.0, brake_percent)
        front_angle = (
            abs(float(raw["tire_slip_angle_fl"]))
            + abs(float(raw["tire_slip_angle_fr"]))
        ) * 0.5
        rear_angle = (
            abs(float(raw["tire_slip_angle_rl"]))
            + abs(float(raw["tire_slip_angle_rr"]))
        ) * 0.5
        body_slip = abs(math.atan2(float(raw["velocity_x"]), max(abs(float(raw["velocity_z"])), 0.1)))
        yaw_rate = abs(float(raw["angular_velocity_y"]))
        decel_g = max(0.0, -float(raw["accel_z"]) / 9.80665)

        front_angle_risk = self.smoothstep(0.35, 1.20, front_angle)
        decel_risk = self.smoothstep(0.18, 0.85, decel_g)
        steering_load = self.smoothstep(30.0, 110.0, abs(float(raw["steer"])))
        instability_cut = (
            (1.0 - self.smoothstep(1.75, 3.10, rear_angle))
            * (1.0 - self.smoothstep(0.85, 1.45, body_slip))
            * (1.0 - self.smoothstep(3.2, 5.2, yaw_rate))
        )
        risk = max(limit_level, front_angle_risk * max(brake_gate, steering_load * 0.55), decel_risk * brake_gate * 0.65)
        return max(0.0, min(1.0, risk * max(0.20, instability_cut)))

    def brake_resistance_dynamic_force(self, now: float, raw: dict[str, float | int | bool], values: dict[str, float]) -> int:
        self.trigger_smooth_bypass[TRIGGER_BRAKE_RESISTANCE_DYNAMIC] = True
        controls_state = self.trigger_controls.get(TRIGGER_BRAKE_RESISTANCE_DYNAMIC)
        if not controls_state or not controls_state["enabled"].get() or not bool(raw["on"]):
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE_DYNAMIC] = False
            self.brake_dynamic_wall_start_percent = -1.0
            self.brake_dynamic_base_force_smoothed = 0.0
            self.brake_dynamic_base_force_last_time = now
            self.reset_brake_dynamic_release_hold()
            self.reset_brake_dynamic_pulse_zone()
            self.reset_brake_dynamic_pulse_gate()
            self.brake_predictive_debug = "dyn off"
            return 0

        if int(raw.get("handbrake", 0)) > 0:
            self.trigger_brake_active[TRIGGER_BRAKE_RESISTANCE_DYNAMIC] = False
            self.brake_dynamic_wall_start_percent = -1.0
            self.brake_dynamic_base_force_smoothed = 0.0
            self.brake_dynamic_base_force_last_time = now
            self.reset_brake_dynamic_release_hold()
            self.reset_brake_dynamic_pulse_zone()
            self.reset_brake_dynamic_pulse_gate()
            self.brake_predictive_debug = "dyn handbrake"
            return 0

        brake_percent = max(0.0, min(100.0, float(raw["brake"]) / 255.0 * 100.0))
        base_wall = self.clamp_int(controls_state["start_percent"].get(), 40, 100)
        min_wall = self.clamp_int(controls_state["max_percent"].get(), 30, 95)
        min_wall = min(min_wall, max(30, base_wall - 1))
        prediction_strength = self.clamp_int(controls_state["wall_percent"].get(), 0, 40)
        risk = self.brake_predictive_risk(raw)

        wall_position = max(float(min_wall), min(100.0, float(base_wall) - prediction_strength * risk))
        self.brake_dynamic_wall_start_percent = wall_position

        slip_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
        slip_response_level = (
            self.brake_resistance_slip_off_level(raw, slip_threshold)
            if speed_kmh >= BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH and brake_percent >= max(3.0, wall_position - 2.0)
            else 0.0
        )

        pulse_percent = self.normalized_dynamic_pulse_strength(self.clamp_int(controls_state["pulse_strength"].get(), 0, 100))
        force_percent = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
        base_force = 255.0 * force_percent / 100.0

        pulse_timing_offset = self.clamp_int(controls_state["pulse_timing_offset"].get(), -5, 5)
        pulse_gate = self.smoothstep(0.42, 0.86, risk)
        min_pulse_position = self.clamp_int(controls_state["pulse_start_percent"].get(), 0, 100)
        pulse_position = max(float(min_pulse_position), wall_position + float(pulse_timing_offset))
        pulse_touch_end = min(100.0, pulse_position + 5.0)
        brake_touch_gate = self.smoothstep(pulse_position, pulse_touch_end, brake_percent)
        effective_pulse_gate = pulse_gate * brake_touch_gate

        pulse_force = 0.0
        if effective_pulse_gate > 0.0 and pulse_percent > 0:
            pulse_rate = self.clamp_int(controls_state["pulse_rate"].get(), 1, 255)
            pulse_shape = self.software_trigger_pulse_shape(now, pulse_rate)
            pulse_force = 255.0 * pulse_percent / 100.0 * effective_pulse_gate * pulse_shape

        haptic_strength = self.clamp_int(controls_state["haptic_pulse_strength"].get(), 0, 10)
        haptic_hz = self.clamp_int(controls_state["haptic_pulse_hz"].get(), 20, 160)
        haptic_start_margin = self.clamp_int(controls_state["haptic_pulse_start_margin"].get(), -20, 25)
        haptic_end_margin = self.clamp_int(controls_state["haptic_pulse_end_margin"].get(), -20, 25)
        if haptic_start_margin < haptic_end_margin:
            haptic_start_margin = haptic_end_margin
        slip_reference = max(wall_position + 1.0, min(100.0, float(base_wall)))
        haptic_position = max(wall_position + 1.0, slip_reference - float(haptic_start_margin))
        haptic_touch_end = max(haptic_position + 0.5, slip_reference - float(haptic_end_margin))
        haptic_touch_end = min(100.0, haptic_touch_end)
        haptic_attack_end = min(haptic_touch_end, haptic_position + 1.5)
        haptic_release_start = max(haptic_position, haptic_touch_end - 1.5)
        haptic_enter_gate = self.smoothstep(haptic_position, haptic_attack_end, brake_percent)
        haptic_exit_gate = 1.0 - self.smoothstep(haptic_release_start, haptic_touch_end, brake_percent)
        haptic_zone_gate = max(0.0, min(1.0, haptic_enter_gate * haptic_exit_gate))
        haptic_level = pulse_gate * haptic_zone_gate if haptic_strength > 0 else 0.0
        self.send_brake_pulse_haptic_state(haptic_level, haptic_hz, haptic_strength)

        self.reset_brake_dynamic_server_pulse()
        force = max(0.0, min(255.0, base_force + pulse_force))
        force, response_mode = self.apply_brake_slip_response(
            controls_state,
            force,
            slip_response_level,
            now,
            TRIGGER_BRAKE_RESISTANCE_DYNAMIC,
            wall_position,
        )
        slip_ratio, slip_combined = self.brake_slip_off_values(raw)
        self.brake_predictive_debug = (
            f"dyn brake={brake_percent:4.1f}% risk={risk:.3f} "
            f"gate={pulse_gate:.3f} touch={brake_touch_gate:.3f}({pulse_position:.0f}-{pulse_touch_end:.0f}% off={pulse_timing_offset:+d}) "
            f"wall={wall_position:4.1f}% raw={self.wall_position_percent_to_start_byte(wall_position) / 255.0 * 100.0:4.1f}% "
            f"slipOff={slip_ratio:.2f}/{slip_combined:.2f} th={slip_threshold:.1f} "
            f"slipLevel={slip_response_level:.2f} mode={response_mode} "
            f"softPulse={pulse_force:3.0f} "
            f"hapt={haptic_level:.2f}@{haptic_hz}Hz({haptic_position:.0f}-{haptic_touch_end:.0f}%) "
            f"rate={self.clamp_int(controls_state['pulse_rate'].get(), 1, 255)}"
        )
        return max(0, min(255, int(round(force))))

    def send_brake_pulse_haptic_state(self, left_level: float, hz: int, volume: int) -> None:
        left = max(0.0, min(1.0, float(left_level)))
        payload = (
            "BRAKE_PULSE_HAPTIC|"
            f"left={left}|"
            f"hz={self.clamp_int(hz, 20, 160)}|"
            f"volume={self.clamp_int(volume, 0, 10)}"
        )
        self.send_haptic_event(payload, count=False)

    def brake_resistance_dynamic_asphalt_force(
        self,
        now: float,
        raw: dict[str, float | int | bool],
        values: dict[str, float],
        controls_state: dict[str, tk.Variable],
        brake_percent: float,
        limit_level: float,
    ) -> int:
        speed_bucket = self.brake_dynamic_speed_bucket(float(raw["speed_kmh"]))
        cache = self.brake_dynamic_cache[speed_bucket]
        early_margin = self.clamp_int(controls_state["start_percent"].get(), 0, 40)
        wall_position = max(5.0, min(95.0, float(cache["wall"]) - early_margin))
        self.brake_dynamic_wall_start_percent = wall_position

        if brake_percent >= 1.0:
            if not self.brake_dynamic_event_active:
                self.brake_dynamic_begin_event(speed_bucket, wall_position)
            self.brake_dynamic_event_peak_brake = max(self.brake_dynamic_event_peak_brake, brake_percent)
            self.brake_dynamic_event_peak_limit = max(self.brake_dynamic_event_peak_limit, limit_level)

            learning_slipping = (
                brake_percent >= BRAKE_DYNAMIC_MIN_LEARNING_BRAKE_PERCENT
                and self.brake_dynamic_learning_allowed(raw)
                and self.brake_resistance_slipping(values, BRAKE_DYNAMIC_LEARNING_SLIP_THRESHOLD)
            )
            if self.brake_dynamic_event_first_slip_brake is None and learning_slipping:
                self.brake_dynamic_event_first_slip_brake = brake_percent

            slip_off_threshold = self.clamp_float(controls_state["slip_threshold"].get() / 10.0, 0.1, 5.0)
            slip_off_slipping = self.brake_resistance_slip_off_active(raw, slip_off_threshold)
            if controls_state["slip_off"].get() and slip_off_slipping and brake_percent >= max(3.0, wall_position - 2.0):
                self.brake_dynamic_event_slip_off_latched = True
        elif self.brake_dynamic_event_active:
            self.brake_dynamic_finish_event()

        if self.brake_dynamic_event_slip_off_latched:
            self.brake_dynamic_wall_start_percent = -1.0
            self.reset_brake_dynamic_pulse_zone()
            self.reset_brake_dynamic_server_pulse()
            return 0

        pulse_percent = self.normalized_dynamic_pulse_strength(self.clamp_int(controls_state["pulse_strength"].get(), 0, 100))
        force_percent = self.clamp_int(controls_state["force_percent"].get(), 0, 100)
        base_force = 255.0 * force_percent / 100.0

        max_gate = self.brake_dynamic_pulse_zone_level(limit_level)
        pulse_margin = self.clamp_int(controls_state["pulse_offset"].get(), 0, 40)
        pulse_start = max(1.0, min(95.0, float(cache["wall"]) - pulse_margin))
        if max_gate > 0 and brake_percent >= pulse_start:
            pulse_strength = 255.0 * pulse_percent / 100.0
            pulse_rate = self.clamp_int(controls_state["pulse_rate"].get(), 1, 255)
            pulse_target = max(0.0, min(255.0, pulse_strength * max_gate))
            self.brake_dynamic_server_pulse = self.smooth_brake_dynamic_server_pulse(pulse_target, controls_state, now)
            self.brake_dynamic_server_pulse_rate = pulse_rate
        else:
            self.reset_brake_dynamic_server_pulse()

        return max(0, min(255, int(round(base_force))))

    @staticmethod
    def default_brake_dynamic_cache() -> list[dict[str, float | int]]:
        return [
            {"wall": 80.0, "confidence": 0.0, "samples": 0},
            {"wall": 76.0, "confidence": 0.0, "samples": 0},
            {"wall": 70.0, "confidence": 0.0, "samples": 0},
            {"wall": 64.0, "confidence": 0.0, "samples": 0},
        ]

    def handle_car_ordinal_change(self, raw: dict[str, float | int | bool]) -> None:
        car_ordinal = int(raw.get("car_ordinal", 0))
        if car_ordinal <= 0:
            return

        previous = int(getattr(self, "last_car_ordinal", 0))
        if previous <= 0:
            self.last_car_ordinal = car_ordinal
            return
        if car_ordinal == previous:
            return

        self.last_car_ordinal = car_ordinal
        self.rpm_hud_needle_angles.clear()
        self.rpm_hud_display_rpm = None
        self.rpm_hud_zero_dropouts = 0
        self.engine_hud_torque_needle_angles.clear()
        self.engine_hud_vacuum_needle_angles.clear()
        self.reset_brake_dynamic_learning()

    def reset_brake_dynamic_learning(self) -> None:
        self.brake_dynamic_cache = self.default_brake_dynamic_cache()
        self.brake_dynamic_event_active = False
        self.brake_dynamic_event_speed_bucket = 0
        self.brake_dynamic_event_wall = 80.0
        self.brake_dynamic_event_peak_brake = 0.0
        self.brake_dynamic_event_peak_limit = 0.0
        self.brake_dynamic_event_first_slip_brake = None
        self.brake_dynamic_event_slip_off_latched = False
        self.brake_dynamic_wall_start_percent = -1.0
        self.brake_dynamic_base_force_smoothed = 0.0
        self.brake_dynamic_base_force_last_time = 0.0
        self.reset_brake_dynamic_release_hold()
        self.reset_brake_dynamic_pulse_zone()
        self.reset_brake_dynamic_server_pulse()
        self.reset_brake_dynamic_pulse_gate()
        self.update_brake_dynamic_cache_text()

    def brake_dynamic_learning_allowed(self, raw: dict[str, float | int | bool]) -> bool:
        if int(raw.get("handbrake", 0)) > 0:
            return False
        front_angle = (
            abs(float(raw["tire_slip_angle_fl"]))
            + abs(float(raw["tire_slip_angle_fr"]))
        ) * 0.5
        rear_angle = (
            abs(float(raw["tire_slip_angle_rl"]))
            + abs(float(raw["tire_slip_angle_rr"]))
        ) * 0.5
        body_slip = abs(math.atan2(float(raw["velocity_x"]), max(abs(float(raw["velocity_z"])), 0.1)))
        yaw_rate = abs(float(raw["angular_velocity_y"]))
        return front_angle < 1.75 and rear_angle < 1.55 and body_slip < 0.85 and yaw_rate < 3.2

    def brake_dynamic_begin_event(self, speed_bucket: int, wall_position: float) -> None:
        self.brake_dynamic_event_active = True
        self.brake_dynamic_event_speed_bucket = speed_bucket
        self.brake_dynamic_event_wall = wall_position
        self.brake_dynamic_event_peak_brake = 0.0
        self.brake_dynamic_event_peak_limit = 0.0
        self.brake_dynamic_event_first_slip_brake = None
        self.brake_dynamic_event_slip_off_latched = False

    def brake_dynamic_finish_event(self) -> None:
        bucket = self.brake_dynamic_event_speed_bucket
        cache = self.brake_dynamic_cache[bucket]
        wall = float(cache["wall"])
        peak_brake = float(self.brake_dynamic_event_peak_brake)
        peak_limit = float(self.brake_dynamic_event_peak_limit)
        first_slip = self.brake_dynamic_event_first_slip_brake

        target = wall
        if first_slip is not None:
            target = min(wall - 1.5, max(20.0, first_slip - BRAKE_DYNAMIC_LEARNING_WALL_MARGIN))
        elif peak_brake >= wall + 8.0 and peak_limit < 0.55:
            target = min(95.0, wall + 1.0)
        elif peak_limit >= 0.72 and peak_brake > 5.0:
            target = max(20.0, min(wall, peak_brake - 5.0))

        cache["wall"] = max(20.0, min(95.0, wall + (target - wall) * 0.30))
        cache["samples"] = int(cache["samples"]) + 1
        cache["confidence"] = min(1.0, float(cache["confidence"]) + 0.08)

        self.brake_dynamic_event_active = False
        self.brake_dynamic_event_peak_brake = 0.0
        self.brake_dynamic_event_peak_limit = 0.0
        self.brake_dynamic_event_first_slip_brake = None
        self.brake_dynamic_event_slip_off_latched = False

    @staticmethod
    def brake_dynamic_speed_bucket(speed_kmh: float) -> int:
        speed = max(0.0, float(speed_kmh))
        if speed < 60.0:
            return 0
        if speed < 120.0:
            return 1
        if speed < 200.0:
            return 2
        return 3

    def reset_brake_dynamic_pulse_zone(self) -> None:
        self.brake_dynamic_pulse_zone_active = False
        self.brake_dynamic_pulse_level_value = 0.0

    @staticmethod
    def software_trigger_pulse_shape(now: float, pulse_rate: int) -> float:
        rate = max(1.0, min(255.0, float(pulse_rate)))
        phase = (max(0.0, float(now)) * rate) % 1.0
        return 1.0 if phase < 0.50 else 0.0

    def reset_brake_dynamic_server_pulse(self) -> None:
        self.brake_dynamic_server_pulse = 0
        self.brake_dynamic_server_pulse_rate = 0
        self.brake_server_vibration_amplitude = 0
        self.brake_server_vibration_frequency = 0
        self.brake_server_vibration_start_zone = 0
        self.brake_dynamic_server_pulse_smoothed = 0.0
        self.brake_dynamic_server_pulse_last_time = 0.0

    def reset_throttle_server_pulse(self) -> None:
        self.throttle_server_pulse = 0
        self.throttle_server_pulse_rate = 0
        self.throttle_server_vibration_amplitude = 0
        self.throttle_server_vibration_frequency = 0
        self.throttle_server_vibration_start_zone = 0

    def clear_drift_relief_r2_outputs(self) -> None:
        for trigger_name in (
            TRIGGER_THROTTLE_PRESSURE,
            TRIGGER_THROTTLE_TRACTION_LIMIT,
            TRIGGER_RPM_REV_LIMIT,
        ):
            self.trigger_brake_active[trigger_name] = False
            self.trigger_smoothed_force[trigger_name] = 0.0
        self.throttle_traction_wall_start_percent = -1.0
        self.throttle_traction_wall_smoothed = -1.0
        self.reset_throttle_server_pulse()
        self.throttle_traction_debug = f"thr drift relief R2 off score={self.drift_mode_score:.2f}"

    def smooth_brake_dynamic_server_pulse(self, target: float, controls_state: dict[str, tk.Variable], now: float) -> int:
        target = max(0.0, min(255.0, float(target)))
        previous = max(0.0, min(255.0, float(getattr(self, "brake_dynamic_server_pulse_smoothed", 0.0))))
        last_time = float(getattr(self, "brake_dynamic_server_pulse_last_time", 0.0))
        dt = 0.0 if last_time <= 0.0 else max(0.0, min(0.1, now - last_time))
        self.brake_dynamic_server_pulse_last_time = now

        smooth_ms = self.clamp_int(controls_state["smooth_start_ms"].get(), 0, 300)
        if target <= previous or smooth_ms <= 0 or dt <= 0.0:
            self.brake_dynamic_server_pulse_smoothed = target
            return max(0, min(255, int(round(target))))

        step = max(1.0, target * dt / (smooth_ms / 1000.0))
        smoothed = min(target, previous + step)
        self.brake_dynamic_server_pulse_smoothed = smoothed
        return max(0, min(255, int(round(smoothed))))

    def reset_brake_dynamic_pulse_gate(self) -> None:
        self.brake_dynamic_pulse_gate_active = False
        self.brake_dynamic_pulse_hold_until = 0.0

    def brake_dynamic_pulse_gate_allows(self, brake_percent: float, pulse_gate: float, now: float) -> bool:
        release_margin = 4.0
        hold_seconds = 0.12
        active = bool(getattr(self, "brake_dynamic_pulse_gate_active", False))
        if active:
            if brake_percent >= pulse_gate - release_margin:
                self.brake_dynamic_pulse_hold_until = now + hold_seconds
                return True
            if now < float(getattr(self, "brake_dynamic_pulse_hold_until", 0.0)):
                return True
            self.brake_dynamic_pulse_gate_active = False
            return False

        if brake_percent >= pulse_gate:
            self.brake_dynamic_pulse_gate_active = True
            self.brake_dynamic_pulse_hold_until = now + hold_seconds
            return True
        return False

    def brake_dynamic_pulse_zone_level(self, limit_level: float) -> float:
        raw_gate = self.smoothstep(0.72, 0.96, limit_level)

        if raw_gate >= 0.18:
            self.brake_dynamic_pulse_zone_active = True
        elif raw_gate <= 0.05:
            self.brake_dynamic_pulse_zone_active = False

        if not self.brake_dynamic_pulse_zone_active:
            self.brake_dynamic_pulse_level_value = 0.0
            return 0.0

        self.brake_dynamic_pulse_level_value = max(0.18, raw_gate)
        return self.brake_dynamic_pulse_level_value

    def smooth_brake_dynamic_base_force(self, target: float, controls_state: dict[str, tk.Variable], now: float) -> float:
        target = max(0.0, min(255.0, float(target)))
        previous = max(0.0, min(255.0, float(getattr(self, "brake_dynamic_base_force_smoothed", 0.0))))
        last_time = float(getattr(self, "brake_dynamic_base_force_last_time", 0.0))
        dt = 0.0 if last_time <= 0.0 else max(0.0, min(0.1, now - last_time))
        self.brake_dynamic_base_force_last_time = now

        smooth_ms = self.clamp_int(controls_state["smooth_start_ms"].get(), 0, 300)
        if smooth_ms <= 0 or dt <= 0.0:
            self.brake_dynamic_base_force_smoothed = target
            return target

        time_constant = max(0.015, smooth_ms / 1000.0)
        alpha = max(0.0, min(1.0, dt / time_constant))
        if target < previous:
            alpha = max(alpha, 0.35)
        smoothed = previous + (target - previous) * alpha
        self.brake_dynamic_base_force_smoothed = max(0.0, min(255.0, smoothed))
        return self.brake_dynamic_base_force_smoothed

    def brake_dynamic_pulse_gate(self, controls_state: dict[str, tk.Variable], limit_level: float) -> float:
        base = float(self.clamp_int(controls_state["wall_percent"].get(), 0, 100))
        gate_range = float(self.clamp_int(controls_state["gate_range"].get(), 0, 30))
        if gate_range <= 0:
            self.brake_dynamic_gate_smoothed = base
            return base

        limit = max(0.0, min(1.0, float(limit_level)))
        offset = (0.5 - limit) * 2.0 * gate_range
        target = max(base - gate_range, min(base + gate_range, base + offset))
        previous = float(getattr(self, "brake_dynamic_gate_smoothed", target))
        smoothed = previous + (target - previous) * 0.18
        self.brake_dynamic_gate_smoothed = max(0.0, min(100.0, smoothed))
        return self.brake_dynamic_gate_smoothed

    def brake_dynamic_limit_level(self, raw: dict[str, float | int | bool]) -> float:
        front_ratio = (
            abs(float(raw["tire_slip_ratio_fl"]))
            + abs(float(raw["tire_slip_ratio_fr"]))
        ) * 0.5
        front_combined = (
            abs(float(raw["tire_combined_slip_fl"]))
            + abs(float(raw["tire_combined_slip_fr"]))
        ) * 0.5
        ratio_level = self.smoothstep(0.06, 0.34, front_ratio)
        combined_level = self.smoothstep(0.18, 0.74, front_combined) * 0.85
        decel_g = max(0.0, -float(raw["accel_z"]) / 9.80665)
        decel_gate = self.smoothstep(0.03, 0.55, decel_g)
        speed_gate = self.smoothstep(8.0, 20.0, max(0.0, float(raw["speed_kmh"])))
        return max(0.0, min(1.0, max(ratio_level, combined_level) * max(decel_gate, 0.35) * speed_gate))

    def brake_trigger_hysteresis(self, trigger_name: str, brake_percent: float, start_percent: int) -> tuple[bool, float]:
        release_at = max(0.0, float(start_percent) - TRIGGER_RELEASE_MARGIN_PERCENT)
        active = bool(self.trigger_brake_active.get(trigger_name, False))
        if active:
            active = brake_percent >= release_at
        else:
            active = brake_percent >= float(start_percent)
        self.trigger_brake_active[trigger_name] = active
        return active, release_at

    @staticmethod
    def brake_resistance_slipping(values: dict[str, float], threshold: float) -> bool:
        return (
            max(0.0, float(values.get("slip_ratio_max", 0.0))) >= threshold
            or max(0.0, float(values.get("slip_combined_max", 0.0))) >= threshold * 1.25
        )

    def apply_brake_slip_response(
        self,
        controls_state: dict[str, tk.Variable],
        base_force: float,
        slip_level: float,
        now: float,
        trigger_name: str,
        wall_position: float,
    ) -> tuple[int, str]:
        base = max(0.0, min(255.0, float(base_force)))
        pulse_enabled = bool(controls_state["slip_pulse_enabled"].get())
        pulse_style = normalize_slip_pulse_style(controls_state["slip_pulse_style"].get(), trigger_name)
        wave_enabled = pulse_enabled and pulse_style == SLIP_PULSE_STYLE_PULSE_KICK
        rumble_enabled = pulse_enabled and pulse_style == SLIP_PULSE_STYLE_RUMBLE
        dsx_wave_enabled = pulse_enabled and pulse_style == SLIP_PULSE_STYLE_WAVE
        mode = f"{SLIP_RESPONSE_PULSE} {pulse_style}" if pulse_enabled else SLIP_RESPONSE_DROP
        level = max(0.0, float(slip_level))
        pulse_start_level = self.clamp_int(controls_state["slip_pulse_start_percent"].get(), 10, 99) / 100.0
        drop_level = self.clamp_int(controls_state["slip_pulse_end_percent"].get(), 100, 150) / 100.0
        pulse_window_active = drop_level > pulse_start_level

        drop_low_percent = self.clamp_int(controls_state["slip_drop_low_percent"].get(), 0, 100)
        drop_low_force = 255.0 * drop_low_percent / 100.0
        low_percent = self.clamp_int(controls_state["slip_low_percent"].get(), 0, 100)
        low_force = 255.0 * low_percent / 100.0
        if level >= drop_level:
            target = drop_low_force
            return max(0, min(255, int(round(target)))), mode
        if wave_enabled and pulse_window_active and pulse_start_level <= level < drop_level:
            high_percent = self.clamp_int(controls_state["slip_pulse_high_percent"].get(), 0, 100)
            high_force = 255.0 * high_percent / 100.0
            rate = self.clamp_int(controls_state["slip_pulse_rate"].get(), 1, SLIP_PULSE_RATE_MAX)
            phase = (now * rate) % 1.0
            target = high_force if phase < 0.5 else low_force
            return max(0, min(255, int(round(target)))), mode
        if rumble_enabled and pulse_window_active and pulse_start_level <= level < drop_level:
            self.brake_dynamic_server_pulse = self.clamp_int(controls_state["slip_rumble_amplitude"].get(), 1, 255)
            self.brake_dynamic_server_pulse_rate = self.clamp_int(controls_state["slip_rumble_rate"].get(), 1, 255)
        if dsx_wave_enabled and pulse_window_active and pulse_start_level <= level < drop_level:
            self.brake_server_vibration_amplitude = self.clamp_int(
                controls_state["slip_dsx_vibration_amplitude"].get(),
                1,
                8,
            )
            self.brake_server_vibration_frequency = self.clamp_int(
                controls_state["slip_dsx_vibration_frequency"].get(),
                1,
                40,
            )
            self.brake_server_vibration_start_zone = self.throttle_vibration_start_zone(
                wall_position,
                self.clamp_int(controls_state["slip_dsx_vibration_margin"].get(), 0, 9),
            )
        return max(0, min(255, int(round(base)))), mode

    @staticmethod
    def brake_slip_off_values(raw: dict[str, float | int | bool]) -> tuple[float, float]:
        front_ratio = max(
            0.0,
            abs(float(raw.get("tire_slip_ratio_fl", 0.0))),
            abs(float(raw.get("tire_slip_ratio_fr", 0.0))),
        )
        front_combined = max(
            0.0,
            abs(float(raw.get("tire_combined_slip_fl", 0.0))),
            abs(float(raw.get("tire_combined_slip_fr", 0.0))),
        )
        return front_ratio, front_combined

    def brake_resistance_slip_off_active(self, raw: dict[str, float | int | bool], threshold: float) -> bool:
        return self.brake_resistance_slip_off_level(raw, threshold) >= 1.0

    def brake_resistance_slip_off_level(self, raw: dict[str, float | int | bool], threshold: float) -> float:
        front_ratio, front_combined = self.brake_slip_off_values(raw)
        ratio_threshold = max(0.001, float(threshold))
        combined_threshold = max(0.001, float(threshold) * 1.25)
        return max(front_ratio / ratio_threshold, front_combined / combined_threshold)

    def road_bumps_levels(self, now: float, raw: dict[str, float | int | bool]) -> tuple[float, float, float, float]:
        if not bool(raw["on"]):
            self.previous_bump_raw = None
            self.previous_bump_at = 0.0
            self.road_bump2_left_level = 0.0
            self.road_bump2_right_level = 0.0
            self.latest_road_bump_offroad2_levels = (0.0, 0.0, 90.0)
            return 0.0, 0.0, 90.0, 0.0

        previous = self.previous_bump_raw
        previous_at = self.previous_bump_at
        self.previous_bump_raw = dict(raw)
        self.previous_bump_at = now
        if previous is None or previous_at <= 0:
            self.road_bump2_left_level *= 0.70
            self.road_bump2_right_level *= 0.70
            self.latest_road_bump_offroad2_levels = (self.road_bump2_left_level, self.road_bump2_right_level, 90.0)
            return 0.0, 0.0, 90.0, 0.0

        dt = max(0.008, min(0.080, now - previous_at))
        speed = max(0.0, float(raw["speed_kmh"]))
        speed_gate = self.smoothstep(8.0, 28.0, speed) * (1.0 - self.smoothstep(230.0, 310.0, speed))

        left_step = abs(float(raw["norm_suspension_travel_fl"]) - float(previous["norm_suspension_travel_fl"]))
        right_step = abs(float(raw["norm_suspension_travel_fr"]) - float(previous["norm_suspension_travel_fr"]))
        left_rate = left_step / dt
        right_rate = right_step / dt
        accel_y_delta = abs(float(raw["accel_y"]) - float(previous["accel_y"]))
        is_asphalt = self.is_asphalt_surface(raw)
        car_class = int(raw["car_class"])
        threshold_scale = self.road_bump_low_class_threshold_scale(car_class)
        if is_asphalt:
            vertical_gate2 = self.smoothstep(0.15 * threshold_scale, 3.80, accel_y_delta)
        else:
            vertical_gate2 = self.smoothstep(0.90 * threshold_scale, 5.00, accel_y_delta)
        left_target2 = self.road_bump2_side_level(left_rate, vertical_gate2, speed_gate, is_asphalt, threshold_scale)
        right_target2 = self.road_bump2_side_level(right_rate, vertical_gate2, speed_gate, is_asphalt, threshold_scale)
        self.road_bump2_left_level = self.road_bump2_envelope(self.road_bump2_left_level, left_target2, is_asphalt)
        self.road_bump2_right_level = self.road_bump2_envelope(self.road_bump2_right_level, right_target2, is_asphalt)
        class_gain = self.road_bump_low_class_gain(car_class)
        output_left = max(0.0, min(1.0, self.road_bump2_left_level * class_gain))
        output_right = max(0.0, min(1.0, self.road_bump2_right_level * class_gain))
        severity2 = max(output_left, output_right)
        hz2 = 60.0 + (44.0 - 70.0) * max(0.0, min(1.0, severity2))
        self.latest_road_bump_offroad2_levels = (output_left, output_right, hz2)
        return self.mix_road_bump_outputs(
            ((output_left, output_right, hz2, EFFECT_ROAD_BUMPS),)
        )

    @staticmethod
    def road_bump_low_class_gain(car_class: int) -> float:
        if car_class <= 0:
            return 1.30
        if car_class == 1:
            return 1.20
        if car_class == 2:
            return 1.10
        return 1.0

    @staticmethod
    def road_bump_low_class_threshold_scale(car_class: int) -> float:
        if car_class <= 0:
            return 0.82
        if car_class == 1:
            return 0.90
        return 1.0

    def road_bump_side_level(self, suspension_rate: float, vertical_gate: float, speed_gate: float) -> float:
        suspension_gate = self.smoothstep(2.20, 8.50, suspension_rate)
        level = max(suspension_gate, vertical_gate * 0.62) * speed_gate
        return max(0.0, min(1.0, level))

    def road_bump2_side_level(
        self,
        suspension_rate: float,
        vertical_gate: float,
        speed_gate: float,
        is_asphalt: bool,
        threshold_scale: float = 1.0,
    ) -> float:
        scale = max(0.75, min(1.0, float(threshold_scale)))
        if is_asphalt:
            suspension_gate = self.smoothstep(1.50 * scale, 12.20, suspension_rate)
            level = max(suspension_gate, vertical_gate * 0.70) * speed_gate
        else:
            suspension_gate = self.smoothstep(2.20 * scale, 8.50, suspension_rate)
            level = max(suspension_gate, vertical_gate * 0.62) * speed_gate
        return max(0.0, min(1.0, level))

    def mix_road_bump_outputs(
        self,
        candidates: tuple[tuple[float, float, float, str], ...],
    ) -> tuple[float, float, float, float]:
        best_hz = 80.0
        best_power = 0.0
        mixed_left = 0.0
        mixed_right = 0.0
        for left, right, hz, effect_name in candidates:
            volume_scale = self.effect_volume(effect_name) / 10.0
            out_left = max(0.0, min(1.0, left)) * volume_scale
            out_right = max(0.0, min(1.0, right)) * volume_scale
            power = max(out_left, out_right)
            mixed_left = max(mixed_left, out_left)
            mixed_right = max(mixed_right, out_right)
            if power > best_power:
                best_power = power
                best_hz = hz
        return mixed_left, mixed_right, best_hz, (10.0 if best_power > 0.0 else 0.0)

    def asphalt_bump_targets(
        self,
        raw: dict[str, float | int | bool],
        previous: dict[str, float | int | bool],
        left_rate: float,
        right_rate: float,
        accel_y_delta: float,
    ) -> tuple[float, float]:
        speed = max(0.0, float(raw["speed_kmh"]))
        speed_gate = self.smoothstep(18.0, 45.0, speed) * (1.0 - self.smoothstep(245.0, 320.0, speed))
        brake_gate = 1.0 - self.smoothstep(8.0, 55.0, float(raw["brake"]))
        vertical_gate = self.smoothstep(0.16, 0.95, accel_y_delta)
        left_suspension_gate = self.smoothstep(0.65, 3.20, left_rate)
        right_suspension_gate = self.smoothstep(0.65, 3.20, right_rate)
        twist_gate = self.smoothstep(0.45, 2.60, abs(left_rate - right_rate))
        left_level = max(left_suspension_gate, vertical_gate * 0.48, twist_gate * 0.42) * speed_gate * brake_gate
        right_level = max(right_suspension_gate, vertical_gate * 0.48, twist_gate * 0.42) * speed_gate * brake_gate
        return max(0.0, min(1.0, left_level)), max(0.0, min(1.0, right_level))

    @staticmethod
    def road_bump_envelope(
        now: float,
        previous: float,
        target: float,
        hold_until: float,
    ) -> tuple[float, float]:
        target = max(0.0, min(1.0, target))
        if target > previous + 0.025:
            level = previous + (target - previous) * 0.98
            hold_until = now + 0.005 + level * 0.001
            return level, hold_until
        if now < hold_until:
            return previous, hold_until
        decayed = max(0.0, previous * 0.10 + target * 0.01)
        floor = 0.035
        if decayed < floor:
            return 0.0, hold_until
        return decayed, hold_until

    @staticmethod
    def road_bump2_envelope(previous: float, target: float, is_asphalt: bool) -> float:
        target = max(0.0, min(1.0, target))
        if target > previous:
            return previous + (target - previous) * 0.82
        if is_asphalt:
            decayed = max(0.0, previous * 0.62 + target * 0.14)
            return 0.0 if decayed < 0.018 else decayed
        decayed = max(0.0, previous * 0.48 + target * 0.10)
        return 0.0 if decayed < 0.035 else decayed

    @staticmethod
    def asphalt_bump_envelope(now: float, previous: float, target: float, hold_until: float) -> tuple[float, float]:
        target = max(0.0, min(1.0, target))
        if target > previous + 0.018:
            hold_until = now + 0.020 + target * 0.040
            return target, hold_until
        if now < hold_until:
            return previous, hold_until
        decayed = max(0.0, previous * 0.12 + target * 0.02)
        if decayed < 0.015:
            return 0.0, hold_until
        return decayed, hold_until

    @staticmethod
    def is_offroad_bump_surface(raw: dict[str, float | int | bool]) -> bool:
        for name in ("surface_rumble_fl", "surface_rumble_fr"):
            rumble = abs(float(raw[name]))
            if rumble >= 0.001 and not (0.20 <= rumble <= 0.29):
                return True
        return False

    @staticmethod
    def is_asphalt_surface(raw: dict[str, float | int | bool]) -> bool:
        return (
            abs(float(raw["surface_rumble_fl"])) < 0.001
            and abs(float(raw["surface_rumble_fr"])) < 0.001
        )

    @staticmethod
    def smoothstep(edge0: float, edge1: float, x: float) -> float:
        if edge0 >= edge1:
            return 1.0 if x >= edge1 else 0.0
        t = max(0.0, min(1.0, (x - edge0) / (edge1 - edge0)))
        return t * t * (3.0 - 2.0 * t)

    def detect_impact_event(
        self,
        now: float,
        raw: dict[str, float | int | bool],
        values: dict[str, float],
    ) -> None:
        if not bool(raw["on"]):
            self.previous_impact_raw = None
            self.previous_impact_at = 0.0
            return

        previous = self.previous_impact_raw
        previous_at = self.previous_impact_at
        self.previous_impact_raw = dict(raw)
        self.previous_impact_at = now
        if previous is None or previous_at <= 0:
            return

        cooldown_s = 0.22
        if now - self.last_impact_at < cooldown_s:
            return

        dt = max(0.001, now - previous_at)
        prev_speed = max(0.0, float(previous["speed_kmh"]))
        speed = max(0.0, float(raw["speed_kmh"]))
        speed_drop = max(0.0, prev_speed - speed)
        accel_g = max(0.0, float(values["accel_g"]))
        slip = max(0.0, float(values["slip_combined_max"]))
        smash_vel_diff = max(0.0, abs(float(raw["smashable_vel_diff"])))
        smash_mass = max(0.0, abs(float(raw["smashable_mass"])))

        # Wall impacts are inferred from the recorded Forza log: sudden speed
        # drop, accel spike, and tire slip spike. Breakable objects are handled
        # separately by Impact - Smashable so they can repeat quickly.
        wall_power = 0.0
        if dt <= 0.08 and prev_speed >= 15.0:
            speed_hit = min(1.0, speed_drop / 80.0)
            accel_hit = min(1.0, max(0.0, accel_g - 25.0) / 120.0)
            slip_hit = min(1.0, max(0.0, slip - 8.0) / 32.0)
            if speed_drop >= 18.0 or accel_g >= 35.0:
                wall_power = max(speed_hit, accel_hit, slip_hit)

        power = wall_power
        if power <= 0:
            return

        reason = "wall"
        self.current_log_analysis["event_impact"] = 1
        self.current_log_analysis["event_impact_reason"] = reason
        self.current_log_analysis["event_impact_power"] = max(0.0, min(1.0, power))
        self.current_log_analysis["event_impact_speed_drop_kmh"] = speed_drop
        self.current_log_analysis["event_impact_accel_g"] = accel_g
        self.current_log_analysis["event_impact_slip"] = slip

        fields = {
            "power": max(0.0, min(1.0, power)),
            "speedDrop": speed_drop,
            "accelG": accel_g,
            "slip": slip,
            "mass": smash_mass,
            "smashVelDiff": smash_vel_diff,
            "volume": self.effect_volume(EFFECT_IMPACTS),
        }
        payload = "IMPACT|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload)
        self.send_collision_kick_trigger_event(power, float(raw["accel_x"]))
        self.trigger_effect_output(EFFECT_IMPACTS, 10.0 * power, 0.18 * (1.0 + max(0.0, min(1.0, power))), 1)
        self.last_impact_at = now

    def detect_smashable_impact_event(self, now: float, raw: dict[str, float | int | bool]) -> None:
        if not bool(raw["on"]):
            return

        cooldown_s = 0.065
        if now - self.last_smashable_impact_at < cooldown_s:
            return

        smash_vel_diff = max(0.0, abs(float(raw["smashable_vel_diff"])))
        smash_mass = max(0.0, abs(float(raw["smashable_mass"])))
        if smash_vel_diff <= 0.01:
            return

        vel_gain = min(1.0, max(0.0, (smash_vel_diff - 0.01) / max(0.2 - 0.01, 0.000001)))
        mass_norm = min(1.0, max(0.0, math.log(1 + smash_mass) / math.log(1 + 80))) if smash_mass > 0 else 0.35
        mass_gain = 0.55 + (1 - 0.55) * mass_norm
        speed_gain = min(1.0, max(0.0, float(raw["speed_kmh"]) - 20.0) / 120.0)
        power = min(1.0, vel_gain * mass_gain * (0.65 + speed_gain * 0.35))
        power = max(0.05, power)

        self.current_log_analysis["event_smashable_impact"] = 1
        self.current_log_analysis["event_smashable_impact_power"] = power
        self.current_log_analysis["event_smashable_impact_mass"] = smash_mass
        self.current_log_analysis["event_smashable_impact_vel_diff"] = smash_vel_diff

        fields = {
            "power": power,
            "mass": smash_mass,
            "smashVelDiff": smash_vel_diff,
            "speed": max(0.0, float(raw["speed_kmh"])),
            "volume": self.effect_volume(EFFECT_IMPACT_SMASHABLE),
        }
        payload = "IMPACT_SMASHABLE|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload)
        self.send_impact_tick_trigger_event(power)
        self.trigger_effect_output(EFFECT_IMPACT_SMASHABLE, 10.0 * power, 0.10, 1)
        self.last_smashable_impact_at = now

    def detect_side_impact_event(self, now: float, raw: dict[str, float | int | bool]) -> None:
        if not bool(raw["on"]):
            self.steer_history.clear()
            return

        self.steer_history.append((now, abs(float(raw["steer"]))))
        while self.steer_history and now - self.steer_history[0][0] > 0.50:
            self.steer_history.popleft()

        previous = self.previous_impact_raw
        previous_at = self.previous_impact_at
        if previous is None or previous_at <= 0:
            return

        cooldown_s = 0.24
        if now - self.last_side_impact_at < cooldown_s:
            return

        dt = max(0.001, now - previous_at)
        if dt > 0.11:
            return

        speed = max(0.0, float(raw["speed_kmh"]))
        if speed < 12.0:
            return

        brake = float(raw["brake"])
        if brake >= 20.0:
            return

        dvel = math.sqrt(
            (float(raw["velocity_x"]) - float(previous["velocity_x"])) ** 2
            + (float(raw["velocity_y"]) - float(previous["velocity_y"])) ** 2
            + (float(raw["velocity_z"]) - float(previous["velocity_z"])) ** 2
        ) * 3.6
        accel_x = abs(float(raw["accel_x"]))
        accel_y = abs(float(raw["accel_y"]))
        accel_z = abs(float(raw["accel_z"]))
        accel_x_delta = abs(float(raw["accel_x"]) - float(previous["accel_x"]))
        accel_y_delta = abs(float(raw["accel_y"]) - float(previous["accel_y"]))
        accel_z_delta = abs(float(raw["accel_z"]) - float(previous["accel_z"]))
        recent_steer = max((steer for _ts, steer in self.steer_history), default=0.0)
        angular_y = abs(float(raw["angular_velocity_y"]))
        angular_y_delta = abs(float(raw["angular_velocity_y"]) - float(previous["angular_velocity_y"]))

        dvel_score = max(0.0, min(1.0, (dvel - 0.9) / 5.8))
        accel_x_score = max(0.0, min(1.0, (accel_x - 4.5) / 13.0))
        accel_z_score = max(0.0, min(1.0, (accel_z - 3.2) / 15.0))
        angular_score = max(0.0, min(1.0, angular_y / 0.85))
        steer_score = max(0.0, min(1.0, (recent_steer - 12.0) / 48.0))
        speed_score = max(0.0, min(1.0, (speed - 12.0) / 60.0))

        impact_score = (
            dvel_score * 0.32
            + accel_x_score * 0.27
            + accel_z_score * 0.18
            + angular_score * 0.13
            + steer_score * 0.07
            + speed_score * 0.03
        )

        has_lateral_signature = accel_x >= 5.8 or angular_y >= 0.18 or (
            dvel >= 1.4 and accel_x >= 6.5
        )
        has_lateral_edge = accel_x_delta >= 3.8 or angular_y_delta >= 0.12 or (
            dvel >= 1.4 and accel_x >= 7.0 and accel_x_delta >= 2.2
        )
        has_impact_edge = has_lateral_edge and (dvel >= 1.0 or accel_x_delta >= 3.8 or accel_z_delta >= 5.0)
        has_steering_context = recent_steer >= 14.0
        vertical_dominant_bump = (
            accel_y_delta >= 2.0
            and accel_y_delta >= accel_x_delta * 1.10
            and accel_y_delta >= angular_y_delta * 30.0
            and accel_x_delta < 6.0
        )
        suspension_step_bump = accel_y >= 11.0 and accel_y_delta >= 4.5 and dvel < 2.4 and angular_y_delta < 0.18
        if vertical_dominant_bump or suspension_step_bump:
            return
        if impact_score < 0.16 or not (has_lateral_signature and has_steering_context and has_impact_edge):
            return

        edge_score = max(
            min(1.0, max(0.0, dvel - 1.25) / 5.0),
            min(1.0, max(0.0, accel_x_delta - 3.8) / 12.0),
            min(1.0, max(0.0, angular_y_delta - 0.12) / 0.55),
        )
        power = max(0.04, min(1.0, (impact_score * 0.70 + edge_score * 0.30) ** 1.15))

        self.current_log_analysis["event_side_impact"] = 1
        self.current_log_analysis["event_side_impact_score"] = impact_score
        self.current_log_analysis["event_side_impact_power"] = power
        self.current_log_analysis["event_side_impact_dvel"] = dvel
        self.current_log_analysis["event_side_impact_recent_steer"] = recent_steer
        self.current_log_analysis["event_side_impact_accel_x"] = accel_x
        self.current_log_analysis["event_side_impact_accel_z"] = accel_z
        self.current_log_analysis["event_side_impact_accel_x_delta"] = accel_x_delta
        self.current_log_analysis["event_side_impact_accel_y_delta"] = accel_y_delta
        self.current_log_analysis["event_side_impact_accel_z_delta"] = accel_z_delta
        self.current_log_analysis["event_side_impact_angular_y_delta"] = angular_y_delta

        fields = {
            "power": power,
            "dVel": dvel,
            "accelX": accel_x,
            "accelZ": accel_z,
            "accelXDelta": accel_x_delta,
            "accelYDelta": accel_y_delta,
            "accelZDelta": accel_z_delta,
            "angularYDelta": angular_y_delta,
            "angularY": angular_y,
            "recentSteer": recent_steer,
            "volume": self.effect_volume(EFFECT_IMPACT_SIDE),
        }
        payload = "IMPACT_SIDE|" + "|".join(f"{key}={value}" for key, value in fields.items())
        self.send_haptic_event(payload)
        self.send_collision_kick_trigger_event(
            power,
            float(raw["accel_x"]),
            impact_score=impact_score,
            dvel=dvel,
            accel_x_delta=accel_x_delta,
            angular_y_delta=angular_y_delta,
        )
        self.trigger_effect_output(EFFECT_IMPACT_SIDE, 10.0 * power, 0.16, 1)
        self.last_side_impact_at = now

    def trigger_effect_output(self, effect_name: str, peak: float, duration_s: float, direction: int) -> None:
        peak = max(0.0, min(10.0, float(peak)))
        if peak <= 0:
            return
        started_at = time.monotonic()
        self.active_output_events.append(
            {
                "effect": effect_name,
                "start": started_at,
                "duration": max(0.001, float(duration_s)),
                "peak": peak,
                "direction": 1.0 if direction >= 0 else -1.0,
            }
        )
        self.seed_output_preview(effect_name, started_at, peak, max(0.001, float(duration_s)), direction)

    def seed_output_preview(
        self,
        effect_name: str,
        started_at: float,
        peak: float,
        duration_s: float,
        direction: int,
    ) -> None:
        history = self.effect_output_samples.setdefault(effect_name, deque())
        # Short effects can be missed visually if we only sample on telemetry
        # packet arrival. Seed a dense shape preview into the visible output
        # window, and avoid mixing it with live event samples.
        sample_count = max(24, min(96, int(duration_s * 240)))
        preview_start = started_at - duration_s
        for idx in range(sample_count + 1):
            x = idx / max(sample_count, 1)
            elapsed = duration_s * x
            envelope = self.effect_output_envelope(effect_name, elapsed, duration_s, direction)
            history.append((preview_start + elapsed, max(0.0, min(10.0, peak * envelope))))

    def update_effect_output_samples(self, now: float, raw: dict[str, float | int | bool]) -> None:
        levels = {name: 0.0 for name in DEFAULT_EFFECT_SETTINGS}
        active_events: list[dict[str, float | str]] = []
        for event in self.active_output_events:
            effect_name = str(event["effect"])
            elapsed = now - float(event["start"])
            duration = float(event["duration"])
            if elapsed < 0 or elapsed > duration:
                continue
            active_events.append(event)
        self.active_output_events = active_events

        levels[EFFECT_REV_LIMIT] = self.rev_limit_output_level(raw)
        self.effect_output_samples.setdefault(EFFECT_REV_LIMIT, deque()).append(
            (now, max(0.0, min(10.0, levels[EFFECT_REV_LIMIT])))
        )
        fl_level, fr_level, _hz = self.rumble_kerbs_levels(raw)
        levels[EFFECT_RUMBLE_KERBS] = max(fl_level, fr_level) * 10.0
        self.effect_output_samples.setdefault(EFFECT_RUMBLE_KERBS, deque()).append(
            (now, max(0.0, min(10.0, levels[EFFECT_RUMBLE_KERBS])))
        )
        left_limit, right_limit, _left_hz, _right_hz = self.latest_tire_limit_levels
        levels[EFFECT_TIRE_LIMIT_LOAD] = max(left_limit, right_limit) * 10.0
        self.effect_output_samples.setdefault(EFFECT_TIRE_LIMIT_LOAD, deque()).append(
            (now, max(0.0, min(10.0, levels[EFFECT_TIRE_LIMIT_LOAD])))
        )
        wheelspin_left, wheelspin_right = self.latest_wheelspin_levels
        levels[EFFECT_WHEELSPIN_BUZZ] = max(wheelspin_left, wheelspin_right) * 10.0
        self.effect_output_samples.setdefault(EFFECT_WHEELSPIN_BUZZ, deque()).append(
            (now, max(0.0, min(10.0, levels[EFFECT_WHEELSPIN_BUZZ])))
        )
        road_left, road_right, _road_hz = self.latest_road_bump_offroad2_levels
        levels[EFFECT_ROAD_BUMPS] = max(road_left, road_right) * 10.0
        self.effect_output_samples.setdefault(EFFECT_ROAD_BUMPS, deque()).append(
            (now, max(0.0, min(10.0, levels[EFFECT_ROAD_BUMPS])))
        )

    def rev_limit_output_level(self, raw: dict[str, float | int | bool]) -> float:
        if not bool(raw["on"]):
            return 0.0
        rpm = max(0.0, float(raw["rpm"]))
        max_rpm = max(0.0, float(raw["max_rpm"]))
        idle_rpm = max(0.0, float(raw["idle_rpm"]))
        if rpm <= 0 or max_rpm <= 1000:
            return 0.0
        start_rpm = max(1000.0, idle_rpm, max_rpm * 0.90)
        end_rpm = max(start_rpm + 1.0, max_rpm)
        intensity = max(0.0, min(1.0, (rpm - start_rpm) / max(end_rpm - start_rpm, 1.0)))
        return 10.0 * intensity

    def prepare_log_analysis(
        self,
        now: float,
        raw: dict[str, float | int | bool],
        values: dict[str, float],
    ) -> None:
        previous = self.previous_impact_raw
        previous_at = self.previous_impact_at
        dt = max(0.001, now - previous_at) if previous is not None and previous_at > 0 else 0.0
        speed = max(0.0, float(raw["speed_kmh"]))
        prev_speed = max(0.0, float(previous["speed_kmh"])) if previous is not None else speed
        speed_drop = max(0.0, prev_speed - speed)
        accel_mag = max(0.0, float(values["accel_g"]))
        angular_mag = math.sqrt(
            float(raw["angular_velocity_x"]) ** 2
            + float(raw["angular_velocity_y"]) ** 2
            + float(raw["angular_velocity_z"]) ** 2
        )
        wheel_speeds = [
            float(raw["wheel_rotation_speed_fl"]),
            float(raw["wheel_rotation_speed_fr"]),
            float(raw["wheel_rotation_speed_rl"]),
            float(raw["wheel_rotation_speed_rr"]),
        ]
        wheel_spread = max(wheel_speeds) - min(wheel_speeds)
        slip = max(0.0, float(values["slip_combined_max"]))
        smash_vel_diff = max(0.0, abs(float(raw["smashable_vel_diff"])))
        smash_mass = max(0.0, abs(float(raw["smashable_mass"])))
        rev_preview = self.rev_limit_output_level(raw)
        impact_score = 0.0
        if dt > 0 and dt <= 0.08 and prev_speed >= 15.0:
            impact_score = max(
                min(1.0, speed_drop / 80.0),
                min(1.0, max(0.0, accel_mag - 25.0) / 120.0),
                min(1.0, max(0.0, slip - 8.0) / 32.0),
            )
        smash_score = 0.0
        if smash_vel_diff > 0.01:
            smash_score = min(1.0, max(0.0, (smash_vel_diff - 0.01) / max(0.2 - 0.01, 0.000001)))

        self.current_log_analysis = {
            "analysis_dt_s": dt,
            "analysis_prev_speed_kmh": prev_speed,
            "analysis_speed_drop_kmh": speed_drop,
            "analysis_speed_drop_per_s": speed_drop / dt if dt > 0 else 0.0,
            "analysis_accel_mag": accel_mag,
            "analysis_angular_velocity_mag": angular_mag,
            "analysis_slip_combined_max": slip,
            "analysis_wheel_speed_spread": wheel_spread,
            "analysis_smashable_vel_diff": smash_vel_diff,
            "analysis_smashable_mass": smash_mass,
            "analysis_impact_candidate_score": max(impact_score, smash_score),
            "analysis_rev_limit_preview": rev_preview,
            "analysis_selected_output_effect": self.selected_output_effect.get(),
            "event_gear_shift": 0,
            "event_gear_shift_dir": 0,
            "event_impact": 0,
            "event_impact_reason": "",
            "event_impact_power": 0.0,
            "event_impact_speed_drop_kmh": 0.0,
            "event_impact_accel_g": 0.0,
            "event_impact_slip": 0.0,
            "event_smashable_impact": 0,
            "event_smashable_impact_power": 0.0,
            "event_smashable_impact_mass": 0.0,
            "event_smashable_impact_vel_diff": 0.0,
            "event_side_impact": 0,
            "event_side_impact_score": 0.0,
            "event_side_impact_power": 0.0,
            "event_side_impact_dvel": 0.0,
            "event_side_impact_recent_steer": 0.0,
            "event_side_impact_accel_x": 0.0,
            "event_side_impact_accel_z": 0.0,
            "event_side_impact_accel_x_delta": 0.0,
            "event_side_impact_accel_y_delta": 0.0,
            "event_side_impact_accel_z_delta": 0.0,
            "event_side_impact_angular_y_delta": 0.0,
        }

    def effect_output_envelope(self, effect_name: str, elapsed_s: float, duration_s: float, direction: int) -> float:
        t_ms = elapsed_s * 1000.0
        duration_ms = max(1.0, duration_s * 1000.0)
        time_scale = max(0.1, duration_ms / self.nominal_effect_duration_ms(effect_name))
        if effect_name == EFFECT_GEAR_SHIFT_CORE:
            return self.core_output_envelope(t_ms, time_scale, direction)
        if effect_name == EFFECT_GEAR_SHIFT_HIGH_HZ:
            return self.high_hz_output_envelope(t_ms, time_scale, direction)
        if effect_name == EFFECT_GEAR_SHIFT_PARTICLES:
            return self.particles_output_envelope(t_ms, time_scale, direction)
        if effect_name == EFFECT_IMPACTS:
            return self.impact_output_envelope(t_ms, time_scale)
        if effect_name == EFFECT_IMPACT_SIDE:
            return self.side_impact_output_envelope(t_ms)
        if effect_name == EFFECT_IMPACT_SMASHABLE:
            return self.smashable_output_envelope(t_ms)
        x = max(0.0, min(1.0, elapsed_s / max(duration_s, 0.001)))
        return max(0.0, (1.0 - x) ** 1.35)

    @staticmethod
    def nominal_effect_duration_ms(effect_name: str) -> float:
        if effect_name == EFFECT_GEAR_SHIFT_CORE:
            return 360.0
        if effect_name == EFFECT_GEAR_SHIFT_HIGH_HZ:
            return 500.0
        if effect_name == EFFECT_GEAR_SHIFT_PARTICLES:
            return 580.0
        if effect_name == EFFECT_IMPACTS:
            return 180.0
        if effect_name == EFFECT_IMPACT_SIDE:
            return 160.0
        if effect_name == EFFECT_IMPACT_SMASHABLE:
            return 100.0
        return 500.0

    @staticmethod
    def pulse(t_ms: float, start_ms: float, end_ms: float, amp: float = 1.0) -> float:
        if t_ms < start_ms or t_ms > end_ms:
            return 0.0
        x = (t_ms - start_ms) / max(end_ms - start_ms, 0.001)
        return amp * math.sin(math.pi * x)

    @staticmethod
    def gaussian(x: float, center: float, width: float, amp: float = 1.0) -> float:
        return amp * math.exp(-((x - center) / max(width, 0.0001)) ** 2)

    def core_output_envelope(self, t_ms: float, scale: float, direction: int) -> float:
        if t_ms < 0 or t_ms > 360 * scale:
            return 0.0
        if direction >= 0:
            hit1 = self.pulse(t_ms, 0, 72 * scale, 1.0)
            hit2 = self.pulse(t_ms, 82 * scale, 154 * scale, 0.76)
            tail = 0.0
            if 138 * scale <= t_ms <= 360 * scale:
                x = max(0.0, min(1.0, (t_ms - 138 * scale) / max(222 * scale, 0.001)))
                tail = 0.34 * ((1 - x) ** 1.9) * (0.70 + 0.30 * math.sin(t_ms * 0.25))
            return max(0.0, min(1.0, hit1 + hit2 + tail))
        hit1 = self.pulse(t_ms, 0, 50 * scale, 0.95)
        hit2 = self.pulse(t_ms, 60 * scale, 110 * scale, 0.85)
        hit3 = self.pulse(t_ms, 120 * scale, 175 * scale, 0.75)
        tail = 0.0
        if 175 * scale <= t_ms <= 360 * scale:
            x = max(0.0, min(1.0, (t_ms - 175 * scale) / max(200 * scale, 0.001)))
            tail = 0.28 * ((1 - x) ** 2.1) * (0.65 + 0.35 * math.sin(t_ms * 0.45))
        return max(0.0, min(1.0, hit1 + hit2 + hit3 + tail))

    def high_hz_output_envelope(self, t_ms: float, scale: float, direction: int) -> float:
        if t_ms < 0 or t_ms > 500 * scale:
            return 0.0
        if direction >= 0:
            if not (138 * scale <= t_ms <= 330 * scale):
                return 0.0
            x = (t_ms - 138 * scale) / max(365 * scale, 0.001)
            peak = (
                self.gaussian(x, 0.05, 0.10, 0.95)
                + self.gaussian(x, 0.38, 0.17, 0.90)
                + self.gaussian(x, 0.80, 0.14, 0.40)
            )
            spike = math.exp(-x * 22.0) * 0.65
            fade = max(0.0, (1 - x) ** 0.52)
            return max(0.0, min(1.0, (peak * fade + spike) * 0.72))
        if not (160 * scale <= t_ms <= 490 * scale):
            return 0.0
        x = (t_ms - 160 * scale) / max(405 * scale, 0.001)
        peak = (
            self.gaussian(x, 0.05, 0.11, 0.90)
            + self.gaussian(x, 0.38, 0.19, 1.00)
            + self.gaussian(x, 0.81, 0.15, 0.48)
        )
        spike = math.exp(-x * 20.0) * 0.60
        fade = max(0.0, (1 - x) ** 0.48)
        return max(0.0, min(1.0, (peak * fade + spike) * 0.72))

    def particles_output_envelope(self, t_ms: float, scale: float, direction: int) -> float:
        if direction >= 0:
            start = (80 + 20) * scale
            end = (470 + 20) * scale
            centers = (0.08, 0.17, 0.25, 0.34, 0.46, 0.57, 0.68, 0.81)
            amps = (0.65, 0.90, 0.68, 0.95, 0.72, 0.82, 0.62, 0.50)
            fade_power = 0.35
        else:
            start = (90 + 20) * scale
            end = (540 + 20) * scale
            centers = (0.07, 0.15, 0.23, 0.31, 0.42, 0.53, 0.64, 0.75, 0.86)
            amps = (0.62, 0.78, 0.68, 0.92, 0.70, 0.80, 0.64, 0.58, 0.45)
            fade_power = 0.32
        if not (start <= t_ms <= end):
            return 0.0
        x = max(0.0, min(1.0, (t_ms - start) / max(end - start, 0.001)))
        burst = sum(self.gaussian(x, center, 0.012, amp) for center, amp in zip(centers, amps))
        fade = max(0.0, (1 - x) ** fade_power)
        return max(0.0, min(1.0, burst * fade))

    def impact_output_envelope(self, t_ms: float, scale: float = 1.0) -> float:
        scale = max(1.0, min(2.0, scale))
        if t_ms < 0:
            return 0.0
        if t_ms > 180 * scale:
            return 0.0
        attack = self.pulse(t_ms, 0, 42 * scale, 1.0)
        body = 0.0
        if 35 * scale <= t_ms <= 120 * scale:
            x = max(0.0, min(1.0, (t_ms - 35 * scale) / max(85.0 * scale, 0.001)))
            body = 0.55 * ((1 - x) ** 1.35) * (0.70 + 0.30 * math.sin(t_ms * 0.62))
        tail = 0.0
        if t_ms >= 95 * scale:
            x = max(0.0, min(1.0, (t_ms - 95 * scale) / max(85.0 * scale, 0.001)))
            tail = 0.24 * ((1 - x) ** 1.8)
        return max(0.0, min(1.0, attack + body + tail))

    def side_impact_output_envelope(self, t_ms: float) -> float:
        if t_ms < 0 or t_ms > 160:
            return 0.0
        attack = self.pulse(t_ms, 0, 34, 0.95)
        scrape = 0.0
        if 26 <= t_ms <= 118:
            x = max(0.0, min(1.0, (t_ms - 26) / 92.0))
            scrape = 0.58 * ((1 - x) ** 1.15) * (0.72 + 0.28 * math.sin(t_ms * 0.82))
        tail = 0.0
        if t_ms >= 92:
            x = max(0.0, min(1.0, (t_ms - 92) / 68.0))
            tail = 0.22 * ((1 - x) ** 1.7)
        return max(0.0, min(1.0, attack + scrape + tail))

    def smashable_output_envelope(self, t_ms: float) -> float:
        if t_ms < 0 or t_ms > 100:
            return 0.0
        attack = self.pulse(t_ms, 0, 18, 0.80)
        rattle = 0.0
        if 12 <= t_ms <= 72:
            x = max(0.0, min(1.0, (t_ms - 12) / 60.0))
            rattle = 0.48 * ((1 - x) ** 0.95) * (0.62 + 0.38 * math.sin(t_ms * 1.35))
        tail = 0.0
        if t_ms >= 55:
            x = max(0.0, min(1.0, (t_ms - 55) / 45.0))
            tail = 0.22 * ((1 - x) ** 1.6)
        return max(0.0, min(1.0, attack + rattle + tail))

    @staticmethod
    def trigger_timestamp_ms() -> int:
        return int(time.time() * 1000)

    def trigger_payload(self, event_name: str, fields: dict[str, int | float | str]) -> str:
        payload_fields: dict[str, int | float | str] = {"ts": self.trigger_timestamp_ms()}
        payload_fields.update(fields)
        return event_name + "|" + "|".join(f"{key}={value}" for key, value in payload_fields.items())

    @staticmethod
    def parse_event_payload(event_name: str) -> tuple[str, dict[str, str]]:
        parts = event_name.split("|")
        fields: dict[str, str] = {}
        for item in parts[1:]:
            if "=" not in item:
                continue
            key, value = item.split("=", 1)
            fields[key] = value
        return parts[0], fields

    @staticmethod
    def dsx_instruction(trigger: int, mode: int, params: list[int]) -> dict:
        return {
            "type": DSX_TRIGGER_UPDATE,
            "parameters": [DSX_CONTROLLER_INDEX, trigger, mode, *params],
        }

    def dsx_addr(self) -> tuple[str, int]:
        return (
            self.dsx_host_text.get().strip() or DEFAULT_DSX_HOST,
            self.normalized_udp_port(self.dsx_port_text.get(), DEFAULT_DSX_PORT),
        )

    def update_dsx_status_text(self) -> None:
        if not hasattr(self, "dsx_status_text"):
            return
        if not self.dsx_udp_enabled.get():
            self.dsx_status_text.set("DSX UDP off")
        elif self.dsx_last_error:
            self.dsx_status_text.set(f"DSX UDP error: {self.dsx_last_error}")
        else:
            host, port = self.dsx_addr()
            self.dsx_status_text.set(f"DSX UDP {host}:{port} sent {self.dsx_sent_count}")

    def dsx_strength_from_255(self, value) -> int:
        force = self.clamp_int(value, 0, 255)
        if 0 <= force <= 8:
            return force
        return max(0, min(8, int(round(force * 8 / 255.0))))

    def dsx_amp_from_percent(self, value) -> int:
        percent = self.clamp_int(value, 0, 100)
        if percent <= 0:
            return 0
        return max(1, min(8, int(round(percent * 8 / 100.0))))

    def dsx_amp_from_255(self, value) -> int:
        amp = self.clamp_int(value, 0, 255)
        if amp <= 0:
            return 0
        return max(1, min(8, int(round(amp * 8 / 255.0))))

    def dsx_start_zone_from_byte(self, value, vibration: bool = False) -> int:
        start = self.clamp_int(value, 0, 255)
        zone = max(0, min(9, int(round(start / 255.0 * 9.0))))
        return max(1, zone) if vibration else zone

    def dsx_float_field(self, fields: dict[str, str], key: str, default: float = 0.0) -> float:
        try:
            return float(fields.get(key, default))
        except (TypeError, ValueError):
            return default

    def dsx_int_field(self, fields: dict[str, str], key: str, default: int = 0) -> int:
        return self.clamp_int(fields.get(key, default), -100000, 100000)

    def dsx_state_from_continuous_fields(self, fields: dict[str, str]) -> tuple[int, list[int]]:
        force = self.clamp_int(fields.get("force", 0), 0, 255)
        start = self.dsx_start_zone_from_byte(fields.get("start", 0), vibration=False)
        vibrate_amp = self.clamp_int(fields.get("vibrateAmp", 0), 0, 8)
        vibrate_freq = self.clamp_int(fields.get("vibrateFreq", 0), 0, 40)
        vibrate_zone = self.clamp_int(fields.get("vibrateStartZone", 1), 1, 9)
        pulse = self.clamp_int(fields.get("pulse", 0), 0, 255)
        pulse_rate = self.clamp_int(fields.get("pulseRate", 0), 0, 255)
        if vibrate_amp > 0 and vibrate_freq > 0:
            return DSX_MODE_V3_VIBRATION, [vibrate_zone, vibrate_amp, vibrate_freq]
        if pulse > 0 and pulse_rate > 0:
            return DSX_MODE_V3_VIBRATION, [max(1, start), self.dsx_amp_from_255(pulse), max(1, min(40, pulse_rate))]
        if force > 0:
            return DSX_MODE_RESISTANCE, [start, self.dsx_strength_from_255(force)]
        return DSX_MODE_NORMAL, []

    def dsx_active_state_for_side(self, trigger: int, now: float) -> tuple[int, list[int]]:
        overlay = self.dsx_overlay_state.get(trigger)
        if overlay is not None:
            until, mode, params, _token, _tag = overlay
            if until > now:
                return mode, params
            self.dsx_overlay_state.pop(trigger, None)
        return self.dsx_base_state.get(trigger, (DSX_MODE_NORMAL, []))

    def dsx_send_current_state(self) -> None:
        now = time.monotonic()
        left_mode, left_params = self.dsx_active_state_for_side(DSX_TRIGGER_LEFT, now)
        right_mode, right_params = self.dsx_active_state_for_side(DSX_TRIGGER_RIGHT, now)
        payload = {
            "instructions": [
                self.dsx_instruction(DSX_TRIGGER_LEFT, left_mode, left_params),
                self.dsx_instruction(DSX_TRIGGER_RIGHT, right_mode, right_params),
            ]
        }
        try:
            self.dsx_sock.sendto(json.dumps(payload, separators=(",", ":")).encode("utf-8"), self.dsx_addr())
            self.dsx_sent_count += 1
            self.dsx_last_error = ""
        except OSError as exc:
            self.dsx_last_error = str(exc)
            self.last_error = f"DSX UDP send failed: {exc}"
        self.update_dsx_status_text()

    def dsx_send_off(self) -> None:
        self.dsx_base_state = {
            DSX_TRIGGER_LEFT: (DSX_MODE_NORMAL, []),
            DSX_TRIGGER_RIGHT: (DSX_MODE_NORMAL, []),
        }
        self.dsx_overlay_state.clear()
        if hasattr(self, "dsx_sock"):
            self.dsx_send_current_state()

    def dsx_set_overlay(self, triggers: tuple[int, ...], mode: int, params: list[int], duration_ms: int, tag: str) -> None:
        duration = max(20, min(1200, int(duration_ms)))
        self.dsx_overlay_token += 1
        token = self.dsx_overlay_token
        until = time.monotonic() + duration / 1000.0
        for trigger in triggers:
            self.dsx_overlay_state[trigger] = (until, mode, params, token, tag)
        self.dsx_send_current_state()
        self.root.after(duration + 5, lambda t=token: self.dsx_clear_overlay_token(t))

    def dsx_clear_overlay_token(self, token: int) -> None:
        changed = False
        for trigger, overlay in list(self.dsx_overlay_state.items()):
            if overlay[3] == token:
                self.dsx_overlay_state.pop(trigger, None)
                changed = True
        if changed and self.dsx_udp_enabled.get():
            self.dsx_send_current_state()

    def dsx_triggers_from_side(self, side: str) -> tuple[int, ...]:
        value = str(side).strip().lower()
        if value in {"left", "l"}:
            return (DSX_TRIGGER_LEFT,)
        if value in {"right", "r"}:
            return (DSX_TRIGGER_RIGHT,)
        return (DSX_TRIGGER_LEFT, DSX_TRIGGER_RIGHT)

    def send_dsx_trigger_event(self, event_name: str) -> bool:
        event, fields = self.parse_event_payload(event_name)
        if event == "TRIGGER_BRAKE":
            self.dsx_base_state[DSX_TRIGGER_LEFT] = self.dsx_state_from_continuous_fields(fields)
            self.dsx_send_current_state()
            return True
        if event == "TRIGGER_THROTTLE":
            self.dsx_base_state[DSX_TRIGGER_RIGHT] = self.dsx_state_from_continuous_fields(fields)
            self.dsx_send_current_state()
            return True
        if event == "TRIGGER_KERB_BUZZ":
            now = time.monotonic()
            for trigger, amp_key, freq_key, zone_key, on_key in (
                (DSX_TRIGGER_LEFT, "leftAmp", "leftFreq", "leftStartZone", "left"),
                (DSX_TRIGGER_RIGHT, "rightAmp", "rightFreq", "rightStartZone", "right"),
            ):
                on = self.clamp_int(fields.get(on_key, 0), 0, 1) > 0
                amp = self.clamp_int(fields.get(amp_key, 0), 0, 8)
                freq = self.clamp_int(fields.get(freq_key, 0), 0, 40)
                zone = self.clamp_int(fields.get(zone_key, 1), 1, 9)
                if on and amp > 0 and freq > 0:
                    self.dsx_overlay_state[trigger] = (now + 0.18, DSX_MODE_V3_VIBRATION, [zone, amp, freq], 0, "kerb")
                else:
                    overlay = self.dsx_overlay_state.get(trigger)
                    if overlay is not None and overlay[4] == "kerb":
                        self.dsx_overlay_state.pop(trigger, None)
            self.dsx_send_current_state()
            return True
        if event in {"TRIGGER_GEAR_SHIFT", "TRIGGER_COLLISION_KICK"}:
            strength = self.dsx_amp_from_percent(fields.get("strength", 0))
            if strength <= 0:
                return True
            duration_ms = self.clamp_int(fields.get("durationMs", 80), 20, 300)
            start = self.dsx_start_zone_from_byte(fields.get("start", 0), vibration=True)
            self.dsx_set_overlay(
                self.dsx_triggers_from_side(fields.get("side", "both")),
                DSX_MODE_V3_VIBRATION,
                [start, strength, 40],
                duration_ms,
                event,
            )
            return True
        if event == "TRIGGER_IMPACT_TICK":
            amp = self.clamp_int(fields.get("amp", 0), 0, 8)
            if amp <= 0:
                return True
            freq = self.clamp_int(fields.get("freq", 40), 1, 40)
            zone = self.clamp_int(fields.get("startZone", 1), 1, 9)
            duration_ms = self.clamp_int(fields.get("durationMs", 80), 20, 300)
            self.dsx_set_overlay((DSX_TRIGGER_RIGHT,), DSX_MODE_V3_VIBRATION, [zone, amp, freq], duration_ms, event)
            return True
        if event == "TRIGGER_MODE_TEST":
            amp = self.dsx_amp_from_255(fields.get("amp", 80))
            freq = self.clamp_int(fields.get("hz", 40), 1, 40)
            count = self.clamp_int(fields.get("count", 1), 1, 30)
            on_ms = self.clamp_int(fields.get("onMs", 80), 20, 1000)
            off_ms = self.clamp_int(fields.get("offMs", 0), 0, 1000)
            duration_ms = min(3000, count * (on_ms + off_ms))
            self.dsx_set_overlay((DSX_TRIGGER_LEFT, DSX_TRIGGER_RIGHT), DSX_MODE_V3_VIBRATION, [1, amp, freq], duration_ms, event)
            return True
        return False

    def clear_trigger_output_state(self, force: bool = False) -> None:
        now = time.monotonic()
        if not force and now - self.last_trigger_clear_at < 0.25:
            return
        self.last_trigger_clear_at = now
        self.trigger_force_last_time = 0.0
        for trigger_name in self.trigger_brake_active:
            self.trigger_brake_active[trigger_name] = False
            self.trigger_smoothed_force[trigger_name] = 0.0
        self.reset_brake_dynamic_server_pulse()
        self.reset_throttle_server_pulse()
        self.brake_dynamic_wall_start_percent = -1.0
        self.brake_predictive_wall_smoothed = -1.0
        self.throttle_traction_wall_start_percent = -1.0
        self.throttle_traction_wall_smoothed = -1.0
        self.send_haptic_event(
            self.trigger_payload(
                "TRIGGER_BRAKE",
                {
                    "force": 0,
                    "pulse": 0,
                    "pulseRate": 0,
                    "vibrateAmp": 0,
                    "vibrateFreq": 0,
                    "vibrateStartZone": 0,
                },
            ),
            count=False,
        )
        self.send_haptic_event(
            self.trigger_payload(
                "TRIGGER_THROTTLE",
                {
                    "force": 0,
                    "pulse": 0,
                    "pulseRate": 0,
                    "vibrateAmp": 0,
                    "vibrateFreq": 0,
                    "vibrateStartZone": 0,
                },
            ),
            count=False,
        )
        self.send_haptic_event(
            self.trigger_payload(
                "TRIGGER_GEAR_SHIFT",
                {
                    "side": "both",
                    "strength": 0,
                    "durationMs": 20,
                    "releaseMs": 0,
                    "softness": 10,
                    "dir": 0,
                },
            ),
            count=False,
        )

    def send_haptic_event(self, event_name: str, count: bool = True) -> None:
        if event_name.startswith("TRIGGER_") and self.dsx_udp_enabled.get():
            if self.send_dsx_trigger_event(event_name):
                if count:
                    self.haptic_event_count += 1
                return
            self.last_error = f"DSX bridge ignored event: {event_name.split('|', 1)[0]}"
            return
        if not self.haptic_audio_device_configured() and not event_name.startswith("TRIGGER_") and not event_name.startswith("MASTER_GAIN"):
            return
        try:
            self.haptic_sock.sendto(event_name.encode("ascii"), self.haptic_addr)
            if count:
                self.haptic_event_count += 1
        except OSError as exc:
            self.last_error = f"haptic event send failed: {exc}"

    def send_trigger_mode_test(self, preset: str) -> None:
        count = self.clamp_int(self.trigger_mode_test_count.get(), 1, 30)
        on_ms = self.clamp_int(self.trigger_mode_test_on_ms.get(), 20, 1000)
        off_ms = self.clamp_int(self.trigger_mode_test_off_ms.get(), 0, 1000)
        hz = self.clamp_int(self.trigger_mode_test_hz.get(), 1, 255)
        amp = self.clamp_int(self.trigger_mode_test_amp.get(), 1, 255)
        wall_start_percent = self.clamp_int(self.trigger_mode_test_wall_start.get(), 0, 100)
        wall_end_percent = self.clamp_int(self.trigger_mode_test_wall_end.get(), 0, 100)
        if wall_end_percent < wall_start_percent:
            wall_start_percent, wall_end_percent = wall_end_percent, wall_start_percent
        wall_start = self.wall_position_percent_to_start_byte(wall_start_percent)
        wall_end = self.wall_position_percent_to_start_byte(wall_end_percent)
        wall_strength = self.clamp_int(self.trigger_mode_test_wall_strength.get(), 0, 255)
        self.send_haptic_event(
            f"TRIGGER_MODE_TEST|preset={preset}|count={count}|onMs={on_ms}|offMs={off_ms}|hz={hz}|amp={amp}"
            f"|wallStart={wall_start}|wallEnd={wall_end}|wallStrength={wall_strength}",
            count=False,
        )
        self.update_trigger_mode_test_status(preset, count, on_ms, off_ms, hz, amp, wall_start_percent, wall_end_percent, wall_strength)

    def clear_trigger_mode_test_status_schedule(self) -> None:
        for after_id in getattr(self, "trigger_mode_test_after_ids", []):
            try:
                self.after_cancel(after_id)
            except tk.TclError:
                pass
        self.trigger_mode_test_after_ids = []

    def schedule_trigger_mode_test_status(self, delay_ms: int, text: str) -> None:
        after_id = self.after(max(0, int(delay_ms)), lambda value=text: self.trigger_mode_test_status.set(value))
        self.trigger_mode_test_after_ids.append(after_id)

    def update_trigger_mode_test_status(
        self,
        preset: str,
        count: int,
        on_ms: int,
        off_ms: int,
        hz: int,
        amp: int,
        wall_start: int,
        wall_end: int,
        wall_strength: int,
    ) -> None:
        self.clear_trigger_mode_test_status_schedule()
        wall_text = f" / wall {wall_start}-{wall_end} @{wall_strength}" if wall_strength > 0 else ""
        if preset == "pulse_sweep":
            rates = [10, 15, 20, 25, 30, 40, 50, 60, 70, 80, 90, 100]
            step_ms = 1200
            gap_ms = 450
            started_at = time.perf_counter()
            total_ms = len(rates) * step_ms + (len(rates) - 1) * gap_ms
            self.update_trigger_mode_sweep_status(started_at, rates, step_ms, gap_ms, total_ms, wall_text)
            return

        label = preset.replace("_", " ").title()
        self.trigger_mode_test_status.set(f"{label}: {count}x, on {on_ms} ms / off {off_ms} ms / hz {hz} / amp {amp}{wall_text}")
        self.schedule_trigger_mode_test_status(max(1200, count * (on_ms + off_ms) + 800), "")

    def update_trigger_mode_sweep_status(
        self,
        started_at: float,
        rates: list[int],
        step_ms: int,
        gap_ms: int,
        total_ms: int,
        wall_text: str,
    ) -> None:
        elapsed_ms = max(0, int((time.perf_counter() - started_at) * 1000))
        if elapsed_ms >= total_ms:
            self.trigger_mode_test_status.set("Pulse Sweep complete")
            self.schedule_trigger_mode_test_status(2500, "")
            return

        block_ms = step_ms + gap_ms
        index = min(len(rates) - 1, elapsed_ms // block_ms)
        in_block_ms = elapsed_ms - index * block_ms
        if in_block_ms < step_ms:
            self.trigger_mode_test_status.set(f"Pulse Sweep: {rates[index]} Hz{wall_text}")
        else:
            self.trigger_mode_test_status.set(f"Pulse Sweep: gap before {rates[min(index + 1, len(rates) - 1)]} Hz{wall_text}")
        after_id = self.after(100, lambda: self.update_trigger_mode_sweep_status(started_at, rates, step_ms, gap_ms, total_ms, wall_text))
        self.trigger_mode_test_after_ids.append(after_id)

    def toggle_log_recording(self) -> None:
        if self.log_writer is None:
            self.start_log_recording()
        else:
            self.stop_log_recording()

    def on_log_record_shortcut(self, event) -> str | None:
        if isinstance(event.widget, tk.Entry):
            return None
        self.toggle_log_recording()
        return "break"

    def start_log_recording(self) -> None:
        try:
            LOG_DIR.mkdir(exist_ok=True)
            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            self.log_path = LOG_DIR / f"telemetry_record_{stamp}.csv"
            self.log_file = self.log_path.open("w", newline="", encoding="utf-8-sig")
            fieldnames = ["elapsed_s", "wall_time", "packet_count"]
            fieldnames.extend(self.analysis_log_fieldnames())
            fieldnames.extend(self.effect_log_fieldnames())
            fieldnames.extend(f"raw_{name}" for name in parse_packet_field_names())
            fieldnames.extend(f"derived_{name}" for name in derived_field_names())
            self.log_writer = csv.DictWriter(self.log_file, fieldnames=fieldnames)
            self.log_writer.writeheader()
            self.log_started_at = time.monotonic()
            self.log_row_count = 0
            self.log_rec_text.set("● Log Rec")
            self.log_rec_fg = "#e74c3c"
            self.log_rec_button.configure(fg=self.log_rec_fg, activeforeground=self.log_rec_fg)
        except OSError as exc:
            self.last_error = f"log record start failed: {exc}"
            self.stop_log_recording()

    def stop_log_recording(self) -> None:
        try:
            if self.log_file is not None:
                self.log_file.flush()
                self.log_file.close()
        except OSError as exc:
            self.last_error = f"log record close failed: {exc}"
        finally:
            self.log_file = None
            self.log_writer = None
            self.log_started_at = 0.0
            self.log_rec_text.set("● Log Rec")
            self.log_rec_fg = "#8a949f"
            if hasattr(self, "log_rec_button"):
                self.log_rec_button.configure(fg=self.log_rec_fg, activeforeground=self.log_rec_fg)

    def write_log_row(
        self,
        now: float,
        raw: dict[str, float | int | bool],
        values: dict[str, float],
    ) -> None:
        if self.log_writer is None:
            return
        row = {
            "elapsed_s": f"{now - self.log_started_at:.6f}",
            "wall_time": datetime.now().isoformat(timespec="milliseconds"),
            "packet_count": self.packet_count,
        }
        for name in self.analysis_log_fieldnames():
            row[name] = self.current_log_analysis.get(name, "")
        for name, value in self.effect_log_values().items():
            row[name] = value
        for name in parse_packet_field_names():
            row[f"raw_{name}"] = raw.get(name, "")
        for name in derived_field_names():
            row[f"derived_{name}"] = values.get(name, "")
        try:
            self.log_writer.writerow(row)
            self.log_row_count += 1
            if self.log_row_count % 60 == 0 and self.log_file is not None:
                self.log_file.flush()
        except OSError as exc:
            self.last_error = f"log record write failed: {exc}"
            self.stop_log_recording()

    @staticmethod
    def analysis_log_fieldnames() -> list[str]:
        return [
            "analysis_dt_s",
            "analysis_prev_speed_kmh",
            "analysis_speed_drop_kmh",
            "analysis_speed_drop_per_s",
            "analysis_accel_mag",
            "analysis_angular_velocity_mag",
            "analysis_slip_combined_max",
            "analysis_wheel_speed_spread",
            "analysis_smashable_vel_diff",
            "analysis_smashable_mass",
            "analysis_impact_candidate_score",
            "analysis_rev_limit_preview",
            "analysis_selected_output_effect",
            "event_gear_shift",
            "event_gear_shift_dir",
            "event_impact",
            "event_impact_reason",
            "event_impact_power",
            "event_impact_speed_drop_kmh",
            "event_impact_accel_g",
            "event_impact_slip",
            "event_smashable_impact",
            "event_smashable_impact_power",
            "event_smashable_impact_mass",
            "event_smashable_impact_vel_diff",
            "event_side_impact",
            "event_side_impact_score",
            "event_side_impact_power",
            "event_side_impact_dvel",
            "event_side_impact_recent_steer",
            "event_side_impact_accel_x",
            "event_side_impact_accel_z",
            "event_side_impact_accel_x_delta",
            "event_side_impact_accel_y_delta",
            "event_side_impact_accel_z_delta",
            "event_side_impact_angular_y_delta",
        ]

    @staticmethod
    def effect_key(effect_name: str) -> str:
        return alias_key(effect_name)

    def effect_log_fieldnames(self) -> list[str]:
        names: list[str] = []
        for effect_name in DEFAULT_EFFECT_SETTINGS:
            key = self.effect_key(effect_name)
            names.extend(
                [
                    f"effect_{key}_enabled",
                    f"effect_{key}_volume",
                    f"effect_{key}_pan",
                    f"effect_{key}_preview",
                ]
            )
        return names

    def effect_log_values(self) -> dict[str, float | int]:
        values: dict[str, float | int] = {}
        for effect_name in DEFAULT_EFFECT_SETTINGS:
            key = self.effect_key(effect_name)
            controls_state = self.effect_controls[effect_name]
            history = self.effect_output_samples.get(effect_name)
            values[f"effect_{key}_enabled"] = 1 if controls_state["enabled"].get() else 0
            values[f"effect_{key}_volume"] = self.clamp_volume(controls_state["volume"].get())
            values[f"effect_{key}_pan"] = (
                self.clamp_pan(controls_state["pan"].get())
                if effect_name in PAN_EFFECTS and "pan" in controls_state
                else 5
            )
            values[f"effect_{key}_preview"] = max((value for _ts, value in history), default=0.0) if history else 0.0
        return values

    def trim_samples(self) -> None:
        now = time.monotonic()
        specs = self.graph_specs()
        active_names = {spec.name for spec in specs}
        active_cutoffs: dict[str, float] = {}
        for idx, spec in enumerate(specs):
            hidden_at = self.graph_hidden_at[idx] if idx < len(self.graph_hidden_at) else 0.0
            cutoff_base = hidden_at if hidden_at > 0.0 and self.graph_hidden_vars[idx].get() else now
            active_cutoffs[spec.name] = cutoff_base - GRAPH_SECONDS
        for name in list(self.samples):
            if name not in active_names:
                del self.samples[name]
                continue
            history = self.samples[name]
            cutoff = active_cutoffs.get(name, now - GRAPH_SECONDS)
            while history and history[0][0] < cutoff:
                history.popleft()
        for history in self.effect_output_samples.values():
            output_cutoff = time.monotonic() - OUTPUT_GRAPH_SECONDS
            while history and history[0][0] < output_cutoff:
                history.popleft()
        for history in self.trigger_output_samples.values():
            output_cutoff = time.monotonic() - OUTPUT_GRAPH_SECONDS
            while history and history[0][0] < output_cutoff:
                history.popleft()

    def udp_state_snapshot(self, now: float) -> tuple[str, str]:
        age = now - self.last_packet_at if self.last_packet_at else None
        if self.udp_bind_failed:
            return "port error", "error"
        if age is None:
            return "waiting", "waiting"
        if age < 1.0 and self.has_valid_driving_telemetry():
            return "live", "live"
        if age < 1.0:
            return "waiting telemetry", "waiting"
        return "stale", "stale"

    def draw(self, now: float | None = None, state: str | None = None, udp_state: str | None = None) -> None:
        width = max(1, self.canvas.winfo_width())
        height = max(1, self.canvas.winfo_height())
        if now is None:
            now = time.monotonic()
        if state is None or udp_state is None:
            state, udp_state = self.udp_state_snapshot(now)
        self.update_udp_status(udp_state)

        if udp_state == "live":
            self.graph_standby_key = None
            self.draw_live_graphs(width, height, now)
        else:
            if self.drift_mode_active or self.drift_mode_score:
                self.drift_mode_active = False
                self.drift_mode_score = 0.0
            self.drift_mode_score_last_update = 0.0
            self.drift_mode_hold_until = 0.0
            self.drift_relief_high_score_since = 0.0
            self.drift_relief_trigger_suppressed = False
            self.drift_oversteer_component = 0.0
            self.update_drift_relief_status_text()
            self.pause_live_graphs(width, height, state)

        self.status.set(
            f"Packets: {self.packet_count}   Haptic events: {self.haptic_event_count}   Window: {GRAPH_SECONDS:g}s"
            + f"   Haptic server: {self.haptic_server_status_text}"
            + (f"   Log rows: {self.log_row_count}" if self.log_writer is not None else "")
            + (f"   Last error: {self.last_error}" if self.last_error else "")
        )
        if self.last_dualsense_input_at and now - self.last_dualsense_input_at < 1.0:
            input_text = self.dualsense_input_text
        else:
            input_text = "DualSense L2/R2 --/--"
        drift_text = f"DRIFT {self.drift_mode_score:.2f}" if self.drift_mode_active else f"drift {self.drift_mode_score:.2f}"
        debug_text = f"{input_text}    {drift_text}    {getattr(self, 'brake_predictive_debug', 'pred --')}"
        self.top_debug_text.set(debug_text)
        self.value_text.set(self.format_values())
        if self.should_draw_hud_windows():
            self.draw_hud()
            self.draw_gforce_hud()
            self.draw_tire_hud()
            self.draw_steer_hud()
            self.draw_applied_steer_hud()
        self.draw_drift_debug_hud()

    def draw_live_graphs(self, width: int, height: int, now: float) -> None:
        self.canvas.delete("all")
        pad_left = 84
        pad_right = 24
        pad_top = 18
        pad_bottom = 28
        plot_w = max(1, width - pad_left - pad_right)
        specs = self.graph_specs()
        data = self.signal_map()
        output_name = self.selected_output_name()
        output_spec = GraphSpec(f"output: {output_name}", 10.0, "#f5f7fa")
        draw_specs = specs + [output_spec]
        row_h = max(62, (height - pad_top - pad_bottom) // len(draw_specs))

        for idx, spec in enumerate(draw_specs):
            top = pad_top + idx * row_h
            bottom = top + row_h - 8
            mid = (top + bottom) / 2
            is_output_graph = idx == len(draw_specs) - 1
            hidden = (not is_output_graph) and idx < len(self.graph_hidden_vars) and self.graph_hidden_vars[idx].get()
            draw_now = self.graph_hidden_at[idx] if hidden and self.graph_hidden_at[idx] > 0.0 else now
            graph_color = self.mix_hex_color(spec.color, "#171b20", 0.62) if hidden else spec.color
            history = self.selected_output_history() if is_output_graph else self.samples.get(spec.name, deque())
            scale = 10.0 if is_output_graph else self.dynamic_scale(spec, history)
            grid_color = "#20262e" if hidden else "#2a3139"
            mid_color = "#1d232a" if hidden else "#222932"
            self.canvas.create_line(pad_left, bottom, width - pad_right, bottom, fill=grid_color)
            self.canvas.create_line(pad_left, mid, width - pad_right, mid, fill=mid_color)
            self.canvas.create_text(12, top + 8, text=spec.name, anchor="nw", fill=graph_color, font=ui_font("Segoe UI", 9, "bold"))
            self.canvas.create_text(
                12,
                top + 26,
                text="hidden" if hidden else f"max {self.format_graph_number(scale)}",
                anchor="nw",
                fill="#4d5661" if hidden else "#66717d",
                font=ui_font("Segoe UI", 8),
            )

            graph_points = []
            point_history = sorted(history, key=lambda item: item[0]) if is_output_graph else list(history)
            if len(point_history) > MAX_GRAPH_DRAW_POINTS:
                step = max(1, (len(point_history) + MAX_GRAPH_DRAW_POINTS - 1) // MAX_GRAPH_DRAW_POINTS)
                point_history = point_history[::step][-MAX_GRAPH_DRAW_POINTS:]
            for ts, value in point_history:
                seconds = OUTPUT_GRAPH_SECONDS if is_output_graph else GRAPH_SECONDS
                x = pad_left + plot_w * (1.0 - max(0.0, min(seconds, draw_now - ts)) / seconds)
                magnitude = max(0.0, min(1.0, abs(value) / scale))
                if value >= 0:
                    y = mid - magnitude * (mid - top)
                else:
                    y = mid + magnitude * (bottom - mid)
                graph_points.append((x, y, float(value)))

            if len(graph_points) >= 2:
                negative_color = self.mix_hex_color(graph_color, "#171b20", 0.42)
                positive_runs = []
                negative_runs = []
                current_sign = 1 if graph_points[0][2] >= 0.0 else -1
                current_run = [(graph_points[0][0], graph_points[0][1])]
                for (x1, y1, v1), (x2, y2, v2) in zip(graph_points, graph_points[1:]):
                    if (v1 < 0.0 < v2) or (v2 < 0.0 < v1):
                        denom = abs(v1) + abs(v2)
                        mix = abs(v1) / denom if denom > 0.0 else 0.5
                        cross_x = x1 + (x2 - x1) * mix
                        current_run.append((cross_x, mid))
                        (positive_runs if current_sign >= 0 else negative_runs).append(current_run)
                        current_sign = 1 if v2 >= 0.0 else -1
                        current_run = [(cross_x, mid), (x2, y2)]
                    else:
                        current_run.append((x2, y2))
                (positive_runs if current_sign >= 0 else negative_runs).append(current_run)
                for run in positive_runs:
                    if len(run) >= 2:
                        coords = [coord for point in run for coord in point]
                        self.canvas.create_line(coords, fill=graph_color, width=2)
                for run in negative_runs:
                    if len(run) >= 2:
                        coords = [coord for point in run for coord in point]
                        self.canvas.create_line(coords, fill=negative_color, width=2)

            latest = history[-1][1] if (is_output_graph or hidden) and history else data.get(spec.name)
            if latest is not None:
                self.canvas.create_text(
                    width - pad_right - 6,
                    top + 8,
                    text=self.format_graph_number(latest),
                    anchor="ne",
                    fill="#68727d" if hidden else "#d6dde5",
                    font=ui_font("Consolas", 10, "bold"),
                )
            elif spec.name:
                self.canvas.create_text(
                    width - pad_right - 6,
                    top + 8,
                    text="no data",
                    anchor="ne",
                    fill="#d06c75",
                    font=ui_font("Consolas", 10, "bold"),
                )

    def pause_live_graphs(self, width: int, height: int, state: str) -> None:
        key = (width, height, state)
        if self.graph_standby_key == key:
            return
        self.graph_standby_key = key

    def has_valid_driving_telemetry(self) -> bool:
        if not self.latest_raw:
            return False
        if not bool(self.latest_raw.get("on", False)):
            return False
        try:
            max_rpm = float(self.latest_raw.get("max_rpm", 0.0))
        except (TypeError, ValueError):
            max_rpm = 0.0
        return max_rpm > 0.0

    def selected_output_name(self) -> str:
        if self.selected_detail_type.get() == "trigger":
            return self.selected_trigger_effect.get()
        return self.selected_output_effect.get()

    def selected_output_history(self) -> deque[tuple[float, float]]:
        if self.selected_detail_type.get() == "trigger":
            return self.trigger_output_samples.get(self.selected_trigger_effect.get(), deque())
        return self.effect_output_samples.get(self.selected_output_effect.get(), deque())

    def format_values(self) -> str:
        if not self.latest_raw:
            return "Waiting for Forza UDP packets. Check Forza Data Out IP/port and Windows Firewall."

        raw = self.latest_raw
        values = self.latest_values
        return (
            f"on={raw['on']}  gear={raw['gear']}  speed={values['speed_kmh']:.1f}km/h  "
            f"rpm={raw['rpm']:.0f}/{raw['max_rpm']:.0f}  accel={raw['accel']}  brake={raw['brake']}  "
            f"steer={raw['steer']}  slipC={values['slip_combined_max']:.3f}  "
            f"rumble={values['surface_rumble_max']:.3f}  smash={values['smashable_vel_diff']:.3f}  "
            f"g={values['accel_g']:.2f}  drift={'ON' if self.drift_mode_active else 'off'}:{self.drift_mode_score:.2f}  "
            f"class={raw['car_class']}  PI={raw['car_performance_index']}  car={raw['car_ordinal']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--haptic-event-port", type=int, default=DEFAULT_HAPTIC_EVENT_PORT)
    parser.add_argument(
        "--export-release-settings",
        nargs="?",
        const=str(RELEASE_SETTINGS_PATH),
        default=None,
        help="Write a release-safe settings JSON with local window/HUD layout keys removed, then exit.",
    )
    args, unknown_args = parser.parse_known_args()
    if unknown_args and not running_frozen():
        parser.error(f"unrecognized arguments: {' '.join(unknown_args)}")

    if args.export_release_settings is not None:
        path = export_release_settings(Path(args.export_release_settings))
        print(f"Exported release settings: {path}")
        return 0

    app = TelemetryApp(args.host, args.port, args.haptic_event_port)
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())















