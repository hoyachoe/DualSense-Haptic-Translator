from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from .app_state import (
    AppState,
    GameMode,
    GameProfileState,
    HUD_NAMES,
    PRESET_NAMES,
    PresetState,
    TELEMETRY_COLORS,
    TELEMETRY_ITEMS,
    clone_effect_settings,
    clone_numeric_settings,
    is_output_graph_item,
)
from .settings_model import EffectSetting, NumericSetting, clamp_setting_value
from .version import APP_VERSION


SNAPSHOT_SCHEMA = 1
HUD_LAYOUT_VERSION = 2
USER_PRESET_NAMES = ("User 1", "User 2")


@dataclass(frozen=True)
class SnapshotAudit:
    warnings: tuple[str, ...]
    game_profile_count: int
    preset_slot_count: int

    @property
    def ok(self) -> bool:
        return not self.warnings

    @property
    def summary(self) -> str:
        status = "structure ok" if self.ok else f"{len(self.warnings)} structure warning(s)"
        return (
            f"{status}; {self.game_profile_count} game profiles, "
            f"{self.preset_slot_count} preset slots"
        )


def _export_effects(settings: dict[str, EffectSetting]) -> dict[str, dict[str, Any]]:
    exported: dict[str, dict[str, Any]] = {}
    for name, setting in settings.items():
        payload = {
            "value": int(setting.value),
            "enabled": bool(setting.enabled),
        }
        if setting.details:
            payload["details"] = deepcopy(setting.details)
        exported[name] = payload
    return exported


def _export_numeric(settings: dict[str, NumericSetting]) -> dict[str, int]:
    return {name: int(setting.value) for name, setting in settings.items()}


def _export_options(state: AppState) -> dict[str, Any]:
    options = state.options
    return {
        "main_ui_language": options.main_ui_language,
        "tooltip_language": options.tooltip_language,
        "main_ui_scale": int(options.main_ui_scale),
        "haptic_low_boost_gain": int(options.haptic_low_boost_gain),
        "preset_shortcut_enabled": bool(options.preset_shortcut_enabled),
        "preset_shortcut_combo": options.preset_shortcut_combo,
        "preset_shortcut_return_preset": options.preset_shortcut_return_preset,
        "telemetry_relay_enabled": bool(options.telemetry_relay_enabled),
        "telemetry_relay_host": options.telemetry_relay_host,
        "telemetry_relay_port": int(options.telemetry_relay_port),
        "dsx_bridge_enabled": bool(options.dsx_bridge_enabled),
        "dsx_host": options.dsx_host,
        "dsx_port": int(options.dsx_port),
        "dsx_audio_export_enabled": bool(options.dsx_audio_export_enabled),
        "dsx_audio_device": options.dsx_audio_device,
        "dsx_audio_volume": int(options.dsx_audio_volume),
    }


def _export_window(state: AppState) -> dict[str, Any]:
    window = state.window
    return {
        "x": window.x,
        "y": window.y,
        "width": int(window.width),
        "height": int(window.height),
    }


def _export_hud(state: AppState) -> dict[str, Any]:
    return {
        "layout_version": HUD_LAYOUT_VERSION,
        "standby_hide": bool(state.hud.standby_hide),
        "snap_enabled": bool(state.hud.snap_enabled),
        "snap_pixel": int(state.hud.snap_pixel),
        "speed_unit": state.hud.speed_unit,
        "power_unit": state.hud.power_unit,
        "boost_unit": state.hud.boost_unit,
        "rpm_style": state.hud.rpm_style,
        "items": {
            name: {
                "enabled": bool(item.enabled),
                "scale": int(item.scale),
                "opacity": int(item.opacity),
                "x": item.x,
                "y": item.y,
            }
            for name, item in state.hud.items.items()
        },
    }


def _export_dualsense_device(state: AppState) -> dict[str, Any]:
    device = state.dualsense_device
    return {
        "selected_device": device.selected_device,
        "highlighted_device": device.highlighted_device,
        "last_test_result": device.last_test_result,
        "registered_candidates": device.registered_candidates,
    }


def _export_sound_to_haptic(state: AppState) -> dict[str, Any]:
    sound = state.sound_to_haptic
    return {
        "enabled": bool(sound.enabled),
        "capture_device": sound.capture_device,
        "highlighted_capture_device": sound.highlighted_capture_device,
        "master_gain": int(sound.master_gain),
        "low_volume_cut": int(sound.low_volume_cut),
        "high_cut_hz": int(sound.high_cut_hz),
        "dynamic_boost": int(sound.dynamic_boost),
    }


