from __future__ import annotations

from collections import deque
import colorsys
import math
from time import monotonic

from PySide6.QtCore import QPoint, QPointF, QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPainterPath, QPen, QPolygonF
from PySide6.QtWidgets import QWidget

from .app_state import AppState, HAPTIC_DEBUG_EFFECT_NAMES, PacketStatus, TRIGGER_DEBUG_EFFECT_NAMES
from .ui_theme import COLORS


class HudOverlayBase(QWidget):
    HUD_NAME = ""
    STANDBY_HIDE_EXEMPT = False
    WIDTH = 280
    HEIGHT = 240
    DEFAULT_X = 120
    DEFAULT_Y = 120

    def __init__(self, state: AppState, title: str):
        super().__init__(None)
        self.state = state
        self._drag_origin: QPoint | None = None
        self._geometry_signature: tuple[int, int, int, int, int] | None = None
        self.setWindowTitle(title)
        self.setWindowFlags(
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._apply_geometry_from_state(force=True)
        self.hide()

    def sync_to_state(self) -> None:
        item = self.state.hud.items.get(self.HUD_NAME)
        should_show = bool(item and item.enabled) and (
            self.STANDBY_HIDE_EXEMPT
            or not self.state.hud.standby_hide
            or self._has_active_driving_telemetry()
        )
        if should_show and not self.isVisible():
            self._apply_geometry_from_state(force=True)
            self.show()
        elif not should_show and self.isVisible():
            self.hide()
        if should_show:
            self._apply_geometry_from_state()
            self.update()

    def _has_active_driving_telemetry(self) -> bool:
        telemetry = self.state.telemetry
        try:
            max_rpm = float(telemetry.last_max_rpm or 0.0)
        except (TypeError, ValueError):
            max_rpm = 0.0
        return (
            self.state.packet_status == PacketStatus.RECEIVING
            and telemetry.last_parsed
            and bool(telemetry.last_is_race_on)
            and max_rpm > 0.0
        )

    def _base_size(self) -> tuple[int, int]:
        return self.WIDTH, self.HEIGHT

    def _apply_geometry_from_state(self, force: bool = False) -> None:
        item = self.state.hud.items.get(self.HUD_NAME)
        scale = max(50, min(200, int(item.scale if item is not None else 100))) / 100.0
        opacity_percent = max(10, min(100, int(item.opacity if item is not None else 100)))
        opacity = opacity_percent / 100.0
        base_width, base_height = self._base_size()
        width = round(base_width * scale)
        height = round(base_height * scale)
        if item is not None and item.x is not None and item.y is not None:
            x = item.x
            y = item.y
        else:
            x = self.DEFAULT_X
            y = self.DEFAULT_Y
        if self._drag_origin is not None:
            x = self.x()
            y = self.y()
        signature = (width, height, x, y, opacity_percent)
        if not force and signature == self._geometry_signature:
            return
        if force or abs(self.windowOpacity() - opacity) > 0.001:
            self.setWindowOpacity(opacity)
        if force or self.width() != width or self.height() != height:
            self.setFixedSize(width, height)
        if self._drag_origin is None and (force or self.x() != x or self.y() != y):
            self.move(x, y)
        self._geometry_signature = signature

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._drag_origin is not None and event.buttons() & Qt.LeftButton:
            self.move(self._snapped_position(event.globalPosition().toPoint() - self._drag_origin))
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_origin = None
        snapped = self._snapped_position(QPoint(self.x(), self.y()))
        if snapped != QPoint(self.x(), self.y()):
            self.move(snapped)
        self.state.set_hud_position(self.HUD_NAME, self.x(), self.y())
        self._geometry_signature = None
        super().mouseReleaseEvent(event)

    def _snapped_position(self, position: QPoint) -> QPoint:
        hud = self.state.hud
        if not hud.snap_enabled:
            return position
        snap = max(1, int(hud.snap_pixel))
        if snap <= 1:
            return position
        return QPoint(
            round(position.x() / snap) * snap,
            round(position.y() / snap) * snap,
        )


class PresetHudOverlay(HudOverlayBase):
    HUD_NAME = "Preset"
    WIDTH = 220
    HEIGHT = 62
    DEFAULT_X = 80
    DEFAULT_Y = 308

    def __init__(self, state: AppState):
        super().__init__(state, "Preset HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        rect = QRect(1, 1, self.WIDTH - 2, self.HEIGHT - 2)
        painter.setPen(QColor(COLORS["line"]))
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawRoundedRect(rect, 7, 7)

        receiving = self.state.packet_status == PacketStatus.RECEIVING
        status = "RECEIVING" if receiving else "WAITING"
        status_color = COLORS["accent_2"] if receiving else COLORS["muted"]

        painter.setPen(QColor(status_color))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(13, 20, status)

        painter.setPen(QColor(COLORS["accent_2"]))
        painter.setFont(QFont("Segoe UI", 13, QFont.Bold))
        painter.drawText(13, 45, self.state.selected_preset)

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        game_text = self.state.selected_game_label.upper()
        painter.drawText(138, 45, game_text[:10])


class RpmHudOverlay(HudOverlayBase):
    HUD_NAME = "RPM"
    WIDTH = 160
    HEIGHT = 160
    DIGITAL_WIDTH = 240
    DIGITAL_HEIGHT = 46
    DIGITAL_DESIGN_WIDTH = 500
    DIGITAL_DESIGN_HEIGHT = 96
    DIGITAL_SEGMENT_COUNT = 40
    DIGITAL_TRACK_X = 58.0
    DIGITAL_TRACK_Y = 32.0
    DIGITAL_TRACK_WIDTH = 328.0
    DIGITAL_TRACK_HEIGHT = 32.0
    DIGITAL_SEGMENT_GAP = 1.0
    DIGITAL_OUTLINE_WIDTH = 2.1
    DIGITAL_MARKER_OUTLINE_WIDTH = 6.0
    DIGITAL_TEXT_OUTLINE_THICKNESS = 2
    DIGITAL_RPM_FONT_SIZE = 16
    MODERN_OUTLINE_COLOR = "#252c35"
    MODERN_GAUGE_OUTLINE_WIDTH = 1.0
    MODERN_MARKER_OUTLINE_WIDTH = 6.0
    MODERN_GEAR_FONT_SIZE = 38
    MODERN_RPM_FONT_RATIO = 0.20
    DEFAULT_X = 616
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "RPM HUD")
        self._needle_angles: list[float] = []

    def _base_size(self) -> tuple[int, int]:
        if self.state.hud.rpm_style == "Digital Bar":
            return self.DIGITAL_WIDTH, self.DIGITAL_HEIGHT
        return self.WIDTH, self.HEIGHT

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        base_width, base_height = self._base_size()
        if self.state.hud.rpm_style == "Digital Bar":
            design_width = self.DIGITAL_DESIGN_WIDTH
            design_height = self.DIGITAL_DESIGN_HEIGHT
        else:
            design_width = base_width
            design_height = base_height
        painter.scale(self.width() / design_width, self.height() / design_height)
        if self.state.hud.rpm_style == "Digital Bar":
            self._draw_rpm_digital_bar(
                painter,
                0.0,
                0.0,
                float(design_width),
                float(design_height),
            )
            return
        size = min(float(design_width), float(design_height))
        x0 = (float(design_width) - size) / 2.0
        y0 = (float(design_height) - size) / 2.0
        if self.state.hud.rpm_style == "Modern":
            self._draw_rpm_modern(painter, x0, y0, x0 + size, y0 + size)
        else:
            self._draw_rpm_gauge(painter, x0, y0, x0 + size, y0 + size)

    def _draw_rpm_digital_bar(
        self,
        painter: QPainter,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
    ) -> None:
        telemetry = self.state.telemetry
        raw_max_rpm = max(0.0, float(telemetry.last_max_rpm or 0.0))
        max_rpm = max(1.0, raw_max_rpm)
        rpm = telemetry.stable_rpm_hud_value()
        display_max_rpm = telemetry.rpm_display_max_rpm(max_rpm)
        ratio = max(0.0, min(1.0, rpm / display_max_rpm))
        red_start_ratio = (
            max(0.0, min(1.0, (max_rpm * 0.85) / display_max_rpm))
            if raw_max_rpm > 1000.0
            else 0.85
        )
        peak_guide_rpm = telemetry.current_rpm_hud_peak_guide()
        peak_guide_ratio = max(0.0, min(1.0, peak_guide_rpm / display_max_rpm))

        track_x = x0 + self.DIGITAL_TRACK_X
        track_y = y0 + self.DIGITAL_TRACK_Y
        track_width = self.DIGITAL_TRACK_WIDTH
        track_height = self.DIGITAL_TRACK_HEIGHT
        segment_count = self.DIGITAL_SEGMENT_COUNT
        red_start_index = max(0, min(segment_count, int(math.floor(red_start_ratio * segment_count))))
        current_count = (
            0
            if ratio <= 0.0
            else max(1, min(segment_count, int(math.ceil(ratio * segment_count - 1e-9))))
        )

        # RPM layers, bottom to top: unfilled, red zone, learned shift marker, current RPM.
        self._draw_digital_segments(
            painter, track_x, track_y, track_width, track_height, 0, segment_count, "#050608"
        )
        self._draw_digital_segments(
            painter,
            track_x,
            track_y,
            track_width,
            track_height,
            red_start_index,
            segment_count,
            "#960D52",
        )
        if 0.0 < peak_guide_ratio and ratio < peak_guide_ratio:
            marker_x = track_x + track_width * peak_guide_ratio

            marker_clip = QPainterPath()
            marker_clip.setFillRule(Qt.OddEvenFill)
            marker_clip.addRect(QRectF(x0, y0, x1 - x0, y1 - y0))
            marker_clip.addRect(QRectF(track_x, track_y, track_width, track_height))
            painter.save()
            painter.setClipPath(marker_clip)
            marker_outline_pen = QPen(
                QColor(self.MODERN_OUTLINE_COLOR),
                self.DIGITAL_MARKER_OUTLINE_WIDTH,
            )
            marker_outline_pen.setCapStyle(Qt.SquareCap)
            painter.setPen(marker_outline_pen)
            painter.drawLine(
                QPointF(marker_x, track_y - 8.0),
                QPointF(marker_x, track_y + track_height + 8.0),
            )
            painter.restore()

            marker_pen = QPen(QColor("#DD3739"), 4.0)
            marker_pen.setCapStyle(Qt.SquareCap)
            painter.setPen(marker_pen)
            painter.drawLine(
                QPointF(marker_x, track_y - 8.0),
                QPointF(marker_x, track_y + track_height + 8.0),
            )
        self._draw_digital_segments(
            painter, track_x, track_y, track_width, track_height, 0, current_count, "#F5F5F5"
        )

        track_outline_pen = QPen(QColor(self.MODERN_OUTLINE_COLOR), self.DIGITAL_OUTLINE_WIDTH)
        track_outline_pen.setJoinStyle(Qt.MiterJoin)
        painter.setPen(track_outline_pen)
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(track_x, track_y, track_width, track_height))

        center_y = (y0 + y1) / 2.0
        self._draw_modern_outlined_text(
            painter,
            QRectF(x0 + 2.0, y0 + 9.0, 50.0, y1 - y0 - 18.0),
            Qt.AlignCenter,
            telemetry.format_gear_for_hud(telemetry.last_gear),
            QFont("Consolas", 42, QFont.Bold),
            self.DIGITAL_TEXT_OUTLINE_THICKNESS,
        )

        actual_rpm_text = str(max(0, int(round(float(telemetry.last_rpm or 0.0)))))
        self._draw_modern_outlined_text(
            painter,
            QRectF(
                track_x + track_width / 2.0 - 64.0,
                y0,
                128.0,
                max(1.0, track_y - y0 - 4.0),
            ),
            Qt.AlignCenter,
            actual_rpm_text,
            QFont("Consolas", self.DIGITAL_RPM_FONT_SIZE, QFont.Bold),
            self.DIGITAL_TEXT_OUTLINE_THICKNESS,
        )

        unit = "mph" if self.state.hud.speed_unit == "mph" else "km"
        speed_value = telemetry.convert_hud_speed(max(0.0, float(telemetry.last_speed or 0.0)), unit)
        speed_text = str(max(0, min(999, int(round(speed_value)))))
        right = x1 - 3.0
        baseline = center_y + 16.0
        painter.setFont(QFont("Consolas", 12, QFont.Bold))
        unit_width = painter.fontMetrics().horizontalAdvance(unit)
        painter.setFont(QFont("Consolas", 32, QFont.Bold))
        speed_width = painter.fontMetrics().horizontalAdvance(speed_text)
        speed_x = right - unit_width - 4.0 - speed_width
        self._draw_outlined_text_at_point(
            painter,
            QPointF(speed_x, baseline),
            speed_text,
            QFont("Consolas", 32, QFont.Bold),
            self.DIGITAL_TEXT_OUTLINE_THICKNESS,
        )
        self._draw_outlined_text_at_point(
            painter,
            QPointF(right - unit_width, baseline),
            unit,
            QFont("Consolas", 12, QFont.Bold),
            self.DIGITAL_TEXT_OUTLINE_THICKNESS,
        )

    def _draw_digital_segments(
        self,
        painter: QPainter,
        track_x: float,
        track_y: float,
        track_width: float,
        track_height: float,
        start_index: int,
        end_index: int,
        color: str,
    ) -> None:
        start_index = max(0, min(self.DIGITAL_SEGMENT_COUNT, int(start_index)))
        end_index = max(start_index, min(self.DIGITAL_SEGMENT_COUNT, int(end_index)))
        if end_index <= start_index:
            return
        step = track_width / self.DIGITAL_SEGMENT_COUNT
        segment_width = max(1.0, step - self.DIGITAL_SEGMENT_GAP)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        for index in range(start_index, end_index):
            painter.drawRect(
                QRectF(
                    track_x + index * step,
                    track_y,
                    segment_width,
                    track_height,
                )
            )

    @classmethod
    def _draw_outlined_text_at_point(
        cls,
        painter: QPainter,
        point: QPointF,
        text: str,
        font: QFont,
        thickness: int,
    ) -> None:
        painter.setFont(font)
        painter.setPen(QColor(cls.MODERN_OUTLINE_COLOR))
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy <= thickness * thickness:
                    painter.drawText(point + QPointF(dx, dy), text)
        painter.setPen(QColor("#F5F5F5"))
        painter.drawText(point, text)

    def _draw_rpm_modern(self, painter: QPainter, x0: float, y0: float, x1: float, y1: float) -> None:
        telemetry = self.state.telemetry
        max_rpm = max(1.0, float(telemetry.last_max_rpm or 0.0))
        rpm = telemetry.stable_rpm_hud_value()
        display_max_rpm = telemetry.rpm_display_max_rpm(max_rpm)
        ratio = max(0.0, min(1.0, rpm / display_max_rpm))
        peak_guide_rpm = telemetry.current_rpm_hud_peak_guide()
        peak_guide_ratio = max(0.0, min(1.0, peak_guide_rpm / display_max_rpm))
        red_start_ratio = max(0.0, min(1.0, (max_rpm * 0.85) / display_max_rpm))
        speed_kmh = max(0.0, float(telemetry.last_speed or 0.0))

        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        outer_radius = diameter / 2.0 - 5.0
        inner_radius = outer_radius * 0.78

        # RPM layers, bottom to top: unfilled, red zone, learned shift marker, current RPM.
        self._draw_modern_rpm_band(
            painter, center_x, center_y, outer_radius, inner_radius, 0.0, 1.0, "#050608"
        )
        self._draw_modern_rpm_band(
            painter, center_x, center_y, outer_radius, inner_radius, red_start_ratio, 1.0, "#960D52"
        )
        if peak_guide_ratio > 0.0:
            self._draw_modern_shift_marker(
                painter, center_x, center_y, outer_radius, inner_radius, peak_guide_ratio
            )
        self._draw_modern_rpm_band(
            painter, center_x, center_y, outer_radius, inner_radius, 0.0, ratio, "#F5F5F5"
        )
        self._draw_modern_rpm_outline(
            painter,
            center_x,
            center_y,
            outer_radius,
            inner_radius,
        )

        self._draw_modern_gear(
            painter,
            center_x,
            center_y,
            telemetry.format_gear_for_hud(telemetry.last_gear),
            str(max(0, int(round(float(telemetry.last_rpm or 0.0))))),
        )
        self._draw_modern_speed(painter, center_x, center_y, outer_radius, speed_kmh)

    def _draw_rpm_gauge(self, painter: QPainter, x0: float, y0: float, x1: float, y1: float) -> None:
        telemetry = self.state.telemetry
        raw_rpm = max(0.0, float(telemetry.last_rpm or 0.0))
        max_rpm = max(1.0, float(telemetry.last_max_rpm or 0.0))
        idle_rpm = max(0.0, float(telemetry.last_idle_rpm or 0.0))
        gear = telemetry.last_gear
        speed_kmh = max(0.0, float(telemetry.last_speed or 0.0))
        rpm = telemetry.stable_rpm_hud_value()
        display_max_rpm = telemetry.rpm_display_max_rpm(max_rpm)
        ratio = max(0.0, min(1.0, rpm / display_max_rpm))
        peak_guide_rpm = telemetry.current_rpm_hud_peak_guide()
        peak_guide_ratio = max(0.0, min(1.0, peak_guide_rpm / display_max_rpm))
        shift_start_ratio = max(0.0, min(1.0, (max_rpm * 0.85) / display_max_rpm))
        red_start_ratio = max(shift_start_ratio, min(1.0, (max_rpm * 0.96) / display_max_rpm))
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        outer_pad = 2.0
        outer_radius = diameter / 2.0 - outer_pad
        inner_radius = outer_radius * 0.48

        painter.setPen(QPen(QColor("#252c35"), 1.0))
        painter.setBrush(QColor("#151a20"))
        painter.drawEllipse(QPointF(center_x, center_y), outer_radius, outer_radius)

        self._draw_rpm_ring_band(painter, center_x, center_y, outer_radius, outer_radius * 0.86, 0.0, shift_start_ratio, "#20272f")
        self._draw_rpm_pie_zone(painter, center_x, center_y, outer_radius, shift_start_ratio, red_start_ratio, "#805200")
        self._draw_rpm_pie_zone(painter, center_x, center_y, outer_radius, red_start_ratio, 1.0, "#8C0437")
        self._draw_rpm_sweep_design_line(painter, center_x, center_y, outer_radius, inner_radius)
        self._draw_rpm_ticks(painter, center_x, center_y, outer_radius, display_max_rpm)

        needle_angle = self.rpm_angle_degrees(ratio)
        needle_inner = max(0.0, inner_radius * 0.68 - 5.0)
        needle_outer = outer_radius * 0.92
        self._clear_rpm_center(painter, center_x, center_y, inner_radius)

        if peak_guide_ratio > 0.0:
            self._draw_rpm_needle(painter, center_x, center_y, needle_inner, needle_outer, self.rpm_angle_degrees(peak_guide_ratio), "#ff304f", 2.4)

        self._needle_angles.append(needle_angle)
        self._needle_angles = self._needle_angles[-4:]
        self._draw_rpm_needle_motion_blur(painter, center_x, center_y, inner_radius, needle_outer, self._needle_angles)
        self._draw_rpm_needle(painter, center_x, center_y, needle_inner, needle_outer, needle_angle, "#f1c40f", 4.0)

        self._draw_outlined_text(
            painter,
            center_x,
            center_y,
            telemetry.format_gear_for_hud(gear),
            QFont("Consolas", max(16, int(outer_radius * 0.342)), QFont.Bold),
            telemetry.rpm_gear_color(raw_rpm, max_rpm, idle_rpm),
            "#11161c",
            2,
        )
        self._draw_rpm_speed_text(painter, center_x, center_y, outer_radius, speed_kmh)

    @staticmethod
    def _clear_rpm_center(painter: QPainter, center_x: float, center_y: float, radius: float) -> None:
        painter.save()
        painter.setCompositionMode(QPainter.CompositionMode_Clear)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(0, 0, 0, 0))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)
        painter.restore()

        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        painter.setPen(QPen(QColor("#252c35"), 1.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

    @staticmethod
    def rpm_angle_degrees(ratio: float) -> float:
        return 240.0 - max(0.0, min(1.0, ratio)) * 240.0

    @staticmethod
    def _rpm_point(center_x: float, center_y: float, radius: float, angle: float) -> QPointF:
        radians = math.radians(angle)
        return QPointF(center_x + math.cos(radians) * radius, center_y - math.sin(radians) * radius)

    def _draw_rpm_pie_zone(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        radius: float,
        start_ratio: float,
        end_ratio: float,
        color: str,
    ) -> None:
        if end_ratio <= start_ratio:
            return
        start_angle = self.rpm_angle_degrees(start_ratio)
        end_angle = self.rpm_angle_degrees(end_ratio) - (7.0 if end_ratio >= 1.0 else 0.0)
        steps = max(3, int(abs(end_angle - start_angle) / 6.0))
        points = [QPointF(center_x, center_y)]
        for step in range(steps + 1):
            angle = start_angle + (end_angle - start_angle) * step / steps
            points.append(self._rpm_point(center_x, center_y, radius, angle))
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(points))

    def _draw_rpm_ring_band(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
        start_ratio: float,
        end_ratio: float,
        color: str,
    ) -> None:
        if end_ratio <= start_ratio:
            return
        start_angle = self.rpm_angle_degrees(start_ratio) + 5.0
        end_angle = self.rpm_angle_degrees(end_ratio)
        steps = 36
        outer_points = [
            self._rpm_point(center_x, center_y, outer_radius, start_angle + (end_angle - start_angle) * step / steps)
            for step in range(steps + 1)
        ]
        inner_points = [
            self._rpm_point(center_x, center_y, inner_radius, start_angle + (end_angle - start_angle) * step / steps)
            for step in range(steps, -1, -1)
        ]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(outer_points + inner_points))

    def _draw_modern_rpm_band(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
        start_ratio: float,
        end_ratio: float,
        color: str,
    ) -> None:
        start_ratio = max(0.0, min(1.0, start_ratio))
        end_ratio = max(0.0, min(1.0, end_ratio))
        if end_ratio <= start_ratio:
            return
        start_angle = self.rpm_angle_degrees(start_ratio)
        end_angle = self.rpm_angle_degrees(end_ratio)
        steps = max(4, int(abs(end_angle - start_angle) / 3.0))
        outer_points = [
            self._rpm_point(
                center_x,
                center_y,
                outer_radius,
                start_angle + (end_angle - start_angle) * step / steps,
            )
            for step in range(steps + 1)
        ]
        inner_points = [
            self._rpm_point(
                center_x,
                center_y,
                inner_radius,
                start_angle + (end_angle - start_angle) * step / steps,
            )
            for step in range(steps, -1, -1)
        ]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(color))
        painter.drawPolygon(QPolygonF(outer_points + inner_points))

    def _draw_modern_shift_marker(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
        ratio: float,
    ) -> None:
        angle = self.rpm_angle_degrees(ratio)

        # Keep the marker outline outside the RPM band so the red marker remains
        # clean through the band itself.  Odd-even fill leaves only the inner and
        # outer radial areas available to the outline stroke.
        clip_extent = outer_radius + self.MODERN_MARKER_OUTLINE_WIDTH + 2.0
        outline_clip = QPainterPath()
        outline_clip.setFillRule(Qt.OddEvenFill)
        outline_clip.addRect(
            QRectF(
                center_x - clip_extent,
                center_y - clip_extent,
                clip_extent * 2.0,
                clip_extent * 2.0,
            )
        )
        outline_clip.addEllipse(QPointF(center_x, center_y), outer_radius, outer_radius)
        outline_clip.addEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)

        painter.save()
        painter.setClipPath(outline_clip)
        outline_pen = QPen(QColor(self.MODERN_OUTLINE_COLOR), self.MODERN_MARKER_OUTLINE_WIDTH)
        outline_pen.setCapStyle(Qt.SquareCap)
        painter.setPen(outline_pen)
        painter.drawLine(
            self._rpm_point(center_x, center_y, inner_radius - 2.0, angle),
            self._rpm_point(center_x, center_y, outer_radius + 5.0, angle),
        )
        painter.restore()

        pen = QPen(QColor("#DD3739"), 4.0)
        pen.setCapStyle(Qt.SquareCap)
        painter.setPen(pen)
        painter.drawLine(
            self._rpm_point(center_x, center_y, inner_radius - 2.0, angle),
            self._rpm_point(center_x, center_y, outer_radius + 5.0, angle),
        )

    def _draw_modern_rpm_outline(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        outer_radius: float,
        inner_radius: float,
    ) -> None:
        start_angle = self.rpm_angle_degrees(0.0)
        end_angle = self.rpm_angle_degrees(1.0)
        steps = 80
        outer_points = [
            self._rpm_point(
                center_x,
                center_y,
                outer_radius,
                start_angle + (end_angle - start_angle) * step / steps,
            )
            for step in range(steps + 1)
        ]
        inner_points = [
            self._rpm_point(
                center_x,
                center_y,
                inner_radius,
                start_angle + (end_angle - start_angle) * step / steps,
            )
            for step in range(steps, -1, -1)
        ]
        pen = QPen(QColor(self.MODERN_OUTLINE_COLOR), self.MODERN_GAUGE_OUTLINE_WIDTH)
        pen.setJoinStyle(Qt.RoundJoin)
        pen.setCapStyle(Qt.RoundCap)
        painter.setBrush(Qt.NoBrush)
        painter.setPen(pen)
        painter.drawPolygon(QPolygonF(outer_points + inner_points))

    @classmethod
    def _draw_modern_gear(
        cls,
        painter: QPainter,
        center_x: float,
        center_y: float,
        gear_text: str,
        rpm_text: str,
    ) -> None:
        cls._draw_modern_outlined_text(
            painter,
            QRectF(center_x - 31.0, center_y - 32.0, 62.0, 64.0),
            Qt.AlignCenter,
            gear_text,
            QFont("Consolas", cls.MODERN_GEAR_FONT_SIZE, QFont.Bold),
            1,
        )
        rpm_font_size = max(4, int(round(cls.MODERN_GEAR_FONT_SIZE * cls.MODERN_RPM_FONT_RATIO)))
        cls._draw_modern_outlined_text(
            painter,
            QRectF(center_x - 36.0, center_y - 50.0, 72.0, 18.0),
            Qt.AlignCenter,
            rpm_text,
            QFont("Consolas", rpm_font_size, QFont.Bold),
            1,
        )

    def _draw_modern_speed(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        radius: float,
        speed_kmh: float,
    ) -> None:
        unit = "mph" if self.state.hud.speed_unit == "mph" else "km"
        speed_value = self.state.telemetry.convert_hud_speed(speed_kmh, unit)
        speed_text = str(max(0, min(999, int(round(speed_value)))))
        right = round(center_x + radius * 0.94)
        unit_font = QFont("Consolas", 12, QFont.Bold)
        painter.setFont(unit_font)
        unit_width = painter.fontMetrics().horizontalAdvance(unit)
        self._draw_modern_outlined_text(
            painter,
            QRectF(right - unit_width - 2.0, center_y + 13.0, unit_width + 2.0, 18.0),
            Qt.AlignRight | Qt.AlignVCenter,
            unit,
            unit_font,
            1,
        )
        speed_font = QFont("Consolas", 32, QFont.Bold)
        painter.setFont(speed_font)
        speed_width = painter.fontMetrics().horizontalAdvance(speed_text)
        self._draw_modern_outlined_text(
            painter,
            QRectF(right - speed_width - 2.0, center_y + 31.0, speed_width + 2.0, 42.0),
            Qt.AlignRight | Qt.AlignVCenter,
            speed_text,
            speed_font,
            1,
        )

    @classmethod
    def _draw_modern_outlined_text(
        cls,
        painter: QPainter,
        rect: QRectF,
        alignment: Qt.AlignmentFlag,
        text: str,
        font: QFont,
        thickness: int,
    ) -> None:
        painter.setFont(font)
        painter.setPen(QColor(cls.MODERN_OUTLINE_COLOR))
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy <= thickness * thickness:
                    painter.drawText(rect.translated(dx, dy), alignment, text)
        painter.setPen(QColor("#F5F5F5"))
        painter.drawText(rect, alignment, text)

    def _draw_rpm_sweep_design_line(self, painter: QPainter, center_x: float, center_y: float, outer_radius: float, inner_radius: float) -> None:
        radius = inner_radius + (outer_radius - inner_radius) * 0.27
        self._draw_arc_line(painter, center_x, center_y, radius, 0.0, 240.0, "#252c35", 1.0)

    def _draw_rpm_ticks(self, painter: QPainter, center_x: float, center_y: float, radius: float, display_max_rpm: float) -> None:
        if display_max_rpm <= 1.0:
            return
        max_tick = int(display_max_rpm // 1000) * 1000
        painter.setFont(QFont("Consolas", 8, QFont.Bold))
        for tick_rpm in range(0, max_tick + 1, 1000):
            ratio = max(0.0, min(1.0, tick_rpm / display_max_rpm))
            angle = self.rpm_angle_degrees(ratio)
            tick_outer = radius * 0.97
            tick_inner = radius * 0.88
            painter.setPen(QPen(QColor("#eef3f4"), 1.0))
            painter.drawLine(
                self._rpm_point(center_x, center_y, tick_inner, angle),
                self._rpm_point(center_x, center_y, tick_outer, angle),
            )
            label_point = self._rpm_point(center_x, center_y, radius * 0.80, angle)
            painter.setPen(QColor("#eef3f4"))
            painter.drawText(QRectF(label_point.x() - 10.0, label_point.y() - 7.0, 20.0, 14.0), Qt.AlignCenter, str(int(tick_rpm / 1000.0)))

    def _draw_arc_line(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        radius: float,
        start_angle: float,
        end_angle: float,
        color: str,
        width: float,
    ) -> None:
        steps = max(8, int(abs(end_angle - start_angle) / 4.0))
        points = [
            self._rpm_point(center_x, center_y, radius, start_angle + (end_angle - start_angle) * step / steps)
            for step in range(steps + 1)
        ]
        painter.setPen(QPen(QColor(color), width))
        for previous, current in zip(points, points[1:]):
            painter.drawLine(previous, current)

    def _draw_rpm_needle_motion_blur(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angles: list[float],
    ) -> None:
        if len(angles) < 2:
            return
        blur_colors = ("#3a3008", "#5c4a0b", "#f1c40f")
        segments = list(zip(angles[:-1], angles[1:]))[-len(blur_colors):]
        color_offset = len(blur_colors) - len(segments)
        for index, (previous_angle, current_angle) in enumerate(segments):
            delta = current_angle - previous_angle
            if abs(delta) < 0.35:
                continue
            if abs(delta) > 42.0:
                previous_angle = current_angle - math.copysign(42.0, delta)
                delta = current_angle - previous_angle
            steps = max(2, min(10, int(abs(delta) / 4.0) + 2))
            outer_points = [
                self._rpm_point(center_x, center_y, needle_outer, previous_angle + delta * step / steps)
                for step in range(steps + 1)
            ]
            inner_points = [
                self._rpm_point(center_x, center_y, needle_inner, previous_angle + delta * step / steps)
                for step in range(steps, -1, -1)
            ]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(blur_colors[color_offset + index]))
            painter.drawPolygon(QPolygonF(outer_points + inner_points))

    def _draw_rpm_needle(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angle: float,
        color: str,
        width: float,
    ) -> None:
        pen = QPen(QColor(color), width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(
            self._rpm_point(center_x, center_y, needle_inner, angle),
            self._rpm_point(center_x, center_y, needle_outer, angle),
        )

    def _draw_outlined_text(
        self,
        painter: QPainter,
        x: float,
        y: float,
        text: str,
        font: QFont,
        fill: str,
        outline: str,
        thickness: int,
    ) -> None:
        painter.setFont(font)
        rect = QRectF(x - 42.0, y - 28.0, 84.0, 56.0)
        painter.setPen(QColor(outline))
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx == 0 and dy == 0:
                    continue
                if dx * dx + dy * dy <= thickness * thickness:
                    painter.drawText(rect.translated(dx, dy), Qt.AlignCenter, text)
        painter.setPen(QColor(fill))
        painter.drawText(rect, Qt.AlignCenter, text)

    def _draw_rpm_speed_text(self, painter: QPainter, center_x: float, center_y: float, radius: float, speed_kmh: float) -> None:
        unit = "mph" if self.state.hud.speed_unit == "mph" else "km"
        speed_value = self.state.telemetry.convert_hud_speed(speed_kmh, unit)
        speed_text = str(max(0, min(999, int(round(speed_value)))))
        x = center_x + radius * 0.61 - 7.0
        y = center_y + radius * 0.82 + 3.0
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        painter.setPen(QColor("#9aa4af"))
        painter.drawText(QRectF(x - 54.0, y - radius * 0.31 - 14.0, 54.0, 14.0), Qt.AlignRight | Qt.AlignVCenter, self.state.telemetry.hud_speed_unit_label(unit))
        painter.setFont(QFont("Consolas", max(13, int(radius * 0.245)), QFont.Bold))
        painter.setPen(QColor("#eef3f4"))
        painter.drawText(QRectF(x - 58.0, y - 24.0, 58.0, 24.0), Qt.AlignRight | Qt.AlignVCenter, speed_text)


class EngineHudOverlay(HudOverlayBase):
    HUD_NAME = "Engine"
    WIDTH = 76
    HEIGHT = 160
    DEFAULT_X = 788
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "Engine HUD")
        self._power_needle_angles: list[float] = []
        self._vacuum_needle_angles: list[float] = []

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        width = float(self.WIDTH)
        height = float(self.HEIGHT)
        gap = max(4.0, min(10.0, height * 0.05))
        diameter = min(width, (height - gap) / 2.0)
        left = (width - diameter) / 2.0
        power_y = 0.0
        boost_y = diameter + gap
        self._draw_power_meter(painter, left, power_y, left + diameter, power_y + diameter)
        self._draw_boost_meter(painter, left, boost_y, left + diameter, boost_y + diameter)

    def _draw_engine_meter_shell(
        self,
        painter: QPainter,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        tick_angles: tuple[float, ...],
    ) -> tuple[float, float, float, float]:
        center_x = (x0 + x1) / 2.0
        center_y = (y0 + y1) / 2.0
        diameter = min(x1 - x0, y1 - y0)
        pad = max(1.0, diameter * 0.03)
        radius = (diameter - pad * 2.0) / 2.0
        inner_radius = radius * 0.58
        painter.setPen(QPen(QColor("#252c35"), 1.0))
        painter.setBrush(QColor("#151a20"))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)
        painter.setPen(QPen(QColor("#d6dde5"), 1.0))
        for angle in tick_angles:
            tick_outer = radius * 0.94
            tick_inner = radius * 0.80
            painter.drawLine(
                self._engine_point(center_x, center_y, tick_inner, angle),
                self._engine_point(center_x, center_y, tick_outer, angle),
            )
        return center_x, center_y, radius, inner_radius

    def _draw_power_meter(self, painter: QPainter, x0: float, y0: float, x1: float, y1: float) -> None:
        telemetry = self.state.telemetry
        raw_power = max(0.0, float(telemetry.last_power or 0.0))
        key = int(telemetry.last_car_ordinal or 0)
        positive_peak = max(telemetry.engine_hud_power_peak_by_car.get(key, 0.0), raw_power)
        telemetry.engine_hud_power_peak_by_car[key] = positive_peak
        power = telemetry.smoothed_engine_hud_power(raw_power)
        positive_max = max(1000.0, positive_peak)
        positive_ratio = max(0.0, min(1.0, power / positive_max))
        zero_angle = 0.0
        positive_sweep_degrees = 120.0
        center_x, center_y, radius, _inner_radius = self._draw_engine_meter_shell(
            painter,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(zero_angle, zero_angle + positive_sweep_degrees),
        )
        track_radius = radius * 0.86
        positive_color = "#119C8E"
        needle_color = "#13C9B4"
        self._draw_engine_arc(painter, center_x, center_y, track_radius, 0.0, positive_sweep_degrees, "#252c35", 3.0)
        if positive_ratio > 0.025:
            self._draw_engine_arc(painter, center_x, center_y, track_radius, 0.0, positive_sweep_degrees * positive_ratio, positive_color, 3.0)
        needle_angle = zero_angle + positive_sweep_degrees * positive_ratio
        needle_outer = radius * 0.68
        cap_radius = max(2.0, radius * 0.07)
        self._power_needle_angles.append(needle_angle)
        self._power_needle_angles = self._power_needle_angles[-4:]
        self._draw_engine_needle_motion_blur(painter, center_x, center_y, cap_radius, needle_outer, self._power_needle_angles, ("#073b34", "#0a6f60", needle_color))
        power_unit = self.state.hud.power_unit
        painter.setFont(QFont("Consolas", max(5, int((x1 - x0) * 0.083)), QFont.Bold))
        painter.setPen(QColor("#8b96a3"))
        painter.drawText(QRectF(center_x - 22.0, center_y - radius * 0.42 - 12.0, 44.0, 12.0), Qt.AlignCenter, telemetry.hud_power_unit_label(power_unit))
        painter.setFont(QFont("Consolas", max(5, int((x1 - x0) * 0.105)), QFont.Bold))
        painter.setPen(QColor(positive_color))
        painter.drawText(QRectF(center_x - 26.0, center_y + 16.0, 52.0, 14.0), Qt.AlignCenter, telemetry.format_hud_power_value(power, power_unit))
        self._draw_engine_needle(painter, center_x, center_y, needle_outer, needle_angle, needle_color, 3.0, cap_radius)

    def _draw_boost_meter(self, painter: QPainter, x0: float, y0: float, x1: float, y1: float) -> None:
        telemetry = self.state.telemetry
        raw_boost = float(telemetry.last_boost or 0.0)
        car_ordinal = int(telemetry.last_car_ordinal or 0)
        if car_ordinal:
            peak = max(telemetry.engine_hud_boost_peak_by_car.get(car_ordinal, 0.0), raw_boost)
            telemetry.engine_hud_boost_peak_by_car[car_ordinal] = peak
        else:
            peak = max(0.0, raw_boost)
        boost = telemetry.smoothed_engine_hud_boost(raw_boost)
        if not telemetry.engine_hud_should_show_boost_meter(peak, raw_boost):
            self._vacuum_needle_angles.clear()
            self._draw_vacuum_meter(painter, x0, y0, x1, y1, boost)
            return
        positive_max = telemetry.boost_display_positive_max(peak)
        negative_min = -18.0
        positive_ratio = 0.0 if positive_max <= 0.0 else max(0.0, min(1.0, boost / positive_max))
        negative_ratio = 0.0 if boost >= 0.0 else max(0.0, min(1.0, abs(boost / negative_min)))
        positive_sweep_degrees = 120.0
        negative_sweep_degrees = 120.0
        center_x, center_y, radius, _inner_radius = self._draw_engine_meter_shell(
            painter,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(-negative_sweep_degrees, 0.0, positive_sweep_degrees),
        )
        track_radius = radius * 0.86
        gauge_color = "#f1c40f"
        value_color = "#2ea8ff" if boost < 0.0 else gauge_color
        arc_color = "#2f5e73" if boost < 0.0 else gauge_color
        self._draw_engine_arc(painter, center_x, center_y, track_radius, -negative_sweep_degrees, 0.0, "#252c35", 3.0)
        self._draw_engine_arc(painter, center_x, center_y, track_radius, 0.0, positive_sweep_degrees, "#252c35", 3.0)
        needle_angle = positive_sweep_degrees * positive_ratio if boost >= 0.0 else -negative_sweep_degrees * negative_ratio
        active_end = needle_angle
        if abs(active_end) >= 3.0:
            self._draw_engine_arc(painter, center_x, center_y, track_radius, 0.0, active_end, arc_color, 3.0)
        needle_outer = radius * 0.68
        cap_radius = max(2.0, radius * 0.07)
        needle_color = value_color if boost < 0.0 else gauge_color
        boost_unit = self.state.hud.boost_unit
        painter.setFont(QFont("Consolas", max(5, int((x1 - x0) * 0.083)), QFont.Bold))
        painter.setPen(QColor("#8b96a3"))
        painter.drawText(QRectF(center_x - 22.0, center_y - radius * 0.42 - 12.0, 44.0, 12.0), Qt.AlignCenter, telemetry.hud_boost_unit_label(boost_unit))
        painter.setFont(QFont("Consolas", max(5, int((x1 - x0) * 0.105)), QFont.Bold))
        painter.setPen(QColor(value_color))
        self._draw_engine_right_value(
            painter,
            center_x,
            center_y,
            radius,
            telemetry.format_hud_boost_value(boost, boost_unit),
        )
        self._draw_engine_needle(painter, center_x, center_y, needle_outer, needle_angle, needle_color, 3.0, cap_radius)

    @staticmethod
    def _draw_engine_right_value(
        painter: QPainter,
        center_x: float,
        center_y: float,
        radius: float,
        text: str,
    ) -> None:
        width = max(40.0, radius * 1.36)
        right_x = center_x + radius * 0.92
        rect = QRectF(right_x - width, center_y + radius * 0.05 - 10.0, width, 14.0)
        painter.drawText(rect, Qt.AlignRight | Qt.AlignVCenter, text)

    def _draw_vacuum_meter(self, painter: QPainter, x0: float, y0: float, x1: float, y1: float, boost: float) -> None:
        vacuum_min = -15.0
        vacuum_psi = max(vacuum_min, min(0.0, boost))
        vacuum_ratio = max(0.0, min(1.0, (vacuum_psi - vacuum_min) / abs(vacuum_min)))
        start_angle = 210.0
        max_angle = 360.0
        sweep_degrees = 150.0
        center_x, center_y, radius, _inner_radius = self._draw_engine_meter_shell(
            painter,
            x0,
            y0,
            x1,
            y1,
            tick_angles=(start_angle, max_angle),
        )
        track_radius = radius * 0.86
        gauge_color = "#2f5e73"
        value_color = "#2ea8ff"
        self._draw_engine_arc(painter, center_x, center_y, track_radius, start_angle, max_angle, "#252c35", 3.0)
        needle_angle = start_angle + sweep_degrees * vacuum_ratio
        if vacuum_ratio > 0.025:
            self._draw_engine_arc(painter, center_x, center_y, track_radius, start_angle, needle_angle, gauge_color, 3.0)
        needle_outer = radius * 0.68
        cap_radius = max(2.0, radius * 0.07)
        self._vacuum_needle_angles.append(needle_angle)
        self._vacuum_needle_angles = self._vacuum_needle_angles[-4:]
        self._draw_engine_needle_motion_blur(painter, center_x, center_y, cap_radius, needle_outer, self._vacuum_needle_angles, ("#173542", "#234f63", gauge_color))
        boost_unit = self.state.hud.boost_unit
        painter.setFont(QFont("Consolas", max(4, int((x1 - x0) * 0.075)), QFont.Bold))
        painter.setPen(QColor("#8b96a3"))
        painter.drawText(QRectF(center_x - 22.0, center_y - radius * 0.42 - 12.0, 44.0, 12.0), Qt.AlignCenter, self.state.telemetry.hud_boost_unit_label(boost_unit))
        painter.setFont(QFont("Consolas", max(5, int((x1 - x0) * 0.105)), QFont.Bold))
        painter.setPen(QColor(value_color))
        self._draw_engine_right_value(
            painter,
            center_x,
            center_y,
            radius,
            self.state.telemetry.format_hud_boost_value(vacuum_psi, boost_unit),
        )
        self._draw_engine_needle(painter, center_x, center_y, needle_outer, needle_angle, value_color, 3.0, cap_radius)

    @staticmethod
    def _engine_point(center_x: float, center_y: float, radius: float, angle: float) -> QPointF:
        radians = math.radians(angle)
        return QPointF(center_x + math.sin(radians) * radius, center_y - math.cos(radians) * radius)

    def _draw_engine_arc(self, painter: QPainter, center_x: float, center_y: float, radius: float, start_angle: float, end_angle: float, color: str, width: float) -> None:
        steps = max(6, int(abs(end_angle - start_angle) / 4.0))
        points = [
            self._engine_point(center_x, center_y, radius, start_angle + (end_angle - start_angle) * step / steps)
            for step in range(steps + 1)
        ]
        painter.setPen(QPen(QColor(color), width))
        for previous, current in zip(points, points[1:]):
            painter.drawLine(previous, current)

    def _draw_engine_needle(self, painter: QPainter, center_x: float, center_y: float, needle_outer: float, angle: float, color: str, width: float, cap_radius: float) -> None:
        needle_color = QColor(color)
        needle_color.setAlpha(255)
        pen = QPen(needle_color, width)
        pen.setCapStyle(Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(QPointF(center_x, center_y), self._engine_point(center_x, center_y, needle_outer, angle))
        painter.setPen(Qt.NoPen)
        painter.setBrush(needle_color)
        painter.drawEllipse(QPointF(center_x, center_y), cap_radius, cap_radius)

    def _draw_engine_needle_motion_blur(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        needle_inner: float,
        needle_outer: float,
        angles: list[float],
        blur_colors: tuple[str, str, str],
    ) -> None:
        if len(angles) < 2:
            return
        segments = list(zip(angles[:-1], angles[1:]))[-len(blur_colors):]
        color_offset = len(blur_colors) - len(segments)
        for index, (previous_angle, current_angle) in enumerate(segments):
            delta = current_angle - previous_angle
            if abs(delta) < 0.35:
                continue
            if abs(delta) > 42.0:
                previous_angle = current_angle - math.copysign(42.0, delta)
                delta = current_angle - previous_angle
            steps = max(2, min(10, int(abs(delta) / 4.0) + 2))
            outer_points = [
                self._engine_point(center_x, center_y, needle_outer, previous_angle + delta * step / steps)
                for step in range(steps + 1)
            ]
            inner_points = [
                self._engine_point(center_x, center_y, needle_inner, previous_angle + delta * step / steps)
                for step in range(steps, -1, -1)
            ]
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(blur_colors[color_offset + index]))
            painter.drawPolygon(QPolygonF(outer_points + inner_points))


