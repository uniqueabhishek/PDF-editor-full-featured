"""
Ultra PDF Editor - Sidebar with Thumbnails, Bookmarks, and Annotations
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QLabel, QApplication,
    QListWidget, QListWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QLineEdit, QFrame, QToolButton, QPushButton
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPoint, QMimeData, QTimer
)
from PyQt6.QtGui import QPixmap, QImage, QDrag, QColor, QPainter, QPen
import fitz
from typing import Optional, List, Dict
from dataclasses import dataclass

# MIME type used to carry a page index during thumbnail drag-and-drop reorder.
_PAGE_MIME = "application/x-pdf-page"


@dataclass
class ThumbnailData:
    """Data for a page thumbnail"""
    page_num: int
    pixmap: Optional[QPixmap] = None
    label: str = ""


class _DeleteOverlay(QWidget):
    """Translucent red overlay with a big X, shown over a page marked for deletion.

    Drawn on top of the thumbnail image; clicking it un-marks the page (this is how
    the small corner ✕ "becomes" a full page-wide X and back again).
    """

    clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # Non-opaque child: Qt repaints the thumbnail image beneath it first, so
        # the translucent red fill blends over the page rather than over a base colour.
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Click to keep this page (cancel deletion)")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        # Translucent red tint over the whole page.
        painter.fillRect(rect, QColor(220, 40, 40, 70))
        # Thick red X corner-to-corner.
        pen = QPen(QColor(200, 25, 25), 5)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        m = 6
        painter.drawLine(rect.left() + m, rect.top() + m,
                         rect.right() - m, rect.bottom() - m)
        painter.drawLine(rect.right() - m, rect.top() + m,
                         rect.left() + m, rect.bottom() - m)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
        super().mousePressEvent(event)


class ThumbnailWidget(QFrame):
    """Widget displaying a single page thumbnail"""

    clicked = pyqtSignal(int)  # page number
    double_clicked = pyqtSignal(int)
    context_menu_requested = pyqtSignal(int, QPoint)
    mark_toggled = pyqtSignal(int, bool)  # page number, is now marked for deletion

    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._selected = False
        self._marked = False        # marked for deletion
        self._delete_mode = False   # delete-selection mode active (badges visible)
        self._pixmap: Optional[QPixmap] = None
        self._drag_start_pos: Optional[QPoint] = None

        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(2)

        # Thumbnail image
        self._image_label = QLabel()
        self._image_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._image_label.setStyleSheet("background-color: white; border: 1px solid #ccc;")
        layout.addWidget(self._image_label)

        # Page number label
        self._page_label = QLabel(str(self.page_num + 1))
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._page_label)

        # Big red X overlay shown when the page is marked for deletion.
        self._overlay = _DeleteOverlay(self)
        self._overlay.clicked.connect(lambda: self._toggle_mark(False))
        self._overlay.hide()

        # Small corner ✕ badge — only visible while in delete-selection mode.
        self._mark_btn = QToolButton(self)
        self._mark_btn.setText("✕")
        self._mark_btn.setFixedSize(20, 20)
        self._mark_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._mark_btn.setToolTip("Mark this page for deletion")
        self._mark_btn.setStyleSheet("""
            QToolButton {
                background-color: rgba(255, 255, 255, 235);
                color: #c81e1e;
                border: 1px solid #c81e1e;
                border-radius: 10px;
                font-weight: bold;
                font-size: 12px;
                padding: 0px;
            }
            QToolButton:hover {
                background-color: #c81e1e;
                color: white;
            }
        """)
        self._mark_btn.clicked.connect(lambda: self._toggle_mark(True))
        self._mark_btn.hide()

        self.setFixedWidth(140)
        self._update_style()

    def _update_style(self):
        if self._marked:
            self.setStyleSheet("""
                ThumbnailWidget {
                    background-color: #fdecea;
                    border: 2px solid #c81e1e;
                    border-radius: 4px;
                }
                QLabel {
                    color: #c81e1e;
                }
            """)
        elif self._selected:
            self.setStyleSheet("""
                ThumbnailWidget {
                    background-color: #0078d4;
                    border-radius: 4px;
                }
                QLabel {
                    color: white;
                }
            """)
        else:
            self.setStyleSheet("""
                ThumbnailWidget {
                    background-color: transparent;
                    border-radius: 4px;
                }
                ThumbnailWidget:hover {
                    background-color: #e5e5e5;
                }
            """)

    def _update_badges(self):
        """Show/hide the corner ✕ and the big-X overlay per the current state."""
        self._mark_btn.setVisible(self._delete_mode and not self._marked)
        self._overlay.setVisible(self._marked)
        self._reposition_badges()
        if self._marked:
            self._overlay.raise_()
        elif self._delete_mode:
            self._mark_btn.raise_()

    def _reposition_badges(self):
        """Keep the overlay over the image and the ✕ badge in the top-right corner."""
        self._overlay.setGeometry(self._image_label.geometry())
        margin = 6
        self._mark_btn.move(
            self.width() - self._mark_btn.width() - margin, margin)

    def _toggle_mark(self, marked: bool):
        """Set the marked state from a user click and notify listeners."""
        self.set_marked(marked)
        self.mark_toggled.emit(self.page_num, marked)

    def set_pixmap(self, pixmap: QPixmap):
        """Set the thumbnail image"""
        self._pixmap = pixmap
        scaled = pixmap.scaled(
            120, 160,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self._image_label.setPixmap(scaled)
        self._image_label.setFixedSize(scaled.size())
        self._reposition_badges()

    def set_selected(self, selected: bool):
        """Set selection state"""
        self._selected = selected
        self._update_style()

    def set_delete_mode(self, enabled: bool):
        """Enter/leave delete-selection mode (controls the corner ✕ badge)."""
        self._delete_mode = enabled
        if not enabled:
            self._marked = False
        self._update_badges()
        self._update_style()

    def set_marked(self, marked: bool):
        """Set whether this page is marked for deletion."""
        self._marked = marked
        self._update_badges()
        self._update_style()

    def set_label(self, label: str):
        """Set page label"""
        self._page_label.setText(label)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_badges()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_start_pos = event.position().toPoint()
            self.clicked.emit(self.page_num)
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        # Start a drag once the pointer has moved far enough with the button held,
        # so a plain click still selects the page.
        if not (event.buttons() & Qt.MouseButton.LeftButton) or self._drag_start_pos is None:
            super().mouseMoveEvent(event)
            return
        moved = (event.position().toPoint() - self._drag_start_pos).manhattanLength()
        if moved < QApplication.startDragDistance():
            return

        drag = QDrag(self)
        mime = QMimeData()
        mime.setData(_PAGE_MIME, str(self.page_num).encode())
        drag.setMimeData(mime)
        if self._pixmap is not None:
            drag.setPixmap(self._pixmap.scaled(
                80, 100, Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        self._drag_start_pos = None
        drag.exec(Qt.DropAction.MoveAction)

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.page_num)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        self.context_menu_requested.emit(self.page_num, event.globalPos())


class ThumbnailPanel(QScrollArea):
    """Panel showing page thumbnails"""

    page_selected = pyqtSignal(int)
    page_double_clicked = pyqtSignal(int)
    pages_reordered = pyqtSignal(int, int)  # source page, insert-before index
    page_rotate_requested = pyqtSignal(int, int)  # page, degrees
    page_delete_requested = pyqtSignal(int)
    pages_delete_requested = pyqtSignal(list)  # batch delete of marked pages
    marked_pages_changed = pyqtSignal(list)  # current set of pages marked for deletion
    page_extract_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._thumbnails: List[ThumbnailWidget] = []
        self._current_page = 0
        self._selected_pages: List[int] = []
        self._marked_pages: set[int] = set()
        self._delete_mode = False
        self._render_dpi = 36  # Low DPI for thumbnails

        self._setup_ui()
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_visible_thumbnails)

    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setAcceptDrops(True)  # accept page reorder drops from thumbnails

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setSpacing(10)
        self._layout.setContentsMargins(10, 10, 10, 10)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop)

        self.setWidget(self._container)

        self.setStyleSheet("""
            QScrollArea {
                background-color: #f5f5f5;
                border: none;
            }
        """)

        v_scrollbar = self.verticalScrollBar()
        if v_scrollbar:
            v_scrollbar.valueChanged.connect(self._on_scroll)

        # Floating action bar — appears over the bottom of the panel once one or
        # more pages are marked for deletion. Parented to the scroll area (not the
        # scrolled container) so it stays pinned while the thumbnails scroll.
        self._delete_bar = QFrame(self)
        self._delete_bar.setObjectName("deleteBar")
        self._delete_bar.setStyleSheet("""
            QFrame#deleteBar {
                background-color: #2b2b2b;
                border-radius: 6px;
            }
            QPushButton {
                color: white;
                border: none;
                padding: 6px 10px;
                font-size: 12px;
            }
            QPushButton#deleteBtn {
                background-color: #c81e1e;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton#deleteBtn:hover { background-color: #e23b3b; }
            QPushButton#clearBtn { color: #dddddd; }
            QPushButton#clearBtn:hover { color: white; }
        """)
        bar_layout = QHBoxLayout(self._delete_bar)
        bar_layout.setContentsMargins(8, 6, 8, 6)
        bar_layout.setSpacing(6)
        self._delete_btn = QPushButton("Delete pages")
        self._delete_btn.setObjectName("deleteBtn")
        self._delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._delete_btn.clicked.connect(self._on_delete_clicked)
        self._clear_btn = QPushButton("Clear")
        self._clear_btn.setObjectName("clearBtn")
        self._clear_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._clear_btn.clicked.connect(self.clear_marks)
        bar_layout.addWidget(self._delete_btn)
        bar_layout.addWidget(self._clear_btn)
        self._delete_bar.hide()

    def set_document(self, doc: Optional[fitz.Document]):
        """Set the document for thumbnail generation"""
        self._doc = doc
        self._clear_thumbnails()

        if doc:
            self._create_thumbnails()
            self._render_timer.start(100)

    def _clear_thumbnails(self):
        """Clear all thumbnails"""
        for thumb in self._thumbnails:
            thumb.setParent(None)
            thumb.deleteLater()
        self._thumbnails.clear()
        self._selected_pages.clear()
        # Marks don't survive a reload; the delete-selection mode does.
        self._marked_pages.clear()
        self._update_delete_bar()
        self.marked_pages_changed.emit([])

    def _create_thumbnails(self):
        """Create thumbnail widgets for all pages"""
        if not self._doc:
            return

        for i in range(len(self._doc)):
            thumb = ThumbnailWidget(i, self._container)
            thumb.clicked.connect(self._on_thumbnail_clicked)
            thumb.double_clicked.connect(self._on_thumbnail_double_clicked)
            thumb.context_menu_requested.connect(self._show_context_menu)
            thumb.mark_toggled.connect(self._on_mark_toggled)
            if self._delete_mode:
                thumb.set_delete_mode(True)
            self._layout.addWidget(thumb)
            self._thumbnails.append(thumb)

    def _render_visible_thumbnails(self):
        """Render thumbnails that are visible"""
        if not self._doc or not self._thumbnails:
            return

        viewport_widget = self.viewport()
        v_scrollbar = self.verticalScrollBar()
        if not viewport_widget or not v_scrollbar:
            return
        viewport = viewport_widget.rect()
        scroll_pos = v_scrollbar.value()

        for thumb in self._thumbnails:
            widget_rect = thumb.geometry()
            widget_rect.translate(0, -scroll_pos)

            if viewport.intersects(widget_rect):
                if thumb._pixmap is None:
                    pixmap = self._render_thumbnail(thumb.page_num)
                    thumb.set_pixmap(pixmap)

    def _render_thumbnail(self, page_num: int) -> QPixmap:
        """Render a single thumbnail"""
        if not self._doc or page_num < 0 or page_num >= len(self._doc):
            return QPixmap()

        page = self._doc[page_num]
        zoom = self._render_dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        pixmap = page.get_pixmap(matrix=matrix, alpha=False)

        img = QImage(pixmap.samples, pixmap.width, pixmap.height,
                     pixmap.stride, QImage.Format.Format_RGB888)
        return QPixmap.fromImage(img)

    def _on_scroll(self):
        """Handle scroll"""
        self._render_timer.start(50)

    # ---- Drag-and-drop page reordering ----

    def dragEnterEvent(self, event):
        if event.mimeData().hasFormat(_PAGE_MIME):
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasFormat(_PAGE_MIME):
            event.acceptProposedAction()

    def dropEvent(self, event):
        md = event.mimeData()
        if not md.hasFormat(_PAGE_MIME):
            return
        try:
            source_page = int(bytes(md.data(_PAGE_MIME)).decode())
        except (ValueError, UnicodeDecodeError):
            return

        # Map the drop point into the thumbnail container's coordinate system,
        # then find the page it should be inserted in front of.
        global_pos = self.mapToGlobal(event.position().toPoint())
        drop_y = self._container.mapFromGlobal(global_pos).y()
        target = len(self._thumbnails)
        for i, thumb in enumerate(self._thumbnails):
            geo = thumb.geometry()
            if drop_y < geo.y() + geo.height() / 2:
                target = i
                break

        event.acceptProposedAction()
        self.pages_reordered.emit(source_page, target)

    def _on_thumbnail_clicked(self, page_num: int):
        """Handle thumbnail click"""
        # Update selection
        for i, thumb in enumerate(self._thumbnails):
            thumb.set_selected(i == page_num)

        self._current_page = page_num
        self._selected_pages = [page_num]
        self.page_selected.emit(page_num)

    def _on_thumbnail_double_clicked(self, page_num: int):
        """Handle thumbnail double click"""
        self.page_double_clicked.emit(page_num)

    def _show_context_menu(self, page_num: int, pos: QPoint):
        """Show context menu for thumbnail"""
        menu = QMenu(self)

        menu.addAction("Go to Page", lambda: self.page_selected.emit(page_num))
        menu.addSeparator()

        # Rotation submenu
        rotate_menu = menu.addMenu("Rotate")
        if rotate_menu:
            rotate_menu.addAction("90° Clockwise", lambda: self.page_rotate_requested.emit(page_num, 90))
            rotate_menu.addAction("90° Counter-Clockwise", lambda: self.page_rotate_requested.emit(page_num, -90))
            rotate_menu.addAction("180°", lambda: self.page_rotate_requested.emit(page_num, 180))

        menu.addSeparator()
        menu.addAction("Extract Page", lambda: self.page_extract_requested.emit([page_num]))
        menu.addAction("Delete Page", lambda: self.page_delete_requested.emit(page_num))

        menu.exec(pos)

    def set_current_page(self, page_num: int):
        """Set and highlight current page"""
        if 0 <= page_num < len(self._thumbnails):
            for i, thumb in enumerate(self._thumbnails):
                thumb.set_selected(i == page_num)
            self._current_page = page_num

            # Scroll to make visible
            thumb = self._thumbnails[page_num]
            self.ensureWidgetVisible(thumb)

    def refresh(self):
        """Refresh all thumbnails"""
        for thumb in self._thumbnails:
            thumb._pixmap = None
        self._render_timer.start(100)

    # ---- Delete-selection mode (corner ✕ badges + batch delete) ----

    def set_delete_mode(self, enabled: bool):
        """Enter/leave delete-selection mode (shows the corner ✕ on every page)."""
        self._delete_mode = enabled
        for thumb in self._thumbnails:
            thumb.set_delete_mode(enabled)
        if not enabled:
            self._marked_pages.clear()
            self._update_delete_bar()
            self.marked_pages_changed.emit([])

    def _on_mark_toggled(self, page_num: int, marked: bool):
        """A thumbnail's ✕/overlay was clicked — track the page and update the bar."""
        if marked:
            self._marked_pages.add(page_num)
        else:
            self._marked_pages.discard(page_num)
        self._update_delete_bar()
        self.marked_pages_changed.emit(sorted(self._marked_pages))

    def _on_delete_clicked(self):
        if self._marked_pages:
            self.pages_delete_requested.emit(sorted(self._marked_pages))

    def get_marked_pages(self) -> List[int]:
        """The pages currently marked for deletion, ascending."""
        return sorted(self._marked_pages)

    def clear_marks(self):
        """Un-mark every page (stays in delete-selection mode)."""
        self._marked_pages.clear()
        for thumb in self._thumbnails:
            thumb.set_marked(False)
        self._update_delete_bar()
        self.marked_pages_changed.emit([])

    def _update_delete_bar(self):
        """Show/label/hide the floating delete bar based on the marked count."""
        count = len(self._marked_pages)
        if count == 0:
            self._delete_bar.hide()
            return
        self._delete_btn.setText(
            f"Delete {count} page" + ("s" if count != 1 else ""))
        self._delete_bar.show()
        self._delete_bar.raise_()
        self._reposition_delete_bar()

    def _reposition_delete_bar(self):
        """Pin the floating bar to the bottom-centre of the viewport."""
        if not self._delete_bar.isVisible():
            return
        self._delete_bar.adjustSize()
        viewport = self.viewport()
        area = viewport.rect() if viewport else self.rect()
        x = area.left() + (area.width() - self._delete_bar.width()) // 2
        y = area.bottom() - self._delete_bar.height() - 12
        self._delete_bar.move(max(0, x), max(0, y))

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._reposition_delete_bar()


