"""
Download utilities for both regular and YouTube downloads.

This module provides common utilities used by both regular and YouTube downloaders,
including retry logic, stream handling, and download validation.
"""

import os
import time
import logging
import tempfile
from pathlib import Path
from typing import Optional, Callable, Any
import shutil

from .errors import DownloaderError, NetworkError
from .progress import ProgressStats, ProgressTracker

def create_temp_download(prefix: str = "download_") -> Path:
    """Create a temporary download file.
    
    Args:
        prefix: Prefix for temporary file
        
    Returns:
        Path: Path to temporary file
    """
    temp_fd, temp_path = tempfile.mkstemp(prefix=prefix)
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
    """Move downloaded file to destination.
    
    Args:
        temp_path: Path to temporary file
        dest_path: Destination path
        overwrite: Whether to overwrite existing file
    """
    if dest_path.exists() and not overwrite:
        raise DownloaderError(f"Destination file already exists: {dest_path}")
    
    try:
        shutil.move(str(temp_path), str(dest_path))
    except Exception as e:
        raise DownloaderError(f"Failed to move file to destination: {e}")

def retry_on_network_error(func: Callable, 
                         max_retries: int = 3,
                         retry_delay: int = 5,
                         **kwargs: Any) -> Any:
    """Retry a function on network error.
    
    Args:
        func: Function to retry
        max_retries: Maximum number of retries
        retry_delay: Delay between retries in seconds
        **kwargs: Arguments to pass to function
        
    Returns:
        Any: Function result
        
    Raises:
        NetworkError: If all retries fail
    """
    last_error = None
    for attempt in range(max_retries):
        try:
            return func(**kwargs)
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
            continue
    
    raise NetworkError(f"Failed after {max_retries} attempts: {last_error}")

def validate_download_path(path: Path) -> None:
    """Validate download path.
    
    Args:
        path: Path to validate
        
    Raises:
        DownloaderError: If path is invalid
    """
    if not path.parent.exists():
        try:
            path.parent.mkdir(parents=True)
        except Exception as e:
            raise DownloaderError(f"Failed to create download directory: {e}")
    
    if not os.access(path.parent, os.W_OK):
        raise DownloaderError(f"No write permission for directory: {path.parent}")

def get_unique_filename(directory: Path, filename: str) -> Path:
    """Get unique filename in directory.
    
    Args:
        directory: Target directory
        filename: Desired filename
        
    Returns:
        Path: Path with unique filename
    """
    base, ext = os.path.splitext(filename)
    counter = 1
    result_path = directory / filename
    
    while result_path.exists():
        new_name = f"{base}_{counter}{ext}"
        result_path = directory / new_name
        counter += 1
    
    return result_path

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters.
    
    Args:
        filename: Filename to sanitize
        
    Returns:
        str: Sanitized filename
    """
    # Replace invalid characters with underscores
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        filename = filename.replace(char, '_')
    
    # Remove leading/trailing spaces and dots
    filename = filename.strip('. ')
    
    # Ensure filename is not empty
    if not filename:
        filename = "download"
    
    return filename
