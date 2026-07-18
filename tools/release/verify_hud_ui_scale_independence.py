from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dht_app.app_state import AppState  # noqa: E402
from dht_app.hud_geometry import (  # noqa: E402
    hud_canonical_value,
    hud_logical_value,
    normalized_main_ui_scale_factor,
)
from dht_app.settings_io import (  # noqa: E402
    HUD_LAYOUT_VERSION,
    apply_app_state_snapshot,
    export_app_state,
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _verify_geometry_is_ui_scale_independent() -> None:
    canonical_width = 280 * 1.2
    canonical_x = 437
    for percent in (90, 100, 110, 125):
        factor = normalized_main_ui_scale_factor(percent)
        logical_width = hud_logical_value(canonical_width, factor)
        logical_x = hud_logical_value(canonical_x, factor)
        _assert(
            abs(logical_width * factor - canonical_width) <= 0.63,
            f"HUD width changed at Main UI Scale {percent}%.",
        )
        _assert(
            abs(logical_x * factor - canonical_x) <= 0.63,
            f"HUD position changed at Main UI Scale {percent}%.",
        )
        _assert(
            abs(hud_canonical_value(logical_x, factor) - canonical_x) <= 1,
            f"HUD coordinate round-trip failed at Main UI Scale {percent}%.",
        )


def _verify_legacy_layout_migration() -> None:
    legacy_state = AppState()
    legacy_state.options.main_ui_scale = 125
    legacy_item = legacy_state.hud.items["RPM"]
    legacy_item.scale = 80
    legacy_item.x = 160
    legacy_item.y = 240
    legacy_snapshot = export_app_state(legacy_state)
    legacy_snapshot["hud"].pop("layout_version")

    restored_state = AppState()
    restored = apply_app_state_snapshot(restored_state, legacy_snapshot)
    item = restored_state.hud.items["RPM"]
    _assert(item.scale == 100, "Legacy HUD scale did not preserve its physical size.")
    _assert((item.x, item.y) == (200, 300), "Legacy HUD position was not migrated.")
    _assert("hud.layout_version.migrated" in restored, "Migration was not reported.")

    factor = normalized_main_ui_scale_factor(restored_state.options.main_ui_scale)
    _assert(hud_logical_value(item.x, factor) == 160, "Migrated X moved on first launch.")
    _assert(hud_logical_value(item.y, factor) == 240, "Migrated Y moved on first launch.")
    _assert(
        hud_logical_value(280 * item.scale / 100.0, factor) == 224,
        "Migrated HUD size moved on first launch.",
    )


def _verify_current_layout_is_not_migrated_twice() -> None:
    state = AppState()
    state.options.main_ui_scale = 125
    item = state.hud.items["RPM"]
    item.scale = 100
    item.x = 200
    item.y = 300
    snapshot = export_app_state(state)
    _assert(
        snapshot["hud"]["layout_version"] == HUD_LAYOUT_VERSION,
        "Current HUD layout marker was not exported.",
    )

    first = AppState()
    apply_app_state_snapshot(first, deepcopy(snapshot))
    first_snapshot = export_app_state(first)
    second = AppState()
    apply_app_state_snapshot(second, first_snapshot)
    first_item = first.hud.items["RPM"]
    second_item = second.hud.items["RPM"]
    _assert(
        (first_item.scale, first_item.x, first_item.y)
        == (second_item.scale, second_item.x, second_item.y)
        == (100, 200, 300),
        "Current HUD layout was migrated more than once.",
    )


def main() -> int:
    _verify_geometry_is_ui_scale_independent()
    _verify_legacy_layout_migration()
    _verify_current_layout_is_not_migrated_twice()
    print("HUD UI-scale independence verification passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
