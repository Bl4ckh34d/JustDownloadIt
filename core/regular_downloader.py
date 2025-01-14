"""
Base downloader implementation for JustDownloadIt.

This module provides the Downloader base class which implements core download functionality.
It handles file downloads with progress tracking, error handling, and cancellation support.

Features:
    - Multi-threaded downloading with progress tracking
    - Automatic file naming and conflict resolution
    - Download speed and ETA calculation
    - Pause/Resume/Cancel functionality
    - Error handling and retry mechanism

Classes:
    Downloader: Base class for download operations

Dependencies:
    - pySmartDL: Smart download library with resume capability
    - core.download_state: Download state tracking
    - utils.errors: Error handling utilities
    - utils.file_utils: File handling utilities
"""

from pathlib import Path
from typing import Optional, Callable, List, Tuple
import uuid
import threading
import time
import logging
from pySmartDL import SmartDL
import re
from urllib.parse import urlparse

from utils.errors import (
    NetworkError, DownloaderError, CancellationError, 
    FileSystemError, InvalidURLError, UnsupportedURLError
)
from utils.logger import DownloaderLogger
from utils.file_utils import sanitize_filename, get_unique_filename
from .config import Config
from .download_state import DownloadState

class Downloader:
    """Base downloader class with SmartDL implementation"""
    
    URL_PATTERN = re.compile(
        r'^https?://'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    
    def __init__(self, url: str, destination: Path, threads: int = Config.DEFAULT_THREADS):
        """Initialize downloader
        
        Args:
            url: URL to download
            destination: Path to save the download
            threads: Number of threads to use
        """
        self._validate_url(url)
        self.url = url
        self.destination = Path(destination)  # Ensure it's a Path object
        self.threads = min(threads, Config.MAX_THREADS)
        self.download_id = url
        self.progress = 0
        self.speed = ""
        self.state = DownloadState.PENDING
        self.error_message = None
        self._progress_callback = None
        self._cancelled = False
        self._lock = threading.Lock()
        self.logger = DownloaderLogger.get_logger()
        self._completion_callback = None
        
        # Create destination directory if it doesn't exist
        self.destination.mkdir(parents=True, exist_ok=True)
        
        # Download statistics tracking
        self.start_time = None
        self.stats = {
            'timestamps': [],  # List of timestamps
            'speeds': [],      # List of speeds in bytes/s
            'progress': [],    # List of progress percentages
            'downloaded': [],  # List of downloaded bytes
            'peak_speed': 0,   # Peak speed in bytes/s
            'avg_speed': 0,    # Average speed in bytes/s
            'total_time': 0,   # Total download time in seconds
            'total_size': 0,   # Total size in bytes
        }
    
    def _validate_url(self, url: str) -> None:
        """
        Validate a URL string.
        
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
        if not self.URL_PATTERN.match(url):
            raise InvalidURLError("Please enter a valid URL (e.g., https://example.com)")
            
        # Parse URL and check scheme
        try:
            parsed = urlparse(url)
            if not parsed.netloc:  # Check if there's a valid domain
                raise InvalidURLError("URL must contain a valid domain")
        except Exception as e:
            raise InvalidURLError(f"Invalid URL format: {str(e)}")
    
    def set_progress_callback(self, callback: Callable) -> None:
        """
        Set the callback function for download progress updates.
        
        Args:
            callback (Callable): Function to call with progress updates.
                Will be called with (download_id, progress, speed, text, total_size, downloaded_size, stats)
        """
        self._progress_callback = callback
    
    def set_completion_callback(self, callback: Callable[[str], None]) -> None:
        """
        Set completion callback function
        
        Args:
            callback (Callable[[str], None]): Function to call when download completes, takes download_id as argument
        """
        self._completion_callback = callback
    
    def start(self) -> None:
        """Start the download"""
        try:
            # Create SmartDL object
            dl = SmartDL(
                self.url,
                str(self.destination),
                progress_bar=False,
                threads=self.threads
            )
            
            # Get filename from URL or Content-Disposition header
            filename = dl.get_dest()
            if not filename:
                filename = urlparse(self.url).path.split('/')[-1]
            
            # Sanitize filename and ensure it's unique
            filename = sanitize_filename(filename)
            dest_path = get_unique_filename(self.destination / filename)
            
            # Update SmartDL destination
            dl.dest = str(dest_path)
            
            # Start download
            self.state = DownloadState.DOWNLOADING
            self.start_time = time.time()
            
            # Setup progress monitoring
            def progress_callback(progress):
                if progress.total_size:
                    percent = (progress.dl_size / progress.total_size) * 100
                else:
                    percent = 0
                    
                speed = progress.speed if progress.speed else 0
                self._progress_hook({
                    'status': 'downloading',
                    'downloaded_bytes': progress.dl_size,
                    'total_bytes': progress.total_size,
                    'speed': speed,
                    'filename': filename,
                    'eta': progress.eta if progress.eta else 0
                })
            
            dl.start(blocking=False)  # Non-blocking to allow cancellation
            
            # Monitor progress while downloading
            while not dl.isFinished() and not self._cancelled:
                if dl.get_status() == "downloading":
                    progress_callback(dl)
                time.sleep(0.1)
                
            # Handle cancellation
            if self._cancelled:
                dl.stop()
                self.state = DownloadState.CANCELLED
                return
                
            # Wait for all threads to finish
            dl.wait(raise_exceptions=True)
            
            # Update final state
            if dl.isSuccessful():
                self.state = DownloadState.COMPLETED
                if self._completion_callback:
                    self._completion_callback(self.download_id)
            else:
                self.state = DownloadState.ERROR
                self.error_message = "Download failed"
                
        except Exception as e:
            self.state = DownloadState.ERROR
            self.error_message = str(e)
            raise DownloaderError(f"Download failed: {str(e)}")
    
    def cancel(self) -> None:
        """
        Cancel the current download.
        """
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                self.logger.info(f"Cancelling download for {self.url}")
                
                # Update progress callback
                if self._progress_callback:
                    self._progress_callback(self.download_id, 0, "", "Download cancelled", 0, 0, None, DownloadState.CANCELLED)
                    
                # Clean up any partial downloads
                try:
                    # Try to stop the SmartDL download if it exists
                    if hasattr(self, '_current_download') and self._current_download:
                        try:
                            self._current_download.stop()
                        except:
                            pass
                            
                    # Clean up partial files
                    for file in self.destination.glob(f"*{self.download_id}*"):
                        try:
                            file.unlink()
                        except:
                            pass
                except Exception as e:
                    self.logger.error(f"Failed to clean up downloads: {e}")
                    
    def stop(self) -> None:
        """Stop the download"""
        self.cancel()
    
    def pause(self) -> None:
        """Pause the download"""
        # Not implemented
    
    def resume(self) -> None:
        """Resume the download"""
        # Not implemented
    
    def get_segments(self) -> List[Tuple[int, float, float]]:
        """Get download segments for progress visualization"""
        # Not implemented
    
    def _update_progress(self, progress: float, speed: str = "") -> None:
        """Update download progress"""
        self.progress = progress
        self.speed = speed
        
        if self._progress_callback:
            self._progress_callback(self.download_id, progress, speed, "", None, None, self.state)
            
    def _set_finished(self) -> None:
        """Set finished state"""
        self.state = DownloadState.COMPLETED
        
        if self._progress_callback:
            self._progress_callback(self.download_id, 100, "", "Download complete", 0, 0, self.state)
