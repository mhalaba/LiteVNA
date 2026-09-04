"""Main application window."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import QSettings, QThread, QTimer, Signal, Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from litevna.analysis import (
    Channel,
    SweepData,
    TdrMode,
    TdrWindow,
    TraceFormat,
    electrical_delay_apply,
    find_min_swr,
    reflection_to_impedance,
    swr,
)
from litevna.calibration import CalStep, CalibrationProfile
from litevna.device import DemoDevice, DeviceLike, LiteVNADevice, SweepSettings, list_serial_ports
from litevna.export import export_csv, export_s1p, export_s2p
from litevna.i18n import available_languages, get_language, set_language, t
from litevna.presets import PRESETS
from litevna.protocol import ChannelSelect, RawSamplesMode
from litevna.ui.charts import TraceCanvas


class SweepWorker(QThread):
    finished_ok = Signal(object)
    failed = Signal(str)
    progress = Signal(float)

    def __init__(self, device: DeviceLike, settings: SweepSettings):
        super().__init__()
        self.device = device
        self.settings = settings

    def run(self) -> None:
        try:
            data = self.device.read_sweep(self.settings, progress=self.progress.emit)
            self.finished_ok.emit(data)
        except Exception as exc:  # noqa: BLE001
            self.failed.emit(str(exc))


def format_freq(hz: float) -> str:
    ah = abs(hz)
    if ah >= 1e9:
        return f"{hz / 1e9:.6g} GHz"
    if ah >= 1e6:
        return f"{hz / 1e6:.6g} MHz"
    if ah >= 1e3:
        return f"{hz / 1e3:.6g} kHz"
    return f"{hz:.0f} Hz"


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings_store = QSettings("LiteVNAStudio", "LiteVNAStudio")
        lang = self.settings_store.value("language", "en")
        set_language(str(lang))

        self.device: DeviceLike | None = None
        self.sweep_data: SweepData | None = None
        self.calibration = CalibrationProfile()
        self.markers_hz: list[float] = []
        self.worker: SweepWorker | None = None
        self.continuous = False
        self._building = True

        self._build_ui()
        self._apply_styles()
        self.retranslate()
        self.refresh_ports()
        self._building = False

        # Restore last language already applied; load demo by default convenience
        if self.settings_store.value("auto_demo", True, type=bool):
            self.demo_check.setChecked(True)

    def _build_ui(self) -> None:
        self.setMinimumSize(1180, 720)
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setSpacing(12)
        root.setContentsMargins(12, 12, 12, 12)

        left = QVBoxLayout()
        left.setSpacing(10)
        root.addLayout(left, 0)

        # Connection
        self.conn_box = QGroupBox()
        conn_form = QFormLayout(self.conn_box)
        self.port_combo = QComboBox()
        self.refresh_btn = QPushButton()
        self.connect_btn = QPushButton()
        self.demo_check = QCheckBox()
        port_row = QHBoxLayout()
        port_row.addWidget(self.port_combo, 1)
        port_row.addWidget(self.refresh_btn)
        conn_form.addRow(self._label_ref("port_label", ""), port_row)
        conn_form.addRow(self.demo_check)
        conn_form.addRow(self.connect_btn)
        self.device_label = QLabel("—")
        self.battery_label = QLabel("—")
        conn_form.addRow(self._label_ref("device_lbl", ""), self.device_label)
        conn_form.addRow(self._label_ref("battery_lbl", ""), self.battery_label)
        left.addWidget(self.conn_box)

        # Language
        self.lang_combo = QComboBox()
        for code, name in available_languages():
            self.lang_combo.addItem(name, code)
        idx = self.lang_combo.findData(get_language())
        if idx >= 0:
            self.lang_combo.setCurrentIndex(idx)
        left.addWidget(self.lang_combo)

        # Stimulus
        self.stim_box = QGroupBox()
        stim = QGridLayout(self.stim_box)
        self.start_spin = self._freq_spin()
        self.stop_spin = self._freq_spin()
        self.center_spin = self._freq_spin()
        self.span_spin = self._freq_spin()
        self.points_spin = QSpinBox()
        self.points_spin.setRange(1, 65535)
        self.points_spin.setValue(201)
        self.avg_spin = QSpinBox()
        self.avg_spin.setRange(1, 80)
        self.avg_spin.setValue(2)
        self.lf_spin = QSpinBox()
        self.lf_spin.setRange(1, 3)
        self.lf_spin.setValue(1)
        self.hf_spin = QSpinBox()
        self.hf_spin.setRange(1, 3)
        self.hf_spin.setValue(3)
        self.vpf_spin = QSpinBox()
        self.vpf_spin.setRange(1, 255)
        self.vpf_spin.setValue(1)
        self.channel_combo = QComboBox()
        self.mode_combo = QComboBox()

        self.start_spin.setValue(1_000_000)
        self.stop_spin.setValue(30_000_000)
        self._sync_center_span_from_start_stop()

        r = 0
        stim.addWidget(self._label_ref("start_lbl", ""), r, 0)
        stim.addWidget(self.start_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("stop_lbl", ""), r, 0)
        stim.addWidget(self.stop_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("center_lbl", ""), r, 0)
        stim.addWidget(self.center_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("span_lbl", ""), r, 0)
        stim.addWidget(self.span_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("points_lbl", ""), r, 0)
        stim.addWidget(self.points_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("avg_lbl", ""), r, 0)
        stim.addWidget(self.avg_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("lf_lbl", ""), r, 0)
        stim.addWidget(self.lf_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("hf_lbl", ""), r, 0)
        stim.addWidget(self.hf_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("vpf_lbl", ""), r, 0)
        stim.addWidget(self.vpf_spin, r, 1)
        r += 1
        stim.addWidget(self._label_ref("ch_lbl", ""), r, 0)
        stim.addWidget(self.channel_combo, r, 1)
        r += 1
        stim.addWidget(self._label_ref("mode_lbl", ""), r, 0)
        stim.addWidget(self.mode_combo, r, 1)
        left.addWidget(self.stim_box)

        # Sweep controls
        sweep_row = QHBoxLayout()
        self.single_btn = QPushButton()
        self.cont_btn = QPushButton()
        self.pause_btn = QPushButton()
        self.pause_btn.setEnabled(False)
        sweep_row.addWidget(self.single_btn)
        sweep_row.addWidget(self.cont_btn)
        sweep_row.addWidget(self.pause_btn)
        left.addLayout(sweep_row)

        # Presets
        self.preset_box = QGroupBox()
        preset_l = QVBoxLayout(self.preset_box)
        self.preset_combo = QComboBox()
        self.apply_preset_btn = QPushButton()
        preset_l.addWidget(self.preset_combo)
        preset_l.addWidget(self.apply_preset_btn)
        left.addWidget(self.preset_box)

        left.addStretch(1)

        # Right side: charts + controls
        right = QVBoxLayout()
        root.addLayout(right, 1)

        top_bar = QHBoxLayout()
        self.format_combo = QComboBox()
        self.trace_channel_combo = QComboBox()
        self.z0_spin = QDoubleSpinBox()
        self.z0_spin.setRange(1, 1000)
        self.z0_spin.setValue(50)
        self.delay_spin = QDoubleSpinBox()
        self.delay_spin.setRange(-1e6, 1e6)
        self.delay_spin.setDecimals(1)
        self.delay_spin.setValue(0)
        self.delay_spin.setSuffix(" ps")
        top_bar.addWidget(self._label_ref("fmt_lbl", ""))
        top_bar.addWidget(self.format_combo)
        top_bar.addWidget(self._label_ref("tr_ch_lbl", ""))
        top_bar.addWidget(self.trace_channel_combo)
        top_bar.addWidget(self._label_ref("z0_lbl", ""))
        top_bar.addWidget(self.z0_spin)
        top_bar.addWidget(self._label_ref("edelay_lbl", ""))
        top_bar.addWidget(self.delay_spin)
        top_bar.addStretch(1)
        right.addLayout(top_bar)

        self.canvas = TraceCanvas()
        right.addWidget(self.canvas, 1)

        self.info_label = QLabel("")
        self.info_label.setObjectName("infoLabel")
        right.addWidget(self.info_label)

        # Markers / Cal / TDR / Export
        tools = QHBoxLayout()
        right.addLayout(tools)

        self.marker_box = QGroupBox()
        mb = QVBoxLayout(self.marker_box)
        self.add_marker_btn = QPushButton()
        self.clear_marker_btn = QPushButton()
        self.marker_info = QLabel("")
        mb.addWidget(self.add_marker_btn)
        mb.addWidget(self.clear_marker_btn)
        mb.addWidget(self.marker_info)
        tools.addWidget(self.marker_box)

        self.cal_box = QGroupBox()
        cb = QGridLayout(self.cal_box)
        self.cal_open_btn = QPushButton()
        self.cal_short_btn = QPushButton()
        self.cal_load_btn = QPushButton()
        self.cal_isol_btn = QPushButton()
        self.cal_thru_btn = QPushButton()
        self.cal_reset_btn = QPushButton()
        self.cal_save_btn = QPushButton()
        self.cal_loadfile_btn = QPushButton()
        self.cal_enable = QCheckBox()
        self.cal_enable.setChecked(True)
        for i, btn in enumerate(
            [
                self.cal_open_btn,
                self.cal_short_btn,
                self.cal_load_btn,
                self.cal_isol_btn,
                self.cal_thru_btn,
            ]
        ):
            cb.addWidget(btn, i // 3, i % 3)
        cb.addWidget(self.cal_reset_btn, 1, 2)
        cb.addWidget(self.cal_save_btn, 2, 0)
        cb.addWidget(self.cal_loadfile_btn, 2, 1)
        cb.addWidget(self.cal_enable, 2, 2)
        tools.addWidget(self.cal_box)

        self.tdr_box = QGroupBox()
        tb = QFormLayout(self.tdr_box)
        self.tdr_mode_combo = QComboBox()
        self.tdr_window_combo = QComboBox()
        self.vf_spin = QDoubleSpinBox()
        self.vf_spin.setRange(0.1, 1.0)
        self.vf_spin.setSingleStep(0.01)
        self.vf_spin.setValue(0.66)
        tb.addRow(self._label_ref("tdr_mode_lbl", ""), self.tdr_mode_combo)
        tb.addRow(self._label_ref("tdr_win_lbl", ""), self.tdr_window_combo)
        tb.addRow(self._label_ref("vf_lbl", ""), self.vf_spin)
        tools.addWidget(self.tdr_box)

        self.export_box = QGroupBox()
        eb = QVBoxLayout(self.export_box)
        self.export_s1p_btn = QPushButton()
        self.export_s2p_btn = QPushButton()
        self.export_csv_btn = QPushButton()
        self.screenshot_btn = QPushButton()
        self.sync_time_btn = QPushButton()
        for b in (
            self.export_s1p_btn,
            self.export_s2p_btn,
            self.export_csv_btn,
            self.screenshot_btn,
            self.sync_time_btn,
        ):
            eb.addWidget(b)
        tools.addWidget(self.export_box)

        self.setStatusBar(QStatusBar())
        self.statusBar().showMessage("")

        # Menu
        about = QAction(self)
        about.triggered.connect(self.show_about)
        self.about_action = about
        self.menuBar().addAction(about)

        # Signals
        self.refresh_btn.clicked.connect(self.refresh_ports)
        self.connect_btn.clicked.connect(self.toggle_connect)
        self.demo_check.toggled.connect(self.on_demo_toggled)
        self.lang_combo.currentIndexChanged.connect(self.on_language_changed)
        self.start_spin.valueChanged.connect(self._on_start_stop_changed)
        self.stop_spin.valueChanged.connect(self._on_start_stop_changed)
        self.center_spin.valueChanged.connect(self._on_center_span_changed)
        self.span_spin.valueChanged.connect(self._on_center_span_changed)
        self.single_btn.clicked.connect(self.run_single)
        self.cont_btn.clicked.connect(self.run_continuous)
        self.pause_btn.clicked.connect(self.pause_sweep)
        self.apply_preset_btn.clicked.connect(self.apply_preset)
        self.format_combo.currentIndexChanged.connect(self.refresh_plot)
        self.trace_channel_combo.currentIndexChanged.connect(self.refresh_plot)
        self.z0_spin.valueChanged.connect(self.refresh_plot)
        self.delay_spin.valueChanged.connect(self.refresh_plot)
        self.tdr_mode_combo.currentIndexChanged.connect(self.refresh_plot)
        self.tdr_window_combo.currentIndexChanged.connect(self.refresh_plot)
        self.vf_spin.valueChanged.connect(self.refresh_plot)
        self.add_marker_btn.clicked.connect(self.add_marker)
        self.clear_marker_btn.clicked.connect(self.clear_markers)
        self.cal_open_btn.clicked.connect(lambda: self.run_cal_step(CalStep.OPEN))
        self.cal_short_btn.clicked.connect(lambda: self.run_cal_step(CalStep.SHORT))
        self.cal_load_btn.clicked.connect(lambda: self.run_cal_step(CalStep.LOAD))
        self.cal_isol_btn.clicked.connect(lambda: self.run_cal_step(CalStep.ISOLATION))
        self.cal_thru_btn.clicked.connect(lambda: self.run_cal_step(CalStep.THRU))
        self.cal_reset_btn.clicked.connect(self.reset_calibration)
        self.cal_save_btn.clicked.connect(self.save_calibration)
        self.cal_loadfile_btn.clicked.connect(self.load_calibration)
        self.cal_enable.toggled.connect(self.on_cal_enable)
        self.export_s1p_btn.clicked.connect(lambda: self.export_file("s1p"))
        self.export_s2p_btn.clicked.connect(lambda: self.export_file("s2p"))
        self.export_csv_btn.clicked.connect(lambda: self.export_file("csv"))
        self.screenshot_btn.clicked.connect(self.take_screenshot)
        self.sync_time_btn.clicked.connect(self.sync_time)

    def _label_ref(self, attr: str, text: str) -> QLabel:
        lbl = QLabel(text)
        setattr(self, attr, lbl)
        return lbl

    def _freq_spin(self) -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setRange(50_000, 6_300_000_000)
        spin.setDecimals(0)
        spin.setSingleStep(100_000)
        spin.setGroupSeparatorShown(True)
        return spin

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow, QWidget {
                background: #f3f1ec;
                color: #1c2430;
                font-family: "Avenir Next", "Helvetica Neue", "Segoe UI", sans-serif;
                font-size: 13px;
            }
            QGroupBox {
                background: #ffffff;
                border: 1px solid #d5d0c8;
                border-radius: 8px;
                margin-top: 12px;
                padding: 10px 8px 8px 8px;
                font-weight: 600;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 4px;
                color: #2a5f55;
            }
            QPushButton {
                background: #2f6f63;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 7px 12px;
                font-weight: 600;
            }
            QPushButton:hover { background: #3a8576; }
            QPushButton:disabled { background: #9aa7a3; }
            QComboBox, QSpinBox, QDoubleSpinBox {
                background: #fff;
                border: 1px solid #cfc8bc;
                border-radius: 5px;
                padding: 4px 6px;
                min-height: 24px;
            }
            QStatusBar { background: #e8e4dc; }
            #infoLabel {
                font-family: "IBM Plex Mono", "SF Mono", Menlo, monospace;
                font-size: 12px;
                color: #243447;
                padding: 6px;
                background: #ebe6dd;
                border-radius: 6px;
            }
            """
        )

    def retranslate(self) -> None:
        self.setWindowTitle(t("app_title"))
        self.conn_box.setTitle(t("connect") + " / " + t("disconnect"))
        self.port_label.setText(t("port"))
        self.refresh_btn.setText(t("refresh_ports"))
        self.demo_check.setText(t("demo_mode"))
        self._update_connect_button()
        self.device_lbl.setText(t("device_info"))
        self.battery_lbl.setText(t("battery"))
        self.stim_box.setTitle(t("stimulus"))
        self.start_lbl.setText(t("start") + " (Hz)")
        self.stop_lbl.setText(t("stop") + " (Hz)")
        self.center_lbl.setText(t("center") + " (Hz)")
        self.span_lbl.setText(t("span") + " (Hz)")
        self.points_lbl.setText(t("points"))
        self.avg_lbl.setText(t("average"))
        self.lf_lbl.setText(t("lf_power"))
        self.hf_lbl.setText(t("hf_power"))
        self.vpf_lbl.setText(t("values_per_freq"))
        self.ch_lbl.setText(t("channel"))
        self.mode_lbl.setText(t("data_mode"))
        self.single_btn.setText(t("single_sweep"))
        self.cont_btn.setText(t("continuous"))
        self.pause_btn.setText(t("pause"))
        self.preset_box.setTitle(t("presets"))
        self.apply_preset_btn.setText(t("apply_preset"))
        self.fmt_lbl.setText(t("format"))
        self.tr_ch_lbl.setText(t("channel"))
        self.z0_lbl.setText(t("z0"))
        self.edelay_lbl.setText(t("electrical_delay"))
        self.marker_box.setTitle(t("markers"))
        self.add_marker_btn.setText(t("add_marker"))
        self.clear_marker_btn.setText(t("clear_markers"))
        self.cal_box.setTitle(t("calibration"))
        self.cal_open_btn.setText(t("cal_open"))
        self.cal_short_btn.setText(t("cal_short"))
        self.cal_load_btn.setText(t("cal_load"))
        self.cal_isol_btn.setText(t("cal_isolation"))
        self.cal_thru_btn.setText(t("cal_thru"))
        self.cal_reset_btn.setText(t("cal_reset"))
        self.cal_save_btn.setText(t("cal_save"))
        self.cal_loadfile_btn.setText(t("cal_load_file"))
        self.cal_enable.setText(t("cal_enabled"))
        self.tdr_box.setTitle(t("tdr"))
        self.tdr_mode_lbl.setText(t("tdr_mode"))
        self.tdr_win_lbl.setText(t("tdr_window"))
        self.vf_lbl.setText(t("velocity_factor"))
        self.export_box.setTitle(t("export"))
        self.export_s1p_btn.setText(t("export_s1p"))
        self.export_s2p_btn.setText(t("export_s2p"))
        self.export_csv_btn.setText(t("export_csv"))
        self.screenshot_btn.setText(t("screenshot"))
        self.sync_time_btn.setText(t("set_time"))
        self.about_action.setText(t("about"))
        self.statusBar().showMessage(t("status_ready"))

        # refill combos preserving selection where possible
        self._refill_channel_combo()
        self._refill_mode_combo()
        self._refill_format_combo()
        self._refill_trace_channel_combo()
        self._refill_tdr_combos()
        self._refill_presets()

    def _refill_channel_combo(self) -> None:
        cur = self.channel_combo.currentData()
        self.channel_combo.blockSignals(True)
        self.channel_combo.clear()
        self.channel_combo.addItem(t("channel_both"), ChannelSelect.BOTH)
        self.channel_combo.addItem(t("channel_s11"), ChannelSelect.S11)
        self.channel_combo.addItem(t("channel_s21"), ChannelSelect.S21)
        if cur is not None:
            i = self.channel_combo.findData(cur)
            if i >= 0:
                self.channel_combo.setCurrentIndex(i)
        self.channel_combo.blockSignals(False)

    def _refill_mode_combo(self) -> None:
        cur = self.mode_combo.currentData()
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItem(t("mode_usb"), RawSamplesMode.USB)
        self.mode_combo.addItem(t("mode_calibrated"), RawSamplesMode.CALIBRATED)
        if cur is not None:
            i = self.mode_combo.findData(cur)
            if i >= 0:
                self.mode_combo.setCurrentIndex(i)
        self.mode_combo.blockSignals(False)

    def _refill_format_combo(self) -> None:
        cur = self.format_combo.currentData()
        mapping = [
            (t("trace_logmag"), TraceFormat.LOGMAG),
            (t("trace_swr"), TraceFormat.SWR),
            (t("trace_smith"), TraceFormat.SMITH),
            (t("trace_phase"), TraceFormat.PHASE),
            (t("trace_delay"), TraceFormat.DELAY),
            (t("trace_polar"), TraceFormat.POLAR),
            (t("trace_linear"), TraceFormat.LINEAR),
            (t("trace_real"), TraceFormat.REAL),
            (t("trace_imag"), TraceFormat.IMAG),
            (t("trace_resistance"), TraceFormat.RESISTANCE),
            (t("trace_reactance"), TraceFormat.REACTANCE),
        ]
        self.format_combo.blockSignals(True)
        self.format_combo.clear()
        for name, fmt in mapping:
            self.format_combo.addItem(name, fmt)
        if cur is not None:
            i = self.format_combo.findData(cur)
            if i >= 0:
                self.format_combo.setCurrentIndex(i)
        else:
            self.format_combo.setCurrentIndex(1)  # SWR default
        self.format_combo.blockSignals(False)

    def _refill_trace_channel_combo(self) -> None:
        cur = self.trace_channel_combo.currentData()
        self.trace_channel_combo.blockSignals(True)
        self.trace_channel_combo.clear()
        self.trace_channel_combo.addItem("S11", Channel.S11)
        self.trace_channel_combo.addItem("S21", Channel.S21)
        if cur is not None:
            i = self.trace_channel_combo.findData(cur)
            if i >= 0:
                self.trace_channel_combo.setCurrentIndex(i)
        self.trace_channel_combo.blockSignals(False)

    def _refill_tdr_combos(self) -> None:
        cur_m = self.tdr_mode_combo.currentData()
        cur_w = self.tdr_window_combo.currentData()
        self.tdr_mode_combo.blockSignals(True)
        self.tdr_mode_combo.clear()
        self.tdr_mode_combo.addItem(t("tdr_off"), TdrMode.OFF)
        self.tdr_mode_combo.addItem(t("tdr_bandpass"), TdrMode.BANDPASS)
        self.tdr_mode_combo.addItem(t("tdr_impulse"), TdrMode.LOWPASS_IMPULSE)
        self.tdr_mode_combo.addItem(t("tdr_step"), TdrMode.LOWPASS_STEP)
        if cur_m is not None:
            i = self.tdr_mode_combo.findData(cur_m)
            if i >= 0:
                self.tdr_mode_combo.setCurrentIndex(i)
        self.tdr_mode_combo.blockSignals(False)

        self.tdr_window_combo.blockSignals(True)
        self.tdr_window_combo.clear()
        self.tdr_window_combo.addItem("Minimum", TdrWindow.MINIMUM)
        self.tdr_window_combo.addItem("Normal", TdrWindow.NORMAL)
        self.tdr_window_combo.addItem("Maximum", TdrWindow.MAXIMUM)
        if cur_w is not None:
            i = self.tdr_window_combo.findData(cur_w)
            if i >= 0:
                self.tdr_window_combo.setCurrentIndex(i)
        else:
            self.tdr_window_combo.setCurrentIndex(1)
        self.tdr_window_combo.blockSignals(False)

    def _refill_presets(self) -> None:
        cur = self.preset_combo.currentData()
        lang = get_language()
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        for p in PRESETS:
            self.preset_combo.addItem(p.localized_name(lang), p.id)
        if cur is not None:
            i = self.preset_combo.findData(cur)
            if i >= 0:
                self.preset_combo.setCurrentIndex(i)
        self.preset_combo.blockSignals(False)

    def on_language_changed(self) -> None:
        if self._building:
            return
        code = self.lang_combo.currentData()
        set_language(str(code))
        self.settings_store.setValue("language", code)
        self.retranslate()
        self.refresh_plot()

    def refresh_ports(self) -> None:
        current = self.port_combo.currentData()
        self.port_combo.clear()
        ports = list_serial_ports()
        for p in ports:
            label = f"{p['device']} — {p['description']}"
            self.port_combo.addItem(label, p["device"])
        if current:
            i = self.port_combo.findData(current)
            if i >= 0:
                self.port_combo.setCurrentIndex(i)

    def on_demo_toggled(self, checked: bool) -> None:
        self.port_combo.setEnabled(not checked)
        self.refresh_btn.setEnabled(not checked)

    def _update_connect_button(self) -> None:
        if self.device and self.device.connected:
            self.connect_btn.setText(t("disconnect"))
        else:
            self.connect_btn.setText(t("connect"))

    def toggle_connect(self) -> None:
        if self.device and self.device.connected:
            self.pause_sweep()
            self.device.disconnect()
            self.device = None
            self.device_label.setText("—")
            self.battery_label.setText("—")
            self._update_connect_button()
            self.statusBar().showMessage(t("disconnected"))
            return

        try:
            if self.demo_check.isChecked():
                self.device = DemoDevice()
            else:
                port = self.port_combo.currentData()
                if not port:
                    raise RuntimeError("No serial port selected")
                self.device = LiteVNADevice(str(port))
            info = self.device.connect()
            self.device_label.setText(
                f"LiteVNA HW{info.hardware_revision} FW {info.firmware}"
            )
            if info.battery_mv is not None:
                self.battery_label.setText(f"{info.battery_mv} mV")
            else:
                self.battery_label.setText("—")
            self._update_connect_button()
            self.statusBar().showMessage(t("connected"))
        except Exception as exc:  # noqa: BLE001
            self.device = None
            QMessageBox.critical(self, t("error"), str(exc))

    def current_settings(self) -> SweepSettings:
        ch = self.channel_combo.currentData() or ChannelSelect.BOTH
        mode = self.mode_combo.currentData() or RawSamplesMode.USB
        return SweepSettings(
            start_hz=int(self.start_spin.value()),
            stop_hz=int(self.stop_spin.value()),
            points=int(self.points_spin.value()),
            average=int(self.avg_spin.value()),
            lf_power=int(self.lf_spin.value()),
            hf_power=int(self.hf_spin.value()),
            channel=ch,
            values_per_frequency=int(self.vpf_spin.value()),
            mode=mode,
        )

    def _on_start_stop_changed(self) -> None:
        if self._building:
            return
        self._building = True
        self._sync_center_span_from_start_stop()
        self._building = False

    def _on_center_span_changed(self) -> None:
        if self._building:
            return
        self._building = True
        center = self.center_spin.value()
        span = max(0, self.span_spin.value())
        self.start_spin.setValue(max(50_000, center - span / 2))
        self.stop_spin.setValue(min(6_300_000_000, center + span / 2))
        self._building = False

    def _sync_center_span_from_start_stop(self) -> None:
        start = self.start_spin.value()
        stop = self.stop_spin.value()
        self.center_spin.setValue((start + stop) / 2)
        self.span_spin.setValue(max(0, stop - start))

    def apply_preset(self) -> None:
        from litevna.presets import get_preset

        pid = self.preset_combo.currentData()
        preset = get_preset(str(pid)) if pid else None
        if not preset:
            return
        self._building = True
        self.start_spin.setValue(preset.start_hz)
        self.stop_spin.setValue(preset.stop_hz)
        self.points_spin.setValue(preset.points)
        self.avg_spin.setValue(preset.average)
        self._sync_center_span_from_start_stop()
        self._building = False
        # Tune demo resonance to preset center
        if isinstance(self.device, DemoDevice):
            self.device.resonance_hz = (preset.start_hz + preset.stop_hz) / 2

    def run_single(self) -> None:
        self.continuous = False
        self._start_sweep()

    def run_continuous(self) -> None:
        self.continuous = True
        self.pause_btn.setEnabled(True)
        self._start_sweep()

    def pause_sweep(self) -> None:
        self.continuous = False
        self.pause_btn.setEnabled(False)
        if self.worker and self.worker.isRunning():
            # Let current finish; no hard kill of serial IO
            pass

    def _start_sweep(self, for_cal: CalStep | None = None) -> None:
        if not self.device or not self.device.connected:
            QMessageBox.warning(self, t("error"), t("disconnected"))
            return
        if self.worker and self.worker.isRunning():
            return
        self.statusBar().showMessage(
            t("status_calibrating") if for_cal else t("status_sweeping")
        )
        self.worker = SweepWorker(self.device, self.current_settings())
        self.worker.finished_ok.connect(
            lambda data, step=for_cal: self._on_sweep_done(data, step)
        )
        self.worker.failed.connect(self._on_sweep_failed)
        self.worker.start()

    def _on_sweep_done(self, data: SweepData, cal_step: CalStep | None) -> None:
        if cal_step is not None:
            try:
                self.calibration.set_step(cal_step, data)
                self.statusBar().showMessage(f"{t('calibration')}: {cal_step.value} OK")
            except Exception as exc:  # noqa: BLE001
                QMessageBox.critical(self, t("error"), str(exc))
            return

        self.sweep_data = data
        self.refresh_plot()
        self.statusBar().showMessage(t("status_ready"))
        if self.continuous:
            QTimer.singleShot(50, self._start_sweep)

    def _on_sweep_failed(self, message: str) -> None:
        self.continuous = False
        self.pause_btn.setEnabled(False)
        self.statusBar().showMessage(t("error"))
        QMessageBox.critical(self, t("error"), message)

    def processed_data(self) -> SweepData | None:
        if self.sweep_data is None:
            return None
        data = self.sweep_data
        self.calibration.enabled = self.cal_enable.isChecked()
        data = self.calibration.apply(data)
        delay_s = self.delay_spin.value() * 1e-12
        if abs(delay_s) > 0:
            data = SweepData(
                frequencies_hz=data.frequencies_hz,
                s11=electrical_delay_apply(data.s11, data.frequencies_hz, delay_s),
                s21=electrical_delay_apply(data.s21, data.frequencies_hz, delay_s),
            )
        return data

    def refresh_plot(self) -> None:
        data = self.processed_data()
        channel = self.trace_channel_combo.currentData() or Channel.S11
        fmt = self.format_combo.currentData() or TraceFormat.SWR
        tdr_mode = self.tdr_mode_combo.currentData() or TdrMode.OFF
        tdr_win = self.tdr_window_combo.currentData() or TdrWindow.NORMAL
        self.canvas.update_trace(
            data,
            channel,
            fmt,
            z0=self.z0_spin.value(),
            markers_hz=self.markers_hz,
            tdr_mode=tdr_mode,
            tdr_window=tdr_win,
            velocity_factor=self.vf_spin.value(),
        )
        if data is None:
            self.info_label.setText("")
            return
        f_min, s_min = find_min_swr(data)
        idx = int(np.argmin(np.abs(data.frequencies_hz - f_min)))
        z = reflection_to_impedance(data.s11[idx], self.z0_spin.value())
        self.info_label.setText(
            f"{t('min_swr')}: {s_min:.3f} {t('at')} {format_freq(f_min)}  |  "
            f"Z ≈ {z.real:.1f} {z.imag:+.1f}j Ω  |  points={len(data.frequencies_hz)}"
        )
        self._update_marker_info(data)

    def add_marker(self) -> None:
        data = self.processed_data()
        if data is None:
            return
        if len(self.markers_hz) >= 8:
            return
        # Place at min SWR or mid span
        f, _ = find_min_swr(data)
        if self.markers_hz:
            f = float(np.median(data.frequencies_hz))
        self.markers_hz.append(f)
        self.refresh_plot()

    def clear_markers(self) -> None:
        self.markers_hz.clear()
        self.refresh_plot()

    def _update_marker_info(self, data: SweepData) -> None:
        if not self.markers_hz:
            self.marker_info.setText("")
            return
        lines = []
        for i, f in enumerate(self.markers_hz):
            idx = int(np.argmin(np.abs(data.frequencies_hz - f)))
            s11 = data.s11[idx]
            z = reflection_to_impedance(s11, self.z0_spin.value())
            lines.append(
                f"M{i + 1}: {format_freq(data.frequencies_hz[idx])}  "
                f"SWR {float(swr(s11)):.2f}  "
                f"Z {z.real:.1f}{z.imag:+.1f}j"
            )
        self.marker_info.setText("\n".join(lines))

    def run_cal_step(self, step: CalStep) -> None:
        self._start_sweep(for_cal=step)

    def reset_calibration(self) -> None:
        self.calibration = CalibrationProfile()
        self.refresh_plot()

    def save_calibration(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, t("cal_save"), "calibration.json", "JSON (*.json)"
        )
        if path:
            self.calibration.save(Path(path))

    def load_calibration(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, t("cal_load_file"), "", "JSON (*.json)"
        )
        if path:
            self.calibration = CalibrationProfile.load(Path(path))
            self.cal_enable.setChecked(self.calibration.enabled)
            self.refresh_plot()

    def on_cal_enable(self, checked: bool) -> None:
        self.calibration.enabled = checked
        self.refresh_plot()

    def export_file(self, kind: str) -> None:
        data = self.processed_data()
        if data is None:
            return
        filters = {
            "s1p": "Touchstone S1P (*.s1p)",
            "s2p": "Touchstone S2P (*.s2p)",
            "csv": "CSV (*.csv)",
        }
        path, _ = QFileDialog.getSaveFileName(
            self, t("export"), f"measurement.{kind}", filters[kind]
        )
        if not path:
            return
        p = Path(path)
        z0 = self.z0_spin.value()
        if kind == "s1p":
            export_s1p(p, data, z0)
        elif kind == "s2p":
            export_s2p(p, data, z0)
        else:
            export_csv(p, data, z0)

    def take_screenshot(self) -> None:
        if not self.device or not self.device.connected:
            return
        try:
            blob = self.device.capture_screenshot()
            path, _ = QFileDialog.getSaveFileName(
                self, t("screenshot"), "litevna_screen.bin", "Binary (*.bin);;BMP (*.bmp)"
            )
            if path:
                Path(path).write_bytes(blob)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("error"), str(exc))

    def sync_time(self) -> None:
        if not self.device or not self.device.connected:
            return
        try:
            self.device.set_unix_time()
            self.statusBar().showMessage(t("set_time") + " OK")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, t("error"), str(exc))

    def show_about(self) -> None:
        QMessageBox.about(self, t("about"), t("about_text"))

    def closeEvent(self, event) -> None:  # noqa: N802
        self.continuous = False
        if self.device and self.device.connected:
            self.device.disconnect()
        super().closeEvent(event)
