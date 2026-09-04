"""Host-side SOLT calibration for LiteVNA (on-device cal not available over USB)."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

import numpy as np

from .analysis import SweepData
from .protocol import DEFAULT_Z0


class CalStep(str, Enum):
    OPEN = "open"
    SHORT = "short"
    LOAD = "load"
    ISOLATION = "isolation"
    THRU = "thru"


@dataclass
class CalibrationProfile:
    name: str = "default"
    frequencies_hz: np.ndarray = field(default_factory=lambda: np.array([], dtype=float))
    open_s11: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    short_s11: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    load_s11: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    isolation_s21: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    thru_s21: np.ndarray = field(default_factory=lambda: np.array([], dtype=complex))
    z0: float = DEFAULT_Z0
    enabled: bool = True

    def has_reflection(self) -> bool:
        return (
            len(self.frequencies_hz) > 0
            and len(self.open_s11) == len(self.frequencies_hz)
            and len(self.short_s11) == len(self.frequencies_hz)
            and len(self.load_s11) == len(self.frequencies_hz)
        )

    def has_transmission(self) -> bool:
        return (
            self.has_reflection()
            and len(self.isolation_s21) == len(self.frequencies_hz)
            and len(self.thru_s21) == len(self.frequencies_hz)
        )

    def set_step(self, step: CalStep, data: SweepData) -> None:
        if len(self.frequencies_hz) == 0:
            self.frequencies_hz = np.asarray(data.frequencies_hz, dtype=float).copy()
        elif not np.allclose(self.frequencies_hz, data.frequencies_hz):
            raise ValueError("Calibration sweep frequencies must match previous steps")

        if step == CalStep.OPEN:
            self.open_s11 = np.asarray(data.s11, dtype=complex).copy()
        elif step == CalStep.SHORT:
            self.short_s11 = np.asarray(data.s11, dtype=complex).copy()
        elif step == CalStep.LOAD:
            self.load_s11 = np.asarray(data.s11, dtype=complex).copy()
        elif step == CalStep.ISOLATION:
            self.isolation_s21 = np.asarray(data.s21, dtype=complex).copy()
        elif step == CalStep.THRU:
            self.thru_s21 = np.asarray(data.s21, dtype=complex).copy()

    def apply(self, data: SweepData) -> SweepData:
        if not self.enabled or not self.has_reflection():
            return data

        # Interpolate error terms onto measurement frequencies
        e00, e11, e10e01 = self._reflection_error_terms()
        freqs = data.frequencies_hz
        e00_i = _interp_complex(self.frequencies_hz, e00, freqs)
        e11_i = _interp_complex(self.frequencies_hz, e11, freqs)
        e10e01_i = _interp_complex(self.frequencies_hz, e10e01, freqs)

        raw_s11 = np.asarray(data.s11, dtype=complex)
        # One-port: S11_a = (S11_m - e00) / (e10e01 + e11*(S11_m - e00))
        numer = raw_s11 - e00_i
        denom = e10e01_i + e11_i * numer
        denom = np.where(np.abs(denom) < 1e-18, 1e-18 + 0j, denom)
        cal_s11 = numer / denom

        cal_s21 = np.asarray(data.s21, dtype=complex).copy()
        if self.has_transmission():
            e30 = _interp_complex(self.frequencies_hz, self.isolation_s21, freqs)
            e10e32 = _interp_complex(
                self.frequencies_hz,
                self.thru_s21 - self.isolation_s21,
                freqs,
            )
            e10e32 = np.where(np.abs(e10e32) < 1e-18, 1e-18 + 0j, e10e32)
            # Simplified: S21_a = (S21_m - e30) / e10e32
            cal_s21 = (np.asarray(data.s21, dtype=complex) - e30) / e10e32

        return SweepData(frequencies_hz=freqs.copy(), s11=cal_s11, s21=cal_s21)

    def _reflection_error_terms(self) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Compute directivity (e00), source match (e11), reflection tracking (e10e01).

        Model: S11_m = e00 + e10e01 * Γ / (1 - e11 * Γ)
        Ideal standards: open Γ=1, short Γ=-1, load Γ=0 → e00 = load.
        """
        g_o = self.open_s11
        g_s = self.short_s11
        g_l = self.load_s11

        e00 = g_l
        a = g_o - e00  # = e10e01 / (1 - e11)
        b = g_s - e00  # = -e10e01 / (1 + e11)
        # a(1 - e11) = -b(1 + e11)  →  e11 = (a + b) / (a - b)
        denom = a - b
        denom = np.where(np.abs(denom) < 1e-18, 1e-18 + 0j, denom)
        e11 = (a + b) / denom
        e10e01 = a * (1.0 - e11)
        return e00, e11, e10e01

    def to_dict(self) -> dict:
        def cplx_list(arr: np.ndarray) -> list:
            return [[float(z.real), float(z.imag)] for z in arr]

        return {
            "name": self.name,
            "z0": self.z0,
            "enabled": self.enabled,
            "frequencies_hz": [float(f) for f in self.frequencies_hz],
            "open_s11": cplx_list(self.open_s11),
            "short_s11": cplx_list(self.short_s11),
            "load_s11": cplx_list(self.load_s11),
            "isolation_s21": cplx_list(self.isolation_s21),
            "thru_s21": cplx_list(self.thru_s21),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationProfile":
        def to_cplx(items: list) -> np.ndarray:
            return np.array([complex(a, b) for a, b in items], dtype=complex)

        return cls(
            name=data.get("name", "default"),
            z0=float(data.get("z0", DEFAULT_Z0)),
            enabled=bool(data.get("enabled", True)),
            frequencies_hz=np.array(data.get("frequencies_hz", []), dtype=float),
            open_s11=to_cplx(data.get("open_s11", [])),
            short_s11=to_cplx(data.get("short_s11", [])),
            load_s11=to_cplx(data.get("load_s11", [])),
            isolation_s21=to_cplx(data.get("isolation_s21", [])),
            thru_s21=to_cplx(data.get("thru_s21", [])),
        )

    def save(self, path: Path) -> None:
        path.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path) -> "CalibrationProfile":
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))


def _interp_complex(x: np.ndarray, y: np.ndarray, x_new: np.ndarray) -> np.ndarray:
    if len(x) == 0:
        return np.zeros(len(x_new), dtype=complex)
    if len(x) == 1:
        return np.full(len(x_new), y[0], dtype=complex)
    re = np.interp(x_new, x, np.real(y))
    im = np.interp(x_new, x, np.imag(y))
    return re + 1j * im
