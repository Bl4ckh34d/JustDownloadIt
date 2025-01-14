"""
File utility functions for JustDownloadIt.

This module provides various file-related utility functions used throughout the application.
It handles file name sanitization, path manipulation, and file system operations.

Functions:
    sanitize_filename: Remove invalid characters from filename
    get_unique_filename: Get a unique filename by adding a number suffix if the file exists

Dependencies:
    - pathlib: Path manipulation
    - os: File system operations
    - re: Regular expressions
"""

import os
from pathlib import Path
import re

def sanitize_filename(filename: str) -> str:
    """
    Remove invalid characters from filename.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Sanitized filename
    """
    # Remove invalid characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    # Remove control characters
    filename = "".join(char for char in filename if ord(char) >= 32)
    return filename.strip()

def get_unique_filename(filepath: Path) -> Path:
    """
    Get a unique filename by adding a number suffix if the file exists.
    
    Args:
        filepath: Original file path
        
    Returns:
        Path: Unique file path
    """
    if not filepath.exists():
        return filepath
        
    directory = filepath.parent
    name = filepath.stem
    extension = filepath.suffix
    counter = 1
    
    while True:
        new_name = f"{name} ({counter}){extension}"
        new_path = directory / new_name
        if not new_path.exists():
            return new_path
        counter += 1
