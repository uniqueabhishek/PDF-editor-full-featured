"""
Ultra PDF Editor - PDF Viewer Widget
High-performance PDF rendering and interaction widget
"""
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QRubberBand,
    QApplication, QMenu, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QPoint, QPointF, QRect, QRectF, QSize, pyqtSignal, QTimer, QThread
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QCursor, QPen, QBrush,
    QWheelEvent, QMouseEvent, QKeyEvent, QTransform, QFont
)
import fitz
from typing import Optional, List, Tuple, Dict, Any
from enum import Enum
from dataclasses import dataclass
import math


class ViewMode(Enum):
    SINGLE_PAGE = "single"
    TWO_PAGE = "two_page"
    CONTINUOUS = "continuous"


class ToolMode(Enum):
    SELECT = "select"
    HAND = "hand"
    TEXT_SELECT = "text_select"
    HIGHLIGHT = "highlight"
    UNDERLINE = "underline"
    STRIKETHROUGH = "strikethrough"
    TEXT_BOX = "text_box"
    STICKY_NOTE = "sticky_note"
    RECTANGLE = "rectangle"
    CIRCLE = "circle"
    LINE = "line"
    ARROW = "arrow"
    FREEHAND = "freehand"
    ERASER = "eraser"
    REDACT = "redact"


class ZoomMode(Enum):
    CUSTOM = "custom"
    FIT_PAGE = "fit_page"
    FIT_WIDTH = "fit_width"
    FIT_HEIGHT = "fit_height"


@dataclass
class RenderTask:
    """A page rendering task"""
    page_num: int
    zoom: float
    priority: int = 0


class PageWidget(QLabel):
    """Widget representing a single PDF page"""

    clicked = pyqtSignal(int, QPointF)  # page_num, position
    annotation_created = pyqtSignal(int, str, QRectF)  # page_num, type, rect

    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._pixmap: Optional[QPixmap] = None
        self._zoom = 1.0
        self._page_rect = QRectF()
        self._selection_start: Optional[QPointF] = None
        self._selection_rect: Optional[QRectF] = None
        self._rubber_band: Optional[QRubberBand] = None
        self._annotations: List[Dict] = []
        self._highlights: List[QRectF] = []

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

    def set_pixmap(self, pixmap: QPixmap, zoom: float = 1.0):
        """Set the page pixmap"""
        self._pixmap = pixmap
        self._zoom = zoom
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def get_page_position(self, widget_pos: QPoint) -> QPointF:
        """Convert widget position to page coordinates"""
        if self._zoom == 0:
            return QPointF(0, 0)
        return QPointF(widget_pos.x() / self._zoom, widget_pos.y() / self._zoom)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._selection_start = event.position()
            self.clicked.emit(self.page_num, self.get_page_position(event.pos()))
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selection_start:
            # Update selection rectangle
            current = event.position()
            rect = QRectF(self._selection_start, current).normalized()
            self._selection_rect = rect
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._selection_rect and self._selection_start:
            # Emit annotation created signal
            page_rect = QRectF(
                self._selection_rect.x() / self._zoom,
                self._selection_rect.y() / self._zoom,
                self._selection_rect.width() / self._zoom,
                self._selection_rect.height() / self._zoom
            )
            self.annotation_created.emit(self.page_num, "selection", page_rect)

        self._selection_start = None
        self._selection_rect = None
        self.update()
        super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)

        if self._selection_rect:
            painter = QPainter(self)
            painter.setPen(QPen(QColor(0, 120, 215), 1))
            painter.setBrush(QBrush(QColor(0, 120, 215, 50)))
            painter.drawRect(self._selection_rect.toRect())
            painter.end()


