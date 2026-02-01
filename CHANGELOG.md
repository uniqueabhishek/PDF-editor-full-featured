# Changelog

All notable changes to Ultra PDF Editor will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Planned
- Multi-tab document support
- Batch processing wizard
- Digital signature support
- PDF comparison tool
- Plugin architecture

---

## [1.0.0] - 2026-02-01

### Added

#### Core Features
- **PDF Viewing**: Open and navigate PDF documents with smooth scrolling
- **Multiple View Modes**: Single page, two-page, and continuous scroll views
- **Zoom Controls**: Fit page, fit width, and custom zoom levels (25%-400%)
- **Page Navigation**: Thumbnails sidebar, keyboard shortcuts, go-to-page dialog

#### Page Management
- **Add Pages**: Insert blank pages at any position
- **Delete Pages**: Remove single or multiple pages
- **Reorder Pages**: Drag and drop in thumbnail view
- **Rotate Pages**: 90°, 180°, 270° rotation
- **Extract Pages**: Save selected pages to new PDF
- **Duplicate Pages**: Copy pages within document

#### Merge & Split
- **Merge PDFs**: Combine multiple PDFs into one
- **Split by Pages**: Divide PDF into fixed-size chunks
- **Split by Ranges**: Custom page range extraction
- **Batch Merge**: Merge multiple files in one operation

#### Annotations
- **Text Markup**: Highlight, underline, strikethrough
- **Sticky Notes**: Add comments at any position
- **Text Boxes**: Free-form text with font customization
- **Shapes**: Rectangle, circle, line, arrow
- **Freehand Drawing**: Pen tool with customizable stroke
- **Stamps**: Built-in and custom stamp support
- **Annotation Panel**: List and manage all annotations

#### Forms
- **Fill Forms**: Complete existing PDF forms
- **Text Fields**: Single and multi-line input
- **Checkboxes**: Toggle controls
- **Radio Buttons**: Grouped selection controls
- **Dropdown Lists**: Selection menus
- **Form Data Export**: FDF and XFDF formats

#### Security
- **Password Protection**: User and owner passwords
- **Encryption**: 128-bit and 256-bit AES
- **Permissions**: Control print, copy, edit access
- **Redaction**: Permanent content removal

#### OCR (Optical Character Recognition)
- **Make Searchable**: Convert scanned PDFs to searchable text
- **30+ Languages**: Support for major world languages
- **Batch OCR**: Process multiple documents

#### Conversion
- **Export to Word**: Convert PDF to .docx format
- **Export to Excel**: Extract tables to .xlsx
- **Export to Images**: PNG, JPG, TIFF output
- **Export to HTML**: Web-ready format
- **Create from Images**: Combine images into PDF

#### User Interface
- **Modern Design**: Clean, professional interface
- **Dark Mode**: System-aware theme switching
- **Customizable Toolbar**: Arrange tools to preference
- **Keyboard Shortcuts**: Comprehensive shortcut support
- **Status Bar**: Document info and zoom level
- **Recent Files**: Quick access to recent documents

#### Performance
- **Lazy Rendering**: Only render visible pages
- **Page Caching**: Smooth navigation
- **Background Processing**: Non-blocking operations
- **Memory Optimization**: Efficient large file handling

### Technical
- Built with Python 3.10+ and PyQt6
- PDF engine powered by PyMuPDF
- Cross-platform support (Windows, macOS, Linux)
- uv package manager for dependency management

---

## Version History Format

### Types of Changes

- **Added**: New features
- **Changed**: Changes to existing functionality
- **Deprecated**: Features to be removed in future
- **Removed**: Features removed in this version
- **Fixed**: Bug fixes
- **Security**: Security-related changes

---

## Upgrade Guide

### From Pre-release to 1.0.0

1. **Settings Migration**: Settings file format changed. Old settings will be reset to defaults.

2. **Dependencies**: Run `uv sync` to update all dependencies.

3. **Tesseract**: For OCR features, ensure Tesseract 5.0+ is installed.

---

## Release Schedule

- **Major versions** (x.0.0): Significant new features, potential breaking changes
- **Minor versions** (x.y.0): New features, backwards compatible
- **Patch versions** (x.y.z): Bug fixes, security updates

---

[Unreleased]: https://github.com/your-org/ultra-pdf-editor/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/your-org/ultra-pdf-editor/releases/tag/v1.0.0
