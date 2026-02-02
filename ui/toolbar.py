"""
Ultra PDF Editor - Toolbar with all tools and actions
"""
from PyQt6.QtWidgets import (
    QToolBar, QWidget, QHBoxLayout, QLabel,
    QSpinBox, QComboBox, QLineEdit,
    QColorDialog, QSlider, QFrame, QToolButton,
    QFontComboBox
)
from PyQt6.QtCore import Qt, QSize, pyqtSignal
from PyQt6.QtGui import QIcon, QColor, QFont, QPixmap, QPainter
from typing import Dict
from enum import Enum


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


def create_color_icon(color: QColor, size: int = 16) -> QIcon:
    """Create a colored square icon"""
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setBrush(color)
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, 2, 2)
    painter.end()

    return QIcon(pixmap)


class ColorButton(QToolButton):
    """Button for selecting colors"""

    color_changed = pyqtSignal(QColor)

    def __init__(self, initial_color: QColor = QColor(255, 255, 0), parent=None):
        super().__init__(parent)
        self._color = initial_color
        self._update_icon()
        self.clicked.connect(self._show_color_dialog)

    def _update_icon(self):
        self.setIcon(create_color_icon(self._color, 20))
        self.setIconSize(QSize(20, 20))

    def _show_color_dialog(self):
        color = QColorDialog.getColor(self._color, self, "Select Color")
        if color.isValid():
            self._color = color
            self._update_icon()
            self.color_changed.emit(color)

    def get_color(self) -> QColor:
        return self._color

    def set_color(self, color: QColor):
        self._color = color
        self._update_icon()


class ZoomWidget(QWidget):
    """Widget for zoom controls"""

    zoom_changed = pyqtSignal(float)
    zoom_in_clicked = pyqtSignal()
    zoom_out_clicked = pyqtSignal()
    fit_width_clicked = pyqtSignal()
    fit_page_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # Zoom out button
        self.zoom_out_btn = QToolButton()
        self.zoom_out_btn.setText("-")
        self.zoom_out_btn.setToolTip("Zoom Out (Ctrl+-)")
        self.zoom_out_btn.clicked.connect(self.zoom_out_clicked)
        layout.addWidget(self.zoom_out_btn)

        # Zoom combo box
        self.zoom_combo = QComboBox()
        self.zoom_combo.setEditable(True)
        self.zoom_combo.setMinimumWidth(80)
        self.zoom_combo.addItems([
            "50%", "75%", "100%", "125%", "150%", "200%", "300%", "400%",
            "Fit Width", "Fit Page"
        ])
        self.zoom_combo.setCurrentText("100%")
        self.zoom_combo.currentTextChanged.connect(self._on_zoom_changed)
        layout.addWidget(self.zoom_combo)

        # Zoom in button
        self.zoom_in_btn = QToolButton()
        self.zoom_in_btn.setText("+")
        self.zoom_in_btn.setToolTip("Zoom In (Ctrl++)")
        self.zoom_in_btn.clicked.connect(self.zoom_in_clicked)
        layout.addWidget(self.zoom_in_btn)

    def _on_zoom_changed(self, text: str):
        text = text.strip()
        if text == "Fit Width":
            self.fit_width_clicked.emit()
        elif text == "Fit Page":
            self.fit_page_clicked.emit()
        else:
            try:
                zoom = float(text.replace("%", ""))
                self.zoom_changed.emit(zoom)
            except ValueError:
                pass

    def set_zoom(self, zoom: float):
        """Set the zoom level display"""
        self.zoom_combo.setCurrentText(f"{zoom:.0f}%")


class PageNavigator(QWidget):
    """Widget for page navigation"""

    page_changed = pyqtSignal(int)
    first_page_clicked = pyqtSignal()
    prev_page_clicked = pyqtSignal()
    next_page_clicked = pyqtSignal()
    last_page_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page_count = 0
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        # First page
        self.first_btn = QToolButton()
        self.first_btn.setText("⏮")
        self.first_btn.setToolTip("First Page (Ctrl+Home)")
        self.first_btn.clicked.connect(self.first_page_clicked)
        layout.addWidget(self.first_btn)

        # Previous page
        self.prev_btn = QToolButton()
        self.prev_btn.setText("◀")
        self.prev_btn.setToolTip("Previous Page (Page Up)")
        self.prev_btn.clicked.connect(self.prev_page_clicked)
        layout.addWidget(self.prev_btn)

        # Page input
        self.page_spin = QSpinBox()
        self.page_spin.setMinimum(1)
        self.page_spin.setMaximum(1)
        self.page_spin.setMinimumWidth(60)
        self.page_spin.valueChanged.connect(lambda v: self.page_changed.emit(v - 1))
        layout.addWidget(self.page_spin)

        # Page count label
        self.page_label = QLabel("/ 0")
        layout.addWidget(self.page_label)

        # Next page
        self.next_btn = QToolButton()
        self.next_btn.setText("▶")
        self.next_btn.setToolTip("Next Page (Page Down)")
        self.next_btn.clicked.connect(self.next_page_clicked)
        layout.addWidget(self.next_btn)

        # Last page
        self.last_btn = QToolButton()
        self.last_btn.setText("⏭")
        self.last_btn.setToolTip("Last Page (Ctrl+End)")
        self.last_btn.clicked.connect(self.last_page_clicked)
        layout.addWidget(self.last_btn)

    def set_page_count(self, count: int):
        """Set total page count"""
        self._page_count = count
        self.page_spin.setMaximum(max(1, count))
        self.page_label.setText(f"/ {count}")

    def set_current_page(self, page: int):
        """Set current page (0-indexed)"""
        self.page_spin.blockSignals(True)
        self.page_spin.setValue(page + 1)
        self.page_spin.blockSignals(False)


