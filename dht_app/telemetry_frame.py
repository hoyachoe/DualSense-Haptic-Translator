from __future__ import annotations

from dataclasses import dataclass

from .app_state import GameMode


@dataclass(frozen=True)
class TelemetryFrame:
    """Normalized telemetry shape shared by game-specific parsers."""

    game_mode: GameMode
    parser_name: str
    packet_size: int
    parsed: bool = False
    is_race_on: bool | None = None
    max_rpm: float | None = None
    idle_rpm: float | None = None
    accel_x: float | None = None
    accel_y: float | None = None
    accel_z: float | None = None
    velocity_x: float | None = None
    velocity_y: float | None = None
    velocity_z: float | None = None
    angular_velocity_y: float | None = None
    norm_suspension_travel_fl: float | None = None
    norm_suspension_travel_fr: float | None = None
    norm_suspension_travel_rl: float | None = None
    norm_suspension_travel_rr: float | None = None
    wheel_rotation_speed_fl: float | None = None
    wheel_rotation_speed_fr: float | None = None
    wheel_rotation_speed_rl: float | None = None
    wheel_rotation_speed_rr: float | None = None
    speed: float | None = None
    rpm: float | None = None
    gear: int | None = None
    throttle: float | None = None
    brake: float | None = None
    clutch: float | None = None
    handbrake: float | None = None
    steer: float | None = None
    wheel_on_rumble_strip_fl: int | None = None
    wheel_on_rumble_strip_fr: int | None = None
    wheel_on_rumble_strip_rl: int | None = None
    wheel_on_rumble_strip_rr: int | None = None
    surface_rumble_fl: float | None = None
    surface_rumble_fr: float | None = None
    surface_rumble_rl: float | None = None
    surface_rumble_rr: float | None = None
    tire_slip_ratio_fl: float | None = None
    tire_slip_ratio_fr: float | None = None
    tire_slip_ratio_rl: float | None = None
    tire_slip_ratio_rr: float | None = None
    tire_slip_angle_fl: float | None = None
    tire_slip_angle_fr: float | None = None
    tire_slip_angle_rl: float | None = None
    tire_slip_angle_rr: float | None = None
    tire_combined_slip_fl: float | None = None
    tire_combined_slip_fr: float | None = None
    tire_combined_slip_rl: float | None = None
    tire_combined_slip_rr: float | None = None
    tire_temp_fl: float | None = None
    tire_temp_fr: float | None = None
    tire_temp_rl: float | None = None
    tire_temp_rr: float | None = None
    boost: float | None = None
    power: float | None = None
    torque: float | None = None
    smashable_vel_diff: float | None = None
    smashable_mass: float | None = None
    car_ordinal: int | None = None
    car_class: int | None = None
    car_performance_index: int | None = None
    drive_train: int | None = None
    drift: float | None = None
    source_note: str = ""


def empty_telemetry_frame(
    game_mode: GameMode,
    parser_name: str,
    packet: bytes,
    source_note: str,
) -> TelemetryFrame:
    return TelemetryFrame(
        game_mode=game_mode,
        parser_name=parser_name,
        packet_size=len(packet),
        parsed=False,
        source_note=source_note,
    )
