"""
Ultra PDF Editor - Alternative Entry Point
"""
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from ui.main_window import MainWindow
from Ultra_PDF_Editor import apply_dark_theme


def main():
    """Launch Ultra PDF Editor"""
    # Enable high DPI scaling
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Ultra PDF Editor")
    app.setOrganizationName("UltraPDF")

    # Apply dark theme by default
    apply_dark_theme(app)

    # Create and show main window
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
