"""Inline text editor overlay used by the Edit Text tool.

A frameless QTextEdit placed directly over a paragraph on a page so the user can
retype it in place. Ctrl+Enter (or clicking away) commits; Esc cancels; a plain
Enter inserts a newline. The widget is intentionally "dumb": the PDFViewer owns
positioning/styling and reacts to the ``committed``/``cancelled`` signals.
"""
from PyQt6.QtWidgets import QTextEdit
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QKeyEvent, QFocusEvent


class InlineTextEditor(QTextEdit):
    """In-place paragraph editor; emits its final text on commit."""

    committed = pyqtSignal(str)   # final plain text
    cancelled = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._finished = False
        self.setAcceptRichText(False)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)

    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        if key == Qt.Key.Key_Escape:
            self.cancel()
            event.accept()
            return
        if (key in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier):
            self.commit()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusOutEvent(self, event: QFocusEvent):
        # Clicking away commits the edit (unless it was already finished).
        super().focusOutEvent(event)
        self.commit()

    def commit(self):
        """Finish editing and emit the current text (once)."""
        if self._finished:
            return
        self._finished = True
        self.committed.emit(self.toPlainText())

    def cancel(self):
        """Abandon editing without applying changes (once)."""
        if self._finished:
            return
        self._finished = True
        self.cancelled.emit()
