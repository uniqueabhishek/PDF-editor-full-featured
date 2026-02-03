"""
Ultra PDF Editor - PDF Viewer Widget
High-performance PDF rendering and interaction widget
"""
from PyQt6.QtWidgets import (
    QWidget, QScrollArea, QVBoxLayout, QHBoxLayout, QLabel,
    QRubberBand, QApplication, QMenu, QSizePolicy
)
from PyQt6.QtCore import (
    Qt, QPoint, QPointF, QRectF, pyqtSignal, QTimer, QThread
)
from PyQt6.QtGui import (
    QPixmap, QImage, QPainter, QColor, QPen, QBrush,
    QWheelEvent, QMouseEvent, QKeyEvent
)
import fitz
from typing import Optional, List, Dict, cast, Any
from enum import Enum
from dataclasses import dataclass


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
    STAMP = "stamp"


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


class PageRenderWorker(QThread):
    """Background worker for rendering PDF pages"""

    page_rendered = pyqtSignal(int, QImage, float)  # page_num, image, zoom

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._tasks: List[RenderTask] = []
        self._render_dpi = 150
        self._rotation = 0
        self._running = True
        self._current_zoom = 1.0

    def set_document(self, doc: Optional[fitz.Document], render_dpi: int = 150):
        """Set the document to render"""
        self._doc = doc
        self._render_dpi = render_dpi
        self._tasks.clear()

    def set_rotation(self, rotation: int):
        """Set rotation angle"""
        self._rotation = rotation

    def request_page(self, page_num: int, zoom: float, priority: int = 0):
        """Request a page to be rendered"""
        # Remove any existing task for this page
        self._tasks = [t for t in self._tasks if t.page_num != page_num]
        self._tasks.append(RenderTask(page_num, zoom, priority))
        self._current_zoom = zoom
        # Sort by priority (higher first)
        self._tasks.sort(key=lambda t: t.priority, reverse=True)

    def clear_tasks(self):
        """Clear pending tasks"""
        self._tasks.clear()

    def stop(self):
        """Stop the worker"""
        self._running = False
        self.wait()

    def run(self):
        """Main render loop"""
        while self._running:
            if self._tasks and self._doc:
                task = self._tasks.pop(0)

                # Skip if zoom changed (task is outdated)
                if abs(task.zoom - self._current_zoom) > 0.001:
                    continue

                try:
                    page = self._doc[task.page_num]
                    zoom_matrix = fitz.Matrix(
                        task.zoom * self._render_dpi / 72,
                        task.zoom * self._render_dpi / 72
                    )
                    zoom_matrix = zoom_matrix.prerotate(self._rotation)

                    pixmap = page.get_pixmap(matrix=zoom_matrix, alpha=False)

                    # Convert to QImage (can be done in thread)
                    img = QImage(
                        pixmap.samples, pixmap.width, pixmap.height,
                        pixmap.stride, QImage.Format.Format_RGB888
                    ).copy()  # Copy to detach from pixmap memory

                    self.page_rendered.emit(task.page_num, img, task.zoom)

                except Exception as e:
                    print(f"Error rendering page {task.page_num}: {e}")
            else:
                self.msleep(10)  # Sleep briefly when idle


