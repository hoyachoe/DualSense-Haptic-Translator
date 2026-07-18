from __future__ import annotations

from dataclasses import dataclass
from numbers import Number
from typing import Any


@dataclass(frozen=True)
class DetailRowSpec:
    label: str
    key: str
    value: int
    minimum: int
    maximum: int
    display_style: str = ""


@dataclass(frozen=True)
class DetailGroupSpec:
    title: str
    rows: tuple[DetailRowSpec, ...]


@dataclass(frozen=True)
class DetailOptionSpec:
    label: str
    key: str
    value: bool | str
    kind: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class DetailOptionGroupSpec:
    title: str
    rows: tuple[DetailOptionSpec, ...]


HAPTIC_DETAIL_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Gear Shift Bite - Core": (
        ("Shape", ("balance", "punch", "length", "tail", "tone")),
    ),
    "Gear Shift Bite - High Hz": (
        ("Shape", ("balance", "punch", "length", "tail", "tone")),
    ),
    "Gear Shift Bite - Particles": (
        ("Shape", ("balance", "punch", "length", "tail", "tone")),
    ),
    "Rev Limit": (
        ("RPM Window", ("rpm_position", "fade_range", "vehicle_rpm_scaling", "max_gear_limit")),
        ("Feel", ("pan", "tone", "pulse_rate", "punch", "downshift_surge", "climb_strength")),
    ),
    "Impacts": (
        ("Detection", ("speed_drop_threshold", "g_force_threshold", "slip_influence")),
        ("Feel", ("impact_punch", "impact_length", "low_impact_hz", "high_impact_hz")),
    ),
    "Impact - Side": (
        ("Detection", ("side_sensitivity", "bump_rejection")),
        ("Feel", ("scrape_strength", "side_length")),
    ),
    "Impact - Smashable": (
        ("Detection", ("smash_sensitivity", "repeat_cooldown")),
        ("Feel", ("smash_punch", "rattle_strength", "smash_length", "light_object_hz", "heavy_object_hz")),
    ),
    "Rumble Kerbs": (
        ("Speed Range", ("speed_low_start", "speed_high_max")),
        ("Frequency", ("low_speed_hz", "high_speed_hz")),
        ("Texture", ("bump_sharpness",)),
    ),
    "Tire Limit Load": (
        ("Load Window", ("entry_threshold", "full_load_point")),
        ("Frequency", ("low_load_hz", "high_load_hz")),
        ("Response", ("attack",)),
    ),
    "Wheelspin Buzz": (
        ("Slip Window", ("slip_start_offset",)),
        ("Feel", ("pan", "buzz_hz", "noise_range", "attack")),
    ),
    "Road Bumps": (
        ("Detection", ("bump_sensitivity", "low_class_correction")),
        ("Strength", ("small_bump_strength", "large_bump_strength")),
        ("Frequency", ("low_bump_hz", "high_bump_hz")),
        ("Envelope", ("attack", "decay")),
    ),
    "Acceleration G Punch - Haptic": (
        ("Gear Scaling", ("max_rpm_offset", "gear_drop_offset", "haptic_gear_1_percent", "haptic_gear_2_percent", "haptic_gear_3_percent")),
        ("Fade", ("shift_wall_fade_percent", "shift_fade_tail_percent")),
        ("Pulse", ("haptic_strength", "shift_delay_ms", "shift_pulse_lock_ms", "start_hz", "end_hz")),
        ("Balance", ("pan",)),
    ),
}


