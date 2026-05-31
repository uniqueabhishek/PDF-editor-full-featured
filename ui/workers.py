"""Background worker for long-running, cancellable operations.

Operations such as OCR and Word export used to run on the GUI thread, pumping
``QApplication.processEvents()`` in a loop, which freezes the window. They now
run on a :class:`FunctionWorker` (a ``QThread``).

Thread-safety note: PyMuPDF documents are **not** thread-safe, so the work
function must operate on its *own* ``fitz.Document`` opened from serialized
bytes — never the editable document held by the main thread. Callers serialize
the document on the GUI thread, hand the bytes to the worker, and apply any
result back on the GUI thread (e.g. via an undoable snapshot).
"""
import logging
from typing import Any, Callable

from PyQt6.QtCore import QThread, pyqtSignal

logger = logging.getLogger(__name__)

# A work function receives (progress_cb, is_cancelled) and returns a result.
#   progress_cb(done: int, total: int) -> None   reports progress (thread-safe).
#   is_cancelled() -> bool                        True once the user cancels.
WorkFn = Callable[[Callable[[int, int], None], Callable[[], bool]], Any]


class FunctionWorker(QThread):
    """Runs a work function off the GUI thread with progress/cancel support."""

    progress = pyqtSignal(int, int)   # done, total
    succeeded = pyqtSignal(object)    # result returned by the work function
    failed = pyqtSignal(str)          # error message

    def __init__(self, fn: WorkFn, parent=None):
        super().__init__(parent)
        self._fn = fn
        self._cancelled = False

    def cancel(self) -> None:
        """Request cancellation; the work function should check is_cancelled()."""
        self._cancelled = True

    def is_cancelled(self) -> bool:
        return self._cancelled

    def run(self) -> None:
        try:
            result = self._fn(self._emit_progress, self.is_cancelled)
        except Exception as exc:  # noqa: BLE001 - reported to the UI
            logger.exception("Background task failed")
            self.failed.emit(str(exc))
            return
        if not self._cancelled:
            self.succeeded.emit(result)

    def _emit_progress(self, done: int, total: int) -> None:
        # Emitting a signal from the worker thread is delivered on the GUI
        # thread via a queued connection — safe to update widgets from slots.
        self.progress.emit(done, total)
