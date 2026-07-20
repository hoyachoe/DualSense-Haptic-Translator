from __future__ import annotations

import copy
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import dht_app.drift_rumble_fade as drift_module  # noqa: E402
import dht_app.haptic_effect_engine as haptic_module  # noqa: E402
import dht_app.trigger_effect_engine as trigger_module  # noqa: E402
from dht_app.app_state import AppState, BRAKE_TRIGGER_EFFECT_NAMES, GameMode  # noqa: E402
from dht_app.drift_rumble_fade import DriftRumbleFadeEngine  # noqa: E402
from dht_app.detail_schema import (  # noqa: E402
    DECIMAL_TENTHS_STYLE,
    TRIGGER_DETAIL_GROUPS,
    detail_value_from_slider,
    format_detail_value,
    grouped_numeric_details,
    grouped_option_details,
)
from dht_app.haptic_effect_engine import HapticEffectEngine  # noqa: E402
from dht_app.output_event_payloads import OutputEventPayload, event  # noqa: E402
from dht_app.preset_loader import load_builtin_presets_into_state  # noqa: E402
from dht_app.settings_io import apply_app_state_snapshot, export_app_state  # noqa: E402
from dht_app.settings_model import EffectSetting  # noqa: E402
from dht_app.telemetry_frame import TelemetryFrame  # noqa: E402
from dht_app.tooltip_texts import detail_tooltip  # noqa: E402
from dht_app.trigger_effect_engine import TriggerEffectEngine  # noqa: E402


class Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


CLOCK = Clock()
haptic_module.monotonic = CLOCK
trigger_module.monotonic = CLOCK
drift_module.monotonic = CLOCK


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _frame(**overrides: object) -> TelemetryFrame:
    values: dict[str, object] = {
        "game_mode": GameMode.HORIZON,
        "parser_name": "trigger-release-fix",
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
        "wheel_rotation_speed_fl": 100.0,
        "wheel_rotation_speed_fr": 100.0,
        "wheel_rotation_speed_rl": 100.0,
        "wheel_rotation_speed_rr": 100.0,
        "speed": 100.0,
        "rpm": 5000.0,
        "gear": 3,
        "throttle": 0.0,
        "brake": 0.0,
        "clutch": 0.0,
        "handbrake": 0.0,
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
        "smashable_vel_diff": 0.0,
        "smashable_mass": 0.0,
        "car_ordinal": 100,
        "car_class": 3,
        "drive_train": 1,
    }
    values.update(overrides)
    return TelemetryFrame(**values)


def _payload_names(payloads: tuple[OutputEventPayload, ...]) -> set[str]:
    return {payload.name for payload in payloads}


def _payload_fields(payload: OutputEventPayload) -> dict[str, str]:
    return dict(payload.params)


def _payload_output_fields(payload: OutputEventPayload) -> dict[str, str]:
    fields = _payload_fields(payload)
    fields.pop("ts", None)
    return fields


def _only_trigger_effect(
    settings: dict[str, EffectSetting],
    name: str,
    value: int,
) -> dict[str, EffectSetting]:
    result = copy.deepcopy(settings)
    for setting in result.values():
        setting.enabled = False
    result[name].enabled = True
    result[name].value = value
    return result


def _all_haptics_disabled(settings: dict[str, EffectSetting]) -> dict[str, EffectSetting]:
    result = copy.deepcopy(settings)
    for setting in result.values():
        setting.enabled = False
    return result


def verify_l2_exclusivity(state: AppState) -> None:
    for selected in BRAKE_TRIGGER_EFFECT_NAMES:
        if not state.trigger_effects[selected].enabled:
            state.toggle_trigger_effect(selected)
        active = [name for name in BRAKE_TRIGGER_EFFECT_NAMES if state.trigger_effects[name].enabled]
        _assert(active == [selected], f"L2 toggle exclusivity failed for {selected}: {active}")

    corrupt = state.game_profiles[state.game_mode].presets[state.selected_preset]
    for name in BRAKE_TRIGGER_EFFECT_NAMES:
        corrupt.trigger_effects[name].enabled = True
    state.selected_trigger_effect = "Brake Resistance - Predictive"
    state.load_game_profile(state.game_mode)
    active = [name for name in BRAKE_TRIGGER_EFFECT_NAMES if state.trigger_effects[name].enabled]
    _assert(active == ["Brake Resistance - Predictive"], f"L2 load normalization failed: {active}")

    settings = copy.deepcopy(state.trigger_effects)
    for setting in settings.values():
        setting.enabled = False
    for name in BRAKE_TRIGGER_EFFECT_NAMES:
        settings[name].enabled = True
        settings[name].value = 10
    combined = TriggerEffectEngine().process_frame(_frame(brake=255.0), settings)
    predictive_only = _only_trigger_effect(settings, "Brake Resistance - Predictive", 10)
    predictive = TriggerEffectEngine().process_frame(_frame(brake=255.0), predictive_only)
    _assert(combined and predictive, "L2 defensive engine output missing.")
    _assert(
        _payload_fields(combined[0])["force"] == _payload_fields(predictive[0])["force"],
        "L2 engine did not prioritize one brake algorithm defensively.",
    )


