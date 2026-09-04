"""RF analysis helpers: impedance, SWR, formats, TDR."""

from __future__ import annotations

import cmath
import math
from dataclasses import dataclass
from enum import Enum

import numpy as np
from scipy.signal import windows

from .protocol import DEFAULT_Z0


class TraceFormat(str, Enum):
    LOGMAG = "logmag"
    PHASE = "phase"
    DELAY = "delay"
    SMITH = "smith"
    SWR = "swr"
    POLAR = "polar"
    LINEAR = "linear"
    REAL = "real"
    IMAG = "imag"
    RESISTANCE = "resistance"
    REACTANCE = "reactance"


class Channel(str, Enum):
    S11 = "s11"
    S21 = "s21"


class TdrMode(str, Enum):
    OFF = "off"
    BANDPASS = "bandpass"
    LOWPASS_IMPULSE = "lowpass_impulse"
    LOWPASS_STEP = "lowpass_step"


class TdrWindow(str, Enum):
    MINIMUM = "minimum"
    NORMAL = "normal"
    MAXIMUM = "maximum"


@dataclass
class SweepData:
    frequencies_hz: np.ndarray
    s11: np.ndarray
    s21: np.ndarray

    def channel(self, which: Channel) -> np.ndarray:
        return self.s11 if which == Channel.S11 else self.s21


def reflection_to_impedance(gamma: complex | np.ndarray, z0: float = DEFAULT_Z0):
    g = np.asarray(gamma, dtype=complex)
    denom = 1.0 - g
    # Avoid divide-by-zero at open circuit
    safe = np.where(np.abs(denom) < 1e-12, 1e-12 + 0j, denom)
    return z0 * (1.0 + g) / safe


def impedance_to_reflection(z: complex | np.ndarray, z0: float = DEFAULT_Z0):
    zz = np.asarray(z, dtype=complex)
    return (zz - z0) / (zz + z0)


def swr(gamma: complex | np.ndarray) -> np.ndarray:
    mag = np.abs(np.asarray(gamma, dtype=complex))
    mag = np.clip(mag, 0.0, 0.999999)
    return (1.0 + mag) / (1.0 - mag)


def return_loss_db(gamma: complex | np.ndarray) -> np.ndarray:
    mag = np.abs(np.asarray(gamma, dtype=complex))
    mag = np.maximum(mag, 1e-15)
    return -20.0 * np.log10(mag)


def logmag_db(s: complex | np.ndarray) -> np.ndarray:
    mag = np.abs(np.asarray(s, dtype=complex))
    mag = np.maximum(mag, 1e-15)
    return 20.0 * np.log10(mag)


def phase_deg(s: complex | np.ndarray) -> np.ndarray:
    return np.degrees(np.angle(np.asarray(s, dtype=complex)))


