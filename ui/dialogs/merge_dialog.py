"""
Ultra PDF Editor - Merge PDFs Dialog

Collects the ordered file list and merge options. The actual merge is performed
by the caller via ``PDFDocument.merge_pdfs()`` so the tested core logic stays the
single implementation.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QLabel, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt
from pathlib import Path
from typing import List


class MergeDialog(QDialog):
    """Dialog for choosing and ordering PDF files to merge."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge PDFs")
        self.setMinimumSize(600, 480)
        self._files: List[str] = []
        self._output_path: str = ""
        self._options: dict = {}
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        instructions = QLabel(
            "Add PDF files to merge. Drag to reorder, or use Move Up/Down. "
            "Files are merged in the order shown."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File list with management buttons
        list_layout = QHBoxLayout()

        self._file_list = QListWidget()
        self._file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        list_layout.addWidget(self._file_list)

        btn_layout = QVBoxLayout()
        self._add_btn = QPushButton("Add Files...")
        self._add_btn.clicked.connect(self._add_files)
        btn_layout.addWidget(self._add_btn)

        self._remove_btn = QPushButton("Remove")
        self._remove_btn.clicked.connect(self._remove_selected)
        btn_layout.addWidget(self._remove_btn)

        self._clear_btn = QPushButton("Clear All")
        self._clear_btn.clicked.connect(self._clear_all)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()

        self._move_up_btn = QPushButton("Move Up")
        self._move_up_btn.clicked.connect(self._move_up)
        btn_layout.addWidget(self._move_up_btn)

        self._move_down_btn = QPushButton("Move Down")
        self._move_down_btn.clicked.connect(self._move_down)
        btn_layout.addWidget(self._move_down_btn)

        list_layout.addLayout(btn_layout)
        layout.addLayout(list_layout)

        # Options
        options_group = QGroupBox("Options")
        options_layout = QVBoxLayout(options_group)

        self._add_bookmarks = QCheckBox("Add a bookmark for each file")
        self._add_bookmarks.setChecked(True)
        options_layout.addWidget(self._add_bookmarks)

        self._compress = QCheckBox("Compress output file")
        self._compress.setChecked(True)
        options_layout.addWidget(self._compress)

        layout.addWidget(options_group)

        # Dialog buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self._merge_btn = QPushButton("Merge...")
        self._merge_btn.clicked.connect(self._on_merge)
        self._merge_btn.setEnabled(False)
        btn_box.addWidget(self._merge_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self._cancel_btn)

        layout.addLayout(btn_box)

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files to Merge", "", "PDF Files (*.pdf)")
        for filepath in files:
            if filepath not in self._files:
                self._files.append(filepath)
                item = QListWidgetItem(Path(filepath).name)
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                item.setToolTip(filepath)
                self._file_list.addItem(item)
        self._update_merge_button()

    def _remove_selected(self):
        for item in self._file_list.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath in self._files:
                self._files.remove(filepath)
            self._file_list.takeItem(self._file_list.row(item))
        self._update_merge_button()

    def _clear_all(self):
        self._files.clear()
        self._file_list.clear()
        self._update_merge_button()

    def _move_up(self):
        row = self._file_list.currentRow()
        if row > 0:
            item = self._file_list.takeItem(row)
            if item is None:
                return
            self._file_list.insertItem(row - 1, item)
            self._file_list.setCurrentRow(row - 1)

    def _move_down(self):
        row = self._file_list.currentRow()
        if 0 <= row < self._file_list.count() - 1:
            item = self._file_list.takeItem(row)
            if item is None:
                return
            self._file_list.insertItem(row + 1, item)
            self._file_list.setCurrentRow(row + 1)

    def _update_merge_button(self):
        self._merge_btn.setEnabled(self._file_list.count() >= 2)

    def _ordered_files(self) -> List[str]:
        """The files in the order currently shown (reflects drag/move)."""
        files = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                filepath = item.data(Qt.ItemDataRole.UserRole)
                if filepath:
                    files.append(filepath)
        return files

    def _on_merge(self):
        files = self._ordered_files()
        if len(files) < 2:
            return
        output_path, _ = QFileDialog.getSaveFileName(
            self, "Save Merged PDF", "merged.pdf", "PDF Files (*.pdf)")
        if not output_path:
            return
        self._files = files
        self._output_path = output_path
        self._options = {
            "add_bookmarks": self._add_bookmarks.isChecked(),
            "compress": self._compress.isChecked(),
        }
        self.accept()

    # ---- Results for the caller ----

    def get_files(self) -> List[str]:
        return self._files

    def get_output_path(self) -> str:
        return self._output_path

    def get_options(self) -> dict:
        return self._options
