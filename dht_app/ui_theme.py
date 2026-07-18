APP_TITLE = "DualSense Haptic Translator"
SLIDER_WIDTH = 116
VALUE_WIDTH = 20
CONTROL_WIDTH = 27
ROW_GAP = 6


COLORS = {
    "bg": "#0b1015",
    "surface": "#111820",
    "surface_2": "#151e28",
    "surface_3": "#1a2632",
    "line": "#273442",
    "text": "#edf4fb",
    "muted": "#8da1b6",
    "faint": "#526474",
    "accent": "#e2267d",
    "accent_outline": "#ff5aa2",
    "accent_2": "#ffd119",
    "cyan": "#23b7ff",
    "green": "#2bd47d",
}


GAME_ACCENTS = {
    "horizon": "#e2267d",
    "motorsport": "#8b5cf6",
}

GAME_ACCENT_OUTLINES = {
    "horizon": "#ff5aa2",
    "motorsport": "#a78bfa",
}


def apply_game_accent(game_mode) -> str:
    value = getattr(game_mode, "value", str(game_mode)).lower()
    accent = GAME_ACCENTS.get(value, GAME_ACCENTS["horizon"])
    outline = GAME_ACCENT_OUTLINES.get(value, GAME_ACCENT_OUTLINES["horizon"])
    COLORS["accent"] = accent
    COLORS["accent_outline"] = outline
    return accent


