from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ["DHT_DEVELOPER_MODE"] = "1"
os.environ["DHT_ENABLE_REAL_OUTPUT_TEST"] = "1"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QAbstractButton, QPushButton  # noqa: E402

from dht_app import runtime_execution_guard, settings_store  # noqa: E402
from dht_app.app_shell import MainWindow  # noqa: E402
from dht_app.app_state import HUD_NAMES, PRESET_NAMES, AppState, GameMode, PacketStatus  # noqa: E402
from dht_app.detail_schema import TRIGGER_DETAIL_GROUPS  # noqa: E402
from dht_app.hud_overlay import PresetHudOverlay, RpmHudOverlay  # noqa: E402
from dht_app.pages_hud import build_hud_dashboard_page  # noqa: E402
from dht_app.settings_io import (  # noqa: E402
    SNAPSHOT_SCHEMA,
    compare_snapshot_schema,
    export_app_state,
)
from dht_app.telemetry_frame import TelemetryFrame  # noqa: E402
from dht_app.trigger_effect_engine import TriggerEffectEngine, TriggerPulseOutput  # noqa: E402
from dht_app.ui_theme import APP_TITLE  # noqa: E402
from dht_app.ui_widgets import HudRow, SliderRow, TriggerToggleRow  # noqa: E402
from dht_app.version import APP_VERSION  # noqa: E402


FORBIDDEN_PUBLIC_TEXT = (
    "Debug Haptic",
    "Debug Trigger",
    "Developer real-output test mode",
    "Inject Test Packet",
    "Real Output Test",
    "Stop Test",
)


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _widget_text(window: MainWindow) -> str:
    values: list[str] = []
    for widget_type in (QLabel, QAbstractButton):
        for widget in window.findChildren(widget_type):
            text = widget.text().strip()
            if text:
                values.append(text)
    return "\n".join(values)


def _disable_background_inputs() -> None:
    MainWindow._start_telemetry_receiver = lambda self: None
    MainWindow._start_dualsense_input_receiver = lambda self: None
    MainWindow._maybe_auto_refresh_dualsense_page = lambda self: None


def _current_standby_button(window: MainWindow) -> QPushButton:
    _assert(window.content_layout is not None and window.content_layout.count() == 1, "HUD page layout is missing.")
    page = window.content_layout.itemAt(0).widget()
    _assert(page is not None, "HUD page widget is missing.")
    matches = [
        button
        for button in page.findChildren(QPushButton)
        if button.text().startswith("Standby Hide")
    ]
    _assert(len(matches) == 1, f"Expected one current Standby Hide button, found {len(matches)}.")
    return matches[0]


def _verify_standby_button_first_click(window: MainWindow, app: QApplication) -> None:
    window._set_page("hud")
    app.processEvents()
    first_page = window.content_layout.itemAt(0).widget()
    button = _current_standby_button(window)
    _assert(not window.state.hud.standby_hide and button.text() == "Standby Hide OFF", "Standby Hide did not start OFF.")

    button.click()
    app.processEvents()
    _assert(first_page.isHidden(), "The replaced HUD page remained visible over the first-click result.")
    button = _current_standby_button(window)
    _assert(window.state.hud.standby_hide and button.text() == "Standby Hide ON", "The first click did not visibly switch Standby Hide ON.")

    button.click()
    app.processEvents()
    button = _current_standby_button(window)
    _assert(not window.state.hud.standby_hide and button.text() == "Standby Hide OFF", "The second click did not switch Standby Hide OFF.")


