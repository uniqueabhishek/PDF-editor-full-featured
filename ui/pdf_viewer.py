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
        """Handle annotation creation"""
        if self._tool_mode == ToolMode.SELECT:
            self.selection_changed.emit(page_num, rect)

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

    def get_selected_text(self) -> str:
        """Get currently selected text"""
        # Implementation would extract text from selection rectangle
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
