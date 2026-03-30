"""
Ultra PDF Editor - Clean PDF Dialog

Shows repeating margin text found by scan_margin_text() and lets the user
choose which items to permanently remove.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTreeWidget, QTreeWidgetItem, QAbstractItemView,
)
from PyQt6.QtCore import Qt
from typing import List, Dict, Any


class CleanPDFDialog(QDialog):
    """
    Confirmation dialog for the Clean PDF feature.

    Displays each detected repeating text item with a checkbox so the user
    can select exactly what to remove before anything is touched.
    """

    _COL_TEXT     = 0
    _COL_LOCATION = 1
    _COL_PAGES    = 2
    _COL_TYPE     = 3

    def __init__(self, findings: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self._findings = findings
        self.setWindowTitle("Clean PDF — Remove Repeating Text")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumSize(600, 380)
        self._setup_ui()
        self._populate(findings)
        self._update_remove_btn()

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        hint = QLabel(
            "Repeating text was found in the page margins. "
            "Check the items you want to permanently remove, then click <b>Remove Selected</b>."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 11px; color: #ccc;")
        layout.addWidget(hint)

        # Tree
        self._tree = QTreeWidget()
        self._tree.setColumnCount(4)
        self._tree.setHeaderLabels(["Text", "Location", "Pages", "Type"])
        self._tree.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._tree.setRootIsDecorated(False)
        self._tree.setAlternatingRowColors(True)
        self._tree.header().setStretchLastSection(False)
        self._tree.setColumnWidth(self._COL_TEXT,     300)
        self._tree.setColumnWidth(self._COL_LOCATION,  70)
        self._tree.setColumnWidth(self._COL_PAGES,     70)
        self._tree.setColumnWidth(self._COL_TYPE,      90)
        self._tree.itemChanged.connect(self._update_remove_btn)
        layout.addWidget(self._tree, 1)

        # Select all / deselect all
        sel_row = QHBoxLayout()
        sel_all = QPushButton("Select All")
        sel_all.clicked.connect(self._select_all)
        sel_row.addWidget(sel_all)
        desel_all = QPushButton("Deselect All")
        desel_all.clicked.connect(self._deselect_all)
        sel_row.addWidget(desel_all)
        sel_row.addStretch()
        layout.addLayout(sel_row)

        info = QLabel("Only the selected text will be removed from the PDF.")
        info.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(info)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        self._remove_btn = QPushButton("Remove Selected")
        self._remove_btn.setDefault(True)
        self._remove_btn.clicked.connect(self.accept)
        btn_row.addWidget(self._remove_btn)
        layout.addLayout(btn_row)

    def _populate(self, findings: List[Dict[str, Any]]) -> None:
        self._tree.blockSignals(True)
        for finding in findings:
            sample = finding["sample_text"]
            display = sample if len(sample) <= 60 else sample[:57] + "…"
            pages_str = f"{finding['page_count']} / {finding['total_pages']}"

            item = QTreeWidgetItem([
                display,
                finding["zone"],
                pages_str,
                finding["category"],
            ])
            item.setCheckState(self._COL_TEXT, Qt.CheckState.Checked)
            item.setData(self._COL_TEXT, Qt.ItemDataRole.UserRole, finding)
            item.setToolTip(self._COL_TEXT, sample)
            self._tree.addTopLevelItem(item)
        self._tree.blockSignals(False)

    # ------------------------------------------------------------------

    def _select_all(self) -> None:
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(
                self._COL_TEXT, Qt.CheckState.Checked
            )
        self._tree.blockSignals(False)
        self._update_remove_btn()

    def _deselect_all(self) -> None:
        self._tree.blockSignals(True)
        for i in range(self._tree.topLevelItemCount()):
            self._tree.topLevelItem(i).setCheckState(
                self._COL_TEXT, Qt.CheckState.Unchecked
            )
        self._tree.blockSignals(False)
        self._update_remove_btn()

    def _update_remove_btn(self) -> None:
        has_checked = any(
            self._tree.topLevelItem(i).checkState(self._COL_TEXT)
            == Qt.CheckState.Checked
            for i in range(self._tree.topLevelItemCount())
        )
        self._remove_btn.setEnabled(has_checked)

    # ------------------------------------------------------------------ Public API

    def get_selected_findings(self) -> List[Dict[str, Any]]:
        """Return the list of finding dicts the user checked."""
        result = []
        for i in range(self._tree.topLevelItemCount()):
            item = self._tree.topLevelItem(i)
            if item.checkState(self._COL_TEXT) == Qt.CheckState.Checked:
                finding = item.data(self._COL_TEXT, Qt.ItemDataRole.UserRole)
                result.append(finding)
        return result
