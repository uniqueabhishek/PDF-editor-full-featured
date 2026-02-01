# Contributing to Ultra PDF Editor

Thank you for your interest in contributing to Ultra PDF Editor! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Environment](#development-environment)
- [Code Style](#code-style)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Issue Guidelines](#issue-guidelines)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

### Our Pledge

We are committed to providing a welcoming and inclusive environment for all contributors. We expect everyone to:

- Be respectful and considerate
- Welcome newcomers and help them learn
- Accept constructive criticism gracefully
- Focus on what is best for the community
- Show empathy towards others

### Unacceptable Behavior

- Harassment, discrimination, or offensive comments
- Personal attacks or trolling
- Publishing others' private information
- Any conduct inappropriate in a professional setting

## Getting Started

### Prerequisites

- Python 3.10 or higher
- Git
- uv package manager (recommended) or pip

### Setting Up Your Development Environment

1. **Fork the repository** on GitHub

2. **Clone your fork**
   ```bash
   git clone https://github.com/YOUR-USERNAME/ultra-pdf-editor.git
   cd ultra-pdf-editor
   ```

3. **Add upstream remote**
   ```bash
   git remote add upstream https://github.com/original-org/ultra-pdf-editor.git
   ```

4. **Install dependencies**
   ```bash
   # Using uv (recommended)
   uv sync --group dev

   # Or using pip
   pip install -e ".[dev]"
   ```

5. **Verify installation**
   ```bash
   uv run python Ultra_PDF_Editor.py
   ```

## Development Environment

### Recommended IDE Setup

**VS Code** (recommended):
```json
// .vscode/settings.json
{
    "python.defaultInterpreterPath": ".venv/Scripts/python.exe",
    "python.analysis.typeCheckingMode": "basic",
    "editor.formatOnSave": true,
    "[python]": {
        "editor.defaultFormatter": "charliermarsh.ruff"
    }
}
```

**PyCharm**:
- Set interpreter to `.venv/Scripts/python.exe`
- Enable Ruff as external tool
- Configure pytest as test runner

### Project Structure Overview

```
ultra-pdf-editor/
├── Ultra_PDF_Editor.py     # Entry point - application startup
├── config.py               # Configuration classes and constants
├── pyproject.toml          # Dependencies and project metadata
│
├── core/                   # Core business logic (no UI)
│   ├── pdf_document.py     # PDFDocument class - main document model
│   ├── operations/         # Stateless PDF operations
│   │   ├── merge.py        # Merge operations
│   │   ├── split.py        # Split operations
│   │   ├── ocr.py          # OCR processing
│   │   └── ...
│   └── converters/         # Format conversion modules
│       ├── to_word.py
│       ├── to_image.py
│       └── ...
│
├── ui/                     # User interface (PyQt6)
│   ├── main_window.py      # Main application window
│   ├── pdf_viewer.py       # PDF rendering widget
│   ├── sidebar.py          # Side panel widgets
│   ├── toolbar.py          # Toolbar widgets
│   └── dialogs/            # Dialog windows
│
├── annotations/            # Annotation handling
├── forms/                  # Form field handling
├── utils/                  # Shared utilities
└── tests/                  # Test suite
```

## Code Style

### General Guidelines

1. **Follow PEP 8** with these exceptions:
   - Line length: 100 characters (not 79)
   - Use double quotes for strings

2. **Use type hints** for all function signatures:
   ```python
   def merge_pdfs(
       self,
       pdf_paths: List[Union[str, Path]],
       output_path: Union[str, Path]
   ) -> bool:
       """Merge multiple PDFs into a new file."""
       ...
   ```

3. **Write docstrings** for all public methods:
   ```python
   def add_blank_page(
       self,
       width: float = 595,
       height: float = 842,
       index: int = -1
   ) -> int:
       """
       Add a blank page to the document.

       Args:
           width: Page width in points (default: A4 width)
           height: Page height in points (default: A4 height)
           index: Insert position (-1 for end)

       Returns:
           Index of the newly created page

       Raises:
           ValueError: If no document is open
       """
       ...
   ```

4. **Use meaningful variable names**:
   ```python
   # Good
   page_count = len(document.pages)
   current_page_index = 0

   # Bad
   n = len(d.p)
   i = 0
   ```

### Ruff Configuration

We use Ruff for linting. Configuration is in `pyproject.toml`:

```toml
[tool.ruff]
line-length = 100
target-version = "py310"

[tool.ruff.lint]
select = ["E", "F", "W", "I", "N", "UP", "B", "C4"]
ignore = ["E501"]  # Line length handled separately
```

Run linting:
```bash
uv run ruff check .
uv run ruff check --fix .  # Auto-fix issues
```

### Import Organization

```python
# Standard library imports
import os
import sys
from pathlib import Path
from typing import List, Optional, Union

# Third-party imports
import fitz
from PyQt6.QtWidgets import QMainWindow, QWidget
from PyQt6.QtCore import Qt, pyqtSignal

# Local imports
from core.pdf_document import PDFDocument
from utils.file_utils import ensure_directory
```

### UI Code Guidelines

1. **Separate logic from presentation**:
   ```python
   # Good - logic in core module
   class MainWindow(QMainWindow):
       def _merge_documents(self):
           result = self._document.merge_pdfs(paths, output)
           self._show_result(result)

   # Bad - business logic in UI
   class MainWindow(QMainWindow):
       def _merge_documents(self):
           merged_doc = fitz.open()
           for path in paths:
               # ... PDF manipulation code
   ```

2. **Use signals for communication**:
   ```python
   class PDFViewer(QWidget):
       page_changed = pyqtSignal(int)  # Emits page number
       zoom_changed = pyqtSignal(float)  # Emits zoom level
   ```

3. **Create reusable widgets**:
   ```python
   class ColorPickerButton(QPushButton):
       """Reusable color picker button widget."""
       color_changed = pyqtSignal(QColor)
   ```

## Testing

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=. --cov-report=html

# Run specific test file
uv run pytest tests/test_pdf_document.py

# Run specific test
uv run pytest tests/test_pdf_document.py::test_create_new_document

# Run with verbose output
uv run pytest -v
```

### Writing Tests

1. **Test file naming**: `test_<module_name>.py`

2. **Test function naming**: `test_<what_is_being_tested>`

3. **Use fixtures** for common setup:
   ```python
   import pytest
   from core.pdf_document import PDFDocument

   @pytest.fixture
   def empty_document():
       """Create an empty PDF document for testing."""
       doc = PDFDocument()
       doc.create_new()
       doc.add_blank_page()
       yield doc
       doc.close()

   @pytest.fixture
   def sample_pdf(tmp_path):
       """Create a sample PDF file for testing."""
       pdf_path = tmp_path / "sample.pdf"
       doc = PDFDocument()
       doc.create_new()
       doc.add_blank_page()
       doc.save(pdf_path)
       doc.close()
       return pdf_path
   ```

4. **Test structure** (Arrange-Act-Assert):
   ```python
   def test_add_blank_page_increases_page_count(empty_document):
       # Arrange
       initial_count = empty_document.page_count

       # Act
       empty_document.add_blank_page()

       # Assert
       assert empty_document.page_count == initial_count + 1
   ```

5. **Test edge cases**:
   ```python
   def test_delete_page_with_invalid_index_raises_error(empty_document):
       with pytest.raises(IndexError):
           empty_document.delete_page(999)

   def test_operations_on_closed_document_raise_error():
       doc = PDFDocument()
       with pytest.raises(ValueError, match="No document is open"):
           doc.add_blank_page()
   ```

### Test Categories

- **Unit tests**: Test individual functions/methods in isolation
- **Integration tests**: Test multiple components working together
- **UI tests**: Test user interface interactions (using pytest-qt)

```python
# UI test example
def test_new_document_button(qtbot, main_window):
    qtbot.mouseClick(main_window.new_button, Qt.MouseButton.LeftButton)
    assert main_window._document.is_open
    assert main_window._document.page_count == 1
```

## Submitting Changes

### Branch Naming

Use descriptive branch names:
- `feature/add-watermark-support`
- `bugfix/fix-merge-crash`
- `docs/update-readme`
- `refactor/simplify-pdf-viewer`

### Commit Messages

Follow conventional commits format:

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types**:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

**Examples**:
```
feat(annotations): add arrow annotation tool

Implement arrow annotation with customizable head styles.
Supports solid, open, and diamond arrow heads.

Closes #123
```

```
fix(viewer): prevent crash when opening corrupted PDF

Add error handling for malformed PDF structures.
Display user-friendly error message instead of crashing.
```

### Before Submitting

1. **Update your branch**:
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run all checks**:
   ```bash
   uv run ruff check .
   uv run pytest
   ```

3. **Test manually**:
   - Open the application
   - Test your changes
   - Test related functionality

## Issue Guidelines

### Reporting Bugs

Use the bug report template and include:

1. **Environment**:
   - OS and version
   - Python version
   - Ultra PDF Editor version

2. **Steps to reproduce**:
   ```
   1. Open application
   2. Click File → Open
   3. Select a PDF with forms
   4. Click on form field
   5. Application crashes
   ```

3. **Expected vs actual behavior**

4. **Error messages** (full traceback if available)

5. **Sample file** (if possible and not confidential)

### Requesting Features

1. **Describe the problem** you're trying to solve
2. **Propose a solution** if you have one
3. **Provide examples** of how it would be used
4. **Note any alternatives** you've considered

## Pull Request Process

### Creating a Pull Request

1. **Create a descriptive title**:
   - Good: "Add support for PDF/A export format"
   - Bad: "Fix stuff" or "Update code"

2. **Fill out the PR template**:
   - Description of changes
   - Related issues
   - Testing performed
   - Screenshots (for UI changes)

3. **Keep PRs focused**:
   - One feature or fix per PR
   - Split large changes into smaller PRs

### Review Process

1. **Automated checks** must pass:
   - Linting (Ruff)
   - Tests (pytest)
   - Type checking (if configured)

2. **Code review**:
   - At least one approval required
   - Address all feedback
   - Request re-review after changes

3. **Merge requirements**:
   - All checks passing
   - Approved by maintainer
   - No merge conflicts
   - Up to date with main branch

### After Merge

- Delete your feature branch
- Update local main: `git pull upstream main`
- Celebrate your contribution!

## Questions?

- Open a [Discussion](https://github.com/your-org/ultra-pdf-editor/discussions) for general questions
- Join our community chat (if available)
- Email maintainers for sensitive issues

---

Thank you for contributing to Ultra PDF Editor!
