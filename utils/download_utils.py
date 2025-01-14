"""
Download utilities for JustDownloadIt.

This module provides common utility functions used by both regular
and YouTube downloaders.
"""

import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from datetime import datetime
import threading
from queue import Queue
from urllib.parse import urlparse
from utils.errors import InvalidURLError, UnsupportedURLError

def calculate_download_stats(timestamps: List[float], 
                           speeds: List[float],
                           progress: List[float],
                           downloaded: List[float]) -> Dict:
    """Calculate download statistics.
    
    Args:
        timestamps: List of timestamps
        speeds: List of speeds in bytes/s
        progress: List of progress percentages
        downloaded: List of downloaded bytes
        
    Returns:
        dict: Dictionary containing calculated statistics
    """
    if not timestamps or not speeds:
        return {
            'peak_speed': 0,
            'avg_speed': 0,
            'total_time': 0,
            'eta': 0,
            'total_size': 0
        }
        
    peak_speed = max(speeds)
    avg_speed = sum(speeds) / len(speeds)
    total_time = timestamps[-1] - timestamps[0]
    
    # Calculate ETA based on recent speed
    if progress and progress[-1] < 100 and speeds[-1] > 0:
        remaining_bytes = (100 - progress[-1]) / 100 * downloaded[-1]
        eta = remaining_bytes / speeds[-1]
    else:
        eta = 0
        
    return {
        'peak_speed': peak_speed,
        'avg_speed': avg_speed,
        'total_time': total_time,
        'eta': eta,
        'total_size': downloaded[-1] if downloaded else 0
    }

def create_download_chunks(total_size: int, chunk_size: int, threads: int) -> List[Tuple[int, int]]:
    """Create download chunks for multi-threaded downloading.
    
    Args:
        total_size: Total file size in bytes
        chunk_size: Size of each chunk in bytes
        threads: Number of threads to use
        
    Returns:
        list: List of (start, end) byte ranges for each chunk
    """
    chunks = []
    bytes_per_thread = total_size // threads
    
    for i in range(threads):
        start = i * bytes_per_thread
        end = start + bytes_per_thread - 1 if i < threads - 1 else total_size - 1
        
        # Break large chunks into smaller ones
        while start < end:
            chunk_end = min(start + chunk_size - 1, end)
            chunks.append((start, chunk_end))
            start = chunk_end + 1
            
    return chunks

def merge_download_chunks(chunks: List[Path], output_path: Path) -> None:
    """Merge downloaded chunks into a single file.
    
    Args:
        chunks: List of chunk file paths
        output_path: Path to final output file
    """
    with output_path.open('wb') as outfile:
        for chunk in chunks:
            with chunk.open('rb') as infile:
                while True:
                    data = infile.read(8192)
                    if not data:
                        break
                    outfile.write(data)
            chunk.unlink()  # Delete chunk after merging

def get_download_headers(url: str, resume_position: Optional[int] = None) -> Dict[str, str]:
    """Get headers for download request.
    
    Args:
        url: Download URL
        resume_position: Byte position to resume from
        
    Returns:
        dict: Headers dictionary
    """
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    if resume_position is not None:
        headers['Range'] = f'bytes={resume_position}-'
        
    return headers

def format_size(size: float) -> str:
    """Format size in bytes to human readable string.
    
    Args:
        size: Size in bytes
        
    Returns:
        str: Formatted size string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            if unit == 'B':
                return f"{size:.0f} {unit}"
            return f"{size:.2f} {unit}"
        size /= 1024.0
    return f"{size:.2f} PB"

URL_PATTERN = re.compile(
    r'^https?://'  # http:// or https://
    r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
    r'localhost|'  # localhost...
    r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
    r'(?::\d+)?'  # optional port
    r'(?:/?|[/?]\S+)$', re.IGNORECASE)

def validate_url(url: str) -> None:
    """Validate a URL string.
    
    Args:
        url (str): URL to validate
        
    Raises:
        InvalidURLError: If URL is invalid
        UnsupportedURLError: If URL scheme is not supported
    """
    # Clean the URL first
    url = url.strip()
    
    if not url:
        raise InvalidURLError("URL cannot be empty")
        
    # Basic format check before parsing
    if not url.startswith(('http://', 'https://')):
        raise UnsupportedURLError("Only HTTP/HTTPS URLs are supported")
        
    # Check URL format
    if not URL_PATTERN.match(url):
        raise InvalidURLError("Please enter a valid URL (e.g., https://example.com)")
        
    # Parse URL and check scheme
    try:
        parsed = urlparse(url)
        if not parsed.netloc:  # Check if there's a valid domain
            raise InvalidURLError("URL must contain a valid domain")
    except Exception as e:
        raise InvalidURLError(f"Invalid URL format: {str(e)}")
