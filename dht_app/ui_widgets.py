from pathlib import Path

from PySide6.QtCore import QEvent, QObject, QPoint, QRectF, QSize, QTimer, Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QScrollBar,
    QSlider,
    QToolTip,
    QVBoxLayout,
    QWidget,
)
try:
    from PySide6.QtSvg import QSvgRenderer
except ImportError:  # pragma: no cover - QtSvg is expected in the packaged app.
    QSvgRenderer = None

from .ui_theme import COLORS, CONTROL_WIDTH, ROW_GAP, SLIDER_WIDTH, VALUE_WIDTH


_ICON_CACHE: dict[tuple[str, str, int], QIcon] = {}
_SVG_PIXMAP_CACHE: dict[tuple[str, int, int], QPixmap] = {}
ICON_RENDER_SCALE = 4


def _svg_pixmap(path: Path, width: int, height: int) -> QPixmap:
    cache_key = (str(path), width, height)
    cached = _SVG_PIXMAP_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if not path.exists() or QSvgRenderer is None:
        return QPixmap()

    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QPixmap()

    render_width = max(1, width * ICON_RENDER_SCALE)
    render_height = max(1, height * ICON_RENDER_SCALE)
    pixmap = QPixmap(render_width, render_height)
    pixmap.fill(Qt.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter, QRectF(0, 0, render_width, render_height))
    painter.end()
    pixmap.setDevicePixelRatio(ICON_RENDER_SCALE)
    _SVG_PIXMAP_CACHE[cache_key] = pixmap
    return pixmap


def _tinted_svg_icon(path: Path, color: str, size: int) -> QIcon:
    cache_key = (str(path), color, size)
    cached = _ICON_CACHE.get(cache_key)
    if cached is not None:
        return cached
    if not path.exists() or QSvgRenderer is None:
        return QIcon(str(path)) if path.exists() else QIcon()

    renderer = QSvgRenderer(str(path))
    if not renderer.isValid():
        return QIcon(str(path))

    render_size = size * ICON_RENDER_SCALE
    base = QPixmap(render_size, render_size)
    base.fill(Qt.transparent)
    painter = QPainter(base)
    painter.setRenderHint(QPainter.Antialiasing)
    renderer.render(painter)
    painter.end()

    tinted = QPixmap(render_size, render_size)
    tinted.fill(Qt.transparent)
    painter = QPainter(tinted)
    painter.setRenderHint(QPainter.Antialiasing)
    painter.drawPixmap(0, 0, base)
    painter.setCompositionMode(QPainter.CompositionMode_SourceIn)
    painter.fillRect(tinted.rect(), QColor(color))
    painter.end()
    tinted.setDevicePixelRatio(ICON_RENDER_SCALE)

    icon = QIcon(tinted)
    _ICON_CACHE[cache_key] = icon
    return icon

class AccentLine(QFrame):
    def __init__(self, color: str = COLORS["accent"], width: int = 4):
        super().__init__()
        self.setFixedWidth(width)
        self.setStyleSheet(f"background: {color}; border-radius: {width // 2}px;")


class ToggleButton(QPushButton):
    def __init__(self, on: bool = True):
        super().__init__()
        self.setCheckable(True)
        self.setChecked(on)
        self.setCursor(Qt.PointingHandCursor)
        self.clicked.connect(self._sync_visual)
        self._sync_visual(on)

    def _sync_visual(self, checked: bool) -> None:
        self.setText("ON" if checked else "OFF")
        self.setObjectName("ToggleOn" if checked else "ToggleOff")
        self.style().unpolish(self)
        self.style().polish(self)


class NavButton(QPushButton):
    ICON_SIZE = 18

    def __init__(
        self,
        text: str,
        active: bool = False,
        tooltip_text: str = "",
        icon_path: str | Path | None = None,
    ):
        super().__init__(text)
        self._icon_path = Path(icon_path) if icon_path is not None else None
        self.setObjectName("NavButton")
        self.setCursor(Qt.PointingHandCursor)
        self.setMinimumHeight(25)
        self.setIconSize(QSize(self.ICON_SIZE, self.ICON_SIZE))
        if tooltip_text:
            self.setToolTip(tooltip_text)
        self.set_active(active)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.refresh_icon()
        self.style().unpolish(self)
        self.style().polish(self)

    def refresh_icon(self) -> None:
        if self._icon_path is None:
            return
        color = COLORS["accent"] if self.property("active") == "true" else COLORS["muted"]
        self.setIcon(_tinted_svg_icon(self._icon_path, color, self.ICON_SIZE))


