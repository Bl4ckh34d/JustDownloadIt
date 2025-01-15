"""URL processing utilities for JustDownloadIt.

This module provides comprehensive URL validation, parsing, and processing
utilities for both YouTube and regular downloads.
"""

import re
from typing import List, Tuple, Optional
from urllib.parse import urlparse, unquote, quote, parse_qs
from pathlib import Path
import logging

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

class URLType:
    """URL type constants."""
    YOUTUBE = 'youtube'
    YOUTUBE_PLAYLIST = 'youtube_playlist'
    REGULAR = 'regular'
    UNKNOWN = 'unknown'

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
    
    # Find the last occurrence of http:// or https:// or www.
    if "http://" in url or "https://" in url or "www." in url:
        last_start = max(
            url.rfind("http://"),
            url.rfind("https://"),
            url.rfind("www.")
        )
        if last_start >= 0:
            url = url[last_start:]
            # Take only up to the next whitespace or newline
            if ' ' in url:
                url = url.split()[0]
            if '\n' in url:
                url = url.split('\n')[0]
    
    url = url.strip()
    
    # Add https:// if no protocol specified
    if not url.startswith(('http://', 'https://')):
        if url.startswith('www.'):
            url = 'https://' + url
        else:
            url = 'https://' + url
    
    return unquote(url)

def check_link_type(url: str) -> str:
    """Check if URL is YouTube video, playlist or regular download.
    
    Args:
        url (str): URL to check
    
    Returns:
        str: URL type from URLType constants
    """
    if not url:
        return URLType.UNKNOWN
        
    # Add https:// if no protocol specified
    if not url.startswith(('http://', 'https://')):
        if url.startswith('www.'):
            url = 'https://' + url
        else:
            url = 'https://' + url
        
    url_lower = url.lower()
    if any(domain in url_lower for domain in ['youtube.com', 'youtu.be']):
        # Check if it's a playlist
        if 'list=' in url_lower:
            return URLType.YOUTUBE_PLAYLIST
        return URLType.YOUTUBE
    
    # Check if it's a valid domain name
    try:
        parsed = urlparse(url_lower)
        if parsed.netloc and '.' in parsed.netloc and not parsed.netloc.endswith('.'):
            return URLType.REGULAR
    except:
        pass
    
    return URLType.UNKNOWN

def extract_playlist_videos(url: str) -> List[str]:
    """Extract individual video URLs from a YouTube playlist.
    
    Args:
        url (str): YouTube playlist URL
        
    Returns:
        List[str]: List of video URLs in the playlist
        
    Raises:
        ValueError: If URL is not a valid YouTube playlist or yt-dlp is not installed
    """
    if not yt_dlp:
        raise ValueError("yt-dlp is required for playlist extraction but not installed")
    
    logger = logging.getLogger(__name__)
    logger.info(f"Attempting to extract videos from playlist: {url}")
    
    # Clean the URL first
    url = clean_url(url)
    
    # Parse URL to extract playlist ID
    parsed_url = urlparse(url)
    query_params = parse_qs(parsed_url.query)
    playlist_id = query_params.get('list', [None])[0]
    
    if not playlist_id:
        raise ValueError("No playlist ID found in URL")
        
    logger.info(f"Found playlist ID: {playlist_id}")
    
    # Ensure URL points to the playlist directly
    playlist_url = f"https://www.youtube.com/playlist?list={playlist_id}"
    
    video_urls = []
    try:
        ydl_opts = {
            'quiet': True,
            'extract_flat': True,
            'force_generic_extractor': False,
            'ignoreerrors': True,  # Skip unavailable videos
            'no_warnings': False,  # Show warnings for debugging
            'logger': logger
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            logger.info("Starting playlist extraction...")
            result = ydl.extract_info(playlist_url, download=False)
            
            if not result:
                raise ValueError("Failed to extract playlist info")
                
            logger.info(f"Extraction result type: {type(result)}")
            logger.info(f"Extraction result keys: {result.keys() if isinstance(result, dict) else 'Not a dict'}")
            
            if isinstance(result, dict) and 'entries' in result:
                entries = result['entries']
                logger.info(f"Found {len(entries)} entries in playlist")
                
                for entry in entries:
                    if not entry:  # Skip unavailable videos
                        continue
                        
                    video_id = entry.get('id') or entry.get('url')
                    if video_id:
                        video_url = f"https://www.youtube.com/watch?v={video_id}"
                        video_urls.append(video_url)
                        logger.debug(f"Added video: {video_url}")
            else:
                raise ValueError("No entries found in playlist data")
            
            if not video_urls:
                raise ValueError("No valid videos found in playlist")
                
            logger.info(f"Successfully extracted {len(video_urls)} videos from playlist")
            return video_urls
            
    except Exception as e:
        logger.error(f"Error extracting playlist videos: {str(e)}")
        logger.error(f"Error type: {type(e)}")
        logger.exception("Full traceback:")
        raise ValueError(f"Failed to extract playlist videos: {str(e)}")

def is_line_valid_url(line: str) -> bool:
    """Check if a line contains only a valid URL and nothing else.
    The line can have whitespace before/after but no other text or characters.
    If there are any spaces between parts of what could be a URL, it's not valid.
    
    Args:
        line (str): Line to check
        
    Returns:
        bool: True if line contains only a valid URL, False otherwise
    """
    # Remove leading/trailing whitespace
    line = line.strip()
    if not line:
        return False
        
    # If line contains any spaces after trimming, it has extra content
    if ' ' in line:
        return False
        
    # Check if valid URL
    is_valid, _ = validate_url(line)
    return is_valid

def parse_urls(text: str) -> List[str]:
    """Parse URLs from text input. Only accepts lines that contain nothing but a valid URL.
    
    Args:
        text (str): Text containing URLs
        
    Returns:
        List[str]: List of valid URLs found in text
    """
    # Split text into lines and process each line
    valid_urls = []
    for line in text.splitlines():
        if is_line_valid_url(line):
            valid_urls.append(clean_url(line))
    return valid_urls

def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """Validate URL format and accessibility.
    
    Args:
        url (str): URL to validate
        
    Returns:
        Tuple[bool, Optional[str]]: (is_valid, error_message)
    """
    url = clean_url(url)
    if not url:
        return False, "Empty URL"
    
    try:
        # Basic URL pattern validation - allow URLs without protocol but require valid domain
        url_pattern = re.compile(
            r'^(?:https?://)?'  # Optional protocol
            r'(?:'
            r'(?:[A-Z0-9][-A-Z0-9]*[A-Z0-9](?:\.[A-Z]{2,})+)|'  # domain name
            r'localhost|'  # localhost
            r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}'  # ip address
            r')'
            r'(?::\d+)?'  # optional port
            r'(?:/[^\s<>"]*)?$',  # optional path
            re.IGNORECASE
        )
        
        if not url_pattern.match(url):
            return False, "Invalid URL format"
        
        # Additional validation for domain names
        parsed = urlparse(url)
        if parsed.netloc:
            if parsed.netloc.endswith('.'):
                return False, "Invalid domain name (ends with dot)"
            if parsed.netloc.count('.') < 1:
                return False, "Invalid domain name (missing TLD)"
            
        return True, None
        
    except Exception as e:
        return False, str(e)

