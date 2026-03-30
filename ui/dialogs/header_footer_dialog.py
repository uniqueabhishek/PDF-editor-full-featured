"""
Ultra PDF Editor - Header and Footer Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLineEdit, QPushButton,
    QLabel, QGroupBox, QSpinBox, QCheckBox, QComboBox,
    QColorDialog, QFrame,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from typing import Dict, Any, Tuple


# Map display name → PyMuPDF built-in font names for each style variant
_FONT_MAP: Dict[str, Dict[str, str]] = {
    "Helvetica": {
        "normal":      "helv",
        "bold":        "helvB",
        "italic":      "helvI",
        "bold_italic": "helvBI",
    },
    "Times Roman": {
        "normal":      "tiro",
        "bold":        "tiroBd",
        "italic":      "tiroIt",
        "bold_italic": "tiroBdIt",
    },
    "Courier": {
        "normal":      "cour",
        "bold":        "courB",
        "italic":      "courI",
        "bold_italic": "courBI",
    },
}


class _ColorButton(QPushButton):
    """Square button showing current color; opens color picker on click."""

    def __init__(self, color: QColor | None = None, parent=None):
        super().__init__(parent)
        self._color = color or QColor(0, 0, 0)
        self.setFixedSize(28, 28)
        self.setToolTip("Click to choose text color")
        self._refresh()
        self.clicked.connect(self._pick)

    def _refresh(self) -> None:
        r, g, b = self._color.red(), self._color.green(), self._color.blue()
        self.setStyleSheet(
            f"background-color: rgb({r},{g},{b});"
            "border: 2px solid #888; border-radius: 4px;"
        )

    def _pick(self) -> None:
        c = QColorDialog.getColor(self._color, self, "Choose Text Color")
        if c.isValid():
            self._color = c
            self._refresh()

    @property
    def color(self) -> QColor:
        return self._color

    def as_fitz_color(self) -> Tuple[float, float, float]:
        return (self._color.redF(), self._color.greenF(), self._color.blueF())


class HeaderFooterDialog(QDialog):
    """Dialog for adding headers and footers to PDF pages."""

    def __init__(self, page_count: int, parent=None):
        super().__init__(parent)
        self._page_count = page_count
        self.setWindowTitle("Add Header and Footer")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumWidth(580)
        self._setup_ui()

    # ------------------------------------------------------------------
    def _setup_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(10)

        root.addWidget(self._build_text_group("Header", "header"))
        root.addWidget(self._build_text_group("Footer", "footer"))

        help_lbl = QLabel(
            "Variables:  {page} = page number   {total} = total pages   "
            "{date} = today's date   {filename} = file name"
        )
        help_lbl.setStyleSheet("color: #888; font-size: 11px;")
        help_lbl.setWordWrap(True)
        root.addWidget(help_lbl)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        root.addWidget(sep)

        root.addWidget(self._build_font_group())
        root.addWidget(self._build_range_group())
        root.addWidget(self._build_margins_group())
        root.addLayout(self._build_buttons())

    def _build_text_group(self, title: str, prefix: str) -> QGroupBox:
        group = QGroupBox(title)
        row = QHBoxLayout(group)
        placeholders = {
            "header": ("Left header text", "Center header text", "Right header text"),
            "footer": ("Left footer text", "Page {page} of {total}", "Right footer text"),
        }
        ph = placeholders[prefix]
        for side, placeholder in zip(("left", "center", "right"), ph):
            col = QVBoxLayout()
            col.addWidget(QLabel(side.capitalize() + ":"))
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            setattr(self, f"_{prefix}_{side}", edit)
            col.addWidget(edit)
            row.addLayout(col)
        return group

    def _build_font_group(self) -> QGroupBox:
        group = QGroupBox("Font Settings")
        row = QHBoxLayout(group)

        row.addWidget(QLabel("Font:"))
        self._font_combo = QComboBox()
        self._font_combo.addItems(list(_FONT_MAP.keys()))
        self._font_combo.setFixedWidth(130)
        row.addWidget(self._font_combo)

        row.addWidget(QLabel("Size:"))
        self._font_size = QSpinBox()
        self._font_size.setRange(6, 72)
        self._font_size.setValue(10)
        self._font_size.setFixedWidth(60)
        row.addWidget(self._font_size)

        self._bold_check = QCheckBox("Bold")
        self._italic_check = QCheckBox("Italic")
        row.addWidget(self._bold_check)
        row.addWidget(self._italic_check)

        row.addWidget(QLabel("Color:"))
        self._color_btn = _ColorButton(QColor(0, 0, 0))
        row.addWidget(self._color_btn)

        row.addStretch()
        return group

    def _build_range_group(self) -> QGroupBox:
        group = QGroupBox("Apply To")
        row = QHBoxLayout(group)

        self._all_pages = QCheckBox("All pages")
        self._all_pages.setChecked(True)
        self._all_pages.toggled.connect(self._on_range_changed)
        row.addWidget(self._all_pages)

        row.addWidget(QLabel("or from page"))
        self._from_page = QSpinBox()
        self._from_page.setRange(1, self._page_count)
        self._from_page.setValue(1)
        self._from_page.setEnabled(False)
        self._from_page.setFixedWidth(65)
        row.addWidget(self._from_page)

        row.addWidget(QLabel("to"))
        self._to_page = QSpinBox()
        self._to_page.setRange(1, self._page_count)
        self._to_page.setValue(self._page_count)
        self._to_page.setEnabled(False)
        self._to_page.setFixedWidth(65)
        row.addWidget(self._to_page)

        row.addStretch()
        return group

    def _build_margins_group(self) -> QGroupBox:
        group = QGroupBox("Margins (points from edge)")
        row = QHBoxLayout(group)
        for attr, label, default in [
            ("_top_margin",    "Top:",       36),
            ("_bottom_margin", "Bottom:",    36),
            ("_side_margin",   "Left/Right:", 36),
        ]:
            row.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(5, 200)
            spin.setValue(default)
            spin.setFixedWidth(65)
            setattr(self, attr, spin)
            row.addWidget(spin)
        row.addStretch()
        return group

    def _build_buttons(self) -> QHBoxLayout:
        row = QHBoxLayout()
        row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        row.addWidget(cancel_btn)
        apply_btn = QPushButton("Apply")
        apply_btn.setDefault(True)
        apply_btn.clicked.connect(self.accept)
        row.addWidget(apply_btn)
        return row

    # ------------------------------------------------------------------
    def _on_range_changed(self, checked: bool) -> None:
        self._from_page.setEnabled(not checked)
        self._to_page.setEnabled(not checked)

    # ------------------------------------------------------------------  Public API

    def get_header_texts(self) -> Dict[str, str]:
        return {
            "left":   self._header_left.text(),
            "center": self._header_center.text(),
            "right":  self._header_right.text(),
        }

    def get_footer_texts(self) -> Dict[str, str]:
        return {
            "left":   self._footer_left.text(),
            "center": self._footer_center.text(),
            "right":  self._footer_right.text(),
        }

    def get_font_settings(self) -> Dict[str, Any]:
        name = self._font_combo.currentText()
        bold = self._bold_check.isChecked()
        italic = self._italic_check.isChecked()
        variants = _FONT_MAP[name]
        if bold and italic:
            fitz_font = variants["bold_italic"]
        elif bold:
            fitz_font = variants["bold"]
        elif italic:
            fitz_font = variants["italic"]
        else:
            fitz_font = variants["normal"]
        return {
            "family":    name,
            "fitz_font": fitz_font,
            "size":      self._font_size.value(),
            "color":     self._color_btn.as_fitz_color(),
        }

    def get_page_range(self) -> Tuple[int, int]:
        """Return (start, end) page indices, 0-based inclusive."""
        if self._all_pages.isChecked():
            return (0, self._page_count - 1)
        return (self._from_page.value() - 1, self._to_page.value() - 1)

    def get_margins(self) -> Dict[str, int]:
        return {
            "top":    self._top_margin.value(),
            "bottom": self._bottom_margin.value(),
            "side":   self._side_margin.value(),
        }