def verify_predictive_handbrake_base_resistance(state: AppState) -> None:
    predictive_name = "Brake Resistance - Predictive"
    settings = _only_trigger_effect(state.trigger_effects, predictive_name, 10)
    setting = settings[predictive_name]
    details = setting.details or {}
    base_wall = trigger_module._detail_int(details, "start_percent", 40, 40, 100)
    expected_start = trigger_module._wall_position_percent_to_start_byte(float(base_wall))
    expected_force = round(
        255.0 * trigger_module._detail_int(details, "force_percent", 70, 0, 100) / 100.0
    )

    high_slip_frame = _frame(
        brake=180.0,
        handbrake=0.0,
        tire_slip_ratio_fl=1.5,
        tire_slip_ratio_fr=1.5,
        tire_combined_slip_fl=1.5,
        tire_combined_slip_fr=1.5,
    )
    engine = TriggerEffectEngine()
    baseline = engine.process_frame(high_slip_frame, settings)
    _assert(baseline, "Predictive brake baseline payload was missing.")

    handbrake = engine.process_frame(
        _frame(
            brake=180.0,
            handbrake=255.0,
            tire_slip_ratio_fl=2.0,
            tire_slip_ratio_fr=2.0,
            tire_combined_slip_fl=2.0,
            tire_combined_slip_fr=2.0,
        ),
        settings,
    )
    _assert(handbrake, "Predictive brake handbrake payload was missing.")
    fields = _payload_output_fields(handbrake[0])
    _assert(
        int(fields["force"]) == expected_force,
        f"Handbrake did not retain predictive base force: {fields}",
    )
    _assert(
        int(fields.get("start", -1)) == expected_start,
        f"Handbrake did not retain predictive base wall: {fields}",
    )
    for key in ("pulse", "pulseRate", "vibrateAmp", "vibrateFreq", "vibrateStartZone"):
        _assert(int(fields[key]) == 0, f"Handbrake left predictive modulation active: {fields}")
    _assert(
        engine.brake_predictive_state.wall_start_percent == float(base_wall),
        "Handbrake did not reset predictive state to the configured base wall.",
    )

    resumed = engine.process_frame(_frame(brake=180.0, handbrake=0.0), settings)
    _assert(
        resumed and int(_payload_output_fields(resumed[0])["force"]) > 0,
        "Predictive brake did not resume after releasing the handbrake.",
    )

    basic_name = "Brake Resistance"
    basic_settings = _only_trigger_effect(state.trigger_effects, basic_name, 10)
    normal_basic = TriggerEffectEngine().process_frame(
        _frame(brake=180.0, handbrake=0.0),
        basic_settings,
    )
    handbrake_basic = TriggerEffectEngine().process_frame(
        _frame(brake=180.0, handbrake=255.0),
        basic_settings,
    )
    _assert(
        normal_basic
        and handbrake_basic
        and _payload_output_fields(normal_basic[0])["force"]
        == _payload_output_fields(handbrake_basic[0])["force"],
        "Basic Brake Resistance changed during the predictive handbrake fix.",
    )


def _configure_semantic_slip_details(setting: EffectSetting, *, include_end: bool = False) -> None:
    setting.enabled = True
    setting.value = 10
    setting.details.update(
        {
            "enabled": True,
            "force_percent": 70,
            "start_percent": 40,
            "max_percent": 45,
            "wall_percent": 0,
            "slip_off": True,
            "slip_threshold": 1.0,
            "slip_drop_low_percent": 0,
            "slip_pulse_enabled": True,
            "slip_pulse_style": "Soft Pulse",
            "slip_pulse_start_percent": 70,
            "slip_pulse_end_percent": 120,
            "slip_soft_pulse_amplitude": 3,
            "slip_soft_pulse_frequency": 40,
            "slip_soft_pulse_start_zone": 0,
        }
    )
    if include_end:
        setting.details["slip_end_threshold"] = 3.0


def _pulse_is_active(pulse: trigger_module.TriggerPulseOutput) -> bool:
    return pulse.pulse > 0 or pulse.vibrate_amp > 0