class PageWidget(QLabel):
    """Widget representing a single PDF page"""

    clicked = pyqtSignal(int, QPointF)  # page_num, position
    annotation_created = pyqtSignal(int, str, QRectF)  # page_num, type, rect
    # page_num, list of (x, y) points in PDF coordinates
    freehand_created = pyqtSignal(int, list)
    # page_num, position in PDF coordinates (for tooltip)
    hover_position = pyqtSignal(int, QPointF)

    def __init__(self, page_num: int, render_dpi: int = 150, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._pixmap: Optional[QPixmap] = None
        self._zoom = 1.0
        self._render_dpi = render_dpi  # Store render DPI for coordinate conversion
        self._page_rect = QRectF()
        self._selection_start: Optional[QPointF] = None
        self._selection_rect: Optional[QRectF] = None
        self._rubber_band: Optional[QRubberBand] = None
        self._annotations: List[Dict] = []
        self._highlights: List[QRectF] = []
        self._is_loading = True
        self._tool_mode: Optional[str] = None  # Current tool mode
        # Points for freehand drawing
        self._freehand_points: List[QPointF] = []

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setText("")  # Clear any default text
        self.setMouseTracking(True)  # Enable mouse tracking for move events

    def set_tool_mode(self, mode: str):
        """Set the current tool mode"""
        self._tool_mode = mode

    def set_pixmap(self, pixmap: QPixmap, zoom: float = 1.0):
        """Set the page pixmap"""
        self._pixmap = pixmap
        self._zoom = zoom
        self._is_loading = False
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def set_placeholder(self, width: int, height: int):
        """Set a white placeholder of the given size"""
        self._is_loading = True
        self._pixmap = None

        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)

        # Create a proper white pixmap
        placeholder = QPixmap(width, height)
        placeholder.fill(Qt.GlobalColor.white)

        # Draw a subtle loading indicator
        painter = QPainter(placeholder)
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        painter.drawRect(0, 0, width - 1, height - 1)
        painter.end()

        self.setPixmap(placeholder)
        self.setFixedSize(width, height)

    def get_page_position(self, widget_pos: QPoint) -> QPointF:
        """Convert widget position to PDF page coordinates (72 DPI)"""
        # Widget pixels are rendered at: zoom * render_dpi / 72
        # To convert back to PDF coordinates (72 DPI), divide by the full scale
        scale = self._zoom * self._render_dpi / 72
        if scale == 0:
            return QPointF(0, 0)
        return QPointF(widget_pos.x() / scale, widget_pos.y() / scale)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            self._selection_start = event.position()
            # Start collecting freehand points
            self._freehand_points = [event.position()]
            self.clicked.emit(
                self.page_num, self.get_page_position(event.pos()))
            event.accept()  # Accept the event to receive move/release events
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._selection_start is not None:
            current = event.position()
            # Update selection rectangle
            rect = QRectF(self._selection_start, current).normalized()
            self._selection_rect = rect
            # Collect points for freehand drawing
            if self._tool_mode == "freehand":
                self._freehand_points.append(current)
            self.update()
            event.accept()
        else:
            # Emit hover position for tooltip handling (when not dragging)
            pdf_pos = self.get_page_position(event.pos())
            self.hover_position.emit(self.page_num, pdf_pos)
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if self._selection_start is not None:
            scale = self._zoom * self._render_dpi / 72

            # Handle freehand drawing with collected points
            if self._tool_mode == "freehand" and len(self._freehand_points) > 1 and scale > 0:
                # Convert all points to PDF coordinates
                pdf_points = []
                for pt in self._freehand_points:
                    pdf_points.append((pt.x() / scale, pt.y() / scale))
                self.freehand_created.emit(self.page_num, pdf_points)
            elif self._selection_rect is not None and scale > 0:
                # Convert widget coordinates to PDF page coordinates (72 DPI)
                page_rect = QRectF(
                    self._selection_rect.x() / scale,
                    self._selection_rect.y() / scale,
                    self._selection_rect.width() / scale,
                    self._selection_rect.height() / scale
                )
                self.annotation_created.emit(
                    self.page_num, "selection", page_rect)

            self._selection_start = None
            self._selection_rect = None
            self._freehand_points = []
            self.update()
            event.accept()
        else:
            super().mouseReleaseEvent(event)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QPainter(self)

        # Draw freehand stroke while drawing
        if self._tool_mode == "freehand" and len(self._freehand_points) > 1:
            painter.setPen(QPen(QColor(255, 0, 0), 2))
            for i in range(1, len(self._freehand_points)):
                p1 = self._freehand_points[i - 1]
                p2 = self._freehand_points[i]
                painter.drawLine(int(p1.x()), int(p1.y()),
                                 int(p2.x()), int(p2.y()))
        elif self._selection_rect is not None:
            # Draw selection rectangle for other tools
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
    annotation_create_requested = pyqtSignal(
        int, str, object, dict)  # page, type, rect/points, data
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

        # Background render worker
        self._render_worker = PageRenderWorker()
        self._render_worker.page_rendered.connect(self._on_page_rendered)
        self._render_worker.start()

        # Setup UI
        self._setup_ui()

        # Render timer for debouncing
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._request_visible_pages)

    def _setup_ui(self):
        """Setup the viewer UI"""
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Container widget for pages
        self._container = QWidget()
        self._container.setAttribute(
            Qt.WidgetAttribute.WA_TransparentForMouseEvents, False)
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
        v_scrollbar = self.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.valueChanged.connect(self._on_scroll)

    def set_document(self, doc: Optional[fitz.Document], filepath: Optional[str] = None):
        """Set the document to display"""
        self._doc = doc
        self._filepath = filepath
        self._current_page = 0
        self._page_cache.clear()

        # Update render worker
        self._render_worker.clear_tasks()
        self._render_worker.set_document(doc, self._render_dpi)

        # Clear existing pages
        self._clear_pages()

        if doc and len(doc) > 0:
            # Create page widgets with placeholders
            self._create_page_widgets()

            # Calculate initial zoom
            self._update_zoom()

            # Request visible pages to be rendered
            QTimer.singleShot(50, self._request_visible_pages)

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
            page_widget = PageWidget(i, self._render_dpi, self._container)
            page_widget.clicked.connect(self._on_page_clicked)
            page_widget.annotation_created.connect(self._on_annotation_created)
            page_widget.freehand_created.connect(self._on_freehand_created)
            page_widget.hover_position.connect(self._on_hover_position)
            page_widget.set_tool_mode(
                self._tool_mode.value if self._tool_mode else "select")

            # Set initial placeholder size based on page dimensions
            page = self._doc[i]
            width = int(page.rect.width * self._zoom * self._render_dpi / 72)
            height = int(page.rect.height * self._zoom * self._render_dpi / 72)
            if self._rotation in (90, 270):
                width, height = height, width
            page_widget.set_placeholder(width, height)

            self._layout.addWidget(page_widget)
            self._page_widgets.append(page_widget)

    def _render_page(self, page_num: int) -> QPixmap:
        """Render a single page to pixmap"""
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return QPixmap()

        # Check cache
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

    def _request_visible_pages(self):
        """Request visible pages to be rendered in background"""
        if not self._doc or not self._page_widgets:
            return

        viewport_widget = self.viewport()
        v_scrollbar = self.verticalScrollBar()
        if not viewport_widget or not v_scrollbar:
            return

        viewport = viewport_widget.rect()
        scroll_pos = v_scrollbar.value()

        for i, page_widget in enumerate(self._page_widgets):
            widget_rect = page_widget.geometry()
            widget_rect.translate(0, -scroll_pos)

            # Check if visible
            if viewport.intersects(widget_rect):
                # Check cache first (only if page is not marked for re-render)
                if i in self._page_cache and not page_widget._is_loading:
                    page_widget.set_pixmap(self._page_cache[i], self._zoom)
                else:
                    # Request background render
                    # Priority based on distance from center
                    center_dist = abs(
                        widget_rect.center().y() - viewport.center().y())
                    priority = int(1000 - center_dist)
                    self._render_worker.request_page(i, self._zoom, priority)

    def _on_page_rendered(self, page_num: int, image: QImage, zoom: float):
        """Handle page rendered from background worker"""
        # Check if zoom still matches (ignore stale renders)
        if abs(zoom - self._zoom) > 0.001:
            return

        if page_num < len(self._page_widgets):
            qpixmap = QPixmap.fromImage(image)

            # Cache the pixmap
            if len(self._page_cache) >= self._cache_size:
                oldest = next(iter(self._page_cache))
                del self._page_cache[oldest]
            self._page_cache[page_num] = qpixmap

            # Update widget
            self._page_widgets[page_num].set_pixmap(qpixmap, zoom)

    def _render_all_pages(self):
        """Update all page sizes and request rendering (used when zoom changes)"""
        if not self._doc or not self._page_widgets:
            return

        # Clear cache and pending tasks
        self._page_cache.clear()
        self._render_worker.clear_tasks()

        # Update all page sizes with white placeholders
        for i, page_widget in enumerate(self._page_widgets):
            page = self._doc[i]
            # Calculate new size based on zoom
            width = int(page.rect.width * self._zoom * self._render_dpi / 72)
            height = int(page.rect.height * self._zoom * self._render_dpi / 72)

            # Apply rotation if needed
            if self._rotation in (90, 270):
                width, height = height, width

            # Set placeholder with correct size
            page_widget.set_placeholder(width, height)

        # Process events to update layout immediately
        QApplication.processEvents()

        # Request visible pages to be rendered
        self._request_visible_pages()

    def _on_scroll(self):
        """Handle scroll events"""
        self._render_timer.start(50)  # Debounce rendering
        self._update_current_page()

    def _update_current_page(self):
        """Update current page based on scroll position"""
        if not self._page_widgets:
            return

        viewport_widget = self.viewport()
        v_scrollbar = self.verticalScrollBar()
        if not viewport_widget or not v_scrollbar:
            return

        viewport_center = viewport_widget.height() / 2
        scroll_pos = v_scrollbar.value()

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

        viewport_widget = self.viewport()
        if not viewport_widget:
            return

        if self._zoom_mode == ZoomMode.FIT_WIDTH:
            viewport_width = viewport_widget.width() - 60  # Account for margins
            page = self._doc[0]
            page_width = page.rect.width * self._render_dpi / 72
            if page_width > 0:
                self._zoom = viewport_width / page_width

        elif self._zoom_mode == ZoomMode.FIT_PAGE:
            viewport = viewport_widget.rect()
            page = self._doc[0]
            page_width = page.rect.width * self._render_dpi / 72
            page_height = page.rect.height * self._render_dpi / 72

            if page_width > 0 and page_height > 0:
                zoom_w = (viewport.width() - 60) / page_width
                zoom_h = (viewport.height() - 60) / page_height
                self._zoom = min(zoom_w, zoom_h)

        elif self._zoom_mode == ZoomMode.FIT_HEIGHT:
            viewport_height = viewport_widget.height() - 60
            page = self._doc[0]
            page_height = page.rect.height * self._render_dpi / 72
            if page_height > 0:
                self._zoom = viewport_height / page_height

        self._page_cache.clear()  # Clear cache on zoom change
        self.zoom_changed.emit(self._zoom * 100)

    def _on_page_clicked(self, page_num: int, position: QPointF):
        """Handle page click"""
        self._current_page = page_num
        self.page_changed.emit(page_num)

        # Check if clicked on a sticky note annotation
        if self._doc and self._tool_mode in (ToolMode.SELECT, ToolMode.HAND):
            self._check_annotation_click(page_num, position)

    def _on_hover_position(self, page_num: int, position: QPointF):
        """Handle mouse hover to show annotation tooltips"""
        if not self._doc or page_num >= len(self._page_widgets):
            return

        page_widget = self._page_widgets[page_num]
        tooltip_text = ""

        try:
            page = self._doc[page_num]
            hover_point = fitz.Point(position.x(), position.y())

            for annot in page.annots():
                # Check if hovering over annotation bounds
                if annot.rect.contains(hover_point):
                    annot_type = annot.type[0]  # Get annotation type number

                    # Type 0 = Text annotation (sticky note)
                    if annot_type == 0:
                        content = annot.info.get("content", "")
                        if content:
                            tooltip_text = content
                            break
        except Exception:
            pass

        # Set or clear tooltip on the page widget
        if tooltip_text:
            page_widget.setToolTip(tooltip_text)
        else:
            page_widget.setToolTip("")

    def _check_annotation_click(self, page_num: int, position: QPointF):
        """Check if user clicked on an annotation and handle it"""
        if not self._doc:
            return
        try:
            page = self._doc[page_num]
            click_point = fitz.Point(position.x(), position.y())

            for annot in page.annots():
                # Check if click is within annotation bounds
                if annot.rect.contains(click_point):
                    annot_type = annot.type[0]  # Get annotation type number

                    # Type 0 = Text annotation (sticky note)
                    if annot_type == 0:
                        self._edit_sticky_note(page_num, annot)
                        return
        except Exception as e:
            print(f"Error checking annotation click: {e}")

    def _edit_sticky_note(self, page_num: int, annot):
        """Open dialog to view/edit sticky note content"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel

        # Get current note content
        current_text = annot.info.get("content", "")

        dialog = QDialog(self)
        dialog.setWindowTitle("Edit Sticky Note")
        dialog.setMinimumSize(400, 250)

        layout = QVBoxLayout(dialog)

        label = QLabel("Note content:")
        layout.addWidget(label)

        text_edit = QTextEdit()
        text_edit.setPlainText(current_text)
        text_edit.setPlaceholderText("Type your note here...")
        layout.addWidget(text_edit)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save |
            QDialogButtonBox.StandardButton.Cancel |
            QDialogButtonBox.StandardButton.Discard
        )
        discard_btn = buttons.button(QDialogButtonBox.StandardButton.Discard)
        if discard_btn:
            discard_btn.setText("Delete Note")
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)

        # Handle delete button
        delete_clicked = [False]  # Use list to modify in nested function

        def on_delete():
            delete_clicked[0] = True
            dialog.reject()

        if discard_btn:
            discard_btn.clicked.connect(on_delete)

        layout.addWidget(buttons)

        result = dialog.exec()

        if delete_clicked[0] and self._doc:
            # Delete the annotation
            page = self._doc[page_num]
            page.delete_annot(annot)
            self.document_modified.emit()
            self.refresh()
        elif result == QDialog.DialogCode.Accepted:
            # Update the annotation text
            new_text = text_edit.toPlainText().strip()
            if new_text:
                annot.set_info(content=new_text)
                annot.update()
                self.document_modified.emit()
                self.refresh()

    def _on_freehand_created(self, page_num: int, points: list):
        """Handle freehand drawing with actual tracked points"""
        if not self._doc or len(points) < 2:
            return

        # Emit signal instead of creating directly
        self.annotation_create_requested.emit(
            page_num, "ink", None, {"points": points})

    def _on_annotation_created(self, page_num: int, annot_type: str, rect: QRectF):
        """Handle annotation creation based on current tool mode"""
        if not self._doc or rect.width() < 5 or rect.height() < 5:
            return

        if self._tool_mode == ToolMode.SELECT:
            self.selection_changed.emit(page_num, rect)

        elif self._tool_mode == ToolMode.TEXT_SELECT:
            # Extract text from the selected area
            text = self._extract_text_from_rect(page_num, rect)
            if text:
                self.text_selected.emit(text)
                # Copy to clipboard
                clipboard = QApplication.clipboard()
                if clipboard:
                    clipboard.setText(text)

        elif self._tool_mode == ToolMode.HIGHLIGHT:
            self.annotation_create_requested.emit(
                page_num, "highlight", rect, {})

        elif self._tool_mode == ToolMode.UNDERLINE:
            self.annotation_create_requested.emit(
                page_num, "underline", rect, {})

        elif self._tool_mode == ToolMode.STRIKETHROUGH:
            self.annotation_create_requested.emit(
                page_num, "strikethrough", rect, {})

        elif self._tool_mode == ToolMode.TEXT_BOX:
            self.annotation_create_requested.emit(
                page_num, "text_box", rect, {})

        elif self._tool_mode == ToolMode.STICKY_NOTE:
            self.annotation_create_requested.emit(
                page_num, "sticky_note", rect, {})

        elif self._tool_mode == ToolMode.RECTANGLE:
            self.annotation_create_requested.emit(
                page_num, "rectangle", rect, {})

        elif self._tool_mode == ToolMode.CIRCLE:
            self.annotation_create_requested.emit(page_num, "circle", rect, {})

        elif self._tool_mode == ToolMode.LINE:
            self.annotation_create_requested.emit(
                page_num, "line", rect, {"arrow": False})

        elif self._tool_mode == ToolMode.ARROW:
            self.annotation_create_requested.emit(
                page_num, "line", rect, {"arrow": True})

        elif self._tool_mode == ToolMode.REDACT:
            # Redaction might be complex, but let's try
            # self.annotation_create_requested.emit(page_num, "redact", rect, {})
            self._create_redaction_annotation(page_num, rect)

        elif self._tool_mode == ToolMode.ERASER:
            self._erase_annotation_at(page_num, rect)

        # Note: FREEHAND is handled via freehand_created signal with actual points

        elif self._tool_mode == ToolMode.STAMP:
            self.annotation_create_requested.emit(page_num, "stamp", rect, {})

    def _extract_text_from_rect(self, page_num: int, rect: QRectF) -> str:
        """Extract text from a rectangular area on a page"""
        if not self._doc:
            return ""
        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(
                rect.x(), rect.y(),
                rect.x() + rect.width(),
                rect.y() + rect.height()
            )
            text = cast(str, page.get_text("text", clip=fitz_rect))
            return text.strip()
        except Exception as e:
            print(f"Error extracting text: {e}")
            return ""

    def _create_text_markup_annotation(self, page_num: int, rect: QRectF, annot_type: str):
        """Create highlight, underline, or strikethrough annotation"""
        if not self._doc:
            return
        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                  rect.x() + rect.width(),
                                  rect.y() + rect.height())

            # Get quads for text in the area
            text_dict = cast(Dict[str, Any], page.get_text("dict", clip=fitz_rect))
            quads = []

            for block in text_dict.get("blocks", []):
                if "lines" in block:
                    for line in block["lines"]:
                        for span in line.get("spans", []):
                            span_rect = fitz.Rect(span["bbox"])
                            if fitz_rect.intersects(span_rect):
                                quads.append(span_rect.quad)

            # Use the appropriate method based on annotation type
            target = quads if quads else fitz_rect
            if annot_type == "highlight":
                annot = page.add_highlight_annot(target)
            elif annot_type == "underline":
                annot = page.add_underline_annot(target)
            else:  # strikethrough
                annot = page.add_strikeout_annot(target)

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
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextEdit, QDialogButtonBox, QLabel

        # Create a custom dialog with better text editing
        dialog = QDialog(self)
        dialog.setWindowTitle(
            "Add Text Box" if free_text else "Add Sticky Note")
        dialog.setMinimumSize(400, 250)

        layout = QVBoxLayout(dialog)

        # Label
        label = QLabel(
            "Enter your text:" if free_text else "Enter note content:")
        layout.addWidget(label)

        # Text edit area
        text_edit = QTextEdit()
        text_edit.setPlaceholderText("Type your text here...")
        layout.addWidget(text_edit)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        text = text_edit.toPlainText().strip()
        if not text:
            return

        if not self._doc:
            return

        try:
            page = self._doc[page_num]
            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                  rect.x() + rect.width(),
                                  rect.y() + rect.height())

            # Get current annotation color
            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())

            if free_text:
                # Free text annotation (text box) - use selected color for text
                # Calculate appropriate font size based on rect height
                auto_fontsize = max(
                    8, min(self._font_size, int(rect.height() * 0.8)))
                annot = page.add_freetext_annot(
                    fitz_rect, text,
                    fontsize=auto_fontsize,
                    fontname="helv",
                    text_color=color,  # Use annotation color for text
                    fill_color=(1, 1, 1)  # White background
                )
                annot.set_opacity(self._annotation_opacity)
                annot.update()
            else:
                # Sticky note - just an icon that shows text on hover/click
                # This is the standard PDF sticky note behavior
                point = fitz.Point(rect.x(), rect.y())
                annot = page.add_text_annot(point, text, icon="Note")
                annot.set_colors(stroke=color)
                annot.set_opacity(self._annotation_opacity)
                annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(
                page_num, "text", {"text": text, "rect": rect})

        except Exception as e:
            print(f"Error creating text annotation: {e}")

    def _create_shape_annotation(self, page_num: int, rect: QRectF, shape: str):
        """Create rectangle or circle annotation"""
        if not self._doc:
            return
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
        if not self._doc:
            return
        try:
            page = self._doc[page_num]

            # Line from start point to end point of selection
            p1 = fitz.Point(rect.x(), rect.y())
            p2 = fitz.Point(rect.x() + rect.width(), rect.y() + rect.height())

            annot = page.add_line_annot(p1, p2)

            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())
            annot.set_colors(stroke=color)

            # Use thicker line for better visibility
            line_width = max(self._stroke_width, 2)
            annot.set_border(width=line_width)

            if arrow:
                # Set line ending to a closed arrow (more visible)
                # Line ending styles: 0=None, 1=Square, 2=Circle, 3=Diamond,
                # 4=OpenArrow, 5=ClosedArrow, 6=Butt, 7=ROpenArrow, 8=RClosedArrow, 9=Slash
                annot.set_line_ends(0, 5)  # None at start, ClosedArrow at end

                # Set interior color for filled arrow head
                annot.set_colors(stroke=color, fill=color)

            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(
                page_num, "line" if not arrow else "arrow", {"rect": rect})

        except Exception as e:
            print(f"Error creating line annotation: {e}")

    def _create_freehand_annotation_from_points(self, page_num: int, points: list):
        """Create a freehand/ink annotation from actual tracked points"""
        if not self._doc:
            return
        try:
            page = self._doc[page_num]

            # Points are already in PDF coordinates as (x, y) tuples
            # add_ink_annot expects list of strokes (each stroke is a list of point tuples)
            annot = page.add_ink_annot([points])

            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())
            annot.set_colors(stroke=color)
            annot.set_border(width=self._stroke_width)
            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(page_num, "freehand", {
                                       "points": len(points)})

        except Exception as e:
            print(f"Error creating freehand annotation: {e}")

    def _create_stamp_annotation(self, page_num: int, rect: QRectF):
        """Create a stamp annotation"""
        from PyQt6.QtWidgets import (QDialog, QVBoxLayout, QListWidget,
                                     QLineEdit, QDialogButtonBox, QGroupBox)

        # Create a custom stamp dialog
        dialog = QDialog(self)
        dialog.setWindowTitle("Add Stamp")
        dialog.setMinimumSize(350, 400)

        layout = QVBoxLayout(dialog)

        # Stamp selection group
        stamp_group = QGroupBox("Select Stamp Type")
        stamp_layout = QVBoxLayout(stamp_group)

        stamp_list = QListWidget()
        stamp_list.setStyleSheet("QListWidget::item { padding: 5px; }")
        stamps = [
            "✓ APPROVED",
            "🔒 CONFIDENTIAL",
            "📝 DRAFT",
            "✔ FINAL",
            "✗ NOT APPROVED",
            "👁 FOR REVIEW",
            "⊘ VOID",
            "📋 COPY",
            "📄 ORIGINAL",
            "⚠ URGENT",
            "📊 SAMPLE",
            "🔄 REVISED"
        ]
        for stamp in stamps:
            stamp_list.addItem(stamp)
        stamp_list.setCurrentRow(0)
        stamp_layout.addWidget(stamp_list)
        layout.addWidget(stamp_group)

        # Custom text group
        custom_group = QGroupBox("Or Enter Custom Text")
        custom_layout = QVBoxLayout(custom_group)
        custom_input = QLineEdit()
        custom_input.setPlaceholderText("Type custom stamp text here...")
        custom_layout.addWidget(custom_input)
        layout.addWidget(custom_group)

        # Buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        # Get stamp text (custom takes priority)
        stamp_text = custom_input.text().strip()
        if not stamp_text:
            current_item = stamp_list.currentItem()
            if current_item:
                # Remove emoji prefix for cleaner stamp
                stamp_text = current_item.text().split(
                    " ", 1)[-1] if " " in current_item.text() else current_item.text()
            else:
                stamp_text = "STAMP"

        if not self._doc:
            return

        try:
            page = self._doc[page_num]

            # Calculate stamp size based on text length
            char_width = 8  # Approximate character width
            text_width = len(stamp_text) * char_width + 20  # Add padding
            min_width = max(rect.width(), text_width, 100)
            min_height = max(rect.height(), 30)

            fitz_rect = fitz.Rect(rect.x(), rect.y(),
                                  rect.x() + min_width,
                                  rect.y() + min_height)

            # Use annotation color for stamp
            color = (self._annotation_color.redF(),
                     self._annotation_color.greenF(),
                     self._annotation_color.blueF())

            # Calculate font size based on stamp size
            fontsize = max(12, min(20, int(min_height * 0.6)))

            # Create outer rectangle border first (double border effect)
            outer_rect = fitz.Rect(
                fitz_rect.x0 - 2, fitz_rect.y0 - 2,
                fitz_rect.x1 + 2, fitz_rect.y1 + 2
            )
            outer_border = page.add_rect_annot(outer_rect)
            outer_border.set_colors(stroke=color)
            outer_border.set_border(width=3)
            outer_border.set_opacity(self._annotation_opacity)
            outer_border.update()

            # Create inner rectangle border
            inner_border = page.add_rect_annot(fitz_rect)
            inner_border.set_colors(stroke=color)
            inner_border.set_border(width=1)
            inner_border.set_opacity(self._annotation_opacity)
            inner_border.update()

            # Create stamp text - centered in the box
            annot = page.add_freetext_annot(
                fitz_rect, stamp_text,
                fontsize=fontsize,
                fontname="helv",
                text_color=color,
                fill_color=(1, 1, 1)  # White background
            )
            annot.set_opacity(self._annotation_opacity)
            annot.update()

            self.document_modified.emit()
            self.refresh()
            self.annotation_added.emit(
                page_num, "stamp", {"text": stamp_text, "rect": rect})

        except Exception as e:
            print(f"Error creating stamp annotation: {e}")

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

        if not self._doc:
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
        if not self._doc:
            return
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
        new_zoom = max(0.1, min(8.0, zoom / 100))
        if abs(new_zoom - self._zoom) < 0.001:
            return  # No significant change

        self._zoom = new_zoom
        self._zoom_mode = ZoomMode.CUSTOM
        self._page_cache.clear()

        # Re-render all visible pages with new zoom
        self._render_all_pages()
        self.zoom_changed.emit(self._zoom * 100)

    def zoom_in(self, factor: float = 1.25):
        """Zoom in by factor"""
        new_zoom = self._zoom * 100 * factor
        self.set_zoom(new_zoom)

    def zoom_out(self, factor: float = 1.25):
        """Zoom out by factor"""
        new_zoom = self._zoom * 100 / factor
        self.set_zoom(new_zoom)

    def fit_width(self):
        """Fit page to viewport width"""
        self._zoom_mode = ZoomMode.FIT_WIDTH
        self._page_cache.clear()
        self._update_zoom()
        self._render_all_pages()

    def fit_page(self):
        """Fit entire page in viewport"""
        self._zoom_mode = ZoomMode.FIT_PAGE
        self._page_cache.clear()
        self._update_zoom()
        self._render_all_pages()

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

        # Update cursor for all tools
        cursor_map = {
            ToolMode.HAND: Qt.CursorShape.OpenHandCursor,
            ToolMode.SELECT: Qt.CursorShape.ArrowCursor,
            ToolMode.TEXT_SELECT: Qt.CursorShape.IBeamCursor,
            ToolMode.HIGHLIGHT: Qt.CursorShape.CrossCursor,
            ToolMode.UNDERLINE: Qt.CursorShape.CrossCursor,
            ToolMode.STRIKETHROUGH: Qt.CursorShape.CrossCursor,
            ToolMode.TEXT_BOX: Qt.CursorShape.CrossCursor,
            ToolMode.STICKY_NOTE: Qt.CursorShape.CrossCursor,
            ToolMode.RECTANGLE: Qt.CursorShape.CrossCursor,
            ToolMode.CIRCLE: Qt.CursorShape.CrossCursor,
            ToolMode.LINE: Qt.CursorShape.CrossCursor,
            ToolMode.ARROW: Qt.CursorShape.CrossCursor,
            ToolMode.FREEHAND: Qt.CursorShape.CrossCursor,
            ToolMode.ERASER: Qt.CursorShape.CrossCursor,
            ToolMode.REDACT: Qt.CursorShape.CrossCursor,
            ToolMode.STAMP: Qt.CursorShape.CrossCursor,
        }
        cursor = cursor_map.get(mode, Qt.CursorShape.ArrowCursor)
        self.setCursor(cursor)

        # Set cursor and tool mode on all page widgets
        for page_widget in self._page_widgets:
            page_widget.setCursor(cursor)
            page_widget.set_tool_mode(mode.value)

    def set_annotation_color(self, color: QColor):
        """Set annotation color"""
        self._annotation_color = color

    def set_annotation_opacity(self, opacity: float):
        """Set annotation opacity (0.0 - 1.0)"""
        self._annotation_opacity = max(0.0, min(1.0, opacity))

    def set_stroke_width(self, width: int):
        """Set stroke width for drawing tools"""
        self._stroke_width = max(1, width)

    def set_font(self, family: str, size: int):
        """Set font family and size for text annotations"""
        self._font_family = family
        self._font_size = size

    def rotate_view(self, degrees: int):
        """Rotate the view"""
        self._rotation = (self._rotation + degrees) % 360
        self._render_worker.set_rotation(self._rotation)
        self._page_cache.clear()
        self._render_all_pages()

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
            if item is None:
                continue
            widget = item.widget()
            if widget:
                widget.setParent(None)
            else:
                nested_layout = item.layout()
                if nested_layout:
                    # Clear nested layout
                    while nested_layout.count():
                        sub_item = nested_layout.takeAt(0)
                        if sub_item:
                            sub_widget = sub_item.widget()
                            if sub_widget:
                                sub_widget.setParent(None)

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

        self._request_visible_pages()

    def get_selected_text(self) -> str:
        """Get currently selected text from selection rectangle"""
        if not self._doc:
            return ""

        # Get text from current page widget's selection
        if self._current_page < len(self._page_widgets):
            page_widget = self._page_widgets[self._current_page]
            if page_widget._selection_rect is not None:
                rect = page_widget._selection_rect
                # Convert widget coordinates to PDF page coordinates (72 DPI)
                scale = page_widget._zoom * page_widget._render_dpi / 72
                if scale > 0:
                    page_rect = QRectF(
                        rect.x() / scale,
                        rect.y() / scale,
                        rect.width() / scale,
                        rect.height() / scale
                    )
                    fitz_rect = fitz.Rect(
                        page_rect.x(), page_rect.y(),
                        page_rect.x() + page_rect.width(),
                        page_rect.y() + page_rect.height()
                    )
                    page = self._doc[self._current_page]
                    text = cast(str, page.get_text("text", clip=fitz_rect))
                    return text.strip()
        return ""

    def refresh(self):
        """Refresh the view - re-render pages to show annotation changes"""
        self._page_cache.clear()
        self._render_worker.clear_tasks()

        # Mark all page widgets as needing re-render
        for page_widget in self._page_widgets:
            page_widget._is_loading = True

        # Request visible pages to be rendered with high priority
        self._request_visible_pages()

        # Also do an immediate synchronous render of the current page for instant feedback
        if self._doc and 0 <= self._current_page < len(self._page_widgets):
            self._render_page_sync(self._current_page)

    def _render_page_sync(self, page_num: int):
        """Synchronously render a single page (for immediate feedback)"""
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return

        try:
            page = self._doc[page_num]
            zoom_matrix = fitz.Matrix(
                self._zoom * self._render_dpi / 72,
                self._zoom * self._render_dpi / 72
            )
            zoom_matrix = zoom_matrix.prerotate(self._rotation)

            pixmap = page.get_pixmap(matrix=zoom_matrix, alpha=False)

            # Convert to QPixmap
            img = QImage(pixmap.samples, pixmap.width, pixmap.height,
                         pixmap.stride, QImage.Format.Format_RGB888)
            qpixmap = QPixmap.fromImage(img)

            # Update cache and widget
            self._page_cache[page_num] = qpixmap
            if page_num < len(self._page_widgets):
                self._page_widgets[page_num].set_pixmap(qpixmap, self._zoom)
        except Exception as e:
            print(f"Error in sync render: {e}")

    def cleanup(self):
        """Clean up resources (call before closing)"""
        self._render_worker.stop()

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

            h_scrollbar = self.horizontalScrollBar()
            v_scrollbar = self.verticalScrollBar()
            if h_scrollbar:
                h_scrollbar.setValue(h_scrollbar.value() - delta.x())
            if v_scrollbar:
                v_scrollbar.setValue(v_scrollbar.value() - delta.y())
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
        if zoom_menu:
            zoom_menu.addAction("Zoom In", self.zoom_in)
            zoom_menu.addAction("Zoom Out", self.zoom_out)
            zoom_menu.addSeparator()
            zoom_menu.addAction("Fit Width", self.fit_width)
            zoom_menu.addAction("Fit Page", self.fit_page)
            zoom_menu.addAction("100%", lambda: self.set_zoom(100))

        menu.addSeparator()

        # Navigation
        nav_menu = menu.addMenu("Go To")
        if nav_menu:
            nav_menu.addAction("First Page", self.first_page)
            nav_menu.addAction("Previous Page", self.previous_page)
            nav_menu.addAction("Next Page", self.next_page)
            nav_menu.addAction("Last Page", self.last_page)

        menu.addSeparator()

        # Rotation
        menu.addAction("Rotate Clockwise", lambda: self.rotate_view(90))
        menu.addAction("Rotate Counter-Clockwise",
                       lambda: self.rotate_view(-90))

        menu.exec(event.globalPos())
