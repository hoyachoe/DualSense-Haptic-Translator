from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .app_state import GameMode, PRESET_NAMES, AppState, GameProfileState, PresetState
from .settings_model import EffectSetting, clamp_setting_value


PRESET_FILE_NAMES = {
    "Base": "base.json",
    "Soft": "soft.json",
    "Semi-Strong": "semi-strong.json",
    "Strong": "strong.json",
    "User 1": "user_1.json",
    "User 2": "user_2.json",
}

HAPTIC_SOURCE_ALIASES = {
    "Rev Limit": ("Rev Limit", "Rev limit"),
}

TRIGGER_SOURCE_ALIASES = {
    "Throttle Resistance - Traction": (
        "Throttle Resistance - Traction",
        "Throttle Resistance - Traction Limit",
    ),
}

REPRESENTATIVE_VALUE_KEYS = (
    "value",
    "volume",
    "strength",
    "force_percent",
    "pulse_strength",
    "kick_strong_pulse_strength",
)

CURRENT_TRIGGER_DEFAULT_DETAILS = {
    "Drift Rumble Fade": {
        "enabled": True,
        "value": 7,
        "volume": 7,
        "condition_strictness": 5,
        "wheelspin_buzz": 2,
        "throttle_pressure": 0,
        "throttle_traction": 0,
        "accel_g_punch": 3,
        "rpm_rev_limit": 8,
    },
}


@dataclass(frozen=True)
class PresetLoadReport:
    loaded_files: int
    missing_files: tuple[str, ...]
    source_root: Path

    @property
    def ok(self) -> bool:
        return self.loaded_files > 0 and not self.missing_files

    @property
    def summary(self) -> str:
        if self.loaded_files <= 0:
            return f"no built-in preset files loaded from {self.source_root}"
        if self.missing_files:
            return (
                f"loaded {self.loaded_files} built-in preset files; "
                f"{len(self.missing_files)} missing"
            )
        return f"loaded {self.loaded_files} built-in preset files"


def default_config_presets_root() -> Path:
    return Path(__file__).resolve().parent / "config_presets"


def load_builtin_presets_into_state(
    state: AppState,
    presets_root: Path | None = None,
) -> PresetLoadReport:
    root = presets_root or default_config_presets_root()
    loaded_files = 0
    missing_files: list[str] = []
    payloads_by_game: dict[GameMode, dict[str, dict[str, Any]]] = {}

    for game_mode in GameMode:
        profile_root = _profile_root(root, game_mode)
        payloads_by_game[game_mode] = {}

        for preset_name in PRESET_NAMES:
            file_name = PRESET_FILE_NAMES[preset_name]
            preset_path = profile_root / file_name
            if not preset_path.exists():
                missing_files.append(str(preset_path))
                continue
            payload = _read_json_object(preset_path)
            if payload is None:
                missing_files.append(str(preset_path))
                continue
            payloads_by_game[game_mode][preset_name] = payload
            loaded_files += 1

    for game_mode in GameMode:
        profile = state.game_profiles.setdefault(game_mode, GameProfileState())
        state.ensure_game_profile_presets(profile)

        for preset_name, payload in payloads_by_game.get(game_mode, {}).items():
            if preset_name not in PRESET_NAMES:
                continue
            preset = preset_from_legacy_payload(payload, profile.presets[preset_name])
            _complete_missing_current_details(
                preset,
                preset_name,
                game_mode,
                payloads_by_game,
            )
            profile.original_presets[preset_name] = deepcopy(preset)
            profile.presets[preset_name] = preset

    state.load_game_profile(state.game_mode)
    return PresetLoadReport(
        loaded_files=loaded_files,
        missing_files=tuple(missing_files),
        source_root=root,
    )


def preset_from_legacy_payload(payload: dict[str, Any], fallback: PresetState | None = None) -> PresetState:
    preset = deepcopy(fallback) if fallback is not None else PresetState()
    haptic_payloads = _dict_or_empty(payload.get("effects"))
    trigger_payloads = _dict_or_empty(payload.get("trigger_effects"))

    preset.haptic_effects = _apply_visible_effects(
        preset.haptic_effects,
        haptic_payloads,
        HAPTIC_SOURCE_ALIASES,
    )
    preset.trigger_effects = _apply_visible_effects(
        preset.trigger_effects,
        trigger_payloads,
        TRIGGER_SOURCE_ALIASES,
    )
    _apply_current_default_details(preset)
    preset.extra_haptic_effects = _extra_effect_payloads(
        haptic_payloads,
        preset.haptic_effects,
        HAPTIC_SOURCE_ALIASES,
    )
    preset.extra_trigger_effects = _extra_effect_payloads(
        trigger_payloads,
        preset.trigger_effects,
        TRIGGER_SOURCE_ALIASES,
    )
    preset.metadata = {
        "app_version": payload.get("app_version"),
        "save_version": payload.get("save_version"),
        "telemetry_game": payload.get("telemetry_game"),
        "source_schema": "legacy_config_presets",
    }
    return preset


def _profile_root(root: Path, game_mode: GameMode) -> Path:
    nested = root / game_mode.value
    if nested.exists():
        return nested
    return root