def verify_semantic_slip_threshold_units(state: AppState) -> None:
    throttle = copy.deepcopy(state.trigger_effects["Throttle Resistance - Traction"])
    _configure_semantic_slip_details(throttle, include_end=True)

    low_throttle_engine = TriggerEffectEngine()
    low_throttle_engine._throttle_traction_force(
        _frame(
            throttle=255.0,
            tire_slip_ratio_rl=0.09,
            tire_slip_ratio_rr=0.09,
            tire_combined_slip_rl=0.09,
            tire_combined_slip_rr=0.09,
        ),
        throttle,
    )
    _assert(
        not _pulse_is_active(low_throttle_engine.throttle_traction_state.pulse_output),
        "Throttle semantic threshold 1.0 was treated as the legacy fixed-point value 0.1.",
    )

    window_throttle_engine = TriggerEffectEngine()
    window_throttle_engine._throttle_traction_force(
        _frame(
            throttle=255.0,
            tire_slip_ratio_rl=0.90,
            tire_slip_ratio_rr=0.90,
            tire_combined_slip_rl=0.90,
            tire_combined_slip_rr=0.90,
        ),
        throttle,
    )
    _assert(
        _pulse_is_active(window_throttle_engine.throttle_traction_state.pulse_output),
        "Throttle semantic threshold 1.0 did not preserve its configured pulse window.",
    )

    no_pulse_throttle = copy.deepcopy(throttle)
    no_pulse_throttle.details["slip_pulse_enabled"] = False
    end_force = TriggerEffectEngine()._throttle_traction_force(
        _frame(
            throttle=255.0,
            tire_slip_ratio_rl=1.50,
            tire_slip_ratio_rr=1.50,
            tire_combined_slip_rl=1.50,
            tire_combined_slip_rr=1.50,
        ),
        no_pulse_throttle,
    )
    _assert(
        end_force > 0,
        "Throttle slip-end threshold 3.0 was treated as the legacy fixed-point value 0.3.",
    )

    brake = copy.deepcopy(state.trigger_effects["Brake Resistance"])
    _configure_semantic_slip_details(brake)
    low_brake_engine = TriggerEffectEngine()
    low_brake_engine._brake_resistance_force(
        _frame(
            brake=255.0,
            tire_slip_ratio_fl=0.09,
            tire_slip_ratio_fr=0.09,
            tire_combined_slip_fl=0.09,
            tire_combined_slip_fr=0.09,
        ),
        brake,
    )
    _assert(
        not _pulse_is_active(low_brake_engine.brake_resistance_pulse),
        "Brake Resistance threshold 1.0 was treated as the legacy fixed-point value 0.1.",
    )

    window_brake_engine = TriggerEffectEngine()
    window_brake_engine._brake_resistance_force(
        _frame(
            brake=255.0,
            tire_slip_ratio_fl=0.90,
            tire_slip_ratio_fr=0.90,
            tire_combined_slip_fl=0.90,
            tire_combined_slip_fr=0.90,
        ),
        brake,
    )
    _assert(
        _pulse_is_active(window_brake_engine.brake_resistance_pulse),
        "Brake Resistance threshold 1.0 did not preserve its configured pulse window.",
    )

    predictive = copy.deepcopy(state.trigger_effects["Brake Resistance - Predictive"])
    _configure_semantic_slip_details(predictive)
    low_predictive_engine = TriggerEffectEngine()
    low_predictive_engine._brake_resistance_predictive_force(
        _frame(
            brake=255.0,
            tire_slip_ratio_fl=0.09,
            tire_slip_ratio_fr=0.09,
            tire_combined_slip_fl=0.09,
            tire_combined_slip_fr=0.09,
        ),
        predictive,
    )
    _assert(
        not _pulse_is_active(low_predictive_engine.brake_predictive_pulse),
        "Predictive Brake Resistance threshold 1.0 was treated as the legacy fixed-point value 0.1.",
    )

    window_predictive_engine = TriggerEffectEngine()
    window_predictive_engine._brake_resistance_predictive_force(
        _frame(
            brake=255.0,
            tire_slip_ratio_fl=0.90,
            tire_slip_ratio_fr=0.90,
            tire_combined_slip_fl=0.90,
            tire_combined_slip_fr=0.90,
        ),
        predictive,
    )
    _assert(
        _pulse_is_active(window_predictive_engine.brake_predictive_pulse),
        "Predictive Brake Resistance threshold 1.0 did not preserve its configured pulse window.",
    )

    roundtrip = AppState()
    load_builtin_presets_into_state(roundtrip)
    roundtrip.trigger_effects["Throttle Resistance - Traction"].details["slip_threshold"] = 1.0
    roundtrip.trigger_effects["Throttle Resistance - Traction"].details["slip_end_threshold"] = 3.0
    roundtrip.trigger_effects["Brake Resistance"].details["slip_threshold"] = 1.0
    roundtrip.trigger_effects["Brake Resistance - Predictive"].details["slip_threshold"] = 1.0
    roundtrip.sync_current_game_profile()
    snapshot = export_app_state(roundtrip)
    restored = AppState()
    load_builtin_presets_into_state(restored)
    apply_app_state_snapshot(restored, snapshot)
    _assert(
        float(restored.trigger_effects["Throttle Resistance - Traction"].details["slip_threshold"]) == 1.0
        and float(restored.trigger_effects["Throttle Resistance - Traction"].details["slip_end_threshold"]) == 3.0
        and float(restored.trigger_effects["Brake Resistance"].details["slip_threshold"]) == 1.0
        and float(restored.trigger_effects["Brake Resistance - Predictive"].details["slip_threshold"]) == 1.0,
        "Semantic slip thresholds changed during settings export/import.",
    )


