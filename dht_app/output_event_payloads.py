from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from time import time
from typing import Any

from .settings_model import EffectSetting


HAPTIC_EVENT_PORT = 18801
TRIGGER_STATUS_PORT = 18802


@dataclass(frozen=True)
class OutputEventPayload:
    """Server-compatible ASCII event payload for the DualSense output service."""

    name: str
    params: tuple[tuple[str, str], ...] = ()

    def to_message(self) -> str:
        if not self.params:
            return self.name
        return "|".join((self.name, *[f"{key}={value}" for key, value in self.params]))


@dataclass(frozen=True)
class OutputProfilePreview:
    game_label: str
    preset_name: str
    payloads: tuple[OutputEventPayload, ...]

    @property
    def summary(self) -> str:
        if not self.payloads:
            return f"{self.game_label} / {self.preset_name}: no output payloads staged"
        names = ", ".join(payload.name for payload in self.payloads)
        return f"{self.game_label} / {self.preset_name}: {len(self.payloads)} payload(s) staged: {names}"

    def messages(self) -> tuple[str, ...]:
        return tuple(payload.to_message() for payload in self.payloads)


def master_gain(percent: float) -> OutputEventPayload:
    return event("MASTER_GAIN", percent=_clamp(percent, 0, 100))


def haptic_low_boost(gain: float) -> OutputEventPayload:
    return event("HAPTIC_LOW_BOOST", gain=_clamp(gain, 0, 10))


def haptic_test(hz: float = 80, amp: float = 40, duration_ms: int = 1500) -> OutputEventPayload:
    return event(
        "HAPTIC_TEST",
        hz=_clamp(hz, 20, 200),
        amp=_clamp(amp, 0, 100),
        durationMs=_clamp_int(duration_ms, 40, 5000),
    )


def gear_shift(
    *,
    direction: int = 1,
    rpm_ratio: float = 0.6,
    throttle: float = 0.6,
    torque: float = 0.5,
    performance_index: int = 700,
    max_rpm: float = 8000,
    core: Mapping[str, Any] | None = None,
    high_hz: Mapping[str, Any] | None = None,
    particles: Mapping[str, Any] | None = None,
) -> OutputEventPayload:
    core = core or {}
    high_hz = high_hz or {}
    particles = particles or {}
    return event(
        "GEAR_SHIFT",
        dir=1 if direction >= 0 else -1,
        rpmRatio=_clamp(rpm_ratio, 0, 1),
        throttle=_clamp(throttle, 0, 1),
        torque=_clamp(torque, 0, 1),
        pi=_clamp_int(performance_index, 0, 9999),
        maxRpm=max(0, float(max_rpm)),
        coreVolume=_detail(core, "volume", 10, 0, 10),
        highHzVolume=_detail(high_hz, "volume", 10, 0, 10),
        particlesVolume=_detail(particles, "volume", 10, 0, 10),
        coreLeft=_gear_shift_left(core, direction),
        coreRight=_gear_shift_right(core, direction),
        highHzLeft=_gear_shift_left(high_hz, direction),
        highHzRight=_gear_shift_right(high_hz, direction),
        particlesLeft=_gear_shift_left(particles, direction),
        particlesRight=_gear_shift_right(particles, direction),
        corePunch=_detail(core, "punch", 5, 0, 10),
        coreLength=_detail(core, "length", 5, 0, 10),
        coreTail=_detail(core, "tail", 5, 0, 10),
        coreTone=_detail(core, "tone", 5, 0, 10),
        highHzPunch=_detail(high_hz, "punch", 5, 0, 10),
        highHzLength=_detail(high_hz, "length", 5, 0, 10),
        highHzTail=_detail(high_hz, "tail", 5, 0, 10),
        highHzTone=_detail(high_hz, "tone", 5, 0, 10),
        particlesPunch=_detail(particles, "punch", 5, 0, 10),
        particlesLength=_detail(particles, "length", 5, 0, 10),
        particlesTail=_detail(particles, "tail", 5, 0, 10),
        particlesTone=_detail(particles, "tone", 5, 0, 10),
    )


