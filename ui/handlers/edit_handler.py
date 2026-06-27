"""
Ultra PDF Editor - Edit and Search operations mixin.

Undo/redo, clipboard, select-all, and the Find / Find & Replace workflow.
Mixed into MainWindow; relies on ``self._history_manager``, ``self._viewer``,
``self._document``, ``self._statusbar`` and the search-state attributes
(``self._search_results``, ``self._current_search_index``, ``self._find_dialog``,
``self._replace_dialog``).
"""
from typing import TYPE_CHECKING

from PyQt6.QtWidgets import QApplication, QMessageBox

from ..dialogs import FindDialog, FindReplaceDialog

if TYPE_CHECKING:
    from ._context import MainWindowContext
    _MixinBase = MainWindowContext
else:
    _MixinBase = object


class EditHandlerMixin(_MixinBase):
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
        """Copy the selected text to the clipboard, then erase the selection."""
        selected_text = self._viewer.get_selected_text()
        if selected_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(selected_text)
        self._delete()

    def _copy(self):
        """Copy selected text to the clipboard (Ctrl+C / Edit menu)."""
        selected_text = self._viewer.get_selected_text()
        if selected_text:
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(selected_text)
            self._on_selection_copied(len(selected_text))
        else:
            self._statusbar.showMessage("No text selected", 2000)

    def _on_selection_copied(self, count: int):
        """Show a status-bar confirmation after text is copied to the clipboard."""
        noun = "character" if count == 1 else "characters"
        self._statusbar.showMessage(
            f"Copied {count} {noun} to clipboard", 2000)

    def _on_selection_needs_ocr(self):
        """Hint to run OCR when selecting on a page with no text layer (a scan)."""
        self._statusbar.showMessage(
            "No selectable text here — run Tools → OCR to make a "
            "scanned page searchable", 4000)

    def _paste(self):
        """Paste clipboard text as a text box on the current page."""
        if not self._document.is_open:
            return
        clipboard = QApplication.clipboard()
        text = clipboard.text() if clipboard else ""
        if not text:
            self._statusbar.showMessage("Clipboard is empty", 2000)
            return

        page_num = self._viewer.get_current_page()
        try:
            info = self._document.get_page_info(page_num)
        except Exception:
            return
        # A reasonable default text-box rectangle near the top-left of the page.
        rect = (50.0, 50.0, max(150.0, min(info.width - 50.0, 400.0)), 150.0)
        # Reuse the annotation pipeline (undoable, refreshes the view).
        self._create_annotation(page_num, "text_box", rect, {"text": text})

    def _delete(self):
        """Erase (redact) the selected region; undoable until the file is saved."""
        if not self._document.is_open:
            return
        selection = self._viewer.get_selection()
        if selection is None:
            self._statusbar.showMessage(
                "Select an area first (Select tool), then Delete", 3000)
            return
        page_num, rect = selection
        if self._run_snapshot_op(
                "Erase selection",
                lambda: self._document.redact_area(page_num, rect)) is not None:
            self._viewer.clear_selection()
            self._statusbar.showMessage("Erased selection (Undo to restore)", 3000)

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
            self._viewer.clear_search_results()
            self._update_search_count(0, 0)
            return

        self._search_results = self._document.search_text(text, case_sensitive)
        total = sum(len(r['rects']) for r in self._search_results)
        self._viewer.set_search_results(self._search_results)

        if self._search_results:
            self._current_search_index = 0
            self._go_to_search_result(0)
            self._update_search_count(0, total)
        else:
            self._update_search_count(0, 0)

    def _update_search_count(self, current: int, total: int):
        """Reflect the active match position in the toolbar and any open dialogs."""
        if self._find_dialog:
            self._find_dialog.set_result_count(current, total)
        if self._replace_dialog:
            self._replace_dialog.set_result_count(current, total)
        toolbar = getattr(self, "_main_toolbar", None)
        search_widget = getattr(toolbar, "search_widget", None)
        if search_widget is not None:
            # The toolbar shows "n/total"; make it 1-based for humans.
            search_widget.set_result_count(current + 1 if total else 0, total)

    def _find_next(self):
        """Go to next search result"""
        if not self._search_results:
            return

        total = sum(len(r['rects']) for r in self._search_results)
        self._current_search_index = (self._current_search_index + 1) % total
        self._go_to_search_result(self._current_search_index)
        self._update_search_count(self._current_search_index, total)

    def _find_previous(self):
        """Go to previous search result"""
        if not self._search_results:
            return

        total = sum(len(r['rects']) for r in self._search_results)
        self._current_search_index = (self._current_search_index - 1) % total
        self._go_to_search_result(self._current_search_index)
        self._update_search_count(self._current_search_index, total)

    def _go_to_search_result(self, index: int):
        """Navigate to and highlight a specific search result"""
        target = self._occurrence_at(index)
        if target is None:
            return
        page_num, rect = target
        self._viewer.scroll_to_search_result(page_num, rect)

    def _replace_search_params(self):
        """The (search_text, case_sensitive) currently entered in the dialog."""
        dlg = self._replace_dialog
        if dlg is None:
            return "", False
        return dlg.get_search_text(), dlg.is_case_sensitive()

    def _occurrence_at(self, index: int):
        """Map a flat search-result index to (page_num, rect tuple), or None."""
        current = 0
        for result in self._search_results:
            for rect in result["rects"]:
                if current == index:
                    return result["page"], rect
                current += 1
        return None

    def _do_replace(self, replacement: str):
        """Replace the current occurrence (redaction-based), then re-search."""
        if not self._document.is_open:
            return
        search, case_sensitive = self._replace_search_params()
        if not self._search_results:
            self._statusbar.showMessage("Find some text first", 2000)
            return
        target = self._occurrence_at(self._current_search_index)
        if target is None:
            return
        page_num, rect = target
        if self._run_snapshot_op(
                "Replace text",
                lambda: self._document.replace_text_one(
                    page_num, rect, replacement)) is not None:
            # Positions changed; re-run the search to refresh highlights/count.
            self._do_search(search, case_sensitive)
            self._statusbar.showMessage("Replaced 1 occurrence", 2000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to replace text. See log for details.")

    def _do_replace_all(self, replacement: str):
        """Replace all occurrences of the search term (redaction-based)."""
        if not self._document.is_open:
            return
        search, case_sensitive = self._replace_search_params()
        if not search:
            self._statusbar.showMessage("Find some text first", 2000)
            return
        cmd = self._run_snapshot_op(
            "Replace all",
            lambda: self._document.replace_text_all(
                search, replacement, case_sensitive))
        if cmd is not None:
            count = cmd.result
            self._do_search(search, case_sensitive)  # matches are gone now
            self._statusbar.showMessage(
                f"Replaced {count} occurrence(s)", 3000)
        else:
            QMessageBox.critical(
                self, "Error", "Failed to replace text. See log for details.")

    def _on_find_closed(self):
        """Handle find dialog closed"""
        self._search_results = []
        self._viewer.clear_search_results()

    def _on_replace_closed(self):
        """Handle replace dialog closed"""
        self._search_results = []
        self._viewer.clear_search_results()

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
