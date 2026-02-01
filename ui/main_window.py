"""
Ultra PDF Editor - Main Application Window
"""
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QSplitter,
    QMenuBar, QMenu, QStatusBar, QFileDialog, QMessageBox, QInputDialog,
    QProgressDialog, QApplication, QDockWidget, QLabel, QToolBar
)
from PyQt6.QtCore import Qt, QSettings, QSize, QTimer, pyqtSignal, QThread
from PyQt6.QtGui import QAction, QKeySequence, QIcon, QCloseEvent, QColor
import fitz
from pathlib import Path
from typing import Optional, List
import os

from .pdf_viewer import PDFViewer, ToolMode, ViewMode
from .sidebar import Sidebar
from .toolbar import MainToolbar, AnnotationToolbar
from core.pdf_document import PDFDocument, DocumentMetadata
from config import config, UserSettings, SUPPORTED_PDF_EXTENSIONS


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()

        # Core state
        self._document = PDFDocument()
        self._settings = UserSettings.load(config.SETTINGS_PATH)
        self._is_modified = False
        self._current_file: Optional[Path] = None

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
        self._splitter.setSizes([config.SIDEBAR_WIDTH, config.WINDOW_WIDTH - config.SIDEBAR_WIDTH])

        layout.addWidget(self._splitter)

    def _setup_menus(self):
        """Setup menu bar"""
        menubar = self.menuBar()

        # === File Menu ===
        file_menu = menubar.addMenu("&File")

        self._new_action = file_menu.addAction("&New", self._new_document)
        self._new_action.setShortcut(QKeySequence.StandardKey.New)

        self._open_action = file_menu.addAction("&Open...", self._open_document)
        self._open_action.setShortcut(QKeySequence.StandardKey.Open)

        # Recent files submenu
        self._recent_menu = file_menu.addMenu("Recent Files")
        self._update_recent_files_menu()

        file_menu.addSeparator()

        self._save_action = file_menu.addAction("&Save", self._save_document)
        self._save_action.setShortcut(QKeySequence.StandardKey.Save)

        self._save_as_action = file_menu.addAction("Save &As...", self._save_document_as)
        self._save_as_action.setShortcut(QKeySequence("Ctrl+Shift+S"))

        file_menu.addSeparator()

        self._close_action = file_menu.addAction("&Close", self._close_document)
        self._close_action.setShortcut(QKeySequence.StandardKey.Close)

        file_menu.addSeparator()

        # Export submenu
        export_menu = file_menu.addMenu("Export")
        export_menu.addAction("Export as Images...", self._export_as_images)
        export_menu.addAction("Export as Word...", self._export_as_word)
        export_menu.addAction("Export as Text...", self._export_as_text)

        file_menu.addSeparator()

        self._print_action = file_menu.addAction("&Print...", self._print_document)
        self._print_action.setShortcut(QKeySequence.StandardKey.Print)

        file_menu.addSeparator()

        self._properties_action = file_menu.addAction("Properties...", self._show_properties)

        file_menu.addSeparator()

        file_menu.addAction("E&xit", self.close)

        # === Edit Menu ===
        edit_menu = menubar.addMenu("&Edit")

        self._undo_action = edit_menu.addAction("&Undo", self._undo)
        self._undo_action.setShortcut(QKeySequence.StandardKey.Undo)

        self._redo_action = edit_menu.addAction("&Redo", self._redo)
        self._redo_action.setShortcut(QKeySequence.StandardKey.Redo)

        edit_menu.addSeparator()

        self._cut_action = edit_menu.addAction("Cu&t", self._cut)
        self._cut_action.setShortcut(QKeySequence.StandardKey.Cut)

        self._copy_action = edit_menu.addAction("&Copy", self._copy)
        self._copy_action.setShortcut(QKeySequence.StandardKey.Copy)

        self._paste_action = edit_menu.addAction("&Paste", self._paste)
        self._paste_action.setShortcut(QKeySequence.StandardKey.Paste)

        self._delete_action = edit_menu.addAction("&Delete", self._delete)
        self._delete_action.setShortcut(QKeySequence.StandardKey.Delete)

        edit_menu.addSeparator()

        self._select_all_action = edit_menu.addAction("Select &All", self._select_all)
        self._select_all_action.setShortcut(QKeySequence.StandardKey.SelectAll)

        edit_menu.addSeparator()

        self._find_action = edit_menu.addAction("&Find...", self._show_find)
        self._find_action.setShortcut(QKeySequence.StandardKey.Find)

        self._replace_action = edit_menu.addAction("Find && &Replace...", self._show_replace)
        self._replace_action.setShortcut(QKeySequence("Ctrl+H"))

        # === View Menu ===
        view_menu = menubar.addMenu("&View")

        # Zoom submenu
        zoom_menu = view_menu.addMenu("Zoom")
        zoom_menu.addAction("Zoom In", self._zoom_in, QKeySequence("Ctrl++"))
        zoom_menu.addAction("Zoom Out", self._zoom_out, QKeySequence("Ctrl+-"))
        zoom_menu.addSeparator()
        zoom_menu.addAction("Fit Width", self._fit_width, QKeySequence("Ctrl+1"))
        zoom_menu.addAction("Fit Page", self._fit_page, QKeySequence("Ctrl+2"))
        zoom_menu.addAction("100%", lambda: self._viewer.set_zoom(100), QKeySequence("Ctrl+0"))

        # Rotation submenu
        rotate_menu = view_menu.addMenu("Rotate")
        rotate_menu.addAction("Rotate Clockwise", lambda: self._rotate(90), QKeySequence("Ctrl+R"))
        rotate_menu.addAction("Rotate Counter-Clockwise", lambda: self._rotate(-90), QKeySequence("Ctrl+Shift+R"))

        view_menu.addSeparator()

        # View mode submenu
        view_mode_menu = view_menu.addMenu("View Mode")
        view_mode_menu.addAction("Single Page", lambda: self._set_view_mode(ViewMode.SINGLE_PAGE))
        view_mode_menu.addAction("Two Pages", lambda: self._set_view_mode(ViewMode.TWO_PAGE))
        view_mode_menu.addAction("Continuous", lambda: self._set_view_mode(ViewMode.CONTINUOUS))

        view_menu.addSeparator()

        # Sidebar toggle
        self._sidebar_action = view_menu.addAction("Show Sidebar")
        self._sidebar_action.setCheckable(True)
        self._sidebar_action.setChecked(True)
        self._sidebar_action.triggered.connect(self._toggle_sidebar)

        # Toolbar toggles
        self._main_toolbar_action = view_menu.addAction("Show Main Toolbar")
        self._main_toolbar_action.setCheckable(True)
        self._main_toolbar_action.setChecked(True)

        self._annotation_toolbar_action = view_menu.addAction("Show Annotation Toolbar")
        self._annotation_toolbar_action.setCheckable(True)
        self._annotation_toolbar_action.setChecked(True)

        view_menu.addSeparator()

        view_menu.addAction("Full Screen", self._toggle_fullscreen, QKeySequence("F11"))

        # === Page Menu ===
        page_menu = menubar.addMenu("&Page")

        page_menu.addAction("Insert Blank Page...", self._insert_blank_page)
        page_menu.addAction("Insert Pages from File...", self._insert_from_file)
        page_menu.addSeparator()
        page_menu.addAction("Delete Page", self._delete_current_page)
        page_menu.addAction("Extract Pages...", self._extract_pages)
        page_menu.addSeparator()
        page_menu.addAction("Rotate Clockwise", lambda: self._rotate_page(90))
        page_menu.addAction("Rotate Counter-Clockwise", lambda: self._rotate_page(-90))
        page_menu.addSeparator()
        page_menu.addAction("Crop Page...", self._crop_page)

        # === Tools Menu ===
        tools_menu = menubar.addMenu("&Tools")

        tools_menu.addAction("Merge PDFs...", self._merge_pdfs)
        tools_menu.addAction("Split PDF...", self._split_pdf)
        tools_menu.addSeparator()
        tools_menu.addAction("Compress PDF...", self._compress_pdf)
        tools_menu.addAction("Optimize PDF...", self._optimize_pdf)
        tools_menu.addSeparator()
        tools_menu.addAction("OCR (Recognize Text)...", self._run_ocr)
        tools_menu.addSeparator()
        tools_menu.addAction("Add Watermark...", self._add_watermark)
        tools_menu.addAction("Add Header/Footer...", self._add_header_footer)
        tools_menu.addSeparator()
        tools_menu.addAction("Encrypt PDF...", self._encrypt_pdf)
        tools_menu.addAction("Remove Password...", self._remove_password)
        tools_menu.addSeparator()
        tools_menu.addAction("Batch Process...", self._batch_process)

        # === Help Menu ===
        help_menu = menubar.addMenu("&Help")
        help_menu.addAction("&About", self._show_about)
        help_menu.addAction("Keyboard Shortcuts", self._show_shortcuts)

    def _setup_toolbars(self):
        """Setup toolbars"""
        # Main toolbar
        self._main_toolbar = MainToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._main_toolbar)

        # Annotation toolbar
        self._annotation_toolbar = AnnotationToolbar()
        self.addToolBar(Qt.ToolBarArea.TopToolBarArea, self._annotation_toolbar)

        # Connect toolbar signals
        self._main_toolbar.new_requested.connect(self._new_document)
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
        self._main_toolbar.rotate_cw_requested.connect(lambda: self._rotate(90))
        self._main_toolbar.rotate_ccw_requested.connect(lambda: self._rotate(-90))
        self._main_toolbar.page_changed.connect(self._viewer.go_to_page)
        self._main_toolbar.first_page_requested.connect(self._viewer.first_page)
        self._main_toolbar.prev_page_requested.connect(self._viewer.previous_page)
        self._main_toolbar.next_page_requested.connect(self._viewer.next_page)
        self._main_toolbar.last_page_requested.connect(self._viewer.last_page)
        self._main_toolbar.search_requested.connect(self._search)

        # Annotation toolbar signals
        self._annotation_toolbar.tool_changed.connect(self._on_tool_changed)
        self._annotation_toolbar.color_changed.connect(self._viewer.set_annotation_color)
        self._annotation_toolbar.opacity_changed.connect(self._viewer.set_annotation_opacity)
        self._annotation_toolbar.stroke_width_changed.connect(self._viewer.set_stroke_width)

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

        # Sidebar signals
        self._sidebar.page_selected.connect(self._viewer.go_to_page)
        self._sidebar.page_double_clicked.connect(self._viewer.go_to_page)
        self._sidebar.bookmark_clicked.connect(self._viewer.go_to_page)
        self._sidebar.page_rotate_requested.connect(self._rotate_page)
        self._sidebar.page_delete_requested.connect(self._delete_page)
        self._sidebar.page_extract_requested.connect(self._extract_specific_pages)

    def _apply_settings(self):
        """Apply saved settings"""
        # Restore window geometry if available
        if self._settings.window_geometry:
            try:
                import base64
                geometry = base64.b64decode(self._settings.window_geometry)
                self.restoreGeometry(geometry)
            except:
                pass

        # Restore sidebar visibility
        self._sidebar.setVisible(self._settings.sidebar_visible)
        self._sidebar_action.setChecked(self._settings.sidebar_visible)

    def _save_settings(self):
        """Save current settings"""
        import base64
        self._settings.window_geometry = base64.b64encode(self.saveGeometry()).decode('utf-8')
        self._settings.sidebar_visible = self._sidebar.isVisible()
        self._settings.save(config.SETTINGS_PATH)

    # ==================== File Operations ====================

    def _new_document(self):
        """Create a new document"""
        if not self._confirm_close():
            return

        self._document.create_new()
        self._document.add_blank_page()
        self._load_document_to_viewer()
        self._current_file = None
        self._is_modified = True
        self._update_title()

    def _open_document(self):
        """Open a document"""
        if not self._confirm_close():
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Open PDF",
            self._settings.last_opened_directory,
            "PDF Files (*.pdf);;All Files (*)"
        )

        if filepath:
            self._open_file(filepath)

    def _open_file(self, filepath: str):
        """Open a specific file"""
        try:
            path = Path(filepath)
            self._settings.last_opened_directory = str(path.parent)

            # Check if password needed
            result = self._document.open(path)

            if not result and self._document.needs_password:
                # Ask for password
                password, ok = QInputDialog.getText(
                    self, "Password Required",
                    "This PDF is password protected. Enter password:",
                    echo=QInputDialog.EchoMode.Password
                )
                if ok:
                    self._document.open(path, password)
                else:
                    return

            self._load_document_to_viewer()
            self._current_file = path
            self._is_modified = False
            self._update_title()

            # Add to recent files
            self._settings.add_recent_file(str(path))
            self._update_recent_files_menu()

            # Update file size
            size = path.stat().st_size
            self._file_size_label.setText(self._format_size(size))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def _load_document_to_viewer(self):
        """Load the current document into the viewer"""
        if self._document.is_open:
            self._viewer.set_document(self._document._doc, str(self._current_file) if self._current_file else None)
            self._sidebar.set_document(self._document._doc)
            self._main_toolbar.set_page_count(self._document.page_count)
            self._update_actions_state()

    def _save_document(self):
        """Save the current document"""
        if not self._document.is_open:
            return

        if self._current_file:
            try:
                self._document.save()
                self._is_modified = False
                self._update_title()
                self._statusbar.showMessage("Document saved", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")
        else:
            self._save_document_as()

    def _save_document_as(self):
        """Save document with new name"""
        if not self._document.is_open:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save PDF As",
            self._settings.last_saved_directory,
            "PDF Files (*.pdf)"
        )

        if filepath:
            try:
                path = Path(filepath)
                if not path.suffix.lower() == '.pdf':
                    path = path.with_suffix('.pdf')

                self._settings.last_saved_directory = str(path.parent)
                self._document.save(path)
                self._current_file = path
                self._is_modified = False
                self._update_title()
                self._statusbar.showMessage("Document saved", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save:\n{e}")

    def _close_document(self):
        """Close the current document"""
        if not self._confirm_close():
            return

        self._document.close()
        self._viewer.set_document(None, None)
        self._sidebar.set_document(None)
        self._current_file = None
        self._is_modified = False
        self._update_title()
        self._update_actions_state()

    def _confirm_close(self) -> bool:
        """Confirm closing with unsaved changes"""
        if not self._is_modified:
            return True

        result = QMessageBox.question(
            self,
            "Unsaved Changes",
            "Do you want to save changes before closing?",
            QMessageBox.StandardButton.Save |
            QMessageBox.StandardButton.Discard |
            QMessageBox.StandardButton.Cancel
        )

        if result == QMessageBox.StandardButton.Save:
            self._save_document()
            return not self._is_modified
        elif result == QMessageBox.StandardButton.Discard:
            return True
        else:
            return False

    def _print_document(self):
        """Print the current document"""
        if not self._document.is_open:
            return
        # Would implement printing
        self._statusbar.showMessage("Printing not yet implemented", 3000)

    def _show_properties(self):
        """Show document properties"""
        if not self._document.is_open:
            return

        metadata = self._document.get_metadata()
        info = f"""
Title: {metadata.title}
Author: {metadata.author}
Subject: {metadata.subject}
Keywords: {metadata.keywords}
Creator: {metadata.creator}
Producer: {metadata.producer}
Created: {metadata.creation_date}
Modified: {metadata.modification_date}
Pages: {metadata.page_count}
Size: {self._format_size(metadata.file_size)}
Encrypted: {metadata.encryption}
        """
        QMessageBox.information(self, "Document Properties", info.strip())

    # ==================== Edit Operations ====================

    def _undo(self):
        """Undo last action"""
        pass

    def _redo(self):
        """Redo last undone action"""
        pass

    def _cut(self):
        """Cut selection"""
        pass

    def _copy(self):
        """Copy selection"""
        pass

    def _paste(self):
        """Paste from clipboard"""
        pass

    def _delete(self):
        """Delete selection"""
        pass

    def _select_all(self):
        """Select all"""
        pass

    def _show_find(self):
        """Show find dialog"""
        pass

    def _show_replace(self):
        """Show find and replace dialog"""
        pass

    def _search(self, text: str):
        """Search for text"""
        if not self._document.is_open or not text:
            return

        results = self._document.search_text(text)
        if results:
            # Go to first result
            first = results[0]
            self._viewer.go_to_page(first["page"])
            self._statusbar.showMessage(f"Found {sum(len(r['rects']) for r in results)} matches")
        else:
            self._statusbar.showMessage("No matches found")

    # ==================== View Operations ====================

    def _zoom_in(self):
        """Zoom in"""
        self._viewer.zoom_in()

    def _zoom_out(self):
        """Zoom out"""
        self._viewer.zoom_out()

    def _fit_width(self):
        """Fit to width"""
        self._viewer.fit_width()

    def _fit_page(self):
        """Fit whole page"""
        self._viewer.fit_page()

    def _rotate(self, degrees: int):
        """Rotate view"""
        self._viewer.rotate_view(degrees)

    def _set_view_mode(self, mode: ViewMode):
        """Set view mode"""
        pass

    def _toggle_sidebar(self, visible: bool):
        """Toggle sidebar visibility"""
        self._sidebar.setVisible(visible)

    def _toggle_fullscreen(self):
        """Toggle fullscreen mode"""
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # ==================== Page Operations ====================

    def _insert_blank_page(self):
        """Insert a blank page"""
        if not self._document.is_open:
            return

        current = self._viewer.get_current_page()
        self._document.add_blank_page(index=current + 1)
        self._load_document_to_viewer()
        self._is_modified = True
        self._update_title()

    def _insert_from_file(self):
        """Insert pages from another PDF"""
        if not self._document.is_open:
            return

        filepath, _ = QFileDialog.getOpenFileName(
            self, "Select PDF to Insert", "", "PDF Files (*.pdf)"
        )
        if filepath:
            current = self._viewer.get_current_page()
            self._document.merge_pdf(filepath, current + 1)
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()

    def _delete_current_page(self):
        """Delete the current page"""
        self._delete_page(self._viewer.get_current_page())

    def _delete_page(self, page_num: int):
        """Delete a specific page"""
        if not self._document.is_open:
            return

        if self._document.page_count <= 1:
            QMessageBox.warning(self, "Cannot Delete", "Cannot delete the only page in the document.")
            return

        result = QMessageBox.question(
            self, "Delete Page",
            f"Are you sure you want to delete page {page_num + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result == QMessageBox.StandardButton.Yes:
            self._document.delete_page(page_num)
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()

    def _rotate_page(self, page_num: int, degrees: int = 90):
        """Rotate a specific page"""
        if not self._document.is_open:
            return

        self._document.rotate_page(page_num, degrees)
        self._load_document_to_viewer()
        self._is_modified = True
        self._update_title()

    def _extract_pages(self):
        """Extract pages to new PDF"""
        pass

    def _extract_specific_pages(self, pages: List[int]):
        """Extract specific pages"""
        if not self._document.is_open or not pages:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Extracted Pages", "", "PDF Files (*.pdf)"
        )
        if filepath:
            self._document.extract_pages(pages, filepath)
            self._statusbar.showMessage(f"Extracted {len(pages)} pages", 3000)

    def _crop_page(self):
        """Crop current page"""
        pass

    # ==================== Tools ====================

    def _merge_pdfs(self):
        """Merge multiple PDFs"""
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDFs to Merge", "", "PDF Files (*.pdf)"
        )
        if len(files) < 2:
            return

        output, _ = QFileDialog.getSaveFileName(
            self, "Save Merged PDF", "", "PDF Files (*.pdf)"
        )
        if output:
            try:
                self._document.merge_pdfs(files, output)
                self._statusbar.showMessage("PDFs merged successfully", 3000)

                if QMessageBox.question(
                    self, "Open Merged PDF",
                    "Do you want to open the merged PDF?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                ) == QMessageBox.StandardButton.Yes:
                    self._open_file(output)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to merge:\n{e}")

    def _split_pdf(self):
        """Split PDF into multiple files"""
        if not self._document.is_open:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            try:
                files = self._document.split_by_pages(output_dir, 1)
                self._statusbar.showMessage(f"Split into {len(files)} files", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to split:\n{e}")

    def _compress_pdf(self):
        """Compress PDF to reduce size"""
        if not self._document.is_open:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Compressed PDF", "", "PDF Files (*.pdf)"
        )
        if filepath:
            try:
                self._document.compress(filepath)
                self._statusbar.showMessage("PDF compressed", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to compress:\n{e}")

    def _optimize_pdf(self):
        """Optimize PDF"""
        self._compress_pdf()

    def _run_ocr(self):
        """Run OCR on document"""
        self._statusbar.showMessage("OCR not yet implemented", 3000)

    def _add_watermark(self):
        """Add watermark to document"""
        if not self._document.is_open:
            return

        text, ok = QInputDialog.getText(self, "Add Watermark", "Watermark text:")
        if ok and text:
            self._document.add_watermark(text)
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()

    def _add_header_footer(self):
        """Add header/footer"""
        pass

    def _encrypt_pdf(self):
        """Encrypt PDF with password"""
        if not self._document.is_open:
            return

        password, ok = QInputDialog.getText(
            self, "Encrypt PDF", "Enter password:",
            QInputDialog.EchoMode.Password
        )
        if ok and password:
            self._document.encrypt(user_password=password, owner_password=password)
            self._save_document()

    def _remove_password(self):
        """Remove password protection"""
        pass

    def _batch_process(self):
        """Open batch processing dialog"""
        pass

    # ==================== Export ====================

    def _export_as_images(self):
        """Export pages as images"""
        if not self._document.is_open:
            return

        output_dir = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if output_dir:
            try:
                for i in range(self._document.page_count):
                    img_bytes = self._document.render_page_to_image(i)
                    filepath = Path(output_dir) / f"page_{i+1:04d}.png"
                    with open(filepath, 'wb') as f:
                        f.write(img_bytes)
                self._statusbar.showMessage(f"Exported {self._document.page_count} images", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

    def _export_as_word(self):
        """Export as Word document"""
        self._statusbar.showMessage("Word export not yet implemented", 3000)

    def _export_as_text(self):
        """Export as plain text"""
        if not self._document.is_open:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export as Text", "", "Text Files (*.txt)"
        )
        if filepath:
            try:
                text = self._document.get_all_text()
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                self._statusbar.showMessage("Exported as text", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

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

    # ==================== Event Handlers ====================

    def _on_page_changed(self, page: int):
        """Handle page change"""
        self._main_toolbar.set_current_page(page)
        self._sidebar.set_current_page(page)
        self._page_info_label.setText(f"Page {page + 1} of {self._document.page_count}")

    def _on_zoom_changed(self, zoom: float):
        """Handle zoom change"""
        self._main_toolbar.set_zoom(zoom)
        self._zoom_label.setText(f"{zoom:.0f}%")

    def _on_document_modified(self):
        """Handle document modification"""
        self._is_modified = True
        self._update_title()

    def _on_tool_changed(self, tool: str):
        """Handle tool change"""
        try:
            mode = ToolMode(tool)
            self._viewer.set_tool_mode(mode)
        except:
            pass

    # ==================== Helpers ====================

    def _update_title(self):
        """Update window title"""
        title = config.APP_NAME
        if self._current_file:
            title = f"{self._current_file.name} - {title}"
        if self._is_modified:
            title = f"*{title}"
        self.setWindowTitle(title)

    def _update_actions_state(self):
        """Update enabled state of actions"""
        has_doc = self._document.is_open

        self._save_action.setEnabled(has_doc)
        self._save_as_action.setEnabled(has_doc)
        self._close_action.setEnabled(has_doc)
        self._print_action.setEnabled(has_doc)
        self._properties_action.setEnabled(has_doc)
        self._find_action.setEnabled(has_doc)

    def _update_recent_files_menu(self):
        """Update recent files menu"""
        self._recent_menu.clear()

        for filepath in self._settings.recent_files[:10]:
            if os.path.exists(filepath):
                action = self._recent_menu.addAction(
                    os.path.basename(filepath),
                    lambda f=filepath: self._open_file(f)
                )
                action.setToolTip(filepath)

        if self._settings.recent_files:
            self._recent_menu.addSeparator()
            self._recent_menu.addAction("Clear Recent Files", self._clear_recent_files)

    def _clear_recent_files(self):
        """Clear recent files list"""
        self._settings.clear_recent_files()
        self._update_recent_files_menu()

    def _format_size(self, size: int) -> str:
        """Format file size for display"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"

    def closeEvent(self, event: QCloseEvent):
        """Handle window close"""
        if self._confirm_close():
            self._save_settings()
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
