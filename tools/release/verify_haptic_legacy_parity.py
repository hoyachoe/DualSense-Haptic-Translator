from __future__ import annotations

import struct
import sys
from copy import deepcopy
from dataclasses import replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PROJECT_ROOT))

import dht_app.haptic_effect_engine as haptic_module  # noqa: E402
from dht_app.app_state import AppState, GameMode, PRESET_NAMES  # noqa: E402
from dht_app.detail_schema import (  # noqa: E402
    HAPTIC_DETAIL_GROUPS,
    HAPTIC_DETAIL_RANGES,
    detail_label,
    format_lr_balance_value,
    grouped_numeric_details,
)
from dht_app.haptic_effect_engine import HapticEffectEngine  # noqa: E402
from dht_app.preset_loader import load_builtin_presets_into_state  # noqa: E402
from dht_app.settings_model import HAPTIC_EFFECT_DEFAULTS, EffectSetting  # noqa: E402
from dht_app.telemetry_frame import TelemetryFrame  # noqa: E402
from dht_app.telemetry_router import route_horizon_packet  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


CLOCK = Clock()
haptic_module.monotonic = CLOCK


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _frame(**overrides: object) -> TelemetryFrame:
    values: dict[str, object] = {
        "game_mode": GameMode.HORIZON,
        "parser_name": "haptic-legacy-parity-verifier",
        "packet_size": 324,
        "parsed": True,
        "is_race_on": True,
        "max_rpm": 8000.0,
        "idle_rpm": 900.0,
        "rpm": 5000.0,
        "accel_x": 0.0,
        "accel_y": 0.0,
        "accel_z": 0.0,
        "velocity_x": 0.0,
        "velocity_y": 0.0,
        "velocity_z": 30.0,
        "angular_velocity_y": 0.0,
        "norm_suspension_travel_fl": 0.25,
        "norm_suspension_travel_fr": 0.25,
        "norm_suspension_travel_rl": 0.25,
        "norm_suspension_travel_rr": 0.25,
        "speed": 100.0,
        "power": 250000.0,
        "torque": 450.0,
        "throttle": 180.0,
        "brake": 0.0,
        "clutch": 0.0,
        "handbrake": 0.0,
        "gear": 3,
        "steer": 0.0,
        "wheel_on_rumble_strip_fl": 0,
        "wheel_on_rumble_strip_fr": 0,
        "wheel_on_rumble_strip_rl": 0,
        "wheel_on_rumble_strip_rr": 0,
        "surface_rumble_fl": 0.0,
        "surface_rumble_fr": 0.0,
        "surface_rumble_rl": 0.0,
        "surface_rumble_rr": 0.0,
        "tire_slip_ratio_fl": 0.0,
        "tire_slip_ratio_fr": 0.0,
        "tire_slip_ratio_rl": 0.0,
        "tire_slip_ratio_rr": 0.0,
        "tire_slip_angle_fl": 0.0,
        "tire_slip_angle_fr": 0.0,
        "tire_slip_angle_rl": 0.0,
        "tire_slip_angle_rr": 0.0,
        "tire_combined_slip_fl": 0.0,
        "tire_combined_slip_fr": 0.0,
        "tire_combined_slip_rl": 0.0,
        "tire_combined_slip_rr": 0.0,
        "tire_temp_fl": 80.0,
        "tire_temp_fr": 80.0,
        "tire_temp_rl": 80.0,
        "tire_temp_rr": 80.0,
        "boost": 0.0,
        "smashable_vel_diff": 0.0,
        "smashable_mass": 0.0,
        "car_ordinal": 100,
        "car_class": 3,
        "car_performance_index": 700,
        "drive_train": 1,
        "drift": 0.0,
    }
    values.update(overrides)
    return TelemetryFrame(**values)


def _fields(payload) -> dict[str, str]:
    return dict(payload.params)


def _minimal_horizon_packet(*, pi: int, gear: int) -> bytes:
    packet = bytearray(324)
    struct.pack_into("<i", packet, 0, 1)
    struct.pack_into("<f", packet, 8, 8000.0)
    struct.pack_into("<f", packet, 12, 900.0)
    struct.pack_into("<f", packet, 16, 5200.0)
    struct.pack_into("<i", packet, 212, 100)
    struct.pack_into("<i", packet, 216, 3)
    struct.pack_into("<i", packet, 220, pi)
    struct.pack_into("<i", packet, 224, 1)
    struct.pack_into("<f", packet, 256, 30.0)
    struct.pack_into("<f", packet, 264, 450.0)
    packet[315] = 180
    packet[319] = gear
    return bytes(packet)


def _enabled(setting: EffectSetting) -> EffectSetting:
    result = deepcopy(setting)
    result.enabled = True
    result.details["enabled"] = True
    return result


def _disabled(setting: EffectSetting) -> EffectSetting:
    result = deepcopy(setting)
    result.enabled = False
    result.details["enabled"] = False
    return result