class PedalHudOverlay(HudOverlayBase):
    HUD_NAME = "Pedal"
    WIDTH = 68
    HEIGHT = 160
    DEFAULT_X = 80
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "Pedal HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        throttle = max(0.0, min(1.0, float(self.state.telemetry.last_throttle or 0.0) / 255.0))
        brake = max(0.0, min(1.0, float(self.state.telemetry.last_brake or 0.0) / 255.0))
        recommended_brake = self.state.telemetry.recommended_brake_level()
        recommended_throttle = self.state.telemetry.recommended_throttle_level()

        outer_pad = 1
        gap = 6
        bar_width = max(12, (self.WIDTH - outer_pad * 2 - gap) // 2)
        brake_x = outer_pad
        throttle_x = brake_x + bar_width + gap
        self._draw_split_bar(painter, brake_x, 0, bar_width, self.HEIGHT, brake, recommended_brake, "#BD1051")
        self._draw_split_bar(painter, throttle_x, 0, bar_width, self.HEIGHT, throttle, recommended_throttle, "#13AC96")

    def _draw_split_bar(
        self,
        painter: QPainter,
        x: int,
        y: int,
        width: int,
        height: int,
        value: float,
        recommended: float,
        base_color: str,
    ) -> None:
        value = max(0.0, min(1.0, float(value)))
        recommended = max(0.0, min(1.0, float(recommended)))
        inner_x = x + 1
        inner_y = y + 1
        inner_width = max(1, width - 2)
        inner_height = max(1, height - 2)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#151a20"))
        painter.drawRect(x, y, width - 1, height - 1)
        base_level = value if value <= recommended else recommended
        if base_level > 0.0:
            base_top = inner_y + inner_height - round(inner_height * base_level)
            painter.setBrush(QColor(base_color))
            painter.drawRect(inner_x, base_top, inner_width, inner_y + inner_height - base_top)
        if value > recommended:
            yellow_top = inner_y + inner_height - round(inner_height * value)
            yellow_bottom = inner_y + inner_height - round(inner_height * recommended)
            painter.setBrush(QColor("#AD8300"))
            painter.drawRect(inner_x, yellow_top, inner_width, max(1, yellow_bottom - yellow_top))
            painter.setPen(QColor("#eef3f4"))
            painter.drawLine(inner_x, yellow_bottom, inner_x + inner_width - 1, yellow_bottom)
            painter.setPen(Qt.NoPen)
        painter.setPen(QColor("#252c35"))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(x, y + height // 2, x + width - 1, y + height // 2)
        painter.drawRect(x, y, width - 1, height - 1)


class GForceHudOverlay(HudOverlayBase):
    HUD_NAME = "G-force"
    WIDTH = 160
    HEIGHT = 160
    DEFAULT_X = 160
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "G-force HUD")
        self._points: list[tuple[float, float]] = []
        self._previous_vector: tuple[float, float] | None = None
        self._impact_markers: list[tuple[float, float, float]] = []

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        lateral_g, longitudinal_g = self.state.telemetry.g_force_values()
        max_g = 2.0
        x_ratio = self._clamp(lateral_g / max_g, -1.0, 1.0)
        y_ratio = self._clamp(longitudinal_g / max_g, -1.0, 1.0)

        center_x = self.WIDTH / 2.0
        center_y = self.HEIGHT / 2.0
        outer_pad = 2.0
        outer = QRectF(outer_pad, outer_pad, self.WIDTH - outer_pad * 2.0, self.HEIGHT - outer_pad * 2.0)
        outer_radius = outer.width() / 2.0
        inner_radius = outer_radius * 0.5
        radius = max(1.0, outer_radius - 7.0)
        point = (center_x + x_ratio * radius, center_y - y_ratio * radius)

        self._update_impact_markers(point, (lateral_g, longitudinal_g))
        self._points.append(point)
        if len(self._points) > 4:
            del self._points[: len(self._points) - 4]

        painter.setPen(QColor("#252c35"))
        painter.setBrush(QColor("#151a20"))
        painter.drawEllipse(outer)
        painter.drawEllipse(QRectF(center_x - inner_radius, center_y - inner_radius, inner_radius * 2.0, inner_radius * 2.0))
        painter.drawLine(round(center_x), round(center_y - outer_radius), round(center_x), round(center_y + outer_radius))
        painter.drawLine(round(center_x - outer_radius), round(center_y), round(center_x + outer_radius), round(center_y))

        self._draw_slip_angle_arc(painter, outer)
        self._draw_impact_markers(painter)

        painter.setPen(QColor("#b89512"))
        painter.drawLine(round(center_x), round(center_y), round(point[0]), round(point[1]))
        colors = ("#3a3008", "#5c4a0b", "#9b7d0d", "#f1c40f")
        start_color = max(0, len(colors) - len(self._points))
        painter.setPen(Qt.NoPen)
        for index, (px, py) in enumerate(self._points):
            color = colors[start_color + index]
            radius_dot = 3 if index < len(self._points) - 1 else 4
            painter.setBrush(QColor(color))
            painter.drawEllipse(round(px - radius_dot), round(py - radius_dot), radius_dot * 2, radius_dot * 2)

    def _draw_slip_angle_arc(self, painter: QPainter, outer: QRectF) -> None:
        slip_angle = self.state.telemetry.hud_slip_angle_degrees()
        if abs(slip_angle) < 0.4:
            return
        display_angle = self._clamp(slip_angle, -175.0, 175.0)
        fill = QColor("#7f332f" if display_angle < 0.0 else "#2f5e73")
        edge = QColor("#d45a50" if display_angle < 0.0 else "#4aa4c7")
        start = 90 * 16
        span = round((-abs(display_angle) if display_angle > 0.0 else abs(display_angle)) * 16)
        painter.setPen(Qt.NoPen)
        painter.setBrush(fill)
        painter.drawPie(outer, start, span)
        painter.setPen(edge)
        painter.setBrush(Qt.NoBrush)
        painter.drawArc(outer, start, span)

    def _update_impact_markers(self, point: tuple[float, float], vector: tuple[float, float]) -> None:
        previous = self._previous_vector
        self._previous_vector = vector
        if previous is None:
            return
        delta_x = vector[0] - previous[0]
        delta_y = vector[1] - previous[1]
        delta_g = (delta_x * delta_x + delta_y * delta_y) ** 0.5
        if delta_g >= 0.75:
            self._impact_markers.append((point[0], point[1], monotonic()))

    def _draw_impact_markers(self, painter: QPainter) -> None:
        now = monotonic()
        keep_seconds = 0.90
        self._impact_markers = [marker for marker in self._impact_markers if now - marker[2] <= keep_seconds]
        painter.setPen(Qt.NoPen)
        for px, py, created_at in self._impact_markers:
            age = self._clamp((now - created_at) / keep_seconds, 0.0, 1.0)
            radius = max(1, round(6 - age * 2.0))
            painter.setBrush(QColor("#e74c3c" if age < 0.45 else "#8f2c2c"))
            painter.drawEllipse(round(px - radius), round(py - radius), radius * 2, radius * 2)

    @staticmethod
    def _clamp(value: float, minimum: float, maximum: float) -> float:
        return max(minimum, min(maximum, value))


class TireHudOverlay(HudOverlayBase):
    HUD_NAME = "Tire"
    WIDTH = 112
    HEIGHT = 160
    DEFAULT_X = 332
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "Tire HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        width = self.WIDTH
        height = self.HEIGHT
        gap_x = max(18.0, width * 0.22)
        gap_y = max(14.0, height * 0.10)
        outer_pad_y = 2.0
        outer_pad_x = 6.0
        tire_w = max(24.0, (width - gap_x - outer_pad_x * 2.0) / 2.0)
        tire_h = max(52.0, (height - gap_y - outer_pad_y * 2.0) / 2.0)
        tire_w = min(tire_w, tire_h * 0.50)
        start_x = (width - tire_w * 2.0 - gap_x) / 2.0
        start_y = outer_pad_y
        positions = (
            ("fl", start_x, start_y),
            ("fr", start_x + tire_w + gap_x, start_y),
            ("rl", start_x, start_y + tire_h + gap_y),
            ("rr", start_x + tire_w + gap_x, start_y + tire_h + gap_y),
        )
        for corner, x, y in positions:
            self._draw_hud_tire(painter, corner, x, y, x + tire_w, y + tire_h)

    def _draw_hud_tire(self, painter: QPainter, corner: str, x0: float, y0: float, x1: float, y1: float) -> None:
        temp_f = self.state.telemetry.tire_temperature_f(corner)
        temp_c = (temp_f - 32.0) * (5.0 / 9.0) if temp_f > 0.0 else 0.0
        combined = abs(float(getattr(self.state.telemetry, f"last_tire_combined_slip_{corner}") or 0.0))
        temp_color = self._tire_temperature_color(temp_c)
        display_colors = (
            (temp_color, temp_color, temp_color)
            if corner in ("fl", "rl")
            else (temp_color, temp_color, temp_color)
        )
        tire_rect = QRectF(x0, y0, x1 - x0, y1 - y0)
        corner_radius = max(4.0, min(tire_rect.width(), tire_rect.height()) * 0.22)
        tire_path = QPainterPath()
        tire_path.addRoundedRect(tire_rect, corner_radius, corner_radius)
        self._draw_rounded_tire_segments(painter, tire_rect, tire_path, display_colors)

        slip_level = max(0.0, min(1.0, combined / 2.0))
        if slip_level > 0.015:
            slip_y = y1 - (y1 - y0) * slip_level
            self._draw_rounded_tire_fill(painter, tire_rect, tire_path, slip_y, "#a84800")
        self._draw_rounded_tire_outline(painter, tire_rect, corner_radius, "#252c35")
        third = (x1 - x0) / 3.0
        painter.save()
        painter.setClipPath(tire_path)
        painter.setPen(QColor("#252c35"))
        for line_x in (x0 + third, x0 + third * 2.0):
            painter.drawLine(round(line_x), round(y0 + 1), round(line_x), round(y1 - 1))
        painter.restore()

        font_size = max(9, min(18, int((y1 - y0) * 0.21)))
        temp_text = "--" if temp_f <= 0.0 else f"{temp_c:.0f}"
        painter.setPen(QColor("#eef3f4"))
        painter.setFont(QFont("Consolas", font_size, QFont.Bold))
        painter.drawText(QRectF(x0, y0, x1 - x0, (y1 - y0) * 0.55), Qt.AlignCenter, temp_text)

    @staticmethod
    def _draw_rounded_tire_segments(
        painter: QPainter,
        rect: QRectF,
        clip_path: QPainterPath,
        fills: tuple[str, str, str],
    ) -> None:
        third = rect.width() / 3.0
        painter.save()
        painter.setClipPath(clip_path)
        painter.setPen(Qt.NoPen)
        for index, fill in enumerate(fills):
            painter.setBrush(QColor(fill))
            painter.drawRect(QRectF(rect.left() + third * index, rect.top(), third + 0.5, rect.height()))
        painter.restore()

    @staticmethod
    def _draw_rounded_tire_outline(
        painter: QPainter,
        rect: QRectF,
        corner_radius: float,
        outline: str,
    ) -> None:
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(outline))
        painter.drawRoundedRect(rect, corner_radius, corner_radius)

    @staticmethod
    def _draw_rounded_tire_fill(
        painter: QPainter,
        rect: QRectF,
        clip_path: QPainterPath,
        fill_y0: float,
        fill: str,
    ) -> None:
        fill_y0 = max(rect.top(), min(rect.bottom(), fill_y0))
        painter.save()
        painter.setClipPath(clip_path)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawRect(QRectF(rect.left(), fill_y0, rect.width(), rect.bottom() - fill_y0))
        painter.restore()

    @staticmethod
    def _draw_pixel_cut_tire_segments(
        painter: QPainter,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        notch: float,
        fills: tuple[str, str, str],
    ) -> None:
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
        third = (x1 - x0) / 3.0
        polygons = (
            (
                x0 + notch, y0,
                x0 + third, y0,
                x0 + third, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
                x0, y0 + notch,
                x0 + notch, y0 + notch,
            ),
            (
                x0 + third, y0,
                x0 + third * 2.0, y0,
                x0 + third * 2.0, y1,
                x0 + third, y1,
            ),
            (
                x0 + third * 2.0, y0,
                x1 - notch, y0,
                x1 - notch, y0 + notch,
                x1, y0 + notch,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + third * 2.0, y1,
            ),
        )
        painter.setPen(Qt.NoPen)
        for points, fill in zip(polygons, fills):
            painter.setBrush(QColor(fill))
            painter.drawPolygon(_polygon(points))

    @staticmethod
    def _draw_pixel_cut_tire_outline(
        painter: QPainter,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        notch: float,
        outline: str,
    ) -> None:
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - y0) / 2.0))
        points = (
            x0 + notch, y0,
            x1 - notch, y0,
            x1 - notch, y0 + notch,
            x1, y0 + notch,
            x1, y1 - notch,
            x1 - notch, y1 - notch,
            x1 - notch, y1,
            x0 + notch, y1,
            x0 + notch, y1 - notch,
            x0, y1 - notch,
            x0, y0 + notch,
            x0 + notch, y0 + notch,
            x0 + notch, y0,
        )
        painter.setBrush(Qt.NoBrush)
        painter.setPen(QColor(outline))
        painter.drawPolyline(_polygon(points))

    @staticmethod
    def _draw_pixel_cut_tire_fill(
        painter: QPainter,
        x0: float,
        fill_y0: float,
        x1: float,
        y1: float,
        notch: float,
        fill: str,
        tire_top: float,
    ) -> None:
        fill_y0 = max(tire_top, min(y1, fill_y0))
        notch = max(0.0, min(notch, (x1 - x0) / 2.0, (y1 - tire_top) / 2.0))
        if fill_y0 <= tire_top:
            points = (
                x0 + notch, tire_top,
                x1 - notch, tire_top,
                x1 - notch, tire_top + notch,
                x1, tire_top + notch,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
                x0, tire_top + notch,
                x0 + notch, tire_top + notch,
            )
        elif fill_y0 <= y1 - notch:
            points = (
                x0, fill_y0,
                x1, fill_y0,
                x1, y1 - notch,
                x1 - notch, y1 - notch,
                x1 - notch, y1,
                x0 + notch, y1,
                x0 + notch, y1 - notch,
                x0, y1 - notch,
            )
        else:
            points = (
                x0 + notch, fill_y0,
                x1 - notch, fill_y0,
                x1 - notch, y1,
                x0 + notch, y1,
            )
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(fill))
        painter.drawPolygon(_polygon(points))

    @staticmethod
    def _tire_temperature_color(temp_c: float) -> str:
        stops = (
            (20.0, "#151a20"),
            (55.0, "#004548"),
            (95.0, "#4f8700"),
            (140.0, "#b8ad00"),
        )
        if temp_c <= stops[0][0]:
            return stops[0][1]
        for index in range(1, len(stops)):
            low_temp, low_color = stops[index - 1]
            high_temp, high_color = stops[index]
            if temp_c <= high_temp:
                mix = _smoothstep(low_temp, high_temp, temp_c)
                return _mix_hex_color(low_color, high_color, mix)
        return stops[-1][1]