class HudRow(QWidget):
    def __init__(
        self,
        name: str,
        scale: str = "100%",
        enabled: bool = True,
        on_toggle=None,
        on_scale_down=None,
        on_scale_up=None,
        opacity: str | None = None,
        on_opacity_down=None,
        on_opacity_up=None,
        tooltip_text: str = "",
        control_tooltips: dict[str, str] | None = None,
    ):
        super().__init__()
        control_tooltips = control_tooltips or {}
        if tooltip_text:
            self.setToolTip(tooltip_text)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"color: {COLORS['text']}; font-size: 8px; font-weight: 900;")
        if tooltip_text:
            name_label.setToolTip(tooltip_text)
        toggle = ToggleButton(enabled)
        toggle.setFixedWidth(24)
        if tooltip_text:
            toggle.setToolTip(f"{tooltip_text}\n{control_tooltips.get('toggle', 'Toggle this HUD on or off.')}")
        if on_toggle is not None:
            toggle.clicked.connect(on_toggle)
        scale_label = QLabel(scale)
        scale_label.setObjectName("ValueBadge")
        scale_label.setAlignment(Qt.AlignCenter)
        scale_label.setFixedWidth(30)
        if tooltip_text:
            scale_label.setToolTip(f"{tooltip_text}\n{control_tooltips.get('scale', 'Current HUD scale.')}")
        minus = QPushButton("-")
        minus.setObjectName("HudStepButton")
        minus.setFixedWidth(18)
        minus.setToolTip(control_tooltips.get("scale_down", "Decrease this HUD scale."))
        if on_scale_down is not None:
            minus.clicked.connect(on_scale_down)
        plus = QPushButton("+")
        plus.setObjectName("HudStepButton")
        plus.setFixedWidth(18)
        plus.setToolTip(control_tooltips.get("scale_up", "Increase this HUD scale."))
        if on_scale_up is not None:
            plus.clicked.connect(on_scale_up)

        layout.addWidget(name_label, 1)
        layout.addSpacing(10)
        layout.addWidget(toggle)
        layout.addSpacing(8)
        layout.addWidget(scale_label)
        layout.addSpacing(2)
        layout.addWidget(minus)
        layout.addSpacing(2)
        layout.addWidget(plus)
        if opacity is not None:
            opacity_label = QLabel("Opacity")
            opacity_label.setStyleSheet(f"color: {COLORS['muted']}; font-size: 7px; font-weight: 900;")
            if tooltip_text:
                opacity_label.setToolTip(f"{tooltip_text}\n{control_tooltips.get('opacity', 'Opacity controls how transparent the HUD appears.')}")
            opacity_value = QLabel(opacity)
            opacity_value.setObjectName("ValueBadge")
            opacity_value.setAlignment(Qt.AlignCenter)
            opacity_value.setFixedWidth(34)
            if tooltip_text:
                opacity_value.setToolTip(f"{tooltip_text}\n{control_tooltips.get('opacity_value', 'Current HUD opacity.')}")
            opacity_minus = QPushButton("-")
            opacity_minus.setObjectName("HudStepButton")
            opacity_minus.setFixedWidth(18)
            opacity_minus.setToolTip(control_tooltips.get("opacity_down", "Decrease this HUD opacity."))
            if on_opacity_down is not None:
                opacity_minus.clicked.connect(on_opacity_down)
            opacity_plus = QPushButton("+")
            opacity_plus.setObjectName("HudStepButton")
            opacity_plus.setFixedWidth(18)
            opacity_plus.setToolTip(control_tooltips.get("opacity_up", "Increase this HUD opacity."))
            if on_opacity_up is not None:
                opacity_plus.clicked.connect(on_opacity_up)
            layout.addSpacing(12)
            layout.addWidget(opacity_label)
            layout.addSpacing(2)
            layout.addWidget(opacity_value)
            layout.addSpacing(2)
            layout.addWidget(opacity_minus)
            layout.addSpacing(2)
            layout.addWidget(opacity_plus)


