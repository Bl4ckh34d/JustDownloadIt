"""URL processing utilities for JustDownloadIt."""

import re
from typing import List, Tuple

def clean_url(url: str) -> str:
    """Clean URL by removing log messages and invalid characters.
    
    Args:
        url (str): Raw URL string
    
    Returns:
        str: Cleaned URL string
    """
    if not url:
        return ""
        
    # Split by common log patterns and take the last part
    url = url.split("INFO:")[-1]
    url = url.split("ERROR:")[-1]
    url = url.split("WARNING:")[-1]
    url = url.split("DEBUG:")[-1]
    
    # Find the last occurrence of http:// or https://
    if "http://" in url or "https://" in url:
        last_http = max(url.rfind("http://"), url.rfind("https://"))
        if last_http >= 0:
            url = url[last_http:]
            # Take only up to the next whitespace or newline
            if ' ' in url:
                url = url.split()[0]
            if '\n' in url:
                url = url.split('\n')[0]
    
    return url.strip()

def check_link_type(url: str) -> str:
    """Check if URL is YouTube or regular download.
    
    Args:
        url (str): URL to check
    
    Returns:
        str: 'youtube' if YouTube URL, 'regular' otherwise
    """
    if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
        return 'youtube'
    return 'regular'

def parse_urls(text: str) -> List[str]:
    """Parse URLs from text input.
    
    Args:
        text (str): Text containing URLs
        
    Returns:
        list[str]: List of cleaned URLs
    """
    urls = []
    for line in text.split('\n'):
        url = clean_url(line)
        if url:
            urls.append(url)
    return urls
