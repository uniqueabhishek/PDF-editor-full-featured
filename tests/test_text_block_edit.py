"""Tests for the inline text-editing engine (detect + reflow-replace).

Headless / no Qt — exercises core/pdf_document.py directly.
"""
import fitz
import pytest

from core.pdf_document import (
    PDFDocument,
    _SPAN_FLAG_BOLD, _SPAN_FLAG_ITALIC, _SPAN_FLAG_SERIF, _SPAN_FLAG_MONO,
    _MIN_EDIT_FONTSIZE,
)


@pytest.fixture
def doc(tmp_path):
    """A 1-page PDF model with one known line of text."""
    p = tmp_path / "edit.pdf"
    d = fitz.open()
    page = d.new_page(width=400, height=300)
    page.insert_text((72, 100), "The quick brown fox", fontsize=14)
    d.save(str(p))
    d.close()
    model = PDFDocument()
    assert model.open(p) is True
    yield model
    model.close()


def _block_center(model, page_num=0):
    page = model.doc[page_num]
    blk = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0][0]
    x0, y0, x1, y1 = blk["bbox"]
    return ((x0 + x1) / 2, (y0 + y1) / 2)


def test_detect_returns_text_bbox_style(doc):
    info = doc.detect_text_block(0, _block_center(doc))
    assert info is not None
    assert "quick" in info["text"]
    x0, y0, x1, y1 = info["bbox"]
    cx, cy = _block_center(doc)
    assert x0 <= cx <= x1 and y0 <= cy <= y1
    assert abs(info["style"]["fontsize"] - 14.0) < 1.0
    assert info["style"]["color"] == (0.0, 0.0, 0.0)


def test_detect_off_text_returns_none(doc):
    assert doc.detect_text_block(0, (5, 5)) is None  # empty corner


def test_detect_on_blank_page_returns_none(tmp_path):
    p = tmp_path / "blank.pdf"
    d = fitz.open()
    d.new_page()
    d.save(str(p))
    d.close()
    model = PDFDocument()
    model.open(p)
    try:
        assert model.detect_text_block(0, (100, 100)) is None
    finally:
        model.close()


def test_replace_roundtrip(doc):
    info = doc.detect_text_block(0, _block_center(doc))
    res = doc.replace_text_block(0, info["bbox"], "The quick brown cat", info["style"])
    assert res["truncated"] is False
    text = doc.doc[0].get_text("text")
    assert "cat" in text
    assert "fox" not in text          # proves redact-then-write order
    assert doc.is_modified is True


def test_fallback_fontname_matrix():
    f = PDFDocument._fallback_fontname
    assert f(0) == "helv"
    assert f(_SPAN_FLAG_BOLD) == "hebo"
    assert f(_SPAN_FLAG_ITALIC) == "heit"
    assert f(_SPAN_FLAG_BOLD | _SPAN_FLAG_ITALIC) == "hebi"
    assert f(_SPAN_FLAG_SERIF) == "tiro"
    assert f(_SPAN_FLAG_SERIF | _SPAN_FLAG_BOLD) == "tibo"
    assert f(_SPAN_FLAG_MONO) == "cour"
    assert f(_SPAN_FLAG_MONO | _SPAN_FLAG_ITALIC) == "coit"


def test_int_color_to_rgb():
    c = PDFDocument._int_color_to_rgb
    assert c(0xFF0000) == (1.0, 0.0, 0.0)
    assert c(0x000000) == (0.0, 0.0, 0.0)
    assert c(0xFFFFFF) == (1.0, 1.0, 1.0)
    assert c(0x0000FF) == (0.0, 0.0, 1.0)


def test_font_covers():
    helv = fitz.Font("helv")
    assert PDFDocument._font_covers(helv, "hello world") is True
    assert PDFDocument._font_covers(helv, "中文") is False  # CJK absent from helv


def test_overflow_shrinks_fontsize(doc):
    info = doc.detect_text_block(0, _block_center(doc))
    # A deliberately tiny target box with far too much text.
    x0, y0, _x1, _y1 = info["bbox"]
    tiny = (x0, y0, x0 + 40, y0 + 14)
    long_text = ("alpha beta gamma delta epsilon zeta eta theta "
                 "iota kappa lambda mu nu xi omicron pi")
    res = doc.replace_text_block(0, tiny, long_text, info["style"])
    assert res["fontsize_used"] < info["style"]["fontsize"]
    assert res["fontsize_used"] >= _MIN_EDIT_FONTSIZE


def test_undo_restores_original(doc):
    before = doc.snapshot()
    info = doc.detect_text_block(0, _block_center(doc))
    doc.replace_text_block(0, info["bbox"], "Totally different words", info["style"])
    assert "fox" not in doc.doc[0].get_text("text")
    doc.restore(before)
    assert "fox" in doc.doc[0].get_text("text")
