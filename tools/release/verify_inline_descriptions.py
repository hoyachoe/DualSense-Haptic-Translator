from __future__ import annotations

import os
import sys
from pathlib import Path


os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QWidget  # noqa: E402

from dht_app.app_state import AppState  # noqa: E402
from dht_app.detail_schema import (  # noqa: E402
    HAPTIC_DETAIL_GROUPS,
    TRIGGER_DETAIL_GROUPS,
    TRIGGER_OPTION_GROUPS,
    grouped_numeric_details,
    grouped_option_details,
)
from dht_app.pages_haptic import build_advanced_panel, build_haptic_panel  # noqa: E402
from dht_app.pages_trigger import build_trigger_advanced_panel, build_trigger_panel  # noqa: E402
from dht_app.preset_loader import load_builtin_presets_into_state  # noqa: E402
from dht_app.tooltip_texts import DETAIL_TOOLTIPS, LOCALIZED_TOOLTIPS, detail_tooltip  # noqa: E402
from dht_app.ui_widgets import AdvancedRow, BoolRow, ChoiceRow, SliderRow, TriggerToggleRow  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _assert_inline_row(row: QWidget, context: str) -> None:
    descriptions = [
        label
        for label in row.findChildren(QLabel)
        if label.objectName() == "InlineDescription"
    ]
    _assert(len(descriptions) == 1, f"{context}: expected one inline description, found {len(descriptions)}.")
    _assert(bool(descriptions[0].text().strip()), f"{context}: inline description is empty.")
    _assert(not getattr(row, "_stable_tooltip_filter", None), f"{context}: stable tooltip filter is still installed.")
    for widget in (row, *row.findChildren(QWidget)):
        _assert(not widget.toolTip(), f"{context}: tooltip remains on {type(widget).__name__}.")


def _active_detail_keys() -> set[str]:
    keys = {
        key
        for groups in (*HAPTIC_DETAIL_GROUPS.values(), *TRIGGER_DETAIL_GROUPS.values())
        for _section, section_keys in groups
        for key in section_keys
    }
    keys.update(
        spec[1]
        for groups in TRIGGER_OPTION_GROUPS.values()
        for _section, rows in groups
        for spec in rows
    )
    return keys


def _verify_detail_translation_coverage() -> None:
    active_keys = _active_detail_keys()
    missing_english = active_keys - DETAIL_TOOLTIPS.keys()
    _assert(not missing_english, f"English detail descriptions are missing: {sorted(missing_english)}")

    generic_markers = {
        "KR": "선택한 이펙트의 감각, 타이밍, 출력 조건을 조정합니다.",
        "CN": "调整所选效果的感觉、时机和输出条件。",
        "ES": "Ajusta la sensacion, el tiempo y la condicion de salida del efecto seleccionado.",
    }
    for language, marker in generic_markers.items():
        direct = LOCALIZED_TOOLTIPS[language]["detail"]
        missing = active_keys - direct.keys()
        _assert(not missing, f"{language} detail descriptions are missing: {sorted(missing)}")
        for key in active_keys:
            text = detail_tooltip(key, language)
            _assert(text == direct[key], f"{language} {key}: direct detail description was not used.")
            _assert(bool(text.strip()), f"{language} {key}: detail description is empty.")
            _assert(marker not in text, f"{language} {key}: generic detail fallback is still visible.")

    expected_bump = (
        "각 연석 요철의 선명도입니다.\n"
        "낮은 값은 질감을 부드럽게 합니다. 높은 값은 개별 홈을 더 뚜렷하게 합니다."
    )
    _assert(detail_tooltip("bump_sharpness", "KR") == expected_bump, "Bump Sharpness lost its legacy Korean detail.")
    _assert("upshift" in detail_tooltip("balance", "EN").lower(), "Up/Down Balance still describes L/R placement.")
    _assert(
        detail_tooltip("howl_start_hz", "KR") != detail_tooltip("start_hz", "KR"),
        "Shift Down Howl Start Hz reused the acceleration-punch description.",
    )
    _assert(
        detail_tooltip("shift_pulse_lock_ms", "KR") != detail_tooltip("shift_pulse_boost_ms", "KR"),
        "Haptic and trigger Shift Pulse Lock descriptions are not distinguished.",
    )
    _assert(
        not detail_tooltip("future_strength", "KR").startswith("Future Strength\n"),
        "Unknown detail fallback repeats the setting title in the inline body.",
    )


def _verify_effect_lists(state: AppState) -> None:
    haptic_panel = build_haptic_panel(None, state)
    haptic_rows = haptic_panel.findChildren(SliderRow)
    _assert(len(haptic_rows) == len(state.haptic_effects), "Haptic list row count does not match the effect model.")
    _assert({row.effect_name for row in haptic_rows} == set(state.haptic_effects), "Haptic list effects do not match the model.")
    for row in haptic_rows:
        _assert_inline_row(row, f"Haptic effect {row.effect_name}")

    trigger_panel = build_trigger_panel(None, state)
    trigger_rows = trigger_panel.findChildren(TriggerToggleRow)
    _assert(len(trigger_rows) == len(state.trigger_effects), "Trigger list row count does not match the effect model.")
    for row in trigger_rows:
        descriptions = [
            label
            for label in row.findChildren(QLabel)
            if label.objectName() == "TriggerDescription"
        ]
        _assert(len(descriptions) == 1 and descriptions[0].text().strip(), f"Trigger effect {row.effect_name}: description is missing.")
        for widget in (row, *row.findChildren(QWidget)):
            _assert(not widget.toolTip(), f"Trigger effect {row.effect_name}: effect-list tooltip remains.")