def extract_filename(url: str, default: str = "download") -> str:
    """Extract filename from URL.
    
    Args:
        url (str): URL to extract filename from
        default (str): Default filename if none found
        
    Returns:
        str: Extracted or default filename
    """
    try:
        path = urlparse(url).path
        filename = Path(path).name
        if filename and '.' in filename:
            return unquote(filename)
    except:
        pass
    return default

def normalize_url(url: str) -> str:
    """Normalize URL by encoding special characters.
    
    Args:
        url (str): URL to normalize
        
    Returns:
        str: Normalized URL
    """
    url = clean_url(url)
    parsed = urlparse(url)
    
    # Encode path but keep slashes
    path_parts = parsed.path.split('/')
    encoded_path = '/'.join(quote(part) for part in path_parts)
    
    # Reconstruct URL with encoded path
    normalized = f"{parsed.scheme}://{parsed.netloc}{encoded_path}"
    if parsed.query:
        normalized += f"?{parsed.query}"
    if parsed.fragment:
        normalized += f"#{parsed.fragment}"
        
    return normalized

def get_youtube_video_id(url: str) -> Optional[str]:
    """Extract YouTube video ID from URL.
    
    Args:
        url (str): YouTube URL
        
    Returns:
        Optional[str]: Video ID if found, None otherwise
    """
    if check_link_type(url) != URLType.YOUTUBE:
        return None
        
    patterns = [
        r'(?:v=|v/|embed/|youtu\.be/)([^&?/]+)',
        r'(?:watch\?v=)([^&?/]+)',
        r'(?:youtube\.com/v/)([^&?/]+)'
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def remove_url_from_text(text: str, url_to_remove: str) -> str:
    """Remove a specific URL from multiline text.
    Only removes the line if it contains exactly the URL (after cleaning).
    
    Args:
        text (str): Multiline text containing URLs
        url_to_remove (str): URL to remove
        
    Returns:
        str: Text with the URL line removed
    """
    url_to_remove = clean_url(url_to_remove)
    lines = text.splitlines()
    new_lines = []
    
    for line in lines:
        line_stripped = line.strip()
        if line_stripped and is_line_valid_url(line_stripped):
            line_url = clean_url(line_stripped)
            if line_url == url_to_remove:
                continue
        new_lines.append(line)
        
    return "\n".join(new_lines)
