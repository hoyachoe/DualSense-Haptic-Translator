from dataclasses import dataclass, field
from typing import Any


@dataclass
class EffectSetting:
    value: int
    enabled: bool = True
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class NumericSetting:
    value: int


def clamp_setting_value(value: int) -> int:
    return max(0, min(10, int(value)))


def make_effect_settings(items: tuple[tuple[str, int, bool], ...]) -> dict[str, EffectSetting]:
    return {name: EffectSetting(value, enabled) for name, value, enabled in items}


def make_numeric_settings(items: tuple[tuple[str, int], ...]) -> dict[str, NumericSetting]:
    return {name: NumericSetting(value) for name, value in items}


HAPTIC_EFFECT_DEFAULTS = (
    ("Gear Shift Bite - Core", 9, True),
    ("Gear Shift Bite - High Hz", 6, True),
    ("Gear Shift Bite - Particles", 6, True),
    ("Rumble Kerbs", 7, True),
    ("Tire Limit Load", 9, True),
    ("Wheelspin Buzz", 4, True),
    ("Acceleration G Punch - Haptic", 6, True),
    ("Rev Limit", 5, False),
    ("Road Bumps", 9, True),
    ("Impacts", 10, True),
    ("Impact - Side", 10, True),
    ("Impact - Smashable", 10, True),
)


HAPTIC_ADVANCED_DEFAULTS = (
    ("Bump Sensitivity", 8),
    ("Low Class Correction", 3),
    ("Small Bump Strength", 7),
    ("Large Bump Strength", 7),
    ("Low Bump Hz", 4),
    ("High Bump Hz", 6),
    ("Attack", 5),
    ("Decay", 5),
)


TRIGGER_EFFECT_DEFAULTS = (
    ("Drift Rumble Fade", 7, True),
    ("Brake Pressure", 6, True),
    ("Brake Resistance", 7, True),
    ("Brake Resistance - Predictive", 8, True),
    ("Gear Shift Kick", 7, True),
    ("Collision Kick", 8, True),
    ("Kerb Wave", 6, True),
    ("Throttle Pressure", 5, True),
    ("Throttle Resistance - Traction", 8, True),
    ("Acceleration G Punch", 7, True),
    ("Shift Down Howl", 6, True),
    ("RPM Rev Limit", 5, False),
    ("Impact Tick", 8, True),
)


TRIGGER_ADVANCED_DEFAULTS = (
    ("Start Position", 4),
    ("End Position", 8),
    ("Resistance Strength", 7),
    ("Slip Release", 6),
    ("Return Delay", 3),
    ("Brake Force Blend", 5),
)
