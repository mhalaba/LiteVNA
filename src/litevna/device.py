"""LiteVNA device connection, sweep control, and demo simulator."""

from __future__ import annotations

import logging
import math
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable

import numpy as np

try:
    import serial
    from serial.tools import list_ports
except ImportError:  # pragma: no cover
    serial = None
    list_ports = None

from .analysis import SweepData, impedance_to_reflection
from .protocol import (
    CMD_INDICATE,
    FIFO_POINT_SIZE,
    INDICATE_REPLY,
    MAX_FREQ_HZ,
    MIN_FREQ_HZ,
    REG_AVERAGE,
    REG_BATTERY_MV,
    REG_CHANNEL_SELECT,
    REG_DEVICE_VARIANT,
    REG_FIRMWARE_MAJOR,
    REG_FIRMWARE_MINOR,
    REG_HARDWARE_REVISION,
    REG_HF_POWER,
    REG_LF_POWER,
    REG_PROTOCOL_VERSION,
    REG_RAW_SAMPLES_MODE,
    REG_SCREENSHOT,
    REG_SN0,
    REG_SN1,
    REG_SN2,
    REG_SWEEP_POINTS,
    REG_SWEEP_START_HZ,
    REG_SWEEP_STEP_HZ,
    REG_UNIX_TIME,
    REG_VALUES_FIFO,
    REG_VALUES_PER_FREQUENCY,
    ChannelSelect,
    DeviceInfo,
    RawSamplesMode,
    chunk_fifo_reads,
    frequencies_hz,
    pack_read,
    pack_read2,
    pack_read4,
    pack_read_fifo,
    pack_write,
    pack_write2,
    pack_write4,
    pack_write8,
    parse_fifo_points,
    step_from_span,
)

logger = logging.getLogger(__name__)


@dataclass
class SweepSettings:
    start_hz: int = 1_000_000
    stop_hz: int = 30_000_000
    points: int = 201
    average: int = 1
    lf_power: int = 1
    hf_power: int = 3
    channel: ChannelSelect = ChannelSelect.BOTH
    values_per_frequency: int = 1
    mode: RawSamplesMode = RawSamplesMode.USB

    def clamped(self) -> "SweepSettings":
        start = max(MIN_FREQ_HZ, min(int(self.start_hz), MAX_FREQ_HZ))
        stop = max(start, min(int(self.stop_hz), MAX_FREQ_HZ))
        points = max(1, min(int(self.points), 65535))
        average = max(1, min(int(self.average), 80))
        lf = max(1, min(int(self.lf_power), 3))
        hf = max(1, min(int(self.hf_power), 3))
        vpf = max(1, min(int(self.values_per_frequency), 65535))
        return SweepSettings(
            start_hz=start,
            stop_hz=stop,
            points=points,
            average=average,
            lf_power=lf,
            hf_power=hf,
            channel=self.channel,
            values_per_frequency=vpf,
            mode=self.mode,
        )

    @property
    def step_hz(self) -> int:
        s = self.clamped()
        return step_from_span(s.start_hz, s.stop_hz, s.points)

    @property
    def center_hz(self) -> int:
        s = self.clamped()
        return (s.start_hz + s.stop_hz) // 2

    @property
    def span_hz(self) -> int:
        s = self.clamped()
        return s.stop_hz - s.start_hz


def list_serial_ports() -> list[dict]:
    """List candidate USB-CDC serial ports (macOS cu.* preferred)."""
    if list_ports is None:
        return []
    ports = []
    for p in list_ports.comports():
        ports.append(
            {
                "device": p.device,
                "name": p.name,
                "description": p.description or "",
                "hwid": p.hwid or "",
                "manufacturer": getattr(p, "manufacturer", None) or "",
            }
        )
    # Prefer macOS callout devices and likely VNA names
    def score(item: dict) -> tuple:
        d = item["device"].lower()
        desc = (item["description"] + item["manufacturer"]).lower()
        prefer = 0
        if "/cu." in d or d.startswith("/dev/cu."):
            prefer -= 10
        if any(k in desc or k in d for k in ("litevna", "nanovna", "cdc", "stm", "ch340", "cp210")):
            prefer -= 5
        return (prefer, d)

    return sorted(ports, key=score)


