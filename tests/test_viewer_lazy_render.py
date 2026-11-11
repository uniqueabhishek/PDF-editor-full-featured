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
            lambda page_num, zoom, priority=0, clip=None: requested.append(page_num))
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
        v.set_zoom(100)
        zoomed_in = len(v._visible_page_indices())
        v.set_zoom(10)
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
            lambda page_num, zoom, priority=0, clip=None: requested.append(page_num))
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
        v._render_worker.request_page = lambda page_num, zoom, priority=0, clip=None: None
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


def test_zoom_burst_renders_only_the_final_zoom(qtbot, many_pages):
    """Five quick Ctrl+wheel steps must not render five zoom levels."""
    from ui.pdf_viewer import _ZOOM_RENDER_DELAY_MS

    requested = []
    v, model = _viewer(qtbot, many_pages)
    try:
        qtbot.wait(100)  # let the open-time render pass run
        v._render_worker.request_page = (
            lambda page_num, zoom, priority=0, clip=None: requested.append(round(zoom, 4)))
        for _ in range(5):
            v.zoom_in()
            qtbot.wait(40)          # notches closer together than the delay
        assert requested == [], f"rendered mid-burst at zooms {set(requested)}"
        qtbot.wait(_ZOOM_RENDER_DELAY_MS + 150)
        assert requested and set(requested) == {round(v._zoom, 4)}
    finally:
        v._render_worker.stop()
        model.close()


