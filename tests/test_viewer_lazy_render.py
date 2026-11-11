"""Only the pages actually on screen may be queued for rendering.

Regression: :meth:`PDFViewer._request_visible_pages` decided visibility from each
page widget's ``geometry()``. That is only populated once the scroll area has
sized its container and run the layout — a turn of the event loop *after*
``set_document()`` — so on the first pass every widget reported the same
position and the whole document looked visible. Opening an 84-page scan queued
all 84 pages and froze the window for 7-11s behind a screen of blank pages.
"""
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

import fitz  # noqa: E402

from core.pdf_document import PDFDocument  # noqa: E402
from ui.pdf_viewer import PDFViewer, _MAX_QUEUED_PAGE_RENDERS  # noqa: E402


@pytest.fixture
def many_pages(tmp_path):
    """A 60-page document whose pages are far taller than the viewport."""
    path = tmp_path / "many.pdf"
    doc = fitz.open()
    for i in range(60):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 100), f"page {i + 1}", fontsize=14)
    doc.save(str(path))
    doc.close()
    return path


def _viewer(qtbot, path, width=900, height=700):
    model = PDFDocument()
    model.open(path)
    v = PDFViewer()
    qtbot.addWidget(v)
    v.resize(width, height)
    v.set_document(model.doc, str(path))
    return v, model


def test_open_does_not_queue_every_page(qtbot, many_pages):
    """The core regression: opening must not request the whole document."""
    requested = []
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = (
            lambda page_num, zoom, priority=0: requested.append(page_num))
        v._request_visible_pages()

        assert requested, "no page was requested — the view would stay blank"
        assert len(requested) < len(v._page_widgets), (
            f"requested {len(requested)} of {len(v._page_widgets)} pages; "
            "visibility fell back to the whole document")
        assert len(requested) <= _MAX_QUEUED_PAGE_RENDERS
        # A page taller than the viewport means only the first page(s) show.
        assert 0 in requested
        assert 59 not in requested, "last page of a 60-page doc is not visible"
    finally:
        v._render_worker.stop()
        model.close()


def test_visible_indices_are_contiguous_from_the_top(qtbot, many_pages):
    v, model = _viewer(qtbot, many_pages)
    try:
        visible = v._visible_page_indices()
        assert visible, "nothing reported visible at the top of the document"
        assert visible[0] == 0
        assert visible == list(range(visible[0], visible[-1] + 1))
    finally:
        v._render_worker.stop()
        model.close()


def test_visible_indices_follow_the_scrollbar(qtbot, many_pages):
    """Scrolling must move the visible window, not keep reporting page 0."""
    v, model = _viewer(qtbot, many_pages)
    try:
        scrollbar = v.verticalScrollBar()
        # The scroll range depends on the laid-out container, which needs the
        # event loop; drive the model directly with an explicit range instead.
        page_h = v._page_pixel_size(0)[1]
        scrollbar.setRange(0, page_h * len(v._page_widgets))
        scrollbar.setValue(page_h * 30)

        visible = v._visible_page_indices()
        assert visible, "nothing visible after scrolling"
        assert 0 not in visible, "still reporting page 0 after scrolling away"
        assert min(visible) >= 25, f"expected to be near page 30, got {visible}"
    finally:
        v._render_worker.stop()
        model.close()


def test_zoomed_out_shows_more_pages_than_zoomed_in(qtbot, many_pages):
    """Sanity-check the geometry maths against zoom."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._zoom = 1.0
        zoomed_in = len(v._visible_page_indices())
        v._zoom = 0.1
        zoomed_out = len(v._visible_page_indices())
        assert zoomed_out > zoomed_in
        # Even zoomed far out the request cap must hold.
        assert zoomed_out <= len(v._page_widgets)
    finally:
        v._render_worker.stop()
        model.close()


def test_request_is_capped_when_geometry_is_degenerate(qtbot, many_pages):
    """If the page-size maths ever collapses (zero-height pages), the backstop
    must still stop us from queueing the entire document."""
    requested = []
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = (
            lambda page_num, zoom, priority=0: requested.append(page_num))
        # Zero-height pages make every page land at the same y — the degenerate
        # case the old geometry-based test hit on every open.
        v._page_pixel_size = lambda i: (100, 0)
        v._request_visible_pages()

        assert len(requested) <= _MAX_QUEUED_PAGE_RENDERS, (
            f"queued {len(requested)} pages with degenerate geometry")
    finally:
        v._render_worker.stop()
        model.close()


def test_page_change_restyles_only_the_changed_thumbnails(qtbot, many_pages):
    """Selecting a page must not call setStyleSheet on every thumbnail."""
    from ui.sidebar import ThumbnailPanel

    doc = fitz.open(str(many_pages))
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    try:
        panel.set_document(doc)
        panel.set_current_page(0)
        calls = []
        for t in panel._thumbnails:
            t._update_style = (lambda n=t.page_num: calls.append(n))
        panel.set_current_page(5)
        assert sorted(calls) == [0, 5], f"restyled {len(calls)} thumbnails"
    finally:
        panel._render_timer.stop()
        doc.close()
