from __future__ import annotations

import argparse
import os
import sys
from copy import deepcopy
from pathlib import Path


os.environ["QT_QPA_PLATFORM"] = "windows"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

APP = QApplication.instance() or QApplication(["verify_rpm_hud"])
APP.setQuitOnLastWindowClosed(False)

from PySide6.QtGui import QColor, QImage, QPainter  # noqa: E402

from dht_app.app_state import AppState  # noqa: E402
from dht_app.hud_overlay import RpmHudOverlay  # noqa: E402
from dht_app.pages_hud import build_hud_dashboard_page  # noqa: E402
from dht_app.settings_io import apply_app_state_snapshot, export_app_state  # noqa: E402


def _assert(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _sample_state(style: str = "Modern") -> AppState:
    state = AppState()
    state.hud.rpm_style = style
    state.telemetry.last_is_race_on = True
    state.telemetry.last_rpm = 5600.0
    state.telemetry.last_max_rpm = 8000.0
    state.telemetry.last_idle_rpm = 900.0
    state.telemetry.last_gear = 5
    state.telemetry.last_speed = 182.0
    state.telemetry.last_car_ordinal = 101
    state.telemetry.rpm_hud_display_rpm = 5600.0
    state.telemetry.rpm_hud_peak_guide_car_ordinal = 101
    state.telemetry.rpm_hud_peak_guide_rpm = 7200.0
    return state


def _render(state: AppState) -> QImage:
    overlay = RpmHudOverlay(state)
    base_width, base_height = overlay._base_size()
    image = QImage(
        base_width,
        base_height,
        QImage.Format_ARGB32,
    )
    image.fill(QColor(0, 0, 0, 0))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.Antialiasing)
    if state.hud.rpm_style == "Digital Bar":
        painter.scale(
            base_width / RpmHudOverlay.DIGITAL_DESIGN_WIDTH,
            base_height / RpmHudOverlay.DIGITAL_DESIGN_HEIGHT,
        )
        overlay._draw_rpm_digital_bar(
            painter,
            0.0,
            0.0,
            float(RpmHudOverlay.DIGITAL_DESIGN_WIDTH),
            float(RpmHudOverlay.DIGITAL_DESIGN_HEIGHT),
        )
    elif state.hud.rpm_style == "Modern":
        overlay._draw_rpm_modern(painter, 0.0, 0.0, float(overlay.WIDTH), float(overlay.HEIGHT))
    else:
        overlay._draw_rpm_gauge(painter, 0.0, 0.0, float(overlay.WIDTH), float(overlay.HEIGHT))
    painter.end()
    overlay.close()
    return image


def _count_pixels(image: QImage) -> dict[str, int]:
    counts = {"opaque": 0, "white": 0, "black": 0, "magenta": 0, "red": 0}
    for y in range(image.height()):
        for x in range(image.width()):
            color = image.pixelColor(x, y)
            red, green, blue, alpha = color.red(), color.green(), color.blue(), color.alpha()
            if alpha >= 160:
                counts["opaque"] += 1
            if alpha >= 200 and red >= 225 and green >= 225 and blue >= 225:
                counts["white"] += 1
            if alpha >= 200 and red <= 25 and green <= 25 and blue <= 25:
                counts["black"] += 1
            if alpha >= 200 and red >= 100 and green <= 55 and 45 <= blue <= 130:
                counts["magenta"] += 1
            if alpha >= 200 and red >= 180 and 30 <= green <= 100 and blue <= 100:
                counts["red"] += 1
    return counts


def _near_color(image: QImage, x: float, y: float, predicate, radius: int = 2) -> bool:
    center_x = int(round(x))
    center_y = int(round(y))
    for sample_y in range(max(0, center_y - radius), min(image.height(), center_y + radius + 1)):
        for sample_x in range(max(0, center_x - radius), min(image.width(), center_x + radius + 1)):
            if predicate(image.pixelColor(sample_x, sample_y)):
                return True
    return False


