"""Application entry point."""

from __future__ import annotations

import os
import sys


def main() -> int:
    # Prefer native macOS look; allow offscreen for tests
    if os.environ.get("QT_QPA_PLATFORM") is None and sys.platform.startswith("linux"):
        # Keep default on Linux CI; macOS uses cocoa
        pass

    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont

    # High-DPI
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("LiteVNA Studio")
    app.setOrganizationName("LiteVNAStudio")
    app.setApplicationVersion("1.0.0")

    # Prefer expressive, non-default stack on macOS
    if sys.platform == "darwin":
        app.setFont(QFont("Avenir Next", 13))
    else:
        app.setFont(QFont("Helvetica Neue", 12))

    from litevna.ui.main_window import MainWindow

    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
