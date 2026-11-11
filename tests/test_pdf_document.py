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


def test_search_case_sensitive_filters(tmp_path):
    p = tmp_path / "case.pdf"
    d = fitz.open()
    page = d.new_page(width=300, height=200)
    page.insert_text((50, 50), "Apple")
    page.insert_text((50, 100), "apple")
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        insensitive = doc.search_text("apple", case_sensitive=False)
        assert sum(len(r["rects"]) for r in insensitive) == 2
        sensitive = doc.search_text("apple", case_sensitive=True)
        assert sum(len(r["rects"]) for r in sensitive) == 1
    finally:
        doc.close()


def test_case_sensitive_matches_get_textbox_reference(tmp_path):
    """The fast per-page character lookup must keep exactly the hits the old
    per-hit ``get_textbox()`` filter kept, including mixed-case runs."""
    p = tmp_path / "mixed.pdf"
    d = fitz.open()
    page = d.new_page()
    page.insert_textbox(fitz.Rect(50, 50, 545, 800),
                        "lorem Lorem LOREM xLoremx Loremipsum dolor. " * 6,
                        fontsize=11)
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        pg = doc.doc[0]
        for term in ("Lorem", "lorem", "LOREM", "m Lo"):
            hits = pg.search_for(term, flags=fitz.TEXT_PRESERVE_WHITESPACE)
            expected = [tuple(r) for r in hits if term in pg.get_textbox(r)]
            got = [tuple(r) for res in doc.search_text(term, case_sensitive=True)
                   for r in res["rects"]]
            assert got == expected, term
    finally:
        doc.close()


def test_replace_text_all(tmp_path):
    p = tmp_path / "rep.pdf"
    d = fitz.open()
    for _ in range(2):
        pg = d.new_page(width=400, height=200)
        pg.insert_text((50, 100), "alpha beta alpha", fontsize=12)
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        assert doc.replace_text_all("alpha", "gamma") == 4  # 2 per page x 2 pages
        assert doc.search_text("alpha") == []
        assert sum(len(r["rects"]) for r in doc.search_text("gamma")) == 4
        assert doc.is_modified is True
    finally:
        doc.close()


def test_replace_all_keeps_each_lines_font_size(tmp_path, monkeypatch):
    """Replacement text takes the size of its own line, not a neighbour's."""
    queued = []
    real = PDFDocument._queue_replacement
    monkeypatch.setattr(PDFDocument, "_queue_replacement", staticmethod(
        lambda page, rect, text, size: (queued.append(size),
                                        real(page, rect, text, size))))
    p = tmp_path / "sizes.pdf"
    d = fitz.open()
    pg = d.new_page()
    y = 80
    for fs in (8, 11, 14, 20):
        pg.insert_text((72, y), f"tempor at {fs}", fontsize=fs)
        y += fs * 1.6
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        assert doc.replace_text_all("tempor", "XX") == 4
        assert [round(s) for s in queued] == [8, 11, 14, 20]
    finally:
        doc.close()


def test_replace_all_in_copy_reports_progress_and_cancels(tmp_path):
    p = tmp_path / "copy.pdf"
    d = fitz.open()
    for _ in range(4):
        d.new_page().insert_text((50, 100), "alpha beta", fontsize=12)
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        data, pw = doc.worker_copy()
        seen = []
        new_bytes, count = PDFDocument.replace_text_all_in_copy(
            data, pw, "alpha", "omega", False, lambda i, n: seen.append((i, n)))
        assert count == 4 and seen == [(i, 4) for i in range(4)]
        assert doc.search_text("omega") == [], "the live document was touched"
        doc.restore(new_bytes)
        assert len(doc.search_text("omega")) == 4

        cancelled = PDFDocument.replace_text_all_in_copy(
            data, pw, "alpha", "omega", False, None, lambda: True)
        assert cancelled == (None, 0)
    finally:
        doc.close()


def test_replace_text_all_case_sensitive(tmp_path):
    p = tmp_path / "repc.pdf"
    d = fitz.open()
    pg = d.new_page(width=400, height=200)
    pg.insert_text((50, 80), "Foo foo", fontsize=12)
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        assert doc.replace_text_all("foo", "bar", case_sensitive=True) == 1
        # The capitalised "Foo" is untouched.
        assert sum(len(r["rects"])
                   for r in doc.search_text("Foo", case_sensitive=True)) == 1
    finally:
        doc.close()


