"""
Ultra PDF Editor - Annotation and redaction mixin.

Handles tool-mode changes from the annotation toolbar, routes annotation-creation
requests from the viewer through the undo/redo history, and performs area
redaction. Mixed into MainWindow; relies on ``self._document``, ``self._viewer``,
``self._history_manager`` and ``self._statusbar``.
"""
from typing import TYPE_CHECKING, Any, Dict

from PyQt6.QtWidgets import QMessageBox

from ..pdf_viewer import ToolMode
from utils.history import AnnotationAddCommand

if TYPE_CHECKING:
    from ._context import MainWindowContext
    _MixinBase = MainWindowContext
else:
    _MixinBase = object


class AnnotationHandlerMixin(_MixinBase):
    """Annotation toolbar and redaction handling for MainWindow."""

    def _on_tool_changed(self, tool: str):
        """Handle tool change"""
        try:
            mode = ToolMode(tool)
            self._viewer.set_tool_mode(mode)
        except ValueError:
            pass  # Ignore unknown tool modes

    def _on_edit_text_committed(self, page_num: int, bbox, new_text: str,
                                style: Dict) -> None:
        """Apply a committed inline text edit (Edit Text tool), undoably."""
        if not self._document.is_open:
            return
        cmd = self._run_snapshot_op(
            "Edit text",
            lambda: self._document.replace_text_block(
                page_num, bbox, new_text, style))
        if cmd is None:
            QMessageBox.critical(
                self, "Edit Text", "Failed to edit text. See log for details.")
            return
        result = getattr(cmd, "result", None) or {}
        if result.get("truncated"):
            self._statusbar.showMessage(
                "Text edited — too long for the box, shrunk to fit and clipped "
                "(Undo to revert)", 4000)
        elif str(result.get("font", "")).startswith("base14"):
            self._statusbar.showMessage(
                "Text edited — original font lacked some glyphs, used a close "
                "match (Undo to revert)", 4000)
        else:
            self._statusbar.showMessage("Text edited (Undo to revert)", 3000)

    def _on_edit_text_unavailable(self, _page_num: int) -> None:
        """Hint when the user double-clicks where there is no editable text."""
        self._statusbar.showMessage(
            "No editable text there. If this is a scanned page, run "
            "Tools → OCR first.", 4000)

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
            # The edit is in place; refresh the render worker's copy and re-render
            # just this page (no full reload, so the view position is preserved).
            self._viewer.invalidate_render_copy(page_num)
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage(f"Added {annot_type} annotation", 2000)
        else:
            self._statusbar.showMessage(f"Failed to add {annot_type} annotation", 2000)

    def _go_to_annotation(self, page_num: int, _index: int) -> None:
        """Navigate to the page of an annotation clicked in the sidebar panel."""
        self._viewer.go_to_page(page_num)

    def _delete_annotation(self, page_num: int, xref: int) -> None:
        """Delete the annotation (identified by xref) chosen in the sidebar; undoable."""
        if not self._document.is_open or not self._document.doc:
            return
        doc = self._document.doc
        if not (0 <= page_num < doc.page_count):
            return
        page = doc[page_num]
        if not any(annot.xref == xref for annot in page.annots()):
            return  # already gone (e.g. removed by an earlier undo/redo)

        def _do():
            pg = self._document.doc[page_num]
            for annot in pg.annots():
                if annot.xref == xref:
                    pg.delete_annot(annot)
                    return

        if self._run_snapshot_op("Delete annotation", _do) is not None:
            self._statusbar.showMessage("Annotation deleted (Undo to restore)", 2000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to delete annotation. See log for details.")

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
        """Show confirmation dialog then erase the selected rectangle."""
        result = QMessageBox.question(
            self,
            "Erase Area",
            "Erase the selected area?\n\nThe content is removed from the page; "
            "you can Undo this until the document is saved.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        import fitz
        fitz_rect = fitz.Rect(
            rect.x(), rect.y(),
            rect.x() + rect.width(),
            rect.y() + rect.height(),
        )
        cmd = self._run_snapshot_op(
            "Erase area", lambda: self._document.redact_area(page_num, fitz_rect))
        if cmd is not None:
            self._statusbar.showMessage("Area erased.", 3000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to erase area. See log for details.")
