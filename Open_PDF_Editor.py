"""
Open PDF Editor - Main Application Entry Point
A free, offline desktop PDF editor: view, edit text, annotate, merge, split,
OCR, redact and password-protect PDFs. The version lives in pyproject.toml
and config.APP_VERSION.
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
    those records went nowhere. Logs to ``CONFIG_DIR/open_pdf_editor.log`` (1 MB x 3
    rotation). The level can be overridden with the ``OPEN_PDF_LOG_LEVEL``
    environment variable (e.g. ``DEBUG``).
    """
    from config import config

    level_name = os.environ.get("OPEN_PDF_LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    root = logging.getLogger()
    root.setLevel(level)

    fmt = logging.Formatter("%(asctime)s %(levelname)-7s %(name)s: %(message)s")

    try:
        config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            config.CONFIG_DIR / "open_pdf_editor.log",
            maxBytes=1_000_000,
            backupCount=3,
            encoding="utf-8",
        )
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
    from PyQt6.QtGui import QFont, QIcon
    from PyQt6.QtWidgets import QApplication

    from config import UserSettings, config
    from ui.theme import apply_theme

    # Enable high DPI scaling
    os.environ["QT_ENABLE_HIGHDPI_SCALING"] = "1"

    # Windows: declare an explicit AppUserModelID *before* any window is shown so
    # the taskbar uses our own icon and groups windows under "Open PDF Editor"
    # instead of the host pythonw.exe.
    if sys.platform == "win32":
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "OpenPDFEditor.OpenPDFEditor.1"
            )
        except Exception:  # noqa: BLE001 - taskbar grouping is cosmetic; never block start-up
            pass

    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)
    app.setOrganizationName(config.APP_AUTHOR)

    # Application icon (window title bar + taskbar). The multi-resolution .ico
    # gives crisp results at every Windows icon size; fall back to the PNG.
    assets_dir = project_root / "resources" / "assets"
    for icon_name in ("OpenPDF.ico", "open-pdf-256.png"):
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
    # Pages render in a child process (core.render_backend); a frozen build
    # must let that child start instead of re-running the app.
    import multiprocessing

    multiprocessing.freeze_support()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Create the application's working directories (config no longer does this
    # at import time), then configure logging so module-level logger.exception(...)
    # calls actually land somewhere.
    from config import config

    config.ensure_dirs()
    setup_logging()
    logging.getLogger(__name__).info("Starting Open PDF Editor")

    # Create application
    app = setup_application()

    # Import main window (after app is created)
    from ui.main_window import MainWindow

    # Create and show main window
    window = MainWindow()
    window.show()

    smoke_pdf = os.environ.get(SMOKE_TEST_ENV)
    if smoke_pdf:
        start_smoke_test(app, window, smoke_pdf)
    # Handle command line arguments (open file if provided)
    elif len(sys.argv) > 1:
        filepath = sys.argv[1]
        if os.path.exists(filepath) and filepath.lower().endswith(".pdf"):
            window._open_file(filepath)

    # Run application
    sys.exit(app.exec())


# Set to a PDF path to check a build end to end without anyone at the screen:
# the app opens the file, waits for the render process to deliver the first
# page, logs "SMOKE OK", and exits 0. Any error or a timeout exits non-zero.
# Used by the release workflow on the packaged exe.
SMOKE_TEST_ENV = "OPEN_PDF_SMOKE_TEST"
SMOKE_TEST_TIMEOUT_MS = 60_000


def start_smoke_test(app, window, pdf_path: str) -> None:
    """Open ``pdf_path`` and exit once its first page has rendered."""
    from PyQt6.QtCore import QTimer

    log = logging.getLogger("smoke_test")
    done = False

    def finish(code: int, message: str) -> None:
        nonlocal done
        if done:
            return
        done = True
        (log.info if code == 0 else log.error)(message)
        # Leave every event loop, including a message box's, and skip the
        # unsaved-changes prompt (nothing is edited, but be safe).
        window._is_modified = False
        # Queued, because a failure can happen before app.exec() has started,
        # and exit() is ignored while no event loop is running.
        QTimer.singleShot(0, lambda: app.exit(code))

    def on_rendered(page_num, *_args) -> None:
        finish(0, f"SMOKE OK {window._document.page_count} pages, page {page_num + 1} rendered")

    previous_hook = sys.excepthook

    def on_exception(exc_type, exc, tb) -> None:
        log.error("Smoke test failed", exc_info=(exc_type, exc, tb))
        finish(1, f"SMOKE FAILED {exc_type.__name__}: {exc}")
        previous_hook(exc_type, exc, tb)

    sys.excepthook = on_exception

    # A message box would wait for a click that never comes; fail instead.
    from PyQt6.QtWidgets import QMessageBox

    def no_dialog(_parent, title, text, *_args, **_kwargs):
        finish(4, f"SMOKE FAILED dialog '{title}': {text}")
        return QMessageBox.StandardButton.Ok

    for name in ("critical", "warning", "information", "question"):
        setattr(QMessageBox, name, staticmethod(no_dialog))

    window._viewer._render_worker.page_rendered.connect(on_rendered)
    QTimer.singleShot(SMOKE_TEST_TIMEOUT_MS, lambda: finish(2, "SMOKE FAILED timeout"))
    window._open_file(pdf_path)
    if not window._document.is_open:
        QTimer.singleShot(0, lambda: finish(3, f"SMOKE FAILED could not open {pdf_path}"))


if __name__ == "__main__":
    main()