class FixedThumbScrollBar(QScrollBar):
    THUMB_HEIGHT = 44
    WHEEL_STEP = 14

    def __init__(self):
        super().__init__(Qt.Vertical)
        self.setFixedWidth(5)
        self.setSingleStep(self.WHEEL_STEP)
        self.setPageStep(24)
        self._drag_offset = 0
        self._dragging = False

    def _thumb_rect(self):
        track_height = self.height()
        thumb_height = min(self.THUMB_HEIGHT, max(12, track_height))
        travel = max(1, track_height - thumb_height)
        value_range = max(1, self.maximum() - self.minimum())
        top = round((self.value() - self.minimum()) / value_range * travel)
        return self.rect().adjusted(0, top, 0, -(track_height - top - thumb_height))

    def _set_value_from_y(self, y: int):
        thumb_height = min(self.THUMB_HEIGHT, max(12, self.height()))
        travel = max(1, self.height() - thumb_height)
        clamped = max(0, min(y, travel))
        value_range = self.maximum() - self.minimum()
        self.setValue(self.minimum() + round(clamped / travel * value_range))

    def paintEvent(self, event):
        if self.maximum() <= self.minimum():
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor(COLORS["accent"]))
        painter.drawRoundedRect(self._thumb_rect(), 3, 3)

    def mousePressEvent(self, event):
        if event.button() != Qt.LeftButton:
            return super().mousePressEvent(event)
        thumb = self._thumb_rect()
        if thumb.contains(event.position().toPoint()):
            self._dragging = True
            self._drag_offset = event.position().toPoint().y() - thumb.top()
        else:
            self._dragging = True
            self._drag_offset = self.THUMB_HEIGHT // 2
            self._set_value_from_y(event.position().toPoint().y() - self._drag_offset)
        self.update()

    def mouseMoveEvent(self, event):
        if not self._dragging:
            return super().mouseMoveEvent(event)
        self._set_value_from_y(event.position().toPoint().y() - self._drag_offset)
        self.update()

    def mouseReleaseEvent(self, event):
        self._dragging = False
        self.update()
        return super().mouseReleaseEvent(event)


class CompactScrollArea(QScrollArea):
    def __init__(self):
        super().__init__()
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVerticalScrollBar(FixedThumbScrollBar())
        self._schedule_scrollbar_tuning()

    def setWidget(self, widget):
        super().setWidget(widget)
        self._schedule_scrollbar_tuning()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._schedule_scrollbar_tuning()

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
        if delta == 0:
            return super().wheelEvent(event)
        steps = delta / 120
        bar = self.verticalScrollBar()
        bar.setValue(round(bar.value() - steps * FixedThumbScrollBar.WHEEL_STEP))
        event.accept()

    def _schedule_scrollbar_tuning(self):
        QTimer.singleShot(0, self._tune_scrollbar)

    def _tune_scrollbar(self):
        try:
            bar = self.verticalScrollBar()
        except RuntimeError:
            return
        if bar is None:
            return
        bar.setSingleStep(FixedThumbScrollBar.WHEEL_STEP)
        bar.setPageStep(24)


class NoWheelSlider(QSlider):
    def wheelEvent(self, event):
        event.ignore()


class StableToolTipFilter(QObject):
    def __init__(self, owner: QWidget, text: str):
        super().__init__(owner)
        self.owner = owner
        self.text = text

    def eventFilter(self, watched, event):
        if event.type() == QEvent.ToolTip:
            if self.text:
                global_pos = event.globalPos()
                QToolTip.showText(global_pos + QPoint(18, 20), self.text, self.owner)
            else:
                QToolTip.hideText()
            return True
        return False


def _install_stable_tooltip(owner: QWidget, tooltip_text: str, *widgets: QWidget) -> None:
    if not tooltip_text:
        return
    tooltip_filter = StableToolTipFilter(owner, tooltip_text)
    owner._stable_tooltip_filter = tooltip_filter
    for widget in (owner, *widgets):
        widget.setToolTip("")
        widget.installEventFilter(tooltip_filter)


def _inline_description(text: str) -> QLabel:
    description = QLabel(text)
    description.setObjectName("InlineDescription")
    description.setStyleSheet("font-size: 8px; color: #8f9ba7;")
    description.setWordWrap(True)
    description.setAttribute(Qt.WA_TransparentForMouseEvents, True)
    return description


