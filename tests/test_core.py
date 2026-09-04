"""Unit tests for protocol, analysis, presets, calibration, export, demo device."""

from __future__ import annotations

import struct
from pathlib import Path

import numpy as np
import pytest

from litevna.analysis import (
    Channel,
    SweepData,
    TdrMode,
    TraceFormat,
    find_min_swr,
    format_trace,
    impedance_to_reflection,
    reflection_to_impedance,
    swr,
    tdr_transform,
)
from litevna.calibration import CalStep, CalibrationProfile
from litevna.device import DemoDevice, SweepSettings
from litevna.export import export_csv, export_s1p, export_s2p
from litevna.i18n import set_language, t
from litevna.presets import PRESETS, get_preset
from litevna.protocol import (
    FIFO_POINT_SIZE,
    parse_fifo_point,
    parse_fifo_points,
    pack_write,
    pack_write8,
    step_from_span,
)


def test_thirty_presets():
    assert len(PRESETS) == 30
    assert get_preset("litevna_full") is not None
    assert get_preset("hf_dipole_20m").start_hz == 14_000_000


def test_i18n_pl_en():
    set_language("en")
    assert "Connect" in t("connect")
    set_language("pl")
    assert "Połącz" in t("connect")
    set_language("en")


def test_protocol_packing():
    assert pack_write(0x40, 5) == bytes([0x20, 0x40, 0x05])
    pkt = pack_write8(0x00, 1_000_000)
    assert pkt[0] == 0x23 and pkt[1] == 0x00
    assert struct.unpack("<Q", pkt[2:])[0] == 1_000_000


def test_fifo_parse():
    raw = struct.pack(
        "<iiiiiiH6s",
        1000,
        0,
        100,
        0,
        50,
        0,
        3,
        b"\x00" * 6,
    )
    assert len(raw) == FIFO_POINT_SIZE
    p = parse_fifo_point(raw)
    assert p.freq_index == 3
    assert abs(p.s11 - 0.1) < 1e-9
    assert abs(p.s21 - 0.05) < 1e-9
    pts = parse_fifo_points(raw * 2)
    assert len(pts) == 2


def test_step_from_span():
    assert step_from_span(0, 100, 11) == 10


def test_swr_and_impedance():
    gamma = impedance_to_reflection(50 + 0j)
    assert abs(gamma) < 1e-9
    assert float(swr(gamma)) == pytest.approx(1.0, abs=1e-6)
    z = reflection_to_impedance(0j)
    assert abs(z - 50) < 1e-6


def test_demo_sweep_finds_resonance():
    demo = DemoDevice(resonance_hz=14_200_000, q=50)
    demo.connect()
    data = demo.read_sweep(
        SweepSettings(start_hz=13_000_000, stop_hz=15_000_000, points=201)
    )
    f, s = find_min_swr(data)
    assert abs(f - 14_200_000) < 100_000
    assert s < 1.5


def test_trace_formats():
    freqs = np.linspace(1e6, 30e6, 51)
    s11 = impedance_to_reflection(50 + 1j * (freqs / 1e6 - 14))
    data = SweepData(freqs, s11, np.ones_like(s11) * 0.9)
    for fmt in TraceFormat:
        x, y = format_trace(data, Channel.S11, fmt)
        assert len(x) == len(y)


def test_tdr():
    freqs = np.linspace(50e3, 100e6, 128)
    s11 = np.exp(-1j * 2 * np.pi * freqs * 20e-9) * 0.5
    data = SweepData(freqs, s11, s11)
    dist, resp = tdr_transform(data, Channel.S11, TdrMode.BANDPASS)
    assert len(dist) > 0 and len(resp) == len(dist)


def test_calibration_improves_match(tmp_path: Path):
    freqs = np.linspace(1e6, 30e6, 101)
    # Systematic error: directivity offset
    err = 0.05 + 0.02j
    open_m = np.full_like(freqs, 1.0 + err, dtype=complex)
    short_m = np.full_like(freqs, -1.0 + err, dtype=complex)
    load_m = np.full_like(freqs, 0.0 + err, dtype=complex)

    cal = CalibrationProfile()
    cal.set_step(CalStep.OPEN, SweepData(freqs, open_m, open_m))
    cal.set_step(CalStep.SHORT, SweepData(freqs, short_m, short_m))
    cal.set_step(CalStep.LOAD, SweepData(freqs, load_m, load_m))

    # DUT is perfect load but measured with same error
    measured = SweepData(freqs, load_m.copy(), load_m.copy())
    corrected = cal.apply(measured)
    assert np.max(np.abs(corrected.s11)) < 0.05

    path = tmp_path / "cal.json"
    cal.save(path)
    loaded = CalibrationProfile.load(path)
    assert loaded.has_reflection()


def test_export(tmp_path: Path):
    demo = DemoDevice()
    data = demo.read_sweep(SweepSettings(points=21))
    s1p = tmp_path / "a.s1p"
    s2p = tmp_path / "a.s2p"
    csv = tmp_path / "a.csv"
    export_s1p(s1p, data)
    export_s2p(s2p, data)
    export_csv(csv, data)
    assert "Hz S RI" in s1p.read_text()
    assert len(s2p.read_text().splitlines()) > 5
    assert "swr" in csv.read_text().splitlines()[0]
