"""
Ultra PDF Editor - Undo/Redo History Manager
Implements command pattern for unlimited undo/redo
"""
import logging
from typing import Callable, List, Optional, Any, Dict, Tuple
from abc import ABC, abstractmethod
from enum import Enum

import fitz

logger = logging.getLogger(__name__)


class CommandType(Enum):
    """Types of commands that can be undone/redone"""
    PAGE_ADD = "page_add"
    PAGE_DELETE = "page_delete"
    PAGE_ROTATE = "page_rotate"
    ANNOTATION_ADD = "annotation_add"
    METADATA_CHANGE = "metadata_change"


class Command(ABC):
    """Abstract base class for undoable commands"""

    # Undo/redo replaces the underlying fitz.Document object (snapshot restore),
    # so the UI must detach the viewer/sidebar before and re-attach afterwards.
    swaps_document: bool = False
    # Undo/redo changes page structure (count/order) or swaps the document, so
    # the viewer needs a full reload rather than a light in-place refresh.
    requires_reload: bool = False

    def __init__(self, command_type: CommandType, description: str = ""):
        self.command_type = command_type
        self.description = description

    @abstractmethod
    def execute(self) -> bool:
        """Execute the command"""
        pass

    @abstractmethod
    def undo(self) -> bool:
        """Undo the command"""
        pass

    def redo(self) -> bool:
        """Redo the command (default: re-execute)"""
        return self.execute()


class PageAddCommand(Command):
    """Command for adding a page"""
    requires_reload = True  # page count changes — rebuild the viewer's pages

    def __init__(self, document, page_index: int, width: float = 595, height: float = 842):
        super().__init__(CommandType.PAGE_ADD, f"Add page at {page_index + 1}")
        self.document = document
        self.page_index = page_index
        self.width = width
        self.height = height
        self.page_data = None

    def execute(self) -> bool:
        try:
            self.document.add_blank_page(
                self.width, self.height, self.page_index)
            return True
        except Exception:
            return False

    def undo(self) -> bool:
        try:
            self.document.delete_page(self.page_index)
            return True
        except Exception:
            return False


class PageDeleteCommand(Command):
    """Command for deleting a page"""
    requires_reload = True  # page count changes — rebuild the viewer's pages

    def __init__(self, document, page_index: int):
        super().__init__(CommandType.PAGE_DELETE,
                         f"Delete page {page_index + 1}")
        self.document = document
        self.page_index = page_index
        # The deleted page's content, captured as a single-page PDF so undo can
        # restore the real page rather than fabricating a blank one.
        self._page_pdf: Optional[bytes] = None

    def execute(self) -> bool:
        try:
            doc = self.document.doc
            if doc is None:
                return False
            # Snapshot the page about to be deleted so undo restores its content.
            holder = fitz.open()
            holder.insert_pdf(doc, from_page=self.page_index, to_page=self.page_index)
            self._page_pdf = holder.tobytes()
            holder.close()
            self.document.delete_page(self.page_index)
            return True
        except Exception:
            logger.exception("PageDeleteCommand.execute failed")
            return False

    def undo(self) -> bool:
        try:
            if self._page_pdf is None:
                return False
            doc = self.document.doc
            if doc is None:
                return False
            holder = fitz.open(stream=self._page_pdf, filetype="pdf")
            doc.insert_pdf(holder, start_at=self.page_index)
            holder.close()
            self.document.mark_modified()
            return True
        except Exception:
            logger.exception("PageDeleteCommand.undo failed")
            return False


class PageRotateCommand(Command):
    """Command for rotating a page"""

    def __init__(self, document, page_index: int, rotation: int):
        super().__init__(CommandType.PAGE_ROTATE,
                         f"Rotate page {page_index + 1}")
        self.document = document
        self.page_index = page_index
        self.rotation = rotation
        self.original_rotation = 0

    def execute(self) -> bool:
        try:
            page_info = self.document.get_page_info(self.page_index)
            self.original_rotation = page_info.rotation
            self.document.rotate_page(self.page_index, self.rotation)
            return True
        except Exception:
            return False

    def undo(self) -> bool:
        try:
            # Rotate back to original
            self.document.rotate_page(self.page_index, -self.rotation)
            return True
        except Exception:
            return False


