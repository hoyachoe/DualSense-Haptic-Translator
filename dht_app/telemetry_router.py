from __future__ import annotations

import struct
from dataclasses import dataclass

from .app_state import GameMode
from .telemetry_frame import TelemetryFrame, empty_telemetry_frame

FORZA_HORIZON_PACKET_SIZE = 324
FORZA_MOTORSPORT_SLED_PACKET_SIZE = 232
FORZA_MOTORSPORT_DASH_PACKET_SIZE = 331
FORZA_MOTORSPORT_DASH_PADDED_PACKET_SIZE = 332


@dataclass(frozen=True)
class TelemetryRouteResult:
    game_mode: GameMode
    parser_name: str
    packet_size: int
    frame: TelemetryFrame
    parsed: bool = False
    details: str = ""


def route_telemetry_packet(game_mode: GameMode, packet: bytes) -> TelemetryRouteResult:
    if game_mode == GameMode.MOTORSPORT:
        return route_motorsport_packet(packet)
    return route_horizon_packet(packet)


def _float(packet: bytes, offset: int) -> float:
    return struct.unpack_from("<f", packet, offset)[0]


def _int(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<i", packet, offset)[0]


def _uint(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<I", packet, offset)[0]


def _sbyte(packet: bytes, offset: int) -> int:
    return struct.unpack_from("<b", packet, offset)[0]


def _common_frame_fields(packet: bytes) -> dict[str, float | int | bool]:
    return {
        "is_race_on": _int(packet, 0) != 0,
        "max_rpm": _float(packet, 8),
        "idle_rpm": _float(packet, 12),
        "rpm": _float(packet, 16),
    }


def _parsed_frame(
    *,
    game_mode: GameMode,
    parser_name: str,
    packet: bytes,
    speed_offset: int,
    power_offset: int,
    torque_offset: int,
    boost_offset: int,
    tire_temp_fl_offset: int,
    tire_temp_fr_offset: int,
    tire_temp_rl_offset: int,
    tire_temp_rr_offset: int,
    smashable_vel_diff_offset: int | None,
    smashable_mass_offset: int | None,
    throttle_offset: int,
    brake_offset: int,
    clutch_offset: int,
    handbrake_offset: int,
    gear_offset: int,
    steer_offset: int,
    source_note: str,
) -> TelemetryFrame:
    fields = _common_frame_fields(packet)
    return TelemetryFrame(
        game_mode=game_mode,
        parser_name=parser_name,
        packet_size=len(packet),
        parsed=True,
        is_race_on=bool(fields["is_race_on"]),
        max_rpm=float(fields["max_rpm"]),
        idle_rpm=float(fields["idle_rpm"]),
        rpm=float(fields["rpm"]),
        accel_x=_float(packet, 20),
        accel_y=_float(packet, 24),
        accel_z=_float(packet, 28),
        velocity_x=_float(packet, 32),
        velocity_y=_float(packet, 36),
        velocity_z=_float(packet, 40),
        angular_velocity_y=_float(packet, 48),
        norm_suspension_travel_fl=_float(packet, 68),
        norm_suspension_travel_fr=_float(packet, 72),
        norm_suspension_travel_rl=_float(packet, 76),
        norm_suspension_travel_rr=_float(packet, 80),
        wheel_rotation_speed_fl=_float(packet, 100),
        wheel_rotation_speed_fr=_float(packet, 104),
        wheel_rotation_speed_rl=_float(packet, 108),
        wheel_rotation_speed_rr=_float(packet, 112),
        speed=_float(packet, speed_offset) * 3.6,
        power=_float(packet, power_offset),
        torque=_float(packet, torque_offset),
        boost=_float(packet, boost_offset),
        smashable_vel_diff=_float(packet, smashable_vel_diff_offset) if smashable_vel_diff_offset is not None else 0.0,
        smashable_mass=_float(packet, smashable_mass_offset) if smashable_mass_offset is not None else 0.0,
        throttle=float(packet[throttle_offset]),
        brake=float(packet[brake_offset]),
        clutch=float(packet[clutch_offset]),
        handbrake=float(packet[handbrake_offset]),
        gear=int(packet[gear_offset]),
        steer=float(_sbyte(packet, steer_offset)),
        wheel_on_rumble_strip_fl=_int(packet, 116),
        wheel_on_rumble_strip_fr=_int(packet, 120),
        wheel_on_rumble_strip_rl=_int(packet, 124),
        wheel_on_rumble_strip_rr=_int(packet, 128),
        surface_rumble_fl=_float(packet, 148),
        surface_rumble_fr=_float(packet, 152),
        surface_rumble_rl=_float(packet, 156),
        surface_rumble_rr=_float(packet, 160),
        tire_slip_ratio_fl=_float(packet, 84),
        tire_slip_ratio_fr=_float(packet, 88),
        tire_slip_ratio_rl=_float(packet, 92),
        tire_slip_ratio_rr=_float(packet, 96),
        tire_slip_angle_fl=_float(packet, 164),
        tire_slip_angle_fr=_float(packet, 168),
        tire_slip_angle_rl=_float(packet, 172),
        tire_slip_angle_rr=_float(packet, 176),
        tire_combined_slip_fl=_float(packet, 180),
        tire_combined_slip_fr=_float(packet, 184),
        tire_combined_slip_rl=_float(packet, 188),
        tire_combined_slip_rr=_float(packet, 192),
        tire_temp_fl=_float(packet, tire_temp_fl_offset),
        tire_temp_fr=_float(packet, tire_temp_fr_offset),
        tire_temp_rl=_float(packet, tire_temp_rl_offset),
        tire_temp_rr=_float(packet, tire_temp_rr_offset),
        car_ordinal=_int(packet, 212),
        car_class=_int(packet, 216),
        car_performance_index=_int(packet, 220),
        drive_train=_int(packet, 224),
        source_note=source_note,
    )


def route_horizon_packet(packet: bytes) -> TelemetryRouteResult:
    parser_name = "Forza Horizon Dash"
    if len(packet) != FORZA_HORIZON_PACKET_SIZE:
        if len(packet) in {FORZA_MOTORSPORT_DASH_PACKET_SIZE, FORZA_MOTORSPORT_DASH_PADDED_PACKET_SIZE}:
            details = "Motorsport Dash packet detected while Horizon is selected."
        elif len(packet) == FORZA_MOTORSPORT_SLED_PACKET_SIZE:
            details = "Motorsport Sled packet detected. Select Motorsport and use Dash format."
        else:
            details = f"Expected Horizon {FORZA_HORIZON_PACKET_SIZE} bytes, got {len(packet)}."
        frame = empty_telemetry_frame(GameMode.HORIZON, parser_name, packet, details)
        return TelemetryRouteResult(
            game_mode=GameMode.HORIZON,
            parser_name=parser_name,
            packet_size=frame.packet_size,
            frame=frame,
            parsed=frame.parsed,
            details=details,
        )

    frame = _parsed_frame(
        game_mode=GameMode.HORIZON,
        parser_name=parser_name,
        packet=packet,
        speed_offset=256,
        power_offset=260,
        torque_offset=264,
        boost_offset=284,
        tire_temp_fl_offset=268,
        tire_temp_fr_offset=272,
        tire_temp_rl_offset=276,
        tire_temp_rr_offset=280,
        smashable_vel_diff_offset=236,
        smashable_mass_offset=240,
        throttle_offset=315,
        brake_offset=316,
        clutch_offset=317,
        handbrake_offset=318,
        gear_offset=319,
        steer_offset=320,
        source_note="Horizon Dash core fields parsed.",
    )
    details = "Horizon parser selected. Core telemetry fields parsed."
    return TelemetryRouteResult(
        game_mode=GameMode.HORIZON,
        parser_name=parser_name,
        packet_size=frame.packet_size,
        frame=frame,
        parsed=frame.parsed,
        details=details,
    )


def route_motorsport_packet(packet: bytes) -> TelemetryRouteResult:
    parser_name = "Forza Motorsport Dash"
    if len(packet) not in {FORZA_MOTORSPORT_DASH_PACKET_SIZE, FORZA_MOTORSPORT_DASH_PADDED_PACKET_SIZE}:
        if len(packet) == FORZA_HORIZON_PACKET_SIZE:
            details = "Horizon-size packet received while Motorsport is selected."
        elif len(packet) == FORZA_MOTORSPORT_SLED_PACKET_SIZE:
            details = "Motorsport Sled packet detected. Set Data Out Packet Format to Dash."
        else:
            details = f"Expected Motorsport Dash {FORZA_MOTORSPORT_DASH_PACKET_SIZE} or {FORZA_MOTORSPORT_DASH_PADDED_PACKET_SIZE} bytes, got {len(packet)}."
        frame = empty_telemetry_frame(GameMode.MOTORSPORT, parser_name, packet, details)
        return TelemetryRouteResult(
            game_mode=GameMode.MOTORSPORT,
            parser_name=parser_name,
            packet_size=frame.packet_size,
            frame=frame,
            parsed=frame.parsed,
            details=details,
        )

    frame = _parsed_frame(
        game_mode=GameMode.MOTORSPORT,
        parser_name=parser_name,
        packet=packet,
        speed_offset=244,
        power_offset=248,
        torque_offset=252,
        boost_offset=272,
        tire_temp_fl_offset=256,
        tire_temp_fr_offset=260,
        tire_temp_rl_offset=264,
        tire_temp_rr_offset=268,
        smashable_vel_diff_offset=None,
        smashable_mass_offset=None,
        throttle_offset=303,
        brake_offset=304,
        clutch_offset=305,
        handbrake_offset=306,
        gear_offset=307,
        steer_offset=308,
        source_note="Motorsport Dash core fields parsed.",
    )
    details = "Motorsport parser selected. Core telemetry fields parsed."
    return TelemetryRouteResult(
        game_mode=GameMode.MOTORSPORT,
        parser_name=parser_name,
        packet_size=frame.packet_size,
        frame=frame,
        parsed=frame.parsed,
        details=details,
    )