class SearchWidget(QWidget):
    """Widget for search functionality"""

    search_requested = pyqtSignal(str)
    search_next = pyqtSignal()
    search_prev = pyqtSignal()
    replace_requested = pyqtSignal(str, str)
    replace_all_requested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        # Search input
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search...")
        self.search_input.setMinimumWidth(150)
        self.search_input.returnPressed.connect(lambda: self.search_requested.emit(self.search_input.text()))
        layout.addWidget(self.search_input)

        # Previous result
        self.prev_btn = QToolButton()
        self.prev_btn.setText("◀")
        self.prev_btn.setToolTip("Previous Result")
        self.prev_btn.clicked.connect(self.search_prev)
        layout.addWidget(self.prev_btn)

        # Next result
        self.next_btn = QToolButton()
        self.next_btn.setText("▶")
        self.next_btn.setToolTip("Next Result")
        self.next_btn.clicked.connect(self.search_next)
        layout.addWidget(self.next_btn)

        # Result count
        self.result_label = QLabel("")
        layout.addWidget(self.result_label)

    def set_result_count(self, current: int, total: int):
        """Update result count display"""
        if total > 0:
            self.result_label.setText(f"{current}/{total}")
        else:
            self.result_label.setText("")

    def get_search_text(self) -> str:
        return self.search_input.text()


class MainToolbar(QToolBar):
    """Main application toolbar"""

    # File signals
    open_requested = pyqtSignal()
    save_requested = pyqtSignal()
    save_as_requested = pyqtSignal()
    print_requested = pyqtSignal()

    # Edit signals
    undo_requested = pyqtSignal()
    redo_requested = pyqtSignal()
    cut_requested = pyqtSignal()
    copy_requested = pyqtSignal()
    paste_requested = pyqtSignal()

    # View signals
    zoom_changed = pyqtSignal(float)
    zoom_in_requested = pyqtSignal()
    zoom_out_requested = pyqtSignal()
    fit_width_requested = pyqtSignal()
    fit_page_requested = pyqtSignal()
    rotate_cw_requested = pyqtSignal()
    rotate_ccw_requested = pyqtSignal()

    # Navigation signals
    page_changed = pyqtSignal(int)
    first_page_requested = pyqtSignal()
    prev_page_requested = pyqtSignal()
    next_page_requested = pyqtSignal()
    last_page_requested = pyqtSignal()

    # Tool signals
    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(QColor)

    # Search signals
    search_requested = pyqtSignal(str)
    search_next = pyqtSignal()
    search_prev = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__("Main Toolbar", parent)
        self.setMovable(False)
        self.setIconSize(QSize(24, 24))

        self._tool_buttons: Dict[str, QToolButton] = {}
        self._setup_ui()

    def _setup_ui(self):
        # === File Section ===
        self._add_action("Open", "📂", "Open File (Ctrl+O)", self.open_requested)
        self._add_action("Save", "💾", "Save (Ctrl+S)", self.save_requested)
        self._add_action("Save As", "📥", "Save As (Ctrl+Shift+S)", self.save_as_requested)

        self.addSeparator()

        # === Edit Section ===
        self._add_action("Undo", "↩", "Undo (Ctrl+Z)", self.undo_requested)
        self._add_action("Redo", "↪", "Redo (Ctrl+Y)", self.redo_requested)

        self.addSeparator()

        # === Navigation Section ===
        self.page_navigator = PageNavigator()
        self.page_navigator.page_changed.connect(self.page_changed)
        self.page_navigator.first_page_clicked.connect(self.first_page_requested)
        self.page_navigator.prev_page_clicked.connect(self.prev_page_requested)
        self.page_navigator.next_page_clicked.connect(self.next_page_requested)
        self.page_navigator.last_page_clicked.connect(self.last_page_requested)
        self.addWidget(self.page_navigator)

        self.addSeparator()

        # === Zoom Section ===
        self.zoom_widget = ZoomWidget()
        self.zoom_widget.zoom_changed.connect(self.zoom_changed)
        self.zoom_widget.zoom_in_clicked.connect(self.zoom_in_requested)
        self.zoom_widget.zoom_out_clicked.connect(self.zoom_out_requested)
        self.zoom_widget.fit_width_clicked.connect(self.fit_width_requested)
        self.zoom_widget.fit_page_clicked.connect(self.fit_page_requested)
        self.addWidget(self.zoom_widget)

        self.addSeparator()

        # === Rotation ===
        self._add_action("Rotate Left", "↺", "Rotate Counter-Clockwise", self.rotate_ccw_requested)
        self._add_action("Rotate Right", "↻", "Rotate Clockwise", self.rotate_cw_requested)

        self.addSeparator()

        # === Search ===
        self.search_widget = SearchWidget()
        self.search_widget.search_requested.connect(self.search_requested)
        self.search_widget.search_next.connect(self.search_next)
        self.search_widget.search_prev.connect(self.search_prev)
        self.addWidget(self.search_widget)

        self.addSeparator()

        # === Print ===
        self._add_action("Print", "🖨", "Print (Ctrl+P)", self.print_requested)

    def _add_action(self, name: str, icon_text: str, tooltip: str, signal: pyqtSignal):
        """Add an action button to the toolbar"""
        btn = QToolButton()
        btn.setText(icon_text)
        btn.setToolTip(tooltip)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        btn.clicked.connect(signal.emit)

        # Style
        btn.setStyleSheet("""
            QToolButton {
                font-size: 16px;
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:pressed {
                background-color: #d0d0d0;
            }
        """)

        self.addWidget(btn)
        return btn

    def set_page_count(self, count: int):
        """Set total page count"""
        self.page_navigator.set_page_count(count)

    def set_current_page(self, page: int):
        """Set current page display"""
        self.page_navigator.set_current_page(page)

    def set_zoom(self, zoom: float):
        """Set zoom level display"""
        self.zoom_widget.set_zoom(zoom)