HAPTIC_DETAIL_RANGES: dict[str, dict[str, tuple[int, int]]] = {
    "Gear Shift Bite - Core": {
        "balance": (0, 10),
        "punch": (0, 10),
        "length": (0, 10),
        "tail": (0, 10),
        "tone": (0, 10),
    },
    "Gear Shift Bite - High Hz": {
        "balance": (0, 10),
        "punch": (0, 10),
        "length": (0, 10),
        "tail": (0, 10),
        "tone": (0, 10),
    },
    "Gear Shift Bite - Particles": {
        "balance": (0, 10),
        "punch": (0, 10),
        "length": (0, 10),
        "tail": (0, 10),
        "tone": (0, 10),
    },
    "Rev Limit": {
        "pan": (0, 10),
        "rpm_position": (80, 99),
        "fade_range": (1, 20),
        "tone": (0, 10),
        "pulse_rate": (0, 10),
        "punch": (0, 10),
        "vehicle_rpm_scaling": (0, 5),
        "max_gear_limit": (0, 10),
        "downshift_surge": (0, 10),
        "climb_strength": (0, 10),
    },
    "Rumble Kerbs": {
        "speed_low_start": (0, 200),
        "speed_high_max": (0, 360),
        "low_speed_hz": (1, 120),
        "high_speed_hz": (1, 160),
        "bump_sharpness": (0, 10),
    },
    "Tire Limit Load": {
        "entry_threshold": (0, 80),
        "full_load_point": (10, 100),
        "low_load_hz": (1, 120),
        "high_load_hz": (1, 160),
        "attack": (0, 10),
    },
    "Wheelspin Buzz": {
        "pan": (0, 10),
        "slip_start_offset": (-10, 10),
        "buzz_hz": (20, 160),
        "noise_range": (0, 30),
        "attack": (0, 10),
    },
    "Acceleration G Punch - Haptic": {
        "pan": (0, 10),
        "haptic_strength": (0, 10),
        "max_rpm_offset": (0, 10),
        "gear_drop_offset": (0, 9),
        "shift_wall_fade_percent": (0, 90),
        "shift_fade_tail_percent": (0, 100),
        "haptic_gear_1_percent": (0, 150),
        "haptic_gear_2_percent": (0, 150),
        "haptic_gear_3_percent": (0, 150),
        "shift_delay_ms": (0, 200),
        "shift_pulse_lock_ms": (0, 200),
        "start_hz": (1, 120),
        "end_hz": (1, 160),
    },
    "Road Bumps": {
        "bump_sensitivity": (0, 10),
        "low_class_correction": (0, 10),
        "small_bump_strength": (0, 10),
        "large_bump_strength": (0, 10),
        "low_bump_hz": (1, 120),
        "high_bump_hz": (1, 160),
        "attack": (0, 10),
        "decay": (0, 10),
    },
    "Impacts": {
        "speed_drop_threshold": (1, 80),
        "g_force_threshold": (1, 120),
        "slip_influence": (0, 10),
        "impact_punch": (0, 10),
        "impact_length": (0, 10),
        "low_impact_hz": (1, 120),
        "high_impact_hz": (1, 160),
    },
    "Impact - Side": {
        "side_sensitivity": (0, 10),
        "bump_rejection": (0, 10),
        "scrape_strength": (0, 10),
        "side_length": (0, 10),
    },
    "Impact - Smashable": {
        "smash_sensitivity": (0, 10),
        "repeat_cooldown": (20, 200),
        "smash_punch": (0, 10),
        "rattle_strength": (0, 10),
        "smash_length": (0, 10),
        "light_object_hz": (1, 180),
        "heavy_object_hz": (1, 140),
    },
}


LR_BALANCE_KEYS = {"pan"}
LR_BALANCE_STYLE = "lr_balance"

NATIVE_SOFT_PULSE_FREQUENCY_MAX = 180
SLIP_PULSE_RATE_MAX = 120