def _verify_inventory_and_ranges(state: AppState) -> None:
    public = tuple(name for name, _value, _enabled in HAPTIC_EFFECT_DEFAULTS)
    _assert(len(public) == 12, f"Expected 12 public haptic effects, got {len(public)}.")
    _assert("Impact - Smashable" in public, "Smashable is missing from HAPTIC_EFFECT_DEFAULTS.")
    for game, profile in state.game_profiles.items():
        for preset_name in PRESET_NAMES:
            preset = profile.presets[preset_name]
            _assert("Impact - Smashable" in preset.haptic_effects, f"Smashable missing from {game.value}/{preset_name}.")
            _assert("Impact - Smashable" not in preset.extra_haptic_effects, f"Smashable remained extra in {game.value}/{preset_name}.")

    expected_ranges = {
        ("Rev Limit", "rpm_position"): (80, 99),
        ("Rev Limit", "fade_range"): (1, 20),
        ("Rev Limit", "pulse_rate"): (0, 10),
        ("Rev Limit", "vehicle_rpm_scaling"): (0, 5),
        ("Rumble Kerbs", "speed_low_start"): (0, 200),
        ("Rumble Kerbs", "speed_high_max"): (0, 360),
        ("Tire Limit Load", "entry_threshold"): (0, 80),
        ("Tire Limit Load", "full_load_point"): (10, 100),
        ("Wheelspin Buzz", "slip_start_offset"): (-10, 10),
        ("Wheelspin Buzz", "noise_range"): (0, 30),
        ("Acceleration G Punch - Haptic", "haptic_gear_1_percent"): (0, 150),
        ("Acceleration G Punch - Haptic", "haptic_gear_2_percent"): (0, 150),
        ("Acceleration G Punch - Haptic", "haptic_gear_3_percent"): (0, 150),
        ("Impacts", "speed_drop_threshold"): (1, 80),
        ("Impacts", "g_force_threshold"): (1, 120),
        ("Impact - Smashable", "repeat_cooldown"): (20, 200),
    }
    for (effect_name, key), expected in expected_ranges.items():
        actual = HAPTIC_DETAIL_RANGES[effect_name][key]
        _assert(actual == expected, f"Wrong range for {effect_name}/{key}: {actual}, expected {expected}.")
    for effect_name, setting in state.haptic_effects.items():
        rendered_ranges = {
            row.key: (row.minimum, row.maximum)
            for group in grouped_numeric_details(effect_name, setting.details, HAPTIC_DETAIL_GROUPS)
            for row in group.rows
        }
        _assert(
            rendered_ranges == HAPTIC_DETAIL_RANGES[effect_name],
            f"Rendered ranges differ for {effect_name}: {rendered_ranges}.",
        )
    _assert(format_lr_balance_value(9, 0, 10) == "1:9", "L/R balance display is inverted.")
    _assert(detail_label("balance") == "Up/Down Balance", "Gear balance label is incorrect.")


def _verify_smashable_and_gear(state: AppState) -> None:
    CLOCK.value = 100.0
    smash_engine = HapticEffectEngine()
    smash_setting = _enabled(state.haptic_effects["Impact - Smashable"])
    smash_engine.process_frame(_frame(), {"Impact - Smashable": smash_setting})
    CLOCK.advance(0.070)
    payloads = smash_engine.process_frame(
        _frame(smashable_vel_diff=0.20, smashable_mass=25.0),
        {"Impact - Smashable": smash_setting},
    )
    _assert(any(payload.name == "IMPACT_SMASHABLE" for payload in payloads), "Smashable output was not emitted.")

    routed = route_horizon_packet(_minimal_horizon_packet(pi=915, gear=3)).frame
    _assert(routed.car_performance_index == 915, f"Router discarded PI: {routed.car_performance_index}.")
    CLOCK.value = 100.0
    gear_engine = HapticEffectEngine()
    gear_settings = {
        name: _enabled(state.haptic_effects[name])
        for name in ("Gear Shift Bite - Core", "Gear Shift Bite - High Hz", "Gear Shift Bite - Particles")
    }
    gear_engine.process_frame(routed, gear_settings)
    CLOCK.advance(0.016)
    payloads = gear_engine.process_frame(replace(routed, gear=4), gear_settings)
    shift = next(payload for payload in payloads if payload.name == "GEAR_SHIFT")
    _assert(_fields(shift).get("pi") == "915", f"Gear shift sent wrong PI: {_fields(shift).get('pi')}.")

    CLOCK.value = 100.0
    reverse_engine = HapticEffectEngine()
    reverse_engine.process_frame(_frame(gear=1), gear_settings)
    CLOCK.advance(0.016)
    reverse = reverse_engine.process_frame(_frame(gear=0), gear_settings)
    _assert(any(payload.name == "GEAR_SHIFT" for payload in reverse), "Reverse transition did not emit GEAR_SHIFT.")


