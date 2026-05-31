"""
Ultra PDF Editor - Page operations mixin.

Insert, delete, extract, rotate and crop pages. Mixed into MainWindow; relies on
``self._document``, ``self._viewer``, ``self._history_manager`` and the shared
``self._load_document_to_viewer`` / ``self._update_title`` helpers.
"""
from typing import List

import fitz
from PyQt6.QtWidgets import QFileDialog, QMessageBox
from PyQt6.QtGui import QImage, QPixmap

from ..dialogs import ExtractPagesDialog, CropDialog
from utils.history import PageAddCommand, PageDeleteCommand, PageRotateCommand


class PageHandlerMixin:
    """Page-menu operations for MainWindow."""

    def _insert_blank_page(self):
        """Insert a blank page"""
        if not self._document.is_open:
            return

        current = self._viewer.get_current_page()
        command = PageAddCommand(self._document, current + 1)
        if self._history_manager.execute(command):
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage("Inserted blank page", 2000)

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
            QMessageBox.warning(self, "Cannot Delete",
                                "Cannot delete the only page in the document.")
            return

        result = QMessageBox.question(
            self, "Delete Page",
            f"Are you sure you want to delete page {page_num + 1}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if result == QMessageBox.StandardButton.Yes:
            command = PageDeleteCommand(self._document, page_num)
            if self._history_manager.execute(command):
                self._load_document_to_viewer()
                self._is_modified = True
                self._update_title()
                self._statusbar.showMessage("Deleted page", 2000)

    def _delete_pages(self, page_nums: List[int]):
        """Delete several pages at once (the pages marked in the sidebar).

        Undoable via a document snapshot; the reload that follows rebuilds the
        sidebar, which clears the deletion marks. The user saves to disk with Save
        (Ctrl+S) — consistent with every other edit.
        """
        if not self._document.is_open:
            return

        pages = sorted(set(page_nums))
        if not pages:
            return

        if len(pages) >= self._document.page_count:
            QMessageBox.warning(
                self, "Cannot Delete",
                "Cannot delete all pages — at least one page must remain.")
            return

        # Human-readable, 1-based list (cap the preview so the dialog stays small).
        labels = [str(p + 1) for p in pages]
        preview = ", ".join(labels[:12]) + (", …" if len(labels) > 12 else "")
        noun = "page" if len(pages) == 1 else "pages"
        result = QMessageBox.question(
            self, "Delete Pages",
            f"Delete {len(pages)} {noun} ({preview})?\n\nYou can undo this with Ctrl+Z.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        if self._run_snapshot_op(
                f"Delete {len(pages)} {noun}",
                lambda: self._document.delete_pages(pages)) is not None:
            self._statusbar.showMessage(f"Deleted {len(pages)} {noun}", 2000)

    def _rotate_page(self, page_num: int, degrees: int = 90):
        """Rotate a specific page"""
        if not self._document.is_open:
            return

        command = PageRotateCommand(self._document, page_num, degrees)
        if self._history_manager.execute(command):
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage("Rotated page", 2000)

    def _reorder_page(self, from_index: int, before_index: int):
        """Move a page via thumbnail drag-and-drop.

        ``before_index`` is the position (in current page coordinates) to insert
        the page in front of; ``page_count`` means move it to the end.
        """
        if not self._document.is_open:
            return
        count = self._document.page_count
        if not (0 <= from_index < count):
            return

        # Build the target order, then reorder in one operation (avoids any
        # ambiguity in single-page move semantics).
        order = list(range(count))
        page = order.pop(from_index)
        insert_at = before_index if before_index <= from_index else before_index - 1
        insert_at = max(0, min(insert_at, len(order)))
        order.insert(insert_at, page)
        if order == list(range(count)):
            return  # dropped back in the same place

        if self._run_snapshot_op(
                "Reorder pages",
                lambda: self._document.reorder_pages(order)) is not None:
            self._statusbar.showMessage("Page moved", 2000)

    def _extract_pages(self):
        """Extract pages to new PDF"""
        if not self._document.is_open:
            return

        dialog = ExtractPagesDialog(
            self._document.page_count, self._viewer.get_current_page(), self)
        if dialog.exec():
            pages = dialog.get_selected_pages()
            if pages:
                filepath, _ = QFileDialog.getSaveFileName(
                    self, "Save Extracted Pages", "", "PDF Files (*.pdf)"
                )
                if filepath:
                    try:
                        self._document.extract_pages(pages, filepath)
                        self._statusbar.showMessage(
                            f"Extracted {len(pages)} pages", 3000)

                        if QMessageBox.question(
                            self, "Open Extracted PDF",
                            "Do you want to open the extracted PDF?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        ) == QMessageBox.StandardButton.Yes:
                            self._open_file(filepath)
                    except Exception as e:
                        QMessageBox.critical(
                            self, "Error", f"Failed to extract pages:\n{e}")

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
        if not self._document.is_open or not self._document.doc:
            return

        page_num = self._viewer.get_current_page()
        page = self._document.doc[page_num]
        rect = page.rect

        # Render page for preview - create a QPixmap
        pix = page.get_pixmap(matrix=fitz.Matrix(0.5, 0.5))
        img = QImage(pix.samples, pix.width, pix.height,
                     pix.stride, QImage.Format.Format_RGB888)
        preview_pixmap = QPixmap.fromImage(img)

        dialog = CropDialog(preview_pixmap, rect.width, rect.height, self)
        if not dialog.exec():
            return

        crop_rect = dialog.get_crop_rect()
        apply_all = dialog.apply_to_all_pages()
        ref_w, ref_h = rect.width, rect.height

        def _do():
            doc = self._document.doc
            doc[page_num].set_cropbox(
                fitz.Rect(crop_rect[0], crop_rect[1], crop_rect[2], crop_rect[3]))
            if apply_all:
                for i in range(self._document.page_count):
                    if i == page_num:
                        continue
                    p = doc[i]
                    p_rect = p.rect
                    # Scale crop proportionally to each page's size.
                    scale_x = p_rect.width / ref_w
                    scale_y = p_rect.height / ref_h
                    p.set_cropbox(fitz.Rect(
                        crop_rect[0] * scale_x, crop_rect[1] * scale_y,
                        crop_rect[2] * scale_x, crop_rect[3] * scale_y))

        if self._run_snapshot_op("Crop page(s)", _do) is not None:
            self._statusbar.showMessage("Page(s) cropped", 2000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to crop page(s). See log for details.")
