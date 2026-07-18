from __future__ import annotations

import math
import struct

from .app_state import GameMode


def build_test_telemetry_packet(game_mode: GameMode, tick: int = 0) -> bytes:
    if game_mode == GameMode.MOTORSPORT:
        return build_motorsport_dash_test_packet(tick)
    return build_horizon_test_packet(tick)


def _wave(tick: int, period: float, low: float, high: float) -> float:
    phase = (math.sin(float(tick) / period) + 1.0) * 0.5
    return low + (high - low) * phase


def _core_packet(size: int, tick: int) -> bytearray:
    packet = bytearray(size)
    max_rpm = 8200.0
    rpm = _wave(tick, 3.8, 1800.0, 7600.0)
    struct.pack_into("<i", packet, 0, 1)
    struct.pack_into("<I", packet, 4, int(tick * 16) & 0xFFFFFFFF)
    struct.pack_into("<f", packet, 8, max_rpm)
    struct.pack_into("<f", packet, 12, 850.0)
    struct.pack_into("<f", packet, 16, rpm)
    struct.pack_into("<f", packet, 20, 0.0)
    struct.pack_into("<f", packet, 24, 0.2)
    struct.pack_into("<f", packet, 28, 0.0)
    struct.pack_into("<f", packet, 32, 0.2)
    struct.pack_into("<f", packet, 36, 0.0)
    struct.pack_into("<f", packet, 40, 18.0)
    struct.pack_into("<f", packet, 48, 0.1)
    left_suspension = 0.22 + 0.006 * math.sin(float(tick) / 2.0)
    right_suspension = 0.24 + 0.005 * math.cos(float(tick) / 2.3)
    if tick % 20 in range(6, 9):
        left_suspension += 0.055
        struct.pack_into("<f", packet, 24, 3.4)
    if tick % 24 in range(12, 15):
        right_suspension += 0.048
        struct.pack_into("<f", packet, 24, 3.1)
    struct.pack_into("<f", packet, 68, left_suspension)
    struct.pack_into("<f", packet, 72, right_suspension)
    struct.pack_into("<f", packet, 76, left_suspension * 0.92)
    struct.pack_into("<f", packet, 80, right_suspension * 0.90)
    if tick % 18 in range(4, 8):
        struct.pack_into("<i", packet, 116, 1)
        struct.pack_into("<f", packet, 148, 0.23)
    if tick % 22 in range(10, 14):
        struct.pack_into("<i", packet, 120, 1)
        struct.pack_into("<f", packet, 152, 0.24)
    if tick % 26 in range(16, 20):
        struct.pack_into("<f", packet, 20, -9.2)
        struct.pack_into("<f", packet, 28, -4.4)
        struct.pack_into("<f", packet, 32, 1.2)
        struct.pack_into("<f", packet, 40, 42.0)
        struct.pack_into("<f", packet, 48, 0.45)
        struct.pack_into("<f", packet, 84, 0.30)
        struct.pack_into("<f", packet, 88, 0.26)
        struct.pack_into("<f", packet, 92, 0.12)
        struct.pack_into("<f", packet, 96, 0.11)
        struct.pack_into("<f", packet, 164, 1.32)
        struct.pack_into("<f", packet, 168, 1.18)
        struct.pack_into("<f", packet, 172, 0.42)
        struct.pack_into("<f", packet, 176, 0.40)
        struct.pack_into("<f", packet, 180, 0.78)
        struct.pack_into("<f", packet, 184, 0.72)
        struct.pack_into("<f", packet, 188, 0.30)
        struct.pack_into("<f", packet, 192, 0.28)
    struct.pack_into("<i", packet, 212, 1501)
    struct.pack_into("<i", packet, 216, 3)
    struct.pack_into("<i", packet, 224, 1)
    if tick % 28 in range(20, 24):
        struct.pack_into("<f", packet, 92, 1.65)
        struct.pack_into("<f", packet, 96, 1.78)
    return packet


def build_horizon_test_packet(tick: int = 0) -> bytes:
    packet = _core_packet(324, tick)
    speed_mps = _wave(tick, 5.2, 8.0, 55.0)
    throttle = int(_wave(tick, 2.5, 45.0, 230.0))
    brake = int(_wave(tick + 8, 4.0, 0.0, 80.0))
    gear = max(1, min(6, int(speed_mps / 8.5) + 1))
    steer = int(_wave(tick, 3.0, -48.0, 48.0))
    if tick % 36 == 10:
        speed_mps = 36.0
        brake = 0
    if tick % 36 == 11:
        speed_mps = 12.0
        brake = 0
        struct.pack_into("<f", packet, 20, 64.0)
        struct.pack_into("<f", packet, 24, 8.0)
        struct.pack_into("<f", packet, 28, -12.0)
        struct.pack_into("<f", packet, 180, 12.0)
        struct.pack_into("<f", packet, 184, 10.5)
    if tick % 40 == 18:
        speed_mps = 22.0
        struct.pack_into("<f", packet, 236, 0.075)
        struct.pack_into("<f", packet, 240, 45.0)
    if tick % 44 == 29:
        speed_mps = 26.0
        brake = 0
        steer = 54
        struct.pack_into("<f", packet, 32, 0.0)
        struct.pack_into("<f", packet, 36, 0.0)
        struct.pack_into("<f", packet, 40, 25.0)
    if tick % 44 == 30:
        speed_mps = 26.0
        brake = 0
        steer = 52
        struct.pack_into("<f", packet, 20, 10.5)
        struct.pack_into("<f", packet, 24, 1.0)
        struct.pack_into("<f", packet, 28, 4.0)
        struct.pack_into("<f", packet, 32, 4.0)
        struct.pack_into("<f", packet, 36, 0.0)
        struct.pack_into("<f", packet, 40, 22.0)
        struct.pack_into("<f", packet, 48, 0.74)
    struct.pack_into("<f", packet, 256, speed_mps)
    struct.pack_into("<f", packet, 260, _wave(tick, 4.7, 80.0, 520.0))
    struct.pack_into("<f", packet, 264, _wave(tick, 4.2, 180.0, 820.0))
    struct.pack_into("<f", packet, 284, _wave(tick, 3.3, 0.0, 2.2))
    packet[315] = throttle
    packet[316] = brake
    packet[317] = 0
    packet[318] = 0
    packet[319] = gear
    struct.pack_into("<b", packet, 320, steer)
    return bytes(packet)


def build_motorsport_dash_test_packet(tick: int = 0) -> bytes:
    packet = _core_packet(332, tick)
    speed_mps = _wave(tick, 4.8, 10.0, 62.0)
    throttle = int(_wave(tick, 2.4, 55.0, 240.0))
    brake = int(_wave(tick + 9, 4.4, 0.0, 75.0))
    gear = max(1, min(6, int(speed_mps / 9.0) + 1))
    steer = int(_wave(tick, 3.2, -44.0, 44.0))
    struct.pack_into("<f", packet, 244, speed_mps)
    struct.pack_into("<f", packet, 248, _wave(tick, 4.5, 90.0, 540.0))
    struct.pack_into("<f", packet, 252, _wave(tick, 4.0, 170.0, 780.0))
    struct.pack_into("<f", packet, 272, _wave(tick, 3.1, 0.0, 2.0))
    packet[303] = throttle
    packet[304] = brake
    packet[305] = 0
    packet[306] = 0
    packet[307] = gear
    struct.pack_into("<b", packet, 308, steer)
    return bytes(packet)
