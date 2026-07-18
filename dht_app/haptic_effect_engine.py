from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from time import monotonic
from typing import Mapping

from .output_event_payloads import OutputEventPayload, accel_g_punch_haptic, gear_shift, impact, impact_side, impact_smashable, rev_limit, road_bumps, rumble_kerbs, tire_limit_load, wheelspin_buzz
from .settings_model import EffectSetting
from .telemetry_frame import TelemetryFrame


TRANSIENT_GEAR_VALUE = 11

GEAR_SHIFT_CORE = "Gear Shift Bite - Core"
GEAR_SHIFT_HIGH_HZ = "Gear Shift Bite - High Hz"
GEAR_SHIFT_PARTICLES = "Gear Shift Bite - Particles"
RUMBLE_KERBS = "Rumble Kerbs"
TIRE_LIMIT_LOAD = "Tire Limit Load"
WHEELSPIN_BUZZ = "Wheelspin Buzz"
ACCEL_G_PUNCH_HAPTIC = "Acceleration G Punch - Haptic"
REV_LIMIT = "Rev Limit"
ROAD_BUMPS = "Road Bumps"
IMPACTS = "Impacts"
IMPACT_SIDE = "Impact - Side"
IMPACT_SMASHABLE = "Impact - Smashable"


@dataclass
class GearShiftState:
    previous_gear: int | None = None
    previous_rpm: float = 0.0


@dataclass
class RumbleKerbsState:
    active: bool = False


@dataclass
class RoadBumpsState:
    previous_frame: TelemetryFrame | None = None
    previous_at: float = 0.0
    left_level: float = 0.0
    right_level: float = 0.0
    active: bool = False


@dataclass
class TireLimitState:
    left_level: float = 0.0
    right_level: float = 0.0
    left_freq_prev: float = 0.0
    right_freq_prev: float = 0.0
    gx_smooth: float = 0.0
    gz_smooth: float = 0.0
    active: bool = False


@dataclass
class WheelspinBuzzState:
    left_level: float = 0.0
    right_level: float = 0.0
    active: bool = False


@dataclass
class RevLimitState:
    car_ordinal: int = 0
    observed_max_gear: int = 0
    previous_gear: int | None = None
    previous_rpm: float = 0.0
    previous_at: float = 0.0
    downshift_surge_until: float = 0.0
    output_active: bool = False


@dataclass
class AccelGPunchHapticState:
    launch_active: bool = False
    launch_gear: int = 0
    shift_active: bool = False
    shift_gear: int = 0
    shift_start_ratio: float = 0.0
    shift_ready_at: float = 0.0
    shift_boost_until: float = 0.0
    last_level: float = 0.0
    previous_gear: int | None = None
    previous_rpm: float = 0.0


@dataclass
class ImpactState:
    previous_frame: TelemetryFrame | None = None
    previous_at: float = 0.0
    last_impact_at: float = 0.0
    last_side_impact_at: float = 0.0
    last_smashable_impact_at: float = 0.0
    steer_history: deque[tuple[float, float]] = field(default_factory=deque)


