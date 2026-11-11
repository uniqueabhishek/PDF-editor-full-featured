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
import logging
import os
import threading
from collections import OrderedDict
from typing import Optional, List, Dict, Union, cast, Any
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Upper bound on how many pages one visibility pass may hand the render worker.
# A viewport holds only a handful of pages even zoomed fully out, so this is
# never reached in normal use; it exists so a not-yet-laid-out geometry can't
# queue an entire document and stall the UI (see _request_visible_pages).
_MAX_QUEUED_PAGE_RENDERS = 12
# Pages within this many of the viewport keep their rendered bitmap; the rest
# are released so memory stays flat however far the user scrolls.
_KEEP_RENDERED_MARGIN = 3
# Pages render this long after the last zoom step (see set_zoom).
_ZOOM_RENDER_DELAY_MS = 150
# A page bigger than this (pixels) renders only its visible part: 8 M pixels is
# ~24 MB, a fit-width page on a 4K screen; 800% zoom would be 139 M pixels.
_MAX_RENDER_PIXELS = 8_000_000


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
    # Part of the page to render, in full-page pixels (see _render_clip_for).
    clip: Optional[tuple] = None


class PageRenderWorker(QThread):
    """Background worker for rendering PDF pages.

    Renders from its OWN private copy of the document so it never touches the
    editable document the main thread reads and mutates (PyMuPDF documents are
    not thread-safe). That copy lives in a separate render process (see
    :mod:`core.render_backend`): PyMuPDF holds the GIL while it renders, so an
    in-thread render froze the window for its whole duration. If the process
    can't start, or dies, rendering falls back to this thread and
    ``copy_lost`` asks the viewer to hand over a fresh copy.

    ``_lock`` serializes every call into the backend (render vs. hand-off /
    patch / close); ``_task_cond`` guards the task queue and lets the loop
    sleep until there is work or a stop.
    """

    # page_num, image, zoom, and for a partial render (x, y, clip) giving the
    # image's offset within the page and the requested clip; None if whole.
    page_rendered = pyqtSignal(int, QImage, float, object)
    copy_lost = pyqtSignal()  # the render process died; resend the document

    def __init__(self, parent=None):
        super().__init__(parent)
        self._backend: Any = None
        self._backend_ready = threading.Event()
        self._tasks: List[RenderTask] = []
        self._render_dpi = 150
        self._rotation = 0
        self._running = True
        self._current_zoom = 1.0
        self._lock = threading.Lock()
        self._task_cond = threading.Condition()

    # ---- backend management ----

    def _start_backend(self):
        """Runs on the worker thread so spawning the process never blocks the UI."""
        from core.render_backend import InProcessRenderer, ProcessRenderer
        backend: Any = None
        if os.environ.get("ULTRA_PDF_RENDER_IN_PROCESS") != "1":
            try:
                backend = ProcessRenderer()
                backend.page_count()  # wait until the process is up
            except Exception:
                logger.exception("Render process unavailable; rendering in-thread")
                backend = None
        self._backend = backend or InProcessRenderer()
        self._backend_ready.set()

    def _ready_backend(self):
        if not self._backend_ready.wait(30):
            raise RuntimeError("render backend did not start")
        return self._backend

    def _call(self, fn_name: str, *args):
        """Call the backend under the lock; survive the render process dying."""
        from core.render_backend import InProcessRenderer, RenderProcessDied
        backend = self._ready_backend()
        try:
            return getattr(backend, fn_name)(*args)
        except RenderProcessDied:
            logger.error("Render process died; rendering in-thread from now on")
            self._backend = InProcessRenderer()
            self.copy_lost.emit()
            return None

    @property
    def uses_render_process(self) -> bool:
        from core.render_backend import ProcessRenderer
        return isinstance(self._ready_backend(), ProcessRenderer)

    def page_count(self) -> int:
        """Pages in the worker's copy (-1 when it has none)."""
        with self._lock:
            count = self._call("page_count")
        return -1 if count is None else count

    def render_samples(self, page_num: int, dpi: int) -> Optional[bytes]:
        """Raw RGB pixels of one page of the worker's copy (for checks/tests)."""
        with self._lock:
            out = self._call("render", page_num, dpi / 72, 0)
        return None if out is None else out[3]

    def set_document(self, data: Optional[Union[bytes, str]],
                     render_dpi: int = 150) -> bool:
        """Give the worker its own document copy.

        ``data`` is serialized PDF bytes, or the path of a file whose content is
        known to match the editable document (a freshly opened file). Passing
        ``None`` detaches (e.g. when the document is closed).

        Returns False if a source was given but could not be used (unreadable,
        or password-locked); the worker is then detached and the caller should
        fall back to serialized bytes.
        """
        with self._task_cond:
            self._tasks.clear()
        with self._lock:
            self._render_dpi = render_dpi
            if data is None:
                self._call("close")
                return True
            return bool(self._call("open", data))

    def patch_pages(self, src: fitz.Document, pages: List[int]) -> bool:
        """Copy just ``pages`` from the editable document into the worker's copy.

        Runs on the GUI thread (which owns ``src``). About 2 ms a page, against
        a full re-serialize that grows with file size (~0.2 s on a 36 MB scan).
        Returns False if the copies no longer line up (no copy, or page count
        differs); the caller then falls back to a full resync.
        """
        with self._task_cond:
            self._tasks = [t for t in self._tasks if t.page_num not in pages]
        with self._lock:
            return bool(self._call("patch", src, list(pages)))

    def delete_pages(self, pages: List[int], expected_before: int) -> bool:
        """Mirror a page deletion in the worker's copy (no re-serialize)."""
        with self._task_cond:
            self._tasks.clear()  # page numbers shift
        with self._lock:
            return bool(self._call("delete_pages", list(pages), expected_before))

    def insert_pages(self, src: fitz.Document, index: int, count: int) -> bool:
        """Mirror an insertion: copy ``src`` pages index..index+count-1 in."""
        with self._task_cond:
            self._tasks.clear()  # page numbers shift
        with self._lock:
            return bool(self._call("insert_pages", src, index, count))

    def set_rotation(self, rotation: int):
        """Set rotation angle"""
        with self._lock:
            self._rotation = rotation

    def request_page(self, page_num: int, zoom: float, priority: int = 0,
                     clip: Optional[tuple] = None):
        """Request a page (or the ``clip`` part of it) to be rendered"""
        with self._task_cond:
            # Remove any existing task for this page
            self._tasks = [t for t in self._tasks if t.page_num != page_num]
            self._tasks.append(RenderTask(page_num, zoom, priority, clip))
            self._current_zoom = zoom
            # Sort by priority (higher first)
            self._tasks.sort(key=lambda t: t.priority, reverse=True)
            self._task_cond.notify()  # wake the render loop

    def clear_tasks(self):
        """Clear pending tasks"""
        with self._task_cond:
            self._tasks.clear()

    def stop(self):
        """Stop the worker and release its document copy (and process)."""
        self._running = False
        with self._task_cond:
            self._task_cond.notify()  # wake the loop so it can exit promptly
        self.wait()
        if self._backend_ready.is_set():
            with self._lock:
                try:
                    self._backend.shutdown()
                except Exception:
                    logger.debug("Failed to shut down the render backend", exc_info=True)

    def run(self):
        """Main render loop"""
        self._start_backend()
        while self._running:
            task = None
            with self._task_cond:
                if not self._tasks and self._running:
                    # Sleep until a task is queued or stop() is called; the
                    # timeout is only a safety net so _running is re-checked.
                    self._task_cond.wait(0.1)
                if self._tasks:
                    task = self._tasks.pop(0)

            if task is None:
                continue

            # Skip if zoom changed (task is outdated)
            if abs(task.zoom - self._current_zoom) > 0.001:
                continue

            img = None
            with self._lock:
                try:
                    out = self._call("render", task.page_num,
                                     task.zoom * self._render_dpi / 72, self._rotation,
                                     task.clip)
                    if out is not None:
                        width, height, stride, samples, ox, oy = out
                        # Copy detaches from the samples buffer so the QImage
                        # owns its pixels.
                        img = QImage(samples, width, height, stride,
                                     QImage.Format.Format_RGB888).copy()
                except Exception:
                    logger.exception("Error rendering page %s", task.page_num)
                    img = None

            if img is not None:
                part = None if task.clip is None else (ox, oy, task.clip)
                self.page_rendered.emit(task.page_num, img, task.zoom, part)


