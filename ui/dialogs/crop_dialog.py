"""
Ultra PDF Editor - Crop Page Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QRadioButton, QButtonGroup, QFrame,
)
from PyQt6.QtCore import Qt, QRectF, QPointF, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QCursor
from typing import Tuple, Optional


class CropPreview(QLabel):
    """Page preview widget with interactive drag-to-crop.

    Drag on the preview to define a crop area. The signal ``crop_dragged``
    fires on mouse-release with the resulting margins (normalised 0-1) from
    each edge: (left, top, right, bottom).
    """

    crop_dragged = pyqtSignal(float, float, float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        # Normalised crop rect (fraction of page), default = full page
        self._crop_rect = QRectF(0.0, 0.0, 1.0, 1.0)
        # Widget-space rectangle where the scaled page image is drawn
        self._page_rect = QRectF()

        self._dragging = False
        self._drag_start: Optional[QPointF] = None
        self._drag_current: Optional[QPointF] = None

        self.setMinimumSize(320, 420)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #3a3a3a; border: 1px solid #666;")
        self.setCursor(QCursor(Qt.CursorShape.CrossCursor))
        self.setMouseTracking(True)

    # ------------------------------------------------------------------ setters

    def set_pixmap(self, pixmap: QPixmap) -> None:
        self._pixmap = pixmap
        self.update()

    def set_crop_margins(
        self, left: float, top: float, right: float, bottom: float
    ) -> None:
        """Set crop rect from per-edge margins (each 0-1 fraction of page size)."""
        w = max(0.0, 1.0 - left - right)
        h = max(0.0, 1.0 - top - bottom)
        self._crop_rect = QRectF(left, top, w, h)
        self.update()

    # ------------------------------------------------------------------ mouse

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self._pixmap
            and not self._page_rect.isEmpty()
        ):
            self._dragging = True
            self._drag_start = self._clamp(event.position())
            self._drag_current = self._drag_start

    def mouseMoveEvent(self, event) -> None:
        if self._dragging:
            self._drag_current = self._clamp(event.position())
            self._rebuild_crop_rect()
            self.update()

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._dragging:
            self._dragging = False
            self._drag_current = self._clamp(event.position())
            self._rebuild_crop_rect()
            self._emit_margins()
            self.update()

    def _clamp(self, pos: QPointF) -> QPointF:
        """Clamp a widget-space point to the page rectangle."""
        if self._page_rect.isEmpty():
            return pos
        x = max(self._page_rect.left(), min(self._page_rect.right(), pos.x()))
        y = max(self._page_rect.top(), min(self._page_rect.bottom(), pos.y()))
        return QPointF(x, y)

    def _rebuild_crop_rect(self) -> None:
        if not self._drag_start or not self._drag_current or self._page_rect.isEmpty():
            return
        pr = self._page_rect
        x0n = (min(self._drag_start.x(), self._drag_current.x()) - pr.x()) / pr.width()
        y0n = (min(self._drag_start.y(), self._drag_current.y()) - pr.y()) / pr.height()
        x1n = (max(self._drag_start.x(), self._drag_current.x()) - pr.x()) / pr.width()
        y1n = (max(self._drag_start.y(), self._drag_current.y()) - pr.y()) / pr.height()
        x0n, y0n = max(0.0, x0n), max(0.0, y0n)
        x1n, y1n = min(1.0, x1n), min(1.0, y1n)
        self._crop_rect = QRectF(x0n, y0n, x1n - x0n, y1n - y0n)

    def _emit_margins(self) -> None:
        r = self._crop_rect
        self.crop_dragged.emit(
            r.left(),          # left margin (fraction from left edge)
            r.top(),           # top margin (fraction from top edge)
            1.0 - r.right(),   # right margin (fraction from right edge)
            1.0 - r.bottom(),  # bottom margin (fraction from bottom edge)
        )

    # ------------------------------------------------------------------ paint

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
        self._page_rect = QRectF(ox, oy, scaled.width(), scaled.height())
        painter.drawPixmap(ox, oy, scaled)

        cr = self._crop_rect
        if cr.width() > 0.001 and cr.height() > 0.001:
            cx = ox + cr.x() * scaled.width()
            cy = oy + cr.y() * scaled.height()
            cw = cr.width()  * scaled.width()
            ch = cr.height() * scaled.height()

            # Darken everything outside the crop area
            dark = QColor(0, 0, 0, 145)
            painter.fillRect(ox,           oy,      scaled.width(), int(cy - oy),                     dark)
            painter.fillRect(ox,           int(cy + ch), scaled.width(), int(oy + scaled.height() - cy - ch), dark)
            painter.fillRect(ox,           int(cy), int(cx - ox),              int(ch), dark)
            painter.fillRect(int(cx + cw), int(cy), int(ox + scaled.width() - cx - cw), int(ch), dark)

            # Crop border
            painter.setPen(QPen(QColor(255, 80, 80), 2))
            painter.drawRect(int(cx), int(cy), int(cw), int(ch))

            # Corner handles
            hs = 8
            painter.setBrush(QColor(255, 80, 80))
            painter.setPen(Qt.PenStyle.NoPen)
            for hx, hy in [
                (cx,            cy),
                (cx + cw - hs,  cy),
                (cx,            cy + ch - hs),
                (cx + cw - hs,  cy + ch - hs),
            ]:
                painter.drawRect(int(hx), int(hy), hs, hs)

        painter.end()


class CropDialog(QDialog):
    """Dialog for cropping PDF pages with live drag-to-crop preview."""

    def __init__(
        self,
        pixmap: QPixmap,
        page_width: float,
        page_height: float,
        parent=None,
    ):
        super().__init__(parent)
        self._page_width  = page_width
        self._page_height = page_height

        self.setWindowTitle("Crop Page")
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )
        self.setMinimumSize(540, 650)
        self._setup_ui()
        self._preview.set_pixmap(pixmap)
        self._update_preview()

    # ------------------------------------------------------------------

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(8)

        hint = QLabel("Drag on the preview to set the crop area, or enter values below.")
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

        # Preview
        self._preview = CropPreview()
        self._preview.crop_dragged.connect(self._on_crop_dragged)
        layout.addWidget(self._preview, 1)

        # Dimensions readout
        self._dims_label = QLabel()
        self._dims_label.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(self._dims_label)
        self._update_dims_label(0.0, 0.0, self._page_width, self._page_height)

        sep = QFrame()
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(sep)

        # Margin spinboxes
        margins_group = QGroupBox("Crop Margins (points)")
        margins_row = QHBoxLayout(margins_group)
        for attr, label, max_val in [
            ("_left_spin",   "Left:",   int(self._page_width  / 2)),
            ("_top_spin",    "Top:",    int(self._page_height / 2)),
            ("_right_spin",  "Right:",  int(self._page_width  / 2)),
            ("_bottom_spin", "Bottom:", int(self._page_height / 2)),
        ]:
            margins_row.addWidget(QLabel(label))
            spin = QSpinBox()
            spin.setRange(0, max_val)
            spin.setValue(0)
            spin.setFixedWidth(72)
            spin.valueChanged.connect(self._update_preview)
            setattr(self, attr, spin)
            margins_row.addWidget(spin)
        layout.addWidget(margins_group)

        # Apply-to radio buttons
        apply_group = QGroupBox("Apply To")
        apply_row = QHBoxLayout(apply_group)
        self._rb_group = QButtonGroup(self)
        self._rb_current = QRadioButton("Current page only")
        self._rb_all     = QRadioButton("All pages")
        self._rb_current.setChecked(True)
        self._rb_group.addButton(self._rb_current, 0)
        self._rb_group.addButton(self._rb_all,     1)
        apply_row.addWidget(self._rb_current)
        apply_row.addWidget(self._rb_all)
        apply_row.addStretch()
        layout.addWidget(apply_group)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        btn_row.addWidget(reset_btn)
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        btn_row.addWidget(cancel_btn)
        crop_btn = QPushButton("Crop")
        crop_btn.setDefault(True)
        crop_btn.clicked.connect(self.accept)
        btn_row.addWidget(crop_btn)
        layout.addLayout(btn_row)

    # ------------------------------------------------------------------

    def _update_dims_label(
        self, x0: float, y0: float, x1: float, y1: float
    ) -> None:
        w_pt = max(0.0, x1 - x0)
        h_pt = max(0.0, y1 - y0)
        self._dims_label.setText(
            f"Crop area: {w_pt:.0f} × {h_pt:.0f} pt"
            f"  ({w_pt / 72:.2f}\" × {h_pt / 72:.2f}\")"
        )

    def _on_crop_dragged(
        self, left_n: float, top_n: float, right_n: float, bottom_n: float
    ) -> None:
        """Callback from preview drag — block spinbox signals to avoid recursion."""
        for spin in (
            self._left_spin, self._top_spin,
            self._right_spin, self._bottom_spin,
        ):
            spin.blockSignals(True)

        self._left_spin.setValue(int(left_n  * self._page_width))
        self._top_spin.setValue(int(top_n    * self._page_height))
        self._right_spin.setValue(int(right_n  * self._page_width))
        self._bottom_spin.setValue(int(bottom_n * self._page_height))

        for spin in (
            self._left_spin, self._top_spin,
            self._right_spin, self._bottom_spin,
        ):
            spin.blockSignals(False)

        x0, y0, x1, y1 = self.get_crop_rect()
        self._update_dims_label(x0, y0, x1, y1)

    def _update_preview(self) -> None:
        left   = self._left_spin.value()   / self._page_width
        top    = self._top_spin.value()    / self._page_height
        right  = self._right_spin.value()  / self._page_width
        bottom = self._bottom_spin.value() / self._page_height
        self._preview.set_crop_margins(left, top, right, bottom)
        x0, y0, x1, y1 = self.get_crop_rect()
        self._update_dims_label(x0, y0, x1, y1)

    def _reset(self) -> None:
        for spin in (
            self._left_spin, self._top_spin,
            self._right_spin, self._bottom_spin,
        ):
            spin.setValue(0)

    # ------------------------------------------------------------------ Public API

    def get_crop_rect(self) -> Tuple[float, float, float, float]:
        """Return (x0, y0, x1, y1) in page points."""
        x0 = float(self._left_spin.value())
        y0 = float(self._top_spin.value())
        x1 = self._page_width  - self._right_spin.value()
        y1 = self._page_height - self._bottom_spin.value()
        return (x0, y0, x1, y1)

    def apply_to_all_pages(self) -> bool:
        return self._rb_all.isChecked()
