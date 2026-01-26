from pathlib import Path
from .base import DocumentParser, ParseResult

# Try to import Pillow for image metadata
try:
    from PIL import Image
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
    """Parser for image files"""

    supported_extensions = ['png', 'jpg', 'jpeg', 'tiff', 'tif', 'bmp', 'gif']

    def __init__(self, enable_ocr: bool = False):
        """
        Initialize image parser

        Args:
            enable_ocr: Whether to attempt OCR on images (requires pytesseract)
        """
        self.enable_ocr = enable_ocr and HAS_OCR

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
                ocr_text = pytesseract.image_to_string(img)
                if ocr_text and ocr_text.strip():
                    text_parts.append(f"\nExtracted Text (OCR):")
                    text_parts.append(ocr_text.strip())
                    metadata['has_ocr_text'] = True
                    metadata['ocr_text_length'] = len(ocr_text.strip())
            except Exception as e:
                text_parts.append(f"\nOCR failed: {str(e)}")
                metadata['ocr_error'] = str(e)
        else:
            text_parts.append("\n[OCR not enabled. Enable OCR for text extraction from images.]")

        return ParseResult.success_result(
            text="\n".join(text_parts),
            metadata=metadata
        )