class SliderRow(QWidget):
    def __init__(
        self,
        name: str,
        value: int,
        enabled: bool = True,
        on_toggle=None,
        on_value_changed=None,
        tooltip_text: str = "",
        on_edit_finished=None,
        description_text: str = "",
    ):
        super().__init__()
        self.effect_name = name
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(2)

        title = QLabel(name)
        title.setStyleSheet("font-size: 8px; font-weight: 800; color: #edf4fb;")
        title.setWordWrap(True)
        slider = NoWheelSlider(Qt.Horizontal)
        slider.setRange(0, 10)
        slider.setValue(value)
        slider.setEnabled(enabled)
        slider.setFixedWidth(SLIDER_WIDTH)
        if on_value_changed is not None:
            slider.valueChanged.connect(on_value_changed)
        if on_edit_finished is not None:
            slider.sliderReleased.connect(on_edit_finished)
        badge = QLabel(str(value))
        badge.setObjectName("ValueBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(VALUE_WIDTH)
        slider.valueChanged.connect(lambda new_value: badge.setText(str(new_value)))
        self.slider = slider
        self.value_badge = badge
        toggle = ToggleButton(enabled)
        toggle.setFixedWidth(CONTROL_WIDTH)
        if on_toggle is not None:
            toggle.clicked.connect(on_toggle)
        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(0)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(slider)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(badge)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(toggle)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addStretch(1)

        layout.addWidget(title, 0, 0, 1, 3)
        control_row_index = 1
        if description_text:
            layout.addWidget(_inline_description(description_text), 1, 0, 1, 3)
            control_row_index = 2
        layout.addWidget(control_row, control_row_index, 0, 1, 3)
        layout.setColumnStretch(0, 1)
        _install_stable_tooltip(self, tooltip_text, title, slider, badge, toggle, control_row)


class TriggerToggleRow(QWidget):
    def __init__(
        self,
        name: str,
        enabled: bool = True,
        on_toggle=None,
        description: str = "",
        on_select=None,
    ):
        super().__init__()
        self.effect_name = name
        self.on_select = on_select
        if on_select is not None:
            self.setCursor(Qt.PointingHandCursor)

        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(ROW_GAP)
        layout.setVerticalSpacing(3)

        title = QLabel(name)
        title.setStyleSheet("font-size: 9px; font-weight: 800; color: #edf4fb;")
        title.setWordWrap(True)
        title.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        toggle = ToggleButton(enabled)
        toggle.setFixedWidth(CONTROL_WIDTH)
        if on_toggle is not None:
            toggle.clicked.connect(on_toggle)
        self.toggle = toggle

        summary = QLabel(description)
        summary.setObjectName("TriggerDescription")
        summary.setStyleSheet("font-size: 8px; color: #8f9ba7;")
        summary.setWordWrap(True)
        summary.setAttribute(Qt.WA_TransparentForMouseEvents, True)

        layout.addWidget(title, 0, 0)
        layout.addWidget(toggle, 0, 1, alignment=Qt.AlignTop)
        layout.addWidget(summary, 1, 0, 1, 2)
        layout.setColumnStretch(0, 1)

    def mousePressEvent(self, event):
        if self.on_select is not None and event.button() == Qt.LeftButton:
            self.on_select()
        super().mousePressEvent(event)


class AdvancedRow(QWidget):
    def __init__(
        self,
        name: str,
        value: int,
        hint: str = "",
        on_value_changed=None,
        minimum: int = 0,
        maximum: int = 10,
        value_formatter=None,
        tooltip_text: str = "",
        description_text: str = "",
    ):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(2)

        title = QLabel(name)
        title.setStyleSheet("font-size: 8px; font-weight: 800;")
        title.setWordWrap(True)
        slider = NoWheelSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        clamped_value = max(minimum, min(maximum, int(value)))
        slider.setValue(clamped_value)
        slider.setFixedWidth(SLIDER_WIDTH)
        if on_value_changed is not None:
            slider.valueChanged.connect(on_value_changed)
        formatter = value_formatter if value_formatter is not None else str
        badge = QLabel(formatter(clamped_value))
        uses_detail_badge = value_formatter is not None or maximum > 10 or minimum < 0
        badge.setObjectName("DetailValueBadge" if uses_detail_badge else "ValueBadge")
        badge.setAlignment(Qt.AlignCenter)
        badge.setFixedWidth(34 if uses_detail_badge else VALUE_WIDTH)
        slider.valueChanged.connect(lambda new_value: badge.setText(formatter(new_value)))
        reserve = QLabel("")
        reserve.setFixedWidth(CONTROL_WIDTH)
        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(0)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(slider)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(badge)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(reserve)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addStretch(1)

        layout.addWidget(title, 0, 0, 1, 3)
        control_row_index = 1
        if description_text:
            layout.addWidget(_inline_description(description_text), 1, 0, 1, 3)
            control_row_index = 2
        layout.addWidget(control_row, control_row_index, 0, 1, 3)
        layout.setColumnStretch(0, 1)
        _install_stable_tooltip(self, tooltip_text, title, slider, badge, reserve, control_row)


class ChoiceRow(QWidget):
    def __init__(
        self,
        name: str,
        value: str,
        options: tuple[str, ...],
        on_value_changed=None,
        tooltip_text: str = "",
        description_text: str = "",
    ):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(2)

        title = QLabel(name)
        title.setStyleSheet("font-size: 8px; font-weight: 800;")
        title.setWordWrap(True)

        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(4)
        control_layout.addSpacing(ROW_GAP)
        for option in options:
            button = QPushButton(option)
            button.setObjectName("ChoiceOn" if option == value else "ChoiceOff")
            button.setCursor(Qt.PointingHandCursor)
            if on_value_changed is not None:
                button.clicked.connect(lambda _checked=False, selected=option: on_value_changed(selected))
            control_layout.addWidget(button)
        control_layout.addStretch(1)

        layout.addWidget(title, 0, 0, 1, 3)
        control_row_index = 1
        if description_text:
            layout.addWidget(_inline_description(description_text), 1, 0, 1, 3)
            control_row_index = 2
        layout.addWidget(control_row, control_row_index, 0, 1, 3)
        layout.setColumnStretch(0, 1)
        _install_stable_tooltip(self, tooltip_text, title, control_row, *control_row.findChildren(QPushButton))


class BoolRow(QWidget):
    def __init__(
        self,
        name: str,
        value: bool,
        on_value_changed=None,
        tooltip_text: str = "",
        description_text: str = "",
    ):
        super().__init__()
        layout = QGridLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        layout.setHorizontalSpacing(0)
        layout.setVerticalSpacing(2)

        title = QLabel(name)
        title.setStyleSheet("font-size: 8px; font-weight: 800;")
        title.setWordWrap(True)

        toggle = ToggleButton(value)
        toggle.setFixedWidth(42)
        if on_value_changed is not None:
            toggle.clicked.connect(lambda checked: on_value_changed(bool(checked)))

        control_row = QWidget()
        control_layout = QHBoxLayout(control_row)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(0)
        control_layout.addSpacing(ROW_GAP)
        control_layout.addWidget(toggle)
        control_layout.addStretch(1)

        layout.addWidget(title, 0, 0, 1, 3)
        control_row_index = 1
        if description_text:
            layout.addWidget(_inline_description(description_text), 1, 0, 1, 3)
            control_row_index = 2
        layout.addWidget(control_row, control_row_index, 0, 1, 3)
        layout.setColumnStretch(0, 1)
        _install_stable_tooltip(self, tooltip_text, title, toggle, control_row)


class MeterPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.setFixedHeight(45)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(0, 2, 0, -2)
        painter.fillRect(rect, QColor(COLORS["surface_2"]))
        painter.setPen(QColor(COLORS["line"]))
        painter.drawRoundedRect(rect, 8, 8)
        width = rect.width() - 28
        x = rect.x() + 14
        y = rect.center().y()
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#2b3642"))
        painter.drawRoundedRect(x, y - 5, width, 10, 5, 5)
        painter.setBrush(QColor(COLORS["accent_2"]))
        painter.drawRoundedRect(x, y - 5, int(width * 0.68), 10, 5, 5)
        painter.setBrush(QColor(COLORS["accent"]))
        painter.drawEllipse(x + int(width * 0.68) - 7, y - 7, 14, 14)


def _clamp_percent(value: float) -> float:
    return max(0.0, min(100.0, float(value)))


class TriggerDebugMeter(QWidget):
    def __init__(
        self,
        force: float = 0.0,
        wall_start: float = 0.0,
        wall_end: float = 100.0,
        pulse_amp: float = 0.0,
        pulse_start: float = 0.0,
        vibrate_amp: float = 0.0,
        vibrate_start: float = 0.0,
    ):
        super().__init__()
        self.force = _clamp_percent(force)
        self.wall_start = _clamp_percent(wall_start)
        self.wall_end = _clamp_percent(wall_end)
        self.pulse_amp = _clamp_percent(pulse_amp)
        self.pulse_start = _clamp_percent(pulse_start)
        self.vibrate_amp = _clamp_percent(vibrate_amp)
        self.vibrate_start = _clamp_percent(vibrate_start)
        self.setMinimumWidth(128)
        self.setFixedHeight(20)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(1, 3, -1, -3)
        painter.setPen(Qt.NoPen)
        painter.setBrush(QColor("#071018"))
        painter.drawRoundedRect(rect, 3, 3)

        x = rect.left() + 5
        width = max(1, rect.width() - 10)
        top = rect.top() + 2
        force_width = round(width * self.force / 100.0)
        painter.setBrush(QColor(COLORS["accent_2"]))
        painter.drawRoundedRect(x, top, force_width, 3, 1, 1)

        wall_start = round(x + width * min(self.wall_start, self.wall_end) / 100.0)
        wall_end = round(x + width * max(self.wall_start, self.wall_end) / 100.0)
        if wall_end > wall_start:
            painter.setBrush(QColor(COLORS["accent"]))
            painter.drawRoundedRect(wall_start, top + 5, wall_end - wall_start, 3, 1, 1)

        pulse_level = max(self.pulse_amp, self.vibrate_amp)
        pulse_start = self.vibrate_start if self.vibrate_amp >= self.pulse_amp else self.pulse_start
        if pulse_level > 0.0:
            pulse_x = round(x + width * _clamp_percent(pulse_start) / 100.0)
            painter.setBrush(QColor(COLORS["cyan"]))
            painter.drawRoundedRect(pulse_x - 1, rect.top(), 2, rect.height(), 1, 1)
            level_width = round(width * pulse_level / 100.0)
            painter.drawRoundedRect(x, top + 10, level_width, 3, 1, 1)


class TriggerDebugOutputRow(QFrame):
    def __init__(self, name: str, spec):
        super().__init__()
        self.setObjectName("SubPanel")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 5, 8, 5)
        layout.setSpacing(8)

        title = QLabel(name)
        title.setStyleSheet(f"color: {COLORS['text']}; font-size: 8px; font-weight: 900;")
        title.setMinimumWidth(112)

        meter = TriggerDebugMeter(
            force=spec.force,
            wall_start=spec.wall_start,
            wall_end=spec.wall_end,
            pulse_amp=spec.pulse_amp,
            pulse_start=spec.pulse_start,
            vibrate_amp=spec.vibrate_amp,
            vibrate_start=spec.vibrate_start,
        )

        value = QLabel(
            f"F {spec.force:.0f}  P {max(spec.pulse_amp, spec.vibrate_amp):.0f}"
        )
        value.setObjectName("DetailValueBadge")
        value.setAlignment(Qt.AlignCenter)
        value.setFixedWidth(44)

        layout.addWidget(title)
        layout.addWidget(meter, 1)
        layout.addWidget(value)


