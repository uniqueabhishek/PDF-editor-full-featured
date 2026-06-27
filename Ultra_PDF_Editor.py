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
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Add the project root to the path before importing local modules
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """Configure application logging to a rotating file plus stderr.

    Modules across the app log via ``logging.getLogger(__name__)`` and several
    error dialogs tell the user to "see the log" — without a configured handler
    those records went nowhere. Logs to ``CONFIG_DIR/ultra_pdf.log`` (1 MB x 3
    rotation). The level can be overridden with the ``ULTRA_PDF_LOG_LEVEL``
    environment variable (e.g. ``DEBUG``).
    """
    from config import config

    level_name = os.environ.get("ULTRA_PDF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    try:
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.CONFIG_DIR / "ultra_pdf.log",
            maxBytes=1_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(fmt)
        file_handler.setLevel(level)
        root.addHandler(file_handler)
    except OSError:
        # If the log file can't be opened (e.g. read-only home), keep going
        # with just the stderr handler below.
        pass

    stderr_handler = logging.StreamHandler()
    stderr_handler.setFormatter(fmt)
    stderr_handler.setLevel(logging.WARNING)
    root.addHandler(stderr_handler)


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
    from PyQt6.QtGui import QFont, QIcon

    from config import config, UserSettings
    from ui.theme import apply_theme

    # Enable high DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    # Windows: declare an explicit AppUserModelID *before* any window is shown so
    # the taskbar uses our own icon and groups windows under "Ultra PDF Editor"
    # instead of the host pythonw.exe.
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "UltraPDFTeam.UltraPDFEditor.1")
        except Exception:
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setOrganizationName(config.APP_AUTHOR)

    # Application icon (window title bar + taskbar). The multi-resolution .ico
    # gives crisp results at every Windows icon size; fall back to the PNG.
    assets_dir = project_root / "resources" / "assets"
    for icon_name in ("UltraPDF.ico", "ultra-pdf-256.png"):
        icon_file = assets_dir / icon_name
        if icon_file.exists():
            app.setWindowIcon(QIcon(str(icon_file)))
            break

    # Set application style
    app.setStyle("Fusion")

    # Set default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Apply the saved theme (also re-applied at runtime from Preferences)
    settings = UserSettings.load(config.SETTINGS_PATH)
    apply_theme(app, settings.theme)

    return app


def main():
    """Main entry point"""
    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Create the application's working directories (config no longer does this
    # at import time), then configure logging so module-level logger.exception(...)
    # calls actually land somewhere.
    from config import config
    config.ensure_dirs()
    setup_logging()
    logging.getLogger(__name__).info("Starting Ultra PDF Editor")

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
