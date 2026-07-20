from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QLabel, QPushButton  # noqa: E402

from dht_app import runtime_execution_guard, settings_store  # noqa: E402
from dht_app.app_shell import MainWindow  # noqa: E402
from dht_app.app_state import AppState  # noqa: E402
from dht_app.settings_io import apply_app_state_snapshot, export_app_state  # noqa: E402
from dht_app.tooltip_texts import action_tooltip, option_tooltip  # noqa: E402
from dht_app.ui_texts import ui_text  # noqa: E402
from dht_app.ui_widgets import OptionCard, ToggleButton  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _disable_background_inputs() -> None:
    MainWindow._start_telemetry_receiver = lambda self: None
    MainWindow._start_dualsense_input_receiver = lambda self: None
    MainWindow._maybe_auto_refresh_dualsense_page = lambda self: None


def _shortcut_buttons(window: MainWindow, shortcut_name: str) -> dict[str, QPushButton]:
    _assert(window.content_layout is not None and window.content_layout.count() == 1, "Options page is missing.")
    page = window.content_layout.itemAt(0).widget()
    _assert(page is not None, "Options page widget is missing.")
    result: dict[str, QPushButton] = {}
    for button in page.findChildren(QPushButton):
        if button.property("shortcutKind") != shortcut_name:
            continue
        action = str(button.property("shortcutAction") or "")
        if action:
            result[action] = button
    _assert(set(result) == {"capture", "apply", "delete"}, f"Incomplete {shortcut_name} shortcut row: {result}")
    return result


def _verify_compact_two_row_ui(window: MainWindow, app: QApplication) -> None:
    window._set_page("options")
    app.processEvents()
    page = window.content_layout.itemAt(0).widget()
    cards = page.findChildren(OptionCard)
    gamepad_cards = [
        card
        for card in cards
        if any(label.text() == "Gamepad Shortcut" for label in card.findChildren(QLabel))
    ]
    _assert(len(gamepad_cards) == 1, "Options does not contain exactly one Gamepad Shortcut card.")
    card = gamepad_cards[0]
    labels = {label.text() for label in card.findChildren(QLabel)}
    _assert("Preset Shortcut" in labels, "Preset Shortcut row label is missing.")
    _assert("HUD ON/OFF Shortcut" in labels, "HUD ON/OFF Shortcut row label is missing.")
    _assert(not card.findChildren(ToggleButton), "The obsolete preset shortcut ON/OFF switch is still visible.")

    preset = _shortcut_buttons(window, "preset")
    hud = _shortcut_buttons(window, "hud")
    _assert(preset["capture"].width() == 100, "Preset shortcut field was not reduced to 100 px.")
    _assert(hud["capture"].width() == 100, "HUD shortcut field was not reduced to 100 px.")
    _assert(hud["capture"].text() == "None", "An unassigned HUD shortcut is not displayed as None.")


def _verify_capture_apply_and_runtime(window: MainWindow, app: QApplication) -> None:
    options = window.state.options
    window._begin_gamepad_shortcut_capture("hud")
    _assert(options.hud_shortcut_capture_active, "HUD shortcut capture did not start.")
    _assert(not options.preset_shortcut_capture_active, "Starting HUD capture left Preset capture active.")
    _assert(
        window._handle_dualsense_button_status({"l1": 1, "r3": 1}, 1.0),
        "HUD shortcut capture ignored the DualSense combination.",
    )
    window._gamepad_shortcut_capture_timer.stop()
    window._finish_gamepad_shortcut_capture()
    _assert(options.hud_shortcut_pending_combo == "L1+R3", "HUD shortcut capture normalized incorrectly.")
    window._apply_gamepad_shortcut("hud")
    _assert(options.hud_shortcut_combo == "L1+R3", "HUD shortcut did not apply.")

    rpm_item = window.state.hud.items["RPM"]
    rpm_item.enabled = True
    configured_enabled = rpm_item.enabled
    window.state.hud.standby_hide = False
    window.state.hud.shortcut_hidden = False
    window.refresh_shell_state()
    app.processEvents()
    rpm_overlay = next(overlay for overlay in window.hud_overlays if overlay.HUD_NAME == "RPM")
    _assert(rpm_overlay.isVisible(), "Enabled RPM HUD was not visible before the HUD shortcut test.")

    window._handle_dualsense_button_status({}, 2.0)
    _assert(
        window._handle_dualsense_button_status({"l1": 1, "r3": 1}, 3.0),
        "HUD shortcut did not trigger.",
    )
    app.processEvents()
    _assert(window.state.hud.shortcut_hidden, "HUD shortcut did not switch overlays OFF.")
    _assert(not rpm_overlay.isVisible(), "HUD shortcut left an enabled overlay visible.")
    _assert(rpm_item.enabled == configured_enabled, "HUD shortcut changed the saved per-HUD enabled state.")

    window._handle_dualsense_button_status({}, 3.2)
    window._handle_dualsense_button_status({"l1": 1, "r3": 1}, 4.0)
    app.processEvents()
    _assert(not window.state.hud.shortcut_hidden, "Second HUD shortcut press did not switch overlays ON.")
    _assert(rpm_overlay.isVisible(), "Second HUD shortcut press did not restore the enabled overlay.")

    window._handle_dualsense_button_status({}, 4.2)
    window.state.set_preset("Base")
    _assert(
        window._handle_dualsense_button_status({"r1": 1, "r3": 1}, 5.0),
        "Preset shortcut did not trigger.",
    )
    _assert(window.state.selected_preset == "User 2", "Preset shortcut did not switch to User 2.")
    window._handle_dualsense_button_status({}, 5.2)
    window._handle_dualsense_button_status({"r1": 1, "r3": 1}, 6.0)
    _assert(window.state.selected_preset == "Base", "Second Preset shortcut press did not return.")