def verify_trigger_detail_schema_and_defaults(state: AppState) -> None:
    predictive_details = copy.deepcopy(state.trigger_effects["Brake Resistance - Predictive"].details)
    predictive_details["slip_threshold"] = 1.5
    groups = grouped_numeric_details(
        "Brake Resistance - Predictive",
        predictive_details,
        TRIGGER_DETAIL_GROUPS,
    )
    rows = {row.key: row for group in groups for row in group.rows}
    threshold = rows["slip_threshold"]
    _assert(
        (
            threshold.value,
            threshold.minimum,
            threshold.maximum,
            threshold.display_style,
        )
        == (15, 1, 50, DECIMAL_TENTHS_STYLE),
        f"Slip Threshold fixed-point UI mapping is incorrect: {threshold}",
    )
    _assert(
        format_detail_value(threshold.display_style, threshold.value) == "1.5"
        and detail_value_from_slider(threshold.display_style, threshold.value) == 1.5,
        "Slip Threshold UI display/callback did not preserve its semantic decimal value.",
    )

    setter_state = AppState()
    load_builtin_presets_into_state(setter_state)
    setter_state.selected_trigger_effect = "Brake Resistance - Predictive"
    setter_state.set_trigger_detail_value("slip_threshold", 1.5)
    _assert(
        setter_state.trigger_effects["Brake Resistance - Predictive"].details["slip_threshold"] == 1.5,
        "AppState rounded Slip Threshold back to an integer.",
    )
    setter_state.set_trigger_detail_value("slip_threshold", 0.0)
    _assert(
        setter_state.trigger_effects["Brake Resistance - Predictive"].details["slip_threshold"] == 0.1,
        "AppState did not clamp Slip Threshold to the legacy 0.1 minimum.",
    )
    setter_state.set_trigger_detail_value("slip_threshold", 12.0)
    _assert(
        setter_state.trigger_effects["Brake Resistance - Predictive"].details["slip_threshold"] == 5.0,
        "AppState did not clamp Slip Threshold to the legacy 5.0 maximum.",
    )

    restored_external = AppState()
    load_builtin_presets_into_state(restored_external)
    apply_app_state_snapshot(
        restored_external,
        {
            "trigger_effects": {
                "Brake Resistance - Predictive": {
                    "enabled": True,
                    "details": {"slip_threshold": 7, "slip_end_threshold": 1.55},
                },
                "Brake Resistance": {
                    "enabled": False,
                    "details": {"slip_threshold": 12},
                },
            }
        },
    )
    restored_external_details = restored_external.trigger_effects["Brake Resistance - Predictive"].details
    _assert(
        restored_external_details["slip_threshold"] == 1.5
        and restored_external_details["slip_end_threshold"] == 1.6,
        f"Known Predictive threshold workaround was not migrated: {restored_external_details}",
    )
    _assert(
        restored_external.trigger_effects["Brake Resistance"].details["slip_threshold"] == 5.0,
        "Imported threshold above the supported range was not clamped to 5.0.",
    )

    external_predictive = copy.deepcopy(state.trigger_effects["Brake Resistance - Predictive"])
    _configure_semantic_slip_details(external_predictive)
    external_predictive.details["slip_threshold"] = 12.0
    external_engine = TriggerEffectEngine()
    external_engine._brake_resistance_predictive_force(
        _frame(
            brake=255.0,
            tire_slip_ratio_fl=4.0,
            tire_slip_ratio_fr=4.0,
            tire_combined_slip_fl=4.0,
            tire_combined_slip_fr=4.0,
        ),
        external_predictive,
    )
    _assert(
        _pulse_is_active(external_engine.brake_predictive_pulse),
        "Runtime did not clamp an external Slip Threshold above 5.0 to the supported range.",
    )

    external_throttle = copy.deepcopy(state.trigger_effects["Throttle Resistance - Traction"])
    _configure_semantic_slip_details(external_throttle, include_end=True)
    external_throttle.details["slip_end_threshold"] = 12.0
    external_throttle.details["slip_pulse_enabled"] = False
    external_end_force = TriggerEffectEngine()._throttle_traction_force(
        _frame(
            throttle=255.0,
            tire_slip_ratio_rl=6.0,
            tire_slip_ratio_rr=6.0,
            tire_combined_slip_rl=6.0,
            tire_combined_slip_rr=6.0,
        ),
        external_throttle,
    )
    _assert(
        external_end_force == 0,
        "Runtime did not clamp an external Slip Off End above 5.0 to the supported range.",
    )

    hidden_rows = {
        "Brake Pressure": {"curve"},
        "Brake Resistance": {"slip_pulse_rate"},
        "Brake Resistance - Predictive": {"slip_pulse_rate"},
        "Throttle Pressure": {"curve", "pulse_strength", "pulse_start_percent", "pulse_rate"},
        "Throttle Resistance - Traction": {"slip_pulse_rate", "slip_low_percent"},
        "Acceleration G Punch": {
            "pulse_start_percent",
            "slip_soft_pulse_amplitude",
            "slip_strong_pulse_amplitude",
        },
        "RPM Rev Limit": {"force_percent"},
    }
    for effect_name, hidden_keys in hidden_rows.items():
        exposed = {
            key
            for _title, keys in TRIGGER_DETAIL_GROUPS[effect_name]
            for key in keys
        }
        _assert(
            exposed.isdisjoint(hidden_keys),
            f"{effect_name} still exposes inactive or duplicate controls: {sorted(exposed & hidden_keys)}",
        )

    for effect_name in (
        "Brake Resistance",
        "Brake Resistance - Predictive",
        "Throttle Resistance - Traction",
    ):
        option_groups = grouped_option_details(effect_name, state.trigger_effects[effect_name].details)
        pulse_type = next(row for group in option_groups for row in group.rows if row.key == "slip_pulse_style")
        _assert(
            pulse_type.options == ("Soft Pulse", "Strong Pulse"),
            f"{effect_name} still exposes the legacy-hidden Pulse Kick path: {pulse_type.options}",
        )

    gear_options = grouped_option_details("Gear Shift Kick", state.trigger_effects["Gear Shift Kick"].details)
    gear_option_rows = {row.key: row for group in gear_options for row in group.rows}
    _assert(
        gear_option_rows["upshift_sides"].options == ("Left", "Right", "Both")
        and gear_option_rows["downshift_sides"].options == ("Left", "Right", "Both"),
        "Gear Shift Kick side selectors are missing or incomplete.",
    )
    for language in ("EN", "KR", "CN", "ES"):
        _assert(
            "0.1" in detail_tooltip("slip_threshold", language)
            and detail_tooltip("upshift_sides", language).strip(),
            f"{language} trigger range/side inline description is missing.",
        )

    accel = copy.deepcopy(state.trigger_effects["Acceleration G Punch"])
    accel.details.update(
        {
            "slip_pulse_enabled": True,
            "pulse_strength": 80,
            "slip_pulse_style": "Strong Pulse",
            "slip_strong_pulse_amplitude": 1,
            "slip_strong_pulse_rate": 77,
        }
    )
    strong_output = TriggerEffectEngine._accel_g_punch_pulse_output(accel, 0.5)
    _assert(
        strong_output.pulse == 102 and strong_output.pulse_rate == 77,
        f"Acceleration G Punch Strong Pulse is not controlled directly by Pulse Strength: {strong_output}",
    )
    accel.details.update(
        {
            "pulse_strength": 75,
            "slip_pulse_style": "Soft Pulse",
            "slip_soft_pulse_amplitude": 1,
            "slip_soft_pulse_frequency": 43,
            "slip_soft_pulse_start_zone": 2,
        }
    )
    soft_output = TriggerEffectEngine._accel_g_punch_pulse_output(accel, 0.5)
    _assert(
        soft_output.vibrate_amp == 3
        and soft_output.vibrate_freq == 43
        and soft_output.vibrate_start_zone == 2,
        f"Acceleration G Punch Soft Pulse is not controlled directly by Pulse Strength: {soft_output}",
    )

    expected_ranges = {
        ("Brake Resistance - Predictive", "start_percent"): (40, 100),
        ("Brake Resistance - Predictive", "max_percent"): (30, 95),
        ("Brake Resistance - Predictive", "wall_percent"): (0, 40),
        ("Throttle Resistance - Traction", "max_percent"): (20, 95),
        ("Gear Shift Kick", "upshift_duration_ms"): (20, 180),
        ("Gear Shift Kick", "release_duration_ms"): (0, 120),
        ("Collision Kick", "smooth_start_ms"): (40, 300),
        ("Acceleration G Punch", "pulse_gear_1_percent"): (0, 150),
        ("Acceleration G Punch", "smooth_start_ms"): (0, 200),
        ("RPM Rev Limit", "start_percent"): (80, 99),
        ("Impact Tick", "smooth_start_ms"): (40, 300),
    }
    for (effect_name, key), expected_range in expected_ranges.items():
        effect_groups = grouped_numeric_details(
            effect_name,
            state.trigger_effects[effect_name].details,
            TRIGGER_DETAIL_GROUPS,
        )
        effect_rows = {row.key: row for group in effect_groups for row in group.rows}
        row = effect_rows[key]
        _assert(
            (row.minimum, row.maximum) == expected_range,
            f"{effect_name}/{key} UI range {(row.minimum, row.maximum)} != runtime range {expected_range}.",
        )

    preset_root = PROJECT_ROOT / "dht_app" / "config_presets"
    preset_paths = sorted(preset_root.glob("*.json"))
    preset_paths.extend(sorted((preset_root / "horizon").glob("*.json")))
    preset_paths.extend(sorted((preset_root / "motorsport").glob("*.json")))
    _assert(len(preset_paths) == 18, f"Expected 18 source preset files, got {len(preset_paths)}.")
    for preset_path in preset_paths:
        payload = json.loads(preset_path.read_text(encoding="utf-8"))
        preset_trigger_effects = payload["trigger_effects"]
        predictive = preset_trigger_effects["Brake Resistance - Predictive"]
        value = predictive["slip_threshold"]
        _assert(
            float(value) == 1.5,
            f"{preset_path.relative_to(PROJECT_ROOT)} still carries the temporary threshold {value}.",
        )
        _assert(
            int(predictive["start_percent"]) == 40,
            f"{preset_path.relative_to(PROJECT_ROOT)} has a Predictive start position that runtime would silently clamp.",
        )
        for effect_name, details in preset_trigger_effects.items():
            if effect_name not in TRIGGER_DETAIL_GROUPS or not isinstance(details, dict):
                continue
            preset_groups = grouped_numeric_details(
                effect_name,
                details,
                TRIGGER_DETAIL_GROUPS,
            )
            for group in preset_groups:
                for row in group.rows:
                    _assert(
                        row.minimum <= row.value <= row.maximum,
                        (
                            f"{preset_path.relative_to(PROJECT_ROOT)} {effect_name}/{row.key} "
                            f"is outside its runtime range: {row.value} not in "
                            f"{row.minimum}..{row.maximum}."
                        ),
                    )