class AnnotationAddCommand(Command):
    """Command for adding an annotation"""

    def __init__(self, document, page_index: int, annot_type: str, rect: Any, annot_data: Optional[Dict[str, Any]] = None):
        super().__init__(CommandType.ANNOTATION_ADD, f"Add {annot_type}")
        self.document = document
        self.page_index = page_index
        self.annot_type = annot_type
        self.rect = rect
        self.annot_data = annot_data or {}
        self._annot_xref = 0

    def _rect_to_tuple(self, rect: Any) -> Tuple[float, float, float, float]:
        """Convert QRectF or similar to tuple (x0, y0, x1, y1)"""
        if rect is None:
            return (0, 0, 0, 0)
        # Check if it's a QRectF (has x(), y(), width(), height() methods)
        if hasattr(rect, 'x') and callable(rect.x):
            return (rect.x(), rect.y(), rect.x() + rect.width(), rect.y() + rect.height())
        # Already a tuple or list
        if isinstance(rect, (tuple, list)) and len(rect) >= 4:
            return (rect[0], rect[1], rect[2], rect[3])
        return (0, 0, 0, 0)

    def _create_stamp_annotation(self, rect: Tuple[float, float, float, float]) -> Any:
        """Create a stamp annotation"""
        try:
            import fitz
            page = self.document.get_page(self.page_index)
            # PyMuPDF stamp constants use fitz.STAMP_* constants
            stamp_id = self.annot_data.get("stamp_id", 0)  # Default to "Approved"
            # Map our IDs to fitz stamp constants
            stamp_map = {
                0: fitz.STAMP_Approved,
                1: fitz.STAMP_AsIs,
                2: fitz.STAMP_Confidential,
                3: fitz.STAMP_Departmental,
                4: fitz.STAMP_Draft,
                5: fitz.STAMP_Experimental,
                6: fitz.STAMP_Expired,
                7: fitz.STAMP_Final,
                8: fitz.STAMP_ForComment,
                9: fitz.STAMP_ForPublicRelease,
                10: fitz.STAMP_NotApproved,
                11: fitz.STAMP_NotForPublicRelease,
                12: fitz.STAMP_Sold,
                13: fitz.STAMP_TopSecret,
            }
            fitz_stamp = stamp_map.get(stamp_id, fitz.STAMP_Approved)
            annot = page.add_stamp_annot(fitz.Rect(rect), stamp=fitz_stamp)
            annot.update()
            self.document.mark_modified()
            return annot
        except Exception:
            logger.exception("Stamp annotation failed")
            return None

    def execute(self) -> bool:
        try:
            annot = None
            rect_tuple = self._rect_to_tuple(self.rect)

            # Style threaded from the toolbar via the viewer. Fall back to each
            # document method's own default when a value wasn't supplied.
            color = self.annot_data.get("color")
            opacity = float(self.annot_data.get("opacity", 1.0))
            width = self.annot_data.get("width", 1)

            if self.annot_type == "highlight":
                annot = self.document.add_highlight(
                    self.page_index, rect_tuple,
                    color=color or (1, 1, 0), opacity=opacity)
            elif self.annot_type == "underline":
                annot = self.document.add_underline(
                    self.page_index, rect_tuple,
                    color=color or (0, 0, 1), opacity=opacity)
            elif self.annot_type == "strikethrough":
                annot = self.document.add_strikethrough(
                    self.page_index, rect_tuple,
                    color=color or (1, 0, 0), opacity=opacity)
            elif self.annot_type == "rectangle":
                annot = self.document.add_rect_annotation(
                    self.page_index, rect_tuple,
                    stroke_color=color or (1, 0, 0), width=width, opacity=opacity)
            elif self.annot_type == "circle":
                annot = self.document.add_circle_annotation(
                    self.page_index, rect_tuple,
                    stroke_color=color or (1, 0, 0), width=width, opacity=opacity)
            elif self.annot_type == "line":
                # Use rect corners as start/end points for line
                start = (rect_tuple[0], rect_tuple[1])
                end = (rect_tuple[2], rect_tuple[3])
                arrow = self.annot_data.get("arrow", False)
                annot = self.document.add_line_annotation(
                    self.page_index, start, end,
                    color=color or (1, 0, 0), width=width, opacity=opacity)
                if arrow and annot:
                    # Add arrow head to the end
                    annot.set_line_ends(0, 5)  # 0=none, 5=closed arrow
                    annot.update()
            elif self.annot_type == "ink":
                # Expecting 'points' in annot_data as list of (x, y) tuples
                if self.annot_data and "points" in self.annot_data:
                    points = self.annot_data["points"]
                    # Points should be a flat list like [(x1,y1), (x2,y2), ...]
                    # Convert to list of tuples if needed and wrap as single stroke
                    if points and len(points) > 0:
                        # Ensure each point is a tuple of floats
                        stroke = [(float(p[0]), float(p[1])) for p in points]
                        strokes = [stroke]
                        annot = self.document.add_ink_annotation(
                            self.page_index, strokes,
                            color=color or (0, 0, 0), width=width, opacity=opacity)
            elif self.annot_type == "stamp":
                # Create a stamp annotation using the rect
                annot = self._create_stamp_annotation(rect_tuple)

            # Text annotations
            elif self.annot_type == "text_box":
                text = self.annot_data.get("text", "Text")
                font_size = self.annot_data.get("font_size", 12)
                # Keep text color at the document default (black) for legibility;
                # the toolbar Color control is markup/shape-oriented and defaults
                # to yellow, which would be unreadable as body text.
                annot = self.document.add_freetext(
                    self.page_index, rect_tuple, text, font_size=font_size)
            elif self.annot_type == "sticky_note":
                # Rect to point
                point = (rect_tuple[0], rect_tuple[1])
                text = self.annot_data.get("text", "")
                annot = self.document.add_text_annotation(
                    self.page_index, point, text)

            if annot:
                self._annot_xref = annot.xref
                return True
            return False
        except Exception:
            return False

    def undo(self) -> bool:
        try:
            if self._annot_xref:
                page = self.document.get_page(self.page_index)
                annots = page.annots()
                if annots:
                    for annot in list(annots):
                        if annot.xref == self._annot_xref:
                            page.delete_annot(annot)
                            return True
            return False
        except Exception:
            return False


