"""
Formatting utilities for JustDownloadIt.

This module provides utility functions for formatting sizes, speeds,
and other download-related information.
"""

from typing import Union

def format_size(size: float, precision: int = 2) -> str:
    """Format size in bytes to human readable string.
    
    Args:
        size: Size in bytes
        precision: Number of decimal places
        
    Returns:
        str: Formatted size string (e.g., "1.5 GB")
    """
    if size == 0:
        return "0 B"
        
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    size = float(size)
    unit_index = 0
    
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
        
    return f"{size:.{precision}f} {units[unit_index]}"

def format_speed(bytes_per_second: float, precision: int = 2) -> str:
    """Format speed in bytes/second to human readable string.
    
    Args:
        bytes_per_second: Speed in bytes per second
        precision: Number of decimal places
        
    Returns:
        str: Formatted speed string (e.g., "1.5 MB/s")
    """
    if bytes_per_second == 0:
        return "0 B/s"
        
    return f"{format_size(bytes_per_second, precision)}/s"

def format_time(seconds: Union[int, float]) -> str:
    """Format time in seconds to human readable string.
    
    Args:
        seconds: Time in seconds
        
    Returns:
        str: Formatted time string (e.g., "1h 30m 45s")
    """
    if seconds < 0:
        return "Unknown"
        
    if seconds < 60:
        return f"{seconds:.0f}s"
        
    minutes = seconds // 60
    seconds = seconds % 60
    
    if minutes < 60:
        return f"{minutes:.0f}m {seconds:.0f}s"
        
    hours = minutes // 60
    minutes = minutes % 60
    
    return f"{hours:.0f}h {minutes:.0f}m {seconds:.0f}s"

def format_progress(progress: float, width: int = 50) -> str:
    """Format progress percentage as a progress bar string.
    
    Args:
        progress: Progress percentage (0-100)
        width: Width of the progress bar in characters
        
    Returns:
        str: ASCII progress bar (e.g., "[=====>     ] 50%")
    """
    filled = int(width * progress / 100)
    bar = "=" * (filled - 1)
    if filled > 0:
        bar += ">"
    bar = bar.ljust(width)
    return f"[{bar}] {progress:.1f}%"