def _count_region(image: QImage, x0: int, y0: int, x1: int, y1: int, predicate) -> int:
    return sum(
        1
        for y in range(max(0, y0), min(image.height(), y1))
        for x in range(max(0, x0), min(image.width(), x1))
        if predicate(image.pixelColor(x, y))
    )


def _verify_modern_outline_and_actual_rpm() -> None:
    state = _sample_state("Modern")
    state.telemetry.stable_rpm_hud_value = lambda: 5600.0
    image = _render(state)
    _assert(
        RpmHudOverlay.MODERN_GAUGE_OUTLINE_WIDTH == 1.0,
        "Modern RPM outline no longer matches the Classic 1 px outline.",
    )
    center = RpmHudOverlay.WIDTH / 2.0
    outer_radius = RpmHudOverlay.WIDTH / 2.0 - 5.0
    outline_point = RpmHudOverlay._rpm_point(
        center,
        center,
        outer_radius,
        RpmHudOverlay.rpm_angle_degrees(0.5),
    )

    def is_outline(color: QColor) -> bool:
        return (
            color.alpha() >= 180
            and 22 <= color.red() <= 55
            and 25 <= color.green() <= 65
            and 30 <= color.blue() <= 75
        )

    _assert(
        _near_color(image, outline_point.x(), outline_point.y(), is_outline, radius=2),
        "Modern RPM band outline is missing or too thin.",
    )
    _assert(
        _count_region(image, 48, 48, 112, 113, is_outline) >= 60,
        "Modern gear number does not have a visible outline.",
    )
    _assert(
        _count_region(image, 88, 108, 152, 154, is_outline) >= 50,
        "Modern speed number does not have a visible outline.",
    )
    _assert(
        _count_region(image, 48, 34, 112, 50, is_outline) >= 4,
        "Actual RPM text above the gear does not have an outline.",
    )

    changed_state = _sample_state("Modern")
    changed_state.telemetry.last_rpm = 5601.0
    changed_state.telemetry.stable_rpm_hud_value = lambda: 5600.0
    changed = _render(changed_state)
    differences = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) != changed.pixel(x, y)
    ]
    _assert(differences, "Modern HUD does not render the actual RPM value.")
    _assert(
        all(46 <= x <= 114 and 32 <= y <= 52 for x, y in differences),
        "Actual RPM text is not confined to the area directly above the gear.",
    )
    expected_font_size = max(
        4,
        int(round(RpmHudOverlay.MODERN_GEAR_FONT_SIZE * RpmHudOverlay.MODERN_RPM_FONT_RATIO)),
    )
    _assert(expected_font_size == 8, "Actual RPM font is not approximately 20% of the gear font.")


def _verify_layer_order() -> None:
    state = _sample_state("Modern")
    state.telemetry.last_rpm = 7440.0
    state.telemetry.rpm_hud_display_rpm = 7440.0
    image = _render(state)
    center = RpmHudOverlay.WIDTH / 2.0
    outer_radius = RpmHudOverlay.WIDTH / 2.0 - 5.0
    inner_radius = outer_radius * 0.78
    middle_radius = (outer_radius + inner_radius) / 2.0
    guide_angle = RpmHudOverlay.rpm_angle_degrees(7200.0 / 8000.0)
    band_point = RpmHudOverlay._rpm_point(center, center, middle_radius, guide_angle)
    marker_point = RpmHudOverlay._rpm_point(center, center, outer_radius + 3.0, guide_angle)

    is_white = lambda color: color.alpha() >= 200 and min(color.red(), color.green(), color.blue()) >= 225
    is_red = lambda color: color.alpha() >= 200 and color.red() >= 180 and 30 <= color.green() <= 100 and color.blue() <= 100
    _assert(
        _near_color(image, band_point.x(), band_point.y(), is_white),
        "Current RPM did not cover the lower red marker/red-zone layers inside the band.",
    )
    _assert(
        _near_color(image, marker_point.x(), marker_point.y(), is_red),
        "Learned upshift marker is not visible beyond the current RPM band.",
    )


