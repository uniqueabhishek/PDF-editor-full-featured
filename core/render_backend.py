"""
Ultra PDF Editor - page render backends for the viewer's render worker.

PyMuPDF holds Python's GIL for the whole of every call, so a render running
on a background *thread* still freezes the GUI thread: while one rendered, the
window got ~30 event-loop turns in 2 s instead of ~350, with gaps over 100 ms.
:class:`ProcessRenderer` therefore keeps the render copy of the document in a
separate process; the worker thread only waits on a pipe, which releases the
GIL. :class:`InProcessRenderer` is the original in-thread renderer, used as a
fallback if the process cannot be started or dies.

Both share one interface (all calls are serialized by the caller's lock):

    open(source)               -> bool   bytes or file path; False if unusable
    close()
    patch(src_doc, pages)      -> bool   copy those pages from the live doc
    delete_pages(pages, n)     -> bool   n = page count before; False if off
    insert_pages(src, i, k)    -> bool   copy src pages i..i+k-1 in at i
    render(page, scale, rot, clip=None) -> see render_page(), or None
    page_count()               -> int    -1 when no document
    shutdown()

This module imports only fitz so the render process starts quickly.
"""

import logging
import multiprocessing
from typing import List, Optional, Tuple, Union

import fitz

logger = logging.getLogger(__name__)

Source = Union[bytes, str]
Clip = Tuple[int, int, int, int]
# (width, height, stride, samples, x offset, y offset) - see render_page()
Rendered = Tuple[int, int, int, bytes, int, int]


def _release_cache() -> None:
    """Empty MuPDF's decoded-image cache; closing a document does not."""
    try:
        fitz.TOOLS.store_shrink(100)
    except Exception:
        logger.debug("Could not shrink the MuPDF cache", exc_info=True)


def _open_source(source: Source) -> Optional[fitz.Document]:
    doc = fitz.open(source) if isinstance(source, str) else fitz.open(stream=source, filetype="pdf")
    if doc.needs_pass:
        doc.close()
        return None
    return doc


def _apply_patch(doc: fitz.Document, pages_pdf: fitz.Document, pages: List[int]) -> None:
    """Replace ``pages`` of ``doc`` with the pages of ``pages_pdf``, in order."""
    for idx, p in enumerate(pages):
        # A fresh graft map per insert, so objects copied by an earlier patch
        # are never reused in their stale form.
        if hasattr(doc, "Graftmaps"):
            doc.Graftmaps = {}
        doc.delete_page(p)
        doc.insert_pdf(pages_pdf, from_page=idx, to_page=idx, start_at=p)


def render_page(
    doc: fitz.Document, page_num: int, scale: float, rotation: int, clip: Optional[Clip] = None
) -> Optional[Rendered]:
    """Render a page, or only the part ``clip`` covers.

    ``clip`` is ``(x0, y0, x1, y1)`` in the coordinates of the full rendered
    page (pixels, origin at its top-left). The result carries the offset of
    the returned pixels within that full page, ``(0, 0)`` without a clip.
    """
    if not 0 <= page_num < len(doc):
        return None
    page = doc[page_num]
    matrix = fitz.Matrix(scale, scale).prerotate(rotation)
    if clip is None:
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        return pix.width, pix.height, pix.stride, pix.samples, 0, 0
    # Map the clip from full-page pixels back to page space; MuPDF places the
    # full page at the transformed page rect's top-left, which may be negative
    # once rotated.
    origin = (page.rect * matrix).irect
    device = fitz.Rect(clip) + (origin.x0, origin.y0, origin.x0, origin.y0)
    pix = page.get_pixmap(matrix=matrix, clip=device * ~matrix, alpha=False)
    return (pix.width, pix.height, pix.stride, pix.samples, pix.x - origin.x0, pix.y - origin.y0)


class InProcessRenderer:
    """Renders in the calling thread from a private document copy."""

    def __init__(self):
        self._doc: Optional[fitz.Document] = None

    def open(self, source: Source) -> bool:
        self.close()
        try:
            self._doc = _open_source(source)
        except Exception:
            logger.exception("Render copy could not be opened")
            self._doc = None
        return self._doc is not None

    def close(self) -> None:
        if self._doc is not None:
            try:
                self._doc.close()
            except Exception:
                logger.debug("Failed to close render copy", exc_info=True)
            self._doc = None
            _release_cache()

    def patch(self, src: fitz.Document, pages: List[int]) -> bool:
        doc = self._doc
        if doc is None or doc.is_closed or len(doc) != len(src):
            return False
        pages = sorted(set(pages))
        try:
            for p in pages:
                if hasattr(doc, "Graftmaps"):
                    doc.Graftmaps = {}
                doc.delete_page(p)
                doc.insert_pdf(src, from_page=p, to_page=p, start_at=p)
            return len(doc) == len(src)
        except Exception:
            logger.exception("Could not patch render copy for pages %s", pages)
            return False

    def delete_pages(self, pages: List[int], expected_before: int) -> bool:
        doc = self._doc
        if doc is None or len(doc) != expected_before:
            return False
        doc.delete_pages(sorted(set(pages)))
        return True

    def insert_pages(self, src: fitz.Document, index: int, count: int) -> bool:
        doc = self._doc
        if doc is None or len(doc) + count != len(src):
            return False
        if hasattr(doc, "Graftmaps"):
            doc.Graftmaps = {}
        doc.insert_pdf(src, from_page=index, to_page=index + count - 1, start_at=index)
        return len(doc) == len(src)

    def render(
        self, page_num: int, scale: float, rotation: int, clip: Optional[Clip] = None
    ) -> Optional[Rendered]:
        if self._doc is None:
            return None
        return render_page(self._doc, page_num, scale, rotation, clip)

    def page_count(self) -> int:
        return len(self._doc) if self._doc is not None else -1

    def shutdown(self) -> None:
        self.close()


