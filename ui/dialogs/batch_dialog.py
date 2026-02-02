"""
Ultra PDF Editor - Batch Processing Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QListWidget, QFileDialog,
    QProgressBar, QLineEdit, QMessageBox,
    QAbstractItemView
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz


class BatchWorker(QThread):
    """Worker thread for batch processing"""

    progress = pyqtSignal(int, str)  # progress value, current file
    finished = pyqtSignal(int, int)  # success count, fail count
    error = pyqtSignal(str)

    def __init__(self, files: List[str], operations: Dict[str, Any],
                 output_dir: str, parent=None):
        super().__init__(parent)
        self._files = files
        self._operations = operations
        self._output_dir = output_dir
        self._cancelled = False

    def run(self):
        success_count = 0
        fail_count = 0

        for i, filepath in enumerate(self._files):
            if self._cancelled:
                break

            filename = Path(filepath).name
            self.progress.emit(i, filename)

            try:
                doc = fitz.open(filepath)

                # Apply operations
                if self._operations.get("compress"):
                    pass  # Compression is applied on save

                if self._operations.get("watermark"):
                    text = self._operations.get("watermark_text", "WATERMARK")
                    for page in doc:
                        shape = page.new_shape()
                        center = fitz.Point(page.rect.width / 2, page.rect.height / 2)
                        shape.insert_text(
                            center, text,
                            fontsize=48,
                            color=(0.5, 0.5, 0.5),
                            rotate=45
                        )
                        shape.finish(fill_opacity=0.3)
                        shape.commit()

                # Encryption will be applied on save if enabled

                # Determine output path
                output_path = Path(self._output_dir) / filename

                # Save with options
                save_opts = {"garbage": 4, "deflate": True}
                if self._operations.get("compress"):
                    save_opts["deflate_images"] = True
                    save_opts["deflate_fonts"] = True

                if self._operations.get("encrypt") and self._operations.get("password"):
                    save_opts["encryption"] = 4  # PDF_ENCRYPT_AES_256
                    save_opts["user_pw"] = self._operations["password"]
                    save_opts["owner_pw"] = self._operations["password"]

                doc.save(str(output_path), **save_opts)
                doc.close()

                success_count += 1

            except Exception as e:
                fail_count += 1
                self.error.emit(f"Error processing {filename}: {str(e)}")

        self.finished.emit(success_count, fail_count)

    def cancel(self):
        self._cancelled = True


class BatchDialog(QDialog):
    """Dialog for batch processing multiple PDFs"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files: List[str] = []
        self._worker: Optional[BatchWorker] = None

        self.setWindowTitle("Batch Processing")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumSize(600, 500)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # File list
        files_group = QGroupBox("Input Files")
        files_layout = QVBoxLayout(files_group)

        self._file_list = QListWidget()
        self._file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        files_layout.addWidget(self._file_list)

        file_btn_layout = QHBoxLayout()
        add_btn = QPushButton("Add Files...")
        add_btn.clicked.connect(self._add_files)
        file_btn_layout.addWidget(add_btn)

        add_folder_btn = QPushButton("Add Folder...")
        add_folder_btn.clicked.connect(self._add_folder)
        file_btn_layout.addWidget(add_folder_btn)

        remove_btn = QPushButton("Remove Selected")
        remove_btn.clicked.connect(self._remove_selected)
        file_btn_layout.addWidget(remove_btn)

        clear_btn = QPushButton("Clear All")
        clear_btn.clicked.connect(self._clear_files)
        file_btn_layout.addWidget(clear_btn)

        file_btn_layout.addStretch()
        files_layout.addLayout(file_btn_layout)

        layout.addWidget(files_group)

        # Operations
        ops_group = QGroupBox("Operations")
        ops_layout = QVBoxLayout(ops_group)

        # Compress
        compress_layout = QHBoxLayout()
        self._compress_check = QCheckBox("Compress/Optimize")
        compress_layout.addWidget(self._compress_check)
        compress_layout.addStretch()
        ops_layout.addLayout(compress_layout)

        # Watermark
        watermark_layout = QHBoxLayout()
        self._watermark_check = QCheckBox("Add Watermark:")
        self._watermark_check.toggled.connect(
            lambda c: self._watermark_input.setEnabled(c)
        )
        watermark_layout.addWidget(self._watermark_check)
        self._watermark_input = QLineEdit()
        self._watermark_input.setPlaceholderText("Watermark text")
        self._watermark_input.setEnabled(False)
        watermark_layout.addWidget(self._watermark_input)
        ops_layout.addLayout(watermark_layout)

        # Encrypt
        encrypt_layout = QHBoxLayout()
        self._encrypt_check = QCheckBox("Encrypt with password:")
        self._encrypt_check.toggled.connect(
            lambda c: self._password_input.setEnabled(c)
        )
        encrypt_layout.addWidget(self._encrypt_check)
        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setEnabled(False)
        encrypt_layout.addWidget(self._password_input)
        ops_layout.addLayout(encrypt_layout)

        layout.addWidget(ops_group)

        # Output directory
        output_group = QGroupBox("Output Directory")
        output_layout = QHBoxLayout(output_group)

        self._output_input = QLineEdit()
        self._output_input.setPlaceholderText("Select output directory...")
        self._output_input.setReadOnly(True)
        output_layout.addWidget(self._output_input)

        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_output)
        output_layout.addWidget(browse_btn)

        layout.addWidget(output_group)

        # Progress
        progress_layout = QVBoxLayout()
        self._progress_label = QLabel("")
        progress_layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setVisible(False)
        progress_layout.addWidget(self._progress_bar)

        layout.addLayout(progress_layout)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        button_layout.addWidget(self._cancel_btn)

        self._process_btn = QPushButton("Process")
        self._process_btn.clicked.connect(self._process)
        self._process_btn.setDefault(True)
        button_layout.addWidget(self._process_btn)

        layout.addLayout(button_layout)

    def _add_files(self):
        """Add PDF files"""
        files, _ = QFileDialog.getOpenFileNames(
            self,
            "Select PDF Files",
            "",
            "PDF Files (*.pdf)"
        )
        for f in files:
            if f not in self._files:
                self._files.append(f)
                self._file_list.addItem(Path(f).name)

    def _add_folder(self):
        """Add all PDFs from a folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            for f in Path(folder).glob("*.pdf"):
                filepath = str(f)
                if filepath not in self._files:
                    self._files.append(filepath)
                    self._file_list.addItem(f.name)

    def _remove_selected(self):
        """Remove selected files"""
        for item in self._file_list.selectedItems():
            row = self._file_list.row(item)
            self._file_list.takeItem(row)
            del self._files[row]

    def _clear_files(self):
        """Clear all files"""
        self._file_list.clear()
        self._files.clear()

    def _browse_output(self):
        """Browse for output directory"""
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self._output_input.setText(folder)

    def _process(self):
        """Start batch processing"""
        if not self._files:
            QMessageBox.warning(self, "No Files", "Please add files to process.")
            return

        output_dir = self._output_input.text()
        if not output_dir:
            QMessageBox.warning(self, "No Output", "Please select an output directory.")
            return

        # Gather operations
        operations = {
            "compress": self._compress_check.isChecked(),
            "watermark": self._watermark_check.isChecked(),
            "watermark_text": self._watermark_input.text(),
            "encrypt": self._encrypt_check.isChecked(),
            "password": self._password_input.text()
        }

        # Check if any operation selected
        if not any([operations["compress"], operations["watermark"], operations["encrypt"]]):
            QMessageBox.warning(
                self, "No Operations",
                "Please select at least one operation to perform."
            )
            return

        # Start worker
        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(self._files))
        self._progress_bar.setValue(0)
        self._process_btn.setEnabled(False)

        self._worker = BatchWorker(self._files, operations, output_dir, self)
        self._worker.progress.connect(self._on_progress)
        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _cancel(self):
        """Cancel processing or close dialog"""
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
        self.reject()

    def _on_progress(self, value: int, filename: str):
        """Update progress"""
        self._progress_bar.setValue(value)
        self._progress_label.setText(f"Processing: {filename}")

    def _on_finished(self, success: int, fail: int):
        """Handle completion"""
        self._progress_bar.setValue(len(self._files))
        self._process_btn.setEnabled(True)
        self._progress_label.setText(f"Completed: {success} succeeded, {fail} failed")

        QMessageBox.information(
            self,
            "Batch Processing Complete",
            f"Successfully processed {success} files.\n"
            f"Failed: {fail} files."
        )

    def _on_error(self, error: str):
        """Handle error"""
        self._progress_label.setText(error)