def _verify_digital_bar() -> tuple[QImage, dict[str, int]]:
    state = _sample_state("Digital Bar")
    image = _render(state)
    counts = _count_pixels(image)
    _assert(
        image.width() == RpmHudOverlay.DIGITAL_WIDTH
        and image.height() == RpmHudOverlay.DIGITAL_HEIGHT,
        "Digital Bar did not use its horizontal design size.",
    )
    _assert(
        (image.width(), image.height()) == (240, 46),
        "Digital Bar base size is not approximately 120% of the previous 200 x 38 size.",
    )
    _assert(counts["white"] >= 650, f"Digital Bar current RPM/text layer is missing: {counts}")
    _assert(counts["black"] >= 120, f"Digital Bar unfilled layer is missing: {counts}")
    _assert(counts["magenta"] >= 120, f"Digital Bar red-zone layer is missing: {counts}")
    _assert(counts["red"] >= 15, f"Digital Bar previous-shift marker is missing: {counts}")

    scale_x = image.width() / RpmHudOverlay.DIGITAL_DESIGN_WIDTH
    scale_y = image.height() / RpmHudOverlay.DIGITAL_DESIGN_HEIGHT
    track_y = (
        RpmHudOverlay.DIGITAL_TRACK_Y + RpmHudOverlay.DIGITAL_TRACK_HEIGHT / 2.0
    ) * scale_y
    step = RpmHudOverlay.DIGITAL_TRACK_WIDTH / RpmHudOverlay.DIGITAL_SEGMENT_COUNT

    def segment_x(index: int) -> float:
        return (RpmHudOverlay.DIGITAL_TRACK_X + (index + 0.5) * step) * scale_x

    def is_white(color: QColor) -> bool:
        return color.alpha() >= 200 and min(color.red(), color.green(), color.blue()) >= 225

    def is_black(color: QColor) -> bool:
        return color.alpha() >= 200 and max(color.red(), color.green(), color.blue()) <= 25

    def is_magenta(color: QColor) -> bool:
        return color.alpha() >= 200 and color.red() >= 100 and color.green() <= 55 and 45 <= color.blue() <= 130

    def is_outline(color: QColor) -> bool:
        return (
            color.alpha() >= 180
            and 22 <= color.red() <= 55
            and 25 <= color.green() <= 65
            and 30 <= color.blue() <= 75
        )

    _assert(
        abs(RpmHudOverlay.DIGITAL_OUTLINE_WIDTH * scale_x - 1.0) <= 0.05,
        "Digital Bar outline is not approximately 1 final-output pixel.",
    )
    outline_x = (
        RpmHudOverlay.DIGITAL_TRACK_X + RpmHudOverlay.DIGITAL_TRACK_WIDTH / 2.0
    ) * scale_x
    outline_y = RpmHudOverlay.DIGITAL_TRACK_Y * scale_y
    _assert(
        _near_color(image, outline_x, outline_y, is_outline, radius=1),
        "Digital Bar track outline is missing.",
    )
    _assert(
        _count_region(image, 0, 0, image.width(), image.height(), is_outline) >= 100,
        "Digital Bar text does not have a visible outline.",
    )

    for index in range(RpmHudOverlay.DIGITAL_SEGMENT_COUNT):
        expected = is_white if index < 28 else is_black if index < 34 else is_magenta
        _assert(
            _near_color(image, segment_x(index), track_y, expected, radius=1),
            f"Digital Bar segment {index} has the wrong layer color.",
        )

    marker_x = (
        RpmHudOverlay.DIGITAL_TRACK_X + RpmHudOverlay.DIGITAL_TRACK_WIDTH * 0.90
    ) * scale_x
    marker_y = (RpmHudOverlay.DIGITAL_TRACK_Y - 5.0) * scale_y
    _assert(
        _near_color(
            image,
            marker_x,
            marker_y,
            lambda color: color.alpha() >= 200
            and color.red() >= 180
            and 30 <= color.green() <= 100
            and color.blue() <= 100,
            radius=1,
        ),
        "Digital Bar previous-shift marker position is wrong.",
    )

    changed_state = _sample_state("Digital Bar")
    changed_state.telemetry.last_rpm = 5601.0
    changed_state.telemetry.stable_rpm_hud_value = lambda: 5600.0
    changed = _render(changed_state)
    rpm_differences = [
        (x, y)
        for y in range(image.height())
        for x in range(image.width())
        if image.pixel(x, y) != changed.pixel(x, y)
    ]
    _assert(rpm_differences, "Digital Bar does not render the actual RPM value.")
    _assert(
        all(58 <= x <= 118 and 0 <= y <= 13 for x, y in rpm_differences),
        "Digital Bar actual RPM is not centered above the track.",
    )

    high_state = _sample_state("Digital Bar")
    high_state.telemetry.last_rpm = 7600.0
    high_state.telemetry.rpm_hud_display_rpm = 7600.0
    high_image = _render(high_state)
    high_counts = _count_pixels(high_image)
    for index in range(38):
        _assert(
            _near_color(high_image, segment_x(index), track_y, is_white, radius=1),
            f"Current RPM did not cover Digital Bar segment {index}.",
        )
    _assert(high_counts["red"] == 0, "Current RPM did not fully hide the previous-shift marker.")

    mph_state = _sample_state("Digital Bar")
    mph_state.hud.speed_unit = "mph"
    _assert(image != _render(mph_state), "Digital Bar did not respond to the speed unit setting.")

    geometry_state = _sample_state("Digital Bar")
    overlay = RpmHudOverlay(geometry_state)
    _assert(
        (overlay.width(), overlay.height())
        == (RpmHudOverlay.DIGITAL_WIDTH, RpmHudOverlay.DIGITAL_HEIGHT),
        "Digital Bar window geometry was not applied.",
    )
    geometry_state.hud.rpm_style = "Modern"
    overlay._apply_geometry_from_state(force=True)
    _assert(
        (overlay.width(), overlay.height()) == (RpmHudOverlay.WIDTH, RpmHudOverlay.HEIGHT),
        "RPM window geometry did not return to the square styles.",
    )
    overlay.close()
    return image, counts


