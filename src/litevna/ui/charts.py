"""pyqtgraph chart widgets for Cartesian, Smith, and TDR plots."""

from __future__ import annotations

import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import QVBoxLayout, QWidget

from litevna.analysis import (
    Channel,
    SweepData,
    TdrMode,
    TdrWindow,
    TraceFormat,
    format_trace,
    tdr_transform,
)


pg.setConfigOptions(antialias=True, background="#1a1d23", foreground="#d8dde6")


class TraceCanvas(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.plot = pg.PlotWidget()
        layout.addWidget(self.plot)
        self.curve = self.plot.plot(pen=pg.mkPen("#3db8a0", width=2))
        self.marker_items: list[pg.ScatterPlotItem] = []
        self._smith_guides_added = False
        self.plot.showGrid(x=True, y=True, alpha=0.25)

    def clear_markers(self) -> None:
        for item in self.marker_items:
            self.plot.removeItem(item)
        self.marker_items.clear()

    def set_markers(self, xs: list[float], ys: list[float], labels: list[str]) -> None:
        self.clear_markers()
        if not xs:
            return
        scatter = pg.ScatterPlotItem(
            x=xs,
            y=ys,
            size=10,
            brush=pg.mkBrush("#e8a03c"),
            pen=pg.mkPen("#fff", width=1),
        )
        self.plot.addItem(scatter)
        self.marker_items.append(scatter)
        for x, y, label in zip(xs, ys, labels):
            text = pg.TextItem(label, color="#e8a03c", anchor=(0.5, 1.4))
            text.setPos(x, y)
            self.plot.addItem(text)
            self.marker_items.append(text)

    def _ensure_smith_guides(self) -> None:
        if self._smith_guides_added:
            return
        # Unit circle
        theta = np.linspace(0, 2 * np.pi, 256)
        self.plot.plot(np.cos(theta), np.sin(theta), pen=pg.mkPen("#5a6474", width=1))
        # Constant resistance circles (r=0.2, 0.5, 1, 2)
        for r in (0.2, 0.5, 1.0, 2.0):
            center = r / (1 + r)
            radius = 1 / (1 + r)
            ang = np.linspace(0, 2 * np.pi, 128)
            self.plot.plot(
                center + radius * np.cos(ang),
                radius * np.sin(ang),
                pen=pg.mkPen("#3a4250", width=1),
            )
        self.plot.setAspectLocked(True, ratio=1)
        self.plot.setXRange(-1.05, 1.05)
        self.plot.setYRange(-1.05, 1.05)
        self._smith_guides_added = True

    def update_trace(
        self,
        data: SweepData | None,
        channel: Channel,
        fmt: TraceFormat,
        z0: float = 50.0,
        markers_hz: list[float] | None = None,
        tdr_mode: TdrMode = TdrMode.OFF,
        tdr_window: TdrWindow = TdrWindow.NORMAL,
        velocity_factor: float = 0.66,
    ) -> None:
        self.clear_markers()
        if data is None or len(data.frequencies_hz) == 0:
            self.curve.setData([], [])
            return

        if tdr_mode != TdrMode.OFF:
            self._smith_guides_added = False
            self.plot.setAspectLocked(False)
            x, y = tdr_transform(data, channel, tdr_mode, tdr_window, velocity_factor)
            self.curve.setData(x, y)
            self.plot.setLabel("bottom", "Distance", units="m")
            self.plot.setLabel("left", "Response")
            return

        x, y = format_trace(data, channel, fmt, z0)

        if fmt in (TraceFormat.SMITH, TraceFormat.POLAR):
            self._ensure_smith_guides()
            self.curve.setData(x, y)
            self.plot.setLabel("bottom", "Real")
            self.plot.setLabel("left", "Imag")
            if markers_hz:
                # Map marker frequencies to nearest S-parameter points
                s = data.channel(channel)
                xs, ys, labels = [], [], []
                for i, f in enumerate(markers_hz):
                    idx = int(np.argmin(np.abs(data.frequencies_hz - f)))
                    xs.append(float(np.real(s[idx])))
                    ys.append(float(np.imag(s[idx])))
                    labels.append(f"M{i + 1}")
                self.set_markers(xs, ys, labels)
            return

        self._smith_guides_added = False
        self.plot.setAspectLocked(False)
        self.curve.setData(x, y)
        self.plot.setLabel("bottom", "Frequency", units="Hz")
        ylabel = {
            TraceFormat.LOGMAG: "dB",
            TraceFormat.PHASE: "deg",
            TraceFormat.DELAY: "ns",
            TraceFormat.SWR: "SWR",
            TraceFormat.LINEAR: "|S|",
            TraceFormat.REAL: "Real",
            TraceFormat.IMAG: "Imag",
            TraceFormat.RESISTANCE: "Ω",
            TraceFormat.REACTANCE: "Ω",
        }.get(fmt, "")
        self.plot.setLabel("left", ylabel)

        if markers_hz:
            xs, ys, labels = [], [], []
            for i, f in enumerate(markers_hz):
                idx = int(np.argmin(np.abs(x - f)))
                xs.append(float(x[idx]))
                ys.append(float(y[idx]))
                labels.append(f"M{i + 1}")
            self.set_markers(xs, ys, labels)
