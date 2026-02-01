"""
Ultra PDF Editor - Split PDF Dialog
Dialog for splitting a PDF into multiple files
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QProgressBar, QMessageBox, QGroupBox, QRadioButton,
    QSpinBox, QLineEdit, QFileDialog, QButtonGroup, QFormLayout,
    QCheckBox, QTextEdit
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from pathlib import Path
from typing import List, Optional, Tuple
import fitz


class SplitWorker(QThread):
    """Worker thread for splitting PDFs"""

    progress = pyqtSignal(int, str)
    finished = pyqtSignal(bool, str, list)  # success, message, output files

    def __init__(self, input_path: str, output_dir: str, mode: str, options: dict):
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.mode = mode
        self.options = options

    def run(self):
        try:
            doc = fitz.open(self.input_path)
            base_name = Path(self.input_path).stem
            output_files = []

            if self.mode == "single":
                # Split into single pages
                total = len(doc)
                for i in range(total):
                    self.progress.emit(int((i / total) * 100), f"Extracting page {i + 1}...")

                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=i, to_page=i)

                    output_path = Path(self.output_dir) / f"{base_name}_page_{i + 1:04d}.pdf"
                    new_doc.save(str(output_path))
                    new_doc.close()

                    output_files.append(str(output_path))

            elif self.mode == "every_n":
                # Split every N pages
                n = self.options.get("pages_per_file", 1)
                total = len(doc)
                file_num = 1

                for i in range(0, total, n):
                    end_page = min(i + n - 1, total - 1)
                    self.progress.emit(int((i / total) * 100), f"Creating file {file_num}...")

                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=i, to_page=end_page)

                    output_path = Path(self.output_dir) / f"{base_name}_part_{file_num:03d}.pdf"
                    new_doc.save(str(output_path))
                    new_doc.close()

                    output_files.append(str(output_path))
                    file_num += 1

            elif self.mode == "ranges":
                # Split by custom ranges
                ranges = self.options.get("ranges", [])

                for idx, (start, end) in enumerate(ranges):
                    self.progress.emit(int((idx / len(ranges)) * 100), f"Creating part {idx + 1}...")

                    new_doc = fitz.open()
                    new_doc.insert_pdf(doc, from_page=start - 1, to_page=end - 1)

                    output_path = Path(self.output_dir) / f"{base_name}_pages_{start}-{end}.pdf"
                    new_doc.save(str(output_path))
                    new_doc.close()

                    output_files.append(str(output_path))

            elif self.mode == "bookmarks":
                # Split by bookmarks/TOC
                toc = doc.get_toc()

                if not toc:
                    self.finished.emit(False, "Document has no bookmarks", [])
                    doc.close()
                    return

                # Find top-level bookmarks
                split_points = []
                for entry in toc:
                    if entry[0] == 1:  # Level 1 bookmark
                        split_points.append((entry[1], entry[2] - 1))  # title, page

                # Add end point
                if split_points:
                    # Create ranges from split points
                    for i, (title, start_page) in enumerate(split_points):
                        if i < len(split_points) - 1:
                            end_page = split_points[i + 1][1] - 1
                        else:
                            end_page = len(doc) - 1

                        self.progress.emit(int((i / len(split_points)) * 100), f"Creating: {title}...")

                        new_doc = fitz.open()
                        new_doc.insert_pdf(doc, from_page=start_page, to_page=end_page)

                        # Sanitize title for filename
                        safe_title = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
                        output_path = Path(self.output_dir) / f"{base_name}_{safe_title}.pdf"
                        new_doc.save(str(output_path))
                        new_doc.close()

                        output_files.append(str(output_path))

            doc.close()

            self.progress.emit(100, "Done!")
            self.finished.emit(True, f"Created {len(output_files)} files", output_files)

        except Exception as e:
            self.finished.emit(False, str(e), [])


class SplitDialog(QDialog):
    """Dialog for splitting PDF files"""

    def __init__(self, filepath: str = None, page_count: int = 0, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Split PDF")
        self.setMinimumSize(500, 450)

        self._filepath = filepath
        self._page_count = page_count
        self._output_files: List[str] = []
        self._worker: Optional[SplitWorker] = None

        self._setup_ui()
        self._update_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File info
        info_group = QGroupBox("Source Document")
        info_layout = QFormLayout(info_group)

        self._file_label = QLabel(Path(self._filepath).name if self._filepath else "No file")
        info_layout.addRow("File:", self._file_label)

        self._pages_label = QLabel(str(self._page_count))
        info_layout.addRow("Pages:", self._pages_label)

        layout.addWidget(info_group)

        # Split mode
        mode_group = QGroupBox("Split Mode")
        mode_layout = QVBoxLayout(mode_group)

        self._mode_group = QButtonGroup(self)

        # Single pages
        self._single_radio = QRadioButton("Extract each page as a separate file")
        self._mode_group.addButton(self._single_radio, 0)
        mode_layout.addWidget(self._single_radio)

        # Every N pages
        every_n_layout = QHBoxLayout()
        self._every_n_radio = QRadioButton("Split every")
        self._mode_group.addButton(self._every_n_radio, 1)
        every_n_layout.addWidget(self._every_n_radio)

        self._pages_spin = QSpinBox()
        self._pages_spin.setMinimum(1)
        self._pages_spin.setMaximum(self._page_count if self._page_count > 0 else 9999)
        self._pages_spin.setValue(1)
        every_n_layout.addWidget(self._pages_spin)

        every_n_layout.addWidget(QLabel("pages"))
        every_n_layout.addStretch()
        mode_layout.addLayout(every_n_layout)

        # Custom ranges
        self._ranges_radio = QRadioButton("Split by page ranges (e.g., 1-5, 6-10, 11-15)")
        self._mode_group.addButton(self._ranges_radio, 2)
        mode_layout.addWidget(self._ranges_radio)

        self._ranges_input = QLineEdit()
        self._ranges_input.setPlaceholderText("Enter ranges: 1-5, 6-10, 11-15")
        self._ranges_input.setEnabled(False)
        mode_layout.addWidget(self._ranges_input)

        # By bookmarks
        self._bookmarks_radio = QRadioButton("Split by bookmarks (chapters)")
        self._mode_group.addButton(self._bookmarks_radio, 3)
        mode_layout.addWidget(self._bookmarks_radio)

        self._single_radio.setChecked(True)
        self._mode_group.buttonClicked.connect(self._on_mode_changed)

        layout.addWidget(mode_group)

        # Output options
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

        # Progress
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        layout.addWidget(self._progress)

        self._status_label = QLabel("")
        layout.addWidget(self._status_label)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._split_btn = QPushButton("Split")
        self._split_btn.clicked.connect(self._start_split)
        btn_layout.addWidget(self._split_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)

    def _on_mode_changed(self, button):
        """Handle mode change"""
        self._ranges_input.setEnabled(button == self._ranges_radio)
        self._pages_spin.setEnabled(button == self._every_n_radio)

    def _browse_output(self):
        """Browse for output directory"""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Output Directory",
            str(Path(self._filepath).parent) if self._filepath else ""
        )
        if directory:
            self._output_dir.setText(directory)

    def _update_ui(self):
        """Update UI based on current state"""
        has_file = bool(self._filepath)
        self._split_btn.setEnabled(has_file)
        self._pages_spin.setMaximum(self._page_count if self._page_count > 0 else 9999)

    def _parse_ranges(self, text: str) -> List[Tuple[int, int]]:
        """Parse page ranges from text"""
        ranges = []

        for part in text.split(','):
            part = part.strip()
            if '-' in part:
                try:
                    start, end = part.split('-')
                    start = int(start.strip())
                    end = int(end.strip())
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

    def _start_split(self):
        """Start the split operation"""
        if not self._output_dir.text():
            QMessageBox.warning(self, "Error", "Please select an output directory.")
            return

        # Determine mode and options
        mode = "single"
        options = {}

        if self._every_n_radio.isChecked():
            mode = "every_n"
            options["pages_per_file"] = self._pages_spin.value()
        elif self._ranges_radio.isChecked():
            mode = "ranges"
            ranges = self._parse_ranges(self._ranges_input.text())
            if not ranges:
                QMessageBox.warning(self, "Error", "Please enter valid page ranges.")
                return
            options["ranges"] = ranges
        elif self._bookmarks_radio.isChecked():
            mode = "bookmarks"

        # Show progress
        self._progress.setVisible(True)
        self._progress.setValue(0)
        self._split_btn.setEnabled(False)

        # Start worker
        self._worker = SplitWorker(
            self._filepath,
            self._output_dir.text(),
            mode,
            options
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _on_progress(self, percentage: int, message: str):
        """Handle progress update"""
        self._progress.setValue(percentage)
        self._status_label.setText(message)

    def _on_finished(self, success: bool, message: str, files: List[str]):
        """Handle split completion"""
        self._progress.setVisible(False)
        self._split_btn.setEnabled(True)

        if success:
            self._output_files = files
            QMessageBox.information(
                self,
                "Split Complete",
                f"{message}\n\nOutput directory: {self._output_dir.text()}"
            )
            self.accept()
        else:
            QMessageBox.critical(
                self,
                "Split Failed",
                f"Failed to split PDF:\n{message}"
            )
            self._status_label.setText(f"Error: {message}")

    def set_document(self, filepath: str, page_count: int):
        """Set the document to split"""
        self._filepath = filepath
        self._page_count = page_count
        self._file_label.setText(Path(filepath).name)
        self._pages_label.setText(str(page_count))
        self._update_ui()

    def get_output_files(self) -> List[str]:
        """Get the list of created files"""
        return self._output_files
