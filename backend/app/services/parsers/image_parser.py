import logging
from pathlib import Path
from .base import DocumentParser, ParseResult

logger = logging.getLogger(__name__)

# Try to import Pillow for image metadata
try:
    from PIL import Image, ImageEnhance, ImageFilter
    from PIL.ExifTags import TAGS
    HAS_PILLOW = True
except ImportError:
    HAS_PILLOW = False

# Try to import pytesseract for OCR (optional)
try:
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False


class ImageParser(DocumentParser):
    """Parser for image files with OCR support"""

    supported_extensions = ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif']

    def __init__(self, enable_ocr: bool = True):  # OCR enabled by default now
        """
        Initialize image parser

        Args:
            enable_ocr: Whether to attempt OCR on images (requires pytesseract)
        """
        self.enable_ocr = enable_ocr and HAS_OCR
        if enable_ocr and not HAS_OCR:
            logger.warning("OCR requested but pytesseract not installed. Install with: pip install pytesseract")

    def parse(self, file_path: str) -> ParseResult:
        """Parse image file from path"""
        if not HAS_PILLOW:
            return ParseResult.success_result(
                text=f"[Image: {Path(file_path).name}. Install 'Pillow' for metadata extraction.]",
                metadata={'file_type': Path(file_path).suffix.lower().lstrip('.')}
            )

        try:
            with Image.open(file_path) as img:
                return self._extract_image_content(img, file_path)
        except Exception as e:
            return ParseResult.error_result(f"Failed to parse image: {str(e)}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse image from bytes"""
        if not HAS_PILLOW:
            return ParseResult.success_result(
                text=f"[Image: {filename}. Install 'Pillow' for metadata extraction.]",
                metadata={'file_type': Path(filename).suffix.lower().lstrip('.')}
            )

        try:
            import io
            with Image.open(io.BytesIO(content)) as img:
                return self._extract_image_content(img, filename)
        except Exception as e:
            return ParseResult.error_result(f"Failed to parse image: {str(e)}")

    def _extract_image_content(self, img: 'Image.Image', filename: str) -> ParseResult:
        """Extract content from PIL Image"""
        text_parts = [f"[Image: {Path(filename).name}]"]
        metadata = {
            'file_type': Path(filename).suffix.lower().lstrip('.'),
            'width': img.width,
            'height': img.height,
            'format': img.format,
            'mode': img.mode,
        }

        # Add dimensions to text
        text_parts.append(f"Dimensions: {img.width} x {img.height} pixels")
        text_parts.append(f"Format: {img.format}, Mode: {img.mode}")

        # Extract EXIF data if available
        exif_data = {}
        try:
            exif = img._getexif()
            if exif:
                for tag_id, value in exif.items():
                    tag = TAGS.get(tag_id, tag_id)
                    if isinstance(value, (str, int, float)):
                        exif_data[tag] = value
                if exif_data:
                    metadata['exif'] = exif_data
                    text_parts.append(f"\nEXIF Metadata:")
                    for key, value in list(exif_data.items())[:10]:
                        text_parts.append(f"  {key}: {value}")
        except:
            pass

        # Attempt OCR if enabled
        if self.enable_ocr:
            try:
                # Preprocess image for better OCR results
                processed_img = self._preprocess_for_ocr(img)
                
                # Run OCR with optimized settings
                ocr_config = '--oem 3 --psm 6'  # LSTM engine, assume uniform block of text
                ocr_text = pytesseract.image_to_string(processed_img, config=ocr_config)
                
                if ocr_text and ocr_text.strip():
                    # Clean up OCR text
                    cleaned_text = self._clean_ocr_text(ocr_text)
                    if cleaned_text:
                        text_parts.append(f"\nExtracted Text (OCR):")
                        text_parts.append(cleaned_text)
                        metadata['has_ocr_text'] = True
                        metadata['ocr_text_length'] = len(cleaned_text)
                else:
                    metadata['has_ocr_text'] = False
            except Exception as e:
                logger.warning(f"OCR failed for {filename}: {str(e)}")
                text_parts.append(f"\n[OCR processing failed: {str(e)}]")
                metadata['ocr_error'] = str(e)
        else:
            if HAS_OCR:
                text_parts.append("\n[OCR available but not enabled for this parse.]")
            else:
                text_parts.append("\n[OCR not available. Install pytesseract for text extraction from images.]")

        return ParseResult.success_result(
            text="\n".join(text_parts),
            metadata=metadata
        )
    
    def _preprocess_for_ocr(self, img: 'Image.Image') -> 'Image.Image':
        """
        Preprocess image for better OCR accuracy.
        
        - Convert to grayscale
        - Enhance contrast
        - Apply slight sharpening
        - Resize if too small
        """
        # Convert to RGB if necessary (handles RGBA, P mode, etc.)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Convert to grayscale
        if img.mode != 'L':
            img = img.convert('L')
        
        # Resize if image is too small (OCR works better with larger images)
        min_dimension = 1000
        if img.width < min_dimension or img.height < min_dimension:
            scale = max(min_dimension / img.width, min_dimension / img.height)
            if scale > 1:
                new_size = (int(img.width * scale), int(img.height * scale))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
        
        # Enhance contrast
        enhancer = ImageEnhance.Contrast(img)
        img = enhancer.enhance(1.5)
        
        # Sharpen slightly
        img = img.filter(ImageFilter.SHARPEN)
        
        return img
    
    def _clean_ocr_text(self, text: str) -> str:
        """Clean up OCR output text."""
        import re
        
        # Remove excessive whitespace
        text = re.sub(r'\n{3,}', '\n\n', text)
        text = re.sub(r' {2,}', ' ', text)
        
        # Remove lines that are mostly special characters (OCR artifacts)
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            # Count alphanumeric vs special chars
            alnum_count = sum(1 for c in line if c.isalnum())
            total_count = len(line.strip())
            if total_count == 0:
                cleaned_lines.append(line)
            elif alnum_count / total_count > 0.3:  # At least 30% alphanumeric
                cleaned_lines.append(line)
        
        return '\n'.join(cleaned_lines).strip()
