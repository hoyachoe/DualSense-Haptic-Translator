from __future__ import annotations

import socket
import threading
import time
from dataclasses import dataclass
from queue import Empty, Queue
from typing import Any

from .output_event_payloads import TRIGGER_STATUS_PORT


@dataclass(frozen=True)
class DualSenseInputEvent:
    kind: str
    values: dict[str, Any] | None = None
    message: str = ""
    received_at: float = 0.0


class DualSenseInputReceiver:
    """Receives DualSense button/trigger status from the output service."""

    def __init__(self, port: int = TRIGGER_STATUS_PORT, host: str = "127.0.0.1", packet_size: int = 512):
        self.host = host
        self.port = int(port)
        self.packet_size = int(packet_size)
        self._events: Queue[DualSenseInputEvent] = Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="DualSenseInputReceiver",
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 1.0) -> None:
        self._stop_event.set()
        sock = self._socket
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass
        thread = self._thread
        if thread is not None:
            thread.join(timeout=timeout)
        self._thread = None
        self._socket = None

    def poll(self, max_events: int = 32) -> list[DualSenseInputEvent]:
        events: list[DualSenseInputEvent] = []
        for _ in range(max(0, int(max_events))):
            try:
                events.append(self._events.get_nowait())
            except Empty:
                break
        return events

    def _run(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.1)
            sock.bind((self.host, self.port))
            self._socket = sock
            self._events.put(
                DualSenseInputEvent(
                    kind="status",
                    message=f"DualSense input receiver listening on {self.host}:{self.port}",
                    received_at=time.monotonic(),
                )
            )
        except OSError as exc:
            self._events.put(
                DualSenseInputEvent(
                    kind="error",
                    message=f"DualSense input receiver failed to start: {exc}",
                    received_at=time.monotonic(),
                )
            )
            return

        while not self._stop_event.is_set():
            try:
                packet, _address = sock.recvfrom(self.packet_size)
            except socket.timeout:
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self._events.put(
                        DualSenseInputEvent(
                            kind="error",
                            message=f"DualSense input receiver socket error: {exc}",
                            received_at=time.monotonic(),
                        )
                    )
                break
            values = self._parse_packet(packet)
            if values:
                self._events.put(
                    DualSenseInputEvent(
                        kind="input",
                        values=values,
                        received_at=time.monotonic(),
                    )
                )

        self._events.put(
            DualSenseInputEvent(
                kind="status",
                message="DualSense input receiver stopped.",
                received_at=time.monotonic(),
            )
        )

    @staticmethod
    def _parse_packet(packet: bytes) -> dict[str, Any]:
        message = packet.decode("ascii", errors="ignore").strip()
        parts = message.split("|")
        if not parts or parts[0] != "DUALSENSE_INPUT":
            return {}
        values: dict[str, Any] = {}
        for part in parts[1:]:
            key, separator, value = part.partition("=")
            if not separator or not key:
                continue
            try:
                values[key] = float(value)
            except ValueError:
                values[key] = value
        return values
