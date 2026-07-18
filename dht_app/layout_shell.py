from dataclasses import dataclass
from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ui_theme import COLORS
from .ui_widgets import NavButton, _tinted_svg_icon
from .app_state import AppState, PacketStatus
from .tooltip_texts import action_tooltip, nav_tooltip
from .ui_texts import ui_text


RESOURCE_DIR = Path(__file__).resolve().parent / "Resource"
NAV_ICON_FILES = {
    "select_dualsense": "icon_dualsense_pad.svg",
    "haptic": "icon_Haptic.svg",
    "trigger": "icon_Trigger.svg",
    "hud": "icon_HUD.svg",
    "telemetry": "icon_Telemetry.svg",
    "options": "icon_option.svg",
    "sound_to_haptic": "icon_sound2haptic.svg",
}


@dataclass
class StatusStripRefs:
    udp_port: QPushButton
    led: QLabel
    packet_status: QLabel
    dualsense_status: QLabel
    sound_haptic_icon: QLabel
    sound_haptic_status: QLabel


@dataclass
class SidebarRefs:
    selected_game: QLabel
    selected_preset: QLabel
    save_button: QPushButton


@dataclass
class FooterRefs:
    primary: QLabel
    message: QLabel
    details: QLabel


def apply_status_strip_state(refs: StatusStripRefs, state: AppState) -> None:
    refs.udp_port.setText(str(state.udp_port))
    refs.packet_status.setText(state.packet_status_label)
    if state.packet_status == PacketStatus.RECEIVING:
        refs.led.setStyleSheet(f"background: {COLORS['accent_2']}; border-radius: 4px;")
        refs.packet_status.setStyleSheet(f"color: {COLORS['accent_2']}; font-weight: 900;")
    else:
        refs.led.setStyleSheet(f"background: {COLORS['line']}; border-radius: 4px;")
        refs.packet_status.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 800;")
    refs.dualsense_status.setText(state.dualsense_status_label)
    sound_on = bool(state.sound_to_haptic.running)
    sound_color = COLORS["accent"] if sound_on else COLORS["muted"]
    sound_label = "Sound To Haptic now ON" if sound_on else "Sound To Haptic off"
    icon_path = RESOURCE_DIR / NAV_ICON_FILES["sound_to_haptic"]
    refs.sound_haptic_icon.setPixmap(_tinted_svg_icon(icon_path, sound_color, 14).pixmap(QSize(14, 14)))
    refs.sound_haptic_status.setText(sound_label)
    refs.sound_haptic_status.setStyleSheet(f"color: {sound_color}; font-weight: 900;")


def apply_sidebar_state(refs: SidebarRefs, state: AppState) -> None:
    refs.selected_game.setText(state.selected_game_label)
    refs.selected_preset.setText(state.selected_preset)
    language = state.options.main_ui_language
    refs.save_button.setText(ui_text("SAVE *" if state.unsaved_changes else "SAVE", language))
    refs.save_button.setProperty("unsaved", "true" if state.unsaved_changes else "false")
    refs.save_button.style().unpolish(refs.save_button)
    refs.save_button.style().polish(refs.save_button)


def apply_footer_state(refs: FooterRefs, state: AppState) -> None:
    refs.primary.setText(state.footer.primary)
    refs.message.setText(state.footer.message)
    refs.details.setText(state.footer.details)


def build_status_strip(state: AppState, on_udp_port_requested=None) -> tuple[QWidget, StatusStripRefs]:
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language
    strip = QFrame()
    strip.setObjectName("StatusStrip")
    strip.setFixedHeight(30)
    layout = QHBoxLayout(strip)
    layout.setContentsMargins(11, 0, 11, 0)
    layout.setSpacing(6)

    udp_label = QLabel(ui_text("UDP", ui_language))
    udp_label.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 800;")
    udp_label.setToolTip(action_tooltip("udp_port", language))
    udp_port = QPushButton(str(state.udp_port))
    udp_port.setObjectName("StatusBox")
    udp_port.setFixedWidth(66)
    udp_port.setCursor(Qt.PointingHandCursor)
    udp_port.setToolTip(action_tooltip("udp_port", language))
    if on_udp_port_requested is not None:
        udp_port.clicked.connect(lambda: on_udp_port_requested(udp_port))
    led = QLabel("")
    led.setObjectName("Led")
    led.setToolTip(action_tooltip("packet_status", language))
    waiting = QLabel(state.packet_status_label)
    waiting.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 800;")
    waiting.setToolTip(action_tooltip("packet_status", language))
    separator = QFrame()
    separator.setObjectName("StatusSeparator")
    separator.setFixedWidth(1)
    separator.setFixedHeight(18)
    device = QLabel(state.dualsense_status_label)
    device.setStyleSheet(f"color: {COLORS['accent_2']}; font-weight: 900;")
    device.setToolTip(action_tooltip("dualsense_status", language))
    sound_icon = QLabel("")
    sound_icon.setFixedSize(16, 16)
    sound_icon.setToolTip(nav_tooltip("sound_to_haptic", language))
    sound_status = QLabel("")
    sound_status.setToolTip(nav_tooltip("sound_to_haptic", language))

    layout.addWidget(udp_label)
    layout.addWidget(udp_port)
    layout.addWidget(led)
    layout.addWidget(waiting)
    layout.addSpacing(8)
    layout.addWidget(separator)
    layout.addSpacing(8)
    layout.addWidget(device)
    layout.addStretch(1)
    layout.addWidget(sound_icon)
    layout.addWidget(sound_status)
    refs = StatusStripRefs(udp_port, led, waiting, device, sound_icon, sound_status)
    apply_status_strip_state(refs, state)
    return strip, refs


