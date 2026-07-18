from __future__ import annotations

import socket
from dataclasses import dataclass


@dataclass(frozen=True)
class TelemetryRelayResult:
    forwarded: bool
    details: str = ""


class TelemetryRelay:
    """Forward raw telemetry packets to another UDP target."""

    def __init__(self):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def close(self) -> None:
        try:
            self._socket.close()
        except OSError:
            pass

    def forward(self, packet: bytes, host: str, port: int) -> TelemetryRelayResult:
        target = (str(host), int(port))
        try:
            self._socket.sendto(packet, target)
        except OSError as exc:
            return TelemetryRelayResult(False, f"relay failed: {exc}")
        return TelemetryRelayResult(True, f"relay forwarded {len(packet)} bytes to {target[0]}:{target[1]}")