def _verify_packet_refresh_preserves_live_controls(window: MainWindow, app: QApplication) -> None:
    from dht_app.telemetry_test_packets import build_test_telemetry_packet

    window._set_page("telemetry")
    app.processEvents()
    telemetry_page = window.content_layout.itemAt(0).widget()
    _assert(telemetry_page is not None, "Telemetry page widget is missing.")
    cards = telemetry_page.telemetry_card_widgets
    _assert(len(cards) == len(window.state.telemetry.cards), "Telemetry live card references are incomplete.")

    first_card = cards[0]
    window._last_telemetry_page_render_at = 0.0
    window.telemetry_receiver.push_test_packet(build_test_telemetry_packet(window.state.game_mode, 1))
    window._poll_telemetry_receiver()
    app.processEvents()
    _assert(window.content_layout.itemAt(0).widget() is telemetry_page, "Telemetry packet refresh replaced the page.")
    _assert(telemetry_page.telemetry_card_widgets[0] is first_card, "Telemetry packet refresh replaced a card control.")
    first_name = window.state.telemetry.cards[0].name
    _assert(
        first_card.value_label.text() == window.state.telemetry.display_value_for(first_name),
        "Telemetry value did not refresh in place.",
    )
    _assert(
        first_card.graph_preview.live_samples == window.state.telemetry.samples_for(first_name),
        "Telemetry graph did not refresh in place.",
    )

    window._set_page("hud")
    app.processEvents()
    hud_page = window.content_layout.itemAt(0).widget()
    button = _current_standby_button(window)
    _assert(not window.state.hud.standby_hide, "Standby Hide must start OFF for the press/release test.")
    QTest.mousePress(button, Qt.LeftButton)
    for tick in range(2, 7):
        idle_packet = bytearray(build_test_telemetry_packet(window.state.game_mode, tick))
        idle_packet[:4] = (0).to_bytes(4, byteorder="little", signed=True)
        window.telemetry_receiver.push_test_packet(idle_packet)
        window._poll_telemetry_receiver()
        app.processEvents()
    _assert(window.content_layout.itemAt(0).widget() is hud_page, "HUD packet refresh replaced the page during a click.")
    _assert(_current_standby_button(window) is button, "HUD packet refresh replaced the pressed button.")
    QTest.mouseRelease(button, Qt.LeftButton)
    app.processEvents()
    _assert(window.state.hud.standby_hide, "A telemetry refresh interrupted the HUD button click.")

    button = _current_standby_button(window)
    button.click()
    app.processEvents()
    _assert(not window.state.hud.standby_hide, "The packet-refresh test did not restore Standby Hide OFF.")


def _verify_trigger_preset_defaults_and_group_order(window: MainWindow) -> None:
    expected = {
        "start_percent": 20,
        "max_percent": 70,
        "wall_percent": 35,
        "slip_threshold": 7,
        "slip_drop_low_percent": 1,
    }
    for game_mode in GameMode:
        profile = window.state.game_profiles[game_mode]
        for preset_name in PRESET_NAMES:
            details = profile.presets[preset_name].trigger_effects["Brake Resistance - Predictive"].details
            actual = {key: details.get(key) for key in expected}
            _assert(
                actual == expected,
                f"{game_mode.value} {preset_name} predictive brake defaults differ: {actual}",
            )

    for effect_name, groups in TRIGGER_DETAIL_GROUPS.items():
        titles = [title for title, _keys in groups]
        if "Soft Pulse" not in titles or "Strong Pulse" not in titles:
            continue
        _assert(
            titles.index("Soft Pulse") < titles.index("Strong Pulse"),
            f"{effect_name} shows Strong Pulse controls before Soft Pulse controls.",
        )


def _layout_contains_widget(layout, target) -> bool:
    for index in range(layout.count()):
        item = layout.itemAt(index)
        widget = item.widget()
        if widget is not None and (widget is target or widget.isAncestorOf(target)):
            return True
        child_layout = item.layout()
        if child_layout is not None and _layout_contains_widget(child_layout, target):
            return True
    return False


