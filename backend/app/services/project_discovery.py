"""
Project discovery service for auto-detecting projects from shared folders.

Scans configured shared folder roots and identifies potential project structures
based on common naming patterns and folder organization.
"""

import os
import re
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ProjectCandidate:
    """A potential project discovered from folder structure."""
    name: str
    root_path: str
    rfi_folder: Optional[str] = None
    specs_folder: Optional[str] = None
    confidence: float = 0.0
    file_count: int = 0
    rfi_count: int = 0
    spec_count: int = 0
    reasons: list[str] = field(default_factory=list)


# Common patterns for project folders
PROJECT_PATTERNS = [
    # Project code patterns (e.g., "2024_ProjectName", "24001_ClientName")
    r"^\d{4,6}[_\-\s]",
    # Year prefixes (e.g., "2024 Project Name")
    r"^20\d{2}[\s_\-]",
    # Project number patterns (e.g., "P2024-001")
    r"^P?\d{4,6}",
]

# Folders that likely contain RFIs
RFI_FOLDER_NAMES = [
    "rfi", "rfis", "rfi's", "request for information",
    "submittals", "submittal", "submissions",
    "rfi-submittals", "rfis-submittals",
    "correspondence", "contractor correspondence",
]

# Folders that likely contain specifications
SPEC_FOLDER_NAMES = [
    "specs", "specifications", "spec",
    "documents", "docs", "contract documents",
    "drawings", "dwg", "cad",
    "bid docs", "bid documents", "construction documents", "cd",
]


def discover_projects(
    root_paths: list[str],
    max_depth: int = 3,
    min_confidence: float = 0.3,
) -> list[ProjectCandidate]:
    """
    Discover potential projects from shared folder roots.
    
    Args:
        root_paths: List of root folder paths to scan
        max_depth: Maximum folder depth to search
        min_confidence: Minimum confidence score to include
        
    Returns:
        List of ProjectCandidate objects sorted by confidence
    """
    candidates = []
    
    for root_path in root_paths:
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            logger.warning(f"Root path does not exist or is not a directory: {root_path}")
            continue
            
        # Scan the root directory for potential projects
        candidates.extend(_scan_for_projects(root, max_depth=max_depth))
    
    # Filter by minimum confidence and sort
    candidates = [c for c in candidates if c.confidence >= min_confidence]
    candidates.sort(key=lambda c: c.confidence, reverse=True)
    
    return candidates


def _scan_for_projects(root: Path, max_depth: int = 3, current_depth: int = 0) -> list[ProjectCandidate]:
    """Recursively scan for project folders."""
    candidates = []
    
    if current_depth > max_depth:
        return candidates
        
    try:
        for item in root.iterdir():
            if not item.is_dir():
                continue
                
            # Skip hidden folders and common non-project folders
            if item.name.startswith('.') or item.name.lower() in [
                'archive', 'archives', 'backup', 'backups', 'old', 
                'temp', 'tmp', 'trash', 'deleted', 'templates',
                '$recycle.bin', 'system volume information',
            ]:
                continue
            
            # Check if this folder looks like a project
            candidate = _evaluate_project_folder(item)
            
            if candidate and candidate.confidence > 0:
                candidates.append(candidate)
            elif current_depth < max_depth:
                # Recurse into subfolders
                candidates.extend(_scan_for_projects(item, max_depth, current_depth + 1))
                
    except PermissionError:
        logger.debug(f"Permission denied accessing: {root}")
    except Exception as e:
        logger.warning(f"Error scanning {root}: {e}")
        
    return candidates


def _evaluate_project_folder(folder: Path) -> Optional[ProjectCandidate]:
    """
    Evaluate if a folder is likely a project folder.
    
    Returns ProjectCandidate if it looks like a project, None otherwise.
    """
    name = folder.name
    confidence = 0.0
    reasons = []
    
    # Check for project naming patterns
    for pattern in PROJECT_PATTERNS:
        if re.match(pattern, name, re.IGNORECASE):
            confidence += 0.3
            reasons.append(f"Matches project pattern: {pattern}")
            break
    
    # Check for common architectural project keywords
    name_lower = name.lower()
    project_keywords = ['project', 'renovation', 'construction', 'building', 'tower', 'residence', 'office', 'retail', 'mixed', 'development']
    for keyword in project_keywords:
        if keyword in name_lower:
            confidence += 0.1
            reasons.append(f"Contains keyword: {keyword}")
            break
    
    # Look for RFI and Specs subfolders
    rfi_folder = None
    specs_folder = None
    
    try:
        subfolders = list(folder.iterdir())
        subfolder_names = [f.name.lower() for f in subfolders if f.is_dir()]
        
        # Check for RFI folder
        for rfi_name in RFI_FOLDER_NAMES:
            for subfolder in subfolders:
                if subfolder.is_dir() and rfi_name in subfolder.name.lower():
                    rfi_folder = str(subfolder)
                    confidence += 0.3
                    reasons.append(f"Found RFI folder: {subfolder.name}")
                    break
            if rfi_folder:
                break
        
        # Check for Specs folder
        for spec_name in SPEC_FOLDER_NAMES:
            for subfolder in subfolders:
                if subfolder.is_dir() and spec_name in subfolder.name.lower():
                    specs_folder = str(subfolder)
                    confidence += 0.3
                    reasons.append(f"Found specs folder: {subfolder.name}")
                    break
            if specs_folder:
                break
                
    except PermissionError:
        pass
    except Exception as e:
        logger.debug(f"Error scanning subfolders of {folder}: {e}")
    
    # Count relevant files
    rfi_count = 0
    spec_count = 0
    file_count = 0
    
    scan_folder = Path(rfi_folder) if rfi_folder else folder
    try:
        for f in scan_folder.rglob('*'):
            if f.is_file():
                file_count += 1
                fname = f.name.lower()
                if 'rfi' in fname:
                    rfi_count += 1
                elif 'submittal' in fname:
                    rfi_count += 1
                elif f.suffix.lower() in ['.pdf', '.docx']:
                    spec_count += 1
                    
                if file_count >= 100:  # Limit for performance
                    break
    except Exception:
        pass
    
    # Boost confidence based on file counts
    if rfi_count > 0:
        confidence += min(0.2, rfi_count * 0.05)
        reasons.append(f"Found {rfi_count} RFI files")
    
    if confidence > 0:
        return ProjectCandidate(
            name=_clean_project_name(name),
            root_path=str(folder),
            rfi_folder=rfi_folder,
            specs_folder=specs_folder,
            confidence=min(1.0, confidence),
            file_count=file_count,
            rfi_count=rfi_count,
            spec_count=spec_count,
            reasons=reasons,
        )
    
    return None


def _clean_project_name(name: str) -> str:
    """Clean up folder name to make a nicer project name."""
    # Remove leading numbers/codes
    cleaned = re.sub(r'^[\d\-_]+\s*', '', name)
    
    # Replace underscores with spaces
    cleaned = cleaned.replace('_', ' ')
    
    # Title case
    cleaned = cleaned.strip()
    
    if not cleaned:
        return name  # Fall back to original if cleaning removes everything
        
    return cleaned
