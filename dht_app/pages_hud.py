from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ui_theme import COLORS
from .ui_widgets import HudRow, OptionCard
from .app_state import DEBUG_HUD_NAMES, AppState, HudState
from .runtime_execution_guard import developer_mode_enabled
from .tooltip_texts import action_tooltip, hud_tooltip, option_tooltip
from .ui_texts import ui_text


HudCallbacks = dict[str, Callable[..., None]]


def _make_option_field(text: str, width: int | None = None) -> QLabel:
    field = QLabel(text)
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


def _connect_callback(widget, callbacks: HudCallbacks | None, key: str) -> None:
    if callbacks is not None and key in callbacks:
        widget.clicked.connect(callbacks[key])


def _callback(callbacks: HudCallbacks | None, key: str):
    if callbacks is None:
        return None
    return callbacks.get(key)


def _hud_key(name: str) -> str:
    return name.lower().replace("-", "").replace(" ", "_")


def _make_step_button(text: str, callback_key: str, callbacks: HudCallbacks | None) -> QPushButton:
    button = QPushButton(text)
    button.setObjectName("HudStepButton")
    button.setFixedWidth(20)
    button.setCursor(Qt.PointingHandCursor)
    _connect_callback(button, callbacks, callback_key)
    return button


def _make_global_row(
    label: str,
    down_key: str,
    up_key: str,
    callbacks: HudCallbacks | None,
) -> QHBoxLayout:
    row = QHBoxLayout()
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    row.addWidget(_make_option_label(label))
    row.addWidget(_make_step_button("-", down_key, callbacks))
    row.addWidget(_make_step_button("+", up_key, callbacks))
    return row


def build_hud_global_card(hud: HudState, callbacks: HudCallbacks | None = None, ui_language: str = "EN", tooltip_language: str = "EN") -> OptionCard:
    card = OptionCard(ui_text("HUD Global", ui_language), tooltip_text=option_tooltip("HUD Global", tooltip_language))
    controls_row = QHBoxLayout()
    controls_row.setContentsMargins(0, 0, 0, 0)
    controls_row.setSpacing(14)
    controls_row.addLayout(
        _make_global_row(ui_text("All HUD Scale", ui_language), "all_hud_scale_down", "all_hud_scale_up", callbacks)
    )
    controls_row.addLayout(
        _make_global_row(ui_text("All HUD Opacity", ui_language), "all_hud_opacity_down", "all_hud_opacity_up", callbacks)
    )
    controls_row.addStretch(1)
    card.layout.addLayout(controls_row)
    reset_row = QHBoxLayout()
    reset_row.setContentsMargins(0, 0, 0, 0)
    reset_row.setSpacing(8)
    reset_scale = _make_option_button(ui_text("Reset Scale", ui_language), 92)
    reset_opacity = _make_option_button(ui_text("Reset Opacity", ui_language), 104)
    reset_scale.setToolTip(action_tooltip("hud_reset_scale", tooltip_language))
    reset_opacity.setToolTip(action_tooltip("hud_reset_opacity", tooltip_language))
    _connect_callback(reset_scale, callbacks, "all_hud_scale_reset")
    _connect_callback(reset_opacity, callbacks, "all_hud_opacity_reset")
    reset_row.addWidget(reset_scale)
    reset_row.addWidget(reset_opacity)
    reset_row.addStretch(1)
    card.layout.addLayout(reset_row)
    card.layout.addStretch(1)
    return card


