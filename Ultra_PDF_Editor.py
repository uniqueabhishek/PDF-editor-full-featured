"""
Ultra PDF Editor - Main Application Entry Point
A powerful yet simple PDF editor with all professional features.

Features:
- View, navigate, and zoom PDFs
- Merge, split, rotate, and reorder pages
- Annotations: highlight, underline, shapes, text boxes, stamps
- Text editing and image insertion
- Forms: fill and create fillable forms
- Security: encryption, digital signatures, redaction
- OCR: convert scanned documents to searchable text
- Conversion: PDF to/from Word, Excel, images
- Batch processing for multiple files
- And much more...

Author: Ultra PDF Team
Version: 1.0.0
"""
import sys
import os
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from PyQt6.QtWidgets import QApplication, QSplashScreen, QMessageBox
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QPixmap, QFont, QIcon
import darkdetect

from config import config, UserSettings


def check_dependencies():
    """Check if all required dependencies are installed"""
    missing = []

    try:
        import fitz  # PyMuPDF
    except ImportError:
        missing.append("PyMuPDF")

    try:
        from PyQt6.QtWidgets import QApplication
    except ImportError:
        missing.append("PyQt6")

    try:
        from PIL import Image
    except ImportError:
        missing.append("Pillow")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Please install them using: pip install -r requirements.txt")
        return False

    return True


def setup_application() -> QApplication:
    """Setup and configure the Qt application"""
    # Enable high DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setOrganizationName(config.APP_AUTHOR)

    # Set application style
    app.setStyle("Fusion")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply theme based on system preference
    settings = UserSettings.load(config.SETTINGS_PATH)

    if settings.theme == "dark" or (settings.theme == "system" and darkdetect.isDark()):
        apply_dark_theme(app)
    else:
        apply_light_theme(app)

    return app


def apply_dark_theme(app: QApplication):
    """Apply dark theme to application"""
    dark_stylesheet = """
    QMainWindow {
        background-color: #1e1e1e;
    }
    QWidget {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    QMenuBar {
        background-color: #2d2d2d;
        color: #ffffff;
    }
    QMenuBar::item:selected {
        background-color: #0078d4;
    }
    QMenu {
        background-color: #2d2d2d;
        color: #ffffff;
        border: 1px solid #3d3d3d;
    }
    QMenu::item:selected {
        background-color: #0078d4;
    }
    QToolBar {
        background-color: #2d2d2d;
        border: none;
        spacing: 3px;
        padding: 3px;
    }
    QToolButton {
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px;
    }
    QToolButton:hover {
        background-color: #3d3d3d;
    }
    QToolButton:pressed {
        background-color: #4d4d4d;
    }
    QStatusBar {
        background-color: #007acc;
        color: white;
    }
    QScrollBar:vertical {
        background-color: #2d2d2d;
        width: 12px;
    }
    QScrollBar::handle:vertical {
        background-color: #5d5d5d;
        border-radius: 6px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #7d7d7d;
    }
    QLineEdit, QSpinBox, QComboBox {
        background-color: #3d3d3d;
        border: 1px solid #5d5d5d;
        border-radius: 4px;
        padding: 4px;
        color: white;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
        border-color: #0078d4;
    }
    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
    }
    QPushButton:hover {
        background-color: #1084d8;
    }
    QPushButton:pressed {
        background-color: #006cbd;
    }
    QTabWidget::pane {
        border: 1px solid #3d3d3d;
    }
    QTabBar::tab {
        background-color: #2d2d2d;
        color: #aaa;
        padding: 8px 16px;
    }
    QTabBar::tab:selected {
        background-color: #0078d4;
        color: white;
    }
    QSplitter::handle {
        background-color: #3d3d3d;
    }
    QTreeWidget, QListWidget {
        background-color: #2d2d2d;
        border: none;
    }
    QTreeWidget::item:hover, QListWidget::item:hover {
        background-color: #3d3d3d;
    }
    QTreeWidget::item:selected, QListWidget::item:selected {
        background-color: #0078d4;
    }
    """
    app.setStyleSheet(dark_stylesheet)


def apply_light_theme(app: QApplication):
    """Apply light theme to application"""
    light_stylesheet = """
    QMainWindow {
        background-color: #f5f5f5;
    }
    QMenuBar {
        background-color: #ffffff;
        border-bottom: 1px solid #e0e0e0;
    }
    QMenuBar::item:selected {
        background-color: #e5e5e5;
    }
    QMenu {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
    }
    QMenu::item:selected {
        background-color: #0078d4;
        color: white;
    }
    QToolBar {
        background-color: #f5f5f5;
        border: none;
        border-bottom: 1px solid #e0e0e0;
        spacing: 3px;
        padding: 3px;
    }
    QToolButton {
        background-color: transparent;
        border: none;
        border-radius: 4px;
        padding: 4px;
    }
    QToolButton:hover {
        background-color: #e0e0e0;
    }
    QToolButton:pressed {
        background-color: #d0d0d0;
    }
    QStatusBar {
        background-color: #0078d4;
        color: white;
    }
    QScrollBar:vertical {
        background-color: #f5f5f5;
        width: 12px;
    }
    QScrollBar::handle:vertical {
        background-color: #c0c0c0;
        border-radius: 6px;
        min-height: 30px;
    }
    QScrollBar::handle:vertical:hover {
        background-color: #a0a0a0;
    }
    QLineEdit, QSpinBox, QComboBox {
        background-color: #ffffff;
        border: 1px solid #c0c0c0;
        border-radius: 4px;
        padding: 4px;
    }
    QLineEdit:focus, QSpinBox:focus, QComboBox:focus {
        border-color: #0078d4;
    }
    QPushButton {
        background-color: #0078d4;
        color: white;
        border: none;
        border-radius: 4px;
        padding: 6px 16px;
    }
    QPushButton:hover {
        background-color: #1084d8;
    }
    QPushButton:pressed {
        background-color: #006cbd;
    }
    QTabWidget::pane {
        border: 1px solid #e0e0e0;
        background-color: white;
    }
    QTabBar::tab {
        background-color: #f5f5f5;
        padding: 8px 16px;
    }
    QTabBar::tab:selected {
        background-color: #0078d4;
        color: white;
    }
    QSplitter::handle {
        background-color: #e0e0e0;
    }
    """
    app.setStyleSheet(light_stylesheet)


def main():
    """Main entry point"""
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Create application
    app = setup_application()

    # Import main window (after app is created)
    from ui.main_window import MainWindow

    # Create and show main window
    window = MainWindow()
    window.show()

    # Handle command line arguments (open file if provided)
    if len(sys.argv) > 1:
        filepath = sys.argv[1]
        if os.path.exists(filepath) and filepath.lower().endswith('.pdf'):
            window._open_file(filepath)

    # Run application
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
