"""Find-as-you-type must not search the whole document on every keystroke."""
import fitz
import pytest

pytest.importorskip("PyQt6")
pytest.importorskip("pytestqt")

from core.pdf_document import PDFDocument  # noqa: E402
from ui.dialogs.find_dialog import (  # noqa: E402
    _LIVE_SEARCH_DELAY_MS, FindDialog, FindReplaceDialog)


@pytest.fixture(params=[FindDialog, FindReplaceDialog])
def dialog(request, qtbot):
    dlg = request.param()
    qtbot.addWidget(dlg)
    searches, nexts = [], []
    dlg.find_requested.connect(lambda t, c: searches.append((t, c)))
    dlg.find_next.connect(lambda: nexts.append(1))
    return dlg, searches, nexts


def test_typing_searches_once_after_a_pause(qtbot, dialog):
    dlg, searches, _ = dialog
    for ch in "lorem":
        dlg._search_input.insert(ch)
    assert searches == [], "searched while still typing"
    qtbot.wait(_LIVE_SEARCH_DELAY_MS + 200)
    assert searches == [("lorem", False)]


def test_single_character_waits_for_enter(qtbot, dialog):
    dlg, searches, nexts = dialog
    dlg._search_input.insert("e")
    qtbot.wait(_LIVE_SEARCH_DELAY_MS + 200)
    assert searches == []
    dlg._find_next()
    assert searches == [("e", False)] and nexts == []
    dlg._find_next()  # same term again: step, don't re-search
    assert searches == [("e", False)] and nexts == [1]


def test_toggling_match_case_searches_again(qtbot, dialog):
    dlg, searches, _ = dialog
    dlg._search_input.insert("Lorem")
    dlg._find_next()
    dlg._case_sensitive.setChecked(True)
    qtbot.wait(_LIVE_SEARCH_DELAY_MS + 200)
    assert searches == [("Lorem", False), ("Lorem", True)]


def test_search_cache_sees_edits(tmp_path):
    """The per-page text pre-filter is dropped on edit, so new text is found."""
    p = tmp_path / "doc.pdf"
    d = fitz.open()
    for i in range(3):
        d.new_page().insert_text((72, 100), f"alpha page {i}")
    d.save(str(p))
    d.close()

    doc = PDFDocument()
    doc.open(p)
    try:
        assert doc.search_text("omega") == []
        doc.replace_text_all("alpha", "omega")
        assert {r["page"] for r in doc.search_text("omega")} == {0, 1, 2}
        # Direct edits made by a snapshot operation are seen too.
        doc.doc[1].insert_text((72, 200), "zeta")
        doc.snapshot()
        assert [r["page"] for r in doc.search_text("zeta")] == [1]
    finally:
        doc.close()