class HapticEffectEngine:
    """Small telemetry-to-haptic payload bridge for the PySide6 migration."""

    def __init__(self) -> None:
        self.gear_shift = GearShiftState()
        self.rumble_kerbs = RumbleKerbsState()
        self.road_bumps = RoadBumpsState()
        self.tire_limit = TireLimitState()
        self.wheelspin_buzz = WheelspinBuzzState()
        self.accel_g_punch_haptic = AccelGPunchHapticState()
        self.rev_limit = RevLimitState()
        self.impacts = ImpactState()
        self.last_payloads: tuple[OutputEventPayload, ...] = ()
        self.last_source_payloads: tuple[OutputEventPayload, ...] = ()
        self.last_haptic_output_specs: dict[str, dict[str, float]] = {}

    def reset(self) -> None:
        self.gear_shift = GearShiftState()
        self.rumble_kerbs = RumbleKerbsState()
        self.road_bumps = RoadBumpsState()
        self.tire_limit = TireLimitState()
        self.wheelspin_buzz = WheelspinBuzzState()
        self.accel_g_punch_haptic = AccelGPunchHapticState()
        self.rev_limit = RevLimitState()
        self.impacts = ImpactState()
        self.last_payloads = ()
        self.last_source_payloads = ()
        self.last_haptic_output_specs = {}

    def _continuous_release_payloads(self) -> tuple[OutputEventPayload, ...]:
        payloads: list[OutputEventPayload] = []
        if self.rumble_kerbs.active:
            payloads.append(rumble_kerbs(front_left=0.0, front_right=0.0, volume=0.0))
        if self.tire_limit.active:
            payloads.append(tire_limit_load(left=0.0, right=0.0, volume=0.0))
        if self.wheelspin_buzz.active:
            payloads.append(wheelspin_buzz(left=0.0, right=0.0, volume=0.0))
        if self.accel_g_punch_haptic.last_level > 0.0:
            payloads.append(accel_g_punch_haptic(left=0.0, right=0.0, volume=0.0))
        if self.rev_limit.output_active:
            payloads.append(rev_limit(rpm=0.0, max_rpm=0.0, volume=0.0))
        if self.road_bumps.active:
            payloads.append(road_bumps(left=0.0, right=0.0, volume=0.0))
        return tuple(payloads)

    def process_frame(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
        effect_gains: Mapping[str, float] | None = None,
    ) -> tuple[OutputEventPayload, ...]:
        if not frame.parsed or frame.is_race_on is False:
            release_payloads = self._continuous_release_payloads()
            self.reset()
            self.last_payloads = release_payloads
            self.last_haptic_output_specs = _haptic_debug_specs_from_payloads(release_payloads, monotonic())
            return release_payloads

        self.last_source_payloads = ()
        gains = effect_gains or {}
        payloads = (
            *self._gear_shift_payloads(frame, haptic_effects),
            *self._rumble_kerbs_payloads(frame, haptic_effects),
            *self._tire_limit_load_payloads(frame, haptic_effects),
            *self._wheelspin_buzz_payloads(frame, haptic_effects, gains),
            *self._accel_g_punch_haptic_payloads(frame, haptic_effects),
            *self._rev_limit_payloads(frame, haptic_effects),
            *self._road_bumps_payloads(frame, haptic_effects),
            *self._impact_payloads(frame, haptic_effects),
        )
        self.last_payloads = payloads
        self.last_haptic_output_specs = _haptic_debug_specs_from_payloads(payloads, monotonic())
        return payloads

    def _gear_shift_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        gear = _positive_int(frame.gear)
        if gear is None:
            return ()
        if gear == TRANSIENT_GEAR_VALUE:
            return ()

        previous = self.gear_shift.previous_gear
        self.gear_shift.previous_gear = gear
        self.gear_shift.previous_rpm = max(0.0, float(frame.rpm or 0.0))

        if previous is None or gear == previous:
            return ()

        core = haptic_effects.get(GEAR_SHIFT_CORE)
        high_hz = haptic_effects.get(GEAR_SHIFT_HIGH_HZ)
        particles = haptic_effects.get(GEAR_SHIFT_PARTICLES)
        haptic_enabled = any(setting is not None and setting.enabled for setting in (core, high_hz, particles))

        gear_delta = gear - previous
        max_rpm = max(1.0, float(frame.max_rpm or 1.0))
        rpm = max(0.0, float(frame.rpm or 0.0))
        throttle = max(0.0, min(1.0, float(frame.throttle or 0.0) / 255.0))
        torque = max(0.0, min(1.0, abs(float(frame.torque or 0.0)) / 900.0))
        payload = gear_shift(
            direction=gear_delta,
            rpm_ratio=rpm / max_rpm,
            throttle=throttle,
            torque=torque,
            performance_index=int(frame.car_performance_index if frame.car_performance_index is not None else 700),
            max_rpm=max_rpm,
            core=_enabled_details(core),
            high_hz=_enabled_details(high_hz),
            particles=_enabled_details(particles),
        )
        self._record_source_payload(payload)
        return (payload,) if haptic_enabled else ()

    def _rumble_kerbs_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(RUMBLE_KERBS)
        haptic_enabled = setting is not None and setting.enabled
        details = dict(setting.details) if setting is not None else {}
        speed = max(0.0, float(frame.speed or 0.0))
        low_speed = _detail_float(details, "speed_low_start", 5.0)
        high_speed = _detail_float(details, "speed_high_max", 330.0)
        speed_gain = _smoothstep(low_speed, high_speed, speed)
        front_left_on = _is_rumble_kerb_on(
            frame.surface_rumble_fl,
            frame.wheel_on_rumble_strip_fl,
            0.21,
            0.25,
        )
        front_right_on = _is_rumble_kerb_on(
            frame.surface_rumble_fr,
            frame.wheel_on_rumble_strip_fr,
            0.20,
            0.29,
        )
        front_left = speed_gain if front_left_on else 0.0
        front_right = speed_gain if front_right_on else 0.0
        active = front_left > 0.0 or front_right > 0.0
        previous_output_active = self.rumble_kerbs.active
        if not active and not previous_output_active:
            return ()

        payload = rumble_kerbs(
            front_left=front_left,
            front_right=front_right,
            hz=_rumble_kerbs_frequency(speed, details),
            speed=speed,
            volume=float(setting.value) if haptic_enabled and setting is not None and active else 0.0,
            details=details,
        )
        self._record_source_payload(payload)
        if not haptic_enabled:
            self.rumble_kerbs.active = False
            return (payload,) if previous_output_active else ()
        self.rumble_kerbs.active = active
        return (payload,)

    def _road_bumps_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(ROAD_BUMPS)
        if setting is None or not setting.enabled:
            was_active = self.road_bumps.active
            self.road_bumps = RoadBumpsState()
            return (road_bumps(left=0.0, right=0.0, volume=0.0),) if was_active else ()

        now = monotonic()
        previous = self.road_bumps.previous_frame
        previous_at = self.road_bumps.previous_at
        self.road_bumps.previous_frame = frame
        self.road_bumps.previous_at = now
        if previous is None or previous_at <= 0.0:
            self.road_bumps.left_level *= 0.70
            self.road_bumps.right_level *= 0.70
            return ()

        details = _enabled_details(setting)
        dt = _clamp(now - previous_at, 0.008, 0.080)
        speed = max(0.0, float(frame.speed or 0.0))
        speed_gate = _smoothstep(8.0, 28.0, speed) * (1.0 - _smoothstep(230.0, 310.0, speed))
        left_rate = abs(
            float(frame.norm_suspension_travel_fl or 0.0)
            - float(previous.norm_suspension_travel_fl or 0.0)
        ) / dt
        right_rate = abs(
            float(frame.norm_suspension_travel_fr or 0.0)
            - float(previous.norm_suspension_travel_fr or 0.0)
        ) / dt
        accel_y_delta = abs(float(frame.accel_y or 0.0) - float(previous.accel_y or 0.0))
        is_asphalt = _is_asphalt_surface(frame)
        car_class = int(frame.car_class if frame.car_class is not None else 3)
        threshold_scale = _road_bump_low_class_threshold_scale(
            car_class,
            details,
        ) * _road_bumps_threshold_scale(details)
        if is_asphalt:
            vertical_gate = _smoothstep(0.15 * threshold_scale, 3.80, accel_y_delta)
        else:
            vertical_gate = _smoothstep(0.90 * threshold_scale, 5.00, accel_y_delta)

        left_target = _road_bump_side_level(left_rate, vertical_gate, speed_gate, is_asphalt, threshold_scale)
        right_target = _road_bump_side_level(right_rate, vertical_gate, speed_gate, is_asphalt, threshold_scale)
        target_severity = max(left_target, right_target)
        strength_gain = _road_bumps_strength_gain(target_severity, details)
        left_target = _clamp(left_target * strength_gain, 0.0, 1.0)
        right_target = _clamp(right_target * strength_gain, 0.0, 1.0)
        self.road_bumps.left_level = _road_bump_envelope(
            self.road_bumps.left_level,
            left_target,
            is_asphalt,
            details,
        )
        self.road_bumps.right_level = _road_bump_envelope(
            self.road_bumps.right_level,
            right_target,
            is_asphalt,
            details,
        )
        class_gain = _road_bump_low_class_gain(car_class, details)
        base_left = _clamp(self.road_bumps.left_level * class_gain, 0.0, 1.0)
        base_right = _clamp(self.road_bumps.right_level * class_gain, 0.0, 1.0)
        severity = max(base_left, base_right)
        if severity <= 0.0 and not self.road_bumps.active:
            return ()

        self.road_bumps.active = severity > 0.0
        high_hz = _detail_float(details, "high_bump_hz", 60.0)
        low_hz = _detail_float(details, "low_bump_hz", 34.0)
        hz = high_hz + (low_hz - high_hz) * _clamp(severity, 0.0, 1.0)
        volume_scale = _clamp(float(setting.value) / 10.0, 0.0, 1.0)
        output_left = _clamp(base_left * volume_scale, 0.0, 1.0)
        output_right = _clamp(base_right * volume_scale, 0.0, 1.0)
        output_active = max(output_left, output_right) > 0.0
        payload = road_bumps(
            left=output_left,
            right=output_right,
            hz=hz,
            volume=10.0 if output_active else 0.0,
        )
        return (payload,)

    def _tire_limit_load_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(TIRE_LIMIT_LOAD)
        if setting is None or not setting.enabled:
            was_active = self.tire_limit.active
            self.tire_limit = TireLimitState()
            return (tire_limit_load(left=0.0, right=0.0, volume=0.0),) if was_active else ()

        details = _enabled_details(setting)
        speed_ms = max(0.0, float(frame.speed or 0.0) / 3.6)
        steer = float(frame.steer or 0.0)
        yaw_rate = abs(float(frame.angular_velocity_y or 0.0))
        abs_steer = abs(steer)

        fl_angle = abs(float(frame.tire_slip_angle_fl or 0.0))
        fr_angle = abs(float(frame.tire_slip_angle_fr or 0.0))
        rl_angle = abs(float(frame.tire_slip_angle_rl or 0.0))
        rr_angle = abs(float(frame.tire_slip_angle_rr or 0.0))
        fl_combined = abs(float(frame.tire_combined_slip_fl or 0.0))
        fr_combined = abs(float(frame.tire_combined_slip_fr or 0.0))
        rl_combined = abs(float(frame.tire_combined_slip_rl or 0.0))
        rr_combined = abs(float(frame.tire_combined_slip_rr or 0.0))
        fl_ratio = abs(float(frame.tire_slip_ratio_fl or 0.0))
        fr_ratio = abs(float(frame.tire_slip_ratio_fr or 0.0))

        front_angle = (fl_angle + fr_angle) * 0.5
        rear_angle = (rl_angle + rr_angle) * 0.5
        front_combined = (fl_combined + fr_combined) * 0.5
        rear_combined = (rl_combined + rr_combined) * 0.5
        front_slip_ratio = (fl_ratio + fr_ratio) * 0.5

        body_slip = abs(math.atan2(float(frame.velocity_x or 0.0), max(abs(float(frame.velocity_z or 0.0)), 0.1)))
        speed_gate = _smoothstep(7.0, 14.0, speed_ms)
        steer_gate = _smoothstep(35.0, 115.0, abs_steer)

        gx = -float(frame.accel_x or 0.0) / 9.80665
        gz = float(frame.accel_z or 0.0) / 9.80665
        self.tire_limit.gx_smooth += (gx - self.tire_limit.gx_smooth) * 0.40
        self.tire_limit.gz_smooth += (gz - self.tire_limit.gz_smooth) * 0.45
        gx_smooth = self.tire_limit.gx_smooth
        gz_smooth = self.tire_limit.gz_smooth
        abs_lateral_g = abs(gx_smooth)

        decel_load = _smoothstep(0.03, 1.00, -gz_smooth)
        accel_unload = _smoothstep(0.03, 0.30, gz_smooth)
        longitudinal_load = _clamp(1.0 + decel_load * 0.40 - accel_unload * 0.45, 0.45, 1.40)
        accel_limit_suppress = _clamp(1.0 - accel_unload * 0.90, 0.15, 1.0)
        lateral_gate = _smoothstep(0.04, 1.20, abs_lateral_g)
        straight_brake_gate = decel_load
        load_intent_gate = max(lateral_gate, straight_brake_gate)

        front_limit_window = _smoothstep(0.75, 1.45, front_angle) * (1.0 - _smoothstep(2.55, 3.90, front_angle))
        combined_window = _smoothstep(0.25, 0.85, front_combined) * (1.0 - _smoothstep(2.65, 3.95, front_combined))
        brake_ratio_window = _smoothstep(0.06, 0.32, front_slip_ratio) * (1.0 - _smoothstep(1.45, 2.55, front_slip_ratio))
        brake_combined_window = _smoothstep(0.18, 0.70, front_combined) * (1.0 - _smoothstep(2.65, 3.95, front_combined))
        straight_brake_limit_window = max(brake_ratio_window, brake_combined_window * 0.70)

        rear_angle_cut = 1.0 - _smoothstep(1.55, 3.05, rear_angle)
        rear_combined_cut = 1.0 - _smoothstep(2.25, 3.80, rear_combined)
        body_slip_cut = 1.0 - _smoothstep(0.75, 1.35, body_slip)
        spin_cut = 1.0 - _smoothstep(3.0, 4.8, yaw_rate)

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

        left = _tire_limit_side_level(
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
            self.tire_limit.left_level,
            details,
        )
        right = _tire_limit_side_level(
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
            self.tire_limit.right_level,
            details,
        )
        self.tire_limit.left_level = left
        self.tire_limit.right_level = right
        severity = max(left, right)
        if severity <= 0.0 and not self.tire_limit.active:
            return ()

        self.tire_limit.active = severity > 0.0
        payload = tire_limit_load(
            left=left,
            right=right,
            left_hz=_tire_limit_frequency(left * 100.0, details),
            right_hz=_tire_limit_frequency(right * 100.0, details),
            volume=float(setting.value) if severity > 0.0 else 0.0,
        )
        return (payload,)

    def _wheelspin_buzz_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
        effect_gains: Mapping[str, float],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(WHEELSPIN_BUZZ)
        if setting is None or not setting.enabled:
            was_active = self.wheelspin_buzz.active
            self.wheelspin_buzz = WheelspinBuzzState()
            return (wheelspin_buzz(left=0.0, right=0.0, volume=0.0),) if was_active else ()

        details = _enabled_details(setting)
        throttle = _clamp(float(frame.throttle or 0.0) / 255.0, 0.0, 1.0)
        speed = max(0.0, float(frame.speed or 0.0))
        drive_train = int(frame.drive_train if frame.drive_train is not None else 1)
        if drive_train == 0:
            left_slip = max(0.0, float(frame.tire_slip_ratio_fl or 0.0))
            right_slip = max(0.0, float(frame.tire_slip_ratio_fr or 0.0))
        else:
            left_slip = max(0.0, float(frame.tire_slip_ratio_rl or 0.0))
            right_slip = max(0.0, float(frame.tire_slip_ratio_rr or 0.0))

        throttle_gate = _smoothstep(0.18, 0.55, throttle)
        speed_gate = 1.0 - _smoothstep(185.0, 245.0, speed)
        left_target = _wheelspin_side_level(left_slip, throttle_gate, speed_gate, details)
        right_target = _wheelspin_side_level(right_slip, throttle_gate, speed_gate, details)
        self.wheelspin_buzz.left_level = _wheelspin_envelope(
            self.wheelspin_buzz.left_level,
            left_target,
            details,
        )
        self.wheelspin_buzz.right_level = _wheelspin_envelope(
            self.wheelspin_buzz.right_level,
            right_target,
            details,
        )
        pan_left, pan_right = _effect_pan_gains(details)
        drift_gain = _clamp(float(effect_gains.get(WHEELSPIN_BUZZ, 1.0)), 0.0, 1.0)
        left = self.wheelspin_buzz.left_level * drift_gain * pan_left
        right = self.wheelspin_buzz.right_level * drift_gain * pan_right
        severity = max(left, right)
        if severity <= 0.0 and not self.wheelspin_buzz.active:
            return ()

        self.wheelspin_buzz.active = severity > 0.0
        payload = wheelspin_buzz(
            left=left,
            right=right,
            hz=_detail_float(details, "buzz_hz", 70.0),
            noise_range=_detail_float(details, "noise_range", 0.0),
            volume=float(setting.value) if severity > 0.0 else 0.0,
        )
        return (payload,)

    def _accel_g_punch_haptic_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(ACCEL_G_PUNCH_HAPTIC)
        if setting is None or not setting.enabled:
            previous_level = self.accel_g_punch_haptic.last_level
            details = dict(setting.details) if setting is not None else {}
            start_hz = _detail_float(details, "start_hz", 44.0)
            self.accel_g_punch_haptic = AccelGPunchHapticState()
            return (
                accel_g_punch_haptic(left=0.0, right=0.0, hz=start_hz, volume=0.0),
            ) if previous_level > 0.0 else ()

        now = monotonic()
        details = _enabled_details(setting)
        start_hz = _detail_float(details, "start_hz", 44.0)
        end_hz = _detail_float(details, "end_hz", 86.0)
        gear = int(frame.gear or 0)
        if gear == TRANSIENT_GEAR_VALUE:
            return ()

        if gear > 0:
            previous_gear = self.accel_g_punch_haptic.previous_gear
            previous_rpm = self.accel_g_punch_haptic.previous_rpm
            if previous_gear is not None and previous_gear > 0 and gear > previous_gear:
                self._begin_accel_g_punch_haptic_upshift(now, gear, details)
            self.accel_g_punch_haptic.previous_gear = gear
            self.accel_g_punch_haptic.previous_rpm = max(0.0, float(frame.rpm or 0.0))
            if previous_rpm < 0.0:
                self.accel_g_punch_haptic.previous_rpm = max(0.0, float(frame.rpm or 0.0))

        if gear < 0:
            self._reset_accel_g_punch_haptic_motion_state()
            return ()

        speed_kmh = max(0.0, float(frame.speed or 0.0))
        throttle_percent = _clamp(float(frame.throttle or 0.0) / 255.0 * 100.0, 0.0, 100.0)
        max_rpm = max(1.0, float(frame.max_rpm or 1.0))
        rpm_ratio = _clamp(float(frame.rpm or 0.0) / max_rpm, 0.0, 1.15)

        launch_allowed = gear in (0, 1)
        if launch_allowed and not self.accel_g_punch_haptic.launch_active and throttle_percent >= 6.0:
            self.accel_g_punch_haptic.launch_active = True
            self.accel_g_punch_haptic.launch_gear = gear
        if self.accel_g_punch_haptic.launch_active and (
            not launch_allowed or gear != self.accel_g_punch_haptic.launch_gear
        ):
            self.accel_g_punch_haptic.launch_active = False

        haptic_gear_factor = _accel_g_punch_haptic_gear_factor(details, gear)
        launch_level = 0.0
        if self.accel_g_punch_haptic.launch_active:
            if throttle_percent < 4.0:
                self.accel_g_punch_haptic.launch_active = False
            else:
                launch_level = _accel_g_punch_launch_accel_level(frame, throttle_percent) * haptic_gear_factor

        shift_level = self._accel_g_punch_haptic_shift_level(
            now,
            frame,
            details,
            gear,
            rpm_ratio,
            throttle_percent,
            haptic_gear_factor,
        )

        low_gear_level = 0.0
        low_gear_factor = _accel_g_punch_low_gear_accel_factor(gear)
        shift_delay_active = (
            self.accel_g_punch_haptic.shift_active
            and gear == self.accel_g_punch_haptic.shift_gear
            and now < self.accel_g_punch_haptic.shift_ready_at
        )
        if low_gear_factor > 0.0 and throttle_percent >= 6.0 and not shift_delay_active:
            accel_level = _accel_g_punch_launch_accel_level(frame, throttle_percent)
            speed_gate = 1.0 - _smoothstep(185.0, 260.0, speed_kmh)
            low_gear_level = accel_level * low_gear_factor * haptic_gear_factor * speed_gate

        level = max(launch_level, shift_level, low_gear_level)
        strength = _detail_float(details, "haptic_strength", 6.0) / 10.0
        level = _clamp(level * strength, 0.0, 1.0)
        previous_level = self.accel_g_punch_haptic.last_level
        self.accel_g_punch_haptic.last_level = level
        if level <= 0.0 and previous_level <= 0.0:
            return ()

        left_gain, right_gain = _effect_pan_gains(details)
        hz = start_hz + (end_hz - start_hz) * level
        payload = accel_g_punch_haptic(
            left=level * left_gain,
            right=level * right_gain,
            hz=max(1.0, min(160.0, hz)),
            volume=float(setting.value) if level > 0.0 else 0.0,
        )
        return (payload,)

    def _begin_accel_g_punch_haptic_upshift(
        self,
        now: float,
        gear: int,
        details: Mapping[str, object],
    ) -> None:
        if gear < 1 or gear == TRANSIENT_GEAR_VALUE:
            return
        delay_ms = _detail_float(details, "shift_delay_ms", 80.0)
        boost_ms = _detail_float(details, "shift_pulse_lock_ms", 90.0)
        self.accel_g_punch_haptic.shift_active = True
        self.accel_g_punch_haptic.shift_gear = gear
        self.accel_g_punch_haptic.shift_start_ratio = -1.0
        self.accel_g_punch_haptic.shift_ready_at = now + delay_ms / 1000.0
        self.accel_g_punch_haptic.shift_boost_until = self.accel_g_punch_haptic.shift_ready_at + boost_ms / 1000.0

    def _accel_g_punch_haptic_shift_level(
        self,
        now: float,
        frame: TelemetryFrame,
        details: Mapping[str, object],
        gear: int,
        rpm_ratio: float,
        throttle_percent: float,
        haptic_gear_factor: float,
    ) -> float:
        if not self.accel_g_punch_haptic.shift_active:
            return 0.0

        shift_start_ratio = _clamp(self.accel_g_punch_haptic.shift_start_ratio, 0.0, 0.95)
        start_unset = self.accel_g_punch_haptic.shift_start_ratio < 0.0
        if now >= self.accel_g_punch_haptic.shift_ready_at and start_unset:
            shift_start_ratio = _clamp(rpm_ratio, 0.0, 0.95)
            self.accel_g_punch_haptic.shift_start_ratio = shift_start_ratio

        output_end_ratio = _accel_g_punch_output_end_ratio(details, gear)
        raw_shift_end_ratio = min(1.0, max(shift_start_ratio + 0.05, output_end_ratio))
        shift_end_ratio = _accel_g_punch_wall_fade_end_ratio(details, gear, shift_start_ratio, raw_shift_end_ratio)
        fade_start_ratio = _accel_g_punch_wall_fade_start_ratio(details, gear, shift_start_ratio, raw_shift_end_ratio)
        fade_start_ratio = min(fade_start_ratio, shift_end_ratio - 0.01)
        if (
            gear != self.accel_g_punch_haptic.shift_gear
            or (not start_unset and rpm_ratio >= shift_end_ratio)
            or throttle_percent < 4.0
        ):
            self.accel_g_punch_haptic.shift_active = False
            return 0.0
        if now < self.accel_g_punch_haptic.shift_ready_at:
            return 0.0
        if now < self.accel_g_punch_haptic.shift_boost_until:
            return 1.0
        if rpm_ratio <= fade_start_ratio:
            rpm_gate = 1.0
        else:
            rpm_gate = 1.0 - _smoothstep(fade_start_ratio, shift_end_ratio, rpm_ratio)
        throttle_gate = _smoothstep(8.0, 55.0, throttle_percent)
        return rpm_gate * throttle_gate * haptic_gear_factor

    def _reset_accel_g_punch_haptic_motion_state(self) -> None:
        self.accel_g_punch_haptic.launch_active = False
        self.accel_g_punch_haptic.launch_gear = 0
        self.accel_g_punch_haptic.shift_active = False
        self.accel_g_punch_haptic.shift_gear = 0
        self.accel_g_punch_haptic.shift_start_ratio = 0.0
        self.accel_g_punch_haptic.shift_ready_at = 0.0
        self.accel_g_punch_haptic.shift_boost_until = 0.0
        self.accel_g_punch_haptic.last_level = 0.0

    def _rev_limit_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        setting = haptic_effects.get(REV_LIMIT)
        if setting is None or not setting.enabled:
            was_active = self.rev_limit.output_active
            self.rev_limit = RevLimitState()
            return (
                rev_limit(
                    rpm=max(0.0, float(frame.rpm or 0.0)),
                    max_rpm=max(0.0, float(frame.max_rpm or 0.0)),
                    idle_rpm=max(0.0, float(frame.idle_rpm or 0.0)),
                    volume=0.0,
                ),
            ) if was_active else ()

        now = monotonic()
        details = _enabled_details(setting)
        state = self._update_rev_limit_vehicle_state(now, frame)
        left, right = _effect_pan_gains(details)
        payload = rev_limit(
            rpm=max(0.0, float(frame.rpm or 0.0)),
            max_rpm=max(0.0, float(frame.max_rpm or 0.0)),
            idle_rpm=max(0.0, float(frame.idle_rpm or 0.0)),
            volume=float(setting.value),
            left=left,
            right=right,
            details=details,
            strength_scale=_rev_limit_strength_scale(state, details),
            observed_max_gear=int(state["observed_max_gear"]),
            is_max_gear=int(state["is_max_gear"]),
            rise_kind=int(state["rise_kind"]),
            rpm_rise_per_s=round(float(state["rpm_rise_per_s"]), 1),
        )
        self.rev_limit.output_active = True
        return (payload,)

    def _update_rev_limit_vehicle_state(
        self,
        now: float,
        frame: TelemetryFrame,
    ) -> dict[str, float | int]:
        car_ordinal = int(frame.car_ordinal or 0)
        gear = int(frame.gear or 0)
        rpm = max(0.0, float(frame.rpm or 0.0))
        state: dict[str, float | int] = {
            "observed_max_gear": self.rev_limit.observed_max_gear,
            "is_max_gear": 0,
            "rpm_rise_per_s": 0.0,
            "rise_kind": 0,
        }
        if car_ordinal <= 0 or gear <= 0 or gear == TRANSIENT_GEAR_VALUE:
            return state

        if self.rev_limit.car_ordinal != car_ordinal:
            self.rev_limit = RevLimitState(car_ordinal=car_ordinal)

        previous_gear = self.rev_limit.previous_gear
        previous_rpm = self.rev_limit.previous_rpm
        previous_at = self.rev_limit.previous_at
        dt = max(0.001, now - previous_at) if previous_at > 0.0 else 0.0
        rpm_rise_per_s = max(0.0, (rpm - previous_rpm) / dt) if dt > 0.0 else 0.0
        if previous_gear is not None and gear < previous_gear and rpm > previous_rpm + 300.0:
            self.rev_limit.downshift_surge_until = now + 0.85

        self.rev_limit.observed_max_gear = max(self.rev_limit.observed_max_gear, gear)
        is_max_gear = 1 if self.rev_limit.observed_max_gear > 0 and gear >= self.rev_limit.observed_max_gear else 0
        rise_kind = 0
        if now <= self.rev_limit.downshift_surge_until:
            rise_kind = 1
        elif rpm_rise_per_s >= 120.0:
            rise_kind = 2

        self.rev_limit.previous_gear = gear
        self.rev_limit.previous_rpm = rpm
        self.rev_limit.previous_at = now
        state.update(
            {
                "observed_max_gear": self.rev_limit.observed_max_gear,
                "is_max_gear": is_max_gear,
                "rpm_rise_per_s": rpm_rise_per_s,
                "rise_kind": rise_kind,
            }
        )
        return state

    def _impact_payloads(
        self,
        frame: TelemetryFrame,
        haptic_effects: Mapping[str, EffectSetting],
    ) -> tuple[OutputEventPayload, ...]:
        now = monotonic()
        previous = self.impacts.previous_frame
        previous_at = self.impacts.previous_at
        self._record_impact_steer(now, frame)

        if previous is None or previous_at <= 0.0:
            self.impacts.previous_frame = frame
            self.impacts.previous_at = now
            return ()

        payloads: list[OutputEventPayload] = []
        side_setting = haptic_effects.get(IMPACT_SIDE) or EffectSetting(0, False, {})
        side_payload = self._side_impact_payload(now, frame, previous, previous_at, side_setting)
        if side_payload is not None:
            self._record_source_payload(side_payload)
            if side_setting.enabled:
                payloads.append(side_payload)

        smashable_setting = haptic_effects.get(IMPACT_SMASHABLE) or EffectSetting(0, False, {})
        smashable_payload = self._smashable_impact_payload(now, frame, smashable_setting)
        if smashable_payload is not None:
            self._record_source_payload(smashable_payload)
            if smashable_setting.enabled:
                payloads.append(smashable_payload)

        impact_setting = haptic_effects.get(IMPACTS) or EffectSetting(0, False, {})
        impact_payload = self._wall_impact_payload(now, frame, previous, previous_at, impact_setting)
        if impact_payload is not None:
            self._record_source_payload(impact_payload)
            if impact_setting.enabled:
                payloads.append(impact_payload)

        self.impacts.previous_frame = frame
        self.impacts.previous_at = now
        return tuple(payloads)

    def _record_source_payload(self, payload: OutputEventPayload) -> None:
        self.last_source_payloads = (*self.last_source_payloads, payload)

    def _record_impact_steer(self, now: float, frame: TelemetryFrame) -> None:
        self.impacts.steer_history.append((now, abs(float(frame.steer or 0.0))))
        while self.impacts.steer_history and now - self.impacts.steer_history[0][0] > 0.50:
            self.impacts.steer_history.popleft()

    def _wall_impact_payload(
        self,
        now: float,
        frame: TelemetryFrame,
        previous: TelemetryFrame,
        previous_at: float,
        setting: EffectSetting,
    ) -> OutputEventPayload | None:
        if now - self.impacts.last_impact_at < 0.22:
            return None

        dt = max(0.001, now - previous_at)
        prev_speed = max(0.0, float(previous.speed or 0.0))
        speed = max(0.0, float(frame.speed or 0.0))
        speed_drop = max(0.0, prev_speed - speed)
        accel_g = _accel_g(frame)
        slip = _slip_combined_max(frame)
        smash_vel_diff = max(0.0, abs(float(frame.smashable_vel_diff or 0.0)))
        smash_mass = max(0.0, abs(float(frame.smashable_mass or 0.0)))

        details = _enabled_details(setting)
        wall_power = 0.0
        speed_drop_threshold = _detail_float(details, "speed_drop_threshold", 18.0)
        g_force_threshold = _detail_float(details, "g_force_threshold", 35.0)
        if dt <= 0.08 and prev_speed >= 15.0:
            speed_hit = min(1.0, speed_drop / 80.0)
            accel_hit = min(1.0, max(0.0, accel_g - 25.0) / 120.0)
            slip_hit = min(1.0, max(0.0, slip - 8.0) / 32.0) * _impact_slip_gain(details)
            if speed_drop >= speed_drop_threshold or accel_g >= g_force_threshold:
                wall_power = max(speed_hit, accel_hit, slip_hit)

        if wall_power <= 0.0:
            return None

        self.impacts.last_impact_at = now
        return impact(
            power=wall_power,
            speed_drop=speed_drop,
            accel_g=accel_g,
            slip=slip,
            mass=smash_mass,
            smash_vel_diff=smash_vel_diff,
            punch=_detail_float(details, "impact_punch", 5.0),
            length=_detail_float(details, "impact_length", 5.0),
            low_hz=_detail_float(details, "low_impact_hz", 44.0),
            high_hz=_detail_float(details, "high_impact_hz", 78.0),
            volume=float(setting.value) if setting.enabled else 0.0,
        )

    def _smashable_impact_payload(
        self,
        now: float,
        frame: TelemetryFrame,
        setting: EffectSetting,
    ) -> OutputEventPayload | None:
        details = _enabled_details(setting)
        cooldown_s = _detail_float(details, "repeat_cooldown", 65.0) / 1000.0
        if now - self.impacts.last_smashable_impact_at < cooldown_s:
            return None

        smash_vel_diff = max(0.0, abs(float(frame.smashable_vel_diff or 0.0)))
        smash_mass = max(0.0, abs(float(frame.smashable_mass or 0.0)))
        threshold = _smashable_velocity_threshold(details)
        if smash_vel_diff <= threshold:
            return None

        vel_gain = min(1.0, max(0.0, (smash_vel_diff - threshold) / max(0.2 - threshold, 0.000001)))
        mass_norm = min(1.0, max(0.0, math.log(1 + smash_mass) / math.log(1 + 80))) if smash_mass > 0 else 0.35
        mass_gain = 0.55 + (1.0 - 0.55) * mass_norm
        speed_gain = min(1.0, max(0.0, max(0.0, float(frame.speed or 0.0)) - 20.0) / 120.0)
        power = max(0.05, min(1.0, vel_gain * mass_gain * (0.65 + speed_gain * 0.35)))

        self.impacts.last_smashable_impact_at = now
        return impact_smashable(
            power=power,
            mass=smash_mass,
            smash_vel_diff=smash_vel_diff,
            speed=max(0.0, float(frame.speed or 0.0)),
            punch=_detail_float(details, "smash_punch", 5.0),
            rattle=_detail_float(details, "rattle_strength", 5.0),
            length=_detail_float(details, "smash_length", 5.0),
            light_hz=_detail_float(details, "light_object_hz", 115.0),
            heavy_hz=_detail_float(details, "heavy_object_hz", 58.0),
            volume=float(setting.value) if setting.enabled else 0.0,
        )

    def _side_impact_payload(
        self,
        now: float,
        frame: TelemetryFrame,
        previous: TelemetryFrame,
        previous_at: float,
        setting: EffectSetting,
    ) -> OutputEventPayload | None:
        if now - self.impacts.last_side_impact_at < 0.24:
            return None

        dt = max(0.001, now - previous_at)
        if dt > 0.11:
            return None

        speed = max(0.0, float(frame.speed or 0.0))
        if speed < 12.0:
            return None
        if float(frame.brake or 0.0) >= 20.0:
            return None

        dvel = math.sqrt(
            (float(frame.velocity_x or 0.0) - float(previous.velocity_x or 0.0)) ** 2
            + (float(frame.velocity_y or 0.0) - float(previous.velocity_y or 0.0)) ** 2
            + (float(frame.velocity_z or 0.0) - float(previous.velocity_z or 0.0)) ** 2
        ) * 3.6
        accel_x = abs(float(frame.accel_x or 0.0))
        accel_y = abs(float(frame.accel_y or 0.0))
        accel_z = abs(float(frame.accel_z or 0.0))
        accel_x_delta = abs(float(frame.accel_x or 0.0) - float(previous.accel_x or 0.0))
        accel_y_delta = abs(float(frame.accel_y or 0.0) - float(previous.accel_y or 0.0))
        accel_z_delta = abs(float(frame.accel_z or 0.0) - float(previous.accel_z or 0.0))
        angular_y = abs(float(frame.angular_velocity_y or 0.0))
        angular_y_delta = abs(float(frame.angular_velocity_y or 0.0) - float(previous.angular_velocity_y or 0.0))
        recent_steer = max((steer for _ts, steer in self.impacts.steer_history), default=0.0)

        details = _enabled_details(setting)
        sensitivity_scale = _side_impact_sensitivity_scale(details)
        lateral_threshold = 5.8 * sensitivity_scale
        edge_threshold = 3.8 * sensitivity_scale
        steer_context = 14.0 * sensitivity_scale
        dvel_score = _clamp((dvel - 0.9 * sensitivity_scale) / 5.8, 0.0, 1.0)
        accel_x_score = _clamp((accel_x - 4.5 * sensitivity_scale) / 13.0, 0.0, 1.0)
        accel_z_score = _clamp((accel_z - 3.2 * sensitivity_scale) / 15.0, 0.0, 1.0)
        angular_score = _clamp(angular_y / max(0.85 * sensitivity_scale, 0.001), 0.0, 1.0)
        steer_score = _clamp((recent_steer - max(0.0, steer_context - 2.0)) / 48.0, 0.0, 1.0)
        speed_score = _clamp((speed - 12.0) / 60.0, 0.0, 1.0)
        impact_score = (
            dvel_score * 0.32
            + accel_x_score * 0.27
            + accel_z_score * 0.18
            + angular_score * 0.13
            + steer_score * 0.07
            + speed_score * 0.03
        )

        has_lateral_signature = accel_x >= lateral_threshold or angular_y >= 0.18 * sensitivity_scale or (
            dvel >= 1.4 * sensitivity_scale and accel_x >= max(lateral_threshold + 0.7, 6.5 * sensitivity_scale)
        )
        has_lateral_edge = accel_x_delta >= edge_threshold or angular_y_delta >= 0.12 * sensitivity_scale or (
            dvel >= 1.4 * sensitivity_scale and accel_x >= 7.0 * sensitivity_scale and accel_x_delta >= 2.2 * sensitivity_scale
        )
        has_impact_edge = has_lateral_edge and (
            dvel >= 1.0 * sensitivity_scale or accel_x_delta >= edge_threshold or accel_z_delta >= 5.0 * sensitivity_scale
        )
        has_steering_context = recent_steer >= steer_context
        bump_rejection_scale = _side_impact_bump_rejection_scale(details)
        vertical_dominant_bump = (
            accel_y_delta >= 2.0 / bump_rejection_scale
            and accel_y_delta >= accel_x_delta * (1.10 / bump_rejection_scale)
            and accel_y_delta >= angular_y_delta * (30.0 / bump_rejection_scale)
            and accel_x_delta < 6.0 * bump_rejection_scale
        )
        suspension_step_bump = (
            accel_y >= 11.0 / bump_rejection_scale
            and accel_y_delta >= 4.5 / bump_rejection_scale
            and dvel < 2.4 * bump_rejection_scale
            and angular_y_delta < 0.18 * bump_rejection_scale
        )
        if vertical_dominant_bump or suspension_step_bump:
            return None
        if impact_score < 0.16 * sensitivity_scale or not (
            has_lateral_signature and has_steering_context and has_impact_edge
        ):
            return None

        edge_score = max(
            _clamp((dvel - 1.25) / 5.0, 0.0, 1.0),
            _clamp((accel_x_delta - 3.8) / 12.0, 0.0, 1.0),
            _clamp((angular_y_delta - 0.12) / 0.55, 0.0, 1.0),
        )
        power = max(0.04, min(1.0, (impact_score * 0.70 + edge_score * 0.30) ** 1.15))
        self.impacts.last_side_impact_at = now
        return impact_side(
            power=power,
            dvel=dvel,
            accel_x=accel_x,
            accel_z=accel_z,
            accel_x_delta=accel_x_delta,
            accel_y_delta=accel_y_delta,
            accel_z_delta=accel_z_delta,
            angular_y_delta=angular_y_delta,
            angular_y=angular_y,
            recent_steer=recent_steer,
            scrape=_detail_float(details, "scrape_strength", 5.0),
            length=_detail_float(details, "side_length", 5.0),
            volume=float(setting.value) if setting.enabled else 0.0,
        )


