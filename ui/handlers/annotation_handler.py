"""
Ultra PDF Editor - Annotation and redaction mixin.

Handles tool-mode changes from the annotation toolbar, routes annotation-creation
requests from the viewer through the undo/redo history, and performs area
redaction. Mixed into MainWindow; relies on ``self._document``, ``self._viewer``,
``self._history_manager`` and ``self._statusbar``.
"""
from typing import Any, Dict

from PyQt6.QtWidgets import QMessageBox

from ..pdf_viewer import ToolMode
from utils.history import AnnotationAddCommand


class AnnotationHandlerMixin:
    """Annotation toolbar and redaction handling for MainWindow."""

    def _on_tool_changed(self, tool: str):
        """Handle tool change"""
        try:
            mode = ToolMode(tool)
            self._viewer.set_tool_mode(mode)
        except ValueError:
            pass  # Ignore unknown tool modes

    def _create_annotation(self, page_num: int, annot_type: str, rect: Any, data: Dict):
        """Handle annotation creation request"""
        if not self._document.is_open:
            return

        if annot_type == "redact":
            self._apply_area_redaction(page_num, rect)
            return

        command = AnnotationAddCommand(
            self._document, page_num, annot_type, rect, data)
        if self._history_manager.execute(command):
            # We don't need to full reload, just refresh view?
            # Ideally we just repaint, but to be safe and consistent:
            # Clear cache for this page
            self._viewer._page_cache.pop(page_num, None)
            self._viewer._render_worker.request_page(
                page_num, self._viewer._zoom)
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage(f"Added {annot_type} annotation", 2000)
        else:
            self._statusbar.showMessage(f"Failed to add {annot_type} annotation", 2000)

    def _activate_erase_selection(self) -> None:
        """Switch to Erase Selection tool so the user can draw a rectangle to erase."""
        if not self._document.is_open:
            QMessageBox.information(self, "No Document", "Please open a PDF first.")
            return
        self._viewer.set_tool_mode(ToolMode.REDACT)
        self._statusbar.showMessage(
            "Erase Selection: draw a rectangle on the page to permanently erase that area.", 0
        )

    def _apply_area_redaction(self, page_num: int, rect) -> None:
        """Show confirmation dialog then permanently erase the selected rectangle."""
        result = QMessageBox.question(
            self,
            "Erase Area",
            "Permanently erase the selected area?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return
        try:
            import fitz
            fitz_rect = fitz.Rect(
                rect.x(), rect.y(),
                rect.x() + rect.width(),
                rect.y() + rect.height(),
            )
            self._document.redact_area(page_num, fitz_rect)
            self._load_document_to_viewer()
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage("Area erased.", 3000)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to erase area:\n{e}")
