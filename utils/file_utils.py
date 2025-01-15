"""
File system utilities for JustDownloadIt.

This module provides comprehensive file system operations used throughout the application.
It handles file operations, path manipulation, temporary files, and validation.

Functions:
    - File Operations:
        - create_temp_file: Create temporary file
        - cleanup_temp_file: Clean up temporary file
        - move_to_destination: Move file to destination
        - ensure_dir: Ensure directory exists
        - get_free_space: Get free space in directory
        - is_file_complete: Check if file is complete
        - cleanup_partial_downloads: Clean up partial downloads
        - calculate_file_hash: Calculate file hash
        
    - Path Manipulation:
        - sanitize_filename: Remove invalid characters from filename
        - get_unique_filename: Get unique filename
        - get_safe_path: Get safe path that doesn't exist
        - get_download_filename: Extract filename from URL
        
    - File Listing:
        - list_downloads: List downloaded files
"""

import os
import re
import shutil
import logging
import tempfile
import hashlib
from pathlib import Path
from typing import Optional, List, Union
from urllib.parse import unquote, urlparse

def create_temp_file(prefix: str = "download_", suffix: str = "") -> Path:
    """Create a temporary file.
    
    Args:
        prefix: Prefix for temporary file
        suffix: Suffix for temporary file
        
    Returns:
        Path: Path to temporary file
    """
    temp_fd, temp_path = tempfile.mkstemp(prefix=prefix, suffix=suffix)
    os.close(temp_fd)
    return Path(temp_path)

def cleanup_temp_file(temp_path: Path) -> None:
    """Safely cleanup a temporary file.
    
    Args:
        temp_path: Path to temporary file
    """
    try:
        if temp_path.exists():
            temp_path.unlink()
    except Exception as e:
        logging.warning(f"Failed to cleanup temp file {temp_path}: {e}")

def move_to_destination(temp_path: Path, dest_path: Path, 
                       overwrite: bool = False) -> None:
    """Move file to destination.
    
    Args:
        temp_path: Source path
        dest_path: Destination path
        overwrite: Whether to overwrite existing file
        
    Raises:
        FileExistsError: If destination exists and overwrite is False
        OSError: If move fails
    """
    if dest_path.exists() and not overwrite:
        raise FileExistsError(f"Destination file already exists: {dest_path}")
    
    try:
        shutil.move(str(temp_path), str(dest_path))
    except Exception as e:
        raise OSError(f"Failed to move file to destination: {e}")

def ensure_dir(path: Path) -> None:
    """Ensure directory exists, create if necessary.
    
    Args:
        path: Directory path
    """
    path.mkdir(parents=True, exist_ok=True)

def get_free_space(path: Path) -> int:
    """Get free space in bytes for given path.
    
    Args:
        path: Path to check
        
    Returns:
        int: Free space in bytes
    """
    if not path.exists():
        path.mkdir(parents=True, exist_ok=True)
    return shutil.disk_usage(str(path)).free

def is_file_complete(file_path: Path, expected_size: Optional[int] = None) -> bool:
    """Check if file is complete based on size.
    
    Args:
        file_path: Path to file
        expected_size: Expected file size in bytes
        
    Returns:
        bool: True if file is complete
    """
    if not file_path.exists():
        return False
        
    if expected_size is None:
        return True
        
    return file_path.stat().st_size == expected_size

def cleanup_partial_downloads(directory: Path, pattern: str = "*.partial") -> None:
    """Clean up partial download files.
    
    Args:
        directory: Directory to clean
        pattern: File pattern to match
    """
    try:
        for partial_file in directory.glob(pattern):
            try:
                partial_file.unlink()
            except Exception as e:
                logging.warning(f"Failed to delete partial file {partial_file}: {e}")
    except Exception as e:
        logging.error(f"Failed to cleanup partial downloads: {e}")

def calculate_file_hash(file_path: Path, hash_type: str = "sha256") -> str:
    """Calculate file hash.
    
    Args:
        file_path: Path to file
        hash_type: Hash algorithm to use
        
    Returns:
        str: File hash
        
    Raises:
        ValueError: If hash type is invalid
        FileNotFoundError: If file doesn't exist
    """
    if not hasattr(hashlib, hash_type):
        raise ValueError(f"Invalid hash type: {hash_type}")
        
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    hash_obj = getattr(hashlib, hash_type)()
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_obj.update(chunk)
            
    return hash_obj.hexdigest()

def sanitize_filename(filename: str) -> str:
    """Remove invalid characters from filename.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    # Limit length
    filename = filename[:255]  # Max filename length on most filesystems
    return filename.strip()

def get_unique_filename(directory: Path, filename: str) -> Path:
    """Get unique filename in directory.
    
    Args:
        directory: Target directory
        filename: Desired filename
        
    Returns:
        Path: Path with unique filename
    """
    filepath = directory / filename
    if not filepath.exists():
        return filepath
        
    name = filepath.stem
    extension = filepath.suffix
    counter = 1
    
    while True:
        new_name = f"{name} ({counter}){extension}"
        new_path = directory / new_name
        if not new_path.exists():
            return new_path
        counter += 1

def get_safe_path(directory: Path, filename: str) -> Path:
    """Get safe path that doesn't exist.
    
    Args:
        directory: Target directory
        filename: Desired filename
        
    Returns:
        Path: Safe path
    """
    safe_name = sanitize_filename(filename)
    return get_unique_filename(directory, safe_name)

def get_download_filename(url: str, content_disposition: Optional[str] = None,
                         default: str = "download") -> str:
    """Extract filename from URL or content disposition.
    
    Args:
        url: Download URL
        content_disposition: Content-Disposition header value
        default: Default filename if none found
        
    Returns:
        str: Filename
    """
    filename = None
    
    # Try content disposition first
    if content_disposition:
        matches = re.findall("filename=(.+)", content_disposition)
        if matches:
            filename = matches[0].strip('"')
    
    # Try URL path
    if not filename:
        path = urlparse(url).path
        if path and '/' in path:
            filename = path.split('/')[-1]
            filename = unquote(filename)
    
    # Use default if nothing found
    if not filename:
        filename = default
    
    return sanitize_filename(filename)

def list_downloads(directory: Path, pattern: str = "*") -> List[Path]:
    """List downloaded files.
    
    Args:
        directory: Directory to search
        pattern: File pattern to match
        
    Returns:
        List[Path]: List of matching files
    """
    if not directory.exists():
        return []
        
    return sorted(directory.glob(pattern))
