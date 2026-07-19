from copy import deepcopy
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import Enum
import math
from time import monotonic
from typing import ClassVar

from .settings_model import (
    HAPTIC_ADVANCED_DEFAULTS,
    HAPTIC_EFFECT_DEFAULTS,
    TRIGGER_ADVANCED_DEFAULTS,
    TRIGGER_EFFECT_DEFAULTS,
    EffectSetting,
    NumericSetting,
    clamp_setting_value,
    make_effect_settings,
    make_numeric_settings,
)


class GameMode(Enum):
    HORIZON = "horizon"
    MOTORSPORT = "motorsport"


class PacketStatus(Enum):
    WAITING = "waiting"
    RECEIVING = "receiving"


class DualSenseStatus(Enum):
    CONNECTED = "connected"
    NOT_SELECTED = "not_selected"
    SERVER_ERROR = "server_error"


TRANSIENT_GEAR_VALUE = 11
DRIFT_SCORE_DECAY_PER_SECOND = 0.28
DRIFT_MODE_ENTER_SCORE = 0.56
DRIFT_MODE_ENTER_HOLD_SECONDS = 0.30
DRIFT_MODE_KEEP_SCORE = 0.50
DRIFT_MODE_RELEASE_SCORE = 0.18
DRIFT_FADE_ENTER_SCORE = 0.70
DRIFT_FADE_RELEASE_SCORE = 0.55
DRIFT_FADE_HOLD_SECONDS = 2.0


PRESET_NAMES = (
    "Base",
    "Soft",
    "Semi-Strong",
    "Strong",
    "User 1",
    "User 2",
)


HUD_NAMES = (
    "Preset",
    "Pedal",
    "G-force",
    "Tire",
    "Steer",
    "Haptic Viz",
    "RPM",
    "Engine",
    "Trigger",
    "Drift",
    "Debug Haptic",
    "Debug Trigger",
)


DEBUG_HUD_NAMES = (
    "Debug Haptic",
    "Debug Trigger",
)


TRIGGER_DEBUG_EFFECT_NAMES = (
    "Brake Pressure",
    "Brake Resistance",
    "Brake Resistance - Predictive",
    "Throttle Pressure",
    "Throttle Resistance - Traction",
    "Acceleration G Punch",
    "RPM Rev Limit",
    "Shift Down Howl",
)


BRAKE_TRIGGER_EFFECT_NAMES = (
    "Brake Pressure",
    "Brake Resistance",
    "Brake Resistance - Predictive",
)


KERB_WAVE_SHARED_DETAIL_MIRRORS = {
    "kerb_l_start_percent": ("kerb_l_start_percent", "kerb_r_start_percent"),
    "kerb_low_hz": ("kerb_low_hz", "kerb_l_low_hz", "kerb_r_low_hz"),
    "kerb_high_hz": ("kerb_high_hz", "kerb_l_high_hz", "kerb_r_high_hz"),
    "kerb_l_low_amp": ("kerb_l_low_amp", "kerb_r_low_amp"),
    "kerb_l_high_amp": ("kerb_l_high_amp", "kerb_r_high_amp"),
}


LEGACY_TELEMETRY_ITEMS = (
    "Speed",
    "RPM",
    "Boost",
    "Torque",
    "Throttle",
    "Brake",
    "Steer",
    "Lateral G",
    "Longitudinal G",
    "Wheel Slip",
    "Drift",
    "Gear",
)

HORIZON_TELEMETRY_ITEMS = (
    "IsRaceOn",
    "TimestampMS",
    "EngineMaxRpm",
    "EngineIdleRpm",
    "CurrentEngineRpm",
    "AccelerationX",
    "AccelerationY",
    "AccelerationZ",
    "VelocityX",
    "VelocityY",
    "VelocityZ",
    "AngularVelocityX",
    "AngularVelocityY",
    "AngularVelocityZ",
    "Yaw",
    "Pitch",
    "Roll",
    "NormalizedSuspensionTravelFrontLeft",
    "NormalizedSuspensionTravelFrontRight",
    "NormalizedSuspensionTravelRearLeft",
    "NormalizedSuspensionTravelRearRight",
    "TireSlipRatioFrontLeft",
    "TireSlipRatioFrontRight",
    "TireSlipRatioRearLeft",
    "TireSlipRatioRearRight",
    "WheelRotationSpeedFrontLeft",
    "WheelRotationSpeedFrontRight",
    "WheelRotationSpeedRearLeft",
    "WheelRotationSpeedRearRight",
    "WheelOnRumbleStripFrontLeft",
    "WheelOnRumbleStripFrontRight",
    "WheelOnRumbleStripRearLeft",
    "WheelOnRumbleStripRearRight",
    "WheelInPuddleFrontLeft",
    "WheelInPuddleFrontRight",
    "WheelInPuddleRearLeft",
    "WheelInPuddleRearRight",
    "SurfaceRumbleFrontLeft",
    "SurfaceRumbleFrontRight",
    "SurfaceRumbleRearLeft",
    "SurfaceRumbleRearRight",
    "TireSlipAngleFrontLeft",
    "TireSlipAngleFrontRight",
    "TireSlipAngleRearLeft",
    "TireSlipAngleRearRight",
    "TireCombinedSlipFrontLeft",
    "TireCombinedSlipFrontRight",
    "TireCombinedSlipRearLeft",
    "TireCombinedSlipRearRight",
    "SuspensionTravelMetersFrontLeft",
    "SuspensionTravelMetersFrontRight",
    "SuspensionTravelMetersRearLeft",
    "SuspensionTravelMetersRearRight",
    "CarOrdinal",
    "CarClass",
    "CarPerformanceIndex",
    "DrivetrainType",
    "NumCylinders",
    "CarGroup",
    "SmashableVelDiff",
    "SmashableMass",
    "PositionX",
    "PositionY",
    "PositionZ",
    "Speed",
    "Power",
    "Torque",
    "TireTempFrontLeft",
    "TireTempFrontRight",
    "TireTempRearLeft",
    "TireTempRearRight",
    "Boost",
    "Fuel",
    "DistanceTraveled",
    "BestLap",
    "LastLap",
    "CurrentLap",
    "CurrentRaceTime",
    "LapNumber",
    "RacePosition",
    "Accel",
    "Brake",
    "Clutch",
    "HandBrake",
    "Gear",
    "Steer",
    "NormalizedDrivingLine",
    "NormalizedAIBrakeDifference",
)


MOTORSPORT_TELEMETRY_ITEMS = (
    "IsRaceOn",
    "TimestampMS",
    "EngineMaxRpm",
    "EngineIdleRpm",
    "CurrentEngineRpm",
    "AccelerationX",
    "AccelerationY",
    "AccelerationZ",
    "VelocityX",
    "VelocityY",
    "VelocityZ",
    "AngularVelocityX",
    "AngularVelocityY",
    "AngularVelocityZ",
    "Yaw",
    "Pitch",
    "Roll",
    "NormalizedSuspensionTravelFrontLeft",
    "NormalizedSuspensionTravelFrontRight",
    "NormalizedSuspensionTravelRearLeft",
    "NormalizedSuspensionTravelRearRight",
    "TireSlipRatioFrontLeft",
    "TireSlipRatioFrontRight",
    "TireSlipRatioRearLeft",
    "TireSlipRatioRearRight",
    "WheelRotationSpeedFrontLeft",
    "WheelRotationSpeedFrontRight",
    "WheelRotationSpeedRearLeft",
    "WheelRotationSpeedRearRight",
    "WheelOnRumbleStripFrontLeft",
    "WheelOnRumbleStripFrontRight",
    "WheelOnRumbleStripRearLeft",
    "WheelOnRumbleStripRearRight",
    "WheelInPuddleDepthFrontLeft",
    "WheelInPuddleDepthFrontRight",
    "WheelInPuddleDepthRearLeft",
    "WheelInPuddleDepthRearRight",
    "SurfaceRumbleFrontLeft",
    "SurfaceRumbleFrontRight",
    "SurfaceRumbleRearLeft",
    "SurfaceRumbleRearRight",
    "TireSlipAngleFrontLeft",
    "TireSlipAngleFrontRight",
    "TireSlipAngleRearLeft",
    "TireSlipAngleRearRight",
    "TireCombinedSlipFrontLeft",
    "TireCombinedSlipFrontRight",
    "TireCombinedSlipRearLeft",
    "TireCombinedSlipRearRight",
    "SuspensionTravelMetersFrontLeft",
    "SuspensionTravelMetersFrontRight",
    "SuspensionTravelMetersRearLeft",
    "SuspensionTravelMetersRearRight",
    "CarOrdinal",
    "CarClass",
    "CarPerformanceIndex",
    "DrivetrainType",
    "NumCylinders",
    "PositionX",
    "PositionY",
    "PositionZ",
    "Speed",
    "Power",
    "Torque",
    "TireTempFrontLeft",
    "TireTempFrontRight",
    "TireTempRearLeft",
    "TireTempRearRight",
    "Boost",
    "Fuel",
    "DistanceTraveled",
    "BestLap",
    "LastLap",
    "CurrentLap",
    "CurrentRaceTime",
    "LapNumber",
    "RacePosition",
    "Accel",
    "Brake",
    "Clutch",
    "HandBrake",
    "Gear",
    "Steer",
    "NormalizedDrivingLine",
    "NormalizedAIBrakeDifference",
    "TireWearFrontLeft",
    "TireWearFrontRight",
    "TireWearRearLeft",
    "TireWearRearRight",
    "TrackOrdinal",
)


TELEMETRY_ITEMS = tuple(
    dict.fromkeys(
        (
            *HORIZON_TELEMETRY_ITEMS,
            *MOTORSPORT_TELEMETRY_ITEMS,
            *LEGACY_TELEMETRY_ITEMS,
            "Boost / Torque",
            "Drift / Slip",
            "G-force",
            "Tire",
        )
    )
)


def telemetry_items_for_game(game_mode: GameMode) -> tuple[str, ...]:
    if game_mode == GameMode.MOTORSPORT:
        return MOTORSPORT_TELEMETRY_ITEMS
    return HORIZON_TELEMETRY_ITEMS


TELEMETRY_NAME_ALIASES = {
    "rpm": "CurrentEngineRpm",
    "throttle": "Accel",
    "handbrake": "HandBrake",
    "g-force": "G-force",
    "g force": "G-force",
    "wheel slip": "Wheel Slip",
    "tire": "Wheel Slip",
    "drift": "Drift",
}


def canonical_telemetry_name(name: str) -> str:
    return TELEMETRY_NAME_ALIASES.get(name.strip().lower(), name.strip())


TELEMETRY_COLORS = (
    "accent_2",
    "cyan",
    "green",
    "accent",
)


HAPTIC_DEBUG_EFFECT_NAMES = tuple(name for name, _value, _enabled in HAPTIC_EFFECT_DEFAULTS)
OUTPUT_CARD_INDEX = 3
OUTPUT_ITEM_HAPTIC_PREFIX = "Haptic: "
OUTPUT_ITEM_TRIGGER_PREFIX = "Trigger: "


def haptic_output_item_name(name: str) -> str:
    return f"{OUTPUT_ITEM_HAPTIC_PREFIX}{name}"


def trigger_output_item_name(name: str) -> str:
    return f"{OUTPUT_ITEM_TRIGGER_PREFIX}{name}"


def output_graph_items() -> tuple[str, ...]:
    return tuple(
        [haptic_output_item_name(name) for name in HAPTIC_DEBUG_EFFECT_NAMES]
        + [trigger_output_item_name(name) for name in TRIGGER_DEBUG_EFFECT_NAMES]
    )


def default_output_graph_item() -> str:
    return haptic_output_item_name("Tire Limit Load")


def is_output_graph_item(name: str) -> bool:
    return name in output_graph_items()


def output_graph_item_parts(name: str) -> tuple[str, str] | None:
    if name.startswith(OUTPUT_ITEM_HAPTIC_PREFIX):
        return "haptic", name[len(OUTPUT_ITEM_HAPTIC_PREFIX):]
    if name.startswith(OUTPUT_ITEM_TRIGGER_PREFIX):
        return "trigger", name[len(OUTPUT_ITEM_TRIGGER_PREFIX):]
    return None


MAIN_UI_LANGUAGES = ("EN", "ES")
TOOLTIP_LANGUAGES = ("EN", "KR", "CN", "ES")


@dataclass
class FooterStatus:
    primary: str = "DualSense L2  0.0% ( 0)   R2  0.0% ( 0)     drift 0.00     pred --"
    message: str = "Waiting for Forza UDP packets. Check Forza Data Out IP/port and Windows Firewall."
    details: str = "Packets: 0   Haptic events: 0   Window: 12s   Haptic server: ready"


@dataclass
class OptionState:
    main_ui_language: str = "EN"
    tooltip_language: str = "EN"
    main_ui_scale: int = 100
    haptic_low_boost_gain: int = 0
    preset_shortcut_enabled: bool = True
    preset_shortcut_combo: str = "R1+R3"
    preset_shortcut_pending_combo: str = "R1+R3"
    preset_shortcut_capture_active: bool = False
    preset_shortcut_return_preset: str = "Base"
    telemetry_relay_enabled: bool = False
    telemetry_relay_host: str = "127.0.0.1"
    telemetry_relay_port: int = 9000
    dsx_bridge_enabled: bool = False
    dsx_host: str = "127.0.0.1"
    dsx_port: int = 6969
    dsx_audio_export_enabled: bool = False
    dsx_audio_device: str = ""
    dsx_audio_volume: int = 100


@dataclass
class WindowState:
    x: int | None = None
    y: int | None = None
    width: int = 836
    height: int = 640