class LiteVNADevice:
    """Hardware LiteVNA over USB CDC (binary V2 protocol)."""

    def __init__(self, port: str, baudrate: int = 115200, timeout: float = 2.0):
        if serial is None:
            raise RuntimeError("pyserial is required for hardware connections")
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: serial.Serial | None = None
        self._lock = threading.RLock()

    @property
    def connected(self) -> bool:
        return self._ser is not None and self._ser.is_open

    def connect(self) -> DeviceInfo:
        with self._lock:
            self._ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout,
            )
            self._ser.reset_input_buffer()
            self._ser.reset_output_buffer()
            # Probe indicate
            self._write(bytes([CMD_INDICATE]))
            reply = self._read_exact(1)
            if reply != INDICATE_REPLY:
                self.disconnect()
                raise ConnectionError(f"Unexpected INDICATE reply: {reply!r}")
            return self.read_device_info()

    def disconnect(self) -> None:
        with self._lock:
            if self._ser is not None:
                try:
                    # Return device to normal UI mode
                    self.write_byte(REG_RAW_SAMPLES_MODE, RawSamplesMode.NORMAL)
                except Exception:  # noqa: BLE001
                    pass
                try:
                    self._ser.close()
                except Exception:  # noqa: BLE001
                    pass
                self._ser = None

    def _write(self, data: bytes) -> None:
        assert self._ser is not None
        self._ser.write(data)
        self._ser.flush()

    def _read_exact(self, n: int) -> bytes:
        assert self._ser is not None
        buf = bytearray()
        deadline = time.time() + self.timeout * max(1.0, n / 1024)
        while len(buf) < n:
            if time.time() > deadline:
                raise TimeoutError(f"Timed out reading {n} bytes (got {len(buf)})")
            chunk = self._ser.read(n - len(buf))
            if chunk:
                buf.extend(chunk)
        return bytes(buf)

    def write_byte(self, address: int, value: int) -> None:
        with self._lock:
            self._write(pack_write(address, value))

    def write_word(self, address: int, value: int) -> None:
        with self._lock:
            self._write(pack_write2(address, value))

    def write_dword(self, address: int, value: int) -> None:
        with self._lock:
            self._write(pack_write4(address, value))

    def write_qword(self, address: int, value: int) -> None:
        with self._lock:
            self._write(pack_write8(address, value))

    def read_byte(self, address: int) -> int:
        with self._lock:
            self._write(pack_read(address))
            return self._read_exact(1)[0]

    def read_word(self, address: int) -> int:
        with self._lock:
            self._write(pack_read2(address))
            return struct.unpack("<H", self._read_exact(2))[0]

    def read_dword(self, address: int) -> int:
        with self._lock:
            self._write(pack_read4(address))
            return struct.unpack("<I", self._read_exact(4))[0]

    def read_device_info(self) -> DeviceInfo:
        variant = self.read_byte(REG_DEVICE_VARIANT)
        proto = self.read_byte(REG_PROTOCOL_VERSION)
        hw = self.read_byte(REG_HARDWARE_REVISION)
        fw_maj = self.read_byte(REG_FIRMWARE_MAJOR)
        fw_min = self.read_byte(REG_FIRMWARE_MINOR)
        battery = None
        serial_parts = None
        try:
            battery = self.read_word(REG_BATTERY_MV)
        except Exception:  # noqa: BLE001
            logger.debug("Battery read failed", exc_info=True)
        try:
            serial_parts = (
                self.read_dword(REG_SN0),
                self.read_dword(REG_SN1),
                self.read_dword(REG_SN2),
            )
        except Exception:  # noqa: BLE001
            logger.debug("Serial number read failed", exc_info=True)
        return DeviceInfo(
            device_variant=variant,
            protocol_version=proto,
            hardware_revision=hw,
            firmware_major=fw_maj,
            firmware_minor=fw_min,
            battery_mv=battery,
            serial_parts=serial_parts,
        )

    def apply_settings(self, settings: SweepSettings) -> SweepSettings:
        s = settings.clamped()
        with self._lock:
            self._write(pack_write(REG_RAW_SAMPLES_MODE, int(s.mode)))
            self._write(pack_write8(REG_SWEEP_START_HZ, s.start_hz))
            self._write(pack_write8(REG_SWEEP_STEP_HZ, s.step_hz))
            self._write(pack_write2(REG_SWEEP_POINTS, s.points))
            self._write(pack_write2(REG_VALUES_PER_FREQUENCY, s.values_per_frequency))
            self._write(pack_write(REG_AVERAGE, s.average))
            self._write(pack_write(REG_LF_POWER, s.lf_power))
            self._write(pack_write(REG_HF_POWER, s.hf_power))
            self._write(pack_write(REG_CHANNEL_SELECT, int(s.channel)))
            # Clear FIFO
            self._write(pack_write(REG_VALUES_FIFO, 0))
        return s

    def set_unix_time(self, ts: int | None = None) -> None:
        if ts is None:
            ts = int(time.time())
        self.write_dword(REG_UNIX_TIME, ts)

    def clear_fifo(self) -> None:
        self.write_byte(REG_VALUES_FIFO, 0)

    def read_sweep(self, settings: SweepSettings, progress: Callable[[float], None] | None = None) -> SweepData:
        s = self.apply_settings(settings)
        # Brief settle for first sweep after settings change
        time.sleep(0.05 + 0.002 * s.average)

        points_needed = s.points
        collected = bytearray()
        # LiteVNA: NN=0 can mean "all points" on some firmwares; we use chunked reads.
        for chunk in chunk_fifo_reads(points_needed, 255):
            with self._lock:
                self._write(pack_read_fifo(REG_VALUES_FIFO, chunk))
                collected.extend(self._read_exact(chunk * FIFO_POINT_SIZE))
            if progress:
                progress(len(collected) / (points_needed * FIFO_POINT_SIZE))

        raw_points = parse_fifo_points(bytes(collected))
        # Sort / map by frequency index
        by_idx = {p.freq_index: p for p in raw_points}
        freqs = frequencies_hz(s.start_hz, s.step_hz, s.points)
        s11 = np.zeros(s.points, dtype=complex)
        s21 = np.zeros(s.points, dtype=complex)
        for i in range(s.points):
            p = by_idx.get(i)
            if p is None:
                # Fallback: use positional if index missing
                if i < len(raw_points):
                    p = raw_points[i]
                else:
                    continue
            s11[i] = p.s11
            s21[i] = p.s21
        return SweepData(
            frequencies_hz=np.asarray(freqs, dtype=float),
            s11=s11,
            s21=s21,
        )

    def capture_screenshot(self) -> bytes:
        """Request device screenshot; returns raw payload (BMP-like or device format)."""
        with self._lock:
            self._write(pack_write(REG_SCREENSHOT, 1))
            # Device-dependent size; read available with short timeout bursts
            chunks = []
            empty_reads = 0
            assert self._ser is not None
            old = self._ser.timeout
            self._ser.timeout = 0.2
            try:
                while empty_reads < 10:
                    data = self._ser.read(4096)
                    if data:
                        chunks.append(data)
                        empty_reads = 0
                    else:
                        empty_reads += 1
            finally:
                self._ser.timeout = old
            return b"".join(chunks)


