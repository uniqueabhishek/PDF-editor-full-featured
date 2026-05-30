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
import importlib.util
import os
import sys
from pathlib import Path

# Add the project root to the path before importing local modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_dependencies():
    """Check if all required dependencies are installed"""
    missing = []

    if importlib.util.find_spec("fitz") is None:
        missing.append("PyMuPDF")

    if importlib.util.find_spec("PyQt6") is None:
        missing.append("PyQt6")

    if importlib.util.find_spec("PIL") is None:
        missing.append("Pillow")

    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Please install them using: uv sync")
        return False

    return True


def setup_application():
    """Setup and configure the Qt application"""
    # Import here after path setup and dependency check
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtGui import QFont
    import darkdetect

    from config import config, UserSettings

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


STYLES_DIR = Path(__file__).parent / "resources" / "styles"


def _load_stylesheet(filename: str) -> str:
    """Load a Qt stylesheet from resources/styles.

    Returns an empty string (falls back to the Fusion default) if the file is
    missing or unreadable, so a missing resource never crashes startup.
    """
    try:
        return (STYLES_DIR / filename).read_text(encoding="utf-8")
    except OSError as e:
        print(f"Warning: could not load stylesheet '{filename}': {e}")
        return ""


def apply_dark_theme(app):
    """Apply dark theme to application"""
    app.setStyleSheet(_load_stylesheet("dark_theme.qss"))


def apply_light_theme(app):
    """Apply light theme to application"""
    app.setStyleSheet(_load_stylesheet("light_theme.qss"))


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