def _export_telemetry(state: AppState) -> dict[str, Any]:
    return {
        "cards": [
            {
                "name": card.name,
                "pattern": int(card.pattern),
                "color_key": card.color_key,
            }
            for card in state.telemetry.cards
        ]
    }


def _export_game_profile(profile: GameProfileState) -> dict[str, Any]:
    return {
        "selected_preset": profile.selected_preset,
        "haptic_effects": _export_effects(profile.haptic_effects),
        "haptic_advanced": _export_numeric(profile.haptic_advanced),
        "trigger_effects": _export_effects(profile.trigger_effects),
        "trigger_advanced": _export_numeric(profile.trigger_advanced),
        "presets": {
            preset_name: _export_preset_state(preset)
            for preset_name, preset in profile.presets.items()
            if preset_name in PRESET_NAMES
        },
    }


def _export_preset_state(preset: PresetState) -> dict[str, Any]:
    payload = {
        "haptic_effects": _export_effects(preset.haptic_effects),
        "haptic_advanced": _export_numeric(preset.haptic_advanced),
        "trigger_effects": _export_effects(preset.trigger_effects),
        "trigger_advanced": _export_numeric(preset.trigger_advanced),
    }
    if preset.extra_haptic_effects:
        payload["extra_haptic_effects"] = deepcopy(preset.extra_haptic_effects)
    if preset.extra_trigger_effects:
        payload["extra_trigger_effects"] = deepcopy(preset.extra_trigger_effects)
    if preset.metadata:
        payload["metadata"] = deepcopy(preset.metadata)
    return payload


def _export_game_profiles(state: AppState) -> dict[str, Any]:
    state.sync_current_game_profile()
    return {
        game_mode.value: _export_game_profile(profile)
        for game_mode, profile in state.game_profiles.items()
    }


def export_app_state(state: AppState) -> dict[str, Any]:
    """Return a file-ready settings snapshot without writing it to disk."""
    return {
        "schema": SNAPSHOT_SCHEMA,
        "app_version": APP_VERSION,
        "udp_port": int(state.udp_port),
        "game_mode": state.game_mode.value,
        "selected_preset": state.selected_preset,
        "ui_selection": {
            "selected_haptic_effect": state.selected_haptic_effect,
            "selected_trigger_effect": state.selected_trigger_effect,
        },
        "haptic_effects": _export_effects(state.haptic_effects),
        "haptic_advanced": _export_numeric(state.haptic_advanced),
        "trigger_effects": _export_effects(state.trigger_effects),
        "trigger_advanced": _export_numeric(state.trigger_advanced),
        "window": _export_window(state),
        "options": _export_options(state),
        "hud": _export_hud(state),
        "dualsense_device": _export_dualsense_device(state),
        "sound_to_haptic": _export_sound_to_haptic(state),
        "telemetry": _export_telemetry(state),
        "game_profiles": _export_game_profiles(state),
    }


def compare_snapshot_schema(snapshot: dict[str, Any]) -> int:
    snapshot_schema = snapshot.get("schema")
    if not isinstance(snapshot_schema, int) or isinstance(snapshot_schema, bool):
        return -1
    if snapshot_schema == SNAPSHOT_SCHEMA:
        return 0
    if snapshot_schema > SNAPSHOT_SCHEMA:
        return 1
    return -1


