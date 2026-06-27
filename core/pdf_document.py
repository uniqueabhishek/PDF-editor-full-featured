"""
Ultra PDF Editor - PDF Document Model
Handles PDF loading, manipulation, and saving using PyMuPDF (fitz)
"""
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union, Sequence
from dataclasses import dataclass
from enum import Enum
import logging
import os
import re
from collections import defaultdict

logger = logging.getLogger(__name__)


# PyMuPDF text-span "flags" bitfield (used by the inline text editor to detect
# bold/italic/serif/monospace so replacement text matches the original style).
_SPAN_FLAG_ITALIC = 1 << 1
_SPAN_FLAG_SERIF = 1 << 2
_SPAN_FLAG_MONO = 1 << 3
_SPAN_FLAG_BOLD = 1 << 4
# Re-typeset text is shrunk no smaller than this before it is allowed to clip.
_MIN_EDIT_FONTSIZE = 5.0


class PageRotation(Enum):
    NONE = 0
    CW_90 = 90
    CW_180 = 180
    CW_270 = 270


@dataclass
class PageInfo:
    """Information about a single PDF page"""
    index: int
    width: float
    height: float
    rotation: int
    has_text: bool
    has_images: bool
    has_annotations: bool
    label: str = ""


@dataclass
class DocumentMetadata:
    """PDF document metadata"""
    title: str = ""
    author: str = ""
    subject: str = ""
    keywords: str = ""
    creator: str = ""
    producer: str = ""
    creation_date: str = ""
    modification_date: str = ""
    encryption: str = ""
    page_count: int = 0
    file_size: int = 0
    pdf_version: str = ""


