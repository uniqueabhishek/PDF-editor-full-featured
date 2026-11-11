"""
Ultra PDF Editor - Find and Replace Dialog
"""

from typing import Any, cast

from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QCheckBox,
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

# Live search waits for a pause in typing, and only for terms this long; a
# shorter term is searched when the user presses Enter / Find Next. Searching
# a 300-page file on every keystroke froze the window 1-4 s per key.
_LIVE_SEARCH_DELAY_MS = 300
_LIVE_SEARCH_MIN_CHARS = 2


class _DebouncedSearchMixin:
    """Find-as-you-type without a full-document search on every keystroke.

    Host classes provide ``_search_input``, ``_case_sensitive`` and the
    ``find_requested`` / ``find_next`` / ``find_prev`` signals.
    """

    _search_input: QLineEdit
    _case_sensitive: QCheckBox
    find_requested: Any  # pyqtSignal(str, bool) on the host class

    def _init_live_search(self):
        self._searched: tuple[str, bool] | None = None  # last sent as find_requested
        self._live_timer = QTimer(cast(QDialog, self))
        self._live_timer.setSingleShot(True)
        self._live_timer.setInterval(_LIVE_SEARCH_DELAY_MS)
        self._live_timer.timeout.connect(self._live_search_due)
        self._case_sensitive.toggled.connect(lambda _on: self._schedule_live_search())

    def _schedule_live_search(self):
        if len(self._search_input.text().strip()) >= _LIVE_SEARCH_MIN_CHARS:
            self._live_timer.start()
        else:
            self._live_timer.stop()

    def _live_search_due(self):
        self._flush_search()

    def _flush_search(self) -> bool:
        """Run the search now if the current term has not been searched yet.

        Returns True if a search was started (results then begin at the first
        match, so the caller should not also step to the next one).
        """
        self._live_timer.stop()
        text = self._search_input.text()
        if not text.strip():
            return False
        key = (text, self._case_sensitive.isChecked())
        if key == self._searched:
            return False
        self._searched = key
        self.find_requested.emit(*key)
        return True

    def _step(self, signal):
        if self._search_input.text().strip() and not self._flush_search():
            signal.emit()


class FindDialog(_DebouncedSearchMixin, QDialog):
    """Find dialog for searching text in PDF"""

    find_requested = pyqtSignal(str, bool)  # text, case_sensitive
    find_next = pyqtSignal()
    find_prev = pyqtSignal()
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(400)

        self._setup_ui()
        self._setup_shortcuts()
        self._init_live_search()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Search input row
        search_layout = QHBoxLayout()
        search_layout.addWidget(QLabel("Find:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter text to find...")
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._find_next)
        search_layout.addWidget(self._search_input)
        layout.addLayout(search_layout)

        # Options
        options_layout = QHBoxLayout()
        self._case_sensitive = QCheckBox("Match case")
        options_layout.addWidget(self._case_sensitive)
        options_layout.addStretch()

        # Result count
        self._result_label = QLabel("")
        options_layout.addWidget(self._result_label)
        layout.addLayout(options_layout)

        # Buttons
        button_layout = QHBoxLayout()

        self._find_prev_btn = QPushButton("Find Previous")
        self._find_prev_btn.clicked.connect(self._find_prev)
        self._find_prev_btn.setEnabled(False)
        button_layout.addWidget(self._find_prev_btn)

        self._find_next_btn = QPushButton("Find Next")
        self._find_next_btn.clicked.connect(self._find_next)
        self._find_next_btn.setEnabled(False)
        self._find_next_btn.setDefault(True)
        button_layout.addWidget(self._find_next_btn)

        button_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        button_layout.addWidget(self._close_btn)

        layout.addLayout(button_layout)

    def _setup_shortcuts(self):
        # F3 for find next
        QShortcut(QKeySequence("F3"), self, self._find_next)
        # Shift+F3 for find previous
        QShortcut(QKeySequence("Shift+F3"), self, self._find_prev)
        # Escape to close
        QShortcut(QKeySequence("Escape"), self, self.close)

    def _on_text_changed(self, text: str):
        """Handle search text change"""
        has_text = bool(text.strip())
        self._find_next_btn.setEnabled(has_text)
        self._find_prev_btn.setEnabled(has_text)
        self._schedule_live_search()

    def _find_next(self):
        """Find next occurrence (searches first if the term is new)."""
        self._step(self.find_next)

    def _find_prev(self):
        """Find previous occurrence (searches first if the term is new)."""
        self._step(self.find_prev)

    def set_result_count(self, current: int, total: int):
        """Update result count display"""
        if total == 0:
            self._result_label.setText("No matches found")
            self._result_label.setStyleSheet("color: #cc0000;")
        else:
            self._result_label.setText(f"{current + 1} of {total}")
            self._result_label.setStyleSheet("color: #006600;")

    def get_search_text(self) -> str:
        """Get current search text"""
        return self._search_input.text().strip()

    def is_case_sensitive(self) -> bool:
        """Check if case sensitive search"""
        return self._case_sensitive.isChecked()

    def set_search_text(self, text: str):
        """Set search text"""
        self._search_input.setText(text)
        self._search_input.selectAll()

    def focus_search(self):
        """Focus the search input"""
        self._search_input.setFocus()
        self._search_input.selectAll()

    def closeEvent(self, event):
        """Handle close event"""
        # Results are dropped on close; search afresh when reopened.
        self._live_timer.stop()
        self._searched = None
        self.closed.emit()
        super().closeEvent(event)


