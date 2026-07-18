from __future__ import annotations

import socket
from dataclasses import dataclass

from .output_event_payloads import HAPTIC_EVENT_PORT, OutputEventPayload


@dataclass(frozen=True)
class OutputEventSendResult:
    message: str
    details: str
    ok: bool = True
    sent_count: int = 0


class OutputEventSender:
    """Small UDP sender boundary for server-compatible output event payloads."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        event_port: int = HAPTIC_EVENT_PORT,
    ) -> None:
        self.host = host
        self.event_port = event_port
        self._udp: socket.socket | None = None

    def send(
        self,
        payloads: tuple[OutputEventPayload, ...],
        *,
        execute: bool = False,
    ) -> OutputEventSendResult:
        if not payloads:
            return OutputEventSendResult(
                "No output event payloads to send.",
                "Payload list is empty.",
            )

        routes = tuple(self._route(payload) for payload in payloads)
        if not execute:
            return OutputEventSendResult(
                "Output event UDP send ready.",
                _dry_run_details(routes, self.host),
                ok=True,
                sent_count=0,
            )

        try:
            udp = self._socket()
            for payload, port in routes:
                udp.sendto(payload.to_message().encode("ascii", "replace"), (self.host, port))
        except OSError as exc:
            self.close()
            return OutputEventSendResult(
                "Output event UDP send failed.",
                str(exc),
                ok=False,
            )
        return OutputEventSendResult(
            "Output event UDP payloads sent.",
            f"{len(routes)} payload(s) sent to {self.host}.",
            ok=True,
            sent_count=len(routes),
        )

    def _route(self, payload: OutputEventPayload) -> tuple[OutputEventPayload, int]:
        return payload, self.event_port

    def _socket(self) -> socket.socket:
        if self._udp is None:
            self._udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._udp

    def close(self) -> None:
        if self._udp is None:
            return
        self._udp.close()
        self._udp = None


def _dry_run_details(routes: tuple[tuple[OutputEventPayload, int], ...], host: str) -> str:
    first_payload, first_port = routes[0]
    return (
        f"Dry-run only. {len(routes)} payload(s) prepared for UDP. "
        f"First target: {host}:{first_port}. First: {first_payload.to_message()}"
    )