@dataclass
class HudItemState:
    enabled: bool = True
    scale: int = 100
    opacity: int = 100
    x: int | None = None
    y: int | None = None


@dataclass
class HudState:
    standby_hide: bool = False
    snap_enabled: bool = True
    snap_pixel: int = 10
    speed_unit: str = "km/h"
    power_unit: str = "PS"
    boost_unit: str = "bar"
    rpm_style: str = "Digital Bar"
    items: dict[str, HudItemState] = field(
        default_factory=lambda: {
            name: HudItemState(enabled=False, scale=100)
            for name in HUD_NAMES
        }
    )


@dataclass
class TriggerDebugSpec:
    force: float = 0.0
    wall_start: float = 0.0
    wall_end: float = 100.0
    pulse_amp: float = 0.0
    pulse_rate: float = 0.0
    pulse_start: float = 0.0
    vibrate_amp: float = 0.0
    vibrate_freq: float = 0.0
    vibrate_start: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> "TriggerDebugSpec":
        return cls(
            force=float(values.get("force", 0.0)),
            wall_start=float(values.get("wall_start", 0.0)),
            wall_end=float(values.get("wall_end", 100.0)),
            pulse_amp=float(values.get("pulse_amp", 0.0)),
            pulse_rate=float(values.get("pulse_rate", 0.0)),
            pulse_start=float(values.get("pulse_start", 0.0)),
            vibrate_amp=float(values.get("vibrate_amp", 0.0)),
            vibrate_freq=float(values.get("vibrate_freq", 0.0)),
            vibrate_start=float(values.get("vibrate_start", 0.0)),
            updated_at=float(values.get("updated_at", 0.0)),
        )


@dataclass
class TriggerDebugState:
    specs: dict[str, TriggerDebugSpec] = field(
        default_factory=lambda: {
            name: TriggerDebugSpec() for name in TRIGGER_DEBUG_EFFECT_NAMES
        }
    )
    last_updated_at: float = 0.0

    def update_specs(self, specs: Mapping[str, Mapping[str, float]]) -> None:
        updated_at = 0.0
        next_specs = {
            name: TriggerDebugSpec() for name in TRIGGER_DEBUG_EFFECT_NAMES
        }
        for name in TRIGGER_DEBUG_EFFECT_NAMES:
            if name not in specs:
                continue
            next_specs[name] = TriggerDebugSpec.from_mapping(specs[name])
            updated_at = max(updated_at, next_specs[name].updated_at)
        self.specs = next_specs
        self.last_updated_at = updated_at


@dataclass
class HapticDebugSpec:
    level: float = 0.0
    left: float = 0.0
    right: float = 0.0
    frequency: float = 0.0
    updated_at: float = 0.0

    @classmethod
    def from_mapping(cls, values: Mapping[str, float]) -> "HapticDebugSpec":
        return cls(
            level=float(values.get("level", 0.0)),
            left=float(values.get("left", 0.0)),
            right=float(values.get("right", 0.0)),
            frequency=float(values.get("frequency", 0.0)),
            updated_at=float(values.get("updated_at", 0.0)),
        )


@dataclass
class HapticDebugState:
    specs: dict[str, HapticDebugSpec] = field(
        default_factory=lambda: {
            name: HapticDebugSpec() for name in HAPTIC_DEBUG_EFFECT_NAMES
        }
    )
    last_updated_at: float = 0.0

    def update_specs(self, specs: Mapping[str, Mapping[str, float]]) -> None:
        updated_at = 0.0
        next_specs = {
            name: HapticDebugSpec() for name in HAPTIC_DEBUG_EFFECT_NAMES
        }
        for name in HAPTIC_DEBUG_EFFECT_NAMES:
            if name not in specs:
                continue
            next_specs[name] = HapticDebugSpec.from_mapping(specs[name])
            updated_at = max(updated_at, next_specs[name].updated_at)
        self.specs = next_specs
        self.last_updated_at = updated_at


@dataclass
class DualSenseDeviceState:
    candidates: list[str] = field(default_factory=list)
    registered_candidates: list[str] = field(default_factory=list)
    highlighted_device: str = ""
    selected_device: str = ""
    last_test_result: str = "Not tested in this session"
    refresh_attempted: bool = False
    left_trigger_percent: float = 0.0
    right_trigger_percent: float = 0.0
    last_input_at: float = 0.0


@dataclass
class SoundToHapticState:
    enabled: bool = False
    running: bool = False
    capture_device: str = ""
    highlighted_capture_device: str = ""
    capture_candidates: list[str] = field(default_factory=list)
    refresh_attempted: bool = False
    master_gain: int = 70
    low_volume_cut: int = 4
    high_cut_hz: int = 0
    dynamic_boost: int = 100
    settings_dirty: bool = False
    last_result: str = "Sound to Haptic is off."


@dataclass
class TelemetryCardState:
    name: str
    pattern: int
    color_key: str


@dataclass
class DriftHudState:
    active: bool = False
    fade_active: bool = False
    score: float = 0.0
    score_last_update: float = 0.0
    candidate_since: float = 0.0
    hold_until: float = 0.0
    fade_high_score_since: float = 0.0
    oversteer_component: float = 0.0
    components: dict[str, float] = field(
        default_factory=lambda: {
            "over": 0.0,
            "angle": 0.0,
            "drive": 0.0,
            "wheel": 0.0,
            "grip": 0.0,
        }
    )

    def reset(self) -> None:
        self.active = False
        self.fade_active = False
        self.score = 0.0
        self.score_last_update = 0.0
        self.candidate_since = 0.0
        self.hold_until = 0.0
        self.fade_high_score_since = 0.0
        self.oversteer_component = 0.0
        for key in self.components:
            self.components[key] = 0.0