def test_replace_text_one(tmp_path):
    p = tmp_path / "rep1.pdf"
    d = fitz.open()
    pg = d.new_page(width=400, height=200)
    pg.insert_text((50, 100), "one two one", fontsize=12)
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    assert doc.open(p) is True
    try:
        rects = doc.search_text("one")[0]["rects"]
        assert len(rects) == 2
        assert doc.replace_text_one(0, rects[0], "xyz") is True
        assert sum(len(r["rects"]) for r in doc.search_text("one")) == 1
    finally:
        doc.close()


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


def test_in_place_save_after_page_delete_is_not_corrupt(make_pdf):
    """A structural edit saved in place must leave a file with a valid xref.

    Regression: a buggy incremental save appended a self-referential /Prev after
    a page deletion, producing an infinite xref loop. Lenient readers auto-repair
    it, so it looked fine on screen but was invalid — MuPDF's is_repaired flag
    catches exactly that.
    """
    src = make_pdf("struct.pdf", pages=5)
    doc = PDFDocument()
    assert doc.open(src) is True
    doc.delete_page(2)
    assert doc.save() is True  # in place
    doc.close()

    check = fitz.open(str(src))
    try:
        assert check.is_repaired is False
        assert len(check) == 4
    finally:
        check.close()


def test_incremental_output_ok_accepts_clean_file(opened, tmp_path):
    good = tmp_path / "good.pdf"
    opened.doc.save(str(good))
    assert opened._incremental_output_ok(good) is True


def test_incremental_output_ok_rejects_repaired_file(opened, tmp_path):
    import re

    good = tmp_path / "good.pdf"
    opened.doc.save(str(good))
    # Point startxref at a bogus offset so the reader can't find the xref table
    # and must rebuild it via a full scan — MuPDF sets is_repaired for this.
    broken = re.sub(rb"startxref\s+\d+", b"startxref\n9999999",
                    good.read_bytes(), count=1)
    broken_path = tmp_path / "broken.pdf"
    broken_path.write_bytes(broken)
    assert opened._incremental_output_ok(broken_path) is False


def test_save_falls_back_to_full_rewrite_when_incremental_is_broken(opened, monkeypatch):
    """When the incremental output fails its integrity check, save() must redo
    the write as a clean full rewrite instead of trusting the damaged file."""
    opened.delete_page(0)
    before = opened.doc  # the live fitz.Document

    monkeypatch.setattr(opened, "_incremental_output_ok", lambda p: False)
    assert opened.save() is True

    # A full rewrite via temp closes and reopens the document, so the underlying
    # fitz object is a fresh instance — proof the fallback path ran.
    assert opened.doc is not before
    assert opened.page_count == 2

    check = fitz.open(str(opened.filepath))
    try:
        assert check.is_repaired is False
        assert len(check) == 2
    finally:
        check.close()


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


def test_compress_in_place_full_rewrites(opened):
    # Compressing with no output path saves over the current file; full_rewrite
    # must force a real rewrite (not a no-op incremental save) and reopen cleanly.
    assert opened.compress() is True
    assert opened.is_open
    assert opened.page_count == 3


def test_compress_to_new_path(opened, tmp_path):
    out = tmp_path / "compressed.pdf"
    assert opened.compress(out) is True
    assert out.exists()
    check = fitz.open(str(out))
    try:
        assert len(check) == 3
    finally:
        check.close()


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


def test_set_filepath_retargets(opened, tmp_path):
    new = tmp_path / "other.pdf"
    opened.set_filepath(new)
    assert opened.filepath == new
    opened.set_filepath(None)
    assert opened.filepath is None


def test_merge_pdfs(make_pdf, tmp_path):
    a = make_pdf("a.pdf", pages=2)
    b = make_pdf("b.pdf", pages=3)
    out = tmp_path / "merged.pdf"

    assert PDFDocument().merge_pdfs([a, b], out) is True
    check = fitz.open(str(out))
    assert len(check) == 5
    check.close()


