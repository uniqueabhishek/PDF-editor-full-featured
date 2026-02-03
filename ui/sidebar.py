"""
Ultra PDF Editor - Sidebar with Thumbnails, Bookmarks, and Annotations
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QLabel,
    QListWidget, QListWidgetItem, QTabWidget, QTreeWidget, QTreeWidgetItem,
    QMenu, QInputDialog, QLineEdit, QFrame
)
from PyQt6.QtCore import (
    Qt, pyqtSignal, QPoint, QTimer
)
from PyQt6.QtGui import QPixmap, QImage
import fitz
from typing import Optional, List, Dict
from dataclasses import dataclass


@dataclass
class ThumbnailData:
    """Data for a page thumbnail"""
    page_num: int
    pixmap: Optional[QPixmap] = None
    label: str = ""


class ThumbnailWidget(QFrame):
    """Widget displaying a single page thumbnail"""

    clicked = pyqtSignal(int)  # page number
    double_clicked = pyqtSignal(int)
    context_menu_requested = pyqtSignal(int, QPoint)

    def __init__(self, page_num: int, parent=None):
        super().__init__(parent)
        self.page_num = page_num
        self._selected = False
        self._pixmap: Optional[QPixmap] = None

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

        self.setFixedWidth(140)
        self._update_style()

    def _update_style(self):
        if self._selected:
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

    def set_selected(self, selected: bool):
        """Set selection state"""
        self._selected = selected
        self._update_style()

    def set_label(self, label: str):
        """Set page label"""
        self._page_label.setText(label)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.page_num)
        super().mousePressEvent(event)

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
    pages_reordered = pyqtSignal(int, int)  # from_index, to_index
    page_rotate_requested = pyqtSignal(int, int)  # page, degrees
    page_delete_requested = pyqtSignal(int)
    page_extract_requested = pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._doc: Optional[fitz.Document] = None
        self._thumbnails: List[ThumbnailWidget] = []
        self._current_page = 0
        self._selected_pages: List[int] = []
        self._render_dpi = 36  # Low DPI for thumbnails

        self._setup_ui()
        self._render_timer = QTimer()
        self._render_timer.setSingleShot(True)
        self._render_timer.timeout.connect(self._render_visible_thumbnails)

    def _setup_ui(self):
        self.setWidgetResizable(True)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)

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

    def _create_thumbnails(self):
        """Create thumbnail widgets for all pages"""
        if not self._doc:
            return

        for i in range(len(self._doc)):
            thumb = ThumbnailWidget(i, self._container)
            thumb.clicked.connect(self._on_thumbnail_clicked)
            thumb.double_clicked.connect(self._on_thumbnail_double_clicked)
            thumb.context_menu_requested.connect(self._show_context_menu)
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


class BookmarkPanel(QTreeWidget):
    """Panel showing document bookmarks/outline"""

    bookmark_clicked = pyqtSignal(int)  # page number
    bookmark_added = pyqtSignal(str, int)  # title, page
    bookmark_deleted = pyqtSignal(int)  # bookmark index
    bookmark_renamed = pyqtSignal(int, str)  # index, new title

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

    def _rename_bookmark(self, item: QTreeWidgetItem):
        """Rename a bookmark"""
        current = item.text(0)
        text, ok = QInputDialog.getText(
            self, "Rename Bookmark", "New name:", QLineEdit.EchoMode.Normal, current
        )
        if ok and text:
            item.setText(0, text)
            # Would need to update document TOC

    def _delete_bookmark(self, item: QTreeWidgetItem):
        """Delete a bookmark"""
        parent = item.parent()
        if not parent:
            parent = self.invisibleRootItem()
        if parent:
            index = parent.indexOfChild(item)
            parent.takeChild(index)
        # Would need to update document TOC

    def _add_bookmark_dialog(self):
        """Show dialog to add bookmark"""
        text, ok = QInputDialog.getText(
            self, "Add Bookmark", "Bookmark title:"
        )
        if ok and text:
            # Would emit signal with title and current page
            pass

    def add_bookmark(self, title: str, page: int):
        """Add a new bookmark"""
        item = QTreeWidgetItem([title])
        item.setData(0, Qt.ItemDataRole.UserRole, page)
        self.addTopLevelItem(item)


class AnnotationPanel(QListWidget):
    """Panel showing document annotations"""

    annotation_clicked = pyqtSignal(int, int)  # page, annotation index
    annotation_deleted = pyqtSignal(int, int)

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
            "rect": tuple(annot.rect)
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
                              lambda: self.annotation_deleted.emit(data["page"], self.row(item)))
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
    page_rotate_requested = pyqtSignal(int, int)
    page_delete_requested = pyqtSignal(int)
    page_extract_requested = pyqtSignal(list)

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
        self.thumbnail_panel.page_extract_requested.connect(self.page_extract_requested)

        self.bookmark_panel.bookmark_clicked.connect(self.bookmark_clicked)
        self.annotation_panel.annotation_clicked.connect(self.annotation_clicked)

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

    def refresh(self):
        """Refresh all panels"""
        self.thumbnail_panel.refresh()
        self.annotation_panel.refresh()