def test_very_high_zoom_renders_only_the_visible_part(qtbot, tmp_path):
    """At 800% a page is ~139 M pixels; only what is on screen gets rendered."""
    from ui.pdf_viewer import _MAX_RENDER_PIXELS, _ZOOM_RENDER_DELAY_MS
    path = tmp_path / "three.pdf"
    d = fitz.open()
    for i in range(3):
        d.new_page(width=595, height=842).insert_text((72, 100), f"page {i + 1}")
    d.save(str(path))
    d.close()
    v, model = _viewer(qtbot, path)
    try:
        v.show()
        v.set_zoom(800)
        qtbot.wait(_ZOOM_RENDER_DELAY_MS + 100)
        widget = v._page_widgets[0]
        qtbot.waitUntil(lambda: widget._partial is not None, timeout=10000)
        pix = widget._pixmap
        assert pix.width() * pix.height() <= _MAX_RENDER_PIXELS
        full_w, full_h = v._page_pixel_size(0)
        assert full_w * full_h > 10 * _MAX_RENDER_PIXELS
        clip, seen = v._render_clip_for(0)
        assert widget.partial_covers(seen)

        # Scroll far down the same page: a new part is rendered for it.
        bar = v.verticalScrollBar()
        qtbot.waitUntil(lambda: bar.maximum() > full_h, timeout=5000)
        bar.setValue(full_h // 2)
        qtbot.waitUntil(lambda: widget.partial_covers(v._render_clip_for(0)[1]),
                        timeout=10000)
        assert widget._partial[1][1] > 0, "still showing the top of the page"
        assert not v._page_cache, "partial renders must not be cached"
    finally:
        v._render_worker.stop()
        model.close()


def test_pages_never_overlap_even_past_qt_layout_limits(qtbot, many_pages):
    """60 pages at 800% are ~842,000 px tall; a QLayout stops at 524,287 px
    and used to stack the pages on top of each other."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v.set_zoom(800)
        geos = [w.geometry() for w in v._page_widgets]
        assert geos[-1].bottom() > 524_287
        for a, b in zip(geos, geos[1:]):
            assert b.top() == a.bottom() + 1 + 10, "pages overlap or drift apart"
        # Visible pages at the very end come from the stored row positions.
        bar = v.verticalScrollBar()
        bar.setRange(0, geos[-1].bottom())
        bar.setValue(geos[-1].top() + 10)
        assert v._visible_page_indices() == [59]
    finally:
        v._render_worker.stop()
        model.close()


def test_two_page_and_single_page_modes_place_pages(qtbot, many_pages):
    from ui.pdf_viewer import ViewMode
    v, model = _viewer(qtbot, many_pages)
    try:
        v.set_view_mode(ViewMode.TWO_PAGE)
        g = [w.geometry() for w in v._page_widgets]
        assert g[0].top() == g[1].top() and g[1].left() > g[0].right()
        assert g[2].top() > g[0].bottom()
        assert v._visible_page_indices()[:2] == [0, 1]

        v.set_view_mode(ViewMode.SINGLE_PAGE)
        v.go_to_page(7)
        shown = [i for i, w in enumerate(v._page_widgets) if not w.isHidden()]
        assert shown == [7] and v._visible_page_indices() == [7]
    finally:
        v._render_worker.stop()
        model.close()


def test_zoom_keeps_old_render_visible_until_the_new_one_lands(qtbot, many_pages):
    from ui.pdf_viewer import _ZOOM_RENDER_DELAY_MS
    v, model = _viewer(qtbot, many_pages)
    try:
        v.show()
        qtbot.waitUntil(lambda: v._page_widgets[0]._pixmap is not None, timeout=5000)
        old = v._page_widgets[0]._pixmap
        v.zoom_in()
        w = v._page_widgets[0]
        assert w._pixmap is None and w._preview is old, "page blanked on zoom"
        assert (w.width(), w.height()) == v._page_pixel_size(0)
        assert w._zoom == v._zoom, "clicks would map at the old zoom"
        qtbot.wait(_ZOOM_RENDER_DELAY_MS)
        qtbot.waitUntil(lambda: w._pixmap is not None, timeout=5000)
        assert w._preview is None
        # Pages far off screen hold neither a render nor a preview.
        assert all(p._preview is None for p in v._page_widgets[10:])
    finally:
        v._render_worker.stop()
        model.close()


def test_find_next_updates_only_the_two_affected_pages(qtbot, many_pages):
    v, model = _viewer(qtbot, many_pages)
    try:
        results = [{"page": p, "rects": [(72, 90 + k, 120, 100 + k) for k in range(50)]}
                   for p in range(60)]
        v.set_search_results(results)
        calls = []
        for w in v._page_widgets:
            real = w.set_search_rects
            w.set_search_rects = (lambda rects, cur=None, _w=w, _r=real:
                                  (calls.append(_w.page_num), _r(rects, cur)))
        v.scroll_to_search_result(3, results[3]["rects"][7])
        v.scroll_to_search_result(9, results[9]["rects"][0])
        assert calls == [3, 3, 9] or sorted(calls) == [3, 3, 9]
        assert v._page_widgets[9]._current_search_rect is not None
        assert v._page_widgets[3]._current_search_rect is None
        assert len(v._page_widgets[3]._search_rects) == 50
    finally:
        v._render_worker.stop()
        model.close()


def test_thumbnails_render_a_couple_per_pass(qtbot, many_pages):
    from ui.sidebar import _MAX_THUMBNAILS_PER_PASS, ThumbnailPanel
    doc = fitz.open(str(many_pages))
    panel = ThumbnailPanel()
    qtbot.addWidget(panel)
    panel.resize(200, 900)
    panel.show()
    try:
        per_pass, count = [], [0]
        real_render = panel._render_thumbnail
        real_pass = panel._render_visible_thumbnails

        def counting_render(n):
            count[0] += 1
            return real_render(n)

        def counting_pass():
            count[0] = 0
            real_pass()
            per_pass.append(count[0])

        panel._render_thumbnail = counting_render
        panel._render_timer.timeout.disconnect()
        panel._render_timer.timeout.connect(counting_pass)
        panel.set_document(doc)
        qtbot.waitUntil(lambda: sum(t._pixmap is not None for t in panel._thumbnails) >= 6,
                        timeout=5000)
        assert max(per_pass) == _MAX_THUMBNAILS_PER_PASS <= 2
    finally:
        panel._render_timer.stop()
        doc.close()


def _worker_pixels(v, page_num):
    return v._render_worker.render_samples(page_num, 40)


def test_single_page_edit_patches_render_copy(qtbot, many_pages):
    """An in-place edit on one page must update the worker copy without a
    full re-serialize, and the copy must then render exactly like the source."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = lambda page_num, zoom, priority=0, clip=None: None
        v._render_source = lambda doc: pytest.fail("full re-serialize on a one-page edit")
        model.doc[5].add_highlight_annot(fitz.Rect(72, 90, 200, 110))
        model.doc[5].draw_rect(fitz.Rect(50, 300, 300, 500), color=(1, 0, 0), width=5)
        v.invalidate_render_copy(5)

        assert not v._resync_timer.isActive(), "fell back to a debounced full resync"
        assert _worker_pixels(v, 5) == model.doc[5].get_pixmap(dpi=40).samples
        assert v._render_worker.page_count() == len(model.doc)

        # Undo-style refresh with a known page takes the same fast path.
        model.doc[8].set_rotation(90)
        v.refresh(8)
        assert not v._resync_timer.isActive()
        assert _worker_pixels(v, 8) == model.doc[8].get_pixmap(dpi=40).samples
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
        assert v._render_worker.page_count() == len(model.doc)
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
        assert v._render_worker.page_count() == len(model.doc)
        assert _worker_pixels(v, 0) == model.doc[0].get_pixmap(dpi=40).samples
    finally:
        v._render_worker.stop()
        model.close()


def test_reload_after_edit_reuses_page_widgets(qtbot, many_pages):
    """A snapshot-style reload with the same layout keeps widgets and position;
    a changed layout rebuilds them."""
    v, model = _viewer(qtbot, many_pages)
    try:
        v._render_worker.request_page = lambda page_num, zoom, priority=0, clip=None: None
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


def test_replacing_render_copy_releases_mupdf_cache(qtbot, many_pages, monkeypatch):
    calls = []
    monkeypatch.setattr(fitz.TOOLS, "store_shrink", lambda pct: calls.append(pct))
    v, model = _viewer(qtbot, many_pages)
    try:
        calls.clear()
        v.set_document(model.doc, str(many_pages), reuse_layout=True)
        assert calls == [100], "discarded render copy left its cache entries behind"
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
