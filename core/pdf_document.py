"""
Ultra PDF Editor - PDF Document Model
Handles PDF loading, manipulation, and saving using PyMuPDF (fitz)
"""
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any, Union, Sequence
from dataclasses import dataclass
from enum import Enum
import os


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
        self._temp_files: List[str] = []

    @property
    def is_open(self) -> bool:
        """Check if a document is currently open"""
        return self._doc is not None

    @property
    def filepath(self) -> Optional[Path]:
        """Get the current file path"""
        return self._filepath

    @property
    def is_modified(self) -> bool:
        """Check if document has unsaved changes"""
        return self._is_modified

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

        # Clean up temp files
        for temp_file in self._temp_files:
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except OSError:
                pass
        self._temp_files.clear()

    def save(self, filepath: Optional[Union[str, Path]] = None,
             encryption: Optional[Dict[str, Any]] = None,
             garbage: int = 4,
             deflate: bool = True,
             deflate_images: bool = True,
             deflate_fonts: bool = True) -> bool:
        """
        Save the PDF document

        Args:
            filepath: Optional new filepath (Save As)
            encryption: Optional encryption settings
            garbage: Garbage collection level (0-4)
            deflate: Compress streams
            deflate_images: Compress images
            deflate_fonts: Compress fonts

        Returns:
            True if successful
        """
        if self._doc is None:
            raise ValueError("No document is open")

        save_path = Path(filepath) if filepath else self._filepath
        if not save_path:
            raise ValueError("No filepath specified")

        try:
            # Prepare save options
            save_options = {
                "garbage": garbage,
                "deflate": deflate,
                "deflate_images": deflate_images,
                "deflate_fonts": deflate_fonts,
            }

            # Handle encryption
            if encryption:
                # PDF_ENCRYPT_AES_256 = 4
                save_options["encryption"] = encryption.get("method", 4)
                if "user_password" in encryption:
                    save_options["user_pw"] = encryption["user_password"]
                if "owner_password" in encryption:
                    save_options["owner_pw"] = encryption["owner_password"]
                if "permissions" in encryption:
                    save_options["permissions"] = encryption["permissions"]

            # If saving to same file, use incremental save or temp file
            if save_path == self._filepath:
                # PDF_ENCRYPT_KEEP = 1
                self._doc.save(str(save_path), incremental=True, encryption=1)
            else:
                self._doc.save(str(save_path), **save_options)

            self._filepath = save_path
            self._is_modified = False
            return True

        except Exception:
            raise

    def save_copy(self, filepath: Union[str, Path]) -> bool:
        """Save a copy without changing the current document path"""
        if self._doc is None:
            raise ValueError("No document is open")

        try:
            self._doc.save(str(filepath), garbage=4, deflate=True)
            return True
        except Exception:
            raise

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
            pass
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

        if to_index < 0:
            to_index = self.page_count

        self._doc.copy_page(page_num, to_index)
        self._is_modified = True
        return to_index

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

    def merge_pdfs(self, pdf_paths: Sequence[Union[str, Path]], output_path: Union[str, Path]) -> bool:
        """Merge multiple PDFs into a new file"""
        merged_doc = fitz.open()

        for pdf_path in pdf_paths:
            pdf = fitz.open(str(pdf_path))
            merged_doc.insert_pdf(pdf)
            pdf.close()

        merged_doc.save(str(output_path))
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
        flags = 0 if case_sensitive else fitz.TEXT_PRESERVE_WHITESPACE

        for page_num in range(self.page_count):
            page = self.get_page(page_num)
            rects = page.search_for(text, flags=flags)
            if rects:
                results.append({
                    "page": page_num,
                    "rects": [(r.x0, r.y0, r.x1, r.y1) for r in rects]
                })

        return results

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
                      color: Tuple[float, float, float] = (1, 1, 0)) -> fitz.Annot:
        """Add a highlight annotation"""
        page = self.get_page(page_num)
        annot = page.add_highlight_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
        annot.update()
        self._is_modified = True
        return annot

    def add_underline(self, page_num: int, rect: Tuple[float, float, float, float],
                      color: Tuple[float, float, float] = (0, 0, 1)) -> fitz.Annot:
        """Add an underline annotation"""
        page = self.get_page(page_num)
        annot = page.add_underline_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
        annot.update()
        self._is_modified = True
        return annot

    def add_strikethrough(self, page_num: int, rect: Tuple[float, float, float, float],
                          color: Tuple[float, float, float] = (1, 0, 0)) -> fitz.Annot:
        """Add a strikethrough annotation"""
        page = self.get_page(page_num)
        annot = page.add_strikeout_annot(fitz.Rect(rect))
        annot.set_colors(stroke=color)
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
                            width: float = 1) -> fitz.Annot:
        """Add a rectangle annotation"""
        page = self.get_page(page_num)
        annot = page.add_rect_annot(fitz.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=int(width))
        annot.update()
        self._is_modified = True
        return annot

    def add_circle_annotation(self, page_num: int, rect: Tuple[float, float, float, float],
                              stroke_color: Tuple[float, float, float] = (1, 0, 0),
                              fill_color: Optional[Tuple[float, float, float]] = None,
                              width: float = 1) -> fitz.Annot:
        """Add a circle/ellipse annotation"""
        page = self.get_page(page_num)
        annot = page.add_circle_annot(fitz.Rect(rect))
        annot.set_colors(stroke=stroke_color, fill=fill_color)
        annot.set_border(width=int(width))
        annot.update()
        self._is_modified = True
        return annot

    def add_line_annotation(self, page_num: int,
                            start: Tuple[float, float], end: Tuple[float, float],
                            color: Tuple[float, float, float] = (1, 0, 0),
                            width: float = 1) -> fitz.Annot:
        """Add a line annotation"""
        page = self.get_page(page_num)
        annot = page.add_line_annot(fitz.Point(start), fitz.Point(end))
        annot.set_colors(stroke=color)
        annot.set_border(width=int(width))
        annot.update()
        self._is_modified = True
        return annot

    def add_ink_annotation(self, page_num: int,
                           points: List[List[Tuple[float, float]]],
                           color: Tuple[float, float, float] = (0, 0, 0),
                           width: float = 2) -> fitz.Annot:
        """Add a freehand drawing (ink) annotation"""
        page = self.get_page(page_num)
        # PyMuPDF expects list of lists of point sequences
        # Each point can be a tuple (x, y) or fitz.Point
        annot = page.add_ink_annot(points)
        annot.set_colors(stroke=color)
        annot.set_border(width=int(width))
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
                permissions: int = 2048) -> bool:  # 2048 = PDF_PERM_ACCESSIBILITY
        """
        Encrypt the document

        Args:
            user_password: Password to open the document
            owner_password: Password for full permissions
            permissions: Permission flags
        """
        if self._doc is None:
            raise ValueError("No document is open")

        # Permissions can be combined:
        # fitz.PDF_PERM_PRINT - printing
        # fitz.PDF_PERM_MODIFY - modifying
        # fitz.PDF_PERM_COPY - copying
        # fitz.PDF_PERM_ANNOTATE - annotating
        # fitz.PDF_PERM_FORM - filling forms
        # fitz.PDF_PERM_ACCESSIBILITY - accessibility
        # fitz.PDF_PERM_ASSEMBLE - assembling
        # fitz.PDF_PERM_PRINT_HQ - high quality printing

        self._password = user_password
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
        return self.save(
            output_path,
            garbage=garbage,
            deflate=deflate,
            deflate_images=deflate_images,
            deflate_fonts=deflate_fonts
        )

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
