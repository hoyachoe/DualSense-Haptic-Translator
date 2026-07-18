from __future__ import annotations

import math
from dataclasses import dataclass, field
from time import monotonic
from typing import Mapping

from .output_event_payloads import OutputEventPayload, trigger_brake, trigger_event, trigger_gear_shift, trigger_throttle
from .settings_model import EffectSetting
from .telemetry_frame import TelemetryFrame


TRIGGER_RELEASE_MARGIN_PERCENT = 4.0
BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH = 8.0
TRANSIENT_GEAR_VALUE = 11
SLIP_RESPONSE_OFF = "Off"
SLIP_PULSE_RATE_MAX = 120

BRAKE_PRESSURE = "Brake Pressure"
BRAKE_RESISTANCE = "Brake Resistance"
BRAKE_RESISTANCE_PREDICTIVE = "Brake Resistance - Predictive"
THROTTLE_PRESSURE = "Throttle Pressure"
THROTTLE_TRACTION = "Throttle Resistance - Traction"
ACCEL_G_PUNCH = "Acceleration G Punch"
RPM_REV_LIMIT = "RPM Rev Limit"
SHIFT_DOWN_HOWL = "Shift Down Howl"
DRIFT_RUMBLE_FADE = "Drift Rumble Fade"
GEAR_SHIFT_KICK = "Gear Shift Kick"
COLLISION_KICK = "Collision Kick"
KERB_WAVE = "Kerb Wave"
IMPACT_TICK = "Impact Tick"
NATIVE_SOFT_PULSE_FREQUENCY_MAX = 180


@dataclass
class TriggerForceState:
    active: bool = False
    smoothed_force: float = 0.0
    previous_at: float = 0.0
    last_sent_force: int = 0


@dataclass(frozen=True)
class TriggerPulseOutput:
    display: int = 0
    pulse: int = 0
    pulse_rate: int = 0
    vibrate_amp: int = 0
    vibrate_freq: int = 0
    vibrate_start_zone: int = 0


@dataclass
class BrakePredictiveState:
    wall_smoothed: float = -1.0
    wall_start_percent: float = -1.0


@dataclass
class ThrottleTractionState:
    wall_smoothed: float = -1.0
    wall_start_percent: float = -1.0
    pulse_output: TriggerPulseOutput = field(default_factory=TriggerPulseOutput)


@dataclass
class AccelGPunchTriggerState:
    launch_active: bool = False
    launch_gear: int = 0
    shift_active: bool = False
    shift_gear: int = 0
    shift_start_ratio: float = 0.0
    shift_ready_at: float = 0.0
    shift_boost_until: float = 0.0
    previous_gear: int | None = None
    previous_rpm: float = 0.0
    last_pulse_level: float = 0.0


@dataclass
class ShiftDownHowlState:
    started_at: float = 0.0
    kick_until: float = 0.0
    howl_until: float = 0.0
    start_zone: int = 3
    previous_gear: int | None = None
    last_output: TriggerPulseOutput = field(default_factory=TriggerPulseOutput)