def _enabled_details(setting: EffectSetting | None) -> dict:
    if setting is None:
        return {"volume": 0}
    details = dict(setting.details)
    details["volume"] = setting.value if setting.enabled else 0
    return details


def _positive_int(value: int | None) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def _rumble_kerbs_frequency(speed_kmh: float, details: Mapping[str, object]) -> float:
    low_speed_hz = _detail_float(details, "low_speed_hz", 18.0)
    high_speed_hz = _detail_float(details, "high_speed_hz", 82.0)
    low_speed_kmh = _detail_float(details, "speed_low_start", 5.0)
    high_speed_kmh = _detail_float(details, "speed_high_max", 330.0)
    speed_mix = _smoothstep(low_speed_kmh, high_speed_kmh, speed_kmh)
    hz = low_speed_hz + (high_speed_hz - low_speed_hz) * speed_mix
    return _clamp(hz, 1.0, 160.0)


def _is_rumble_kerb_on(
    surface_rumble: float | None,
    wheel_on_rumble: int | None,
    low: float,
    high: float,
) -> bool:
    rumble = abs(float(surface_rumble or 0.0))
    wheel_flag = int(wheel_on_rumble or 0)
    return low <= rumble <= high or wheel_flag != 0


def _is_asphalt_surface(frame: TelemetryFrame) -> bool:
    return abs(float(frame.surface_rumble_fl or 0.0)) < 0.001 and abs(float(frame.surface_rumble_fr or 0.0)) < 0.001