class DemoDevice:
    """Software simulator for development without hardware."""

    def __init__(self, resonance_hz: float = 14_200_000.0, q: float = 40.0):
        self.resonance_hz = resonance_hz
        self.q = q
        self._info = DeviceInfo(
            device_variant=0x02,
            protocol_version=0x01,
            hardware_revision=0x04,
            firmware_major=1,
            firmware_minor=4,
            battery_mv=4020,
            serial_parts=(0x44454D4F, 0x00000001, 0x00000000),
        )
        self.port = "demo"
        self._settings = SweepSettings()

    @property
    def connected(self) -> bool:
        return True

    def connect(self) -> DeviceInfo:
        return self._info

    def disconnect(self) -> None:
        return None

    def read_device_info(self) -> DeviceInfo:
        return self._info

    def apply_settings(self, settings: SweepSettings) -> SweepSettings:
        self._settings = settings.clamped()
        return self._settings

    def set_unix_time(self, ts: int | None = None) -> None:
        return None

    def clear_fifo(self) -> None:
        return None

    def capture_screenshot(self) -> bytes:
        return b"DEMO_SCREENSHOT"

    def read_sweep(self, settings: SweepSettings, progress: Callable[[float], None] | None = None) -> SweepData:
        s = self.apply_settings(settings)
        freqs = np.asarray(frequencies_hz(s.start_hz, s.step_hz, s.points), dtype=float)
        # Series RLC near resonance → low SWR at f0
        f0 = self.resonance_hz
        r = 50.0
        # Reactance from detuning
        x = 2.0 * self.q * r * ((freqs / f0) - (f0 / freqs))
        z = r + 1j * x
        s11 = impedance_to_reflection(z, 50.0)
        # Mild S21 loss
        s21 = 0.95 * np.exp(-1j * 2.0 * math.pi * freqs * 1e-9)
        # Add tiny noise
        rng = np.random.default_rng(int(time.time() * 10) % 10_000)
        s11 = s11 + (rng.normal(0, 0.002, size=s.points) + 1j * rng.normal(0, 0.002, size=s.points))
        if progress:
            for i in range(5):
                progress((i + 1) / 5)
                time.sleep(0.01)
        return SweepData(frequencies_hz=freqs, s11=s11, s21=s21)


DeviceLike = LiteVNADevice | DemoDevice
