"""
Ultra PDF Editor - Main Application Window

MainWindow owns the application shell: window layout, menus, toolbars, status bar,
signal wiring, settings and the top-level event handlers. The behaviour behind the
menu/toolbar actions lives in cohesive handler mixins under ``ui.handlers`` (file,
edit/search, view, page, tools and annotation), which MainWindow inherits.
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QSplitter,
    QStatusBar, QMessageBox, QLabel
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence, QCloseEvent
from pathlib import Path
from typing import TYPE_CHECKING, Optional, List, Dict
import os

from .pdf_viewer import PDFViewer, ViewMode
from .sidebar import Sidebar
from .toolbar import MainToolbar, AnnotationToolbar
from .handlers import (
    FileHandlerMixin, EditHandlerMixin, ViewHandlerMixin,
    PageHandlerMixin, ToolsHandlerMixin, AnnotationHandlerMixin,
)
from core.pdf_document import PDFDocument
from config import config, UserSettings
from utils.history import HistoryManager

if TYPE_CHECKING:
    from .dialogs import FindDialog, FindReplaceDialog


class MainWindow(
    FileHandlerMixin,
    EditHandlerMixin,
    ViewHandlerMixin,
    PageHandlerMixin,
    ToolsHandlerMixin,
    AnnotationHandlerMixin,
    QMainWindow,
):
    """Main application window.

    The action handlers are provided by the mixins above; this class is
    responsible for constructing and wiring the UI and for the shared helpers
    those handlers depend on (title/state updates, recent files, etc.).
    """

    def _create_action(self, text: str, slot=None, shortcut=None, checkable=False) -> QAction:
        """Helper to create menu actions (PyQt6 compatible)"""
        action = QAction(text, self)
        if slot:
            action.triggered.connect(slot)
        if shortcut:
            action.setShortcut(shortcut)
        if checkable:
            action.setCheckable(True)
        return action

    def __init__(self):
        super().__init__()

        # Core state
        self._document = PDFDocument()
        self._settings = UserSettings.load(config.SETTINGS_PATH)
        self._is_modified = False
        self._current_file: Optional[Path] = None

        # Undo/Redo history manager
        self._history_manager = HistoryManager(config.UNDO_HISTORY_SIZE)

        # Search state
        self._search_results: List[Dict] = []
        self._current_search_index = 0
        self._find_dialog: Optional["FindDialog"] = None
        self._replace_dialog: Optional["FindReplaceDialog"] = None

        # Setup UI
        self._setup_ui()
        self._setup_menus()
        self._setup_toolbars()
        self._setup_statusbar()
        self._connect_signals()
        self._apply_settings()

        # Set initial state
        self._update_title()
        self._update_actions_state()

    def _setup_ui(self):
        """Setup the main UI layout"""
        self.setWindowTitle(config.APP_NAME)
        self.setMinimumSize(config.WINDOW_MIN_WIDTH, config.WINDOW_MIN_HEIGHT)
        self.resize(config.WINDOW_WIDTH, config.WINDOW_HEIGHT)

        # Central widget with splitter
        central = QWidget()
        self.setCentralWidget(central)

        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Splitter for sidebar and viewer
        self._splitter = QSplitter(Qt.Orientation.Horizontal)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.setMinimumWidth(150)
        self._sidebar.setMaximumWidth(400)
        self._splitter.addWidget(self._sidebar)

        # PDF Viewer
        self._viewer = PDFViewer()
        self._splitter.addWidget(self._viewer)

        # Set initial sizes
        self._splitter.setSizes(
            [config.SIDEBAR_WIDTH, config.WINDOW_WIDTH - config.SIDEBAR_WIDTH])

        layout.addWidget(self._splitter)

    def _setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()
        assert menubar is not None  # QMainWindow always has a menu bar

        # === File Menu ===
        file_menu = menubar.addMenu("&File")
        assert file_menu is not None

        self._new_action = file_menu.addAction("&New", self._new_document)
        assert self._new_action is not None
        self._new_action.setShortcut(QKeySequence.StandardKey.New)

        self._open_action = file_menu.addAction(
            "&Open...", self._open_document)
        assert self._open_action is not None
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("Recent Files")
        assert self._recent_menu is not None
        self._update_recent_files_menu()

        file_menu.addSeparator()

        self._save_action = file_menu.addAction("&Save", self._save_document)
        assert self._save_action is not None
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)

        self._save_as_action = file_menu.addAction(
            "Save &As...", self._save_document_as)
        assert self._save_as_action is not None
        self._save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))

        file_menu.addSeparator()

        self._close_action = file_menu.addAction(
            "&Close", self._close_document)
        assert self._close_action is not None
        self._close_action.setShortcut(QKeySequence.StandardKey.Close)

        file_menu.addSeparator()

        # Export submenu
        export_menu = file_menu.addMenu("Export")
        assert export_menu is not None
        export_menu.addAction("Export as Images...", self._export_as_images)
        export_menu.addAction("Export as Word...", self._export_as_word)
        export_menu.addAction("Export as Text...", self._export_as_text)

        file_menu.addSeparator()

        self._print_action = file_menu.addAction(
            "&Print...", self._print_document)
        assert self._print_action is not None
        self._print_action.setShortcut(QKeySequence.StandardKey.Print)

        file_menu.addSeparator()

        self._properties_action = file_menu.addAction(
            "Properties...", self._show_properties)

        file_menu.addSeparator()

        file_menu.addAction("E&xit", self.close)

        # === Edit Menu ===
        edit_menu = menubar.addMenu("&Edit")
        assert edit_menu is not None

        self._undo_action = edit_menu.addAction("&Undo", self._undo)
        assert self._undo_action is not None
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)

        self._redo_action = edit_menu.addAction("&Redo", self._redo)
        assert self._redo_action is not None
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)

        edit_menu.addSeparator()

        self._cut_action = edit_menu.addAction("Cu&t", self._cut)
        assert self._cut_action is not None
        self._cut_action.setShortcut(QKeySequence.StandardKey.Cut)

        self._copy_action = edit_menu.addAction("&Copy", self._copy)
        assert self._copy_action is not None
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)

        self._paste_action = edit_menu.addAction("&Paste", self._paste)
        assert self._paste_action is not None
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)

        self._delete_action = edit_menu.addAction("&Delete", self._delete)
        assert self._delete_action is not None
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)

        edit_menu.addSeparator()

        self._select_all_action = edit_menu.addAction(
            "Select &All", self._select_all)
        assert self._select_all_action is not None
        self._select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)

        edit_menu.addSeparator()

        self._find_action = edit_menu.addAction("&Find...", self._show_find)
        assert self._find_action is not None
        self._find_action.setShortcut(QKeySequence.StandardKey.Find)

        self._replace_action = edit_menu.addAction(
            "Find && &Replace...", self._show_replace)
        assert self._replace_action is not None
        self._replace_action.setShortcut(QKeySequence("Ctrl+H"))

        # === View Menu ===
        view_menu = menubar.addMenu("&View")
        assert view_menu is not None

        # Zoom submenu
        zoom_menu = view_menu.addMenu("Zoom")
        assert zoom_menu is not None
        zoom_in_action = zoom_menu.addAction("Zoom In")
        assert zoom_in_action is not None
        zoom_in_action.setShortcut(QKeySequence("Ctrl++"))
        zoom_in_action.triggered.connect(self._zoom_in)
        zoom_out_action = zoom_menu.addAction("Zoom Out")
        assert zoom_out_action is not None
        zoom_out_action.setShortcut(QKeySequence("Ctrl+-"))
        zoom_out_action.triggered.connect(self._zoom_out)
        zoom_menu.addSeparator()
        fit_width_action = zoom_menu.addAction("Fit Width")
        assert fit_width_action is not None
        fit_width_action.setShortcut(QKeySequence("Ctrl+1"))
        fit_width_action.triggered.connect(self._fit_width)
        fit_page_action = zoom_menu.addAction("Fit Page")
        assert fit_page_action is not None
        fit_page_action.setShortcut(QKeySequence("Ctrl+2"))
        fit_page_action.triggered.connect(self._fit_page)
        zoom_100_action = zoom_menu.addAction("100%")
        assert zoom_100_action is not None
        zoom_100_action.setShortcut(QKeySequence("Ctrl+0"))
        zoom_100_action.triggered.connect(lambda: self._viewer.set_zoom(100))

        # Rotation submenu
        rotate_menu = view_menu.addMenu("Rotate")
        assert rotate_menu is not None
        rotate_cw_action = rotate_menu.addAction("Rotate Clockwise")
        assert rotate_cw_action is not None
        rotate_cw_action.setShortcut(QKeySequence("Ctrl+R"))
        rotate_cw_action.triggered.connect(lambda: self._rotate(90))
        rotate_ccw_action = rotate_menu.addAction("Rotate Counter-Clockwise")
        assert rotate_ccw_action is not None
        rotate_ccw_action.setShortcut(QKeySequence("Ctrl+Shift+R"))
        rotate_ccw_action.triggered.connect(lambda: self._rotate(-90))

        view_menu.addSeparator()

        # View mode submenu
        view_mode_menu = view_menu.addMenu("View Mode")
        assert view_mode_menu is not None
        view_mode_menu.addAction(self._create_action(
            "Single Page", lambda: self._set_view_mode(ViewMode.SINGLE_PAGE)))
        view_mode_menu.addAction(self._create_action(
            "Two Pages", lambda: self._set_view_mode(ViewMode.TWO_PAGE)))
        view_mode_menu.addAction(self._create_action(
            "Continuous", lambda: self._set_view_mode(ViewMode.CONTINUOUS)))

        view_menu.addSeparator()

        # Sidebar toggle
        self._sidebar_action = view_menu.addAction("Show Sidebar")
        assert self._sidebar_action is not None
        self._sidebar_action.setCheckable(True)
        self._sidebar_action.setChecked(True)
        self._sidebar_action.triggered.connect(self._toggle_sidebar)

        # Toolbar toggles
        self._main_toolbar_action = view_menu.addAction("Show Main Toolbar")
        assert self._main_toolbar_action is not None
        self._main_toolbar_action.setCheckable(True)
        self._main_toolbar_action.setChecked(True)

        self._annotation_toolbar_action = view_menu.addAction(
            "Show Annotation Toolbar")
        assert self._annotation_toolbar_action is not None
        self._annotation_toolbar_action.setCheckable(True)
        self._annotation_toolbar_action.setChecked(True)

        view_menu.addSeparator()

        fullscreen_action = self._create_action(
            "Full Screen", self._toggle_fullscreen, QKeySequence("F11"))
        view_menu.addAction(fullscreen_action)

        # === Page Menu ===
        page_menu = menubar.addMenu("&Page")
        assert page_menu is not None

        page_menu.addAction(self._create_action(
            "Insert Blank Page...", self._insert_blank_page))
        page_menu.addAction(self._create_action(
            "Insert Pages from File...", self._insert_from_file))
        page_menu.addSeparator()
        page_menu.addAction(self._create_action(
            "Delete Page", self._delete_current_page))
        page_menu.addAction(self._create_action(
            "Extract Pages...", self._extract_pages))
        page_menu.addSeparator()
        page_menu.addAction(self._create_action(
            "Rotate Clockwise", lambda: self._rotate_page(90)))
        page_menu.addAction(self._create_action(
            "Rotate Counter-Clockwise", lambda: self._rotate_page(-90)))
        page_menu.addSeparator()
        page_menu.addAction(self._create_action(
            "Crop Page...", self._crop_page))

        # === Tools Menu ===
        tools_menu = menubar.addMenu("&Tools")
        assert tools_menu is not None

        tools_menu.addAction(self._create_action(
            "Merge PDFs...", self._merge_pdfs))
        tools_menu.addAction(self._create_action(
            "Split PDF...", self._split_pdf))
        tools_menu.addSeparator()
        tools_menu.addAction(self._create_action(
            "Compress PDF...", self._compress_pdf))
        tools_menu.addAction(self._create_action(
            "Optimize PDF...", self._optimize_pdf))
        tools_menu.addSeparator()
        tools_menu.addAction(self._create_action(
            "OCR (Recognize Text)...", self._run_ocr))
        tools_menu.addSeparator()
        tools_menu.addAction(self._create_action(
            "Add Watermark...", self._add_watermark))
        tools_menu.addAction(self._create_action(
            "Add Header/Footer...", self._add_header_footer))
        tools_menu.addSeparator()
        tools_menu.addAction(self._create_action(
            "Encrypt PDF...", self._encrypt_pdf))
        tools_menu.addAction(self._create_action(
            "Remove Password...", self._remove_password))
        tools_menu.addSeparator()
        tools_menu.addAction(self._create_action(
            "Batch Process...", self._batch_process))

        # === Trim Header/Footer Menu ===
        hf_menu = menubar.addMenu("&Trim Header/Footer")
        assert hf_menu is not None
        _manual_act = self._create_action("Manual Trim", self._remove_header_footer)
        _manual_act.setStatusTip("Permanently erase a fixed-height strip from the top and/or bottom of selected pages")
        hf_menu.addAction(_manual_act)
        _smart_act = self._create_action("Smart Detection && Trim", self._clean_pdf)
        _smart_act.setStatusTip("Scan all pages for repeating text in margins, review findings, and remove what you select")
        hf_menu.addAction(_smart_act)
        hf_menu.addSeparator()
        _erase_act = self._create_action("Erase Selection", self._activate_erase_selection)
        _erase_act.setStatusTip("Draw a rectangle on the page to permanently erase that area")
        hf_menu.addAction(_erase_act)

        # === Help Menu ===
        help_menu = menubar.addMenu("&Help")
        assert help_menu is not None
        help_menu.addAction(self._create_action("&About", self._show_about))
        help_menu.addAction(self._create_action(
            "Keyboard Shortcuts", self._show_shortcuts))

    def _setup_toolbars(self):
        """Setup toolbars"""
        # Main toolbar
        self._main_toolbar = MainToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._main_toolbar)

        # Add toolbar break to put annotation toolbar on its own row
        self.addToolBarBreak(Qt.ToolBarArea.TopToolBarArea)

        # Annotation toolbar (on second row for better visibility)
        self._annotation_toolbar = AnnotationToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea,
                        self._annotation_toolbar)

        # Connect toolbar signals
        self._main_toolbar.open_requested.connect(self._open_document)
        self._main_toolbar.save_requested.connect(self._save_document)
        self._main_toolbar.save_as_requested.connect(self._save_document_as)
        self._main_toolbar.print_requested.connect(self._print_document)
        self._main_toolbar.undo_requested.connect(self._undo)
        self._main_toolbar.redo_requested.connect(self._redo)
        self._main_toolbar.zoom_changed.connect(self._viewer.set_zoom)
        self._main_toolbar.zoom_in_requested.connect(self._zoom_in)
        self._main_toolbar.zoom_out_requested.connect(self._zoom_out)
        self._main_toolbar.fit_width_requested.connect(self._fit_width)
        self._main_toolbar.fit_page_requested.connect(self._fit_page)
        self._main_toolbar.rotate_cw_requested.connect(
            lambda: self._rotate(90))
        self._main_toolbar.rotate_ccw_requested.connect(
            lambda: self._rotate(-90))
        self._main_toolbar.page_changed.connect(self._viewer.go_to_page)
        self._main_toolbar.first_page_requested.connect(
            self._viewer.first_page)
        self._main_toolbar.prev_page_requested.connect(
            self._viewer.previous_page)
        self._main_toolbar.next_page_requested.connect(self._viewer.next_page)
        self._main_toolbar.last_page_requested.connect(self._viewer.last_page)
        self._main_toolbar.search_requested.connect(self._search)
        self._main_toolbar.clean_pdf_requested.connect(self._clean_pdf)
        self._main_toolbar.remove_header_footer_requested.connect(self._remove_header_footer)

        # Annotation toolbar signals
        self._annotation_toolbar.tool_changed.connect(self._on_tool_changed)
        self._annotation_toolbar.color_changed.connect(
            self._viewer.set_annotation_color)
        self._annotation_toolbar.opacity_changed.connect(
            self._viewer.set_annotation_opacity)
        self._annotation_toolbar.stroke_width_changed.connect(
            self._viewer.set_stroke_width)
        self._annotation_toolbar.font_changed.connect(self._viewer.set_font)

    def _setup_statusbar(self):
        """Setup status bar"""
        self._statusbar = QStatusBar()
        self.setStatusBar(self._statusbar)

        # Page info label
        self._page_info_label = QLabel("No document")
        self._statusbar.addWidget(self._page_info_label)

        # Spacer
        self._statusbar.addWidget(QWidget(), 1)

        # Zoom info label
        self._zoom_label = QLabel("100%")
        self._statusbar.addPermanentWidget(self._zoom_label)

        # File size label
        self._file_size_label = QLabel("")
        self._statusbar.addPermanentWidget(self._file_size_label)

    def _connect_signals(self):
        """Connect signals between components"""
        # Viewer signals
        self._viewer.page_changed.connect(self._on_page_changed)
        self._viewer.zoom_changed.connect(self._on_zoom_changed)
        self._viewer.document_modified.connect(self._on_document_modified)
        self._viewer.annotation_create_requested.connect(
            self._create_annotation)

        # Sidebar signals
        self._sidebar.page_selected.connect(self._viewer.go_to_page)
        self._sidebar.page_double_clicked.connect(self._viewer.go_to_page)
        self._sidebar.bookmark_clicked.connect(self._viewer.go_to_page)
        self._sidebar.page_rotate_requested.connect(self._rotate_page)
        self._sidebar.page_delete_requested.connect(self._delete_page)
        self._sidebar.page_extract_requested.connect(
            self._extract_specific_pages)
        self._sidebar.pages_reordered.connect(self._reorder_page)
        self._sidebar.toc_changed.connect(self._apply_toc)
        self._sidebar.bookmark_add_requested.connect(self._add_bookmark)

    def _apply_settings(self):
        """Apply saved settings"""
        # Restore window geometry if available
        if self._settings.window_geometry:
            try:
                import base64
                geometry = base64.b64decode(self._settings.window_geometry)
                self.restoreGeometry(geometry)
            except Exception:
                pass

        # Restore sidebar visibility
        self._sidebar.setVisible(self._settings.sidebar_visible)
        if self._sidebar_action:
            self._sidebar_action.setChecked(self._settings.sidebar_visible)

    def _save_settings(self):
        """Save current settings"""
        import base64
        geometry_data = self.saveGeometry().data()  # Get raw bytes from QByteArray
        self._settings.window_geometry = base64.b64encode(geometry_data).decode('utf-8')  # type: ignore[assignment]
        self._settings.sidebar_visible = self._sidebar.isVisible()
        self._settings.save(config.SETTINGS_PATH)

    # ==================== Event Handlers ====================

    def _on_page_changed(self, page: int):
        """Handle page change"""
        self._main_toolbar.set_current_page(page)
        self._sidebar.set_current_page(page)
        self._page_info_label.setText(
            f"Page {page + 1} of {self._document.page_count}")

    def _on_zoom_changed(self, zoom: float):
        """Handle zoom change"""
        self._main_toolbar.set_zoom(zoom)
        self._zoom_label.setText(f"{zoom:.0f}%")

    def _on_document_modified(self):
        """Handle document modification"""
        self._is_modified = True
        self._update_title()
        # Refresh sidebar thumbnails to reflect changes
        self._sidebar.refresh()

    # ==================== Help ====================

    def _show_about(self):
        """Show about dialog"""
        QMessageBox.about(
            self,
            f"About {config.APP_NAME}",
            f"""<h2>{config.APP_NAME}</h2>
            <p>Version {config.APP_VERSION}</p>
            <p>A powerful yet simple PDF editor with all the features you need.</p>
            <p>Built with Python, PyQt6, and PyMuPDF.</p>
            """
        )

    def _show_shortcuts(self):
        """Show keyboard shortcuts"""
        shortcuts = """
