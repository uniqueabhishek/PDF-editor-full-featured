"""Tests for the undo/redo history manager and commands (headless)."""
import pytest

from core.pdf_document import PDFDocument
from utils.history import (
    HistoryManager, PageAddCommand, PageDeleteCommand, PageRotateCommand,
    AnnotationAddCommand,
)


@pytest.fixture
def doc(sample_pdf):
    d = PDFDocument()
    d.open(sample_pdf)
    yield d
    d.close()


def test_execute_pushes_undo(doc):
    hm = HistoryManager()
    assert hm.can_undo() is False
    assert hm.execute(PageAddCommand(doc, 1)) is True
    assert hm.can_undo() is True
    assert doc.page_count == 4


def test_undo_then_redo_page_add(doc):
    hm = HistoryManager()
    hm.execute(PageAddCommand(doc, 1))
    assert doc.page_count == 4
    assert hm.undo() is True
    assert doc.page_count == 3
    assert hm.can_redo() is True
    assert hm.redo() is True
    assert doc.page_count == 4


def test_undo_page_delete_restores_count(doc):
    hm = HistoryManager()
    hm.execute(PageDeleteCommand(doc, 0))
    assert doc.page_count == 2
    assert hm.undo() is True
    assert doc.page_count == 3


def test_rotate_command_undo(doc):
    hm = HistoryManager()
    hm.execute(PageRotateCommand(doc, 0, 90))
    assert doc.get_page_info(0).rotation == 90
    hm.undo()
    assert doc.get_page_info(0).rotation == 0


def test_new_action_clears_redo_stack(doc):
    hm = HistoryManager()
    hm.execute(PageAddCommand(doc, 1))
    hm.undo()
    assert hm.can_redo() is True
    hm.execute(PageAddCommand(doc, 1))
    assert hm.can_redo() is False


def test_annotation_add_and_undo(doc):
    hm = HistoryManager()
    page = doc.get_page(0)
    before = len(list(page.annots()))
    cmd = AnnotationAddCommand(
        doc, 0, "rectangle", (72, 92, 200, 150),
        {"color": (1, 0, 0), "width": 2, "opacity": 1.0})
    assert hm.execute(cmd) is True
    assert len(list(doc.get_page(0).annots())) == before + 1
    assert hm.undo() is True
    assert len(list(doc.get_page(0).annots())) == before


def test_undo_redo_empty_stacks():
    hm = HistoryManager()
    assert hm.undo() is False
    assert hm.redo() is False


def test_history_max_size_evicts_oldest(doc):
    hm = HistoryManager(max_size=3)
    for _ in range(5):
        hm.execute(PageRotateCommand(doc, 0, 90))
    assert hm.get_undo_count() == 3


def test_descriptions_present(doc):
    hm = HistoryManager()
    hm.execute(PageAddCommand(doc, 1))
    assert "page" in hm.get_undo_description().lower()


def test_clear_history(doc):
    hm = HistoryManager()
    hm.execute(PageAddCommand(doc, 1))
    hm.clear()
    assert hm.can_undo() is False
    assert hm.can_redo() is False
