"""Utility functions for file operations"""

import re

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing invalid characters
    
    Args:
        filename: Original filename
        
    Returns:
        Sanitized filename safe for all operating systems
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