class DocumentSnapshotCommand(Command):
    """Undoable wrapper for in-place mutations that have no natural inverse.

    Captures a full-document snapshot before and after running ``operation``, so
    destructive edits (redaction, crop, watermark, header/footer, OCR, ...) can
    be reversed by restoring the document to its earlier bytes. Restoring swaps
    the underlying document object, hence ``swaps_document``/``requires_reload``.
    """

    swaps_document = True
    requires_reload = True

    def __init__(self, document: Any, operation: Callable[[], Any],
                 command_type: CommandType = CommandType.METADATA_CHANGE,
                 description: str = ""):
        super().__init__(command_type, description)
        self.document = document
        self._operation = operation
        self._before: Optional[bytes] = None
        self._after: Optional[bytes] = None
        self.result: Any = None

    def execute(self) -> bool:
        try:
            self._before = self.document.snapshot()
        except Exception:
            logger.exception("Could not snapshot before '%s'", self.description)
            return False
        try:
            self.result = self._operation()
        except Exception:
            logger.exception("Operation '%s' failed; rolling back", self.description)
            try:
                self.document.restore(self._before)
            except Exception:
                logger.exception("Rollback after '%s' failed", self.description)
            return False
        try:
            self._after = self.document.snapshot()
        except Exception:
            # The mutation succeeded but redo won't be available; not fatal.
            logger.exception("Could not snapshot after '%s'", self.description)
        return True

    def undo(self) -> bool:
        if self._before is None:
            return False
        try:
            self.document.restore(self._before)
            return True
        except Exception:
            logger.exception("Undo of '%s' failed", self.description)
            return False

    def redo(self) -> bool:
        if self._after is None:
            return self.execute()
        try:
            self.document.restore(self._after)
            return True
        except Exception:
            logger.exception("Redo of '%s' failed", self.description)
            return False


class HistoryManager:
    """Manages undo/redo history"""

    def __init__(self, max_size: int = 100):
        self._undo_stack: List[Command] = []
        self._redo_stack: List[Command] = []
        self._max_size = max_size
        self._is_executing = False

    def execute(self, command: Command) -> bool:
        """Execute a command and add it to history"""
        if self._is_executing:
            return False

        self._is_executing = True
        try:
            if command.execute():
                self._undo_stack.append(command)
                self._redo_stack.clear()  # Clear redo stack on new action

                # Limit history size
                while len(self._undo_stack) > self._max_size:
                    self._undo_stack.pop(0)

                return True
            return False
        finally:
            self._is_executing = False

    def undo(self) -> bool:
        """Undo the last command"""
        if not self.can_undo():
            return False

        self._is_executing = True
        try:
            command = self._undo_stack.pop()
            if command.undo():
                self._redo_stack.append(command)
                return True
            else:
                # If undo fails, put the command back
                self._undo_stack.append(command)
                return False
        finally:
            self._is_executing = False

    def redo(self) -> bool:
        """Redo the last undone command"""
        if not self.can_redo():
            return False

        self._is_executing = True
        try:
            command = self._redo_stack.pop()
            if command.redo():
                self._undo_stack.append(command)
                return True
            else:
                # If redo fails, put the command back
                self._redo_stack.append(command)
                return False
        finally:
            self._is_executing = False

    def can_undo(self) -> bool:
        """Check if undo is available"""
        return len(self._undo_stack) > 0

    def can_redo(self) -> bool:
        """Check if redo is available"""
        return len(self._redo_stack) > 0

    def peek_undo(self) -> Optional[Command]:
        """The command that the next undo() will reverse, or None."""
        return self._undo_stack[-1] if self._undo_stack else None

    def peek_redo(self) -> Optional[Command]:
        """The command that the next redo() will re-apply, or None."""
        return self._redo_stack[-1] if self._redo_stack else None

    def get_undo_description(self) -> str:
        """Get description of the next undo action"""
        if self.can_undo():
            return self._undo_stack[-1].description
        return ""

    def get_redo_description(self) -> str:
        """Get description of the next redo action"""
        if self.can_redo():
            return self._redo_stack[-1].description
        return ""

    def get_undo_count(self) -> int:
        """Get number of available undo actions"""
        return len(self._undo_stack)

    def get_redo_count(self) -> int:
        """Get number of available redo actions"""
        return len(self._redo_stack)

    def clear(self):
        """Clear all history"""
        self._undo_stack.clear()
        self._redo_stack.clear()

    def get_history(self) -> List[str]:
        """Get list of all actions in history"""
        return [cmd.description for cmd in self._undo_stack]
