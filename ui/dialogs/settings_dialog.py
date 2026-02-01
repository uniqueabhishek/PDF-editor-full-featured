"""
Ultra PDF Editor - Settings Dialog
Application preferences and settings
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QTabWidget, QWidget, QFormLayout, QComboBox, QSpinBox,
    QCheckBox, QLineEdit, QGroupBox, QColorDialog, QFontComboBox,
    QSlider, QFileDialog
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from pathlib import Path
from typing import Dict, Any

from config import UserSettings, config


class SettingsDialog(QDialog):
    """Settings/Preferences dialog"""

    settings_changed = pyqtSignal(dict)

    def __init__(self, settings: UserSettings, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.setMinimumSize(550, 450)

        self._settings = settings
        self._changes: Dict[str, Any] = {}

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self):
        layout = QVBoxLayout(self)

        # Tab widget
        tabs = QTabWidget()

        # General tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")

        # View tab
        view_tab = self._create_view_tab()
        tabs.addTab(view_tab, "View")

        # Editor tab
        editor_tab = self._create_editor_tab()
        tabs.addTab(editor_tab, "Editor")

        # Annotations tab
        annotations_tab = self._create_annotations_tab()
        tabs.addTab(annotations_tab, "Annotations")

        # Performance tab
        performance_tab = self._create_performance_tab()
        tabs.addTab(performance_tab, "Performance")

        layout.addWidget(tabs)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self._restore_btn = QPushButton("Restore Defaults")
        self._restore_btn.clicked.connect(self._restore_defaults)
        btn_layout.addWidget(self._restore_btn)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._apply_settings)
        btn_layout.addWidget(self._apply_btn)

        self._ok_btn = QPushButton("OK")
        self._ok_btn.clicked.connect(self._save_and_close)
        btn_layout.addWidget(self._ok_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(self._cancel_btn)

        layout.addLayout(btn_layout)

    def _create_general_tab(self) -> QWidget:
        """Create general settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItems(["System", "Light", "Dark"])
        theme_layout.addRow("Theme:", self._theme_combo)

        layout.addWidget(theme_group)

        # Startup
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)

        self._restore_session = QCheckBox("Restore last session on startup")
        startup_layout.addWidget(self._restore_session)

        self._check_updates = QCheckBox("Check for updates on startup")
        startup_layout.addWidget(self._check_updates)

        layout.addWidget(startup_group)

        # File handling
        file_group = QGroupBox("File Handling")
        file_layout = QVBoxLayout(file_group)

        self._confirm_close = QCheckBox("Confirm before closing unsaved documents")
        file_layout.addWidget(self._confirm_close)

        self._create_backup = QCheckBox("Create backup before saving")
        file_layout.addWidget(self._create_backup)

        layout.addWidget(file_group)

        layout.addStretch()
        return widget

    def _create_view_tab(self) -> QWidget:
        """Create view settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Default view
        view_group = QGroupBox("Default View Settings")
        view_layout = QFormLayout(view_group)

        self._default_zoom = QComboBox()
        self._default_zoom.addItems(["Fit Width", "Fit Page", "100%", "125%", "150%"])
        view_layout.addRow("Default zoom:", self._default_zoom)

        self._default_view_mode = QComboBox()
        self._default_view_mode.addItems(["Single Page", "Two Pages", "Continuous"])
        view_layout.addRow("View mode:", self._default_view_mode)

        layout.addWidget(view_group)

        # Display options
        display_group = QGroupBox("Display Options")
        display_layout = QVBoxLayout(display_group)

        self._show_rulers = QCheckBox("Show rulers")
        display_layout.addWidget(self._show_rulers)

        self._show_guides = QCheckBox("Show guides")
        display_layout.addWidget(self._show_guides)

        self._smooth_scrolling = QCheckBox("Smooth scrolling")
        self._smooth_scrolling.setChecked(True)
        display_layout.addWidget(self._smooth_scrolling)

        layout.addWidget(display_group)

        # Sidebar
        sidebar_group = QGroupBox("Sidebar")
        sidebar_layout = QFormLayout(sidebar_group)

        self._sidebar_width = QSpinBox()
        self._sidebar_width.setRange(100, 500)
        self._sidebar_width.setValue(250)
        sidebar_layout.addRow("Sidebar width:", self._sidebar_width)

        self._thumbnail_size = QComboBox()
        self._thumbnail_size.addItems(["Small", "Medium", "Large"])
        self._thumbnail_size.setCurrentText("Medium")
        sidebar_layout.addRow("Thumbnail size:", self._thumbnail_size)

        layout.addWidget(sidebar_group)

        layout.addStretch()
        return widget

    def _create_editor_tab(self) -> QWidget:
        """Create editor settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Auto-save
        autosave_group = QGroupBox("Auto-Save")
        autosave_layout = QFormLayout(autosave_group)

        self._autosave_enabled = QCheckBox("Enable auto-save")
        autosave_layout.addRow(self._autosave_enabled)

        self._autosave_interval = QSpinBox()
        self._autosave_interval.setRange(60, 3600)
        self._autosave_interval.setValue(300)
        self._autosave_interval.setSuffix(" seconds")
        autosave_layout.addRow("Interval:", self._autosave_interval)

        layout.addWidget(autosave_group)

        # Undo/Redo
        undo_group = QGroupBox("Undo/Redo")
        undo_layout = QFormLayout(undo_group)

        self._undo_levels = QSpinBox()
        self._undo_levels.setRange(10, 500)
        self._undo_levels.setValue(100)
        undo_layout.addRow("Undo levels:", self._undo_levels)

        layout.addWidget(undo_group)

        # OCR
        ocr_group = QGroupBox("OCR Settings")
        ocr_layout = QFormLayout(ocr_group)

        self._ocr_language = QComboBox()
        self._ocr_language.addItems([
            "English", "Spanish", "French", "German", "Italian",
            "Portuguese", "Chinese", "Japanese", "Korean"
        ])
        ocr_layout.addRow("Language:", self._ocr_language)

        self._ocr_dpi = QSpinBox()
        self._ocr_dpi.setRange(150, 600)
        self._ocr_dpi.setValue(300)
        ocr_layout.addRow("OCR DPI:", self._ocr_dpi)

        layout.addWidget(ocr_group)

        layout.addStretch()
        return widget

    def _create_annotations_tab(self) -> QWidget:
        """Create annotations settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Default colors
        colors_group = QGroupBox("Default Colors")
        colors_layout = QFormLayout(colors_group)

        self._highlight_color_btn = QPushButton()
        self._highlight_color_btn.setStyleSheet("background-color: #FFFF00")
        self._highlight_color_btn.clicked.connect(lambda: self._pick_color("highlight"))
        colors_layout.addRow("Highlight:", self._highlight_color_btn)

        self._text_color_btn = QPushButton()
        self._text_color_btn.setStyleSheet("background-color: #000000")
        self._text_color_btn.clicked.connect(lambda: self._pick_color("text"))
        colors_layout.addRow("Text:", self._text_color_btn)

        self._shape_color_btn = QPushButton()
        self._shape_color_btn.setStyleSheet("background-color: #FF0000")
        self._shape_color_btn.clicked.connect(lambda: self._pick_color("shape"))
        colors_layout.addRow("Shapes:", self._shape_color_btn)

        layout.addWidget(colors_group)

        # Default font
        font_group = QGroupBox("Default Font")
        font_layout = QFormLayout(font_group)

        self._default_font = QFontComboBox()
        font_layout.addRow("Font:", self._default_font)

        self._default_font_size = QSpinBox()
        self._default_font_size.setRange(6, 72)
        self._default_font_size.setValue(12)
        font_layout.addRow("Size:", self._default_font_size)

        layout.addWidget(font_group)

        # Default opacity
        opacity_group = QGroupBox("Default Opacity")
        opacity_layout = QFormLayout(opacity_group)

        self._default_opacity = QSlider(Qt.Orientation.Horizontal)
        self._default_opacity.setRange(10, 100)
        self._default_opacity.setValue(50)
        opacity_layout.addRow("Opacity:", self._default_opacity)

        layout.addWidget(opacity_group)

        layout.addStretch()
        return widget

    def _create_performance_tab(self) -> QWidget:
        """Create performance settings tab"""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Rendering
        render_group = QGroupBox("Rendering")
        render_layout = QFormLayout(render_group)

        self._render_dpi = QSpinBox()
        self._render_dpi.setRange(72, 300)
        self._render_dpi.setValue(150)
        render_layout.addRow("Render DPI:", self._render_dpi)

        self._gpu_acceleration = QCheckBox("Enable GPU acceleration")
        self._gpu_acceleration.setChecked(True)
        render_layout.addRow(self._gpu_acceleration)

        layout.addWidget(render_group)

        # Cache
        cache_group = QGroupBox("Cache")
        cache_layout = QFormLayout(cache_group)

        self._page_cache = QSpinBox()
        self._page_cache.setRange(5, 50)
        self._page_cache.setValue(10)
        cache_layout.addRow("Page cache size:", self._page_cache)

        self._thumbnail_cache = QSpinBox()
        self._thumbnail_cache.setRange(50, 500)
        self._thumbnail_cache.setValue(100)
        cache_layout.addRow("Thumbnail cache:", self._thumbnail_cache)

        clear_cache_btn = QPushButton("Clear Cache")
        clear_cache_btn.clicked.connect(self._clear_cache)
        cache_layout.addRow(clear_cache_btn)

        layout.addWidget(cache_group)

        layout.addStretch()
        return widget

    def _pick_color(self, color_type: str):
        """Open color picker"""
        color = QColorDialog.getColor()
        if color.isValid():
            btn = {
                "highlight": self._highlight_color_btn,
                "text": self._text_color_btn,
                "shape": self._shape_color_btn
            }.get(color_type)
            if btn:
                btn.setStyleSheet(f"background-color: {color.name()}")

    def _clear_cache(self):
        """Clear application cache"""
        from utils.file_utils import clean_temp_files
        clean_temp_files(0)

    def _load_settings(self):
        """Load current settings into UI"""
        # Theme
        theme_map = {"system": 0, "light": 1, "dark": 2}
        self._theme_combo.setCurrentIndex(theme_map.get(self._settings.theme, 0))

        # General
        self._restore_session.setChecked(self._settings.restore_last_session)
        self._confirm_close.setChecked(self._settings.confirm_close_unsaved)
        self._autosave_enabled.setChecked(self._settings.autosave_enabled)
        self._autosave_interval.setValue(self._settings.autosave_interval)

        # View
        self._sidebar_width.setValue(self._settings.sidebar_width)
        self._show_rulers.setChecked(self._settings.show_rulers)
        self._show_guides.setChecked(self._settings.show_guides)

        # Annotations
        self._highlight_color_btn.setStyleSheet(
            f"background-color: {self._settings.default_highlight_color}"
        )
        self._text_color_btn.setStyleSheet(
            f"background-color: {self._settings.default_text_color}"
        )
        self._shape_color_btn.setStyleSheet(
            f"background-color: {self._settings.default_shape_color}"
        )
        self._default_font_size.setValue(self._settings.default_font_size)

        # Performance
        self._gpu_acceleration.setChecked(self._settings.enable_gpu_acceleration)
        self._page_cache.setValue(self._settings.page_cache_size)
        self._thumbnail_cache.setValue(self._settings.thumbnail_cache_size)

    def _gather_settings(self) -> Dict[str, Any]:
        """Gather settings from UI"""
        theme_map = {0: "system", 1: "light", 2: "dark"}

        return {
            "theme": theme_map.get(self._theme_combo.currentIndex(), "system"),
            "restore_last_session": self._restore_session.isChecked(),
            "confirm_close_unsaved": self._confirm_close.isChecked(),
            "autosave_enabled": self._autosave_enabled.isChecked(),
            "autosave_interval": self._autosave_interval.value(),
            "sidebar_width": self._sidebar_width.value(),
            "show_rulers": self._show_rulers.isChecked(),
            "show_guides": self._show_guides.isChecked(),
            "default_font_size": self._default_font_size.value(),
            "enable_gpu_acceleration": self._gpu_acceleration.isChecked(),
            "page_cache_size": self._page_cache.value(),
            "thumbnail_cache_size": self._thumbnail_cache.value(),
        }

    def _apply_settings(self):
        """Apply settings without closing"""
        changes = self._gather_settings()

        for key, value in changes.items():
            if hasattr(self._settings, key):
                setattr(self._settings, key, value)

        self.settings_changed.emit(changes)

    def _save_and_close(self):
        """Save settings and close dialog"""
        self._apply_settings()
        self._settings.save(config.SETTINGS_PATH)
        self.accept()

    def _restore_defaults(self):
        """Restore default settings"""
        self._settings = UserSettings()
        self._load_settings()