def audit_snapshot_structure(snapshot: dict[str, Any]) -> SnapshotAudit:
    warnings: list[str] = []
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        warnings.append("schema mismatch")
    if not str(snapshot.get("app_version") or "").strip():
        warnings.append("missing app version")

    game_mode = snapshot.get("game_mode")
    try:
        GameMode(game_mode)
    except ValueError:
        warnings.append("unknown selected game mode")

    game_profiles = snapshot.get("game_profiles")
    game_profile_count = 0
    preset_slot_count = 0
    if not isinstance(game_profiles, dict):
        warnings.append("missing game_profiles")
        return SnapshotAudit(tuple(warnings), game_profile_count, preset_slot_count)

    for game_mode in GameMode:
        profile = game_profiles.get(game_mode.value)
        if not isinstance(profile, dict):
            warnings.append(f"missing {game_mode.value} game profile")
            continue
        game_profile_count += 1
        if "original_presets" in profile:
            warnings.append(f"{game_mode.value} profile contains original_presets")
        selected_preset = profile.get("selected_preset")
        if selected_preset not in PRESET_NAMES:
            warnings.append(f"{game_mode.value} profile has unknown selected preset")
        presets = profile.get("presets")
        if not isinstance(presets, dict):
            warnings.append(f"{game_mode.value} profile missing preset slots")
            continue
        for preset_name in PRESET_NAMES:
            preset = presets.get(preset_name)
            if not isinstance(preset, dict):
                warnings.append(f"{game_mode.value} missing {preset_name} preset slot")
                continue
            preset_slot_count += 1
            for key in (
                "haptic_effects",
                "haptic_advanced",
                "trigger_effects",
                "trigger_advanced",
            ):
                if not isinstance(preset.get(key), dict):
                    warnings.append(f"{game_mode.value} {preset_name} missing {key}")
    return SnapshotAudit(tuple(warnings), game_profile_count, preset_slot_count)


