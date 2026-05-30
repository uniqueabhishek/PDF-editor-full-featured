"""Tests for the undo/redo history manager and commands (headless)."""
import pytest

from core.pdf_document import PDFDocument
from utils.history import (
    HistoryManager, PageAddCommand, PageDeleteCommand, PageRotateCommand,
    AnnotationAddCommand, DocumentSnapshotCommand,
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


def test_undo_page_delete_restores_content(doc):
    """Undoing a delete must bring back the real page, not a blank one."""
    hm = HistoryManager()
    assert "page 2" in doc.get_page_text(1)
    hm.execute(PageDeleteCommand(doc, 1))
    assert doc.page_count == 2
    assert "page 2" not in doc.get_page_text(1)

    assert hm.undo() is True
    assert doc.page_count == 3
    assert "page 2" in doc.get_page_text(1)


def test_undo_page_delete_then_redo(doc):
    hm = HistoryManager()
    hm.execute(PageDeleteCommand(doc, 1))
    hm.undo()
    assert hm.redo() is True
    assert doc.page_count == 2
    assert "page 2" not in doc.get_page_text(1)


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


# ==================== Snapshot-based undo (destructive ops) ====================

def test_document_snapshot_command_undo_redo(doc):
    """Destructive ops captured by snapshot must be reversible."""
    hm = HistoryManager()
    assert "page 1" in doc.get_page_text(0)

    def erase_page_0():
        doc.redact_area(0, doc.doc[0].rect)  # wipe the whole first page
        return "erased"

    cmd = DocumentSnapshotCommand(doc, erase_page_0, description="Erase page 1")
    assert hm.execute(cmd) is True
    assert cmd.result == "erased"
    assert doc.get_page_text(0).strip() == ""

    assert hm.undo() is True
    assert "page 1" in doc.get_page_text(0)  # real content is back

    assert hm.redo() is True
    assert doc.get_page_text(0).strip() == ""


def test_document_snapshot_command_rolls_back_on_failure(doc):
    hm = HistoryManager()
    before = doc.get_page_text(0)

    def boom():
        doc.redact_area(0, doc.doc[0].rect)
        raise RuntimeError("operation blew up midway")

    assert hm.execute(DocumentSnapshotCommand(doc, boom, description="boom")) is False
    assert hm.can_undo() is False              # failed command not pushed
    assert doc.get_page_text(0) == before      # rolled back to pre-op state


def test_snapshot_command_sets_view_flags():
    cmd = DocumentSnapshotCommand(None, lambda: None)
    assert cmd.swaps_document is True
    assert cmd.requires_reload is True


def test_page_structure_commands_require_reload(doc):
    assert PageDeleteCommand(doc, 0).requires_reload is True
    assert PageAddCommand(doc, 0).requires_reload is True
    # In-place edits don't need a full viewer reload.
    assert PageRotateCommand(doc, 0, 90).requires_reload is False


def test_peek_returns_next_commands(doc):
    hm = HistoryManager()
    cmd = PageAddCommand(doc, 1)
    hm.execute(cmd)
    assert hm.peek_undo() is cmd
    assert hm.peek_redo() is None
    hm.undo()
    assert hm.peek_undo() is None
    assert hm.peek_redo() is cmd