def build_hud_units_card(hud: HudState, callbacks: HudCallbacks | None = None, ui_language: str = "EN", tooltip_language: str = "EN") -> OptionCard:
    card = OptionCard(ui_text("HUD Units", ui_language), tooltip_text=option_tooltip("HUD Units", tooltip_language))
    row_layout = QHBoxLayout()
    row_layout.setContentsMargins(0, 0, 0, 0)
    row_layout.setSpacing(7)
    units = [
        ("Speed", hud.speed_unit, "speed_unit_cycle"),
        ("Power", hud.power_unit, "power_unit_cycle"),
        ("Boost", hud.boost_unit, "boost_unit_cycle"),
    ]
    tooltip_keys = {
        "Speed": "hud_unit_speed",
        "Power": "hud_unit_power",
        "Boost": "hud_unit_boost",
    }
    for name, value, callback_key in units:
        row_layout.addWidget(_make_option_label(ui_text(name, ui_language)))
        button = _make_option_button(value, 58)
        button.setToolTip(action_tooltip(tooltip_keys[name], tooltip_language))
        _connect_callback(button, callbacks, callback_key)
        row_layout.addWidget(button)
        row_layout.addSpacing(6)
    row_layout.addStretch(1)
    card.layout.addLayout(row_layout)
    style_row = QHBoxLayout()
    style_row.setContentsMargins(0, 0, 0, 0)
    style_row.setSpacing(7)
    style_label = _make_option_label(ui_text("RPM Style", ui_language))
    style_row.addWidget(style_label)
    style_callback = _callback(callbacks, "rpm_style_select")
    for style in ("Classic", "Modern", "Digital Bar"):
        style_button = _make_option_button(ui_text(style, ui_language), 88)
        style_button.setProperty("active", "true" if style == hud.rpm_style else "false")
        style_button.setToolTip(action_tooltip("hud_rpm_style", tooltip_language))
        if style_callback is not None:
            style_button.clicked.connect(
                lambda checked=False, value=style, callback=style_callback: callback(value)
            )
        style_row.addWidget(style_button)
    style_row.addStretch(1)
    card.layout.addLayout(style_row)
    card.layout.addStretch(1)
    return card


