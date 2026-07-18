from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .app_state import AppState
from .detail_schema import HAPTIC_DETAIL_GROUPS, format_detail_value, grouped_numeric_details
from .tooltip_texts import action_tooltip, detail_tooltip, effect_tooltip
from .ui_theme import COLORS
from .ui_texts import ui_text
from .ui_widgets import AdvancedRow, CompactScrollArea, SliderRow


HapticCallbacks = dict[str, Callable[..., None]]


def _connect_callback(widget, callbacks: HapticCallbacks | None, key: str) -> None:
    if callbacks is not None and key in callbacks:
        widget.clicked.connect(callbacks[key])


def _callback(callbacks: HapticCallbacks | None, key: str):
    if callbacks is None:
        return None
    return callbacks.get(key)


def _row_key(name: str) -> str:
    return (
        name.lower()
        .replace("-", "")
        .replace("/", "")
        .replace(" ", "_")
    )


def _effect_summary(name: str, language: str) -> str:
    description = effect_tooltip(name, language)
    return next((line.strip() for line in description.splitlines() if line.strip()), description)


def build_haptic_panel(callbacks: HapticCallbacks | None = None, state: AppState | None = None) -> QWidget:
    language = state.options.tooltip_language if state is not None else "EN"
    ui_language = state.options.main_ui_language if state is not None else "EN"
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(9, 8, 9, 8)
    layout.setSpacing(6)

    header = QHBoxLayout()
    title = QLabel(ui_text("Haptic Effects", ui_language))
    title.setObjectName("PanelTitle")
    header.addWidget(title)
    header.addStretch(1)
    gain = state.options.haptic_low_boost_gain if state is not None else 0
    eq = QPushButton(f"EQ BOOST GAIN {gain}/10")
    eq.setObjectName("PrimaryButton")
    eq.setToolTip(action_tooltip("eq_boost_gain", language))
    _connect_callback(eq, callbacks, "eq_boost_gain")
    header.addWidget(eq)
    header.addSpacing(22)
    layout.addLayout(header)

    selected = QLabel(ui_text("Haptic Strength", ui_language))
    selected.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: 900;")
    layout.addWidget(selected)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.setProperty("scroll_key", "haptic_effects")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("PanelCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 5, 0)
    content_layout.setSpacing(2)

    if state is not None:
        effects = [
            (name, setting.value, setting.enabled)
            for name, setting in state.haptic_effects.items()
        ]
    else:
        effects = [
            ("Gear Shift Bite - Core", 9, True),
            ("Gear Shift Bite - High Hz", 6, True),
            ("Gear Shift Bite - Particles", 6, True),
            ("Rumble Kerbs", 7, True),
            ("Tire Limit Load", 9, True),
            ("Wheelspin Buzz", 4, True),
            ("Acceleration G Punch - Haptic", 6, True),
            ("Rev Limit", 5, False),
            ("Road Bumps", 9, True),
            ("Impacts", 10, True),
            ("Impact - Side", 10, True),
            ("Impact - Smashable", 10, True),
        ]
    for name, value, enabled in effects:
        key = _row_key(name)
        row_frame = QFrame()
        row_frame.setObjectName("SubPanel")
        if state is not None and name == state.selected_haptic_effect:
            row_frame.setProperty("active", "true")
        select_callback = _callback(callbacks, f"{key}_select")
        if select_callback is not None:
            row_frame.setCursor(Qt.PointingHandCursor)
            row_frame.mousePressEvent = lambda event, callback=select_callback: callback()
        row_layout = QVBoxLayout(row_frame)
        row_layout.setContentsMargins(6, 2, 6, 2)
        row_layout.addWidget(
            SliderRow(
                name,
                value,
                enabled,
                _callback(callbacks, f"{key}_toggle"),
                _callback(callbacks, f"{key}_value"),
                on_edit_finished=_callback(callbacks, f"{key}_value_finished"),
                description_text=_effect_summary(name, language),
            )
        )
        content_layout.addWidget(row_frame)
    content_layout.addStretch(1)
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    return panel


def build_advanced_panel(callbacks: HapticCallbacks | None = None, state: AppState | None = None) -> QWidget:
    language = state.options.tooltip_language if state is not None else "EN"
    ui_language = state.options.main_ui_language if state is not None else "EN"
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(9, 8, 9, 8)
    layout.setSpacing(6)

    header = QHBoxLayout()
    title = QLabel(ui_text("Advanced Settings", ui_language))
    title.setObjectName("PanelTitle")
    header.addWidget(title)
    header.addStretch(1)
    layout.addLayout(header)

    selected_name = state.selected_haptic_effect if state is not None else "Road Bumps"
    selected = QLabel(selected_name)
    selected.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: 900;")
    layout.addWidget(selected)

    description = QLabel(effect_tooltip(selected_name, language))
    description.setObjectName("HapticDescription")
    description.setStyleSheet(f"color: {COLORS['muted']}; font-size: 8px;")
    description.setWordWrap(True)
    layout.addWidget(description)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.setProperty("scroll_key", "haptic_advanced")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("PanelCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 5, 0)
    content_layout.setSpacing(3)

    detail_groups = []
    if state is not None and selected_name in state.haptic_effects:
        detail_groups = grouped_numeric_details(
            selected_name,
            state.haptic_effects[selected_name].details,
            HAPTIC_DETAIL_GROUPS,
        )
    if detail_groups:
        detail_callback = _callback(callbacks, "haptic_detail_value")
        for group in detail_groups:
            group_label = QLabel(group.title)
            group_label.setObjectName("DetailGroup")
            content_layout.addWidget(group_label)
            for detail in group.rows:
                row = QFrame()
                row.setObjectName("SubPanel")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(6, 2, 6, 2)
                row_layout.addWidget(
                    AdvancedRow(
                        detail.label,
                        detail.value,
                        "",
                        (
                            (lambda new_value, key=detail.key, callback=detail_callback: callback(key, new_value))
                            if detail_callback is not None
                            else None
                        ),
                        detail.minimum,
                        detail.maximum,
                        value_formatter=(
                            (lambda new_value, detail=detail: format_detail_value(detail.display_style, new_value, detail.minimum, detail.maximum))
                            if detail.display_style
                            else None
                        ),
                        description_text=detail_tooltip(detail.key, language),
                    )
                )
                content_layout.addWidget(row)
    elif state is not None:
        settings = [
            (name, setting.value, "")
            for name, setting in state.haptic_advanced.items()
        ]
        for name, value, hint in settings:
            key = _row_key(name)
            row = QFrame()
            row.setObjectName("SubPanel")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.addWidget(
                AdvancedRow(
                    name,
                    value,
                    hint,
                    _callback(callbacks, f"advanced_{key}_value"),
                    description_text=detail_tooltip(key, language),
                )
            )
            content_layout.addWidget(row)
    else:
        settings = [
            ("Bump Sensitivity", 8, ""),
            ("Low Class Correction", 3, ""),
            ("Small Bump Strength", 7, ""),
            ("Large Bump Strength", 7, ""),
            ("Low Bump Hz", 4, ""),
            ("High Bump Hz", 6, ""),
            ("Attack", 5, ""),
            ("Decay", 5, ""),
        ]
        for name, value, hint in settings:
            key = _row_key(name)
            row = QFrame()
            row.setObjectName("SubPanel")
            row_layout = QVBoxLayout(row)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.addWidget(
                AdvancedRow(
                    name,
                    value,
                    hint,
                    _callback(callbacks, f"advanced_{key}_value"),
                    description_text=detail_tooltip(key, language),
                )
            )
            content_layout.addWidget(row)
    content_layout.addStretch(1)
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    return panel