class SteerHudOverlay(HudOverlayBase):
    HUD_NAME = "Steer"
    WIDTH = 68
    HEIGHT = 160
    DEFAULT_X = 456
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "Steer HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        width = float(self.WIDTH)
        height = float(self.HEIGHT)
        painter.fillRect(QRectF(0.0, 0.0, width, height), QColor("#151a20"))

        balance, grip_loss = self.state.telemetry.current_oversteer_balance()
        color = QColor("#7f332f" if balance > 0.0 else "#2f5e73")
        magnitude = min(1.0, abs(balance))
        center_y = height * 0.5
        half_height = max(1.0, height * 0.5 - 1.0)
        bar_count = 20
        bar_gap = 1.0
        bar_width = max(1.0, math.floor((width - bar_gap * (bar_count - 1)) / float(bar_count)))
        total_bar_width = bar_width * bar_count + bar_gap * (bar_count - 1)
        left_pad = max(0.0, math.floor((width - total_bar_width) * 0.5))
        center_position = (bar_count - 1) / 2.0

        painter.setPen(Qt.NoPen)
        painter.setBrush(color)
        for index in range(bar_count):
            factor = self.steer_hud_bar_shape_factor(index, center_position, grip_loss)
            level = magnitude * factor
            if level <= 0.015:
                continue
            bx0 = left_pad + (bar_width + bar_gap) * index
            if balance > 0.0:
                top = center_y - half_height * level
                painter.drawRect(QRectF(bx0, top, bar_width, center_y - top))
            else:
                bottom = center_y + half_height * level
                painter.drawRect(QRectF(bx0, center_y, bar_width, bottom - center_y))

        painter.setPen(QColor("#252c35"))
        painter.setBrush(Qt.NoBrush)
        painter.drawLine(QPointF(0.0, center_y), QPointF(width - 1.0, center_y))
        painter.drawRect(QRectF(0.0, 0.0, width - 1.0, height - 1.0))

        painter.setFont(QFont("Segoe UI", max(6, int(height * 0.055)), QFont.Bold))
        painter.setPen(QColor("#9a5a56"))
        painter.drawText(QRectF(0.0, center_y - half_height * 0.88, width, 14.0), Qt.AlignCenter, "OVER")
        painter.setPen(QColor("#5c8292"))
        painter.drawText(QRectF(0.0, center_y + half_height * 0.72, width, 14.0), Qt.AlignCenter, "UNDER")

    @staticmethod
    def steer_hud_bar_shape_factor(index: int, center_position: float, grip_loss: float) -> float:
        grip_loss = max(0.0, min(1.0, grip_loss))
        distance = abs(index - center_position) / max(1.0, center_position)
        shape_loss = max(0.0, min(1.0, (grip_loss - 0.18) / 0.82))
        focus_power = 1.35 + shape_loss * 4.2
        focused_peak = max(0.0, 1.0 - distance) ** focus_power
        flat_shape = 1.0 - 0.08 * distance
        edge_floor = 0.012 + 0.12 * (1.0 - shape_loss)
        return max(edge_floor, flat_shape * (1.0 - shape_loss) + focused_peak * shape_loss)


