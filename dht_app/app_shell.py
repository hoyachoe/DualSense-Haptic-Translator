import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QProcess, QRect, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QIcon, QIntValidator
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


from .ui_theme import APP_TITLE, apply_game_accent, stylesheet

from .app_state import HUD_NAMES, MAIN_UI_LANGUAGES, PRESET_NAMES, TOOLTIP_LANGUAGES, AppState, DualSenseStatus, GameMode, PacketStatus
from .engine_bridge import BridgeResult, EngineBridge
from .hud_overlay import DriftHudOverlay, EngineHudOverlay, GForceHudOverlay, HapticDebugHudOverlay, HapticVizHudOverlay, PedalHudOverlay, PresetHudOverlay, RpmHudOverlay, SteerHudOverlay, TireHudOverlay, TriggerDebugHudOverlay, TriggerHudOverlay
from .settings_io import (
    SNAPSHOT_SCHEMA,
    apply_user_preset_recovery,
    apply_app_state_snapshot,
    audit_snapshot_structure,
    compare_snapshot_schema,
    export_app_state,
    list_recoverable_user_preset_items,
    summarize_snapshot,
)
from .version import APP_VERSION
from .settings_store import (
    SettingsStoreError,
    list_settings_backups,
    load_settings_snapshot,
    save_settings_snapshot,
    save_settings_snapshot_with_backup,
    user_data_dir,
)
from .telemetry_receiver import TelemetryReceiver
from .dualsense_input_receiver import DualSenseInputReceiver
from .ui_widgets import CompactScrollArea, TitleBar
from .ui_texts import ui_code_text, ui_text
from .update_checker import check_latest_release
from .layout_shell import (
    apply_footer_state,
    apply_sidebar_state,
    apply_status_strip_state,
    build_footer_bar,
    build_sidebar,
    build_status_strip,
)
from .pages_dualsense import build_dualsense_select_page
from .pages_haptic import build_advanced_panel, build_haptic_panel
from .pages_hud import build_hud_dashboard_page
from .pages_options import build_options_page
from .pages_sound_to_haptic import build_sound_to_haptic_page
from .pages_telemetry import build_telemetry_page, refresh_telemetry_page
from .pages_trigger import build_trigger_advanced_panel, build_trigger_panel
from .preset_loader import load_builtin_presets_into_state
from .runtime_execution_guard import developer_mode_enabled
from .sound_to_haptic_runtime import SoundToHapticRuntime


LANGUAGE_MENU_LABELS = {
    "EN": "English",
    "ES": "Spanish",
    "KR": "Korean",
    "CN": "Chinese",
}

MAIN_UI_SCALE_VALUES = (90, 100, 110, 125)

DUALSENSE_COMBO_ORDER = (
    ("touchpad", "Touchpad"),
    ("ps", "PS"),
    ("create", "Create"),
    ("options", "Options"),
    ("l1", "L1"),
    ("r1", "R1"),
    ("l2Button", "L2"),
    ("r2Button", "R2"),
    ("l3", "L3"),
    ("r3", "R3"),
    ("square", "Square"),
    ("cross", "Cross"),
    ("circle", "Circle"),
    ("triangle", "Triangle"),
    ("dpadUp", "Dpad Up"),
    ("dpadRight", "Dpad Right"),
    ("dpadDown", "Dpad Down"),
    ("dpadLeft", "Dpad Left"),
)

DUALSENSE_COMBO_LABEL_ORDER = tuple(label for _key, label in DUALSENSE_COMBO_ORDER)

DUALSENSE_COMBO_ALIASES = {
    "DPADUP": "Dpad Up",
    "DPADRIGHT": "Dpad Right",
    "DPADDOWN": "Dpad Down",
    "DPADLEFT": "Dpad Left",
    "TOUCHPAD": "Touchpad",
    "CREATE": "Create",
    "OPTIONS": "Options",
    "SQUARE": "Square",
    "CROSS": "Cross",
    "CIRCLE": "Circle",
    "TRIANGLE": "Triangle",
    "PS": "PS",
    "L1": "L1",
    "R1": "R1",
    "L2": "L2",
    "R2": "R2",
    "L3": "L3",
    "R3": "R3",
}


