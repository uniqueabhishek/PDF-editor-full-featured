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


def test_scrolling_away_releases_page_bitmaps(qtbot, many_pages):
    """Pages far from the viewport must drop their bitmap so memory stays flat."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = lambda page_num, zoom, priority=0: None
        for i in range(10):
            v._render_page_sync(i)
        assert all(v._page_widgets[i]._pixmap is not None for i in range(10))
        size_before = v._page_widgets[0].size()

        page_h = v._page_pixel_size(0)[1]
        scrollbar = v.verticalScrollBar()
        scrollbar.setRange(0, page_h * len(v._page_widgets))
        scrollbar.setValue(page_h * 40)
        v._request_visible_pages()

        held = [i for i, w in enumerate(v._page_widgets) if w._pixmap is not None]
        assert not any(i < 30 for i in held), f"pages still holding bitmaps: {held}"
        # The released page keeps its size so the layout does not jump.
        assert v._page_widgets[0].size() == size_before
    finally:
        v._render_worker.stop()
        model.close()


def _worker_pixels(v, page_num):
    with v._render_worker._lock:
        return v._render_worker._doc[page_num].get_pixmap(dpi=40).samples


def test_single_page_edit_patches_render_copy(qtbot, many_pages):
    """An in-place edit on one page must update the worker copy without a
    full re-serialize, and the copy must then render exactly like the source."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = lambda page_num, zoom, priority=0: None
        v._render_source = lambda doc: pytest.fail("full re-serialize on a one-page edit")
        model.doc[5].add_highlight_annot(fitz.Rect(72, 90, 200, 110))
        model.doc[5].draw_rect(fitz.Rect(50, 300, 300, 500), color=(1, 0, 0), width=5)
        v.invalidate_render_copy(5)

        assert not v._resync_timer.isActive(), "fell back to a debounced full resync"
        assert _worker_pixels(v, 5) == model.doc[5].get_pixmap(dpi=40).samples
        assert len(v._render_worker._doc) == len(model.doc)

        # Undo-style refresh with a known page takes the same fast path.
        model.doc[8].set_rotation(90)
        v.refresh(8)
        assert not v._resync_timer.isActive()
        assert v._render_worker._doc[8].rotation == 90
    finally:
        v._render_worker.stop()
        model.close()


def test_patch_falls_back_when_page_count_differs(qtbot, many_pages):
    v, model = _viewer(qtbot, many_pages)
    try:
        model.doc.new_page()
        v.invalidate_render_copy(0)
        assert v._resync_timer.isActive(), "a stale copy must trigger a full resync"
    finally:
        v._render_worker.stop()
        model.close()


def test_render_source_is_used_instead_of_serializing(qtbot, many_pages, tmp_path):
    model = PDFDocument()
    model.open(many_pages)
    v = PDFViewer()
    qtbot.addWidget(v)
    try:
        v._render_source = lambda doc: pytest.fail("serialized despite a usable source")
        v.set_document(model.doc, str(many_pages), render_source=str(many_pages))
        assert len(v._render_worker._doc) == len(model.doc)
        snap = model.snapshot()
        v.set_document(model.doc, str(many_pages), render_source=snap)
        assert _worker_pixels(v, 3) == model.doc[3].get_pixmap(dpi=40).samples
    finally:
        v._render_worker.stop()
        model.close()


def test_locked_render_source_falls_back_to_serializing(qtbot, many_pages, tmp_path):
    locked = tmp_path / "locked.pdf"
    src = fitz.open(str(many_pages))
    src.save(str(locked), encryption=fitz.PDF_ENCRYPT_AES_256,
             user_pw="u", owner_pw="o")
    src.close()
    model = PDFDocument()
    model.open(locked, "u")
    v = PDFViewer()
    qtbot.addWidget(v)
    try:
        v.set_document(model.doc, str(locked), render_source=str(locked))
        doc = v._render_worker._doc
        assert doc is not None and not doc.needs_pass
        assert len(doc) == len(model.doc)
    finally:
        v._render_worker.stop()
        model.close()


def test_reload_after_edit_reuses_page_widgets(qtbot, many_pages):
    """A snapshot-style reload with the same layout keeps widgets and position;
    a changed layout rebuilds them."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = lambda page_num, zoom, priority=0: None
        widgets = list(v._page_widgets)
        v._current_page = 12

        model.doc[12].draw_rect(fitz.Rect(50, 50, 200, 200), color=(1, 0, 0))
        model.restore(model.snapshot())          # swaps the document object
        v.detach_document()
        v.set_document(model.doc, str(many_pages), reuse_layout=True)
        assert v._page_widgets == widgets, "page widgets were rebuilt"
        assert v._current_page == 12, "reload jumped away from the current page"
        assert v._doc is model.doc
        assert widgets[12]._pixmap is not None, "current page not re-rendered"

        # A page size change must not reuse the stale layout.
        model.doc[3].set_cropbox(fitz.Rect(0, 0, 300, 300))
        v.set_document(model.doc, str(many_pages), reuse_layout=True)
        assert v._page_widgets != widgets
        assert v._current_page == 0
    finally:
        v._render_worker.stop()
        model.close()


def test_thumbnails_reused_on_same_page_count(qtbot, many_pages):
    from ui.sidebar import ThumbnailPanel

    doc = fitz.open(str(many_pages))
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    try:
        panel.set_document(doc)
        thumbs = list(panel._thumbnails)
        doc2 = fitz.open(str(many_pages))
        panel.detach_document()
        panel.set_document(doc2, reuse_layout=True)
        assert panel._thumbnails == thumbs
        assert all(t._pixmap is None for t in thumbs), "stale thumbnails kept as fresh"
        doc2.new_page()
        panel.set_document(doc2, reuse_layout=True)
        assert len(panel._thumbnails) == len(doc2)
    finally:
        panel._render_timer.stop()
        doc.close()


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