def _road_bumps_threshold_scale(details: Mapping[str, object]) -> float:
    sensitivity = _detail_float(details, "bump_sensitivity", 5.0)
    return _clamp(1.0 - (sensitivity - 5.0) * 0.09, 0.55, 1.45)


def _road_bumps_low_class_correction_scale(details: Mapping[str, object]) -> float:
    correction = _detail_float(details, "low_class_correction", 3.0)
    return _clamp(correction / 3.0, 0.0, 10.0 / 3.0)


def _road_bumps_strength_gain(target_level: float, details: Mapping[str, object]) -> float:
    small_gain = _detail_float(details, "small_bump_strength", 5.0) / 5.0
    large_gain = _detail_float(details, "large_bump_strength", 5.0) / 5.0
    large_mix = _smoothstep(0.35, 0.75, target_level)
    return small_gain * (1.0 - large_mix) + large_gain * large_mix


def _road_bumps_attack_alpha(details: Mapping[str, object]) -> float:
    attack = _detail_float(details, "attack", 5.0)
    if attack <= 5.0:
        return 0.42 + (0.82 - 0.42) * (attack / 5.0)
    return 0.82 + (0.95 - 0.82) * ((attack - 5.0) / 5.0)


def _road_bumps_decay_scale(details: Mapping[str, object]) -> float:
    decay = _detail_float(details, "decay", 5.0)
    return 0.60 + decay * 0.08