def group_delay_s(frequencies_hz: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Approximate group delay from unwrapped phase."""
    freqs = np.asarray(frequencies_hz, dtype=float)
    phase = np.unwrap(np.angle(np.asarray(s, dtype=complex)))
    delay = np.zeros_like(phase, dtype=float)
    if len(freqs) < 2:
        return delay
    dphase = np.diff(phase)
    df = np.diff(freqs) * 2.0 * math.pi
    gd = -dphase / np.where(np.abs(df) < 1e-30, 1e-30, df)
    delay[0] = gd[0]
    delay[1:] = gd
    return delay


def electrical_delay_apply(s: np.ndarray, frequencies_hz: np.ndarray, delay_s: float) -> np.ndarray:
    if abs(delay_s) < 1e-18:
        return s
    freqs = np.asarray(frequencies_hz, dtype=float)
    return np.asarray(s, dtype=complex) * np.exp(1j * 2.0 * math.pi * freqs * delay_s)


def format_trace(
    data: SweepData,
    channel: Channel,
    fmt: TraceFormat,
    z0: float = DEFAULT_Z0,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (x, y) for Cartesian plots, or (re, im) for Smith/Polar."""
    s = data.channel(channel)
    freqs = data.frequencies_hz

    if fmt == TraceFormat.LOGMAG:
        return freqs, logmag_db(s)
    if fmt == TraceFormat.PHASE:
        return freqs, phase_deg(s)
    if fmt == TraceFormat.DELAY:
        return freqs, group_delay_s(freqs, s) * 1e9  # ns
    if fmt == TraceFormat.SWR:
        return freqs, swr(s)
    if fmt == TraceFormat.LINEAR:
        return freqs, np.abs(s)
    if fmt == TraceFormat.REAL:
        return freqs, np.real(s)
    if fmt == TraceFormat.IMAG:
        return freqs, np.imag(s)
    if fmt in (TraceFormat.RESISTANCE, TraceFormat.REACTANCE):
        z = reflection_to_impedance(s, z0)
        if fmt == TraceFormat.RESISTANCE:
            return freqs, np.real(z)
        return freqs, np.imag(z)
    if fmt in (TraceFormat.SMITH, TraceFormat.POLAR):
        return np.real(s), np.imag(s)
    raise ValueError(f"Unknown format: {fmt}")


def _tdr_window(n: int, kind: TdrWindow) -> np.ndarray:
    if kind == TdrWindow.MINIMUM:
        return np.ones(n)
    if kind == TdrWindow.NORMAL:
        return windows.kaiser(n, beta=6.0)
    return windows.kaiser(n, beta=13.0)


def tdr_transform(
    data: SweepData,
    channel: Channel,
    mode: TdrMode,
    window: TdrWindow = TdrWindow.NORMAL,
    velocity_factor: float = 0.66,
) -> tuple[np.ndarray, np.ndarray]:
    """Return (distance_m, response) time-domain transform."""
    if mode == TdrMode.OFF:
        return np.array([]), np.array([])

    s = np.asarray(data.channel(channel), dtype=complex)
    freqs = np.asarray(data.frequencies_hz, dtype=float)
    n = len(s)
    if n < 4:
        return np.array([]), np.array([])

    win = _tdr_window(n, window)
    s_w = s * win

    if mode == TdrMode.BANDPASS:
        td = np.fft.ifft(s_w)
        response = np.abs(td)
    elif mode == TdrMode.LOWPASS_IMPULSE:
        # Mirror for Hermitian symmetry (low-pass)
        mirrored = np.concatenate([s_w, np.conj(s_w[-2:0:-1])])
        td = np.fft.ifft(mirrored)
        response = np.real(td)
    else:  # LOWPASS_STEP
        mirrored = np.concatenate([s_w, np.conj(s_w[-2:0:-1])])
        impulse = np.real(np.fft.ifft(mirrored))
        response = np.cumsum(impulse)

    df = (freqs[-1] - freqs[0]) / max(n - 1, 1)
    # Time step for IFFT
    dt = 1.0 / (2.0 * (freqs[-1] if mode != TdrMode.BANDPASS else (freqs[-1] - freqs[0] + df)))
    if mode == TdrMode.BANDPASS:
        dt = 1.0 / ((freqs[-1] - freqs[0]) + df)

    c = 299_792_458.0
    # Round-trip distance for reflection measurements
    distance = np.arange(len(response)) * dt * c * velocity_factor / 2.0
    # Keep useful first half
    half = len(response) // 2
    return distance[:half], response[:half]


def find_min_swr(data: SweepData) -> tuple[float, float]:
    """Return (freq_hz, min_swr)."""
    values = swr(data.s11)
    idx = int(np.argmin(values))
    return float(data.frequencies_hz[idx]), float(values[idx])


def complex_to_polar_db_deg(s: complex) -> tuple[float, float]:
    mag = abs(s)
    db = 20.0 * math.log10(max(mag, 1e-15))
    ang = math.degrees(cmath.phase(s))
    return db, ang
