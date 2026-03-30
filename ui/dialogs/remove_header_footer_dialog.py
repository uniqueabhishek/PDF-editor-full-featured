"""
Ultra PDF Editor - Remove Header/Footer Dialog

Uses PyMuPDF redaction to permanently erase content in the top/bottom
strip of each selected page.
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QCheckBox, QFrame,
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QColor, QBrush
from typing import Optional, Tuple


class _StripPreview(QLabel):
    """Page thumbnail with coloured overlays showing the strips to be removed."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._header_frac: float = 0.0   # fraction of page height (0-1)
        self._footer_frac: float = 0.0

        self.setMinimumSize(220, 300)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #3a3a3a; border: 1px solid #666;")

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def set_fractions(self, header_frac: float, footer_frac: float) -> None:
        self._header_frac = max(0.0, min(0.49, header_frac))
        self._footer_frac = max(0.0, min(0.49, footer_frac))
        self.update()

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        if not self._pixmap:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        wr = self.rect()
        scaled = self._pixmap.scaled(
            wr.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        ox = (wr.width()  - scaled.width())  // 2
        oy = (wr.height() - scaled.height()) // 2
        painter.drawPixmap(ox, oy, scaled)

        sw, sh = scaled.width(), scaled.height()

        # Header overlay
        if self._header_frac > 0:
            h_px = int(self._header_frac * sh)
            painter.fillRect(ox, oy, sw, h_px, QColor(220, 60, 60, 160))

        # Footer overlay
        if self._footer_frac > 0:
            f_px = int(self._footer_frac * sh)
            painter.fillRect(ox, oy + sh - f_px, sw, f_px, QColor(60, 120, 220, 160))

        painter.end()


class RemoveHeaderFooterDialog(QDialog):
    """Dialog to strip header/footer strips from PDF pages via redaction."""

    def __init__(
        self,
        pixmap: QPixmap,
        page_height: float,
        page_count: int,
        parent=None,
    ):
        super().__init__(parent)
        self._page_height = page_height
        self._page_count  = page_count

        self.setWindowTitle("Remove Header / Footer")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumSize(460, 520)
        self._setup_ui()
        self._preview.set_pixmap(pixmap)
        self._update_preview()

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        hint = QLabel(
            "Set the height of the strip to permanently remove from the top "
            "(header, <span style='color:#dc3c3c;'>red</span>) and/or bottom "
            "(footer, <span style='color:#3c78dc;'>blue</span>) of each page."
        )
        hint.setTextFormat(Qt.TextFormat.RichText)
        hint.setWordWrap(True)
        hint.setStyleSheet("font-size: 11px; color: #aaa;")
        layout.addWidget(hint)

        # Preview
        self._preview = _StripPreview()
        layout.addWidget(self._preview, 1)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Strip controls
        strips_group = QGroupBox("Strip Heights (points)")
        strips_row = QHBoxLayout(strips_group)

        strips_row.addWidget(QLabel("Header:"))
        self._header_spin = QSpinBox()
        self._header_spin.setRange(0, int(self._page_height * 0.49))
        self._header_spin.setValue(0)
        self._header_spin.setSuffix(" pt")
        self._header_spin.setFixedWidth(80)
        self._header_spin.valueChanged.connect(self._update_preview)
        strips_row.addWidget(self._header_spin)

        strips_row.addSpacing(20)
        strips_row.addWidget(QLabel("Footer:"))
        self._footer_spin = QSpinBox()
        self._footer_spin.setRange(0, int(self._page_height * 0.49))
        self._footer_spin.setValue(0)
        self._footer_spin.setSuffix(" pt")
        self._footer_spin.setFixedWidth(80)
        self._footer_spin.valueChanged.connect(self._update_preview)
        strips_row.addWidget(self._footer_spin)

        strips_row.addStretch()
        layout.addWidget(strips_group)

        # Inch readout
        self._size_label = QLabel()
        self._size_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._size_label)
        self._refresh_size_label()

        # Page range
        range_group = QGroupBox("Apply To")
        range_row = QHBoxLayout(range_group)
        self._all_pages = QCheckBox("All pages")
        self._all_pages.setChecked(True)
        self._all_pages.toggled.connect(self._on_range_changed)
        range_row.addWidget(self._all_pages)
        range_row.addWidget(QLabel("or from page"))
        self._from_page = QSpinBox()
        self._from_page.setRange(1, self._page_count)
        self._from_page.setValue(1)
        self._from_page.setEnabled(False)
        self._from_page.setFixedWidth(65)
        range_row.addWidget(self._from_page)
        range_row.addWidget(QLabel("to"))
        self._to_page = QSpinBox()
        self._to_page.setRange(1, self._page_count)
        self._to_page.setValue(self._page_count)
        self._to_page.setEnabled(False)
        self._to_page.setFixedWidth(65)
        range_row.addWidget(self._to_page)
        range_row.addStretch()
        layout.addWidget(range_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        remove_btn = QPushButton("Remove")
        remove_btn.setDefault(True)
        remove_btn.clicked.connect(self._validate_and_accept)
        btn_row.addWidget(remove_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _on_range_changed(self, checked: bool) -> None:
        self._from_page.setEnabled(not checked)
        self._to_page.setEnabled(not checked)

    def _update_preview(self) -> None:
        self._preview.set_fractions(
            self._header_spin.value() / self._page_height,
            self._footer_spin.value() / self._page_height,
        )
        self._refresh_size_label()

    def _refresh_size_label(self) -> None:
        h_pt = self._header_spin.value()
        f_pt = self._footer_spin.value()
        parts = []
        if h_pt:
            parts.append(f"Header: {h_pt} pt ({h_pt / 72:.2f}\")")
        if f_pt:
            parts.append(f"Footer: {f_pt} pt ({f_pt / 72:.2f}\")")
        self._size_label.setText("  |  ".join(parts) if parts else "Nothing selected.")

    def _validate_and_accept(self) -> None:
        if self._header_spin.value() == 0 and self._footer_spin.value() == 0:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.warning(
                self,
                "Nothing to Remove",
                "Set a header or footer height greater than 0.",
            )
            return
        self.accept()

    # ------------------------------------------------------------------ Public API

    def get_header_height(self) -> int:
        return self._header_spin.value()

    def get_footer_height(self) -> int:
        return self._footer_spin.value()

    def get_page_range(self) -> Tuple[int, int]:
        """Return (start, end) 0-based inclusive."""
        if self._all_pages.isChecked():
            return (0, self._page_count - 1)
        return (self._from_page.value() - 1, self._to_page.value() - 1)