def _road_bump_low_class_gain(car_class: int, details: Mapping[str, object]) -> float:
    correction_scale = _road_bumps_low_class_correction_scale(details)
    if car_class <= 0:
        return 1.0 + 0.30 * correction_scale
    if car_class == 1:
        return 1.0 + 0.20 * correction_scale
    if car_class == 2:
        return 1.0 + 0.10 * correction_scale
    return 1.0


def _road_bump_low_class_threshold_scale(car_class: int, details: Mapping[str, object]) -> float:
    correction_scale = _road_bumps_low_class_correction_scale(details)
    if car_class <= 0:
        return max(0.55, 1.0 - 0.18 * correction_scale)
    if car_class == 1:
        return max(0.55, 1.0 - 0.10 * correction_scale)
    return 1.0


def _road_bump_side_level(
    suspension_rate: float,
    vertical_gate: float,
    speed_gate: float,
    is_asphalt: bool,
    threshold_scale: float,
) -> float:
    scale = _clamp(threshold_scale, 0.55, 1.45)
    if is_asphalt:
        suspension_gate = _smoothstep(1.50 * scale, 12.20, suspension_rate)
        level = max(suspension_gate, vertical_gate * 0.70) * speed_gate
    else:
        suspension_gate = _smoothstep(2.20 * scale, 8.50, suspension_rate)
        level = max(suspension_gate, vertical_gate * 0.62) * speed_gate
    return _clamp(level, 0.0, 1.0)