def _verify_settings_compatibility() -> None:
    state = AppState()
    _assert(state.hud.rpm_style == "Digital Bar", "The first-run RPM style is not Digital Bar.")

    direct_state = AppState()
    direct_state.set_rpm_style("Modern")
    _assert(
        direct_state.hud.rpm_style == "Modern" and direct_state.unsaved_changes,
        "Direct RPM style selection was not stored in app state.",
    )
    direct_state.set_rpm_style("Unknown")
    _assert(
        direct_state.hud.rpm_style == "Modern",
        "Direct RPM style selection accepted an invalid style.",
    )

    state.cycle_rpm_style()
    _assert(state.hud.rpm_style == "Classic", "RPM style cycle did not select Classic.")
    state.cycle_rpm_style()
    _assert(state.hud.rpm_style == "Modern", "RPM style cycle did not select Modern.")
    state.cycle_rpm_style()
    _assert(state.hud.rpm_style == "Digital Bar", "RPM style cycle did not select Digital Bar.")

    snapshot = export_app_state(state)
    _assert(snapshot["hud"]["rpm_style"] == "Digital Bar", "Digital Bar RPM style was not exported.")
    restored = AppState()
    apply_app_state_snapshot(restored, snapshot)
    _assert(restored.hud.rpm_style == "Digital Bar", "Digital Bar RPM style was not restored.")
    state.cycle_rpm_style()
    _assert(state.hud.rpm_style == "Classic", "RPM style cycle did not return to Classic.")

    legacy_snapshot = deepcopy(snapshot)
    legacy_snapshot["hud"].pop("rpm_style", None)
    legacy_restored = AppState()
    apply_app_state_snapshot(legacy_restored, legacy_snapshot)
    _assert(legacy_restored.hud.rpm_style == "Classic", "Legacy settings did not keep Classic RPM style.")

    invalid_snapshot = deepcopy(snapshot)
    invalid_snapshot["hud"]["rpm_style"] = "Unknown"
    invalid_restored = AppState()
    apply_app_state_snapshot(invalid_restored, invalid_snapshot)
    _assert(invalid_restored.hud.rpm_style == "Classic", "Invalid RPM style was accepted.")


