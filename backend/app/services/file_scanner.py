import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass


@dataclass
class ScannedFile:
    """Represents a file discovered during folder scanning"""
    file_path: str
    filename: str
    file_type: str
    file_size: int
    modified_date: datetime


# Supported file extensions by category
FILE_TYPE_CATEGORIES = {
    # Documents (text-extractable)
    'pdf': 'document',
    'docx': 'document',
    'doc': 'document',
    'txt': 'document',
    'md': 'document',
    'rtf': 'document',

    # CAD/Drawings
    'dwg': 'drawing',
    'dxf': 'drawing',

    # BIM
    'rvt': 'bim',
    'rfa': 'bim',
    'ifc': 'bim',

    # Images
    'png': 'image',
    'jpg': 'image',
    'jpeg': 'image',
    'tiff': 'image',
    'tif': 'image',
    'bmp': 'image',
    'gif': 'image',

    # Spreadsheets
    'xlsx': 'spreadsheet',
    'xls': 'spreadsheet',
    'csv': 'spreadsheet',
}

# All supported extensions
SUPPORTED_EXTENSIONS = set(FILE_TYPE_CATEGORIES.keys())


class FileScanner:
    """Scans folders and discovers files"""

    def __init__(self, supported_extensions: Optional[set] = None):
        self.supported_extensions = supported_extensions or SUPPORTED_EXTENSIONS

    def scan_folder(
        self,
        folder_path: str,
        recursive: bool = True
    ) -> list[ScannedFile]:
        """
        Scan a folder and return all supported files

        Args:
            folder_path: Path to the folder to scan
            recursive: Whether to scan subdirectories

        Returns:
            List of ScannedFile objects
        """
        folder = Path(folder_path)

        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")

        if not folder.is_dir():
            raise ValueError(f"Path is not a directory: {folder_path}")

        files = []

        if recursive:
            pattern = "**/*"
        else:
            pattern = "*"

        for file_path in folder.glob(pattern):
            if file_path.is_file():
                scanned = self._scan_file(file_path)
                if scanned:
                    files.append(scanned)

        return files

    def _scan_file(self, file_path: Path) -> Optional[ScannedFile]:
        """
        Scan a single file and extract metadata

        Args:
            file_path: Path object for the file

        Returns:
            ScannedFile object or None if not supported
        """
        # Get file extension (lowercase, without dot)
        extension = file_path.suffix.lower().lstrip('.')

        if extension not in self.supported_extensions:
            return None

        try:
            stat = file_path.stat()
            return ScannedFile(
                file_path=str(file_path.absolute()),
                filename=file_path.name,
                file_type=extension,
                file_size=stat.st_size,
                modified_date=datetime.fromtimestamp(stat.st_mtime)
            )
        except (OSError, PermissionError) as e:
            print(f"Error scanning file {file_path}: {e}")
            return None

    def classify_content_type(
        self,
        file_path: str,
        folder_type: str  # 'rfi' or 'specs'
    ) -> str:
        """
        Classify what type of content a file represents

        Args:
            file_path: Path to the file
            folder_type: Whether file is from 'rfi' or 'specs' folder

        Returns:
            Content type: 'rfi', 'specification', 'drawing', 'image', 'other'
        """
        extension = Path(file_path).suffix.lower().lstrip('.')
        category = FILE_TYPE_CATEGORIES.get(extension, 'other')

        # Files in RFI folder are RFIs (documents)
        if folder_type == 'rfi':
            if category == 'document':
                return 'rfi'
            elif category in ('drawing', 'image'):
                return 'drawing'  # Supporting drawings for RFI
            else:
                return 'other'

        # Files in specs folder
        if folder_type == 'specs':
            if category == 'document':
                return 'specification'
            elif category == 'drawing':
                return 'drawing'
            elif category == 'image':
                return 'image'
            elif category == 'bim':
                return 'drawing'
            else:
                return 'other'

        return 'other'

    def get_file_category(self, file_type: str) -> str:
        """Get the category for a file type"""
        return FILE_TYPE_CATEGORIES.get(file_type.lower(), 'other')
