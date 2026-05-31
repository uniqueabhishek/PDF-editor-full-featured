"""GUI / handler smoke tests (require pytest-qt, run headless via offscreen).

These cover the wiring the headless core tests can't: the background worker,
MainWindow construction, the open/save flow and undo/redo view-sync.
"""
import pytest

# Skip the whole module cleanly if PyQt6 / pytest-qt aren't available.
pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")


# ==================== FunctionWorker ====================

def test_function_worker_success(qtbot):
    from ui.workers import FunctionWorker
    worker = FunctionWorker(lambda progress, cancelled: 42)
    with qtbot.waitSignal(worker.succeeded, timeout=3000) as blocker:
        worker.start()
    assert blocker.args == [42]


def test_function_worker_failure(qtbot):
    from ui.workers import FunctionWorker

    def boom(progress, cancelled):
        raise RuntimeError("nope")

    worker = FunctionWorker(boom)
    with qtbot.waitSignal(worker.failed, timeout=3000) as blocker:
        worker.start()
    assert "nope" in blocker.args[0]


def test_function_worker_reports_progress(qtbot):
    from ui.workers import FunctionWorker
    seen = []

    def work(progress, cancelled):
        for i in range(3):
            progress(i, 3)
        return "ok"

    worker = FunctionWorker(work)
    worker.progress.connect(lambda done, total: seen.append((done, total)))
    with qtbot.waitSignal(worker.succeeded, timeout=3000):
        worker.start()
    assert (0, 3) in seen and (2, 3) in seen


# ==================== MainWindow ====================

@pytest.fixture
def main_window(qtbot, tmp_path, monkeypatch):
    """A MainWindow with config paths isolated to tmp (no real home, no prompts)."""
    from config import config
    autosave = tmp_path / "autosave"
    autosave.mkdir()
    monkeypatch.setattr(config, "AUTOSAVE_DIR", autosave)
    monkeypatch.setattr(config, "SETTINGS_PATH", tmp_path / "settings.json")

    from ui.main_window import MainWindow
    window = MainWindow()
    # Never raise the unsaved-changes prompt at teardown (a modal dialog would
    # hang headlessly), and keep auto-save quiet during the test.
    window._settings.confirm_close_unsaved = False
    window._autosave_timer.stop()
    qtbot.addWidget(window)
    yield window
    # close() runs the real teardown: cancels workers, stops the render thread,
    # closes the document.
    window.close()


def test_mainwindow_opens_pdf(main_window, make_pdf):
    pdf = make_pdf("doc.pdf", pages=3)
    main_window._open_file(str(pdf))
    assert main_window._document.is_open
    assert main_window._document.page_count == 3
    assert main_window._viewer.get_page_count() == 3


def test_mainwindow_search_populates_results(main_window, make_pdf):
    pdf = make_pdf("doc.pdf", pages=2, text="Findme")
    main_window._open_file(str(pdf))
    main_window._do_search("Findme", False)
    total = sum(len(r["rects"]) for r in main_window._search_results)
    assert total >= 2


def test_mainwindow_insert_page_then_undo(main_window, make_pdf):
    pdf = make_pdf("doc.pdf", pages=3)
    main_window._open_file(str(pdf))
    main_window._insert_blank_page()
    assert main_window._document.page_count == 4
    main_window._undo()
    assert main_window._document.page_count == 3


def test_mainwindow_save_reattaches_document(main_window, make_pdf):
    pdf = make_pdf("doc.pdf", pages=2)
    main_window._open_file(str(pdf))
    main_window._rotate_page(0, 90)        # an undoable in-place edit
    assert main_window._is_modified
    main_window._save_document()           # _current_file set -> no dialog
    # After the save→detach→reattach dance the document is still usable.
    assert main_window._document.is_open
    assert main_window._document.page_count == 2
    assert main_window._is_modified is False