def _verify_style_control() -> None:
    state = AppState()
    state.hud.rpm_style = "Digital Bar"
    callbacks: list[str] = []
    page = build_hud_dashboard_page(
        {"rpm_style_select": lambda style: callbacks.append(str(style))},
        state,
    )
    style_buttons = {
        button.text(): button
        for button in page.findChildren(QPushButton)
        if button.text() in ("Classic", "Modern", "Digital Bar")
    }
    _assert(
        set(style_buttons) == {"Classic", "Modern", "Digital Bar"},
        "RPM style does not expose three direct-selection buttons.",
    )
    _assert(
        style_buttons["Digital Bar"].property("active") == "true"
        and style_buttons["Classic"].property("active") == "false"
        and style_buttons["Modern"].property("active") == "false",
        "RPM style selected-button highlight is incorrect.",
    )
    _assert(
        all("40-segment" in button.toolTip() for button in style_buttons.values()),
        "RPM style control tooltip is incomplete.",
    )
    style_buttons["Modern"].click()
    _assert(callbacks == ["Modern"], "RPM direct-selection callback was not connected.")
    page.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify and optionally render RPM HUD styles.")
    parser.add_argument("--output", type=Path, help="Optional PNG preview path.")
    parser.add_argument(
        "--style",
        choices=("Modern", "Digital Bar"),
        default="Modern",
        help="Style to save when --output is used.",
    )
    args = parser.parse_args()

    _verify_settings_compatibility()
    _verify_style_control()

    modern = _render(_sample_state("Modern"))
    classic = _render(_sample_state("Classic"))
    mph_state = _sample_state("Modern")
    mph_state.hud.speed_unit = "mph"
    mph = _render(mph_state)
    counts = _count_pixels(modern)
    _assert(counts["opaque"] >= 2500, f"Modern RPM HUD is unexpectedly sparse: {counts}")
    _assert(counts["white"] >= 1000, f"Current RPM/white text layer is missing: {counts}")
    _assert(counts["black"] >= 400, f"Unfilled black RPM layer is missing: {counts}")
    _assert(counts["magenta"] >= 100, f"Magenta red-zone layer is missing: {counts}")
    _assert(counts["red"] >= 20, f"Previous-shift red marker is missing: {counts}")
    _assert(modern != classic, "Modern RPM HUD render is identical to Classic.")
    _assert(modern != mph, "Modern RPM HUD did not respond to the speed unit setting.")
    _assert(abs(mph_state.telemetry.convert_hud_speed(182.0, "mph") - 113.089522) < 0.001, "mph conversion changed.")
    _verify_layer_order()
    _verify_modern_outline_and_actual_rpm()
    digital, digital_counts = _verify_digital_bar()

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        output_image = digital if args.style == "Digital Bar" else modern
        _assert(output_image.save(str(args.output), "PNG"), f"Could not save preview: {args.output}")
        print(f"Preview: {args.output}")

    APP.quit()
    print(
        "RPM HUD render and settings verification: PASS "
        f"Modern={counts} DigitalBar={digital_counts}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