def rev_limit(
    *,
    rpm: float,
    max_rpm: float,
    idle_rpm: float = 800,
    volume: float = 10,
    left: float = 1,
    right: float = 1,
    details: Mapping[str, Any] | None = None,
    strength_scale: float = 1,
    observed_max_gear: int = 0,
    is_max_gear: int = 0,
    rise_kind: int = 0,
    rpm_rise_per_s: float = 0,
) -> OutputEventPayload:
    details = details or {}
    return event(
        "REV_LIMIT",
        rpm=max(0, float(rpm)),
        maxRpm=max(0, float(max_rpm)),
        idleRpm=max(0, float(idle_rpm)),
        volume=_clamp(volume, 0, 10),
        left=_clamp(left, 0, 1),
        right=_clamp(right, 0, 1),
        rpmPosition=_detail(details, "rpm_position", 96, 80, 99),
        fadeRange=_detail(details, "fade_range", 10, 1, 20),
        tone=_detail(details, "tone", 5, 0, 10),
        pulseRate=_detail(details, "pulse_rate", 5, 0, 10),
        punch=_detail(details, "punch", 5, 0, 10),
        vehicleRpmScaling=_detail(details, "vehicle_rpm_scaling", 1, 0, 5),
        strengthScale=_clamp(strength_scale, 0, 1.2),
        observedMaxGear=_clamp_int(observed_max_gear, 0, 20),
        isMaxGear=_clamp_int(is_max_gear, 0, 1),
        riseKind=_clamp_int(rise_kind, 0, 2),
        rpmRisePerS=max(0, float(rpm_rise_per_s)),
    )


def rumble_kerbs(
    *,
    front_left: float,
    front_right: float,
    hz: float = 24,
    speed: float = 0,
    volume: float = 10,
    details: Mapping[str, Any] | None = None,
) -> OutputEventPayload:
    details = details or {}
    return event(
        "RUMBLE_KERBS",
        fl=_clamp(front_left, 0, 1),
        fr=_clamp(front_right, 0, 1),
        hz=_clamp(hz, 1, 160),
        speed=max(0, float(speed)),
        sharpness=_detail(details, "bump_sharpness", 5, 0, 10),
        volume=_clamp(volume, 0, 10),
    )


def tire_limit_load(
    *,
    left: float,
    right: float,
    left_hz: float = 35,
    right_hz: float = 35,
    volume: float = 10,
) -> OutputEventPayload:
    return event(
        "TIRE_LIMIT_LOAD",
        left=_clamp(left, 0, 1),
        right=_clamp(right, 0, 1),
        leftHz=_clamp(left_hz, 1, 160),
        rightHz=_clamp(right_hz, 1, 160),
        volume=_clamp(volume, 0, 10),
    )


def wheelspin_buzz(
    *,
    left: float,
    right: float,
    hz: float = 70,
    noise_range: float = 0,
    volume: float = 10,
) -> OutputEventPayload:
    return event(
        "WHEELSPIN_BUZZ",
        left=_clamp(left, 0, 1),
        right=_clamp(right, 0, 1),
        hz=_clamp(hz, 20, 160),
        noiseRange=_clamp(noise_range, 0, 30),
        volume=_clamp(volume, 0, 10),
    )


def accel_g_punch_haptic(*, left: float, right: float, hz: float = 62, volume: float = 10) -> OutputEventPayload:
    return event(
        "ACCEL_G_PUNCH_HAPTIC",
        left=_clamp(left, 0, 1),
        right=_clamp(right, 0, 1),
        hz=_clamp(hz, 1, 160),
        volume=_clamp(volume, 0, 10),
    )


def road_bumps(*, left: float, right: float, hz: float = 65, volume: float = 10) -> OutputEventPayload:
    return event(
        "ROAD_BUMPS",
        left=_clamp(left, 0, 1),
        right=_clamp(right, 0, 1),
        hz=_clamp(hz, 1, 160),
        volume=_clamp(volume, 0, 10),
    )


def brake_pulse_haptic(*, left: float, hz: float = 70, volume: float = 0) -> OutputEventPayload:
    return event(
        "BRAKE_PULSE_HAPTIC",
        left=_clamp(left, 0, 1),
        hz=_clamp(hz, 20, 160),
        volume=_clamp(volume, 0, 10),
    )