def build_hud_dashboard_page(callbacks: HudCallbacks | None = None, state: AppState | None = None) -> QWidget:
    hud = state.hud if state is not None else HudState()
    language = state.options.tooltip_language if state is not None else "EN"
    ui_language = state.options.main_ui_language if state is not None else "EN"
    page = QWidget()
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(0)

    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(8)

    title = QLabel(ui_text("HUD Dashboard", ui_language))
    title.setObjectName("PanelTitle")
    layout.addWidget(title)

    toolbar = QHBoxLayout()
    toolbar.setSpacing(6)
    regular_huds = [
        item
        for name, item in hud.items.items()
        if not name.startswith("Debug ")
    ]
    all_enabled = all(item.enabled for item in regular_huds)
    all_toggle = QPushButton(ui_text("All HUD ON" if all_enabled else "All HUD OFF", ui_language))
    all_toggle.setObjectName("PrimaryButton")
    all_toggle.setFixedWidth(88)
    all_toggle.setToolTip(action_tooltip("hud_all_toggle", language))
    _connect_callback(all_toggle, callbacks, "hud_all_toggle")
    standby = QPushButton(ui_text("Standby Hide ON" if hud.standby_hide else "Standby Hide OFF", ui_language))
    standby.setFixedWidth(108)
    standby.setToolTip(action_tooltip("standby_hide", language))
    _connect_callback(standby, callbacks, "standby_hide_toggle")
    reset = QPushButton(ui_text("HUD Location Reset", ui_language))
    reset.setFixedWidth(128)
    reset.setToolTip(action_tooltip("hud_location_reset", language))
    _connect_callback(reset, callbacks, "hud_location_reset")
    snap = QPushButton(ui_text("Snap HUD ON" if hud.snap_enabled else "Snap HUD OFF", ui_language))
    snap.setObjectName("PrimaryButton")
    snap.setFixedWidth(84)
    snap.setToolTip(action_tooltip("snap_hud", language))
    _connect_callback(snap, callbacks, "snap_hud_toggle")
    snap_label = QLabel(ui_text("Snap Pixel", ui_language))
    snap_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 8px; font-weight: 900;")
    snap_value = QLabel(str(hud.snap_pixel))
    snap_value.setObjectName("ValueBadge")
    snap_value.setAlignment(Qt.AlignCenter)
    snap_value.setFixedWidth(28)
    snap_minus = QPushButton("-")
    snap_minus.setObjectName("HudStepButton")
    snap_minus.setFixedWidth(20)
    snap_minus.setToolTip(action_tooltip("snap_pixel_down", language))
    _connect_callback(snap_minus, callbacks, "snap_pixel_down")
    snap_plus = QPushButton("+")
    snap_plus.setObjectName("HudStepButton")
    snap_plus.setFixedWidth(20)
    snap_plus.setToolTip(action_tooltip("snap_pixel_up", language))
    _connect_callback(snap_plus, callbacks, "snap_pixel_up")
    toolbar.addWidget(all_toggle)
    toolbar.addWidget(standby)
    toolbar.addSpacing(8)
    toolbar.addWidget(reset)
    toolbar.addSpacing(26)
    toolbar.addWidget(snap)
    toolbar.addWidget(snap_label)
    toolbar.addWidget(snap_value)
    toolbar.addWidget(snap_minus)
    toolbar.addWidget(snap_plus)
    toolbar.addStretch(1)
    layout.addLayout(toolbar)

    hud_controls_row = QHBoxLayout()
    hud_controls_row.setContentsMargins(0, 0, 0, 0)
    hud_controls_row.setSpacing(10)
    hud_controls_row.addWidget(build_hud_global_card(hud, callbacks, ui_language, language), 1)
    hud_controls_row.addWidget(build_hud_units_card(hud, callbacks, ui_language, language), 1)
    layout.addLayout(hud_controls_row)

    section = QLabel(ui_text("Active HUD", ui_language))
    section.setObjectName("TriggerGroup")
    layout.addWidget(section)

    hud_area = QHBoxLayout()
    hud_area.setContentsMargins(0, 0, 0, 0)
    hud_area.setSpacing(0)

    content = QWidget()
    content_layout = QGridLayout(content)
    content_layout.setContentsMargins(0, 0, 0, 0)
    content_layout.setHorizontalSpacing(12)
    content_layout.setVerticalSpacing(8)

    show_developer_huds = developer_mode_enabled()
    hud_items = [
        (name, item)
        for name, item in hud.items.items()
        if show_developer_huds or name not in DEBUG_HUD_NAMES
    ]
    for index, (name, item) in enumerate(hud_items):
        key = _hud_key(name)
        row = QFrame()
        row.setObjectName("SubPanel")
        row_layout = QVBoxLayout(row)
        row_layout.setContentsMargins(7, 6, 7, 6)
        row_layout.addWidget(
            HudRow(
                name,
                f"{item.scale}%",
                item.enabled,
                _callback(callbacks, f"{key}_toggle"),
                _callback(callbacks, f"{key}_scale_down"),
                _callback(callbacks, f"{key}_scale_up"),
                f"{item.opacity}%",
                _callback(callbacks, f"{key}_opacity_down"),
                _callback(callbacks, f"{key}_opacity_up"),
                hud_tooltip(name, language),
                {
                    "toggle": action_tooltip("hud_row_toggle", language),
                    "scale": action_tooltip("hud_row_scale", language),
                    "scale_down": action_tooltip("hud_row_scale_down", language),
                    "scale_up": action_tooltip("hud_row_scale_up", language),
                    "opacity": action_tooltip("hud_row_opacity", language),
                    "opacity_value": action_tooltip("hud_row_opacity_value", language),
                    "opacity_down": action_tooltip("hud_row_opacity_down", language),
                    "opacity_up": action_tooltip("hud_row_opacity_up", language),
                },
            )
        )
        content_layout.addWidget(row, index // 2, index % 2)
    hud_area.addWidget(content, 1)
    layout.addLayout(hud_area)
    layout.addStretch(1)

    page_layout.addWidget(panel, 1)
    return page
