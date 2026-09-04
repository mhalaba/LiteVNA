"""Headless UI smoke test (requires QT_QPA_PLATFORM=offscreen on CI)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from litevna.i18n import set_language
from litevna.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def test_main_window_opens_and_switches_language(qapp):
    set_language("en")
    win = MainWindow()
    win.show()
    assert win.windowTitle() == "LiteVNA Studio"
    assert win.preset_combo.count() == 30

    # Demo connect + single sweep
    win.demo_check.setChecked(True)
    win.toggle_connect()
    assert win.device is not None
    win.apply_preset()
    win.run_single()
    assert win.worker is not None
    win.worker.wait(10000)
    # Deliver queued finished_ok signal
    qapp.processEvents()
    assert win.sweep_data is not None

    # Switch to Polish
    idx = win.lang_combo.findData("pl")
    win.lang_combo.setCurrentIndex(idx)
    qapp.processEvents()
    assert "Połącz" in win.connect_btn.text() or "Rozłącz" in win.connect_btn.text()
    win.close()
