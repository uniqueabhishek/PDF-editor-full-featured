"""
Ultra PDF Editor - Edit and Search operations mixin.

Undo/redo, clipboard, select-all, and the Find / Find & Replace workflow.
Mixed into MainWindow; relies on ``self._history_manager``, ``self._viewer``,
``self._document``, ``self._statusbar`` and the search-state attributes
(``self._search_results``, ``self._current_search_index``, ``self._find_dialog``,
``self._replace_dialog``).
"""
from PyQt6.QtWidgets import QApplication, QMessageBox

from ..dialogs import FindDialog, FindReplaceDialog


class EditHandlerMixin:
    """Edit-menu operations and document search for MainWindow."""

    # ==================== Edit Operations ====================

    def _undo(self):
        """Undo last action"""
        if self._history_manager.can_undo():
            desc = self._history_manager.get_undo_description()
            command = self._history_manager.peek_undo()
            self._apply_history_step(self._history_manager.undo, command, f"Undo: {desc}")
        else:
            self._statusbar.showMessage("Nothing to undo", 2000)

    def _redo(self):
        """Redo last undone action"""
        if self._history_manager.can_redo():
            desc = self._history_manager.get_redo_description()
            command = self._history_manager.peek_redo()
            self._apply_history_step(self._history_manager.redo, command, f"Redo: {desc}")
        else:
            self._statusbar.showMessage("Nothing to redo", 2000)

    def _apply_history_step(self, action, command, success_message: str):
        """Run an undo/redo step and refresh the view to match the result.

        Commands that swap the underlying document (snapshot restore) need the
        viewer detached first so the background render worker releases the old
        document, then a full reload. Commands that change page structure need a
        reload too; lighter in-place edits only need a refresh.
        """
        swaps_document = getattr(command, "swaps_document", False)
        requires_reload = getattr(command, "requires_reload", False)

        if swaps_document:
            # Release the old document from the viewer/sidebar (and its render
            # worker) before it is closed and replaced by the snapshot.
            self._viewer.set_document(None, None)
            self._sidebar.set_document(None)

        if action():
            if requires_reload:
                self._load_document_to_viewer()
            else:
                self._viewer._page_cache.clear()
                self._viewer.refresh()
            self._is_modified = True
            self._update_title()
            self._statusbar.showMessage(success_message, 2000)
        else:
            # Re-attach whatever document is still open so the view isn't blank.
            if swaps_document:
                self._load_document_to_viewer()
            self._statusbar.showMessage("Action failed", 2000)

    def _cut(self):
        """Cut selection"""
        self._copy()
        self._delete()

    def _copy(self):
        """Copy selection"""
        # Copy selected text to clipboard
        selected_text = self._viewer.get_selected_text()
        if selected_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(selected_text)
            self._statusbar.showMessage("Text copied to clipboard", 2000)
        else:
            self._statusbar.showMessage("No text selected", 2000)

    def _paste(self):
        """Paste from clipboard"""
        clipboard = QApplication.clipboard()
        text = clipboard.text() if clipboard else ""
        if text:
            # For now, show info that paste creates text annotation
            self._statusbar.showMessage(
                "Use Text Box tool to add text to PDF", 3000)
        else:
            self._statusbar.showMessage("Clipboard is empty", 2000)

    def _delete(self):
        """Delete selection"""
        # Delete selected annotation if any
        self._statusbar.showMessage("Select an annotation to delete", 2000)

    def _select_all(self):
        """Select all text on current page"""
        if not self._document.is_open:
            return
        page_num = self._viewer.get_current_page()
        text = self._document.get_page_text(page_num)
        if text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            self._statusbar.showMessage("Page text copied to clipboard", 2000)

    def _show_find(self):
        """Show find dialog"""
        if not self._document.is_open:
            return

        if self._find_dialog is None:
            self._find_dialog = FindDialog(self)
            self._find_dialog.find_requested.connect(self._do_search)
            self._find_dialog.find_next.connect(self._find_next)
            self._find_dialog.find_prev.connect(self._find_previous)
            self._find_dialog.closed.connect(self._on_find_closed)

        self._find_dialog.show()
        self._find_dialog.raise_()
        self._find_dialog.focus_search()

    def _show_replace(self):
        """Show find and replace dialog"""
        if not self._document.is_open:
            return

        if self._replace_dialog is None:
            self._replace_dialog = FindReplaceDialog(self)
            self._replace_dialog.find_requested.connect(self._do_search)
            self._replace_dialog.find_next.connect(self._find_next)
            self._replace_dialog.find_prev.connect(self._find_previous)
            self._replace_dialog.replace_requested.connect(self._do_replace)
            self._replace_dialog.replace_all_requested.connect(
                self._do_replace_all)
            self._replace_dialog.closed.connect(self._on_replace_closed)

        self._replace_dialog.show()
        self._replace_dialog.raise_()
        self._replace_dialog.focus_search()

    def _do_search(self, text: str, case_sensitive: bool = False):
        """Perform search and update results"""
        if not self._document.is_open or not text:
            self._search_results = []
            return

        self._search_results = self._document.search_text(text, case_sensitive)
        total = sum(len(r['rects']) for r in self._search_results)

        if self._search_results:
            self._current_search_index = 0
            self._go_to_search_result(0)

            if self._find_dialog:
                self._find_dialog.set_result_count(0, total)
            if self._replace_dialog:
                self._replace_dialog.set_result_count(0, total)
        else:
            if self._find_dialog:
                self._find_dialog.set_result_count(0, 0)
            if self._replace_dialog:
                self._replace_dialog.set_result_count(0, 0)

    def _find_next(self):
        """Go to next search result"""
        if not self._search_results:
            return

        total = sum(len(r['rects']) for r in self._search_results)
        self._current_search_index = (self._current_search_index + 1) % total
        self._go_to_search_result(self._current_search_index)

        if self._find_dialog:
            self._find_dialog.set_result_count(
                self._current_search_index, total)
        if self._replace_dialog:
            self._replace_dialog.set_result_count(
                self._current_search_index, total)

    def _find_previous(self):
        """Go to previous search result"""
        if not self._search_results:
            return

        total = sum(len(r['rects']) for r in self._search_results)
        self._current_search_index = (self._current_search_index - 1) % total
        self._go_to_search_result(self._current_search_index)

        if self._find_dialog:
            self._find_dialog.set_result_count(
                self._current_search_index, total)
        if self._replace_dialog:
            self._replace_dialog.set_result_count(
                self._current_search_index, total)

    def _go_to_search_result(self, index: int):
        """Navigate to a specific search result"""
        current = 0
        for result in self._search_results:
            page_num = result['page']
            for rect in result['rects']:
                if current == index:
                    self._viewer.go_to_page(page_num)
                    return
                current += 1

    def _do_replace(self, replacement: str):
        """Replace current occurrence"""
        # PDF text replacement is complex - using redaction approach
        QMessageBox.information(
            self,
            "Replace",
            "Direct text replacement in PDFs is limited.\n"
            "Consider using the Redaction tool to remove text and then add new text."
        )

    def _do_replace_all(self, replacement: str):
        """Replace all occurrences"""
        QMessageBox.information(
            self,
            "Replace All",
            "Direct text replacement in PDFs is limited.\n"
            "PDF files store text as rendered graphics, not editable text.\n"
            "Consider exporting to Word format for text editing."
        )

    def _on_find_closed(self):
        """Handle find dialog closed"""
        self._search_results = []

    def _on_replace_closed(self):
        """Handle replace dialog closed"""
        self._search_results = []

    def _search(self, text: str):
        """Search for text (from toolbar)"""
        if not self._document.is_open or not text:
            return

        self._do_search(text, False)
        total = sum(len(r['rects']) for r in self._search_results)
        if total > 0:
            self._statusbar.showMessage(f"Found {total} matches")
        else:
            self._statusbar.showMessage("No matches found")
