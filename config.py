"""
Ultra PDF Editor - Configuration
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import List, Optional
from enum import Enum


class Theme(Enum):
    LIGHT = "light"
    DARK = "dark"
    SYSTEM = "system"


class ViewMode(Enum):
    SINGLE_PAGE = "single"
    TWO_PAGE = "two_page"
    CONTINUOUS = "continuous"


class ZoomMode(Enum):
    FIT_PAGE = "fit_page"
    FIT_WIDTH = "fit_width"
    CUSTOM = "custom"


@dataclass
class AppConfig:
    """Application configuration settings"""

    # Application Info
    APP_NAME: str = "Ultra PDF Editor"
    APP_VERSION: str = "1.0.0"
    APP_AUTHOR: str = "Ultra PDF Team"

    # Paths
    CONFIG_DIR: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor")
    RECENT_FILES_PATH: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor" / "recent_files.json")
    SETTINGS_PATH: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor" / "settings.json")
    TEMP_DIR: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor" / "temp")
    AUTOSAVE_DIR: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor" / "autosave")
    STAMPS_DIR: Path = field(default_factory=lambda: Path.home() / ".ultra_pdf_editor" / "stamps")

    # Window Settings
    WINDOW_WIDTH: int = 1400
    WINDOW_HEIGHT: int = 900
    WINDOW_MIN_WIDTH: int = 800
    WINDOW_MIN_HEIGHT: int = 600
    SIDEBAR_WIDTH: int = 250

    # View Settings
    DEFAULT_ZOOM: float = 100.0
    MIN_ZOOM: float = 10.0
    MAX_ZOOM: float = 800.0
    ZOOM_STEP: float = 25.0
    DEFAULT_VIEW_MODE: ViewMode = ViewMode.CONTINUOUS
    DEFAULT_ZOOM_MODE: ZoomMode = ZoomMode.FIT_WIDTH

    # Theme
    THEME: Theme = Theme.SYSTEM

    # Editor Settings
    MAX_RECENT_FILES: int = 20
    AUTOSAVE_INTERVAL: int = 300  # seconds (5 minutes)
    UNDO_HISTORY_SIZE: int = 100

    # Thumbnail Settings
    THUMBNAIL_WIDTH: int = 150
    THUMBNAIL_HEIGHT: int = 200
    THUMBNAIL_QUALITY: int = 2  # DPI multiplier for thumbnails

    # Rendering Settings
    RENDER_DPI: int = 150
    HIGH_QUALITY_DPI: int = 300

    # OCR Settings
    OCR_LANGUAGE: str = "eng"
    OCR_DPI: int = 300

    # Compression Settings
    IMAGE_QUALITY: int = 85  # JPEG quality for compression

    # Annotation Defaults
    HIGHLIGHT_COLOR: str = "#FFFF00"  # Yellow
    HIGHLIGHT_OPACITY: float = 0.5
    TEXT_BOX_FONT: str = "Arial"
    TEXT_BOX_SIZE: int = 12
    SHAPE_STROKE_COLOR: str = "#FF0000"  # Red
    SHAPE_FILL_COLOR: str = "#FFFFFF"
    SHAPE_STROKE_WIDTH: int = 2

    # Watermark Defaults
    WATERMARK_OPACITY: float = 0.3
    WATERMARK_FONT_SIZE: int = 48
    WATERMARK_ROTATION: int = 45

    # Export Settings
    DEFAULT_IMAGE_FORMAT: str = "PNG"
    DEFAULT_IMAGE_DPI: int = 150

    # Keyboard Shortcuts
    SHORTCUTS: dict = field(default_factory=lambda: {
        "open": "Ctrl+O",
        "save": "Ctrl+S",
        "save_as": "Ctrl+Shift+S",
        "close": "Ctrl+W",
        "print": "Ctrl+P",
        "undo": "Ctrl+Z",
        "redo": "Ctrl+Y",
        "cut": "Ctrl+X",
        "copy": "Ctrl+C",
        "paste": "Ctrl+V",
        "delete": "Delete",
        "select_all": "Ctrl+A",
        "find": "Ctrl+F",
        "find_replace": "Ctrl+H",
        "zoom_in": "Ctrl++",
        "zoom_out": "Ctrl+-",
        "zoom_fit": "Ctrl+0",
        "fullscreen": "F11",
        "next_page": "Page_Down",
        "prev_page": "Page_Up",
        "first_page": "Ctrl+Home",
        "last_page": "Ctrl+End",
        "rotate_cw": "Ctrl+R",
        "rotate_ccw": "Ctrl+Shift+R",
        "merge": "Ctrl+M",
        "split": "Ctrl+Shift+M",
        "properties": "Ctrl+D",
    })

    def __post_init__(self):
        """Ensure directories exist"""
        self.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.TEMP_DIR.mkdir(parents=True, exist_ok=True)
        self.AUTOSAVE_DIR.mkdir(parents=True, exist_ok=True)
        self.STAMPS_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class UserSettings:
    """User-modifiable settings that persist between sessions"""

    # Window state
    window_geometry: Optional[bytes] = None
    window_state: Optional[bytes] = None
    sidebar_visible: bool = True
    sidebar_width: int = 250
    toolbar_visible: bool = True
    statusbar_visible: bool = True

    # View preferences
    theme: str = "system"
    zoom_level: float = 100.0
    view_mode: str = "continuous"
    show_rulers: bool = False
    show_guides: bool = False

    # Editor preferences
    autosave_enabled: bool = True
    autosave_interval: int = 300
    restore_last_session: bool = True
    confirm_close_unsaved: bool = True

    # Recent files
    recent_files: List[str] = field(default_factory=list)
    last_opened_directory: str = ""
    last_saved_directory: str = ""

    # Annotation preferences
    default_highlight_color: str = "#FFFF00"
    default_text_color: str = "#000000"
    default_shape_color: str = "#FF0000"
    default_font_family: str = "Arial"
    default_font_size: int = 12

    # OCR preferences
    ocr_language: str = "eng"
    ocr_auto_detect: bool = True

    # Export preferences
    default_export_format: str = "PDF"
    default_image_format: str = "PNG"
    default_image_dpi: int = 150

    # Performance
    enable_gpu_acceleration: bool = True
    thumbnail_cache_size: int = 100  # Number of thumbnails to cache
    page_cache_size: int = 10  # Number of rendered pages to cache

    @classmethod
    def load(cls, path: Path) -> 'UserSettings':
        """Load settings from JSON file"""
        if path.exists():
            try:
                import base64
                with open(path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                # Convert base64 strings back to bytes for window geometry/state
                if data.get('window_geometry') and isinstance(data['window_geometry'], str):
                    data['window_geometry'] = base64.b64decode(data['window_geometry'])
                if data.get('window_state') and isinstance(data['window_state'], str):
                    data['window_state'] = base64.b64decode(data['window_state'])
                return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
            except (json.JSONDecodeError, TypeError, ValueError):
                pass
        return cls()

    def save(self, path: Path):
        """Save settings to JSON file"""
        import base64
        path.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(self)
        # Convert bytes to base64 for JSON serialization
        if data.get('window_geometry') and isinstance(data['window_geometry'], bytes):
            data['window_geometry'] = base64.b64encode(data['window_geometry']).decode('utf-8')
        if data.get('window_state') and isinstance(data['window_state'], bytes):
            data['window_state'] = base64.b64encode(data['window_state']).decode('utf-8')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)

    def add_recent_file(self, filepath: str, max_files: int = 20):
        """Add a file to recent files list"""
        filepath = os.path.abspath(filepath)
        if filepath in self.recent_files:
            self.recent_files.remove(filepath)
        self.recent_files.insert(0, filepath)
        self.recent_files = self.recent_files[:max_files]

    def clear_recent_files(self):
        """Clear recent files list"""
        self.recent_files = []


# File type definitions
SUPPORTED_PDF_EXTENSIONS = ['.pdf']

SUPPORTED_IMAGE_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.bmp', '.gif', '.tiff', '.tif', '.webp']

SUPPORTED_DOCUMENT_EXTENSIONS = ['.docx', '.doc', '.xlsx', '.xls', '.pptx', '.ppt', '.html', '.htm', '.txt', '.rtf']

EXPORT_IMAGE_FORMATS = ['PNG', 'JPEG', 'TIFF', 'BMP', 'GIF', 'WEBP']

EXPORT_DOCUMENT_FORMATS = ['DOCX', 'XLSX', 'PPTX', 'HTML', 'TXT']

# Stamp presets
DEFAULT_STAMPS = [
    {"name": "Approved", "text": "APPROVED", "color": "#00AA00"},
    {"name": "Rejected", "text": "REJECTED", "color": "#FF0000"},
    {"name": "Draft", "text": "DRAFT", "color": "#FFA500"},
    {"name": "Confidential", "text": "CONFIDENTIAL", "color": "#FF0000"},
    {"name": "Final", "text": "FINAL", "color": "#0000FF"},
    {"name": "For Review", "text": "FOR REVIEW", "color": "#800080"},
    {"name": "Not Approved", "text": "NOT APPROVED", "color": "#FF0000"},
    {"name": "Void", "text": "VOID", "color": "#808080"},
    {"name": "Preliminary", "text": "PRELIMINARY", "color": "#FFA500"},
    {"name": "Information Only", "text": "INFORMATION ONLY", "color": "#0000FF"},
]

# Paper sizes (in points, 1 point = 1/72 inch)
PAPER_SIZES = {
    "Letter": (612, 792),
    "Legal": (612, 1008),
    "A4": (595, 842),
    "A3": (842, 1191),
    "A5": (420, 595),
    "B5": (499, 709),
    "Tabloid": (792, 1224),
    "Executive": (522, 756),
}

# Global config instance
config = AppConfig()
