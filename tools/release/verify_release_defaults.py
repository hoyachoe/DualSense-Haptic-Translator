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
from dht_app.settings_io import apply_app_state_snapshot, export_app_state  # noqa: E402


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


def main() -> int:
    _verify_safe_first_run_defaults()
    _verify_legacy_rpm_compatibility()
    _verify_public_preset_defaults()
    print("Release defaults and clean first-run policy verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