def stylesheet() -> str:
    return f"""
    QWidget {{
        color: {COLORS["text"]};
        font-family: "Segoe UI", "Malgun Gothic", sans-serif;
        font-size: 9px;
    }}

    QLabel {{
        background: transparent;
    }}

    QMainWindow {{
        background: {COLORS["bg"]};
    }}

    QFrame#SideBar {{
        background: {COLORS["surface"]};
        border-right: 1px solid {COLORS["line"]};
    }}

    QFrame#TopBar {{
        background: {COLORS["surface"]};
        border-bottom: 1px solid {COLORS["line"]};
    }}

    QFrame#WindowShell {{
        background: {COLORS["bg"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
    }}

    QFrame#TitleBar {{
        background: {COLORS["surface"]};
        border-bottom: 1px solid {COLORS["line"]};
        border-top-left-radius: 6px;
        border-top-right-radius: 6px;
    }}

    QLabel#TitleLogo {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
        color: {COLORS["accent"]};
        font-size: 14px;
        font-weight: 900;
    }}

    QLabel#TitleStatus {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 5px;
        color: {COLORS["accent_2"]};
        font-weight: 800;
        padding: 4px 10px;
    }}

    QFrame#StatusStrip {{
        background: {COLORS["bg"]};
        border-bottom: 1px solid {COLORS["line"]};
    }}

    QFrame#FooterBar {{
        background: {COLORS["bg"]};
        border-top: 1px solid {COLORS["line"]};
    }}

    QLabel#StatusBox, QPushButton#StatusBox {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-weight: 900;
        padding: 3px 6px;
        selection-background-color: {COLORS["accent"]};
        selection-color: white;
    }}

    QPushButton#StatusBox:hover {{
        background: #213041;
        border-color: #3b4d61;
    }}

    QLabel#GameBox {{
        background: transparent;
        border: none;
        color: {COLORS["accent_2"]};
        font-size: 9px;
        font-weight: 900;
        padding: 1px 4px 3px 4px;
    }}

    QLabel#PresetBox {{
        background: transparent;
        border: none;
        color: {COLORS["accent_2"]};
        font-size: 10px;
        font-weight: 900;
        padding: 1px 4px 3px 4px;
    }}

    QLabel#FooterPrimary {{
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-size: 9px;
        font-weight: 800;
    }}

    QLabel#FooterLine {{
        color: #b9d8f2;
        font-family: "Consolas", monospace;
        font-size: 9px;
    }}

    QPushButton#LogButton {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["muted"]};
        font-size: 8px;
        font-weight: 800;
        padding: 5px 8px;
    }}

    QPushButton#LogButton:hover {{
        background: #223040;
        color: {COLORS["text"]};
    }}

    QLabel#Led {{
        background: {COLORS["accent_2"]};
        border-radius: 4px;
        min-width: 8px;
        max-width: 8px;
        min-height: 8px;
        max-height: 8px;
    }}

    QFrame#StatusSeparator {{
        background: {COLORS["line"]};
    }}

    QFrame#Panel {{
        background: {COLORS["surface"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
    }}

    QFrame#SubPanel {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 5px;
    }}

    QFrame#SubPanel[active="true"] {{
        background: #1c2936;
        border: 1px solid {COLORS["accent"]};
    }}

    QFrame#TelemetryCard {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
    }}

    QFrame#OptionCard {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
    }}

    QScrollArea#OptionsScroll {{
        background: {COLORS["surface"]};
        border: none;
    }}

    QWidget#OptionsViewport {{
        background: {COLORS["surface"]};
    }}

    QScrollArea#OptionsScroll QWidget#OptionsCanvas {{
        background: {COLORS["surface"]};
    }}

    QScrollArea#PanelScroll {{
        background: {COLORS["surface"]};
        border: none;
    }}

    QWidget#PanelViewport {{
        background: {COLORS["surface"]};
    }}

    QScrollArea#PanelScroll QWidget#PanelCanvas {{
        background: {COLORS["surface"]};
    }}

    QDialog#UdpPortDialog {{
        background: {COLORS["surface"]};
    }}

    QDialog#HapticEqDialog {{
        background: {COLORS["surface"]};
    }}

    QDialog#SettingsRecoveryDialog {{
        background: {COLORS["surface"]};
    }}

    QTextEdit#RecoveryList {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 4px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-size: 9px;
        font-weight: 800;
        padding: 8px;
        selection-background-color: {COLORS["accent"]};
        selection-color: white;
    }}

    QLabel#TelemetryHint {{
        color: {COLORS["muted"]};
        font-size: 8px;
        font-weight: 800;
    }}

    QLabel#TelemetryValue {{
        background: #080e13;
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        font-size: 10px;
        font-weight: 900;
        padding: 3px 7px;
    }}

    QLabel#OptionTitle {{
        color: {COLORS["text"]};
        font-size: 12px;
        font-weight: 900;
    }}

    QLabel#OptionText {{
        color: #b9d8f2;
        font-size: 8px;
        font-weight: 500;
    }}

    QLabel#OptionField {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-size: 10px;
        font-weight: 900;
        padding: 5px 8px;
    }}

    QLabel#OptionField[active="true"] {{
        background: {COLORS["accent"]};
        border-color: {COLORS["accent_outline"]};
        color: white;
    }}

    QPushButton#OptionField {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-size: 10px;
        font-weight: 900;
        padding: 5px 8px;
        text-align: left;
    }}

    QPushButton#OptionField:hover {{
        border-color: {COLORS["accent_2"]};
    }}

    QPushButton#OptionField[active="true"] {{
        background: {COLORS["accent"]};
        border-color: {COLORS["accent_outline"]};
        color: white;
    }}

    QLineEdit#OptionField {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", monospace;
        font-size: 10px;
        font-weight: 900;
        padding: 5px 8px;
        selection-background-color: {COLORS["accent"]};
        selection-color: white;
    }}

    QLabel#OptionLabel {{
        color: #b9d8f2;
        font-size: 8px;
        font-weight: 900;
    }}

    QLabel#OptionStatus {{
        color: {COLORS["muted"]};
        font-family: "Consolas", monospace;
        font-size: 10px;
        font-weight: 900;
    }}

    QFrame#DeviceList {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 4px;
    }}

    QPushButton#DeviceCandidate {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 0px;
        color: {COLORS["text"]};
        font-family: "Consolas", "Malgun Gothic", monospace;
        font-size: 9px;
        font-weight: 800;
        padding: 3px 5px;
        text-align: left;
    }}

    QPushButton#DeviceCandidate:hover {{
        background: {COLORS["surface_3"]};
    }}

    QPushButton#DeviceCandidateRegistered {{
        background: #101820;
        border: 1px solid {COLORS["line"]};
        border-radius: 0px;
        color: {COLORS["muted"]};
        font-family: "Consolas", "Malgun Gothic", monospace;
        font-size: 9px;
        font-weight: 800;
        padding: 3px 5px;
        text-align: left;
    }}

    QPushButton#DeviceCandidateRegistered:hover {{
        background: {COLORS["surface_3"]};
        color: {COLORS["text"]};
    }}

    QPushButton#DeviceCandidateSelected {{
        background: {COLORS["accent_2"]};
        border: 1px solid {COLORS["accent_2"]};
        border-radius: 0px;
        color: #071018;
        font-family: "Consolas", "Malgun Gothic", monospace;
        font-size: 9px;
        font-weight: 800;
        padding: 3px 5px;
        text-align: left;
    }}

    QLabel#DeviceNotice {{
        color: {COLORS["accent_2"]};
        font-size: 8px;
        font-weight: 900;
    }}

    QLabel#DeviceSectionLabel {{
        color: {COLORS["muted"]};
        font-size: 8px;
        font-weight: 900;
        padding: 5px 6px 3px 6px;
    }}

    QLabel#DeviceEmpty {{
        color: {COLORS["faint"]};
        font-size: 8px;
        font-weight: 800;
        padding: 7px 6px;
    }}

    QLabel#DeviceSavedBox {{
        background: #0a1118;
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-family: "Consolas", "Malgun Gothic", monospace;
        font-size: 9px;
        font-weight: 900;
        padding: 6px;
    }}

    QLabel#DeveloperNotice {{
        color: {COLORS["accent_2"]};
        font-size: 8px;
        font-weight: 900;
        padding-top: 2px;
    }}

    QLabel#TriggerGroup {{
        color: {COLORS["muted"]};
        font-size: 9px;
        font-weight: 900;
        padding-top: 4px;
    }}

    QLabel#DetailGroup {{
        color: {COLORS["muted"]};
        background: transparent;
        border-top: 1px solid {COLORS["line"]};
        font-size: 9px;
        font-weight: 900;
        padding: 6px 0px 2px 2px;
    }}

    QLabel#AppName {{
        font-size: 11px;
        font-weight: 700;
        color: {COLORS["text"]};
    }}

    QLabel#SectionTitle {{
        font-size: 15px;
        font-weight: 800;
        color: {COLORS["accent"]};
    }}

    QLabel#PanelTitle {{
        font-size: 12px;
        font-weight: 800;
        color: {COLORS["accent"]};
    }}

    QLabel#SmallTitle {{
        font-size: 9px;
        font-weight: 800;
        color: {COLORS["muted"]};
        letter-spacing: 0px;
    }}

    QLabel#ValueBadge {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["text"]};
        font-size: 8px;
        font-weight: 800;
        padding: 1px 3px;
        min-width: 18px;
        max-width: 20px;
    }}

    QLabel#DetailValueBadge {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["text"]};
        font-size: 8px;
        font-weight: 800;
        padding: 1px 3px;
        min-width: 30px;
        max-width: 44px;
    }}

    QLabel#StatusGood {{
        color: {COLORS["accent_2"]};
        font-weight: 800;
    }}

    QPushButton {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 4px;
        color: {COLORS["text"]};
        font-weight: 800;
        padding: 4px 6px;
    }}

    QPushButton:hover {{
        background: #213041;
        border-color: #3b4d61;
    }}

    QPushButton#NavButton {{
        text-align: left;
        background: transparent;
        border: 1px solid transparent;
        border-radius: 5px;
        color: {COLORS["muted"]};
        padding: 6px 4px;
        font-size: 9px;
    }}

    QPushButton#NavButton:hover {{
        background: {COLORS["surface_2"]};
        color: {COLORS["text"]};
    }}

    QPushButton#NavButton[active="true"] {{
        background: {COLORS["surface_3"]};
        border: 1px solid transparent;
        color: {COLORS["text"]};
    }}

    QPushButton#PrimaryButton {{
        background: {COLORS["accent"]};
        border-color: {COLORS["accent_outline"]};
        color: white;
    }}

    QPushButton#SoundHapticPowerOff {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 6px;
        color: {COLORS["text"]};
        font-size: 13px;
        font-weight: 900;
        padding: 10px 14px;
    }}

    QPushButton#SoundHapticPowerOff:hover {{
        background: #213040;
        border-color: {COLORS["accent_outline"]};
    }}

    QPushButton#SoundHapticPowerOn {{
        background: {COLORS["accent"]};
        border: 1px solid {COLORS["accent_outline"]};
        border-radius: 6px;
        color: white;
        font-size: 13px;
        font-weight: 900;
        padding: 10px 14px;
    }}

    QPushButton#SoundHapticPowerOn:hover {{
        background: {COLORS["accent_outline"]};
        border-color: {COLORS["accent_2"]};
    }}

    QPushButton#SecondaryButton {{
        background: {COLORS["surface_3"]};
        border-color: {COLORS["line"]};
        color: {COLORS["text"]};
    }}

    QPushButton#DangerButton {{
        background: #5a2c19;
        border-color: {COLORS["accent_2"]};
        color: {COLORS["accent_2"]};
    }}

    QPushButton#DangerButton:hover {{
        background: #6c351f;
        border-color: #ffe36a;
    }}

    QPushButton[unsaved="true"] {{
        background: {COLORS["accent_2"]};
        border-color: #ffe36a;
        color: #071018;
    }}

    QPushButton#SecondaryButton[unsaved="true"] {{
        background: {COLORS["accent_2"]};
        border-color: #ffe36a;
        color: #071018;
    }}

    QPushButton#WindowButton {{
        background: transparent;
        border: none;
        border-radius: 3px;
        color: {COLORS["muted"]};
        font-size: 14px;
        font-weight: 400;
        padding: 3px 8px;
        min-width: 28px;
    }}

    QPushButton#WindowButton:hover {{
        background: {COLORS["surface_3"]};
        color: {COLORS["text"]};
    }}

    QPushButton#WindowButtonClose {{
        background: transparent;
        border: none;
        border-radius: 3px;
        color: {COLORS["muted"]};
        font-size: 14px;
        font-weight: 400;
        padding: 3px 8px;
        min-width: 28px;
    }}

    QPushButton#WindowButtonClose:hover {{
        background: #b32645;
        color: white;
    }}

    QPushButton#ToggleOn {{
        background: {COLORS["accent"]};
        border-color: {COLORS["accent_outline"]};
        color: white;
        font-size: 8px;
        min-width: 24px;
        padding: 2px 3px;
    }}

    QPushButton#ToggleOff {{
        background: #1b2631;
        color: {COLORS["muted"]};
        font-size: 8px;
        min-width: 24px;
        padding: 2px 3px;
    }}

    QPushButton#ChoiceOn {{
        background: {COLORS["accent"]};
        border-color: {COLORS["accent_outline"]};
        color: white;
        font-size: 8px;
        padding: 2px 6px;
    }}

    QPushButton#ChoiceOff {{
        background: #1b2631;
        border-color: {COLORS["line"]};
        color: {COLORS["muted"]};
        font-size: 8px;
        padding: 2px 6px;
    }}

    QPushButton#HudStepButton {{
        background: {COLORS["surface_3"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 3px;
        color: {COLORS["text"]};
        font-size: 10px;
        font-weight: 900;
        padding: 1px 5px;
    }}

    QPushButton#TelemetryName {{
        background: #080e13;
        border: 1px solid transparent;
        border-radius: 3px;
        color: {COLORS["accent"]};
        font-size: 10px;
        font-weight: 900;
        padding: 3px 7px;
        text-align: left;
    }}

    QPushButton#TelemetryName:hover {{
        background: {COLORS["surface_3"]};
        border-color: {COLORS["line"]};
    }}

    QMenu {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        color: {COLORS["accent_2"]};
        font-size: 9px;
        padding: 4px;
    }}

    QMenu::item {{
        color: {COLORS["accent_2"]};
        padding: 5px 22px 5px 8px;
        border-radius: 3px;
    }}

    QMenu::item:selected {{
        background: {COLORS["surface_3"]};
        color: {COLORS["accent_2"]};
    }}

    QMenu::item:disabled {{
        background: transparent;
        color: {COLORS["muted"]};
    }}

    QDialog#TelemetryMenu {{
        background: {COLORS["surface_2"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 5px;
    }}

    QPushButton#TelemetryMenuItem {{
        background: transparent;
        border: 1px solid transparent;
        border-radius: 3px;
        color: {COLORS["accent_2"]};
        font-size: 9px;
        font-weight: 800;
        padding: 4px 8px;
        text-align: left;
    }}

    QPushButton#TelemetryMenuItem:hover {{
        background: {COLORS["surface_3"]};
        border-color: {COLORS["line"]};
    }}

    QPushButton#TelemetryMenuItem[active="true"] {{
        background: {COLORS["surface_3"]};
        border-color: {COLORS["accent_2"]};
        color: {COLORS["accent_2"]};
    }}

    QToolTip {{
        background: #101820;
        color: {COLORS["text"]};
        border: 1px solid {COLORS["line"]};
        border-radius: 5px;
        padding: 7px 9px;
        font-size: 9px;
    }}

    QSlider::groove:horizontal {{
        background: #2b3642;
        height: 3px;
        border-radius: 2px;
    }}

    QSlider::sub-page:horizontal {{
        background: {COLORS["accent_2"]};
        border-radius: 2px;
    }}

    QSlider::handle:horizontal {{
        background: {COLORS["accent_2"]};
        border: 1px solid #ffe56a;
        width: 10px;
        height: 10px;
        margin: -4px 0;
        border-radius: 5px;
    }}

    QScrollArea {{
        border: none;
        background: transparent;
    }}

    QScrollBar:vertical {{
        background: transparent;
        width: 5px;
    }}

    QScrollBar::handle:vertical {{
        background: {COLORS["accent"]};
        border-radius: 2px;
        min-height: 8px;
    }}

    QScrollBar::handle:vertical:hover {{
        background: #f04a96;
    }}

    QScrollBar::add-line:vertical,
    QScrollBar::sub-line:vertical {{
        height: 0px;
    }}
    """