def verify_haptic_independent_sources(state: AppState) -> dict[str, OutputEventPayload]:
    haptic_settings = _all_haptics_disabled(state.haptic_effects)
    sources: dict[str, OutputEventPayload] = {}

    gear_engine = HapticEffectEngine()
    gear_engine.process_frame(_frame(gear=3), haptic_settings)
    CLOCK.advance(0.02)
    gear_payloads = gear_engine.process_frame(_frame(gear=4), haptic_settings)
    _assert(not gear_payloads, "Disabled gear haptics unexpectedly emitted audio payloads.")
    _assert("GEAR_SHIFT" in _payload_names(gear_engine.last_source_payloads), "Gear source was not detected.")
    sources["GEAR_SHIFT"] = next(p for p in gear_engine.last_source_payloads if p.name == "GEAR_SHIFT")

    kerb_engine = HapticEffectEngine()
    kerb_payloads = kerb_engine.process_frame(
        _frame(wheel_on_rumble_strip_fl=1, surface_rumble_fl=0.23),
        haptic_settings,
    )
    _assert(not kerb_payloads, "Disabled kerb haptic unexpectedly emitted audio payloads.")
    _assert("RUMBLE_KERBS" in _payload_names(kerb_engine.last_source_payloads), "Kerb source was not detected.")
    sources["RUMBLE_KERBS"] = next(p for p in kerb_engine.last_source_payloads if p.name == "RUMBLE_KERBS")

    impact_engine = HapticEffectEngine()
    impact_engine.process_frame(_frame(speed=100.0, accel_z=0.0), haptic_settings)
    CLOCK.advance(0.04)
    impact_payloads = impact_engine.process_frame(_frame(speed=45.0, accel_z=420.0), haptic_settings)
    _assert(not impact_payloads, "Disabled impact haptic unexpectedly emitted audio payloads.")
    _assert("IMPACT" in _payload_names(impact_engine.last_source_payloads), "Wall impact source was not detected.")
    sources["IMPACT"] = next(p for p in impact_engine.last_source_payloads if p.name == "IMPACT")

    smash_engine = HapticEffectEngine()
    smash_engine.process_frame(_frame(smashable_vel_diff=0.0), haptic_settings)
    CLOCK.advance(0.02)
    smash_payloads = smash_engine.process_frame(
        _frame(smashable_vel_diff=0.20, smashable_mass=25.0),
        haptic_settings,
    )
    _assert(not smash_payloads, "Disabled smash haptic unexpectedly emitted audio payloads.")
    _assert("IMPACT_SMASHABLE" in _payload_names(smash_engine.last_source_payloads), "Smash source was not detected.")
    sources["IMPACT_SMASHABLE"] = next(
        p for p in smash_engine.last_source_payloads if p.name == "IMPACT_SMASHABLE"
    )
    return sources