def _read_json_object(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8-sig") as handle:
            payload = json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def _dict_or_empty(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _apply_visible_effects(
    target: dict[str, EffectSetting],
    source: dict[str, Any],
    aliases: dict[str, tuple[str, ...]],
) -> dict[str, EffectSetting]:
    updated: dict[str, EffectSetting] = {}
    for display_name, fallback_setting in target.items():
        payload = _find_effect_payload(display_name, source, aliases)
        if payload is None:
            updated[display_name] = deepcopy(fallback_setting)
            continue
        updated[display_name] = _effect_setting_from_payload(payload, fallback_setting)
    return updated


def _find_effect_payload(
    display_name: str,
    source: dict[str, Any],
    aliases: dict[str, tuple[str, ...]],
) -> dict[str, Any] | None:
    candidate_names = aliases.get(display_name, (display_name,))
    for candidate in candidate_names:
        payload = source.get(candidate)
        if isinstance(payload, dict):
            return payload
    return None


def _effect_setting_from_payload(
    payload: dict[str, Any],
    fallback: EffectSetting,
) -> EffectSetting:
    return EffectSetting(
        value=_representative_value(payload, fallback.value),
        enabled=bool(payload.get("enabled", fallback.enabled)),
        details=deepcopy(payload),
    )


def _apply_current_default_details(preset: PresetState) -> None:
    for effect_name, default_details in CURRENT_TRIGGER_DEFAULT_DETAILS.items():
        setting = preset.trigger_effects.get(effect_name)
        if setting is None or setting.details:
            continue
        setting.details = deepcopy(default_details)
        setting.value = _representative_value(setting.details, setting.value)
        setting.enabled = bool(setting.details.get("enabled", setting.enabled))


def _complete_missing_current_details(
    preset: PresetState,
    preset_name: str,
    game_mode: GameMode,
    payloads_by_game: dict[GameMode, dict[str, dict[str, Any]]],
) -> None:
    _complete_missing_effect_details(
        preset.haptic_effects,
        "effects",
        HAPTIC_SOURCE_ALIASES,
        preset_name,
        game_mode,
        payloads_by_game,
    )
    _complete_missing_effect_details(
        preset.trigger_effects,
        "trigger_effects",
        TRIGGER_SOURCE_ALIASES,
        preset_name,
        game_mode,
        payloads_by_game,
    )
    _apply_current_default_details(preset)


def _complete_missing_effect_details(
    settings: dict[str, EffectSetting],
    section_name: str,
    aliases: dict[str, tuple[str, ...]],
    preset_name: str,
    game_mode: GameMode,
    payloads_by_game: dict[GameMode, dict[str, dict[str, Any]]],
) -> None:
    for effect_name, setting in settings.items():
        if setting.details:
            continue
        payload = _fallback_effect_payload(
            effect_name,
            section_name,
            aliases,
            preset_name,
            game_mode,
            payloads_by_game,
        )
        if payload is None:
            continue
        completed = _effect_setting_from_payload(payload, setting)
        setting.value = completed.value
        setting.enabled = completed.enabled
        setting.details = completed.details


def _fallback_effect_payload(
    effect_name: str,
    section_name: str,
    aliases: dict[str, tuple[str, ...]],
    preset_name: str,
    game_mode: GameMode,
    payloads_by_game: dict[GameMode, dict[str, dict[str, Any]]],
) -> dict[str, Any] | None:
    candidate_slots = (
        (game_mode, preset_name),
        (GameMode.HORIZON, preset_name),
        (game_mode, "Base"),
        (GameMode.HORIZON, "Base"),
        (game_mode, "User 2"),
        (GameMode.HORIZON, "User 2"),
    )
    seen: set[tuple[GameMode, str]] = set()
    for candidate_game, candidate_preset in candidate_slots:
        key = (candidate_game, candidate_preset)
        if key in seen:
            continue
        seen.add(key)
        payload = payloads_by_game.get(candidate_game, {}).get(candidate_preset)
        if not isinstance(payload, dict):
            continue
        section = _dict_or_empty(payload.get(section_name))
        found = _find_effect_payload(effect_name, section, aliases)
        if found is not None:
            return found
    return None


def _representative_value(payload: dict[str, Any], fallback: int) -> int:
    for key in REPRESENTATIVE_VALUE_KEYS:
        if key not in payload:
            continue
        value = payload[key]
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            continue
        if key in {"strength", "force_percent", "pulse_strength", "kick_strong_pulse_strength"}:
            return clamp_setting_value(round(numeric / 10.0))
        return clamp_setting_value(round(numeric))
    return clamp_setting_value(fallback)


def _extra_effect_payloads(
    source: dict[str, Any],
    visible: dict[str, EffectSetting],
    aliases: dict[str, tuple[str, ...]],
) -> dict[str, dict[str, Any]]:
    visible_source_names = set(visible)
    for display_name in visible:
        visible_source_names.update(aliases.get(display_name, (display_name,)))
    extras: dict[str, dict[str, Any]] = {}
    for name, payload in source.items():
        if name in visible_source_names:
            continue
        if not isinstance(payload, dict):
            continue
        extras[name] = deepcopy(payload)
    return extras
