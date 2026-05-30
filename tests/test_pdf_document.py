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


# ==================== Encryption ====================

def test_encrypt_then_save_requires_password(opened, tmp_path):
    out = tmp_path / "encrypted.pdf"
    assert opened.encrypt(user_password="s3cret") is True
    assert opened.save(out) is True

    # The freshly written file must actually demand the password.
    raw = fitz.open(str(out))
    try:
        assert raw.needs_pass  # PyMuPDF returns an int flag, not a bool
        assert raw.authenticate("wrong") == 0
        assert raw.authenticate("s3cret") > 0
    finally:
        raw.close()


def test_encrypt_save_in_place_overwrites_with_encrypted(make_pdf):
    src = make_pdf("plain.pdf", pages=2)
    doc = PDFDocument()
    assert doc.open(src) is True
    assert doc.encrypt(user_password="pw123") is True
    assert doc.save() is True  # in-place full rewrite via temp file
    doc.close()

    raw = fitz.open(str(src))
    try:
        assert raw.needs_pass
        assert raw.authenticate("pw123") > 0
    finally:
        raw.close()


def test_plain_save_is_not_encrypted(opened, tmp_path):
    out = tmp_path / "plain_out.pdf"
    assert opened.save(out) is True
    raw = fitz.open(str(out))
    try:
        assert not raw.needs_pass
    finally:
        raw.close()


def test_encryption_request_is_cleared_after_save(opened, tmp_path):
    opened.encrypt(user_password="once")
    opened.save(tmp_path / "enc1.pdf")

    # A subsequent save to a new path must NOT re-encrypt.
    out2 = tmp_path / "enc2.pdf"
    opened.save(out2)
    raw = fitz.open(str(out2))
    try:
        assert not raw.needs_pass
    finally:
        raw.close()


def test_encrypt_requires_a_password(opened):
    with pytest.raises(ValueError):
        opened.encrypt()


# ==================== Snapshot / restore (undo support) ====================

def test_snapshot_restore_round_trip(opened):
    original = opened.get_page_text(0)
    assert "page 1" in original

    snap = opened.snapshot()
    opened.redact_area(0, opened.doc[0].rect)  # wipe page 0
    assert opened.get_page_text(0).strip() == ""

    opened.restore(snap)
    assert "page 1" in opened.get_page_text(0)
    assert opened.page_count == 3


def test_restore_swaps_document_object(opened):
    snap = opened.snapshot()
    before = opened.doc
    opened.restore(snap)
    # restore() rebuilds the document, so the underlying object must change
    # (callers holding the old doc need to re-fetch it).
    assert opened.doc is not before
    assert opened.page_count == 3


def test_snapshot_requires_open_document():
    doc = PDFDocument()
    with pytest.raises(ValueError):
        doc.snapshot()


def test_render_worker_copy_opens_and_renders_without_password(make_pdf, tmp_path):
    """The viewer hands the render thread a decrypted, in-memory copy.

    Validates the core assumption of the isolated-render-thread design: an
    authenticated (originally encrypted) document can be serialized to a
    password-free copy that opens and renders on its own.
    """
    src = make_pdf("enc_src.pdf", pages=2)
    d = PDFDocument()
    d.open(src)
    d.encrypt(user_password="pw")
    out = tmp_path / "enc.pdf"
    d.save(out)
    d.close()

    doc = PDFDocument()
    assert doc.open(out, password="pw") is True
    # Same serialization the viewer's _render_source() uses for the worker copy.
    data = doc.doc.tobytes(garbage=0, deflate=True, encryption=fitz.PDF_ENCRYPT_NONE)
    doc.close()

    copy = fitz.open(stream=data, filetype="pdf")
    try:
        assert not copy.needs_pass
        pm = copy[0].get_pixmap()
        assert pm.width > 0 and pm.height > 0
    finally:
        copy.close()
