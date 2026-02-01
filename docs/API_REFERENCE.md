# Ultra PDF Editor - API Reference

This document provides detailed API documentation for the core modules of Ultra PDF Editor.

## Table of Contents

- [PDFDocument Class](#pdfdocument-class)
- [OCRProcessor Class](#ocrprocessor-class)
- [Annotation Classes](#annotation-classes)
- [Form Field Classes](#form-field-classes)
- [Converter Modules](#converter-modules)
- [Configuration Classes](#configuration-classes)

---

## PDFDocument Class

**Module**: `core.pdf_document`

The main class for handling PDF documents. Provides methods for opening, editing, and saving PDF files.

### Constructor

```python
PDFDocument()
```

Creates a new PDFDocument instance without opening any file.

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_open` | `bool` | Whether a document is currently loaded |
| `filepath` | `Optional[Path]` | Path to the current file (None if unsaved) |
| `is_modified` | `bool` | Whether the document has unsaved changes |
| `page_count` | `int` | Number of pages in the document |
| `is_encrypted` | `bool` | Whether the document is encrypted |
| `needs_password` | `bool` | Whether a password is required to open |

### Document Operations

#### `open(filepath, password=None) -> bool`

Opens a PDF file.

**Parameters:**
- `filepath` (`Union[str, Path]`): Path to the PDF file
- `password` (`Optional[str]`): Password for encrypted PDFs

**Returns:** `True` if successful, `False` if password is required

**Raises:**
- `FileNotFoundError`: If file doesn't exist
- `ValueError`: If password is invalid

**Example:**
```python
doc = PDFDocument()
if doc.open("document.pdf"):
    print(f"Opened {doc.page_count} pages")
elif doc.needs_password:
    doc.open("document.pdf", password="secret")
```

---

#### `create_new() -> bool`

Creates a new empty PDF document.

**Returns:** `True` if successful

**Example:**
```python
doc = PDFDocument()
doc.create_new()
doc.add_blank_page()  # Add at least one page
doc.save("new_document.pdf")
```

---

#### `save(filepath=None, encryption=None, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True) -> bool`

Saves the document.

**Parameters:**
- `filepath` (`Optional[Union[str, Path]]`): Save path (uses current path if None)
- `encryption` (`Optional[Dict]`): Encryption settings
- `garbage` (`int`): Garbage collection level (0-4, default 4)
- `deflate` (`bool`): Compress streams
- `deflate_images` (`bool`): Compress images
- `deflate_fonts` (`bool`): Compress fonts

**Returns:** `True` if successful

**Raises:**
- `ValueError`: If no document is open or no filepath specified

**Encryption Settings:**
```python
encryption = {
    "method": fitz.PDF_ENCRYPT_AES_256,
    "user_password": "user_pass",
    "owner_password": "owner_pass",
    "permissions": fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY
}
doc.save("encrypted.pdf", encryption=encryption)
```

---

#### `save_copy(filepath) -> bool`

Saves a copy without changing the current document path.

**Parameters:**
- `filepath` (`Union[str, Path]`): Path for the copy

**Returns:** `True` if successful

---

#### `close()`

Closes the current document and releases resources.

---

### Page Operations

#### `get_page(page_num) -> fitz.Page`

Gets a page object by index.

**Parameters:**
- `page_num` (`int`): Page index (0-based)

**Returns:** `fitz.Page` object

**Raises:**
- `ValueError`: If no document is open
- `IndexError`: If page number is out of range

---

#### `get_page_info(page_num) -> PageInfo`

Gets information about a specific page.

**Parameters:**
- `page_num` (`int`): Page index (0-based)

**Returns:** `PageInfo` dataclass with:
- `index`: Page index
- `width`: Page width in points
- `height`: Page height in points
- `rotation`: Current rotation (0, 90, 180, 270)
- `has_text`: Whether page contains text
- `has_images`: Whether page contains images
- `has_annotations`: Whether page has annotations
- `label`: Page label (if any)

---

#### `add_blank_page(width=595, height=842, index=-1) -> int`

Adds a blank page to the document.

**Parameters:**
- `width` (`float`): Page width in points (default: A4 width)
- `height` (`float`): Page height in points (default: A4 height)
- `index` (`int`): Insert position (-1 for end)

**Returns:** Index of the new page

**Example:**
```python
# Add A4 page at end
doc.add_blank_page()

# Add Letter size page at position 2
doc.add_blank_page(width=612, height=792, index=2)
```

---

#### `delete_page(page_num)`

Deletes a page from the document.

**Parameters:**
- `page_num` (`int`): Page index to delete

---

#### `delete_pages(page_nums)`

Deletes multiple pages.

**Parameters:**
- `page_nums` (`List[int]`): List of page indices to delete

**Note:** Pages are deleted in descending order to maintain correct indices.

---

#### `rotate_page(page_num, rotation)`

Rotates a page.

**Parameters:**
- `page_num` (`int`): Page index
- `rotation` (`int`): Rotation in degrees (90, 180, 270, or negative values)

---

#### `move_page(from_index, to_index)`

Moves a page from one position to another.

**Parameters:**
- `from_index` (`int`): Source page index
- `to_index` (`int`): Destination index

---

#### `copy_page(page_num, to_index=-1) -> int`

Duplicates a page within the document.

**Parameters:**
- `page_num` (`int`): Page to copy
- `to_index` (`int`): Destination index (-1 for end)

**Returns:** Index of the new page

---

#### `extract_pages(page_nums, output_path) -> bool`

Extracts specific pages to a new PDF file.

**Parameters:**
- `page_nums` (`List[int]`): Pages to extract
- `output_path` (`Union[str, Path]`): Output file path

**Example:**
```python
# Extract pages 1, 3, 5 (0-indexed: 0, 2, 4)
doc.extract_pages([0, 2, 4], "extracted.pdf")
```

---

### Rendering

#### `render_page(page_num, zoom=1.0, rotation=0, alpha=False) -> fitz.Pixmap`

Renders a page to a pixmap.

**Parameters:**
- `page_num` (`int`): Page index
- `zoom` (`float`): Zoom factor (1.0 = 100%)
- `rotation` (`int`): Additional rotation in degrees
- `alpha` (`bool`): Include alpha channel

**Returns:** `fitz.Pixmap` object

---

#### `render_page_to_image(page_num, dpi=150) -> bytes`

Renders a page to PNG image bytes.

**Parameters:**
- `page_num` (`int`): Page index
- `dpi` (`int`): Resolution (default: 150)

**Returns:** PNG image as bytes

---

### Merge & Split Operations

#### `merge_pdf(other_path, position=-1) -> bool`

Merges another PDF into the current document.

**Parameters:**
- `other_path` (`Union[str, Path]`): PDF to merge
- `position` (`int`): Insert position (-1 for end)

---

#### `merge_pdfs(pdf_paths, output_path) -> bool`

**Static method.** Merges multiple PDFs into a new file.

**Parameters:**
- `pdf_paths` (`List[Union[str, Path]]`): List of PDF files
- `output_path` (`Union[str, Path]`): Output file path

**Example:**
```python
PDFDocument().merge_pdfs(
    ["doc1.pdf", "doc2.pdf", "doc3.pdf"],
    "merged.pdf"
)
```

---

#### `split_by_pages(output_dir, pages_per_file=1) -> List[str]`

Splits document into multiple files.

**Parameters:**
- `output_dir` (`Union[str, Path]`): Output directory
- `pages_per_file` (`int`): Pages per output file

**Returns:** List of created file paths

---

#### `split_by_ranges(ranges, output_dir) -> List[str]`

Splits document by specific page ranges.

**Parameters:**
- `ranges` (`List[Tuple[int, int]]`): List of (start, end) tuples (0-indexed, inclusive)
- `output_dir` (`Union[str, Path]`): Output directory

**Returns:** List of created file paths

**Example:**
```python
# Split into: pages 1-5, pages 6-10, pages 11-15
doc.split_by_ranges([(0, 4), (5, 9), (10, 14)], "output/")
```

---

### Text Operations

#### `get_page_text(page_num, text_type="text") -> str`

Extracts text from a page.

**Parameters:**
- `page_num` (`int`): Page index
- `text_type` (`str`): Extraction type: "text", "blocks", "words", "html", "dict", "json", "xhtml", "xml"

**Returns:** Extracted text in specified format

---

#### `get_all_text() -> str`

Extracts all text from the document.

**Returns:** Combined text from all pages

---

#### `search_text(text, case_sensitive=False) -> List[Dict]`

Searches for text in the document.

**Parameters:**
- `text` (`str`): Text to search for
- `case_sensitive` (`bool`): Case-sensitive search

**Returns:** List of dicts with `page` and `rects` keys

**Example:**
```python
results = doc.search_text("invoice")
for result in results:
    print(f"Page {result['page'] + 1}: {len(result['rects'])} matches")
```

---

#### `add_text(page_num, text, position, font_size=12, font_name="helv", color=(0, 0, 0)) -> bool`

Adds text to a page.

**Parameters:**
- `page_num` (`int`): Page index
- `text` (`str`): Text to add
- `position` (`Tuple[float, float]`): (x, y) position in points
- `font_size` (`float`): Font size
- `font_name` (`str`): Font name ("helv", "tiro", "cour", etc.)
- `color` (`Tuple[float, float, float]`): RGB color (0-1 range)

---

### Image Operations

#### `get_page_images(page_num) -> List[Dict]`

Gets list of images on a page.

**Returns:** List of dicts with image metadata (xref, width, height, etc.)

---

#### `extract_image(xref) -> bytes`

Extracts an image by its xref (cross-reference number).

**Parameters:**
- `xref` (`int`): Image cross-reference number

**Returns:** Image bytes

---

#### `extract_all_images(output_dir) -> List[str]`

Extracts all images from the document.

**Parameters:**
- `output_dir` (`Union[str, Path]`): Output directory

**Returns:** List of saved file paths

---

#### `insert_image(page_num, image_path, rect=None, keep_proportion=True) -> bool`

Inserts an image into a page.

**Parameters:**
- `page_num` (`int`): Page index
- `image_path` (`Union[str, Path]`): Path to image file
- `rect` (`Optional[Tuple[float, float, float, float]]`): Target rectangle (x0, y0, x1, y1)
- `keep_proportion` (`bool`): Maintain aspect ratio

---

### Annotation Operations

#### `add_highlight(page_num, rect, color=(1, 1, 0)) -> fitz.Annot`

Adds a highlight annotation.

**Parameters:**
- `page_num` (`int`): Page index
- `rect` (`Tuple[float, float, float, float]`): Rectangle (x0, y0, x1, y1)
- `color` (`Tuple[float, float, float]`): RGB color (0-1 range)

**Returns:** Created annotation object

---

#### `add_underline(page_num, rect, color=(0, 0, 1)) -> fitz.Annot`

Adds an underline annotation.

---

#### `add_strikethrough(page_num, rect, color=(1, 0, 0)) -> fitz.Annot`

Adds a strikethrough annotation.

---

#### `add_text_annotation(page_num, position, text, icon="Note") -> fitz.Annot`

Adds a sticky note annotation.

**Parameters:**
- `page_num` (`int`): Page index
- `position` (`Tuple[float, float]`): (x, y) position
- `text` (`str`): Note content
- `icon` (`str`): Icon type ("Note", "Comment", "Help", "Insert", "Key", "NewParagraph", "Paragraph")

---

#### `add_freetext(page_num, rect, text, font_size=12, text_color=(0, 0, 0), fill_color=(1, 1, 1)) -> fitz.Annot`

Adds a text box annotation.

---

#### `add_rect_annotation(page_num, rect, stroke_color=(1, 0, 0), fill_color=None, width=1) -> fitz.Annot`

Adds a rectangle annotation.

---

#### `add_circle_annotation(page_num, rect, stroke_color=(1, 0, 0), fill_color=None, width=1) -> fitz.Annot`

Adds a circle/ellipse annotation.

---

#### `add_line_annotation(page_num, start, end, color=(1, 0, 0), width=1) -> fitz.Annot`

Adds a line annotation.

**Parameters:**
- `start` (`Tuple[float, float]`): Start point
- `end` (`Tuple[float, float]`): End point

---

#### `add_ink_annotation(page_num, points, color=(0, 0, 0), width=2) -> fitz.Annot`

Adds a freehand drawing annotation.

**Parameters:**
- `points` (`List[List[Tuple[float, float]]]`): List of stroke paths

---

#### `delete_annotation(page_num, annot)`

Deletes an annotation.

---

### Watermark Operations

#### `add_watermark(text, font_size=48, color=(0.5, 0.5, 0.5), opacity=0.3, rotation=45, pages=None) -> bool`

Adds a text watermark.

**Parameters:**
- `text` (`str`): Watermark text
- `font_size` (`float`): Font size
- `color` (`Tuple[float, float, float]`): RGB color
- `opacity` (`float`): Transparency (0-1)
- `rotation` (`float`): Rotation angle
- `pages` (`Optional[List[int]]`): Specific pages (None for all)

---

#### `add_image_watermark(image_path, opacity=0.3, pages=None) -> bool`

Adds an image watermark.

---

### Security Operations

#### `encrypt(user_password="", owner_password="", permissions=fitz.PDF_PERM_ACCESSIBILITY) -> bool`

Encrypts the document.

**Permission Flags:**
- `fitz.PDF_PERM_PRINT` - Allow printing
- `fitz.PDF_PERM_MODIFY` - Allow modification
- `fitz.PDF_PERM_COPY` - Allow copying
- `fitz.PDF_PERM_ANNOTATE` - Allow annotations
- `fitz.PDF_PERM_FORM` - Allow form filling
- `fitz.PDF_PERM_ACCESSIBILITY` - Allow accessibility
- `fitz.PDF_PERM_ASSEMBLE` - Allow assembly
- `fitz.PDF_PERM_PRINT_HQ` - Allow high-quality printing

---

#### `decrypt(password) -> bool`

Decrypts the document.

**Returns:** `True` if decryption successful

---

### Metadata Operations

#### `get_metadata() -> DocumentMetadata`

Gets document metadata.

**Returns:** `DocumentMetadata` dataclass

---

#### `set_metadata(metadata) -> bool`

Sets document metadata.

**Parameters:**
- `metadata` (`Dict[str, str]`): Metadata fields ("title", "author", "subject", "keywords", "creator", "producer")

---

### Bookmarks/TOC

#### `get_toc() -> List`

Gets table of contents.

**Returns:** List of `[level, title, page, dest]` entries

---

#### `set_toc(toc) -> bool`

Sets table of contents.

---

#### `add_bookmark(title, page_num, level=1) -> bool`

Adds a bookmark.

---

---

## OCRProcessor Class

**Module**: `core.operations.ocr`

Handles Optical Character Recognition for scanned PDFs.

### Constructor

```python
OCRProcessor(language: str = "eng")
```

**Parameters:**
- `language` (`str`): OCR language code (e.g., "eng", "fra", "deu")

### Properties

| Property | Type | Description |
|----------|------|-------------|
| `is_available` | `bool` | Whether Tesseract OCR is installed |
| `language` | `str` | Current OCR language |

### Methods

#### `ocr_page(page, dpi=300, preprocess=True) -> str`

Performs OCR on a single page.

**Parameters:**
- `page` (`fitz.Page`): Page object
- `dpi` (`int`): Resolution for OCR
- `preprocess` (`bool`): Apply image preprocessing

**Returns:** Extracted text

---

#### `make_searchable_pdf(input_path, output_path=None, pages=None, dpi=300, callback=None) -> Path`

Converts a scanned PDF to searchable PDF.

**Parameters:**
- `input_path` (`Union[str, Path]`): Input PDF
- `output_path` (`Optional[Union[str, Path]]`): Output path
- `pages` (`Optional[List[int]]`): Pages to process (None for all)
- `dpi` (`int`): OCR resolution
- `callback` (`Callable`): Progress callback `(current, total, status)`

**Returns:** Path to output file

---

#### `get_available_languages() -> List[str]`

Gets list of available OCR languages.

---

### Language Codes

```python
from core.operations.ocr import LANGUAGE_CODES

# Available mappings
LANGUAGE_CODES = {
    "English": "eng",
    "Spanish": "spa",
    "French": "fra",
    "German": "deu",
    "Chinese (Simplified)": "chi_sim",
    "Japanese": "jpn",
    # ... more languages
}
```

---

## Configuration Classes

**Module**: `config`

### AppConfig Class

Application-wide configuration constants.

```python
from config import config

# Access configuration
print(config.APP_NAME)        # "Ultra PDF Editor"
print(config.APP_VERSION)     # "1.0.0"
print(config.SETTINGS_PATH)   # Path to settings file
print(config.TEMP_DIR)        # Temporary files directory
print(config.AUTOSAVE_DIR)    # Autosave directory
```

### UserSettings Class

User preferences that persist between sessions.

```python
from config import UserSettings, config

# Load settings
settings = UserSettings.load(config.SETTINGS_PATH)

# Access/modify settings
settings.theme = "dark"
settings.zoom_level = 150.0
settings.autosave_enabled = True

# Save settings
settings.save(config.SETTINGS_PATH)
```

**Available Settings:**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `theme` | `str` | `"system"` | Theme: "light", "dark", "system" |
| `zoom_level` | `float` | `100.0` | Default zoom percentage |
| `view_mode` | `str` | `"continuous"` | View mode |
| `autosave_enabled` | `bool` | `True` | Enable autosave |
| `autosave_interval` | `int` | `300` | Autosave interval (seconds) |
| `ocr_language` | `str` | `"eng"` | Default OCR language |
| `default_image_dpi` | `int` | `150` | Default export DPI |
| `recent_files` | `List[str]` | `[]` | Recent files list |

---

## Error Handling

All methods that operate on documents will raise:

- `ValueError` with message "No document is open" if called without an open document
- `IndexError` for invalid page numbers
- `FileNotFoundError` for missing files
- Other appropriate exceptions for specific error conditions

**Recommended pattern:**

```python
from core.pdf_document import PDFDocument

doc = PDFDocument()
try:
    doc.open("document.pdf")
    doc.add_blank_page()
    doc.save()
except FileNotFoundError:
    print("File not found")
except ValueError as e:
    print(f"Document error: {e}")
finally:
    doc.close()
```

---

## Thread Safety

The `PDFDocument` class is **not thread-safe**. If you need to process multiple documents concurrently, create separate instances for each thread.

```python
from concurrent.futures import ThreadPoolExecutor
from core.pdf_document import PDFDocument

def process_pdf(filepath):
    doc = PDFDocument()  # Each thread gets its own instance
    try:
        doc.open(filepath)
        # ... process document
    finally:
        doc.close()

with ThreadPoolExecutor(max_workers=4) as executor:
    executor.map(process_pdf, pdf_files)
```

---

## Units and Coordinates

- **Points**: All measurements are in PDF points (1 point = 1/72 inch)
- **Coordinates**: Origin (0, 0) is at top-left of page
- **Colors**: RGB values in range 0.0 to 1.0
- **Rotation**: Degrees, clockwise positive

**Common page sizes in points:**

| Size | Width | Height |
|------|-------|--------|
| A4 | 595 | 842 |
| Letter | 612 | 792 |
| Legal | 612 | 1008 |
| A3 | 842 | 1191 |
| A5 | 420 | 595 |