class HapticVizHudOverlay(HudOverlayBase):
    HUD_NAME = "Haptic Viz"
    WIDTH = 68
    HEIGHT = 160
    DEFAULT_X = 536
    DEFAULT_Y = 100
    BIN_COUNT = 20
    DEFAULT_EFFECT_FREQUENCIES = {
        "Gear Shift Bite - Core": 72.0,
        "Gear Shift Bite - High Hz": 128.0,
        "Gear Shift Bite - Particles": 96.0,
        "Rev Limit": 120.0,
        "Tire Limit Load": 80.0,
        "Wheelspin Buzz": 92.0,
        "Rumble Kerbs": 62.0,
        "Road Bumps": 48.0,
        "Acceleration G Punch - Haptic": 78.0,
        "Impacts": 58.0,
        "Impact - Side": 58.0,
        "Impact - Smashable": 112.0,
    }

    def __init__(self, state: AppState):
        super().__init__(state, "Haptic Viz HUD")
        self._left_bins = [0.0] * self.BIN_COUNT
        self._right_bins = [0.0] * self.BIN_COUNT
        self._observed_min_hz: float | None = None
        self._observed_max_hz: float | None = None
        self._left_peak = 0.0
        self._right_peak = 0.0
        self._last_decay_at = monotonic()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, False)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        self._record_current_specs()
        self._decay_bins()
        self._draw_visualizer(painter)

    def _record_current_specs(self) -> None:
        for name in HAPTIC_DEBUG_EFFECT_NAMES:
            spec = self.state.haptic_debug.specs[name]
            level = max(0.0, min(1.0, float(spec.level) / 100.0))
            if level <= 0.004:
                continue
            left = max(0.0, min(1.0, float(spec.left))) * level
            right = max(0.0, min(1.0, float(spec.right))) * level
            if left <= 0.004 and right <= 0.004:
                left = level
                right = level
            self._record_sample(self._spec_frequency(name, spec.frequency), left, right)

    def _decay_bins(self) -> None:
        now = monotonic()
        dt = max(0.0, min(0.25, now - self._last_decay_at))
        self._last_decay_at = now
        if dt <= 0.0:
            return
        decay = max(0.0, 1.0 - dt * 4.8)
        self._left_bins = [value * decay if value > 0.004 else 0.0 for value in self._left_bins]
        self._right_bins = [value * decay if value > 0.004 else 0.0 for value in self._right_bins]

    def _record_sample(self, hz: float, left: float, right: float) -> None:
        hz = max(1.0, min(400.0, float(hz)))
        left = max(0.0, min(1.0, float(left)))
        right = max(0.0, min(1.0, float(right)))
        self._update_observed_range(hz, left, right)
        index = self._bin_index(hz)
        self._left_bins[index] = max(self._left_bins[index], left)
        self._right_bins[index] = max(self._right_bins[index], right)

    def _update_observed_range(self, hz: float, left: float, right: float) -> None:
        if self._observed_min_hz is None:
            self._observed_min_hz = hz
            self._observed_max_hz = hz
        else:
            self._observed_min_hz = min(self._observed_min_hz, hz)
            self._observed_max_hz = max(self._observed_max_hz or hz, hz)
        self._left_peak = max(self._left_peak, left)
        self._right_peak = max(self._right_peak, right)

    def _observed_hz_bounds(self) -> tuple[float, float]:
        low = self._observed_min_hz
        high = self._observed_max_hz
        if low is None or high is None:
            return 20.0, 180.0
        low = max(1.0, float(low))
        high = max(low, float(high))
        if high - low < 2.0:
            center = (low + high) * 0.5
            low = max(1.0, center - 1.0)
            high = center + 1.0
        return low, high

    def _bin_index(self, hz: float) -> int:
        low, high = self._observed_hz_bounds()
        hz = max(low, min(high, float(hz)))
        ratio = (hz - low) / max(1.0, high - low)
        return max(0, min(self.BIN_COUNT - 1, int(round(ratio * (self.BIN_COUNT - 1)))))

    def _draw_visualizer(self, painter: QPainter) -> None:
        width = float(self.WIDTH)
        height = float(self.HEIGHT)
        bg = "#151a20"
        line = "#252c35"
        center_line = "#3a4652"
        left_color = "#2f5e73"
        right_color = "#f1c40f"

        painter.fillRect(QRectF(0.0, 0.0, width, height), QColor(bg))
        painter.setPen(QColor(line))
        painter.setBrush(Qt.NoBrush)
        painter.drawRect(QRectF(0.0, 0.0, width - 1.0, height - 1.0))

        center_x = round(width * 0.5)
        left_zero_x = center_x - 4
        right_zero_x = center_x + 4
        painter.setPen(QColor(center_line))
        painter.drawLine(QPointF(center_x, 1.0), QPointF(center_x, height - 2.0))
        painter.setPen(QColor(line))
        painter.drawLine(QPointF(left_zero_x, 1.0), QPointF(left_zero_x, height - 2.0))
        painter.drawLine(QPointF(right_zero_x, 1.0), QPointF(right_zero_x, height - 2.0))

        label_y = height * 0.10
        painter.setFont(QFont("Segoe UI", max(6, int(height * 0.055)), QFont.Bold))
        painter.setPen(QColor(center_line))
        painter.drawText(QRectF(0.0, label_y - 7.0, left_zero_x, 14.0), Qt.AlignCenter, "L")
        painter.drawText(QRectF(right_zero_x, label_y - 7.0, width - right_zero_x, 14.0), Qt.AlignCenter, "R")

        pad_y = max(5, round(height * 0.04))
        usable_h = max(1, height - pad_y * 2)
        gap = max(1, round(height / 160.0))
        bar_h = max(2, int((usable_h - gap * (self.BIN_COUNT - 1)) / self.BIN_COUNT))
        max_left_w = max(1.0, left_zero_x - 3.0)
        max_right_w = max(1.0, (width - 4.0) - right_zero_x)
        center_index = (self.BIN_COUNT - 1) * 0.5

        painter.setPen(Qt.NoPen)
        for visual_index in range(self.BIN_COUNT):
            bin_index = self.BIN_COUNT - 1 - visual_index
            y = pad_y + visual_index * (bar_h + gap)
            y2 = min(height - pad_y, y + bar_h)
            left_level = max(0.0, min(1.0, self._left_bins[bin_index] / max(0.01, self._left_peak)))
            right_level = max(0.0, min(1.0, self._right_bins[bin_index] / max(0.01, self._right_peak)))
            vertical_bias = (center_index - visual_index) / max(1.0, center_index)
            if left_level > 0.01:
                painter.setBrush(QColor(self._hue_shift(left_color, 0.105 * vertical_bias)))
                lx0 = max(2.0, left_zero_x - max_left_w * left_level)
                left_width = (left_zero_x - 1.0) - lx0
                if left_width > 0.0:
                    painter.drawRect(QRectF(lx0, y, left_width, y2 - y))
            if right_level > 0.01:
                painter.setBrush(QColor(self._hue_shift(right_color, -0.080 * vertical_bias)))
                rx1 = min(width - 3.0, right_zero_x + max_right_w * right_level)
                right_start = right_zero_x + 1.0
                right_width = rx1 - right_start
                if right_width > 0.0:
                    painter.drawRect(QRectF(right_start, y, right_width, y2 - y))

    @classmethod
    def _spec_frequency(cls, name: str, frequency: float) -> float:
        frequency = max(0.0, float(frequency))
        if frequency > 0.0:
            return frequency
        return cls.DEFAULT_EFFECT_FREQUENCIES.get(name, 80.0)

    @staticmethod
    def _hue_shift(color: str, amount: float) -> str:
        try:
            r = int(color[1:3], 16) / 255.0
            g = int(color[3:5], 16) / 255.0
            b = int(color[5:7], 16) / 255.0
        except (TypeError, ValueError):
            return color
        h, s, v = colorsys.rgb_to_hsv(r, g, b)
        r2, g2, b2 = colorsys.hsv_to_rgb((h + amount) % 1.0, s, v)
        return f"#{int(round(r2 * 255)):02x}{int(round(g2 * 255)):02x}{int(round(b2 * 255)):02x}"