def impact(
    *,
    power: float,
    speed_drop: float = 0,
    accel_g: float = 0,
    slip: float = 0,
    mass: float = 0,
    smash_vel_diff: float = 0,
    punch: float = 5,
    length: float = 5,
    low_hz: float = 44,
    high_hz: float = 78,
    volume: float = 10,
) -> OutputEventPayload:
    return event(
        "IMPACT",
        power=_clamp(power, 0, 1),
        speedDrop=max(0, float(speed_drop)),
        accelG=max(0, float(accel_g)),
        slip=max(0, float(slip)),
        mass=max(0, float(mass)),
        smashVelDiff=max(0, float(smash_vel_diff)),
        punch=_clamp(punch, 0, 10),
        length=_clamp(length, 0, 10),
        lowHz=_clamp(low_hz, 1, 120),
        highHz=_clamp(high_hz, 1, 160),
        volume=_clamp(volume, 0, 10),
    )


def impact_side(
    *,
    power: float,
    dvel: float = 0,
    accel_x: float = 0,
    accel_z: float = 0,
    accel_x_delta: float = 0,
    accel_y_delta: float = 0,
    accel_z_delta: float = 0,
    angular_y_delta: float = 0,
    angular_y: float = 0,
    recent_steer: float = 0,
    scrape: float = 5,
    length: float = 5,
    volume: float = 10,
) -> OutputEventPayload:
    return event(
        "IMPACT_SIDE",
        power=_clamp(power, 0, 1),
        dVel=max(0, float(dvel)),
        accelX=max(0, float(accel_x)),
        accelZ=max(0, float(accel_z)),
        accelXDelta=max(0, float(accel_x_delta)),
        accelYDelta=max(0, float(accel_y_delta)),
        accelZDelta=max(0, float(accel_z_delta)),
        angularYDelta=max(0, float(angular_y_delta)),
        angularY=max(0, float(angular_y)),
        recentSteer=max(0, float(recent_steer)),
        scrape=_clamp(scrape, 0, 10),
        length=_clamp(length, 0, 10),
        volume=_clamp(volume, 0, 10),
    )


def impact_smashable(
    *,
    power: float,
    mass: float = 0,
    smash_vel_diff: float = 0,
    speed: float = 0,
    punch: float = 5,
    rattle: float = 5,
    length: float = 5,
    light_hz: float = 115,
    heavy_hz: float = 58,
    volume: float = 10,
) -> OutputEventPayload:
    return event(
        "IMPACT_SMASHABLE",
        power=_clamp(power, 0, 1),
        mass=max(0, float(mass)),
        smashVelDiff=max(0, float(smash_vel_diff)),
        speed=max(0, float(speed)),
        punch=_clamp(punch, 0, 10),
        rattle=_clamp(rattle, 0, 10),
        length=_clamp(length, 0, 10),
        lightHz=_clamp(light_hz, 1, 160),
        heavyHz=_clamp(heavy_hz, 1, 160),
        volume=_clamp(volume, 0, 10),
    )


def trigger_brake(
    *,
    force: int,
    start: int | None = None,
    end: int | None = None,
    mode: int | str = 0,
    pulse: int = 0,
    pulse_rate: int = 0,
    vibrate_amp: int = 0,
    vibrate_freq: int = 0,
    vibrate_start_zone: int = 0,
    include_timestamp: bool = True,
) -> OutputEventPayload:
    start_byte = _clamp_int(start, 0, 255) if start is not None else None
    end_byte = _clamp_int(end, 0, 255) if end is not None else None
    if start_byte is not None and end_byte is not None and end_byte < start_byte:
        start_byte, end_byte = end_byte, start_byte
    params = {
        "force": _clamp_int(force, 0, 255),
        "mode": mode,
        "pulse": _clamp_int(pulse, 0, 255),
        "pulseRate": _clamp_int(pulse_rate, 0, 255),
        "vibrateAmp": _clamp_int(vibrate_amp, 0, 8),
        "vibrateFreq": _clamp_int(vibrate_freq, 0, 255),
        "vibrateStartZone": _clamp_int(vibrate_start_zone, 0, 9),
    }
    if start_byte is not None:
        params["start"] = start_byte
    if end_byte is not None:
        params["end"] = end_byte
    return trigger_event("TRIGGER_BRAKE", include_timestamp=include_timestamp, **params)


