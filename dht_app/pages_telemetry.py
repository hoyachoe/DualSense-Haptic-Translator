from collections.abc import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ui_theme import COLORS
from .ui_widgets import CompactScrollArea, TelemetryCard
from .app_state import AppState, default_output_graph_item, is_output_graph_item, output_graph_items, telemetry_items_for_game
from .runtime_execution_guard import developer_mode_enabled
from .tooltip_texts import action_tooltip, telemetry_tooltip
from .ui_texts import ui_text


TelemetryCallbacks = dict[str, Callable[..., None]]


def refresh_telemetry_page(page: QWidget, state: AppState) -> bool:
    """Refresh live values without replacing controls that may own mouse focus."""
    telemetry = state.telemetry
    card_widgets = getattr(page, "telemetry_card_widgets", None)
    if not isinstance(card_widgets, list) or len(card_widgets) != len(telemetry.cards):
        return False

    for index, (card, card_widget) in enumerate(zip(telemetry.cards, card_widgets)):
        card_name = card.name
        is_output_card = index == len(telemetry.cards) - 1
        if is_output_card and not is_output_graph_item(card_name):
            return False
        if not isinstance(card_widget, TelemetryCard) or card_widget.telemetry_name != card_name:
            return False

        value_text = (
            state.output_graph_display_value_for(card_name)
            if is_output_card
            else telemetry.display_value_for(card_name)
        )
        card_widget.update_live_data(value_text, telemetry.samples_for(card_name))
    return True


def build_telemetry_page(
    callbacks: TelemetryCallbacks | None = None,
    state: AppState | None = None,
) -> QWidget:
    telemetry = state.telemetry if state is not None else AppState().telemetry
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

    header = QHBoxLayout()
    title = QLabel(ui_text("Telemetry", ui_language))
    title.setObjectName("PanelTitle")
    title.setToolTip(telemetry_tooltip("Telemetry", language))
    note = QLabel(ui_text("Click a graph title to choose telemetry fields for the selected game.", ui_language))
    note.setObjectName("TelemetryHint")
    note.setToolTip(action_tooltip("telemetry_note", language))
    header.addWidget(title)
    header.addSpacing(8)
    header.addWidget(note)
    if developer_mode_enabled():
        inject = QPushButton("Inject Test Packet")
        inject.setObjectName("DangerButton")
        inject.setToolTip(action_tooltip("inject_test_packet", language))
        if callbacks is not None and "inject_test_packet" in callbacks:
            inject.clicked.connect(callbacks["inject_test_packet"])
        header.addSpacing(8)
        header.addWidget(inject)
    header.addStretch(1)
    layout.addLayout(header)

    scroll = CompactScrollArea()
    scroll.setObjectName("PanelScroll")
    scroll.setProperty("scroll_key", "telemetry_cards")
    scroll.viewport().setObjectName("PanelViewport")
    scroll.viewport().setAttribute(Qt.WA_StyledBackground, True)
    content = QWidget()
    content.setObjectName("PanelCanvas")
    content.setAttribute(Qt.WA_StyledBackground, True)
    content_layout = QVBoxLayout(content)
    content_layout.setContentsMargins(0, 0, 5, 0)
    content_layout.setSpacing(4)
    card_widgets: list[TelemetryCard] = []

    for index, card in enumerate(telemetry.cards):
        callback = None
        if callbacks is not None:
            callback = callbacks.get(f"telemetry_card_{index}_select")
        is_output_card = state is not None and index == len(telemetry.cards) - 1
        card_name = card.name
        if is_output_card and not is_output_graph_item(card_name):
            card_name = default_output_graph_item()
            card.name = card_name
        if is_output_card and state is not None:
            items = output_graph_items()
            value_text = state.output_graph_display_value_for(card_name)
            samples = telemetry.samples_for(card_name)
            tooltip = action_tooltip("telemetry_output_graph", language)
            hint_text = ui_text("click name to choose output effect", ui_language)
        else:
            items = telemetry_items_for_game(state.game_mode if state is not None else AppState().game_mode)
            value_text = telemetry.display_value_for(card_name)
            samples = telemetry.samples_for(card_name)
            tooltip = telemetry_tooltip(card_name, language)
            hint_text = ui_text("click name to change telemetry", ui_language)
        color = "#f5f7fa" if is_output_card else COLORS.get(card.color_key, COLORS["accent_2"])
        card_widget = TelemetryCard(
            card_name,
            card.pattern,
            color,
            callback,
            items,
            value_text,
            samples,
            tooltip,
            hint_text,
            action_tooltip("telemetry_current_value", language),
        )
        card_widgets.append(card_widget)
        content_layout.addWidget(card_widget, 1)

    page.telemetry_card_widgets = card_widgets
    scroll.setWidget(content)
    layout.addWidget(scroll, 1)
    page_layout.addWidget(panel, 1)
    return page
