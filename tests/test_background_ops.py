"""Long document operations run off the GUI thread and still produce results."""
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")


@pytest.fixture
def main_window(qtbot, tmp_path, monkeypatch):
    from config import config
    autosave = tmp_path / "autosave"
    autosave.mkdir()
    monkeypatch.setattr(config, "AUTOSAVE_DIR", autosave)
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")

    from ui.main_window import MainWindow
    window = MainWindow()
    window._settings.confirm_close_unsaved = False
    window._autosave_timer.stop()
    qtbot.addWidget(window)
    yield window
    window.close()


def _assert_view_matches_document(window):
    """Widgets, thumbnails and the render copy all line up with the document."""
    doc = window._document.doc
    viewer, thumbs = window._viewer, window._sidebar.thumbnail_panel._thumbnails
    assert len(viewer._page_widgets) == len(thumbs) == len(doc)
    assert [w.page_num for w in viewer._page_widgets] == list(range(len(doc)))
    assert [t.page_num for t in thumbs] == list(range(len(doc)))
    assert [t._page_label.text() for t in thumbs] == [str(i + 1) for i in range(len(doc))]
    assert viewer._render_worker.page_count() == len(doc)
    for i in range(len(doc)):
        assert viewer._render_worker.render_samples(i, 20) == doc[i].get_pixmap(dpi=20).samples
        w, h = viewer._page_pixel_size(i)
        assert abs(viewer._page_widgets[i].width() - w) <= 1
        assert abs(viewer._page_widgets[i].height() - h) <= 1


def test_page_structure_edits_update_the_view_in_place(main_window, make_pdf,
                                                       qtbot, monkeypatch):
    import ui.handlers.page_handler as ph
    monkeypatch.setattr(ph.QMessageBox, "question",
                        staticmethod(lambda *a, **k: ph.QMessageBox.StandardButton.Yes))
    pdf = make_pdf("doc.pdf", pages=4)
    main_window._open_file(str(pdf))
    win = main_window
    untouched = win._viewer._page_widgets[0]
    reloads = []
    real_load = win._load_document_to_viewer
    win._load_document_to_viewer = lambda *a, **k: (reloads.append(1), real_load(*a, **k))

    win._viewer._current_page = 1
    win._insert_blank_page()             # new page at index 2
    _assert_view_matches_document(win)
    win._delete_page(0)
    _assert_view_matches_document(win)
    win._rotate_page(1, 90)
    _assert_view_matches_document(win)
    for _ in range(3):
        win._undo()
        _assert_view_matches_document(win)
    for _ in range(3):
        win._redo()
        _assert_view_matches_document(win)

    assert reloads == [], "a page edit rebuilt the whole view"
    assert untouched not in win._viewer._page_widgets  # page 0 was deleted (redo)
    assert win._document.page_count == 4


@pytest.fixture(params=["thread", "process"])
def render_mode(request, monkeypatch):
    monkeypatch.setenv("ULTRA_PDF_RENDER_IN_PROCESS",
                       "1" if request.param == "thread" else "0")
    return request.param


def test_save_keeps_the_view_and_can_overwrite_repeatedly(render_mode, main_window,
                                                         make_pdf):
    win = main_window
    pdf = make_pdf("doc.pdf", pages=3)
    win._open_file(str(pdf))
    widgets = list(win._viewer._page_widgets)
    thumbs = list(win._sidebar.thumbnail_panel._thumbnails)
    serialized = []
    real = win._viewer._render_source
    win._viewer._render_source = lambda doc: (serialized.append(1), real(doc))[1]

    for _ in range(3):  # the render copy must let go of the file every time
        win._rotate_page(0, 90)
        win._save_document()
        assert win._is_modified is False
        assert win._viewer._page_widgets == widgets, "save rebuilt the page widgets"
        assert win._sidebar.thumbnail_panel._thumbnails == thumbs
        _assert_view_matches_document(win)

    assert serialized == [], "save re-serialized the document for the render copy"
    import fitz
    on_disk = fitz.open(str(win._current_file))
    try:
        assert on_disk[0].rotation == 270
    finally:
        on_disk.close()


def _wait_idle(qtbot, window, timeout=15000):
    qtbot.waitUntil(lambda: not window._active_workers, timeout=timeout)


@pytest.mark.parametrize("fmt, ext", [(0, "png"), (1, "jpg")])
def test_export_as_images_in_background(main_window, make_pdf, tmp_path,
                                        qtbot, monkeypatch, fmt, ext):
    import ui.handlers.file_handler as fh
    pdf = make_pdf("doc.pdf", pages=3)
    main_window._open_file(str(pdf))
    out = tmp_path / "images"
    out.mkdir()
    monkeypatch.setattr(fh.QFileDialog, "getExistingDirectory",
                        staticmethod(lambda *a, **k: str(out)))
    monkeypatch.setattr(fh.QInputDialog, "getItem",
                        staticmethod(lambda _p, _t, _l, items, *a, **k: (items[fmt], True)))

    main_window._export_as_images()
    assert main_window._active_workers, "export ran on the GUI thread"
    _wait_idle(qtbot, main_window)
    assert sorted(p.name for p in out.iterdir()) == [
        f"page_{i:04d}.{ext}" for i in (1, 2, 3)]


def test_replace_all_in_background_is_undoable(main_window, make_pdf, qtbot):
    pdf = make_pdf("doc.pdf", pages=3, text="alpha")
    main_window._open_file(str(pdf))
    main_window._replace_search_params = lambda: ("alpha", False)

    main_window._do_replace_all("omega")
    assert main_window._active_workers, "Replace All ran on the GUI thread"
    _wait_idle(qtbot, main_window)
    doc = main_window._document
    assert len(doc.search_text("omega")) == 3 and doc.search_text("alpha") == []

    main_window._undo()
    assert len(main_window._document.search_text("alpha")) == 3