def trigger_throttle(
    *,
    force: int,
    start: int | None = None,
    pulse: int = 0,
    pulse_rate: int = 0,
    vibrate_amp: int = 0,
    vibrate_freq: int = 0,
    vibrate_start_zone: int = 0,
    include_timestamp: bool = True,
) -> OutputEventPayload:
    params = {
        "force": _clamp_int(force, 0, 255),
        "pulse": _clamp_int(pulse, 0, 255),
        "pulseRate": _clamp_int(pulse_rate, 0, 255),
        "vibrateAmp": _clamp_int(vibrate_amp, 0, 8),
        "vibrateFreq": _clamp_int(vibrate_freq, 0, 255),
        "vibrateStartZone": _clamp_int(vibrate_start_zone, 0, 9),
    }
    if start is not None:
        params["start"] = _clamp_int(start, 0, 255)
    return trigger_event("TRIGGER_THROTTLE", include_timestamp=include_timestamp, **params)


def trigger_gear_shift(
    *,
    side: str | int = "R",
    strength: int = 70,
    start: int | None = None,
    duration_ms: int = 45,
    direction: int = 0,
    release_strength: int = 0,
    release_ms: int = 45,
    softness: int = 7,
    include_timestamp: bool = True,
) -> OutputEventPayload:
    params = {
        "side": side,
        "strength": _clamp_int(strength, 0, 100),
        "durationMs": _clamp_int(duration_ms, 20, 180),
        "dir": _clamp_int(direction, -1, 1),
        "releaseStrength": _clamp_int(release_strength, 0, 100),
        "releaseMs": _clamp_int(release_ms, 0, 120),
        "softness": _clamp_int(softness, 0, 10),
    }
    if start is not None:
        params["start"] = _clamp_int(start, 0, 255)
    return trigger_event("TRIGGER_GEAR_SHIFT", include_timestamp=include_timestamp, **params)


def trigger_mode_test(
    *,
    side: str | int = "R",
    preset: str = "off",
    count: int = 8,
    on_ms: int = 160,
    off_ms: int = 120,
    hz: int = 80,
    amp: int = 80,
    wall_start: int = 0,
    wall_end: int = 0,
    wall_strength: int = 0,
    zones: str = "",
) -> OutputEventPayload:
    params = {
        "side": side,
        "preset": preset,
        "count": _clamp_int(count, 1, 30),
        "onMs": _clamp_int(on_ms, 20, 1000),
        "offMs": _clamp_int(off_ms, 0, 1000),
        "hz": _clamp_int(hz, 1, 255),
        "amp": _clamp_int(amp, 1, 255),
        "wallStart": _clamp_int(wall_start, 0, 255),
        "wallEnd": _clamp_int(wall_end, 0, 255),
        "wallStrength": _clamp_int(wall_strength, 0, 255),
    }
    if zones:
        params["zones"] = zones
    return event("TRIGGER_MODE_TEST", **params)


def build_haptic_profile_preview(
    game_label: str,
    preset_name: str,
    effects: Mapping[str, EffectSetting],
) -> OutputProfilePreview:
    payloads: list[OutputEventPayload] = []
    core = effects.get("Gear Shift Bite - Core")
    high_hz = effects.get("Gear Shift Bite - High Hz")
    particles = effects.get("Gear Shift Bite - Particles")
    if any(setting is not None and setting.enabled for setting in (core, high_hz, particles)):
        payloads.append(
            gear_shift(
                core=_effect_details(core),
                high_hz=_effect_details(high_hz),
                particles=_effect_details(particles),
            )
        )
    rumble = effects.get("Rumble Kerbs")
    if rumble is not None and rumble.enabled:
        payloads.append(
            rumble_kerbs(
                front_left=0,
                front_right=0,
                hz=_detail(rumble.details, "low_speed_hz", 24, 1, 160),
                speed=0,
                volume=rumble.value,
                details=rumble.details,
            )
        )
    road = effects.get("Road Bumps")
    if road is not None and road.enabled:
        payloads.append(
            road_bumps(
                left=0,
                right=0,
                hz=_detail(road.details, "low_bump_hz", 65, 35, 110),
                volume=road.value,
            )
        )
    return OutputProfilePreview(game_label, preset_name, tuple(payloads))