def _road_bump_envelope(
    previous: float,
    target: float,
    is_asphalt: bool,
    details: Mapping[str, object],
) -> float:
    target = _clamp(target, 0.0, 1.0)
    if target > previous:
        return previous + (target - previous) * _road_bumps_attack_alpha(details)

    decay_scale = _road_bumps_decay_scale(details)
    if is_asphalt:
        decayed = max(
            0.0,
            previous * _clamp(0.62 * decay_scale, 0.10, 0.92)
            + target * _clamp(0.14 * decay_scale, 0.02, 0.35),
        )
        return 0.0 if decayed < 0.018 else decayed

    decayed = max(
        0.0,
        previous * _clamp(0.48 * decay_scale, 0.08, 0.88)
        + target * _clamp(0.10 * decay_scale, 0.02, 0.30),
    )
    return 0.0 if decayed < 0.035 else decayed


def _tire_limit_side_level(
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
    previous: float,
    details: Mapping[str, object],
) -> float:
    side_limit_window = _smoothstep(0.65, 1.40, side_front_angle) * (
        1.0 - _smoothstep(2.45, 3.60, side_front_angle)
    )
    side_combined_window = _smoothstep(0.25, 0.85, side_front_combined) * (
        1.0 - _smoothstep(2.65, 3.95, side_front_combined)
    )
    side_lateral_g = -gx_smooth if output_side < 0 else gx_smooth
    lateral_side = _smoothstep(0.04, 1.20, side_lateral_g)
    brake_bias = _smoothstep(0.06, 1.00, abs_lateral_g) * 0.30
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
    raw_clamped = _clamp(raw, 0.0, 1.0)
    entry_threshold = _detail_float(details, "entry_threshold", 40.0) / 100.0
    if entry_threshold > 0.0:
        raw_clamped = max(0.0, (raw_clamped - entry_threshold) / max(1.0 - entry_threshold, 0.001))
    target = raw_clamped ** 0.85
    alpha = _tire_limit_attack_alpha(details) if target > previous else 0.62
    out = previous + (target - previous) * alpha
    return _clamp(out, 0.0, 1.0)