class TelemetryGraphPreview(QWidget):
    def __init__(
        self,
        pattern: int = 0,
        color: str = COLORS["accent_2"],
        samples: list[float] | None = None,
    ):
        super().__init__()
        self.pattern = pattern
        self.color = color
        self.live_samples = list(samples or [])
        self.setMinimumHeight(78)

    def set_live_samples(self, samples: list[float] | None) -> None:
        next_samples = list(samples or [])
        if next_samples == self.live_samples:
            return
        self.live_samples = next_samples
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = self.rect().adjusted(2, 2, -2, -2)
        painter.fillRect(rect, QColor("#081017"))
        painter.setPen(QColor("#17232d"))
        for i in range(1, 5):
            x = rect.left() + rect.width() * i / 5
            painter.drawLine(int(x), rect.top(), int(x), rect.bottom())
        mid_y = rect.top() + rect.height() / 2.0
        painter.setPen(QColor("#26333f"))
        painter.drawLine(rect.left(), int(mid_y), rect.right(), int(mid_y))

        samples = self.live_samples or {
            0: [0.18, 0.22, 0.35, 0.62, 0.58, 0.74, 0.52, 0.68, 0.48, 0.57, 0.42],
            1: [0.12, 0.15, 0.18, 0.24, 0.33, 0.46, 0.61, 0.66, 0.72, 0.78, 0.83],
            2: [0.50, 0.42, 0.56, 0.36, 0.63, 0.44, 0.70, 0.39, 0.58, 0.48, 0.66],
            3: [0.22, 0.28, 0.26, 0.30, 0.74, 0.68, 0.34, 0.31, 0.72, 0.76, 0.29],
        }.get(self.pattern, [])
        if len(samples) < 2:
            return

        points = []
        for index, value in enumerate(samples):
            x = rect.left() + rect.width() * index / (len(samples) - 1)
            signed_value = max(-1.0, min(1.0, float(value)))
            y = mid_y - (rect.height() * 0.48 * signed_value)
            points.append((int(x), int(y)))

        painter.setPen(QColor(self.color))
        for start, end in zip(points, points[1:]):
            painter.drawLine(start[0], start[1], end[0], end[1])
        painter.setBrush(QColor(self.color))
        painter.setPen(Qt.NoPen)
        for x, y in points[-3:]:
            painter.drawEllipse(x - 2, y - 2, 4, 4)


