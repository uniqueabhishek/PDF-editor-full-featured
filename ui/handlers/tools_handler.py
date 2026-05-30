"""
Ultra PDF Editor - Tools mixin.

Merge, split, compress/optimize, OCR, watermark, header/footer (add, remove and
smart-clean), encryption and batch processing. Mixed into MainWindow; relies on
``self._document``, ``self._viewer``, ``self._current_file`` and the shared
``self._load_document_to_viewer`` / ``self._update_title`` /
``self._save_document`` helpers.
"""
import datetime

import fitz
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFileDialog, QMessageBox, QInputDialog, QProgressDialog, QApplication
)
from PyQt6.QtGui import QImage, QPixmap

from ..dialogs import (
    HeaderFooterDialog, RemoveHeaderFooterDialog, BatchDialog,
    MergeDialog, SplitDialog,
)


class ToolsHandlerMixin:
    """Tools-menu and header/footer operations for MainWindow."""

    def _merge_pdfs(self):
        """Merge multiple PDFs into a new file (order/options via MergeDialog)."""
        dialog = MergeDialog(self)
        if not dialog.exec():
            return

        files = dialog.get_files()
        output = dialog.get_output_path()
        if len(files) < 2 or not output:
            return

        opts = dialog.get_options()
        try:
            self._document.merge_pdfs(
                files, output,
                add_bookmarks=opts.get("add_bookmarks", False),
                compress=opts.get("compress", True),
            )
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
        """Split the current PDF into multiple files (mode/options via SplitDialog)."""
        if not self._document.is_open:
            return

        dialog = SplitDialog(
            str(self._current_file) if self._current_file else None,
            self._document.page_count, self)
        if not dialog.exec():
            return

        opts = dialog.get_split_options()
        output_dir = opts.get("output_dir")
        if not output_dir:
            return

        mode = opts.get("mode", "single")
        try:
            if mode == "every_n":
                files = self._document.split_by_pages(output_dir, opts["pages_per_file"])
            elif mode == "ranges":
                ranges = [(start - 1, end - 1) for start, end in opts["ranges"]]
                files = self._document.split_by_ranges(ranges, output_dir)
            elif mode == "bookmarks":
                files = self._document.split_by_bookmarks(output_dir)
            else:
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
                QMessageBox.critical(
                    self, "Error", f"Failed to compress:\n{e}")

    def _optimize_pdf(self):
        """Optimize PDF"""
        self._compress_pdf()

    def _run_ocr(self):
        """Run OCR on document"""
        if not self._document.is_open:
            return

        try:
            import pytesseract
            from PIL import Image
            import io
        except ImportError:
            QMessageBox.warning(
                self,
                "OCR Not Available",
                "OCR requires pytesseract and Pillow libraries.\n\n"
                "Install with: pip install pytesseract Pillow\n\n"
                "You also need Tesseract OCR installed on your system:\n"
                "- Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki\n"
                "- macOS: brew install tesseract\n"
                "- Linux: sudo apt install tesseract-ocr"
            )
            return

        # Confirm with user
        result = QMessageBox.question(
            self,
            "Run OCR",
            f"This will add a searchable text layer to all {self._document.page_count} pages.\n\n"
            "This process may take some time. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        # Create progress dialog
        progress = QProgressDialog(
            "Running OCR...", "Cancel", 0, self._document.page_count, self)
        progress.setWindowTitle("OCR Processing")
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.show()

        def _do():
            doc = self._document.doc
            for i in range(self._document.page_count):
                if progress.wasCanceled():
                    break

                progress.setValue(i)
                progress.setLabelText(
                    f"Processing page {i + 1} of {self._document.page_count}...")
                QApplication.processEvents()

                # Render page to image (the zoom must match the coordinate
                # scaling applied to the OCR word boxes below).
                page = doc[i]
                zoom = 2  # higher resolution for better OCR
                pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
                img = Image.open(io.BytesIO(pix.tobytes("png")))

                # Position each recognised word individually so the invisible
                # text layer lines up with the page (image_to_string would put
                # the whole page's text at a single point).
                data = pytesseract.image_to_data(
                    img, output_type=pytesseract.Output.DICT)
                for j, word in enumerate(data["text"]):
                    if not word.strip():
                        continue
                    x = data["left"][j] / zoom
                    y = (data["top"][j] + data["height"][j]) / zoom
                    fontsize = max(1.0, data["height"][j] / zoom)
                    page.insert_text(
                        fitz.Point(x, y), word, fontsize=fontsize,
                        color=(1, 1, 1), render_mode=3)

            progress.setValue(self._document.page_count)

        cmd = self._run_snapshot_op("OCR", _do)
        progress.close()
        if cmd is not None:
            self._statusbar.showMessage(
                "OCR completed - document is now searchable", 3000)
        else:
            QMessageBox.critical(
                self, "OCR Error", "Failed to run OCR. See log for details.")

    def _add_watermark(self):
        """Add watermark to document"""
        if not self._document.is_open:
            return

        text, ok = QInputDialog.getText(
            self, "Add Watermark", "Watermark text:")
        if ok and text:
            cmd = self._run_snapshot_op(
                "Add watermark", lambda: self._document.add_watermark(text))
            if cmd is not None:
                self._statusbar.showMessage("Watermark added", 2000)
            else:
                QMessageBox.critical(
                    self, "Error", "Failed to add watermark. See log for details.")

    def _add_header_footer(self):
        """Add header/footer"""
        if not self._document.is_open:
            return

        dialog = HeaderFooterDialog(self._document.page_count, self)
        if not dialog.exec() or not self._document.doc:
            return

        # Get settings from dialog
        header_texts = dialog.get_header_texts()
        footer_texts = dialog.get_footer_texts()
        font_settings = dialog.get_font_settings()
        page_range = dialog.get_page_range()
        margins = dialog.get_margins()

        fontsize      = font_settings['size']
        fontname      = font_settings['fitz_font']
        font_color    = font_settings['color']
        margin_top    = margins['top']
        margin_bottom = margins['bottom']
        margin_side   = margins['side']
        filename_str  = self._current_file.name if self._current_file else ""
        today_str     = datetime.datetime.now().strftime("%Y-%m-%d")

        def _do():
            doc = self._document.doc
            for i in range(page_range[0], page_range[1] + 1):
                page = doc[i]
                rect = page.rect

                def process_text(raw: str) -> str:
                    return (
                        raw
                        .replace("{page}",     str(i + 1))
                        .replace("{total}",    str(self._document.page_count))
                        .replace("{date}",     today_str)
                        .replace("{filename}", filename_str)
                    )

                def insert(pt: "fitz.Point", raw: str) -> None:
                    page.insert_text(
                        pt, process_text(raw),
                        fontsize=fontsize,
                        fontname=fontname,
                        color=font_color,
                    )

                def text_w(raw: str) -> float:
                    return fitz.get_text_length(
                        process_text(raw),
                        fontname=fontname,
                        fontsize=fontsize,
                    )

                # Add header
                if any(header_texts.values()):
                    y = margin_top
                    if header_texts['left']:
                        insert(fitz.Point(margin_side, y), header_texts['left'])
                    if header_texts['center']:
                        insert(fitz.Point((rect.width - text_w(header_texts['center'])) / 2, y),
                               header_texts['center'])
                    if header_texts['right']:
                        insert(fitz.Point(rect.width - margin_side - text_w(header_texts['right']), y),
                               header_texts['right'])

                # Add footer
                if any(footer_texts.values()):
                    y = rect.height - margin_bottom
                    if footer_texts['left']:
                        insert(fitz.Point(margin_side, y), footer_texts['left'])
                    if footer_texts['center']:
                        insert(fitz.Point((rect.width - text_w(footer_texts['center'])) / 2, y),
                               footer_texts['center'])
                    if footer_texts['right']:
                        insert(fitz.Point(rect.width - margin_side - text_w(footer_texts['right']), y),
                               footer_texts['right'])

        if self._run_snapshot_op("Add header/footer", _do) is not None:
            self._statusbar.showMessage("Header/Footer added", 2000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to add header/footer. See log for details.")

    def _remove_header_footer(self):
        """Remove header/footer strips via redaction"""
        if not self._document.is_open or not self._document.doc:
            return

        doc = self._document.doc
        page_num = self._viewer.get_current_page()
        page = doc[page_num]
        rect = page.rect

        # Render a small preview of the current page
        pix = page.get_pixmap(matrix=fitz.Matrix(0.4, 0.4))
        img = QImage(pix.samples, pix.width, pix.height,
                     pix.stride, QImage.Format.Format_RGB888)
        preview_pixmap = QPixmap.fromImage(img)

        dialog = RemoveHeaderFooterDialog(
            preview_pixmap, rect.height, self._document.page_count, self
        )
        if not dialog.exec():
            return

        header_h = dialog.get_header_height()
        footer_h = dialog.get_footer_height()
        start, end = dialog.get_page_range()

        def _do():
            d = self._document.doc
            for i in range(start, end + 1):
                pg = d[i]
                pr = pg.rect

                if header_h > 0:
                    pg.add_redact_annot(
                        fitz.Rect(pr.x0, pr.y0, pr.x1, pr.y0 + header_h),
                        fill=(1, 1, 1),
                    )
                if footer_h > 0:
                    pg.add_redact_annot(
                        fitz.Rect(pr.x0, pr.y1 - footer_h, pr.x1, pr.y1),
                        fill=(1, 1, 1),
                    )
                pg.apply_redactions()

        if self._run_snapshot_op("Trim header/footer", _do) is not None:
            pages_label = f"{end - start + 1} page(s)"
            self._statusbar.showMessage(
                f"Header/Footer removed from {pages_label}", 3000
            )
        else:
            QMessageBox.critical(
                self, "Error", "Failed to remove header/footer. See log for details."
            )

    def _clean_pdf(self):
        """Scan for repeating margin text, show non-modal dialog, then redact on accept."""
        if not self._document.is_open:
            QMessageBox.information(self, "No Document", "Please open a PDF first.")
            return

        # Close any previously open Clean PDF dialog
        if hasattr(self, "_clean_pdf_dlg") and self._clean_pdf_dlg is not None:
            self._clean_pdf_dlg.close()
            self._clean_pdf_dlg = None

        try:
            self._statusbar.showMessage("Scanning pages for repeating text…")
            findings = self._document.scan_margin_text()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Scan failed:\n{e}")
            self._statusbar.clearMessage()
            return

        if not findings:
            self._statusbar.clearMessage()
            QMessageBox.information(
                self,
                "Nothing Found",
                "No repeating text was detected in the page margins.\n\n"
                "Detection requires text that appears on at least 30 % of pages "
                "in the top or bottom 15 % of the page.",
            )
            return

        self._statusbar.showMessage(
            f"Found {len(findings)} repeating item(s) — review and click Remove Selected.", 0
        )

        from ui.dialogs import CleanPDFDialog
        dlg = CleanPDFDialog(findings, parent=self)
        dlg.setModal(False)          # non-modal: user can scroll the PDF freely
        self._clean_pdf_dlg = dlg    # keep reference so it isn't garbage-collected
        dlg.accepted.connect(self._apply_clean_pdf)
        dlg.rejected.connect(lambda: self._statusbar.clearMessage())
        dlg.finished.connect(lambda _: setattr(self, "_clean_pdf_dlg", None))
        dlg.show()

    def _apply_clean_pdf(self):
        """Called when the user clicks Remove Selected in the Clean PDF dialog."""
        dlg = getattr(self, "_clean_pdf_dlg", None)
        if dlg is None:
            return
        selected = dlg.get_selected_findings()
        if not selected:
            self._statusbar.clearMessage()
            return
        cmd = self._run_snapshot_op(
            "Clean PDF (redact margins)",
            lambda: self._document.redact_findings(selected))
        if cmd is not None:
            total_rects, pages = cmd.result
            self._statusbar.showMessage(
                f"Removed {total_rects} item(s) across {pages} page(s).", 5000
            )
        else:
            QMessageBox.critical(
                self, "Error", "Redaction failed. See log for details.")

    def _encrypt_pdf(self):
        """Password-protect the document with AES-256 encryption."""
        if not self._document.is_open:
            return

        from PyQt6.QtWidgets import QLineEdit
        password, ok = QInputDialog.getText(
            self, "Encrypt PDF",
            "Enter a password to protect this PDF:",
            QLineEdit.EchoMode.Password,
        )
        if not ok or not password:
            return

        # Confirm the password — an encryption typo locks the file permanently.
        confirm, ok = QInputDialog.getText(
            self, "Encrypt PDF",
            "Re-enter the password to confirm:",
            QLineEdit.EchoMode.Password,
        )
        if not ok:
            return
        if confirm != password:
            QMessageBox.warning(
                self, "Passwords Do Not Match",
                "The passwords you entered do not match. "
                "The document was not encrypted.",
            )
            return

        try:
            self._document.encrypt(
                user_password=password, owner_password=password)
            self._save_document()
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to encrypt the document:\n{e}")
            return

        if not self._document.is_modified:
            self._statusbar.showMessage(
                "PDF encrypted with AES-256 and saved.", 4000)

    def _remove_password(self):
        """Remove password protection"""
        if not self._document.is_open or not self._document.doc:
            return

        if not self._document.doc.is_encrypted:
            QMessageBox.information(
                self, "No Password", "This document is not password protected.")
            return

        # Ask for current password
        from PyQt6.QtWidgets import QLineEdit
        password, ok = QInputDialog.getText(
            self, "Remove Password",
            "Enter current password to remove protection:",
            QLineEdit.EchoMode.Password
        )
        if not ok:
            return

        try:
            doc = self._document.doc
            if not doc:
                return
            # Try to authenticate with the password
            if doc.authenticate(password):
                # Save without encryption
                filepath, _ = QFileDialog.getSaveFileName(
                    self, "Save Unprotected PDF", "", "PDF Files (*.pdf)"
                )
                if filepath:
                    doc.save(
                        filepath, encryption=0)  # PDF_ENCRYPT_NONE
                    self._statusbar.showMessage(
                        "Password removed and saved", 3000)

                    if QMessageBox.question(
                        self, "Open Unprotected PDF",
                        "Do you want to open the unprotected PDF?",
                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                    ) == QMessageBox.StandardButton.Yes:
                        self._open_file(filepath)
            else:
                QMessageBox.warning(self, "Incorrect Password",
                                    "The password you entered is incorrect.")
        except Exception as e:
            QMessageBox.critical(
                self, "Error", f"Failed to remove password:\n{e}")

    def _batch_process(self):
        """Open batch processing dialog"""
        dialog = BatchDialog(self)
        dialog.exec()
