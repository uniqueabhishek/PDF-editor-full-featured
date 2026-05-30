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
        if dialog.exec():
            crop_rect = dialog.get_crop_rect()
            try:
                # Apply crop to the page
                new_rect = fitz.Rect(
                    crop_rect[0], crop_rect[1], crop_rect[2], crop_rect[3])
                page.set_cropbox(new_rect)

                # Apply to all pages if requested
                if dialog.apply_to_all_pages():
                    for i in range(self._document.page_count):
                        if i != page_num:
                            p = self._document.doc[i]
                            p_rect = p.rect
                            # Scale crop proportionally
                            scale_x = p_rect.width / rect.width
                            scale_y = p_rect.height / rect.height
                            p_new_rect = fitz.Rect(
                                crop_rect[0] * scale_x,
                                crop_rect[1] * scale_y,
                                crop_rect[2] * scale_x,
                                crop_rect[3] * scale_y
                            )
                            p.set_cropbox(p_new_rect)

                self._load_document_to_viewer()
                self._is_modified = True
                self._update_title()
                self._statusbar.showMessage("Page(s) cropped", 2000)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error", f"Failed to crop page:\n{e}")
