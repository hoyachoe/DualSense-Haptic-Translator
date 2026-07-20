from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dht_app.app_state import (  # noqa: E402
    PRESET_NAMES,
    AppState,
    GameMode,
    default_output_graph_item,
)
from dht_app.preset_loader import load_builtin_presets_into_state  # noqa: E402
from dht_app.settings_io import (  # noqa: E402
    PRESET_CONTENT_KEYS,
    apply_app_state_snapshot,
    export_app_state,
    preserve_saved_preset_content,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _verify_safe_first_run_defaults() -> None:
    state = AppState()
    _assert(state.hud.rpm_style == "Digital Bar", "Digital Bar is not the first-run RPM style.")
    _assert(not any(item.enabled for item in state.hud.items.values()), "A HUD overlay is enabled on first run.")
    _assert(not state.sound_to_haptic.enabled, "Sound To Haptic is enabled on first run.")
    _assert(not state.options.dsx_bridge_enabled, "DSX bridge is enabled on first run.")
    _assert(not state.options.dsx_audio_export_enabled, "DSX audio export is enabled on first run.")
    _assert(not state.options.telemetry_relay_enabled, "Telemetry relay is enabled on first run.")
    _assert(not state.dualsense_device.selected_device, "A personal DualSense device is a default.")
    _assert(
        default_output_graph_item() == "Haptic: Tire Limit Load",
        "Telemetry output card is not Tire Limit Load by default.",
    )


def _verify_legacy_rpm_compatibility() -> None:
    snapshot = export_app_state(AppState())
    snapshot["hud"].pop("rpm_style", None)
    restored = AppState()
    apply_app_state_snapshot(restored, snapshot)
    _assert(restored.hud.rpm_style == "Classic", "Legacy settings did not preserve Classic RPM.")


def _verify_public_preset_defaults() -> None:
    state = AppState()
    report = load_builtin_presets_into_state(state)
    _assert(report.loaded_files == 12 and not report.missing_files, report.summary)

    horizon = state.game_profiles[GameMode.HORIZON]
    base_predictive = horizon.presets["Base"].trigger_effects[
        "Brake Resistance - Predictive"
    ].details
    expected_predictive = {
        "force_percent": 50,
        "slip_pulse_start_percent": 50,
        "slip_pulse_end_percent": 110,
    }
    actual_predictive = {
        key: base_predictive.get(key)
        for key in expected_predictive
    }
    _assert(
        actual_predictive == expected_predictive,
        f"Horizon Base predictive brake defaults differ: {actual_predictive}",
    )

    for preset_name in ("Base", "Soft", "Semi-Strong"):
        impact_tick = horizon.presets[preset_name].trigger_effects["Impact Tick"]
        _assert(not impact_tick.enabled, f"Horizon {preset_name} Impact Tick is enabled.")
        _assert(
            impact_tick.details.get("enabled") is False,
            f"Horizon {preset_name} Impact Tick detail state is enabled.",
        )
    _assert(
        horizon.presets["Strong"].trigger_effects["Impact Tick"].enabled,
        "Horizon Strong Impact Tick changed outside the approved current defaults.",
    )

    for game_mode in GameMode:
        profile = state.game_profiles[game_mode]
        for preset_name in PRESET_NAMES:
            preset = profile.presets[preset_name]
            _assert(
                "Impact - Smashable" in preset.haptic_effects,
                f"{game_mode.value}/{preset_name} is missing public Smashable settings.",
            )
            _assert(
                "Impact - Smashable" not in preset.extra_haptic_effects,
                f"{game_mode.value}/{preset_name} retained stale Smashable extra data.",
            )

    active = deepcopy(horizon.presets["Base"])
    _assert(
        active.trigger_effects["Brake Resistance - Predictive"].details["force_percent"] == 50,
        "Approved Base trigger defaults were not loaded into the active preset.",
    )


def _verify_preset_save_button_policy() -> None:
    state = AppState()
    report = load_builtin_presets_into_state(state)
    _assert(not report.missing_files, report.summary)
    saved_snapshot = export_app_state(state)

    state.set_haptic_effect_value("Road Bumps", 1)
    state.set_haptic_detail_value("volume", 2)
    haptic_advanced_name = next(iter(state.haptic_advanced))
    state.set_haptic_advanced_value(haptic_advanced_name, 3)
    state.set_trigger_effect_value("Brake Resistance - Predictive", 4)
    state.set_trigger_detail_value("force_percent", 5)
    trigger_advanced_name = next(iter(state.trigger_advanced))
    state.set_trigger_advanced_value(trigger_advanced_name, 6)
    state.set_preset("Strong")
    state.toggle_haptic_effect("Road Bumps")
    state.toggle_trigger_effect("Impact Tick")
    state.set_game_mode(GameMode.MOTORSPORT)
    state.set_preset("User 1")
    state.set_haptic_effect_value("Road Bumps", 7)
    state.options.main_ui_scale = 125
    state.hud.standby_hide = not state.hud.standby_hide

    current_snapshot = export_app_state(state)
    merged = preserve_saved_preset_content(current_snapshot, saved_snapshot)

    _assert(
        merged["options"]["main_ui_scale"] == 125,
        "A preference-only save discarded the current Main UI scale.",
    )
    _assert(
        merged["hud"]["standby_hide"] == current_snapshot["hud"]["standby_hide"],
        "A preference-only save discarded the current HUD preference.",
    )
    _assert(
        merged["game_mode"] == current_snapshot["game_mode"]
        and merged["selected_preset"] == current_snapshot["selected_preset"],
        "A preference-only save discarded the current game or preset selection.",
    )

    for game_mode in GameMode:
        game_key = game_mode.value
        current_profile = current_snapshot["game_profiles"][game_key]
        merged_profile = merged["game_profiles"][game_key]
        saved_profile = saved_snapshot["game_profiles"][game_key]
        _assert(
            merged_profile["selected_preset"] == current_profile["selected_preset"],
            f"{game_key} preset selection was not preserved.",
        )
        _assert(
            merged_profile["presets"] == saved_profile["presets"],
            f"{game_key} unsaved preset slots leaked into a preference-only save.",
        )
        selected_saved = saved_profile["presets"][merged_profile["selected_preset"]]
        for key in PRESET_CONTENT_KEYS:
            _assert(
                merged_profile[key] == selected_saved[key],
                f"{game_key} active {key} did not return to the last SAVE payload.",
            )

    active_profile = merged["game_profiles"][merged["game_mode"]]
    for key in PRESET_CONTENT_KEYS:
        _assert(
            merged[key] == active_profile[key],
            f"Top-level {key} disagrees with the selected saved preset.",
        )

    _assert(state.preset_unsaved_changes, "Preset edits were not marked separately as dirty.")
    state.mark_preferences_saved()
    _assert(
        state.unsaved_changes and state.preset_unsaved_changes,
        "Saving preferences incorrectly cleared pending preset edits.",
    )
    state.mark_settings_saved()
    _assert(
        not state.unsaved_changes and not state.preset_unsaved_changes,
        "Explicit settings SAVE did not clear the preset dirty state.",
    )


def main() -> int:
    _verify_safe_first_run_defaults()
    _verify_legacy_rpm_compatibility()
    _verify_public_preset_defaults()
    _verify_preset_save_button_policy()
    print("Release defaults and clean first-run policy verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