DETAIL_LABEL_OVERRIDES = {
    "balance": "Up/Down Balance",
    "curve": "Curve",
    "force_percent": "Resistance Strength",
    "start_percent": "Resistance Start Position",
    "max_percent": "Resistance Max Position",
    "wall_percent": "Prediction Strength",
    "gate_range": "Gate Range",
    "smooth_start_ms": "Smooth Start",
    "shift_pulse_boost_ms": "Shift Pulse Lock ms",
    "pulse_strength": "Pulse Strength",
    "pulse_start_percent": "Pulse Start Position",
    "pulse_rate": "Pulse Rate",
    "slip_threshold": "Slip Threshold",
    "slip_end_threshold": "Slip Off End",
    "slip_drop_low_percent": "Slip Drop Low Resistance",
    "slip_low_percent": "Slip Low Resistance",
    "slip_pulse_start_percent": "Slip Pulse Start Level",
    "slip_pulse_end_percent": "Slip Pulse End Level",
    "slip_pulse_rate": "Slip Pulse Rate",
    "slip_strong_pulse_amplitude": "Strong Pulse Amplitude",
    "slip_strong_pulse_rate": "Strong Pulse Rate",
    "slip_soft_pulse_amplitude": "Soft Pulse Amplitude",
    "slip_soft_pulse_frequency": "Soft Pulse Frequency",
    "slip_soft_pulse_start_zone": "Soft Pulse Start Zone",
    "max_rpm_offset": "Max RPM Offset",
    "gear_drop_offset": "Gear Drop Offset",
    "launch_wall_fade_percent": "Launch Wall Fade %",
    "shift_wall_fade_percent": "Shift Wall Fade %",
    "shift_fade_tail_percent": "Shift Tail %",
    "pulse_gear_1_percent": "Pulse Gear 1 %",
    "pulse_gear_2_percent": "Pulse Gear 2 %",
    "pulse_gear_3_percent": "Pulse Gear 3+ %",
    "howl_start_hz": "Start Hz",
    "howl_end_hz": "End Hz",
    "howl_duration_ms": "Pulse Length ms",
    "howl_noise_percent": "Noise",
    "howl_amp": "Soft Pulse Amp",
    "howl_start_zone": "Soft Pulse Start Zone",
    "kick_strong_pulse_strength": "Kick Soft Pulse Strength",
    "kick_strong_pulse_hz": "Kick Soft Pulse Hz",
    "kick_strong_pulse_duration_ms": "Kick Soft Pulse Length ms",
    "upshift_strength_percent": "Upshift Kick Strength",
    "upshift_duration_ms": "Upshift Kick Duration",
    "downshift_strength_percent": "Downshift Kick Strength",
    "downshift_duration_ms": "Downshift Kick Duration",
    "early_input_soft_zone": "Early Input Soft Zone",
    "kick_late_position": "Kick Late Position",
    "kick_softness": "Kick Softness",
    "release_duration_ms": "Kick Release Duration",
    "kerb_l_start_percent": "Trigger Start Position",
    "kerb_r_start_percent": "R2 Trigger Start Position",
    "kerb_l_low_hz": "L2 Low Speed Hz",
    "kerb_l_high_hz": "L2 High Speed Hz",
    "kerb_r_low_hz": "R2 Low Speed Hz",
    "kerb_r_high_hz": "R2 High Speed Hz",
    "kerb_l_low_amp": "Low Speed Amp",
    "kerb_l_high_amp": "High Speed Amp",
    "kerb_r_low_amp": "R2 Low Speed Amp",
    "kerb_r_high_amp": "R2 High Speed Amp",
    "kerb_low_hz": "Low Speed Hz",
    "kerb_high_hz": "High Speed Hz",
    "condition_strictness": "Condition Strictness",
    "wheelspin_buzz": "Wheelspin Buzz",
    "throttle_pressure": "Throttle Pressure",
    "throttle_traction": "Throttle Traction",
    "accel_g_punch": "Acceleration G Punch",
    "rpm_rev_limit": "RPM Rev Limit",
}