def _float_status_value(values: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(values.get(key, default))
    except (TypeError, ValueError):
        return default


def _normalize_dualsense_combo_text(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    text = text.replace("D-pad", "Dpad").replace("D_PAD", "Dpad")
    text = re.sub(r"(?i)\bdpad\s*up\b", "DpadUp", text)
    text = re.sub(r"(?i)\bdpad\s*right\b", "DpadRight", text)
    text = re.sub(r"(?i)\bdpad\s*down\b", "DpadDown", text)
    text = re.sub(r"(?i)\bdpad\s*left\b", "DpadLeft", text)
    parts: list[str] = []
    for raw in re.split(r"[+,\s]+", text):
        key = raw.strip().replace("_", "").replace("-", "").upper()
        key = re.sub(r"[^A-Z0-9]", "", key)
        if key:
            parts.append(DUALSENSE_COMBO_ALIASES.get(key, raw.strip()))
    unique: list[str] = []
    for label in DUALSENSE_COMBO_LABEL_ORDER:
        if label in parts and label not in unique:
            unique.append(label)
    for label in parts:
        if label not in unique:
            unique.append(label)
    return "+".join(unique)


def _dualsense_combo_from_status(values: dict) -> str:
    active = [
        label
        for key, label in DUALSENSE_COMBO_ORDER
        if _float_status_value(values, key, 0.0) >= 0.5
    ]
    return "+".join(active)


def _dualsense_combo_part_count(combo: str) -> int:
    if not combo:
        return 0
    return len([part for part in combo.split("+") if part.strip()])


def _normalize_main_ui_scale(scale: object) -> int:
    try:
        requested = int(scale)
    except (TypeError, ValueError):
        requested = 100
    return min(MAIN_UI_SCALE_VALUES, key=lambda value: abs(value - requested))


def _read_startup_main_ui_scale() -> int:
    try:
        snapshot = load_settings_snapshot()
    except SettingsStoreError:
        return 100
    if not isinstance(snapshot, dict):
        return 100
    options = snapshot.get("options")
    if not isinstance(options, dict):
        return 100
    return _normalize_main_ui_scale(options.get("main_ui_scale", 100))


def _apply_startup_main_ui_scale() -> int:
    scale = _read_startup_main_ui_scale()
    os.environ["QT_SCALE_FACTOR"] = f"{scale / 100.0:.2f}"
    return scale


class MainWindow(QMainWindow):
    FAST_HUD_NAMES = frozenset(("Pedal", "G-force", "Steer", "RPM", "Engine", "Trigger"))
    NORMAL_HUD_NAMES = frozenset(("Tire", "Haptic Viz", "Drift"))
    DEBUG_HUD_NAMES = frozenset(("Debug Haptic", "Debug Trigger"))

    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_TITLE)
        icon_path = Path(__file__).resolve().parent / "Resource" / "icon_DHT.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.Window)
        self.resize(836, 640)
        self.setMinimumSize(790, 544)
        self.state = AppState()
        self._builtin_preset_report = load_builtin_presets_into_state(self.state)
        self._pending_settings_notice = None
        self._settings_load_failed = False
        self._settings_upgrade_pending = False
        self._load_initial_settings()
        self._apply_game_theme()
        self._restore_main_window_geometry()
        self.developer_mode = developer_mode_enabled()
        self.engine = EngineBridge(self.state)
        self.sound_to_haptic_runtime = SoundToHapticRuntime(Path(__file__).resolve().parent)
        regular_hud_overlays = (
            PedalHudOverlay(self.state),
            GForceHudOverlay(self.state),
            TireHudOverlay(self.state),
            SteerHudOverlay(self.state),
            HapticVizHudOverlay(self.state),
            RpmHudOverlay(self.state),
            EngineHudOverlay(self.state),
            TriggerHudOverlay(self.state),
            PresetHudOverlay(self.state),
            DriftHudOverlay(self.state),
        )
        developer_hud_overlays = (
            HapticDebugHudOverlay(self.state),
            TriggerDebugHudOverlay(self.state),
        ) if self.developer_mode else ()
        self.hud_overlays = regular_hud_overlays + developer_hud_overlays
        self.fast_hud_overlays = self._hud_group(self.FAST_HUD_NAMES)
        self.normal_hud_overlays = self._hud_group(self.NORMAL_HUD_NAMES)
        self.debug_hud_overlays = self._hud_group(self.DEBUG_HUD_NAMES)
        grouped_names = self.FAST_HUD_NAMES | self.NORMAL_HUD_NAMES | self.DEBUG_HUD_NAMES
        self.event_hud_overlays = tuple(
            overlay for overlay in self.hud_overlays
            if overlay.HUD_NAME not in grouped_names
        )
        self.telemetry_receiver = TelemetryReceiver(self.state.udp_port)
        self.telemetry_poll_timer = QTimer(self)
        self.telemetry_poll_timer.setTimerType(Qt.PreciseTimer)
        self.telemetry_poll_timer.setInterval(16)
        self.telemetry_poll_timer.timeout.connect(self._poll_telemetry_receiver)
        self.dualsense_input_receiver = DualSenseInputReceiver()
        self.dualsense_input_poll_timer = QTimer(self)
        self.dualsense_input_poll_timer.setTimerType(Qt.PreciseTimer)
        self.dualsense_input_poll_timer.setInterval(16)
        self.dualsense_input_poll_timer.timeout.connect(self._poll_dualsense_input_receiver)
        self.fast_hud_timer = self._make_hud_timer(16, self._sync_fast_hud_overlays, precise=True)
        self.normal_hud_timer = self._make_hud_timer(33, self._sync_normal_hud_overlays)
        self.debug_hud_timer = self._make_hud_timer(66, self._sync_debug_hud_overlays)
        self._preset_shortcut_capture_candidate = ""
        self._preset_shortcut_previous_combo = ""
        self._preset_shortcut_last_triggered_at = 0.0
        self._preset_shortcut_capture_timer = QTimer(self)
        self._preset_shortcut_capture_timer.setSingleShot(True)
        self._preset_shortcut_capture_timer.timeout.connect(self._finish_preset_shortcut_capture)
        self._last_telemetry_page_render_at = 0.0
        self._telemetry_page_render_interval = 0.05
        self._last_shell_state_render_at = 0.0
        self._last_packet_event_at = 0.0
        self._telemetry_timeout_seconds = 1.25
        self._test_packet_tick = 0
        self.current_page = self._initial_page()
        self.nav_buttons = {}
        self.content_layout: QVBoxLayout | None = None
        self.status_refs = None
        self.sidebar_refs = None
        self.footer_refs = None
        self._dualsense_auto_refresh_scheduled = False
        self._sound_to_haptic_auto_refresh_scheduled = False
        self._scroll_positions: dict[str, int] = {}

        central = QFrame()
        central.setObjectName("WindowShell")
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(TitleBar(self))
        status_strip, self.status_refs = build_status_strip(self.state, self._show_udp_port_dialog)
        root.addWidget(status_strip)

        main = QHBoxLayout()
        main.setContentsMargins(0, 0, 0, 0)
        main.setSpacing(0)

        sidebar, self.nav_buttons, self.sidebar_refs = build_sidebar(
            self.current_page,
            self._set_page,
            self.state,
            self._show_game_menu,
            self._show_preset_menu,
            self._show_load_preset_menu,
            self._request_save,
            self._request_load_backup,
        )
        main.addWidget(sidebar)
        main.addWidget(self._build_content(), 1)
        root.addLayout(main, 1)
        footer_bar, self.footer_refs = build_footer_bar(self.state)
        root.addWidget(footer_bar)
        self._start_telemetry_receiver()
        self._start_dualsense_input_receiver()
        self._sync_hud_overlays()
        self._maybe_auto_refresh_dualsense_page()
        QTimer.singleShot(0, self._show_pending_settings_notice)
        QTimer.singleShot(350, self._request_output_service_startup)

    def _initial_page(self) -> str:
        if not self.state.dualsense_device.selected_device.strip():
            self.state.dualsense_status = DualSenseStatus.NOT_SELECTED
            return "select_dualsense"
        return "haptic"

    def _load_initial_settings(self):
        try:
            snapshot = load_settings_snapshot()
        except SettingsStoreError as exc:
            self._settings_load_failed = True
            self.state.footer.message = "Settings load failed."
            self.state.footer.details = str(exc)
            return
        if snapshot is None:
            return

        schema_state = compare_snapshot_schema(snapshot)
        if schema_state == 0:
            restored = apply_app_state_snapshot(self.state, snapshot)
            audit = audit_snapshot_structure(snapshot)
            source_app_version = str(snapshot.get("app_version") or "unknown")
            upgrade_note = ""
            if source_app_version != APP_VERSION:
                self._settings_upgrade_pending = True
                self.state.mark_unsaved_changes()
                upgrade_note = (
                    f" Compatible app {source_app_version} settings will be backed up "
                    f"and stamped as {APP_VERSION} on save or normal exit."
                )
            self.state.footer.message = "Settings loaded."
            self.state.footer.details = (
                f"Loaded {len(restored)} compatible settings from app user_data; "
                f"{audit.summary}.{upgrade_note}"
            )
            return
        if schema_state > 0:
            self._pending_settings_notice = ("newer", snapshot)
            self.state.footer.message = "Settings file uses a newer format."
            self.state.footer.details = (
                f"Current settings format {SNAPSHOT_SCHEMA}; file format {snapshot.get('schema', 'unknown')} "
                f"from app {snapshot.get('app_version', 'unknown')}. "
                "Use the latest app version or remove the settings file."
            )
            return
        self._pending_settings_notice = ("older", snapshot)
        self.state.footer.message = "Older settings format detected."
        self.state.footer.details = (
            f"Current settings format {SNAPSHOT_SCHEMA}; file format {snapshot.get('schema', 'unknown')} "
            f"from app {snapshot.get('app_version', 'unknown')}. "
            "Compatible import confirmation will be shown."
        )

    def _show_pending_settings_notice(self):
        if self._pending_settings_notice is None:
            return
        kind, snapshot = self._pending_settings_notice
        self._pending_settings_notice = None
        if kind == "newer":
            self._show_newer_settings_notice(snapshot)
            return
        if kind == "older":
            self._show_older_settings_notice(snapshot)

    def _show_newer_settings_notice(self, snapshot: dict):
        answer = QMessageBox.question(
            self,
            "Settings Format Is Newer",
            (
                "The settings file uses a newer data format.\n\n"
                f"Current app version: {APP_VERSION}\n"
                f"Current settings format: {SNAPSHOT_SCHEMA}\n"
                f"File app version: {snapshot.get('app_version', 'unknown')}\n"
                f"File settings format: {snapshot.get('schema', 'unknown')}\n\n"
                "Use the latest app version, or remove the settings file if you want a clean start.\n"
                "Open the settings folder now?"
            ),
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer == QMessageBox.Yes:
            self._open_settings_folder()
        self.refresh_shell_state()

    def _show_older_settings_notice(self, snapshot: dict):
        recoverable = list_recoverable_user_preset_items(snapshot)
        if not recoverable:
            QMessageBox.information(
                self,
                "No User Presets To Recover",
                (
                    "The settings file uses an older data format, "
                    "but no compatible User 1/User 2 preset settings were found.\n\n"
                    "Built-in presets are not imported during version recovery."
                ),
            )
            self.state.footer.message = "Older settings import skipped."
            self.state.footer.details = "No compatible User 1/User 2 preset values were found."
            self.refresh_shell_state()
            return

        if not self._confirm_user_preset_recovery(snapshot, recoverable):
            self.state.footer.message = "Older settings import skipped."
            self.state.footer.details = "The app is using clean default settings for this session."
            self.refresh_shell_state()
            return

        restored = apply_user_preset_recovery(self.state, snapshot)
        audit = audit_snapshot_structure(snapshot)
        try:
            result = save_settings_snapshot_with_backup(export_app_state(self.state))
        except SettingsStoreError as exc:
            self.state.footer.message = "Older settings imported, but save failed."
            self.state.footer.details = str(exc)
        else:
            self.state.mark_settings_saved()
            self.state.footer.message = "Older User presets imported."
            self.state.footer.details = (
                f"Imported {len(restored)} User 1/User 2 settings; "
                f"saved as {result.settings_path.name}; {audit.summary}"
            )
        self._render_content()
        self.refresh_shell_state()

    def _confirm_user_preset_recovery(self, snapshot: dict, recoverable: list[str]) -> bool:
        dialog = QDialog(self)
        dialog.setObjectName("SettingsRecoveryDialog")
        dialog.setWindowTitle("Recover Older User Presets")
        dialog.setModal(True)
        dialog.resize(620, 430)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel("Recover compatible User preset settings?")
        title.setObjectName("PanelTitle")
        layout.addWidget(title)

        message = QLabel(
            "The settings file uses an older data format.\n\n"
            f"Current app version: {APP_VERSION}\n"
            f"Current settings format: {SNAPSHOT_SCHEMA}\n"
            f"File app version: {snapshot.get('app_version', 'unknown')}\n"
            f"File settings format: {snapshot.get('schema', 'unknown')}\n\n"
            "Only compatible User 1/User 2 preset values will be imported. "
            "Built-in presets are kept from the current app version."
        )
        message.setObjectName("OptionText")
        message.setWordWrap(True)
        layout.addWidget(message)

        list_box = QTextEdit()
        list_box.setObjectName("RecoveryList")
        list_box.setReadOnly(True)
        list_box.setPlainText("\n".join(recoverable))
        layout.addWidget(list_box, 1)

        question = QLabel("Recover these settings now?")
        question.setObjectName("OptionLabel")
        layout.addWidget(question)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.button(QDialogButtonBox.Ok).setText("Recover")
        buttons.button(QDialogButtonBox.Cancel).setText("Cancel")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        return dialog.exec() == QDialog.Accepted

    def _open_settings_folder(self):
        target = user_data_dir()
        target.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))

    def refresh_shell_state(self, sync_hud: bool = True):
        if self.status_refs is not None:
            apply_status_strip_state(self.status_refs, self.state)
        if self.sidebar_refs is not None:
            apply_sidebar_state(self.sidebar_refs, self.state)
        if self.footer_refs is not None:
            apply_footer_state(self.footer_refs, self.state)
        if sync_hud:
            self._sync_hud_overlays()

    def _sync_hud_overlays(self) -> None:
        for overlay in getattr(self, "hud_overlays", ()):
            overlay.sync_to_state()

    def _hud_group(self, names: frozenset[str]) -> tuple:
        return tuple(
            overlay for overlay in getattr(self, "hud_overlays", ())
            if overlay.HUD_NAME in names
        )

    def _make_hud_timer(self, interval_ms: int, callback, precise: bool = False) -> QTimer:
        timer = QTimer(self)
        if precise:
            timer.setTimerType(Qt.PreciseTimer)
        timer.setInterval(interval_ms)
        timer.timeout.connect(callback)
        return timer

    def _sync_hud_group(self, overlays: tuple) -> None:
        if self.state.packet_status != PacketStatus.RECEIVING:
            return
        for overlay in overlays:
            overlay.sync_to_state()

    def _sync_fast_hud_overlays(self) -> None:
        self._sync_hud_group(self.fast_hud_overlays)

    def _sync_normal_hud_overlays(self) -> None:
        self._sync_hud_group(self.normal_hud_overlays)

    def _sync_debug_hud_overlays(self) -> None:
        self._sync_hud_group(self.debug_hud_overlays)

    def _sync_event_hud_overlays(self) -> None:
        for overlay in getattr(self, "event_hud_overlays", ()):
            overlay.sync_to_state()

    def _apply_bridge_result(self, result: BridgeResult) -> None:
        self.state.footer.message = result.message
        self.state.footer.details = result.details

    def _start_telemetry_receiver(self) -> None:
        self.telemetry_receiver.start(self.state.udp_port)
        self.telemetry_poll_timer.start()
        self.fast_hud_timer.start()
        self.normal_hud_timer.start()
        if self.developer_mode:
            self.debug_hud_timer.start()

    def _start_dualsense_input_receiver(self) -> None:
        self.dualsense_input_receiver.start()
        self.dualsense_input_poll_timer.start()

    def _show_udp_port_dialog(self, source_widget=None) -> None:
        language = self.state.options.main_ui_language
        dialog = QDialog(self)
        dialog.setObjectName("UdpPortDialog")
        dialog.setAttribute(Qt.WA_StyledBackground, True)
        dialog.setWindowTitle(ui_text("UDP Input Port", language))
        dialog.setModal(True)
        dialog.setMinimumWidth(430)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(10)

        title = QLabel(ui_text("UDP Input Port", language))
        title.setStyleSheet("font-size: 15px; font-weight: 900;")
        layout.addWidget(title)

        description = QLabel(
            ui_text(
                "Forza Data Out sends telemetry packets to this app through a UDP port. Set the same port number here and in the game telemetry settings.",
                language,
            )
        )
        description.setWordWrap(True)
        description.setStyleSheet("color: #b9d8f2; font-size: 10px; line-height: 140%;")
        layout.addWidget(description)

        input_label = QLabel(ui_text("Port", language))
        input_label.setStyleSheet("font-weight: 900;")
        layout.addWidget(input_label)

        field = QLineEdit(str(self.state.udp_port))
        field.setObjectName("OptionField")
        field.setAlignment(Qt.AlignCenter)
        field.setFixedWidth(92)
        field.setFixedHeight(28)
        field.setValidator(QIntValidator(1, 65535, field))
        field.setMaxLength(5)
        field.selectAll()
        field_row = QHBoxLayout()
        field_row.setContentsMargins(0, 0, 0, 0)
        field_row.addWidget(field)
        field_row.addStretch(1)
        layout.addLayout(field_row)

        error = QLabel("")
        error.setStyleSheet("color: #ffd21a; font-size: 9px; font-weight: 800;")
        error.setWordWrap(True)
        layout.addWidget(error)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        cancel = QPushButton(ui_text("Cancel", language))
        cancel.setObjectName("SecondaryButton")
        save = QPushButton(ui_text("Save", language))
        save.setObjectName("PrimaryButton")
        cancel.clicked.connect(dialog.reject)
        buttons.addWidget(cancel)
        buttons.addWidget(save)
        layout.addLayout(buttons)

        def save_port() -> None:
            text = field.text().strip()
            try:
                port = int(text)
            except ValueError:
                error.setText(ui_text("Enter a UDP port from 1 to 65535.", language))
                return
            if not 1 <= port <= 65535:
                error.setText(ui_text("Enter a UDP port from 1 to 65535.", language))
                return
            self._set_udp_input_port(str(port))
            dialog.accept()

        save.clicked.connect(save_port)
        field.returnPressed.connect(save_port)
        dialog.exec()

    def _set_udp_input_port(self, value: str) -> bool:
        changed = self.state.set_udp_port(value)
        if changed:
            self._last_packet_event_at = 0.0
            self.telemetry_receiver.stop(timeout=0.4)
            self.telemetry_receiver.start(self.state.udp_port)
            self.telemetry_poll_timer.start()
        self.refresh_shell_state()
        return changed

    def _poll_telemetry_receiver(self) -> None:
        events = self.telemetry_receiver.poll(max_events=64)
        if not events:
            self._check_telemetry_timeout()
            return

        packet_seen = False
        now = time.monotonic()
        for event in events:
            result = self.engine.handle_receiver_event(event)
            self._apply_bridge_result(result)
            if event.kind == "packet" and self.state.packet_status == PacketStatus.RECEIVING:
                packet_seen = True
                self._last_packet_event_at = now
            elif event.kind == "error":
                self._last_packet_event_at = 0.0

        if packet_seen and self.current_page == "telemetry":
            if now - self._last_telemetry_page_render_at >= self._telemetry_page_render_interval:
                self._last_telemetry_page_render_at = now
                self._refresh_current_page_from_telemetry()
        if packet_seen:
            if now - self._last_shell_state_render_at >= 0.10:
                self._last_shell_state_render_at = now
                self._sync_event_hud_overlays()
                self.refresh_shell_state(sync_hud=False)
        else:
            self.refresh_shell_state()

    def _poll_dualsense_input_receiver(self) -> None:
        events = self.dualsense_input_receiver.poll(max_events=64)
        if not events:
            return
        render_needed = False
        refresh_needed = False
        for event in events:
            if event.kind == "input" and event.values:
                self._update_dualsense_footer_from_status(event.values, event.received_at)
                render_needed = self._handle_dualsense_button_status(event.values, event.received_at) or render_needed
                refresh_needed = True
            elif event.kind == "error":
                self.state.footer.details = event.message
                refresh_needed = True
        if render_needed:
            self._render_content()
        if refresh_needed:
            self.refresh_shell_state(sync_hud=False)

    def _update_dualsense_footer_from_status(self, values: dict, received_at: float = 0.0) -> None:
        left_pct = _float_status_value(values, "leftPct", 0.0)
        right_pct = _float_status_value(values, "rightPct", 0.0)
        left_raw = int(round(_float_status_value(values, "left", 0.0)))
        right_raw = int(round(_float_status_value(values, "right", 0.0)))
        self.state.dualsense_device.left_trigger_percent = max(0.0, min(100.0, left_pct))
        self.state.dualsense_device.right_trigger_percent = max(0.0, min(100.0, right_pct))
        self.state.dualsense_device.last_input_at = max(0.0, float(received_at))
        drift_score = getattr(self.state.telemetry.drift_hud, "score", 0.0)
        self.state.footer.primary = (
            f"DualSense L2 {left_pct:4.1f}% ({left_raw:3d})   "
            f"R2 {right_pct:4.1f}% ({right_raw:3d})     "
            f"drift {drift_score:.2f}     pred --"
        )

    def _handle_dualsense_button_status(self, values: dict, now: float) -> bool:
        options = self.state.options
        combo = _normalize_dualsense_combo_text(_dualsense_combo_from_status(values))
        if options.preset_shortcut_capture_active:
            if combo:
                candidate_count = _dualsense_combo_part_count(self._preset_shortcut_capture_candidate)
                combo_count = _dualsense_combo_part_count(combo)
                if combo != self._preset_shortcut_capture_candidate and combo_count >= candidate_count:
                    self._preset_shortcut_capture_candidate = combo
                    options.preset_shortcut_pending_combo = f"{combo} ..."
                    self._schedule_preset_shortcut_capture_finish()
                    return True
            return False

        saved_combo = _normalize_dualsense_combo_text(options.preset_shortcut_combo)
        if (
            options.preset_shortcut_enabled
            and saved_combo
            and combo == saved_combo
            and combo != self._preset_shortcut_previous_combo
            and now - self._preset_shortcut_last_triggered_at >= 0.55
        ):
            self._preset_shortcut_last_triggered_at = now
            self._preset_shortcut_previous_combo = combo
            self._toggle_user2_preset_shortcut()
            return True
        self._preset_shortcut_previous_combo = combo
        return False

    def _toggle_user2_preset_shortcut(self) -> None:
        current = self.state.selected_preset if self.state.selected_preset in PRESET_NAMES else "Base"
        if current == "User 2":
            target = self.state.options.preset_shortcut_return_preset
            if target not in PRESET_NAMES or target == "User 2":
                target = "Base"
        else:
            self.state.options.preset_shortcut_return_preset = current
            target = "User 2"
        self.state.set_preset(target)
        self.state.footer.message = f"DualSense shortcut preset: {current} -> {target}"
        self.state.footer.details = f"Shortcut {self.state.options.preset_shortcut_combo} toggles User 2 for quick tuning."
        self._sync_event_hud_overlays()

    def _check_telemetry_timeout(self) -> None:
        if self.state.packet_status != PacketStatus.RECEIVING:
            return
        if self._last_packet_event_at <= 0.0:
            return
        if time.monotonic() - self._last_packet_event_at < self._telemetry_timeout_seconds:
            return
        self.state.packet_status = PacketStatus.WAITING
        self.state.footer.message = "Waiting for Forza UDP packets. Check Forza Data Out IP/port and Windows Firewall."
        self.state.footer.details = (
            f"Packets: {self.state.telemetry.packet_count}   "
            f"Last parser: {self.state.telemetry.last_parser_name or '--'}   "
            f"UDP receiver: listening on {self.state.udp_port}"
        )
        self.refresh_shell_state()

    def closeEvent(self, event):
        self._capture_hud_overlay_positions()
        self._capture_main_window_geometry()
        self._auto_save_dirty_settings_on_close()
        self.fast_hud_timer.stop()
        self.normal_hud_timer.stop()
        self.debug_hud_timer.stop()
        self.telemetry_poll_timer.stop()
        self.dualsense_input_poll_timer.stop()
        self._preset_shortcut_capture_timer.stop()
        for overlay in getattr(self, "hud_overlays", ()):
            overlay.close()
        self.telemetry_receiver.stop()
        self.dualsense_input_receiver.stop()
        self.engine.reset_triggers("app close")
        self.engine.close()
        self.sound_to_haptic_runtime.stop()
        super().closeEvent(event)

    def _capture_hud_overlay_positions(self) -> None:
        for overlay in getattr(self, "hud_overlays", ()):
            item = self.state.hud.items.get(overlay.HUD_NAME)
            if item is None or not overlay.isVisible():
                continue
            x = overlay.x()
            y = overlay.y()
            if item.x == x and item.y == y:
                continue
            if item.x is None and item.y is None and x == overlay.DEFAULT_X and y == overlay.DEFAULT_Y:
                continue
            self.state.set_hud_position(overlay.HUD_NAME, x, y)

    def _restore_main_window_geometry(self) -> None:
        window = self.state.window
        width = max(self.minimumWidth(), int(window.width or self.width()))
        height = max(self.minimumHeight(), int(window.height or self.height()))
        self.resize(width, height)
        if window.x is None or window.y is None:
            return
        x, y = self._bounded_window_position(int(window.x), int(window.y), width, height)
        self.move(x, y)

    def _bounded_window_position(self, x: int, y: int, width: int, height: int) -> tuple[int, int]:
        target = QRect(x, y, width, height)
        for screen in QApplication.screens():
            available = screen.availableGeometry()
            if available.intersects(target) and available.contains(target.topLeft()):
                return x, y
        primary = QApplication.primaryScreen()
        if primary is None:
            return x, y
        available = primary.availableGeometry()
        return available.x() + 40, available.y() + 40

    def _capture_main_window_geometry(self) -> None:
        geometry = self.geometry()
        self.state.set_window_geometry(
            geometry.x(),
            geometry.y(),
            geometry.width(),
            geometry.height(),
        )

    def _auto_save_dirty_settings_on_close(self) -> None:
        if self._settings_load_failed:
            return
        if not self.state.unsaved_changes:
            return
        try:
            snapshot = export_app_state(self.state)
            if self._settings_upgrade_pending:
                save_settings_snapshot_with_backup(snapshot)
            else:
                save_settings_snapshot(snapshot)
        except SettingsStoreError:
            return
        self._settings_upgrade_pending = False
        self.state.mark_settings_saved()

    def _show_game_menu(self, source_widget):
        language = self.state.options.main_ui_language
        menu = QMenu(self)
        header = menu.addAction(ui_text("Select Game", language))
        header.setEnabled(False)
        menu.addSeparator()
        horizon_action = menu.addAction("Forza Horizon")
        motorsport_action = menu.addAction("Forza Motorsport")
        for action, game_mode in (
            (horizon_action, GameMode.HORIZON),
            (motorsport_action, GameMode.MOTORSPORT),
        ):
            action.setCheckable(True)
            action.setChecked(self.state.game_mode == game_mode)
        selected = menu.exec(source_widget.mapToGlobal(source_widget.rect().bottomLeft()))
        if selected == horizon_action:
            self.state.set_game_mode(GameMode.HORIZON)
        elif selected == motorsport_action:
            self.state.set_game_mode(GameMode.MOTORSPORT)
        else:
            return
        self._apply_game_theme()
        self._render_content()
        self.refresh_shell_state()

    def _apply_game_theme(self) -> None:
        apply_game_accent(self.state.game_mode)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet())
        for key, button in getattr(self, "nav_buttons", {}).items():
            button.set_active(key == self.current_page)
        self.update()
        for overlay in getattr(self, "hud_overlays", ()):
            overlay.update()

    def _show_preset_menu(self, source_widget):
        language = self.state.options.main_ui_language
        menu = QMenu(self)
        header = menu.addAction(ui_text("Select Preset", language))
        header.setEnabled(False)
        menu.addSeparator()
        actions = {}
        for name in PRESET_NAMES:
            action = menu.addAction(name)
            action.setCheckable(True)
            action.setChecked(name == self.state.selected_preset)
            actions[action] = name

        selected = menu.exec(source_widget.mapToGlobal(source_widget.rect().bottomLeft()))
        if selected is None:
            return
        if selected in actions:
            self.state.set_preset(actions[selected])
        else:
            return
        self._render_content()
        self.refresh_shell_state()

    def _show_load_preset_menu(self, source_widget):
        language = self.state.options.main_ui_language
        menu = QMenu(self)
        header = menu.addAction(
            ui_code_text("Copy preset values into {preset}", language, preset=self.state.selected_preset)
        )
        header.setEnabled(False)
        menu.addSeparator()
        actions = {}
        for name in PRESET_NAMES:
            if name == self.state.selected_preset:
                continue
            action = menu.addAction(name)
            actions[action] = name
        menu.addSeparator()
        restore_original_action = menu.addAction(ui_text("Restore Original Settings", language))

        selected = menu.exec(source_widget.mapToGlobal(source_widget.rect().bottomLeft()))
        if selected is None:
            return
        if selected == restore_original_action:
            if not self._confirm_restore_original_settings():
                self.state.footer.message = ui_text("Restore original settings cancelled.", language)
                self.state.footer.details = ui_text("Current preset values were not changed.", language)
                self.refresh_shell_state()
                return
            self.state.restore_current_preset_original_settings()
            self._render_content()
            self.refresh_shell_state()
            return
        source_preset = actions.get(selected)
        if source_preset is None:
            return
        if not self._confirm_load_preset_values(source_preset):
            self.state.footer.message = ui_text("Copy preset cancelled.", language)
            self.state.footer.details = ui_text("Current preset values were not changed.", language)
            self.refresh_shell_state()
            return
        self.state.load_preset_values_into_current(source_preset)
        self._render_content()
        self.refresh_shell_state()

    def _confirm_load_preset_values(self, source_preset: str) -> bool:
        language = self.state.options.main_ui_language
        answer = QMessageBox.question(
            self,
            ui_text("Copy Preset", language),
            ui_code_text(
                "Copy this preset's settings into the current preset?\n\nCurrent preset: {current}\nCopy from: {source}",
                language,
                current=self.state.selected_preset,
                source=source_preset,
            ),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return answer == QMessageBox.Ok

    def _confirm_restore_original_settings(self) -> bool:
        language = self.state.options.main_ui_language
        answer = QMessageBox.question(
            self,
            ui_text("Restore Original Settings", language),
            ui_code_text(
                "Restore the current preset to its original built-in settings?\n\nCurrent preset: {current}",
                language,
                current=self.state.selected_preset,
            ),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Cancel,
        )
        return answer == QMessageBox.Ok

    def _confirm_main_ui_scale_restart(self, scale: int) -> bool:
        answer = QMessageBox.question(
            self,
            "Restart Required",
            (
                "Changing the main UI scale requires restarting the app.\n\n"
                f"The app will close briefly and reopen with Main UI Scale {scale}%.\n\n"
                "Apply this scale and restart now?"
            ),
            QMessageBox.Ok | QMessageBox.Cancel,
            QMessageBox.Ok,
        )
        return answer == QMessageBox.Ok

    def _restart_app(self) -> bool:
        working_dir = str(Path(__file__).resolve().parent)
        if getattr(sys, "frozen", False):
            program = sys.executable
            arguments = sys.argv[1:]
        else:
            program = sys.executable
            script = Path(sys.argv[0]).resolve()
            arguments = [str(script), *sys.argv[1:]]
        return QProcess.startDetached(program, arguments, working_dir)

    def _request_save(self):
        self.state.mark_save_requested()
        self._save_current_settings(ui_text("Settings saved", self.state.options.main_ui_language))
        self.refresh_shell_state()

    def _save_current_settings(self, success_message: str, details_prefix: str = "") -> bool:
        snapshot = export_app_state(self.state)
        try:
            result = save_settings_snapshot_with_backup(snapshot)
        except SettingsStoreError as exc:
            self.state.footer.message = "Settings save failed."
            self.state.footer.details = str(exc)
            return False
        else:
            self._settings_upgrade_pending = False
            self.state.mark_settings_saved()
            backup_text = (
                f" backup: {result.backup_path.name}"
                if result.backup_path is not None
                else " first save, no previous backup"
            )
            prefix = f"{details_prefix} " if details_prefix else ""
            self.state.footer.message = f"{success_message}: {result.settings_path.name}"
            self.state.footer.details = f"{prefix}{summarize_snapshot(snapshot)};{backup_text}"
            return True

    def _request_load_backup(self):
        backups = list_settings_backups()
        if not backups:
            self.state.footer.message = "No settings backups found."
            self.state.footer.details = "Save settings at least twice to create a restorable backup."
            self.refresh_shell_state()
            return

        menu = QMenu(self)
        actions = {}
        for index, backup_path in enumerate(backups[:5], start=1):
            timestamp = datetime.fromtimestamp(backup_path.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            label = f"{index}. {timestamp}  {backup_path.name}"
            action = menu.addAction(label)
            action.setData(str(backup_path))
            actions[action] = backup_path

        selected = menu.exec(self.mapToGlobal(self.rect().center()))
        if selected is None:
            self.state.mark_load_backup_requested()
            self.state.footer.details = "Backup restore cancelled before selection."
            self.refresh_shell_state()
            return

        backup_path = actions[selected]
        answer = QMessageBox.question(
            self,
            "Load Backup",
            f"Replace current settings with this backup?\n\n{backup_path.name}",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if answer != QMessageBox.Yes:
            self.state.footer.message = "Load backup cancelled."
            self.state.footer.details = "Current settings were not changed."
            self.refresh_shell_state()
            return

        try:
            snapshot = load_settings_snapshot(backup_path)
        except SettingsStoreError as exc:
            self.state.footer.message = "Load backup failed."
            self.state.footer.details = str(exc)
            self.refresh_shell_state()
            return
        if snapshot is None:
            self.state.footer.message = "Load backup failed."
            self.state.footer.details = f"Backup file is empty or missing: {backup_path.name}"
            self.refresh_shell_state()
            return

        schema_state = compare_snapshot_schema(snapshot)
        if schema_state != 0:
            self.state.footer.message = "Backup format is not compatible yet."
            self.state.footer.details = (
                f"Current settings format {SNAPSHOT_SCHEMA}; backup format {snapshot.get('schema', 'unknown')} "
                f"from app {snapshot.get('app_version', 'unknown')}. "
                "Use a compatible backup or start with clean settings."
            )
            self.refresh_shell_state()
            return

        restored = apply_app_state_snapshot(self.state, snapshot)
        audit = audit_snapshot_structure(snapshot)
        try:
            result = save_settings_snapshot_with_backup(export_app_state(self.state))
        except SettingsStoreError as exc:
            self.state.footer.message = "Backup loaded, but save failed."
            self.state.footer.details = str(exc)
        else:
            self._settings_upgrade_pending = False
            self.state.mark_settings_saved()
            self.state.footer.message = f"Backup restored: {backup_path.name}"
            self.state.footer.details = (
                f"Restored {len(restored)} settings. Current file replaced: "
                f"{result.settings_path.name}; {audit.summary}"
            )
        self._render_content()
        self.refresh_shell_state()

    def _set_page(self, page: str):
        if self.current_page == page:
            return
        self.current_page = page
        for key, button in self.nav_buttons.items():
            button.set_active(key == page)
        self._render_content()
        self._maybe_auto_refresh_dualsense_page()
        self._maybe_auto_refresh_sound_to_haptic_page()

    def _maybe_auto_refresh_dualsense_page(self) -> None:
        if self.current_page != "select_dualsense":
            return
        if self.state.dualsense_device.refresh_attempted:
            return
        if self._dualsense_auto_refresh_scheduled:
            return
        self._dualsense_auto_refresh_scheduled = True
        QTimer.singleShot(0, self._auto_refresh_dualsense_candidates)

    def _auto_refresh_dualsense_candidates(self) -> None:
        self._dualsense_auto_refresh_scheduled = False
        if self.current_page != "select_dualsense":
            return
        if self.state.dualsense_device.refresh_attempted:
            return
        self._request_dualsense_refresh()

    def _maybe_auto_refresh_sound_to_haptic_page(self) -> None:
        if self.current_page != "sound_to_haptic":
            return
        if self.state.sound_to_haptic.refresh_attempted:
            return
        if self._sound_to_haptic_auto_refresh_scheduled:
            return
        self._sound_to_haptic_auto_refresh_scheduled = True
        QTimer.singleShot(0, self._auto_refresh_sound_to_haptic_candidates)

    def _auto_refresh_sound_to_haptic_candidates(self) -> None:
        self._sound_to_haptic_auto_refresh_scheduled = False
        if self.current_page != "sound_to_haptic":
            return
        if self.state.sound_to_haptic.refresh_attempted:
            return
        self._request_sound_to_haptic_refresh()

    def _clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            child_layout = item.layout()
            widget = item.widget()
            if child_layout is not None:
                self._clear_layout(child_layout)
            if widget is not None:
                widget.hide()
                widget.deleteLater()

    def _capture_scroll_positions(self) -> dict[str, int]:
        positions = dict(self._scroll_positions)
        for scroll in self.findChildren(CompactScrollArea):
            key = scroll.property("scroll_key")
            if isinstance(key, str) and key:
                positions[key] = scroll.verticalScrollBar().value()
        self._scroll_positions = positions
        return dict(positions)

    def _schedule_scroll_restore(self, positions: dict[str, int]) -> None:
        if not positions:
            return

        def restore() -> None:
            for scroll in self.findChildren(CompactScrollArea):
                key = scroll.property("scroll_key")
                if not isinstance(key, str) or key not in positions:
                    continue
                bar = scroll.verticalScrollBar()
                value = max(bar.minimum(), min(bar.maximum(), int(positions[key])))
                bar.setValue(value)

        QTimer.singleShot(0, restore)
        QTimer.singleShot(30, restore)

    def _build_content(self) -> QWidget:
        outer = QWidget()
        layout = QVBoxLayout(outer)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        body = QWidget()
        body_layout = QVBoxLayout(body)
        body_layout.setContentsMargins(8, 8, 8, 8)
        body_layout.setSpacing(6)
        self.content_layout = body_layout
        self._render_content()

        layout.addWidget(body, 1)
        return outer

    def _render_content(self):
        if self.content_layout is None:
            return
        scroll_positions = self._capture_scroll_positions()
        try:
            self._clear_layout(self.content_layout)
            if self.current_page == "select_dualsense":
                self.content_layout.addWidget(
                    build_dualsense_select_page(
                        self._request_dualsense_test_save,
                        self._request_dualsense_refresh,
                        self._request_dualsense_save_device,
                        self._request_dualsense_cancel,
                        self._select_dualsense_candidate,
                        self._request_dualsense_real_output_test,
                        self._request_dualsense_real_output_stop,
                        self.state,
                    ),
                    1,
                )
                return
            if self.current_page == "trigger":
                panels = QHBoxLayout()
                panels.setSpacing(8)
                callbacks = self._trigger_callbacks()
                panels.addWidget(build_trigger_panel(callbacks, self.state), 1)
                panels.addWidget(build_trigger_advanced_panel(callbacks, self.state), 1)
                self.content_layout.addLayout(panels, 1)
                return
            if self.current_page == "hud":
                self.content_layout.addWidget(build_hud_dashboard_page(self._hud_callbacks(), self.state), 1)
                return
            if self.current_page == "telemetry":
                self.content_layout.addWidget(build_telemetry_page(self._telemetry_callbacks(), self.state), 1)
                return
            if self.current_page == "options":
                self.content_layout.addWidget(build_options_page(self._option_callbacks(), self.state), 1)
                return
            if self.current_page == "sound_to_haptic":
                self.content_layout.addWidget(build_sound_to_haptic_page(self._sound_to_haptic_callbacks(), self.state), 1)
                return
            panels = QHBoxLayout()
            panels.setSpacing(8)
            callbacks = self._haptic_callbacks()
            panels.addWidget(build_haptic_panel(callbacks, self.state), 1)
            panels.addWidget(build_advanced_panel(callbacks, self.state), 1)
            self.content_layout.addLayout(panels, 1)
        finally:
            self._schedule_scroll_restore(scroll_positions)

    def _refresh_current_page_from_telemetry(self) -> None:
        if self.current_page != "telemetry" or self.content_layout is None:
            return
        if self.content_layout.count() != 1:
            self._render_content()
            return
        page = self.content_layout.itemAt(0).widget()
        if page is None or not refresh_telemetry_page(page, self.state):
            self._render_content()

    def _request_dualsense_refresh(self):
        self._apply_bridge_result(self.engine.refresh_dualsense_candidates())
        self._render_content()
        self.refresh_shell_state()

    def _request_dualsense_test_save(self):
        self._apply_bridge_result(self.engine.test_dualsense_haptic())
        self._render_content()
        self.refresh_shell_state()

    def _request_dualsense_save_device(self):
        save_result = self.engine.save_dualsense_device()
        self._apply_bridge_result(save_result)
        saved_device = self.state.dualsense_device.selected_device.strip()
        if save_result.changed:
            self._save_current_settings(
                "DualSense device saved to settings",
                f"Device: {saved_device}.",
            )
            QMessageBox.information(
                self,
                "DualSense Device Saved",
                f"The following device has been registered:\n\n{saved_device}",
            )
            self._apply_bridge_result(self.engine.start_output_service_for_selected_device())
        else:
            QMessageBox.warning(
                self,
                "DualSense Device Not Saved",
                (
                    "The selected device could not be registered.\n\n"
                    f"Selected device: {saved_device or 'None'}\n\n"
                    f"{save_result.details}"
                ),
            )
        self._render_content()
        self.refresh_shell_state()

    def _request_output_service_startup(self):
        has_saved_device = bool(self.state.dualsense_device.selected_device.strip())
        result = self.engine.start_output_service_for_selected_device()
        if has_saved_device:
            self._apply_bridge_result(result)
        self.refresh_shell_state()

    def _request_dualsense_real_output_test(self):
        result = self.engine.start_output_service_real_test()
        self._apply_bridge_result(result)
        if result.changed:
            QTimer.singleShot(500, self._request_dualsense_haptic_probe)
        self._render_content()
        self.refresh_shell_state()

    def _request_dualsense_real_output_stop(self):
        self._apply_bridge_result(self.engine.stop_output_service_real_test())
        self._render_content()
        self.refresh_shell_state()

    def _request_dualsense_haptic_probe(self):
        self._apply_bridge_result(self.engine.send_haptic_test_event())
        self.refresh_shell_state()

    def _request_dualsense_cancel(self):
        self.state.mark_dualsense_cancelled()
        self._render_content()
        self.refresh_shell_state()

    def _select_dualsense_candidate(self, device_name: str):
        self.state.select_dualsense_candidate(device_name)
        self._render_content()
        self.refresh_shell_state()

    def _sound_to_haptic_callbacks(self):
        return {
            "refresh": lambda checked=False: self._request_sound_to_haptic_refresh(),
            "select_capture": lambda device_name: self._select_sound_to_haptic_capture(device_name),
            "save_capture": lambda checked=False: self._request_sound_to_haptic_save_capture(),
            "start": lambda checked=False: self._request_sound_to_haptic_start(),
            "stop": lambda checked=False: self._request_sound_to_haptic_stop(),
            "apply": lambda checked=False: self._request_sound_to_haptic_apply(),
            "master_gain": lambda value: self._set_sound_to_haptic_master_gain(value),
            "low_volume_cut": lambda value: self._set_sound_to_haptic_low_volume_cut(value),
            "high_cut_hz_step": lambda value: self._set_sound_to_haptic_high_cut_hz(value * 1000),
            "dynamic_boost": lambda value: self._set_sound_to_haptic_dynamic_boost(value),
        }

    def _request_sound_to_haptic_refresh(self):
        result = self.sound_to_haptic_runtime.list_capture_devices()
        if result.ok:
            self.state.set_sound_to_haptic_capture_candidates(list(result.devices), result.details)
        else:
            self.state.set_sound_to_haptic_capture_candidates([], result.details)
            self.state.footer.message = "Sound to Haptic device scan failed."
            self.state.footer.details = result.details
        self._render_content()
        self.refresh_shell_state()

    def _select_sound_to_haptic_capture(self, device_name: str):
        self.state.select_sound_to_haptic_capture_device(device_name)
        self._render_content()
        self.refresh_shell_state()

    def _request_sound_to_haptic_save_capture(self):
        self.state.save_sound_to_haptic_capture_device()
        saved_device = self.state.sound_to_haptic.capture_device.strip()
        if saved_device:
            self._save_current_settings(
                "Sound to Haptic capture saved to settings",
                f"Capture source: {saved_device}.",
            )
            QMessageBox.information(
                self,
                "Sound To Haptic Capture Saved",
                f"The following playback capture source has been registered:\n\n{saved_device}",
            )
        self._render_content()
        self.refresh_shell_state()

    def _request_sound_to_haptic_start(self):
        highlighted = self.state.sound_to_haptic.highlighted_capture_device.strip()
        saved = self.state.sound_to_haptic.capture_device.strip()
        if highlighted and highlighted != saved:
            self.state.save_sound_to_haptic_capture_device()
        result = self.sound_to_haptic_runtime.start(self.state)
        self.state.mark_sound_to_haptic_running(result.ok, result.details)
        if result.ok:
            self.state.sound_to_haptic.settings_dirty = False
            self._save_current_settings("Sound to Haptic started", result.details)
        self._render_content()
        self.refresh_shell_state()

    def _request_sound_to_haptic_stop(self):
        result = self.sound_to_haptic_runtime.stop()
        self.state.mark_sound_to_haptic_running(False, result.details)
        self._render_content()
        self.refresh_shell_state()

    def _request_sound_to_haptic_apply(self):
        if self.sound_to_haptic_runtime.is_running():
            result = self.sound_to_haptic_runtime.start(self.state)
            self.state.mark_sound_to_haptic_running(result.ok, result.details)
            if result.ok:
                self.state.sound_to_haptic.settings_dirty = False
        else:
            self.state.sound_to_haptic.last_result = "Sound To Haptic settings are ready."
            self.state.footer.message = "Sound to Haptic settings applied."
            self.state.footer.details = "Start Sound Haptic to use the saved capture source with these filter values."
            self.state.sound_to_haptic.settings_dirty = False
        self._save_current_settings("Sound to Haptic settings saved", self.state.footer.details)
        self._render_content()
        self.refresh_shell_state()

    def _set_sound_to_haptic_master_gain(self, value: int):
        self.state.set_sound_to_haptic_master_gain(value)
        self.refresh_shell_state()

    def _set_sound_to_haptic_low_volume_cut(self, value: int):
        self.state.set_sound_to_haptic_low_volume_cut(value)
        self.refresh_shell_state()

    def _set_sound_to_haptic_high_cut_hz(self, value: int):
        self.state.set_sound_to_haptic_high_cut_hz(value)
        self.refresh_shell_state()

    def _set_sound_to_haptic_dynamic_boost(self, value: int):
        self.state.set_sound_to_haptic_dynamic_boost(value)
        self.refresh_shell_state()

    def _option_callbacks(self):
        return {
            "language_main": lambda source: self._show_main_ui_language_menu(source),
            "language_tooltip": lambda source: self._show_tooltip_language_menu(source),
            "main_ui_scale_value": lambda value: self._set_main_ui_scale(value),
            "preset_shortcut_toggle": lambda checked=False: self._toggle_preset_shortcut(),
            "preset_shortcut_capture": lambda checked=False: self._begin_preset_shortcut_capture(),
            "preset_shortcut_apply": lambda checked=False: self._apply_preset_shortcut(),
            "telemetry_relay_toggle": lambda checked=False: self._toggle_telemetry_relay(),
            "telemetry_relay_host_value": lambda value: self._set_telemetry_relay_host(value),
            "telemetry_relay_port_value": lambda value: self._set_telemetry_relay_port(value),
            "telemetry_relay_apply": lambda checked=False: self._apply_telemetry_relay(),
            "dsx_bridge_toggle": lambda checked=False: self._toggle_dsx_bridge(),
            "dsx_host_value": lambda value: self._set_dsx_host(value),
            "dsx_port_value": lambda value: self._set_dsx_port(value),
            "dsx_audio_toggle": lambda checked=False: self._toggle_dsx_audio_export(),
            "dsx_audio_device_select": lambda source: self._request_dsx_audio_device_select(source),
            "dsx_audio_volume_value": lambda value: self._set_dsx_audio_volume(value),
            "dsx_audio_volume_apply": lambda checked=False: self._apply_dsx_audio_volume(),
            "update_check": lambda checked=False: self._check_for_updates(),
        }

    def _request_option_action(self, action_name: str):
        self.state.mark_option_action_requested(action_name)
        self.refresh_shell_state()

    def _cycle_main_ui_language(self):
        self.state.cycle_main_ui_language()
        self._render_content()
        self.refresh_shell_state()

    def _cycle_tooltip_language(self):
        self.state.cycle_tooltip_language()
        self._render_content()
        self.refresh_shell_state()

    def _show_main_ui_language_menu(self, source_widget):
        self._show_language_menu(
            source_widget,
            ui_text("Main UI Language", self.state.options.main_ui_language),
            self.state.options.main_ui_language,
            MAIN_UI_LANGUAGES,
            self._set_main_ui_language,
        )

    def _show_tooltip_language_menu(self, source_widget):
        self._show_language_menu(
            source_widget,
            ui_text("Tooltip Language", self.state.options.main_ui_language),
            self.state.options.tooltip_language,
            TOOLTIP_LANGUAGES,
            self._set_tooltip_language,
        )

    def _show_language_menu(self, source_widget, title: str, current: str, languages: tuple[str, ...], setter):
        menu = QMenu(self)
        header = menu.addAction(title)
        header.setEnabled(False)
        menu.addSeparator()
        actions = {}
        for code in languages:
            label = LANGUAGE_MENU_LABELS.get(code, code)
            action_text = f"{label} [{code}]" if label != code else code
            action = menu.addAction(action_text)
            action.setCheckable(True)
            action.setChecked(code == current)
            actions[action] = code
        selected = menu.exec(source_widget.mapToGlobal(source_widget.rect().bottomLeft()))
        if selected in actions:
            setter(actions[selected])

    def _set_main_ui_language(self, language: str):
        self.state.set_main_ui_language(language)
        self._render_content()
        self.refresh_shell_state()

    def _set_tooltip_language(self, language: str):
        self.state.set_tooltip_language(language)
        self._render_content()
        self.refresh_shell_state()

    def _set_main_ui_scale(self, scale: int):
        target_scale = _normalize_main_ui_scale(scale)
        if target_scale == self.state.options.main_ui_scale:
            self.state.footer.message = f"Main UI scale is already {target_scale}%."
            self.state.footer.details = "No restart is required."
            self.refresh_shell_state()
            return
        if not self._confirm_main_ui_scale_restart(target_scale):
            self.state.footer.message = "Main UI scale change cancelled."
            self.state.footer.details = f"Current Main UI Scale remains {self.state.options.main_ui_scale}%."
            self._render_content()
            self.refresh_shell_state()
            return
        self.state.set_main_ui_scale(target_scale)
        if not self._save_current_settings(
            "Main UI scale saved",
            "Restarting the app to apply the selected scale.",
        ):
            self.refresh_shell_state()
            return
        if self._restart_app():
            self.close()
            return
        self.state.footer.message = "Main UI scale saved, but restart failed."
        self.state.footer.details = "Please close and reopen the app manually to apply the selected scale."
        self._render_content()
        self.refresh_shell_state()

    def _toggle_preset_shortcut(self):
        self.state.toggle_preset_shortcut()
        self._render_content()
        self.refresh_shell_state()

    def _begin_preset_shortcut_capture(self):
        options = self.state.options
        options.preset_shortcut_capture_active = True
        options.preset_shortcut_pending_combo = "Hold DualSense shortcut..."
        self._preset_shortcut_capture_candidate = ""
        self._preset_shortcut_capture_timer.stop()
        self.state.footer.message = "Preset shortcut capture is waiting."
        self.state.footer.details = "Hold the DualSense button combination for a moment, then press Apply."
        self._render_content()
        self.refresh_shell_state()

    def _schedule_preset_shortcut_capture_finish(self):
        self._preset_shortcut_capture_timer.stop()
        self._preset_shortcut_capture_timer.start(360)

    def _finish_preset_shortcut_capture(self):
        options = self.state.options
        if not options.preset_shortcut_capture_active:
            return
        combo = _normalize_dualsense_combo_text(self._preset_shortcut_capture_candidate)
        if not combo:
            options.preset_shortcut_pending_combo = "Hold DualSense shortcut..."
            self.state.footer.message = "Preset shortcut capture is waiting."
            self.state.footer.details = "No DualSense button combination has been detected yet."
            self._render_content()
            self.refresh_shell_state()
            return
        options.preset_shortcut_pending_combo = combo
        options.preset_shortcut_capture_active = False
        self._preset_shortcut_capture_candidate = ""
        self._preset_shortcut_previous_combo = combo
        self.state.footer.message = f"Captured DualSense shortcut: {combo}"
        self.state.footer.details = "Press Apply to store this shortcut."
        self._render_content()
        self.refresh_shell_state()

    def _apply_preset_shortcut(self):
        options = self.state.options
        pending = str(options.preset_shortcut_pending_combo or "").strip()
        if options.preset_shortcut_capture_active or pending.endswith("..."):
            self.state.footer.message = "Preset shortcut capture is still active."
            self.state.footer.details = "Release the buttons for a moment, then press Apply after the captured shortcut appears."
            self.refresh_shell_state()
            return
        if not pending or pending.startswith("Hold DualSense"):
            self.state.footer.message = "Preset shortcut was not changed."
            self.state.footer.details = "Click the shortcut field and hold a DualSense button combination first."
            self.refresh_shell_state()
            return
        combo = _normalize_dualsense_combo_text(pending)
        if not combo:
            self.state.footer.message = "Preset shortcut was not changed."
            self.state.footer.details = "The captured shortcut was empty or invalid."
            self.refresh_shell_state()
            return
        options.preset_shortcut_combo = combo
        options.preset_shortcut_pending_combo = combo
        options.preset_shortcut_capture_active = False
        self._preset_shortcut_capture_candidate = ""
        self._preset_shortcut_capture_timer.stop()
        self.state.apply_preset_shortcut()
        self.state.mark_unsaved_changes()
        self._save_current_settings("Preset shortcut saved", f"Shortcut: {combo}.")
        self._render_content()
        self.refresh_shell_state()

    def _toggle_telemetry_relay(self):
        self.state.toggle_telemetry_relay()
        self._apply_bridge_result(self.engine.apply_telemetry_relay())
        self._render_content()
        self.refresh_shell_state()

    def _set_telemetry_relay_host(self, value: str):
        self.state.set_telemetry_relay_host(value)
        self.refresh_shell_state()

    def _set_telemetry_relay_port(self, value: str):
        self.state.set_telemetry_relay_port(value)
        self.refresh_shell_state()

    def _apply_telemetry_relay(self):
        self.state.apply_telemetry_relay()
        self._apply_bridge_result(self.engine.apply_telemetry_relay())
        self.refresh_shell_state()

    def _toggle_dsx_bridge(self):
        self.state.toggle_dsx_bridge()
        if not self.state.options.dsx_bridge_enabled:
            self._apply_bridge_result(self.engine.reset_triggers("DSX bridge disabled"))
        self._apply_bridge_result(self.engine.apply_external_output_settings())
        self._render_content()
        self.refresh_shell_state()

    def _set_dsx_host(self, value: str):
        self.state.set_dsx_host(value)
        self.refresh_shell_state()

    def _set_dsx_port(self, value: str):
        self.state.set_dsx_port(value)
        self.refresh_shell_state()

    def _toggle_dsx_audio_export(self):
        self.state.toggle_dsx_audio_export()
        self._apply_bridge_result(self.engine.apply_external_output_settings())
        self._render_content()
        self.refresh_shell_state()

    def _request_dsx_audio_device_select(self, source_widget=None):
        self.state.request_dsx_audio_device_select()
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            devices, result = self.engine.refresh_dsx_audio_output_devices()
        finally:
            QApplication.restoreOverrideCursor()
        self._apply_bridge_result(result)
        if not devices:
            self.refresh_shell_state()
            return

        language = self.state.options.main_ui_language
        current = str(self.state.options.dsx_audio_device).strip()
        menu = QMenu(self)
        header = menu.addAction(ui_text("Audio Output Device Select", language))
        header.setEnabled(False)
        menu.addSeparator()
        actions = {}
        for device_name in devices:
            action = menu.addAction(device_name)
            action.setCheckable(True)
            action.setChecked(device_name == current)
            actions[action] = device_name
        if source_widget is not None:
            anchor = source_widget.mapToGlobal(source_widget.rect().bottomLeft())
        else:
            anchor = self.mapToGlobal(self.rect().center())
        selected = menu.exec(anchor)
        if selected in actions:
            selected_device = actions[selected]
            if selected_device == current:
                self.state.footer.message = "DSX audio output device unchanged."
                self.state.footer.details = f"Output device: {current}"
            else:
                self.state.set_dsx_audio_device(selected_device)
                self._apply_bridge_result(self.engine.apply_external_output_settings())
            self._render_content()
        self.refresh_shell_state()

    def _set_dsx_audio_volume(self, value: int):
        self.state.set_dsx_audio_volume(value)
        self.refresh_shell_state()

    def _apply_dsx_audio_volume(self):
        self.state.apply_dsx_audio_volume()
        self._apply_bridge_result(self.engine.apply_external_output_settings())
        self._render_content()
        self.refresh_shell_state()

    def _check_for_updates(self):
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = check_latest_release(APP_VERSION)
        finally:
            QApplication.restoreOverrideCursor()

        if not result.ok:
            QMessageBox.warning(
                self,
                "Update Check Failed",
                (
                    "Could not check GitHub releases.\n\n"
                    f"{result.error}\n\n"
                    "This is different from being up to date."
                ),
            )
            self.state.footer.message = "Update check failed."
            self.state.footer.details = result.error
            self.refresh_shell_state()
            return

        if result.update_available:
            answer = QMessageBox.question(
                self,
                "Update Available",
                (
                    "A newer release is available on GitHub.\n\n"
                    f"Current version: {result.current_version}\n"
                    f"Latest version: {result.latest_version}\n\n"
                    "Open the GitHub release page?"
                ),
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.Yes,
            )
            self.state.footer.message = f"Update available: v{result.latest_version}"
            self.state.footer.details = result.release_name or "GitHub release found."
            if answer == QMessageBox.Yes and result.release_url:
                QDesktopServices.openUrl(QUrl(result.release_url))
            self.refresh_shell_state()
            return

        QMessageBox.information(
            self,
            "No Update Available",
            (
                "You are using the latest GitHub release.\n\n"
                f"Current version: {result.current_version}\n"
                f"Latest version: {result.latest_version}"
            ),
        )
        self.state.footer.message = "No update available."
        self.state.footer.details = f"Latest GitHub release: v{result.latest_version}"
        self.refresh_shell_state()

    def _hud_callbacks(self):
        callbacks = {
            "hud_all_toggle": lambda checked=False: self._toggle_hud_all(),
            "standby_hide_toggle": lambda checked=False: self._toggle_standby_hide(),
            "hud_location_reset": lambda checked=False: self._request_hud_location_reset(),
            "snap_hud_toggle": lambda checked=False: self._toggle_snap_hud(),
            "snap_pixel_down": lambda checked=False: self._adjust_snap_pixel(-1),
            "snap_pixel_up": lambda checked=False: self._adjust_snap_pixel(1),
            "all_hud_scale_down": lambda checked=False: self._adjust_all_hud_scale(-10),
            "all_hud_scale_up": lambda checked=False: self._adjust_all_hud_scale(10),
            "all_hud_scale_reset": lambda checked=False: self._reset_all_hud_scale(),
            "all_hud_opacity_down": lambda checked=False: self._adjust_all_hud_opacity(-10),
            "all_hud_opacity_up": lambda checked=False: self._adjust_all_hud_opacity(10),
            "all_hud_opacity_reset": lambda checked=False: self._reset_all_hud_opacity(),
            "speed_unit_cycle": lambda checked=False: self._cycle_speed_unit(),
            "power_unit_cycle": lambda checked=False: self._cycle_power_unit(),
            "boost_unit_cycle": lambda checked=False: self._cycle_boost_unit(),
            "rpm_style_cycle": lambda checked=False: self._cycle_rpm_style(),
            "rpm_style_select": lambda style: self._select_rpm_style(style),
        }
        for name in HUD_NAMES:
            key = name.lower().replace("-", "").replace(" ", "_")
            callbacks[f"{key}_toggle"] = (
                lambda checked=False, hud_name=name: self._toggle_hud_item(hud_name)
            )
            callbacks[f"{key}_scale_down"] = (
                lambda checked=False, hud_name=name: self._adjust_hud_scale(hud_name, -25)
            )
            callbacks[f"{key}_scale_up"] = (
                lambda checked=False, hud_name=name: self._adjust_hud_scale(hud_name, 25)
            )
            callbacks[f"{key}_opacity_down"] = (
                lambda checked=False, hud_name=name: self._adjust_hud_opacity(hud_name, -10)
            )
            callbacks[f"{key}_opacity_up"] = (
                lambda checked=False, hud_name=name: self._adjust_hud_opacity(hud_name, 10)
            )
        return callbacks

    def _request_hud_action(self, action_name: str):
        self.state.mark_hud_action_requested(action_name)
        self.refresh_shell_state()

    def _toggle_hud_all(self):
        self.state.toggle_hud_all()
        self._render_content()
        self.refresh_shell_state()

    def _toggle_standby_hide(self):
        self.state.toggle_standby_hide()
        self._render_content()
        self.refresh_shell_state()

    def _request_hud_location_reset(self):
        self.state.request_hud_location_reset()
        self.refresh_shell_state()

    def _toggle_snap_hud(self):
        self.state.toggle_snap_hud()
        self._render_content()
        self.refresh_shell_state()

    def _adjust_snap_pixel(self, delta: int):
        self.state.adjust_snap_pixel(delta)
        self._render_content()
        self.refresh_shell_state()

    def _toggle_hud_item(self, name: str):
        self.state.toggle_hud_item(name)
        self.refresh_shell_state()

    def _adjust_hud_scale(self, name: str, delta: int):
        self.state.adjust_hud_scale(name, delta)
        self._render_content()
        self.refresh_shell_state()

    def _adjust_all_hud_scale(self, delta: int):
        self.state.adjust_all_hud_scale(delta)
        self._render_content()
        self.refresh_shell_state()

    def _reset_all_hud_scale(self):
        self.state.reset_all_hud_scale()
        self._render_content()
        self.refresh_shell_state()

    def _adjust_hud_opacity(self, name: str, delta: int):
        self.state.adjust_hud_opacity(name, delta)
        self._render_content()
        self.refresh_shell_state()

    def _adjust_all_hud_opacity(self, delta: int):
        self.state.adjust_all_hud_opacity(delta)
        self._render_content()
        self.refresh_shell_state()

    def _reset_all_hud_opacity(self):
        self.state.reset_all_hud_opacity()
        self._render_content()
        self.refresh_shell_state()

    def _cycle_speed_unit(self):
        self.state.cycle_speed_unit()
        self._render_content()
        self.refresh_shell_state()

    def _cycle_rpm_style(self):
        self.state.cycle_rpm_style()
        self._render_content()
        self.refresh_shell_state()

    def _select_rpm_style(self, style: str):
        self.state.set_rpm_style(style)
        self._render_content()
        self.refresh_shell_state()

    def _cycle_power_unit(self):
        self.state.cycle_power_unit()
        self._render_content()
        self.refresh_shell_state()

    def _cycle_boost_unit(self):
        self.state.cycle_boost_unit()
        self._render_content()
        self.refresh_shell_state()

    def _telemetry_callbacks(self):
        callbacks = {
            f"telemetry_card_{index}_select": (
                lambda telemetry_name, card_index=index: self._set_telemetry_card(card_index, telemetry_name)
            )
            for index in range(len(self.state.telemetry.cards))
        }
        if self.developer_mode:
            callbacks["inject_test_packet"] = lambda checked=False: self._inject_test_telemetry_packet()
        return callbacks

    def _set_telemetry_card(self, index: int, telemetry_name: str):
        self.state.set_telemetry_card(index, telemetry_name)
        self._render_content()
        self.refresh_shell_state()

    def _inject_test_telemetry_packet(self):
        if not self.developer_mode:
            return
        from .telemetry_test_packets import build_test_telemetry_packet

        packet = build_test_telemetry_packet(self.state.game_mode, self._test_packet_tick)
        self._test_packet_tick += 1
        self.telemetry_receiver.push_test_packet(packet)
        self._poll_telemetry_receiver()
        self.refresh_shell_state()

    def _haptic_callbacks(self):
        callbacks = {
            "eq_boost_gain": lambda checked=False: self._apply_haptic_low_boost_gain(),
        }
        effects = [
            "Gear Shift Bite - Core",
            "Gear Shift Bite - High Hz",
            "Gear Shift Bite - Particles",
            "Rumble Kerbs",
            "Tire Limit Load",
            "Wheelspin Buzz",
            "Acceleration G Punch - Haptic",
            "Rev Limit",
            "Road Bumps",
            "Impacts",
            "Impact - Side",
        ]
        advanced = [
            "Bump Sensitivity",
            "Low Class Correction",
            "Small Bump Strength",
            "Large Bump Strength",
            "Low Bump Hz",
            "High Bump Hz",
            "Attack",
            "Decay",
        ]

        def row_key(name: str) -> str:
            return name.lower().replace("-", "").replace("/", "").replace(" ", "_")

        for name in effects:
            key = row_key(name)
            callbacks[f"{key}_select"] = (
                lambda checked=False, effect_name=name: self._select_haptic_effect(effect_name)
            )
            callbacks[f"{key}_toggle"] = (
                lambda checked=False, effect_name=name: self._toggle_haptic_effect(effect_name)
            )
            callbacks[f"{key}_value"] = (
                lambda value, effect_name=name: self._set_haptic_effect_value(effect_name, value)
            )
            callbacks[f"{key}_value_finished"] = self._finish_effect_slider_edit
        for name in advanced:
            callbacks[f"advanced_{row_key(name)}_value"] = (
                lambda value, setting_name=name: self._set_haptic_advanced_value(setting_name, value)
            )
        callbacks["haptic_detail_value"] = (
            lambda detail_key, value: self._set_haptic_detail_value(detail_key, value)
        )
        return callbacks

    def _request_haptic_action(self, action_name: str):
        self.state.mark_haptic_action_requested(action_name)
        self._apply_bridge_result(self.engine.apply_haptic_settings())
        self.refresh_shell_state()

    def _apply_haptic_low_boost_gain(self):
        self.state.apply_haptic_low_boost_gain()
        self._apply_bridge_result(self.engine.apply_haptic_low_boost_gain())
        self.refresh_shell_state()

    def _set_haptic_effect_value(self, name: str, value: int):
        self.state.set_haptic_effect_value(name, value)
        self.refresh_shell_state()

    def _finish_effect_slider_edit(self):
        QTimer.singleShot(0, self._render_content)

    def _select_haptic_effect(self, name: str):
        self.state.select_haptic_effect(name)
        self._render_content()
        self.refresh_shell_state()

    def _set_haptic_detail_value(self, key: str, value: int):
        self.state.set_haptic_detail_value(key, value)
        self.refresh_shell_state()

    def _toggle_haptic_effect(self, name: str):
        self.state.toggle_haptic_effect(name)
        self._render_content()
        self.refresh_shell_state()

    def _set_haptic_advanced_value(self, name: str, value: int):
        self.state.set_haptic_advanced_value(name, value)
        self.refresh_shell_state()

    def _trigger_callbacks(self):
        callbacks = {}
        effects = [
            "Drift Rumble Fade",
            "Brake Pressure",
            "Brake Resistance",
            "Brake Resistance - Predictive",
            "Gear Shift Kick",
            "Collision Kick",
            "Kerb Wave",
            "Throttle Pressure",
            "Throttle Resistance - Traction",
            "Acceleration G Punch",
            "Shift Down Howl",
            "RPM Rev Limit",
            "Impact Tick",
        ]
        advanced = [
            "Start Position",
            "End Position",
            "Resistance Strength",
            "Slip Release",
            "Return Delay",
            "Brake Force Blend",
        ]

        def row_key(name: str) -> str:
            return name.lower().replace("-", "").replace("/", "").replace(" ", "_")

        for name in effects:
            key = row_key(name)
            callbacks[f"{key}_select"] = (
                lambda checked=False, effect_name=name: self._select_trigger_effect(effect_name)
            )
            callbacks[f"{key}_toggle"] = (
                lambda checked=False, effect_name=name: self._toggle_trigger_effect(effect_name)
            )
        for name in advanced:
            callbacks[f"advanced_{row_key(name)}_value"] = (
                lambda value, setting_name=name: self._set_trigger_advanced_value(setting_name, value)
            )
        callbacks["trigger_detail_value"] = (
            lambda detail_key, value: self._set_trigger_detail_value(detail_key, value)
        )
        return callbacks

    def _request_trigger_action(self, action_name: str):
        self.state.mark_trigger_action_requested(action_name)
        self._apply_bridge_result(self.engine.apply_trigger_settings())
        self.refresh_shell_state()

    def _select_trigger_effect(self, name: str):
        self.state.select_trigger_effect(name)
        self._render_content()
        self.refresh_shell_state()

    def _set_trigger_detail_value(self, key: str, value):
        self.state.set_trigger_detail_value(key, value)
        if isinstance(value, (bool, str)):
            self._render_content()
        self.refresh_shell_state()

    def _toggle_trigger_effect(self, name: str):
        self.state.toggle_trigger_effect(name)
        self._render_content()
        self.refresh_shell_state()

    def _set_trigger_advanced_value(self, name: str, value: int):
        self.state.set_trigger_advanced_value(name, value)
        self.refresh_shell_state()

def main() -> int:
    _apply_startup_main_ui_scale()
    app = QApplication(sys.argv)
    app.setStyle("Fusion")
    app.setStyleSheet(stylesheet())
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
