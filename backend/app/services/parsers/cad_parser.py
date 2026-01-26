from pathlib import Path
from typing import Optional
from .base import DocumentParser, ParseResult

# Try to import ezdxf for DXF parsing
try:
    import ezdxf
    HAS_EZDXF = True
except ImportError:
    HAS_EZDXF = False


class CADParser(DocumentParser):
    """Parser for CAD files (DWG, DXF)"""

    supported_extensions = ['dwg', 'dxf']

    def parse(self, file_path: str) -> ParseResult:
        """Parse CAD file from path"""
        extension = Path(file_path).suffix.lower().lstrip('.')

        if extension == 'dxf':
            return self._parse_dxf(file_path)
        elif extension == 'dwg':
            return self._parse_dwg(file_path)
        else:
            return ParseResult.error_result(f"Unsupported CAD format: {extension}")

    def parse_bytes(self, content: bytes, filename: str) -> ParseResult:
        """Parse CAD from bytes - limited support"""
        extension = Path(filename).suffix.lower().lstrip('.')

        if extension == 'dxf':
            # For DXF, we can parse from string
            try:
                import io
                if HAS_EZDXF:
                    doc = ezdxf.read(io.StringIO(content.decode('utf-8', errors='ignore')))
                    return self._extract_dxf_content(doc, filename)
            except Exception as e:
                return ParseResult.error_result(f"Failed to parse DXF from bytes: {str(e)}")

        # For DWG, we can only extract metadata from bytes
        return ParseResult.success_result(
            text=f"[CAD file: {filename}. Content extraction requires file path access.]",
            metadata={'file_type': extension, 'format': 'binary'}
        )

    def _parse_dxf(self, file_path: str) -> ParseResult:
        """Parse DXF file"""
        if not HAS_EZDXF:
            return ParseResult.success_result(
                text=f"[DXF file. Install 'ezdxf' for content extraction.]",
                metadata={'file_type': 'dxf', 'parser_available': False}
            )

        try:
            doc = ezdxf.readfile(file_path)
            return self._extract_dxf_content(doc, file_path)
        except Exception as e:
            return ParseResult.error_result(f"Failed to parse DXF: {str(e)}")

    def _extract_dxf_content(self, doc, filename: str) -> ParseResult:
        """Extract content from ezdxf document"""
        text_parts = []
        metadata = {
            'file_type': 'dxf',
            'dxf_version': doc.dxfversion if hasattr(doc, 'dxfversion') else 'unknown',
            'layers': [],
            'blocks': [],
            'text_entities': 0,
            'dimension_count': 0,
        }

        # Extract layers
        for layer in doc.layers:
            metadata['layers'].append(layer.dxf.name)

        # Extract block names
        for block in doc.blocks:
            if not block.name.startswith('*'):  # Skip anonymous blocks
                metadata['blocks'].append(block.name)

        # Extract text content from modelspace
        msp = doc.modelspace()

        for entity in msp:
            entity_type = entity.dxftype()

            # Text entities
            if entity_type in ('TEXT', 'MTEXT'):
                try:
                    if entity_type == 'TEXT':
                        text = entity.dxf.text
                    else:  # MTEXT
                        text = entity.text
                    if text and text.strip():
                        text_parts.append(text.strip())
                        metadata['text_entities'] += 1
                except:
                    pass

            # Dimension text
            elif entity_type == 'DIMENSION':
                metadata['dimension_count'] += 1
                try:
                    if hasattr(entity.dxf, 'text') and entity.dxf.text:
                        text_parts.append(f"[Dimension: {entity.dxf.text}]")
                except:
                    pass

        # Build summary
        summary_parts = [f"[DXF Drawing: {Path(filename).name}]"]
        summary_parts.append(f"Layers ({len(metadata['layers'])}): {', '.join(metadata['layers'][:10])}")
        if len(metadata['layers']) > 10:
            summary_parts[-1] += f"... and {len(metadata['layers']) - 10} more"

        if metadata['blocks']:
            summary_parts.append(f"Blocks ({len(metadata['blocks'])}): {', '.join(metadata['blocks'][:10])}")

        if text_parts:
            summary_parts.append(f"\nText content ({metadata['text_entities']} items):")
            summary_parts.extend(text_parts[:50])  # Limit to first 50 text items
            if len(text_parts) > 50:
                summary_parts.append(f"... and {len(text_parts) - 50} more text items")

        return ParseResult.success_result(
            text="\n".join(summary_parts),
            metadata=metadata
        )

    def _parse_dwg(self, file_path: str) -> ParseResult:
        """Parse DWG file - limited support"""
        # DWG is a proprietary format. Full parsing requires:
        # 1. LibreDWG (open source but complex to install)
        # 2. ODA File Converter (requires license for commercial use)
        # 3. Converting to DXF first

        metadata = {
            'file_type': 'dwg',
            'format': 'proprietary',
            'note': 'DWG is a proprietary format. Consider converting to DXF for full content extraction.',
        }

        # Try to extract basic info from file header
        try:
            with open(file_path, 'rb') as f:
                header = f.read(6)
                # DWG version magic bytes
                version_map = {
                    b'AC1012': 'R13',
                    b'AC1014': 'R14',
                    b'AC1015': '2000',
                    b'AC1018': '2004',
                    b'AC1021': '2007',
                    b'AC1024': '2010',
                    b'AC1027': '2013',
                    b'AC1032': '2018',
                }
                version = version_map.get(header, 'Unknown')
                metadata['dwg_version'] = version
        except:
            pass

        return ParseResult.success_result(
            text=f"[DWG Drawing: {Path(file_path).name}]\nDWG Version: {metadata.get('dwg_version', 'Unknown')}\n\nNote: Full content extraction from DWG requires conversion to DXF format.",
            metadata=metadata
        )