def test_merge_pdfs_adds_bookmark_per_file(make_pdf, tmp_path):
    a = make_pdf("intro.pdf", pages=2)
    b = make_pdf("body.pdf", pages=3)
    out = tmp_path / "merged_bm.pdf"

    assert PDFDocument().merge_pdfs([a, b], out, add_bookmarks=True) is True
    check = fitz.open(str(out))
    try:
        toc = check.get_toc()
        assert [(e[1], e[2]) for e in toc] == [("intro", 1), ("body", 3)]
    finally:
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


def test_plain_document_is_not_protected(opened):
    assert opened.is_protected is False


def test_is_protected_after_encrypt_request(opened):
    opened.encrypt(user_password="pw123")
    # Encryption is queued (pending) before save — already counts as protected
    # so auto-save won't write a plaintext copy.
    assert opened.is_protected is True


def test_is_protected_for_password_protected_file(make_pdf):
    src = make_pdf("secret.pdf", pages=1)
    doc = PDFDocument()
    assert doc.open(src) is True
    doc.encrypt(user_password="pw123")
    assert doc.save() is True
    doc.close()

    reopened = PDFDocument()
    assert reopened.open(src, password="pw123") is True
    assert reopened.is_protected is True
    reopened.close()


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


# ==================== Bookmarks / TOC ====================

def test_add_bookmark_persists_in_toc(opened):
    assert opened.get_toc() == []
    opened.add_bookmark("Chapter 1", page_num=0)
    opened.add_bookmark("Chapter 2", page_num=2)
    toc = opened.get_toc()
    titles = [entry[1] for entry in toc]
    assert titles == ["Chapter 1", "Chapter 2"]
    # TOC pages are 1-indexed.
    assert toc[1][2] == 3


def test_set_toc_round_trips_through_save(opened, tmp_path):
    opened.set_toc([[1, "Intro", 1], [1, "Body", 2]])
    out = tmp_path / "with_toc.pdf"
    opened.save(out)

    reopened = PDFDocument()
    reopened.open(out)
    try:
        titles = [e[1] for e in reopened.get_toc()]
        assert titles == ["Intro", "Body"]
    finally:
        reopened.close()


# ==================== Page reorder ====================

def test_reorder_pages_changes_order(opened):
    before = [opened.get_page_text(i).strip() for i in range(3)]
    opened.reorder_pages([2, 0, 1])
    after = [opened.get_page_text(i).strip() for i in range(3)]
    assert after == [before[2], before[0], before[1]]
    assert opened.page_count == 3


def test_reorder_pages_remaps_bookmarks(opened):
    # Bookmark each page, then reorder so page 3 -> 1, page 1 -> 2, page 2 -> 3.
    opened.set_toc([[1, "BM1", 1], [1, "BM2", 2], [1, "BM3", 3]])
    opened.reorder_pages([2, 0, 1])
    toc = {title: page for _level, title, page in opened.get_toc()}
    # The bookmark that pointed at old page 3 now points at new page 1, etc.
    assert toc == {"BM1": 2, "BM2": 3, "BM3": 1}


def test_reorder_pages_requires_open_document():
    doc = PDFDocument()
    with pytest.raises(ValueError):
        doc.reorder_pages([0])


# ==================== Split ====================

def test_split_by_pages_every_n(opened, tmp_path):
    files = opened.split_by_pages(tmp_path, pages_per_file=2)
    # 3 pages, 2 per file -> 2 files (2 + 1).
    assert len(files) == 2
    first = fitz.open(files[0])
    assert len(first) == 2
    first.close()


def test_split_by_ranges(opened, tmp_path):
    files = opened.split_by_ranges([(0, 0), (1, 2)], tmp_path)
    assert len(files) == 2
    second = fitz.open(files[1])
    assert len(second) == 2
    second.close()


def test_split_by_bookmarks(opened, tmp_path):
    opened.set_toc([[1, "Chapter A", 1], [1, "Chapter B", 3]])
    files = opened.split_by_bookmarks(tmp_path)
    assert len(files) == 2
    # Chapter A spans pages 1-2, Chapter B page 3.
    a = fitz.open(files[0])
    b = fitz.open(files[1])
    try:
        assert len(a) == 2
        assert len(b) == 1
    finally:
        a.close()
        b.close()


def test_split_by_bookmarks_without_toc_raises(opened, tmp_path):
    with pytest.raises(ValueError):
        opened.split_by_bookmarks(tmp_path)


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