class FindReplaceDialog(_DebouncedSearchMixin, QDialog):
    """Find and Replace dialog"""

    find_requested = pyqtSignal(str, bool)  # text, case_sensitive
    find_next = pyqtSignal()
    find_prev = pyqtSignal()
    replace_requested = pyqtSignal(str)  # replacement text
    replace_all_requested = pyqtSignal(str)  # replacement text
    closed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Find and Replace")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)

        self._setup_ui()
        self._setup_shortcuts()
        self._init_live_search()

    def _setup_ui(self):  # noqa: PLR0915 - widget layout built in order
        layout = QVBoxLayout(self)

        # Find input row
        find_layout = QHBoxLayout()
        find_layout.addWidget(QLabel("Find:"))
        self._search_input = QLineEdit()
        self._search_input.setPlaceholderText("Enter text to find...")
        self._search_input.textChanged.connect(self._on_text_changed)
        self._search_input.returnPressed.connect(self._find_next)
        find_layout.addWidget(self._search_input)
        layout.addLayout(find_layout)

        # Replace input row
        replace_layout = QHBoxLayout()
        replace_layout.addWidget(QLabel("Replace:"))
        self._replace_input = QLineEdit()
        self._replace_input.setPlaceholderText("Enter replacement text...")
        replace_layout.addWidget(self._replace_input)
        layout.addLayout(replace_layout)

        # Options
        options_layout = QHBoxLayout()
        self._case_sensitive = QCheckBox("Match case")
        options_layout.addWidget(self._case_sensitive)
        options_layout.addStretch()

        # Result count
        self._result_label = QLabel("")
        options_layout.addWidget(self._result_label)
        layout.addLayout(options_layout)

        # Warning about PDF replacement
        warning = QLabel(
            "Note: Text replacement in PDFs is limited and may not preserve formatting."
        )
        warning.setStyleSheet("color: #996600; font-size: 11px;")
        warning.setWordWrap(True)
        layout.addWidget(warning)

        # Find buttons
        find_btn_layout = QHBoxLayout()
        self._find_prev_btn = QPushButton("Find Previous")
        self._find_prev_btn.clicked.connect(self._find_prev)
        self._find_prev_btn.setEnabled(False)
        find_btn_layout.addWidget(self._find_prev_btn)

        self._find_next_btn = QPushButton("Find Next")
        self._find_next_btn.clicked.connect(self._find_next)
        self._find_next_btn.setEnabled(False)
        find_btn_layout.addWidget(self._find_next_btn)

        find_btn_layout.addStretch()
        layout.addLayout(find_btn_layout)

        # Replace buttons
        replace_btn_layout = QHBoxLayout()
        self._replace_btn = QPushButton("Replace")
        self._replace_btn.clicked.connect(self._replace)
        self._replace_btn.setEnabled(False)
        replace_btn_layout.addWidget(self._replace_btn)

        self._replace_all_btn = QPushButton("Replace All")
        self._replace_all_btn.clicked.connect(self._replace_all)
        self._replace_all_btn.setEnabled(False)
        replace_btn_layout.addWidget(self._replace_all_btn)

        replace_btn_layout.addStretch()

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(self.close)
        replace_btn_layout.addWidget(self._close_btn)

        layout.addLayout(replace_btn_layout)

    def _setup_shortcuts(self):
        QShortcut(QKeySequence("F3"), self, self._find_next)
        QShortcut(QKeySequence("Shift+F3"), self, self._find_prev)
        QShortcut(QKeySequence("Escape"), self, self.close)

    def _on_text_changed(self, text: str):
        """Handle search text change"""
        has_text = bool(text.strip())
        self._find_next_btn.setEnabled(has_text)
        self._find_prev_btn.setEnabled(has_text)
        self._replace_btn.setEnabled(has_text)
        self._replace_all_btn.setEnabled(has_text)
        self._schedule_live_search()

    def _find_next(self):
        self._step(self.find_next)

    def _find_prev(self):
        self._step(self.find_prev)

    def _replace(self):
        """Replace current occurrence"""
        # Make sure the highlighted match belongs to the term in the box.
        self._flush_search()
        self.replace_requested.emit(self._replace_input.text())

    def _replace_all(self):
        """Replace all occurrences"""
        result = QMessageBox.question(
            self,
            "Replace All",
            f"Replace all occurrences of '{self._search_input.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if result == QMessageBox.StandardButton.Yes:
            self.replace_all_requested.emit(self._replace_input.text())

    def set_result_count(self, current: int, total: int):
        """Update result count display"""
        if total == 0:
            self._result_label.setText("No matches found")
            self._result_label.setStyleSheet("color: #cc0000;")
        else:
            self._result_label.setText(f"{current + 1} of {total}")
            self._result_label.setStyleSheet("color: #006600;")

    def get_search_text(self) -> str:
        return self._search_input.text().strip()

    def get_replace_text(self) -> str:
        return self._replace_input.text()

    def is_case_sensitive(self) -> bool:
        return self._case_sensitive.isChecked()

    def focus_search(self):
        self._search_input.setFocus()
        self._search_input.selectAll()

    def closeEvent(self, event):
        # Results are dropped on close; search afresh when reopened.
        self._live_timer.stop()
        self._searched = None
        self.closed.emit()
        super().closeEvent(event)
