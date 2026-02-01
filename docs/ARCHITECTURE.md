# Ultra PDF Editor - Architecture Documentation

This document describes the software architecture, design decisions, and implementation details of Ultra PDF Editor.

## Table of Contents

1. [System Overview](#system-overview)
2. [Architecture Principles](#architecture-principles)
3. [Layer Architecture](#layer-architecture)
4. [Component Diagrams](#component-diagrams)
5. [Core Components](#core-components)
6. [Data Flow](#data-flow)
7. [Design Patterns](#design-patterns)
8. [Technology Stack](#technology-stack)
9. [Performance Considerations](#performance-considerations)
10. [Security Architecture](#security-architecture)
11. [Extension Points](#extension-points)

---

## System Overview

Ultra PDF Editor is a desktop application for PDF manipulation, built with a layered architecture that separates concerns between business logic and user interface.

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Ultra PDF Editor                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Presentation Layer                     │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────┐  │   │
│  │  │MainWindow │ │ PDFViewer │ │  Sidebar  │ │ Dialogs │  │   │
│  │  └───────────┘ └───────────┘ └───────────┘ └─────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Business Layer                        │   │
│  │  ┌─────────────┐ ┌────────────┐ ┌──────────────────┐    │   │
│  │  │ PDFDocument │ │ Operations │ │    Converters    │    │   │
│  │  └─────────────┘ └────────────┘ └──────────────────┘    │   │
│  └─────────────────────────────────────────────────────────┘   │
│                              │                                  │
│                              ▼                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                   Infrastructure Layer                   │   │
│  │  ┌─────────┐ ┌─────────┐ ┌──────────┐ ┌─────────────┐   │   │
│  │  │ PyMuPDF │ │ Pillow  │ │Tesseract │ │python-docx  │   │   │
│  │  └─────────┘ └─────────┘ └──────────┘ └─────────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Architecture Principles

### 1. Separation of Concerns

Each component has a single, well-defined responsibility:
- **UI components** handle user interaction only
- **Business logic** operates independently of UI
- **Data access** is abstracted behind interfaces

### 2. Dependency Inversion

High-level modules don't depend on low-level modules:
```
MainWindow → PDFDocument (interface) → fitz.Document (implementation)
```

### 3. Single Source of Truth

- One `PDFDocument` instance per open file
- State changes flow through defined channels
- UI reflects document state, not vice versa

### 4. Fail-Safe Design

- All operations validate preconditions
- Errors are caught and reported gracefully
- Temporary files are cleaned up automatically

---

## Layer Architecture

### Presentation Layer (`ui/`)

Handles all user interface concerns using PyQt6.

```
ui/
├── main_window.py      # Application shell and coordination
├── pdf_viewer.py       # PDF rendering and interaction
├── sidebar.py          # Side panels (thumbnails, bookmarks)
├── toolbar.py          # Toolbar widgets
└── dialogs/            # Modal dialog windows
    ├── merge_dialog.py
    ├── split_dialog.py
    ├── settings_dialog.py
    └── ...
```

**Responsibilities:**
- Render user interface
- Handle user input events
- Display feedback and errors
- Coordinate between UI components

**Rules:**
- No direct PDF manipulation
- No file I/O (except via document model)
- Communicate via signals/slots

### Business Layer (`core/`)

Contains all PDF manipulation logic.

```
core/
├── pdf_document.py     # Main document model
├── operations/         # Stateless operations
│   ├── merge.py
│   ├── split.py
│   ├── ocr.py
│   └── compress.py
└── converters/         # Format conversion
    ├── to_word.py
    ├── to_image.py
    └── to_excel.py
```

**Responsibilities:**
- PDF loading and saving
- Page manipulation
- Annotation management
- Format conversion

**Rules:**
- No UI dependencies
- No PyQt6 imports
- Pure Python with type hints

### Infrastructure Layer

Third-party libraries providing core capabilities:

| Library | Purpose |
|---------|---------|
| PyMuPDF (fitz) | PDF rendering, manipulation |
| pypdf | PDF metadata, merging |
| pikepdf | Advanced PDF operations |
| Pillow | Image processing |
| pytesseract | OCR integration |
| python-docx | Word conversion |

---

## Component Diagrams

### Main Window Structure

```
MainWindow
├── MenuBar
│   ├── FileMenu
│   ├── EditMenu
│   ├── ViewMenu
│   ├── ToolsMenu
│   ├── AnnotationsMenu
│   └── HelpMenu
├── MainToolbar
│   ├── FileActions (new, open, save)
│   ├── EditActions (undo, redo)
│   ├── ZoomControls
│   └── PageNavigation
├── AnnotationToolbar
│   ├── SelectionTools
│   ├── MarkupTools
│   ├── ShapeTools
│   └── DrawingTools
├── CentralWidget (QSplitter)
│   ├── Sidebar
│   │   ├── ThumbnailPanel
│   │   ├── BookmarkPanel
│   │   └── AnnotationPanel
│   └── PDFViewer
│       ├── ScrollArea
│       └── PageWidgets[]
└── StatusBar
    ├── ToolModeLabel
    ├── PageInfoLabel
    └── ZoomLabel
```

### Document Model

```
PDFDocument
├── Properties
│   ├── _doc: fitz.Document
│   ├── _filepath: Path
│   ├── _is_modified: bool
│   └── _password: str
├── Document Operations
│   ├── open()
│   ├── create_new()
│   ├── save()
│   └── close()
├── Page Operations
│   ├── get_page()
│   ├── add_blank_page()
│   ├── delete_page()
│   ├── rotate_page()
│   └── move_page()
├── Content Operations
│   ├── get_text()
│   ├── search_text()
│   ├── add_text()
│   └── insert_image()
├── Annotation Operations
│   ├── add_highlight()
│   ├── add_text_annotation()
│   ├── add_shape()
│   └── delete_annotation()
└── Security Operations
    ├── encrypt()
    └── decrypt()
```

---

## Core Components

### PDFDocument (`core/pdf_document.py`)

The central model class managing PDF state.

**State Management:**
```python
class PDFDocument:
    def __init__(self):
        self._doc: Optional[fitz.Document] = None  # PyMuPDF document
        self._filepath: Optional[Path] = None       # Current file path
        self._is_modified: bool = False             # Unsaved changes flag
        self._password: Optional[str] = None        # Document password
```

**Key Design Decisions:**

1. **Explicit None checks**: Uses `is None` instead of falsy checks because `fitz.Document` with 0 pages evaluates to `False`.

2. **Modification tracking**: All mutating operations set `_is_modified = True`.

3. **Resource management**: `close()` releases resources and cleans temp files.

### PDFViewer (`ui/pdf_viewer.py`)

High-performance PDF rendering widget.

**Architecture:**
```
PDFViewer (QScrollArea)
└── ContentWidget (QWidget)
    └── PageWidgets[] (QLabel)
        └── Rendered Pixmaps
```

**Rendering Pipeline:**
1. Calculate visible pages
2. Queue render tasks
3. Render pages in background
4. Cache rendered pixmaps
5. Display on screen

**Page Caching:**
```python
_page_cache: Dict[Tuple[int, float], QPixmap]  # (page_num, zoom) → pixmap
```

### Sidebar (`ui/sidebar.py`)

Tabbed panel for document navigation.

**Components:**
- `ThumbnailPanel`: Page preview grid
- `BookmarkPanel`: TOC tree view
- `AnnotationPanel`: Annotation list

**Communication:**
```python
# Signals
page_selected = pyqtSignal(int)        # User clicked thumbnail
bookmark_clicked = pyqtSignal(int)      # User clicked bookmark
annotation_selected = pyqtSignal(object) # User clicked annotation
```

---

## Data Flow

### Document Loading Flow

```
User clicks Open
        │
        ▼
┌───────────────────┐
│ QFileDialog       │
│ (select file)     │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ PDFDocument.open()│
│ - Validate file   │
│ - Load with fitz  │
│ - Check password  │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ _load_to_viewer() │
│ - Set document    │
│ - Update sidebar  │
│ - Render pages    │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Update UI state   │
│ - Window title    │
│ - Enable actions  │
│ - Status bar      │
└───────────────────┘
```

### Annotation Creation Flow

```
User selects Highlight tool
        │
        ▼
┌───────────────────┐
│ Set tool mode     │
│ Update cursor     │
└───────────────────┘
        │
User drags on page
        │
        ▼
┌───────────────────┐
│ PageWidget        │
│ mousePressEvent   │
│ mouseMoveEvent    │
│ mouseReleaseEvent │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ PDFDocument       │
│ .add_highlight()  │
│ - Create annot    │
│ - Set modified    │
└───────────────────┘
        │
        ▼
┌───────────────────┐
│ Re-render page    │
│ Update sidebar    │
└───────────────────┘
```

### Save Flow

```
User clicks Save
        │
        ▼
┌───────────────────────┐
│ Check is_modified     │
│ Check filepath        │
└───────────────────────┘
        │
        ├── No filepath → Save As dialog
        │
        ▼
┌───────────────────────┐
│ PDFDocument.save()    │
│ - Prepare options     │
│ - Write to temp       │
│ - Rename to target    │
│ - Clear modified flag │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│ Update UI             │
│ - Window title        │
│ - Status message      │
└───────────────────────┘
```

---

## Design Patterns

### Model-View-Controller (MVC)

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│    Model    │     │    View     │     │ Controller  │
│             │     │             │     │             │
│ PDFDocument │◄────│  PDFViewer  │◄────│ MainWindow  │
│             │     │  Sidebar    │     │             │
│             │────►│  Dialogs    │────►│             │
└─────────────┘     └─────────────┘     └─────────────┘
```

### Command Pattern (Undo/Redo)

```python
class Command(ABC):
    @abstractmethod
    def execute(self): pass

    @abstractmethod
    def undo(self): pass

class AddPageCommand(Command):
    def __init__(self, document, page_index):
        self.document = document
        self.page_index = page_index

    def execute(self):
        self.document.add_blank_page(index=self.page_index)

    def undo(self):
        self.document.delete_page(self.page_index)
```

### Observer Pattern (Signals/Slots)

```python
# In PDFViewer
page_changed = pyqtSignal(int)
zoom_changed = pyqtSignal(float)

# In MainWindow
self._viewer.page_changed.connect(self._on_page_changed)
self._viewer.zoom_changed.connect(self._on_zoom_changed)
```

### Factory Pattern (Annotations)

```python
class AnnotationFactory:
    @staticmethod
    def create(annot_type: str, **kwargs) -> Annotation:
        creators = {
            'highlight': HighlightAnnotation,
            'underline': UnderlineAnnotation,
            'text_box': TextBoxAnnotation,
            'rectangle': RectangleAnnotation,
        }
        return creators[annot_type](**kwargs)
```

### Strategy Pattern (Converters)

```python
class Converter(ABC):
    @abstractmethod
    def convert(self, input_path, output_path): pass

class WordConverter(Converter):
    def convert(self, input_path, output_path):
        # Word-specific conversion logic
        pass

class ImageConverter(Converter):
    def convert(self, input_path, output_path):
        # Image-specific conversion logic
        pass
```

---

## Technology Stack

### Core Technologies

| Component | Technology | Version | Purpose |
|-----------|------------|---------|---------|
| Language | Python | 3.10+ | Primary language |
| GUI | PyQt6 | 6.6+ | User interface |
| PDF Engine | PyMuPDF | 1.23+ | PDF manipulation |

### Libraries by Function

**PDF Processing:**
- `PyMuPDF` (fitz): Rendering, annotations, forms
- `pypdf`: Merging, splitting, metadata
- `pikepdf`: Advanced manipulation, repair
- `reportlab`: PDF generation

**Document Conversion:**
- `python-docx`: Word documents
- `openpyxl`: Excel spreadsheets
- `python-pptx`: PowerPoint
- `beautifulsoup4`: HTML parsing

**Image Processing:**
- `Pillow`: Image manipulation
- `pdf2image`: PDF to images

**OCR:**
- `pytesseract`: Tesseract wrapper

**Security:**
- `cryptography`: Encryption support

---

## Performance Considerations

### Page Rendering

**Challenge:** Large PDFs with high-resolution rendering.

**Solutions:**
1. **Lazy rendering**: Only render visible pages
2. **Page caching**: Cache rendered pixmaps
3. **Background rendering**: Render in worker threads
4. **Progressive loading**: Low-res preview, then high-res

```python
class RenderWorker(QThread):
    page_rendered = pyqtSignal(int, QPixmap)

    def run(self):
        pixmap = self.render_page(self.page_num, self.zoom)
        self.page_rendered.emit(self.page_num, pixmap)
```

### Memory Management

**Strategies:**
1. **LRU cache** for page pixmaps
2. **Weak references** for thumbnails
3. **Explicit cleanup** on document close
4. **Configurable cache sizes**

```python
# Cache configuration
THUMBNAIL_CACHE_SIZE = 100  # pages
PAGE_CACHE_SIZE = 10        # pages at current zoom
```

### Large Document Handling

**Optimizations:**
1. **Thumbnail generation**: On-demand, not upfront
2. **Search**: Use PDF internal search, not text extraction
3. **Batch operations**: Process in chunks with progress
4. **Memory mapping**: Let OS manage large files

---

## Security Architecture

### Input Validation

```python
def open(self, filepath: Union[str, Path], password: Optional[str] = None):
    filepath = Path(filepath)

    # Validate file exists
    if not filepath.exists():
        raise FileNotFoundError(f"File not found: {filepath}")

    # Validate extension
    if filepath.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {filepath.suffix}")

    # Safe file opening
    try:
        self._doc = fitz.open(str(filepath))
    except Exception as e:
        raise ValueError(f"Invalid PDF file: {e}")
```

### Password Handling

```python
# Passwords are stored only in memory, never persisted
self._password: Optional[str] = None

# Cleared on document close
def close(self):
    self._password = None
```

### Temporary File Security

```python
# Secure temp file creation
with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
    tmp_path = tmp.name

try:
    # Use temp file
    self._doc.save(tmp_path)
    shutil.move(tmp_path, target_path)
finally:
    # Ensure cleanup
    if os.path.exists(tmp_path):
        os.remove(tmp_path)
```

---

## Extension Points

### Adding New Annotation Types

1. Create annotation class in `annotations/`
2. Register with `AnnotationFactory`
3. Add tool button in `AnnotationToolbar`
4. Implement rendering in `PageWidget`

### Adding New Converters

1. Create converter in `core/converters/`
2. Implement `Converter` interface
3. Register in export menu
4. Add file filter to dialog

### Adding New Operations

1. Create operation in `core/operations/`
2. Add method to `PDFDocument` if needed
3. Create menu action
4. Add keyboard shortcut (optional)

### Plugin Architecture (Future)

```python
# Proposed plugin interface
class Plugin(ABC):
    @property
    @abstractmethod
    def name(self) -> str: pass

    @property
    @abstractmethod
    def version(self) -> str: pass

    @abstractmethod
    def initialize(self, app: Application): pass

    @abstractmethod
    def shutdown(self): pass
```

---

## Future Architecture Considerations

### Multi-Document Interface

```
MainWindow
├── TabWidget
│   ├── DocumentTab[0]
│   │   ├── PDFViewer
│   │   └── PDFDocument
│   ├── DocumentTab[1]
│   │   ├── PDFViewer
│   │   └── PDFDocument
│   └── ...
└── SharedSidebar
```

### Async Operations

```python
async def ocr_document(self, pages: List[int]):
    tasks = [self._ocr_page(page) for page in pages]
    results = await asyncio.gather(*tasks)
    return results
```

### Remote Storage Integration

```python
class StorageBackend(ABC):
    @abstractmethod
    async def read(self, path: str) -> bytes: pass

    @abstractmethod
    async def write(self, path: str, data: bytes): pass

class LocalStorage(StorageBackend): ...
class CloudStorage(StorageBackend): ...  # Future
```

---

*This architecture is designed for maintainability, extensibility, and performance while keeping the codebase accessible to contributors.*
