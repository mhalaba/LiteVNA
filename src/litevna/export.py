"""Export sweep data to Touchstone / CSV."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from .analysis import SweepData, reflection_to_impedance, swr
from .protocol import DEFAULT_Z0


def export_s1p(path: Path, data: SweepData, z0: float = DEFAULT_Z0) -> None:
    lines = [
        "! LiteVNA Studio S1P export",
        f"# Hz S RI R {z0:g}",
    ]
    for f, s in zip(data.frequencies_hz, data.s11):
        lines.append(f"{f:.0f} {s.real:.8e} {s.imag:.8e}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_s2p(path: Path, data: SweepData, z0: float = DEFAULT_Z0) -> None:
    lines = [
        "! LiteVNA Studio S2P export",
        f"# Hz S RI R {z0:g}",
    ]
    # S12/S22 unknown on T/R VNA — export 0
    for f, s11, s21 in zip(data.frequencies_hz, data.s11, data.s21):
        lines.append(
            f"{f:.0f} {s11.real:.8e} {s11.imag:.8e} "
            f"{s21.real:.8e} {s21.imag:.8e} "
            f"0.0 0.0 0.0 0.0"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def export_csv(path: Path, data: SweepData, z0: float = DEFAULT_Z0) -> None:
    z = reflection_to_impedance(data.s11, z0)
    sw = swr(data.s11)
    header = "freq_hz,s11_re,s11_im,s21_re,s21_im,swr,r_ohm,x_ohm"
    rows = [header]
    for i in range(len(data.frequencies_hz)):
        rows.append(
            f"{data.frequencies_hz[i]:.0f},"
            f"{data.s11[i].real:.8e},{data.s11[i].imag:.8e},"
            f"{data.s21[i].real:.8e},{data.s21[i].imag:.8e},"
            f"{sw[i]:.6f},{np.real(z)[i]:.6f},{np.imag(z)[i]:.6f}"
        )
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
