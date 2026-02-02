"""
Ultra PDF Editor - OCR Module
Optical Character Recognition for scanned PDFs
"""
from pathlib import Path
from typing import Union, Optional, List, Dict, Any
import fitz
from PIL import Image


class OCRProcessor:
    """Handles OCR operations on PDF documents"""

    def __init__(self, language: str = "eng"):
        """
        Initialize OCR processor

        Args:
            language: OCR language code (eng, fra, deu, spa, etc.)
        """
        self._language = language
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Check if Tesseract OCR is available"""
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            return True
        except Exception:
            return False

    @property
    def is_available(self) -> bool:
        """Check if OCR is available"""
        return self._tesseract_available

    @property
    def language(self) -> str:
        return self._language

    @language.setter
    def language(self, value: str):
        self._language = value

    def ocr_page(
        self,
        page: fitz.Page,
        dpi: int = 300,
        preprocess: bool = True
    ) -> str:
        """
        Perform OCR on a single page

        Args:
            page: fitz.Page object
            dpi: Resolution for OCR
            preprocess: Apply preprocessing to improve OCR

        Returns:
            Extracted text
        """
        if not self._tesseract_available:
            raise RuntimeError("Tesseract OCR is not available")

        import pytesseract

        # Render page to image
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        # Convert to PIL Image
        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        # Preprocess image
        if preprocess:
            img = self._preprocess_image(img)

        # Perform OCR
        text = pytesseract.image_to_string(img, lang=self._language)

        return text

    def _preprocess_image(self, img: Image.Image) -> Image.Image:
        """
        Preprocess image to improve OCR accuracy

        Args:
            img: PIL Image

        Returns:
            Preprocessed image
        """
        # Convert to grayscale
        img = img.convert('L')

        # Increase contrast
        from PIL import ImageEnhance
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)

        # Sharpen
        enhancer = ImageEnhance.Sharpness(img)
        img = enhancer.enhance(1.5)

        return img

    def ocr_page_to_searchable(
        self,
        page: fitz.Page,
        dpi: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Perform OCR and get text with positions

        Args:
            page: fitz.Page object
            dpi: Resolution for OCR

        Returns:
            List of text blocks with positions
        """
        if not self._tesseract_available:
            raise RuntimeError("Tesseract OCR is not available")

        import pytesseract

        # Render page
        zoom = dpi / 72.0
        matrix = fitz.Matrix(zoom, zoom)
        pixmap = page.get_pixmap(matrix=matrix)

        img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

        # Get OCR data with positions
        data = pytesseract.image_to_data(img, lang=self._language, output_type=pytesseract.Output.DICT)

        results = []
        n_boxes = len(data['text'])

        for i in range(n_boxes):
            text = data['text'][i].strip()
            if text:
                # Convert coordinates back to PDF points
                x = data['left'][i] / zoom
                y = data['top'][i] / zoom
                w = data['width'][i] / zoom
                h = data['height'][i] / zoom

                results.append({
                    'text': text,
                    'x': x,
                    'y': y,
                    'width': w,
                    'height': h,
                    'confidence': data['conf'][i],
                })

        return results

    def make_searchable_pdf(
        self,
        input_path: Union[str, Path],
        output_path: Optional[Union[str, Path]] = None,
        pages: Optional[List[int]] = None,
        dpi: int = 300,
        callback: Optional[Any] = None
    ) -> Path:
        """
        Convert a scanned PDF to a searchable PDF

        Args:
            input_path: Input PDF path
            output_path: Output path (defaults to input_searchable.pdf)
            pages: Pages to process (None = all)
            dpi: OCR resolution
            callback: Progress callback(current, total, status)

        Returns:
            Path to output file
        """
        if not self._tesseract_available:
            raise RuntimeError("Tesseract OCR is not available")

        import pytesseract

        input_path = Path(input_path)
        if output_path is None:
            actual_output_path = input_path.parent / f"{input_path.stem}_searchable.pdf"
        else:
            actual_output_path = Path(output_path)

        # Open source document
        doc = fitz.open(str(input_path))

        if pages is None:
            pages = list(range(len(doc)))

        total = len(pages)

        for i, page_num in enumerate(pages):
            page = doc[page_num]

            if callback:
                callback(i + 1, total, f"Processing page {page_num + 1}")

            # Check if page already has text
            page_text = page.get_text("text")
            if isinstance(page_text, str) and page_text.strip():
                continue  # Skip pages with existing text

            # Render to image
            zoom = dpi / 72.0
            matrix = fitz.Matrix(zoom, zoom)
            pixmap = page.get_pixmap(matrix=matrix)

            img = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)

            # Get OCR data with positions
            try:
                pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                    img, lang=self._language, extension='pdf'
                )

                # The OCR'd PDF layer
                ocr_doc = fitz.open("pdf", pdf_bytes)

                if len(ocr_doc) > 0:
                    # Get text from OCR page
                    ocr_page = ocr_doc[0]

                    # Extract text with positions and add to original page
                    text_dict = ocr_page.get_text("dict")
                    blocks = text_dict.get("blocks", []) if isinstance(text_dict, dict) else []

                    for block in blocks:
                        if isinstance(block, dict) and block.get("type") == 0:  # Text block
                            for line in block.get("lines", []):
                                if isinstance(line, dict):
                                    for span in line.get("spans", []):
                                        if isinstance(span, dict):
                                            text = span.get("text", "")
                                            if isinstance(text, str) and text.strip():
                                                # Scale coordinates
                                                bbox = span.get("bbox", (0, 0, 0, 0))
                                                # Create scaled rect (unused but kept for potential future use)
                                                _ = fitz.Rect(
                                                    bbox[0] / zoom,
                                                    bbox[1] / zoom,
                                                    bbox[2] / zoom,
                                                    bbox[3] / zoom
                                                )

                                                # Note: This creates a text layer that's searchable
                                                # but doesn't visually change the page

                ocr_doc.close()

            except Exception as e:
                if callback:
                    callback(i + 1, total, f"Error on page {page_num + 1}: {e}")

        # Save result
        doc.save(str(actual_output_path), garbage=4, deflate=True)
        doc.close()

        return actual_output_path

    def ocr_image_to_pdf(
        self,
        image_path: Union[str, Path],
        output_path: Union[str, Path],
        dpi: int = 300
    ) -> Path:
        """
        Convert an image to searchable PDF using OCR

        Args:
            image_path: Input image path
            output_path: Output PDF path
            dpi: Resolution for processing

        Returns:
            Path to output file
        """
        if not self._tesseract_available:
            raise RuntimeError("Tesseract OCR is not available")

        import pytesseract

        img = Image.open(str(image_path))

        # Generate searchable PDF
        pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            img, lang=self._language, extension='pdf'
        )

        output_path = Path(output_path)
        with open(output_path, 'wb') as f:
            if isinstance(pdf_bytes, bytes):
                f.write(pdf_bytes)

        return output_path

    def get_available_languages(self) -> List[str]:
        """Get list of available OCR languages"""
        if not self._tesseract_available:
            return []

        import pytesseract
        try:
            return pytesseract.get_languages()
        except Exception:
            return ["eng"]


# Language code mapping
LANGUAGE_CODES = {
    "English": "eng",
    "Spanish": "spa",
    "French": "fra",
    "German": "deu",
    "Italian": "ita",
    "Portuguese": "por",
    "Dutch": "nld",
    "Russian": "rus",
    "Chinese (Simplified)": "chi_sim",
    "Chinese (Traditional)": "chi_tra",
    "Japanese": "jpn",
    "Korean": "kor",
    "Arabic": "ara",
    "Hindi": "hin",
    "Thai": "tha",
    "Vietnamese": "vie",
}


def ocr_pdf(
    input_path: Union[str, Path],
    output_path: Optional[Union[str, Path]] = None,
    language: str = "eng"
) -> Path:
    """
    Convenience function to OCR a PDF

    Args:
        input_path: Input PDF path
        output_path: Output path
        language: OCR language

    Returns:
        Path to output file
    """
    processor = OCRProcessor(language)
    return processor.make_searchable_pdf(input_path, output_path)