def _verify_effect_sliders_survive_continuous_edit(window: MainWindow, app: QApplication) -> None:
    effect_name = "Road Bumps"
    window._set_page("haptic")
    app.processEvents()
    rows = [row for row in window.findChildren(SliderRow) if row.effect_name == effect_name]
    _assert(len(rows) == 1, f"Expected one {effect_name} slider row, found {len(rows)}.")
    row = rows[0]
    slider = row.slider
    values = [value for value in range(slider.minimum(), slider.maximum() + 1) if value != slider.value()][:2]
    _assert(len(values) == 2, f"Could not choose continuous edit values for {effect_name}.")

    slider.sliderPressed.emit()
    slider.setValue(values[0])
    app.processEvents()
    _assert(
        _layout_contains_widget(window.content_layout, slider),
        f"{effect_name} slider was replaced after the first drag value.",
    )
    slider.setValue(values[1])
    app.processEvents()
    _assert(
        _layout_contains_widget(window.content_layout, slider),
        f"{effect_name} slider was replaced before drag release.",
    )
    _assert(window.state.haptic_effects[effect_name].value == values[1], f"{effect_name} did not accept values.")
    _assert(row.value_badge.text() == str(values[1]), f"{effect_name} badge did not track the drag value.")

    slider.sliderReleased.emit()
    app.processEvents()
    _assert(
        not _layout_contains_widget(window.content_layout, slider),
        f"{effect_name} did not refresh its detail panel after drag release.",
    )
    _assert(window.state.haptic_effects[effect_name].value == values[1], f"{effect_name} lost its released value.")


def _verify_trigger_toggle_description_rows(window: MainWindow, app: QApplication) -> None:
    window._set_page("trigger")
    app.processEvents()
    rows = window.findChildren(TriggerToggleRow)
    _assert(len(rows) == len(window.state.trigger_effects), "Trigger list does not contain one row per effect.")
    _assert(
        {row.effect_name for row in rows} == set(window.state.trigger_effects),
        "Trigger toggle rows do not match the public trigger effects.",
    )
    for row in rows:
        descriptions = [label for label in row.findChildren(QLabel) if label.objectName() == "TriggerDescription"]
        _assert(len(descriptions) == 1 and descriptions[0].text().strip(), f"{row.effect_name} description is missing.")
        _assert(not hasattr(row, "slider"), f"{row.effect_name} still exposes a list strength slider.")
        _assert(not row.toolTip(), f"{row.effect_name} still exposes an effect-list tooltip.")

    test_name = "Impact Tick"
    test_row = next(row for row in rows if row.effect_name == test_name)
    original_enabled = window.state.trigger_effects[test_name].enabled
    QTest.mouseClick(test_row.toggle, Qt.LeftButton)
    app.processEvents()
    _assert(
        window.state.trigger_effects[test_name].enabled is not original_enabled,
        "Trigger ON/OFF switch did not change state on the first click.",
    )
    refreshed_row = next(row for row in window.findChildren(TriggerToggleRow) if row.effect_name == test_name)
    _assert(
        refreshed_row.toggle.isChecked() == window.state.trigger_effects[test_name].enabled,
        "Refreshed trigger switch does not reflect the stored state.",
    )
    QTest.mouseClick(refreshed_row.toggle, Qt.LeftButton)
    app.processEvents()
    _assert(
        window.state.trigger_effects[test_name].enabled is original_enabled,
        "Trigger ON/OFF switch did not restore its original state.",
    )