def _apply_effects(target: dict[str, EffectSetting], source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    for name, payload in source.items():
        if name not in target or not isinstance(payload, dict):
            continue
        setting = target[name]
        if "value" in payload:
            setting.value = clamp_setting_value(payload["value"])
        elif "volume" in payload:
            setting.value = clamp_setting_value(payload["volume"])
        if "enabled" in payload:
            setting.enabled = bool(payload["enabled"])
        detail_payload = payload.get("details")
        if isinstance(detail_payload, dict):
            setting.details = deepcopy(detail_payload)
        else:
            flat_details = {
                key: deepcopy(value)
                for key, value in payload.items()
                if key not in {"value", "enabled"}
            }
            if flat_details:
                setting.details = flat_details
        restored.append(name)
    return restored


def _apply_numeric(target: dict[str, NumericSetting], source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    for name, value in source.items():
        if name not in target:
            continue
        target[name].value = clamp_setting_value(value)
        restored.append(name)
    return restored


def _apply_options(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    options = state.options

    string_keys = (
        "main_ui_language",
        "tooltip_language",
        "preset_shortcut_combo",
        "preset_shortcut_return_preset",
        "telemetry_relay_host",
        "dsx_host",
        "dsx_audio_device",
    )
    bool_keys = (
        "preset_shortcut_enabled",
        "telemetry_relay_enabled",
        "dsx_bridge_enabled",
        "dsx_audio_export_enabled",
    )
    int_keys = (
        "main_ui_scale",
        "telemetry_relay_port",
        "dsx_port",
        "dsx_audio_volume",
        "haptic_low_boost_gain",
    )

    for key in string_keys:
        if key in source:
            value = str(source[key])
            if key == "preset_shortcut_return_preset" and value not in PRESET_NAMES:
                value = "Base"
            setattr(options, key, value)
            restored.append(f"options.{key}")
    for key in bool_keys:
        if key in source:
            setattr(options, key, bool(source[key]))
            restored.append(f"options.{key}")
    for key in int_keys:
        if key not in source:
            continue
        try:
            value = int(source[key])
        except (TypeError, ValueError):
            continue
        if key == "dsx_audio_volume":
            value = max(0, min(100, value))
        elif key == "main_ui_scale":
            value = min((90, 100, 110, 125), key=lambda scale: abs(scale - value))
        elif key == "haptic_low_boost_gain":
            value = max(0, min(10, value))
        elif key in ("telemetry_relay_port", "dsx_port"):
            value = _clamp_udp_port(value)
        setattr(options, key, value)
        restored.append(f"options.{key}")
    options.preset_shortcut_pending_combo = options.preset_shortcut_combo
    options.preset_shortcut_capture_active = False
    return restored


def _apply_window(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    window = state.window
    if "x" in source and source["x"] is not None:
        try:
            window.x = max(-4000, min(8000, int(source["x"])))
            restored.append("window.x")
        except (TypeError, ValueError):
            pass
    if "y" in source and source["y"] is not None:
        try:
            window.y = max(-4000, min(8000, int(source["y"])))
            restored.append("window.y")
        except (TypeError, ValueError):
            pass
    if "width" in source:
        try:
            window.width = max(790, min(4000, int(source["width"])))
            restored.append("window.width")
        except (TypeError, ValueError):
            pass
    if "height" in source:
        try:
            window.height = max(544, min(3000, int(source["height"])))
            restored.append("window.height")
        except (TypeError, ValueError):
            pass
    return restored


def _apply_sound_to_haptic(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    sound = state.sound_to_haptic
    for key in ("capture_device", "highlighted_capture_device"):
        if key in source:
            setattr(sound, key, str(source[key]).strip())
            restored.append(f"sound_to_haptic.{key}")
    if "enabled" in source:
        sound.enabled = bool(source["enabled"])
        restored.append("sound_to_haptic.enabled")
    int_ranges = {
        "master_gain": (0, 100),
        "low_volume_cut": (0, 50),
        "high_cut_hz": (0, 24000),
        "dynamic_boost": (0, 300),
    }
    if "high_cut_hz" not in source and "boost_hz" in source:
        try:
            sound.high_cut_hz = max(0, min(24000, int(source["boost_hz"])))
            restored.append("sound_to_haptic.high_cut_hz")
        except (TypeError, ValueError):
            pass
    if "dynamic_boost" not in source and "boost_gain" in source:
        try:
            sound.dynamic_boost = max(0, min(300, 100 + int(source["boost_gain"]) * 20))
            restored.append("sound_to_haptic.dynamic_boost")
        except (TypeError, ValueError):
            pass
    for key, (minimum, maximum) in int_ranges.items():
        if key not in source:
            continue
        try:
            value = int(source[key])
        except (TypeError, ValueError):
            continue
        setattr(sound, key, max(minimum, min(maximum, value)))
        restored.append(f"sound_to_haptic.{key}")
    sound.running = False
    return restored


def _apply_hud(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    hud = state.hud
    try:
        layout_version = int(source.get("layout_version", 1))
    except (TypeError, ValueError):
        layout_version = 1
    legacy_layout = layout_version < HUD_LAYOUT_VERSION
    legacy_ui_factor = max(0.01, int(state.options.main_ui_scale) / 100.0)

    for key in ("standby_hide", "snap_enabled"):
        if key in source:
            setattr(hud, key, bool(source[key]))
            restored.append(f"hud.{key}")

    if "snap_pixel" in source:
        try:
            hud.snap_pixel = max(1, min(50, int(source["snap_pixel"])))
            restored.append("hud.snap_pixel")
        except (TypeError, ValueError):
            pass

    for key in ("speed_unit", "power_unit", "boost_unit"):
        if key in source:
            setattr(hud, key, str(source[key]))
            restored.append(f"hud.{key}")

    if "rpm_style" in source:
        rpm_style = str(source["rpm_style"])
        if rpm_style in ("Classic", "Modern", "Digital Bar"):
            hud.rpm_style = rpm_style
            restored.append("hud.rpm_style")
        else:
            hud.rpm_style = "Classic"
    else:
        # Settings created before selectable RPM styles used the Classic gauge.
        hud.rpm_style = "Classic"

    item_payload = source.get("items")
    if isinstance(item_payload, dict):
        for name in HUD_NAMES:
            if name not in item_payload or name not in hud.items:
                continue
            payload = item_payload[name]
            if not isinstance(payload, dict):
                continue
            item = hud.items[name]
            if "enabled" in payload:
                item.enabled = bool(payload["enabled"])
            if "scale" in payload:
                try:
                    scale = int(payload["scale"])
                    if legacy_layout:
                        scale = round(scale * legacy_ui_factor)
                    item.scale = max(50, min(200, scale))
                except (TypeError, ValueError):
                    pass
            if "opacity" in payload:
                try:
                    item.opacity = max(10, min(100, int(payload["opacity"])))
                except (TypeError, ValueError):
                    pass
            if "x" in payload and payload["x"] is not None:
                try:
                    x = int(payload["x"])
                    if legacy_layout:
                        x = round(x * legacy_ui_factor)
                    item.x = max(-8000, min(16000, x))
                except (TypeError, ValueError):
                    pass
            if "y" in payload and payload["y"] is not None:
                try:
                    y = int(payload["y"])
                    if legacy_layout:
                        y = round(y * legacy_ui_factor)
                    item.y = max(-8000, min(16000, y))
                except (TypeError, ValueError):
                    pass
            restored.append(f"hud.items.{name}")
    if legacy_layout:
        restored.append("hud.layout_version.migrated")
    else:
        restored.append("hud.layout_version")
    return restored


def _apply_dualsense_device(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    device = state.dualsense_device

    selected = source.get("selected_device")
    if isinstance(selected, str) and selected:
        device.selected_device = selected
        if selected not in device.registered_candidates:
            device.registered_candidates.insert(0, selected)
        restored.append("dualsense_device.selected_device")

    highlighted = source.get("highlighted_device")
    if isinstance(highlighted, str) and highlighted:
        device.highlighted_device = highlighted
        if highlighted not in device.registered_candidates:
            device.registered_candidates.insert(0, highlighted)
        restored.append("dualsense_device.highlighted_device")

    registered_candidates = source.get("registered_candidates")
    if isinstance(registered_candidates, list):
        for candidate in reversed(registered_candidates):
            if isinstance(candidate, str) and candidate and candidate not in device.registered_candidates:
                device.registered_candidates.insert(0, candidate)
        restored.append("dualsense_device.registered_candidates")

    last_test_result = source.get("last_test_result")
    if isinstance(last_test_result, str):
        device.last_test_result = last_test_result
        restored.append("dualsense_device.last_test_result")
    return restored


def _apply_telemetry(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    cards = source.get("cards")
    if not isinstance(cards, list):
        return restored

    for index, payload in enumerate(cards[: len(state.telemetry.cards)]):
        if not isinstance(payload, dict):
            continue
        card = state.telemetry.cards[index]
        name = payload.get("name")
        if isinstance(name, str) and index == len(state.telemetry.cards) - 1 and is_output_graph_item(name):
            card.name = name
        elif isinstance(name, str) and name in TELEMETRY_ITEMS:
            card.name = name
        elif isinstance(name, str) and name in ("Boost / Torque", "Drift / Slip"):
            card.name = name
        pattern = payload.get("pattern")
        try:
            card.pattern = max(0, min(3, int(pattern)))
        except (TypeError, ValueError):
            pass
        color_key = payload.get("color_key")
        if isinstance(color_key, str) and color_key in TELEMETRY_COLORS:
            card.color_key = color_key
        restored.append(f"telemetry.cards.{index}")
    return restored


def _apply_game_profile(profile: GameProfileState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored

    for preset_name in PRESET_NAMES:
        profile.presets.setdefault(preset_name, PresetState())

    selected_preset = source.get("selected_preset")
    if selected_preset in PRESET_NAMES:
        profile.selected_preset = selected_preset
        restored.append("selected_preset")

    restored.extend(_apply_effects(profile.haptic_effects, source.get("haptic_effects")))
    restored.extend(_apply_numeric(profile.haptic_advanced, source.get("haptic_advanced")))
    restored.extend(_apply_effects(profile.trigger_effects, source.get("trigger_effects")))
    restored.extend(_apply_numeric(profile.trigger_advanced, source.get("trigger_advanced")))

    presets = source.get("presets")
    if isinstance(presets, dict):
        for preset_name, preset_payload in presets.items():
            if preset_name not in PRESET_NAMES:
                continue
            preset = profile.presets.setdefault(preset_name, PresetState())
            preset_restored = _apply_preset_state(preset, preset_payload)
            if preset_restored:
                restored.extend(f"presets.{preset_name}.{name}" for name in preset_restored)
    else:
        preset = profile.presets.setdefault(profile.selected_preset, PresetState())
        preset.haptic_effects = clone_effect_settings(profile.haptic_effects)
        preset.haptic_advanced = clone_numeric_settings(profile.haptic_advanced)
        preset.trigger_effects = clone_effect_settings(profile.trigger_effects)
        preset.trigger_advanced = clone_numeric_settings(profile.trigger_advanced)
    return restored


def _apply_preset_state(preset: PresetState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    restored.extend(_apply_effects(preset.haptic_effects, source.get("haptic_effects")))
    restored.extend(_apply_numeric(preset.haptic_advanced, source.get("haptic_advanced")))
    restored.extend(_apply_effects(preset.trigger_effects, source.get("trigger_effects")))
    restored.extend(_apply_numeric(preset.trigger_advanced, source.get("trigger_advanced")))
    extra_haptic = source.get("extra_haptic_effects")
    if isinstance(extra_haptic, dict):
        preset.extra_haptic_effects = deepcopy(extra_haptic)
        restored.append("extra_haptic_effects")
    extra_trigger = source.get("extra_trigger_effects")
    if isinstance(extra_trigger, dict):
        preset.extra_trigger_effects = deepcopy(extra_trigger)
        restored.append("extra_trigger_effects")
    metadata = source.get("metadata")
    if isinstance(metadata, dict):
        preset.metadata = deepcopy(metadata)
        restored.append("metadata")
    return restored


def _preview_user_preset_payload(prefix: str, source: Any) -> list[str]:
    items: list[str] = []
    if not isinstance(source, dict):
        return items
    for section in ("haptic_effects", "haptic_advanced", "trigger_effects", "trigger_advanced"):
        payload = source.get(section)
        if not isinstance(payload, dict):
            continue
        for name in payload:
            items.append(f"{prefix}.{section}.{name}")
    return items


def list_recoverable_user_preset_items(snapshot: dict[str, Any]) -> list[str]:
    """List compatible user-preset settings without applying them."""
    items: list[str] = []
    game_profiles = snapshot.get("game_profiles")
    if isinstance(game_profiles, dict):
        for key, payload in game_profiles.items():
            try:
                game_mode = GameMode(key)
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            presets = payload.get("presets")
            if not isinstance(presets, dict):
                continue
            for preset_name in USER_PRESET_NAMES:
                items.extend(
                    _preview_user_preset_payload(
                        f"{game_mode.value}.{preset_name}",
                        presets.get(preset_name),
                    )
                )
    else:
        selected_preset = snapshot.get("selected_preset")
        if selected_preset in USER_PRESET_NAMES:
            legacy_payload = {
                "haptic_effects": snapshot.get("haptic_effects"),
                "haptic_advanced": snapshot.get("haptic_advanced"),
                "trigger_effects": snapshot.get("trigger_effects"),
                "trigger_advanced": snapshot.get("trigger_advanced"),
            }
            items.extend(_preview_user_preset_payload(f"legacy.{selected_preset}", legacy_payload))
    return items


def _apply_user_preset_payload(preset: PresetState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored
    for section, target, applier in (
        ("haptic_effects", preset.haptic_effects, _apply_effects),
        ("haptic_advanced", preset.haptic_advanced, _apply_numeric),
        ("trigger_effects", preset.trigger_effects, _apply_effects),
        ("trigger_advanced", preset.trigger_advanced, _apply_numeric),
    ):
        section_restored = applier(target, source.get(section))
        restored.extend(f"{section}.{name}" for name in section_restored)
    return restored


def apply_user_preset_recovery(state: AppState, snapshot: dict[str, Any]) -> list[str]:
    """Recover only user preset values from an older settings snapshot."""
    restored: list[str] = []
    game_profiles = snapshot.get("game_profiles")
    if isinstance(game_profiles, dict):
        for key, payload in game_profiles.items():
            try:
                game_mode = GameMode(key)
            except ValueError:
                continue
            if not isinstance(payload, dict):
                continue
            presets = payload.get("presets")
            if not isinstance(presets, dict):
                continue
            profile = state.game_profiles.setdefault(game_mode, GameProfileState())
            state.ensure_game_profile_presets(profile)
            for preset_name in USER_PRESET_NAMES:
                preset_payload = presets.get(preset_name)
                preset = profile.presets.setdefault(preset_name, PresetState())
                preset_restored = _apply_user_preset_payload(preset, preset_payload)
                restored.extend(f"{game_mode.value}.{preset_name}.{name}" for name in preset_restored)
    else:
        selected_preset = snapshot.get("selected_preset")
        if selected_preset in USER_PRESET_NAMES:
            profile = state.game_profiles.setdefault(state.game_mode, GameProfileState())
            state.ensure_game_profile_presets(profile)
            preset = profile.presets.setdefault(selected_preset, PresetState())
            legacy_payload = {
                "haptic_effects": snapshot.get("haptic_effects"),
                "haptic_advanced": snapshot.get("haptic_advanced"),
                "trigger_effects": snapshot.get("trigger_effects"),
                "trigger_advanced": snapshot.get("trigger_advanced"),
            }
            preset_restored = _apply_user_preset_payload(preset, legacy_payload)
            restored.extend(f"{state.game_mode.value}.{selected_preset}.{name}" for name in preset_restored)

    if state.selected_preset in USER_PRESET_NAMES:
        profile = state.game_profiles.setdefault(state.game_mode, GameProfileState())
        state.ensure_game_profile_presets(profile)
        active = profile.presets.setdefault(state.selected_preset, PresetState())
        state.haptic_effects = clone_effect_settings(active.haptic_effects)
        state.haptic_advanced = clone_numeric_settings(active.haptic_advanced)
        state.trigger_effects = clone_effect_settings(active.trigger_effects)
        state.trigger_advanced = clone_numeric_settings(active.trigger_advanced)
        profile.selected_preset = state.selected_preset
    return restored


def _apply_game_profiles(state: AppState, source: Any) -> list[str]:
    restored: list[str] = []
    if not isinstance(source, dict):
        return restored

    for key, payload in source.items():
        try:
            game_mode = GameMode(key)
        except ValueError:
            continue
        profile = state.game_profiles.setdefault(game_mode, GameProfileState())
        profile_restored = _apply_game_profile(profile, payload)
        if profile_restored:
            restored.extend(f"game_profiles.{key}.{name}" for name in profile_restored)
    return restored


def apply_app_state_snapshot(state: AppState, snapshot: dict[str, Any]) -> list[str]:
    """Apply compatible settings and return restored setting names."""
    restored: list[str] = []

    game_mode = snapshot.get("game_mode")
    if game_mode is not None:
        try:
            state.game_mode = GameMode(game_mode)
            restored.append("game_mode")
        except ValueError:
            pass

    selected_preset = snapshot.get("selected_preset")
    if selected_preset in PRESET_NAMES:
        state.selected_preset = selected_preset
        restored.append("selected_preset")

    ui_selection = snapshot.get("ui_selection")
    if isinstance(ui_selection, dict):
        selected_haptic = ui_selection.get("selected_haptic_effect")
        if isinstance(selected_haptic, str) and selected_haptic in state.haptic_effects:
            state.selected_haptic_effect = selected_haptic
            restored.append("ui_selection.selected_haptic_effect")
        selected_trigger = ui_selection.get("selected_trigger_effect")
        if isinstance(selected_trigger, str) and selected_trigger in state.trigger_effects:
            state.selected_trigger_effect = selected_trigger
            restored.append("ui_selection.selected_trigger_effect")

    if "udp_port" in snapshot:
        try:
            state.udp_port = _clamp_udp_port(int(snapshot["udp_port"]))
            restored.append("udp_port")
        except (TypeError, ValueError):
            pass

    restored.extend(_apply_effects(state.haptic_effects, snapshot.get("haptic_effects")))
    restored.extend(_apply_numeric(state.haptic_advanced, snapshot.get("haptic_advanced")))
    restored.extend(_apply_effects(state.trigger_effects, snapshot.get("trigger_effects")))
    restored.extend(_apply_numeric(state.trigger_advanced, snapshot.get("trigger_advanced")))
    restored.extend(_apply_window(state, snapshot.get("window")))
    restored.extend(_apply_options(state, snapshot.get("options")))
    restored.extend(_apply_hud(state, snapshot.get("hud")))
    restored.extend(_apply_dualsense_device(state, snapshot.get("dualsense_device")))
    restored.extend(_apply_sound_to_haptic(state, snapshot.get("sound_to_haptic")))
    restored.extend(_apply_telemetry(state, snapshot.get("telemetry")))
    profile_restored = _apply_game_profiles(state, snapshot.get("game_profiles"))
    if profile_restored:
        restored.extend(profile_restored)
        state.load_game_profile(state.game_mode)
    else:
        state.sync_current_game_profile()
    return restored


def summarize_snapshot(snapshot: dict[str, Any]) -> str:
    haptic_count = len(snapshot.get("haptic_effects", {}))
    trigger_count = len(snapshot.get("trigger_effects", {}))
    advanced_count = len(snapshot.get("haptic_advanced", {})) + len(
        snapshot.get("trigger_advanced", {})
    )
    option_count = len(snapshot.get("options", {}))
    hud_count = len(snapshot.get("hud", {}).get("items", {})) if isinstance(snapshot.get("hud"), dict) else 0
    device_count = 1 if isinstance(snapshot.get("dualsense_device"), dict) else 0
    telemetry_count = len(snapshot.get("telemetry", {}).get("cards", {})) if isinstance(snapshot.get("telemetry"), dict) else 0
    return (
        f"settings snapshot v{snapshot.get('app_version', 'unknown')} "
        f"prepared: {haptic_count} haptic effects, "
        f"{trigger_count} trigger effects, {advanced_count} advanced values, "
        f"{option_count} options, {hud_count} HUD items, "
        f"{device_count} device selection, {telemetry_count} telemetry cards; "
        f"{audit_snapshot_structure(snapshot).summary}"
    )


def _clamp_udp_port(value: int) -> int:
    return max(1, min(65535, int(value)))