def _verify_delete_and_reassignment(window: MainWindow, app: QApplication) -> None:
    window._set_page("options")
    app.processEvents()
    hud_buttons = _shortcut_buttons(window, "hud")
    window.state.hud.shortcut_hidden = True
    hud_buttons["delete"].click()
    app.processEvents()
    _assert(window.state.options.hud_shortcut_combo == "", "HUD Delete did not clear the saved shortcut.")
    _assert(not window.state.hud.shortcut_hidden, "Deleting the HUD shortcut left overlays locked OFF.")
    _assert(_shortcut_buttons(window, "hud")["capture"].text() == "None", "HUD Delete did not show None.")

    window.state.options.hud_shortcut_combo = "L1+R3"
    window.state.options.hud_shortcut_pending_combo = "L1+R3"
    window.state.options.preset_shortcut_pending_combo = "L1+R3"
    window._apply_gamepad_shortcut("preset")
    _assert(window.state.options.preset_shortcut_combo == "L1+R3", "Preset shortcut reassignment failed.")
    _assert(window.state.options.hud_shortcut_combo == "", "Duplicate shortcut remained assigned to HUD.")

    window._set_page("options")
    app.processEvents()
    _shortcut_buttons(window, "preset")["delete"].click()
    app.processEvents()
    _assert(window.state.options.preset_shortcut_combo == "", "Preset Delete did not clear the shortcut.")
    _assert(not window.state.options.preset_shortcut_enabled, "Legacy enabled value was not synchronized with None.")
    _assert(_shortcut_buttons(window, "preset")["capture"].text() == "None", "Preset Delete did not show None.")


def _verify_settings_compatibility() -> None:
    source = AppState()
    source.options.hud_shortcut_combo = "L1+L3"
    snapshot = export_app_state(source)
    _assert(snapshot["options"]["hud_shortcut_combo"] == "L1+L3", "HUD shortcut was not exported.")
    restored = AppState()
    apply_app_state_snapshot(restored, snapshot)
    _assert(restored.options.hud_shortcut_combo == "L1+L3", "HUD shortcut did not round-trip.")
    _assert(restored.options.hud_shortcut_pending_combo == "L1+L3", "HUD pending shortcut was not initialized.")

    legacy = export_app_state(AppState())
    legacy["options"].pop("hud_shortcut_combo", None)
    legacy["options"]["preset_shortcut_enabled"] = False
    legacy["options"]["preset_shortcut_combo"] = "R1+R3"
    migrated = AppState()
    apply_app_state_snapshot(migrated, legacy)
    _assert(migrated.options.preset_shortcut_combo == "", "Legacy shortcut OFF did not migrate to None.")
    _assert(not migrated.options.preset_shortcut_enabled, "Legacy shortcut enable state did not migrate.")


def _verify_localized_text() -> None:
    _assert(ui_text("Gamepad Shortcut", "ES") == "Atajos del gamepad", "Spanish card title is missing.")
    for language in ("KR", "CN", "ES"):
        _assert(option_tooltip("Gamepad Shortcut", language), f"{language} Gamepad option tooltip is missing.")
        for key in (
            "preset_shortcut_capture",
            "preset_shortcut_apply",
            "preset_shortcut_delete",
            "hud_shortcut_capture",
            "hud_shortcut_apply",
            "hud_shortcut_delete",
        ):
            _assert(action_tooltip(key, language), f"{language} tooltip is missing: {key}")


def main() -> int:
    _disable_background_inputs()
    app = QApplication.instance() or QApplication(["verify_gamepad_shortcuts"])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="dht_gamepad_shortcuts_") as directory:
        root = Path(directory)
        runtime_execution_guard.PUBLIC_RELEASE_MARKER = root / "PUBLIC_RELEASE"
        runtime_execution_guard.PUBLIC_RELEASE_MARKER.write_text("public\n", encoding="ascii")
        settings_store.app_root_dir = lambda: root
        window = MainWindow()
        try:
            _verify_compact_two_row_ui(window, app)
            _verify_capture_apply_and_runtime(window, app)
            _verify_delete_and_reassignment(window, app)
            settings_path = settings_store.settings_file_path(root)
            _assert(settings_path.is_file(), "Shortcut Apply/Delete did not save settings.")
            saved = json.loads(settings_path.read_text(encoding="utf-8"))
            _assert(saved["options"]["preset_shortcut_combo"] == "", "Saved Preset shortcut is not None/empty.")
            _assert(saved["options"]["hud_shortcut_combo"] == "", "Saved HUD shortcut is not None/empty.")
        finally:
            window.close()
            app.processEvents()
    _verify_settings_compatibility()
    _verify_localized_text()
    app.quit()
    print("Gamepad shortcut UI, capture, delete, persistence, and HUD visibility verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