def verify_transient_producers_and_legacy_value_compatibility(
    state: AppState,
    sources: dict[str, OutputEventPayload],
) -> None:
    cases = (
        ("Gear Shift Kick", sources["GEAR_SHIFT"], "TRIGGER_GEAR_SHIFT"),
        ("Collision Kick", sources["IMPACT"], "TRIGGER_COLLISION_KICK"),
        ("Kerb Wave", sources["RUMBLE_KERBS"], "TRIGGER_KERB_BUZZ"),
        ("Impact Tick", sources["IMPACT_SMASHABLE"], "TRIGGER_IMPACT_TICK"),
    )
    for effect_name, source, expected_event in cases:
        high_settings = _only_trigger_effect(state.trigger_effects, effect_name, 10)
        high = TriggerEffectEngine().process_frame(_frame(), high_settings, (source,))
        _assert(expected_event in _payload_names(high), f"{effect_name} producer missing: {_payload_names(high)}")

        legacy_zero_settings = _only_trigger_effect(state.trigger_effects, effect_name, 0)
        legacy_zero = TriggerEffectEngine().process_frame(_frame(), legacy_zero_settings, (source,))
        _assert(
            expected_event in _payload_names(legacy_zero),
            f"{effect_name} was incorrectly disabled by the legacy value field.",
        )
        high_payload = next(payload for payload in high if payload.name == expected_event)
        legacy_zero_payload = next(payload for payload in legacy_zero if payload.name == expected_event)
        _assert(
            _payload_output_fields(high_payload) == _payload_output_fields(legacy_zero_payload),
            f"{effect_name} output still depends on the legacy value field.",
        )

    gear_settings = _only_trigger_effect(state.trigger_effects, "Gear Shift Kick", 10)
    gear_settings["Gear Shift Kick"].details["early_input_soft_zone"] = 60
    released_engine = TriggerEffectEngine()
    released_engine.update_trigger_input(0.0, 0.0, CLOCK.value)
    released = released_engine.process_frame(_frame(), gear_settings, (sources["GEAR_SHIFT"],))
    pressed_engine = TriggerEffectEngine()
    pressed_engine.update_trigger_input(0.0, 60.0, CLOCK.value)
    pressed = pressed_engine.process_frame(_frame(), gear_settings, (sources["GEAR_SHIFT"],))
    released_strength = int(_payload_fields(released[0])["strength"])
    pressed_strength = int(_payload_fields(pressed[0])["strength"])
    _assert(
        0 < released_strength < pressed_strength,
        f"Gear early-input soft zone did not react to trigger position: {released_strength}/{pressed_strength}",
    )

    kerb_settings = _only_trigger_effect(state.trigger_effects, "Kerb Wave", 10)
    engine = TriggerEffectEngine()
    active = engine.process_frame(_frame(), kerb_settings, (sources["RUMBLE_KERBS"],))
    _assert("TRIGGER_KERB_BUZZ" in _payload_names(active), "Kerb wave active state missing.")
    release_source = event("RUMBLE_KERBS", fl=0.0, fr=0.0, speed=100.0)
    released = engine.process_frame(_frame(), kerb_settings, (release_source,))
    release = next((p for p in released if p.name == "TRIGGER_KERB_BUZZ"), None)
    _assert(release is not None, "Kerb wave release event missing.")
    fields = _payload_fields(release)
    _assert(fields["left"] == "0" and fields["right"] == "0", "Kerb wave release was not zeroed.")


