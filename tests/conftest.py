"""
Shared pytest fixtures for Ultra PDF Editor.

These tests exercise the headless core (no Qt / no display required): document
model, undo/redo, settings and file utilities.
"""
import sys
from pathlib import Path

import pytest

# The project uses a flat layout (core/, config.py, utils/ at the repo root) and
# is run from source, so make the repo root importable for the test session.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import fitz  # noqa: E402  (import after sys.path setup)


def _build_pdf(path: Path, pages: int, text: str) -> Path:
    """Create a simple multi-page PDF with one distinct text line per page."""
    doc = fitz.open()
    for i in range(pages):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"{text} page {i + 1}", fontsize=14)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def make_pdf(tmp_path):
    """Factory fixture: make_pdf(name, pages, text) -> Path to a created PDF."""
    def _factory(name: str = "sample.pdf", pages: int = 3, text: str = "Hello World") -> Path:
        return _build_pdf(tmp_path / name, pages, text)
    return _factory


@pytest.fixture
def sample_pdf(make_pdf):
    """A 3-page PDF with searchable text."""
    return make_pdf()