@dataclass
class TelemetryState:
    HUD_GARAGE_CONFIRM_PACKETS: ClassVar[int] = 12
    HISTORY_LIMIT: int = 144
    cards: list[TelemetryCardState] = field(
        default_factory=lambda: [
            TelemetryCardState("RPM", 0, "accent_2"),
            TelemetryCardState("Speed", 1, "cyan"),
            TelemetryCardState("Boost / Torque", 2, "green"),
            TelemetryCardState(default_output_graph_item(), 3, "accent"),
        ]
    )
    packet_count: int = 0
    last_parser_name: str = ""
    last_packet_size: int = 0
    last_parsed: bool = False
    last_is_race_on: bool | None = None
    last_speed: float | None = None
    last_rpm: float | None = None
    last_max_rpm: float | None = None
    last_idle_rpm: float | None = None
    last_gear: int | None = None
    last_throttle: float | None = None
    last_brake: float | None = None
    last_clutch: float | None = None
    last_handbrake: float | None = None
    last_boost: float | None = None
    last_power: float | None = None
    last_torque: float | None = None
    last_steer: float | None = None
    last_drift: float | None = None
    last_accel_x: float | None = None
    last_accel_y: float | None = None
    last_accel_z: float | None = None
    last_velocity_x: float | None = None
    last_velocity_y: float | None = None
    last_velocity_z: float | None = None
    last_angular_velocity_y: float | None = None
    last_norm_suspension_travel_fl: float | None = None
    last_norm_suspension_travel_fr: float | None = None
    last_norm_suspension_travel_rl: float | None = None
    last_norm_suspension_travel_rr: float | None = None
    last_wheel_rotation_speed_fl: float | None = None
    last_wheel_rotation_speed_fr: float | None = None
    last_wheel_rotation_speed_rl: float | None = None
    last_wheel_rotation_speed_rr: float | None = None
    last_wheel_on_rumble_strip_fl: int | None = None
    last_wheel_on_rumble_strip_fr: int | None = None
    last_wheel_on_rumble_strip_rl: int | None = None
    last_wheel_on_rumble_strip_rr: int | None = None
    last_surface_rumble_fl: float | None = None
    last_surface_rumble_fr: float | None = None
    last_surface_rumble_rl: float | None = None
    last_surface_rumble_rr: float | None = None
    last_tire_slip_ratio_fl: float | None = None
    last_tire_slip_ratio_fr: float | None = None
    last_tire_slip_ratio_rl: float | None = None
    last_tire_slip_ratio_rr: float | None = None
    last_tire_slip_angle_fl: float | None = None
    last_tire_slip_angle_fr: float | None = None
    last_tire_slip_angle_rl: float | None = None
    last_tire_slip_angle_rr: float | None = None
    last_tire_combined_slip_fl: float | None = None
    last_tire_combined_slip_fr: float | None = None
    last_tire_combined_slip_rl: float | None = None
    last_tire_combined_slip_rr: float | None = None
    last_tire_temp_fl: float | None = None
    last_tire_temp_fr: float | None = None
    last_tire_temp_rl: float | None = None
    last_tire_temp_rr: float | None = None
    last_car_ordinal: int | None = None
    last_car_class: int | None = None
    last_drive_train: int | None = None
    last_smashable_vel_diff: float | None = None
    last_smashable_mass: float | None = None
    last_note: str = "No telemetry frame received yet."
    histories: dict[str, list[float]] = field(default_factory=dict)
    output_histories: dict[str, list[float]] = field(default_factory=dict)
    steer_hud_last_sign: int = 0
    steer_hud_last_sign_changed_at: float = 0.0
    steer_hud_pending_sign: int = 0
    steer_hud_pending_count: int = 0
    steer_hud_stable_balance: float = 0.0
    _steer_balance_cache_packet: int = -1
    _steer_balance_cache: tuple[float, float] = (0.0, 0.0)
    rpm_hud_display_rpm: float | None = None
    rpm_hud_zero_dropouts: int = 0
    rpm_hud_peak_guide_car_ordinal: int = 0
    rpm_hud_peak_guide_rpm: float = 0.0
    rpm_hud_previous_car_ordinal: int = 0
    rpm_hud_previous_gear: int | None = None
    rpm_hud_previous_rpm: float = 0.0
    hud_garage_candidate_packets: int = 0
    engine_hud_boost_peak_by_car: dict[int, float] = field(default_factory=dict)
    engine_hud_boost_display_by_car: dict[int, float] = field(default_factory=dict)
    engine_hud_power_peak_by_car: dict[int, float] = field(default_factory=dict)
    engine_hud_power_display_by_car: dict[int, float] = field(default_factory=dict)
    drift_hud: DriftHudState = field(default_factory=DriftHudState)

    @property
    def latest_summary(self) -> str:
        if not self.last_parser_name:
            return self.last_note
        if not self.last_parsed:
            return f"{self.last_parser_name}: {self.last_note}"
        speed = "--" if self.last_speed is None else f"{self.last_speed:.1f} km/h"
        rpm = "--" if self.last_rpm is None else f"{self.last_rpm:.0f}"
        max_rpm = "--" if self.last_max_rpm is None else f"{self.last_max_rpm:.0f}"
        gear = "--" if self.last_gear is None else str(self.last_gear)
        throttle = "--" if self.last_throttle is None else f"{self.last_throttle:.0f}"
        brake = "--" if self.last_brake is None else f"{self.last_brake:.0f}"
        return (
            f"{self.last_parser_name}: {speed}, rpm {rpm}/{max_rpm}, "
            f"gear {gear}, throttle {throttle}, brake {brake}"
        )

    @staticmethod
    def _finite_magnitude_within(value: float | None, limit: float) -> bool:
        try:
            number = float(value)
        except (TypeError, ValueError):
            return False
        return math.isfinite(number) and abs(number) <= limit

    def _looks_like_horizon_garage_standby(self) -> bool:
        """Identify Horizon garage packets without treating a driving handbrake as standby."""
        if (
            self.last_parser_name != "Forza Horizon Dash"
            or not self.last_parsed
            or not bool(self.last_is_race_on)
            or not self._finite_magnitude_within(self.last_speed, 0.5)
        ):
            return False

        try:
            handbrake = float(self.last_handbrake)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(handbrake) or handbrake < 254.0:
            return False

        # Horizon keeps IsRaceOn and the loaded car active in the garage. Captured
        # garage packets instead have a full game-applied handbrake, no wheel
        # motion, and no surface simulation. Requiring the complete signature
        # avoids hiding during ordinary e-brake turns or while the car is moving.
        wheel_speeds = (
            self.last_wheel_rotation_speed_fl,
            self.last_wheel_rotation_speed_fr,
            self.last_wheel_rotation_speed_rl,
            self.last_wheel_rotation_speed_rr,
        )
        surface_rumble = (
            self.last_surface_rumble_fl,
            self.last_surface_rumble_fr,
            self.last_surface_rumble_rl,
            self.last_surface_rumble_rr,
        )
        return all(
            self._finite_magnitude_within(value, 0.05) for value in wheel_speeds
        ) and all(
            self._finite_magnitude_within(value, 0.001) for value in surface_rumble
        )

    def _update_hud_garage_standby_state(self) -> None:
        if self._looks_like_horizon_garage_standby():
            self.hud_garage_candidate_packets = min(
                self.HUD_GARAGE_CONFIRM_PACKETS,
                self.hud_garage_candidate_packets + 1,
            )
        else:
            self.hud_garage_candidate_packets = 0

    def has_active_hud_telemetry(self) -> bool:
        try:
            max_rpm = float(self.last_max_rpm or 0.0)
        except (TypeError, ValueError):
            max_rpm = 0.0
        return (
            self.last_parsed
            and bool(self.last_is_race_on)
            and math.isfinite(max_rpm)
            and max_rpm > 0.0
            and self.hud_garage_candidate_packets < self.HUD_GARAGE_CONFIRM_PACKETS
        )

    def record_frame(self, frame) -> None:
        self.packet_count += 1
        self.last_parser_name = frame.parser_name
        self.last_packet_size = int(frame.packet_size)
        self.last_parsed = bool(frame.parsed)
        self.last_is_race_on = frame.is_race_on
        self.last_speed = frame.speed
        self.last_rpm = frame.rpm
        self.last_max_rpm = frame.max_rpm
        self.last_idle_rpm = frame.idle_rpm
        self.last_gear = frame.gear
        self.last_throttle = frame.throttle
        self.last_brake = frame.brake
        self.last_clutch = frame.clutch
        self.last_handbrake = frame.handbrake
        self.last_boost = frame.boost
        self.last_power = frame.power
        self.last_torque = frame.torque
        self.last_steer = frame.steer
        self.last_drift = frame.drift
        self.last_accel_x = frame.accel_x
        self.last_accel_y = frame.accel_y
        self.last_accel_z = frame.accel_z
        self.last_velocity_x = frame.velocity_x
        self.last_velocity_y = frame.velocity_y
        self.last_velocity_z = frame.velocity_z
        self.last_angular_velocity_y = frame.angular_velocity_y
        self.last_norm_suspension_travel_fl = frame.norm_suspension_travel_fl
        self.last_norm_suspension_travel_fr = frame.norm_suspension_travel_fr
        self.last_norm_suspension_travel_rl = frame.norm_suspension_travel_rl
        self.last_norm_suspension_travel_rr = frame.norm_suspension_travel_rr
        self.last_wheel_rotation_speed_fl = frame.wheel_rotation_speed_fl
        self.last_wheel_rotation_speed_fr = frame.wheel_rotation_speed_fr
        self.last_wheel_rotation_speed_rl = frame.wheel_rotation_speed_rl
        self.last_wheel_rotation_speed_rr = frame.wheel_rotation_speed_rr
        self.last_wheel_on_rumble_strip_fl = frame.wheel_on_rumble_strip_fl
        self.last_wheel_on_rumble_strip_fr = frame.wheel_on_rumble_strip_fr
        self.last_wheel_on_rumble_strip_rl = frame.wheel_on_rumble_strip_rl
        self.last_wheel_on_rumble_strip_rr = frame.wheel_on_rumble_strip_rr
        self.last_surface_rumble_fl = frame.surface_rumble_fl
        self.last_surface_rumble_fr = frame.surface_rumble_fr
        self.last_surface_rumble_rl = frame.surface_rumble_rl
        self.last_surface_rumble_rr = frame.surface_rumble_rr
        self.last_tire_slip_ratio_fl = frame.tire_slip_ratio_fl
        self.last_tire_slip_ratio_fr = frame.tire_slip_ratio_fr
        self.last_tire_slip_ratio_rl = frame.tire_slip_ratio_rl
        self.last_tire_slip_ratio_rr = frame.tire_slip_ratio_rr
        self.last_tire_slip_angle_fl = frame.tire_slip_angle_fl
        self.last_tire_slip_angle_fr = frame.tire_slip_angle_fr
        self.last_tire_slip_angle_rl = frame.tire_slip_angle_rl
        self.last_tire_slip_angle_rr = frame.tire_slip_angle_rr
        self.last_tire_combined_slip_fl = frame.tire_combined_slip_fl
        self.last_tire_combined_slip_fr = frame.tire_combined_slip_fr
        self.last_tire_combined_slip_rl = frame.tire_combined_slip_rl
        self.last_tire_combined_slip_rr = frame.tire_combined_slip_rr
        self.last_tire_temp_fl = frame.tire_temp_fl
        self.last_tire_temp_fr = frame.tire_temp_fr
        self.last_tire_temp_rl = frame.tire_temp_rl
        self.last_tire_temp_rr = frame.tire_temp_rr
        self.last_car_ordinal = frame.car_ordinal
        self.last_car_class = frame.car_class
        self.last_drive_train = frame.drive_train
        self.last_smashable_vel_diff = frame.smashable_vel_diff
        self.last_smashable_mass = frame.smashable_mass
        self.last_note = frame.source_note
        self._update_hud_garage_standby_state()
        if self.last_parsed:
            self._record_rpm_hud_shift_guide()
            self.update_drift_hud_state(monotonic())
            self._record_history_samples()
        else:
            self.drift_hud.reset()

    @staticmethod
    def _format_value(value: float | int | None, suffix: str = "", decimals: int = 0) -> str:
        if value is None:
            return "--"
        if decimals <= 0:
            return f"{value:.0f}{suffix}"
        return f"{value:.{decimals}f}{suffix}"

    def raw_telemetry_value_for(self, telemetry_name: str) -> float | int | bool | None:
        key = canonical_telemetry_name(telemetry_name)
        values = {
            "IsRaceOn": None if self.last_is_race_on is None else int(bool(self.last_is_race_on)),
            "EngineMaxRpm": self.last_max_rpm,
            "EngineIdleRpm": self.last_idle_rpm,
            "CurrentEngineRpm": self.last_rpm,
            "AccelerationX": self.last_accel_x,
            "AccelerationY": self.last_accel_y,
            "AccelerationZ": self.last_accel_z,
            "VelocityX": self.last_velocity_x,
            "VelocityY": self.last_velocity_y,
            "VelocityZ": self.last_velocity_z,
            "AngularVelocityY": self.last_angular_velocity_y,
            "NormalizedSuspensionTravelFrontLeft": self.last_norm_suspension_travel_fl,
            "NormalizedSuspensionTravelFrontRight": self.last_norm_suspension_travel_fr,
            "NormalizedSuspensionTravelRearLeft": self.last_norm_suspension_travel_rl,
            "NormalizedSuspensionTravelRearRight": self.last_norm_suspension_travel_rr,
            "WheelRotationSpeedFrontLeft": self.last_wheel_rotation_speed_fl,
            "WheelRotationSpeedFrontRight": self.last_wheel_rotation_speed_fr,
            "WheelRotationSpeedRearLeft": self.last_wheel_rotation_speed_rl,
            "WheelRotationSpeedRearRight": self.last_wheel_rotation_speed_rr,
            "TireSlipRatioFrontLeft": self.last_tire_slip_ratio_fl,
            "TireSlipRatioFrontRight": self.last_tire_slip_ratio_fr,
            "TireSlipRatioRearLeft": self.last_tire_slip_ratio_rl,
            "TireSlipRatioRearRight": self.last_tire_slip_ratio_rr,
            "WheelOnRumbleStripFrontLeft": self.last_wheel_on_rumble_strip_fl,
            "WheelOnRumbleStripFrontRight": self.last_wheel_on_rumble_strip_fr,
            "WheelOnRumbleStripRearLeft": self.last_wheel_on_rumble_strip_rl,
            "WheelOnRumbleStripRearRight": self.last_wheel_on_rumble_strip_rr,
            "SurfaceRumbleFrontLeft": self.last_surface_rumble_fl,
            "SurfaceRumbleFrontRight": self.last_surface_rumble_fr,
            "SurfaceRumbleRearLeft": self.last_surface_rumble_rl,
            "SurfaceRumbleRearRight": self.last_surface_rumble_rr,
            "TireSlipAngleFrontLeft": self.last_tire_slip_angle_fl,
            "TireSlipAngleFrontRight": self.last_tire_slip_angle_fr,
            "TireSlipAngleRearLeft": self.last_tire_slip_angle_rl,
            "TireSlipAngleRearRight": self.last_tire_slip_angle_rr,
            "TireCombinedSlipFrontLeft": self.last_tire_combined_slip_fl,
            "TireCombinedSlipFrontRight": self.last_tire_combined_slip_fr,
            "TireCombinedSlipRearLeft": self.last_tire_combined_slip_rl,
            "TireCombinedSlipRearRight": self.last_tire_combined_slip_rr,
            "CarOrdinal": self.last_car_ordinal,
            "CarClass": self.last_car_class,
            "DrivetrainType": self.last_drive_train,
            "SmashableVelDiff": self.last_smashable_vel_diff,
            "SmashableMass": self.last_smashable_mass,
            "Speed": self.last_speed,
            "Power": self.last_power,
            "Torque": self.last_torque,
            "TireTempFrontLeft": self.last_tire_temp_fl,
            "TireTempFrontRight": self.last_tire_temp_fr,
            "TireTempRearLeft": self.last_tire_temp_rl,
            "TireTempRearRight": self.last_tire_temp_rr,
            "Boost": self.last_boost,
            "Accel": self.last_throttle,
            "Brake": self.last_brake,
            "Clutch": self.last_clutch,
            "HandBrake": self.last_handbrake,
            "Gear": self.last_gear,
            "Steer": self.last_steer,
            "Drift": self.last_drift,
        }
        return values.get(key)

    def display_value_for(self, telemetry_name: str) -> str:
        if not self.last_parsed:
            return "--"

        key = canonical_telemetry_name(telemetry_name)
        if key == "Boost / Torque":
            boost = self._format_value(self.last_boost, " bar", 2)
            torque = self._format_value(self.last_torque, " Nm")
            return f"{boost} / {torque}"
        if key == "G-force":
            lateral_g, longitudinal_g = self.g_force_values()
            return f"{lateral_g:+.2f} / {longitudinal_g:+.2f} g"
        if key in {"Wheel Slip", "Drift / Slip"}:
            return f"{max(self.tire_slip_levels()) * 100.0:.0f}%"

        value = self.raw_telemetry_value_for(key)
        if value is None:
            return "--"
        if key == "CurrentEngineRpm":
            rpm = self._format_value(self.last_rpm)
            max_rpm = self._format_value(self.last_max_rpm)
            return f"{rpm}/{max_rpm}"
        if key == "Speed":
            return self._format_value(float(value), " km/h", 1)
        if key == "Boost":
            return self._format_value(float(value), " bar", 2)
        if key == "Torque":
            return self._format_value(float(value), " Nm")
        if key in {"Accel", "Brake", "Clutch", "HandBrake"}:
            return self._format_value(float(value), "")
        if key == "Steer":
            return self._format_value(float(value), "")
        if key in {"IsRaceOn", "Gear", "CarOrdinal", "CarClass", "DrivetrainType"}:
            return str(int(value))
        return self._format_value(float(value), "", 2)

    @staticmethod
    def _clamp_graph_value(value: float | None) -> float | None:
        if value is None:
            return None
        return max(0.0, min(1.0, float(value)))

    @staticmethod
    def _clamp_signed_graph_value(value: float | None) -> float | None:
        if value is None:
            return None
        return max(-1.0, min(1.0, float(value)))

    def graph_value_for(self, telemetry_name: str) -> float | None:
        if not self.last_parsed:
            return None

        key = canonical_telemetry_name(telemetry_name)
        if key == "Speed":
            return self._clamp_graph_value((self.last_speed or 0.0) / 350.0)
        if key == "CurrentEngineRpm":
            max_rpm = max(float(self.last_max_rpm or 0.0), 1.0)
            return self._clamp_graph_value((self.last_rpm or 0.0) / max_rpm)
        if key == "EngineMaxRpm":
            return self._clamp_graph_value((self.last_max_rpm or 0.0) / 12000.0)
        if key == "EngineIdleRpm":
            return self._clamp_graph_value((self.last_idle_rpm or 0.0) / 3000.0)
        if key == "Boost":
            return self._clamp_signed_graph_value((self.last_boost or 0.0) / 3.0)
        if key == "Power":
            return self._clamp_signed_graph_value((self.last_power or 0.0) / 1_000_000.0)
        if key == "Torque":
            return self._clamp_signed_graph_value((self.last_torque or 0.0) / 1200.0)
        if key == "Boost / Torque":
            boost = self._clamp_graph_value((self.last_boost or 0.0) / 3.0) or 0.0
            torque = self._clamp_graph_value((self.last_torque or 0.0) / 1200.0) or 0.0
            return max(boost, torque)
        if key == "Accel":
            return self._clamp_graph_value((self.last_throttle or 0.0) / 255.0)
        if key == "Brake":
            return self._clamp_graph_value((self.last_brake or 0.0) / 255.0)
        if key == "Clutch":
            return self._clamp_graph_value((self.last_clutch or 0.0) / 255.0)
        if key == "HandBrake":
            return self._clamp_graph_value((self.last_handbrake or 0.0) / 255.0)
        if key == "Steer":
            return self._clamp_signed_graph_value(self.steer_balance_value())
        if key == "Gear":
            return self._clamp_graph_value((self.last_gear or 0) / 10.0)
        if key in {"Drift", "Drift / Slip"}:
            return self._clamp_graph_value(self.last_drift)
        if key == "G-force":
            lateral_g, longitudinal_g = self.g_force_values()
            return self._clamp_signed_graph_value(longitudinal_g / 2.5)
        if key == "Wheel Slip":
            return self._clamp_graph_value(max(self.tire_slip_levels()))
        if key in {"IsRaceOn", "NormalizedSuspensionTravelFrontLeft", "NormalizedSuspensionTravelFrontRight", "NormalizedSuspensionTravelRearLeft", "NormalizedSuspensionTravelRearRight"}:
            return self._clamp_graph_value(self.raw_telemetry_value_for(key))
        if key.startswith("WheelOnRumbleStrip"):
            return self._clamp_graph_value(self.raw_telemetry_value_for(key))
        if key.startswith("SurfaceRumble"):
            return self._clamp_graph_value(abs(float(self.raw_telemetry_value_for(key) or 0.0)))
        if key.startswith("Acceleration"):
            return self._clamp_signed_graph_value(float(self.raw_telemetry_value_for(key) or 0.0) / 20.0)
        if key.startswith("Velocity"):
            return self._clamp_signed_graph_value(float(self.raw_telemetry_value_for(key) or 0.0) / 100.0)
        if key == "AngularVelocityY":
            return self._clamp_signed_graph_value(float(self.last_angular_velocity_y or 0.0) / 5.0)
        if key.startswith("TireSlipRatio") or key.startswith("TireSlipAngle") or key.startswith("TireCombinedSlip"):
            return self._clamp_graph_value(abs(float(self.raw_telemetry_value_for(key) or 0.0)) / 3.0)
        if key.startswith("TireTemp"):
            return self._clamp_graph_value(float(self.raw_telemetry_value_for(key) or 0.0) / 200.0)
        if key == "SmashableVelDiff":
            return self._clamp_graph_value(abs(float(self.last_smashable_vel_diff or 0.0)) / 120.0)
        if key == "SmashableMass":
            return self._clamp_graph_value(float(self.last_smashable_mass or 0.0) / 500.0)
        if key == "CarClass":
            return self._clamp_graph_value(float(self.last_car_class or 0) / 10.0)
        if key == "DrivetrainType":
            return self._clamp_graph_value(float(self.last_drive_train or 0) / 3.0)
        return None

    def g_force_values(self) -> tuple[float, float]:
        lateral_g = -float(self.last_accel_x or 0.0) / 9.80665
        longitudinal_g = -float(self.last_accel_z or 0.0) / 9.80665
        return lateral_g, longitudinal_g

    def stable_rpm_hud_value(self) -> float:
        rpm = max(0.0, float(self.last_rpm or 0.0))
        idle_rpm = max(0.0, float(self.last_idle_rpm or 0.0))
        speed_kmh = max(0.0, float(self.last_speed or 0.0))
        is_on = bool(self.last_is_race_on)
        previous = self.rpm_hud_display_rpm
        if previous is None:
            self.rpm_hud_display_rpm = rpm
            return rpm

        idle_floor = max(450.0, idle_rpm * 0.55)
        if is_on and speed_kmh > 1.0 and rpm <= 100.0 and previous > idle_floor:
            self.rpm_hud_zero_dropouts += 1
            if self.rpm_hud_zero_dropouts <= 2:
                return previous
        else:
            self.rpm_hud_zero_dropouts = 0

        if abs(rpm - previous) > 6000.0:
            smoothed = rpm
        else:
            alpha = 0.45 if rpm > previous else 0.30
            smoothed = previous + (rpm - previous) * alpha
        self.rpm_hud_display_rpm = smoothed
        return smoothed

    def current_rpm_hud_peak_guide(self) -> float:
        car_ordinal = int(self.last_car_ordinal or 0)
        if car_ordinal <= 0:
            return 0.0
        if self.rpm_hud_peak_guide_car_ordinal != car_ordinal:
            self.rpm_hud_peak_guide_car_ordinal = car_ordinal
            self.rpm_hud_peak_guide_rpm = 0.0
        return self.rpm_hud_peak_guide_rpm

    def _record_rpm_hud_shift_guide(self) -> None:
        if not bool(self.last_is_race_on):
            return

        car_ordinal = int(self.last_car_ordinal or 0)
        if car_ordinal <= 0:
            return

        gear_value = self.last_gear
        if gear_value is None:
            return

        gear = int(gear_value)
        if gear == TRANSIENT_GEAR_VALUE:
            return

        if self.rpm_hud_peak_guide_car_ordinal != car_ordinal:
            self.rpm_hud_peak_guide_car_ordinal = car_ordinal
            self.rpm_hud_peak_guide_rpm = 0.0

        if self.rpm_hud_previous_car_ordinal != car_ordinal:
            self.rpm_hud_previous_car_ordinal = car_ordinal
            self.rpm_hud_previous_gear = None
            self.rpm_hud_previous_rpm = 0.0

        previous_gear = self.rpm_hud_previous_gear
        if previous_gear is not None and gear != previous_gear and gear - previous_gear > 0:
            shift_rpm = self.rpm_hud_previous_rpm if self.rpm_hud_previous_rpm > 0.0 else float(self.last_rpm or 0.0)
            self._set_rpm_hud_shift_guide(car_ordinal, shift_rpm)

        self.rpm_hud_previous_gear = gear
        self.rpm_hud_previous_rpm = max(0.0, float(self.last_rpm or 0.0))

    def _set_rpm_hud_shift_guide(self, car_ordinal: int, shift_rpm: float) -> None:
        max_rpm = max(1.0, float(self.last_max_rpm or 0.0))
        if car_ordinal <= 0 or max_rpm <= 1000.0 or shift_rpm <= 0.0:
            return

        adjusted_rpm = min(max_rpm * 0.99, max(0.0, float(shift_rpm)) * 0.99)
        if self.rpm_hud_peak_guide_car_ordinal != car_ordinal:
            self.rpm_hud_peak_guide_car_ordinal = car_ordinal
            self.rpm_hud_peak_guide_rpm = 0.0
        self.rpm_hud_peak_guide_rpm = max(self.rpm_hud_peak_guide_rpm, adjusted_rpm)

    @staticmethod
    def rpm_display_max_rpm(max_rpm: float) -> float:
        if max_rpm <= 1000.0:
            return 1000.0
        return max(1000.0, math.ceil(max_rpm / 1000.0) * 1000.0)

    @staticmethod
    def format_gear_for_hud(gear: int | None) -> str:
        value = int(gear if gear is not None else 0)
        if value == 0:
            return "R"
        if value == 11:
            return "-"
        return str(max(0, value))

    @staticmethod
    def rpm_gear_color(rpm: float, max_rpm: float, idle_rpm: float) -> str:
        ratio = max(0.0, min(1.0, rpm / max(max_rpm, 1.0)))
        low_limit = max(0.22, min(0.36, (idle_rpm / max(max_rpm, 1.0)) + 0.11))
        if ratio >= 0.85:
            return "#f1c40f"
        if ratio <= low_limit:
            return "#2ea8ff"
        return "#eef3f4"

    @staticmethod
    def convert_hud_speed(speed_kmh: float, unit: str) -> float:
        return speed_kmh * 0.621371 if unit == "mph" else speed_kmh

    @staticmethod
    def hud_speed_unit_label(unit: str) -> str:
        return "mph" if unit == "mph" else "km/h"

    @staticmethod
    def boost_display_positive_max(peak: float) -> float:
        if peak <= 0.0:
            return 0.0
        return max(1.0, peak)

    @staticmethod
    def engine_hud_should_show_boost_meter(peak: float, current_boost: float) -> bool:
        return max(peak, current_boost) >= 1.0

    def smoothed_engine_hud_boost(self, boost: float) -> float:
        car_ordinal = int(self.last_car_ordinal or 0)
        key = car_ordinal if car_ordinal > 0 else 0
        previous = self.engine_hud_boost_display_by_car.get(key)
        if previous is None or abs(boost - previous) > 35.0:
            smoothed = boost
        else:
            alpha = 0.35 if abs(boost) > abs(previous) else 0.20
            smoothed = previous + (boost - previous) * alpha
        self.engine_hud_boost_display_by_car[key] = smoothed
        return smoothed

    def smoothed_engine_hud_power(self, power: float) -> float:
        car_ordinal = int(self.last_car_ordinal or 0)
        key = car_ordinal if car_ordinal > 0 else 0
        previous = self.engine_hud_power_display_by_car.get(key)
        if previous is None or abs(power - previous) > 300000.0:
            smoothed = power
        else:
            alpha = 0.35 if abs(power) > abs(previous) else 0.20
            smoothed = previous + (power - previous) * alpha
        self.engine_hud_power_display_by_car[key] = smoothed
        return smoothed

    @staticmethod
    def convert_hud_power(power_watts: float, unit: str) -> float:
        if unit == "kW":
            return power_watts / 1000.0
        if unit == "PS":
            return power_watts / 735.49875
        return power_watts / 745.699872

    @staticmethod
    def hud_power_unit_label(unit: str) -> str:
        if unit == "kW":
            return "kW"
        if unit == "PS":
            return "PS"
        return "hp"

    def format_hud_power_value(self, power_watts: float, unit: str) -> str:
        return f"{self.convert_hud_power(max(0.0, power_watts), unit):.0f}"

    @staticmethod
    def convert_hud_boost(boost_psi: float, unit: str) -> float:
        return boost_psi * 0.0689475729 if unit == "bar" else boost_psi

    @staticmethod
    def hud_boost_unit_label(unit: str) -> str:
        return "bar" if unit == "bar" else "psi"

    def format_hud_boost_value(self, boost_psi: float, unit: str) -> str:
        value = self.convert_hud_boost(boost_psi, unit)
        return f"{value:.1f}" if unit == "bar" else f"{value:.0f}"

    def tire_slip_levels(self) -> tuple[float, float, float, float]:
        values = (
            self._tire_corner_level("fl"),
            self._tire_corner_level("fr"),
            self._tire_corner_level("rl"),
            self._tire_corner_level("rr"),
        )
        return values

    def _tire_corner_level(self, corner: str) -> float:
        ratio = abs(float(getattr(self, f"last_tire_slip_ratio_{corner}") or 0.0))
        angle = abs(float(getattr(self, f"last_tire_slip_angle_{corner}") or 0.0))
        combined = abs(float(getattr(self, f"last_tire_combined_slip_{corner}") or 0.0))
        ratio_level = min(1.0, ratio / 2.0)
        angle_level = min(1.0, angle / 1.35)
        combined_level = min(1.0, combined / 2.2)
        return max(ratio_level, angle_level, combined_level)

    def tire_temperature_f(self, corner: str) -> float:
        return float(getattr(self, f"last_tire_temp_{corner}") or 0.0)

    def recommended_brake_level(self) -> float:
        brake = max(0.0, min(1.0, float(self.last_brake or 0.0) / 255.0))
        speed_kmh = max(0.0, float(self.last_speed or 0.0))
        if brake < 0.03 or speed_kmh < 8.0:
            return brake

        slip_threshold = 1.4
        front_ratio, front_combined = self.brake_slip_values()
        ratio_start = max(0.06, slip_threshold * 0.22)
        ratio_risk = self._smoothstep(ratio_start, slip_threshold, front_ratio)
        combined_risk = self._smoothstep(0.18, max(0.74, slip_threshold * 1.25), front_combined) * 0.85
        decel_g = max(0.0, -float(self.last_accel_z or 0.0) / 9.80665)
        brake_gate = self._smoothstep(8.0, 55.0, brake * 100.0)
        decel_gate = self._smoothstep(0.08, 0.60, decel_g)
        risk = max(ratio_risk, combined_risk) * max(brake_gate, decel_gate * 0.65)
        if risk <= 0.02:
            return brake

        severe_slip = self._smoothstep(slip_threshold, slip_threshold * 1.75, front_ratio) * 0.16
        reduction = max(0.0, min(0.72, risk * 0.46 + severe_slip))
        recommended = brake * (1.0 - reduction)
        if brake - recommended < 0.02:
            return brake
        return max(0.0, min(brake, recommended))

    def recommended_throttle_level(self) -> float:
        throttle = max(0.0, min(1.0, float(self.last_throttle or 0.0) / 255.0))
        speed_kmh = max(0.0, float(self.last_speed or 0.0))
        if throttle < 0.03 or speed_kmh < 4.0:
            return throttle

        slip_threshold = 1.4
        driven_slip, driven_combined = self.throttle_driven_slip_values()
        throttle_gate = self._smoothstep(12.0, 60.0, throttle * 100.0)
        speed_gate = 1.0 - self._smoothstep(210.0, 270.0, speed_kmh)
        ratio_start = max(0.25, slip_threshold * 0.55)
        ratio_risk = self._smoothstep(ratio_start, slip_threshold, driven_slip)
        combined_risk = self._smoothstep(0.35, max(0.75, slip_threshold * 0.85), driven_combined) * 0.55
        risk = max(ratio_risk, combined_risk) * throttle_gate * speed_gate
        if risk <= 0.02:
            return throttle

        severe_slip = self._smoothstep(slip_threshold, slip_threshold * 1.80, driven_slip) * 0.15
        reduction = max(0.0, min(0.70, risk * 0.45 + severe_slip))
        recommended = throttle * (1.0 - reduction)
        if throttle - recommended < 0.02:
            return throttle
        return max(0.0, min(throttle, recommended))

    def brake_slip_values(self) -> tuple[float, float]:
        front_ratio = max(
            0.0,
            abs(float(self.last_tire_slip_ratio_fl or 0.0)),
            abs(float(self.last_tire_slip_ratio_fr or 0.0)),
        )
        front_combined = max(
            0.0,
            abs(float(self.last_tire_combined_slip_fl or 0.0)),
            abs(float(self.last_tire_combined_slip_fr or 0.0)),
        )
        return front_ratio, front_combined

    def throttle_driven_slip_values(self) -> tuple[float, float]:
        drive_train = int(self.last_drive_train if self.last_drive_train is not None else 1)
        if drive_train == 0:
            ratio_values = (self.last_tire_slip_ratio_fl, self.last_tire_slip_ratio_fr)
            combined_values = (self.last_tire_combined_slip_fl, self.last_tire_combined_slip_fr)
        else:
            ratio_values = (self.last_tire_slip_ratio_rl, self.last_tire_slip_ratio_rr)
            combined_values = (self.last_tire_combined_slip_rl, self.last_tire_combined_slip_rr)
        driven_ratio = max(0.0, *(max(0.0, float(value or 0.0)) for value in ratio_values))
        driven_combined = max(0.0, *(abs(float(value or 0.0)) for value in combined_values))
        return driven_ratio, driven_combined

    @staticmethod
    def _smoothstep(edge0: float, edge1: float, value: float) -> float:
        if edge0 >= edge1:
            return 1.0 if value >= edge1 else 0.0
        t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
        return t * t * (3.0 - 2.0 * t)

    def steer_balance_value(self) -> float:
        return self.current_oversteer_balance()[0]

    def current_oversteer_balance(self) -> tuple[float, float]:
        if self._steer_balance_cache_packet == self.packet_count:
            return self._steer_balance_cache
        if not self.last_parsed:
            self._steer_balance_cache_packet = self.packet_count
            self._steer_balance_cache = (0.0, 0.0)
            return self._steer_balance_cache
        raw_balance, grip_loss = self.raw_oversteer_balance()
        balance = self.stabilized_steer_hud_balance(raw_balance, grip_loss)
        self._steer_balance_cache_packet = self.packet_count
        self._steer_balance_cache = (balance, grip_loss)
        return self._steer_balance_cache

    def raw_oversteer_balance(self) -> tuple[float, float]:
        front_angle = (
            abs(float(self.last_tire_slip_angle_fl or 0.0))
            + abs(float(self.last_tire_slip_angle_fr or 0.0))
        ) * 0.5
        rear_angle = (
            abs(float(self.last_tire_slip_angle_rl or 0.0))
            + abs(float(self.last_tire_slip_angle_rr or 0.0))
        ) * 0.5
        diff = rear_angle - front_angle
        speed_kmh = max(0.0, float(self.last_speed or 0.0))
        speed_gate = self._smoothstep(12.0, 62.0, speed_kmh)
        high_speed_gain = 1.0 + 0.22 * self._smoothstep(95.0, 180.0, speed_kmh)
        speed_scale = (0.18 + 0.82 * speed_gate) * high_speed_gain
        magnitude = self._smoothstep(0.04, 0.85, abs(diff)) * speed_scale
        magnitude = max(0.0, min(1.0, magnitude))
        slip_max = max(
            abs(float(self.last_tire_combined_slip_fl or 0.0)),
            abs(float(self.last_tire_combined_slip_fr or 0.0)),
            abs(float(self.last_tire_combined_slip_rl or 0.0)),
            abs(float(self.last_tire_combined_slip_rr or 0.0)),
        )
        throttle = max(0.0, min(1.0, float(self.last_throttle or 0.0) / 255.0))
        brake = max(0.0, min(1.0, float(self.last_brake or 0.0) / 255.0))
        lateral_g = abs(float(self.last_accel_x or 0.0)) / 9.80665
        drive_load = max(throttle, brake)
        coasting_steer = self._smoothstep(0.0, 0.18, 0.18 - drive_load)
        slip_start = 0.95 + 0.38 * coasting_steer
        slip_end = 2.65 + 0.35 * coasting_steer
        grip_loss = self._smoothstep(slip_start, slip_end, slip_max)
        load_gate = max(
            self._smoothstep(0.05, 0.38, drive_load),
            self._smoothstep(0.45, 1.15, lateral_g),
        )
        grip_loss *= 0.35 + 0.65 * load_gate
        if magnitude <= 0.0:
            return 0.0, grip_loss
        raw_balance = magnitude if diff > 0.0 else -magnitude
        return raw_balance, grip_loss

    def stabilized_steer_hud_balance(self, raw_balance: float, grip_loss: float) -> float:
        now = monotonic()
        raw_sign = 1 if raw_balance > 0.025 else -1 if raw_balance < -0.025 else 0
        current_sign = self.steer_hud_last_sign
        high_slip = grip_loss >= 0.38

        if raw_sign == 0:
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance *= 0.72
            if abs(self.steer_hud_stable_balance) < 0.015:
                self.steer_hud_stable_balance = 0.0
                self.steer_hud_last_sign = 0
            return self.steer_hud_stable_balance

        if current_sign == 0 or raw_sign == current_sign:
            self.steer_hud_last_sign = raw_sign
            self.steer_hud_last_sign_changed_at = now if current_sign != raw_sign else self.steer_hud_last_sign_changed_at
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance = self.steer_hud_stable_balance * 0.35 + raw_balance * 0.65
            return self.steer_hud_stable_balance

        if self.steer_hud_pending_sign == raw_sign:
            self.steer_hud_pending_count += 1
        else:
            self.steer_hud_pending_sign = raw_sign
            self.steer_hud_pending_count = 1

        hold_seconds = 0.18 if high_slip else 0.08
        elapsed = now - self.steer_hud_last_sign_changed_at if self.steer_hud_last_sign_changed_at else hold_seconds
        stronger_opposite = abs(raw_balance) >= max(0.18, abs(self.steer_hud_stable_balance) * (1.18 if high_slip else 1.05))
        persistent_opposite = self.steer_hud_pending_count >= (3 if high_slip else 2)
        if elapsed >= hold_seconds and (stronger_opposite or persistent_opposite):
            self.steer_hud_last_sign = raw_sign
            self.steer_hud_last_sign_changed_at = now
            self.steer_hud_pending_sign = 0
            self.steer_hud_pending_count = 0
            self.steer_hud_stable_balance = self.steer_hud_stable_balance * 0.25 + raw_balance * 0.75
        else:
            decay = 0.92 if high_slip else 0.80
            self.steer_hud_stable_balance *= decay
        return self.steer_hud_stable_balance

    def hud_slip_angle_value(self) -> float:
        speed = max(0.0, float(self.last_speed or 0.0))
        if speed < 3.0:
            return 0.0
        tire_slip_angle = (
            float(self.last_tire_slip_angle_fl or 0.0)
            + float(self.last_tire_slip_angle_fr or 0.0)
            + float(self.last_tire_slip_angle_rl or 0.0)
            + float(self.last_tire_slip_angle_rr or 0.0)
        ) * 0.25
        if abs(tire_slip_angle) < 0.025:
            return 0.0
        return -tire_slip_angle

    def hud_slip_angle_degrees(self) -> float:
        return self.hud_slip_angle_value() * 20.0

    def update_drift_hud_state(self, now: float) -> None:
        state = self.drift_hud
        if not self.last_parsed or not bool(self.last_is_race_on):
            state.reset()
            return

        score = self._smoothed_drift_hud_score(now, self.compute_drift_hud_score())
        state.score = score
        if score >= DRIFT_MODE_ENTER_SCORE:
            if state.candidate_since <= 0.0:
                state.candidate_since = now
            if state.active or now - state.candidate_since >= DRIFT_MODE_ENTER_HOLD_SECONDS:
                state.active = True
                state.hold_until = now + 2.20
        elif state.active and score >= DRIFT_MODE_KEEP_SCORE:
            state.hold_until = now + 2.20
        else:
            state.candidate_since = 0.0

        if score <= DRIFT_MODE_RELEASE_SCORE and now >= state.hold_until:
            state.active = False

        self._update_drift_fade_state(now, score)

    def compute_drift_hud_score(self) -> float:
        state = self.drift_hud
        speed_kmh = max(0.0, float(self.last_speed or 0.0))
        speed_gate = self._smoothstep(18.0, 55.0, speed_kmh)
        if speed_gate <= 0.0:
            state.oversteer_component = 0.0
            for key in state.components:
                state.components[key] = 0.0
            return 0.0

        raw_balance, grip_loss = self.raw_oversteer_balance()
        oversteer_gate = self._smoothed_drift_oversteer_component(
            self.drift_oversteer_signal(raw_balance, grip_loss)
        )
        grip_gate = self._smoothstep(0.18, 0.65, grip_loss)
        slip_angle_gate = self._smoothstep(0.28, 0.95, abs(self.hud_slip_angle_value()))
        driven_ratio, driven_combined = self.throttle_driven_slip_values()
        driven_slip_gate = max(
            self._smoothstep(1.10, 1.95, driven_ratio),
            self._smoothstep(0.70, 1.65, driven_combined),
        )
        wheel_over_gate = self.driven_wheel_overrotation_gate()
        yaw_gate = self._smoothstep(0.30, 1.10, abs(float(self.last_angular_velocity_y or 0.0)))
        drive_gate = max(driven_slip_gate, wheel_over_gate)
        rotation_context = max(yaw_gate, oversteer_gate, wheel_over_gate * 0.72)
        angle_with_rotation = slip_angle_gate * rotation_context
        drift_shape = max(oversteer_gate * 0.58, angle_with_rotation * 0.82, yaw_gate * 0.72)
        drift_context = max(
            grip_gate * 0.78,
            drive_gate * 0.58,
            min(slip_angle_gate, max(yaw_gate, oversteer_gate)) * 0.52,
        )
        sustained_drift_score = (
            angle_with_rotation * 0.24
            + grip_gate * 0.30
            + drive_gate * 0.24
            + oversteer_gate * 0.16
            + yaw_gate * 0.06
        )
        score = max(
            drift_shape * drift_context,
            sustained_drift_score,
            oversteer_gate * grip_gate * 0.62,
            yaw_gate * grip_gate * drive_gate * 0.55,
        )
        if yaw_gate < 0.22 and oversteer_gate < 0.28:
            score = min(score, 0.44)
        state.components = {
            "over": oversteer_gate,
            "angle": slip_angle_gate,
            "drive": driven_slip_gate,
            "wheel": wheel_over_gate,
            "grip": grip_gate,
        }
        return max(0.0, min(1.0, score * speed_gate))

    def drift_oversteer_signal(self, raw_balance: float, grip_loss: float) -> float:
        rear_bias_gate = self._smoothstep(0.05, 1.25, max(0.0, raw_balance))
        slip_angle_gate = self._smoothstep(0.22, 0.90, abs(self.hud_slip_angle_value()))
        yaw_gate = self._smoothstep(0.20, 1.05, abs(float(self.last_angular_velocity_y or 0.0)))
        lateral_g = abs(float(self.last_accel_x or 0.0)) / 9.80665
        lateral_gate = self._smoothstep(0.25, 1.05, lateral_g)
        steer_gate = self._smoothstep(0.06, 0.46, abs(float(self.last_steer or 0.0)) / 127.0)
        sustained_rotation_gate = yaw_gate * max(slip_angle_gate, lateral_gate * 0.70) * max(0.55, steer_gate)
        sliding_context_gate = max(grip_loss * 0.62, lateral_gate * 0.42, steer_gate * 0.28)
        body_slip_gate = slip_angle_gate * max(rear_bias_gate, yaw_gate * 0.70, sliding_context_gate * 0.55)
        return max(0.0, min(1.0, max(rear_bias_gate, sustained_rotation_gate, body_slip_gate)))

    def driven_wheel_overrotation_gate(self) -> float:
        driven_ratio, driven_combined = self.throttle_driven_slip_values()
        return max(
            self._smoothstep(1.12, 1.55, driven_ratio),
            self._smoothstep(0.75, 1.65, driven_combined) * 0.80,
        )

    def _smoothed_drift_oversteer_component(self, target: float) -> float:
        target = max(0.0, min(1.0, float(target)))
        previous = self.drift_hud.oversteer_component
        alpha = 0.34 if target > previous else 0.16
        value = previous + (target - previous) * alpha
        if target < 0.025 and value < 0.035:
            value = 0.0
        self.drift_hud.oversteer_component = max(0.0, min(1.0, value))
        return self.drift_hud.oversteer_component

    def _smoothed_drift_hud_score(self, now: float, target: float) -> float:
        target = max(0.0, min(1.0, float(target)))
        state = self.drift_hud
        previous = max(0.0, min(1.0, float(state.score)))
        last_update = float(state.score_last_update)
        dt = 0.0 if last_update <= 0.0 else max(0.0, min(0.2, now - last_update))
        state.score_last_update = now
        if target >= previous:
            alpha = 0.55 if dt <= 0.0 else min(0.85, 0.45 + dt * 3.0)
            value = previous + (target - previous) * alpha
        else:
            value = max(target, previous - DRIFT_SCORE_DECAY_PER_SECOND * max(dt, 1.0 / 120.0))
        if target < 0.025 and value < 0.035:
            value = 0.0
        return max(0.0, min(1.0, value))

    def _update_drift_fade_state(self, now: float, score: float) -> None:
        state = self.drift_hud
        if not state.active:
            state.fade_high_score_since = 0.0
            state.fade_active = False
            return
        if score < DRIFT_FADE_RELEASE_SCORE:
            state.fade_high_score_since = 0.0
            state.fade_active = False
            return
        if score < DRIFT_FADE_ENTER_SCORE:
            if not state.fade_active:
                state.fade_high_score_since = 0.0
            return
        if state.fade_high_score_since <= 0.0:
            state.fade_high_score_since = now
        if now - state.fade_high_score_since >= DRIFT_FADE_HOLD_SECONDS:
            state.fade_active = True

    def samples_for(self, telemetry_name: str) -> list[float]:
        if is_output_graph_item(telemetry_name):
            return list(self.output_histories.get(telemetry_name, []))
        return list(self.histories.get(telemetry_name, []))

    def append_output_sample(self, output_name: str, value: float) -> None:
        if not is_output_graph_item(output_name):
            return
        samples = self.output_histories.setdefault(output_name, [])
        samples.append(max(-1.0, min(1.0, float(value))))
        if len(samples) > self.HISTORY_LIMIT:
            del samples[: len(samples) - self.HISTORY_LIMIT]

    def _append_history_sample(self, telemetry_name: str, value: float | None) -> None:
        if value is None:
            return
        samples = self.histories.setdefault(telemetry_name, [])
        samples.append(value)
        if len(samples) > self.HISTORY_LIMIT:
            del samples[: len(samples) - self.HISTORY_LIMIT]

    def _record_history_samples(self) -> None:
        names = {card.name for card in self.cards}
        names.update(("Speed", "RPM", "Boost", "Torque", "Boost / Torque", "Throttle", "Brake", "Steer", "Gear", "Drift / Slip", "G-force", "Tire"))
        for name in names:
            self._append_history_sample(name, self.graph_value_for(name))


