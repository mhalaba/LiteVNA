"""LiteVNA / NanoVNA V2 binary USB-CDC protocol constants and helpers."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from enum import IntEnum
from typing import Iterable

# Host → device opcodes
CMD_NOP = 0x00
CMD_INDICATE = 0x0D
CMD_READ = 0x10
CMD_READ2 = 0x11
CMD_READ4 = 0x12
CMD_READ8 = 0x13
CMD_READFIFO = 0x18
CMD_WRITE = 0x20
CMD_WRITE2 = 0x21
CMD_WRITE4 = 0x22
CMD_WRITE8 = 0x23
CMD_WRITEFIFO = 0x28

# Register addresses
REG_SWEEP_START_HZ = 0x00
REG_SWEEP_STEP_HZ = 0x10
REG_SWEEP_POINTS = 0x20
REG_VALUES_PER_FREQUENCY = 0x22
REG_RAW_SAMPLES_MODE = 0x26
REG_VALUES_FIFO = 0x30
REG_AVERAGE = 0x40
REG_LF_POWER = 0x41
REG_HF_POWER = 0x42
REG_CHANNEL_SELECT = 0x44
REG_COLOR_VALUE = 0x50
REG_COLOR_INDEX = 0x54
REG_UNIX_TIME = 0x58
REG_BATTERY_MV = 0x5C
REG_SCREENSHOT = 0xEE
REG_SN0 = 0xD0
REG_SN1 = 0xD4
REG_SN2 = 0xD8
REG_DEVICE_VARIANT = 0xF0
REG_PROTOCOL_VERSION = 0xF1
REG_HARDWARE_REVISION = 0xF2
REG_FIRMWARE_MAJOR = 0xF3
REG_FIRMWARE_MINOR = 0xF4

# DFU
REG_FLASH_WRITE_START = 0xE0
REG_FLASH_FIFO = 0xE4
REG_USER_ARGUMENT = 0xE8
REG_DO_REBOOT = 0xEF
DFU_REBOOT_MAGIC = 0x5E

FIFO_POINT_SIZE = 32
INDICATE_REPLY = b"2"
DEVICE_VARIANT_LITEVNA = 0x02
MIN_FREQ_HZ = 50_000
MAX_FREQ_HZ = 6_300_000_000
DEFAULT_Z0 = 50.0


class RawSamplesMode(IntEnum):
    USB = 0
    RAW_DATA = 1
    NORMAL = 2
    CALIBRATED = 3


class ChannelSelect(IntEnum):
    BOTH = 0x00
    S11 = 0x01
    S21 = 0x02


@dataclass(frozen=True)
class DeviceInfo:
    device_variant: int
    protocol_version: int
    hardware_revision: int
    firmware_major: int
    firmware_minor: int
    battery_mv: int | None = None
    serial_parts: tuple[int, int, int] | None = None

    @property
    def firmware(self) -> str:
        return f"{self.firmware_major}.{self.firmware_minor}"

    @property
    def is_litevna(self) -> bool:
        return self.device_variant == DEVICE_VARIANT_LITEVNA


@dataclass
class RawPoint:
    fwd0: complex
    rev0: complex
    rev1: complex
    freq_index: int

    @property
    def s11(self) -> complex:
        if abs(self.fwd0) < 1e-30:
            return complex(0.0)
        return self.rev0 / self.fwd0

    @property
    def s21(self) -> complex:
        if abs(self.fwd0) < 1e-30:
            return complex(0.0)
        return self.rev1 / self.fwd0


def pack_write8(address: int, value: int) -> bytes:
    return bytes([CMD_WRITE8, address]) + struct.pack("<Q", value)


def pack_write2(address: int, value: int) -> bytes:
    return bytes([CMD_WRITE2, address]) + struct.pack("<H", value)


def pack_write(address: int, value: int) -> bytes:
    return bytes([CMD_WRITE, address, value & 0xFF])


def pack_write4(address: int, value: int) -> bytes:
    return bytes([CMD_WRITE4, address]) + struct.pack("<I", value)


def pack_read(address: int) -> bytes:
    return bytes([CMD_READ, address])


def pack_read2(address: int) -> bytes:
    return bytes([CMD_READ2, address])


def pack_read4(address: int) -> bytes:
    return bytes([CMD_READ4, address])


def pack_read8(address: int) -> bytes:
    return bytes([CMD_READ8, address])


def pack_read_fifo(address: int, count: int) -> bytes:
    return bytes([CMD_READFIFO, address, count & 0xFF])


def pack_write_fifo(address: int, payload: bytes) -> bytes:
    if len(payload) > 255:
        raise ValueError("WRITEFIFO payload max 255 bytes")
    return bytes([CMD_WRITEFIFO, address, len(payload)]) + payload


def parse_fifo_point(data: bytes) -> RawPoint:
    if len(data) != FIFO_POINT_SIZE:
        raise ValueError(f"Expected {FIFO_POINT_SIZE} bytes, got {len(data)}")
    (
        fwd0_re,
        fwd0_im,
        rev0_re,
        rev0_im,
        rev1_re,
        rev1_im,
        freq_index,
        _reserved,
    ) = struct.unpack("<iiiiiiH6s", data)
    return RawPoint(
        fwd0=complex(fwd0_re, fwd0_im),
        rev0=complex(rev0_re, rev0_im),
        rev1=complex(rev1_re, rev1_im),
        freq_index=freq_index,
    )


def parse_fifo_points(blob: bytes) -> list[RawPoint]:
    if len(blob) % FIFO_POINT_SIZE != 0:
        raise ValueError("FIFO blob length must be multiple of 32")
    return [
        parse_fifo_point(blob[i : i + FIFO_POINT_SIZE])
        for i in range(0, len(blob), FIFO_POINT_SIZE)
    ]


def frequencies_hz(start_hz: int, step_hz: int, points: int) -> list[int]:
    return [int(start_hz + i * step_hz) for i in range(points)]


def step_from_span(start_hz: int, stop_hz: int, points: int) -> int:
    if points < 2:
        return 0
    return max(1, int(round((stop_hz - start_hz) / (points - 1))))


def chunk_fifo_reads(total_points: int, max_per_read: int = 255) -> Iterable[int]:
    remaining = total_points
    while remaining > 0:
        n = min(remaining, max_per_read)
        yield n
        remaining -= n
