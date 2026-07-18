from __future__ import annotations

from time import monotonic

from .settings_model import EffectSetting
from .telemetry_frame import TelemetryFrame


DRIFT_SCORE_DECAY_PER_SECOND = 0.28
DRIFT_MODE_ENTER_SCORE = 0.56
DRIFT_MODE_ENTER_HOLD_SECONDS = 0.30
DRIFT_MODE_KEEP_SCORE = 0.50
DRIFT_MODE_RELEASE_SCORE = 0.18

DRIFT_RUMBLE_FADE = "Drift Rumble Fade"
WHEELSPIN_BUZZ = "Wheelspin Buzz"
THROTTLE_PRESSURE = "Throttle Pressure"
THROTTLE_TRACTION = "Throttle Resistance - Traction"
ACCEL_G_PUNCH = "Acceleration G Punch"
RPM_REV_LIMIT = "RPM Rev Limit"

GAIN_DETAIL_KEYS = {
    WHEELSPIN_BUZZ: "wheelspin_buzz",
    THROTTLE_PRESSURE: "throttle_pressure",
    THROTTLE_TRACTION: "throttle_traction",
    ACCEL_G_PUNCH: "accel_g_punch",
    RPM_REV_LIMIT: "rpm_rev_limit",
}


class DriftRumbleFadeEngine:
    """Port of the legacy sustained-drift detector and output fade filter."""

    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.active = False
        self.score = 0.0
        self.score_last_update = 0.0
        self.hold_until = 0.0
        self.candidate_since = 0.0
        self.oversteer_component = 0.0
        self.high_score_since = 0.0
        self.suppression_active = False
        self.last_gains: dict[str, float] = {}

    def update(
        self,
        frame: TelemetryFrame,
        setting: EffectSetting | None,
    ) -> dict[str, float]:
        if (
            not frame.parsed
            or frame.is_race_on is False
            or setting is None
            or not setting.enabled
        ):
            self.reset()
            return {}

        now = monotonic()
        target = self._compute_score(frame)
        self.score = self._smoothed_score(now, target)
        if self.score >= DRIFT_MODE_ENTER_SCORE:
            if self.candidate_since <= 0.0:
                self.candidate_since = now
            if self.active or now - self.candidate_since >= DRIFT_MODE_ENTER_HOLD_SECONDS:
                self.active = True
                self.hold_until = now + 2.20
        elif self.active and self.score >= DRIFT_MODE_KEEP_SCORE:
            self.hold_until = now + 2.20
        else:
            self.candidate_since = 0.0
        if self.score <= DRIFT_MODE_RELEASE_SCORE and now >= self.hold_until:
            self.active = False

        self._update_suppression(now, setting)
        if not self.suppression_active:
            self.last_gains = {}
            return {}

        details = setting.details or {}
        gains: dict[str, float] = {}
        for effect_name, detail_key in GAIN_DETAIL_KEYS.items():
            configured = _detail_0_10(details, detail_key, _default_gain_value(detail_key)) / 10.0
            gains[effect_name] = _clamp(configured, 0.0, 1.0)
        self.last_gains = gains
        return dict(gains)

    def _update_suppression(self, now: float, setting: EffectSetting) -> None:
        if not self.active:
            self.high_score_since = 0.0
            self.suppression_active = False
            return

        looseness = _detail_0_10(setting.details or {}, "condition_strictness", 5) / 10.0
        enter_score = 0.82 + (0.60 - 0.82) * looseness
        hold_seconds = 2.80 + (1.10 - 2.80) * looseness
        release_score = max(0.35, enter_score - 0.15)
        if self.score < release_score:
            self.high_score_since = 0.0
            self.suppression_active = False
            return
        if self.score < enter_score:
            if not self.suppression_active:
                self.high_score_since = 0.0
            return
        if self.high_score_since <= 0.0:
            self.high_score_since = now
        if now - self.high_score_since >= hold_seconds:
            self.suppression_active = True

    def _compute_score(self, frame: TelemetryFrame) -> float:
        speed_gate = _smoothstep(18.0, 55.0, max(0.0, float(frame.speed or 0.0)))
        if speed_gate <= 0.0:
            self.oversteer_component = 0.0
            return 0.0

        raw_balance, grip_loss = self._raw_oversteer_balance(frame)
        oversteer_gate = self._smoothed_oversteer(
            self._drift_oversteer_signal(frame, raw_balance, grip_loss)
        )
        grip_gate = _smoothstep(0.18, 0.65, grip_loss)
        slip_angle_gate = _smoothstep(0.28, 0.95, abs(_hud_slip_angle_value(frame)))
        driven_ratio, driven_combined = _driven_slip_values(frame)
        driven_slip_gate = max(
            _smoothstep(1.10, 1.95, driven_ratio),
            _smoothstep(0.70, 1.65, driven_combined),
        )
        wheel_over_gate = _driven_wheel_overrotation_gate(frame)
        yaw_gate = _smoothstep(0.30, 1.10, abs(float(frame.angular_velocity_y or 0.0)))
        drive_gate = max(driven_slip_gate, wheel_over_gate)
        rotation_context = max(yaw_gate, oversteer_gate, wheel_over_gate * 0.72)
        angle_with_rotation = slip_angle_gate * rotation_context
        drift_shape = max(oversteer_gate * 0.58, angle_with_rotation * 0.82, yaw_gate * 0.72)
        drift_context = max(
            grip_gate * 0.78,
            drive_gate * 0.58,
            min(slip_angle_gate, max(yaw_gate, oversteer_gate)) * 0.52,
        )
        sustained_score = (
            angle_with_rotation * 0.24
            + grip_gate * 0.30
            + drive_gate * 0.24
            + oversteer_gate * 0.16
            + yaw_gate * 0.06
        )
        score = max(
            drift_shape * drift_context,
            sustained_score,
            oversteer_gate * grip_gate * 0.62,
            yaw_gate * grip_gate * drive_gate * 0.55,
        )
        if yaw_gate < 0.22 and oversteer_gate < 0.28:
            score = min(score, 0.44)
        return _clamp(score * speed_gate, 0.0, 1.0)

    def _raw_oversteer_balance(self, frame: TelemetryFrame) -> tuple[float, float]:
        front_angle = (
            abs(float(frame.tire_slip_angle_fl or 0.0))
            + abs(float(frame.tire_slip_angle_fr or 0.0))
        ) * 0.5
        rear_angle = (
            abs(float(frame.tire_slip_angle_rl or 0.0))
            + abs(float(frame.tire_slip_angle_rr or 0.0))
        ) * 0.5
        diff = rear_angle - front_angle
        speed = max(0.0, float(frame.speed or 0.0))
        speed_gate = _smoothstep(12.0, 62.0, speed)
        high_speed_gain = 1.0 + 0.22 * _smoothstep(95.0, 180.0, speed)
        speed_scale = (0.18 + 0.82 * speed_gate) * high_speed_gain
        magnitude = _clamp(_smoothstep(0.04, 0.85, abs(diff)) * speed_scale, 0.0, 1.0)
        slip_max = max(
            abs(float(frame.tire_combined_slip_fl or 0.0)),
            abs(float(frame.tire_combined_slip_fr or 0.0)),
            abs(float(frame.tire_combined_slip_rl or 0.0)),
            abs(float(frame.tire_combined_slip_rr or 0.0)),
        )
        throttle = _clamp(float(frame.throttle or 0.0) / 255.0, 0.0, 1.0)
        brake = _clamp(float(frame.brake or 0.0) / 255.0, 0.0, 1.0)
        lateral_g = abs(float(frame.accel_x or 0.0)) / 9.80665
        drive_load = max(throttle, brake)
        coasting_steer = _smoothstep(0.0, 0.18, 0.18 - drive_load)
        grip_loss = _smoothstep(0.95 + 0.38 * coasting_steer, 2.65 + 0.35 * coasting_steer, slip_max)
        load_gate = max(
            _smoothstep(0.05, 0.38, drive_load),
            _smoothstep(0.45, 1.15, lateral_g),
        )
        grip_loss *= 0.35 + 0.65 * load_gate
        if magnitude <= 0.0:
            return 0.0, grip_loss
        return (magnitude if diff > 0.0 else -magnitude), grip_loss

    def _drift_oversteer_signal(
        self,
        frame: TelemetryFrame,
        raw_balance: float,
        grip_loss: float,
    ) -> float:
        rear_bias_gate = _smoothstep(0.05, 1.25, max(0.0, raw_balance))
        slip_angle_gate = _smoothstep(0.22, 0.90, abs(_hud_slip_angle_value(frame)))
        yaw_gate = _smoothstep(0.20, 1.05, abs(float(frame.angular_velocity_y or 0.0)))
        lateral_gate = _smoothstep(0.25, 1.05, abs(float(frame.accel_x or 0.0)) / 9.80665)
        steer_gate = _smoothstep(0.06, 0.46, abs(float(frame.steer or 0.0)) / 127.0)
        sustained_rotation = yaw_gate * max(slip_angle_gate, lateral_gate * 0.70) * max(0.55, steer_gate)
        sliding_context = max(grip_loss * 0.62, lateral_gate * 0.42, steer_gate * 0.28)
        body_slip = slip_angle_gate * max(rear_bias_gate, yaw_gate * 0.70, sliding_context * 0.55)
        return _clamp(max(rear_bias_gate, sustained_rotation, body_slip), 0.0, 1.0)

    def _smoothed_oversteer(self, target: float) -> float:
        target = _clamp(target, 0.0, 1.0)
        alpha = 0.34 if target > self.oversteer_component else 0.16
        value = self.oversteer_component + (target - self.oversteer_component) * alpha
        if target < 0.025 and value < 0.035:
            value = 0.0
        self.oversteer_component = _clamp(value, 0.0, 1.0)
        return self.oversteer_component

    def _smoothed_score(self, now: float, target: float) -> float:
        target = _clamp(target, 0.0, 1.0)
        previous = _clamp(self.score, 0.0, 1.0)
        dt = 0.0 if self.score_last_update <= 0.0 else _clamp(now - self.score_last_update, 0.0, 0.2)
        self.score_last_update = now
        if target >= previous:
            alpha = 0.55 if dt <= 0.0 else min(0.85, 0.45 + dt * 3.0)
            value = previous + (target - previous) * alpha
        else:
            value = max(target, previous - DRIFT_SCORE_DECAY_PER_SECOND * max(dt, 1.0 / 120.0))
        if target < 0.025 and value < 0.035:
            value = 0.0
        return _clamp(value, 0.0, 1.0)


