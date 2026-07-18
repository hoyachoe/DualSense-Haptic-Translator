from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QVBoxLayout, QWidget

from .ui_theme import COLORS
from .app_state import AppState
from .runtime_execution_guard import check_real_output_execution_guard
from .tooltip_texts import action_tooltip, nav_tooltip
from .ui_texts import ui_text


def build_dualsense_select_page(
    on_test_save=None,
    on_refresh=None,
    on_save_device=None,
    on_cancel=None,
    on_select_candidate=None,
    on_real_output_test=None,
    on_real_output_stop=None,
    state: AppState | None = None,
) -> QWidget:
    device_state = state.dualsense_device if state is not None else AppState().dualsense_device
    language = state.options.tooltip_language if state is not None else "EN"
    ui_language = state.options.main_ui_language if state is not None else "EN"
    page = QWidget()
    page_layout = QHBoxLayout(page)
    page_layout.setContentsMargins(0, 0, 0, 0)
    page_layout.setSpacing(10)
    left_col = QWidget()
    left_layout = QVBoxLayout(left_col)
    left_layout.setContentsMargins(0, 0, 0, 0)
    left_layout.setSpacing(0)

    panel = QFrame()
    panel.setObjectName("Panel")
    layout = QVBoxLayout(panel)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(9)

    title = QLabel(ui_text("Select DualSense Audio Device", ui_language))
    title.setObjectName("PanelTitle")
    title.setToolTip(nav_tooltip("select_dualsense", language))
    subtitle = QLabel(
        ui_text(
            "Choose the DualSense audio device used for haptic output. USB is recommended. Select a device, test haptics, then save it.",
            ui_language,
        )
    )
    subtitle.setToolTip(nav_tooltip("select_dualsense", language))
    subtitle.setStyleSheet(f"color: {COLORS['muted']}; font-size: 9px; font-weight: 800;")
    subtitle.setWordWrap(True)

    device_row = QHBoxLayout()
    device_row.setContentsMargins(0, 0, 0, 0)
    device_row.setSpacing(8)

    device_list = QFrame()
    device_list.setObjectName("DeviceList")
    device_list.setMinimumHeight(196)
    device_layout = QVBoxLayout(device_list)
    device_layout.setContentsMargins(0, 0, 0, 0)
    device_layout.setSpacing(0)

    section = QLabel(ui_text("Current candidates", ui_language))
    section.setObjectName("DeviceSectionLabel")
    device_layout.addWidget(section)

    if not device_state.candidates:
        empty = QLabel(
            ui_text("No current DualSense candidate has been confirmed yet.", ui_language)
            if not device_state.refresh_attempted
            else ui_text("No current DualSense candidate found.", ui_language)
        )
        empty.setObjectName("DeviceEmpty")
        empty.setWordWrap(True)
        device_layout.addWidget(empty)

    for candidate in device_state.candidates:
        selected = candidate == device_state.highlighted_device
        device_button = QPushButton(candidate)
        device_button.setObjectName("DeviceCandidateSelected" if selected else "DeviceCandidate")
        device_button.setFixedHeight(22)
        device_button.setCursor(Qt.PointingHandCursor)
        device_button.setToolTip(action_tooltip("device_current_candidate", language))
        if on_select_candidate is not None:
            device_button.clicked.connect(
                lambda checked=False, device_name=candidate: on_select_candidate(device_name)
            )
        device_layout.addWidget(device_button)

    device_layout.addStretch(1)

    registered_panel = QFrame()
    registered_panel.setObjectName("DeviceList")
    registered_panel.setMinimumHeight(196)
    registered_layout = QVBoxLayout(registered_panel)
    registered_layout.setContentsMargins(0, 0, 0, 0)
    registered_layout.setSpacing(0)

    registered_label = QLabel(ui_text("Registered device", ui_language))
    registered_label.setObjectName("DeviceSectionLabel")
    registered_layout.addWidget(registered_label)

    saved_device = device_state.selected_device.strip()
    saved_text = saved_device or ui_text("No saved device", ui_language)
    saved_box = QLabel(saved_text)
    saved_box.setObjectName("DeviceSavedBox" if saved_device else "DeviceEmpty")
    saved_box.setWordWrap(True)
    saved_box.setToolTip(action_tooltip("saved_device", language))
    registered_layout.addWidget(saved_box)

    history_label = QLabel(ui_text("Saved history", ui_language))
    history_label.setObjectName("DeviceSectionLabel")
    registered_layout.addWidget(history_label)

    registered_items = [
        candidate
        for candidate in device_state.registered_candidates
        if candidate
    ]
    if not registered_items:
        empty_registered = QLabel(ui_text("No registered device history yet.", ui_language))
        empty_registered.setObjectName("DeviceEmpty")
        empty_registered.setWordWrap(True)
        registered_layout.addWidget(empty_registered)
    for candidate in registered_items:
        selected = candidate == device_state.highlighted_device
        device_button = QPushButton(candidate)
        device_button.setObjectName("DeviceCandidateSelected" if selected else "DeviceCandidateRegistered")
        device_button.setFixedHeight(22)
        device_button.setCursor(Qt.PointingHandCursor)
        device_button.setToolTip(action_tooltip("device_registered_candidate", language))
        if on_select_candidate is not None:
            device_button.clicked.connect(
                lambda checked=False, device_name=candidate: on_select_candidate(device_name)
            )
        registered_layout.addWidget(device_button)
    registered_layout.addStretch(1)

    device_row.addWidget(device_list, 7)
    device_row.addWidget(registered_panel, 3)

    notice = QLabel(ui_text("Current candidates are refreshed from Windows. Registered device is the saved output target.", ui_language))
    notice.setObjectName("DeviceNotice")
    notice.setWordWrap(True)
    selected_text = device_state.selected_device or ui_text("No saved device", ui_language)
    status = QLabel(f"{ui_text('Saved device', ui_language)}: {selected_text}\n{ui_text('Last test', ui_language)}: {device_state.last_test_result}")
    status.setObjectName("TelemetryHint")
    status.setWordWrap(True)

    actions = QHBoxLayout()
    actions.setSpacing(6)
    test = QPushButton(ui_text("Test Haptic", ui_language))
    test.setObjectName("PrimaryButton")
    test.setToolTip(action_tooltip("test_haptic", language))
    if on_test_save is not None:
        test.clicked.connect(on_test_save)
    refresh = QPushButton(ui_text("Refresh", ui_language))
    refresh.setToolTip(action_tooltip("refresh_devices", language))
    if on_refresh is not None:
        refresh.clicked.connect(on_refresh)
    save = QPushButton(ui_text("Save Device", ui_language))
    save.setObjectName("PrimaryButton")
    save.setToolTip(action_tooltip("save_device", language))
    if on_save_device is not None:
        save.clicked.connect(on_save_device)
    actions.addWidget(test)
    actions.addStretch(1)
    actions.addWidget(refresh)
    actions.addWidget(save)

    guard = check_real_output_execution_guard()
    if guard.allowed:
        dev_actions = QHBoxLayout()
        dev_actions.setSpacing(6)
        dev_note = QLabel(ui_text("Developer real-output test mode is enabled for this process.", ui_language))
        dev_note.setObjectName("DeveloperNotice")
        dev_note.setWordWrap(True)
        real_test = QPushButton(ui_text("Real Output Test", ui_language))
        real_test.setObjectName("DangerButton")
        real_test.setToolTip(action_tooltip("real_output_test", language))
        real_stop = QPushButton(ui_text("Stop Test", ui_language))
        real_stop.setObjectName("SecondaryButton")
        real_stop.setToolTip(action_tooltip("real_output_stop", language))
        if on_real_output_test is not None:
            real_test.clicked.connect(on_real_output_test)
        if on_real_output_stop is not None:
            real_stop.clicked.connect(on_real_output_stop)
        dev_actions.addWidget(real_test)
        dev_actions.addWidget(real_stop)
        dev_actions.addStretch(1)

    layout.addWidget(title)
    layout.addWidget(subtitle)
    layout.addLayout(device_row, 1)
    layout.addWidget(notice)
    layout.addWidget(status)
    layout.addLayout(actions)
    if guard.allowed:
        layout.addWidget(dev_note)
        layout.addLayout(dev_actions)

    left_layout.addWidget(panel, 4)
    left_layout.addStretch(1)
    page_layout.addWidget(left_col, 14)
    page_layout.addStretch(1)
    return page