class PDFViewer(QScrollArea):
    """
    Main PDF viewer widget with support for:
    - Continuous scroll and single page view
    - Zoom and pan
    - Annotations and markup
    - Text selection
    - Multiple tool modes
    """

    # Signals
    page_changed = pyqtSignal(int)  # current page number
    zoom_changed = pyqtSignal(float)  # new zoom level
    selection_changed = pyqtSignal(int, QRectF)  # page, selection rect
    annotation_added = pyqtSignal(int, str, dict)  # page, type, data
    document_modified = pyqtSignal()
    text_selected = pyqtSignal(str)  # selected text

    def __init__(self, parent=None):
        super().__init__(parent)

        # Document reference
        self._doc: Optional[fitz.Document] = None
        self._filepath: Optional[str] = None

        # View state
        self._current_page = 0
        self._zoom = 1.0
        self._zoom_mode = ZoomMode.FIT_WIDTH
        self._view_mode = ViewMode.CONTINUOUS
        self._rotation = 0

        # Rendering
        self._render_dpi = 150
        self._page_widgets: List[PageWidget] = []
        self._page_cache: Dict[int, QPixmap] = {}
        self._cache_size = 10

        # Tool state
        self._tool_mode = ToolMode.HAND
        self._annotation_color = QColor(255, 255, 0)  # Yellow
        self._annotation_opacity = 0.5
        self._stroke_width = 2
        self._font_size = 12
        self._font_family = "Arial"

        # Interaction state
        self._is_panning = False
        self._last_pan_pos = QPoint()
        self._freehand_points: List[QPointF] = []

        # Setup UI
        self._setup_ui()

        # Render timer for debouncing
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_visible_pages)

    def _setup_ui(self):
        """Setup the viewer UI"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container widget for pages
        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(20, 20, 20, 20)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        self.setWidget(self._container)

        # Styling
        self.setStyleSheet("""
            QScrollArea {
                background-color: #525659;
                border: none;
            }
            QScrollBar:vertical {
                background: #3c3c3c;
                width: 12px;
            }
            QScrollBar::handle:vertical {
                background: #606060;
                border-radius: 6px;
                min-height: 30px;
            }
            QScrollBar:horizontal {
                background: #3c3c3c;
                height: 12px;
            }
            QScrollBar::handle:horizontal {
                background: #606060;
                border-radius: 6px;
                min-width: 30px;
            }
        """)

        # Connect scroll for page tracking
        self.verticalScrollBar().valueChanged.connect(self._on_scroll)

    def set_document(self, doc: fitz.Document, filepath: str = None):
        """Set the document to display"""
        self._doc = doc
        self._filepath = filepath
        self._current_page = 0
        self._page_cache.clear()

        # Clear existing pages
        self._clear_pages()

        if doc and len(doc) > 0:
            # Create page widgets
            self._create_page_widgets()

            # Initial render
            self._update_zoom()
            self._render_visible_pages()

    def _clear_pages(self):
        """Clear all page widgets"""
        for widget in self._page_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._page_widgets.clear()

    def _create_page_widgets(self):
        """Create widgets for all pages"""
        if not self._doc:
            return

        for i in range(len(self._doc)):
            page_widget = PageWidget(i, self._container)
            page_widget.clicked.connect(self._on_page_clicked)
            page_widget.annotation_created.connect(self._on_annotation_created)
            self._layout.addWidget(page_widget)
            self._page_widgets.append(page_widget)

    def _render_page(self, page_num: int) -> QPixmap:
        """Render a single page to pixmap"""
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return QPixmap()

        # Check cache
        cache_key = (page_num, self._zoom, self._rotation)
        if page_num in self._page_cache:
            return self._page_cache[page_num]

        page = self._doc[page_num]
        zoom_matrix = fitz.Matrix(self._zoom * self._render_dpi / 72,
                                   self._zoom * self._render_dpi / 72)
        zoom_matrix = zoom_matrix.prerotate(self._rotation)

        pixmap = page.get_pixmap(matrix=zoom_matrix, alpha=False)

        # Convert to QPixmap
        img = QImage(pixmap.samples, pixmap.width, pixmap.height,
                     pixmap.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(img)

        # Cache management
        if len(self._page_cache) >= self._cache_size:
            # Remove oldest entry
            oldest = next(iter(self._page_cache))
            del self._page_cache[oldest]

        self._page_cache[page_num] = qpixmap
        return qpixmap

    def _render_visible_pages(self):
        """Render pages that are currently visible"""
        if not self._doc or not self._page_widgets:
            return

        viewport = self.viewport().rect()
        scroll_pos = self.verticalScrollBar().value()

        for i, page_widget in enumerate(self._page_widgets):
            widget_rect = page_widget.geometry()
            widget_rect.translate(0, -scroll_pos)

            # Check if visible
            if viewport.intersects(widget_rect):
                pixmap = self._render_page(i)
                page_widget.set_pixmap(pixmap, self._zoom)

    def _on_scroll(self):
        """Handle scroll events"""
        self._render_timer.start(50)  # Debounce rendering
        self._update_current_page()

    def _update_current_page(self):
        """Update current page based on scroll position"""
        if not self._page_widgets:
            return

        viewport_center = self.viewport().height() / 2
        scroll_pos = self.verticalScrollBar().value()

        for i, page_widget in enumerate(self._page_widgets):
            widget_rect = page_widget.geometry()
            widget_center = widget_rect.center().y() - scroll_pos

            if abs(widget_center - viewport_center) < widget_rect.height() / 2:
                if i != self._current_page:
                    self._current_page = i
                    self.page_changed.emit(i)
                break

    def _update_zoom(self):
        """Update zoom level based on zoom mode"""
        if not self._doc or not self._page_widgets:
            return

        if self._zoom_mode == ZoomMode.FIT_WIDTH:
            viewport_width = self.viewport().width() - 60  # Account for margins
            page = self._doc[0]
            page_width = page.rect.width * self._render_dpi / 72
            self._zoom = viewport_width / page_width

        elif self._zoom_mode == ZoomMode.FIT_PAGE:
            viewport = self.viewport().rect()
            page = self._doc[0]
            page_width = page.rect.width * self._render_dpi / 72
            page_height = page.rect.height * self._render_dpi / 72

            zoom_w = (viewport.width() - 60) / page_width
            zoom_h = (viewport.height() - 60) / page_height
            self._zoom = min(zoom_w, zoom_h)

        elif self._zoom_mode == ZoomMode.FIT_HEIGHT:
            viewport_height = self.viewport().height() - 60
            page = self._doc[0]
            page_height = page.rect.height * self._render_dpi / 72
            self._zoom = viewport_height / page_height

        self._page_cache.clear()  # Clear cache on zoom change
        self.zoom_changed.emit(self._zoom * 100)

    def _on_page_clicked(self, page_num: int, position: QPointF):
        """Handle page click"""
        self._current_page = page_num
        self.page_changed.emit(page_num)

    def _on_annotation_created(self, page_num: int, annot_type: str, rect: QRectF):
        """Handle annotation creation based on current tool mode"""
        if not self._doc or rect.width() < 5 or rect.height() < 5:
            return

        if self._tool_mode == ToolMode.SELECT:
            self.selection_changed.emit(page_num, rect)

        elif self._tool_mode == ToolMode.HIGHLIGHT:
            self._create_text_markup_annotation(page_num, rect, fitz.PDF_ANNOT_HIGHLIGHT)

        elif self._tool_mode == ToolMode.UNDERLINE:
            self._create_text_markup_annotation(page_num, rect, fitz.PDF_ANNOT_UNDERLINE)

        elif self._tool_mode == ToolMode.STRIKETHROUGH:
            self._create_text_markup_annotation(page_num, rect, fitz.PDF_ANNOT_STRIKEOUT)

        elif self._tool_mode == ToolMode.TEXT_BOX:
            self._create_text_annotation(page_num, rect, free_text=True)

        elif self._tool_mode == ToolMode.STICKY_NOTE:
            self._create_text_annotation(page_num, rect, free_text=False)

        elif self._tool_mode == ToolMode.RECTANGLE:
            self._create_shape_annotation(page_num, rect, "rectangle")

        elif self._tool_mode == ToolMode.CIRCLE:
            self._create_shape_annotation(page_num, rect, "circle")

        elif self._tool_mode == ToolMode.LINE:
            self._create_line_annotation(page_num, rect, arrow=False)

        elif self._tool_mode == ToolMode.ARROW:
            self._create_line_annotation(page_num, rect, arrow=True)

        elif self._tool_mode == ToolMode.REDACT:
            self._create_redaction_annotation(page_num, rect)

        elif self._tool_mode == ToolMode.ERASER:
            self._erase_annotation_at(page_num, rect)

    def _create_text_markup_annotation(self, page_num: int, rect: QRectF, annot_type: int):
        """Create highlight, underline, or strikethrough annotation"""
        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                   rect.x() + rect.width(),
                                   rect.y() + rect.height())

            # Get quads for text in the area
            text_dict = page.get_text("dict", clip=fitz_rect)
            quads = []

            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if fitz_rect.intersects(span_rect):
                                quads.append(span_rect.quad)

            if quads:
                annot = page.add_highlight_annot(quads) if annot_type == fitz.PDF_ANNOT_HIGHLIGHT else \
                        page.add_underline_annot(quads) if annot_type == fitz.PDF_ANNOT_UNDERLINE else \
                        page.add_strikeout_annot(quads)
            else:
                # No text found, create annotation on the rect itself
                if annot_type == fitz.PDF_ANNOT_HIGHLIGHT:
                    annot = page.add_highlight_annot(fitz_rect)
                elif annot_type == fitz.PDF_ANNOT_UNDERLINE:
                    annot = page.add_underline_annot(fitz_rect)
                else:
                    annot = page.add_strikeout_annot(fitz_rect)

            # Set color
            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())
            annot.set_colors(stroke=color)
            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, "text_markup", {"rect": rect})

        except Exception as e:
            print(f"Error creating text markup annotation: {e}")

    def _create_text_annotation(self, page_num: int, rect: QRectF, free_text: bool = False):
        """Create text box or sticky note annotation"""
        from PyQt6.QtWidgets import QInputDialog

        text, ok = QInputDialog.getMultiLineText(
            self, "Add Text",
            "Enter text:" if free_text else "Enter note:",
            ""
        )
        if not ok or not text:
            return

        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                   rect.x() + rect.width(),
                                   rect.y() + rect.height())

            if free_text:
                # Free text annotation (text box)
                annot = page.add_freetext_annot(
                    fitz_rect, text,
                    fontsize=self._font_size,
                    fontname="helv",
                    text_color=(0, 0, 0),
                    fill_color=(1, 1, 0.8)
                )
            else:
                # Sticky note
                point = fitz.Point(rect.x(), rect.y())
                annot = page.add_text_annot(point, text)
                color = (self._annotation_color.redF(),
                         self._annotation_color.greenF(),
                         self._annotation_color.blueF())
                annot.set_colors(stroke=color)

            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, "text", {"text": text, "rect": rect})

        except Exception as e:
            print(f"Error creating text annotation: {e}")

    def _create_shape_annotation(self, page_num: int, rect: QRectF, shape: str):
        """Create rectangle or circle annotation"""
        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                   rect.x() + rect.width(),
                                   rect.y() + rect.height())

            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())

            if shape == "rectangle":
                annot = page.add_rect_annot(fitz_rect)
            else:  # circle
                annot = page.add_circle_annot(fitz_rect)

            annot.set_colors(stroke=color)
            annot.set_border(width=self._stroke_width)
            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, shape, {"rect": rect})

        except Exception as e:
            print(f"Error creating shape annotation: {e}")

    def _create_line_annotation(self, page_num: int, rect: QRectF, arrow: bool = False):
        """Create line or arrow annotation"""
        try:
            page = self._doc[page_num]

            # Line from top-left to bottom-right of selection
            p1 = fitz.Point(rect.x(), rect.y())
            p2 = fitz.Point(rect.x() + rect.width(), rect.y() + rect.height())

            annot = page.add_line_annot(p1, p2)

            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())
            annot.set_colors(stroke=color)
            annot.set_border(width=self._stroke_width)

            if arrow:
                # Set line ending to arrow
                annot.set_line_ends(fitz.PDF_ANNOT_LE_NONE, fitz.PDF_ANNOT_LE_OPEN_ARROW)

            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, "line" if not arrow else "arrow", {"rect": rect})

        except Exception as e:
            print(f"Error creating line annotation: {e}")

    def _create_redaction_annotation(self, page_num: int, rect: QRectF):
        """Create redaction annotation"""
        from PyQt6.QtWidgets import QMessageBox

        result = QMessageBox.question(
            self, "Apply Redaction",
            "This will permanently remove content in the selected area.\n"
            "The redaction will be applied when you save the document.\n\n"
            "Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if result != QMessageBox.StandardButton.Yes:
            return

        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                   rect.x() + rect.width(),
                                   rect.y() + rect.height())

            annot = page.add_redact_annot(fitz_rect)
            annot.set_colors(stroke=(0, 0, 0), fill=(0, 0, 0))
            annot.update()

            # Apply the redaction
            page.apply_redactions()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, "redaction", {"rect": rect})

        except Exception as e:
            print(f"Error creating redaction: {e}")

    def _erase_annotation_at(self, page_num: int, rect: QRectF):
        """Erase annotations that intersect with the given rect"""
        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                   rect.x() + rect.width(),
                                   rect.y() + rect.height())

            deleted = False
            for annot in page.annots():
                if annot.rect.intersects(fitz_rect):
                    page.delete_annot(annot)
                    deleted = True

            if deleted:
                self.document_modified.emit()
                self.refresh()

        except Exception as e:
            print(f"Error erasing annotation: {e}")

    # ==================== Public Interface ====================

    def get_current_page(self) -> int:
        """Get current page number (0-indexed)"""
        return self._current_page

    def get_page_count(self) -> int:
        """Get total page count"""
        return len(self._doc) if self._doc else 0

    def get_zoom(self) -> float:
        """Get current zoom level (percentage)"""
        return self._zoom * 100

    def set_zoom(self, zoom: float):
        """Set zoom level (percentage)"""
        self._zoom = max(0.1, min(8.0, zoom / 100))
        self._zoom_mode = ZoomMode.CUSTOM
        self._page_cache.clear()
        self._render_visible_pages()
        self.zoom_changed.emit(self._zoom * 100)

    def zoom_in(self, factor: float = 1.25):
        """Zoom in by factor"""
        self.set_zoom(self._zoom * 100 * factor)

    def zoom_out(self, factor: float = 1.25):
        """Zoom out by factor"""
        self.set_zoom(self._zoom * 100 / factor)

    def fit_width(self):
        """Fit page to viewport width"""
        self._zoom_mode = ZoomMode.FIT_WIDTH
        self._update_zoom()
        self._render_visible_pages()

    def fit_page(self):
        """Fit entire page in viewport"""
        self._zoom_mode = ZoomMode.FIT_PAGE
        self._update_zoom()
        self._render_visible_pages()

    def go_to_page(self, page_num: int):
        """Navigate to a specific page"""
        if not self._page_widgets or page_num < 0 or page_num >= len(self._page_widgets):
            return

        page_widget = self._page_widgets[page_num]
        self.ensureWidgetVisible(page_widget)
        self._current_page = page_num
        self.page_changed.emit(page_num)

    def next_page(self):
        """Go to next page"""
        if self._current_page < len(self._page_widgets) - 1:
            self.go_to_page(self._current_page + 1)

    def previous_page(self):
        """Go to previous page"""
        if self._current_page > 0:
            self.go_to_page(self._current_page - 1)

    def first_page(self):
        """Go to first page"""
        self.go_to_page(0)

    def last_page(self):
        """Go to last page"""
        self.go_to_page(len(self._page_widgets) - 1)

    def set_tool_mode(self, mode: ToolMode):
        """Set the current tool mode"""
        self._tool_mode = mode

        # Update cursor
        cursor_map = {
            ToolMode.HAND: Qt.CursorShape.OpenHandCursor,
            ToolMode.SELECT: Qt.CursorShape.ArrowCursor,
            ToolMode.TEXT_SELECT: Qt.CursorShape.IBeamCursor,
            ToolMode.HIGHLIGHT: Qt.CursorShape.CrossCursor,
            ToolMode.FREEHAND: Qt.CursorShape.CrossCursor,
        }
        self.setCursor(cursor_map.get(mode, Qt.CursorShape.ArrowCursor))

    def set_annotation_color(self, color: QColor):
        """Set annotation color"""
        self._annotation_color = color

    def set_annotation_opacity(self, opacity: float):
        """Set annotation opacity (0.0 - 1.0)"""
        self._annotation_opacity = max(0.0, min(1.0, opacity))

    def set_stroke_width(self, width: int):
        """Set stroke width for drawing tools"""
        self._stroke_width = max(1, width)

    def rotate_view(self, degrees: int):
        """Rotate the view"""
        self._rotation = (self._rotation + degrees) % 360
        self._page_cache.clear()
        self._render_visible_pages()

    def set_view_mode(self, mode: ViewMode):
        """Set the view mode (single page, two page, continuous)"""
        if self._view_mode == mode:
            return

        self._view_mode = mode
        self._rebuild_layout()

    def _rebuild_layout(self):
        """Rebuild the page layout based on current view mode"""
        if not self._doc or not self._page_widgets:
            return

        # Clear current layout
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().setParent(None)
            elif item.layout():
                # Clear nested layout
                while item.layout().count():
                    sub_item = item.layout().takeAt(0)
                    if sub_item.widget():
                        sub_item.widget().setParent(None)

        if self._view_mode == ViewMode.CONTINUOUS:
            # All pages in vertical layout
            for page_widget in self._page_widgets:
                page_widget.setParent(self._container)
                self._layout.addWidget(page_widget)

        elif self._view_mode == ViewMode.SINGLE_PAGE:
            # Only show current page
            for i, page_widget in enumerate(self._page_widgets):
                page_widget.setParent(self._container)
                if i == self._current_page:
                    self._layout.addWidget(page_widget)
                    page_widget.show()
                else:
                    page_widget.hide()

        elif self._view_mode == ViewMode.TWO_PAGE:
            # Show pages in pairs
            for i in range(0, len(self._page_widgets), 2):
                row_layout = QHBoxLayout()
                row_layout.setSpacing(20)
                row_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

                # Left page
                self._page_widgets[i].setParent(self._container)
                row_layout.addWidget(self._page_widgets[i])
                self._page_widgets[i].show()

                # Right page (if exists)
                if i + 1 < len(self._page_widgets):
                    self._page_widgets[i + 1].setParent(self._container)
                    row_layout.addWidget(self._page_widgets[i + 1])
                    self._page_widgets[i + 1].show()

                self._layout.addLayout(row_layout)

        self._render_visible_pages()

    def get_selected_text(self) -> str:
        """Get currently selected text from selection rectangle"""
        if not self._doc:
            return ""

        # Get text from current page widget's selection
        if self._current_page < len(self._page_widgets):
            page_widget = self._page_widgets[self._current_page]
            if page_widget._selection_rect:
                rect = page_widget._selection_rect
                page_rect = QRectF(
                    rect.x() / page_widget._zoom,
                    rect.y() / page_widget._zoom,
                    rect.width() / page_widget._zoom,
                    rect.height() / page_widget._zoom
                )
                fitz_rect = fitz.Rect(
                    page_rect.x(), page_rect.y(),
                    page_rect.x() + page_rect.width(),
                    page_rect.y() + page_rect.height()
                )
                page = self._doc[self._current_page]
                text = page.get_text("text", clip=fitz_rect)
                return text.strip()
        return ""

    def refresh(self):
        """Refresh the view"""
        self._page_cache.clear()
        self._render_visible_pages()

    # ==================== Event Handlers ====================

    def wheelEvent(self, event: QWheelEvent):
        """Handle mouse wheel for zoom/scroll"""
        modifiers = event.modifiers()

        if modifiers == Qt.KeyboardModifier.ControlModifier:
            # Zoom with Ctrl+wheel
            delta = event.angleDelta().y()
            if delta > 0:
                self.zoom_in()
            else:
                self.zoom_out()
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press"""
        if self._tool_mode == ToolMode.HAND and event.button() == Qt.MouseButton.LeftButton:
            self._is_panning = True
            self._last_pan_pos = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move"""
        if self._is_panning:
            delta = event.pos() - self._last_pan_pos
            self._last_pan_pos = event.pos()

            self.horizontalScrollBar().setValue(
                self.horizontalScrollBar().value() - delta.x()
            )
            self.verticalScrollBar().setValue(
                self.verticalScrollBar().value() - delta.y()
            )
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release"""
        if self._is_panning:
            self._is_panning = False
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def keyPressEvent(self, event: QKeyEvent):
        """Handle key press"""
        key = event.key()

        if key == Qt.Key.Key_PageDown:
            self.next_page()
        elif key == Qt.Key.Key_PageUp:
            self.previous_page()
        elif key == Qt.Key.Key_Home:
            self.first_page()
        elif key == Qt.Key.Key_End:
            self.last_page()
        elif key == Qt.Key.Key_Plus or key == Qt.Key.Key_Equal:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.zoom_in()
        elif key == Qt.Key.Key_Minus:
            if event.modifiers() == Qt.KeyboardModifier.ControlModifier:
                self.zoom_out()
        else:
            super().keyPressEvent(event)

    def resizeEvent(self, event):
        """Handle resize"""
        super().resizeEvent(event)
        if self._zoom_mode in (ZoomMode.FIT_WIDTH, ZoomMode.FIT_PAGE, ZoomMode.FIT_HEIGHT):
            self._update_zoom()
            self._render_timer.start(100)

    def contextMenuEvent(self, event):
        """Show context menu"""
        menu = QMenu(self)

        # Zoom options
        zoom_menu = menu.addMenu("Zoom")
        zoom_menu.addAction("Zoom In", self.zoom_in)
        zoom_menu.addAction("Zoom Out", self.zoom_out)
        zoom_menu.addSeparator()
        zoom_menu.addAction("Fit Width", self.fit_width)
        zoom_menu.addAction("Fit Page", self.fit_page)
        zoom_menu.addAction("100%", lambda: self.set_zoom(100))

        menu.addSeparator()

        # Navigation
        nav_menu = menu.addMenu("Go To")
        nav_menu.addAction("First Page", self.first_page)
        nav_menu.addAction("Previous Page", self.previous_page)
        nav_menu.addAction("Next Page", self.next_page)
        nav_menu.addAction("Last Page", self.last_page)

        menu.addSeparator()

        # Rotation
        menu.addAction("Rotate Clockwise", lambda: self.rotate_view(90))
        menu.addAction("Rotate Counter-Clockwise", lambda: self.rotate_view(-90))

        menu.exec(event.globalPos())
