"""The render copy lives in a separate process so rendering never holds the
GUI thread's GIL, and the viewer survives that process dying."""
import threading
import time

import fitz
import pytest

from core.render_backend import InProcessRenderer, ProcessRenderer


@pytest.fixture
def scan_pdf(tmp_path):
    """Pages heavy enough to render that a GIL hold would be measurable."""
    path = tmp_path / "heavy.pdf"
    doc = fitz.open()
    for i in range(6):
        page = doc.new_page()
        for k in range(400):
            page.draw_circle((50 + (k * 37) % 500, 50 + (k * 53) % 740), 20 + k % 30,
                             color=(k % 7 / 7, 0.3, 0.6), fill=(0.2, k % 5 / 5, 0.4))
        page.insert_text((72, 72), f"page {i}", fontsize=20)
    doc.save(str(path))
    doc.close()
    return path


@pytest.fixture
def process_renderer():
    r = ProcessRenderer()
    yield r
    r.shutdown()


def test_process_renderer_matches_in_process(scan_pdf, process_renderer):
    local = InProcessRenderer()
    src = fitz.open(str(scan_pdf))
    try:
        assert process_renderer.open(str(scan_pdf)) and local.open(str(scan_pdf))
        assert process_renderer.page_count() == local.page_count() == 6
        assert process_renderer.render(2, 0.5, 90) == local.render(2, 0.5, 90)

        # Patch one page from an edited live document.
        src[3].draw_rect(fitz.Rect(10, 10, 300, 300), color=(1, 0, 0), width=8)
        assert process_renderer.patch(src, [3]) and local.patch(src, [3])
        expect = src[3].get_pixmap(matrix=fitz.Matrix(0.5, 0.5), alpha=False).samples
        assert process_renderer.render(3, 0.5, 0)[3] == expect
        # A page-count mismatch is refused, not half-applied.
        src.new_page()
        assert process_renderer.patch(src, [0]) is False
    finally:
        local.shutdown()
        src.close()


@pytest.mark.parametrize("make", [InProcessRenderer, ProcessRenderer])
def test_page_insert_and_delete_mirror_the_live_document(scan_pdf, make):
    r = make()
    src = fitz.open(str(scan_pdf))
    try:
        assert r.open(str(scan_pdf))
        src.new_page(pno=2).insert_text((72, 72), "inserted", fontsize=30)
        assert r.insert_pages(src, 2, 1)
        src.delete_pages([0, 4])
        assert r.delete_pages([0, 4], 7)
        assert r.page_count() == len(src) == 5
        for i in range(5):
            expect = src[i].get_pixmap(matrix=fitz.Matrix(0.2, 0.2), alpha=False).samples
            assert r.render(i, 0.2, 0)[3] == expect
        assert r.delete_pages([0], 99) is False  # stale count: refused
    finally:
        r.shutdown()
        src.close()


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_clipped_render_matches_the_same_region_of_a_full_render(scan_pdf, rotation):
    from core.render_backend import render_page
    doc = fitz.open(str(scan_pdf))
    try:
        w, h, stride, full, ox, oy = render_page(doc, 1, 0.8, rotation)
        assert (ox, oy) == (0, 0)
        clip = (w // 5, h // 3, w // 5 + 120, h // 3 + 90)
        cw, ch, cstride, part, px, py = render_page(doc, 1, 0.8, rotation, clip)
        assert (px, py) == clip[:2] and (cw, ch) == (120, 90)
        # Same region, same content; anti-aliasing may differ by a shade.
        worst = 0
        for row in range(ch):
            start = (py + row) * stride + px * 3
            a = part[row * cstride: row * cstride + cw * 3]
            b = full[start: start + cw * 3]
            worst = max(worst, max(abs(x - y) for x, y in zip(a, b, strict=True)))
        assert worst <= 8, f"clipped render differs by up to {worst}"
    finally:
        doc.close()


def test_rendering_in_the_process_does_not_block_this_thread(scan_pdf, process_renderer):
    """While the process renders, other Python threads keep running."""
    assert process_renderer.open(str(scan_pdf))
    stop = threading.Event()

    def render_loop():
        while not stop.is_set():
            for i in range(6):
                process_renderer.render(i, 2.0, 0)

    t = threading.Thread(target=render_loop, daemon=True)
    t.start()
    ticks, worst, last = 0, 0.0, time.perf_counter()
    end = last + 1.5
    while time.perf_counter() < end:
        time.sleep(0.005)
        now = time.perf_counter()
        worst = max(worst, now - last)
        last = now
        ticks += 1
    stop.set()
    t.join(5)
    # An in-thread render loop leaves ~30 ticks in this window (GIL held).
    assert ticks > 150, f"only {ticks} ticks; worst gap {worst * 1000:.0f} ms"


def test_password_locked_source_is_refused(tmp_path, scan_pdf, process_renderer):
    locked = tmp_path / "locked.pdf"
    d = fitz.open(str(scan_pdf))
    d.save(str(locked), encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="u", owner_pw="o")
    d.close()
    assert process_renderer.open(str(locked)) is False
    assert process_renderer.page_count() == -1


def test_viewer_falls_back_when_render_process_dies(qtbot, scan_pdf, monkeypatch):
    pytest.importorskip("PyQt6")
    pytest.importorskip("pytestqt")
    monkeypatch.setenv("ULTRA_PDF_RENDER_IN_PROCESS", "0")
    from core.pdf_document import PDFDocument
    from ui.pdf_viewer import PDFViewer

    model = PDFDocument()
    model.open(scan_pdf)
    v = PDFViewer()
    qtbot.addWidget(v)
    try:
        v.resize(800, 600)
        v.set_document(model.doc, str(scan_pdf), render_source=str(scan_pdf))
        worker = v._render_worker
        assert worker.uses_render_process
        assert worker.page_count() == 6

        worker._backend._proc.kill()          # simulate a crash in MuPDF
        worker._backend._proc.join(5)
        with qtbot.waitSignal(worker.copy_lost, timeout=5000):
            worker.page_count()               # the next call notices
        assert not worker.uses_render_process
        qtbot.waitUntil(lambda: worker.page_count() == 6, timeout=5000)
    finally:
        v._render_worker.stop()
        model.close()