def _tire_limit_frequency(value_0_100: float, details: Mapping[str, object]) -> float:
    value = _clamp(value_0_100, 0.0, 100.0)
    entry_trigger = _detail_float(details, "entry_threshold", 40.0)
    force_loaded_at = max(entry_trigger + 1.0, _detail_float(details, "full_load_point", 40.0))
    loaded_mix = _smoothstep(force_loaded_at, 100.0, value)
    low_load_hz = _detail_float(details, "low_load_hz", 40.0)
    high_load_hz = _detail_float(details, "high_load_hz", 15.0)
    return low_load_hz + (high_load_hz - low_load_hz) * loaded_mix


def _tire_limit_attack_alpha(details: Mapping[str, object]) -> float:
    attack = _detail_float(details, "attack", 5.0)
    if attack <= 5.0:
        return 0.18 + (0.42 - 0.18) * (attack / 5.0)
    return 0.42 + (0.70 - 0.42) * ((attack - 5.0) / 5.0)


def _wheelspin_side_level(
    slip_ratio: float,
    throttle_gate: float,
    speed_gate: float,
    details: Mapping[str, object],
) -> float:
    slip_offset = _detail_float(details, "slip_start_offset", 0.0) * 0.05
    slip_on_start = max(0.2, 1.3 + slip_offset)
    slip_on_end = max(slip_on_start + 0.1, 1.9 + slip_offset)
    slip_on = _smoothstep(slip_on_start, slip_on_end, slip_ratio)
    slip_cut = 1.0 - _smoothstep(2.1, 2.85, slip_ratio)
    return _clamp(slip_on * slip_cut * throttle_gate * speed_gate, 0.0, 1.0)


def _wheelspin_envelope(
    previous: float,
    target: float,
    details: Mapping[str, object],
) -> float:
    if target > previous:
        floor = 0.18 if target > 0.05 else 0.0
        return max(floor, previous + (target - previous) * _wheelspin_buzz_attack_alpha(details))
    return max(0.0, previous * 0.82 + target * 0.08)


def _wheelspin_buzz_attack_alpha(details: Mapping[str, object]) -> float:
    attack = _detail_float(details, "attack", 5.0)
    if attack <= 5.0:
        return 0.28 + (0.62 - 0.28) * (attack / 5.0)
    return 0.62 + (0.82 - 0.62) * ((attack - 5.0) / 5.0)


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


def _accel_g_punch_output_end_ratio(details: Mapping[str, object], gear: int) -> float:
    max_offset = round(_detail_float(details, "max_rpm_offset", 10.0))
    drop_offset = round(_detail_float(details, "gear_drop_offset", 9.0))
    max_offset = int(_clamp(max_offset, 0, 10))
    drop_offset = int(_clamp(drop_offset, 0, 9))
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
    fade_percent = round(_detail_float(details, "shift_wall_fade_percent", 40.0))
    fade_percent = int(_clamp(fade_percent, 0, 90))
    span = max(0.01, end_ratio - start_ratio)
    return max(start_ratio, min(end_ratio - 0.01, start_ratio + span * fade_percent / 100.0))


def _accel_g_punch_wall_fade_end_ratio(
    details: Mapping[str, object],
    gear: int,
    start_ratio: float,
    end_ratio: float,
) -> float:
    fade_percent = int(_clamp(round(_detail_float(details, "shift_wall_fade_percent", 40.0)), 0, 90))
    tail_percent = int(_clamp(round(_detail_float(details, "shift_fade_tail_percent", 35.0)), 0, 100))
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


def _accel_g_punch_haptic_gear_factor(details: Mapping[str, object], gear: int) -> float:
    if gear <= 1:
        percent = _detail_float(details, "haptic_gear_1_percent", 100.0)
    elif gear == 2:
        percent = _detail_float(details, "haptic_gear_2_percent", 100.0)
    else:
        base_percent = _detail_float(details, "haptic_gear_3_percent", 50.0)
        third_gear_factor = max(0.01, _accel_g_punch_shift_gear_factor(3))
        gear_decay = _accel_g_punch_shift_gear_factor(gear) / third_gear_factor
        percent = round(base_percent * gear_decay)
    return _clamp(percent / 100.0, 0.0, 1.5)


