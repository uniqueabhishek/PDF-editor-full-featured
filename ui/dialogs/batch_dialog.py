"""
Ultra PDF Editor - Batch Processing Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGroupBox, QCheckBox, QTreeWidget, QTreeWidgetItem,
    QFileDialog, QProgressBar, QLineEdit, QMessageBox,
    QComboBox, QFrame, QAbstractItemView,
)
from PyQt6.QtCore import Qt, pyqtSignal, QThread
from PyQt6.QtGui import QColor
from typing import List, Dict, Any, Optional
from pathlib import Path
import fitz


# ── Status colour palette ────────────────────────────────────────────────────
_S_PENDING    = ("Pending",      QColor(150, 150, 150))
_S_PROCESSING = ("Processing…",  QColor(0,   120, 212))
_S_DONE       = ("Done",         QColor(50,  185,  50))
_S_FAILED     = ("Failed",       QColor(220,  60,  60))


# ── Worker thread ─────────────────────────────────────────────────────────────

class BatchWorker(QThread):
    """Processes PDF files sequentially in a background thread."""

    # (index, filename)
    file_started = pyqtSignal(int, str)
    # (index, success, error_message)
    file_done    = pyqtSignal(int, bool, str)
    # (success_count, fail_count)
    all_done     = pyqtSignal(int, int)

    def __init__(
        self,
        files:      List[str],
        operations: Dict[str, Any],
        output_dir: str,
        suffix:     str,
        parent=None,
    ):
        super().__init__(parent)
        self._files      = files
        self._operations = operations
        self._output_dir = output_dir
        self._suffix     = suffix
        self._cancelled  = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        success = fail = 0
        for i, filepath in enumerate(self._files):
            if self._cancelled:
                break
            self.file_started.emit(i, Path(filepath).name)
            try:
                self._process_file(filepath)
                success += 1
                self.file_done.emit(i, True, "")
            except Exception as exc:
                fail += 1
                self.file_done.emit(i, False, str(exc))
        self.all_done.emit(success, fail)

    def _process_file(self, filepath: str) -> None:
        ops = self._operations
        doc = fitz.open(filepath)

        if ops.get("rotate"):
            angle = ops["rotate_angle"]
            for page in doc:
                page.set_rotation((page.rotation + angle) % 360)

        if ops.get("watermark") and ops.get("watermark_text"):
            text = ops["watermark_text"]
            for page in doc:
                # Diagonal watermark centred on page using standard insert_text
                page.insert_text(
                    fitz.Point(page.rect.width * 0.12, page.rect.height * 0.55),
                    text,
                    fontsize=60,
                    color=(0.65, 0.65, 0.65),
                    rotate=45,
                )

        # Build output path
        stem     = Path(filepath).stem
        out_name = (stem + self._suffix + ".pdf") if self._suffix else Path(filepath).name
        out_path = Path(self._output_dir) / out_name

        save_opts: Dict[str, Any] = {"garbage": 4, "deflate": True}
        if ops.get("compress"):
            save_opts["deflate_images"] = True
            save_opts["deflate_fonts"]  = True

        if ops.get("encrypt") and ops.get("password"):
            save_opts["encryption"] = 4          # PDF_ENCRYPT_AES_256
            save_opts["user_pw"]    = ops["password"]
            save_opts["owner_pw"]   = ops["password"]

        doc.save(str(out_path), **save_opts)
        doc.close()


# ── Drag-and-drop tree ────────────────────────────────────────────────────────

class _DropTree(QTreeWidget):
    """QTreeWidget that accepts dragged PDF files."""

    files_dropped = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.DropOnly)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event) -> None:
        paths = [
            u.toLocalFile()
            for u in event.mimeData().urls()
            if u.toLocalFile().lower().endswith(".pdf")
        ]
        if paths:
            self.files_dropped.emit(paths)
            event.acceptProposedAction()
        else:
            event.ignore()


# ── Main dialog ───────────────────────────────────────────────────────────────

class BatchDialog(QDialog):
    """Dialog for batch processing multiple PDFs."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._files:  List[str]            = []
        self._worker: Optional[BatchWorker] = None

        self.setWindowTitle("Batch Processing")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumSize(680, 580)
        self._setup_ui()

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        layout.addWidget(self._build_files_group())
        layout.addWidget(self._build_ops_group())
        layout.addWidget(self._build_output_group())

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Progress area
        self._progress_label = QLabel("Ready.")
        self._progress_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self._progress_label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setTextVisible(True)
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        layout.addLayout(self._build_buttons())

    # ── Group builders ─────────────────────────────────────────────────

    def _build_files_group(self) -> QGroupBox:
        group = QGroupBox("Input Files  (drag & drop PDFs here)")
        vbox  = QVBoxLayout(group)

        self._file_tree = _DropTree()
        self._file_tree.setColumnCount(2)
        self._file_tree.setHeaderLabels(["File", "Status"])
        self._file_tree.header().setStretchLastSection(False)
        self._file_tree.setColumnWidth(0, 460)
        self._file_tree.setColumnWidth(1, 110)
        self._file_tree.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )
        self._file_tree.files_dropped.connect(self._add_paths)
        vbox.addWidget(self._file_tree)

        btn_row = QHBoxLayout()
        for label, slot in [
            ("Add Files…",    self._add_files),
            ("Add Folder…",   self._add_folder),
            ("Remove Selected", self._remove_selected),
            ("Clear All",     self._clear_files),
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(slot)
            btn_row.addWidget(btn)
        btn_row.addStretch()
        vbox.addLayout(btn_row)
        return group

    def _build_ops_group(self) -> QGroupBox:
        group = QGroupBox("Operations")
        vbox  = QVBoxLayout(group)

        # Compress
        self._compress_check = QCheckBox("Compress / Optimize")
        vbox.addWidget(self._compress_check)

        # Rotate
        rotate_row = QHBoxLayout()
        self._rotate_check = QCheckBox("Rotate all pages:")
        self._rotate_combo = QComboBox()
        self._rotate_combo.addItems(
            ["90° clockwise", "90° counter-clockwise", "180°"]
        )
        self._rotate_combo.setEnabled(False)
        self._rotate_check.toggled.connect(self._rotate_combo.setEnabled)
        rotate_row.addWidget(self._rotate_check)
        rotate_row.addWidget(self._rotate_combo)
        rotate_row.addStretch()
        vbox.addLayout(rotate_row)

        # Watermark
        wm_row = QHBoxLayout()
        self._watermark_check = QCheckBox("Add watermark text:")
        self._watermark_input = QLineEdit()
        self._watermark_input.setPlaceholderText("e.g. CONFIDENTIAL")
        self._watermark_input.setEnabled(False)
        self._watermark_check.toggled.connect(self._watermark_input.setEnabled)
        wm_row.addWidget(self._watermark_check)
        wm_row.addWidget(self._watermark_input)
        vbox.addLayout(wm_row)

        # Encrypt
        enc_row = QHBoxLayout()
        self._encrypt_check  = QCheckBox("Encrypt with password:")
        self._password_input = QLineEdit()
        self._password_input.setPlaceholderText("Password")
        self._password_input.setEchoMode(QLineEdit.EchoMode.Password)
        self._password_input.setEnabled(False)
        self._encrypt_check.toggled.connect(self._password_input.setEnabled)
        enc_row.addWidget(self._encrypt_check)
        enc_row.addWidget(self._password_input)
        vbox.addLayout(enc_row)

        return group

    def _build_output_group(self) -> QGroupBox:
        group = QGroupBox("Output")
        vbox  = QVBoxLayout(group)

        dir_row = QHBoxLayout()
        dir_row.addWidget(QLabel("Directory:"))
        self._output_input = QLineEdit()
        self._output_input.setPlaceholderText("Select output directory…")
        self._output_input.setReadOnly(True)
        dir_row.addWidget(self._output_input)
        browse_btn = QPushButton("Browse…")
        browse_btn.clicked.connect(self._browse_output)
        dir_row.addWidget(browse_btn)
        vbox.addLayout(dir_row)

        suffix_row = QHBoxLayout()
        suffix_row.addWidget(QLabel("Filename suffix (optional):"))
        self._suffix_input = QLineEdit()
        self._suffix_input.setPlaceholderText(
            "e.g.  _processed   (leave blank to overwrite source name)"
        )
        self._suffix_input.setMaximumWidth(300)
        suffix_row.addWidget(self._suffix_input)
        suffix_row.addStretch()
        vbox.addLayout(suffix_row)

        return group

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self._cancel)
        row.addWidget(self._cancel_btn)
        self._process_btn = QPushButton("Process")
        self._process_btn.setDefault(True)
        self._process_btn.clicked.connect(self._process)
        row.addWidget(self._process_btn)
        return row

    # ── File management ────────────────────────────────────────────────

    def _add_paths(self, paths: List[str]) -> None:
        for p in paths:
            if p not in self._files:
                self._files.append(p)
                item = QTreeWidgetItem([Path(p).name, _S_PENDING[0]])
                item.setForeground(1, _S_PENDING[1])
                self._file_tree.addTopLevelItem(item)

    def _add_files(self) -> None:
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select PDF Files", "", "PDF Files (*.pdf)"
        )
        self._add_paths(files)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if folder:
            self._add_paths(
                [str(f) for f in sorted(Path(folder).glob("*.pdf"))]
            )

    def _remove_selected(self) -> None:
        for item in reversed(self._file_tree.selectedItems()):
            idx = self._file_tree.indexOfTopLevelItem(item)
            if 0 <= idx < len(self._files):
                self._files.pop(idx)
                self._file_tree.takeTopLevelItem(idx)

    def _clear_files(self) -> None:
        self._file_tree.clear()
        self._files.clear()

    def _browse_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Select Output Directory")
        if folder:
            self._output_input.setText(folder)

    # ── Status helpers ─────────────────────────────────────────────────

    def _set_status(self, index: int, label: str, color: QColor) -> None:
        item = self._file_tree.topLevelItem(index)
        if item:
            item.setText(1, label)
            item.setForeground(1, color)

    # ── Processing ─────────────────────────────────────────────────────

    def _process(self) -> None:
        if not self._files:
            QMessageBox.warning(self, "No Files", "Please add files to process.")
            return

        output_dir = self._output_input.text().strip()
        if not output_dir:
            QMessageBox.warning(
                self, "No Output Directory", "Please select an output directory."
            )
            return

        _angle_map = {0: 90, 1: 270, 2: 180}
        operations: Dict[str, Any] = {
            "compress":      self._compress_check.isChecked(),
            "rotate":        self._rotate_check.isChecked(),
            "rotate_angle":  _angle_map[self._rotate_combo.currentIndex()],
            "watermark":     self._watermark_check.isChecked(),
            "watermark_text": self._watermark_input.text().strip(),
            "encrypt":       self._encrypt_check.isChecked(),
            "password":      self._password_input.text(),
        }

        if not any([
            operations["compress"],
            operations["rotate"],
            operations["watermark"],
            operations["encrypt"],
        ]):
            QMessageBox.warning(
                self, "No Operations", "Please select at least one operation."
            )
            return

        if operations["watermark"] and not operations["watermark_text"]:
            QMessageBox.warning(
                self, "No Watermark Text", "Please enter watermark text."
            )
            return

        if operations["encrypt"] and not operations["password"]:
            QMessageBox.warning(
                self, "No Password", "Please enter an encryption password."
            )
            return

        # Reset all statuses to Pending
        for i in range(len(self._files)):
            self._set_status(i, _S_PENDING[0], _S_PENDING[1])

        self._progress_bar.setVisible(True)
        self._progress_bar.setMaximum(len(self._files))
        self._progress_bar.setValue(0)
        self._process_btn.setEnabled(False)

        suffix = self._suffix_input.text().strip()
        self._worker = BatchWorker(
            self._files, operations, output_dir, suffix, self
        )
        self._worker.file_started.connect(self._on_file_started)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.all_done.connect(self._on_all_done)
        self._worker.start()

    def _cancel(self) -> None:
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._worker.wait()
            self._progress_label.setText("Cancelled.")
            self._process_btn.setEnabled(True)
        else:
            self.reject()

    # ── Worker callbacks ───────────────────────────────────────────────

    def _on_file_started(self, index: int, filename: str) -> None:
        self._set_status(index, _S_PROCESSING[0], _S_PROCESSING[1])
        self._progress_label.setText(f"Processing: {filename}")
        self._progress_bar.setValue(index)
        item = self._file_tree.topLevelItem(index)
        if item:
            self._file_tree.scrollToItem(item)

    def _on_file_done(self, index: int, success: bool, message: str) -> None:
        if success:
            self._set_status(index, _S_DONE[0], _S_DONE[1])
        else:
            self._set_status(index, _S_FAILED[0], _S_FAILED[1])
            item = self._file_tree.topLevelItem(index)
            if item:
                item.setToolTip(1, message)

    def _on_all_done(self, success: int, fail: int) -> None:
        self._progress_bar.setValue(len(self._files))
        self._process_btn.setEnabled(True)
        self._progress_label.setText(
            f"Complete — {success} succeeded, {fail} failed."
        )
        msg = f"Processed {success} file(s) successfully."
        if fail:
            msg += (
                f"\n\n{fail} file(s) failed. "
                "Hover over a 'Failed' row in the list to see the error."
            )
        QMessageBox.information(self, "Batch Processing Complete", msg)