class TriggerHudOverlay(HudOverlayBase):
    HUD_NAME = "Trigger"
    WIDTH = 152
    HEIGHT = 184
    DEFAULT_X = 876
    DEFAULT_Y = 100

    def __init__(self, state: AppState):
        super().__init__(state, "Trigger HUD")
        self._last_frame_at = monotonic()
        self._l2_vibration_phase = 0.0
        self._r2_vibration_phase = 0.0
        self._l2_vibration_angles: deque[float] = deque(maxlen=4)
        self._r2_vibration_angles: deque[float] = deque(maxlen=4)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        gap = max(4.0, min(8.0, self.HEIGHT * 0.05))
        cell_height = max(1.0, (self.HEIGHT - gap) / 2.0)
        gauge_width = min(float(self.WIDTH), cell_height * 2.0)
        left = (self.WIDTH - gauge_width) / 2.0
        frame_now = monotonic()
        frame_dt = max(0.0, min(0.05, frame_now - self._last_frame_at))
        self._last_frame_at = frame_now

        l2_output = self._summary("L2", frame_now)
        r2_output = self._summary("R2", frame_now)
        self._draw_trigger_meter(
            painter,
            left,
            -2.0,
            left + gauge_width,
            cell_height - 2.0,
            self._input_ratio("L2"),
            l2_output,
            self._l2_vibration_angles,
            "_l2_vibration_phase",
            frame_dt,
            "L2",
            "#13C9B4",
            "#13C9B4",
            "#119C8E",
        )
        bottom_top = cell_height + gap
        self._draw_trigger_meter(
            painter,
            left,
            bottom_top - 14.0,
            left + gauge_width,
            bottom_top + cell_height - 14.0,
            self._input_ratio("R2"),
            r2_output,
            self._r2_vibration_angles,
            "_r2_vibration_phase",
            frame_dt,
            "R2",
            "#f1c40f",
            "#f1c40f",
            "#6f5d14",
        )

    def _input_ratio(self, side: str) -> float:
        telemetry = self.state.telemetry
        if not telemetry.last_parsed:
            return 0.0
        value = telemetry.last_brake if side == "L2" else telemetry.last_throttle
        return max(0.0, min(1.0, float(value or 0.0) / 255.0))

    def _summary(self, side: str, now: float) -> dict[str, float]:
        names = [
            name for name in TRIGGER_DEBUG_EFFECT_NAMES
            if (name.startswith("Brake ") if side == "L2" else not name.startswith("Brake "))
        ]
        force = 0.0
        wall_start = 0.0
        wall_end = 100.0
        wall_force = -1.0
        pulse_amp = 0.0
        pulse_rate = 0.0
        pulse_start = 0.0
        vibrate_amp = 0.0
        vibrate_freq = 0.0
        vibrate_start = 0.0
        updated_at = 0.0
        for name in names:
            spec = self.state.trigger_debug.specs[name]
            updated_at = max(updated_at, float(spec.updated_at))
            if now - float(spec.updated_at) >= 0.45:
                continue
            spec_force = max(0.0, min(255.0, float(spec.force)))
            force = max(force, spec_force)
            if spec_force > wall_force:
                wall_force = spec_force
                wall_start = max(0.0, min(100.0, float(spec.wall_start)))
                wall_end = max(0.0, min(100.0, float(spec.wall_end)))
            if float(spec.pulse_amp) > pulse_amp:
                pulse_amp = max(0.0, min(255.0, float(spec.pulse_amp)))
                pulse_rate = max(0.0, min(255.0, float(spec.pulse_rate)))
                pulse_start = max(0.0, min(100.0, float(spec.pulse_start)))
            if float(spec.vibrate_amp) > vibrate_amp:
                vibrate_amp = max(0.0, min(8.0, float(spec.vibrate_amp)))
                vibrate_freq = max(0.0, min(180.0, float(spec.vibrate_freq)))
                vibrate_start = max(0.0, min(100.0, float(spec.vibrate_start)))
        return {
            "force": force,
            "wall_start": min(wall_start, wall_end),
            "wall_end": max(wall_start, wall_end),
            "pulse_amp": pulse_amp,
            "pulse_rate": pulse_rate,
            "pulse_start": pulse_start,
            "vibrate_amp": vibrate_amp,
            "vibrate_freq": vibrate_freq,
            "vibrate_start": vibrate_start,
            "updated_at": updated_at,
        }

    def _draw_trigger_meter(
        self,
        painter: QPainter,
        x0: float,
        y0: float,
        x1: float,
        y1: float,
        trigger_ratio: float,
        output: dict[str, float],
        vibration_angles: deque[float],
        vibration_phase_attr: str,
        frame_dt: float,
        label: str,
        label_color: str,
        gauge_color: str,
        fan_color: str,
    ) -> None:
        start_angle = 210.0
        max_angle = 90.0
        sweep_degrees = 120.0
        needle_angle = start_angle - sweep_degrees * max(0.0, min(1.0, trigger_ratio))
        cell_width = max(1.0, x1 - x0)
        cell_height = max(1.0, y1 - y0)
        diameter = cell_width
        pad = max(1.0, min(cell_width, cell_height) * 0.035)
        center_x = (x0 + x1) / 2.0
        center_y = y0 + pad + 1.0
        radius = max(1.0, min(cell_width / 2.0 - pad, cell_height - center_y + y0 - pad))
        needle_outer = radius * 0.82
        needle_inner = radius * 0.18
        sector_inner = needle_inner
        needle_cap_radius = max(1.8, radius * 0.045)
        fan_outer = radius * 0.76
        background_outer = radius
        line_width = 1.0

        def angle_from_percent(percent: float) -> float:
            ratio = max(0.0, min(1.0, percent / 100.0))
            return start_angle - sweep_degrees * ratio

        def point_at(angle: float, distance: float) -> QPointF:
            radians = math.radians(angle)
            return QPointF(
                center_x + math.sin(radians) * distance,
                center_y - math.cos(radians) * distance,
            )

        def sector_polygon(angle_a: float, angle_b: float, distance: float, inner_distance: float = 0.0) -> QPolygonF:
            low = min(angle_a, angle_b)
            high = max(angle_a, angle_b)
            extent = high - low
            steps = max(3, int(extent / 6.0))
            points: list[QPointF] = []
            if inner_distance <= 0.0:
                points.append(QPointF(center_x, center_y))
            for index in range(steps + 1):
                points.append(point_at(low + extent * (index / steps), distance))
            if inner_distance > 0.0:
                for index in range(steps, -1, -1):
                    points.append(point_at(low + extent * (index / steps), inner_distance))
            return QPolygonF(points)

        background_steps = max(6, int((start_angle - max_angle) / 6.0))
        background_outer_points: list[QPointF] = []
        background_inner_points: list[QPointF] = []
        for index in range(background_steps + 1):
            angle = max_angle + (start_angle - max_angle) * (index / background_steps)
            background_outer_points.append(point_at(angle, background_outer))
            background_inner_points.append(point_at(angle, sector_inner))
        background_polygon = sector_polygon(max_angle, start_angle, background_outer, sector_inner)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#151a20"))
        painter.drawPolygon(background_polygon)

        painter.setPen(QPen(QColor("#252c35"), line_width))
        painter.setBrush(Qt.NoBrush)
        for previous, current in zip(background_outer_points, background_outer_points[1:]):
            painter.drawLine(previous, current)
        for previous, current in zip(background_inner_points, background_inner_points[1:]):
            painter.drawLine(previous, current)
        painter.drawLine(point_at(max_angle, sector_inner), point_at(max_angle, background_outer))
        painter.drawLine(point_at(start_angle, sector_inner), point_at(start_angle, background_outer))
        for angle in (start_angle, max_angle):
            painter.setPen(QPen(QColor("#d6dde5"), line_width))
            painter.drawLine(point_at(angle, radius * 0.78), point_at(angle, radius))

        label_point = point_at(240.0, radius * 0.70)
        painter.setPen(QColor(label_color))
        painter.setFont(QFont("Consolas", max(5, int(diameter * 0.091)), QFont.Bold))
        painter.drawText(QRectF(label_point.x() - 16.0, label_point.y() - 14.0, 32.0, 16.0), Qt.AlignCenter, label)

        residual = max(0.0, needle_angle - max_angle)
        if residual >= 2.0:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(fan_color))
            painter.drawPolygon(sector_polygon(max_angle, needle_angle, fan_outer, sector_inner))

        force = max(0.0, min(255.0, float(output.get("force", 0.0))))
        if force > 0.0:
            force_ratio = force / 255.0
            wall_start = max(0.0, min(100.0, float(output.get("wall_start", 0.0))))
            wall_end = max(wall_start, min(100.0, float(output.get("wall_end", 100.0))))
            wall_start_angle = angle_from_percent(wall_start)
            wall_end_angle = angle_from_percent(wall_end)
            if abs(wall_start_angle - wall_end_angle) >= 1.0:
                wall_outer = needle_outer + (background_outer * 1.08 - needle_outer) * force_ratio
                wall_inner = wall_outer * 0.40
                painter.setPen(Qt.NoPen)
                painter.setBrush(QColor("#8c0437"))
                painter.drawPolygon(sector_polygon(wall_start_angle, wall_end_angle, wall_outer, wall_inner))
                painter.setPen(QPen(QColor("#bd1051"), line_width))
                for angle in (wall_start_angle, wall_end_angle):
                    painter.drawLine(point_at(angle, wall_inner), point_at(angle, wall_outer))

        pulse_data = self._pulse_display_data(output)
        if pulse_data is not None:
            amp, freq, start_percent = pulse_data
            vibration_phase = float(getattr(self, vibration_phase_attr)) + frame_dt * (3.0 + freq * 0.55) * math.tau
            setattr(self, vibration_phase_attr, vibration_phase)
            amp_ratio = max(0.0, min(1.0, amp))
            vibration_start_angle = angle_from_percent(start_percent)
            if abs(vibration_start_angle - max_angle) < 2.0:
                vibration_start_angle = start_angle
            travel = 0.5 + 0.5 * math.sin(vibration_phase)
            vibration_center_angle = (max_angle + vibration_start_angle) * 0.5
            vibration_half_width = min(7.0, max(1.0, abs(vibration_start_angle - max_angle) * 0.12))
            vibration_angle = vibration_center_angle + (travel * 2.0 - 1.0) * vibration_half_width
            vibration_outer = needle_outer * 1.08 + (background_outer * 1.14 - needle_outer * 1.08) * amp_ratio
            vibration_inner = max(1.0, vibration_outer * 0.40)
            vibration_angles.append(vibration_angle)
            self._draw_trigger_motion_blur(
                painter,
                center_x,
                center_y,
                vibration_inner,
                vibration_outer,
                list(vibration_angles),
                ("#4b0638", "#8d0b69", "#d516a0"),
            )
            pen = QPen(QColor("#ff37c7"), 5.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(point_at(vibration_angle, vibration_inner), point_at(vibration_angle, vibration_outer))
        else:
            vibration_angles.clear()

        painter.setPen(QPen(QColor("#3a4652"), line_width))
        painter.drawLine(point_at(max_angle, sector_inner), point_at(max_angle, background_outer))
        needle_color = QColor(gauge_color)
        needle_pen = QPen(needle_color, 3.0)
        needle_pen.setCapStyle(Qt.RoundCap)
        painter.setPen(needle_pen)
        painter.drawLine(point_at(needle_angle, needle_inner), point_at(needle_angle, needle_outer))
        painter.setPen(Qt.NoPen)
        painter.setBrush(needle_color)
        painter.drawEllipse(point_at(needle_angle, needle_inner), needle_cap_radius, needle_cap_radius)

    @staticmethod
    def _pulse_display_data(output: dict[str, float]) -> tuple[float, float, float] | None:
        vibrate_amp = max(0.0, min(8.0, float(output.get("vibrate_amp", 0.0))))
        vibrate_freq = max(0.0, min(180.0, float(output.get("vibrate_freq", 0.0))))
        if vibrate_amp > 0.0 and vibrate_freq > 0.0:
            return vibrate_amp / 8.0, vibrate_freq, max(0.0, min(100.0, float(output.get("vibrate_start", 0.0))))
        pulse_amp = max(0.0, min(255.0, float(output.get("pulse_amp", 0.0))))
        pulse_rate = max(0.0, min(255.0, float(output.get("pulse_rate", 0.0))))
        if pulse_amp > 0.0 and pulse_rate > 0.0:
            return pulse_amp / 255.0, max(1.0, min(40.0, pulse_rate)), max(0.0, min(100.0, float(output.get("pulse_start", 0.0))))
        return None

    def _draw_trigger_motion_blur(
        self,
        painter: QPainter,
        center_x: float,
        center_y: float,
        inner: float,
        outer: float,
        angles: list[float],
        colors: tuple[str, str, str],
    ) -> None:
        if len(angles) < 2:
            return
        for index, current_angle in enumerate(angles[:-1]):
            next_angle = angles[index + 1]
            delta = next_angle - current_angle
            if abs(delta) > 180.0:
                current_angle = next_angle - math.copysign(42.0, delta)
                delta = next_angle - current_angle
            steps = max(2, min(10, int(abs(delta) / 4.0) + 2))
            color = colors[min(index, len(colors) - 1)]
            alpha = max(45, int(78 + index * 38))
            pen_color = QColor(color)
            pen_color.setAlpha(alpha)
            pen = QPen(pen_color, 2.0)
            pen.setCapStyle(Qt.RoundCap)
            painter.setPen(pen)
            for step in range(steps):
                angle_a = current_angle + delta * (step / steps)
                angle_b = current_angle + delta * ((step + 1) / steps)
                painter.drawLine(
                    self._trigger_point(center_x, center_y, inner, angle_a),
                    self._trigger_point(center_x, center_y, outer, angle_b),
                )

    @staticmethod
    def _trigger_point(center_x: float, center_y: float, distance: float, angle: float) -> QPointF:
        radians = math.radians(angle)
        return QPointF(
            center_x + math.sin(radians) * distance,
            center_y - math.cos(radians) * distance,
        )


class DriftHudOverlay(HudOverlayBase):
    HUD_NAME = "Drift"
    WIDTH = 200
    HEIGHT = 160
    DEFAULT_X = 312
    DEFAULT_Y = 308

    def __init__(self, state: AppState):
        super().__init__(state, "Drift HUD")
        self._tire_angle = 0.0
        self._tire_last_update = monotonic()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        rect = QRect(1, 1, self.WIDTH - 2, self.HEIGHT - 2)
        painter.setPen(QColor(COLORS["line"]))
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawRoundedRect(rect, 6, 6)

        state = self.state.telemetry.drift_hud
        title_color = COLORS["accent"] if state.fade_active else (COLORS["accent_2"] if state.active else "#aeb8c4")
        title = "FADE" if state.fade_active else ("DRIFT" if state.active else "MONITOR")

        painter.setPen(QColor(title_color))
        painter.setFont(QFont("Segoe UI", 12, QFont.Bold))
        painter.drawText(10, 24, title)
        painter.setFont(QFont("Consolas", 13, QFont.Bold))
        painter.drawText(QRectF(self.WIDTH - 58, 8, 48, 18), Qt.AlignRight | Qt.AlignVCenter, f"{state.score:.2f}")

        label_x = 10
        score_y = 38
        self._draw_drift_bar(painter, label_x, score_y, min(self.WIDTH - 10, 186), "score", state.score, state.fade_active)

        y = score_y + 19
        for label, key in (
            ("over", "over"),
            ("angle", "angle"),
            ("drive", "drive"),
            ("wheel", "wheel"),
            ("grip", "grip"),
        ):
            self._draw_drift_bar(painter, label_x, y, min(self.WIDTH - 78, 121), label, state.components.get(key, 0.0), False)
            y += 17

        self._draw_drift_tire(painter, state.active, state.fade_active)
        self._draw_status(painter, state.active, state.fade_active)

    def _draw_drift_bar(self, painter: QPainter, x0: int, y: int, x1: int, label: str, value: float, hot: bool) -> None:
        value = max(0.0, min(1.0, float(value)))
        label_w = 46
        bar_x0 = x0 + label_w
        bar_x1 = max(bar_x0 + 1, x1)
        bar_h = 7
        fill = COLORS["accent"] if hot else COLORS["accent_2"]
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(x0, y + 8, label)

        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#252c35"))
        painter.drawRect(bar_x0, y, bar_x1 - bar_x0, bar_h)
        if value > 0.0:
            painter.setBrush(QColor(fill))
            painter.drawRect(bar_x0, y, round((bar_x1 - bar_x0) * value), bar_h)

    def _draw_status(self, painter: QPainter, active: bool, fade_active: bool) -> None:
        if fade_active:
            status = "DRIFT RUMBLE FADE"
            status_color = COLORS["accent"]
        elif active:
            status = "RUMBLE FADE ARMED"
            status_color = COLORS["accent_2"]
        else:
            status = "RUMBLE FADE READY"
            status_color = COLORS["muted"]
        painter.setPen(QColor(status_color))
        painter.setFont(QFont("Segoe UI", 8, QFont.Bold))
        painter.drawText(10, self.HEIGHT - 8, status)

    def _draw_drift_tire(self, painter: QPainter, drift_active: bool, fade_active: bool) -> None:
        now = monotonic()
        dt = max(0.0, min(0.12, now - self._tire_last_update))
        self._tire_last_update = now
        telemetry = self.state.telemetry
        speed_kmh = max(0.0, float(telemetry.last_speed or 0.0))
        speed_factor = min(1.0, speed_kmh / 120.0)
        spin_speed = 45.0 + speed_factor * 220.0
        if drift_active:
            spin_speed *= 1.65
        if fade_active:
            spin_speed *= 2.45
        if not bool(telemetry.last_is_race_on) or speed_kmh < 1.0:
            spin_speed = 18.0 if drift_active or fade_active else 0.0
        self._tire_angle = (self._tire_angle + spin_speed * dt) % 360.0

        diameter = min(64.0, max(44.0, self.HEIGHT - 86.0))
        radius = diameter / 2.0
        center_x = min(self.WIDTH - radius - 8.0, max(136.0, self.WIDTH - radius - 8.0))
        center_y = min(self.HEIGHT - radius - 24.0, max(92.0, self.HEIGHT - radius - 24.0))
        inner_radius = radius * 0.47
        tire_outline = COLORS["accent"] if fade_active else ("#caa31b" if drift_active else "#6f777c")
        arc_color = COLORS["accent"] if fade_active else (COLORS["accent_2"] if drift_active else "#e6ebee")

        painter.setPen(QPen(QColor(tire_outline), 1.0))
        painter.setBrush(QColor("#5d6368"))
        painter.drawEllipse(QPointF(center_x, center_y), radius, radius)

        painter.setPen(QPen(QColor("#4a5054"), 4.0))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(QPointF(center_x, center_y), radius * 0.72, radius * 0.72)

        painter.save()
        painter.translate(center_x, center_y)
        painter.rotate(self._tire_angle)
        arc_width = max(5.0, radius * 0.20)
        painter.setPen(QPen(QColor(arc_color), arc_width, Qt.SolidLine, Qt.RoundCap))
        arc_rect = QRectF(-radius + arc_width, -radius + arc_width, (radius - arc_width) * 2.0, (radius - arc_width) * 2.0)
        for offset in (32.0, 212.0):
            painter.drawArc(arc_rect, int(offset * 16), int(58.0 * 16))
        painter.restore()

        painter.setPen(QPen(QColor("#343a3f"), 2.0))
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawEllipse(QPointF(center_x, center_y), inner_radius, inner_radius)


class TriggerDebugHudOverlay(HudOverlayBase):
    """First-pass independent Debug Trigger HUD renderer.

    This window intentionally reads from AppState instead of owning trigger
    logic. The final overlay system can replace the renderer while keeping the
    same state boundary.
    """

    HUD_NAME = "Debug Trigger"
    WIDTH = 280
    HEIGHT = 238
    DEFAULT_X = 816
    DEFAULT_Y = 308

    def __init__(self, state: AppState):
        super().__init__(state, "Debug Trigger HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        rect = QRect(1, 1, self.WIDTH - 2, self.HEIGHT - 2)
        painter.setPen(QColor(COLORS["line"]))
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawRoundedRect(rect, 7, 7)

        painter.setPen(QColor(COLORS["accent_2"]))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(12, 22, "DEBUG TRIGGER")

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(162, 22, "output / wall / pulse")

        y = 42
        y = self._draw_group(painter, "L2", y)
        for name in TRIGGER_DEBUG_EFFECT_NAMES:
            if name.startswith("Brake "):
                y = self._draw_row(painter, name, y)

        y += 4
        y = self._draw_group(painter, "R2", y)
        for name in TRIGGER_DEBUG_EFFECT_NAMES:
            if not name.startswith("Brake "):
                y = self._draw_row(painter, name, y)

    def _draw_group(self, painter: QPainter, text: str, y: int) -> int:
        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(12, y, text)
        painter.setPen(QColor(COLORS["line"]))
        painter.drawLine(34, y - 4, self.WIDTH - 12, y - 4)
        return y + 11

    def _draw_row(self, painter: QPainter, name: str, y: int) -> int:
        spec = self.state.trigger_debug.specs[name]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#0a1118"))
        painter.drawRoundedRect(10, y - 8, self.WIDTH - 20, 19, 3, 3)

        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(15, y + 5, _short_trigger_name(name))

        track_x = 112
        track_y = y - 3
        track_w = 102
        self._draw_meter(painter, track_x, track_y, track_w, spec)

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Consolas", 7, QFont.Bold))
        force_percent = _trigger_force_percent(spec)
        pulse_percent = _trigger_pulse_percent(spec)
        pulse_tag = _trigger_pulse_tag(spec)
        painter.drawText(222, y + 5, f"{force_percent:02.0f}% {pulse_tag}{pulse_percent:02.0f}")
        return y + 22

    def _draw_meter(self, painter: QPainter, x: int, y: int, width: int, spec) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#071018"))
        painter.drawRoundedRect(x - 1, y - 2, width + 2, 15, 2, 2)
        painter.setBrush(QColor("#263240"))
        painter.drawRect(x, y, width, 3)
        painter.drawRect(x, y + 5, width, 3)
        painter.drawRect(x, y + 10, width, 3)

        force_percent = _trigger_force_percent(spec)
        if force_percent > 0.0:
            painter.setBrush(QColor(COLORS["accent_2"]))
            painter.drawRect(x, y, _percent_width(width, force_percent), 3)

        wall_start_percent = max(0.0, min(100.0, min(spec.wall_start, spec.wall_end)))
        wall_end_percent = max(0.0, min(100.0, max(spec.wall_start, spec.wall_end)))
        wall_start = x + _percent_width(width, wall_start_percent)
        wall_end = x + _percent_width(width, wall_end_percent)
        if force_percent > 0.0 and wall_end > wall_start:
            painter.setBrush(QColor(COLORS["accent"]))
            painter.drawRect(wall_start, y + 5, max(1, wall_end - wall_start), 3)

        pulse_percent = _trigger_pulse_percent(spec)
        if pulse_percent > 0.0:
            painter.setBrush(QColor("#1d5260"))
            painter.drawRect(x, y + 10, _percent_width(width, pulse_percent), 3)
            pulse_start = _trigger_pulse_start(spec)
            pulse_x = x + _percent_width(width, pulse_start)
            rate = _trigger_pulse_rate(spec)
            jitter = int(round(math.sin(monotonic() * (3.0 + rate * 0.12)) * min(3.0, 1.0 + pulse_percent / 35.0)))
            painter.setBrush(QColor(COLORS["cyan"]))
            painter.drawRect(pulse_x - 1 + jitter, y - 1, 3, 15)


class HapticDebugHudOverlay(HudOverlayBase):
    HUD_NAME = "Debug Haptic"
    WIDTH = 280
    HEIGHT = 318
    DEFAULT_X = 524
    DEFAULT_Y = 308

    def __init__(self, state: AppState):
        super().__init__(state, "Debug Haptic HUD")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        scale = self.width() / self.WIDTH
        painter.scale(scale, scale)
        rect = QRect(1, 1, self.WIDTH - 2, self.HEIGHT - 2)
        painter.setPen(QColor(COLORS["line"]))
        painter.setBrush(QColor(COLORS["surface"]))
        painter.drawRoundedRect(rect, 7, 7)

        painter.setPen(QColor(COLORS["accent_2"]))
        painter.setFont(QFont("Segoe UI", 10, QFont.Bold))
        painter.drawText(12, 22, "DEBUG HAPTIC")

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Segoe UI", 7, QFont.Bold))
        painter.drawText(166, 22, "level over Hz band")

        y = 43
        for name in HAPTIC_DEBUG_EFFECT_NAMES:
            y = self._draw_row(painter, name, y)

    def _draw_row(self, painter: QPainter, name: str, y: int) -> int:
        spec = self.state.haptic_debug.specs[name]
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#0a1118"))
        painter.drawRoundedRect(10, y - 8, self.WIDTH - 20, 27, 3, 3)

        label = _short_haptic_name(name)
        track_x = 112
        track_w = 144
        self._draw_channel_row(
            painter,
            f"{label} L",
            y,
            track_x,
            track_w,
            spec.left * 100.0,
            spec.frequency,
        )
        self._draw_channel_row(
            painter,
            f"{label} R",
            y + 12,
            track_x,
            track_w,
            spec.right * 100.0,
            spec.frequency,
        )
        return y + 31

    def _draw_channel_row(
        self,
        painter: QPainter,
        label: str,
        y: int,
        track_x: int,
        track_w: int,
        level: float,
        frequency: float,
    ) -> None:
        painter.setPen(QColor(COLORS["text"]))
        painter.setFont(QFont("Segoe UI", 6, QFont.Bold))
        painter.drawText(15, y + 3, label)
        self._draw_channel_meter(painter, track_x, y - 3, track_w, level, frequency)

        painter.setPen(QColor(COLORS["muted"]))
        painter.setFont(QFont("Consolas", 6, QFont.Bold))
        painter.drawText(track_x + track_w + 5, y + 3, f"{level:03.0f}")

    def _draw_channel_meter(
        self,
        painter: QPainter,
        x: int,
        y: int,
        width: int,
        level: float,
        frequency: float,
    ) -> None:
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#263240"))
        painter.drawRoundedRect(x, y, width, 7, 3, 3)

        if level > 0.0 and frequency > 0.0:
            freq_x = x + _frequency_position(width, frequency)
            painter.setBrush(QColor(COLORS["accent"]))
            painter.drawRect(freq_x - 7, y - 1, 14, 9)

        painter.setBrush(QColor(COLORS["accent_2"]))
        painter.drawRoundedRect(x, y + 2, _percent_width(width, level), 3, 1, 1)


def _percent_width(width: int, value: float) -> int:
    clamped = max(0.0, min(100.0, float(value)))
    return round(width * clamped / 100.0)


def _trigger_force_percent(spec) -> float:
    return max(0.0, min(100.0, float(spec.force) * 100.0 / 255.0))


def _trigger_soft_pulse_percent(spec) -> float:
    return max(0.0, min(100.0, float(spec.vibrate_amp) * 100.0 / 8.0))


def _trigger_strong_pulse_percent(spec) -> float:
    return max(0.0, min(100.0, float(spec.pulse_amp) * 100.0 / 255.0))


def _trigger_uses_soft_pulse(spec) -> bool:
    soft_percent = _trigger_soft_pulse_percent(spec)
    strong_percent = _trigger_strong_pulse_percent(spec)
    return soft_percent > 0.0 and soft_percent >= strong_percent


def _trigger_pulse_percent(spec) -> float:
    return max(_trigger_soft_pulse_percent(spec), _trigger_strong_pulse_percent(spec))


def _trigger_pulse_start(spec) -> float:
    return float(spec.vibrate_start if _trigger_uses_soft_pulse(spec) else spec.pulse_start)


def _trigger_pulse_rate(spec) -> float:
    return max(0.0, float(spec.vibrate_freq if _trigger_uses_soft_pulse(spec) else spec.pulse_rate))


def _trigger_pulse_tag(spec) -> str:
    if _trigger_uses_soft_pulse(spec):
        return "S"
    if _trigger_strong_pulse_percent(spec) > 0.0:
        return "H"
    return "-"


def _frequency_position(width: int, frequency: float) -> int:
    clamped = max(0.0, min(160.0, float(frequency)))
    return round(width * clamped / 160.0)


def _polygon(points: tuple[float, ...]) -> QPolygonF:
    return QPolygonF([
        QPointF(points[index], points[index + 1])
        for index in range(0, len(points), 2)
    ])


def _smoothstep(edge0: float, edge1: float, value: float) -> float:
    if edge0 >= edge1:
        return 1.0 if value >= edge1 else 0.0
    t = max(0.0, min(1.0, (value - edge0) / (edge1 - edge0)))
    return t * t * (3.0 - 2.0 * t)


def _mix_hex_color(start: str, end: str, amount: float) -> str:
    amount = max(0.0, min(1.0, amount))
    sr, sg, sb = int(start[1:3], 16), int(start[3:5], 16), int(start[5:7], 16)
    er, eg, eb = int(end[1:3], 16), int(end[3:5], 16), int(end[5:7], 16)
    r = int(sr + (er - sr) * amount)
    g = int(sg + (eg - sg) * amount)
    b = int(sb + (eb - sb) * amount)
    return f"#{r:02x}{g:02x}{b:02x}"


def _short_trigger_name(name: str) -> str:
    names = {
        "Brake Pressure": "Brake Pressure",
        "Brake Resistance": "Brake Resist",
        "Brake Resistance - Predictive": "Brake Predict",
        "Throttle Pressure": "Throttle Press",
        "Throttle Resistance - Traction": "Traction",
        "Acceleration G Punch": "Accel G Punch",
        "RPM Rev Limit": "RPM Limit",
        "Shift Down Howl": "Down Howl",
    }
    return names.get(name, name)


def _short_haptic_name(name: str) -> str:
    names = {
        "Gear Shift Bite - Core": "Shift Core",
        "Gear Shift Bite - High Hz": "Shift High Hz",
        "Gear Shift Bite - Particles": "Shift Particles",
        "Rumble Kerbs": "Kerbs",
        "Tire Limit Load": "Tire Limit",
        "Wheelspin Buzz": "Wheelspin",
        "Acceleration G Punch - Haptic": "Accel G",
        "Rev Limit": "Rev Limit",
        "Road Bumps": "Road Bumps",
        "Impacts": "Impacts",
        "Impact - Side": "Impact Side",
    }
    return names.get(name, name)