class BookmarkPanel(QTreeWidget):
    """Panel showing document bookmarks/outline"""

    bookmark_clicked = pyqtSignal(int)  # page number
    toc_changed = pyqtSignal(list)  # full new table of contents (after rename/delete)
    bookmark_add_requested = pyqtSignal(str)  # title (added at the current page)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._toc: List = []

        self._setup_ui()

    def _setup_ui(self):
        self.setHeaderHidden(True)
        self.setAnimated(True)
        self.setIndentation(20)
        self.setStyleSheet("""
            QTreeWidget {
                background-color: #ffffff;
                border: none;
            }
            QTreeWidget::item {
                padding: 5px;
            }
            QTreeWidget::item:hover {
                background-color: #e5e5e5;
            }
            QTreeWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        self.itemClicked.connect(self._on_item_clicked)
        self.itemDoubleClicked.connect(self._on_item_double_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_document(self, doc: Optional[fitz.Document]):
        """Set document and load bookmarks"""
        self._doc = doc
        self.clear()

        if doc:
            self._load_bookmarks()

    def _load_bookmarks(self):
        """Load bookmarks from document"""
        if not self._doc:
            return

        try:
            self._toc = self._doc.get_toc()
        except Exception:
            self._toc = []
            return

        if not self._toc:
            # Show placeholder
            item = QTreeWidgetItem(["No bookmarks"])
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.addTopLevelItem(item)
            return

        # Build tree from TOC
        # TOC format: [level, title, page, dest]
        root_item = self.invisibleRootItem()
        if not root_item:
            return
        item_stack: list[tuple[int, QTreeWidgetItem]] = [(0, root_item)]

        for entry in self._toc:
            level = entry[0]
            title = entry[1]
            page = entry[2] - 1  # Convert to 0-indexed

            # Find parent at appropriate level
            while item_stack[-1][0] >= level:
                item_stack.pop()

            parent = item_stack[-1][1]

            # Create item
            item = QTreeWidgetItem([title])
            item.setData(0, Qt.ItemDataRole.UserRole, page)
            parent.addChild(item)

            item_stack.append((level, item))

        self.expandAll()

    def _on_item_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle item click"""
        page = item.data(0, Qt.ItemDataRole.UserRole)
        if page is not None:
            self.bookmark_clicked.emit(page)

    def _on_item_double_clicked(self, item: QTreeWidgetItem, column: int):
        """Handle double click for rename"""
        pass  # Could implement inline editing

    def _show_context_menu(self, pos: QPoint):
        """Show context menu"""
        item = self.itemAt(pos)
        menu = QMenu(self)

        if item:
            page = item.data(0, Qt.ItemDataRole.UserRole)
            if page is not None:
                menu.addAction("Go to Page", lambda: self.bookmark_clicked.emit(page))
                menu.addSeparator()
                menu.addAction("Rename", lambda: self._rename_bookmark(item))
                menu.addAction("Delete", lambda: self._delete_bookmark(item))
        else:
            menu.addAction("Add Bookmark Here...", self._add_bookmark_dialog)

        menu.exec(self.mapToGlobal(pos))

    def _build_toc_from_tree(self) -> List:
        """Rebuild a PyMuPDF TOC ([level, title, page], 1-indexed) from the tree."""
        toc: List = []

        def walk(parent: QTreeWidgetItem, level: int):
            for i in range(parent.childCount()):
                child = parent.child(i)
                page = child.data(0, Qt.ItemDataRole.UserRole)
                if page is None:
                    continue  # skip the "No bookmarks" placeholder
                toc.append([level, child.text(0), int(page) + 1])
                walk(child, level + 1)

        root = self.invisibleRootItem()
        if root:
            walk(root, 1)
        return toc

    def _rename_bookmark(self, item: QTreeWidgetItem):
        """Rename a bookmark and persist the change to the document TOC."""
        current = item.text(0)
        text, ok = QInputDialog.getText(
            self, "Rename Bookmark", "New name:", QLineEdit.EchoMode.Normal, current
        )
        if ok and text:
            item.setText(0, text)
            self.toc_changed.emit(self._build_toc_from_tree())

    def _delete_bookmark(self, item: QTreeWidgetItem):
        """Delete a bookmark (and its children) and persist the change."""
        parent = item.parent()
        if not parent:
            parent = self.invisibleRootItem()
        if parent:
            index = parent.indexOfChild(item)
            parent.takeChild(index)
        self.toc_changed.emit(self._build_toc_from_tree())

    def _add_bookmark_dialog(self):
        """Ask for a title and request a bookmark at the current page."""
        text, ok = QInputDialog.getText(
            self, "Add Bookmark", "Bookmark title:"
        )
        if ok and text:
            self.bookmark_add_requested.emit(text)


class AnnotationPanel(QListWidget):
    """Panel showing document annotations"""

    annotation_clicked = pyqtSignal(int, int)  # page, annotation index
    annotation_deleted = pyqtSignal(int, int)  # page, annotation xref

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._annotations: List[Dict] = []

        self._setup_ui()

    def _setup_ui(self):
        self.setStyleSheet("""
            QListWidget {
                background-color: #ffffff;
                border: none;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #eee;
            }
            QListWidget::item:hover {
                background-color: #f0f0f0;
            }
            QListWidget::item:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

        self.itemClicked.connect(self._on_item_clicked)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def set_document(self, doc: Optional[fitz.Document]):
        """Set document and load annotations"""
        self._doc = doc
        self.clear()
        self._annotations.clear()

        if doc:
            self._load_annotations()

    def _load_annotations(self):
        """Load all annotations from document"""
        if not self._doc:
            return

        for page_num in range(len(self._doc)):
            page = self._doc[page_num]
            annots = page.annots()

            if annots:
                for annot in annots:
                    self._add_annotation_item(page_num, annot)

        if self.count() == 0:
            item = QListWidgetItem("No annotations")
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self.addItem(item)

    def _add_annotation_item(self, page_num: int, annot):
        """Add an annotation to the list"""
        annot_type = annot.type[1]  # Get type name
        content = annot.info.get("content", "")[:50]

        text = f"Page {page_num + 1}: {annot_type}"
        if content:
            text += f" - {content}"

        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, {
            "page": page_num,
            "type": annot_type,
            "rect": tuple(annot.rect),
            "xref": annot.xref,
        })

        self._annotations.append({
            "page": page_num,
            "annot": annot
        })

        self.addItem(item)

    def _on_item_clicked(self, item: QListWidgetItem):
        """Handle item click"""
        data = item.data(Qt.ItemDataRole.UserRole)
        if data:
            self.annotation_clicked.emit(data["page"], self.row(item))

    def _show_context_menu(self, pos: QPoint):
        """Show context menu"""
        item = self.itemAt(pos)
        if item:
            data = item.data(Qt.ItemDataRole.UserRole)
            if data:
                menu = QMenu(self)
                menu.addAction("Go to Annotation",
                              lambda: self.annotation_clicked.emit(data["page"], self.row(item)))
                menu.addAction("Delete",
                              lambda: self.annotation_deleted.emit(data["page"], data["xref"]))
                menu.exec(self.mapToGlobal(pos))

    def refresh(self):
        """Refresh annotations list"""
        if self._doc:
            self.set_document(self._doc)


class Sidebar(QTabWidget):
    """Main sidebar widget with tabs for thumbnails, bookmarks, and annotations"""

    page_selected = pyqtSignal(int)
    page_double_clicked = pyqtSignal(int)
    bookmark_clicked = pyqtSignal(int)
    annotation_clicked = pyqtSignal(int, int)
    annotation_deleted = pyqtSignal(int, int)  # page, annotation xref
    page_rotate_requested = pyqtSignal(int, int)
    page_delete_requested = pyqtSignal(int)
    pages_delete_requested = pyqtSignal(list)  # batch delete of marked pages
    marked_pages_changed = pyqtSignal(list)  # current set of pages marked for deletion
    page_extract_requested = pyqtSignal(list)
    pages_reordered = pyqtSignal(int, int)  # source page, insert-before index
    toc_changed = pyqtSignal(list)  # full new table of contents
    bookmark_add_requested = pyqtSignal(str)  # title (added at current page)

    def __init__(self, parent=None):
        super().__init__(parent)

        self._setup_ui()

    def _setup_ui(self):
        self.setTabPosition(QTabWidget.TabPosition.West)
        self.setDocumentMode(True)

        # Create panels
        self.thumbnail_panel = ThumbnailPanel()
        self.bookmark_panel = BookmarkPanel()
        self.annotation_panel = AnnotationPanel()

        # Add tabs
        self.addTab(self.thumbnail_panel, "Pages")
        self.addTab(self.bookmark_panel, "Bookmarks")
        self.addTab(self.annotation_panel, "Annotations")

        # Connect signals
        self.thumbnail_panel.page_selected.connect(self.page_selected)
        self.thumbnail_panel.page_double_clicked.connect(self.page_double_clicked)
        self.thumbnail_panel.page_rotate_requested.connect(self.page_rotate_requested)
        self.thumbnail_panel.page_delete_requested.connect(self.page_delete_requested)
        self.thumbnail_panel.pages_delete_requested.connect(self.pages_delete_requested)
        self.thumbnail_panel.marked_pages_changed.connect(self.marked_pages_changed)
        self.thumbnail_panel.page_extract_requested.connect(self.page_extract_requested)
        self.thumbnail_panel.pages_reordered.connect(self.pages_reordered)

        self.bookmark_panel.bookmark_clicked.connect(self.bookmark_clicked)
        self.bookmark_panel.toc_changed.connect(self.toc_changed)
        self.bookmark_panel.bookmark_add_requested.connect(self.bookmark_add_requested)
        self.annotation_panel.annotation_clicked.connect(self.annotation_clicked)
        self.annotation_panel.annotation_deleted.connect(self.annotation_deleted)

        # Styling
        self.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background-color: #f5f5f5;
            }
            QTabBar::tab {
                padding: 10px 5px;
                min-width: 30px;
            }
            QTabBar::tab:selected {
                background-color: #0078d4;
                color: white;
            }
        """)

    def set_document(self, doc: Optional[fitz.Document]):
        """Set document for all panels"""
        self.thumbnail_panel.set_document(doc)
        self.bookmark_panel.set_document(doc)
        self.annotation_panel.set_document(doc)

    def set_current_page(self, page_num: int):
        """Update current page in thumbnail panel"""
        self.thumbnail_panel.set_current_page(page_num)

    def set_delete_mode(self, enabled: bool):
        """Toggle delete-selection mode on the thumbnail panel."""
        self.thumbnail_panel.set_delete_mode(enabled)

    def get_marked_pages(self) -> List[int]:
        """Pages currently marked for deletion in the thumbnail panel."""
        return self.thumbnail_panel.get_marked_pages()

    def clear_page_marks(self):
        """Un-mark every page in the thumbnail panel."""
        self.thumbnail_panel.clear_marks()

    def refresh(self):
        """Refresh all panels"""
        self.thumbnail_panel.refresh()
        self.annotation_panel.refresh()
