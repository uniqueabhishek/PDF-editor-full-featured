"""Tests for the core PDFDocument model (headless, no Qt)."""
from pathlib import Path

import fitz
import pytest

from core.pdf_document import PDFDocument


@pytest.fixture
def opened(sample_pdf):
    doc = PDFDocument()
    assert doc.open(sample_pdf) is True
    yield doc
    doc.close()


def test_open_sets_state(opened, sample_pdf):
    assert opened.is_open
    assert opened.page_count == 3
    assert opened.filepath == Path(sample_pdf)
    assert opened.doc is not None
    assert opened.is_modified is False


def test_open_missing_file_raises():
    doc = PDFDocument()
    with pytest.raises(FileNotFoundError):
        doc.open("does_not_exist.pdf")


def test_create_new_and_add_blank_page():
    doc = PDFDocument()
    assert doc.create_new() is True
    assert doc.page_count == 0
    assert doc.add_blank_page() == 0
    assert doc.page_count == 1
    assert doc.is_modified is True
    doc.close()


def test_add_blank_page_at_index(opened):
    opened.add_blank_page(index=1)
    assert opened.page_count == 4


def test_delete_page(opened):
    opened.delete_page(0)
    assert opened.page_count == 2


def test_delete_pages_handles_descending_indices(opened):
    opened.delete_pages([0, 2])
    assert opened.page_count == 1


def test_rotate_page_accumulates(opened):
    opened.rotate_page(0, 90)
    assert opened.get_page_info(0).rotation == 90
    opened.rotate_page(0, 90)
    assert opened.get_page_info(0).rotation == 180


def test_move_page_preserves_all_pages(opened):
    before = sorted(opened.get_page_text(i).strip() for i in range(3))
    opened.move_page(0, 2)
    after = sorted(opened.get_page_text(i).strip() for i in range(3))
    assert before == after
    assert opened.page_count == 3


def test_copy_page_increases_count(opened):
    before = opened.page_count
    opened.copy_page(0)
    assert opened.page_count == before + 1


def test_extract_pages(opened, tmp_path):
    out = tmp_path / "extract.pdf"
    assert opened.extract_pages([0, 2], out) is True
    assert out.exists()
    check = fitz.open(str(out))
    assert len(check) == 2
    check.close()


def test_get_page_text(opened):
    assert "page 1" in opened.get_page_text(0)


def test_search_text_finds_page(opened):
    results = opened.search_text("page 2")
    assert any(r["page"] == 1 for r in results)
    assert all("rects" in r for r in results)


def test_metadata_round_trip(opened):
    opened.set_metadata({"title": "My Title", "author": "Tester"})
    meta = opened.get_metadata()
    assert meta.title == "My Title"
    assert meta.author == "Tester"
    assert meta.page_count == 3


def test_save_round_trip(opened, tmp_path):
    opened.add_blank_page()
    out = tmp_path / "saved.pdf"
    assert opened.save(out) is True
    assert opened.is_modified is False

    reopened = PDFDocument()
    reopened.open(out)
    assert reopened.page_count == 4
    reopened.close()


def test_save_copy_keeps_current_path(opened, tmp_path):
    original = opened.filepath
    out = tmp_path / "copy.pdf"
    assert opened.save_copy(out) is True
    assert out.exists()
    assert opened.filepath == original


def test_save_copy_requires_open_document():
    doc = PDFDocument()
    with pytest.raises(ValueError):
        doc.save_copy("nope.pdf")


def test_add_highlight_applies_style(opened):
    annot = opened.add_highlight(0, (72, 92, 200, 108), color=(0, 1, 1), opacity=0.4)
    assert annot is not None
    assert opened.is_modified is True
    assert abs(annot.opacity - 0.4) < 0.02


def test_mark_modified_toggles_flag():
    doc = PDFDocument()
    doc.create_new()
    doc.mark_modified(False)
    assert doc.is_modified is False
    doc.mark_modified()
    assert doc.is_modified is True
    doc.close()


def test_merge_pdfs(make_pdf, tmp_path):
    a = make_pdf("a.pdf", pages=2)
    b = make_pdf("b.pdf", pages=3)
    out = tmp_path / "merged.pdf"

    assert PDFDocument().merge_pdfs([a, b], out) is True
    check = fitz.open(str(out))
    assert len(check) == 5
    check.close()


def test_close_resets_state(opened):
    opened.close()
    assert opened.is_open is False
    assert opened.doc is None
    assert opened.page_count == 0