<h3>Keyboard Shortcuts</h3>
<table>
<tr><td>Ctrl+N</td><td>New Document</td></tr>
<tr><td>Ctrl+O</td><td>Open</td></tr>
<tr><td>Ctrl+S</td><td>Save</td></tr>
<tr><td>Ctrl+Shift+S</td><td>Save As</td></tr>
<tr><td>Ctrl+P</td><td>Print</td></tr>
<tr><td>Ctrl+Z</td><td>Undo</td></tr>
<tr><td>Ctrl+Y</td><td>Redo</td></tr>
<tr><td>Ctrl+F</td><td>Find</td></tr>
<tr><td>Ctrl++</td><td>Zoom In</td></tr>
<tr><td>Ctrl+-</td><td>Zoom Out</td></tr>
<tr><td>Ctrl+0</td><td>Zoom 100%</td></tr>
<tr><td>Page Up/Down</td><td>Navigate Pages</td></tr>
<tr><td>Ctrl+Home</td><td>First Page</td></tr>
<tr><td>Ctrl+End</td><td>Last Page</td></tr>
<tr><td>F11</td><td>Full Screen</td></tr>
</table>
        """
        QMessageBox.information(self, "Keyboard Shortcuts", shortcuts)

    # ==================== Helpers ====================

    def _update_title(self):
        """Update window title"""
        title = config.APP_NAME
        if self._current_file:
            title = f"{self._current_file.name} - {title}"
        if self._is_modified:
            title = f"*{title}"
        self.setWindowTitle(title)

    def _run_snapshot_op(self, description: str, operation, command_type=None):
        """Run a destructive document mutation as an undoable snapshot command.

        ``operation`` is a no-argument callable that performs the in-place change
        (and may return a value, available afterwards as ``command.result``). The
        document is snapshotted before/after so the edit can be undone. Returns
        the executed command on success, or None if the operation failed.
        """
        from utils.history import DocumentSnapshotCommand, CommandType
        command = DocumentSnapshotCommand(
            self._document, operation,
            command_type or CommandType.METADATA_CHANGE, description)
        if self._history_manager.execute(command):
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()
            return command
        return None

    # ==================== Bookmarks ====================

    def _apply_toc(self, toc: list):
        """Persist a bookmark rename/delete from the sidebar to the document."""
        if not self._document.is_open:
            return
        try:
            self._document.set_toc(toc)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not update bookmarks:\n{e}")
            return
        # Reload the panel so it matches the stored outline exactly.
        self._sidebar.bookmark_panel.set_document(self._document.doc)
        self._is_modified = True
        self._update_title()

    def _add_bookmark(self, title: str):
        """Add a bookmark for the current page (from the sidebar)."""
        if not self._document.is_open:
            return
        page = self._viewer.get_current_page()
        try:
            self._document.add_bookmark(title, page)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Could not add bookmark:\n{e}")
            return
        self._sidebar.bookmark_panel.set_document(self._document.doc)
        self._is_modified = True
        self._update_title()
        self._statusbar.showMessage(f"Bookmark added on page {page + 1}", 2000)

    def _update_actions_state(self):
        """Update enabled state of actions"""
        has_doc = self._document.is_open

        if self._save_action:
            self._save_action.setEnabled(has_doc)
        if self._save_as_action:
            self._save_as_action.setEnabled(has_doc)
        if self._close_action:
            self._close_action.setEnabled(has_doc)
        if self._print_action:
            self._print_action.setEnabled(has_doc)
        if self._properties_action:
            self._properties_action.setEnabled(has_doc)
        if self._find_action:
            self._find_action.setEnabled(has_doc)

    def _update_recent_files_menu(self):
        """Update recent files menu"""
        if not self._recent_menu:
            return
        self._recent_menu.clear()

        for filepath in self._settings.recent_files[:10]:
            if os.path.exists(filepath):
                action = self._recent_menu.addAction(
                    os.path.basename(filepath),
                    lambda f=filepath: self._open_file(f)
                )
                if action:
                    action.setToolTip(filepath)

        if self._settings.recent_files:
            self._recent_menu.addSeparator()
            self._recent_menu.addAction(
                "Clear Recent Files", self._clear_recent_files)

    def _clear_recent_files(self):
        """Clear recent files list"""
        self._settings.clear_recent_files()
        self._update_recent_files_menu()

    def _format_size(self, size_bytes: int) -> str:
        """Format file size for display"""
        size: float = float(size_bytes)
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""
        if self._confirm_close():
            self._save_settings()
            self._viewer.cleanup()  # Stop background render thread
            self._document.close()
            event.accept()
        else:
            event.ignore()

    def dragEnterEvent(self, event):
        """Handle drag enter"""
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.toLocalFile().lower().endswith('.pdf'):
                    event.acceptProposedAction()
                    return

    def dropEvent(self, event):
        """Handle file drop"""
        for url in event.mimeData().urls():
            filepath = url.toLocalFile()
            if filepath.lower().endswith('.pdf'):
                self._open_file(filepath)
                break