def _verify_haptic_advanced(state: AppState) -> None:
    for effect_name, setting in state.haptic_effects.items():
        state.selected_haptic_effect = effect_name
        panel = build_advanced_panel(None, state)
        expected = sum(
            len(group.rows)
            for group in grouped_numeric_details(effect_name, setting.details, HAPTIC_DETAIL_GROUPS)
        )
        rows = panel.findChildren(AdvancedRow)
        _assert(len(rows) == expected, f"Haptic {effect_name}: expected {expected} detail rows, found {len(rows)}.")
        effect_descriptions = [
            label
            for label in panel.findChildren(QLabel)
            if label.objectName() == "HapticDescription"
        ]
        _assert(
            len(effect_descriptions) == 1 and effect_descriptions[0].text().strip(),
            f"Haptic {effect_name}: selected-effect description is missing.",
        )
        for index, row in enumerate(rows):
            _assert_inline_row(row, f"Haptic {effect_name} detail {index + 1}")


def _verify_trigger_advanced(state: AppState) -> None:
    detail_types = (AdvancedRow, BoolRow, ChoiceRow)
    for effect_name, setting in state.trigger_effects.items():
        state.selected_trigger_effect = effect_name
        panel = build_trigger_advanced_panel(None, state)
        expected_numeric = sum(
            len(group.rows)
            for group in grouped_numeric_details(effect_name, setting.details, TRIGGER_DETAIL_GROUPS)
        )
        expected_options = sum(
            len(group.rows)
            for group in grouped_option_details(effect_name, setting.details)
        )
        rows = [row for row_type in detail_types for row in panel.findChildren(row_type)]
        expected = expected_numeric + expected_options
        _assert(len(rows) == expected, f"Trigger {effect_name}: expected {expected} detail rows, found {len(rows)}.")
        for index, row in enumerate(rows):
            _assert_inline_row(row, f"Trigger {effect_name} detail {index + 1}")


