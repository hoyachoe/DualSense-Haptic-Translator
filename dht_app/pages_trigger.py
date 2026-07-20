from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from .app_state import AppState
from .detail_schema import (
    TRIGGER_DETAIL_GROUPS,
    detail_value_from_slider,
    format_detail_value,
    grouped_numeric_details,
    grouped_option_details,
)
from .tooltip_texts import detail_tooltip, effect_tooltip
from .ui_theme import COLORS
from .ui_texts import ui_text
from .ui_widgets import AdvancedRow, BoolRow, ChoiceRow, CompactScrollArea, TriggerToggleRow


TriggerCallbacks = dict[str, Callable[..., None]]


def _callback(callbacks: TriggerCallbacks | None, key: str):
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


def build_trigger_panel(callbacks: TriggerCallbacks | None = None, state: AppState | None = None) -> QWidget:
    language = state.options.tooltip_language if state is not None else "EN"
    ui_language = state.options.main_ui_language if state is not None else "EN"
    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(9, 8, 9, 8)
    layout.setSpacing(6)

    header = QHBoxLayout()
    title = QLabel(ui_text("Trigger Effects", ui_language))
    title.setObjectName("PanelTitle")
    header.addWidget(title)
    header.addStretch(1)
    layout.addLayout(header)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.setProperty("scroll_key", "trigger_effects")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("PanelCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 5, 0)
    content_layout.setSpacing(2)

    default_trigger_groups = [
        (
            "L2 Triggers",
            [
                ("Brake Pressure", True),
                ("Brake Resistance", True),
                ("Brake Resistance - Predictive", True),
            ],
        ),
        (
            "L2R2 Triggers",
            [
                ("Gear Shift Kick", True),
                ("Collision Kick", True),
                ("Kerb Wave", True),
            ],
        ),
        (
            "R2 Triggers",
            [
                ("Throttle Pressure", True),
                ("Throttle Resistance - Traction", True),
                ("Acceleration G Punch", True),
                ("Shift Down Howl", True),
                ("RPM Rev Limit", False),
                ("Impact Tick", True),
            ],
        ),
    ]
    if state is None:
        trigger_groups = default_trigger_groups
        drift_enabled = True
    else:
        drift = state.trigger_effects["Drift Rumble Fade"]
        drift_enabled = drift.enabled
        trigger_groups = []
        for group_name, effects in default_trigger_groups:
            group_items = []
            for name, _ in effects:
                setting = state.trigger_effects[name]
                group_items.append((name, setting.enabled))
            trigger_groups.append((group_name, group_items))
    top_row = QFrame()
    top_row.setObjectName("SubPanel")
    if state is not None and state.selected_trigger_effect == "Drift Rumble Fade":
        top_row.setProperty("active", "true")
    top_layout = QVBoxLayout(top_row)
    top_layout.setContentsMargins(6, 2, 6, 2)
    top_layout.addWidget(
        TriggerToggleRow(
            "Drift Rumble Fade",
            drift_enabled,
            _callback(callbacks, "drift_rumble_fade_toggle"),
            _effect_summary("Drift Rumble Fade", language),
            _callback(callbacks, "drift_rumble_fade_select"),
        )
    )
    content_layout.addWidget(top_row)

    for group_name, effects in trigger_groups:
        group = QLabel(group_name)
        group.setObjectName("TriggerGroup")
        content_layout.addWidget(group)
        for name, enabled in effects:
            key = _row_key(name)
            row_frame = QFrame()
            row_frame.setObjectName("SubPanel")
            if state is not None and name == state.selected_trigger_effect:
                row_frame.setProperty("active", "true")
            row_layout = QVBoxLayout(row_frame)
            row_layout.setContentsMargins(6, 2, 6, 2)
            row_layout.addWidget(
                TriggerToggleRow(
                    name,
                    enabled,
                    _callback(callbacks, f"{key}_toggle"),
                    _effect_summary(name, language),
                    _callback(callbacks, f"{key}_select"),
                )
            )
            content_layout.addWidget(row_frame)
    content_layout.addStretch(1)
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    return panel


def build_trigger_advanced_panel(callbacks: TriggerCallbacks | None = None, state: AppState | None = None) -> QWidget:
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

    selected_name = state.selected_trigger_effect if state is not None else "Brake Resistance - Predictive"
    selected = QLabel(selected_name)
    selected.setStyleSheet(f"color: {COLORS['text']}; font-size: 11px; font-weight: 900;")
    layout.addWidget(selected)

    description = QLabel(effect_tooltip(selected_name, language))
    description.setObjectName("TriggerDescription")
    description.setStyleSheet(f"color: {COLORS['muted']}; font-size: 8px;")
    description.setWordWrap(True)
    layout.addWidget(description)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.setProperty("scroll_key", "trigger_advanced")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("PanelCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 5, 0)
    content_layout.setSpacing(3)

    option_groups = []
    detail_groups = []
    if state is not None and selected_name in state.trigger_effects:
        option_groups = grouped_option_details(
            selected_name,
            state.trigger_effects[selected_name].details,
        )
        detail_groups = grouped_numeric_details(
            selected_name,
            state.trigger_effects[selected_name].details,
            TRIGGER_DETAIL_GROUPS,
        )
    if option_groups or detail_groups:
        detail_callback = _callback(callbacks, "trigger_detail_value")
        option_groups_by_title = {group.title: group for group in option_groups}
        rendered_option_titles: set[str] = set()

        def add_option_rows(group) -> None:
            group_label = QLabel(group.title)
            group_label.setObjectName("DetailGroup")
            content_layout.addWidget(group_label)
            for detail in group.rows:
                row = QFrame()
                row.setObjectName("SubPanel")
                row_layout = QVBoxLayout(row)
                row_layout.setContentsMargins(6, 2, 6, 2)
                if detail.kind == "toggle":
                    row_layout.addWidget(
                        BoolRow(
                            detail.label,
                            bool(detail.value),
                            (
                                (lambda new_value, key=detail.key, callback=detail_callback: callback(key, new_value))
                                if detail_callback is not None
                                else None
                            ),
                            description_text=detail_tooltip(detail.key, language),
                        )
                    )
                else:
                    row_layout.addWidget(
                        ChoiceRow(
                            detail.label,
                            str(detail.value),
                            detail.options,
                            (
                                (lambda new_value, key=detail.key, callback=detail_callback: callback(key, new_value))
                                if detail_callback is not None
                                else None
                            ),
                            description_text=detail_tooltip(detail.key, language),
                        )
                    )
                content_layout.addWidget(row)

        for group in detail_groups:
            group_label = QLabel(group.title)
            group_label.setObjectName("DetailGroup")
            content_layout.addWidget(group_label)
            option_group = option_groups_by_title.get(group.title)
            if option_group is not None:
                rendered_option_titles.add(group.title)
                for detail in option_group.rows:
                    row = QFrame()
                    row.setObjectName("SubPanel")
                    row_layout = QVBoxLayout(row)
                    row_layout.setContentsMargins(6, 2, 6, 2)
                    if detail.kind == "toggle":
                        row_layout.addWidget(
                            BoolRow(
                                detail.label,
                                bool(detail.value),
                                (
                                    (lambda new_value, key=detail.key, callback=detail_callback: callback(key, new_value))
                                    if detail_callback is not None
                                    else None
                                ),
                                description_text=detail_tooltip(detail.key, language),
                            )
                        )
                    else:
                        row_layout.addWidget(
                            ChoiceRow(
                                detail.label,
                                str(detail.value),
                                detail.options,
                                (
                                    (lambda new_value, key=detail.key, callback=detail_callback: callback(key, new_value))
                                    if detail_callback is not None
                                    else None
                                ),
                                description_text=detail_tooltip(detail.key, language),
                            )
                        )
                    content_layout.addWidget(row)
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
                            (
                                lambda new_value,
                                key=detail.key,
                                display_style=detail.display_style,
                                callback=detail_callback: callback(
                                    key,
                                    detail_value_from_slider(display_style, new_value),
                                )
                            )
                            if detail_callback is not None
                            else None
                        ),
                        detail.minimum,
                        detail.maximum,
                        value_formatter=(
                            (
                                lambda new_value, detail=detail: format_detail_value(
                                    detail.display_style,
                                    new_value,
                                    detail.minimum,
                                    detail.maximum,
                                )
                            )
                            if detail.display_style
                            else None
                        ),
                        description_text=detail_tooltip(detail.key, language),
                    )
                )
                content_layout.addWidget(row)
        for group in option_groups:
            if group.title not in rendered_option_titles:
                add_option_rows(group)
    elif state is not None:
        settings = [
            (name, setting.value, "")
            for name, setting in state.trigger_advanced.items()
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
            ("Start Position", 4, ""),
            ("End Position", 8, ""),
            ("Resistance Strength", 7, ""),
            ("Slip Release", 6, ""),
            ("Return Delay", 3, ""),
            ("Brake Force Blend", 5, ""),
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