class AnnotationToolbar(QToolBar):
    """Toolbar for annotation and markup tools"""

    tool_changed = pyqtSignal(str)
    color_changed = pyqtSignal(QColor)
    opacity_changed = pyqtSignal(float)
    stroke_width_changed = pyqtSignal(int)
    font_changed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__("Annotation Toolbar", parent)
        self.setMovable(False)
        self.setIconSize(QSize(24, 24))

        self._current_tool = ToolMode.SELECT
        self._tool_buttons: Dict[str, QToolButton] = {}
        self._setup_ui()

    def _setup_ui(self):
        # === Selection Tools ===
        self._add_tool_button("Select", "👆", ToolMode.SELECT, "Select tool")
        self._add_tool_button("Hand", "✋", ToolMode.HAND, "Hand tool (Pan)")
        self._add_tool_button("Text Select", "I", ToolMode.TEXT_SELECT, "Select text")

        self.addSeparator()

        # === Text Markup ===
        self._add_tool_button("Highlight", "🖍", ToolMode.HIGHLIGHT, "Highlight text")
        self._add_tool_button("Underline", "U̲", ToolMode.UNDERLINE, "Underline text")
        self._add_tool_button("Strikethrough", "S̶", ToolMode.STRIKETHROUGH, "Strikethrough text")

        self.addSeparator()

        # === Annotations ===
        self._add_tool_button("Text Box", "T", ToolMode.TEXT_BOX, "Add text box")
        self._add_tool_button("Sticky Note", "📝", ToolMode.STICKY_NOTE, "Add sticky note")

        self.addSeparator()

        # === Shapes ===
        self._add_tool_button("Rectangle", "▢", ToolMode.RECTANGLE, "Draw rectangle")
        self._add_tool_button("Circle", "○", ToolMode.CIRCLE, "Draw circle/ellipse")
        self._add_tool_button("Line", "╱", ToolMode.LINE, "Draw line")
        self._add_tool_button("Arrow", "→", ToolMode.ARROW, "Draw arrow")
        self._add_tool_button("Freehand", "✏", ToolMode.FREEHAND, "Freehand drawing")

        self.addSeparator()

        # === Redact & Stamp ===
        self._add_tool_button("Redact", "█", ToolMode.REDACT, "Redact content")
        self._add_tool_button("Stamp", "🔖", ToolMode.STAMP, "Add stamp")

        self.addSeparator()

        # === Style Controls Group ===
        # Create a container widget for style controls with proper layout
        style_container = QWidget()
        style_layout = QHBoxLayout(style_container)
        style_layout.setContentsMargins(4, 0, 4, 0)
        style_layout.setSpacing(8)

        # Color picker with label
        color_label = QLabel("Color:")
        color_label.setStyleSheet("font-size: 11px;")
        style_layout.addWidget(color_label)

        self.color_btn = ColorButton(QColor(255, 255, 0))
        self.color_btn.setToolTip("Annotation color")
        self.color_btn.setFixedSize(24, 24)
        self.color_btn.color_changed.connect(self.color_changed)
        style_layout.addWidget(self.color_btn)

        # Separator
        style_layout.addWidget(self._create_separator_line())

        # Opacity with label
        opacity_label = QLabel("Opacity:")
        opacity_label.setStyleSheet("font-size: 11px;")
        style_layout.addWidget(opacity_label)

        self.opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self.opacity_slider.setMinimum(10)
        self.opacity_slider.setMaximum(100)
        self.opacity_slider.setValue(50)
        self.opacity_slider.setFixedWidth(60)
        self.opacity_slider.setToolTip("Annotation opacity")
        self.opacity_slider.valueChanged.connect(lambda v: self.opacity_changed.emit(v / 100))
        style_layout.addWidget(self.opacity_slider)

        # Separator
        style_layout.addWidget(self._create_separator_line())

        # Stroke width with label
        stroke_label = QLabel("Width:")
        stroke_label.setStyleSheet("font-size: 11px;")
        style_layout.addWidget(stroke_label)

        self.stroke_spin = QSpinBox()
        self.stroke_spin.setMinimum(1)
        self.stroke_spin.setMaximum(20)
        self.stroke_spin.setValue(2)
        self.stroke_spin.setFixedWidth(50)
        self.stroke_spin.setToolTip("Stroke width for lines and shapes")
        self.stroke_spin.valueChanged.connect(self.stroke_width_changed)
        style_layout.addWidget(self.stroke_spin)

        self.addWidget(style_container)

        self.addSeparator()

        # === Font Controls Group ===
        font_container = QWidget()
        font_layout = QHBoxLayout(font_container)
        font_layout.setContentsMargins(4, 0, 4, 0)
        font_layout.setSpacing(8)

        font_label = QLabel("Font:")
        font_label.setStyleSheet("font-size: 11px;")
        font_layout.addWidget(font_label)

        self.font_combo = QFontComboBox()
        self.font_combo.setCurrentFont(QFont("Arial"))
        self.font_combo.setFixedWidth(120)
        self.font_combo.setToolTip("Font family for text annotations")
        self.font_combo.currentFontChanged.connect(
            lambda: self.font_changed.emit(self.font_combo.currentFont().family(), self.font_size_spin.value())
        )
        font_layout.addWidget(self.font_combo)

        size_label = QLabel("Size:")
        size_label.setStyleSheet("font-size: 11px;")
        font_layout.addWidget(size_label)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setMinimum(6)
        self.font_size_spin.setMaximum(72)
        self.font_size_spin.setValue(12)
        self.font_size_spin.setFixedWidth(50)
        self.font_size_spin.setToolTip("Font size for text annotations")
        self.font_size_spin.valueChanged.connect(
            lambda: self.font_changed.emit(self.font_combo.currentFont().family(), self.font_size_spin.value())
        )
        font_layout.addWidget(self.font_size_spin)

        self.addWidget(font_container)

    def _create_separator_line(self) -> QFrame:
        """Create a vertical separator line"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet("color: #ccc;")
        return line

    def _add_tool_button(self, name: str, icon_text: str, mode: ToolMode, tooltip: str):
        """Add a tool button"""
        btn = QToolButton()
        btn.setText(icon_text)
        btn.setToolTip(tooltip)
        btn.setCheckable(True)
        btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)

        btn.setStyleSheet("""
            QToolButton {
                font-size: 16px;
                padding: 4px 8px;
                border: none;
                border-radius: 4px;
            }
            QToolButton:hover {
                background-color: #e0e0e0;
            }
            QToolButton:checked {
                background-color: #0078d4;
                color: white;
            }
        """)

        btn.clicked.connect(lambda checked, m=mode: self._on_tool_selected(m))
        self.addWidget(btn)
        self._tool_buttons[mode.value] = btn

        # Set initial state
        if mode == ToolMode.SELECT:
            btn.setChecked(True)

    def _on_tool_selected(self, mode: ToolMode):
        """Handle tool selection"""
        self._current_tool = mode

        # Update button states
        for tool_mode, btn in self._tool_buttons.items():
            btn.setChecked(tool_mode == mode.value)

        self.tool_changed.emit(mode.value)

    def get_current_tool(self) -> ToolMode:
        """Get current tool mode"""
        return self._current_tool

    def get_color(self) -> QColor:
        """Get current annotation color"""
        return self.color_btn.get_color()

    def get_opacity(self) -> float:
        """Get current opacity"""
        return self.opacity_slider.value() / 100

    def get_stroke_width(self) -> int:
        """Get current stroke width"""
        return self.stroke_spin.value()
