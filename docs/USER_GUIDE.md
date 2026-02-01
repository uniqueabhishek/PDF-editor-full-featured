# Ultra PDF Editor - User Guide

A comprehensive guide to using Ultra PDF Editor for all your PDF editing needs.

## Table of Contents

1. [Getting Started](#getting-started)
2. [Interface Overview](#interface-overview)
3. [Working with Documents](#working-with-documents)
4. [Page Management](#page-management)
5. [Annotations and Markup](#annotations-and-markup)
6. [Text Editing](#text-editing)
7. [Images](#images)
8. [Forms](#forms)
9. [Security Features](#security-features)
10. [OCR - Text Recognition](#ocr---text-recognition)
11. [Conversion](#conversion)
12. [Batch Operations](#batch-operations)
13. [Customization](#customization)
14. [Tips and Tricks](#tips-and-tricks)

---

## Getting Started

### Launching the Application

**Windows:**
```bash
# Using uv
uv run python Ultra_PDF_Editor.py

# Or directly
.venv\Scripts\python.exe Ultra_PDF_Editor.py
```

**macOS/Linux:**
```bash
uv run python Ultra_PDF_Editor.py
```

### First Launch

On first launch, Ultra PDF Editor will:
1. Create a settings directory for your preferences
2. Display the main window with an empty workspace
3. Set the theme based on your system preference

### Opening Your First PDF

**Method 1: File Menu**
1. Click `File` → `Open` or press `Ctrl+O`
2. Navigate to your PDF file
3. Click `Open`

**Method 2: Drag and Drop**
1. Drag a PDF file from your file explorer
2. Drop it onto the Ultra PDF Editor window

**Method 3: Command Line**
```bash
uv run python Ultra_PDF_Editor.py "path/to/document.pdf"
```

---

## Interface Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│  File  Edit  View  Tools  Annotations  Help           [─][□][✕]   │
├─────────────────────────────────────────────────────────────────────┤
│ [📄][📂][💾] │ [⟲][⟳] │ [🔍-][100%][🔍+] │ [◀][▶] Page 1 of 10 │
├──────────────┬──────────────────────────────────────────────────────┤
│              │                                                      │
│  THUMBNAILS  │                                                      │
│              │                    PDF VIEWER                        │
│  [Page 1]    │                                                      │
│  [Page 2]    │              (Document Display Area)                 │
│  [Page 3]    │                                                      │
│  ...         │                                                      │
│              │                                                      │
├──────────────┴──────────────────────────────────────────────────────┤
│  Ready                                          Document: 2.5 MB    │
└─────────────────────────────────────────────────────────────────────┘
```

### Main Components

#### Menu Bar
Access all features through organized menus:
- **File**: Document operations (open, save, export, print)
- **Edit**: Undo/redo, copy, paste, find
- **View**: Zoom, view modes, panels
- **Tools**: Merge, split, compress, OCR
- **Annotations**: Markup and annotation tools
- **Help**: Documentation and about

#### Main Toolbar
Quick access to common operations:
- **New/Open/Save** - Document operations
- **Undo/Redo** - Edit history
- **Zoom controls** - View magnification
- **Page navigation** - Move between pages

#### Annotation Toolbar
(Visible when annotation mode is active)
- Selection tools
- Text markup (highlight, underline, strikethrough)
- Shapes (rectangle, circle, line, arrow)
- Text boxes and sticky notes
- Freehand drawing

#### Sidebar Panels

**Thumbnails Panel**
- Visual overview of all pages
- Click to navigate
- Drag to reorder pages
- Right-click for page operations

**Bookmarks Panel**
- Document outline/table of contents
- Click to jump to sections
- Create and edit bookmarks

**Annotations Panel**
- List of all annotations
- Click to navigate to annotation
- Edit or delete annotations

#### Status Bar
- Current tool mode
- Page information
- Document size
- Zoom level

---

## Working with Documents

### Creating a New Document

1. Click `File` → `New` or press `Ctrl+N`
2. A blank page is added automatically
3. Add content using annotations, text, or images

### Opening Documents

**Supported formats:**
- PDF files (`.pdf`)
- Password-protected PDFs (enter password when prompted)

**Opening password-protected PDFs:**
1. Open the PDF file
2. When prompted, enter the password
3. Click `OK`

### Saving Documents

**Save (Ctrl+S)**
- Saves changes to the current file
- If new document, prompts for location

**Save As (Ctrl+Shift+S)**
- Saves to a new location
- Original file remains unchanged

**Save options:**
- **Compression**: Reduce file size
- **Encryption**: Add password protection
- **PDF/A**: Archival format compliance

### Document Properties

Access via `File` → `Properties`:
- **Title, Author, Subject, Keywords**
- **Creation and modification dates**
- **Page count and file size**
- **PDF version and encryption status**

---

## Page Management

### Navigating Pages

| Action | Keyboard | Mouse |
|--------|----------|-------|
| Next page | Page Down, → | Scroll down |
| Previous page | Page Up, ← | Scroll up |
| First page | Ctrl+Home | - |
| Last page | Ctrl+End | - |
| Go to page | Ctrl+G | Click page in sidebar |

### Adding Pages

**Add blank page:**
1. `Edit` → `Insert Blank Page`
2. Choose position (before/after current)
3. Select page size (A4, Letter, Custom)

**Insert from another PDF:**
1. `Edit` → `Insert Pages From File`
2. Select the source PDF
3. Choose which pages to insert
4. Select insertion point

### Deleting Pages

**Delete current page:**
1. Navigate to the page
2. `Edit` → `Delete Page` or press `Delete`

**Delete multiple pages:**
1. Select pages in thumbnail view (Ctrl+click for multiple)
2. Right-click → `Delete Selected Pages`

### Reordering Pages

**Using thumbnails:**
1. Click and drag a page thumbnail
2. Drop at the desired position

**Using menu:**
1. `Edit` → `Move Page`
2. Enter source and destination positions

### Rotating Pages

**Rotate current page:**
- `Edit` → `Rotate Right` (Ctrl+R) - 90° clockwise
- `Edit` → `Rotate Left` (Ctrl+Shift+R) - 90° counter-clockwise

**Rotate multiple pages:**
1. Select pages in thumbnail view
2. Right-click → `Rotate Selected`
3. Choose rotation angle

### Extracting Pages

1. Select pages to extract (thumbnail view)
2. Right-click → `Extract to New PDF`
3. Choose save location

### Cropping Pages

1. `Edit` → `Crop Pages`
2. Drag to define the crop area
3. Apply to current page or all pages

---

## Annotations and Markup

### Text Markup

#### Highlight
1. Click the **Highlight** tool (or press `H`)
2. Click and drag over text to highlight
3. Adjust color in the properties panel

#### Underline
1. Click the **Underline** tool
2. Click and drag over text
3. Choose color and style

#### Strikethrough
1. Click the **Strikethrough** tool
2. Click and drag over text

### Comments

#### Sticky Notes
1. Click the **Sticky Note** tool
2. Click where you want the note
3. Type your comment
4. Click outside to finish

#### Text Boxes
1. Click the **Text Box** tool
2. Click and drag to create the box
3. Type your text
4. Customize font, size, and color

### Shapes

#### Rectangle
1. Click the **Rectangle** tool
2. Click and drag to draw
3. Adjust border and fill colors

#### Circle/Ellipse
1. Click the **Circle** tool
2. Click and drag to draw
3. Customize appearance

#### Line
1. Click the **Line** tool
2. Click start point, drag to end
3. Adjust color and width

#### Arrow
1. Click the **Arrow** tool
2. Click start, drag to endpoint
3. Choose arrow head style

### Freehand Drawing

1. Click the **Freehand** tool (pencil icon)
2. Draw directly on the page
3. Adjust color and stroke width
4. Click another tool to finish

### Stamps

**Built-in stamps:**
1. Click the **Stamp** tool
2. Select from: Approved, Draft, Confidential, etc.
3. Click on the page to place

**Custom stamps:**
1. `Annotations` → `Create Custom Stamp`
2. Select an image file
3. Name your stamp
4. Use like built-in stamps

### Managing Annotations

**Edit annotation:**
1. Click on the annotation
2. Modify properties in the sidebar
3. Or double-click to edit content

**Delete annotation:**
1. Select the annotation
2. Press `Delete` or right-click → `Delete`

**View all annotations:**
1. Open the Annotations panel
2. Click any annotation to navigate
3. Sort by type, page, or date

---

## Text Editing

### Editing Existing Text

> **Note**: Text editing works best with native PDF text. Scanned documents require OCR first.

1. Click the **Edit Text** tool
2. Click on text to edit
3. Make changes directly
4. Click outside to finish

### Adding New Text

1. Click the **Add Text** tool
2. Click where you want text
3. Type your content
4. Customize:
   - Font family
   - Font size
   - Color
   - Bold, italic, underline

### Find and Replace

1. `Edit` → `Find` (Ctrl+F)
2. Enter search text
3. Use `Next`/`Previous` to navigate
4. For replace: `Edit` → `Find and Replace` (Ctrl+H)

---

## Images

### Inserting Images

1. `Edit` → `Insert Image` or press `I`
2. Select image file (PNG, JPG, BMP, etc.)
3. Click on page or drag to position
4. Resize using corner handles

### Editing Images

**Move:**
- Click and drag the image

**Resize:**
- Drag corner handles
- Hold Shift to maintain aspect ratio

**Rotate:**
- Use rotation handle above the image

**Delete:**
- Select and press `Delete`

### Extracting Images

**Extract single image:**
1. Right-click on the image
2. Select `Extract Image`
3. Choose format and location

**Extract all images:**
1. `Tools` → `Extract Images`
2. Select output folder
3. Choose format (PNG, JPG, etc.)

---

## Forms

### Filling Existing Forms

1. Open a PDF with form fields
2. Click on a form field to select
3. Type to fill text fields
4. Click checkboxes to toggle
5. Select from dropdown lists

### Creating Fillable Forms

#### Add Text Field
1. `Forms` → `Add Text Field`
2. Draw the field area
3. Set properties:
   - Field name
   - Default value
   - Character limit
   - Formatting

#### Add Checkbox
1. `Forms` → `Add Checkbox`
2. Click to place
3. Set checked/unchecked state

#### Add Radio Buttons
1. `Forms` → `Add Radio Button`
2. Create a group of buttons
3. Only one can be selected

#### Add Dropdown List
1. `Forms` → `Add Dropdown`
2. Draw the field
3. Add list options

### Form Data

**Export form data:**
1. `Forms` → `Export Data`
2. Choose format (FDF, XFDF)

**Import form data:**
1. `Forms` → `Import Data`
2. Select data file
3. Fields are populated automatically

---

## Security Features

### Password Protection

**Set passwords:**
1. `File` → `Security` → `Encrypt Document`
2. Set **User Password** (required to open)
3. Set **Owner Password** (required for full access)

**Remove passwords:**
1. `File` → `Security` → `Remove Security`
2. Enter owner password

### Permissions

When encrypting, set permissions:
- ☐ Allow printing
- ☐ Allow copying text
- ☐ Allow editing
- ☐ Allow form filling
- ☐ Allow annotations

### Digital Signatures

**Add signature:**
1. `Security` → `Sign Document`
2. Select certificate
3. Draw signature area
4. Apply signature

**Verify signatures:**
1. Open signed document
2. Click on signature
3. View validation status

### Redaction

> **Warning**: Redaction permanently removes content. Always save a backup first!

1. `Security` → `Redact`
2. Select content to redact
3. Choose redaction style (black, white, custom)
4. Click `Apply Redaction`

---

## OCR - Text Recognition

### Requirements
- Tesseract OCR must be installed
- Language packs for desired languages

### Make PDF Searchable

1. `Tools` → `OCR` → `Make Searchable`
2. Select language
3. Choose pages (all or specific)
4. Click `Start OCR`
5. Wait for processing
6. Save the searchable PDF

### OCR Settings

- **Language**: Primary document language
- **DPI**: Higher = better quality, slower
- **Pages**: All, range, or current

---

## Conversion

### PDF to Word

1. `File` → `Export` → `Microsoft Word`
2. Choose `.docx` format
3. Select pages to convert
4. Click `Export`

### PDF to Images

1. `File` → `Export` → `Images`
2. Select format (PNG, JPG, TIFF)
3. Set DPI (72-600)
4. Choose pages
5. Click `Export`

### PDF to Other Formats

Available exports:
- Microsoft Excel (.xlsx)
- PowerPoint (.pptx)
- HTML
- Plain Text
- PDF/A (archival)

### Import to PDF

**Images to PDF:**
1. `File` → `Create PDF from Images`
2. Select image files
3. Arrange order
4. Click `Create`

**Documents to PDF:**
1. `File` → `Create PDF from File`
2. Select Word, Excel, or other document
3. Conversion happens automatically

---

## Batch Operations

### Batch Merge

1. `Tools` → `Batch` → `Merge PDFs`
2. Add files to merge
3. Arrange order
4. Set output path
5. Click `Merge`

### Batch Convert

1. `Tools` → `Batch` → `Convert`
2. Add input files
3. Select output format
4. Choose destination folder
5. Click `Convert All`

### Batch Watermark

1. `Tools` → `Batch` → `Add Watermark`
2. Add PDF files
3. Configure watermark (text/image)
4. Apply to all files

### Batch Compress

1. `Tools` → `Batch` → `Compress`
2. Add files
3. Select compression level
4. Process all files

---

## Customization

### Theme Settings

`Edit` → `Preferences` → `Appearance`
- **Light**: Bright interface
- **Dark**: Dark interface
- **System**: Follow OS setting

### View Preferences

`Edit` → `Preferences` → `View`
- Default zoom level
- Default view mode (single, continuous)
- Show rulers
- Show guides

### Editor Settings

`Edit` → `Preferences` → `Editor`
- Autosave interval
- Undo history limit
- Default font
- Default colors

### Keyboard Shortcuts

`Edit` → `Preferences` → `Shortcuts`
- View all shortcuts
- Customize bindings
- Reset to defaults

---

## Tips and Tricks

### Productivity Tips

1. **Use keyboard shortcuts** - Much faster than menus
2. **Thumbnail navigation** - Quick page overview
3. **Right-click menus** - Context-specific options
4. **Recent files** - Quick access to past documents

### Performance Tips

1. **Large documents**: Use single-page view
2. **Many images**: Reduce thumbnail cache size
3. **Slow rendering**: Lower DPI for preview
4. **Memory issues**: Close unused tabs

### Quality Tips

1. **OCR accuracy**: Use 300+ DPI
2. **Image quality**: Use PNG for screenshots, JPG for photos
3. **File size**: Use compression for email attachments
4. **Compatibility**: Save as PDF 1.5 for older readers

### Common Tasks Quick Reference

| Task | Quick Method |
|------|--------------|
| Zoom to fit | Ctrl+0 |
| Find text | Ctrl+F |
| Add highlight | H, then drag |
| Rotate page | Ctrl+R |
| Delete page | Select + Delete |
| Merge PDFs | Tools → Merge |
| Save copy | Ctrl+Shift+S |

---

## Troubleshooting

### Document Won't Open

1. Check if file is corrupted
2. Verify file extension is `.pdf`
3. Try password if encrypted
4. Check file permissions

### OCR Not Working

1. Verify Tesseract installation
2. Check language pack
3. Ensure document is scanned (not native PDF)

### Annotations Not Saving

1. Use `Save` not just close
2. Check write permissions
3. Try `Save As` to new location

### Slow Performance

1. Reduce thumbnail cache
2. Close unused documents
3. Lower preview quality
4. Check available memory

### Getting Help

- Press `F1` for context help
- `Help` → `Documentation`
- Check GitHub issues
- Contact support

---

*Ultra PDF Editor - Professional PDF editing made simple.*