def build_sidebar(
    current_page: str,
    on_page_selected,
    state: AppState,
    on_select_game=None,
    on_select_preset=None,
    on_load_preset=None,
    on_save=None,
    on_load_backup=None,
) -> tuple[QWidget, dict[str, NavButton], SidebarRefs]:
    side = QFrame()
    side.setObjectName("SideBar")
    side.setFixedWidth(138)
    layout = QVBoxLayout(side)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language

    nav_buttons: dict[str, NavButton] = {}
    items = [
        ("select_dualsense", "SELECT DUALSENSE"),
        ("haptic", "HAPTIC EFFECTS"),
        ("trigger", "TRIGGER EFFECTS"),
        ("hud", "HUD DASHBOARD"),
        ("telemetry", "TELEMETRY"),
        ("options", "OPTIONS"),
        ("sound_to_haptic", "SOUND TO HAPTIC"),
    ]
    for key, text in items:
        if key == "sound_to_haptic":
            layout.addSpacing(18)
        icon_file = NAV_ICON_FILES.get(key, "")
        icon_path = RESOURCE_DIR / icon_file if icon_file else None
        button = NavButton(ui_text(text, ui_language), key == current_page, nav_tooltip(key, language), icon_path)
        button.clicked.connect(lambda checked=False, page=key: on_page_selected(page))
        nav_buttons[key] = button
        layout.addWidget(button)

    layout.addStretch(1)

    action_box = QFrame()
    action_box.setObjectName("SubPanel")
    action_layout = QVBoxLayout(action_box)
    action_layout.setContentsMargins(6, 6, 6, 6)
    action_layout.setSpacing(5)
    select = QPushButton(ui_text("SELECT GAME", ui_language))
    select.setObjectName("PrimaryButton")
    select.setToolTip(action_tooltip("select_game", language))
    if on_select_game is not None:
        select.clicked.connect(lambda checked=False, button=select: on_select_game(button))
    game = QLabel(state.selected_game_label)
    game.setObjectName("GameBox")
    game.setToolTip(action_tooltip("select_game", language))
    save = QPushButton(ui_text("SAVE", ui_language))
    save.setToolTip(action_tooltip("save", language))
    save.setProperty("unsaved", "true" if state.unsaved_changes else "false")
    if on_save is not None:
        save.clicked.connect(on_save)
    backup = QPushButton(ui_text("LOAD BACKUP", ui_language))
    backup.setToolTip(action_tooltip("load_backup", language))
    if on_load_backup is not None:
        backup.clicked.connect(on_load_backup)
    select_preset = QPushButton(ui_text("SELECT PRESET", ui_language))
    select_preset.setToolTip(action_tooltip("select_preset", language))
    if on_select_preset is not None:
        select_preset.clicked.connect(lambda checked=False, button=select_preset: on_select_preset(button))
    preset = QLabel(state.selected_preset)
    preset.setObjectName("PresetBox")
    preset.setToolTip(action_tooltip("select_preset", language))
    load_preset = QPushButton(ui_text("COPY PRESET", ui_language))
    load_preset.setToolTip(action_tooltip("copy_preset", language))
    if on_load_preset is not None:
        load_preset.clicked.connect(lambda checked=False, button=load_preset: on_load_preset(button))
    action_layout.addWidget(select)
    action_layout.addWidget(game)
    action_layout.addWidget(save)
    action_layout.addWidget(backup)
    action_layout.addWidget(select_preset)
    action_layout.addWidget(preset)
    action_layout.addWidget(load_preset)
    layout.addWidget(action_box)
    layout.addSpacing(24)
    return side, nav_buttons, SidebarRefs(game, preset, save)


def build_footer_bar(state: AppState) -> tuple[QWidget, FooterRefs]:
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language
    footer = QFrame()
    footer.setObjectName("FooterBar")
    footer.setFixedHeight(58)

    layout = QHBoxLayout(footer)
    layout.setContentsMargins(10, 5, 10, 5)
    layout.setSpacing(8)

    text_col = QVBoxLayout()
    text_col.setContentsMargins(0, 0, 0, 0)
    text_col.setSpacing(2)

    line1 = QLabel(state.footer.primary)
    line1.setObjectName("FooterPrimary")
    line2 = QLabel(state.footer.message)
    line2.setObjectName("FooterLine")
    line3 = QLabel(state.footer.details)
    line3.setObjectName("FooterLine")

    text_col.addWidget(line1)
    text_col.addWidget(line2)
    text_col.addWidget(line3)

    layout.addLayout(text_col, 1)
    return footer, FooterRefs(line1, line2, line3)