def clone_effect_settings(
    settings: dict[str, EffectSetting],
) -> dict[str, EffectSetting]:
    return {
        name: EffectSetting(
            value=setting.value,
            enabled=setting.enabled,
            details=deepcopy(setting.details),
        )
        for name, setting in settings.items()
    }


def clone_numeric_settings(
    settings: dict[str, NumericSetting],
) -> dict[str, NumericSetting]:
    return {
        name: NumericSetting(value=setting.value)
        for name, setting in settings.items()
    }


@dataclass
class PresetState:
    haptic_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(HAPTIC_EFFECT_DEFAULTS)
    )
    haptic_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(HAPTIC_ADVANCED_DEFAULTS)
    )
    trigger_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(TRIGGER_EFFECT_DEFAULTS)
    )
    trigger_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(TRIGGER_ADVANCED_DEFAULTS)
    )
    extra_haptic_effects: dict[str, dict] = field(default_factory=dict)
    extra_trigger_effects: dict[str, dict] = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)


def clone_preset_state(preset: PresetState) -> PresetState:
    return PresetState(
        haptic_effects=clone_effect_settings(preset.haptic_effects),
        haptic_advanced=clone_numeric_settings(preset.haptic_advanced),
        trigger_effects=clone_effect_settings(preset.trigger_effects),
        trigger_advanced=clone_numeric_settings(preset.trigger_advanced),
        extra_haptic_effects=deepcopy(preset.extra_haptic_effects),
        extra_trigger_effects=deepcopy(preset.extra_trigger_effects),
        metadata=deepcopy(preset.metadata),
    )