def _road_output(state: AppState, volume: int) -> dict[str, str]:
    CLOCK.value = 100.0
    engine = HapticEffectEngine()
    setting = _enabled(state.haptic_effects["Road Bumps"])
    setting.value = volume
    engine.process_frame(_frame(), {"Road Bumps": setting})
    CLOCK.advance(0.016)
    payloads = engine.process_frame(
        _frame(norm_suspension_travel_fl=0.43, norm_suspension_travel_fr=0.40, accel_y=4.5),
        {"Road Bumps": setting},
    )
    return _fields(next(payload for payload in payloads if payload.name == "ROAD_BUMPS"))


def _verify_road_volume(state: AppState) -> None:
    full = _road_output(state, 10)
    low = _road_output(state, 2)
    _assert(full["hz"] == low["hz"], f"Road Bumps volume changed frequency: {full['hz']} vs {low['hz']}.")
    _assert(float(low["left"]) < float(full["left"]), "Road Bumps volume did not reduce amplitude.")


def _continuous_cases(state: AppState):
    tire_frame = _frame(
        speed=120.0,
        steer=95.0,
        angular_velocity_y=0.5,
        accel_x=-8.0,
        velocity_x=2.0,
        velocity_z=30.0,
        tire_slip_angle_fl=1.4,
        tire_slip_angle_fr=1.4,
        tire_slip_angle_rl=0.5,
        tire_slip_angle_rr=0.5,
        tire_combined_slip_fl=0.8,
        tire_combined_slip_fr=0.8,
        tire_combined_slip_rl=0.5,
        tire_combined_slip_rr=0.5,
    )
    return {
        "Rumble Kerbs": ("RUMBLE_KERBS", [_frame(wheel_on_rumble_strip_fl=1, speed=120.0)]),
        "Tire Limit Load": ("TIRE_LIMIT_LOAD", [tire_frame] * 8),
        "Wheelspin Buzz": (
            "WHEELSPIN_BUZZ",
            [_frame(speed=80.0, throttle=255.0, tire_slip_ratio_rl=1.9, tire_slip_ratio_rr=1.9)],
        ),
        "Acceleration G Punch - Haptic": (
            "ACCEL_G_PUNCH_HAPTIC",
            [_frame(gear=1, speed=35.0, throttle=255.0, accel_z=6.0, rpm=7600.0)],
        ),
        "Rev Limit": ("REV_LIMIT", [_frame(rpm=7920.0, throttle=255.0, gear=4)]),
        "Road Bumps": (
            "ROAD_BUMPS",
            [
                _frame(norm_suspension_travel_fl=0.2, norm_suspension_travel_fr=0.2, accel_y=0.0),
                _frame(norm_suspension_travel_fl=0.7, norm_suspension_travel_fr=0.65, accel_y=8.0),
            ],
        ),
    }


def _activate(engine: HapticEffectEngine, name: str, setting: EffectSetting, frames: list[TelemetryFrame]):
    payloads = ()
    for active_frame in frames:
        CLOCK.advance(0.016)
        payloads = engine.process_frame(active_frame, {name: setting})
    return payloads


def _verify_continuous_release(state: AppState) -> None:
    for name, (event_name, frames) in _continuous_cases(state).items():
        CLOCK.value = 100.0
        engine = HapticEffectEngine()
        setting = _enabled(state.haptic_effects[name])
        active_payloads = _activate(engine, name, setting, frames)
        _assert(any(payload.name == event_name for payload in active_payloads), f"{name} did not become active.")
        CLOCK.advance(0.016)
        release = engine.process_frame(frames[-1], {name: _disabled(setting)})
        zero = next((payload for payload in release if payload.name == event_name), None)
        _assert(zero is not None, f"{name} did not emit an immediate release payload.")
        _assert(float(_fields(zero).get("volume", "1")) == 0.0, f"{name} release volume was not zero.")
        CLOCK.advance(0.016)
        repeated = engine.process_frame(frames[-1], {name: _disabled(setting)})
        _assert(not any(payload.name == event_name for payload in repeated), f"{name} repeated its release payload.")

    CLOCK.value = 100.0
    race_engine = HapticEffectEngine()
    name = "Road Bumps"
    setting = _enabled(state.haptic_effects[name])
    frames = _continuous_cases(state)[name][1]
    _activate(race_engine, name, setting, frames)
    CLOCK.advance(0.016)
    release = race_engine.process_frame(replace(frames[-1], is_race_on=False), {name: setting})
    zero = next((payload for payload in release if payload.name == "ROAD_BUMPS"), None)
    _assert(zero is not None and float(_fields(zero)["volume"]) == 0.0, "Race-off did not release Road Bumps.")


def main() -> None:
    state = AppState()
    report = load_builtin_presets_into_state(state)
    _assert(report.ok and report.loaded_files == 12, f"Preset load failed: {report.summary}.")
    _verify_inventory_and_ranges(state)
    _verify_smashable_and_gear(state)
    _verify_road_volume(state)
    _verify_continuous_release(state)
    print("PASS: Haptic legacy parity verified (12 effects, PI, ranges, balance, Road Bumps, releases, reverse).")


if __name__ == "__main__":
    main()
