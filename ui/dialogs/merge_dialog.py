"""
Ultra PDF Editor - Merge PDFs Dialog
Dialog for merging multiple PDF files
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QListWidget,
    QListWidgetItem, QFileDialog, QLabel, QProgressBar, QMessageBox,
    QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from pathlib import Path
from typing import List, Optional
import fitz


class MergeWorker(QThread):
    """Worker thread for merging PDFs"""

    progress = pyqtSignal(int, str)  # percentage, message
    finished = pyqtSignal(bool, str)  # success, message/path

    def __init__(self, files: List[str], output_path: str, options: dict):
        super().__init__()
        self.files = files
        self.output_path = output_path
        self.options = options

    def run(self):
        try:
            merged = fitz.open()
            total = len(self.files)

            for i, filepath in enumerate(self.files):
                self.progress.emit(int((i / total) * 100), f"Processing: {Path(filepath).name}")

                doc = fitz.open(filepath)

                # Apply page range if specified
                start_page = self.options.get(f"start_{i}", 0)
                end_page = self.options.get(f"end_{i}", len(doc) - 1)

                merged.insert_pdf(doc, from_page=start_page, to_page=end_page)
                doc.close()

            self.progress.emit(90, "Saving merged document...")

            # Apply compression if requested
            save_options = {"garbage": 4, "deflate": True}

            merged.save(self.output_path, **save_options)
            merged.close()

            self.progress.emit(100, "Done!")
            self.finished.emit(True, self.output_path)

        except Exception as e:
            self.finished.emit(False, str(e))


class MergeDialog(QDialog):
    """Dialog for merging PDF files"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Merge PDFs")
        self.setMinimumSize(600, 500)
        self._files: List[str] = []
        self._worker: Optional[MergeWorker] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Instructions
        instructions = QLabel(
            "Add PDF files to merge. Drag to reorder. "
            "Files will be merged in the order shown."
        )
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        # File list
        list_layout = QHBoxLayout()

        self._file_list = QListWidget()
        self._file_list.setDragDropMode(QListWidget.DragDropMode.InternalMove)
        self._file_list.setSelectionMode(QListWidget.SelectionMode.ExtendedSelection)
        list_layout.addWidget(self._file_list)

        # Buttons for list management
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

        self._add_bookmarks = QCheckBox("Add bookmark for each file")
        self._add_bookmarks.setChecked(True)
        options_layout.addWidget(self._add_bookmarks)

        self._compress = QCheckBox("Compress output file")
        self._compress.setChecked(True)
        options_layout.addWidget(self._compress)

        layout.addWidget(options_group)

        # Progress bar
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Dialog buttons
        btn_box = QHBoxLayout()
        btn_box.addStretch()

        self._merge_btn = QPushButton("Merge")
        self._merge_btn.clicked.connect(self._start_merge)
        self._merge_btn.setEnabled(False)
        btn_box.addWidget(self._merge_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_box.addWidget(self._cancel_btn)

        layout.addLayout(btn_box)

    def _add_files(self):
        """Add files to the list"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files to Merge",
            "",
            "PDF Files (*.pdf)"
        )

        for filepath in files:
            if filepath not in self._files:
                self._files.append(filepath)
                item = QListWidgetItem(Path(filepath).name)
                item.setData(Qt.ItemDataRole.UserRole, filepath)
                item.setToolTip(filepath)
                self._file_list.addItem(item)

        self._update_merge_button()

    def _remove_selected(self):
        """Remove selected files"""
        for item in self._file_list.selectedItems():
            filepath = item.data(Qt.ItemDataRole.UserRole)
            self._files.remove(filepath)
            self._file_list.takeItem(self._file_list.row(item))

        self._update_merge_button()

    def _clear_all(self):
        """Clear all files"""
        self._files.clear()
        self._file_list.clear()
        self._update_merge_button()

    def _move_up(self):
        """Move selected item up"""
        current_row = self._file_list.currentRow()
        if current_row > 0:
            item = self._file_list.takeItem(current_row)
            if item is None:
                return
            self._file_list.insertItem(current_row - 1, item)
            self._file_list.setCurrentRow(current_row - 1)

            # Update files list
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath:
                self._files.remove(filepath)
                self._files.insert(current_row - 1, filepath)

    def _move_down(self):
        """Move selected item down"""
        current_row = self._file_list.currentRow()
        if current_row < self._file_list.count() - 1:
            item = self._file_list.takeItem(current_row)
            if item is None:
                return
            self._file_list.insertItem(current_row + 1, item)
            self._file_list.setCurrentRow(current_row + 1)

            # Update files list
            filepath = item.data(Qt.ItemDataRole.UserRole)
            if filepath:
                self._files.remove(filepath)
                self._files.insert(current_row + 1, filepath)

    def _update_merge_button(self):
        """Update merge button state"""
        self._merge_btn.setEnabled(len(self._files) >= 2)

    def _start_merge(self):
        """Start the merge operation"""
        # Get output path
        output_path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Merged PDF",
            "merged.pdf",
            "PDF Files (*.pdf)"
        )

        if not output_path:
            return

        # Get file order from list widget
        ordered_files = []
        for i in range(self._file_list.count()):
            item = self._file_list.item(i)
            if item:
                filepath = item.data(Qt.ItemDataRole.UserRole)
                if filepath:
                    ordered_files.append(filepath)

        # Prepare options
        options = {
            "add_bookmarks": self._add_bookmarks.isChecked(),
            "compress": self._compress.isChecked(),
        }

        # Show progress
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._merge_btn.setEnabled(False)
        self._add_btn.setEnabled(False)

        # Start worker
        self._worker = MergeWorker(ordered_files, output_path, options)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percentage: int, message: str):
        """Handle progress update"""
        self._progress.setValue(percentage)
        self._status_label.setText(message)

    def _on_finished(self, success: bool, message: str):
        """Handle merge completion"""
        self._progress.setVisible(False)
        self._merge_btn.setEnabled(True)
        self._add_btn.setEnabled(True)

        if success:
            QMessageBox.information(
                self,
                "Merge Complete",
                f"PDFs merged successfully!\n\nSaved to: {message}"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Merge Failed",
                f"Failed to merge PDFs:\n{message}"
            )
            self._status_label.setText(f"Error: {message}")

    def get_output_path(self) -> str:
        """Get the output file path"""
        return self._worker.output_path if self._worker else ""
