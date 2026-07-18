from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .app_state import AppState
from .tooltip_texts import action_tooltip, nav_tooltip, option_tooltip
from .ui_texts import ui_text
from .ui_theme import COLORS
from .ui_widgets import AdvancedRow, CompactScrollArea, OptionCard


SoundToHapticCallbacks = dict[str, Callable[..., None]]


def _callback(callbacks: SoundToHapticCallbacks | None, key: str):
    if callbacks is None:
        return None
    return callbacks.get(key)


def _connect_callback(widget, callbacks: SoundToHapticCallbacks | None, key: str) -> None:
    callback = _callback(callbacks, key)
    if callback is not None:
        widget.clicked.connect(callback)


def _build_device_button(text: str, selected: bool, callback=None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("DeviceCandidateSelected" if selected else "DeviceCandidate")
    button.setFixedHeight(22)
    button.setCursor(Qt.PointingHandCursor)
    if callback is not None:
        button.clicked.connect(lambda checked=False, value=text: callback(value))
    return button


def _build_capture_card(state: AppState, callbacks: SoundToHapticCallbacks | None) -> QFrame:
    sound = state.sound_to_haptic
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language

    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(9)

    title = QLabel(ui_text("Sound To Haptic", ui_language))
    title.setObjectName("PanelTitle")
    title.setToolTip(nav_tooltip("sound_to_haptic", language))
    subtitle = QLabel(
        ui_text(
            "Convert a selected Windows playback stream into DualSense channels 3/4 haptics.",
            ui_language,
        )
    )
    subtitle.setStyleSheet(f"color: {COLORS['muted']}; font-size: 9px; font-weight: 800;")
    subtitle.setWordWrap(True)
    subtitle.setToolTip(nav_tooltip("sound_to_haptic", language))
    layout.addWidget(title)
    layout.addWidget(subtitle)

    row = QHBoxLayout()
    row.setSpacing(8)

    candidates = QFrame()
    candidates.setObjectName("DeviceList")
    candidates.setMinimumHeight(202)
    candidates_layout = QVBoxLayout(candidates)
    candidates_layout.setContentsMargins(0, 0, 0, 0)
    candidates_layout.setSpacing(0)
    section = QLabel(ui_text("Current playback candidates", ui_language))
    section.setObjectName("DeviceSectionLabel")
    candidates_layout.addWidget(section)

    if not sound.capture_candidates:
        empty_text = (
            ui_text("No playback candidates have been refreshed yet.", ui_language)
            if not sound.refresh_attempted
            else ui_text("No playback candidates found.", ui_language)
        )
        empty = QLabel(empty_text)
        empty.setObjectName("DeviceEmpty")
        empty.setWordWrap(True)
        candidates_layout.addWidget(empty)
    for candidate in sound.capture_candidates:
        selected = candidate == sound.highlighted_capture_device
        button = _build_device_button(
            candidate,
            selected,
            _callback(callbacks, "select_capture"),
        )
        button.setToolTip(action_tooltip("sound_haptic_capture_device", language))
        candidates_layout.addWidget(button)
    candidates_layout.addStretch(1)

    registered = QFrame()
    registered.setObjectName("DeviceList")
    registered.setMinimumHeight(202)
    registered_layout = QVBoxLayout(registered)
    registered_layout.setContentsMargins(0, 0, 0, 0)
    registered_layout.setSpacing(0)
    registered_label = QLabel(ui_text("Registered capture", ui_language))
    registered_label.setObjectName("DeviceSectionLabel")
    registered_layout.addWidget(registered_label)
    saved_device = sound.capture_device.strip()
    saved_box = QLabel(saved_device or ui_text("No saved capture device", ui_language))
    saved_box.setObjectName("DeviceSavedBox" if saved_device else "DeviceEmpty")
    saved_box.setWordWrap(True)
    saved_box.setToolTip(action_tooltip("sound_haptic_capture_device", language))
    registered_layout.addWidget(saved_box)
    registered_layout.addStretch(1)

    row.addWidget(candidates, 7)
    row.addWidget(registered, 3)
    layout.addLayout(row, 1)

    status = QLabel(sound.last_result or ui_text("Sound to Haptic is off.", ui_language))
    status.setObjectName("TelemetryHint")
    status.setWordWrap(True)
    layout.addWidget(status)

    actions = QHBoxLayout()
    actions.setSpacing(6)
    refresh = QPushButton(ui_text("Refresh Capture", ui_language))
    refresh.setToolTip(action_tooltip("sound_haptic_refresh", language))
    _connect_callback(refresh, callbacks, "refresh")
    save = QPushButton(ui_text("Save Capture", ui_language))
    save.setObjectName("PrimaryButton")
    save.setToolTip(action_tooltip("sound_haptic_save_capture", language))
    _connect_callback(save, callbacks, "save_capture")
    actions.addStretch(1)
    actions.addWidget(refresh)
    actions.addWidget(save)
    layout.addLayout(actions)
    return panel


def _build_filter_card(state: AppState, callbacks: SoundToHapticCallbacks | None) -> OptionCard:
    sound = state.sound_to_haptic
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language
    card = OptionCard(
        ui_text("Sound haptic settings", ui_language),
        "",
        option_tooltip("Sound To Haptic", language),
    )
    card.layout.setSpacing(7)

    card.layout.addWidget(
        AdvancedRow(
            ui_text("Master Gain", ui_language),
            sound.master_gain,
            minimum=0,
            maximum=100,
            value_formatter=lambda value: f"{value}%",
            on_value_changed=_callback(callbacks, "master_gain"),
            tooltip_text=action_tooltip("sound_haptic_master_gain", language),
        )
    )
    card.layout.addWidget(
        AdvancedRow(
            ui_text("Low Volume Cut", ui_language),
            sound.low_volume_cut,
            minimum=0,
            maximum=50,
            value_formatter=lambda value: f"{value}%",
            on_value_changed=_callback(callbacks, "low_volume_cut"),
            tooltip_text=action_tooltip("sound_haptic_low_volume_cut", language),
        )
    )
    card.layout.addWidget(
        AdvancedRow(
            ui_text("High Cut Hz", ui_language),
            round(sound.high_cut_hz / 1000),
            minimum=0,
            maximum=24,
            value_formatter=lambda value: "Off" if value <= 0 else f"{value * 1000} Hz",
            on_value_changed=_callback(callbacks, "high_cut_hz_step"),
            tooltip_text=action_tooltip("sound_haptic_high_cut_hz", language),
        )
    )
    card.layout.addWidget(
        AdvancedRow(
            ui_text("Dynamic Boost", ui_language),
            sound.dynamic_boost,
            minimum=0,
            maximum=300,
            value_formatter=lambda value: f"{value}%",
            on_value_changed=_callback(callbacks, "dynamic_boost"),
            tooltip_text=action_tooltip("sound_haptic_dynamic_boost", language),
        )
    )
    apply = QPushButton(ui_text("Apply Settings", ui_language))
    apply.setObjectName("SecondaryButton")
    apply.setFixedWidth(112)
    apply.setProperty("unsaved", "true" if sound.settings_dirty else "false")
    apply.setToolTip(action_tooltip("sound_haptic_apply", language))
    _connect_callback(apply, callbacks, "apply")
    card.layout.addWidget(apply, alignment=Qt.AlignLeft)
    card.layout.addStretch(1)
    return card


def _build_power_card(state: AppState, callbacks: SoundToHapticCallbacks | None) -> QFrame:
    sound = state.sound_to_haptic
    language = state.options.tooltip_language
    ui_language = state.options.main_ui_language
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(10, 10, 10, 10)
    layout.setSpacing(6)

    hint = QLabel(
        ui_text(
            "Optional sound-driven haptics can add audio texture on top of telemetry, or run as a standalone sound-to-haptic mode.",
            ui_language,
        )
    )
    hint.setWordWrap(True)
    hint.setStyleSheet(f"color: {COLORS['muted']}; font-weight: 800;")
    layout.addWidget(hint)

    power = QPushButton(
        ui_text("Stop Sound Haptic", ui_language)
        if sound.running
        else ui_text("Start Sound Haptic", ui_language)
    )
    power.setObjectName("SoundHapticPowerOn" if sound.running else "SoundHapticPowerOff")
    power.setMinimumHeight(54)
    power.setToolTip(
        action_tooltip("sound_haptic_stop", language)
        if sound.running
        else action_tooltip("sound_haptic_start", language)
    )
    _connect_callback(power, callbacks, "stop" if sound.running else "start")
    layout.addWidget(power)
    return panel


def build_sound_to_haptic_page(callbacks: SoundToHapticCallbacks | None = None, state: AppState | None = None) -> QWidget:
    state = state or AppState()
    page = QWidget()
    page.setObjectName("PanelCanvas")
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(10)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.setProperty("scroll_key", "sound_to_haptic_page")
    container = QWidget()
    container.setObjectName("PanelCanvas")
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    right_col = QWidget()
    right_col.setObjectName("PanelCanvas")
    right_layout = QVBoxLayout(right_col)
    right_layout.setContentsMargins(0, 0, 0, 0)
    right_layout.setSpacing(10)
    right_layout.addWidget(_build_filter_card(state, callbacks), 1)
    right_layout.addWidget(_build_power_card(state, callbacks), 0)
    right_layout.addStretch(1)
    layout.addWidget(_build_capture_card(state, callbacks), 7)
    layout.addWidget(right_col, 3)
    scroll.setWidget(container)
    page_layout.addWidget(scroll, 1)
    return page
