"""
Ultra PDF Editor - Extract Pages Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QFileDialog, QMessageBox, QGroupBox, QRadioButton
)
from PyQt6.QtCore import Qt
from typing import List, Optional
import re


class ExtractPagesDialog(QDialog):
    """Dialog for extracting pages from a PDF"""

    def __init__(self, page_count: int, current_page: int = 0, parent=None):
        super().__init__(parent)
        self._page_count = page_count
        self._current_page = current_page
        self._output_path: Optional[str] = None
        self._selected_pages: List[int] = []

        self.setWindowTitle("Extract Pages")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(450)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Page selection
        selection_group = QGroupBox("Select Pages to Extract")
        selection_layout = QVBoxLayout(selection_group)

        # All pages option
        self._all_pages_radio = QRadioButton(f"All pages (1-{self._page_count})")
        selection_layout.addWidget(self._all_pages_radio)

        # Current page option
        self._current_page_radio = QRadioButton(f"Current page ({self._current_page + 1})")
        selection_layout.addWidget(self._current_page_radio)

        # Page range option
        range_layout = QHBoxLayout()
        self._range_radio = QRadioButton("Page range:")
        self._range_radio.setChecked(True)
        range_layout.addWidget(self._range_radio)

        self._range_input = QLineEdit()
        self._range_input.setPlaceholderText("e.g., 1-5, 8, 10-12")
        self._range_input.setText(f"1-{self._page_count}")
        range_layout.addWidget(self._range_input)
        selection_layout.addLayout(range_layout)

        # Help text
        help_label = QLabel(
            "Enter page numbers separated by commas.\n"
            "Use hyphen for ranges (e.g., 1-5, 8, 10-12)"
        )
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        selection_layout.addWidget(help_label)

        layout.addWidget(selection_group)

        # Output file
        output_group = QGroupBox("Output File")
        output_layout = QHBoxLayout(output_group)

        self._output_input = QLineEdit()
        self._output_input.setPlaceholderText("Select output file...")
        self._output_input.setReadOnly(True)
        output_layout.addWidget(self._output_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        self._extract_btn = QPushButton("Extract")
        self._extract_btn.clicked.connect(self._extract)
        self._extract_btn.setDefault(True)
        button_layout.addWidget(self._extract_btn)

        layout.addLayout(button_layout)

        # Connect radio buttons
        self._all_pages_radio.toggled.connect(self._on_selection_changed)
        self._current_page_radio.toggled.connect(self._on_selection_changed)
        self._range_radio.toggled.connect(self._on_selection_changed)

    def _on_selection_changed(self):
        """Enable/disable range input based on selection"""
        self._range_input.setEnabled(self._range_radio.isChecked())

    def _browse_output(self):
        """Browse for output file"""
        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Extracted Pages",
            "extracted_pages.pdf",
            "PDF Files (*.pdf)"
        )
        if filepath:
            if not filepath.lower().endswith('.pdf'):
                filepath += '.pdf'
            self._output_input.setText(filepath)
            self._output_path = filepath

    def _parse_page_range(self, range_str: str) -> List[int]:
        """Parse page range string into list of page numbers (0-indexed)"""
        pages = []
        range_str = range_str.strip()

        if not range_str:
            return pages

        parts = range_str.split(',')
        for part in parts:
            part = part.strip()
            if '-' in part:
                # Range like "1-5"
                match = re.match(r'(\d+)\s*-\s*(\d+)', part)
                if match:
                    start = int(match.group(1)) - 1  # Convert to 0-indexed
                    end = int(match.group(2)) - 1
                    if 0 <= start < self._page_count and 0 <= end < self._page_count:
                        pages.extend(range(min(start, end), max(start, end) + 1))
            else:
                # Single page like "8"
                try:
                    page = int(part) - 1  # Convert to 0-indexed
                    if 0 <= page < self._page_count:
                        pages.append(page)
                except ValueError:
                    pass

        # Remove duplicates and sort
        return sorted(set(pages))

    def _extract(self):
        """Validate and accept"""
        # Check output path
        if not self._output_path:
            QMessageBox.warning(
                self,
                "No Output File",
                "Please select an output file location."
            )
            return

        # Get selected pages
        if self._all_pages_radio.isChecked():
            self._selected_pages = list(range(self._page_count))
        elif self._current_page_radio.isChecked():
            self._selected_pages = [self._current_page]
        else:
            self._selected_pages = self._parse_page_range(self._range_input.text())

        if not self._selected_pages:
            QMessageBox.warning(
                self,
                "Invalid Page Range",
                "Please enter a valid page range."
            )
            return

        self.accept()

    def get_selected_pages(self) -> List[int]:
        """Get list of selected pages (0-indexed)"""
        return self._selected_pages

    def get_output_path(self) -> str:
        """Get output file path"""
        return self._output_path or ""
