"""
Ultra PDF Editor - Split PDF Dialog

Collects the split mode and options. The actual split is performed by the caller
via the ``PDFDocument.split_by_*`` methods, which operate on the in-memory
document (so unsaved edits are honoured) and are covered by tests.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QMessageBox, QGroupBox, QRadioButton, QSpinBox, QLineEdit,
    QFileDialog, QButtonGroup, QFormLayout
)
from pathlib import Path
from typing import List, Optional, Tuple


class SplitDialog(QDialog):
    """Dialog for choosing how to split a PDF."""

    def __init__(self, filepath: Optional[str] = None, page_count: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split PDF")
        self.setMinimumSize(500, 420)

        self._filepath = filepath
        self._page_count = page_count
        self._options: dict = {}

        self._setup_ui()
        self._update_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Source info
        info_group = QGroupBox("Source Document")
        info_layout = QFormLayout(info_group)
        self._file_label = QLabel(Path(self._filepath).name if self._filepath else "Current document")
        info_layout.addRow("File:", self._file_label)
        self._pages_label = QLabel(str(self._page_count))
        info_layout.addRow("Pages:", self._pages_label)
        layout.addWidget(info_group)

        # Split mode
        mode_group = QGroupBox("Split Mode")
        mode_layout = QVBoxLayout(mode_group)
        self._mode_group = QButtonGroup(self)

        self._single_radio = QRadioButton("Extract each page as a separate file")
        self._mode_group.addButton(self._single_radio, 0)
        mode_layout.addWidget(self._single_radio)

        every_n_layout = QHBoxLayout()
        self._every_n_radio = QRadioButton("Split every")
        self._mode_group.addButton(self._every_n_radio, 1)
        every_n_layout.addWidget(self._every_n_radio)
        self._pages_spin = QSpinBox()
        self._pages_spin.setMinimum(1)
        self._pages_spin.setMaximum(self._page_count if self._page_count > 0 else 9999)
        self._pages_spin.setValue(1)
        self._pages_spin.setEnabled(False)
        every_n_layout.addWidget(self._pages_spin)
        every_n_layout.addWidget(QLabel("pages"))
        every_n_layout.addStretch()
        mode_layout.addLayout(every_n_layout)

        self._ranges_radio = QRadioButton("Split by page ranges (e.g., 1-5, 6-10, 11-15)")
        self._mode_group.addButton(self._ranges_radio, 2)
        mode_layout.addWidget(self._ranges_radio)
        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText("Enter ranges: 1-5, 6-10, 11-15")
        self._ranges_input.setEnabled(False)
        mode_layout.addWidget(self._ranges_input)

        self._bookmarks_radio = QRadioButton("Split by bookmarks (chapters)")
        self._mode_group.addButton(self._bookmarks_radio, 3)
        mode_layout.addWidget(self._bookmarks_radio)

        self._single_radio.setChecked(True)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)
        layout.addWidget(mode_group)

        # Output
        output_group = QGroupBox("Output")
        output_layout = QFormLayout(output_group)
        output_dir_layout = QHBoxLayout()
        self._output_dir = QLineEdit()
        self._output_dir.setPlaceholderText("Select output directory...")
        output_dir_layout.addWidget(self._output_dir)
        self._browse_btn = QPushButton("Browse...")
        self._browse_btn.clicked.connect(self._browse_output)
        output_dir_layout.addWidget(self._browse_btn)
        output_layout.addRow("Directory:", output_dir_layout)
        layout.addWidget(output_group)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self._split_btn = QPushButton("Split")
        self._split_btn.clicked.connect(self._on_split)
        btn_layout.addWidget(self._split_btn)
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)
        layout.addLayout(btn_layout)

    def _on_mode_changed(self, button):
        self._ranges_input.setEnabled(button == self._ranges_radio)
        self._pages_spin.setEnabled(button == self._every_n_radio)

    def _browse_output(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Output Directory",
            str(Path(self._filepath).parent) if self._filepath else "")
        if directory:
            self._output_dir.setText(directory)

    def _update_ui(self):
        self._split_btn.setEnabled(self._page_count > 0)
        self._pages_spin.setMaximum(self._page_count if self._page_count > 0 else 9999)

    def _parse_ranges(self, text: str) -> List[Tuple[int, int]]:
        """Parse '1-5, 6-10' into validated 1-indexed (start, end) tuples."""
        ranges: List[Tuple[int, int]] = []
        for part in text.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start_s, end_s = part.split('-')
                    start, end = int(start_s.strip()), int(end_s.strip())
                    if 1 <= start <= end <= self._page_count:
                        ranges.append((start, end))
                except ValueError:
                    pass
            else:
                try:
                    page = int(part)
                    if 1 <= page <= self._page_count:
                        ranges.append((page, page))
                except ValueError:
                    pass
        return ranges

    def _on_split(self):
        if not self._output_dir.text():
            QMessageBox.warning(self, "Error", "Please select an output directory.")
            return

        if self._every_n_radio.isChecked():
            mode, options = "every_n", {"pages_per_file": self._pages_spin.value()}
        elif self._ranges_radio.isChecked():
            ranges = self._parse_ranges(self._ranges_input.text())
            if not ranges:
                QMessageBox.warning(self, "Error", "Please enter valid page ranges.")
                return
            mode, options = "ranges", {"ranges": ranges}
        elif self._bookmarks_radio.isChecked():
            mode, options = "bookmarks", {}
        else:
            mode, options = "single", {}

        options["mode"] = mode
        options["output_dir"] = self._output_dir.text()
        self._options = options
        self.accept()

    def set_document(self, filepath: str, page_count: int):
        self._filepath = filepath
        self._page_count = page_count
        self._file_label.setText(Path(filepath).name if filepath else "Current document")
        self._pages_label.setText(str(page_count))
        self._update_ui()

    def get_split_options(self) -> dict:
        """Return {'mode', 'output_dir', and mode-specific params} after accept."""
        return self._options
