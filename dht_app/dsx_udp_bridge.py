from __future__ import annotations

import json
import socket
import time
from dataclasses import dataclass
from typing import Iterable

from .output_event_payloads import OutputEventPayload


DSX_CONTROLLER_INDEX = 0
DSX_TRIGGER_UPDATE = 1
DSX_TRIGGER_LEFT = 1
DSX_TRIGGER_RIGHT = 2
DSX_MODE_NORMAL = 0
DSX_MODE_RESISTANCE = 13
DSX_MODE_V3_VIBRATION = 23
DSX_VIBRATION_FREQ_MAX = 40


@dataclass(frozen=True)
class DsxBridgeResult:
    sent: bool
    details: str
    sent_count: int = 0
    ignored_count: int = 0


class DsxUdpBridge:
    """Translate internal trigger payloads to DSX adaptive trigger UDP JSON."""

    def __init__(self) -> None:
        self._socket: socket.socket | None = None
        self._base_state: dict[int, tuple[int, tuple[int, ...]]] = {
            DSX_TRIGGER_LEFT: (DSX_MODE_NORMAL, ()),
            DSX_TRIGGER_RIGHT: (DSX_MODE_NORMAL, ()),
        }
        self._overlay_state: dict[int, tuple[float, int, tuple[int, ...], int, str]] = {}
        self._overlay_token = 0
        self.sent_count = 0
        self.last_error = ""

    def close(self) -> None:
        if self._socket is None:
            return
        try:
            self._socket.close()
        finally:
            self._socket = None

    def reset(self, host: str, port: int) -> DsxBridgeResult:
        self._base_state = {
            DSX_TRIGGER_LEFT: (DSX_MODE_NORMAL, ()),
            DSX_TRIGGER_RIGHT: (DSX_MODE_NORMAL, ()),
        }
        self._overlay_state.clear()
        return self._send_current_state(host, port, reason="reset")

    def send(
        self,
        payloads: Iterable[OutputEventPayload],
        host: str,
        port: int,
    ) -> DsxBridgeResult:
        handled = 0
        ignored = 0
        for payload in payloads:
            if self._apply_payload(payload):
                handled += 1
            else:
                ignored += 1
        if handled <= 0:
            return DsxBridgeResult(False, f"no DSX-compatible payloads; ignored={ignored}", ignored_count=ignored)
        sent = self._send_current_state(host, port, reason=f"{handled} payload(s)")
        return DsxBridgeResult(sent.sent, sent.details, sent.sent_count, ignored)

    def _apply_payload(self, payload: OutputEventPayload) -> bool:
        event = payload.name.strip().upper()
        fields = _payload_fields(payload)
        if event in {"TRIGGER_RESET", "TRIGGER_OFF"}:
            self._base_state[DSX_TRIGGER_LEFT] = (DSX_MODE_NORMAL, ())
            self._base_state[DSX_TRIGGER_RIGHT] = (DSX_MODE_NORMAL, ())
            self._overlay_state.clear()
            return True
        if event == "TRIGGER_BRAKE":
            self._base_state[DSX_TRIGGER_LEFT] = self._state_from_continuous_fields(fields)
            return True
        if event == "TRIGGER_THROTTLE":
            self._base_state[DSX_TRIGGER_RIGHT] = self._state_from_continuous_fields(fields)
            return True
        if event == "TRIGGER_KERB_BUZZ":
            now = time.monotonic()
            for trigger, amp_key, freq_key, zone_key, on_key in (
                (DSX_TRIGGER_LEFT, "leftAmp", "leftFreq", "leftStartZone", "left"),
                (DSX_TRIGGER_RIGHT, "rightAmp", "rightFreq", "rightStartZone", "right"),
            ):
                enabled = _int_field(fields, on_key, 0, 0, 1) > 0
                amp = _int_field(fields, amp_key, 0, 0, 8)
                freq = _int_field(fields, freq_key, 0, 1, DSX_VIBRATION_FREQ_MAX)
                zone = _int_field(fields, zone_key, 1, 1, 9)
                if enabled and amp > 0 and freq > 0:
                    self._overlay_state[trigger] = (
                        now + 0.18,
                        DSX_MODE_V3_VIBRATION,
                        (zone, amp, freq),
                        0,
                        "kerb",
                    )
                else:
                    overlay = self._overlay_state.get(trigger)
                    if overlay is not None and overlay[4] == "kerb":
                        self._overlay_state.pop(trigger, None)
            return True
        if event in {"TRIGGER_GEAR_SHIFT", "TRIGGER_COLLISION_KICK"}:
            strength = _amp_from_percent(fields.get("strength", "0"))
            if strength <= 0:
                return True
            duration_ms = _int_field(fields, "durationMs", 80, 20, 300)
            start = _start_zone_from_byte(fields.get("start", "0"), vibration=True)
            self._set_overlay(
                _triggers_from_side(fields.get("side", "both")),
                DSX_MODE_V3_VIBRATION,
                (start, strength, DSX_VIBRATION_FREQ_MAX),
                duration_ms,
                event,
            )
            return True
        if event == "TRIGGER_IMPACT_TICK":
            amp = _int_field(fields, "amp", 0, 0, 8)
            if amp <= 0:
                return True
            freq = _int_field(fields, "freq", DSX_VIBRATION_FREQ_MAX, 1, DSX_VIBRATION_FREQ_MAX)
            zone = _int_field(fields, "startZone", 1, 1, 9)
            duration_ms = _int_field(fields, "durationMs", 80, 20, 300)
            self._set_overlay((DSX_TRIGGER_RIGHT,), DSX_MODE_V3_VIBRATION, (zone, amp, freq), duration_ms, event)
            return True
        if event == "TRIGGER_MODE_TEST":
            amp = _amp_from_255(fields.get("amp", "80"))
            freq = _int_field(fields, "hz", DSX_VIBRATION_FREQ_MAX, 1, DSX_VIBRATION_FREQ_MAX)
            count = _int_field(fields, "count", 1, 1, 30)
            on_ms = _int_field(fields, "onMs", 80, 20, 1000)
            off_ms = _int_field(fields, "offMs", 0, 0, 1000)
            duration_ms = min(3000, count * (on_ms + off_ms))
            self._set_overlay(
                (DSX_TRIGGER_LEFT, DSX_TRIGGER_RIGHT),
                DSX_MODE_V3_VIBRATION,
                (1, amp, freq),
                duration_ms,
                event,
            )
            return True
        return False

    def _state_from_continuous_fields(self, fields: dict[str, str]) -> tuple[int, tuple[int, ...]]:
        force = _int_field(fields, "force", 0, 0, 255)
        start = _start_zone_from_byte(fields.get("start", "0"), vibration=False)
        vibrate_amp = _int_field(fields, "vibrateAmp", 0, 0, 8)
        vibrate_freq = _int_field(fields, "vibrateFreq", 0, 0, DSX_VIBRATION_FREQ_MAX)
        vibrate_zone = _int_field(fields, "vibrateStartZone", 1, 1, 9)
        pulse = _int_field(fields, "pulse", 0, 0, 255)
        pulse_rate = _int_field(fields, "pulseRate", 0, 0, 255)
        if vibrate_amp > 0 and vibrate_freq > 0:
            return DSX_MODE_V3_VIBRATION, (vibrate_zone, vibrate_amp, vibrate_freq)
        if pulse > 0 and pulse_rate > 0:
            return DSX_MODE_V3_VIBRATION, (max(1, start), _amp_from_255(pulse), max(1, min(DSX_VIBRATION_FREQ_MAX, pulse_rate)))
        if force > 0:
            return DSX_MODE_RESISTANCE, (start, _strength_from_255(force))
        return DSX_MODE_NORMAL, ()

    def _set_overlay(
        self,
        triggers: tuple[int, ...],
        mode: int,
        params: tuple[int, ...],
        duration_ms: int,
        tag: str,
    ) -> None:
        duration = max(20, min(1200, int(duration_ms)))
        self._overlay_token += 1
        until = time.monotonic() + duration / 1000.0
        for trigger in triggers:
            self._overlay_state[trigger] = (until, mode, params, self._overlay_token, tag)

    def _active_state_for_side(self, trigger: int, now: float) -> tuple[int, tuple[int, ...]]:
        overlay = self._overlay_state.get(trigger)
        if overlay is not None:
            until, mode, params, _token, _tag = overlay
            if until > now:
                return mode, params
            self._overlay_state.pop(trigger, None)
        return self._base_state.get(trigger, (DSX_MODE_NORMAL, ()))

    def _send_current_state(self, host: str, port: int, reason: str) -> DsxBridgeResult:
        target = (str(host).strip() or "127.0.0.1", int(port))
        now = time.monotonic()
        left_mode, left_params = self._active_state_for_side(DSX_TRIGGER_LEFT, now)
        right_mode, right_params = self._active_state_for_side(DSX_TRIGGER_RIGHT, now)
        message = {
            "instructions": [
                _instruction(DSX_TRIGGER_LEFT, left_mode, left_params),
                _instruction(DSX_TRIGGER_RIGHT, right_mode, right_params),
            ]
        }
        try:
            self._udp().sendto(json.dumps(message, separators=(",", ":")).encode("utf-8"), target)
        except OSError as exc:
            self.last_error = str(exc)
            self.close()
            return DsxBridgeResult(False, f"DSX UDP send failed: {exc}")
        self.sent_count += 1
        self.last_error = ""
        return DsxBridgeResult(True, f"DSX UDP {reason} sent to {target[0]}:{target[1]} total={self.sent_count}", sent_count=1)

    def _udp(self) -> socket.socket:
        if self._socket is None:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket


def _instruction(trigger: int, mode: int, params: tuple[int, ...]) -> dict:
    return {
        "type": DSX_TRIGGER_UPDATE,
        "parameters": [DSX_CONTROLLER_INDEX, trigger, mode, *params],
    }


def _payload_fields(payload: OutputEventPayload) -> dict[str, str]:
    return {str(key): str(value) for key, value in payload.params}


def _int_field(fields: dict[str, str], key: str, default: int, minimum: int, maximum: int) -> int:
    return _clamp_int(fields.get(key, default), minimum, maximum)


def _clamp_int(value, minimum: int, maximum: int) -> int:
    try:
        clean = int(round(float(value)))
    except (TypeError, ValueError):
        clean = minimum
    return max(minimum, min(maximum, clean))


def _strength_from_255(value) -> int:
    force = _clamp_int(value, 0, 255)
    if 0 <= force <= 8:
        return force
    return max(0, min(8, int(round(force * 8 / 255.0))))


def _amp_from_percent(value) -> int:
    percent = _clamp_int(value, 0, 100)
    if percent <= 0:
        return 0
    return max(1, min(8, int(round(percent * 8 / 100.0))))


def _amp_from_255(value) -> int:
    amp = _clamp_int(value, 0, 255)
    if amp <= 0:
        return 0
    return max(1, min(8, int(round(amp * 8 / 255.0))))


def _start_zone_from_byte(value, vibration: bool = False) -> int:
    start = _clamp_int(value, 0, 255)
    zone = max(0, min(9, int(round(start / 255.0 * 9.0))))
    return max(1, zone) if vibration else zone


def _triggers_from_side(side: str) -> tuple[int, ...]:
    value = str(side).strip().lower()
    if value in {"left", "l", "-1"}:
        return (DSX_TRIGGER_LEFT,)
    if value in {"right", "r", "1"}:
        return (DSX_TRIGGER_RIGHT,)
    return (DSX_TRIGGER_LEFT, DSX_TRIGGER_RIGHT)
