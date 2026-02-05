"""
Ultra PDF Editor - Undo/Redo History Manager
Implements command pattern for unlimited undo/redo
"""
from typing import List, Optional, Any, Dict, Tuple
from dataclasses import dataclass
from abc import ABC, abstractmethod
from enum import Enum


class CommandType(Enum):
    """Types of commands that can be undone/redone"""
    PAGE_ADD = "page_add"
    PAGE_DELETE = "page_delete"
    PAGE_ROTATE = "page_rotate"
    PAGE_MOVE = "page_move"
    ANNOTATION_ADD = "annotation_add"
    ANNOTATION_DELETE = "annotation_delete"
    ANNOTATION_MODIFY = "annotation_modify"
    TEXT_ADD = "text_add"
    TEXT_EDIT = "text_edit"
    TEXT_DELETE = "text_delete"
    IMAGE_ADD = "image_add"
    IMAGE_DELETE = "image_delete"
    IMAGE_MODIFY = "image_modify"
    FORM_FIELD_ADD = "form_field_add"
    FORM_FIELD_DELETE = "form_field_delete"
    FORM_FIELD_MODIFY = "form_field_modify"
    METADATA_CHANGE = "metadata_change"
    BOOKMARK_ADD = "bookmark_add"
    BOOKMARK_DELETE = "bookmark_delete"
    MERGE = "merge"
    SPLIT = "split"


class Command(ABC):
    """Abstract base class for undoable commands"""

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


@dataclass
class PageAddCommand(Command):
    """Command for adding a page"""
    document: Any
    page_index: int
    page_data: Optional[bytes] = None
    width: float = 595
    height: float = 842

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


@dataclass
class PageDeleteCommand(Command):
    """Command for deleting a page"""
    document: Any
    page_index: int
    page_data: Optional[bytes] = None

    def __init__(self, document, page_index: int):
        super().__init__(CommandType.PAGE_DELETE,
                         f"Delete page {page_index + 1}")
        self.document = document
        self.page_index = page_index
        self.page_data = None

    def execute(self) -> bool:
        try:
            # Store page data for undo
            # Note: In real implementation, we'd save the page content
            self.document.delete_page(self.page_index)
            return True
        except Exception:
            return False

    def undo(self) -> bool:
        try:
            # Restore the page
            # Note: In real implementation, we'd restore from saved data
            self.document.add_blank_page(index=self.page_index)
            return True
        except Exception:
            return False


@dataclass
class PageRotateCommand(Command):
    """Command for rotating a page"""
    document: Any
    page_index: int
    rotation: int
    original_rotation: int = 0

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


@dataclass
class PageMoveCommand(Command):
    """Command for moving a page"""
    document: Any
    from_index: int
    to_index: int

    def __init__(self, document, from_index: int, to_index: int):
        super().__init__(CommandType.PAGE_MOVE,
                         f"Move page {from_index + 1} to {to_index + 1}")
        self.document = document
        self.from_index = from_index
        self.to_index = to_index

    def execute(self) -> bool:
        try:
            self.document.move_page(self.from_index, self.to_index)
            return True
        except Exception:
            return False

    def undo(self) -> bool:
        try:
            self.document.move_page(self.to_index, self.from_index)
            return True
        except Exception:
            return False


@dataclass
class AnnotationAddCommand(Command):
    """Command for adding an annotation"""
    document: Any
    page_index: int
    annot_type: str
    rect: Any  # Tuple or Rect
    annot_data: Optional[Dict[str, Any]] = None
    _annot_xref: int = 0

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
            # Mark document as modified
            self.document._is_modified = True
            return annot
        except Exception as e:
            print(f"Stamp error: {e}")
            return None

    def execute(self) -> bool:
        try:
            annot = None
            rect_tuple = self._rect_to_tuple(self.rect)
            if self.annot_type == "highlight":
                annot = self.document.add_highlight(self.page_index, rect_tuple)
            elif self.annot_type == "underline":
                annot = self.document.add_underline(self.page_index, rect_tuple)
            elif self.annot_type == "strikethrough":
                annot = self.document.add_strikethrough(
                    self.page_index, rect_tuple)
            elif self.annot_type == "rectangle":
                annot = self.document.add_rect_annotation(
                    self.page_index, rect_tuple)
            elif self.annot_type == "circle":
                annot = self.document.add_circle_annotation(
                    self.page_index, rect_tuple)
            elif self.annot_type == "line":
                # Use rect corners as start/end points for line
                start = (rect_tuple[0], rect_tuple[1])
                end = (rect_tuple[2], rect_tuple[3])
                arrow = self.annot_data.get("arrow", False)
                annot = self.document.add_line_annotation(
                    self.page_index, start, end)
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
                            self.page_index, strokes)
            elif self.annot_type == "stamp":
                # Create a stamp annotation using the rect
                annot = self._create_stamp_annotation(rect_tuple)

            # Text annotations
            elif self.annot_type == "text_box":
                text = self.annot_data.get("text", "Text")
                annot = self.document.add_freetext(
                    self.page_index, rect_tuple, text)
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


class TransactionManager:
    """Manages compound commands as transactions"""

    def __init__(self, history: HistoryManager):
        self._history = history
        self._transaction_commands: List[Command] = []
        self._in_transaction = False
        self._transaction_name = ""

    def begin_transaction(self, name: str = ""):
        """Begin a new transaction"""
        if self._in_transaction:
            raise RuntimeError("Transaction already in progress")

        self._in_transaction = True
        self._transaction_name = name
        self._transaction_commands.clear()

    def add_command(self, command: Command):
        """Add a command to the current transaction"""
        if not self._in_transaction:
            raise RuntimeError("No transaction in progress")

        command.execute()
        self._transaction_commands.append(command)

    def commit_transaction(self) -> bool:
        """Commit the current transaction"""
        if not self._in_transaction:
            return False

        if self._transaction_commands:
            # Create a compound command
            compound = CompoundCommand(
                self._transaction_commands.copy(),
                self._transaction_name or "Multiple actions"
            )
            self._history._undo_stack.append(compound)
            self._history._redo_stack.clear()

        self._in_transaction = False
        self._transaction_commands.clear()
        return True

    def rollback_transaction(self) -> bool:
        """Rollback the current transaction"""
        if not self._in_transaction:
            return False

        # Undo all commands in reverse order
        for command in reversed(self._transaction_commands):
            command.undo()

        self._in_transaction = False
        self._transaction_commands.clear()
        return True

    @property
    def in_transaction(self) -> bool:
        return self._in_transaction


class CompoundCommand(Command):
    """A command that contains multiple sub-commands"""

    def __init__(self, commands: List[Command], description: str = ""):
        super().__init__(CommandType.METADATA_CHANGE, description)
        self._commands = commands

    def execute(self) -> bool:
        for command in self._commands:
            if not command.execute():
                # Rollback previously executed commands
                idx = self._commands.index(command)
                for i in range(idx - 1, -1, -1):
                    self._commands[i].undo()
                return False
        return True

    def undo(self) -> bool:
        # Undo in reverse order
        for command in reversed(self._commands):
            if not command.undo():
                return False
        return True

    def redo(self) -> bool:
        return self.execute()
