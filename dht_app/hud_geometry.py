from __future__ import annotations


def normalized_main_ui_scale_factor(scale: object) -> float:
    """Return the user-selected Qt scale as a safe multiplier."""
    try:
        percent = int(scale)
    except (TypeError, ValueError):
        percent = 100
    return max(0.01, percent / 100.0)


def hud_logical_value(canonical_value: float, main_ui_scale_factor: float) -> int:
    """Convert a 100%-UI HUD value into Qt logical coordinates."""
    factor = max(0.01, float(main_ui_scale_factor))
    return round(float(canonical_value) / factor)


def hud_canonical_value(logical_value: float, main_ui_scale_factor: float) -> int:
    """Convert a Qt logical HUD value into persistent 100%-UI coordinates."""
    factor = max(0.01, float(main_ui_scale_factor))
    return round(float(logical_value) * factor)
