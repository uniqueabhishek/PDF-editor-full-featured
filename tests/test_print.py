"""Printing renders pages at a capped resolution and still fills the page."""
import fitz
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


def test_print_caps_render_dpi_and_prints_every_page(main_window, make_pdf,
                                                     tmp_path, monkeypatch):
    import PyQt6.QtPrintSupport as qps
    import ui.handlers.file_handler as fh

    out = tmp_path / "printed.pdf"
    real_printer = qps.QPrinter

    class FilePrinter(real_printer):
        def __init__(self, mode):
            super().__init__(mode)
            self.setOutputFormat(real_printer.OutputFormat.PdfFormat)
            self.setOutputFileName(str(out))
            self.setResolution(1200)  # far above the cap

    monkeypatch.setattr(qps, "QPrinter", FilePrinter)
    monkeypatch.setattr(qps.QPrintDialog, "exec",
                        lambda self: qps.QPrintDialog.DialogCode.Accepted)

    rendered = []
    real_get_pixmap = fitz.Page.get_pixmap

    def spy(page, *a, **k):
        pix = real_get_pixmap(page, *a, **k)
        rendered.append(pix.width / page.rect.width * 72)
        return pix
    monkeypatch.setattr(fitz.Page, "get_pixmap", spy)

    pdf = make_pdf("doc.pdf", pages=3)
    main_window._open_file(str(pdf))
    rendered.clear()
    main_window._print_document()

    assert rendered and max(rendered) <= fh._PRINT_MAX_DPI + 1
    printed = fitz.open(str(out))
    try:
        assert len(printed) == 3
        # The page image was drawn (the printed page is not blank).
        pix = printed[0].get_pixmap(dpi=30)
        assert min(pix.samples) < 128
    finally:
        printed.close()