def _verify_kerb_speed_descriptions(state: AppState) -> None:
    low_speed_keys = ("low_speed_hz", "kerb_l_low_hz", "kerb_r_low_hz", "kerb_low_hz")
    high_speed_keys = ("high_speed_hz", "kerb_l_high_hz", "kerb_r_high_hz", "kerb_high_hz")
    expected = {
        "EN": (
            "Sets the kerb vibration rate when the vehicle is moving at low speed.\nAt low vehicle speed, the kerb vibration should not pulse too quickly.",
            "Kerb vibration pulses faster when the vehicle crosses a kerb at high speed.\nThis Hz value sets the vibration rate at the vehicle's maximum speed.",
        ),
        "KR": (
            "차량이 낮은 속도일 때 진동의 빠르기입니다.\n차량 속도가 낮을 때는 연석 진동이 빠르지 않도록 설정합니다.",
            "차량이 높은 속도로 연석을 통과할 때 더 빠르게 진동합니다.\n설정한 Hz 값은 최고 속도에서의 진동 빠르기입니다.",
        ),
        "CN": (
            "设置车辆低速行驶时的路肩振动速率。\n车辆速度较低时，路肩振动不应设置得过快。",
            "车辆高速通过路肩时，振动会更快。\n该 Hz 值设置车辆达到最高速度时的振动速率。",
        ),
        "ES": (
            "Define la velocidad de vibración del piano cuando el vehículo circula a baja velocidad.\nA baja velocidad, la vibración del piano no debe ser demasiado rápida.",
            "Cuando el vehículo pasa por el piano a alta velocidad, la vibración es más rápida.\nEl valor en Hz define la velocidad de vibración a la velocidad máxima del vehículo.",
        ),
    }
    fallback_numeric = grouped_numeric_details("Kerb Wave", {}, TRIGGER_DETAIL_GROUPS)
    fallback_options = grouped_option_details("Kerb Wave", {})
    _assert(sum(len(group.rows) for group in fallback_numeric) == 5, "Kerb Wave missing-detail fallback did not expose five shared settings.")
    _assert(sum(len(group.rows) for group in fallback_options) == 2, "Kerb Wave missing-detail fallback did not expose both side switches.")
    state.selected_trigger_effect = "Kerb Wave"
    structure_panel = build_trigger_advanced_panel(None, state)
    bool_rows = structure_panel.findChildren(BoolRow)
    numeric_rows = structure_panel.findChildren(AdvancedRow)
    _assert(len(bool_rows) == 2, "Kerb Wave must expose exactly L2 and R2 output toggles.")
    _assert(len(numeric_rows) == 5, "Kerb Wave must expose exactly five shared numeric settings.")
    structure_panel.resize(560, 700)
    structure_panel.show()
    app = QApplication.instance()
    if app is not None:
        app.processEvents()
    toggle_bottom = max(row.mapTo(structure_panel, row.rect().bottomLeft()).y() for row in bool_rows)
    numeric_top = min(row.mapTo(structure_panel, row.rect().topLeft()).y() for row in numeric_rows)
    _assert(toggle_bottom < numeric_top, "Kerb Wave L2/R2 switches are not above the shared numeric settings.")
    structure_panel.hide()
    structure_texts = [label.text() for label in structure_panel.findChildren(QLabel)]
    for title in (
        "L2 ON",
        "R2 ON",
        "Trigger Start Position",
        "Low Speed Hz",
        "High Speed Hz",
        "Low Speed Amp",
        "High Speed Amp",
    ):
        _assert(structure_texts.count(title) == 1, f"Kerb Wave shared control is missing or duplicated: {title}.")
    for removed_title in (
        "L2 Trigger Start Position",
        "R2 Trigger Start Position",
        "L2 Low Speed Hz",
        "R2 Low Speed Hz",
        "L2 High Speed Hz",
        "R2 High Speed Hz",
        "L2 Low Speed Amp",
        "R2 Low Speed Amp",
        "L2 High Speed Amp",
        "R2 High Speed Amp",
    ):
        _assert(removed_title not in structure_texts, f"Kerb Wave still exposes a split L/R tuning row: {removed_title}.")

    interactive_panel = build_trigger_advanced_panel(
        {"trigger_detail_value": state.set_trigger_detail_value},
        state,
    )
    interactive_rows = interactive_panel.findChildren(BoolRow)
    l2_row = next(
        row
        for row in interactive_rows
        if any(label.text() == "L2 ON" for label in row.findChildren(QLabel))
    )
    l2_toggle = l2_row.findChild(QPushButton)
    _assert(l2_toggle is not None, "Kerb Wave L2 toggle button is missing.")
    original_l2 = bool(state.trigger_effects["Kerb Wave"].details.get("kerb_l_enabled", True))
    original_r2 = bool(state.trigger_effects["Kerb Wave"].details.get("kerb_r_enabled", True))
    QTest.mouseClick(l2_toggle, Qt.LeftButton)
    _assert(
        state.trigger_effects["Kerb Wave"].details.get("kerb_l_enabled") is (not original_l2),
        "Kerb Wave L2 switch did not change on the first click.",
    )
    _assert(
        state.trigger_effects["Kerb Wave"].details.get("kerb_r_enabled") is original_r2,
        "Kerb Wave L2 switch unexpectedly changed the R2 switch.",
    )
    QTest.mouseClick(l2_toggle, Qt.LeftButton)
    _assert(
        state.trigger_effects["Kerb Wave"].details.get("kerb_l_enabled") is original_l2,
        "Kerb Wave L2 switch did not restore its original state.",
    )

    for language, (low_text, high_text) in expected.items():
        for key in low_speed_keys:
            _assert(detail_tooltip(key, language) == low_text, f"{language} {key}: low-speed Kerb Wave text differs.")
        for key in high_speed_keys:
            _assert(detail_tooltip(key, language) == high_text, f"{language} {key}: high-speed Kerb Wave text differs.")
        state.options.tooltip_language = language
        state.selected_trigger_effect = "Kerb Wave"
        panel = build_trigger_advanced_panel(None, state)
        rendered_texts = [
            label.text()
            for label in panel.findChildren(QLabel)
            if label.objectName() == "InlineDescription"
        ]
        _assert(rendered_texts.count(low_text) == 1, f"{language}: shared Kerb Wave Low Speed Hz text is missing.")
        _assert(rendered_texts.count(high_text) == 1, f"{language}: shared Kerb Wave High Speed Hz text is missing.")
        state.selected_haptic_effect = "Rumble Kerbs"
        haptic_panel = build_advanced_panel(None, state)
        haptic_texts = [
            label.text()
            for label in haptic_panel.findChildren(QLabel)
            if label.objectName() == "InlineDescription"
        ]
        _assert(haptic_texts.count(low_text) == 1, f"{language}: Rumble Kerbs Low Speed Hz does not use the localized text.")
        _assert(haptic_texts.count(high_text) == 1, f"{language}: Rumble Kerbs High Speed Hz does not use the localized text.")


def main() -> int:
    app = QApplication.instance() or QApplication([])
    state = AppState()
    report = load_builtin_presets_into_state(state)
    _assert(report.loaded_files > 0, "Built-in presets were not available for detail-row verification.")
    _verify_detail_translation_coverage()
    _verify_effect_lists(state)
    _verify_haptic_advanced(state)
    _verify_trigger_advanced(state)
    _verify_kerb_speed_descriptions(state)
    app.processEvents()
    print("PASS: inline descriptions replace effect/detail tooltips across Haptic and Trigger panels.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
