# Ultra PDF Editor

A powerful, professional-grade PDF editor built with Python and PyQt6. Designed for users who need comprehensive PDF manipulation capabilities without cloud dependencies.

![Python](https://img.shields.io/badge/Python-3.10+-blue.svg)
![PyQt6](https://img.shields.io/badge/PyQt6-6.6+-green.svg)
![License](https://img.shields.io/badge/License-MIT-yellow.svg)
![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20macOS%20%7C%20Linux-lightgrey.svg)

## Features

### Core Document Operations
- **Open/Save PDF files** with full format preservation
- **Create new PDFs** from scratch
- **Multiple document tabs** for simultaneous editing
- **Auto-save & recovery** to prevent data loss
- **Drag & drop** file support

### Page Management
- Add, insert, delete, and duplicate pages
- Reorder pages via drag & drop
- Rotate pages (90°, 180°, 270°)
- Crop and resize pages
- Extract pages to new PDF
- Page thumbnails sidebar with quick navigation

### Merge & Split
- Merge multiple PDFs into a single document
- Split PDF by page count or custom ranges
- Split by bookmarks
- Batch merge operations

### Annotations & Markup
- **Text markup**: Highlight, underline, strikethrough
- **Sticky notes** and comments
- **Text boxes** with customizable fonts
- **Shapes**: Rectangle, circle, line, arrow, polygon
- **Freehand drawing** tools
- **Stamps**: Approved, Draft, Confidential, and custom stamps
- Annotation color and opacity controls

### Forms
- Fill existing PDF forms
- Create fillable forms with:
  - Text fields
  - Checkboxes and radio buttons
  - Dropdown lists
  - Date pickers
  - Signature fields
- Form data import/export (FDF, XFDF)

### Security
- **Password protection** (user and owner passwords)
- **Encryption**: 128-bit and 256-bit AES
- **Permission controls**: Print, copy, edit restrictions
- **Redaction tools** for permanent content removal
- **Digital signatures** support

### OCR (Optical Character Recognition)
- Convert scanned PDFs to searchable text
- Multiple language support (30+ languages)
- Batch OCR processing

### Conversion
| From PDF | To PDF |
|----------|--------|
| Word (.docx) | Word (.docx) |
| Excel (.xlsx) | Excel (.xlsx) |
| PowerPoint (.pptx) | Images (PNG, JPG, TIFF) |
| Images | HTML |
| HTML | Plain Text |
| PDF/A (archival) | |

### View & Navigation
- Zoom controls (fit page, fit width, custom %)
- Single page, two-page, and continuous scroll views
- Full-screen mode
- Dark mode / Light mode / System theme
- Bookmarks panel
- Search within document

## System Requirements

### Minimum Requirements
- **OS**: Windows 10, macOS 10.14+, or Linux (Ubuntu 20.04+)
- **Python**: 3.10 or higher
- **RAM**: 4 GB
- **Storage**: 500 MB free space

### Recommended Requirements
- **RAM**: 8 GB or more
- **Storage**: 1 GB free space (for OCR language packs)
- **Display**: 1920x1080 or higher resolution

### For OCR Features
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) must be installed separately
- Language packs for non-English OCR

## Installation

### Using uv (Recommended)

```bash
# Clone the repository
git clone https://github.com/your-org/ultra-pdf-editor.git
cd ultra-pdf-editor

# Install dependencies with uv
uv sync

# Run the application
uv run python Ultra_PDF_Editor.py
```

### Using pip

```bash
# Clone the repository
git clone https://github.com/your-org/ultra-pdf-editor.git
cd ultra-pdf-editor

# Create virtual environment
python -m venv .venv

# Activate virtual environment
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e .

# Run the application
python Ultra_PDF_Editor.py
```

### Installing Tesseract (for OCR)

**Windows:**
```bash
# Using chocolatey
choco install tesseract

# Or download installer from:
# https://github.com/UB-Mannheim/tesseract/wiki
```

**macOS:**
```bash
brew install tesseract
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt install tesseract-ocr
# For additional languages:
sudo apt install tesseract-ocr-fra tesseract-ocr-deu  # French, German, etc.
```

## Quick Start

### Opening a PDF
```
File → Open (Ctrl+O)
```
Or drag and drop a PDF file onto the application window.

### Creating a New Document
```
File → New (Ctrl+N)
```

### Adding Annotations
1. Select an annotation tool from the toolbar
2. Click and drag on the page to create the annotation
3. Adjust properties in the sidebar

### Merging PDFs
```
Tools → Merge PDFs
```
Select multiple files and arrange their order.

### Converting to Word
```
File → Export → Microsoft Word (.docx)
```

## Keyboard Shortcuts

| Action | Windows/Linux | macOS |
|--------|---------------|-------|
| New Document | Ctrl+N | Cmd+N |
| Open | Ctrl+O | Cmd+O |
| Save | Ctrl+S | Cmd+S |
| Save As | Ctrl+Shift+S | Cmd+Shift+S |
| Close | Ctrl+W | Cmd+W |
| Print | Ctrl+P | Cmd+P |
| Undo | Ctrl+Z | Cmd+Z |
| Redo | Ctrl+Y | Cmd+Shift+Z |
| Find | Ctrl+F | Cmd+F |
| Zoom In | Ctrl++ | Cmd++ |
| Zoom Out | Ctrl+- | Cmd+- |
| Fit Page | Ctrl+0 | Cmd+0 |
| Fit Width | Ctrl+1 | Cmd+1 |
| Full Screen | F11 | Cmd+Ctrl+F |
| Next Page | Page Down | Page Down |
| Previous Page | Page Up | Page Up |

## Project Structure

```
ultra-pdf-editor/
├── Ultra_PDF_Editor.py     # Application entry point
├── config.py               # Configuration and settings
├── pyproject.toml          # Project dependencies
│
├── core/                   # Core PDF operations
│   ├── pdf_document.py     # Document model
│   ├── operations/         # PDF operations (merge, split, OCR)
│   └── converters/         # Format converters
│
├── ui/                     # User interface
│   ├── main_window.py      # Main application window
│   ├── pdf_viewer.py       # PDF rendering widget
│   ├── sidebar.py          # Side panels
│   ├── toolbar.py          # Toolbars
│   └── dialogs/            # Dialog windows
│
├── annotations/            # Annotation system
├── forms/                  # Form handling
└── utils/                  # Utilities
```

## Configuration

User settings are stored at:
- **Windows**: `%APPDATA%\UltraPDF\settings.json`
- **macOS**: `~/Library/Application Support/UltraPDF/settings.json`
- **Linux**: `~/.config/UltraPDF/settings.json`

### Available Settings

```json
{
  "theme": "system",          // "light", "dark", or "system"
  "zoom_level": 100.0,
  "view_mode": "continuous",  // "single", "two_page", or "continuous"
  "autosave_enabled": true,
  "autosave_interval": 300,   // seconds
  "ocr_language": "eng",
  "default_image_dpi": 150
}
```

## Dependencies

| Package | Purpose |
|---------|---------|
| PyQt6 | GUI framework |
| PyMuPDF (fitz) | PDF rendering & manipulation |
| pypdf | PDF merging, splitting, metadata |
| pikepdf | Advanced PDF manipulation |
| reportlab | PDF generation |
| Pillow | Image processing |
| pytesseract | OCR integration |
| python-docx | Word document conversion |
| openpyxl | Excel conversion |
| cryptography | Encryption support |

## Troubleshooting

### Common Issues

**Application won't start**
- Ensure Python 3.10+ is installed
- Run `uv sync` to install all dependencies
- Check for error messages in the terminal

**OCR not working**
- Verify Tesseract is installed: `tesseract --version`
- Install required language packs
- Check Tesseract is in your system PATH

**PDF won't open**
- File may be corrupted - try opening in another PDF reader
- File may be encrypted - enter the password when prompted
- Check file permissions

**Slow performance with large PDFs**
- Reduce thumbnail cache size in settings
- Close unused document tabs
- Disable GPU acceleration if experiencing graphics issues

### Getting Help

1. Check the [User Guide](docs/USER_GUIDE.md) for detailed instructions
2. Search [existing issues](https://github.com/your-org/ultra-pdf-editor/issues)
3. Open a new issue with:
   - Your OS and Python version
   - Steps to reproduce the problem
   - Error messages (if any)

## Contributing

We welcome contributions! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Development Setup

```bash
# Clone the repository
git clone https://github.com/your-org/ultra-pdf-editor.git
cd ultra-pdf-editor

# Install with dev dependencies
uv sync --group dev

# Run tests
uv run pytest

# Run linter
uv run ruff check .
```

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- [PyMuPDF](https://pymupdf.readthedocs.io/) for excellent PDF handling
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) for the GUI framework
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract) for OCR capabilities
- All open-source contributors

---

**Ultra PDF Editor** - Professional PDF editing made simple.
