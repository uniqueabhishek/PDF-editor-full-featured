"""Type-checking-only declaration of the contract the handler mixins rely on.

The action handlers under ``ui.handlers`` are mixins composed into
:class:`ui.main_window.MainWindow`. They reference shared state
(``self._document``, ``self._viewer``, …) and helpers (``self._update_title``,
``self._run_snapshot_op``, …) that live on ``MainWindow`` or on a sibling mixin,
so a type checker reading a mixin in isolation cannot see them.

Each mixin declares ``MainWindowContext`` as its base **only while type
checking** (at runtime the base is ``object``), which gives the checker the full
``QMainWindow`` widget API plus the app-specific members below — without any
runtime metaclass conflict between ``Protocol``/Qt's ``sip`` metaclass.

Usage in a mixin module::

    from typing import TYPE_CHECKING
    if TYPE_CHECKING:
        from ._context import MainWindowContext
        _MixinBase = MainWindowContext
    else:
        _MixinBase = object

    class FileHandlerMixin(_MixinBase):
        ...
"""
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path
    from typing import Any, Callable, Dict, List, Optional

    from PyQt6.QtWidgets import QDialog, QLabel, QMainWindow, QStatusBar

    from config import UserSettings
    from core.pdf_document import PDFDocument
    from utils.history import CommandType, HistoryManager

    from ..dialogs import FindDialog, FindReplaceDialog
    from ..pdf_viewer import PDFViewer
    from ..sidebar import Sidebar
    from ..toolbar import MainToolbar

    class MainWindowContext(QMainWindow):
        """The surface MainWindow exposes to its handler mixins (typing only)."""

        # --- shared state ---
        _document: PDFDocument
        _viewer: PDFViewer
        _sidebar: Sidebar
        _settings: UserSettings
        _main_toolbar: MainToolbar
        _statusbar: QStatusBar
        _file_size_label: QLabel
        _current_file: Optional[Path]
        _is_modified: bool
        _history_manager: HistoryManager
        _search_results: List[Dict]
        _current_search_index: int
        _find_dialog: Optional[FindDialog]
        _replace_dialog: Optional[FindReplaceDialog]
        _clean_pdf_dlg: Optional[QDialog]

        # --- shared helpers (MainWindow) ---
        def _load_document_to_viewer(self) -> None: ...
        def _update_title(self) -> None: ...
        def _update_actions_state(self) -> None: ...
        def _update_recent_files_menu(self) -> None: ...
        def _format_size(self, size_bytes: int) -> str: ...
        def _confirm_close(self) -> bool: ...
        def _clear_autosave(self) -> None: ...
        def _run_snapshot_op(
            self, description: str, operation: "Callable[[], Any]",
            command_type: "Optional[CommandType]" = None) -> "Any": ...

        # --- cross-mixin handlers ---
        def _open_file(self, filepath: str) -> None: ...
        def _save_document(self) -> None: ...
        def _save_document_as(self) -> None: ...
        def _compress_pdf(self) -> None: ...
        def _create_annotation(self, page_num: int, annot_type: str,
                               rect: "Any", data: Dict) -> None: ...
        def _apply_area_redaction(self, page_num: int, rect: "Any") -> None: ...
        def _delete(self) -> None: ...
        def _delete_page(self, page_num: int) -> None: ...
        def _apply_history_step(self, action: "Callable[[], bool]",
                                command: "Any", success_message: str) -> None: ...
        def _do_search(self, text: str, case_sensitive: bool = False) -> None: ...
        def _go_to_search_result(self, index: int) -> None: ...
        def _find_next(self) -> None: ...
        def _find_previous(self) -> None: ...
        def _do_replace(self, replacement: str) -> None: ...
        def _do_replace_all(self, replacement: str) -> None: ...
        def _on_find_closed(self) -> None: ...
        def _on_replace_closed(self) -> None: ...
        def _apply_clean_pdf(self) -> None: ...