class TelemetryCard(QFrame):
    DEFAULT_TELEMETRY_ITEMS = [
        "Speed",
        "RPM",
        "Boost",
        "Torque",
        "Throttle",
        "Brake",
        "Steer",
        "Lateral G",
        "Longitudinal G",
        "Wheel Slip",
        "Drift",
        "Gear",
    ]

    def __init__(
        self,
        name: str,
        pattern: int,
        color: str,
        on_selected=None,
        items=None,
        value_text: str = "--",
        samples: list[float] | None = None,
        tooltip_text: str = "",
        hint_text: str = "click name to change telemetry",
        value_tooltip: str = "",
    ):
        super().__init__()
        self.telemetry_name = name
        self.telemetry_items = items or self.DEFAULT_TELEMETRY_ITEMS
        self.on_selected = on_selected
        self.setObjectName("TelemetryCard")
        self.setMinimumHeight(104)
        if tooltip_text:
            self.setToolTip(tooltip_text)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 5)
        layout.setSpacing(1)

        header = QHBoxLayout()
        header.setContentsMargins(0, 0, 0, 0)
        header.setSpacing(6)

        name_button = QPushButton(name)
        name_button.setObjectName("TelemetryName")
        name_button.setCursor(Qt.PointingHandCursor)
        name_button.setFixedWidth(142)
        if tooltip_text:
            name_button.setToolTip(tooltip_text)
        name_button.setStyleSheet(
            f"QPushButton#TelemetryName {{ color: {color}; }}"
            f"QPushButton#TelemetryName:hover {{ color: {color}; }}"
        )
        name_button.clicked.connect(lambda checked=False, button=name_button: self._show_telemetry_menu(button))

        hint = QLabel(hint_text)
        hint.setObjectName("TelemetryHint")
        if tooltip_text:
            hint.setToolTip(tooltip_text)
        value = QLabel(value_text)
        value.setObjectName("TelemetryValue")
        value.setStyleSheet(f"QLabel#TelemetryValue {{ color: {color}; }}")
        value.setMinimumWidth(118)
        value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        if tooltip_text:
            value.setToolTip(f"{tooltip_text}\n{value_tooltip or 'Current graph value.'}")
        header.addWidget(name_button)
        header.addWidget(hint)
        header.addStretch(1)
        header.addWidget(value)

        graph = TelemetryGraphPreview(pattern, color, samples)
        self.value_label = value
        self.graph_preview = graph
        layout.addLayout(header)
        layout.addWidget(graph, 1)

    def update_live_data(self, value_text: str, samples: list[float] | None) -> None:
        if self.value_label.text() != value_text:
            self.value_label.setText(value_text)
        self.graph_preview.set_live_samples(samples)

    def _show_telemetry_menu(self, button: QPushButton):
        items = list(self.telemetry_items)
        if not items:
            return

        popup = QDialog(self, Qt.Popup | Qt.FramelessWindowHint)
        popup.setObjectName("TelemetryMenu")
        popup.setAttribute(Qt.WA_StyledBackground, True)

        grid = QGridLayout(popup)
        grid.setContentsMargins(6, 6, 6, 6)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(4)

        columns = 4 if len(items) > 48 else 3
        rows_per_column = max(1, (len(items) + columns - 1) // columns)
        for index, item in enumerate(items):
            row = index % rows_per_column
            column = index // rows_per_column
            item_button = QPushButton(item)
            item_button.setObjectName("TelemetryMenuItem")
            item_button.setCursor(Qt.PointingHandCursor)
            item_button.setFixedWidth(168)
            item_button.setMinimumHeight(22)
            if item == self.telemetry_name:
                item_button.setProperty("active", "true")
            item_button.clicked.connect(
                lambda checked=False, value=item, dialog=popup: self._select_telemetry_item(value, dialog)
            )
            grid.addWidget(item_button, row, column)

        popup.adjustSize()
        popup_size = popup.sizeHint()
        position = button.mapToGlobal(QPoint(0, button.height() + 3))
        screen = button.screen()
        if screen is not None:
            geometry = screen.availableGeometry()
            x = min(max(geometry.left() + 8, position.x()), geometry.right() - popup_size.width() - 8)
            y = min(max(geometry.top() + 8, position.y()), geometry.bottom() - popup_size.height() - 8)
            position = QPoint(x, y)
        popup.move(position)
        popup.exec()

    def _select_telemetry_item(self, item: str, popup: QDialog) -> None:
        popup.accept()
        if self.on_selected is not None:
            self.on_selected(item)


class OptionCard(QFrame):
    def __init__(self, title: str, description: str = "", tooltip_text: str = ""):
        super().__init__()
        self.setObjectName("OptionCard")
        if tooltip_text:
            self.setToolTip(tooltip_text)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(12, 10, 12, 10)
        self.layout.setSpacing(8)

        title_label = QLabel(title)
        title_label.setObjectName("OptionTitle")
        if tooltip_text:
            title_label.setToolTip(tooltip_text)
        self.layout.addWidget(title_label)

        if description:
            desc = QLabel(description)
            desc.setObjectName("OptionText")
            desc.setWordWrap(True)
            if tooltip_text:
                desc.setToolTip(tooltip_text)
            self.layout.addWidget(desc)


class LogoMark(QWidget):
    LOGO_PATH = Path(__file__).resolve().parent / "Resource" / "DHT_logo.svg"

    def __init__(self):
        super().__init__()
        self.setFixedSize(25, 25)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        logo = _svg_pixmap(self.LOGO_PATH, self.width(), self.height())
        if not logo.isNull():
            painter.drawPixmap(0, 0, logo)
            return

        d_font = QFont("Segoe UI", 14, QFont.Black)
        painter.setFont(d_font)
        painter.setPen(QColor(COLORS["accent"]))
        painter.drawText(0, 17, "D")

        ht_font = QFont("Segoe UI", 5, QFont.Bold)
        painter.setFont(ht_font)
        painter.setPen(QColor(COLORS["text"]))
        painter.drawText(15, 17, "HT")


class WindowControlButton(QPushButton):
    def __init__(self, kind: str):
        super().__init__()
        self.kind = kind
        self.setText("")
        self.setObjectName("WindowButtonClose" if kind == "close" else "WindowButton")
        self.setFixedSize(32, 26)
        self.setCursor(Qt.ArrowCursor)
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_Hover, True)

    def enterEvent(self, event):
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.update()
        super().leaveEvent(event)

    def mousePressEvent(self, event):
        self.update()
        super().mousePressEvent(event)

    def mouseReleaseEvent(self, event):
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing, True)

        hover = self.underMouse()
        pressed = self.isDown()
        if hover:
            background = QColor("#8f1d37" if pressed and self.kind == "close" else "#b32645" if self.kind == "close" else COLORS["surface_3"])
            painter.fillRect(self.rect(), background)

        color = QColor("#ffffff" if hover and self.kind == "close" else COLORS["text"] if hover else COLORS["muted"])
        pen = QPen(color, 1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        painter.setPen(pen)

        cx = self.width() / 2
        cy = self.height() / 2
        if self.kind == "minimize":
            y = cy + 4
            painter.drawLine(int(cx - 5), int(y), int(cx + 5), int(y))
        elif self.kind == "maximize":
            size = 9
            left = int(cx - size / 2)
            top = int(cy - size / 2)
            painter.drawRect(left, top, size, size)
        else:
            offset = 5
            painter.drawLine(int(cx - offset), int(cy - offset), int(cx + offset), int(cy + offset))
            painter.drawLine(int(cx + offset), int(cy - offset), int(cx - offset), int(cy + offset))


class TitleBar(QFrame):
    def __init__(self, window: QMainWindow):
        super().__init__()
        self.window = window
        self._drag_pos: QPoint | None = None
        self.setObjectName("TitleBar")
        self.setFixedHeight(34)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 0, 8, 0)
        layout.setSpacing(6)

        logo = LogoMark()

        title = QLabel("DualSense Haptic Translator")
        title.setObjectName("AppName")

        minimize = WindowControlButton("minimize")
        minimize.clicked.connect(window.showMinimized)

        maximize = WindowControlButton("maximize")
        maximize.clicked.connect(self._toggle_maximized)

        close = WindowControlButton("close")
        close.clicked.connect(window.close)

        layout.addWidget(logo)
        layout.addWidget(title)
        layout.addStretch(1)
        layout.addSpacing(4)
        layout.addWidget(minimize)
        layout.addWidget(maximize)
        layout.addWidget(close)

    def _toggle_maximized(self):
        if self.window.isMaximized():
            self.window.showNormal()
        else:
            self.window.showMaximized()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window.frameGeometry().topLeft()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_pos is not None and event.buttons() & Qt.LeftButton:
            if self.window.isMaximized():
                self.window.showNormal()
                self._drag_pos = QPoint(self.window.width() // 2, 24)
            self.window.move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()

    def mouseReleaseEvent(self, event):
        self._drag_pos = None
        event.accept()
