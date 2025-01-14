"""
File utility functions for JustDownloadIt.

This module provides various file-related utility functions used throughout the application.
It handles file name sanitization, path manipulation, and file system operations.

Functions:
    sanitize_filename: Clean filenames of invalid characters
    get_unique_filename: Generate unique filename to avoid conflicts
    ensure_dir: Create directory if it doesn't exist
    get_file_size: Get human-readable file size
    is_valid_path: Check if a path is valid for the current OS

Dependencies:
    - pathlib: Path manipulation
    - os: File system operations
"""

import os
import re

def sanitize_filename(filename: str) -> str:
    """
    Sanitize a filename by removing invalid characters and replacing them with underscores.
    
    Args:
        filename (str): The filename to sanitize
        
    Returns:
        str: The sanitized filename that is safe to use on the filesystem
    """
    # Replace invalid characters with underscore
    # This covers Windows, macOS, and Linux invalid characters
    invalid_chars = r'[<>:"/\\|?*\x00-\x1f]'
    sanitized = re.sub(invalid_chars, '_', filename)
    
    # Remove dots and spaces from start/end
    sanitized = sanitized.strip('. ')
    
    # Ensure filename isn't empty after sanitization
    if not sanitized:
        sanitized = 'download'
        
    return sanitized