class PDFDocument:
    """Main PDF document class for handling PDF operations"""

    def __init__(self):
        self._doc: Optional[fitz.Document] = None
        self._filepath: Optional[Path] = None
        self._is_modified: bool = False
        self._password: Optional[str] = None
        # Encryption settings queued by encrypt() and applied on the next save.
        self._pending_encryption: Optional[Dict[str, Any]] = None

    @property
    def is_open(self) -> bool:
        """Check if a document is currently open"""
        return self._doc is not None

    @property
    def doc(self) -> Optional[fitz.Document]:
        """The underlying PyMuPDF document, or None when nothing is open.

        Public, read-only access for the UI/forms layers that must hand the
        document to PyMuPDF-based widgets (viewer, sidebar) or do low-level page
        work. Prefer the higher-level methods on this class where one exists;
        this exists so callers don't have to reach into the private ``_doc``.
        """
        return self._doc

    @property
    def filepath(self) -> Optional[Path]:
        """Get the current file path"""
        return self._filepath

    @property
    def is_modified(self) -> bool:
        """Check if document has unsaved changes"""
        return self._is_modified

    def mark_modified(self, modified: bool = True) -> None:
        """Mark the document as having unsaved changes (or clear the flag)."""
        self._is_modified = modified

    def set_filepath(self, filepath: Optional[Union[str, Path]]) -> None:
        """Retarget the document's path without saving.

        Used by crash recovery: the content is loaded from a recovery copy, but
        a subsequent Save should write back to the original file.
        """
        self._filepath = Path(filepath) if filepath else None

    @property
    def page_count(self) -> int:
        """Get total number of pages"""
        return len(self._doc) if self._doc else 0

    @property
    def is_encrypted(self) -> bool:
        """Check if document is encrypted"""
        return self._doc.is_encrypted if self._doc else False

    @property
    def needs_password(self) -> bool:
        """Check if document needs password to open"""
        return self._doc.needs_pass if self._doc else False

    @property
    def is_protected(self) -> bool:
        """True if the document is password-protected, encrypted, or has
        encryption queued for the next save.

        Used to avoid writing an *unencrypted* recovery/auto-save copy of a
        protected document to disk, which would leak its plaintext. Errs toward
        True (``needs_pass`` stays True after authentication, ``is_encrypted``
        covers owner-password-only files, and ``_pending_encryption`` covers a
        just-requested encrypt that hasn't been saved yet).
        """
        if self._doc is None:
            return False
        return bool(self._doc.needs_pass or self._doc.is_encrypted
                    or self._pending_encryption)

    def open(self, filepath: Union[str, Path], password: Optional[str] = None) -> bool:
        """
        Open a PDF file

        Args:
            filepath: Path to the PDF file
            password: Optional password for encrypted PDFs

        Returns:
            True if successful, False otherwise
        """
        try:
            self.close()
            filepath = Path(filepath)

            if not filepath.exists():
                raise FileNotFoundError(f"File not found: {filepath}")

            self._doc = fitz.open(str(filepath))

            if self._doc.needs_pass:
                if password:
                    if not self._doc.authenticate(password):
                        self._doc.close()
                        self._doc = None
                        raise ValueError("Invalid password")
                    self._password = password
                else:
                    # Return False to indicate password is needed
                    return False

            self._filepath = filepath
            self._is_modified = False
            return True

        except Exception:
            self._doc = None
            self._filepath = None
            raise

    def create_new(self) -> bool:
        """Create a new empty PDF document"""
        self.close()
        # Create a new empty PDF document
        self._doc = fitz.open()
        self._filepath = None
        self._is_modified = True
        return True

    def close(self):
        """Close the current document"""
        if self._doc:
            self._doc.close()
        self._doc = None
        self._filepath = None
        self._is_modified = False
        self._password = None
        self._pending_encryption = None

    def save(self, filepath: Optional[Union[str, Path]] = None,
             encryption: Optional[Dict[str, Any]] = None,
             garbage: int = 4,
             deflate: bool = True,
             deflate_images: bool = True,
             deflate_fonts: bool = True,
             full_rewrite: bool = False) -> bool:
        """
        Save the PDF document

        Args:
            filepath: Optional new filepath (Save As)
            encryption: Optional encryption settings
            garbage: Garbage collection level (0-4)
            deflate: Compress streams
            deflate_images: Compress images
            deflate_fonts: Compress fonts
            full_rewrite: Force a full rewrite even when saving in place (an
                incremental save can't garbage-collect, so compression needs this)

        Returns:
            True if successful
        """
        if self._doc is None:
            raise ValueError("No document is open")

        save_path = Path(filepath) if filepath else self._filepath
        if not save_path:
            raise ValueError("No filepath specified")

        # An explicit ``encryption`` argument wins; otherwise apply any settings
        # queued by encrypt(). When encryption is being set or changed we must do
        # a full rewrite — PyMuPDF cannot change encryption on an incremental save
        # (an incremental save can only KEEP the existing encryption state).
        enc = encryption if encryption is not None else self._pending_encryption

        save_options: Dict[str, Any] = {
            "garbage": garbage,
            "deflate": deflate,
            "deflate_images": deflate_images,
            "deflate_fonts": deflate_fonts,
        }
        if enc:
            save_options["encryption"] = enc.get("method", fitz.PDF_ENCRYPT_AES_256)
            if enc.get("user_password") is not None:
                save_options["user_pw"] = enc["user_password"]
            if enc.get("owner_password") is not None:
                save_options["owner_pw"] = enc["owner_password"]
            if enc.get("permissions") is not None:
                save_options["permissions"] = enc["permissions"]

        if save_path == self._filepath:
            if enc or full_rewrite:
                # Encryption change or an explicit full rewrite (e.g. compress):
                # the incremental path can only KEEP state / can't garbage-collect,
                # so go straight to a full rewrite.
                save_path = self._save_full_via_temp(save_path, save_options)
            else:
                try:
                    # Incremental saves must keep the existing encryption state;
                    # PDF_ENCRYPT_KEEP is 0 (PDF_ENCRYPT_NONE is 1 and would raise
                    # "can't change encryption on an incremental save").
                    self._doc.save(str(save_path), incremental=True,
                                   encryption=fitz.PDF_ENCRYPT_KEEP)
                except Exception:
                    # Incremental save not possible; do a full save via temp file.
                    logger.debug(
                        "Incremental save failed for %s; falling back to full save",
                        save_path, exc_info=True)
                    save_path = self._save_full_via_temp(save_path, save_options)
        else:
            self._doc.save(str(save_path), **save_options)

        self._filepath = save_path
        self._is_modified = False
        self._pending_encryption = None
        return True

    def _save_full_via_temp(self, save_path: Path,
                            save_options: Dict[str, Any]) -> Path:
        """Full-rewrite save over the file the document already has open.

        PyMuPDF cannot full-save onto the file it is currently reading (and
        cannot change encryption with an incremental save), so write to a temp
        file in the same directory, close the document to release the OS lock,
        replace the original, then reopen it.

        Returns the path actually written — normally ``save_path``, but a sibling
        ``*.edited.pdf`` if the original stayed locked by another process.
        """
        import tempfile
        import gc
        import time

        tmp_fd, tmp_path = tempfile.mkstemp(suffix=".pdf", dir=str(save_path.parent))
        os.close(tmp_fd)
        try:
            self._doc.save(tmp_path, **save_options)
            # Close the doc so Windows releases the file lock, then replace.
            self._doc.close()
            self._doc = None
            gc.collect()

            # Retry the replace — the target may be briefly locked by an AV
            # scanner or an external viewer (Adobe/Edge).
            last_err = None
            for _attempt in range(8):
                try:
                    os.replace(tmp_path, str(save_path))
                    last_err = None
                    break
                except PermissionError as e:
                    last_err = e
                    time.sleep(0.25)

            if last_err is not None:
                # Target stayed locked — save alongside with an ".edited" suffix.
                final_path = save_path.with_name(save_path.stem + ".edited.pdf")
                os.replace(tmp_path, str(final_path))
            else:
                final_path = save_path

            # Reopen the saved file, re-authenticating if we just encrypted it.
            self._doc = fitz.open(str(final_path))
            if self._doc.needs_pass and self._password:
                self._doc.authenticate(self._password)
            return final_path

        except Exception:
            # Clean up the temp file if it's still around.
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            # If we closed the doc but never replaced, reopen the original so the
            # application still has a live document to work with.
            if self._doc is None and save_path.exists():
                try:
                    self._doc = fitz.open(str(save_path))
                    if self._doc.needs_pass and self._password:
                        self._doc.authenticate(self._password)
                except Exception:
                    logger.warning(
                        "Could not reopen original %s after a failed save",
                        save_path, exc_info=True)
            raise

    def save_copy(self, filepath: Union[str, Path]) -> bool:
        """Save a copy without changing the current document path"""
        if self._doc is None:
            raise ValueError("No document is open")

        self._doc.save(str(filepath), garbage=4, deflate=True)
        return True

    def recovery_bytes(self) -> bytes:
        """Serialize the document for a crash-recovery copy, optimized for speed.

        Unlike :meth:`snapshot`, this skips compression and garbage collection
        (``garbage=0, deflate=False``): a recovery copy is transient and written
        on a timer, so we trade file size for a fast serialize that doesn't stall
        the UI. Existing encryption is kept so the copy reopens the same way;
        callers must still avoid writing an unencrypted recovery of a protected
        document (see ``MainWindow._autosave``).
        """
        if self._doc is None:
            raise ValueError("No document is open")
        return self._doc.tobytes(garbage=0, deflate=False,
                                 encryption=fitz.PDF_ENCRYPT_KEEP)

    # ==================== Snapshots (undo support) ====================

    def snapshot(self) -> bytes:
        """Serialize the current document to PDF bytes for an undo snapshot.

        Used by the history layer to make destructive, otherwise-irreversible
        operations (redaction, crop, watermark, OCR, header/footer) undoable by
        capturing the document before and after the change.
        """
        if self._doc is None:
            raise ValueError("No document is open")
        # Keep any existing encryption so a restored snapshot re-opens the same way.
        # garbage=1 (drop unused objects) rather than 3: a before/after snapshot
        # only needs a faithful round-trip, not the expensive duplicate-stream-merge
        # pass, which dominates the per-op cost on large documents. deflate=True is
        # kept so the undo stack's in-memory snapshots stay compact.
        return self._doc.tobytes(garbage=1, deflate=True,
                                 encryption=fitz.PDF_ENCRYPT_KEEP)

    def restore(self, data: bytes) -> None:
        """Replace the in-memory document with one rebuilt from snapshot bytes.

        The underlying :class:`fitz.Document` object is swapped, so callers that
        hold the previous ``doc`` (viewer, sidebar) must re-fetch it afterwards.
        """
        new_doc = fitz.open(stream=data, filetype="pdf")
        if new_doc.needs_pass and self._password:
            new_doc.authenticate(self._password)
        old_doc = self._doc
        self._doc = new_doc
        if old_doc is not None:
            try:
                old_doc.close()
            except Exception:
                logger.debug(
                    "Failed to close previous document during restore",
                    exc_info=True)
        self._is_modified = True

    # ==================== Page Operations ====================

    def get_page(self, page_num: int) -> fitz.Page:
        """Get a page object by page number (0-indexed)"""
        if self._doc is None:
            raise ValueError("No document is open")
        if page_num < 0 or page_num >= len(self._doc):
            raise IndexError(f"Page {page_num} out of range")
        return self._doc[page_num]

    def _get_page_label(self, page_num: int) -> str:
        """Get the label for a specific page"""
        try:
            if self._doc is None:
                return str(page_num + 1)
            labels = self._doc.get_page_labels()
            if labels and isinstance(labels, list) and page_num < len(labels):
                label = labels[page_num]
                return str(label) if label else str(page_num + 1)
        except Exception:
            logger.debug(
                "Could not read page label for page %d; using ordinal",
                page_num, exc_info=True)
        return str(page_num + 1)

    def get_page_info(self, page_num: int) -> PageInfo:
        """Get information about a specific page"""
        page = self.get_page(page_num)
        rect = page.rect

        return PageInfo(
            index=page_num,
            width=rect.width,
            height=rect.height,
            rotation=page.rotation,
            has_text=bool(str(page.get_text("text")).strip()),
            has_images=bool(page.get_images()),
            has_annotations=bool(page.annots()),
            label=self._get_page_label(page_num)
        )

    def get_all_pages_info(self) -> List[PageInfo]:
        """Get information about all pages"""
        return [self.get_page_info(i) for i in range(self.page_count)]

    def render_page(self, page_num: int, zoom: float = 1.0,
                    rotation: int = 0, alpha: bool = False) -> fitz.Pixmap:
        """
        Render a page to a pixmap

        Args:
            page_num: Page number (0-indexed)
            zoom: Zoom factor (1.0 = 100%)
            rotation: Additional rotation in degrees
            alpha: Include alpha channel

        Returns:
            fitz.Pixmap object
        """
        page = self.get_page(page_num)
        matrix = fitz.Matrix(zoom, zoom).prerotate(rotation)
        return page.get_pixmap(matrix=matrix, alpha=alpha)

    def render_page_to_image(self, page_num: int, dpi: int = 150) -> bytes:
        """Render a page to PNG image bytes"""
        zoom = dpi / 72.0
        pixmap = self.render_page(page_num, zoom=zoom)
        return pixmap.tobytes("png")

    def add_blank_page(self, width: float = 595, height: float = 842,
                       index: int = -1) -> int:
        """
        Add a blank page to the document

        Args:
            width: Page width in points
            height: Page height in points
            index: Insert position (-1 for end)

        Returns:
            Index of the new page
        """
        if self._doc is None:
            raise ValueError("No document is open")

        if index < 0:
            index = self.page_count

        self._doc.new_page(pno=index, width=width, height=height)
        self._is_modified = True
        return index

    def delete_page(self, page_num: int):
        """Delete a page from the document"""
        if self._doc is None:
            raise ValueError("No document is open")
        self._doc.delete_page(page_num)
        self._is_modified = True

    def delete_pages(self, page_nums: List[int]):
        """Delete multiple pages (in descending order to maintain indices)"""
        for page_num in sorted(page_nums, reverse=True):
            self.delete_page(page_num)

    def rotate_page(self, page_num: int, rotation: int):
        """
        Rotate a page

        Args:
            page_num: Page number (0-indexed)
            rotation: Rotation in degrees (90, 180, 270, or -90, -180, -270)
        """
        page = self.get_page(page_num)
        current_rotation = page.rotation
        new_rotation = (current_rotation + rotation) % 360
        page.set_rotation(new_rotation)
        self._is_modified = True

    def rotate_pages(self, page_nums: List[int], rotation: int):
        """Rotate multiple pages"""
        for page_num in page_nums:
            self.rotate_page(page_num, rotation)

    def move_page(self, from_index: int, to_index: int):
        """Move a page from one position to another"""
        if self._doc is None:
            raise ValueError("No document is open")
        self._doc.move_page(from_index, to_index)
        self._is_modified = True

    def reorder_pages(self, new_order: Sequence[int]) -> bool:
        """Reorder the document's pages to match ``new_order``.

        ``new_order`` is the desired sequence of current page indices (a
        permutation of ``range(page_count)`` for a pure reorder). Used by the
        thumbnail drag-and-drop; computing the full target order avoids any
        ambiguity in single-page move semantics.
        """
        if self._doc is None:
            raise ValueError("No document is open")
        new_order = list(new_order)
        # Document.select() discards the table of contents entirely, so capture
        # it first and remap each entry's page through the permutation, then
        # restore it after the reorder (otherwise every bookmark is lost).
        old_toc = self._doc.get_toc()
        self._doc.select(new_order)
        if old_toc:
            # old page index (0-based) -> new position (0-based)
            remap = {old_idx: new_pos for new_pos, old_idx in enumerate(new_order)}
            new_toc = []
            for entry in old_toc:
                level, title, page = entry[0], entry[1], entry[2]
                old_idx = page - 1
                if old_idx in remap:
                    new_toc.append([level, title, remap[old_idx] + 1])
            if new_toc:
                try:
                    self._doc.set_toc(new_toc)
                except Exception:
                    # Dropping entries can break the level hierarchy; skip
                    # rather than fail the whole reorder.
                    logger.warning(
                        "Could not restore TOC after reorder", exc_info=True)
        self._is_modified = True
        return True

    def copy_page(self, page_num: int, to_index: int = -1) -> int:
        """
        Copy a page within the document

        Args:
            page_num: Source page number
            to_index: Destination index (-1 for end)

        Returns:
            Index of the new page
        """
        if self._doc is None:
            raise ValueError("No document is open")

        # PyMuPDF's copy_page expects ``to`` in range(-1, page_count); -1 means
        # "after the last page". Keep -1 for the append case (mapping it to
        # page_count would be out of range and raise) while still reporting the
        # index the copied page actually lands at.
        new_index = self.page_count if to_index < 0 else to_index
        self._doc.copy_page(page_num, to_index)
        self._is_modified = True
        return new_index

    def extract_pages(self, page_nums: List[int], output_path: Union[str, Path]) -> bool:
        """Extract specific pages to a new PDF"""
        if self._doc is None:
            raise ValueError("No document is open")

        new_doc = fitz.open()
        for page_num in sorted(page_nums):
            new_doc.insert_pdf(self._doc, from_page=page_num, to_page=page_num)

        new_doc.save(str(output_path))
        new_doc.close()
        return True

    # ==================== Merge & Split ====================

    def merge_pdf(self, other_path: Union[str, Path], position: int = -1) -> bool:
        """
        Merge another PDF into this document

        Args:
            other_path: Path to the PDF to merge
            position: Insert position (-1 for end)
        """
        if self._doc is None:
            raise ValueError("No document is open")

        other_doc = fitz.open(str(other_path))

        if position < 0:
            position = self.page_count

        self._doc.insert_pdf(other_doc, start_at=position)
        other_doc.close()
        self._is_modified = True
        return True

    def merge_pdfs(self, pdf_paths: Sequence[Union[str, Path]],
                   output_path: Union[str, Path],
                   add_bookmarks: bool = False,
                   compress: bool = True) -> bool:
        """Merge multiple PDFs into a new file.

        Args:
            pdf_paths: PDFs to merge, in the given order.
            output_path: Destination file.
            add_bookmarks: Add a top-level bookmark per source file.
            compress: Garbage-collect and deflate the output.
        """
        merged_doc = fitz.open()
        toc: List = []

        for pdf_path in pdf_paths:
            if add_bookmarks:
                # The next inserted file starts at the current page count (+1 for
                # the 1-indexed TOC).
                toc.append([1, Path(pdf_path).stem, merged_doc.page_count + 1])
            pdf = fitz.open(str(pdf_path))
            merged_doc.insert_pdf(pdf)
            pdf.close()

        if add_bookmarks and toc:
            merged_doc.set_toc(toc)

        save_options = {"garbage": 4, "deflate": True} if compress else {}
        merged_doc.save(str(output_path), **save_options)
        merged_doc.close()
        return True

    def split_by_pages(self, output_dir: Union[str, Path],
                       pages_per_file: int = 1) -> List[str]:
        """
        Split document into multiple files

        Args:
            output_dir: Directory for output files
            pages_per_file: Number of pages per output file

        Returns:
            List of created file paths
        """
        if self._doc is None:
            raise ValueError("No document is open")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        base_name = self._filepath.stem if self._filepath else "split"

        for i in range(0, self.page_count, pages_per_file):
            end_page = min(i + pages_per_file - 1, self.page_count - 1)

            new_doc = fitz.open()
            new_doc.insert_pdf(self._doc, from_page=i, to_page=end_page)

            output_path = output_dir / f"{base_name}_pages_{i+1}-{end_page+1}.pdf"
            new_doc.save(str(output_path))
            new_doc.close()

            created_files.append(str(output_path))

        return created_files

    def split_by_ranges(self, ranges: List[Tuple[int, int]],
                        output_dir: Union[str, Path]) -> List[str]:
        """
        Split document by specific page ranges

        Args:
            ranges: List of (start, end) tuples (0-indexed, inclusive)
            output_dir: Directory for output files

        Returns:
            List of created file paths
        """
        if self._doc is None:
            raise ValueError("No document is open")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        created_files = []
        base_name = self._filepath.stem if self._filepath else "split"

        for idx, (start, end) in enumerate(ranges):
            new_doc = fitz.open()
            new_doc.insert_pdf(self._doc, from_page=start, to_page=end)

            output_path = output_dir / f"{base_name}_part_{idx+1}.pdf"
            new_doc.save(str(output_path))
            new_doc.close()

            created_files.append(str(output_path))

        return created_files

    def split_by_bookmarks(self, output_dir: Union[str, Path]) -> List[str]:
        """
        Split the document at each top-level (level-1) bookmark.

        Each chapter becomes its own file spanning from its bookmark page up to
        (but not including) the next top-level bookmark's page.

        Returns:
            List of created file paths.
        """
        if self._doc is None:
            raise ValueError("No document is open")

        points = [(entry[1], entry[2] - 1)
                  for entry in self._doc.get_toc() if entry[0] == 1]
        if not points:
            raise ValueError("Document has no top-level bookmarks to split by")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        base_name = self._filepath.stem if self._filepath else "split"

        created_files: List[str] = []
        for i, (title, start) in enumerate(points):
            end = points[i + 1][1] - 1 if i < len(points) - 1 else self.page_count - 1
            end = max(end, start)

            new_doc = fitz.open()
            new_doc.insert_pdf(self._doc, from_page=start, to_page=end)

            safe = "".join(c for c in title if c.isalnum() or c in " -_").strip()[:50]
            output_path = output_dir / f"{base_name}_{safe or f'part_{i+1}'}.pdf"
            new_doc.save(str(output_path))
            new_doc.close()
            created_files.append(str(output_path))

        return created_files

    # ==================== Text Operations ====================

    def get_page_text(self, page_num: int, text_type: str = "text") -> str:
        """
        Extract text from a page

        Args:
            page_num: Page number
            text_type: Type of text extraction ("text", "blocks", "words", "html", "dict", "json", "rawdict", "xhtml", "xml")
        """
        page = self.get_page(page_num)
        result = page.get_text(text_type)
        # Ensure we return a string for the common "text" type
        if isinstance(result, str):
            return result
        return str(result)

    def get_all_text(self) -> str:
        """Extract all text from the document"""
        texts = []
        for i in range(self.page_count):
            texts.append(self.get_page_text(i))
        return "\n\n".join(texts)

    def search_text(self, text: str, case_sensitive: bool = False) -> List[Dict]:
        """
        Search for text in the document

        Returns:
            List of dicts with page number and rectangles
        """
        if self._doc is None:
            raise ValueError("No document is open")

        results = []
        # PyMuPDF's search_for is always case-insensitive; the flag here only
        # controls whitespace handling, not case. When the caller wants a
        # case-sensitive match we post-filter each hit against the exact-case
        # text inside its bounding box.
        flags = fitz.TEXT_PRESERVE_WHITESPACE

        for page_num in range(self.page_count):
            page = self.get_page(page_num)
            rects = page.search_for(text, flags=flags)
            if case_sensitive and rects:
                rects = [r for r in rects if text in page.get_textbox(r)]
            if rects:
                results.append({
                    "page": page_num,
                    "rects": [(r.x0, r.y0, r.x1, r.y1) for r in rects]
                })

        return results

    # ---- text replacement (redaction-based) ----

    @staticmethod
    def _estimate_fontsize(page: fitz.Page, rect: fitz.Rect) -> float:
        """Best-effort font size of the text inside ``rect``.

        Falls back to a height-based estimate when no spans are found, so the
        replacement text roughly matches the original.
        """
        try:
            d = page.get_text("dict", clip=rect)
            sizes = [s["size"]
                     for b in d.get("blocks", []) if b.get("type") == 0
                     for line in b.get("lines", [])
                     for s in line.get("spans", [])]
            if sizes:
                return max(1.0, min(sizes))
        except Exception:
            logger.debug("Could not estimate font size; using height", exc_info=True)
        return max(1.0, rect.height * 0.8)

    def _redact_replace_rect(self, page: fitz.Page, rect: fitz.Rect,
                             replacement: str) -> None:
        """Queue a redaction that erases ``rect`` and draws ``replacement`` in it.

        Caller must invoke ``page.apply_redactions()`` afterwards. The replaced
        text is re-typeset in Helvetica at the original's estimated size, so the
        original font/styling is not preserved — the honest limitation of PDF
        text replacement.
        """
        fontsize = self._estimate_fontsize(page, rect)
        page.add_redact_annot(
            rect, text=replacement, fontname="helv", fontsize=fontsize,
            text_color=(0, 0, 0), fill=(1, 1, 1), align=fitz.TEXT_ALIGN_LEFT)

    def replace_text_all(self, search: str, replacement: str,
                         case_sensitive: bool = False) -> int:
        """Replace every occurrence of ``search`` with ``replacement``.

        Uses redaction: the original text is removed and the replacement drawn
        in its place. Returns the number of occurrences replaced.
        """
        if self._doc is None:
            raise ValueError("No document is open")
        if not search:
            return 0

        count = 0
        for page_num in range(self.page_count):
            page = self._doc[page_num]
            rects = page.search_for(search, flags=fitz.TEXT_PRESERVE_WHITESPACE)
            if case_sensitive and rects:
                rects = [r for r in rects if search in page.get_textbox(r)]
            if not rects:
                continue
            for r in rects:
                self._redact_replace_rect(page, r, replacement)
                count += 1
            page.apply_redactions()

        if count:
            self._is_modified = True
        return count

    def replace_text_one(self, page_num: int,
                         rect: Tuple[float, float, float, float],
                         replacement: str) -> bool:
        """Replace a single occurrence located at ``rect`` on ``page_num``."""
        if self._doc is None:
            raise ValueError("No document is open")
        page = self._doc[page_num]
        self._redact_replace_rect(page, fitz.Rect(rect), replacement)
        page.apply_redactions()
        self._is_modified = True
        return True

    # ==================== Inline text editing ====================
    # detect_text_block + replace_text_block power the "Edit Text" tool: pick the
    # paragraph under a click, then erase it and re-typeset the new text with
    # reflow, reusing the detected font/size/colour. Fidelity is best-effort —
    # subsetted embedded fonts may lack newly typed glyphs (then a matched base-14
    # font is used), and mixed inline styling within a block is flattened to its
    # dominant style. See replace_text_block for the honest limitations.

    @staticmethod
    def _int_color_to_rgb(color: Any) -> Tuple[float, float, float]:
        """Convert a PyMuPDF span colour (an sRGB int) to an (r, g, b) 0-1 triple."""
        if isinstance(color, (tuple, list)):
            c = tuple(float(v) for v in color[:3]) or (0.0, 0.0, 0.0)
            if len(c) < 3:
                return (0.0, 0.0, 0.0)
            return tuple(v / 255.0 if v > 1 else v for v in c)  # type: ignore[return-value]
        try:
            c = int(color)
        except (TypeError, ValueError):
            return (0.0, 0.0, 0.0)
        return ((c >> 16 & 255) / 255.0, (c >> 8 & 255) / 255.0, (c & 255) / 255.0)

    @staticmethod
    def _fallback_fontname(flags: int) -> str:
        """A base-14 font short-name matching the bold/italic/serif/mono of ``flags``."""
        idx = (1 if flags & _SPAN_FLAG_BOLD else 0) + (2 if flags & _SPAN_FLAG_ITALIC else 0)
        if flags & _SPAN_FLAG_MONO:
            family = ("cour", "cobo", "coit", "cobi")
        elif flags & _SPAN_FLAG_SERIF:
            family = ("tiro", "tibo", "tiit", "tibi")
        else:
            family = ("helv", "hebo", "heit", "hebi")
        return family[idx]

    @staticmethod
    def _font_covers(font: "fitz.Font", text: str) -> bool:
        """True if ``font`` has a glyph for every non-space character in ``text``."""
        for ch in text:
            if ch.isspace():
                continue
            try:
                if font.has_glyph(ord(ch)) == 0:   # 0 == .notdef / missing
                    return False
            except Exception:
                return False
        return True

    def _resolve_font_xref(self, page: "fitz.Page", span_font: str) -> int:
        """xref of the embedded font whose base name matches ``span_font`` (else 0)."""
        if not span_font:
            return 0
        target = span_font.split("+")[-1].lower()
        try:
            for info in page.get_fonts(full=True):
                xref, basefont = info[0], (info[3] or "")
                name = basefont.split("+")[-1].lower()
                if name and (name == target or name in target or target in name):
                    return xref
        except Exception:
            logger.debug("get_fonts failed during font resolution", exc_info=True)
        return 0

    def _font_for_style(self, style: Dict[str, Any], text: str) -> Tuple["fitz.Font", str]:
        """Pick a font for re-typesetting: the embedded one if it covers ``text``,
        otherwise a base-14 font matched to the original's bold/italic/serif/mono.

        Returns ``(fitz.Font, label)`` where label is ``"embedded:<name>"`` or
        ``"base14:<name>"`` so the UI can tell the user when a fallback was used.
        """
        xref = int(style.get("font_xref", 0) or 0)
        if xref and self._doc is not None:
            try:
                info = self._doc.extract_font(xref)
                buffer = info[3] if info and len(info) >= 4 else None
                if buffer:
                    font = fitz.Font(fontbuffer=buffer)
                    if self._font_covers(font, text):
                        return font, "embedded:" + (info[0] or "")
            except Exception:
                logger.debug("extract_font failed for xref %s", xref, exc_info=True)
        name = self._fallback_fontname(int(style.get("flags", 0)))
        return fitz.Font(name), "base14:" + name

    @staticmethod
    def _infer_align(block: Dict[str, Any]) -> int:
        """Guess paragraph alignment from how the block's line edges line up."""
        lines = [ln for ln in block.get("lines", []) if ln.get("spans")]
        if len(lines) < 2:
            return fitz.TEXT_ALIGN_LEFT

        def spread(vals: List[float]) -> float:
            return max(vals) - min(vals)

        x0s = [ln["bbox"][0] for ln in lines]
        x1s = [ln["bbox"][2] for ln in lines]
        centers = [(ln["bbox"][0] + ln["bbox"][2]) / 2 for ln in lines]
        left_aligned = spread(x0s) <= 2.0
        right_aligned = spread(x1s) <= 2.0
        if left_aligned and right_aligned:
            return fitz.TEXT_ALIGN_JUSTIFY
        if right_aligned and not left_aligned:
            return fitz.TEXT_ALIGN_RIGHT
        if spread(centers) <= 2.0 and not left_aligned:
            return fitz.TEXT_ALIGN_CENTER
        return fitz.TEXT_ALIGN_LEFT

    def detect_text_block(self, page_num: int,
                          point: Tuple[float, float]) -> Optional[Dict[str, Any]]:
        """Find the text paragraph under ``point`` (PDF coords) on ``page_num``.

        Returns ``None`` when the point isn't over a text block (e.g. a scanned
        page with no text layer). Otherwise returns a dict with the block's
        ``bbox``, the joined ``text``, the dominant ``style`` (fontsize, rgb
        colour, flags, fontname, embedded font xref) and an inferred ``align``.
        """
        if self._doc is None or not (0 <= page_num < self.page_count):
            return None
        try:
            page = self._doc[page_num]
            data = page.get_text("dict")
        except Exception:
            logger.exception("detect_text_block: get_text failed")
            return None

        pt = fitz.Point(float(point[0]), float(point[1]))
        tol = 3.0
        best = None
        best_area: Optional[float] = None
        for blk in data.get("blocks", []):
            if blk.get("type") != 0:
                continue
            x0, y0, x1, y1 = blk["bbox"]
            if not fitz.Rect(x0 - tol, y0 - tol, x1 + tol, y1 + tol).contains(pt):
                continue
            area = (x1 - x0) * (y1 - y0)
            if best_area is None or area < best_area:
                best, best_area = blk, area
        if best is None:
            return None

        lines_text: List[str] = []
        spans_all: List[Dict[str, Any]] = []
        for line in best.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            spans_all.extend(spans)
            lines_text.append("".join(s.get("text", "") for s in spans))
        text = " ".join(t.strip() for t in lines_text if t.strip()).strip()
        if not text or not spans_all:
            return None

        # Dominant style: the (size, font, flags, colour) carrying the most text.
        weights: "defaultdict[Tuple, float]" = defaultdict(float)
        for s in spans_all:
            key = (round(float(s.get("size", 0.0)), 1), s.get("font", ""),
                   int(s.get("flags", 0)), s.get("color", 0))
            weights[key] += max(1, len(s.get("text", "")))
        size, font_name, flags, color_int = max(weights, key=lambda k: weights[k])

        style = {
            "fontsize": float(size) if size else 12.0,
            "color": self._int_color_to_rgb(color_int),
            "flags": int(flags),
            "fontname": font_name,
            "font_xref": self._resolve_font_xref(page, font_name),
        }
        return {
            "page": page_num,
            "bbox": tuple(float(v) for v in best["bbox"]),
            "text": text,
            "style": style,
            "align": self._infer_align(best),
        }

    def replace_text_block(self, page_num: int,
                           bbox: Tuple[float, float, float, float],
                           new_text: str, style: Dict[str, Any],
                           bg_color: Optional[Tuple[float, float, float]] = None
                           ) -> Dict[str, Any]:
        """Erase the paragraph at ``bbox`` and re-typeset ``new_text`` into it.

        The old text is removed by redaction (filled with ``bg_color`` or white),
        then the new text is re-flowed into the same rectangle with the detected
        font/size/colour. The font size is reduced (to a 5pt floor) if the new
        text doesn't fit; anything still overflowing is clipped and reported.

        Honest limitations: a white/sampled fill can show on non-white
        backgrounds; subsetted embedded fonts may force a base-14 fallback;
        justification/kerning/leading aren't reproduced; view rotation isn't
        handled. Returns ``{overflow, fontsize_used, font, truncated}``.
        """
        if self._doc is None:
            raise ValueError("No document is open")
        if not (0 <= page_num < self.page_count):
            raise ValueError("page_num out of range")

        rect = fitz.Rect(bbox)
        fill = bg_color if bg_color is not None else (1.0, 1.0, 1.0)
        page = self._doc[page_num]

        # 1) Erase the old text. Keep underlying images intact.
        page.add_redact_annot(rect, fill=fill)
        try:
            page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        except (TypeError, AttributeError):
            page.apply_redactions()

        # 2) Re-typeset the new text (a fresh page handle post-redaction).
        page = self._doc[page_num]
        text = new_text or ""
        font, label = self._font_for_style(style, text)
        color = style.get("color", (0.0, 0.0, 0.0))
        align = int(style.get("align", fitz.TEXT_ALIGN_LEFT))
        used = float(style.get("fontsize", 12.0)) or 12.0

        overflow: Any = None
        truncated = False
        if text.strip():
            while True:
                writer = fitz.TextWriter(page.rect)
                try:
                    # fill_textbox returns the (possibly empty) list of lines that
                    # did not fit; empty means everything fit. It raises if the box
                    # is too short for even the first line at this size.
                    overflow = writer.fill_textbox(
                        rect, text, font=font, fontsize=used, align=align)
                    started = True
                except Exception:
                    overflow = None
                    started = False
                too_big = (not started) or bool(overflow)
                if not too_big or used <= _MIN_EDIT_FONTSIZE:
                    if started:
                        writer.write_text(page, color=color)
                    truncated = too_big
                    break
                used = round(used - 0.5, 1)

        self._is_modified = True
        return {
            "overflow": overflow if isinstance(overflow, list) else [],
            "fontsize_used": used,
            "font": label,
            "truncated": truncated,
        }

    def add_text(self, page_num: int, text: str, position: Tuple[float, float],
                 font_size: float = 12, font_name: str = "helv",
                 color: Tuple[float, float, float] = (0, 0, 0)) -> bool:
        """Add text to a page"""
        page = self.get_page(page_num)

        text_writer = fitz.TextWriter(page.rect)
        font = fitz.Font(font_name)
        text_writer.append(position, text, font=font, fontsize=int(font_size))
        text_writer.write_text(page, color=color)

        self._is_modified = True
        return True

    # ==================== Image Operations ====================

    def get_page_images(self, page_num: int) -> List[Dict]:
        """Get list of images on a page"""
        page = self.get_page(page_num)
        images = page.get_images()

        result = []
        for img in images:
            xref = img[0]
            result.append({
                "xref": xref,
                "width": img[2],
                "height": img[3],
                "bpc": img[4],
                "colorspace": img[5],
            })
        return result

    def extract_image(self, xref: int) -> bytes:
        """Extract an image by its xref"""
        if self._doc is None:
            raise ValueError("No document is open")
        return self._doc.extract_image(xref)["image"]

    def extract_all_images(self, output_dir: Union[str, Path]) -> List[str]:
        """Extract all images from the document"""
        if self._doc is None:
            raise ValueError("No document is open")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        saved_files = []
        image_count = 0

        for page_num in range(self.page_count):
            page = self.get_page(page_num)
            images = page.get_images()

            for img in images:
                xref = img[0]
                image_data = self._doc.extract_image(xref)

                ext = image_data["ext"]
                image_bytes = image_data["image"]

                filename = f"image_{page_num+1}_{image_count+1}.{ext}"
                filepath = output_dir / filename

                with open(filepath, "wb") as f:
                    f.write(image_bytes)

                saved_files.append(str(filepath))
                image_count += 1

        return saved_files

    def insert_image(self, page_num: int, image_path: Union[str, Path],
                     rect: Optional[Tuple[float, float, float, float]] = None,
                     keep_proportion: bool = True) -> bool:
        """Insert an image into a page"""
        page = self.get_page(page_num)

        if rect:
            target_rect = fitz.Rect(rect)
        else:
            target_rect = page.rect

        page.insert_image(target_rect, filename=str(image_path),
                         keep_proportion=keep_proportion)
        self._is_modified = True
        return True

    # ==================== Metadata ====================

    def get_metadata(self) -> DocumentMetadata:
        """Get document metadata"""
        if self._doc is None:
            raise ValueError("No document is open")

        meta = self._doc.metadata or {}

        return DocumentMetadata(
            title=meta.get("title", "") if meta else "",
            author=meta.get("author", "") if meta else "",
            subject=meta.get("subject", "") if meta else "",
            keywords=meta.get("keywords", "") if meta else "",
            creator=meta.get("creator", "") if meta else "",
            producer=meta.get("producer", "") if meta else "",
            creation_date=meta.get("creationDate", "") if meta else "",
            modification_date=meta.get("modDate", "") if meta else "",
            encryption="Yes" if self.is_encrypted else "No",
            page_count=self.page_count,
            file_size=self._filepath.stat().st_size if self._filepath else 0,
            pdf_version=f"PDF {meta.get('format', 'Unknown') if meta else 'Unknown'}"
        )

    def set_metadata(self, metadata: Dict[str, str]) -> bool:
        """Set document metadata"""
        if self._doc is None:
            raise ValueError("No document is open")

        self._doc.set_metadata(metadata)
        self._is_modified = True
        return True

    # ==================== Bookmarks/TOC ====================

    def get_toc(self) -> List:
        """Get table of contents (bookmarks)"""
        if self._doc is None:
            raise ValueError("No document is open")
        return self._doc.get_toc()

    def set_toc(self, toc: List) -> bool:
        """
        Set table of contents

        Args:
            toc: List of [level, title, page, dest] entries
        """
        if self._doc is None:
            raise ValueError("No document is open")
        self._doc.set_toc(toc)
        self._is_modified = True
        return True

    def add_bookmark(self, title: str, page_num: int, level: int = 1) -> bool:
        """Add a bookmark"""
        toc = self.get_toc()
        toc.append([level, title, page_num + 1])
        return self.set_toc(toc)

    # ==================== Annotations ====================

    def get_annotations(self, page_num: int) -> List[fitz.Annot]:
        """Get all annotations on a page"""
        page = self.get_page(page_num)
        return list(page.annots()) if page.annots() else []

    def add_highlight(self, page_num: int, rect: Tuple[float, float, float, float],
                      color: Tuple[float, float, float] = (1, 1, 0),
                      opacity: float = 1.0) -> fitz.Annot:
        """Add a highlight annotation"""
        page = self.get_page(page_num)
        annot = page.add_highlight_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_underline(self, page_num: int, rect: Tuple[float, float, float, float],
                      color: Tuple[float, float, float] = (0, 0, 1),
                      opacity: float = 1.0) -> fitz.Annot:
        """Add an underline annotation"""
        page = self.get_page(page_num)
        annot = page.add_underline_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_strikethrough(self, page_num: int, rect: Tuple[float, float, float, float],
                          color: Tuple[float, float, float] = (1, 0, 0),
                          opacity: float = 1.0) -> fitz.Annot:
        """Add a strikethrough annotation"""
        page = self.get_page(page_num)
        annot = page.add_strikeout_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_text_annotation(self, page_num: int, position: Tuple[float, float],
                            text: str, icon: str = "Note") -> fitz.Annot:
        """Add a sticky note/text annotation"""
        page = self.get_page(page_num)
        annot = page.add_text_annot(fitz.Point(position), text, icon=icon)
        annot.update()
        self._is_modified = True
        return annot

    def add_freetext(self, page_num: int, rect: Tuple[float, float, float, float],
                     text: str, font_size: float = 12,
                     text_color: Tuple[float, float, float] = (0, 0, 0),
                     fill_color: Tuple[float, float, float] = (1, 1, 1)) -> fitz.Annot:
        """Add a free text box annotation"""
        page = self.get_page(page_num)
        annot = page.add_freetext_annot(
            fitz.Rect(rect),
            text,
            fontsize=font_size,
            text_color=text_color,
            fill_color=fill_color
        )
        annot.update()
        self._is_modified = True
        return annot

    def add_rect_annotation(self, page_num: int, rect: Tuple[float, float, float, float],
                            stroke_color: Tuple[float, float, float] = (1, 0, 0),
                            fill_color: Optional[Tuple[float, float, float]] = None,
                            width: float = 1, opacity: float = 1.0) -> fitz.Annot:
        """Add a rectangle annotation"""
        page = self.get_page(page_num)
        annot = page.add_rect_annot(fitz.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=int(width))
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_circle_annotation(self, page_num: int, rect: Tuple[float, float, float, float],
                              stroke_color: Tuple[float, float, float] = (1, 0, 0),
                              fill_color: Optional[Tuple[float, float, float]] = None,
                              width: float = 1, opacity: float = 1.0) -> fitz.Annot:
        """Add a circle/ellipse annotation"""
        page = self.get_page(page_num)
        annot = page.add_circle_annot(fitz.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=int(width))
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_line_annotation(self, page_num: int,
                            start: Tuple[float, float], end: Tuple[float, float],
                            color: Tuple[float, float, float] = (1, 0, 0),
                            width: float = 1, opacity: float = 1.0) -> fitz.Annot:
        """Add a line annotation"""
        page = self.get_page(page_num)
        annot = page.add_line_annot(fitz.Point(start), fitz.Point(end))
        annot.set_colors(stroke=color)
        annot.set_border(width=int(width))
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def add_ink_annotation(self, page_num: int,
                           points: List[List[Tuple[float, float]]],
                           color: Tuple[float, float, float] = (0, 0, 0),
                           width: float = 2, opacity: float = 1.0) -> fitz.Annot:
        """Add a freehand drawing (ink) annotation"""
        page = self.get_page(page_num)
        # PyMuPDF expects list of lists of point sequences
        # Each point can be a tuple (x, y) or fitz.Point
        annot = page.add_ink_annot(points)
        annot.set_colors(stroke=color)
        annot.set_border(width=int(width))
        annot.set_opacity(opacity)
        annot.update()
        self._is_modified = True
        return annot

    def delete_annotation(self, page_num: int, annot: fitz.Annot):
        """Delete an annotation"""
        page = self.get_page(page_num)
        page.delete_annot(annot)
        self._is_modified = True

    # ==================== Watermark ====================

    def add_watermark(self, text: str,
                      font_size: float = 48,
                      color: Tuple[float, float, float] = (0.5, 0.5, 0.5),
                      opacity: float = 0.3,
                      rotation: float = 45,
                      pages: Optional[List[int]] = None) -> bool:
        """Add a text watermark to pages"""
        if self._doc is None:
            raise ValueError("No document is open")

        target_pages = pages if pages else range(self.page_count)

        for page_num in target_pages:
            page = self.get_page(page_num)
            rect = page.rect

            # Create watermark shape
            shape = page.new_shape()

            # Calculate center position
            center = fitz.Point(rect.width / 2, rect.height / 2)

            # Insert text with rotation
            shape.insert_text(
                center,
                text,
                fontsize=font_size,
                color=color,
                rotate=int(rotation),
            )

            shape.finish(color=color, fill=color, fill_opacity=opacity)
            shape.commit()

        self._is_modified = True
        return True

    def add_image_watermark(self, image_path: Union[str, Path],
                            opacity: float = 0.3,
                            pages: Optional[List[int]] = None) -> bool:
        """Add an image watermark to pages"""
        if self._doc is None:
            raise ValueError("No document is open")

        target_pages = pages if pages else range(self.page_count)

        for page_num in target_pages:
            page = self.get_page(page_num)
            rect = page.rect

            # Insert watermark image
            page.insert_image(rect, filename=str(image_path), overlay=True,
                            keep_proportion=True, alpha=int(opacity * 255))

        self._is_modified = True
        return True

    # ==================== Security ====================

    def encrypt(self, user_password: str = "", owner_password: str = "",
                permissions: Optional[int] = None,
                method: int = fitz.PDF_ENCRYPT_AES_256) -> bool:
        """
        Queue password encryption to be applied on the next save.

        PyMuPDF can only (re)encrypt a PDF during a full rewrite, so the settings
        are stored here and applied by :meth:`save`. The usual flow is
        ``encrypt(...)`` followed by ``save(...)`` to write the encrypted file.

        Args:
            user_password: Password required to open the document.
            owner_password: Password granting full permissions. Defaults to the
                user password when omitted so the file isn't left with an empty
                owner password.
            permissions: Optional permission bitmask built from ``fitz.PDF_PERM_*``
                flags (e.g. ``fitz.PDF_PERM_PRINT | fitz.PDF_PERM_COPY``). When
                ``None`` every action is permitted and the password only controls
                opening the document.
            method: Encryption algorithm (default AES-256).

        Returns:
            True once the encryption request has been queued.
        """
        if self._doc is None:
            raise ValueError("No document is open")

        if not user_password and not owner_password:
            raise ValueError("At least one of user_password or owner_password is required")

        enc: Dict[str, Any] = {"method": method}
        if user_password:
            enc["user_password"] = user_password
        # Always set an owner password (falling back to the user password) so the
        # document can't be opened with full owner rights and no password.
        enc["owner_password"] = owner_password or user_password
        if permissions is not None:
            enc["permissions"] = permissions

        self._pending_encryption = enc
        # Re-opening the encrypted file after the save needs the open password.
        self._password = user_password or owner_password or None
        self._is_modified = True
        return True

    def decrypt(self, password: str) -> bool:
        """Decrypt the document"""
        if self._doc is None:
            raise ValueError("No document is open")

        if self._doc.authenticate(password):
            self._password = password
            return True
        return False

    def save_unencrypted(self, output_path: Union[str, Path]) -> bool:
        """Save an unprotected copy of the (already open) document.

        No password prompt: the document is already authenticated, so we re-prime
        it with the stored password before serializing — without that, writing the
        streams back out without encryption can fail (empty/garbled content) once
        the document has been serialized elsewhere (e.g. for the render worker).
        """
        if self._doc is None:
            raise ValueError("No document is open")
        if self._password:
            self._doc.authenticate(self._password)
        self._doc.save(str(output_path), encryption=fitz.PDF_ENCRYPT_NONE)
        return True

    # ==================== Compression ====================

    def compress(self, output_path: Optional[Union[str, Path]] = None,
                 garbage: int = 4,
                 deflate: bool = True,
                 deflate_images: bool = True,
                 deflate_fonts: bool = True,
                 image_quality: int = 85) -> bool:
        """
        Compress the PDF to reduce file size

        Args:
            output_path: Optional output path
            garbage: Garbage collection level (0-4)
            deflate: Compress streams
            deflate_images: Compress images
            deflate_fonts: Compress fonts
            image_quality: JPEG quality for images (1-100)
        """
        # full_rewrite ensures garbage collection runs even when compressing in
        # place — an incremental save would leave the file size unchanged.
        return self.save(
            output_path,
            garbage=garbage,
            deflate=deflate,
            deflate_images=deflate_images,
            deflate_fonts=deflate_fonts,
            full_rewrite=True,
        )

    # ==================== Clean PDF — Scan & Redact ====================
    #
    # scan_margin_text()  — scan pages, return repeating items for user review
    # redact_findings()   — redact user-selected items
    # ------------------------------------------------------------------

    _MARGIN_FRAC   = 0.10   # top / bottom 10 % of page height (percentage cap)
    _MARGIN_MAX_PT = 80.0   # hard cap: never more than 80 pt (~1.1 in) from edge
    _MAX_HF_LEN    = 120    # lines longer than this are body text

    # ---- margin line extraction ----

    @staticmethod
    def _margin_lines(page: fitz.Page, margin_frac: float) -> List[Dict[str, Any]]:
        """Return text lines sitting in the top or bottom margin zone.

        The zone depth is min(margin_frac * page_height, _MARGIN_MAX_PT) so
        that on tall pages we don't reach into the content area.
        """
        pr = page.rect
        depth = min(pr.height * margin_frac, PDFDocument._MARGIN_MAX_PT)
        top_lim = pr.y0 + depth
        bot_lim = pr.y1 - depth

        out: List[Dict[str, Any]] = []
        for blk in page.get_text("dict").get("blocks", []):
            if blk.get("type") != 0:
                continue
            for line in blk.get("lines", []):
                bbox = line["bbox"]
                cy = (bbox[1] + bbox[3]) / 2.0
                if cy < top_lim:
                    zone = "top"
                elif cy > bot_lim:
                    zone = "bottom"
                else:
                    continue
                spans = line.get("spans", [])
                if not spans:
                    continue
                text = "".join(s.get("text", "") for s in spans).strip()
                if not text:
                    continue
                out.append({
                    "zone":  zone,
                    "bbox":  bbox,
                    "text":  text,
                    "spans": spans,
                })
        return out

    # ---- header / footer detection ----

    _NUM_RE  = re.compile(r"\d+")
    _DATE_RE = re.compile(
        r"\d{1,2}[/\-.]\d{1,2}[/\-.]\d{2,4}"
        r"|\d{4}[/\-.]\d{1,2}[/\-.]\d{1,2}"
        r"|(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w*\s+\d{1,2},?\s*\d{4}",
        re.IGNORECASE,
    )

    @staticmethod
    def _templatize(text: str) -> str:
        """Replace dates and numbers with '#' for template matching."""
        t = PDFDocument._DATE_RE.sub("#", text)
        t = PDFDocument._NUM_RE.sub("#", t)
        return " ".join(t.lower().split())

    # ---- page-number detection ----

    _PN_ARABIC_RE = re.compile(
        r"^[\s\-–—|\[\](){}/.*·©®]*"
        r"(?:page|pg\.?|p\.?)?\s*"
        r"(\d{1,5})"
        r"(?:\s*(?:of|/)\s*\d{1,5})?"
        r"[\s\-–—|\[\](){}/.*·©®]*$",
        re.IGNORECASE,
    )
    _PN_ROMAN_RE = re.compile(
        r"^[\s\-–—|\[\](){}/.*·]*"
        r"(?:page\s+)?"
        r"((?=[IVXLCDM])"
        r"M{0,4}(?:CM|CD|D?C{0,3})(?:XC|XL|L?X{0,3})(?:IX|IV|V?I{0,3}))"
        r"[\s\-–—|\[\](){}/.*·]*$",
        re.IGNORECASE,
    )

    @staticmethod
    def _extract_page_number(text: str) -> Optional[int]:
        t = text.strip()
        if not t or len(t) > 30:
            return None
        m = PDFDocument._PN_ARABIC_RE.match(t)
        if m:
            return int(m.group(1))
        m = PDFDocument._PN_ROMAN_RE.match(t)
        if m and m.group(1):
            val = PDFDocument._roman_to_int(m.group(1))
            if 0 < val < 5000:
                return val
        return None

    @staticmethod
    def _roman_to_int(s: str) -> int:
        _map = {"I": 1, "V": 5, "X": 10, "L": 50,
                "C": 100, "D": 500, "M": 1000}
        s = s.upper()
        total = prev = 0
        for ch in reversed(s):
            v = _map.get(ch, 0)
            total += -v if v < prev else v
            prev = v
        return total

    # ---- public scan & redact methods ----

    def scan_margin_text(self) -> List[Dict[str, Any]]:
        """
        Scan all pages for repeating text in the top/bottom margin zones.

        Returns a list of finding dicts for the user to review:
          {
            "id":          str,                 # unique group key
            "zone":        "Header" | "Footer",
            "sample_text": str,                 # representative text
            "page_count":  int,                 # pages this appears on
            "total_pages": int,
            "category":    "Page Number" | "Text",
            "rects":       [(page_idx, fitz.Rect), ...],
          }

        Only groups appearing on ≥ 30 % of pages (min 2) are returned.
        """
        if self._doc is None:
            raise ValueError("No document is open")

        doc = self._doc
        page_count = len(doc)
        if page_count < 2:
            return []

        mf = PDFDocument._MARGIN_FRAC
        ml = PDFDocument._MAX_HF_LEN

        # ---- pass 1: collect all margin lines and count lines-per-zone-per-page ----
        # key = (zone, tmpl) → {pages: set, lines: [(page_idx, bbox, text)], sample: str}
        groups: Dict[Tuple[str, str], Dict[str, Any]] = defaultdict(
            lambda: {"pages": set(), "lines": [], "sample": ""}
        )
        # (page_idx, zone) → count of distinct lines on that page in that zone
        page_zone_count: Dict[Tuple[int, str], int] = defaultdict(int)

        for page_idx in range(page_count):
            page = doc[page_idx]
            for ln in PDFDocument._margin_lines(page, mf):
                text = ln["text"]
                if len(text) > ml:
                    continue
                tmpl = PDFDocument._templatize(text)
                if len(tmpl) < 1:
                    continue
                zone = ln["zone"]
                page_zone_count[(page_idx, zone)] += 1
                key = (zone, tmpl)
                g = groups[key]
                g["pages"].add(page_idx)
                g["lines"].append((page_idx, ln["bbox"], text))
                if not g["sample"]:
                    g["sample"] = text

        # ---- determine which zones are "content-heavy" (likely tables) ----
        # If the median lines-per-page in a zone exceeds 3, that zone is table content.
        zone_line_counts: Dict[str, List[int]] = defaultdict(list)
        for (page_idx, zone), cnt in page_zone_count.items():
            zone_line_counts[zone].append(cnt)

        crowded_zones: set = set()
        for zone, counts in zone_line_counts.items():
            counts_sorted = sorted(counts)
            median = counts_sorted[len(counts_sorted) // 2]
            if median > 6:
                crowded_zones.add(zone)

        threshold = max(2, int(page_count * 0.30))
        findings: List[Dict[str, Any]] = []

        for (zone, tmpl), g in groups.items():
            if zone in crowded_zones:
                continue  # zone is table content, not a header/footer
            if len(g["pages"]) < threshold:
                continue

            sample = g["sample"]
            is_page_num = PDFDocument._extract_page_number(sample) is not None

            rects: List[Tuple[int, fitz.Rect]] = []
            for page_idx, bbox, _text in g["lines"]:
                bx0, by0, bx1, by1 = bbox
                rects.append((page_idx, fitz.Rect(bx0 - 2, by0 - 2, bx1 + 2, by1 + 2)))

            findings.append({
                "id":          f"{zone}::{tmpl}",
                "zone":        "Header" if zone == "top" else "Footer",
                "sample_text": sample,
                "page_count":  len(g["pages"]),
                "total_pages": page_count,
                "category":    "Page Number" if is_page_num else "Text",
                "rects":       rects,
            })

        findings.sort(key=lambda f: (0 if f["zone"] == "Header" else 1, -f["page_count"]))
        return findings

    def redact_findings(self, findings: List[Dict[str, Any]]) -> Tuple[int, int]:
        """
        Apply redactions for user-selected findings.

        Returns (items_removed, pages_modified).
        """
        if self._doc is None:
            raise ValueError("No document is open")
        if not findings:
            return 0, 0

        by_page: Dict[int, List[fitz.Rect]] = defaultdict(list)
        total_rects = 0
        for finding in findings:
            for page_idx, rect in finding["rects"]:
                by_page[page_idx].append(rect)
                total_rects += 1

        for page_idx, rects in by_page.items():
            page = self._doc[page_idx]
            for r in rects:
                page.add_redact_annot(r, fill=(1, 1, 1))
            page.apply_redactions()

        self._is_modified = True
        return total_rects, len(by_page)

    def redact_area(self, page_idx: int, rect: fitz.Rect) -> None:
        """Permanently erase the given rectangle on a single page (white fill)."""
        if self._doc is None:
            raise ValueError("No document is open")
        page = self._doc[page_idx]
        page.add_redact_annot(rect, fill=(1, 1, 1))
        page.apply_redactions()
        self._is_modified = True

    def __del__(self):
        """Best-effort cleanup on garbage collection.

        Explicit ``close()`` (on window close) is the real cleanup path; this is
        only a backstop and must never raise — during interpreter shutdown the
        ``fitz`` module may already be partially torn down.
        """
        try:
            self.close()
        except Exception:
            pass