def _effect_pan_gains(details: Mapping[str, object]) -> tuple[float, float]:
    pan = _clamp(round(_detail_float(details, "pan", 5.0)), 0.0, 10.0)
    left = 1.0 if pan <= 5.0 else max(0.0, (10.0 - pan) / 5.0)
    right = 1.0 if pan >= 5.0 else max(0.0, pan / 5.0)
    return left, right


def _rev_limit_strength_scale(
    state: Mapping[str, float | int],
    details: Mapping[str, object],
) -> float:
    scale = 1.0
    if int(state.get("is_max_gear", 0)):
        scale *= 0.45 + 0.55 * (_detail_float(details, "max_gear_limit", 7.0) / 10.0)
    rise_kind = int(state.get("rise_kind", 0))
    if rise_kind == 1:
        scale *= 0.45 + 0.75 * (_detail_float(details, "downshift_surge", 5.0) / 10.0)
    elif rise_kind == 2:
        scale *= 0.45 + 0.75 * (_detail_float(details, "climb_strength", 5.0) / 10.0)
    return _clamp(scale, 0.0, 1.2)


def _accel_g(frame: TelemetryFrame) -> float:
    return math.sqrt(
        float(frame.accel_x or 0.0) ** 2
        + float(frame.accel_y or 0.0) ** 2
        + float(frame.accel_z or 0.0) ** 2
    )


def _slip_combined_max(frame: TelemetryFrame) -> float:
    return max(
        abs(float(frame.tire_combined_slip_fl or 0.0)),
        abs(float(frame.tire_combined_slip_fr or 0.0)),
        abs(float(frame.tire_combined_slip_rl or 0.0)),
        abs(float(frame.tire_combined_slip_rr or 0.0)),
    )


def _impact_slip_gain(details: Mapping[str, object]) -> float:
    return _detail_float(details, "slip_influence", 5.0) / 5.0


def _side_impact_sensitivity_scale(details: Mapping[str, object]) -> float:
    sensitivity = _detail_float(details, "side_sensitivity", 5.0)
    return _clamp(1.0 - (sensitivity - 5.0) * 0.08, 0.60, 1.40)


def _side_impact_bump_rejection_scale(details: Mapping[str, object]) -> float:
    rejection = _detail_float(details, "bump_rejection", 5.0)
    return _clamp(1.0 + (rejection - 5.0) * 0.10, 0.50, 1.50)


def _smashable_velocity_threshold(details: Mapping[str, object]) -> float:
    sensitivity = _detail_float(details, "smash_sensitivity", 5.0)
    return _clamp(0.01 * (1.0 - (sensitivity - 5.0) * 0.12), 0.002, 0.030)


def _haptic_debug_specs_from_payloads(
    payloads: tuple[OutputEventPayload, ...],
    updated_at: float,
) -> dict[str, dict[str, float]]:
    specs: dict[str, dict[str, float]] = {}
    for payload in payloads:
        params = _payload_float_params(payload)
        if payload.name == "GEAR_SHIFT":
            _set_haptic_debug_spec(
                specs,
                GEAR_SHIFT_CORE,
                params.get("coreVolume", 0.0) * 10.0,
                params.get("coreLeft", 0.0),
                params.get("coreRight", 0.0),
                0.0,
                updated_at,
            )
            _set_haptic_debug_spec(
                specs,
                GEAR_SHIFT_HIGH_HZ,
                params.get("highHzVolume", 0.0) * 10.0,
                params.get("highHzLeft", 0.0),
                params.get("highHzRight", 0.0),
                0.0,
                updated_at,
            )
            _set_haptic_debug_spec(
                specs,
                GEAR_SHIFT_PARTICLES,
                params.get("particlesVolume", 0.0) * 10.0,
                params.get("particlesLeft", 0.0),
                params.get("particlesRight", 0.0),
                0.0,
                updated_at,
            )
        elif payload.name == "RUMBLE_KERBS":
            _set_lr_haptic_debug_spec(specs, RUMBLE_KERBS, params, "fl", "fr", "hz", updated_at)
        elif payload.name == "TIRE_LIMIT_LOAD":
            _set_lr_haptic_debug_spec(specs, TIRE_LIMIT_LOAD, params, "left", "right", "leftHz", updated_at)
        elif payload.name == "WHEELSPIN_BUZZ":
            _set_lr_haptic_debug_spec(specs, WHEELSPIN_BUZZ, params, "left", "right", "hz", updated_at)
        elif payload.name == "ACCEL_G_PUNCH_HAPTIC":
            _set_lr_haptic_debug_spec(specs, ACCEL_G_PUNCH_HAPTIC, params, "left", "right", "hz", updated_at)
        elif payload.name == "REV_LIMIT":
            level = max(params.get("left", 0.0), params.get("right", 0.0)) * params.get("volume", 0.0) * 10.0
            level *= params.get("strengthScale", 1.0)
            _set_haptic_debug_spec(
                specs,
                REV_LIMIT,
                level,
                params.get("left", 0.0),
                params.get("right", 0.0),
                0.0,
                updated_at,
            )
        elif payload.name == "ROAD_BUMPS":
            _set_lr_haptic_debug_spec(specs, ROAD_BUMPS, params, "left", "right", "hz", updated_at)
        elif payload.name == "IMPACT":
            _set_haptic_debug_spec(
                specs,
                IMPACTS,
                params.get("power", 0.0) * params.get("volume", 0.0) * 10.0,
                1.0,
                1.0,
                max(params.get("lowHz", 0.0), params.get("highHz", 0.0)),
                updated_at,
            )
        elif payload.name == "IMPACT_SIDE":
            _set_haptic_debug_spec(
                specs,
                IMPACT_SIDE,
                params.get("power", 0.0) * params.get("volume", 0.0) * 10.0,
                1.0,
                1.0,
                0.0,
                updated_at,
            )
        elif payload.name == "IMPACT_SMASHABLE":
            _set_haptic_debug_spec(
                specs,
                IMPACT_SMASHABLE,
                params.get("power", 0.0) * params.get("volume", 0.0) * 10.0,
                1.0,
                1.0,
                max(params.get("lightHz", 0.0), params.get("heavyHz", 0.0)),
                updated_at,
            )
    return specs


def _set_lr_haptic_debug_spec(
    specs: dict[str, dict[str, float]],
    name: str,
    params: Mapping[str, float],
    left_key: str,
    right_key: str,
    freq_key: str,
    updated_at: float,
) -> None:
    left = params.get(left_key, 0.0)
    right = params.get(right_key, 0.0)
    level = max(left, right) * params.get("volume", 0.0) * 10.0
    _set_haptic_debug_spec(specs, name, level, left, right, params.get(freq_key, 0.0), updated_at)


def _set_haptic_debug_spec(
    specs: dict[str, dict[str, float]],
    name: str,
    level: float,
    left: float,
    right: float,
    frequency: float,
    updated_at: float,
) -> None:
    previous = specs.get(name)
    level = _clamp(level, 0.0, 100.0)
    if previous is not None and previous["level"] >= level:
        return
    specs[name] = {
        "level": level,
        "left": _clamp(left, 0.0, 1.0),
        "right": _clamp(right, 0.0, 1.0),
        "frequency": max(0.0, float(frequency)),
        "updated_at": float(updated_at),
    }


def _payload_float_params(payload: OutputEventPayload) -> dict[str, float]:
    values: dict[str, float] = {}
    for key, value in payload.params:
        try:
            values[key] = float(value)
        except (TypeError, ValueError):
            values[key] = 0.0
    return values


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 >= edge1:
        return 1.0 if value >= edge1 else 0.0
    x = _clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _detail_float(details: Mapping[str, object], key: str, fallback: float) -> float:
    try:
        return float(details.get(key, fallback))
    except (TypeError, ValueError):
        return fallback


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, float(value)))
