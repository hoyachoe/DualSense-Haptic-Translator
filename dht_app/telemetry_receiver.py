from __future__ import annotations

import socket
import threading
from dataclasses import dataclass
from queue import Empty, Queue


@dataclass(frozen=True)
class TelemetryReceiverEvent:
    kind: str
    packet: bytes = b""
    address: tuple[str, int] | None = None
    message: str = ""


class TelemetryReceiver:
    """Small UDP receiver boundary for Forza Data Out packets.

    The receiver owns the socket and background thread, but it never touches
    UI state directly. The UI can poll events and pass packets into
    EngineBridge on the main thread.
    """

    def __init__(self, port: int, host: str = "0.0.0.0", packet_size: int = 1500):
        self.host = host
        self.port = int(port)
        self.packet_size = int(packet_size)
        self._events: Queue[TelemetryReceiverEvent] = Queue()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._socket: socket.socket | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, port: int | None = None) -> None:
        if port is not None:
            self.port = int(port)
        if self.is_running:
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="TelemetryReceiver",
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

    def poll(self, max_events: int = 32) -> list[TelemetryReceiverEvent]:
        events: list[TelemetryReceiverEvent] = []
        for _ in range(max(0, int(max_events))):
            try:
                events.append(self._events.get_nowait())
            except Empty:
                break
        return events

    def push_test_packet(self, packet: bytes) -> None:
        self._events.put(TelemetryReceiverEvent(kind="packet", packet=bytes(packet)))

    def _run(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(0.1)
            sock.bind((self.host, self.port))
            self._socket = sock
            self._events.put(
                TelemetryReceiverEvent(
                    kind="status",
                    message=f"Telemetry receiver listening on {self.host}:{self.port}",
                )
            )
        except OSError as exc:
            self._events.put(
                TelemetryReceiverEvent(
                    kind="error",
                    message=f"Telemetry receiver failed to start: {exc}",
                )
            )
            return

        while not self._stop_event.is_set():
            try:
                packet, address = sock.recvfrom(self.packet_size)
            except socket.timeout:
                continue
            except OSError as exc:
                if not self._stop_event.is_set():
                    self._events.put(
                        TelemetryReceiverEvent(
                            kind="error",
                            message=f"Telemetry receiver socket error: {exc}",
                        )
                    )
                break
            self._events.put(
                TelemetryReceiverEvent(
                    kind="packet",
                    packet=packet,
                    address=address,
                )
            )

        self._events.put(TelemetryReceiverEvent(kind="status", message="Telemetry receiver stopped."))
