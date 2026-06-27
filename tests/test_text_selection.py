"""Tests for the word-based (Acrobat-style) Text Select tool.

Covers the selection algorithm (reading order, cross-line spans), the
clipboard/status wiring, and tool-switch clearing. Run headless via the
offscreen Qt platform configured in conftest.
"""
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

import fitz  # noqa: E402
from PyQt6.QtWidgets import QApplication  # noqa: E402
from PyQt6.QtCore import QPointF  # noqa: E402


@pytest.fixture
def viewer(qtbot):
    """A PDFViewer showing a 1-page doc with two known lines of text."""
    from ui.pdf_viewer import PDFViewer
    doc = fitz.open()
    page = doc.new_page(width=400, height=300)
    page.insert_text((72, 100), "Hello world foo", fontsize=14)
    page.insert_text((72, 130), "second line here", fontsize=14)

    v = PDFViewer()
    qtbot.addWidget(v)
    v.set_document(doc, "t.pdf")
    yield v
    # Stop the background render thread so the test process exits cleanly.
    v._render_worker.stop()
    doc.close()


def _center(words, text):
    for w in words:
        if w[4] == text:
            return QPointF((w[0] + w[2]) / 2, (w[1] + w[3]) / 2)
    raise AssertionError(f"word {text!r} not found")


def test_words_are_in_reading_order(viewer):
    words = viewer.get_page_words(0)
    assert [w[4] for w in words] == [
        "Hello", "world", "foo", "second", "line", "here"]


def test_cross_line_selection_spans_partial_lines(viewer):
    from ui.pdf_viewer import PageWidget
    words = viewer.get_page_words(0)
    pw = PageWidget(0)
    pw._sel_words = words

    rects, text = pw._selection_for(
        _center(words, "world"), _center(words, "line"))
    # Tail of line 1 + head of line 2, one highlight rect per line.
    assert text == "world foo\nsecond line"
    assert len(rects) == 2


def test_single_word_and_full_selection(viewer):
    from ui.pdf_viewer import PageWidget
    words = viewer.get_page_words(0)
    pw = PageWidget(0)
    pw._sel_words = words

    _, single = pw._selection_for(
        _center(words, "Hello"), _center(words, "Hello"))
    assert single == "Hello"

    _, full = pw._selection_for(
        _center(words, "Hello"), _center(words, "here"))
    assert full == "Hello world foo\nsecond line here"


def test_selection_copies_and_reports_count(viewer, qtbot):
    with qtbot.waitSignal(viewer.selection_copied, timeout=1000) as blocker:
        viewer._on_text_selection_made(0, "alpha beta", [])
    assert blocker.args == [10]
    assert viewer.get_selected_text() == "alpha beta"
    assert QApplication.clipboard().text() == "alpha beta"


def test_context_menu_shows_only_copy_with_selection(viewer, monkeypatch):
    from PyQt6.QtWidgets import QMenu

    captured = {}

    def fake_exec(self, *args, **kwargs):
        captured["labels"] = [a.text() for a in self.actions() if a.text()]
        return None

    monkeypatch.setattr(QMenu, "exec", fake_exec)

    # No selection -> full menu (zoom/navigate/rotate present, no Copy).
    viewer.clear_selection()

    class _Evt:
        def globalPos(self):
            from PyQt6.QtCore import QPoint
            return QPoint(0, 0)

    viewer.contextMenuEvent(_Evt())
    assert "Copy" not in captured["labels"]
    assert any("Rotate" in lbl for lbl in captured["labels"])

    # With a selection -> only Copy.
    viewer._on_text_selection_made(0, "alpha beta", [])
    viewer.contextMenuEvent(_Evt())
    assert captured["labels"] == ["Copy"]


def test_switching_tool_clears_selection(viewer):
    from ui.pdf_viewer import ToolMode
    viewer._on_text_selection_made(0, "alpha beta", [])
    assert viewer.get_selected_text() == "alpha beta"
    viewer.set_tool_mode(ToolMode.HIGHLIGHT)
    assert viewer.get_selected_text() == ""


def test_page_without_text_layer_has_no_words(qtbot):
    from ui.pdf_viewer import PDFViewer
    doc = fitz.open()
    doc.new_page()  # blank, image-less page: no extractable words
    v = PDFViewer()
    qtbot.addWidget(v)
    v.set_document(doc, "blank.pdf")
    try:
        assert v.get_page_words(0) == []
        # A page widget signalling "no text" should surface the OCR hint.
        with qtbot.waitSignal(v.selection_needs_ocr, timeout=1000):
            v._page_widgets[0].selection_needs_text.emit(0)
    finally:
        v._render_worker.stop()
        doc.close()


def test_default_tool_is_text_select(qtbot):
    # NB: ui.toolbar and ui.pdf_viewer each define their own ToolMode enum;
    # they bridge via the string `.value`, so compare each with its own enum.
    from ui.pdf_viewer import PDFViewer
    from ui.pdf_viewer import ToolMode as ViewerToolMode
    from ui.toolbar import AnnotationToolbar
    from ui.toolbar import ToolMode as ToolbarToolMode

    tb = AnnotationToolbar()
    qtbot.addWidget(tb)
    assert tb.get_current_tool() == ToolbarToolMode.TEXT_SELECT

    v = PDFViewer()
    qtbot.addWidget(v)
    try:
        assert v._tool_mode == ViewerToolMode.TEXT_SELECT
    finally:
        v._render_worker.stop()
