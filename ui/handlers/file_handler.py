"""
Ultra PDF Editor - File operations mixin.

Open/new/save/close, print, properties and the Export submenu. Mixed into
MainWindow; relies on ``self._document``, ``self._viewer``, ``self._sidebar``,
``self._settings``, ``self._main_toolbar`` and the shared helpers
``self._update_title`` / ``self._update_actions_state`` /
``self._update_recent_files_menu`` / ``self._format_size``.
"""
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import fitz
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QProgressDialog, QApplication
)
from PyQt6.QtGui import QImage, QPageLayout

if TYPE_CHECKING:
    from ._context import MainWindowContext
    _MixinBase = MainWindowContext
else:
    _MixinBase = object

# Pages are rendered for printing at no more than this resolution.
_PRINT_MAX_DPI = 300


class FileHandlerMixin(_MixinBase):
    """File-menu operations (open/save/print/export) for MainWindow."""

    # ==================== File Operations ====================

    def _new_document(self):
        """Create a new document"""
        if not self._confirm_close():
            return

        try:
            self._document.create_new()
            self._document.add_blank_page()
            self._current_file = None
            self._load_document_to_viewer()
            self._is_modified = True
            self._clear_autosave()  # discard any prior document's recovery copy
            self._update_title()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to create new document:\n{e}")

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
                from PyQt6.QtWidgets import QLineEdit
                password, ok = QInputDialog.getText(
                    self, "Password Required",
                    "This PDF is password protected. Enter password:",
                    echo=QLineEdit.EchoMode.Password
                )
                if ok:
                    self._document.open(path, password)
                else:
                    return

            # Freshly opened and unmodified, so the render worker can open the
            # file itself rather than have the whole document re-serialized.
            self._load_document_to_viewer(render_source=str(path))
            self._current_file = path
            self._is_modified = False
            self._clear_autosave()  # newly opened doc has no pending recovery
            self._update_title()

            # Add to recent files
            self._settings.add_recent_file(str(path))
            self._update_recent_files_menu()

            # Update file size
            size = path.stat().st_size
            self._file_size_label.setText(self._format_size(size))

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open file:\n{e}")

    def _load_document_to_viewer(self, render_source=None, reuse_layout=False):
        """Load the current document into the viewer.

        ``render_source`` (file path or snapshot bytes exactly matching the
        document) spares the viewer a full re-serialize for its render worker.
        ``reuse_layout`` marks a reload of the same document after an edit:
        page and thumbnail widgets are kept when the page layout is unchanged.
        """
        if self._document.is_open and self._document.doc:
            self._viewer.set_document(self._document.doc, str(
                self._current_file) if self._current_file else "",
                render_source=render_source, reuse_layout=reuse_layout)
            self._sidebar.set_document(self._document.doc, reuse_layout=reuse_layout)
            self._main_toolbar.set_page_count(self._document.page_count)
            # Bind the Edit Text tool's paragraph lookup to the live document
            # (it's swapped on every snapshot undo/redo, so re-bind each load).
            self._viewer.set_text_block_provider(self._document.detect_text_block)
            self._update_actions_state()

    def _save_document(self):
        """Save the current document"""
        if not self._document.is_open:
            return

        if self._current_file:
            try:
                # The render copy may have the file open (it is opened from the
                # path); close it so the file can be overwritten. The page and
                # thumbnail widgets stay: saving changes nothing on screen, and
                # rebuilding them made every Ctrl+S take 0.4-0.6 s.
                self._viewer.release_render_copy()
                self._sidebar.detach_document()
                saved = False
                try:
                    self._document.save()
                    saved = True
                finally:
                    # save() may have redirected to a new path (e.g. *.edited.pdf)
                    # when the original was locked — sync _current_file.
                    if self._document.filepath:
                        self._current_file = Path(str(self._document.filepath))
                    # Reattach whatever doc is currently open (save() may have
                    # reopened it from disk after a full rewrite). After a good
                    # save the file on disk is the document, so the render copy
                    # opens it rather than re-serializing.
                    if self._document.is_open and self._document.doc:
                        path = str(self._current_file) if self._current_file else ""
                        self._viewer.set_document(
                            self._document.doc, path,
                            render_source=path if saved and path else None,
                            reuse_layout=True, keep_images=saved)
                        self._sidebar.set_document(
                            self._document.doc, reuse_layout=True, keep_images=saved)
                self._is_modified = False
                self._clear_autosave()  # saved — no unsaved changes to recover
                self._update_title()
                saved_name = self._current_file.name if self._current_file else "document"
                self._statusbar.showMessage(f"Saved as {saved_name}", 4000)
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
                self._clear_autosave()  # saved — no unsaved changes to recover
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
        self._clear_autosave()
        self._update_title()
        self._update_actions_state()

    def _confirm_close(self) -> bool:
        """Confirm closing with unsaved changes"""
        if not self._is_modified:
            return True

        # Respect the preference to skip the unsaved-changes prompt.
        if not self._settings.confirm_close_unsaved:
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

        try:
            from PyQt6.QtPrintSupport import QPrinter, QPrintDialog
            from PyQt6.QtGui import QPainter
        except ImportError:
            QMessageBox.warning(self, "Print Not Available",
                                "Print support requires PyQt6 print modules.")
            return

        printer = QPrinter(QPrinter.PrinterMode.HighResolution)
        printer.setPageOrientation(QPageLayout.Orientation.Portrait)

        dialog = QPrintDialog(printer, self)
        dialog.setWindowTitle("Print Document")

        if dialog.exec() == QPrintDialog.DialogCode.Accepted:
            # Create progress dialog
            progress = QProgressDialog(
                "Printing...", "Cancel", 0, self._document.page_count, self)
            progress.setWindowTitle("Printing")
            progress.setWindowModality(Qt.WindowModality.WindowModal)
            progress.show()

            painter = QPainter()
            painter.begin(printer)

            try:
                doc = self._document.doc
                if not doc:
                    return
                for i in range(self._document.page_count):
                    if progress.wasCanceled():
                        break

                    progress.setValue(i)
                    progress.setLabelText(
                        f"Printing page {i + 1} of {self._document.page_count}...")
                    QApplication.processEvents()

                    if i > 0:
                        printer.newPage()

                    # Render at no more than _PRINT_MAX_DPI. Rendering at the
                    # printer's native resolution (600+ dpi) cost ~1 s and
                    # ~250 MB per scanned page; 300 dpi is print quality.
                    page = doc[i]
                    dpi = min(printer.resolution(), _PRINT_MAX_DPI)
                    scale = dpi / 72.0
                    pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
                    img = QImage(pix.samples, pix.width, pix.height,
                                 pix.stride, QImage.Format.Format_RGB888)

                    # Draw at the page's true size in printer pixels, shrunk to
                    # fit and centred; the printer scales the image itself, so
                    # no QPixmap conversion or smooth-scaled copy is needed.
                    page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    to_device = printer.resolution() / 72.0
                    w = page.rect.width * to_device
                    h = page.rect.height * to_device
                    fit = min(1.0, page_rect.width() / w, page_rect.height() / h)
                    w, h = w * fit, h * fit
                    target = QRectF((page_rect.width() - w) / 2,
                                    (page_rect.height() - h) / 2, w, h)
                    painter.drawImage(target, img)

                progress.setValue(self._document.page_count)
                self._statusbar.showMessage("Document sent to printer", 3000)

            except Exception as e:
                QMessageBox.critical(self, "Print Error",
                                     f"Failed to print:\n{e}")
            finally:
                painter.end()

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

    # ==================== Export ====================

    def _export_as_images(self):
        """Export pages as images"""
        if not self._document.is_open:
            return

        output_dir = QFileDialog.getExistingDirectory(
            self, "Select Output Directory")
        if not output_dir:
            return
        formats = ["PNG (lossless)", "JPEG (smaller, about 3x faster)"]
        choice, ok = QInputDialog.getItem(
            self, "Export as Images", "Image format:", formats, 0, False)
        if not ok:
            return
        ext = "jpg" if choice == formats[1] else "png"

        # Rendering and encoding every page took ~50 s on a 60-page scan with
        # the window frozen; do it on a private copy in the background.
        try:
            data, password = self._document.worker_copy()
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not prepare document:\n{e}")
            return
        total = self._document.page_count
        progress = QProgressDialog("Exporting images...", "Cancel", 0, total, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        def work(progress_cb, is_cancelled):
            wdoc = fitz.open(stream=data, filetype="pdf")
            try:
                if wdoc.needs_pass and password:
                    wdoc.authenticate(password)
                done = 0
                for i in range(len(wdoc)):
                    if is_cancelled():
                        break
                    progress_cb(i, total)
                    pix = wdoc[i].get_pixmap(dpi=150, alpha=False)
                    out = Path(output_dir) / f"page_{i + 1:04d}.{ext}"
                    if ext == "jpg":
                        out.write_bytes(pix.tobytes("jpg", jpg_quality=90))
                    else:
                        out.write_bytes(pix.tobytes("png"))
                    done += 1
                return done
            finally:
                wdoc.close()

        def finished(done):
            self._statusbar.showMessage(f"Exported {done} images", 3000)

        self._run_background(work, progress, finished, error_title="Export Error")

    def _export_as_word(self):
        """Export page text to a Word document, off the GUI thread.

        Reading text doesn't mutate the document, but PyMuPDF is not thread-safe,
        so the worker reads from its own copy (serialized bytes) rather than the
        live document.
        """
        if not self._document.is_open or not self._document.doc:
            return

        try:
            import docx  # noqa: F401  (presence check)
        except ImportError:
            QMessageBox.warning(
                self,
                "Export Not Available",
                "Word export requires the python-docx library.\n\n"
                "Install with: pip install python-docx"
            )
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export as Word Document", "", "Word Documents (*.docx)"
        )
        if not filepath:
            return

        try:
            src_bytes = self._document.doc.tobytes(
                garbage=0, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not prepare document:\n{e}")
            return
        total = self._document.page_count

        progress = QProgressDialog(
            "Exporting to Word...", "Cancel", 0, total, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        def work(progress_cb, is_cancelled):
            from docx import Document as WordDocument
            wdoc = fitz.open(stream=src_bytes, filetype="pdf")
            try:
                out = WordDocument()
                for i in range(len(wdoc)):
                    if is_cancelled():
                        break
                    progress_cb(i, total)
                    text = wdoc[i].get_text("text")
                    if text.strip():
                        for line in text.split("\n"):
                            if line.strip():
                                out.add_paragraph(line)
                    if i < len(wdoc) - 1:
                        out.add_page_break()
                out.save(filepath)
                return filepath
            finally:
                wdoc.close()

        def on_success(saved_path):
            self._statusbar.showMessage(
                f"Exported to {Path(saved_path).name}", 3000)
            if QMessageBox.question(
                self, "Open Word Document",
                "Export complete. Do you want to open the Word document?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                self._open_with_default_app(saved_path)

        self._run_background(work, progress, on_success, error_title="Export Error")

    @staticmethod
    def _open_with_default_app(filepath: str):
        """Open a file with the OS default application (cross-platform)."""
        import os
        import sys
        import subprocess
        try:
            if sys.platform.startswith("win"):
                os.startfile(filepath)  # type: ignore[attr-defined]
            elif sys.platform == "darwin":
                subprocess.Popen(["open", filepath])
            else:
                subprocess.Popen(["xdg-open", filepath])
        except Exception:
            logging.getLogger(__name__).warning(
                "Could not open %s with the default app", filepath, exc_info=True)

    def _export_as_text(self):
        """Export as plain text on a background worker (extracting every page's
        text blocks the GUI thread on a large document)."""
        if not self._document.is_open or not self._document.doc:
            return

        filepath, _ = QFileDialog.getSaveFileName(
            self, "Export as Text", "", "Text Files (*.txt)"
        )
        if not filepath:
            return

        try:
            # Serialize once on the GUI thread; the worker reads from its own copy
            # (PyMuPDF is not thread-safe). deflate=False keeps this fast.
            src_bytes = self._document.doc.tobytes(
                garbage=0, deflate=False, encryption=fitz.PDF_ENCRYPT_NONE)
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Could not prepare document:\n{e}")
            return
        total = self._document.page_count

        progress = QProgressDialog(
            "Exporting to text...", "Cancel", 0, total, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(Qt.WindowModality.WindowModal)

        def work(progress_cb, is_cancelled):
            tdoc = fitz.open(stream=src_bytes, filetype="pdf")
            try:
                parts = []
                for i in range(len(tdoc)):
                    if is_cancelled():
                        return None  # don't write a partial file
                    progress_cb(i, total)
                    parts.append(tdoc[i].get_text("text"))
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write("\n\n".join(parts))
                return filepath
            finally:
                tdoc.close()

        def on_success(saved_path):
            self._statusbar.showMessage(
                f"Exported to {Path(saved_path).name}", 3000)

        self._run_background(work, progress, on_success, error_title="Export Error")