class PageWidget(QLabel):
    """Widget representing a single PDF page"""

    clicked = pyqtSignal(int, QPointF)  # page_num, position
    annotation_created = pyqtSignal(int, str, QRectF)  # page_num, type, rect
    # page_num, list of (x, y) points in PDF coordinates
    freehand_created = pyqtSignal(int, list)
    # page_num, position in PDF coordinates (for tooltip)
    hover_position = pyqtSignal(int, QPointF)
    # page_num, selected text, list[QRectF] highlight rects (PDF coords); the
    # text is "" when a bare click clears the selection.
    text_selection_made = pyqtSignal(int, str, list)
    # Emitted when the user drags to select on a page that has no text layer
    # (e.g. an un-OCR'd scan), so the UI can hint at running OCR.
    selection_needs_text = pyqtSignal(int)
    # page_num, position in PDF coordinates — request to edit the paragraph there.
    edit_text_requested = pyqtSignal(int, QPointF)

    def __init__(self, page_num: int, render_dpi: int = 150, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._pixmap: Optional[QPixmap] = None
        # (offset QPoint, clip) when only part of the page is rendered.
        self._partial: Optional[tuple] = None
        self._zoom = 1.0
        self._render_dpi = render_dpi  # Store render DPI for coordinate conversion
        self._page_rect = QRectF()
        self._selection_start: Optional[QPointF] = None
        self._selection_rect: Optional[QRectF] = None
        self._rubber_band: Optional[QRubberBand] = None
        self._annotations: List[Dict] = []
        # Search-result rectangles in PDF coordinates (72 dpi); scaled to widget
        # pixels at paint time so they track zoom. _current_search_rect is the
        # active match, drawn in a stronger colour.
        self._search_rects: List[QRectF] = []
        self._current_search_rect: Optional[QRectF] = None
        self._is_loading = True
        self._tool_mode: Optional[str] = None  # Current tool mode
        # Points for freehand drawing
        self._freehand_points: List[QPointF] = []

        # --- word-based text selection (Text Select tool) ------------------
        # Provider returns this page's words in reading order, each a tuple
        # (x0, y0, x1, y1, "word", block_no, line_no, word_no) in PDF coords.
        self._word_provider = None
        self._sel_words: Optional[List] = None      # words snapshot for a drag
        self._text_anchor: Optional[QPointF] = None  # drag start (PDF coords)
        self._text_press_widget: Optional[QPointF] = None  # drag start (px)
        self._text_selecting = False
        # Persistent highlight rectangles (PDF coords) for the active selection.
        self._text_sel_rects: List[QRectF] = []

        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        self.setText("")  # Clear any default text
        self.setMouseTracking(True)  # Enable mouse tracking for move events

    def set_tool_mode(self, mode: str):
        """Set the current tool mode"""
        self._tool_mode = mode

    def set_search_rects(self, rects: List[QRectF],
                         current: Optional[QRectF] = None):
        """Show search-result highlights (``rects`` in PDF coordinates)."""
        self._search_rects = rects
        self._current_search_rect = current
        self.update()

    def clear_search_rects(self):
        """Remove any search-result highlights."""
        if self._search_rects or self._current_search_rect is not None:
            self._search_rects = []
            self._current_search_rect = None
            self.update()

    def set_pixmap(self, pixmap: QPixmap, zoom: float = 1.0):
        """Set the page pixmap"""
        self._partial = None
        self._pixmap = pixmap
        self._zoom = zoom
        self._is_loading = False
        self.setPixmap(pixmap)
        self.setFixedSize(pixmap.size())

    def set_partial_pixmap(self, pixmap: QPixmap, zoom: float, x: int, y: int,
                           clip: tuple):
        """Show a render of only part of the page (very high zoom).

        The widget keeps its full page size; ``pixmap`` is painted at ``(x, y)``
        and covers ``clip`` (full-page pixels), which the viewer checks to
        decide when scrolling needs a fresh part.
        """
        self._pixmap = pixmap
        self._partial = (QPoint(x, y), clip)
        self._zoom = zoom
        self._is_loading = False
        self.clear()  # QLabel would centre the pixmap; paintEvent places it
        self.update()

    def partial_covers(self, rect: tuple) -> bool:
        """True if the shown partial render covers ``rect`` (x0, y0, x1, y1)."""
        if self._partial is None or self._pixmap is None:
            return False
        cx0, cy0, cx1, cy1 = self._partial[1]
        x0, y0, x1, y1 = rect
        return cx0 <= x0 and cy0 <= y0 and cx1 >= x1 and cy1 >= y1

    def set_placeholder(self, width: int, height: int):
        """Reserve space for a not-yet-rendered page without allocating a pixmap.

        This used to fill a full-resolution white ``QPixmap`` per page (~8 MB for a
        Letter page at 150 DPI). On a large document that allocated gigabytes of
        placeholder bitmaps that are never shown once the real render arrives. The
        widget's stylesheet already paints a white background with a light border,
        so clearing the pixmap and fixing the size gives the same look at zero
        pixel cost.
        """
        self._is_loading = True
        self._pixmap = None
        self._partial = None

        # Ensure valid dimensions
        width = max(1, width)
        height = max(1, height)

        # Drop any previous pixmap; the stylesheet draws the white page + border.
        self.clear()
        self.setFixedSize(width, height)

    def release_pixmap(self):
        """Free the rendered bitmap of a page that has scrolled far off screen.

        Keeps the widget's size (so the layout does not move) and its zoom, and
        leaves ``_is_loading`` alone: a page already marked stale stays stale,
        and a fresh one may be restored from the viewer's LRU cache when it
        scrolls back. Without this every page ever viewed kept its full-size
        bitmap (~5 MB at fit-width), so scrolling a 300-page file reached 1.8 GB.
        """
        if self._pixmap is None:
            return
        self._pixmap = None
        self._partial = None
        self.clear()

    def get_page_position(self, widget_pos: QPoint) -> QPointF:
        """Convert widget position to PDF page coordinates (72 DPI)"""
        # Widget pixels are rendered at: zoom * render_dpi / 72
        # To convert back to PDF coordinates (72 DPI), divide by the full scale
        scale = self._zoom * self._render_dpi / 72
        if scale == 0:
            return QPointF(0, 0)
        return QPointF(widget_pos.x() / scale, widget_pos.y() / scale)

    @staticmethod
    def _nearest_word_index(words: List, p: QPointF) -> Optional[int]:
        """Index of the word nearest point ``p`` (PDF coords), caret-style.

        Distance to a word's box is the point-to-rectangle distance with the
        vertical component weighted heavier, so the result prefers a word on the
        row the pointer is on (mimicking a text caret) rather than the nearest
        word on an adjacent line.
        """
        if not words:
            return None
        px, py = p.x(), p.y()
        best_i = None
        best_d = None
        for i, w in enumerate(words):
            x0, y0, x1, y1 = w[0], w[1], w[2], w[3]
            dx = max(x0 - px, 0.0, px - x1)
            dy = max(y0 - py, 0.0, py - y1)
            d = dy * 3.0 + dx
            if best_d is None or d < best_d:
                best_d = d
                best_i = i
        return best_i

    def _selection_for(self, a: Optional[QPointF], b: Optional[QPointF]):
        """Return (highlight rects in PDF coords, selected text) for a drag.

        Selects every word between the words nearest ``a`` and ``b`` in reading
        order, grouped per text line so the highlight spans whole lines in the
        middle and partial lines at the ends — like a normal text selection.
        """
        words = self._sel_words or []
        if not words or a is None or b is None:
            return [], ""
        ia = self._nearest_word_index(words, a)
        ib = self._nearest_word_index(words, b)
        if ia is None or ib is None:
            return [], ""
        lo, hi = (ia, ib) if ia <= ib else (ib, ia)
        selected = words[lo:hi + 1]

        # Group consecutive words that share a (block, line) into lines.
        groups: List = []
        for w in selected:
            key = (w[5], w[6])
            if groups and groups[-1][0] == key:
                groups[-1][1].append(w)
            else:
                groups.append((key, [w]))

        rects: List[QRectF] = []
        lines: List[str] = []
        for _key, line_words in groups:
            r = QRectF(line_words[0][0], line_words[0][1],
                       line_words[0][2] - line_words[0][0],
                       line_words[0][3] - line_words[0][1])
            for w in line_words[1:]:
                r = r.united(QRectF(w[0], w[1], w[2] - w[0], w[3] - w[1]))
            rects.append(r)
            lines.append(" ".join(w[4] for w in line_words))
        return rects, "\n".join(lines)

    def clear_text_selection(self):
        """Drop the current text-selection highlight (no signal emitted)."""
        if self._text_sel_rects or self._text_selecting:
            self._text_sel_rects = []
            self._text_selecting = False
            self._text_anchor = None
            self.update()

    def mouseDoubleClickEvent(self, event: QMouseEvent):
        # In the Text tool, double-clicking a paragraph opens it for editing
        # (the same tool handles drag-to-select and double-click-to-edit).
        if (event.button() == Qt.MouseButton.LeftButton
                and self._tool_mode == ToolMode.TEXT_SELECT.value):
            self.edit_text_requested.emit(
                self.page_num, self.get_page_position(event.pos()))
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def mousePressEvent(self, event: QMouseEvent):
        if event.button() == Qt.MouseButton.LeftButton:
            if self._tool_mode == ToolMode.TEXT_SELECT.value:
                # Begin a word-based text selection. Snapshot the page's words
                # once for the duration of the drag.
                self._text_selecting = True
                self._text_press_widget = event.position()
                self._text_anchor = self.get_page_position(event.pos())
                self._sel_words = (
                    self._word_provider(self.page_num)
                    if self._word_provider else [])
                self._text_sel_rects = []
                self.update()
                self.clicked.emit(
                    self.page_num, self.get_page_position(event.pos()))
                event.accept()
                return
            self._selection_start = event.position()
            # Start collecting freehand points
            self._freehand_points = [event.position()]
            self.clicked.emit(
                self.page_num, self.get_page_position(event.pos()))
            event.accept()  # Accept the event to receive move/release events
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._text_selecting:
            current = self.get_page_position(event.pos())
            rects, _ = self._selection_for(self._text_anchor, current)
            self._text_sel_rects = rects
            self.update()
            event.accept()
            return
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
        if self._text_selecting:
            self._text_selecting = False
            moved = (
                (event.position() - self._text_press_widget).manhattanLength()
                if self._text_press_widget is not None else 0)
            if moved < 3:
                # A bare click clears the current selection.
                self._text_sel_rects = []
                self.update()
                self.text_selection_made.emit(self.page_num, "", [])
                event.accept()
                return
            current = self.get_page_position(event.pos())
            rects, text = self._selection_for(self._text_anchor, current)
            self._text_sel_rects = rects
            self.update()
            self.text_selection_made.emit(self.page_num, text, list(rects))
            if not text and not self._sel_words:
                # Real drag but the page has no extractable text (a scan).
                self.selection_needs_text.emit(self.page_num)
            event.accept()
            return
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
        if self._partial is not None and self._pixmap is not None:
            painter.drawPixmap(self._partial[0], self._pixmap)

        # Draw search-result highlights underneath any active tool overlay.
        if self._search_rects:
            scale = self._zoom * self._render_dpi / 72
            for r in self._search_rects:
                wr = QRectF(r.x() * scale, r.y() * scale,
                            r.width() * scale, r.height() * scale)
                if self._current_search_rect is not None and r == self._current_search_rect:
                    painter.fillRect(wr, QColor(255, 140, 0, 120))
                    painter.setPen(QPen(QColor(220, 110, 0), 1))
                    painter.setBrush(Qt.BrushStyle.NoBrush)
                    painter.drawRect(wr)
                else:
                    painter.fillRect(wr, QColor(255, 230, 0, 90))

        # Draw the word-based text selection highlight (translucent blue).
        if self._text_sel_rects:
            scale = self._zoom * self._render_dpi / 72
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(QColor(0, 120, 215, 70)))
            for r in self._text_sel_rects:
                wr = QRectF(r.x() * scale, r.y() * scale,
                            r.width() * scale, r.height() * scale)
                painter.drawRect(wr)

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
    selection_copied = pyqtSignal(int)  # number of characters copied
    selection_needs_ocr = pyqtSignal()  # dragged on a page with no text layer
    # page_num, bbox (PDF coords tuple), new_text, style dict — a committed edit.
    edit_text_committed = pyqtSignal(int, tuple, str, dict)
    edit_text_unavailable = pyqtSignal(int)  # double-clicked where there's no text

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
        # LRU cache keyed by page number; most-recently-used at the end.
        self._page_cache: "OrderedDict[int, QPixmap]" = OrderedDict()
        # Pages whose widget currently holds a bitmap (see _release_offscreen_pixmaps).
        self._shown_pages: set = set()
        # Page rects the current widgets were built for (see set_document reuse).
        self._page_rects: List[tuple] = []
        self._cache_size = 10

        # Search highlighting: results from PDFDocument.search_text plus the
        # active match (page_num, QRectF in PDF coords).
        self._search_results: List[Dict] = []
        self._current_result: Optional[tuple] = None

        # Tool state — Text Select is the default cursor tool (Acrobat-style).
        self._tool_mode = ToolMode.TEXT_SELECT
        self._tool_cursor = Qt.CursorShape.IBeamCursor
        # Per-page word boxes cache (PDF coords), filled lazily for selection.
        self._page_words_cache: Dict[int, List] = {}
        # Active text selection as (page_num, text), or None.
        self._text_selection: Optional[tuple] = None
        # Inline "Edit Text" state: a provider that finds the paragraph under a
        # point, the live editor overlay, and its context.
        self._text_block_provider = None
        self._inline_editor = None
        self._edit_ctx: Optional[dict] = None
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
        # The render process died: hand the in-thread fallback a fresh copy.
        # Queued, because copy_lost is emitted while the worker lock is held.
        self._render_worker.copy_lost.connect(
            self._resync_render_worker, Qt.ConnectionType.QueuedConnection)
        self._render_worker.start()

        # Setup UI
        self._setup_ui()

        # Render timer for debouncing
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._request_visible_pages)
        # Zoom steps (Ctrl+wheel, Ctrl+/-) resize the pages at once but only
        # render once the zooming pauses; each notch used to render every
        # visible page at a zoom level that was thrown away a moment later.
        self._zoom_render_timer = QTimer()
        self._zoom_render_timer.setSingleShot(True)
        self._zoom_render_timer.setInterval(_ZOOM_RENDER_DELAY_MS)
        self._zoom_render_timer.timeout.connect(self._request_visible_pages)

        # Debounce timer for re-serializing the document for the render worker.
        # Re-serializing the whole document after every edit is expensive on
        # large PDFs, so a burst of edits collapses into a single re-copy.
        self._resync_timer = QTimer()
        self._resync_timer.setSingleShot(True)
        self._resync_timer.timeout.connect(self._resync_render_worker)

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

    def set_document(self, doc: Optional[fitz.Document], filepath: Optional[str] = None,
                     render_source: Optional[Union[bytes, str]] = None,
                     reuse_layout: bool = False, keep_images: bool = False):
        """Set the document to display.

        ``keep_images`` (with ``reuse_layout``) is for re-attaching a document
        whose content did not change, e.g. after a save: the pages on screen
        and the page cache stay valid, so nothing is re-rendered.

        ``render_source`` lets the caller hand the render worker a copy it
        already has instead of re-serializing the whole document: the path of a
        file just opened unchanged, or the snapshot bytes a document was just
        restored from / saved into. It must match ``doc`` exactly. If it can't
        be used (e.g. password-locked) the document is serialized as before.

        ``reuse_layout`` is for reloading the *same* document after an edit
        (snapshot op, undo/redo). If the page count and every page size are
        unchanged, the existing page widgets are kept and only re-rendered,
        and the scroll position stays put. Rebuilding them cost ~1 s on a
        300-page file. Any difference falls back to a full rebuild.
        """
        reuse = (reuse_layout and doc is not None and not doc.is_closed
                 and bool(self._page_widgets)
                 and len(doc) == len(self._page_widgets)
                 and self._page_rects == self._doc_page_rects(doc))

        self._doc = doc
        self._filepath = filepath
        if not reuse:
            self._current_page = 0
        if not (reuse and keep_images):
            self._page_cache.clear()
            # Drop highlights from the previous document.
            self._search_results = []
            self._current_result = None
            # Drop any cached word boxes / text selection from the previous document.
            self._page_words_cache.clear()
            self._text_selection = None
        # Cancel any debounced re-serialize queued for the previous document.
        self._resync_timer.stop()

        # Hand the render worker its own private copy (see PageRenderWorker) so
        # the background thread never touches this editable document.
        self._render_worker.clear_tasks()
        if doc is None or render_source is None or not self._render_worker.set_document(
                render_source, self._render_dpi):
            self._render_worker.set_document(self._render_source(doc), self._render_dpi)

        if reuse and keep_images:
            self._teardown_inline_editor()
            return

        if reuse:
            self._teardown_inline_editor()
            for page_widget in self._page_widgets:
                page_widget.clear_text_selection()
                page_widget.clear_search_rects()
                # Keep showing the old bitmap until the fresh render lands
                # (no blank flash), but never restore it from cache.
                page_widget._is_loading = True
            if 0 <= self._current_page < len(self._page_widgets):
                self._render_page_sync(self._current_page)
            QTimer.singleShot(0, self._request_visible_pages)
            return

        # Clear existing pages
        self._clear_pages()

        if doc and len(doc) > 0:
            # Create page widgets with placeholders
            self._create_page_widgets()

            # Calculate initial zoom
            self._update_zoom()

            # Request visible pages to be rendered
            QTimer.singleShot(50, self._request_visible_pages)

    @staticmethod
    def _doc_page_rects(doc: fitz.Document) -> List[tuple]:
        """Every page's on-screen rect (rotation applied), to compare layouts."""
        return [tuple(doc[i].rect) for i in range(len(doc))]

    def release_render_copy(self):
        """Close the render worker's copy (it may hold the file open)."""
        self._resync_timer.stop()
        self._render_worker.set_document(None)

    def detach_document(self):
        """Let go of the document without destroying the page widgets.

        Used before an undo/redo swaps the document object, so nothing touches
        the old one once it is closed, while the widgets stay for
        ``set_document(..., reuse_layout=True)`` to pick up again.
        """
        self._teardown_inline_editor()
        self._doc = None
        self._resync_timer.stop()
        self._render_timer.stop()
        self._render_worker.clear_tasks()

    def _render_source(self, doc: Optional[fitz.Document]) -> Optional[bytes]:
        """Serialize the document to PDF bytes for the render worker's copy.

        Encryption is dropped in this transient, in-memory copy so the worker
        can render without a password; the bytes never touch disk. Returns None
        if there is no document or serialization fails (the worker then renders
        nothing and the main-thread sync render still shows the current page).

        ``deflate=False``: the copy lives only in memory and is fed straight to
        ``fitz.open(stream=...)``, so compressing it buys nothing and re-deflating
        every stream is the dominant cost of each per-edit resync on large PDFs.
        """
        if doc is None:
            return None
        try:
            return doc.tobytes(garbage=0, deflate=False,
                               encryption=fitz.PDF_ENCRYPT_NONE)
        except Exception:
            logger.exception("Could not serialize document for the render worker")
            return None

    def _schedule_worker_resync(self, delay_ms: int = 350):
        """Debounce re-serializing the document for the background render worker.

        ``doc.tobytes()`` over the whole document is the dominant per-edit cost
        on large PDFs. Callers render the current page synchronously for instant
        feedback, so the worker's copy can be refreshed lazily — a burst of edits
        then costs a single serialize once the user pauses.
        """
        self._resync_timer.start(delay_ms)

    def _doc_live(self) -> bool:
        """True if a document is open and not yet closed.

        ``not self._doc`` / ``if self._doc`` call ``fitz.Document.__len__``, which
        raises 'document closed' on a closed document — which can happen when a
        queued timer (render/scroll/thumbnail) fires after the document was closed
        or swapped. Guard with this instead of relying on truthiness.
        """
        return self._doc is not None and not self._doc.is_closed

    def _resync_render_worker(self):
        """Hand the worker a fresh copy of the (mutated) document, then re-render."""
        if not self._doc_live():
            return
        self._render_worker.set_document(
            self._render_source(self._doc), self._render_dpi)
        self._request_visible_pages()

    def invalidate_render_copy(self, page_num: int = -1):
        """Refresh the worker's document copy after an in-place edit.

        Renders the given page synchronously from the editable document for
        instant feedback, then patches just that page into the worker's copy.
        Only when the page is unknown or the patch fails does it fall back to a
        debounced full re-serialize (which also re-requests the visible pages).
        """
        if 0 <= page_num < len(self._page_widgets):
            self._page_cache.pop(page_num, None)
            self._page_words_cache.pop(page_num, None)
            self._render_page_sync(page_num)
            if self._patch_render_copy([page_num]):
                return
        else:
            self._page_words_cache.clear()
        self._schedule_worker_resync()

    def _patch_render_copy(self, pages: List[int]) -> bool:
        """Patch ``pages`` into the worker's copy; False means do a full resync.

        Skipped while a full resync is already pending: the worker's copy is
        then older than the last edit, so patching one page would not bring it
        up to date — the pending resync will.
        """
        if not self._doc_live() or self._resync_timer.isActive():
            return False
        if not self._render_worker.patch_pages(self._doc, pages):
            return False
        self._request_visible_pages()
        return True

    def _clear_pages(self):
        """Clear all page widgets"""
        # The inline editor is parented to a page widget about to be destroyed.
        self._teardown_inline_editor()
        for widget in self._page_widgets:
            widget.setParent(None)
            widget.deleteLater()
        self._page_widgets.clear()
        self._shown_pages.clear()
        self._page_rects = []

    def _create_page_widgets(self):
        """Create widgets for all pages"""
        if not self._doc:
            return

        self._page_rects = self._doc_page_rects(self._doc)
        for i in range(len(self._doc)):
            page_widget = self._make_page_widget(i)
            self._layout.addWidget(page_widget)
            self._page_widgets.append(page_widget)

    def _make_page_widget(self, i: int) -> "PageWidget":
        page_widget = PageWidget(i, self._render_dpi, self._container)
        page_widget.clicked.connect(self._on_page_clicked)
        page_widget.annotation_created.connect(self._on_annotation_created)
        page_widget.freehand_created.connect(self._on_freehand_created)
        page_widget.hover_position.connect(self._on_hover_position)
        page_widget.text_selection_made.connect(self._on_text_selection_made)
        page_widget.selection_needs_text.connect(
            lambda _p: self.selection_needs_ocr.emit())
        page_widget.edit_text_requested.connect(self._on_edit_text_requested)
        page_widget._word_provider = self.get_page_words
        page_widget.set_tool_mode(
            self._tool_mode.value if self._tool_mode else "select")
        page_widget.setCursor(self._tool_cursor)
        # Set initial placeholder size based on page dimensions
        width, height = self._page_pixel_size(i)
        page_widget.set_placeholder(width, height)
        return page_widget

    # ---- page structure edits, applied without rebuilding the view ----
    # Deleting / inserting / rotating a page used to reload the viewer: a
    # re-serialize for the render worker plus every page widget rebuilt,
    # 0.3-0.6 s each, and the view jumped back to page 1.

    def _after_structure_change(self):
        self._teardown_inline_editor()
        self._page_cache.clear()
        self._page_words_cache.clear()
        self._text_selection = None
        self._search_results = []
        self._current_result = None
        for i, w in enumerate(self._page_widgets):
            w.page_num = i
            w.clear_text_selection()
            w.clear_search_rects()
        self._page_rects = self._doc_page_rects(self._doc)
        self._current_page = min(self._current_page, len(self._page_widgets) - 1)
        self._layout.activate()
        QTimer.singleShot(0, self._request_visible_pages)

    def pages_inserted(self, index: int, count: int = 1):
        """``count`` pages were inserted into the document at ``index``."""
        if not self._doc_live() or not self._page_widgets:
            return
        if not self._render_worker.insert_pages(self._doc, index, count):
            self._schedule_worker_resync()
        for k in range(count):
            w = self._make_page_widget(index + k)
            self._layout.insertWidget(index + k, w)
            self._page_widgets.insert(index + k, w)
        self._shown_pages = {p + count if p >= index else p for p in self._shown_pages}
        self._after_structure_change()

    def pages_removed(self, pages: List[int]):
        """``pages`` (indices before the removal) were deleted."""
        if not self._doc_live() or not self._page_widgets:
            return
        gone = sorted(set(pages))
        if not self._render_worker.delete_pages(gone, len(self._page_widgets)):
            self._schedule_worker_resync()
        for p in reversed(gone):
            w = self._page_widgets.pop(p)
            w.setParent(None)
            w.deleteLater()
        self._shown_pages = {p - sum(1 for g in gone if g < p)
                             for p in self._shown_pages if p not in gone}
        self._after_structure_change()

    def page_resized(self, page_num: int):
        """A page's size or rotation changed in place (e.g. rotate page)."""
        if not self._doc_live() or not 0 <= page_num < len(self._page_widgets):
            return
        self._page_rects[page_num] = tuple(self._doc[page_num].rect)
        self._page_cache.pop(page_num, None)
        self._page_words_cache.pop(page_num, None)
        self._page_widgets[page_num].set_placeholder(*self._page_pixel_size(page_num))
        self._layout.activate()
        if not self._patch_render_copy([page_num]):
            self._schedule_worker_resync()

    def _page_pixel_size(self, page_num: int) -> tuple:
        """On-screen size of a page in device pixels at the current zoom.

        Single source of truth for the placeholder sizes and for
        :meth:`_visible_page_indices`, so predicted page positions always agree
        with the sizes the layout is given.
        """
        page = self._doc[page_num]
        scale = self._zoom * self._render_dpi / 72
        width = int(page.rect.width * scale)
        height = int(page.rect.height * scale)
        if self._rotation in (90, 270):
            width, height = height, width
        return width, height

    def _visible_page_indices(self) -> List[int]:
        """Indices of the pages intersecting the viewport, in view order.

        Derived from the page sizes and the layout's own margins/spacing rather
        than from each widget's ``geometry()``. Widget geometry is only valid
        once the scroll area has sized its container and run the layout, which
        happens a turn of the event loop *after* set_document() — before that
        every widget still reports the same position, so a geometry-based test
        reports the whole document as visible and queues every page for
        rendering (a multi-second freeze on a long scan). Computing the
        positions ourselves makes visibility correct on the very first pass.
        """
        viewport_widget = self.viewport()
        v_scrollbar = self.verticalScrollBar()
        if viewport_widget is None or v_scrollbar is None:
            return []

        margins = self._layout.contentsMargins()
        spacing = self._layout.spacing()
        top = v_scrollbar.value()
        bottom = top + viewport_widget.height()

        visible: List[int] = []
        y = margins.top()
        for i in range(len(self._page_widgets)):
            height = self._page_pixel_size(i)[1]
            # Pages stack top-to-bottom, so once one starts past the viewport
            # every later page is off-screen too.
            if y > bottom:
                break
            if y + height >= top:
                visible.append(i)
            y += height + spacing
        return visible

    def _cache_get(self, page_num: int) -> Optional[QPixmap]:
        """Return a cached pixmap, marking it most-recently-used (true LRU)."""
        pixmap = self._page_cache.get(page_num)
        if pixmap is not None:
            self._page_cache.move_to_end(page_num)
        return pixmap

    def _cache_put(self, page_num: int, pixmap: QPixmap) -> None:
        """Insert a pixmap as most-recently-used, evicting the LRU entry."""
        self._page_cache[page_num] = pixmap
        self._page_cache.move_to_end(page_num)
        while len(self._page_cache) > self._cache_size:
            # popitem(last=False) drops the least-recently-used entry.
            self._page_cache.popitem(last=False)

    def _render_page(self, page_num: int) -> QPixmap:
        """Render a single page to pixmap"""
        if not self._doc_live() or page_num < 0 or page_num >= len(self._doc):
            return QPixmap()

        # Check cache
        cached = self._cache_get(page_num)
        if cached is not None:
            return cached

        page = self._doc[page_num]
        zoom_matrix = fitz.Matrix(self._zoom * self._render_dpi / 72,
                                  self._zoom * self._render_dpi / 72)
        zoom_matrix = zoom_matrix.prerotate(self._rotation)

        pixmap = page.get_pixmap(matrix=zoom_matrix, alpha=False)

        # Convert to QPixmap
        img = QImage(pixmap.samples, pixmap.width, pixmap.height,
                     pixmap.stride, QImage.Format.Format_RGB888)
        qpixmap = QPixmap.fromImage(img)

        self._cache_put(page_num, qpixmap)
        return qpixmap

    def _request_visible_pages(self):
        """Request visible pages to be rendered in background"""
        if not self._doc_live() or not self._page_widgets:
            return
        # Mid-zoom (the scroll debounce also fires as pages resize): wait for
        # the zoom debounce, which renders the final zoom level.
        if self._zoom_render_timer.isActive():
            return

        visible = self._visible_page_indices()
        if not visible:
            return

        self._release_offscreen_pixmaps(visible)

        # Render outwards from the middle of the screen: the page the user is
        # looking at should arrive first.
        center = visible[len(visible) // 2]

        queued = 0
        for i in visible:
            page_widget = self._page_widgets[i]

            # Too big to render whole (very high zoom): render the visible part
            # only, and again only once scrolling leaves the part already shown.
            region = self._render_clip_for(i)
            if region is not None:
                clip, seen = region
                if not page_widget._is_loading and page_widget.partial_covers(seen):
                    continue
                if queued >= _MAX_QUEUED_PAGE_RENDERS:
                    break
                self._render_worker.request_page(
                    i, self._zoom, priority=1000 - abs(i - center), clip=clip)
                queued += 1
                continue

            # Check cache first (only if page is not marked for re-render)
            cached = None if page_widget._is_loading else self._cache_get(i)
            if cached is not None:
                page_widget.set_pixmap(cached, self._zoom)
                self._shown_pages.add(i)
                continue

            # Backstop: never hand the worker more than a screenful at once, so
            # a single pass can't queue an entire document however the visible
            # range was computed. Anything dropped here is picked up by the next
            # scroll/zoom pass.
            if queued >= _MAX_QUEUED_PAGE_RENDERS:
                logger.debug(
                    "Capped page-render queue at %d; deferring page %d onwards",
                    _MAX_QUEUED_PAGE_RENDERS, i)
                break

            # Priority by distance from the centre page (higher renders first).
            self._render_worker.request_page(
                i, self._zoom, priority=1000 - abs(i - center))
            queued += 1

    def _release_offscreen_pixmaps(self, visible: List[int]) -> None:
        """Drop bitmaps of pages more than a few pages away from the viewport.

        Pages just outside the view keep theirs so short scrolls stay instant;
        released pages come back from the LRU cache or a fresh render.
        """
        lo = visible[0] - _KEEP_RENDERED_MARGIN
        hi = visible[-1] + _KEEP_RENDERED_MARGIN
        for i in [p for p in self._shown_pages if p < lo or p > hi]:
            if i < len(self._page_widgets):
                self._page_widgets[i].release_pixmap()
            self._shown_pages.discard(i)

    def _render_clip_for(self, page_num: int) -> Optional[tuple]:
        """``(clip, visible)`` for a page too large to render whole, else None.

        Both are ``(x0, y0, x1, y1)`` in the page widget's pixels: ``visible``
        is the part on screen, ``clip`` that part plus half a viewport around
        it, so short scrolls need no new render. Without this cap a page at
        800% was a 9917x14034 bitmap, 531 MB, several of them cached.
        """
        width, height = self._page_pixel_size(page_num)
        if width * height <= _MAX_RENDER_PIXELS:
            return None
        viewport = self.viewport()
        if viewport is None:
            return None
        geo = self._page_widgets[page_num].geometry()
        h_bar, v_bar = self.horizontalScrollBar(), self.verticalScrollBar()
        sx = h_bar.value() if h_bar else 0
        sy = v_bar.value() if v_bar else 0
        vw, vh = viewport.width(), viewport.height()
        x0 = max(0, sx - geo.x())
        y0 = max(0, sy - geo.y())
        x1 = min(width, sx + vw - geo.x())
        y1 = min(height, sy + vh - geo.y())
        if x1 <= x0 or y1 <= y0:  # not actually on screen yet
            x0, y0, x1, y1 = 0, 0, min(width, vw), min(height, vh)
        mx, my = vw // 2, vh // 2
        clip = (max(0, x0 - mx), max(0, y0 - my),
                min(width, x1 + mx), min(height, y1 + my))
        return clip, (x0, y0, x1, y1)

    def _on_page_rendered(self, page_num: int, image: QImage, zoom: float,
                          part: Optional[tuple] = None):
        """Handle page rendered from background worker"""
        # Check if zoom still matches (ignore stale renders)
        if abs(zoom - self._zoom) > 0.001:
            return

        if page_num < len(self._page_widgets) and part is not None:
            # Partial renders of huge pages are never cached.
            x, y, clip = part
            self._page_widgets[page_num].set_partial_pixmap(
                QPixmap.fromImage(image), zoom, x, y, clip)
            self._shown_pages.add(page_num)
            return

        if page_num < len(self._page_widgets):
            qpixmap = QPixmap.fromImage(image)
            self._cache_put(page_num, qpixmap)

            # Update widget
            self._page_widgets[page_num].set_pixmap(qpixmap, zoom)
            self._shown_pages.add(page_num)

    def _render_all_pages(self, defer_render: bool = False):
        """Update all page sizes and request rendering (used when zoom changes).

        ``defer_render`` (zoom steps) starts the zoom debounce instead of
        rendering now, so a burst of steps renders only the final zoom.
        """
        if not self._doc_live() or not self._page_widgets:
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

        # Recompute the layout so the new page sizes are reflected in each
        # widget's geometry before _request_visible_pages() tests visibility
        # against it. This used to spin QApplication.processEvents(), which does
        # the same job only as a side effect while also re-entering the event
        # loop mid-render; activate() is synchronous and side-effect free.
        self._layout.activate()

        if defer_render:
            self._zoom_render_timer.start()
            return
        self._zoom_render_timer.stop()
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
            # Pages are ordered top-to-bottom: once one starts past the viewport
            # centre, no later page can straddle the centre either — stop here.
            if widget_rect.top() - scroll_pos > viewport_center:
                break
            widget_center = widget_rect.center().y() - scroll_pos
            if abs(widget_center - viewport_center) < widget_rect.height() / 2:
                if i != self._current_page:
                    self._current_page = i
                    self.page_changed.emit(i)
                break

    def _update_zoom(self):
        """Update zoom level based on zoom mode"""
        if not self._doc_live() or not self._page_widgets:
            return

        # A zoom/resize would leave the inline editor misaligned; finish it first.
        self._close_inline_editor(commit=True)

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
        # `not self._doc` would call fitz.Document.__len__ (-> page_count),
        # which raises ValueError on a closed document; test identity instead.
        if self._doc is None or page_num >= len(self._page_widgets):
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
        except Exception:
            logger.exception("Error checking annotation click")

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

    def _style_data(self) -> Dict[str, Any]:
        """Current annotation style (color/opacity/width/font) from the toolbar.

        Threaded into every ``annotation_create_requested`` so the command that
        actually creates the annotation applies the user's chosen style instead
        of falling back to hard-coded defaults.
        """
        return {
            "color": (
                self._annotation_color.redF(),
                self._annotation_color.greenF(),
                self._annotation_color.blueF(),
            ),
            "opacity": self._annotation_opacity,
            "width": self._stroke_width,
            "font_size": self._font_size,
            "font_family": self._font_family,
        }

    def _request_annotation(self, page_num: int, annot_type: str,
                            rect, extra: Optional[Dict[str, Any]] = None):
        """Emit an annotation-creation request with the current style merged in."""
        data = self._style_data()
        if extra:
            data.update(extra)
        self.annotation_create_requested.emit(page_num, annot_type, rect, data)

    def _on_freehand_created(self, page_num: int, points: list):
        """Handle freehand drawing with actual tracked points"""
        if not self._doc or len(points) < 2:
            return

        # Emit signal instead of creating directly
        self._request_annotation(page_num, "ink", None, {"points": points})

    def _on_annotation_created(self, page_num: int, annot_type: str, rect: QRectF):
        """Handle annotation creation based on current tool mode"""
        # Reject accidental clicks (near-zero drag), but allow thin selections so
        # that horizontal/vertical lines and arrows (height or width ~0) still work.
        if not self._doc:
            return
        drag_distance = (rect.width() ** 2 + rect.height() ** 2) ** 0.5
        if drag_distance < 5:
            return

        if self._tool_mode == ToolMode.SELECT:
            self.selection_changed.emit(page_num, rect)

        # Text Select is handled directly in PageWidget (word-based selection),
        # so it never reaches this rubber-band path.

        elif self._tool_mode == ToolMode.HIGHLIGHT:
            self._request_annotation(page_num, "highlight", rect)

        elif self._tool_mode == ToolMode.UNDERLINE:
            self._request_annotation(page_num, "underline", rect)

        elif self._tool_mode == ToolMode.STRIKETHROUGH:
            self._request_annotation(page_num, "strikethrough", rect)

        elif self._tool_mode == ToolMode.TEXT_BOX:
            self._create_text_annotation(page_num, rect, free_text=True)

        elif self._tool_mode == ToolMode.STICKY_NOTE:
            self._create_text_annotation(page_num, rect, free_text=False)

        elif self._tool_mode == ToolMode.RECTANGLE:
            self._request_annotation(page_num, "rectangle", rect)

        elif self._tool_mode == ToolMode.CIRCLE:
            self._request_annotation(page_num, "circle", rect)

        elif self._tool_mode == ToolMode.LINE:
            self._request_annotation(page_num, "line", rect, {"arrow": False})

        elif self._tool_mode == ToolMode.ARROW:
            self._request_annotation(page_num, "line", rect, {"arrow": True})

        elif self._tool_mode == ToolMode.REDACT:
            self._request_annotation(page_num, "redact", rect)

        elif self._tool_mode == ToolMode.ERASER:
            self._erase_annotation_at(page_num, rect)

        # Note: FREEHAND is handled via freehand_created signal with actual points

        elif self._tool_mode == ToolMode.STAMP:
            self._create_stamp_annotation(page_num, rect)

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
        except Exception:
            logger.exception("Error extracting text")
            return ""

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

        # Emit signal to create annotation through history manager (enables undo)
        annot_type = "text_box" if free_text else "sticky_note"
        self._request_annotation(page_num, annot_type, rect, {"text": text})

    def _create_stamp_annotation(self, page_num: int, rect: QRectF):
        """Create a stamp annotation with user-selected stamp type"""
        from PyQt6.QtWidgets import QDialog, QVBoxLayout, QComboBox, QDialogButtonBox, QLabel

        # Available stamp types
        stamp_types = [
            (0, "Approved"),
            (1, "As Is"),
            (2, "Confidential"),
            (3, "Departmental"),
            (4, "Draft"),
            (5, "Experimental"),
            (6, "Expired"),
            (7, "Final"),
            (8, "For Comment"),
            (9, "For Public Release"),
            (10, "Not Approved"),
            (11, "Not For Public Release"),
            (12, "Sold"),
            (13, "Top Secret"),
        ]

        dialog = QDialog(self)
        dialog.setWindowTitle("Select Stamp Type")
        dialog.setMinimumWidth(300)

        layout = QVBoxLayout(dialog)

        label = QLabel("Choose a stamp type:")
        layout.addWidget(label)

        combo = QComboBox()
        for stamp_id, stamp_name in stamp_types:
            combo.addItem(stamp_name, userData=stamp_id)
        layout.addWidget(combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)

        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        stamp_id = combo.currentData()
        if stamp_id is None:
            stamp_id = combo.currentIndex()  # Fallback to index if userData not retrieved

        # Emit signal to create stamp through history manager (enables undo)
        self._request_annotation(page_num, "stamp", rect, {"stamp_id": stamp_id})

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

        except Exception:
            logger.exception("Error erasing annotation")

    # ==================== Public Interface ====================

    def get_current_page(self) -> int:
        """Get current page number (0-indexed)"""
        return self._current_page

    def get_page_count(self) -> int:
        """Get total page count"""
        return len(self._doc) if self._doc_live() else 0

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

        # Resize now; render once the zooming pauses.
        self._render_all_pages(defer_render=True)
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

    def set_search_results(self, results: List[Dict]):
        """Highlight search results across pages.

        ``results`` is the list from ``PDFDocument.search_text``: dicts of
        ``{"page": int, "rects": [(x0, y0, x1, y1), ...]}`` in PDF coordinates.
        """
        self._search_results = results or []
        self._current_result = None
        self._apply_search_highlights()

    def clear_search_results(self):
        """Remove all search-result highlights."""
        self._search_results = []
        self._current_result = None
        for pw in self._page_widgets:
            pw.clear_search_rects()

    def _apply_search_highlights(self):
        """Push the stored search rects onto each page widget."""
        by_page: Dict[int, List[QRectF]] = {}
        for res in self._search_results:
            page = res.get("page", -1)
            for (x0, y0, x1, y1) in res.get("rects", []):
                by_page.setdefault(page, []).append(
                    QRectF(x0, y0, x1 - x0, y1 - y0))

        cur_page, cur_rect = self._current_result or (-1, None)
        for i, pw in enumerate(self._page_widgets):
            rects = by_page.get(i)
            if rects:
                pw.set_search_rects(rects, cur_rect if i == cur_page else None)
            else:
                pw.clear_search_rects()

    def scroll_to_search_result(self, page_num: int, rect):
        """Mark ``rect`` (PDF-coord tuple) on ``page_num`` as active and reveal it."""
        if not (0 <= page_num < len(self._page_widgets)):
            return
        x0, y0, x1, y1 = rect
        self._current_result = (page_num, QRectF(x0, y0, x1 - x0, y1 - y0))
        self._apply_search_highlights()

        # Scroll so the match is centred in the viewport where possible.
        pw = self._page_widgets[page_num]
        scale = self._zoom * self._render_dpi / 72
        cx = int(((x0 + x1) / 2) * scale)
        cy = int(((y0 + y1) / 2) * scale)
        target = pw.mapTo(self._container, QPoint(cx, cy))
        viewport = self.viewport()
        ymargin = viewport.height() // 2 if viewport else 0
        self.ensureVisible(target.x(), target.y(), 50, ymargin)

        self._current_page = page_num
        self.page_changed.emit(page_num)
        # The target page may still be a placeholder — make sure it renders.
        self._request_visible_pages()

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
        # Switching tools finishes any in-progress inline edit.
        self._close_inline_editor(commit=True)
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
        self._tool_cursor = cursor
        self.setCursor(cursor)

        # Leaving the Text Select tool drops the text-selection highlight so it
        # doesn't linger while drawing/annotating with another tool.
        if mode != ToolMode.TEXT_SELECT:
            self._text_selection = None
            for page_widget in self._page_widgets:
                page_widget.clear_text_selection()

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
        if not self._doc_live() or not self._page_widgets:
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

    def get_page_words(self, page_num: int) -> List:
        """Return ``page_num``'s words in reading order (cached).

        Each word is the PyMuPDF tuple ``(x0, y0, x1, y1, "word", block_no,
        line_no, word_no)`` in PDF coordinates. Returns ``[]`` if the page has no
        text layer (e.g. a scan that hasn't been OCR'd).
        """
        if not self._doc_live() or page_num < 0 or page_num >= len(self._doc):
            return []
        words = self._page_words_cache.get(page_num)
        if words is None:
            try:
                raw = self._doc[page_num].get_text("words")
            except Exception:
                logger.exception("Could not extract words for selection")
                raw = []
            # Sort into natural reading order: block, then line, then word.
            words = sorted(raw, key=lambda w: (w[5], w[6], w[7]))
            self._page_words_cache[page_num] = words
        return words

    def _on_text_selection_made(self, page_num: int, text: str, _rects: list):
        """Store the active text selection, copy it, and report the count."""
        # Only one selection is active at a time — clear highlights elsewhere.
        for i, pw in enumerate(self._page_widgets):
            if i != page_num:
                pw.clear_text_selection()

        if text:
            self._text_selection = (page_num, text)
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            self.text_selected.emit(text)
            self.selection_copied.emit(len(text))
        else:
            self._text_selection = None

    def _copy_text_selection(self):
        """Copy the active text selection to the clipboard (right-click Copy)."""
        if self._text_selection and self._text_selection[1]:
            text = self._text_selection[1]
            clipboard = QApplication.clipboard()
            if clipboard:
                clipboard.setText(text)
            self.selection_copied.emit(len(text))

    # ==================== Inline text editing (Edit Text tool) ============

    def set_text_block_provider(self, provider):
        """Set the callback that finds the paragraph under a point.

        ``provider(page_num, (x, y)) -> dict | None`` — see
        ``PDFDocument.detect_text_block``. Re-set after every document load so it
        stays bound to the live document.
        """
        self._text_block_provider = provider

    def _on_edit_text_requested(self, page_num: int, point: QPointF):
        """Open an inline editor over the paragraph at ``point`` on ``page_num``."""
        self._close_inline_editor(commit=True)
        if self._text_block_provider is None:
            self.edit_text_unavailable.emit(page_num)
            return
        try:
            block = self._text_block_provider(page_num, (point.x(), point.y()))
        except Exception:
            logger.exception("text block provider failed")
            block = None
        if not block:
            self.edit_text_unavailable.emit(page_num)
            return
        if 0 <= page_num < len(self._page_widgets):
            self._open_inline_editor(page_num, block)

    def _open_inline_editor(self, page_num: int, block: dict):
        from ui.inline_text_editor import InlineTextEditor
        from PyQt6.QtGui import QFont, QFontMetricsF

        page_widget = self._page_widgets[page_num]
        scale = page_widget._zoom * page_widget._render_dpi / 72
        if scale <= 0:
            return
        x0, y0, x1, y1 = block["bbox"]
        style = block["style"]

        editor = InlineTextEditor(page_widget)
        editor.document().setDocumentMargin(2)
        editor.setPlainText(block["text"])

        font = QFont()
        flags = int(style.get("flags", 0))
        font.setBold(bool(flags & (1 << 4)))
        font.setItalic(bool(flags & (1 << 1)))
        r, g, b = style.get("color", (0, 0, 0))
        editor.setStyleSheet(
            "QTextEdit { background: rgba(255,255,255,238);"
            " border: 1px solid #0078d4; padding: 0px;"
            f" color: rgb({int(r * 255)},{int(g * 255)},{int(b * 255)}); }}")

        # Geometry. The editor's font metrics don't match the PDF's (the same
        # text is usually much wider on screen), so forcing the original size
        # would wrap the text out of the one-line box. Instead: keep the box at
        # the selection's width and SHRINK the editor font (to a floor) until the
        # text fits — a one-line header stays one line — then size the height to
        # whatever the content needs so nothing is clipped.
        pad = 2
        frame = editor.frameWidth()
        chrome_w = 2 * frame + 2 * int(editor.document().documentMargin())
        block_w = (x1 - x0) * scale
        block_h = (y1 - y0) * scale
        gx = max(0, int(x0 * scale) - pad)
        gy = max(0, int(y0 * scale) - pad)
        avail_w = max(120.0, page_widget.width() - gx - 2)

        width = int(min(max(block_w, 120.0), avail_w))
        text_area = max(20.0, width - chrome_w)

        px = max(8, int(style.get("fontsize", 12) * scale))
        font.setPixelSize(px)
        lines = editor.toPlainText().split("\n")
        widest = max((QFontMetricsF(font).horizontalAdvance(ln) for ln in lines),
                     default=0.0)
        if widest > text_area:
            px = max(9, int(px * text_area / widest))
            font.setPixelSize(px)
        editor.setFont(font)

        editor.document().setTextWidth(text_area)
        content_h = editor.document().size().height()
        height = int(max(content_h + 2 * frame + 2, block_h + 2 * pad))
        avail_h = max(40, page_widget.height() - gy - 2)
        editor.setGeometry(gx, gy, width, min(height, avail_h))

        editor.committed.connect(self._on_inline_committed)
        editor.cancelled.connect(self._on_inline_cancelled)

        self._inline_editor = editor
        self._edit_ctx = {
            "page": page_num,
            "bbox": tuple(float(v) for v in block["bbox"]),
            "style": style,
            "original": block["text"],
        }
        editor.show()
        editor.raise_()
        editor.setFocus()

    def _on_inline_committed(self, text: str):
        ctx = self._edit_ctx
        self._teardown_inline_editor()
        if ctx is None or text == ctx["original"]:
            return  # no change -> no undoable op
        self.edit_text_committed.emit(
            ctx["page"], ctx["bbox"], text, ctx["style"])

    def _on_inline_cancelled(self):
        self._teardown_inline_editor()

    def _teardown_inline_editor(self):
        editor = self._inline_editor
        self._inline_editor = None
        self._edit_ctx = None
        if editor is not None:
            editor.hide()
            editor.deleteLater()

    def _close_inline_editor(self, commit: bool = True):
        """Finish any open inline edit programmatically (tool change / zoom)."""
        editor = self._inline_editor
        if editor is None:
            return
        if commit:
            editor.commit()
        else:
            editor.cancel()

    def get_selected_text(self) -> str:
        """Get the currently selected text.

        Prefers the word-based Text Select selection; falls back to the legacy
        rubber-band rectangle (used by the Select/erase tools) otherwise.
        """
        if self._text_selection is not None:
            return self._text_selection[1]
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

    def get_selection(self):
        """Return the current selection as (page_num, fitz.Rect) or None.

        Mirrors get_selected_text() but returns the selected region in PDF
        coordinates so callers can erase/redact it.
        """
        if not self._doc:
            return None
        if self._current_page < len(self._page_widgets):
            page_widget = self._page_widgets[self._current_page]
            rect = page_widget._selection_rect
            if rect is not None:
                scale = page_widget._zoom * page_widget._render_dpi / 72
                if scale > 0:
                    fitz_rect = fitz.Rect(
                        rect.x() / scale, rect.y() / scale,
                        (rect.x() + rect.width()) / scale,
                        (rect.y() + rect.height()) / scale,
                    )
                    return self._current_page, fitz_rect
        return None

    def clear_selection(self):
        """Clear both the rubber-band and the word-based text selection."""
        self._text_selection = None
        for page_widget in self._page_widgets:
            page_widget.clear_text_selection()
        if 0 <= self._current_page < len(self._page_widgets):
            page_widget = self._page_widgets[self._current_page]
            page_widget._selection_rect = None
            page_widget._selection_start = None
            page_widget.update()

    def refresh(self, changed_page: int = -1):
        """Refresh the view - re-render pages to show document changes.

        Pass ``changed_page`` when the change is known to be confined to one
        page (e.g. undoing an annotation); the worker's copy is then patched
        instead of re-serialized.
        """
        self._page_cache.clear()
        # Word positions may have shifted; drop the cache and stale selection.
        self._page_words_cache.clear()
        self._text_selection = None
        for pw in self._page_widgets:
            pw.clear_text_selection()

        # Mark all page widgets as needing re-render
        for page_widget in self._page_widgets:
            page_widget._is_loading = True

        # A changed page may have changed shape (undoing a rotation): resize
        # its widget, or the page keeps its old, rotated proportions.
        if (0 <= changed_page < len(self._page_widgets) and self._doc_live()
                and tuple(self._doc[changed_page].rect) != self._page_rects[changed_page]):
            self._page_rects[changed_page] = tuple(self._doc[changed_page].rect)
            self._page_widgets[changed_page].set_placeholder(
                *self._page_pixel_size(changed_page))
            self._layout.activate()

        # Immediate synchronous render of the current page for instant feedback,
        # straight from the editable document.
        if self._doc_live() and 0 <= self._current_page < len(self._page_widgets):
            self._render_page_sync(self._current_page)

        # The document may have changed in place — refresh the worker's copy:
        # patch the one changed page if known, else re-serialize lazily
        # (debounced). Both re-request the visible pages once the copy is fresh,
        # avoiding a stale-render flash.
        if 0 <= changed_page < len(self._page_widgets):
            if self._patch_render_copy([changed_page]):
                return
        self._schedule_worker_resync()

    def _render_page_sync(self, page_num: int):
        """Synchronously render a single page (for immediate feedback)"""
        if not self._doc_live() or page_num < 0 or page_num >= len(self._doc):
            return

        try:
            from core.render_backend import render_page
            region = (self._render_clip_for(page_num)
                      if page_num < len(self._page_widgets) else None)
            clip = region[0] if region is not None else None
            out = render_page(self._doc, page_num, self._zoom * self._render_dpi / 72,
                              self._rotation, clip)
            if out is None:
                return
            width, height, stride, samples, ox, oy = out
            img = QImage(samples, width, height, stride, QImage.Format.Format_RGB888)
            qpixmap = QPixmap.fromImage(img)
            if clip is not None:
                # Huge page: show just the rendered part, never cache it.
                self._page_widgets[page_num].set_partial_pixmap(
                    qpixmap, self._zoom, ox, oy, clip)
                self._shown_pages.add(page_num)
                return

            # Update cache and widget
            self._cache_put(page_num, qpixmap)
            if page_num < len(self._page_widgets):
                self._page_widgets[page_num].set_pixmap(qpixmap, self._zoom)
                self._shown_pages.add(page_num)
        except Exception:
            logger.exception("Error in sync render of page %s", page_num)

    def cleanup(self):
        """Clean up resources (call before closing)"""
        self._resync_timer.stop()
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

        # With an active text selection, only Copy is relevant — the view
        # commands (zoom/navigate/rotate) just get in the way, so show Copy alone.
        if self._text_selection is not None and self._text_selection[1]:
            menu.addAction("Copy", self._copy_text_selection)
            menu.exec(event.globalPos())
            return

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
