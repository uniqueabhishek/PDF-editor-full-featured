"""
Ultra PDF Editor - Header and Footer Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QGroupBox, QComboBox, QSpinBox, QCheckBox, QFontComboBox
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from typing import Dict, Any, Optional


class HeaderFooterDialog(QDialog):
    """Dialog for adding headers and footers to PDF pages"""

    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self._page_count = page_count

        self.setWindowTitle("Add Header and Footer")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumWidth(500)

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Header section
        header_group = QGroupBox("Header")
        header_layout = QVBoxLayout(header_group)

        # Header text inputs (left, center, right)
        header_row = QHBoxLayout()

        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Left:"))
        self._header_left = QLineEdit()
        self._header_left.setPlaceholderText("Left header text")
        left_layout.addWidget(self._header_left)
        header_row.addLayout(left_layout)

        center_layout = QVBoxLayout()
        center_layout.addWidget(QLabel("Center:"))
        self._header_center = QLineEdit()
        self._header_center.setPlaceholderText("Center header text")
        center_layout.addWidget(self._header_center)
        header_row.addLayout(center_layout)

        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Right:"))
        self._header_right = QLineEdit()
        self._header_right.setPlaceholderText("Right header text")
        right_layout.addWidget(self._header_right)
        header_row.addLayout(right_layout)

        header_layout.addLayout(header_row)
        layout.addWidget(header_group)

        # Footer section
        footer_group = QGroupBox("Footer")
        footer_layout = QVBoxLayout(footer_group)

        # Footer text inputs (left, center, right)
        footer_row = QHBoxLayout()

        f_left_layout = QVBoxLayout()
        f_left_layout.addWidget(QLabel("Left:"))
        self._footer_left = QLineEdit()
        self._footer_left.setPlaceholderText("Left footer text")
        f_left_layout.addWidget(self._footer_left)
        footer_row.addLayout(f_left_layout)

        f_center_layout = QVBoxLayout()
        f_center_layout.addWidget(QLabel("Center:"))
        self._footer_center = QLineEdit()
        self._footer_center.setPlaceholderText("Page {page} of {total}")
        f_center_layout.addWidget(self._footer_center)
        footer_row.addLayout(f_center_layout)

        f_right_layout = QVBoxLayout()
        f_right_layout.addWidget(QLabel("Right:"))
        self._footer_right = QLineEdit()
        self._footer_right.setPlaceholderText("Right footer text")
        f_right_layout.addWidget(self._footer_right)
        footer_row.addLayout(f_right_layout)

        footer_layout.addLayout(footer_row)
        layout.addWidget(footer_group)

        # Variables help
        help_label = QLabel(
            "Variables: {page} = page number, {total} = total pages, "
            "{date} = current date"
        )
        help_label.setStyleSheet("color: #666; font-size: 11px;")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # Font settings
        font_group = QGroupBox("Font Settings")
        font_layout = QHBoxLayout(font_group)

        font_layout.addWidget(QLabel("Font:"))
        self._font_combo = QFontComboBox()
        self._font_combo.setCurrentFont(QFont("Helvetica"))
        font_layout.addWidget(self._font_combo)

        font_layout.addWidget(QLabel("Size:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(6, 72)
        self._font_size.setValue(10)
        font_layout.addWidget(self._font_size)

        font_layout.addStretch()
        layout.addWidget(font_group)

        # Page range
        range_group = QGroupBox("Apply To")
        range_layout = QHBoxLayout(range_group)

        self._all_pages = QCheckBox("All pages")
        self._all_pages.setChecked(True)
        self._all_pages.toggled.connect(self._on_range_changed)
        range_layout.addWidget(self._all_pages)

        range_layout.addWidget(QLabel("or from page"))
        self._from_page = QSpinBox()
        self._from_page.setRange(1, self._page_count)
        self._from_page.setValue(1)
        self._from_page.setEnabled(False)
        range_layout.addWidget(self._from_page)

        range_layout.addWidget(QLabel("to"))
        self._to_page = QSpinBox()
        self._to_page.setRange(1, self._page_count)
        self._to_page.setValue(self._page_count)
        self._to_page.setEnabled(False)
        range_layout.addWidget(self._to_page)

        range_layout.addStretch()
        layout.addWidget(range_group)

        # Margin settings
        margin_group = QGroupBox("Margins (points from edge)")
        margin_layout = QHBoxLayout(margin_group)

        margin_layout.addWidget(QLabel("Top:"))
        self._top_margin = QSpinBox()
        self._top_margin.setRange(10, 200)
        self._top_margin.setValue(36)  # 0.5 inch
        margin_layout.addWidget(self._top_margin)

        margin_layout.addWidget(QLabel("Bottom:"))
        self._bottom_margin = QSpinBox()
        self._bottom_margin.setRange(10, 200)
        self._bottom_margin.setValue(36)
        margin_layout.addWidget(self._bottom_margin)

        margin_layout.addWidget(QLabel("Left/Right:"))
        self._side_margin = QSpinBox()
        self._side_margin.setRange(10, 200)
        self._side_margin.setValue(36)
        margin_layout.addWidget(self._side_margin)

        margin_layout.addStretch()
        layout.addWidget(margin_group)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        apply_btn = QPushButton("Apply")
        apply_btn.clicked.connect(self.accept)
        apply_btn.setDefault(True)
        button_layout.addWidget(apply_btn)

        layout.addLayout(button_layout)

    def _on_range_changed(self, checked: bool):
        """Enable/disable page range inputs"""
        self._from_page.setEnabled(not checked)
        self._to_page.setEnabled(not checked)

    def get_header_texts(self) -> Dict[str, str]:
        """Get header text configuration"""
        return {
            "left": self._header_left.text(),
            "center": self._header_center.text(),
            "right": self._header_right.text()
        }

    def get_footer_texts(self) -> Dict[str, str]:
        """Get footer text configuration"""
        return {
            "left": self._footer_left.text(),
            "center": self._footer_center.text(),
            "right": self._footer_right.text()
        }

    def get_font_settings(self) -> Dict[str, Any]:
        """Get font settings"""
        return {
            "family": self._font_combo.currentFont().family(),
            "size": self._font_size.value()
        }

    def get_page_range(self) -> tuple:
        """Get page range (0-indexed, start and end inclusive)"""
        if self._all_pages.isChecked():
            return (0, self._page_count - 1)
        return (self._from_page.value() - 1, self._to_page.value() - 1)

    def get_margins(self) -> Dict[str, int]:
        """Get margin settings"""
        return {
            "top": self._top_margin.value(),
            "bottom": self._bottom_margin.value(),
            "side": self._side_margin.value()
        }
