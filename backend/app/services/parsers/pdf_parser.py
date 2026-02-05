import io
import logging
from typing import Optional
import PyPDF2
import pdfplumber
from .base import DocumentParser, ParseResult

logger = logging.getLogger(__name__)

# Try to import OCR dependencies
try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class PDFParser(DocumentParser):
    """Parser for PDF documents with OCR support for scanned pages"""

    supported_extensions = ['pdf']
    
    def __init__(self, enable_ocr: bool = True):
        """
        Initialize PDF parser.
        
        Args:
            enable_ocr: Whether to attempt OCR on scanned/image-only pages
        """
        self.enable_ocr = enable_ocr and HAS_OCR
        if enable_ocr and not HAS_OCR:
            logger.warning("OCR requested but dependencies not installed. Install with: pip install pytesseract pillow")

    def parse(self, file_path: str) -> ParseResult:
        """Parse PDF file from path"""
        try:
            content = self._read_file(file_path)
            return self.parse_bytes(content, file_path)
        except Exception as e:
            return ParseResult.error_result(f"Failed to read file: {str(e)}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse PDF from bytes"""
        text_parts = []
        metadata = {
            'page_count': 0,
            'has_images': False,
            'has_tables': False,
        }

        # Try PyPDF2 first (faster for simple PDFs)
        try:
            pdf_file = io.BytesIO(content)
            pdf_reader = PyPDF2.PdfReader(pdf_file)
            metadata['page_count'] = len(pdf_reader.pages)

            # Extract document info
            if pdf_reader.metadata:
                if pdf_reader.metadata.title:
                    metadata['title'] = pdf_reader.metadata.title
                if pdf_reader.metadata.author:
                    metadata['author'] = pdf_reader.metadata.author

            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text and text.strip():
                    text_parts.append(f"[Page {page_num + 1}]\n{text}")

                # Check for images
                if '/XObject' in page.get('/Resources', {}):
                    metadata['has_images'] = True

        except Exception as e:
            # PyPDF2 failed, try pdfplumber
            pass

        # If PyPDF2 didn't extract much text, try pdfplumber
        if not text_parts or all(len(t) < 50 for t in text_parts):
            try:
                pdf_file = io.BytesIO(content)
                with pdfplumber.open(pdf_file) as pdf:
                    metadata['page_count'] = len(pdf.pages)
                    text_parts = []

                    for page_num, page in enumerate(pdf.pages):
                        text = page.extract_text()
                        if text and text.strip():
                            text_parts.append(f"[Page {page_num + 1}]\n{text}")

                        # Check for tables
                        tables = page.extract_tables()
                        if tables:
                            metadata['has_tables'] = True
                            for table in tables:
                                table_text = self._format_table(table)
                                if table_text:
                                    text_parts.append(f"[Table on Page {page_num + 1}]\n{table_text}")

                        # Check for images
                        if page.images:
                            metadata['has_images'] = True

            except Exception as e:
                return ParseResult.error_result(f"Failed to parse PDF: {str(e)}")

        if not text_parts:
            # PDF might be image-only (scanned document)
            metadata['is_scanned'] = True
            
            if self.enable_ocr and metadata.get('has_images'):
                # Attempt OCR on scanned PDF
                ocr_text = self._ocr_pdf(content, filename)
                if ocr_text:
                    metadata['ocr_performed'] = True
                    return ParseResult.success_result(
                        text=f"[Scanned PDF - Text extracted via OCR]\n\n{ocr_text}",
                        metadata=metadata
                    )
            
            return ParseResult.success_result(
                text="[This appears to be a scanned/image-only PDF. OCR was not able to extract text.]",
                metadata=metadata
            )
        
        # Check if we got very little text (might be partially scanned)
        total_text_len = sum(len(t) for t in text_parts)
        if total_text_len < 200 and self.enable_ocr and metadata.get('has_images'):
            # Try OCR to supplement
            ocr_text = self._ocr_pdf(content, filename)
            if ocr_text and len(ocr_text) > total_text_len:
                metadata['ocr_performed'] = True
                text_parts.append(f"\n[Additional text extracted via OCR]\n{ocr_text}")

        return ParseResult.success_result(
            text="\n\n".join(text_parts),
            metadata=metadata
        )
    
    def _ocr_pdf(self, content: bytes, filename: str) -> Optional[str]:
        """
        Perform OCR on a PDF by converting pages to images.
        
        Args:
            content: PDF file content as bytes
            filename: Original filename for logging
            
        Returns:
            Extracted text from OCR or None if failed
        """
        if not HAS_OCR:
            return None
            
        try:
            # Try to use pdf2image for high-quality conversion
            try:
                from pdf2image import convert_from_bytes
                
                # Convert PDF pages to images (limit to first 10 pages for performance)
                images = convert_from_bytes(content, dpi=200, first_page=1, last_page=10)
                
                ocr_results = []
                for page_num, img in enumerate(images, 1):
                    # Preprocess for OCR
                    processed = self._preprocess_image_for_ocr(img)
                    
                    # Run OCR
                    text = pytesseract.image_to_string(processed, config='--oem 3 --psm 6')
                    if text and text.strip():
                        ocr_results.append(f"[Page {page_num}]\n{text.strip()}")
                
                if ocr_results:
                    return "\n\n".join(ocr_results)
                    
            except ImportError:
                logger.debug("pdf2image not installed, using pdfplumber for image extraction")
                
                # Fallback: try to extract images from PDF with pdfplumber
                pdf_file = io.BytesIO(content)
                with pdfplumber.open(pdf_file) as pdf:
                    ocr_results = []
                    for page_num, page in enumerate(pdf.pages[:10], 1):  # Limit to 10 pages
                        if page.images:
                            for img_info in page.images[:3]:  # Limit images per page
                                try:
                                    # Extract image from page
                                    img_obj = page.within_bbox(
                                        (img_info['x0'], img_info['top'], 
                                         img_info['x1'], img_info['bottom'])
                                    ).to_image(resolution=200)
                                    
                                    # Convert to PIL Image and run OCR
                                    pil_img = img_obj.original
                                    processed = self._preprocess_image_for_ocr(pil_img)
                                    text = pytesseract.image_to_string(processed, config='--oem 3 --psm 6')
                                    if text and text.strip():
                                        ocr_results.append(f"[Page {page_num} Image]\n{text.strip()}")
                                except Exception as img_err:
                                    logger.debug(f"Failed to OCR image on page {page_num}: {img_err}")
                    
                    if ocr_results:
                        return "\n\n".join(ocr_results)
                        
        except Exception as e:
            logger.warning(f"OCR failed for PDF {filename}: {str(e)}")
            
        return None
    
    def _preprocess_image_for_ocr(self, img: 'Image.Image') -> 'Image.Image':
        """Preprocess image for better OCR results."""
        from PIL import ImageEnhance, ImageFilter
        
        # Convert to grayscale
        if img.mode != 'L':
            if img.mode not in ('RGB', 'L'):
                img = img.convert('RGB')
            img = img.convert('L')
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # Sharpen
        img = img.filter(ImageFilter.SHARPEN)
        
        return img

    def _format_table(self, table: list) -> Optional[str]:
        """Format extracted table as text"""
        if not table:
            return None

        rows = []
        for row in table:
            if row:
                cells = [str(cell) if cell else '' for cell in row]
                rows.append(' | '.join(cells))

        return '\n'.join(rows) if rows else None