def verify_kerb_wave_shared_tuning_and_side_switches(
    state: AppState,
    source: OutputEventPayload,
) -> None:
    settings = _only_trigger_effect(state.trigger_effects, "Kerb Wave", 10)
    details = settings["Kerb Wave"].details
    details.update(
        {
            "kerb_l_enabled": True,
            "kerb_r_enabled": True,
            "kerb_l_start_percent": 20,
            "kerb_r_start_percent": 90,
            "kerb_low_hz": 10,
            "kerb_high_hz": 40,
            "kerb_l_low_hz": 70,
            "kerb_l_high_hz": 90,
            "kerb_r_low_hz": 110,
            "kerb_r_high_hz": 130,
            "kerb_l_low_amp": 1,
            "kerb_l_high_amp": 8,
            "kerb_r_low_amp": 8,
            "kerb_r_high_amp": 1,
        }
    )
    payloads = TriggerEffectEngine().process_frame(_frame(), settings, (source,))
    payload = next((item for item in payloads if item.name == "TRIGGER_KERB_BUZZ"), None)
    _assert(payload is not None, "Kerb Wave shared-output payload is missing.")
    fields = _payload_fields(payload)
    _assert(fields["left"] == "1" and fields["right"] == "1", "Kerb Wave did not enable both trigger sides.")
    _assert(fields["leftAmp"] == fields["rightAmp"], "Kerb Wave L2/R2 amplitudes are not shared.")
    _assert(fields["leftFreq"] == fields["rightFreq"], "Kerb Wave L2/R2 frequencies are not shared.")
    _assert(fields["leftStartZone"] == fields["rightStartZone"], "Kerb Wave L2/R2 start positions are not shared.")

    for left_enabled, right_enabled in ((False, True), (True, False)):
        side_settings = copy.deepcopy(settings)
        side_details = side_settings["Kerb Wave"].details
        side_details["kerb_l_enabled"] = left_enabled
        side_details["kerb_r_enabled"] = right_enabled
        side_payloads = TriggerEffectEngine().process_frame(_frame(), side_settings, (source,))
        side_payload = next((item for item in side_payloads if item.name == "TRIGGER_KERB_BUZZ"), None)
        _assert(side_payload is not None, "Kerb Wave side-switch payload is missing.")
        side_fields = _payload_fields(side_payload)
        _assert(side_fields["left"] == ("1" if left_enabled else "0"), "Kerb Wave L2 ON switch was ignored.")
        _assert(side_fields["right"] == ("1" if right_enabled else "0"), "Kerb Wave R2 ON switch was ignored.")

    state.selected_trigger_effect = "Kerb Wave"
    mirror_cases = {
        "kerb_l_start_percent": (33, ("kerb_l_start_percent", "kerb_r_start_percent")),
        "kerb_low_hz": (14, ("kerb_low_hz", "kerb_l_low_hz", "kerb_r_low_hz")),
        "kerb_high_hz": (52, ("kerb_high_hz", "kerb_l_high_hz", "kerb_r_high_hz")),
        "kerb_l_low_amp": (3, ("kerb_l_low_amp", "kerb_r_low_amp")),
        "kerb_l_high_amp": (7, ("kerb_l_high_amp", "kerb_r_high_amp")),
    }
    for visible_key, (value, mirrored_keys) in mirror_cases.items():
        state.set_trigger_detail_value(visible_key, value)
        current_details = state.trigger_effects["Kerb Wave"].details
        _assert(
            all(current_details.get(key) == value for key in mirrored_keys),
            f"Kerb Wave shared setting did not mirror {visible_key}: {mirrored_keys}",
        )
    state.set_trigger_detail_value("kerb_l_enabled", False)
    state.set_trigger_detail_value("kerb_r_enabled", True)
    _assert(state.trigger_effects["Kerb Wave"].details["kerb_l_enabled"] is False, "Kerb Wave L2 switch was not stored independently.")
    _assert(state.trigger_effects["Kerb Wave"].details["kerb_r_enabled"] is True, "Kerb Wave R2 switch was not stored independently.")

    snapshot = export_app_state(state)
    restored_state = AppState()
    load_builtin_presets_into_state(restored_state)
    apply_app_state_snapshot(restored_state, snapshot)
    restored_details = restored_state.trigger_effects["Kerb Wave"].details
    _assert(restored_details.get("kerb_l_enabled") is False, "Saved Kerb Wave L2 switch was not restored.")
    _assert(restored_details.get("kerb_r_enabled") is True, "Saved Kerb Wave R2 switch was not restored.")
    for _visible_key, (value, mirrored_keys) in mirror_cases.items():
        _assert(
            all(restored_details.get(key) == value for key in mirrored_keys),
            f"Saved Kerb Wave shared value was not restored: {mirrored_keys}",
        )


