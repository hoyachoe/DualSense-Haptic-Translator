from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QIntValidator
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from .ui_theme import COLORS
from .ui_texts import ui_text
from .ui_widgets import CompactScrollArea, NoWheelSlider, OptionCard, ToggleButton
from .app_state import AppState, OptionState
from .version import APP_VERSION
from .tooltip_texts import action_tooltip, option_tooltip


OptionCallbacks = dict[str, Callable[..., None]]


def _make_option_field(text: str, width: int | None = None) -> QLabel:
    field = QLabel(text)
    field.setObjectName("OptionField")
    field.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    if width is not None:
        field.setFixedWidth(width)
    return field


def _make_option_input(text: str, width: int | None = None) -> QLineEdit:
    field = QLineEdit(text)
    field.setObjectName("OptionField")
    field.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
    if width is not None:
        field.setFixedWidth(width)
    return field


def _make_option_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("OptionLabel")
    return label


def _make_option_button(text: str, width: int | None = None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("OptionField")
    button.setCursor(Qt.PointingHandCursor)
    if width is not None:
        button.setFixedWidth(width)
    return button


def _connect_callback(widget, callbacks: OptionCallbacks | None, key: str) -> None:
    if callbacks is not None and key in callbacks:
        widget.clicked.connect(callbacks[key])


def _connect_source_callback(widget, callbacks: OptionCallbacks | None, key: str) -> None:
    if callbacks is not None and key in callbacks:
        widget.clicked.connect(lambda checked=False, source=widget: callbacks[key](source))


def _connect_text_callback(field: QLineEdit, callbacks: OptionCallbacks | None, key: str) -> None:
    if callbacks is not None and key in callbacks:
        field.editingFinished.connect(lambda target=field: callbacks[key](target.text()))


def _set_tooltip(widget, text: str) -> None:
    if text:
        widget.setToolTip(text)


def _build_language_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    tooltip = option_tooltip("Language", options.tooltip_language)
    card = OptionCard(
        ui_text("Language", options.main_ui_language),
        "",
        tooltip,
    )
    card.layout.setSpacing(6)
    row = QHBoxLayout()
    row.setSpacing(8)
    main_label = _make_option_label(ui_text("Main UI", options.main_ui_language))
    main_value = _make_option_button(f"[{options.main_ui_language}]", 48)
    _set_tooltip(main_value, action_tooltip("main_ui_language", options.tooltip_language))
    _connect_source_callback(main_value, callbacks, "language_main")
    tooltip_label = _make_option_label(ui_text("Tooltip", options.main_ui_language))
    tooltip_value = _make_option_button(f"[{options.tooltip_language}]", 48)
    _set_tooltip(tooltip_value, action_tooltip("tooltip_language", options.tooltip_language))
    _connect_source_callback(tooltip_value, callbacks, "language_tooltip")
    row.addWidget(main_label)
    row.addWidget(main_value)
    row.addSpacing(16)
    row.addWidget(tooltip_label)
    row.addWidget(tooltip_value)
    row.addStretch(1)
    card.layout.addLayout(row)
    card.setMaximumHeight(104)
    return card


def _build_window_scale_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    card = OptionCard(
        ui_text("Window Scale", options.main_ui_language),
        ui_text("Adjust the main interface scale.", options.main_ui_language),
        ui_text("Changing the main UI scale requires an app restart.", options.main_ui_language),
    )
    row = QHBoxLayout()
    row.setSpacing(6)
    for scale in (90, 100, 110, 125):
        button = _make_option_button(f"{scale}%", 54)
        if scale == options.main_ui_scale:
            button.setProperty("active", "true")
        _set_tooltip(button, action_tooltip("window_scale", options.tooltip_language))
        if callbacks is not None and "main_ui_scale_value" in callbacks:
            button.clicked.connect(lambda checked=False, value=scale: callbacks["main_ui_scale_value"](value))
        row.addWidget(button)
    row.addStretch(1)
    card.layout.addLayout(row)
    card.setMaximumHeight(116)
    return card


def _add_gamepad_shortcut_row(
    card: OptionCard,
    options: OptionState,
    callbacks: OptionCallbacks | None,
    shortcut_name: str,
    label_text: str,
    combo: str,
    capture_active: bool,
) -> None:
    row = QHBoxLayout()
    row.setSpacing(6)
    label = _make_option_label(ui_text(label_text, options.main_ui_language))
    label.setFixedWidth(118)
    row.addWidget(label)

    display_combo = combo if combo else ui_text("None", options.main_ui_language)
    shortcut = _make_option_button(display_combo, 100)
    shortcut.setProperty("shortcutKind", shortcut_name)
    shortcut.setProperty("shortcutAction", "capture")
    if capture_active:
        shortcut.setProperty("active", "true")
    _set_tooltip(shortcut, action_tooltip(f"{shortcut_name}_shortcut_capture", options.tooltip_language))
    _connect_callback(shortcut, callbacks, f"{shortcut_name}_shortcut_capture")
    row.addWidget(shortcut)

    apply = QPushButton(ui_text("Apply", options.main_ui_language))
    apply.setFixedWidth(52)
    apply.setProperty("shortcutKind", shortcut_name)
    apply.setProperty("shortcutAction", "apply")
    _set_tooltip(apply, action_tooltip(f"{shortcut_name}_shortcut_apply", options.tooltip_language))
    _connect_callback(apply, callbacks, f"{shortcut_name}_shortcut_apply")
    row.addWidget(apply)

    delete = QPushButton(ui_text("Delete", options.main_ui_language))
    delete.setFixedWidth(54)
    delete.setProperty("shortcutKind", shortcut_name)
    delete.setProperty("shortcutAction", "delete")
    _set_tooltip(delete, action_tooltip(f"{shortcut_name}_shortcut_delete", options.tooltip_language))
    _connect_callback(delete, callbacks, f"{shortcut_name}_shortcut_delete")
    row.addWidget(delete)
    row.addStretch(1)
    card.layout.addLayout(row)


def _build_gamepad_shortcut_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    tooltip = option_tooltip("Gamepad Shortcut", options.tooltip_language)
    card = OptionCard(
        ui_text("Gamepad Shortcut", options.main_ui_language),
        ui_text("Assign DualSense button combinations. None disables a shortcut.", options.main_ui_language),
        tooltip,
    )
    card.layout.setSpacing(6)
    _add_gamepad_shortcut_row(
        card,
        options,
        callbacks,
        "preset",
        "Preset Shortcut",
        options.preset_shortcut_pending_combo or options.preset_shortcut_combo,
        options.preset_shortcut_capture_active,
    )
    _add_gamepad_shortcut_row(
        card,
        options,
        callbacks,
        "hud",
        "HUD ON/OFF Shortcut",
        options.hud_shortcut_pending_combo or options.hud_shortcut_combo,
        options.hud_shortcut_capture_active,
    )
    card.layout.addStretch(1)
    return card


def _build_app_info_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    card = OptionCard(
        ui_text("App Version", options.main_ui_language),
        ui_text("Check GitHub releases for a newer public version.", options.main_ui_language),
        option_tooltip("App Version", options.tooltip_language),
    )
    row = QHBoxLayout()
    row.setSpacing(8)
    row.addWidget(_make_option_label(ui_text("Current", options.main_ui_language)))
    row.addWidget(_make_option_field(APP_VERSION, 72))
    row.addStretch(1)
    check = QPushButton(ui_text("Check for Updates", options.main_ui_language))
    check.setFixedWidth(128)
    _set_tooltip(check, action_tooltip("update_check", options.tooltip_language))
    _connect_callback(check, callbacks, "update_check")
    row.addWidget(check)
    card.layout.addLayout(row)
    card.setMaximumHeight(112)
    return card


def _build_telemetry_relay_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    tooltip = option_tooltip("Telemetry UDP Relay", options.tooltip_language)
    card = OptionCard(
        ui_text("Telemetry UDP Relay", options.main_ui_language),
        ui_text("Copies the original Forza Data Out UDP packet to another local app, HUD, or simulator device.", options.main_ui_language),
        tooltip,
    )
    toggle_row = QHBoxLayout()
    toggle_row.setSpacing(8)
    off = ToggleButton(options.telemetry_relay_enabled)
    off.setFixedWidth(48)
    _set_tooltip(off, action_tooltip("telemetry_relay_toggle", options.tooltip_language))
    _connect_callback(off, callbacks, "telemetry_relay_toggle")
    toggle_row.addWidget(off)
    toggle_row.addWidget(_make_option_label(ui_text("Forward raw Forza telemetry packets", options.main_ui_language)))
    toggle_row.addStretch(1)
    card.layout.addLayout(toggle_row)

    grid = QGridLayout()
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(6)
    host_field = _make_option_input(options.telemetry_relay_host)
    _set_tooltip(host_field, action_tooltip("telemetry_relay_host", options.tooltip_language))
    _connect_text_callback(host_field, callbacks, "telemetry_relay_host_value")
    port_field = _make_option_input(str(options.telemetry_relay_port))
    port_field.setValidator(QIntValidator(1, 65535, port_field))
    _set_tooltip(port_field, action_tooltip("telemetry_relay_port", options.tooltip_language))
    _connect_text_callback(port_field, callbacks, "telemetry_relay_port_value")
    grid.addWidget(_make_option_label(ui_text("Target Host", options.main_ui_language)), 0, 0)
    grid.addWidget(host_field, 0, 1)
    grid.addWidget(_make_option_label(ui_text("Target Port", options.main_ui_language)), 1, 0)
    grid.addWidget(port_field, 1, 1)
    grid.setColumnStretch(1, 1)
    card.layout.addLayout(grid)

    hint = QLabel(ui_text("Use a different port from the app input. Example: app listens on 8800, relay sends to 9000.", options.main_ui_language))
    hint.setObjectName("TelemetryHint")
    hint.setWordWrap(True)
    card.layout.addWidget(hint)
    apply = QPushButton(ui_text("Apply", options.main_ui_language))
    apply.setFixedWidth(56)
    _set_tooltip(apply, action_tooltip("telemetry_relay_apply", options.tooltip_language))
    _connect_callback(apply, callbacks, "telemetry_relay_apply")
    card.layout.addWidget(apply)
    status = QLabel(ui_text("Telemetry relay on" if options.telemetry_relay_enabled else "Telemetry relay off", options.main_ui_language))
    status.setObjectName("OptionStatus")
    card.layout.addWidget(status)
    return card


def _build_dsx_option_card(options: OptionState, callbacks: OptionCallbacks | None = None) -> OptionCard:
    tooltip = option_tooltip("DSX Output", options.tooltip_language)
    card = OptionCard(
        ui_text("DSX Output", options.main_ui_language),
        ui_text("Send adaptive trigger commands over UDP. Audio export sends the selected source to the chosen playback device.", options.main_ui_language),
        tooltip,
    )

    bridge = QHBoxLayout()
    bridge.setSpacing(8)
    bridge_toggle = ToggleButton(options.dsx_bridge_enabled)
    bridge_toggle.setFixedWidth(48)
    _set_tooltip(bridge_toggle, action_tooltip("dsx_bridge_toggle", options.tooltip_language))
    _connect_callback(bridge_toggle, callbacks, "dsx_bridge_toggle")
    bridge.addWidget(bridge_toggle)
    bridge.addWidget(_make_option_label(ui_text("DSX Trigger UDP Bridge", options.main_ui_language)))
    bridge.addStretch(1)
    card.layout.addLayout(bridge)

    host_grid = QGridLayout()
    host_grid.setHorizontalSpacing(8)
    host_grid.setVerticalSpacing(6)
    dsx_host_field = _make_option_input(options.dsx_host)
    _set_tooltip(dsx_host_field, action_tooltip("dsx_host", options.tooltip_language))
    _connect_text_callback(dsx_host_field, callbacks, "dsx_host_value")
    dsx_port_field = _make_option_input(str(options.dsx_port))
    dsx_port_field.setValidator(QIntValidator(1, 65535, dsx_port_field))
    _set_tooltip(dsx_port_field, action_tooltip("dsx_port", options.tooltip_language))
    _connect_text_callback(dsx_port_field, callbacks, "dsx_port_value")
    host_grid.addWidget(_make_option_label(ui_text("Host", options.main_ui_language)), 0, 0)
    host_grid.addWidget(dsx_host_field, 0, 1)
    host_grid.addWidget(_make_option_label(ui_text("Port", options.main_ui_language)), 1, 0)
    host_grid.addWidget(dsx_port_field, 1, 1)
    host_grid.setColumnStretch(1, 1)
    card.layout.addLayout(host_grid)

    audio = QHBoxLayout()
    audio.setSpacing(8)
    audio_toggle = ToggleButton(options.dsx_audio_export_enabled)
    audio_toggle.setFixedWidth(48)
    _set_tooltip(audio_toggle, action_tooltip("dsx_audio_toggle", options.tooltip_language))
    _connect_callback(audio_toggle, callbacks, "dsx_audio_toggle")
    audio.addWidget(audio_toggle)
    audio.addWidget(_make_option_label(ui_text("Audio Export Mode", options.main_ui_language)))
    audio.addStretch(1)
    card.layout.addLayout(audio)

    separator = QFrame()
    separator.setFrameShape(QFrame.HLine)
    separator.setStyleSheet(f"color: {COLORS['line']}; background: {COLORS['line']};")
    card.layout.addWidget(separator)

    device_title = QLabel(ui_text("Audio Output Device Select", options.main_ui_language))
    device_title.setStyleSheet(f"color: {COLORS['text']}; font-size: 10px; font-weight: 900;")
    device_title.setAlignment(Qt.AlignCenter)
    card.layout.addWidget(device_title)

    device_row = QHBoxLayout()
    device_row.setSpacing(0)
    device_name = options.dsx_audio_device or ui_text("Not selected", options.main_ui_language)
    device_row.addWidget(_make_option_field(device_name), 1)
    plus = QPushButton("+")
    plus.setFixedWidth(48)
    _set_tooltip(plus, action_tooltip("dsx_audio_device_select", options.tooltip_language))
    _connect_source_callback(plus, callbacks, "dsx_audio_device_select")
    device_row.addWidget(plus)
    card.layout.addLayout(device_row)

    volume_row = QHBoxLayout()
    volume_row.setSpacing(8)
    volume_row.addWidget(_make_option_label(ui_text("Haptic Audio Volume", options.main_ui_language)))
    slider = NoWheelSlider(Qt.Horizontal)
    slider.setRange(0, 100)
    slider.setValue(options.dsx_audio_volume)
    slider.setFixedWidth(160)
    _set_tooltip(slider, action_tooltip("dsx_audio_volume", options.tooltip_language))
    if callbacks is not None and "dsx_audio_volume_value" in callbacks:
        slider.valueChanged.connect(callbacks["dsx_audio_volume_value"])
    volume_row.addWidget(slider)
    volume_row.addWidget(_make_option_field(f"{options.dsx_audio_volume}%", 58))
    apply = QPushButton(ui_text("Apply", options.main_ui_language))
    apply.setFixedWidth(56)
    _set_tooltip(apply, action_tooltip("dsx_audio_volume_apply", options.tooltip_language))
    _connect_callback(apply, callbacks, "dsx_audio_volume_apply")
    volume_row.addWidget(apply)
    volume_row.addStretch(1)
    card.layout.addLayout(volume_row)

    status = QLabel(ui_text("DSX UDP on" if options.dsx_bridge_enabled else "DSX UDP off", options.main_ui_language))
    status.setObjectName("OptionStatus")
    card.layout.addWidget(status)
    return card


def build_options_page(callbacks: OptionCallbacks | None = None, state: AppState | None = None) -> QWidget:
    options = state.options if state is not None else OptionState()
    page = QWidget()
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    header = QHBoxLayout()
    title = QLabel(ui_text("Options", options.main_ui_language))
    title.setObjectName("PanelTitle")
    note = QLabel(ui_text("Settings are grouped as compact cards for quick review and release-ready configuration.", options.main_ui_language))
    note.setObjectName("TelemetryHint")
    header.addWidget(title)
    header.addSpacing(8)
    header.addWidget(note)
    header.addStretch(1)
    layout.addLayout(header)

    scroll = CompactScrollArea()
    scroll.setObjectName("OptionsScroll")
    scroll.viewport().setObjectName("OptionsViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("OptionsCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    grid = QGridLayout(content)
    grid.setContentsMargins(0, 0, 5, 0)
    grid.setHorizontalSpacing(8)
    grid.setVerticalSpacing(8)

    relay_wrap = QWidget()
    relay_layout = QHBoxLayout(relay_wrap)
    relay_layout.setContentsMargins(0, 0, 0, 0)
    relay_layout.setSpacing(0)
    relay_layout.addWidget(_build_telemetry_relay_option_card(options, callbacks), 65)
    relay_layout.addStretch(35)

    dsx_wrap = QWidget()
    dsx_layout = QHBoxLayout(dsx_wrap)
    dsx_layout.setContentsMargins(0, 0, 0, 0)
    dsx_layout.setSpacing(0)
    dsx_layout.addWidget(_build_dsx_option_card(options, callbacks), 85)
    dsx_layout.addStretch(15)

    left_stack = QWidget()
    left_layout = QVBoxLayout(left_stack)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(8)
    left_layout.addWidget(_build_window_scale_option_card(options, callbacks))
    left_layout.addWidget(_build_language_option_card(options, callbacks))

    grid.addWidget(left_stack, 0, 0)
    grid.addWidget(_build_gamepad_shortcut_option_card(options, callbacks), 0, 1)
    grid.addWidget(relay_wrap, 1, 0, 1, 2)
    grid.addWidget(dsx_wrap, 2, 0, 1, 2)
    grid.addWidget(_build_app_info_option_card(options, callbacks), 3, 0, 1, 2)
    grid.setColumnStretch(0, 1)
    grid.setColumnStretch(1, 1)
    grid.setRowStretch(4, 1)

    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    page_layout.addWidget(panel, 1)
    return page
