"""GUI-level tests for the Edit Text tool (offscreen Qt via conftest)."""
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

import fitz  # noqa: E402
from PyQt6.QtCore import QPointF  # noqa: E402

from core.pdf_document import PDFDocument  # noqa: E402
from ui.pdf_viewer import PDFViewer  # noqa: E402


def _viewer_with_text(qtbot, tmp_path, text="Hello world"):
    p = tmp_path / "edit.pdf"
    d = fitz.open()
    page = d.new_page(width=400, height=300)
    page.insert_text((72, 100), text, fontsize=14)
    d.save(str(p))
    d.close()
    model = PDFDocument()
    model.open(p)
    v = PDFViewer()
    qtbot.addWidget(v)
    v.set_document(model.doc, str(p))
    v.set_text_block_provider(model.detect_text_block)
    return v, model


def _block_center(model):
    page = model.doc[0]
    blk = [b for b in page.get_text("dict")["blocks"] if b["type"] == 0][0]
    x0, y0, x1, y1 = blk["bbox"]
    return QPointF((x0 + x1) / 2, (y0 + y1) / 2)


def test_inline_edit_commit_emits_signal(qtbot, tmp_path):
    v, model = _viewer_with_text(qtbot, tmp_path)
    try:
        v._on_edit_text_requested(0, _block_center(model))
        assert v._inline_editor is not None
        v._inline_editor.setPlainText("Hello there")
        with qtbot.waitSignal(v.edit_text_committed, timeout=1000) as blocker:
            v._inline_editor.commit()
        page_num, _bbox, text, _style = blocker.args
        assert page_num == 0
        assert text == "Hello there"
        assert v._inline_editor is None        # torn down after commit
    finally:
        v._render_worker.stop()
        model.close()


def test_editor_sizes_to_show_full_text(qtbot, tmp_path):
    # A long header would wrap out of a one-line box; the editor must size itself
    # so the whole paragraph is visible (regression for the clipped-text bug).
    v, model = _viewer_with_text(
        qtbot, tmp_path, text="Electronic Reservation Slip (ERS)-Normal User")
    try:
        v.resize(900, 600)
        v._on_edit_text_requested(0, _block_center(model))
        ed = v._inline_editor
        assert ed is not None
        assert ed.toPlainText().endswith("Normal User")
        content_h = ed.document().size().height()
        viewport_h = ed.height() - 2 * ed.frameWidth()
        assert viewport_h + 2 >= content_h      # nothing clipped vertically
    finally:
        v._render_worker.stop()
        model.close()


def test_double_click_in_text_tool_requests_edit(qtbot, tmp_path):
    from PyQt6.QtGui import QMouseEvent
    from PyQt6.QtCore import QEvent, Qt
    v, model = _viewer_with_text(qtbot, tmp_path)
    try:
        pw = v._page_widgets[0]
        pw.set_tool_mode("text_select")        # the default tool — no separate button
        got = []
        pw.edit_text_requested.connect(lambda p, pt: got.append(p))
        ev = QMouseEvent(
            QEvent.Type.MouseButtonDblClick, QPointF(5, 5),
            Qt.MouseButton.LeftButton, Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.NoModifier)
        pw.mouseDoubleClickEvent(ev)
        assert got == [0]                      # double-click asked to edit page 0
    finally:
        v._render_worker.stop()
        model.close()


def test_inline_edit_unavailable_when_no_block(qtbot, tmp_path):
    d = fitz.open()
    d.new_page()
    v = PDFViewer()
    qtbot.addWidget(v)
    v.set_document(d, "x.pdf")
    v.set_text_block_provider(lambda pn, pt: None)
    try:
        with qtbot.waitSignal(v.edit_text_unavailable, timeout=1000):
            v._on_edit_text_requested(0, QPointF(10, 10))
    finally:
        v._render_worker.stop()
        d.close()


def test_unchanged_text_emits_nothing(qtbot, tmp_path):
    v, model = _viewer_with_text(qtbot, tmp_path, text="Same text")
    fired = []
    v.edit_text_committed.connect(lambda *a: fired.append(a))
    try:
        v._on_edit_text_requested(0, _block_center(model))
        assert v._inline_editor is not None
        v._inline_editor.commit()              # committed without editing
        assert fired == []                     # no undoable op for a no-op edit
    finally:
        v._render_worker.stop()
        model.close()