def _hud_slip_angle_value(frame: TelemetryFrame) -> float:
    if float(frame.speed or 0.0) < 3.0:
        return 0.0
    value = (
        float(frame.tire_slip_angle_fl or 0.0)
        + float(frame.tire_slip_angle_fr or 0.0)
        + float(frame.tire_slip_angle_rl or 0.0)
        + float(frame.tire_slip_angle_rr or 0.0)
    ) * 0.25
    return 0.0 if abs(value) < 0.025 else -value


def _driven_slip_values(frame: TelemetryFrame) -> tuple[float, float]:
    if int(frame.drive_train if frame.drive_train is not None else 1) == 0:
        ratios = (frame.tire_slip_ratio_fl, frame.tire_slip_ratio_fr)
        combined = (frame.tire_combined_slip_fl, frame.tire_combined_slip_fr)
    else:
        ratios = (frame.tire_slip_ratio_rl, frame.tire_slip_ratio_rr)
        combined = (frame.tire_combined_slip_rl, frame.tire_combined_slip_rr)
    return (
        max(0.0, *(max(0.0, float(value or 0.0)) for value in ratios)),
        max(0.0, *(abs(float(value or 0.0)) for value in combined)),
    )


def _driven_wheel_overrotation_gate(frame: TelemetryFrame) -> float:
    front = (
        abs(float(frame.wheel_rotation_speed_fl or 0.0))
        + abs(float(frame.wheel_rotation_speed_fr or 0.0))
    ) * 0.5
    rear = (
        abs(float(frame.wheel_rotation_speed_rl or 0.0))
        + abs(float(frame.wheel_rotation_speed_rr or 0.0))
    ) * 0.5
    driven, reference = (front, rear) if int(frame.drive_train or 0) == 0 else (rear, front)
    if reference < 0.1:
        return 0.0
    return _smoothstep(1.12, 1.55, driven / reference)


def _default_gain_value(key: str) -> int:
    return {
        "wheelspin_buzz": 2,
        "throttle_pressure": 0,
        "throttle_traction": 0,
        "accel_g_punch": 3,
        "rpm_rev_limit": 8,
    }.get(key, 5)


def _detail_0_10(details: dict, key: str, default: int) -> int:
    try:
        return max(0, min(10, int(round(float(details.get(key, default))))))
    except (TypeError, ValueError):
        return default


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 >= edge1:
        return 1.0 if value >= edge1 else 0.0
    x = _clamp((value - edge0) / (edge1 - edge0), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))
