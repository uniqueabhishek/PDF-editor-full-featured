"""
Ultra PDF Editor - Find and Replace Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QCheckBox, QLabel, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeySequence, QShortcut


class FindDialog(QDialog):
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

        if has_text:
            self.find_requested.emit(text, self._case_sensitive.isChecked())

    def _find_next(self):
        """Find next occurrence"""
        text = self._search_input.text().strip()
        if text:
            self.find_next.emit()

    def _find_prev(self):
        """Find previous occurrence"""
        text = self._search_input.text().strip()
        if text:
            self.find_prev.emit()

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
        self.closed.emit()
        super().closeEvent(event)


class FindReplaceDialog(QDialog):
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

    def _setup_ui(self):
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

        if has_text:
            self.find_requested.emit(text, self._case_sensitive.isChecked())

    def _find_next(self):
        text = self._search_input.text().strip()
        if text:
            self.find_next.emit()

    def _find_prev(self):
        text = self._search_input.text().strip()
        if text:
            self.find_prev.emit()

    def _replace(self):
        """Replace current occurrence"""
        self.replace_requested.emit(self._replace_input.text())

    def _replace_all(self):
        """Replace all occurrences"""
        result = QMessageBox.question(
            self,
            "Replace All",
            f"Replace all occurrences of '{self._search_input.text()}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
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
        self.closed.emit()
        super().closeEvent(event)