def make_preset_state_from_maps(
    haptic_effects: dict[str, EffectSetting],
    haptic_advanced: dict[str, NumericSetting],
    trigger_effects: dict[str, EffectSetting],
    trigger_advanced: dict[str, NumericSetting],
) -> PresetState:
    return PresetState(
        haptic_effects=clone_effect_settings(haptic_effects),
        haptic_advanced=clone_numeric_settings(haptic_advanced),
        trigger_effects=clone_effect_settings(trigger_effects),
        trigger_advanced=clone_numeric_settings(trigger_advanced),
    )


def make_default_preset_slots() -> dict[str, PresetState]:
    return {name: PresetState() for name in PRESET_NAMES}


@dataclass
class GameProfileState:
    selected_preset: str = "Base"
    presets: dict[str, PresetState] = field(default_factory=make_default_preset_slots)
    original_presets: dict[str, PresetState] = field(default_factory=make_default_preset_slots)
    haptic_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(HAPTIC_EFFECT_DEFAULTS)
    )
    haptic_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(HAPTIC_ADVANCED_DEFAULTS)
    )
    trigger_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(TRIGGER_EFFECT_DEFAULTS)
    )
    trigger_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(TRIGGER_ADVANCED_DEFAULTS)
    )


@dataclass
class AppState:
    udp_port: int = 8800
    packet_status: PacketStatus = PacketStatus.WAITING
    dualsense_status: DualSenseStatus = DualSenseStatus.CONNECTED
    unsaved_changes: bool = False
    game_mode: GameMode = GameMode.HORIZON
    selected_preset: str = "Base"
    selected_haptic_effect: str = "Road Bumps"
    selected_trigger_effect: str = "Brake Resistance - Predictive"
    footer: FooterStatus = field(default_factory=FooterStatus)
    window: WindowState = field(default_factory=WindowState)
    options: OptionState = field(default_factory=OptionState)
    hud: HudState = field(default_factory=HudState)
    trigger_debug: TriggerDebugState = field(default_factory=TriggerDebugState)
    haptic_debug: HapticDebugState = field(default_factory=HapticDebugState)
    dualsense_device: DualSenseDeviceState = field(default_factory=DualSenseDeviceState)
    sound_to_haptic: SoundToHapticState = field(default_factory=SoundToHapticState)
    telemetry: TelemetryState = field(default_factory=TelemetryState)
    haptic_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(HAPTIC_EFFECT_DEFAULTS)
    )
    haptic_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(HAPTIC_ADVANCED_DEFAULTS)
    )
    trigger_effects: dict[str, EffectSetting] = field(
        default_factory=lambda: make_effect_settings(TRIGGER_EFFECT_DEFAULTS)
    )
    trigger_advanced: dict[str, NumericSetting] = field(
        default_factory=lambda: make_numeric_settings(TRIGGER_ADVANCED_DEFAULTS)
    )
    game_profiles: dict[GameMode, GameProfileState] = field(
        default_factory=lambda: {
            GameMode.HORIZON: GameProfileState(),
            GameMode.MOTORSPORT: GameProfileState(),
        }
    )
    # Runtime-only scale used to cancel the process-wide Qt scale for HUD windows.
    # This deliberately remains separate from the mutable saved option so changing
    # Main UI Scale cannot resize HUDs before the required app restart.
    startup_main_ui_scale: int = field(default=100, repr=False, compare=False)

    def __post_init__(self) -> None:
        self.normalize_trigger_brake_exclusivity(prefer=self.selected_trigger_effect)
        self.sync_current_game_profile()

    def ensure_game_profile_presets(self, profile: GameProfileState) -> None:
        for preset_name in PRESET_NAMES:
            profile.presets.setdefault(preset_name, PresetState())
            profile.original_presets.setdefault(preset_name, PresetState())
        if profile.selected_preset not in PRESET_NAMES:
            profile.selected_preset = "Base"

    def sync_current_game_profile(self) -> None:
        self.normalize_trigger_brake_exclusivity(prefer=self.selected_trigger_effect)
        profile = self.game_profiles.setdefault(self.game_mode, GameProfileState())
        self.ensure_game_profile_presets(profile)
        if self.selected_preset not in PRESET_NAMES:
            self.selected_preset = "Base"
        existing_preset = profile.presets.get(self.selected_preset)
        active_preset = make_preset_state_from_maps(
            self.haptic_effects,
            self.haptic_advanced,
            self.trigger_effects,
            self.trigger_advanced,
        )
        if existing_preset is not None:
            active_preset.extra_haptic_effects = deepcopy(existing_preset.extra_haptic_effects)
            active_preset.extra_trigger_effects = deepcopy(existing_preset.extra_trigger_effects)
            active_preset.metadata = deepcopy(existing_preset.metadata)
        profile.selected_preset = self.selected_preset
        profile.presets[self.selected_preset] = active_preset
        profile.haptic_effects = clone_effect_settings(active_preset.haptic_effects)
        profile.haptic_advanced = clone_numeric_settings(active_preset.haptic_advanced)
        profile.trigger_effects = clone_effect_settings(active_preset.trigger_effects)
        profile.trigger_advanced = clone_numeric_settings(active_preset.trigger_advanced)

    def load_game_profile(self, game_mode: GameMode) -> None:
        profile = self.game_profiles.setdefault(game_mode, GameProfileState())
        self.ensure_game_profile_presets(profile)
        if profile.selected_preset not in PRESET_NAMES:
            profile.selected_preset = "Base"
        preset = profile.presets.setdefault(profile.selected_preset, PresetState())
        self.selected_preset = profile.selected_preset
        self.haptic_effects = clone_effect_settings(preset.haptic_effects)
        self.haptic_advanced = clone_numeric_settings(preset.haptic_advanced)
        self.trigger_effects = clone_effect_settings(preset.trigger_effects)
        self.trigger_advanced = clone_numeric_settings(preset.trigger_advanced)
        self.normalize_trigger_brake_exclusivity(prefer=self.selected_trigger_effect)
        profile.haptic_effects = clone_effect_settings(self.haptic_effects)
        profile.haptic_advanced = clone_numeric_settings(self.haptic_advanced)
        profile.trigger_effects = clone_effect_settings(self.trigger_effects)
        profile.trigger_advanced = clone_numeric_settings(self.trigger_advanced)
        if self.selected_haptic_effect not in self.haptic_effects:
            self.selected_haptic_effect = next(iter(self.haptic_effects), "")
        if self.selected_trigger_effect not in self.trigger_effects:
            self.selected_trigger_effect = next(iter(self.trigger_effects), "")

    @property
    def packet_status_label(self) -> str:
        if self.packet_status == PacketStatus.RECEIVING:
            return "Receiving"
        return "Waiting"

    @property
    def dualsense_status_label(self) -> str:
        labels = {
            DualSenseStatus.CONNECTED: "DualSense device connected",
            DualSenseStatus.NOT_SELECTED: "Select DualSense device",
            DualSenseStatus.SERVER_ERROR: "DualSense server needs attention",
        }
        return labels[self.dualsense_status]

    @property
    def selected_game_label(self) -> str:
        labels = {
            GameMode.HORIZON: "Forza Horizon",
            GameMode.MOTORSPORT: "Forza Motorsport",
        }
        return labels[self.game_mode]

    def mark_unsaved_changes(self) -> None:
        self.unsaved_changes = True

    def mark_settings_saved(self) -> None:
        self.unsaved_changes = False

    def set_udp_port(self, port: str | int) -> bool:
        try:
            clean_port = int(str(port).strip())
        except (TypeError, ValueError):
            self.footer.message = "UDP input port was not changed."
            self.footer.details = f"Enter a UDP port from 1 to 65535. Current: {self.udp_port}"
            return False
        clean_port = _clamp_udp_port(clean_port)
        if clean_port == self.udp_port:
            return False
        self.udp_port = clean_port
        self.packet_status = PacketStatus.WAITING
        self.footer.message = f"UDP input port updated: {self.udp_port}"
        self.footer.details = "Telemetry receiver restarted on the selected input port."
        self.mark_unsaved_changes()
        return True

    def set_game_mode(self, game_mode: GameMode) -> None:
        if game_mode == self.game_mode:
            self.footer.message = f"{self.selected_game_label} is already selected."
            self.footer.details = "Game-specific settings profile is already active."
            return
        self.sync_current_game_profile()
        self.game_mode = game_mode
        self.load_game_profile(game_mode)
        self.footer.message = f"{self.selected_game_label} selected."
        self.footer.details = "Game-specific preset, haptic, and trigger settings profile loaded."
        self.mark_unsaved_changes()

    def set_preset(self, preset_name: str) -> None:
        if preset_name not in PRESET_NAMES:
            raise ValueError(f"Unknown preset: {preset_name}")
        self.sync_current_game_profile()
        profile = self.game_profiles.setdefault(self.game_mode, GameProfileState())
        self.ensure_game_profile_presets(profile)
        profile.selected_preset = preset_name
        self.load_game_profile(self.game_mode)
        self.footer.message = f"Preset selected: {preset_name}"
        self.footer.details = f"{self.selected_game_label} preset slot loaded."
        self.mark_unsaved_changes()

    def load_preset_values_into_current(self, source_preset: str) -> None:
        if source_preset not in PRESET_NAMES:
            raise ValueError(f"Unknown preset: {source_preset}")
        if source_preset == self.selected_preset:
            self.footer.message = f"{source_preset} is already the active preset."
            self.footer.details = "Load source is the same as the current preset."
            return
        profile = self.game_profiles.setdefault(self.game_mode, GameProfileState())
        self.ensure_game_profile_presets(profile)
        source = profile.presets[source_preset]
        profile.presets[self.selected_preset] = clone_preset_state(source)
        self.load_game_profile(self.game_mode)
        self.footer.message = f"Preset values loaded: {source_preset} -> {self.selected_preset}"
        self.footer.details = f"{self.selected_game_label} current preset was overwritten with selected preset values."
        self.mark_unsaved_changes()

    def restore_current_preset_original_settings(self) -> None:
        self.sync_current_game_profile()
        profile = self.game_profiles.setdefault(self.game_mode, GameProfileState())
        self.ensure_game_profile_presets(profile)
        original = profile.original_presets[self.selected_preset]
        profile.presets[self.selected_preset] = clone_preset_state(original)
        self.load_game_profile(self.game_mode)
        self.footer.message = f"Original settings restored: {self.selected_preset}"
        self.footer.details = f"{self.selected_game_label} preset slot restored from the built-in original preset store."
        self.mark_unsaved_changes()

    def mark_save_requested(self) -> None:
        self.footer.message = f"Save requested for preset: {self.selected_preset}"
        self.footer.details = "Preparing a settings snapshot for the app user_data folder."

    def mark_load_backup_requested(self) -> None:
        self.footer.message = "Load backup requested."
        self.footer.details = "Choose a settings backup to restore, then confirm before applying it."

    def mark_dualsense_refresh_requested(self) -> None:
        self.footer.message = "DualSense device refresh requested."
        self.footer.details = "Checking current playback devices for DualSense audio candidates."

    def mark_dualsense_test_save_requested(self) -> None:
        self.dualsense_device.selected_device = self.dualsense_device.highlighted_device
        self.dualsense_status = DualSenseStatus.CONNECTED
        self.dualsense_device.last_test_result = "Test requested"
        self.footer.message = f"DualSense test and save requested: {self.dualsense_device.selected_device}"
        self.footer.details = "Device selection was saved. Haptic validation is handled by the output service."

    def mark_dualsense_save_requested(self) -> None:
        self.dualsense_device.selected_device = self.dualsense_device.highlighted_device
        self.dualsense_status = DualSenseStatus.CONNECTED
        self.footer.message = f"DualSense device saved: {self.dualsense_device.selected_device}"
        self.footer.details = "Selected audio-device value is stored in AppState and will be saved with settings."

    def mark_dualsense_cancelled(self) -> None:
        self.dualsense_device.highlighted_device = self.dualsense_device.selected_device
        self.footer.message = "DualSense device selection cancelled."
        self.footer.details = "No device selection changes were applied."

    def select_dualsense_candidate(self, device_name: str) -> None:
        known_devices = self.dualsense_device.candidates + self.dualsense_device.registered_candidates
        if device_name not in known_devices:
            return
        self.dualsense_device.highlighted_device = device_name
        self.footer.message = f"DualSense candidate selected: {device_name}"
        self.footer.details = "Use Test Haptic to validate it, or Save Device to store it."

    def set_sound_to_haptic_capture_candidates(self, candidates: list[str], details: str = "") -> None:
        unique = []
        for candidate in candidates:
            clean = str(candidate).strip()
            if clean and clean not in unique:
                unique.append(clean)
        sound = self.sound_to_haptic
        sound.capture_candidates = unique
        sound.refresh_attempted = True
        if sound.capture_device and sound.capture_device in unique:
            sound.highlighted_capture_device = sound.capture_device
        elif sound.highlighted_capture_device not in unique:
            sound.highlighted_capture_device = unique[0] if unique else ""
        sound.last_result = details or f"{len(unique)} capture device(s) found."
        self.footer.message = "Sound to Haptic capture devices refreshed."
        self.footer.details = sound.last_result

    def select_sound_to_haptic_capture_device(self, device_name: str) -> None:
        clean = str(device_name).strip()
        if clean not in self.sound_to_haptic.capture_candidates:
            return
        self.sound_to_haptic.highlighted_capture_device = clean
        self.footer.message = f"Sound to Haptic capture selected: {clean}"
        self.footer.details = "Use Save Capture or Start to apply this audio source."

    def save_sound_to_haptic_capture_device(self) -> None:
        sound = self.sound_to_haptic
        clean = sound.highlighted_capture_device.strip()
        if not clean:
            self.footer.message = "Sound to Haptic capture device was not saved."
            self.footer.details = "Refresh capture devices and choose a playback source first."
            return
        sound.capture_device = clean
        self.footer.message = "Sound to Haptic capture device saved."
        self.footer.details = f"Capture source: {clean}"
        self.mark_unsaved_changes()

    def set_sound_to_haptic_master_gain(self, value: int) -> None:
        new_value = max(0, min(100, int(value)))
        if self.sound_to_haptic.master_gain == new_value:
            return
        self.sound_to_haptic.master_gain = new_value
        self.sound_to_haptic.settings_dirty = True
        self.footer.message = f"Sound to Haptic output gain: {self.sound_to_haptic.master_gain}%"
        self.footer.details = "Restart Sound to Haptic or press Apply while running to use the new value."
        self.mark_unsaved_changes()

    def set_sound_to_haptic_low_volume_cut(self, value: int) -> None:
        new_value = max(0, min(50, int(value)))
        if self.sound_to_haptic.low_volume_cut == new_value:
            return
        self.sound_to_haptic.low_volume_cut = new_value
        self.sound_to_haptic.settings_dirty = True
        self.footer.message = f"Sound to Haptic low-volume cut: {self.sound_to_haptic.low_volume_cut}%"
        self.footer.details = "Lower values keep more quiet detail. Higher values remove low-level noise before output."
        self.mark_unsaved_changes()

    def set_sound_to_haptic_high_cut_hz(self, value: int) -> None:
        new_value = max(0, min(24000, int(value)))
        if self.sound_to_haptic.high_cut_hz == new_value:
            return
        self.sound_to_haptic.high_cut_hz = new_value
        self.sound_to_haptic.settings_dirty = True
        label = "Off" if self.sound_to_haptic.high_cut_hz <= 0 else f"{self.sound_to_haptic.high_cut_hz} Hz"
        self.footer.message = f"Sound to Haptic high-frequency cut: {label}"
        self.footer.details = "Lower values remove more high-frequency audio before it reaches DualSense channels 3/4."
        self.mark_unsaved_changes()

    def set_sound_to_haptic_dynamic_boost(self, value: int) -> None:
        new_value = max(0, min(300, int(value)))
        if self.sound_to_haptic.dynamic_boost == new_value:
            return
        self.sound_to_haptic.dynamic_boost = new_value
        self.sound_to_haptic.settings_dirty = True
        self.footer.message = f"Sound to Haptic dynamic boost: {self.sound_to_haptic.dynamic_boost}%"
        self.footer.details = "Values above 100% lift quieter sound more than loud sound, making subtle audio easier to feel."
        self.mark_unsaved_changes()

    def mark_sound_to_haptic_running(self, running: bool, details: str = "") -> None:
        self.sound_to_haptic.running = bool(running)
        self.sound_to_haptic.enabled = bool(running)
        self.sound_to_haptic.last_result = details or ("Sound to Haptic running." if running else "Sound to Haptic stopped.")
        self.footer.message = "Sound to Haptic started." if running else "Sound to Haptic stopped."
        self.footer.details = self.sound_to_haptic.last_result

    def mark_option_action_requested(self, action_name: str) -> None:
        self.footer.message = f"Option action requested: {action_name}"
        self.footer.details = "Option changes are kept in the current settings session."

    def cycle_main_ui_language(self) -> None:
        self.set_main_ui_language(_next_language(self.options.main_ui_language, MAIN_UI_LANGUAGES))

    def set_main_ui_language(self, language: str) -> None:
        if language not in MAIN_UI_LANGUAGES:
            self.footer.message = f"Unsupported main UI language: {language}"
            self.footer.details = "Choose one of the languages available in the Main UI language menu."
            return
        self.options.main_ui_language = language
        self.footer.message = f"Main UI language selected: {self.options.main_ui_language}"
        self.footer.details = "Main UI language preference was stored."
        self.mark_unsaved_changes()

    def cycle_tooltip_language(self) -> None:
        self.set_tooltip_language(_next_language(self.options.tooltip_language, TOOLTIP_LANGUAGES))

    def set_tooltip_language(self, language: str) -> None:
        if language not in TOOLTIP_LANGUAGES:
            self.footer.message = f"Unsupported tooltip language: {language}"
            self.footer.details = "Choose one of the languages available in the Tooltip language menu."
            return
        self.options.tooltip_language = language
        self.footer.message = f"Tooltip language selected: {self.options.tooltip_language}"
        self.footer.details = "Tooltip text tables will use this value after the help engine is connected."
        self.mark_unsaved_changes()

    def set_main_ui_scale(self, scale: int) -> None:
        allowed_scales = (90, 100, 110, 125)
        try:
            requested = int(scale)
        except (TypeError, ValueError):
            requested = 100
        nearest = min(allowed_scales, key=lambda value: abs(value - requested))
        self.options.main_ui_scale = nearest
        self.footer.message = f"Main UI scale selected: {nearest}%"
        self.footer.details = "Main UI scale will be applied the next time the app starts."
        self.mark_unsaved_changes()

    def toggle_preset_shortcut(self) -> None:
        self.options.preset_shortcut_enabled = not self.options.preset_shortcut_enabled
        state = "ON" if self.options.preset_shortcut_enabled else "OFF"
        self.footer.message = f"Preset shortcut {state}"
        self.footer.details = f"Shortcut combo: {self.options.preset_shortcut_combo}"
        self.mark_unsaved_changes()

    def apply_preset_shortcut(self) -> None:
        self.footer.message = f"Preset shortcut applied: {self.options.preset_shortcut_combo}"
        self.footer.details = "Shortcut preference was stored for the selected DualSense device."

    def toggle_telemetry_relay(self) -> None:
        self.options.telemetry_relay_enabled = not self.options.telemetry_relay_enabled
        state = "ON" if self.options.telemetry_relay_enabled else "OFF"
        self.footer.message = f"Telemetry UDP relay {state}"
        self.footer.details = f"Target: {self.options.telemetry_relay_host}:{self.options.telemetry_relay_port}"
        self.mark_unsaved_changes()

    def apply_telemetry_relay(self) -> None:
        self.footer.message = "Telemetry UDP relay settings applied."
        self.footer.details = f"Target: {self.options.telemetry_relay_host}:{self.options.telemetry_relay_port}"

    def set_telemetry_relay_host(self, host: str) -> None:
        clean_host = str(host).strip() or "127.0.0.1"
        self.options.telemetry_relay_host = clean_host
        self.footer.message = "Telemetry UDP relay host updated."
        self.footer.details = f"Target: {self.options.telemetry_relay_host}:{self.options.telemetry_relay_port}"
        self.mark_unsaved_changes()

    def set_telemetry_relay_port(self, port: str | int) -> None:
        try:
            clean_port = int(port)
        except (TypeError, ValueError):
            self.footer.message = "Telemetry UDP relay port was not changed."
            self.footer.details = f"Enter a UDP port from 1 to 65535. Current: {self.options.telemetry_relay_port}"
            return
        self.options.telemetry_relay_port = _clamp_udp_port(clean_port)
        self.footer.message = "Telemetry UDP relay port updated."
        self.footer.details = f"Target: {self.options.telemetry_relay_host}:{self.options.telemetry_relay_port}"
        self.mark_unsaved_changes()

    def toggle_dsx_bridge(self) -> None:
        self.options.dsx_bridge_enabled = not self.options.dsx_bridge_enabled
        state = "ON" if self.options.dsx_bridge_enabled else "OFF"
        self.footer.message = f"DSX trigger UDP bridge {state}"
        self.footer.details = f"Target: {self.options.dsx_host}:{self.options.dsx_port}"
        self.mark_unsaved_changes()

    def set_dsx_host(self, host: str) -> None:
        clean_host = str(host).strip() or "127.0.0.1"
        self.options.dsx_host = clean_host
        self.footer.message = "DSX UDP host updated."
        self.footer.details = f"Target: {self.options.dsx_host}:{self.options.dsx_port}"
        self.mark_unsaved_changes()

    def set_dsx_port(self, port: str | int) -> None:
        try:
            clean_port = int(port)
        except (TypeError, ValueError):
            self.footer.message = "DSX UDP port was not changed."
            self.footer.details = f"Enter a UDP port from 1 to 65535. Current: {self.options.dsx_port}"
            return
        self.options.dsx_port = _clamp_udp_port(clean_port)
        self.footer.message = "DSX UDP port updated."
        self.footer.details = f"Target: {self.options.dsx_host}:{self.options.dsx_port}"
        self.mark_unsaved_changes()

    def toggle_dsx_audio_export(self) -> None:
        self.options.dsx_audio_export_enabled = not self.options.dsx_audio_export_enabled
        state = "ON" if self.options.dsx_audio_export_enabled else "OFF"
        self.footer.message = f"DSX audio export {state}"
        self.footer.details = f"Output device: {self.options.dsx_audio_device}"
        self.mark_unsaved_changes()

    def request_dsx_audio_device_select(self) -> None:
        self.footer.message = "DSX audio output device selection requested."
        self.footer.details = "Choose an output device from the audio-device selector."

    def set_dsx_audio_device(self, device_name: str) -> None:
        clean_name = str(device_name).strip()
        if not clean_name:
            self.footer.message = "DSX audio output device was not changed."
            self.footer.details = "The selected playback device name was empty."
            return
        self.options.dsx_audio_device = clean_name
        self.footer.message = "DSX audio output device selected."
        self.footer.details = f"Output device: {self.options.dsx_audio_device}"
        self.mark_unsaved_changes()

    def apply_dsx_audio_volume(self) -> None:
        self.footer.message = f"DSX audio volume applied: {self.options.dsx_audio_volume}%"
        self.footer.details = f"Output device: {self.options.dsx_audio_device}"

    def set_dsx_audio_volume(self, value: int) -> None:
        self.options.dsx_audio_volume = max(0, min(100, int(value)))
        self.footer.message = f"DSX audio volume adjusted: {self.options.dsx_audio_volume}%"
        self.footer.details = "Click Apply when ready to commit this output volume."
        self.mark_unsaved_changes()

    def set_haptic_low_boost_gain(self, value: int) -> None:
        self.options.haptic_low_boost_gain = max(0, min(10, int(value)))
        self.footer.message = f"Haptic Low Boost Gain adjusted: {self.options.haptic_low_boost_gain}/10"
        self.footer.details = "Click EQ Boost Gain to apply this value to the haptic output server."
        self.mark_unsaved_changes()

    def apply_haptic_low_boost_gain(self) -> None:
        gain = max(0, min(10, int(self.options.haptic_low_boost_gain)))
        self.options.haptic_low_boost_gain = gain
        self.footer.message = f"Haptic Low Boost Gain applied: {gain}/10"
        self.footer.details = "The output runtime will send the current low-level boost gain to the haptic server."

    def mark_hud_action_requested(self, action_name: str) -> None:
        self.footer.message = f"HUD action requested: {action_name}"
        self.footer.details = "HUD layout settings were updated for the current session."

    def toggle_hud_all(self) -> None:
        regular_items = [
            item
            for name, item in self.hud.items.items()
            if name not in DEBUG_HUD_NAMES
        ]
        enable = not all(item.enabled for item in regular_items)
        for item in regular_items:
            item.enabled = enable
        state = "ON" if enable else "OFF"
        self.footer.message = f"HUD regular overlays {state}"
        self.footer.details = "Debug HUD overlays are excluded from HUD ALL and remain individually controlled."
        self.mark_unsaved_changes()

    def toggle_standby_hide(self) -> None:
        self.hud.standby_hide = not self.hud.standby_hide
        state = "ON" if self.hud.standby_hide else "OFF"
        self.footer.message = f"HUD standby hide {state}"
        self.footer.details = "HUD standby visibility preference was stored."
        self.mark_unsaved_changes()

    def toggle_snap_hud(self) -> None:
        self.hud.snap_enabled = not self.hud.snap_enabled
        state = "ON" if self.hud.snap_enabled else "OFF"
        self.footer.message = f"HUD snap {state}"
        self.footer.details = f"Snap pixel: {self.hud.snap_pixel}"
        self.mark_unsaved_changes()

    def adjust_snap_pixel(self, delta: int) -> None:
        self.hud.snap_pixel = max(1, min(50, self.hud.snap_pixel + delta))
        self.footer.message = f"HUD snap pixel: {self.hud.snap_pixel}"
        self.footer.details = "HUD snap spacing preference was stored."
        self.mark_unsaved_changes()

    def request_hud_location_reset(self) -> None:
        for item in self.hud.items.values():
            item.x = None
            item.y = None
        self.footer.message = "HUD location reset requested."
        self.footer.details = "HUD positions will use the default layout anchors."
        self.mark_unsaved_changes()

    def toggle_hud_item(self, name: str) -> None:
        item = self.hud.items[name]
        item.enabled = not item.enabled
        state = "ON" if item.enabled else "OFF"
        self.footer.message = f"{name} HUD {state}"
        self.footer.details = "HUD visibility preference was stored."
        self.mark_unsaved_changes()

    def adjust_hud_scale(self, name: str, delta: int) -> None:
        item = self.hud.items[name]
        item.scale = max(50, min(200, item.scale + delta))
        self.footer.message = f"{name} HUD scale: {item.scale}%"
        self.footer.details = "HUD scale preference was stored."
        self.mark_unsaved_changes()

    def adjust_all_hud_scale(self, delta: int) -> None:
        for item in self.hud.items.values():
            item.scale = max(50, min(200, item.scale + delta))
        sign = "+" if delta > 0 else ""
        self.footer.message = f"All HUD scale offset: {sign}{delta}%"
        self.footer.details = "Each HUD keeps its relative scale and is clamped between 50% and 200%."
        self.mark_unsaved_changes()

    def reset_all_hud_scale(self) -> None:
        for item in self.hud.items.values():
            item.scale = 100
        self.footer.message = "All HUD scale reset to 100%"
        self.footer.details = "All HUD scale values now share the same baseline."
        self.mark_unsaved_changes()

    def adjust_hud_opacity(self, name: str, delta: int) -> None:
        item = self.hud.items[name]
        item.opacity = max(10, min(100, item.opacity + delta))
        self.footer.message = f"{name} HUD opacity: {item.opacity}%"
        self.footer.details = "HUD opacity preference was stored."
        self.mark_unsaved_changes()

    def adjust_all_hud_opacity(self, delta: int) -> None:
        for item in self.hud.items.values():
            item.opacity = max(10, min(100, item.opacity + delta))
        sign = "+" if delta > 0 else ""
        self.footer.message = f"All HUD opacity offset: {sign}{delta}%"
        self.footer.details = "Each HUD keeps its relative opacity and is clamped between 10% and 100%."
        self.mark_unsaved_changes()

    def reset_all_hud_opacity(self) -> None:
        for item in self.hud.items.values():
            item.opacity = 100
        self.footer.message = "All HUD opacity reset to 100%"
        self.footer.details = "All HUD opacity values now share the same baseline."
        self.mark_unsaved_changes()

    def set_hud_position(self, name: str, x: int, y: int) -> None:
        item = self.hud.items.get(name)
        if item is None:
            return
        item.x = int(x)
        item.y = int(y)
        self.mark_unsaved_changes()

    def set_window_geometry(self, x: int, y: int, width: int, height: int) -> None:
        x = max(-4000, min(8000, int(x)))
        y = max(-4000, min(8000, int(y)))
        width = max(790, min(4000, int(width)))
        height = max(544, min(3000, int(height)))
        if (
            self.window.x == x
            and self.window.y == y
            and self.window.width == width
            and self.window.height == height
        ):
            return
        self.window.x = x
        self.window.y = y
        self.window.width = width
        self.window.height = height
        self.mark_unsaved_changes()

    def update_trigger_debug_specs(self, specs: Mapping[str, Mapping[str, float]]) -> None:
        self.trigger_debug.update_specs(specs)
        self._record_trigger_output_graph_samples()

    def update_haptic_debug_specs(self, specs: Mapping[str, Mapping[str, float]]) -> None:
        self.haptic_debug.update_specs(specs)
        self._record_haptic_output_graph_samples()

    def _record_haptic_output_graph_samples(self) -> None:
        now = monotonic()
        for name, spec in self.haptic_debug.specs.items():
            age = now - float(spec.updated_at)
            value = 0.0 if age > 0.80 else max(0.0, min(1.0, float(spec.level) / 100.0))
            self.telemetry.append_output_sample(haptic_output_item_name(name), value)

    def _record_trigger_output_graph_samples(self) -> None:
        now = monotonic()
        for name, spec in self.trigger_debug.specs.items():
            age = now - float(spec.updated_at)
            if age > 0.80:
                value = 0.0
            else:
                force = max(0.0, min(1.0, float(spec.force) / 255.0))
                pulse = max(0.0, min(1.0, float(spec.pulse_amp) / 255.0))
                vibration = max(0.0, min(1.0, float(spec.vibrate_amp) / 8.0))
                value = max(force, pulse, vibration)
            self.telemetry.append_output_sample(trigger_output_item_name(name), value)

    def output_graph_display_value_for(self, output_name: str) -> str:
        value = self.output_graph_value_for(output_name)
        if value is None:
            return "--"
        return f"{value * 100.0:.0f}%"

    def output_graph_value_for(self, output_name: str) -> float | None:
        parts = output_graph_item_parts(output_name)
        if parts is None:
            return None
        kind, name = parts
        now = monotonic()
        if kind == "haptic":
            spec = self.haptic_debug.specs.get(name)
            if spec is None or now - float(spec.updated_at) > 0.80:
                return 0.0
            return max(0.0, min(1.0, float(spec.level) / 100.0))
        spec = self.trigger_debug.specs.get(name)
        if spec is None or now - float(spec.updated_at) > 0.80:
            return 0.0
        force = max(0.0, min(1.0, float(spec.force) / 255.0))
        pulse = max(0.0, min(1.0, float(spec.pulse_amp) / 255.0))
        vibration = max(0.0, min(1.0, float(spec.vibrate_amp) / 8.0))
        return max(force, pulse, vibration)

    def cycle_speed_unit(self) -> None:
        self.hud.speed_unit = _next_language(self.hud.speed_unit, ("km/h", "mph"))
        self.footer.message = f"HUD speed unit: {self.hud.speed_unit}"
        self.footer.details = "HUD speed unit preference was stored."
        self.mark_unsaved_changes()

    def set_rpm_style(self, style: str) -> None:
        style = str(style)
        if style not in ("Classic", "Modern", "Digital Bar"):
            return
        if style == self.hud.rpm_style:
            return
        self.hud.rpm_style = style
        self.footer.message = f"RPM HUD style: {self.hud.rpm_style}"
        self.footer.details = "RPM HUD style preference was stored."
        self.mark_unsaved_changes()

    def cycle_rpm_style(self) -> None:
        self.set_rpm_style(
            _next_language(
                self.hud.rpm_style,
                ("Classic", "Modern", "Digital Bar"),
            )
        )

    def cycle_power_unit(self) -> None:
        self.hud.power_unit = _next_language(self.hud.power_unit, ("PS", "hp", "kW"))
        self.footer.message = f"HUD power unit: {self.hud.power_unit}"
        self.footer.details = "HUD power unit preference was stored."
        self.mark_unsaved_changes()

    def cycle_boost_unit(self) -> None:
        self.hud.boost_unit = _next_language(self.hud.boost_unit, ("bar", "psi"))
        self.footer.message = f"HUD boost unit: {self.hud.boost_unit}"
        self.footer.details = "HUD boost unit preference was stored."
        self.mark_unsaved_changes()

    def set_telemetry_card(self, index: int, telemetry_name: str) -> None:
        if index < 0 or index >= len(self.telemetry.cards):
            return
        if index == OUTPUT_CARD_INDEX:
            if not is_output_graph_item(telemetry_name):
                return
            self.telemetry.cards[index].name = telemetry_name
            self.footer.message = f"Output graph set to {telemetry_name}"
            self.footer.details = "The bottom graph now follows the selected haptic or trigger output."
            self.mark_unsaved_changes()
            return
        if telemetry_name not in TELEMETRY_ITEMS:
            return
        self.telemetry.cards[index].name = telemetry_name
        self.footer.message = f"Telemetry card {index + 1} set to {telemetry_name}"
        self.footer.details = "Telemetry card selection was stored."
        self.mark_unsaved_changes()

    def mark_haptic_action_requested(self, action_name: str) -> None:
        self.footer.message = f"Haptic action requested: {action_name}"
        self.footer.details = "Haptic settings are ready for the output profile."

    def mark_trigger_action_requested(self, action_name: str) -> None:
        self.footer.message = f"Trigger action requested: {action_name}"
        self.footer.details = "Trigger settings are ready for the output profile."

    def select_haptic_effect(self, name: str) -> None:
        if name not in self.haptic_effects:
            return
        self.selected_haptic_effect = name
        self.footer.message = f"Haptic effect selected: {name}"
        self.footer.details = "Advanced Settings now shows this effect's preserved preset details."

    def select_trigger_effect(self, name: str) -> None:
        if name not in self.trigger_effects:
            return
        self.selected_trigger_effect = name
        self.footer.message = f"Trigger effect selected: {name}"
        self.footer.details = "Advanced Settings now shows this effect's preserved preset details."

    def set_haptic_effect_value(self, name: str, value: int) -> None:
        self.select_haptic_effect(name)
        setting = self.haptic_effects[name]
        setting.value = clamp_setting_value(value)
        if "volume" in setting.details:
            setting.details["volume"] = setting.value
        self.sync_current_game_profile()
        self.footer.message = f"Haptic effect value updated: {name} = {setting.value}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def toggle_haptic_effect(self, name: str) -> None:
        self.select_haptic_effect(name)
        setting = self.haptic_effects[name]
        setting.enabled = not setting.enabled
        if "enabled" in setting.details:
            setting.details["enabled"] = setting.enabled
        self.sync_current_game_profile()
        state = "ON" if setting.enabled else "OFF"
        self.footer.message = f"Haptic effect toggled: {name} {state}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def set_haptic_detail_value(self, key: str, value: int) -> None:
        if self.selected_haptic_effect not in self.haptic_effects:
            return
        setting = self.haptic_effects[self.selected_haptic_effect]
        setting.details[key] = int(value)
        if key == "volume":
            setting.value = clamp_setting_value(value)
        self.sync_current_game_profile()
        self.footer.message = f"Haptic detail updated: {self.selected_haptic_effect} / {key} = {value}"
        self.footer.details = "Stored in the current preset detail payload. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def set_haptic_advanced_value(self, name: str, value: int) -> None:
        setting = self.haptic_advanced[name]
        setting.value = clamp_setting_value(value)
        self.sync_current_game_profile()
        self.footer.message = f"Haptic advanced value updated: {name} = {setting.value}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def set_trigger_effect_value(self, name: str, value: int) -> None:
        self.select_trigger_effect(name)
        setting = self.trigger_effects[name]
        setting.value = clamp_setting_value(value)
        if "volume" in setting.details:
            setting.details["volume"] = setting.value
        self.sync_current_game_profile()
        self.footer.message = f"Trigger effect value updated: {name} = {setting.value}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def toggle_trigger_effect(self, name: str) -> None:
        self.select_trigger_effect(name)
        setting = self.trigger_effects[name]
        setting.enabled = not setting.enabled
        if "enabled" in setting.details:
            setting.details["enabled"] = setting.enabled
        if setting.enabled:
            self.normalize_trigger_brake_exclusivity(prefer=name)
        self.sync_current_game_profile()
        state = "ON" if setting.enabled else "OFF"
        self.footer.message = f"Trigger effect toggled: {name} {state}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def normalize_trigger_brake_exclusivity(self, prefer: str | None = None) -> None:
        active = [
            name
            for name in BRAKE_TRIGGER_EFFECT_NAMES
            if name in self.trigger_effects and self.trigger_effects[name].enabled
        ]
        if len(active) <= 1:
            return
        keep = prefer if prefer in active else active[0]
        for name in BRAKE_TRIGGER_EFFECT_NAMES:
            if name == keep or name not in self.trigger_effects:
                continue
            setting = self.trigger_effects[name]
            setting.enabled = False
            if "enabled" in setting.details:
                setting.details["enabled"] = False

    def set_trigger_detail_value(self, key: str, value) -> None:
        if self.selected_trigger_effect not in self.trigger_effects:
            return
        setting = self.trigger_effects[self.selected_trigger_effect]
        if isinstance(value, bool):
            stored_value = value
        elif isinstance(value, str):
            stored_value = value
        else:
            stored_value = int(value)
        detail_keys = (key,)
        if self.selected_trigger_effect == "Kerb Wave":
            detail_keys = KERB_WAVE_SHARED_DETAIL_MIRRORS.get(key, detail_keys)
        for detail_key in detail_keys:
            setting.details[detail_key] = stored_value
        if key == "volume":
            setting.value = clamp_setting_value(int(stored_value))
        self.sync_current_game_profile()
        self.footer.message = f"Trigger detail updated: {self.selected_trigger_effect} / {key} = {stored_value}"
        self.footer.details = "Stored in the current preset detail payload. Use SAVE to persist this change."
        self.mark_unsaved_changes()

    def set_trigger_advanced_value(self, name: str, value: int) -> None:
        setting = self.trigger_advanced[name]
        setting.value = clamp_setting_value(value)
        self.sync_current_game_profile()
        self.footer.message = f"Trigger advanced value updated: {name} = {setting.value}"
        self.footer.details = "Stored in the current preset. Use SAVE to persist this change."
        self.mark_unsaved_changes()


def _next_language(current: str, values: tuple[str, ...]) -> str:
    if current not in values:
        return values[0]
    index = values.index(current)
    return values[(index + 1) % len(values)]


def _clamp_udp_port(value: int) -> int:
    return max(1, min(65535, int(value)))