def verify_drift_fade(state: AppState) -> None:
    setting = copy.deepcopy(state.trigger_effects["Drift Rumble Fade"])
    setting.enabled = True
    setting.value = 0
    engine = DriftRumbleFadeEngine()
    drift_frame = _frame(
        speed=105.0,
        throttle=230.0,
        steer=58.0,
        accel_x=10.0,
        angular_velocity_y=1.35,
        tire_slip_angle_fl=0.10,
        tire_slip_angle_fr=0.10,
        tire_slip_angle_rl=1.55,
        tire_slip_angle_rr=1.50,
        tire_combined_slip_fl=0.35,
        tire_combined_slip_fr=0.35,
        tire_combined_slip_rl=2.50,
        tire_combined_slip_rr=2.40,
        tire_slip_ratio_rl=2.60,
        tire_slip_ratio_rr=2.45,
        wheel_rotation_speed_fl=100.0,
        wheel_rotation_speed_fr=100.0,
        wheel_rotation_speed_rl=190.0,
        wheel_rotation_speed_rr=188.0,
    )
    gains: dict[str, float] = {}
    for _ in range(100):
        gains = engine.update(drift_frame, setting)
        CLOCK.advance(0.05)
    _assert(engine.active and engine.suppression_active, "Drift Rumble Fade did not enter sustained-drift suppression.")
    _assert(gains and min(gains.values()) < 1.0, f"Drift Rumble Fade gains were not produced: {gains}")

    pressure = copy.deepcopy(state.trigger_effects["Throttle Pressure"])
    pressure.enabled = True
    pressure.value = 0
    settings = {name: EffectSetting(0, False, {}) for name in state.trigger_effects}
    settings["Throttle Pressure"] = pressure
    no_fade = TriggerEffectEngine().process_frame(_frame(throttle=255.0), settings)
    full_fade = TriggerEffectEngine().process_frame(
        _frame(throttle=255.0),
        settings,
        effect_gains={"Throttle Pressure": 0.0},
    )
    _assert(no_fade and full_fade, "Throttle Pressure comparison payload missing.")
    _assert(int(_payload_fields(no_fade[0])["force"]) > 0, "Throttle Pressure baseline was zero.")
    _assert(int(_payload_fields(full_fade[0])["force"]) == 0, "Drift fade did not scale trigger force.")

    _assert(gains, "Drift Rumble Fade was incorrectly disabled by the legacy value field.")
    setting.enabled = False
    _assert(engine.update(drift_frame, setting) == {}, "Drift Rumble Fade ON/OFF switch did not disable the filter.")


def main() -> None:
    state = AppState()
    report = load_builtin_presets_into_state(state)
    _assert(report.loaded_files == 12, f"Expected 12 built-in presets, got {report.loaded_files}.")
    verify_l2_exclusivity(state)
    verify_predictive_handbrake_base_resistance(state)
    verify_semantic_slip_threshold_units(state)
    verify_trigger_detail_schema_and_defaults(state)
    sources = verify_haptic_independent_sources(state)
    verify_transient_producers_and_legacy_value_compatibility(state, sources)
    verify_kerb_wave_shared_tuning_and_side_switches(state, sources["RUMBLE_KERBS"])
    verify_drift_fade(state)
    print("PASS: Trigger release fixes verified (semantic 0.1-step slip thresholds, runtime-matched UI ranges, Acceleration G Punch pulse parity, no inactive controls, Gear Shift sides, preset defaults, L2 exclusivity, predictive handbrake base hold, 5 producers, Kerb shared output, ON/OFF-only output, drift fade).")


if __name__ == "__main__":
    main()
