"""
Ultra PDF Editor - Crop Page Dialog
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QSpinBox, QGroupBox, QCheckBox
)
from PyQt6.QtCore import Qt, QRectF
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor
from typing import Tuple, Optional


class CropPreview(QLabel):
    """Widget for showing crop preview"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._pixmap: Optional[QPixmap] = None
        self._crop_rect = QRectF(0, 0, 1, 1)  # Normalized (0-1)
        self._page_rect = QRectF()

        self.setMinimumSize(300, 400)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: #404040; border: 1px solid #666;")

    def set_pixmap(self, pixmap: QPixmap):
        """Set the page preview pixmap"""
        self._pixmap = pixmap
        self.update()

    def set_crop_margins(self, left: float, top: float, right: float, bottom: float):
        """Set crop margins (0-1 normalized)"""
        self._crop_rect = QRectF(left, top, 1 - left - right, 1 - top - bottom)
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)

        if not self._pixmap:
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Calculate scaled pixmap size to fit widget
        widget_rect = self.rect()
        scaled = self._pixmap.scaled(
            widget_rect.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )

        # Center the pixmap
        x = (widget_rect.width() - scaled.width()) // 2
        y = (widget_rect.height() - scaled.height()) // 2
        self._page_rect = QRectF(x, y, scaled.width(), scaled.height())

        # Draw the pixmap
        painter.drawPixmap(int(x), int(y), scaled)

        # Draw crop overlay (darken outside crop area)
        crop_x = x + self._crop_rect.x() * scaled.width()
        crop_y = y + self._crop_rect.y() * scaled.height()
        crop_w = self._crop_rect.width() * scaled.width()
        crop_h = self._crop_rect.height() * scaled.height()

        # Draw darkened areas
        dark = QColor(0, 0, 0, 128)

        # Top
        painter.fillRect(int(x), int(y), int(scaled.width()), int(crop_y - y), dark)
        # Bottom
        painter.fillRect(int(x), int(crop_y + crop_h), int(scaled.width()),
                        int(scaled.height() - crop_y - crop_h + y), dark)
        # Left
        painter.fillRect(int(x), int(crop_y), int(crop_x - x), int(crop_h), dark)
        # Right
        painter.fillRect(int(crop_x + crop_w), int(crop_y),
                        int(scaled.width() - crop_x - crop_w + x), int(crop_h), dark)

        # Draw crop rectangle
        pen = QPen(QColor(255, 100, 100), 2)
        painter.setPen(pen)
        painter.drawRect(int(crop_x), int(crop_y), int(crop_w), int(crop_h))

        painter.end()


class CropDialog(QDialog):
    """Dialog for cropping PDF pages"""

    def __init__(self, pixmap: QPixmap, page_width: float, page_height: float, parent=None):
        super().__init__(parent)
        self._page_width = page_width
        self._page_height = page_height

        self.setWindowTitle("Crop Page")
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint)
        self.setMinimumSize(500, 600)

        self._setup_ui()
        self._preview.set_pixmap(pixmap)
        self._update_preview()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Preview
        self._preview = CropPreview()
        layout.addWidget(self._preview, 1)

        # Margin controls
        margins_group = QGroupBox("Crop Margins (in points)")
        margins_layout = QHBoxLayout(margins_group)

        # Left margin
        left_layout = QVBoxLayout()
        left_layout.addWidget(QLabel("Left:"))
        self._left_spin = QSpinBox()
        self._left_spin.setRange(0, int(self._page_width / 2))
        self._left_spin.setValue(0)
        self._left_spin.valueChanged.connect(self._update_preview)
        left_layout.addWidget(self._left_spin)
        margins_layout.addLayout(left_layout)

        # Top margin
        top_layout = QVBoxLayout()
        top_layout.addWidget(QLabel("Top:"))
        self._top_spin = QSpinBox()
        self._top_spin.setRange(0, int(self._page_height / 2))
        self._top_spin.setValue(0)
        self._top_spin.valueChanged.connect(self._update_preview)
        top_layout.addWidget(self._top_spin)
        margins_layout.addLayout(top_layout)

        # Right margin
        right_layout = QVBoxLayout()
        right_layout.addWidget(QLabel("Right:"))
        self._right_spin = QSpinBox()
        self._right_spin.setRange(0, int(self._page_width / 2))
        self._right_spin.setValue(0)
        self._right_spin.valueChanged.connect(self._update_preview)
        right_layout.addWidget(self._right_spin)
        margins_layout.addLayout(right_layout)

        # Bottom margin
        bottom_layout = QVBoxLayout()
        bottom_layout.addWidget(QLabel("Bottom:"))
        self._bottom_spin = QSpinBox()
        self._bottom_spin.setRange(0, int(self._page_height / 2))
        self._bottom_spin.setValue(0)
        self._bottom_spin.valueChanged.connect(self._update_preview)
        bottom_layout.addWidget(self._bottom_spin)
        margins_layout.addLayout(bottom_layout)

        layout.addWidget(margins_group)

        # Apply to all pages option
        self._apply_all = QCheckBox("Apply to all pages")
        layout.addWidget(self._apply_all)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        reset_btn = QPushButton("Reset")
        reset_btn.clicked.connect(self._reset)
        button_layout.addWidget(reset_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        crop_btn = QPushButton("Crop")
        crop_btn.clicked.connect(self.accept)
        crop_btn.setDefault(True)
        button_layout.addWidget(crop_btn)

        layout.addLayout(button_layout)

    def _update_preview(self):
        """Update crop preview"""
        left = self._left_spin.value() / self._page_width
        top = self._top_spin.value() / self._page_height
        right = self._right_spin.value() / self._page_width
        bottom = self._bottom_spin.value() / self._page_height

        self._preview.set_crop_margins(left, top, right, bottom)

    def _reset(self):
        """Reset all margins to zero"""
        self._left_spin.setValue(0)
        self._top_spin.setValue(0)
        self._right_spin.setValue(0)
        self._bottom_spin.setValue(0)

    def get_crop_rect(self) -> Tuple[float, float, float, float]:
        """Get crop rectangle (x0, y0, x1, y1) in page coordinates"""
        x0 = self._left_spin.value()
        y0 = self._top_spin.value()
        x1 = self._page_width - self._right_spin.value()
        y1 = self._page_height - self._bottom_spin.value()
        return (x0, y0, x1, y1)

    def apply_to_all_pages(self) -> bool:
        """Check if crop should be applied to all pages"""
        return self._apply_all.isChecked()
