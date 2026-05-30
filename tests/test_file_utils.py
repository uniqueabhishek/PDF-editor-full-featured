"""Tests for the pure file-utility helpers (headless)."""
import hashlib
from pathlib import Path

from utils.file_utils import (
    format_file_size, sanitize_filename, ensure_extension,
    get_unique_filename, validate_pdf, get_file_hash,
    get_pdf_page_count, is_pdf_encrypted, list_pdfs_in_directory,
)


def test_format_file_size():
    assert format_file_size(0) == "0.0 B"
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1536) == "1.5 KB"
    assert format_file_size(1024 ** 2) == "1.0 MB"
    assert format_file_size(1024 ** 3) == "1.0 GB"


def test_sanitize_filename_replaces_invalid_chars():
    assert sanitize_filename('a<b>c:d"e/f\\g|h?i*j') == "a_b_c_d_e_f_g_h_i_j"
    assert sanitize_filename("  spaced.pdf  ") == "spaced.pdf"


def test_ensure_extension():
    assert ensure_extension(Path("file.txt"), ".pdf") == Path("file.pdf")
    assert ensure_extension(Path("file"), "pdf") == Path("file.pdf")
    # already correct (case-insensitive) -> unchanged
    assert ensure_extension(Path("file.PDF"), ".pdf") == Path("file.PDF")


def test_get_unique_filename(tmp_path):
    first = get_unique_filename(tmp_path, "doc", ".pdf")
    assert first.name == "doc.pdf"
    first.write_text("x", encoding="utf-8")
    second = get_unique_filename(tmp_path, "doc", ".pdf")
    assert second.name == "doc_1.pdf"


def test_validate_pdf(sample_pdf, tmp_path):
    ok, _ = validate_pdf(Path(sample_pdf))
    assert ok is True

    not_pdf = tmp_path / "note.txt"
    not_pdf.write_text("hello", encoding="utf-8")
    assert validate_pdf(not_pdf)[0] is False

    assert validate_pdf(tmp_path / "missing.pdf")[0] is False


def test_validate_pdf_rejects_bad_header(tmp_path):
    fake = tmp_path / "fake.pdf"
    fake.write_bytes(b"not a pdf at all")
    ok, msg = validate_pdf(fake)
    assert ok is False
    assert "header" in msg.lower()


def test_get_file_hash_matches_md5(tmp_path):
    f = tmp_path / "data.bin"
    f.write_bytes(b"hello world")
    assert get_file_hash(f) == hashlib.md5(b"hello world").hexdigest()


def test_get_pdf_page_count(sample_pdf):
    assert get_pdf_page_count(Path(sample_pdf)) == 3


def test_is_pdf_encrypted_false(sample_pdf):
    assert is_pdf_encrypted(Path(sample_pdf)) is False


def test_list_pdfs_in_directory(make_pdf, tmp_path):
    make_pdf("one.pdf")
    make_pdf("two.pdf")
    (tmp_path / "note.txt").write_text("x", encoding="utf-8")
    names = sorted(p.name for p in list_pdfs_in_directory(tmp_path))
    assert names == ["one.pdf", "two.pdf"]