def _verify_clean_first_run(temp_root: Path, app: QApplication) -> None:
    temp_root.mkdir(parents=True, exist_ok=True)
    runtime_execution_guard.PUBLIC_RELEASE_MARKER = temp_root / "PUBLIC_RELEASE"
    runtime_execution_guard.PUBLIC_RELEASE_MARKER.write_text(
        "automated public first-run verification\n",
        encoding="ascii",
    )
    settings_store.app_root_dir = lambda: temp_root

    window = MainWindow()
    app.processEvents()
    _assert(window.windowTitle() == APP_TITLE == "DualSense Haptic Translator", "Public window title is not final.")
    _assert(window.current_page == "select_dualsense", "Clean first run must open Select DualSense.")
    _assert(not window.developer_mode, "Public marker did not force developer mode off.")
    _assert(window.state.udp_port == 8800, "Clean first-run UDP port must be 8800.")
    _assert(not window.state.dualsense_device.selected_device, "Clean first run restored a device unexpectedly.")
    _assert(not window.state.options.dsx_audio_device, "Clean first run contains a personal DSX audio device.")
    _assert(
        not any(overlay.isVisible() for overlay in window.hud_overlays),
        "A HUD overlay opened automatically on clean first run.",
    )
    _assert("dht_app.telemetry_test_packets" not in sys.modules, "Developer packet module loaded at startup.")

    collected_text: list[str] = []
    for page in ("select_dualsense", "hud", "telemetry"):
        window._set_page(page)
        app.processEvents()
        collected_text.append(_widget_text(window))
    all_text = "\n".join(collected_text)
    for forbidden in FORBIDDEN_PUBLIC_TEXT:
        _assert(forbidden not in all_text, f"Developer-only public UI text found: {forbidden}")
    _assert("dht_app.telemetry_test_packets" not in sys.modules, "Developer packet module loaded in public Telemetry page.")
    _assert(not window.debug_hud_overlays, "Developer HUD overlays exist in public mode.")
    _verify_trigger_preset_defaults_and_group_order(window)
    _verify_trigger_toggle_description_rows(window, app)
    _verify_effect_sliders_survive_continuous_edit(window, app)
    _verify_standby_button_first_click(window, app)
    _verify_packet_refresh_preserves_live_controls(window, app)

    window.close()
    app.processEvents()

    settings_path = settings_store.settings_file_path(temp_root)
    _assert(settings_path.is_file(), "Graceful first close did not create the settings file.")
    snapshot = json.loads(settings_path.read_text(encoding="utf-8"))
    _assert(snapshot.get("app_version") == APP_VERSION, "First-run app version is incorrect.")
    _assert(snapshot.get("schema") == SNAPSHOT_SCHEMA, "First-run settings schema is incorrect.")
    _assert(snapshot.get("udp_port") == 8800, "First-run settings saved an unexpected UDP port.")
    _assert(snapshot.get("hud", {}).get("rpm_style") == "Digital Bar", "First-run RPM HUD style is not Digital Bar.")
    device = snapshot.get("dualsense_device", {})
    _assert(not device.get("selected_device"), "First-run settings saved a personal controller device.")
    options = snapshot.get("options", {})
    _assert(not options.get("dsx_audio_device"), "First-run settings saved a personal DSX device.")
    user_files = sorted(path.name for path in settings_path.parent.iterdir())
    _assert(user_files == [settings_store.SETTINGS_FILE_NAME], f"Unexpected first-run user_data contents: {user_files}")


