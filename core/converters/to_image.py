"""
Ultra PDF Editor - PDF to Image Converter
Convert PDF pages to various image formats
"""
from pathlib import Path
from typing import List, Optional, Tuple, Union
from enum import Enum
import fitz
from PIL import Image
import io


class ImageFormat(Enum):
    """Supported output image formats"""
    PNG = "png"
    JPEG = "jpeg"
    TIFF = "tiff"
    BMP = "bmp"
    GIF = "gif"
    WEBP = "webp"


class PDFToImageConverter:
    """Converts PDF pages to images"""

    def __init__(self, pdf_path: Optional[Union[str, Path]] = None, document: Optional[fitz.Document] = None):
        """
        Initialize converter with either a file path or an open document

        Args:
            pdf_path: Path to PDF file
            document: Open fitz.Document
        """
        self._doc: Optional[fitz.Document] = None
        self._owns_doc = False

        if document:
            self._doc = document
        elif pdf_path:
            self._doc = fitz.open(str(pdf_path))
            self._owns_doc = True

    def __del__(self):
        if self._owns_doc and self._doc:
            self._doc.close()

    def set_document(self, document: fitz.Document):
        """Set the document to convert"""
        if self._owns_doc and self._doc:
            self._doc.close()
        self._doc = document
        self._owns_doc = False

    def convert_page(
        self,
        page_num: int,
        dpi: int = 150,
        format: ImageFormat = ImageFormat.PNG,
        alpha: bool = False,
        colorspace: str = "rgb"
    ) -> bytes:
        """
        Convert a single page to image bytes

        Args:
            page_num: Page number (0-indexed)
            dpi: Output resolution
            format: Output image format
            alpha: Include alpha channel
            colorspace: "rgb", "gray", or "cmyk"

        Returns:
            Image data as bytes
        """
        if not self._doc:
            raise ValueError("No document loaded")

        page = self._doc[page_num]
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        # Get colorspace
        cs = {
            "rgb": fitz.csRGB,
            "gray": fitz.csGRAY,
            "cmyk": fitz.csCMYK,
        }.get(colorspace.lower(), fitz.csRGB)

        # Render page
        pixmap = page.get_pixmap(matrix=matrix, alpha=alpha, colorspace=cs)

        # Convert to PIL Image for format conversion
        if format == ImageFormat.PNG:
            return pixmap.tobytes("png")
        elif format == ImageFormat.JPEG:
            # Convert to PIL for JPEG (no alpha support)
            img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=95)
            return buffer.getvalue()
        else:
            # Use PIL for other formats
            mode = "RGBA" if alpha else "RGB"
            img = Image.frombytes(mode, (pixmap.width, pixmap.height), pixmap.samples)
            buffer = io.BytesIO()
            img.save(buffer, format=format.value.upper())
            return buffer.getvalue()

    def convert_page_to_file(
        self,
        page_num: int,
        output_path: Union[str, Path],
        dpi: int = 150,
        format: Optional[ImageFormat] = None,
        alpha: bool = False
    ) -> Path:
        """
        Convert a single page and save to file

        Args:
            page_num: Page number (0-indexed)
            output_path: Output file path
            dpi: Output resolution
            format: Output format (inferred from extension if None)
            alpha: Include alpha channel

        Returns:
            Path to output file
        """
        output_path = Path(output_path)

        # Infer format from extension if not specified
        if format is None:
            ext = output_path.suffix.lower().lstrip('.')
            format = {
                'png': ImageFormat.PNG,
                'jpg': ImageFormat.JPEG,
                'jpeg': ImageFormat.JPEG,
                'tiff': ImageFormat.TIFF,
                'tif': ImageFormat.TIFF,
                'bmp': ImageFormat.BMP,
                'gif': ImageFormat.GIF,
                'webp': ImageFormat.WEBP,
            }.get(ext, ImageFormat.PNG)

        image_data = self.convert_page(page_num, dpi, format, alpha)

        with open(output_path, 'wb') as f:
            f.write(image_data)

        return output_path

    def convert_all_pages(
        self,
        output_dir: Union[str, Path],
        prefix: str = "page",
        dpi: int = 150,
        format: ImageFormat = ImageFormat.PNG,
        alpha: bool = False,
        pages: Optional[List[int]] = None,
        callback=None
    ) -> List[Path]:
        """
        Convert multiple pages to images

        Args:
            output_dir: Output directory
            prefix: Filename prefix
            dpi: Output resolution
            format: Output format
            alpha: Include alpha channel
            pages: List of page numbers (None = all pages)
            callback: Progress callback function(current, total, filename)

        Returns:
            List of output file paths
        """
        if not self._doc:
            raise ValueError("No document loaded")

        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        if pages is None:
            pages = list(range(len(self._doc)))

        output_files = []
        total = len(pages)

        for i, page_num in enumerate(pages):
            ext = format.value
            filename = f"{prefix}_{page_num + 1:04d}.{ext}"
            output_path = output_dir / filename

            self.convert_page_to_file(page_num, output_path, dpi, format, alpha)
            output_files.append(output_path)

            if callback:
                callback(i + 1, total, filename)

        return output_files

    def convert_to_multipage_tiff(
        self,
        output_path: Union[str, Path],
        dpi: int = 150,
        pages: Optional[List[int]] = None,
        compression: str = "tiff_lzw"
    ) -> Path:
        """
        Convert pages to a multipage TIFF file

        Args:
            output_path: Output file path
            dpi: Output resolution
            pages: List of page numbers (None = all pages)
            compression: TIFF compression method

        Returns:
            Path to output file
        """
        if not self._doc:
            raise ValueError("No document loaded")

        output_path = Path(output_path)

        if pages is None:
            pages = list(range(len(self._doc)))

        images = []
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)

        for page_num in pages:
            page = self._doc[page_num]
            pixmap = page.get_pixmap(matrix=matrix)
            img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
            images.append(img)

        # Save as multipage TIFF
        if images:
            images[0].save(
                output_path,
                format="TIFF",
                save_all=True,
                append_images=images[1:],
                compression=compression,
                dpi=(dpi, dpi)
            )

        return output_path

    def get_page_dimensions(self, page_num: int, dpi: int = 72) -> Tuple[int, int]:
        """
        Get page dimensions at specified DPI

        Returns:
            (width, height) in pixels
        """
        if not self._doc:
            raise ValueError("No document loaded")

        page = self._doc[page_num]
        zoom = dpi / 72.0
        return (
            int(page.rect.width * zoom),
            int(page.rect.height * zoom)
        )

    @property
    def page_count(self) -> int:
        """Get number of pages"""
        return len(self._doc) if self._doc else 0


def convert_pdf_to_images(
    pdf_path: Union[str, Path],
    output_dir: Union[str, Path],
    dpi: int = 150,
    format: str = "png"
) -> List[Path]:
    """
    Convenience function to convert PDF to images

    Args:
        pdf_path: Input PDF path
        output_dir: Output directory
        dpi: Output resolution
        format: Output format (png, jpeg, tiff, etc.)

    Returns:
        List of output file paths
    """
    converter = PDFToImageConverter(pdf_path)
    image_format = ImageFormat(format.lower())
    return converter.convert_all_pages(output_dir, dpi=dpi, format=image_format)