def build_trigger_profile_preview(
    game_label: str,
    preset_name: str,
    effects: Mapping[str, EffectSetting],
) -> OutputProfilePreview:
    payloads: list[OutputEventPayload] = []
    brake = effects.get("Brake Resistance - Predictive") or effects.get("Brake Resistance")
    if brake is not None and brake.enabled:
        payloads.append(
            trigger_brake(
                force=_percent_to_byte(_detail(brake.details, "force_percent", brake.value * 10, 0, 100)),
                start=_wall_position_percent_to_start_byte(_detail(brake.details, "start_percent", 50, 0, 100)),
            )
        )
    throttle = effects.get("Throttle Resistance - Traction") or effects.get("Throttle Pressure")
    if throttle is not None and throttle.enabled:
        payloads.append(
            trigger_throttle(
                force=_percent_to_byte(_detail(throttle.details, "force_percent", throttle.value * 10, 0, 100)),
                start=_wall_position_percent_to_start_byte(_detail(throttle.details, "start_percent", 50, 0, 100)),
            )
        )
    shift = effects.get("Gear Shift Kick")
    if shift is not None and shift.enabled:
        payloads.append(
            trigger_gear_shift(
                side=shift.details.get("upshift_sides", "R"),
                strength=int(_detail(shift.details, "upshift_strength_percent", shift.value * 10, 0, 100)),
                duration_ms=int(_detail(shift.details, "upshift_duration_ms", 45, 20, 180)),
            )
        )
    return OutputProfilePreview(game_label, preset_name, tuple(payloads))


def event(name: str, **params: Any) -> OutputEventPayload:
    return OutputEventPayload(name, tuple((key, _format_value(value)) for key, value in params.items()))


def trigger_reset(include_timestamp: bool = True) -> OutputEventPayload:
    return trigger_event("TRIGGER_RESET", include_timestamp=include_timestamp)


def trigger_event(name: str, include_timestamp: bool = True, **params: Any) -> OutputEventPayload:
    if include_timestamp:
        params = {"ts": int(time() * 1000), **params}
    return event(name, **params)


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0").rstrip(".")
        return text or "0"
    text = str(value).strip()
    return text.replace("|", "/").replace("=", "-")


def _detail(details: Mapping[str, Any], key: str, fallback: float, minimum: float, maximum: float) -> float:
    try:
        value = float(details.get(key, fallback))
    except (TypeError, ValueError):
        value = fallback
    return _clamp(value, minimum, maximum)


def _effect_details(setting: EffectSetting | None) -> dict[str, Any]:
    if setting is None:
        return {"volume": 0}
    details = dict(setting.details)
    details["volume"] = setting.value if setting.enabled else 0
    return details


def _gear_shift_left(details: Mapping[str, Any], direction: int) -> float:
    balance = _detail(details, "balance", 5, 0, 10)
    mix = _clamp(balance / 10.0, 0, 1)
    if direction >= 0:
        return 1.0 - mix
    return mix


def _gear_shift_right(details: Mapping[str, Any], direction: int) -> float:
    balance = _detail(details, "balance", 5, 0, 10)
    mix = _clamp(balance / 10.0, 0, 1)
    if direction >= 0:
        return mix
    return 1.0 - mix


def _percent_to_byte(percent: float) -> int:
    return _clamp_int(round(_clamp(percent, 0, 100) / 100.0 * 255.0), 0, 255)


def _wall_position_percent_to_start_byte(position_percent: float) -> int:
    # Same perceived trigger-wall calibration used by the stable Tkinter app.
    desired = _clamp(position_percent, 0, 100)
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
    return _percent_to_byte(_clamp(raw_percent, 0, 80))


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))


def _clamp_int(value: int | float, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(round(float(value)))))