def serve(conn) -> None:
    """Render-process main loop: one request in, one reply out."""
    doc: Optional[fitz.Document] = None

    def drop():
        nonlocal doc
        if doc is not None:
            doc.close()
            doc = None
            _release_cache()

    while True:
        try:
            msg = conn.recv()
        except (EOFError, OSError):
            break
        op = msg[0]
        try:
            if op == "quit":
                drop()
                conn.send(("ok", None))
                break
            if op == "open":
                drop()
                doc = _open_source(msg[1])
                conn.send(("ok", doc is not None))
            elif op == "close":
                drop()
                conn.send(("ok", None))
            elif op == "patch":
                expected, pages, data = msg[1], msg[2], msg[3]
                if doc is None or len(doc) != expected:
                    conn.send(("ok", False))
                    continue
                pages_pdf = fitz.open(stream=data, filetype="pdf")
                try:
                    _apply_patch(doc, pages_pdf, pages)
                finally:
                    pages_pdf.close()
                conn.send(("ok", len(doc) == expected))
            elif op == "delete":
                pages, expected = msg[1], msg[2]
                if doc is None or len(doc) != expected:
                    conn.send(("ok", False))
                    continue
                doc.delete_pages(sorted(set(pages)))
                conn.send(("ok", True))
            elif op == "insert":
                index, expected_after, data = msg[1], msg[2], msg[3]
                pages_pdf = fitz.open(stream=data, filetype="pdf")
                try:
                    if doc is None or len(doc) + len(pages_pdf) != expected_after:
                        conn.send(("ok", False))
                        continue
                    if hasattr(doc, "Graftmaps"):
                        doc.Graftmaps = {}
                    doc.insert_pdf(pages_pdf, start_at=index)
                finally:
                    pages_pdf.close()
                conn.send(("ok", len(doc) == expected_after))
            elif op == "render":
                result = None if doc is None else render_page(doc, msg[1], msg[2], msg[3], msg[4])
                conn.send(("ok", result))
            elif op == "count":
                conn.send(("ok", len(doc) if doc is not None else -1))
            else:
                conn.send(("err", f"unknown op {op!r}"))
        except Exception as e:  # noqa: BLE001 - report every failure to the caller
            try:
                conn.send(("err", repr(e)))
            except (OSError, ValueError):
                break


class RenderProcessDied(RuntimeError):
    """The render process exited; its document copy is gone."""


class ProcessRenderer:
    """Keeps the render copy in a child process (see module docstring)."""

    def __init__(self):
        ctx = multiprocessing.get_context("spawn")
        self._conn, child = ctx.Pipe()
        self._proc = ctx.Process(target=serve, args=(child,), daemon=True, name="ultra-pdf-render")
        self._proc.start()
        child.close()

    def _call(self, *msg):
        try:
            self._conn.send(msg)
            status, value = self._conn.recv()
        except (EOFError, OSError, BrokenPipeError) as e:
            raise RenderProcessDied(str(e)) from e
        if status != "ok":
            raise RuntimeError(value)
        return value

    def open(self, source: Source) -> bool:
        try:
            return bool(self._call("open", source))
        except RenderProcessDied:
            raise
        except Exception:
            logger.exception("Render process could not open its copy")
            return False

    def close(self) -> None:
        self._call("close")

    def patch(self, src: fitz.Document, pages: List[int]) -> bool:
        pages = sorted(set(pages))
        pages_pdf = fitz.open()
        try:
            for p in pages:
                pages_pdf.insert_pdf(src, from_page=p, to_page=p)
            data = pages_pdf.tobytes(garbage=0, deflate=False)
        except Exception:
            logger.exception("Could not extract pages %s for the render copy", pages)
            return False
        finally:
            pages_pdf.close()
        try:
            return bool(self._call("patch", len(src), pages, data))
        except RenderProcessDied:
            raise
        except Exception:
            logger.exception("Render process could not patch pages %s", pages)
            return False

    def delete_pages(self, pages: List[int], expected_before: int) -> bool:
        return bool(self._call("delete", list(pages), expected_before))

    def insert_pages(self, src: fitz.Document, index: int, count: int) -> bool:
        pages_pdf = fitz.open()
        try:
            pages_pdf.insert_pdf(src, from_page=index, to_page=index + count - 1)
            data = pages_pdf.tobytes(garbage=0, deflate=False)
        finally:
            pages_pdf.close()
        return bool(self._call("insert", index, len(src), data))

    def render(
        self, page_num: int, scale: float, rotation: int, clip: Optional[Clip] = None
    ) -> Optional[Rendered]:
        return self._call("render", page_num, scale, rotation, clip)

    def page_count(self) -> int:
        return int(self._call("count"))

    def shutdown(self) -> None:
        try:
            self._call("quit")
        except Exception:
            pass
        self._proc.join(2)
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(1)
        self._conn.close()