TRIGGER_DETAIL_GROUPS: dict[str, tuple[tuple[str, tuple[str, ...]], ...]] = {
    "Drift Rumble Fade": (
        ("Condition", ("condition_strictness",)),
        (
            "Fade Amount",
            (
                "wheelspin_buzz",
                "throttle_pressure",
                "throttle_traction",
                "accel_g_punch",
                "rpm_rev_limit",
            ),
        ),
    ),
    "Brake Pressure": (
        ("Pedal Range", ("start_percent", "max_percent", "force_percent", "curve")),
    ),
    "Brake Resistance": (
        ("Resistance", ("force_percent", "start_percent")),
        ("Slip Release", ("slip_threshold", "slip_drop_low_percent")),
        ("Slip Pulse Window", ("slip_pulse_start_percent", "slip_pulse_end_percent", "slip_pulse_rate")),
        ("Soft Pulse", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone")),
        ("Strong Pulse", ("slip_strong_pulse_amplitude", "slip_strong_pulse_rate")),
    ),
    "Brake Resistance - Predictive": (
        ("Resistance", ("force_percent", "start_percent", "max_percent", "wall_percent")),
        ("Slip Release", ("slip_threshold", "slip_drop_low_percent")),
        ("Slip Pulse Window", ("slip_pulse_start_percent", "slip_pulse_end_percent", "slip_pulse_rate")),
        ("Soft Pulse", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone")),
        ("Strong Pulse", ("slip_strong_pulse_amplitude", "slip_strong_pulse_rate")),
    ),
    "Gear Shift Kick": (
        ("Upshift", ("upshift_strength_percent", "upshift_duration_ms")),
        ("Downshift", ("downshift_strength_percent", "downshift_duration_ms")),
        ("Release Shape", ("early_input_soft_zone", "kick_late_position", "kick_softness", "release_duration_ms")),
    ),
    "Collision Kick": (
        ("Kick", ("force_percent", "smooth_start_ms")),
    ),
    "Kerb Wave": (
        ("Kerb Output", ("kerb_l_start_percent", "kerb_low_hz", "kerb_high_hz", "kerb_l_low_amp", "kerb_l_high_amp")),
    ),
    "Throttle Pressure": (
        ("Pedal Range", ("start_percent", "max_percent", "force_percent", "curve")),
        ("Response", ("smooth_start_ms", "pulse_strength", "pulse_start_percent", "pulse_rate")),
    ),
    "Throttle Resistance - Traction": (
        ("Resistance", ("force_percent", "max_percent", "wall_percent")),
        ("Traction Slip", ("slip_threshold", "slip_end_threshold", "slip_drop_low_percent", "slip_low_percent")),
        ("Slip Pulse Window", ("slip_pulse_start_percent", "slip_pulse_end_percent", "slip_pulse_rate")),
        ("Soft Pulse", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone")),
        ("Strong Pulse", ("slip_strong_pulse_amplitude", "slip_strong_pulse_rate")),
    ),
    "Acceleration G Punch": (
        ("Gear Scaling", ("max_rpm_offset", "gear_drop_offset", "pulse_gear_1_percent", "pulse_gear_2_percent", "pulse_gear_3_percent")),
        ("Fade", ("launch_wall_fade_percent", "shift_wall_fade_percent", "shift_fade_tail_percent")),
        ("Pulse Timing", ("smooth_start_ms", "shift_pulse_boost_ms", "pulse_strength", "pulse_start_percent")),
        ("Soft Pulse", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone")),
        ("Strong Pulse", ("slip_strong_pulse_amplitude", "slip_strong_pulse_rate")),
    ),
    "Shift Down Howl": (
        ("Howl", ("howl_start_hz", "howl_end_hz", "howl_duration_ms", "howl_noise_percent", "howl_amp", "howl_start_zone")),
        ("Kick Soft Pulse", ("kick_strong_pulse_strength", "kick_strong_pulse_hz", "kick_strong_pulse_duration_ms")),
    ),
    "RPM Rev Limit": (
        ("RPM Window", ("start_percent", "force_percent")),
        ("Soft Pulse", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone")),
        ("Strong Pulse", ("slip_strong_pulse_amplitude", "slip_strong_pulse_rate")),
    ),
    "Impact Tick": (
        ("Soft Pulse Tick", ("slip_soft_pulse_amplitude", "slip_soft_pulse_frequency", "slip_soft_pulse_start_zone", "smooth_start_ms")),
    ),
}


TRIGGER_OPTION_GROUPS: dict[str, tuple[tuple[str, tuple[tuple[str, str, str, tuple[str, ...]], ...]], ...]] = {
    "Kerb Wave": (
        (
            "Kerb Output",
            (
                ("toggle", "kerb_l_enabled", "L2 ON", ()),
                ("toggle", "kerb_r_enabled", "R2 ON", ()),
            ),
        ),
    ),
    "Brake Resistance": (
        (
            "Slip Pulse Window",
            (
                ("toggle", "slip_pulse_enabled", "Enable Slip Pulse", ()),
                ("choice", "slip_pulse_style", "Pulse Type", ("Pulse Kick", "Soft Pulse", "Strong Pulse")),
            ),
        ),
    ),
    "Brake Resistance - Predictive": (
        (
            "Slip Pulse Window",
            (
                ("toggle", "slip_pulse_enabled", "Enable Slip Pulse", ()),
                ("choice", "slip_pulse_style", "Pulse Type", ("Pulse Kick", "Soft Pulse", "Strong Pulse")),
            ),
        ),
    ),
    "Throttle Resistance - Traction": (
        (
            "Slip Pulse Window",
            (
                ("toggle", "slip_pulse_enabled", "Enable Slip Pulse", ()),
                ("choice", "slip_pulse_style", "Pulse Type", ("Pulse Kick", "Soft Pulse", "Strong Pulse")),
            ),
        ),
    ),
    "Acceleration G Punch": (
        (
            "Pulse Timing",
            (
                ("toggle", "slip_pulse_enabled", "Enable Pulse", ()),
                ("choice", "slip_pulse_style", "Pulse Type", ("Soft Pulse", "Strong Pulse")),
            ),
        ),
    ),
    "RPM Rev Limit": (
        (
            "RPM Window",
            (
                ("choice", "slip_pulse_style", "Pulse Type", ("Soft Pulse", "Strong Pulse")),
            ),
        ),
    ),
}


def _details_for_ui(effect_name: str, details: dict[str, Any]) -> dict[str, Any]:
    if effect_name != "Kerb Wave":
        return details
    normalized = dict(details)
    fallback_specs = {
        "kerb_l_enabled": (("kerb_l_enabled",), True),
        "kerb_r_enabled": (("kerb_r_enabled",), True),
        "kerb_l_start_percent": (("kerb_l_start_percent", "kerb_r_start_percent"), 20),
        "kerb_low_hz": (("kerb_low_hz", "kerb_l_low_hz", "kerb_r_low_hz"), 10),
        "kerb_high_hz": (("kerb_high_hz", "kerb_l_high_hz", "kerb_r_high_hz"), 40),
        "kerb_l_low_amp": (("kerb_l_low_amp", "kerb_r_low_amp"), 1),
        "kerb_l_high_amp": (("kerb_l_high_amp", "kerb_r_high_amp"), 8),
    }
    for target_key, (source_keys, default_value) in fallback_specs.items():
        if target_key in normalized:
            continue
        normalized[target_key] = next(
            (normalized[key] for key in source_keys if key in normalized),
            default_value,
        )
    return normalized


def grouped_numeric_details(
    effect_name: str,
    details: dict[str, Any],
    group_map: dict[str, tuple[tuple[str, tuple[str, ...]], ...]],
) -> list[DetailGroupSpec]:
    details = _details_for_ui(effect_name, details)
    consumed: set[str] = set()
    groups: list[DetailGroupSpec] = []
    priority_rows: list[DetailRowSpec] = []
    range_overrides = HAPTIC_DETAIL_RANGES.get(effect_name, {}) if group_map is HAPTIC_DETAIL_GROUPS else {}
    for title, keys in group_map.get(effect_name, ()):
        grouped_rows: list[DetailRowSpec] = []
        for key in keys:
            row = _row_for_key(key, details, range_overrides.get(key))
            if row is not None:
                consumed.add(row.key)
                if row.display_style == LR_BALANCE_STYLE:
                    priority_rows.append(row)
                else:
                    grouped_rows.append(row)
        rows = tuple(grouped_rows)
        if rows:
            groups.append(DetailGroupSpec(title, rows))

    if priority_rows:
        groups.insert(0, DetailGroupSpec("Balance", tuple(priority_rows)))

    if groups:
        return groups

    other_rows = []
    for key, value in details.items():
        if key in consumed or key in {"enabled", "volume"}:
            continue
        row = _row_for_key(key, details, range_overrides.get(key))
        if row is not None:
            other_rows.append(row)
    if other_rows:
        groups.append(DetailGroupSpec("Additional", tuple(other_rows)))
    return groups


def grouped_option_details(effect_name: str, details: dict[str, Any]) -> list[DetailOptionGroupSpec]:
    details = _details_for_ui(effect_name, details)
    groups: list[DetailOptionGroupSpec] = []
    for title, option_specs in TRIGGER_OPTION_GROUPS.get(effect_name, ()):
        rows: list[DetailOptionSpec] = []
        for kind, key, label, options in option_specs:
            if key not in details:
                continue
            value = details.get(key)
            if kind == "toggle":
                rows.append(DetailOptionSpec(label, key, bool(value), kind))
            elif kind == "choice":
                normalized = normalize_choice_value(value, options)
                rows.append(DetailOptionSpec(label, key, normalized, kind, options))
        if rows:
            groups.append(DetailOptionGroupSpec(title, tuple(rows)))
    return groups


def normalize_choice_value(value: object, options: tuple[str, ...]) -> str:
    if not options:
        return str(value or "")
    normalized = str(value or "").strip().lower().replace("_", " ").replace("-", " ")
    for option in options:
        option_normalized = option.lower().replace("_", " ").replace("-", " ")
        if normalized == option_normalized:
            return option
    if normalized in {"strong", "rumble"} and "Strong Pulse" in options:
        return "Strong Pulse"
    if normalized in {"soft", "wave"} and "Soft Pulse" in options:
        return "Soft Pulse"
    if normalized in {"pulse kick", "kick"} and "Pulse Kick" in options:
        return "Pulse Kick"
    return options[0]


def _row_for_key(
    key: str,
    details: dict[str, Any],
    range_override: tuple[int, int] | None = None,
) -> DetailRowSpec | None:
    value = details.get(key)
    if isinstance(value, bool) or not isinstance(value, Number):
        return None
    numeric_value = int(round(float(value)))
    minimum, maximum = range_override or detail_range(key, numeric_value)
    display_style = LR_BALANCE_STYLE if is_lr_balance_key(key) else ""
    return DetailRowSpec(detail_label(key), key, numeric_value, minimum, maximum, display_style)


def is_lr_balance_key(key: str) -> bool:
    return key.lower() in LR_BALANCE_KEYS


def detail_label(key: str) -> str:
    if is_lr_balance_key(key):
        return "L/R Balance"
    if key in DETAIL_LABEL_OVERRIDES:
        return DETAIL_LABEL_OVERRIDES[key]
    label = key.replace("_", " ").title()
    return (
        label.replace(" Hz", " Hz")
        .replace(" Ms", " ms")
        .replace(" Rpm", " RPM")
        .replace(" G ", " G ")
        .replace(" L ", " L ")
        .replace(" R ", " R ")
    )


def detail_range(key: str, value: int) -> tuple[int, int]:
    lower_key = key.lower()
    minimum = min(0, int(value))
    maximum = 10
    if lower_key in {"slip_strong_pulse_amplitude", "slip_strong_pulse_rate", "pulse_rate"}:
        minimum, maximum = 1, 255
    elif lower_key == "slip_pulse_rate":
        minimum, maximum = 1, SLIP_PULSE_RATE_MAX
    elif lower_key in {
        "slip_soft_pulse_amplitude",
        "howl_amp",
        "kerb_l_low_amp",
        "kerb_l_high_amp",
        "kerb_r_low_amp",
        "kerb_r_high_amp",
    }:
        minimum, maximum = 1, 8
    elif lower_key in {"slip_soft_pulse_start_zone", "howl_start_zone"}:
        minimum, maximum = 0, 9
    elif lower_key in {
        "slip_soft_pulse_frequency",
        "howl_start_hz",
        "howl_end_hz",
        "kick_strong_pulse_hz",
        "kerb_low_hz",
        "kerb_high_hz",
        "kerb_l_low_hz",
        "kerb_l_high_hz",
        "kerb_r_low_hz",
        "kerb_r_high_hz",
    }:
        minimum, maximum = 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX
    elif lower_key == "slip_pulse_start_percent":
        minimum, maximum = 10, 99
    elif lower_key == "slip_pulse_end_percent":
        minimum, maximum = 100, 150
    elif lower_key == "max_rpm_offset":
        minimum, maximum = 0, 10
    elif lower_key == "gear_drop_offset":
        minimum, maximum = 0, 9
    elif lower_key in {"launch_wall_fade_percent", "shift_wall_fade_percent"}:
        minimum, maximum = 0, 90
    elif lower_key == "howl_noise_percent":
        minimum, maximum = 0, 10
    elif lower_key == "wall_percent":
        minimum, maximum = 0, 60
    elif lower_key == "howl_duration_ms":
        minimum, maximum = 40, 1200
    elif lower_key == "kick_strong_pulse_duration_ms":
        minimum, maximum = 0, 180
    elif lower_key in {"shift_pulse_boost_ms", "smooth_start_ms"}:
        minimum, maximum = 0, 300
    elif "percent" in lower_key or lower_key in {"strength", "force", "amp", "amplitude"}:
        maximum = 100
    elif "hz" in lower_key or "frequency" in lower_key or "rate" in lower_key:
        maximum = 200
    elif "ms" in lower_key or "duration" in lower_key or "delay" in lower_key or "cooldown" in lower_key:
        maximum = 1000
    elif "threshold" in lower_key:
        maximum = max(10, int(value) + 5)
    elif "rpm" in lower_key:
        maximum = 100
    elif "position" in lower_key or "point" in lower_key or "zone" in lower_key or "range" in lower_key:
        maximum = max(10, int(value))
    elif abs(int(value)) > 10:
        maximum = max(100, int(value))
    if minimum < 0:
        minimum = min(-20, minimum)
    return minimum, max(maximum, int(value), 1)


def format_detail_value(display_style: str, value: int, minimum: int = 0, maximum: int = 10) -> str:
    if display_style == LR_BALANCE_STYLE:
        return format_lr_balance_value(value, minimum, maximum)
    return str(value)


def format_lr_balance_value(value: int, minimum: int = 0, maximum: int = 10) -> str:
    if maximum <= minimum:
        right = max(0, min(10, int(round(value))))
    else:
        normalized = (int(value) - minimum) / (maximum - minimum)
        right = int(round(max(0.0, min(1.0, normalized)) * 10))
    return f"{10 - right}:{right}"