def _verify_legacy_092_schema_1_upgrade(temp_root: Path, app: QApplication) -> None:
    temp_root.mkdir(parents=True, exist_ok=True)
    runtime_execution_guard.PUBLIC_RELEASE_MARKER = temp_root / "PUBLIC_RELEASE"
    runtime_execution_guard.PUBLIC_RELEASE_MARKER.write_text("public\n", encoding="ascii")
    settings_store.app_root_dir = lambda: temp_root

    legacy_state = AppState()
    legacy_state.udp_port = 18888
    legacy_state.set_preset("Soft")
    legacy_state.options.dsx_audio_volume = 73
    legacy_snapshot = export_app_state(legacy_state)
    legacy_snapshot["app_version"] = "0.92"
    legacy_snapshot.get("hud", {}).pop("rpm_style", None)
    settings_path = settings_store.settings_file_path(temp_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(
        json.dumps(legacy_snapshot, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    _assert(compare_snapshot_schema(legacy_snapshot) == 0, "0.92/schema 1 settings are not compatible.")
    _assert(compare_snapshot_schema({"schema": SNAPSHOT_SCHEMA + 1}) > 0, "Newer schema was not rejected.")
    _assert(compare_snapshot_schema({"schema": SNAPSHOT_SCHEMA - 1}) < 0, "Older schema was not detected.")

    window = MainWindow()
    app.processEvents()
    _assert(window._pending_settings_notice is None, "Compatible 0.92 settings triggered a migration prompt.")
    _assert(window.state.udp_port == 18888, "Compatible 0.92 UDP port was not restored.")
    _assert(window.state.selected_preset == "Soft", "Compatible 0.92 preset was not restored.")
    _assert(window.state.options.dsx_audio_volume == 73, "Compatible 0.92 option was not restored.")
    _assert(window.state.hud.rpm_style == "Classic", "Legacy settings did not retain the Classic RPM HUD default.")
    window.close()
    app.processEvents()

    upgraded = json.loads(settings_path.read_text(encoding="utf-8"))
    _assert(
        upgraded.get("app_version") == APP_VERSION,
        f"Compatible settings were not upgraded to app {APP_VERSION}.",
    )
    _assert(upgraded.get("schema") == SNAPSHOT_SCHEMA, "Compatible settings schema changed unexpectedly.")
    _assert(upgraded.get("udp_port") == 18888, "Compatible settings lost the restored UDP port.")
    _assert(upgraded.get("selected_preset") == "Soft", "Compatible settings lost the restored preset.")
    backups = settings_store.list_settings_backups(temp_root)
    _assert(len(backups) == 1, "Compatible 0.92 settings were not backed up exactly once.")
    backup_snapshot = json.loads(backups[0].read_text(encoding="utf-8"))
    _assert(backup_snapshot.get("app_version") == "0.92", "Compatibility backup did not preserve app 0.92.")
    _assert(backup_snapshot.get("udp_port") == 18888, "Compatibility backup did not preserve values.")


def _verify_corrupt_settings_preserved(temp_root: Path, app: QApplication) -> None:
    temp_root.mkdir(parents=True, exist_ok=True)
    runtime_execution_guard.PUBLIC_RELEASE_MARKER = temp_root / "PUBLIC_RELEASE"
    runtime_execution_guard.PUBLIC_RELEASE_MARKER.write_text("public\n", encoding="ascii")
    settings_store.app_root_dir = lambda: temp_root
    settings_path = settings_store.settings_file_path(temp_root)
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    corrupt_payload = "{ this is not valid json\n"
    settings_path.write_text(corrupt_payload, encoding="utf-8")

    window = MainWindow()
    app.processEvents()
    _assert(window._settings_load_failed, "Corrupt settings did not set the load-failure guard.")
    _assert(window.state.footer.message == "Settings load failed.", "Corrupt settings error is not visible in status.")
    _assert(window.current_page == "select_dualsense", "Corrupt settings did not fall back to Select DualSense.")
    window.close()
    app.processEvents()

    _assert(settings_path.read_text(encoding="utf-8") == corrupt_payload, "Corrupt settings were overwritten on close.")


def _verify_idle_trigger_release() -> None:
    frame = TelemetryFrame(
        game_mode=GameMode.HORIZON,
        parser_name="idle release verification",
        packet_size=324,
        parsed=True,
        is_race_on=False,
    )
    engine = TriggerEffectEngine()
    _assert(engine.process_frame(frame, {}) == (), "A clean idle frame emitted a trigger payload.")

    engine.shift_down_howl.started_at = 1.0
    engine.shift_down_howl.last_output = TriggerPulseOutput(display=48, vibrate_amp=3)
    released = engine.process_frame(frame, {})
    _assert(len(released) == 1, "An active throttle trigger was not released exactly once.")
    _assert(
        released[0].name == "TRIGGER_THROTTLE" and "force=0" in released[0].to_message(),
        "Idle telemetry did not emit the expected zero-force throttle release.",
    )
    _assert(engine.process_frame(frame, {}) == (), "Idle telemetry repeated a completed trigger release.")


def _verify_hud_standby_visibility(app: QApplication) -> None:
    state = AppState()
    state.hud.items["RPM"].enabled = True
    rpm = RpmHudOverlay(state)
    try:
        rpm.sync_to_state()
        app.processEvents()
        _assert(rpm.isVisible(), "Standby Hide OFF did not keep an enabled HUD visible while waiting.")

        state.hud.standby_hide = True
        rpm.sync_to_state()
        app.processEvents()
        _assert(not rpm.isVisible(), "Standby Hide ON did not hide an enabled HUD while waiting.")

        state.packet_status = PacketStatus.RECEIVING
        state.telemetry.last_parsed = True
        state.telemetry.last_is_race_on = False
        state.telemetry.last_max_rpm = 8000.0
        rpm.sync_to_state()
        app.processEvents()
        _assert(not rpm.isVisible(), "Menu packets incorrectly bypassed Standby Hide.")

        state.telemetry.last_is_race_on = True
        rpm.sync_to_state()
        app.processEvents()
        _assert(rpm.isVisible(), "An enabled HUD did not return when valid driving telemetry started.")

        state.packet_status = PacketStatus.WAITING
        rpm.sync_to_state()
        app.processEvents()
        _assert(not rpm.isVisible(), "An enabled HUD did not hide when telemetry returned to waiting.")

        state.hud.standby_hide = False
        rpm.sync_to_state()
        app.processEvents()
        _assert(rpm.isVisible(), "Turning Standby Hide OFF did not restore the enabled HUD immediately.")

        state.hud.items["RPM"].enabled = False
        rpm.sync_to_state()
        app.processEvents()
        _assert(not rpm.isVisible(), "Standby Hide bypassed the individual HUD OFF state.")
    finally:
        rpm.close()

    state.hud.items["Preset"].enabled = True
    preset = PresetHudOverlay(state)
    try:
        preset.sync_to_state()
        app.processEvents()
        _assert(preset.isVisible(), "Standby Hide OFF did not show the enabled Preset HUD while waiting.")

        state.hud.standby_hide = True
        preset.sync_to_state()
        app.processEvents()
        _assert(not preset.isVisible(), "Standby Hide ON did not hide the Preset HUD while waiting.")

        state.packet_status = PacketStatus.RECEIVING
        state.telemetry.last_parsed = True
        state.telemetry.last_is_race_on = True
        state.telemetry.last_max_rpm = 8000.0
        preset.sync_to_state()
        app.processEvents()
        _assert(preset.isVisible(), "The Preset HUD did not return with valid driving telemetry.")

        state.packet_status = PacketStatus.WAITING
        preset.sync_to_state()
        app.processEvents()
        _assert(not preset.isVisible(), "The Preset HUD did not hide when telemetry returned to waiting.")

        state.hud.standby_hide = False
        preset.sync_to_state()
        app.processEvents()
        _assert(preset.isVisible(), "Turning Standby Hide OFF did not restore the Preset HUD.")

        state.hud.items["Preset"].enabled = False
        preset.sync_to_state()
        app.processEvents()
        _assert(not preset.isVisible(), "The individual Preset HUD OFF state was ignored.")
    finally:
        preset.close()


def _verify_preset_hud_dashboard_row() -> None:
    _assert(HUD_NAMES[0] == "Preset", "Preset HUD is not in the visible dashboard list order.")
    state = AppState()
    calls: list[str] = []
    callbacks = {
        "preset_toggle": lambda checked=False: calls.append("toggle"),
        "preset_scale_down": lambda checked=False: calls.append("scale_down"),
        "preset_scale_up": lambda checked=False: calls.append("scale_up"),
        "preset_opacity_down": lambda checked=False: calls.append("opacity_down"),
        "preset_opacity_up": lambda checked=False: calls.append("opacity_up"),
    }
    page = build_hud_dashboard_page(callbacks, state)
    try:
        rows = page.findChildren(HudRow)
        matching_rows = [
            row
            for row in rows
            if any(label.text() == "Preset" for label in row.findChildren(QLabel))
        ]
        _assert(len(matching_rows) == 1, "HUD Dashboard is missing the individual Preset row.")
        buttons = matching_rows[0].findChildren(QAbstractButton)
        _assert(len(buttons) == 5, "Preset HUD row does not expose toggle, scale, and opacity controls.")
        for button in buttons:
            button.click()
        _assert(
            calls == ["toggle", "scale_down", "scale_up", "opacity_down", "opacity_up"],
            f"Preset HUD controls are not independently connected: {calls}",
        )
    finally:
        page.close()


def main() -> int:
    _disable_background_inputs()
    app = QApplication.instance() or QApplication(["verify_first_run"])
    app.setQuitOnLastWindowClosed(False)
    with tempfile.TemporaryDirectory(prefix="dht_first_run_") as directory:
        temp_root = Path(directory)
        _verify_clean_first_run(temp_root / "clean", app)
        _verify_legacy_092_schema_1_upgrade(temp_root / "legacy_092", app)
        _verify_corrupt_settings_preserved(temp_root / "corrupt", app)
        _verify_idle_trigger_release()
        _verify_hud_standby_visibility(app)
        _verify_preset_hud_dashboard_row()
    app.quit()
    print("Public first-run UI and settings verification: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
