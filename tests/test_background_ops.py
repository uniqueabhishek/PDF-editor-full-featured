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