class TriggerEffectEngine:
    """Telemetry-to-trigger payload bridge for the PySide6 migration."""

    def __init__(self) -> None:
        self.brake_pressure = TriggerForceState()
        self.brake_resistance = TriggerForceState()
        self.brake_resistance_pulse = TriggerPulseOutput()
        self.brake_predictive = TriggerForceState()
        self.brake_predictive_state = BrakePredictiveState()
        self.brake_predictive_pulse = TriggerPulseOutput()
        self.throttle_pressure = TriggerForceState()
        self.throttle_traction = TriggerForceState()
        self.throttle_traction_state = ThrottleTractionState()
        self.accel_g_punch = TriggerForceState()
        self.accel_g_punch_state = AccelGPunchTriggerState()
        self.rpm_rev_limit = TriggerForceState()
        self.shift_down_howl = ShiftDownHowlState()
        self.kerb_wave_active = False
        self.dualsense_left_percent = 0.0
        self.dualsense_right_percent = 0.0
        self.dualsense_input_at = 0.0
        self.last_payloads: tuple[OutputEventPayload, ...] = ()
        self.last_trigger_output_specs: dict[str, dict[str, float]] = {}

    def reset(self) -> None:
        self.brake_pressure = TriggerForceState()
        self.brake_resistance = TriggerForceState()
        self.brake_resistance_pulse = TriggerPulseOutput()
        self.brake_predictive = TriggerForceState()
        self.brake_predictive_state = BrakePredictiveState()
        self.brake_predictive_pulse = TriggerPulseOutput()
        self.throttle_pressure = TriggerForceState()
        self.throttle_traction = TriggerForceState()
        self.throttle_traction_state = ThrottleTractionState()
        self.accel_g_punch = TriggerForceState()
        self.accel_g_punch_state = AccelGPunchTriggerState()
        self.rpm_rev_limit = TriggerForceState()
        self.shift_down_howl = ShiftDownHowlState()
        self.kerb_wave_active = False
        self.last_payloads = ()
        self.last_trigger_output_specs = {}

    def update_trigger_input(self, left_percent: float, right_percent: float, received_at: float) -> None:
        self.dualsense_left_percent = _clamp(float(left_percent), 0.0, 100.0)
        self.dualsense_right_percent = _clamp(float(right_percent), 0.0, 100.0)
        self.dualsense_input_at = max(0.0, float(received_at))

    def process_frame(
        self,
        frame: TelemetryFrame,
        trigger_effects: Mapping[str, EffectSetting],
        source_payloads: tuple[OutputEventPayload, ...] = (),
        effect_gains: Mapping[str, float] | None = None,
    ) -> tuple[OutputEventPayload, ...]:
        if not frame.parsed or frame.is_race_on is False:
            payloads = (
                *self._release_brake_payloads(),
                *self._release_throttle_payloads(),
                *self._release_kerb_wave_payloads(),
            )
            self.reset()
            self.last_payloads = payloads
            return payloads

        gains = effect_gains or {}
        payloads = (
            *self._brake_payloads(frame, trigger_effects, gains),
            *self._throttle_payloads(frame, trigger_effects, gains),
            *self._transient_payloads(frame, trigger_effects, source_payloads),
        )
        self.last_payloads = payloads
        return payloads

    def _brake_payloads(
        self,
        frame: TelemetryFrame,
        trigger_effects: Mapping[str, EffectSetting],
        effect_gains: Mapping[str, float],
    ) -> tuple[OutputEventPayload, ...]:
        pressure_setting = trigger_effects.get(BRAKE_PRESSURE)
        resistance_setting = trigger_effects.get(BRAKE_RESISTANCE)
        predictive_setting = trigger_effects.get(BRAKE_RESISTANCE_PREDICTIVE)
        pressure_enabled = pressure_setting is not None and pressure_setting.enabled
        resistance_enabled = resistance_setting is not None and resistance_setting.enabled
        predictive_enabled = predictive_setting is not None and predictive_setting.enabled
        if sum((pressure_enabled, resistance_enabled, predictive_enabled)) > 1:
            if predictive_enabled:
                pressure_enabled = False
                resistance_enabled = False
            elif resistance_enabled:
                pressure_enabled = False
        if not pressure_enabled and not resistance_enabled and not predictive_enabled:
            return self._release_brake_payloads()

        now = monotonic()
        pressure_dt = self._force_dt(self.brake_pressure, now)
        resistance_dt = self._force_dt(self.brake_resistance, now)
        predictive_dt = self._force_dt(self.brake_predictive, now)

        pressure_force = 0
        if pressure_enabled and pressure_setting is not None:
            pressure_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._brake_pressure_force(frame, pressure_setting),
                    effect_gains.get(BRAKE_PRESSURE, 1.0),
                ),
                pressure_setting,
                self.brake_pressure,
                pressure_dt,
            )

        resistance_force = 0
        if resistance_enabled and resistance_setting is not None:
            resistance_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._brake_resistance_force(frame, resistance_setting),
                    effect_gains.get(BRAKE_RESISTANCE, 1.0),
                ),
                resistance_setting,
                self.brake_resistance,
                resistance_dt,
            )

        predictive_force = 0
        if predictive_enabled and predictive_setting is not None:
            predictive_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._brake_resistance_predictive_force(frame, predictive_setting),
                    effect_gains.get(BRAKE_RESISTANCE_PREDICTIVE, 1.0),
                ),
                predictive_setting,
                self.brake_predictive,
                predictive_dt,
            )

        resistance_pulse = _apply_effect_gain_to_pulse(
            self.brake_resistance_pulse,
            effect_gains.get(BRAKE_RESISTANCE, 1.0),
        )
        predictive_pulse = _apply_effect_gain_to_pulse(
            self.brake_predictive_pulse,
            effect_gains.get(BRAKE_RESISTANCE_PREDICTIVE, 1.0),
        )
        force = _clamp_int(pressure_force + resistance_force + predictive_force, 0, 255)
        pulse_output = _merge_trigger_pulse_outputs(resistance_pulse, predictive_pulse)
        self.brake_pressure.last_sent_force = pressure_force
        self.brake_resistance.last_sent_force = resistance_force
        self.brake_predictive.last_sent_force = predictive_force
        start = self._brake_start_byte(
            resistance_force,
            resistance_setting,
            predictive_force,
            predictive_setting,
        )
        self._update_l2_debug_specs(
            now,
            pressure_force,
            resistance_force,
            predictive_force,
            resistance_setting,
            predictive_setting,
            resistance_pulse,
            predictive_pulse,
        )
        return (
            trigger_brake(
                force=force,
                start=start if start >= 0 else None,
                pulse=pulse_output.pulse,
                pulse_rate=pulse_output.pulse_rate,
                vibrate_amp=pulse_output.vibrate_amp,
                vibrate_freq=pulse_output.vibrate_freq,
                vibrate_start_zone=pulse_output.vibrate_start_zone,
            ),
        )

    def _throttle_payloads(
        self,
        frame: TelemetryFrame,
        trigger_effects: Mapping[str, EffectSetting],
        effect_gains: Mapping[str, float],
    ) -> tuple[OutputEventPayload, ...]:
        pressure_setting = trigger_effects.get(THROTTLE_PRESSURE)
        traction_setting = trigger_effects.get(THROTTLE_TRACTION)
        accel_setting = trigger_effects.get(ACCEL_G_PUNCH)
        rpm_setting = trigger_effects.get(RPM_REV_LIMIT)
        howl_setting = trigger_effects.get(SHIFT_DOWN_HOWL)
        pressure_enabled = pressure_setting is not None and pressure_setting.enabled
        traction_enabled = traction_setting is not None and traction_setting.enabled
        accel_enabled = accel_setting is not None and accel_setting.enabled
        rpm_enabled = rpm_setting is not None and rpm_setting.enabled
        howl_enabled = howl_setting is not None and howl_setting.enabled
        if not pressure_enabled and not traction_enabled and not accel_enabled and not rpm_enabled and not howl_enabled:
            return self._release_throttle_payloads()

        now = monotonic()
        pressure_dt = self._force_dt(self.throttle_pressure, now)
        traction_dt = self._force_dt(self.throttle_traction, now)
        accel_dt = self._force_dt(self.accel_g_punch, now)
        rpm_dt = self._force_dt(self.rpm_rev_limit, now)

        pressure_force = 0
        if pressure_enabled and pressure_setting is not None:
            pressure_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._throttle_pressure_force(frame, pressure_setting),
                    effect_gains.get(THROTTLE_PRESSURE, 1.0),
                ),
                pressure_setting,
                self.throttle_pressure,
                pressure_dt,
            )

        traction_force = 0
        if traction_enabled and traction_setting is not None:
            traction_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._throttle_traction_force(frame, traction_setting),
                    effect_gains.get(THROTTLE_TRACTION, 1.0),
                ),
                traction_setting,
                self.throttle_traction,
                traction_dt,
            )

        accel_force = 0
        if accel_enabled and accel_setting is not None:
            accel_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    self._accel_g_punch_force(frame, accel_setting, now),
                    effect_gains.get(ACCEL_G_PUNCH, 1.0),
                ),
                accel_setting,
                self.accel_g_punch,
                accel_dt,
            )
        else:
            self.accel_g_punch = TriggerForceState()
            self.accel_g_punch_state = AccelGPunchTriggerState()

        rpm_force = 0
        rpm_pulse = TriggerPulseOutput()
        if rpm_enabled and rpm_setting is not None:
            rpm_target_force = self._rpm_rev_limit_force(frame, rpm_setting)
            rpm_force = self._smooth_force(
                _apply_effect_gain_to_force(
                    rpm_target_force,
                    effect_gains.get(RPM_REV_LIMIT, 1.0),
                ),
                rpm_setting,
                self.rpm_rev_limit,
                rpm_dt,
            )
            rpm_pulse = _apply_effect_gain_to_pulse(
                self._rpm_rev_limit_pulse_output(rpm_setting, rpm_target_force),
                effect_gains.get(RPM_REV_LIMIT, 1.0),
            )
        else:
            self.rpm_rev_limit = TriggerForceState()

        accel_pulse = TriggerPulseOutput()
        if accel_enabled and accel_setting is not None:
            accel_pulse = _apply_effect_gain_to_pulse(
                self._accel_g_punch_pulse_output(accel_setting, self.accel_g_punch_state.last_pulse_level),
                effect_gains.get(ACCEL_G_PUNCH, 1.0),
            )

        howl_output = TriggerPulseOutput()
        if howl_enabled and howl_setting is not None:
            self._track_shift_down_howl(frame, howl_setting, now)
            howl_output = _apply_effect_gain_to_pulse(
                self._shift_down_howl_output(howl_setting, now),
                effect_gains.get(SHIFT_DOWN_HOWL, 1.0),
            )
        else:
            self.shift_down_howl = ShiftDownHowlState()

        traction_pulse = (
            _apply_effect_gain_to_pulse(
                self.throttle_traction_state.pulse_output,
                effect_gains.get(THROTTLE_TRACTION, 1.0),
            )
            if traction_enabled
            else TriggerPulseOutput()
        )
        pulse_output = _merge_trigger_pulse_outputs(traction_pulse, accel_pulse, rpm_pulse, howl_output)
        self.shift_down_howl.last_output = howl_output

        force = _clamp_int(pressure_force + traction_force + accel_force + rpm_force, 0, 255)
        self.throttle_pressure.last_sent_force = pressure_force
        self.throttle_traction.last_sent_force = traction_force
        self.accel_g_punch.last_sent_force = accel_force
        self.rpm_rev_limit.last_sent_force = rpm_force
        start = self._throttle_start_byte(traction_force)
        self._update_r2_debug_specs(
            now,
            pressure_force,
            traction_force,
            accel_force,
            rpm_force,
            traction_pulse,
            accel_pulse,
            rpm_pulse,
            howl_output,
        )
        return (
            trigger_throttle(
                force=force,
                start=start if start >= 0 else None,
                pulse=pulse_output.pulse,
                pulse_rate=pulse_output.pulse_rate,
                vibrate_amp=pulse_output.vibrate_amp,
                vibrate_freq=pulse_output.vibrate_freq,
                vibrate_start_zone=pulse_output.vibrate_start_zone,
            ),
        )

    def _transient_payloads(
        self,
        frame: TelemetryFrame,
        trigger_effects: Mapping[str, EffectSetting],
        source_payloads: tuple[OutputEventPayload, ...],
    ) -> tuple[OutputEventPayload, ...]:
        payloads: list[OutputEventPayload] = []
        for source in source_payloads:
            fields = dict(source.params)
            if source.name == "GEAR_SHIFT":
                payload = self._gear_shift_kick_payload(trigger_effects, fields)
            elif source.name in {"IMPACT", "IMPACT_SIDE"}:
                payload = self._collision_kick_payload(frame, trigger_effects, fields)
            elif source.name == "IMPACT_SMASHABLE":
                payload = self._impact_tick_payload(trigger_effects, fields)
            elif source.name == "RUMBLE_KERBS":
                payload = self._kerb_wave_payload(trigger_effects, fields)
            else:
                payload = None
            if payload is not None:
                payloads.append(payload)
        return tuple(payloads)

    def _gear_shift_kick_payload(
        self,
        trigger_effects: Mapping[str, EffectSetting],
        source_fields: Mapping[str, str],
    ) -> OutputEventPayload | None:
        setting = trigger_effects.get(GEAR_SHIFT_KICK)
        if setting is None or not setting.enabled:
            return None
        direction = _field_int(source_fields, "dir", 0)
        is_upshift = direction > 0
        howl = trigger_effects.get(SHIFT_DOWN_HOWL)
        if not is_upshift and howl is not None and howl.enabled:
            return None

        details = setting.details or {}
        strength_key = "upshift_strength_percent" if is_upshift else "downshift_strength_percent"
        duration_key = "upshift_duration_ms" if is_upshift else "downshift_duration_ms"
        side_key = "upshift_sides" if is_upshift else "downshift_sides"
        side = _normalize_trigger_side(details.get(side_key), "right" if is_upshift else "left")
        strength = self._gear_shift_softened_strength(
            _detail_int(details, strength_key, 70, 0, 100),
            side,
            _detail_int(details, "early_input_soft_zone", 0, 0, 60),
        )
        if strength <= 0:
            return None
        late_position = _detail_int(details, "kick_late_position", 0, 0, 100)
        return trigger_gear_shift(
            side=side,
            strength=strength,
            start=_wall_position_percent_to_start_byte(late_position) if late_position > 0 else None,
            duration_ms=_detail_int(details, duration_key, 45, 20, 180),
            direction=1 if is_upshift else -1,
            softness=_detail_int(details, "kick_softness", 7, 0, 10),
            release_ms=_detail_int(details, "release_duration_ms", 45, 0, 120),
        )

    def _gear_shift_softened_strength(self, strength: int, side: str, soft_zone: int) -> int:
        if soft_zone <= 0 or self.dualsense_input_at <= 0.0 or monotonic() - self.dualsense_input_at > 1.0:
            return strength
        if side == "left":
            trigger_percent = self.dualsense_left_percent
        elif side == "right":
            trigger_percent = self.dualsense_right_percent
        else:
            trigger_percent = max(self.dualsense_left_percent, self.dualsense_right_percent)
        mix = _clamp(trigger_percent / max(1.0, float(soft_zone)), 0.0, 1.0)
        return _clamp_int(round(strength * (0.35 + 0.65 * mix)), 0, 100)

    def _collision_kick_payload(
        self,
        frame: TelemetryFrame,
        trigger_effects: Mapping[str, EffectSetting],
        source_fields: Mapping[str, str],
    ) -> OutputEventPayload | None:
        setting = trigger_effects.get(COLLISION_KICK)
        if setting is None or not setting.enabled:
            return None
        power = _field_float(source_fields, "power", 0.0)
        if power < 0.14:
            return None
        details = setting.details or {}
        base_strength = _detail_int(details, "force_percent", 80, 0, 100)
        strength = max(1, min(100, int(round(base_strength * _clamp(power, 0.20, 1.0)))))
        if strength <= 0:
            return None
        return trigger_event(
            "TRIGGER_COLLISION_KICK",
            side="left" if float(frame.accel_x or 0.0) < 0.0 else "right",
            strength=strength,
            durationMs=_detail_int(details, "smooth_start_ms", 80, 40, 300),
        )

    def _impact_tick_payload(
        self,
        trigger_effects: Mapping[str, EffectSetting],
        source_fields: Mapping[str, str],
    ) -> OutputEventPayload | None:
        setting = trigger_effects.get(IMPACT_TICK)
        if setting is None or not setting.enabled:
            return None
        power = _field_float(source_fields, "power", 0.0)
        if power < 0.08:
            return None
        details = setting.details or {}
        base_amp = _detail_int(details, "slip_soft_pulse_amplitude", 2, 1, 8)
        amp = max(1, min(8, int(round(base_amp * _clamp(power, 0.15, 1.0)))))
        return trigger_event(
            "TRIGGER_IMPACT_TICK",
            amp=amp,
            freq=_detail_int(
                details,
                "slip_soft_pulse_frequency",
                40,
                1,
                NATIVE_SOFT_PULSE_FREQUENCY_MAX,
            ),
            startZone=_detail_int(details, "slip_soft_pulse_start_zone", 0, 0, 9),
            durationMs=_detail_int(details, "smooth_start_ms", 80, 40, 300),
        )

    def _kerb_wave_payload(
        self,
        trigger_effects: Mapping[str, EffectSetting],
        source_fields: Mapping[str, str],
    ) -> OutputEventPayload | None:
        setting = trigger_effects.get(KERB_WAVE)
        details = setting.details if setting is not None else {}
        enabled = setting is not None and setting.enabled
        kerb_level = max(
            0.0,
            _field_float(source_fields, "fl", 0.0),
            _field_float(source_fields, "fr", 0.0),
        )
        kerb_on = enabled and kerb_level > 0.0
        left_on = kerb_on and _detail_bool(details, "kerb_l_enabled", True)
        right_on = kerb_on and _detail_bool(details, "kerb_r_enabled", True)
        if not left_on and not right_on and not self.kerb_wave_active:
            return None

        speed = max(0.0, _field_float(source_fields, "speed", 0.0))
        shared_amp = _clamp_int(
            round(
                _kerb_wave_value(
                    speed,
                    _detail_int(details, "kerb_l_low_amp", 2, 1, 8),
                    _detail_int(details, "kerb_l_high_amp", 5, 1, 8),
                )
            ),
            0,
            8,
        )
        legacy_low_hz = _detail_int(
            details,
            "kerb_l_low_hz",
            24,
            1,
            NATIVE_SOFT_PULSE_FREQUENCY_MAX,
        )
        legacy_high_hz = _detail_int(
            details,
            "kerb_l_high_hz",
            70,
            1,
            NATIVE_SOFT_PULSE_FREQUENCY_MAX,
        )
        shared_low_hz = _detail_int(
            details,
            "kerb_low_hz",
            legacy_low_hz,
            1,
            NATIVE_SOFT_PULSE_FREQUENCY_MAX,
        )
        shared_high_hz = _detail_int(
            details,
            "kerb_high_hz",
            legacy_high_hz,
            1,
            NATIVE_SOFT_PULSE_FREQUENCY_MAX,
        )
        shared_frequency = _kerb_wave_value(speed, shared_low_hz, shared_high_hz)
        shared_start_zone = _start_percent_to_zone(
            _detail_int(details, "kerb_l_start_percent", 0, 0, 100)
        )
        left_on = left_on and shared_amp > 0
        right_on = right_on and shared_amp > 0
        self.kerb_wave_active = left_on or right_on
        return trigger_event(
            "TRIGGER_KERB_BUZZ",
            left=1 if left_on else 0,
            right=1 if right_on else 0,
            leftAmp=shared_amp if left_on else 0,
            leftFreq=shared_frequency if left_on else 0,
            leftStartZone=shared_start_zone,
            rightAmp=shared_amp if right_on else 0,
            rightFreq=shared_frequency if right_on else 0,
            rightStartZone=shared_start_zone,
        )

    def _release_kerb_wave_payloads(self) -> tuple[OutputEventPayload, ...]:
        if not self.kerb_wave_active:
            return ()
        self.kerb_wave_active = False
        return (
            trigger_event(
                "TRIGGER_KERB_BUZZ",
                left=0,
                right=0,
                leftAmp=0,
                leftFreq=0,
                leftStartZone=0,
                rightAmp=0,
                rightFreq=0,
                rightStartZone=0,
            ),
        )

    def _brake_pressure_force(self, frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        brake_percent = _clamp(float(frame.brake or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        start = _detail_int(details, "start_percent", 0, 0, 100)
        end = _detail_int(details, "max_percent", 100, 0, 100)
        if end <= start:
            end = min(100, start + 1)

        active, ramp_start = self._hysteresis(self.brake_pressure, brake_percent, start)
        if not active:
            return 0

        mix = _clamp((brake_percent - ramp_start) / max(1.0, end - ramp_start), 0.0, 1.0)
        max_force = 255.0 * _detail_int(details, "force_percent", 45, 0, 100) / 100.0
        return _clamp_int(round(max_force * mix), 0, 255)

    def _throttle_pressure_force(self, frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        throttle_percent = _clamp(float(frame.throttle or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        start = _detail_int(details, "start_percent", 0, 0, 100)
        end = _detail_int(details, "max_percent", 100, 0, 100)
        if end <= start:
            end = min(100, start + 1)

        active, ramp_start = self._hysteresis(self.throttle_pressure, throttle_percent, start)
        if not active:
            return 0

        mix = _clamp((throttle_percent - ramp_start) / max(1.0, end - ramp_start), 0.0, 1.0)
        max_force = 255.0 * _detail_int(details, "force_percent", 35, 0, 100) / 100.0
        return _clamp_int(round(max_force * mix), 0, 255)

    def _throttle_traction_force(self, frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        self.throttle_traction_state.pulse_output = TriggerPulseOutput()
        throttle_percent = _clamp(float(frame.throttle or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        speed_kmh = max(0.0, float(frame.speed or 0.0))
        if throttle_percent < 3.0 or speed_kmh < 4.0:
            self.throttle_traction.active = False
            self.throttle_traction_state = ThrottleTractionState()
            return 0

        base_wall = 100
        min_wall = _detail_int(details, "max_percent", 45, 20, 95)
        min_wall = min(min_wall, max(20, base_wall - 1))
        prediction_strength = _detail_int(details, "wall_percent", 35, 0, 60)
        slip_threshold = _detail_float(details, "slip_threshold", 1.6, 0.1, 50.0) / 10.0
        slip_end_threshold = _detail_float(details, "slip_end_threshold", 2.2, 0.1, 50.0) / 10.0
        slip_end_threshold = max(slip_threshold + 0.1, slip_end_threshold)

        driven_slip, driven_combined = self._throttle_driven_slip_values(frame)
        throttle_gate = _smoothstep(12.0, 60.0, throttle_percent)
        speed_gate = 1.0 - _smoothstep(210.0, 270.0, speed_kmh)
        ratio_start = max(0.25, slip_threshold * 0.55)
        ratio_risk = _smoothstep(ratio_start, slip_threshold, driven_slip)
        combined_risk = _smoothstep(0.35, max(0.75, slip_threshold * 0.85), driven_combined) * 0.55
        risk = _clamp(max(ratio_risk, combined_risk) * throttle_gate * speed_gate, 0.0, 1.0)

        wall_target = max(float(min_wall), min(100.0, float(base_wall) - prediction_strength * risk))
        previous_wall = self.throttle_traction_state.wall_smoothed
        if previous_wall < 0.0:
            wall_position = wall_target
        else:
            alpha = 0.30 if wall_target < previous_wall else 0.12
            wall_position = previous_wall + (wall_target - previous_wall) * alpha
        wall_position = _clamp(wall_position, float(min_wall), 100.0)
        self.throttle_traction_state.wall_smoothed = wall_position
        self.throttle_traction_state.wall_start_percent = wall_position

        max_force = 255.0 * _detail_int(details, "force_percent", 35, 0, 100) / 100.0
        if driven_slip >= slip_end_threshold:
            drop_force = 255.0 * _detail_int(details, "slip_drop_low_percent", 0, 0, 100) / 100.0
            return _clamp_int(round(drop_force), 0, 255)

        force_gate = max(0.18, risk) if throttle_percent >= max(8.0, wall_position - 18.0) else risk
        force = max_force * _clamp(force_gate, 0.0, 1.0)
        pulse_enabled = _detail_bool(details, "slip_pulse_enabled", False)
        slip_level = driven_slip / max(0.1, slip_threshold)
        pulse_start_level = _detail_int(details, "slip_pulse_start_percent", 15, 10, 99) / 100.0
        pulse_end_level = _detail_int(details, "slip_pulse_end_percent", 100, 100, 150) / 100.0
        pulse_active = pulse_enabled and pulse_start_level <= slip_level < pulse_end_level
        if pulse_active:
            style_text = str(details.get("slip_pulse_style", "Soft Pulse")).strip().lower()
            if style_text in {"pulse kick", "pulse_kick", "kick"}:
                low_force = 255.0 * _detail_int(details, "slip_low_percent", 10, 0, 100) / 100.0
                high_force = 255.0 * _detail_int(details, "slip_pulse_high_percent", 35, 0, 100) / 100.0
                rate = _detail_int(details, "slip_pulse_rate", 12, 1, SLIP_PULSE_RATE_MAX)
                phase = (monotonic() * rate) % 1.0
                force = high_force if phase < 0.5 else low_force
            else:
                self.throttle_traction_state.pulse_output = _throttle_traction_pulse_output(details, wall_position)

        return _clamp_int(round(force), 0, 255)

    def _update_r2_debug_specs(
        self,
        now: float,
        pressure_force: int,
        traction_force: int,
        accel_force: int,
        rpm_force: int,
        traction_pulse: TriggerPulseOutput,
        accel_pulse: TriggerPulseOutput,
        rpm_pulse: TriggerPulseOutput,
        howl_output: TriggerPulseOutput,
    ) -> None:
        traction_wall = self.throttle_traction_state.wall_start_percent
        traction_wall = traction_wall if traction_wall >= 0.0 else 100.0
        self.last_trigger_output_specs.update(
            {
                THROTTLE_PRESSURE: _trigger_debug_spec(pressure_force, 0.0, 100.0, updated_at=now),
                THROTTLE_TRACTION: _trigger_debug_spec(
                    traction_force,
                    traction_wall,
                    100.0,
                    traction_pulse,
                    updated_at=now,
                ),
                ACCEL_G_PUNCH: _trigger_debug_spec(accel_force, 0.0, 100.0, accel_pulse, updated_at=now),
                RPM_REV_LIMIT: _trigger_debug_spec(rpm_force, 0.0, 100.0, rpm_pulse, updated_at=now),
                SHIFT_DOWN_HOWL: _trigger_debug_spec(
                    howl_output.display,
                    0.0,
                    100.0,
                    howl_output,
                    updated_at=now,
                ),
            }
        )

    def _update_l2_debug_specs(
        self,
        now: float,
        pressure_force: int,
        resistance_force: int,
        predictive_force: int,
        resistance_setting: EffectSetting | None,
        predictive_setting: EffectSetting | None,
        resistance_pulse: TriggerPulseOutput,
        predictive_pulse: TriggerPulseOutput,
    ) -> None:
        resistance_wall = 100.0
        if resistance_force > 0 and resistance_setting is not None:
            resistance_wall = float(_detail_int(resistance_setting.details or {}, "start_percent", 0, 0, 100))

        predictive_wall = 100.0
        if (
            predictive_force > 0
            and predictive_setting is not None
            and self.brake_predictive_state.wall_start_percent >= 0.0
        ):
            predictive_wall = self.brake_predictive_state.wall_start_percent

        self.last_trigger_output_specs.update(
            {
                BRAKE_PRESSURE: _trigger_debug_spec(pressure_force, 0.0, 100.0, updated_at=now),
                BRAKE_RESISTANCE: _trigger_debug_spec(
                    resistance_force,
                    resistance_wall,
                    100.0,
                    resistance_pulse,
                    updated_at=now,
                ),
                BRAKE_RESISTANCE_PREDICTIVE: _trigger_debug_spec(
                    predictive_force,
                    predictive_wall,
                    100.0,
                    predictive_pulse,
                    updated_at=now,
                ),
            }
        )

    def _accel_g_punch_force(self, frame: TelemetryFrame, setting: EffectSetting, now: float) -> int:
        details = setting.details or {}
        gear = int(frame.gear or 0)
        if gear == TRANSIENT_GEAR_VALUE:
            self.accel_g_punch_state.last_pulse_level = 0.0
            return 0

        self._track_accel_g_punch_shift(frame, setting, now)

        speed_kmh = max(0.0, float(frame.speed or 0.0))
        throttle_percent = _clamp(float(frame.throttle or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        max_rpm = max(1.0, float(frame.max_rpm or 1.0))
        rpm_ratio = _clamp(float(frame.rpm or 0.0) / max_rpm, 0.0, 1.15)

        state = self.accel_g_punch_state
        launch_allowed = gear in (0, 1)
        if launch_allowed and not state.launch_active and throttle_percent >= 6.0:
            state.launch_active = True
            state.launch_gear = gear
        if state.launch_active and (not launch_allowed or gear != state.launch_gear):
            state.launch_active = False

        launch_level = 0.0
        launch_pulse_level = 0.0
        pulse_gear_factor = _accel_g_punch_pulse_gear_factor(details, gear)
        if state.launch_active:
            if throttle_percent < 4.0:
                state.launch_active = False
            else:
                launch_level = _accel_g_punch_launch_accel_level(frame, throttle_percent)
                launch_pulse_level = launch_level * pulse_gear_factor

        shift_level = self._accel_g_punch_shift_level(frame, details, gear, rpm_ratio, throttle_percent, now)
        shift_pulse_level = self._accel_g_punch_shift_pulse_level(frame, details, gear, rpm_ratio, throttle_percent, now)
        low_gear_accel_level = 0.0
        low_gear_accel_pulse_level = 0.0
        low_gear_factor = _accel_g_punch_low_gear_accel_factor(gear)
        shift_delay_active = (
            state.shift_active
            and gear == state.shift_gear
            and now < state.shift_ready_at
        )
        if low_gear_factor > 0.0 and throttle_percent >= 6.0 and not shift_delay_active:
            accel_level = _accel_g_punch_launch_accel_level(frame, throttle_percent)
            speed_gate = 1.0 - _smoothstep(185.0, 260.0, speed_kmh)
            low_gear_accel_level = accel_level * low_gear_factor * speed_gate
            low_gear_accel_pulse_level = low_gear_accel_level * pulse_gear_factor

        level = max(launch_level, shift_level, low_gear_accel_level)
        state.last_pulse_level = max(launch_pulse_level, shift_pulse_level, low_gear_accel_pulse_level)
        if level <= 0.0:
            return 0

        max_force = 255.0 * _detail_int(details, "force_percent", 35, 0, 100) / 100.0
        return _clamp_int(round(max_force * _clamp(level, 0.0, 1.0)), 0, 255)

    @staticmethod
    def _rpm_rev_limit_force(frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        max_rpm = max(1.0, float(frame.max_rpm or 1.0))
        rpm_ratio = _clamp(float(frame.rpm or 0.0) / max_rpm, 0.0, 1.25)
        throttle_gate = _smoothstep(0.08, 0.30, _clamp(float(frame.throttle or 0.0) / 255.0, 0.0, 1.0))
        start_ratio = _detail_int(details, "start_percent", 90, 80, 99) / 100.0
        limit_gate = _smoothstep(start_ratio, 1.00, rpm_ratio) * throttle_gate
        if limit_gate <= 0.0:
            return 0

        style = _normalize_pulse_style(details.get("slip_pulse_style", "Soft Pulse"), default_style="Soft Pulse")
        if style == "Strong Pulse":
            strong_amp = _detail_int(details, "slip_strong_pulse_amplitude", 80, 1, 255)
            return _clamp_int(round(strong_amp * limit_gate), 0, 255)

        soft_amp = _detail_int(details, "slip_soft_pulse_amplitude", 3, 1, 8)
        force = 255.0 * soft_amp / 8.0 * limit_gate
        return _clamp_int(round(force), 0, 255)

    def _track_accel_g_punch_shift(self, frame: TelemetryFrame, setting: EffectSetting, now: float) -> None:
        gear = int(frame.gear or 0)
        if gear < 1 or gear == TRANSIENT_GEAR_VALUE:
            return
        state = self.accel_g_punch_state
        previous = state.previous_gear
        state.previous_gear = gear
        state.previous_rpm = max(0.0, float(frame.rpm or 0.0))
        if previous is None or previous <= 0 or gear <= previous:
            return

        details = setting.details or {}
        state.shift_active = True
        state.shift_gear = gear
        state.shift_start_ratio = -1.0
        delay_ms = _detail_int(details, "smooth_start_ms", 80, 0, 200)
        boost_ms = _detail_int(details, "shift_pulse_boost_ms", 90, 0, 200)
        state.shift_ready_at = now + delay_ms / 1000.0
        state.shift_boost_until = state.shift_ready_at + boost_ms / 1000.0

    def _track_shift_down_howl(self, frame: TelemetryFrame, setting: EffectSetting, now: float) -> None:
        gear = int(frame.gear or 0)
        state = self.shift_down_howl
        if gear <= 0 or gear == TRANSIENT_GEAR_VALUE:
            return

        previous = state.previous_gear
        state.previous_gear = gear
        if previous is None or previous <= gear:
            return

        details = setting.details or {}
        kick_ms = _detail_int(details, "kick_strong_pulse_duration_ms", 45, 0, 180)
        howl_ms = _detail_int(details, "howl_duration_ms", 360, 40, 1200)
        if kick_ms <= 0 and howl_ms <= 0:
            return

        state.started_at = now
        state.kick_until = now + kick_ms / 1000.0
        state.howl_until = state.kick_until + howl_ms / 1000.0
        state.start_zone = _detail_int(details, "howl_start_zone", 3, 0, 9)

    def _shift_down_howl_output(self, setting: EffectSetting, now: float) -> TriggerPulseOutput:
        details = setting.details or {}
        state = self.shift_down_howl
        if state.started_at <= 0.0 or now >= state.howl_until:
            state.started_at = 0.0
            state.kick_until = 0.0
            state.howl_until = 0.0
            state.start_zone = _detail_int(details, "howl_start_zone", 3, 0, 9)
            return TriggerPulseOutput()

        kick_strength = _detail_int(details, "kick_strong_pulse_strength", 65, 0, 100)
        kick_hz = _detail_int(details, "kick_strong_pulse_hz", 110, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX)
        if now < state.kick_until and kick_strength > 0:
            return TriggerPulseOutput(
                display=_clamp_int(round(kick_strength / 100.0 * 255.0), 0, 255),
                vibrate_amp=_amp_from_percent(kick_strength),
                vibrate_freq=kick_hz,
                vibrate_start_zone=state.start_zone,
            )

        howl_total = max(0.001, state.howl_until - state.kick_until)
        progress = _clamp((now - state.kick_until) / howl_total, 0.0, 1.0)
        fade = max(0.0, 1.0 - progress)
        start_hz = _detail_int(details, "howl_start_hz", 40, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX)
        end_hz = _detail_int(details, "howl_end_hz", 40, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX)
        freq = start_hz + (end_hz - start_hz) * progress
        amp = float(_detail_int(details, "howl_amp", 2, 1, 8)) * fade
        noise = _detail_int(details, "howl_noise_percent", 3, 0, 10) / 10.0
        if noise > 0.0:
            wobble = math.sin(now * 61.0) * 0.65 + math.sin(now * 97.0 + 1.7) * 0.35
            freq += wobble * noise * 12.0 * fade
            amp *= 1.0 + wobble * noise * 0.16 * fade
        if amp < 0.45:
            return TriggerPulseOutput()

        vibrate_amp = _clamp_int(round(amp), 1, 8)
        return TriggerPulseOutput(
            display=_clamp_int(round(vibrate_amp / 8.0 * 255.0), 0, 255),
            vibrate_amp=vibrate_amp,
            vibrate_freq=_clamp_int(round(freq), 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX),
            vibrate_start_zone=state.start_zone,
        )

    def _accel_g_punch_shift_level(
        self,
        frame: TelemetryFrame,
        details: Mapping[str, object],
        gear: int,
        rpm_ratio: float,
        throttle_percent: float,
        now: float,
    ) -> float:
        state = self.accel_g_punch_state
        if not state.shift_active:
            return 0.0

        shift_start_ratio = _clamp(state.shift_start_ratio, 0.0, 0.95)
        trigger_start_unset = state.shift_start_ratio < 0.0
        if now >= state.shift_ready_at and trigger_start_unset:
            shift_start_ratio = _clamp(rpm_ratio, 0.0, 0.95)
            state.shift_start_ratio = shift_start_ratio

        shift_output_end_ratio = _accel_g_punch_output_end_ratio(details, gear)
        raw_shift_end_ratio = min(1.0, max(shift_start_ratio + 0.05, shift_output_end_ratio))
        shift_end_ratio = _accel_g_punch_wall_fade_end_ratio(details, gear, shift_start_ratio, raw_shift_end_ratio)
        shift_wall_fade_ratio = _accel_g_punch_wall_fade_start_ratio(details, gear, shift_start_ratio, raw_shift_end_ratio)
        shift_wall_fade_ratio = min(shift_wall_fade_ratio, shift_end_ratio - 0.01)

        if (
            gear != state.shift_gear
            or (not trigger_start_unset and rpm_ratio >= shift_end_ratio)
            or throttle_percent < 4.0
        ):
            state.shift_active = False
            return 0.0
        if now < state.shift_ready_at:
            return 0.0

        if rpm_ratio <= shift_wall_fade_ratio:
            rpm_gate = 1.0
        else:
            rpm_gate = 1.0 - _smoothstep(shift_wall_fade_ratio, shift_end_ratio, rpm_ratio)
        throttle_gate = _smoothstep(8.0, 55.0, throttle_percent)
        return rpm_gate * throttle_gate * _accel_g_punch_shift_gear_factor(gear)

    def _accel_g_punch_shift_pulse_level(
        self,
        frame: TelemetryFrame,
        details: Mapping[str, object],
        gear: int,
        rpm_ratio: float,
        throttle_percent: float,
        now: float,
    ) -> float:
        del frame
        state = self.accel_g_punch_state
        if (
            not state.shift_active
            or gear != state.shift_gear
            or now < state.shift_ready_at
            or throttle_percent < 4.0
        ):
            return 0.0
        if now < state.shift_boost_until:
            return 1.0

        shift_start_ratio = _clamp(state.shift_start_ratio, 0.0, 0.95)
        shift_output_end_ratio = _accel_g_punch_output_end_ratio(details, gear)
        raw_shift_end_ratio = min(1.0, max(shift_start_ratio + 0.05, shift_output_end_ratio))
        shift_end_ratio = _accel_g_punch_wall_fade_end_ratio(details, gear, shift_start_ratio, raw_shift_end_ratio)
        if rpm_ratio >= shift_end_ratio:
            return 0.0

        throttle_gate = _smoothstep(8.0, 55.0, throttle_percent)
        rpm_gate = 1.0 - _smoothstep(shift_start_ratio, shift_end_ratio, rpm_ratio)
        return (
            rpm_gate
            * throttle_gate
            * _accel_g_punch_shift_gear_factor(gear)
            * _accel_g_punch_pulse_gear_factor(details, gear)
        )

    @staticmethod
    def _accel_g_punch_pulse_output(setting: EffectSetting, pulse_level: float) -> TriggerPulseOutput:
        details = setting.details or {}
        if not _detail_bool(details, "slip_pulse_enabled", True):
            return TriggerPulseOutput()
        pulse_strength = _detail_int(details, "pulse_strength", 18, 0, 100)
        return _trigger_pulse_output_from_style(
            details,
            _clamp(pulse_level, 0.0, 1.0) * pulse_strength / 100.0,
            default_style="Soft Pulse",
            default_strong_amp=80,
            default_strong_rate=80,
            default_soft_amp=3,
            default_soft_frequency=24,
            default_soft_start_zone=1,
        )

    @staticmethod
    def _rpm_rev_limit_pulse_output(setting: EffectSetting, target_force: int) -> TriggerPulseOutput:
        if target_force <= 0:
            return TriggerPulseOutput()
        details = setting.details or {}
        style = _normalize_pulse_style(details.get("slip_pulse_style", "Soft Pulse"), default_style="Soft Pulse")
        if style == "Strong Pulse":
            strong_amp = _detail_int(details, "slip_strong_pulse_amplitude", 80, 1, 255)
            limit_gate = _clamp(float(target_force) / max(1.0, float(strong_amp)), 0.0, 1.0)
            pulse = _clamp_int(round(strong_amp * limit_gate), 0, 255)
            if pulse <= 0:
                return TriggerPulseOutput()
            return TriggerPulseOutput(
                display=pulse,
                pulse=pulse,
                pulse_rate=_detail_int(details, "slip_strong_pulse_rate", 80, 1, 255),
            )

        soft_amp = _detail_int(details, "slip_soft_pulse_amplitude", 2, 1, 8)
        soft_full_scale = max(1.0, 255.0 * soft_amp / 8.0)
        limit_gate = _clamp(float(target_force) / soft_full_scale, 0.0, 1.0)
        vibrate_amp = _clamp_int(round(soft_amp * limit_gate), 0, 8)
        if vibrate_amp <= 0:
            return TriggerPulseOutput()
        return TriggerPulseOutput(
            display=_clamp_int(round(255.0 * vibrate_amp / 8.0), 0, 255),
            vibrate_amp=vibrate_amp,
            vibrate_freq=_detail_int(details, "slip_soft_pulse_frequency", 40, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX),
            vibrate_start_zone=_detail_int(details, "slip_soft_pulse_start_zone", 0, 0, 9),
        )

    def _brake_resistance_force(self, frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        self.brake_resistance_pulse = TriggerPulseOutput()
        max_force = 255.0 * _detail_int(details, "force_percent", 70, 0, 100) / 100.0
        brake_percent = _clamp(float(frame.brake or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        speed_kmh = max(0.0, float(frame.speed or 0.0))
        slip_release_enabled = (
            _detail_bool(details, "slip_off", False)
            or str(details.get("slip_response_mode", SLIP_RESPONSE_OFF)) != SLIP_RESPONSE_OFF
            or _detail_bool(details, "slip_pulse_enabled", False)
        )
        if slip_release_enabled and brake_percent >= 10.0 and speed_kmh >= BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH:
            slip_threshold = _detail_float(details, "slip_threshold", 1.6, 0.1, 50.0) / 10.0
            slip_level = self._brake_resistance_slip_off_level(frame, slip_threshold)
            force, self.brake_resistance_pulse = self._brake_slip_response(
                details,
                max_force,
                slip_level,
                float(_detail_int(details, "start_percent", 0, 0, 100)),
                monotonic(),
            )
            return _clamp_int(round(force), 0, 255)
        return _clamp_int(round(max_force), 0, 255)

    def _brake_resistance_predictive_force(self, frame: TelemetryFrame, setting: EffectSetting) -> int:
        details = setting.details or {}
        self.brake_predictive_pulse = TriggerPulseOutput()
        if int(frame.handbrake or 0) > 0:
            self.brake_predictive.active = False
            self.brake_predictive_state = BrakePredictiveState()
            return 0

        brake_percent = _clamp(float(frame.brake or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        speed_kmh = max(0.0, float(frame.speed or 0.0))
        base_wall = _detail_int(details, "start_percent", 40, 40, 100)
        min_wall = _detail_int(details, "max_percent", 30, 30, 95)
        min_wall = min(min_wall, max(30, base_wall - 1))
        prediction_strength = _detail_int(details, "wall_percent", 0, 0, 40)
        risk = self._brake_predictive_risk(frame)

        moving_wall_target = max(float(min_wall), min(100.0, float(base_wall) - prediction_strength * risk))
        previous_wall = self.brake_predictive_state.wall_smoothed
        if previous_wall < 0.0:
            moving_wall = moving_wall_target
        else:
            alpha = 0.24 if moving_wall_target < previous_wall else 0.10
            moving_wall = previous_wall + (moving_wall_target - previous_wall) * alpha
        wall_position = _clamp(moving_wall, float(min_wall), 100.0)
        self.brake_predictive_state.wall_smoothed = wall_position
        self.brake_predictive_state.wall_start_percent = wall_position

        slip_threshold = _detail_float(details, "slip_threshold", 1.6, 0.1, 50.0) / 10.0
        if speed_kmh >= BRAKE_SLIP_RESPONSE_MIN_SPEED_KMH and brake_percent >= max(3.0, wall_position - 2.0):
            slip_level = self._brake_resistance_slip_off_level(frame, slip_threshold)
        else:
            slip_level = 0.0

        base_force = 255.0 * _detail_int(details, "force_percent", 70, 0, 100) / 100.0
        force, self.brake_predictive_pulse = self._brake_slip_response(
            details,
            base_force,
            slip_level,
            wall_position,
            monotonic(),
        )
        return _clamp_int(round(force), 0, 255)

    def _brake_start_byte(
        self,
        resistance_force: int,
        resistance_setting: EffectSetting | None,
        predictive_force: int,
        predictive_setting: EffectSetting | None,
    ) -> int:
        if predictive_setting is not None and predictive_setting.enabled and predictive_force > 0:
            wall_position = self.brake_predictive_state.wall_start_percent
            if wall_position >= 0.0:
                return _wall_position_percent_to_start_byte(wall_position)
        return self._brake_resistance_start_byte(resistance_force, resistance_setting)

    @staticmethod
    def _brake_resistance_start_byte(resistance_force: int, setting: EffectSetting | None) -> int:
        if setting is None or not setting.enabled or resistance_force <= 0:
            return -1
        start_percent = _detail_int(setting.details or {}, "start_percent", 0, 0, 100)
        return _wall_position_percent_to_start_byte(float(start_percent))

    def _throttle_start_byte(self, traction_force: int) -> int:
        if traction_force <= 0 or self.throttle_traction_state.wall_start_percent < 0.0:
            return -1
        return _wall_position_percent_to_start_byte(self.throttle_traction_state.wall_start_percent)

    @staticmethod
    def _brake_resistance_slip_off_level(frame: TelemetryFrame, threshold: float) -> float:
        front_ratio = max(
            0.0,
            abs(float(frame.tire_slip_ratio_fl or 0.0)),
            abs(float(frame.tire_slip_ratio_fr or 0.0)),
        )
        front_combined = max(
            0.0,
            abs(float(frame.tire_combined_slip_fl or 0.0)),
            abs(float(frame.tire_combined_slip_fr or 0.0)),
        )
        ratio_threshold = max(0.001, float(threshold))
        combined_threshold = max(0.001, float(threshold) * 1.25)
        return max(front_ratio / ratio_threshold, front_combined / combined_threshold)

    @staticmethod
    def _throttle_driven_slip_values(frame: TelemetryFrame) -> tuple[float, float]:
        drive_train = int(frame.drive_train if frame.drive_train is not None else 1)
        if drive_train == 0:
            ratio_values = (
                float(frame.tire_slip_ratio_fl or 0.0),
                float(frame.tire_slip_ratio_fr or 0.0),
            )
            combined_values = (
                float(frame.tire_combined_slip_fl or 0.0),
                float(frame.tire_combined_slip_fr or 0.0),
            )
        else:
            ratio_values = (
                float(frame.tire_slip_ratio_rl or 0.0),
                float(frame.tire_slip_ratio_rr or 0.0),
            )
            combined_values = (
                float(frame.tire_combined_slip_rl or 0.0),
                float(frame.tire_combined_slip_rr or 0.0),
            )
        driven_ratio = max(0.0, *(max(0.0, value) for value in ratio_values))
        driven_combined = max(0.0, *(abs(value) for value in combined_values))
        return driven_ratio, driven_combined

    @staticmethod
    def _brake_dynamic_limit_level(frame: TelemetryFrame) -> float:
        front_ratio = (
            abs(float(frame.tire_slip_ratio_fl or 0.0))
            + abs(float(frame.tire_slip_ratio_fr or 0.0))
        ) * 0.5
        front_combined = (
            abs(float(frame.tire_combined_slip_fl or 0.0))
            + abs(float(frame.tire_combined_slip_fr or 0.0))
        ) * 0.5
        ratio_level = _smoothstep(0.06, 0.34, front_ratio)
        combined_level = _smoothstep(0.18, 0.74, front_combined) * 0.85
        decel_g = max(0.0, -float(frame.accel_z or 0.0) / 9.80665)
        decel_gate = _smoothstep(0.03, 0.55, decel_g)
        speed_gate = _smoothstep(8.0, 20.0, max(0.0, float(frame.speed or 0.0)))
        return _clamp(max(ratio_level, combined_level) * max(decel_gate, 0.35) * speed_gate, 0.0, 1.0)

    def _brake_predictive_risk(self, frame: TelemetryFrame) -> float:
        limit_level = self._brake_dynamic_limit_level(frame)
        brake_percent = _clamp(float(frame.brake or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        brake_gate = _smoothstep(4.0, 42.0, brake_percent)
        front_angle = (
            abs(float(frame.tire_slip_angle_fl or 0.0))
            + abs(float(frame.tire_slip_angle_fr or 0.0))
        ) * 0.5
        rear_angle = (
            abs(float(frame.tire_slip_angle_rl or 0.0))
            + abs(float(frame.tire_slip_angle_rr or 0.0))
        ) * 0.5
        body_slip = abs(math.atan2(float(frame.velocity_x or 0.0), max(abs(float(frame.velocity_z or 0.0)), 0.1)))
        yaw_rate = abs(float(frame.angular_velocity_y or 0.0))
        decel_g = max(0.0, -float(frame.accel_z or 0.0) / 9.80665)

        front_angle_risk = _smoothstep(0.35, 1.20, front_angle)
        decel_risk = _smoothstep(0.18, 0.85, decel_g)
        steering_load = _smoothstep(30.0, 110.0, abs(float(frame.steer or 0.0)))
        instability_cut = (
            (1.0 - _smoothstep(1.75, 3.10, rear_angle))
            * (1.0 - _smoothstep(0.85, 1.45, body_slip))
            * (1.0 - _smoothstep(3.2, 5.2, yaw_rate))
        )
        risk = max(limit_level, front_angle_risk * max(brake_gate, steering_load * 0.55), decel_risk * brake_gate * 0.65)
        return _clamp(risk * max(0.20, instability_cut), 0.0, 1.0)

    @staticmethod
    def _apply_brake_slip_drop(details: Mapping[str, object], base_force: float, slip_level: float) -> float:
        drop_level = _detail_int(details, "slip_pulse_end_percent", 100, 1, 150) / 100.0
        if slip_level < drop_level:
            return base_force
        drop_low_percent = _detail_int(details, "slip_drop_low_percent", 0, 0, 100)
        return 255.0 * drop_low_percent / 100.0

    @staticmethod
    def _brake_slip_response(
        details: Mapping[str, object],
        base_force: float,
        slip_level: float,
        wall_position: float,
        now: float,
    ) -> tuple[float, TriggerPulseOutput]:
        base = _clamp(float(base_force), 0.0, 255.0)
        level = max(0.0, float(slip_level))
        pulse_start_level = _detail_int(details, "slip_pulse_start_percent", 85, 10, 99) / 100.0
        drop_level = _detail_int(details, "slip_pulse_end_percent", 100, 100, 150) / 100.0
        pulse_window_active = drop_level > pulse_start_level

        if level >= drop_level:
            drop_low_percent = _detail_int(details, "slip_drop_low_percent", 0, 0, 100)
            return 255.0 * drop_low_percent / 100.0, TriggerPulseOutput()

        pulse_enabled = _detail_bool(details, "slip_pulse_enabled", False)
        if not pulse_enabled or not pulse_window_active or not (pulse_start_level <= level < drop_level):
            return base, TriggerPulseOutput()

        style_text = str(details.get("slip_pulse_style", "Soft Pulse")).strip().lower().replace("_", " ").replace("-", " ")
        if style_text in {"pulse kick", "kick"}:
            low_force = 255.0 * _detail_int(details, "slip_low_percent", 10, 0, 100) / 100.0
            high_force = 255.0 * _detail_int(details, "slip_pulse_high_percent", 35, 0, 100) / 100.0
            rate = _detail_int(details, "slip_pulse_rate", 12, 1, SLIP_PULSE_RATE_MAX)
            phase = (now * rate) % 1.0
            return (high_force if phase < 0.5 else low_force), TriggerPulseOutput()

        if style_text in {"strong pulse", "strong", "rumble"}:
            pulse = _detail_int(details, "slip_strong_pulse_amplitude", 80, 1, 255)
            return base, TriggerPulseOutput(
                display=pulse,
                pulse=pulse,
                pulse_rate=_detail_int(details, "slip_strong_pulse_rate", 80, 1, 255),
            )

        vibrate_amp = _detail_int(details, "slip_soft_pulse_amplitude", 2, 1, 8)
        return base, TriggerPulseOutput(
            display=_clamp_int(round(255.0 * vibrate_amp / 8.0), 0, 255),
            vibrate_amp=vibrate_amp,
            vibrate_freq=_detail_int(details, "slip_soft_pulse_frequency", 40, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX),
            vibrate_start_zone=_throttle_vibration_start_zone(
                wall_position,
                _detail_int(details, "slip_soft_pulse_start_zone", 0, 0, 9),
            ),
        )

    @staticmethod
    def _force_dt(state: TriggerForceState, now: float) -> float:
        dt = 0.0 if state.previous_at <= 0.0 else _clamp(now - state.previous_at, 0.0, 0.1)
        state.previous_at = now
        return dt

    @staticmethod
    def _hysteresis(state: TriggerForceState, brake_percent: float, start_percent: int) -> tuple[bool, float]:
        release_at = max(0.0, float(start_percent) - TRIGGER_RELEASE_MARGIN_PERCENT)
        active = state.active
        if active:
            active = brake_percent >= release_at
        else:
            active = brake_percent >= float(start_percent)
        state.active = active
        return active, release_at

    @staticmethod
    def _smooth_force(target_force: int, setting: EffectSetting, state: TriggerForceState, dt: float) -> int:
        target = float(_clamp_int(target_force, 0, 255))
        current = float(state.smoothed_force)
        if target <= current:
            state.smoothed_force = target
            return int(round(target))

        smooth_ms = _detail_int(setting.details or {}, "smooth_start_ms", 80, 0, 300)
        if smooth_ms <= 0 or dt <= 0.0:
            state.smoothed_force = target
            return int(round(target))

        step = max(1.0, target * dt / (smooth_ms / 1000.0))
        current = min(target, current + step)
        state.smoothed_force = current
        return int(round(current))

    def _release_brake_payloads(self) -> tuple[OutputEventPayload, ...]:
        pressure_live = self.brake_pressure.last_sent_force > 0 or self.brake_pressure.smoothed_force > 0.0
        resistance_live = self.brake_resistance.last_sent_force > 0 or self.brake_resistance.smoothed_force > 0.0
        predictive_live = self.brake_predictive.last_sent_force > 0 or self.brake_predictive.smoothed_force > 0.0
        if not pressure_live and not resistance_live and not predictive_live:
            return ()
        self.brake_pressure.active = False
        self.brake_pressure.smoothed_force = 0.0
        self.brake_pressure.last_sent_force = 0
        self.brake_resistance.active = False
        self.brake_resistance.smoothed_force = 0.0
        self.brake_resistance.last_sent_force = 0
        self.brake_predictive.active = False
        self.brake_predictive.smoothed_force = 0.0
        self.brake_predictive.last_sent_force = 0
        self.brake_predictive_state = BrakePredictiveState()
        self.brake_resistance_pulse = TriggerPulseOutput()
        self.brake_predictive_pulse = TriggerPulseOutput()
        for name in (BRAKE_PRESSURE, BRAKE_RESISTANCE, BRAKE_RESISTANCE_PREDICTIVE):
            self.last_trigger_output_specs.pop(name, None)
        return (trigger_brake(force=0),)

    def _release_throttle_payloads(self) -> tuple[OutputEventPayload, ...]:
        pressure_live = self.throttle_pressure.last_sent_force > 0 or self.throttle_pressure.smoothed_force > 0.0
        traction_live = self.throttle_traction.last_sent_force > 0 or self.throttle_traction.smoothed_force > 0.0
        accel_live = self.accel_g_punch.last_sent_force > 0 or self.accel_g_punch.smoothed_force > 0.0
        rpm_live = self.rpm_rev_limit.last_sent_force > 0 or self.rpm_rev_limit.smoothed_force > 0.0
        howl_live = self.shift_down_howl.last_output.display > 0 or self.shift_down_howl.started_at > 0.0
        if not pressure_live and not traction_live and not accel_live and not rpm_live and not howl_live:
            return ()
        self.throttle_pressure.active = False
        self.throttle_pressure.smoothed_force = 0.0
        self.throttle_pressure.last_sent_force = 0
        self.throttle_traction.active = False
        self.throttle_traction.smoothed_force = 0.0
        self.throttle_traction.last_sent_force = 0
        self.throttle_traction_state = ThrottleTractionState()
        self.accel_g_punch.active = False
        self.accel_g_punch.smoothed_force = 0.0
        self.accel_g_punch.last_sent_force = 0
        self.accel_g_punch_state = AccelGPunchTriggerState()
        self.rpm_rev_limit.active = False
        self.rpm_rev_limit.smoothed_force = 0.0
        self.rpm_rev_limit.last_sent_force = 0
        self.shift_down_howl = ShiftDownHowlState()
        for name in (THROTTLE_PRESSURE, THROTTLE_TRACTION, ACCEL_G_PUNCH, RPM_REV_LIMIT, SHIFT_DOWN_HOWL):
            self.last_trigger_output_specs.pop(name, None)
        return (trigger_throttle(force=0),)


def _apply_effect_gain_to_force(force: int | float, effect_gain: float = 1.0) -> int:
    gain = _clamp(float(effect_gain), 0.0, 1.0)
    scaled = _clamp_int(round(float(force) * gain), 0, 255)
    if scaled <= 0 and float(force) > 0.0 and gain > 0.0:
        return 1
    return scaled


def _apply_effect_gain_to_pulse(
    output: TriggerPulseOutput,
    effect_gain: float = 1.0,
) -> TriggerPulseOutput:
    gain = _clamp(float(effect_gain), 0.0, 1.0)
    pulse = _clamp_int(round(output.pulse * gain), 0, 255)
    vibrate_amp = _clamp_int(round(output.vibrate_amp * gain), 0, 8)
    display = _clamp_int(round(output.display * gain), 0, 255)
    if gain > 0.0 and output.pulse > 0 and pulse <= 0:
        pulse = 1
    if gain > 0.0 and output.vibrate_amp > 0 and vibrate_amp <= 0:
        vibrate_amp = 1
    if gain > 0.0 and output.display > 0 and display <= 0:
        display = 1
    return TriggerPulseOutput(
        display=display,
        pulse=pulse,
        pulse_rate=output.pulse_rate if pulse > 0 else 0,
        vibrate_amp=vibrate_amp,
        vibrate_freq=output.vibrate_freq if vibrate_amp > 0 else 0,
        vibrate_start_zone=output.vibrate_start_zone if vibrate_amp > 0 else 0,
    )


def _field_float(fields: Mapping[str, str], key: str, default: float) -> float:
    try:
        return float(fields.get(key, default))
    except (TypeError, ValueError):
        return default


def _field_int(fields: Mapping[str, str], key: str, default: int) -> int:
    try:
        return int(round(float(fields.get(key, default))))
    except (TypeError, ValueError):
        return default


def _normalize_trigger_side(value: object, default: str) -> str:
    text = str(value or default).strip().lower()
    if text in {"both", "b", "lr", "left+right", "l+r"}:
        return "both"
    if text in {"left", "l", "1"}:
        return "left"
    if text in {"right", "r", "2"}:
        return "right"
    return default


def _kerb_wave_value(speed_kmh: float, low_value: int, high_value: int) -> int:
    low = int(low_value)
    high = int(high_value)
    if low > high:
        low, high = high, low
    mix = _smoothstep(5.0, 330.0, max(0.0, float(speed_kmh)))
    return int(round(low + (high - low) * mix))


def _start_percent_to_zone(start_percent: int | float) -> int:
    return _clamp_int(round(_clamp(float(start_percent), 0.0, 100.0) / 100.0 * 9.0), 0, 9)


def _accel_g_punch_shift_gear_factor(gear: int) -> float:
    if gear <= 1:
        return 1.00
    gear_factors = {
        2: 0.78,
        3: 0.60,
        4: 0.46,
        5: 0.36,
        6: 0.28,
    }
    return gear_factors.get(int(gear), 0.22)


def _accel_g_punch_low_gear_accel_factor(gear: int) -> float:
    if gear == 2:
        return 0.58
    if gear == 3:
        return 0.28
    return 0.0


def _accel_g_punch_pulse_gear_factor(details: Mapping[str, object], gear: int) -> float:
    if gear <= 1:
        percent = _detail_int(details, "pulse_gear_1_percent", 100, 0, 150)
    elif gear == 2:
        percent = _detail_int(details, "pulse_gear_2_percent", 100, 0, 150)
    else:
        base_percent = _detail_int(details, "pulse_gear_3_percent", 50, 0, 150)
        third_gear_factor = max(0.01, _accel_g_punch_shift_gear_factor(3))
        gear_decay = _accel_g_punch_shift_gear_factor(gear) / third_gear_factor
        percent = round(base_percent * gear_decay)
    return _clamp(percent / 100.0, 0.0, 1.5)


def _throttle_traction_pulse_output(details: Mapping[str, object], wall_position: float) -> TriggerPulseOutput:
    style = _normalize_pulse_style(details.get("slip_pulse_style", "Soft Pulse"), default_style="Soft Pulse")
    if style == "Strong Pulse":
        pulse = _detail_int(details, "slip_strong_pulse_amplitude", 80, 1, 255)
        return TriggerPulseOutput(
            display=pulse,
            pulse=pulse,
            pulse_rate=_detail_int(details, "slip_strong_pulse_rate", 80, 1, 255),
        )

    vibrate_amp = _detail_int(details, "slip_soft_pulse_amplitude", 2, 1, 8)
    return TriggerPulseOutput(
        display=_clamp_int(round(255.0 * vibrate_amp / 8.0), 0, 255),
        vibrate_amp=vibrate_amp,
        vibrate_freq=_detail_int(details, "slip_soft_pulse_frequency", 40, 1, NATIVE_SOFT_PULSE_FREQUENCY_MAX),
        vibrate_start_zone=_throttle_vibration_start_zone(
            wall_position,
            _detail_int(details, "slip_soft_pulse_start_zone", 0, 0, 9),
        ),
    )


def _throttle_vibration_start_zone(wall_position: float, margin: int) -> int:
    wall = _clamp(float(wall_position), 0.0, 100.0)
    zone = _clamp_int(int(wall // 10.0), 0, 9)
    return _clamp_int(zone - _clamp_int(margin, 0, 9), 0, 9)


def _accel_g_punch_output_end_ratio(details: Mapping[str, object], gear: int) -> float:
    max_offset = _detail_int(details, "max_rpm_offset", 10, 0, 10)
    drop_offset = _detail_int(details, "gear_drop_offset", 9, 0, 9)
    if gear <= 1:
        percent = 90 + max_offset
    else:
        step = max(0, int(gear) - 2)
        base_percent = (80 + max_offset) - 10 * step
        missing_drop = 9 - drop_offset
        penalty_unit = step * step + 2 * step + 2
        percent = base_percent - missing_drop * penalty_unit
    return _clamp(percent / 100.0, 0.35, 1.0)


def _accel_g_punch_wall_fade_start_ratio(
    details: Mapping[str, object],
    gear: int,
    start_ratio: float,
    end_ratio: float,
) -> float:
    if gear <= 1:
        fade_percent = _detail_int(details, "launch_wall_fade_percent", 50, 0, 90)
    else:
        fade_percent = _detail_int(details, "shift_wall_fade_percent", 40, 0, 90)
    span = max(0.01, end_ratio - start_ratio)
    return max(start_ratio, min(end_ratio - 0.01, start_ratio + span * fade_percent / 100.0))


def _accel_g_punch_wall_fade_end_ratio(
    details: Mapping[str, object],
    gear: int,
    start_ratio: float,
    end_ratio: float,
) -> float:
    if gear <= 1:
        fade_percent = _detail_int(details, "launch_wall_fade_percent", 50, 0, 90)
        tail_percent = fade_percent
    else:
        fade_percent = _detail_int(details, "shift_wall_fade_percent", 40, 0, 90)
        tail_percent = _detail_int(details, "shift_fade_tail_percent", 35, 0, 100)
    span = max(0.01, end_ratio - start_ratio)
    fade_start = max(start_ratio, min(end_ratio - 0.01, start_ratio + span * fade_percent / 100.0))
    tail_span = max(0.01, end_ratio - fade_start) * tail_percent / 100.0
    return max(fade_start + 0.01, min(end_ratio, fade_start + tail_span))


def _accel_g_punch_launch_accel_level(frame: TelemetryFrame, throttle_percent: float) -> float:
    longitudinal_g = max(0.0, float(frame.accel_z or 0.0) / 9.80665)
    accel_gate = _smoothstep(0.03, 0.72, longitudinal_g)
    throttle_gate = _smoothstep(6.0, 62.0, throttle_percent)
    fallback_gate = throttle_gate * 0.55
    return _clamp(max(accel_gate, fallback_gate) * throttle_gate, 0.0, 1.0)


def _wall_position_percent_to_start_byte(position_percent: float) -> int:
    desired = _clamp(float(position_percent), 0.0, 100.0)
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
    raw_percent = _clamp(raw_percent, 0.0, 80.0)
    return _clamp_int(round(raw_percent / 100.0 * 255.0), 0, 255)


def _detail_int(details: Mapping[str, object], key: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(round(float(details.get(key, default))))
    except (TypeError, ValueError):
        value = default
    return _clamp_int(value, minimum, maximum)


def _detail_float(details: Mapping[str, object], key: str, default: float, minimum: float, maximum: float) -> float:
    try:
        value = float(details.get(key, default))
    except (TypeError, ValueError):
        value = default
    return _clamp(value, minimum, maximum)


def _detail_bool(details: Mapping[str, object], key: str, default: bool) -> bool:
    value = details.get(key, default)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def _amp_from_percent(percent: int | float) -> int:
    value = _clamp_int(percent, 0, 100)
    if value <= 0:
        return 0
    return _clamp_int(round(value * 8 / 100.0), 1, 8)


def _trigger_pulse_output_from_style(
    details: Mapping[str, object],
    level: float,
    *,
    default_style: str,
    default_strong_amp: int,
    default_strong_rate: int,
    default_soft_amp: int,
    default_soft_frequency: int,
    default_soft_start_zone: int,
) -> TriggerPulseOutput:
    output_level = _clamp(level, 0.0, 1.0)
    if output_level <= 0.0:
        return TriggerPulseOutput()
    style = _normalize_pulse_style(details.get("slip_pulse_style", default_style), default_style=default_style)
    if style == "Strong Pulse":
        strong_amp = _detail_int(details, "slip_strong_pulse_amplitude", default_strong_amp, 1, 255)
        pulse = _clamp_int(round(strong_amp * output_level), 0, 255)
        if pulse <= 0:
            return TriggerPulseOutput()
        return TriggerPulseOutput(
            display=pulse,
            pulse=pulse,
            pulse_rate=_detail_int(details, "slip_strong_pulse_rate", default_strong_rate, 1, 255),
        )

    soft_amp = _detail_int(details, "slip_soft_pulse_amplitude", default_soft_amp, 1, 8)
    vibrate_amp = _clamp_int(round(soft_amp * output_level), 0, 8)
    if vibrate_amp <= 0:
        return TriggerPulseOutput()
    return TriggerPulseOutput(
        display=_clamp_int(round(255.0 * vibrate_amp / 8.0), 0, 255),
        vibrate_amp=vibrate_amp,
        vibrate_freq=_detail_int(
            details,
            "slip_soft_pulse_frequency",
            default_soft_frequency,
            1,
            NATIVE_SOFT_PULSE_FREQUENCY_MAX,
        ),
        vibrate_start_zone=_detail_int(details, "slip_soft_pulse_start_zone", default_soft_start_zone, 0, 9),
    )


def _merge_trigger_pulse_outputs(*outputs: TriggerPulseOutput) -> TriggerPulseOutput:
    best_strong = TriggerPulseOutput()
    best_soft = TriggerPulseOutput()
    for output in outputs:
        if output.pulse > best_strong.pulse:
            best_strong = output
        if output.vibrate_amp > best_soft.vibrate_amp:
            best_soft = output
    return TriggerPulseOutput(
        display=max(best_strong.display, best_soft.display),
        pulse=best_strong.pulse,
        pulse_rate=best_strong.pulse_rate,
        vibrate_amp=best_soft.vibrate_amp,
        vibrate_freq=best_soft.vibrate_freq,
        vibrate_start_zone=best_soft.vibrate_start_zone,
    )


def _trigger_debug_spec(
    force: float,
    wall_start: float = 0.0,
    wall_end: float = 100.0,
    pulse_output: TriggerPulseOutput | None = None,
    *,
    updated_at: float,
) -> dict[str, float]:
    pulse_output = pulse_output or TriggerPulseOutput()
    wall_start = _clamp(float(wall_start), 0.0, 100.0)
    wall_end = _clamp(float(wall_end), 0.0, 100.0)
    if wall_end < wall_start:
        wall_start, wall_end = wall_end, wall_start
    pulse_start = wall_start
    vibrate_start = _clamp(float(pulse_output.vibrate_start_zone) * 10.0, 0.0, 100.0)
    return {
        "force": _clamp(float(force), 0.0, 255.0),
        "wall_start": wall_start,
        "wall_end": wall_end,
        "pulse_amp": float(max(0, pulse_output.pulse)),
        "pulse_rate": float(max(0, pulse_output.pulse_rate)),
        "pulse_start": pulse_start,
        "vibrate_amp": float(max(0, pulse_output.vibrate_amp)),
        "vibrate_freq": float(max(0, pulse_output.vibrate_freq)),
        "vibrate_start": vibrate_start,
        "updated_at": float(updated_at),
    }


def _normalize_pulse_style(style: object, *, default_style: str) -> str:
    value = str(style or default_style).strip().lower().replace("_", " ").replace("-", " ")
    if value in {"strong pulse", "strong", "rumble"}:
        return "Strong Pulse"
    if value in {"soft pulse", "soft", "wave"}:
        return "Soft Pulse"
    return "Soft Pulse" if default_style == "Soft Pulse" else "Strong Pulse"


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _clamp_int(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, int(value)))


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 >= edge1:
        return 1.0 if value >= edge1 else 0.0
    t = _clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)
