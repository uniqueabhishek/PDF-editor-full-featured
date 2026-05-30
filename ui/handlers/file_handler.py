"""
Ultra PDF Editor - File operations mixin.

Open/new/save/close, print, properties and the Export submenu. Mixed into
MainWindow; relies on ``self._document``, ``self._viewer``, ``self._sidebar``,
``self._settings``, ``self._main_toolbar`` and the shared helpers
``self._update_title`` / ``self._update_actions_state`` /
``self._update_recent_files_menu`` / ``self._format_size``.
"""
from pathlib import Path

import fitz
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QProgressDialog, QApplication
)
from PyQt6.QtGui import QImage, QPixmap, QPageLayout


class FileHandlerMixin:
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

            self._load_document_to_viewer()
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

    def _load_document_to_viewer(self):
        """Load the current document into the viewer"""
        if self._document.is_open and self._document.doc:
            self._viewer.set_document(self._document.doc, str(
                self._current_file) if self._current_file else "")
            self._sidebar.set_document(self._document.doc)
            self._main_toolbar.set_page_count(self._document.page_count)
            self._update_actions_state()

    def _save_document(self):
        """Save the current document"""
        if not self._document.is_open:
            return

        if self._current_file:
            try:
                # Detach doc from viewer/sidebar so their render workers release
                # any file handles (mmap) before we try to overwrite the file.
                self._viewer.set_document(None, None)
                self._sidebar.set_document(None)
                try:
                    self._document.save()
                finally:
                    # save() may have redirected to a new path (e.g. *.edited.pdf)
                    # when the original was locked — sync _current_file.
                    if self._document.filepath:
                        self._current_file = Path(str(self._document.filepath))
                    # Reattach whatever doc is currently open (save() may have
                    # reopened it from disk after a full rewrite).
                    if self._document.is_open and self._document.doc:
                        self._viewer.set_document(
                            self._document.doc,
                            str(self._current_file) if self._current_file else "",
                        )
                        self._sidebar.set_document(self._document.doc)
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

                    # Render page to image at printer resolution
                    page = doc[i]
                    # Calculate scale for printer DPI
                    dpi = printer.resolution()
                    scale = dpi / 72.0  # PDF points to printer DPI
                    mat = fitz.Matrix(scale, scale)
                    pix = page.get_pixmap(matrix=mat)

                    # Convert to QImage
                    img = QImage(pix.samples, pix.width, pix.height,
                                 pix.stride, QImage.Format.Format_RGB888)
                    pixmap = QPixmap.fromImage(img)

                    # Calculate position to center on page
                    page_rect = printer.pageRect(QPrinter.Unit.DevicePixel)
                    x = (page_rect.width() - pixmap.width()) / 2
                    y = (page_rect.height() - pixmap.height()) / 2

                    # Scale to fit page if needed
                    if pixmap.width() > page_rect.width() or pixmap.height() > page_rect.height():
                        pixmap = pixmap.scaled(
                            int(page_rect.width()), int(page_rect.height()),
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        x = (page_rect.width() - pixmap.width()) / 2
                        y = (page_rect.height() - pixmap.height()) / 2

                    painter.drawPixmap(int(x), int(y), pixmap)

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
        if output_dir:
            try:
                for i in range(self._document.page_count):
                    img_bytes = self._document.render_page_to_image(i)
                    filepath = Path(output_dir) / f"page_{i+1:04d}.png"
                    with open(filepath, 'wb') as f:
                        f.write(img_bytes)
                self._statusbar.showMessage(
                    f"Exported {self._document.page_count} images", 3000)
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to export:\n{e}")

    def _export_as_word(self):
        """Export as Word document"""
        if not self._document.is_open:
            return

        try:
            from docx import Document as WordDocument
            from docx.shared import Inches, Pt  # noqa: F401
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

        # Create progress dialog
        progress = QProgressDialog(
            "Exporting to Word...", "Cancel", 0, self._document.page_count, self)
        progress.setWindowTitle("Exporting")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        try:
            doc = WordDocument()

            for i in range(self._document.page_count):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                progress.setLabelText(
                    f"Processing page {i + 1} of {self._document.page_count}...")
                QApplication.processEvents()

                # Get text from page
                text = self._document.get_page_text(i)

                if text.strip():
                    # Add text paragraphs
                    for line in text.split('\n'):
                        if line.strip():
                            doc.add_paragraph(line)

                # Add page break between pages (except last page)
                if i < self._document.page_count - 1:
                    doc.add_page_break()

            progress.setValue(self._document.page_count)
            doc.save(filepath)
            self._statusbar.showMessage(
                f"Exported to {Path(filepath).name}", 3000)

            if QMessageBox.question(
                self, "Open Word Document",
                "Export complete. Do you want to open the Word document?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            ) == QMessageBox.StandardButton.Yes:
                # Open with the OS default application (cross-platform).
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
                except Exception as e:
                    QMessageBox.warning(
                        self, "Open Failed",
                        f"Saved, but couldn't open the file automatically:\n{e}")

        except Exception as e:
            QMessageBox.critical(self, "Export Error",
                                 f"Failed to export:\n{e}")

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
