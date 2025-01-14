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
from utils.file_utils import sanitize_filename
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
        """Initialize downloader"""
        self._validate_url(url)
        self.url = url
        self.destination = destination
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
        """
        Start the download in a new thread.
        
        Raises:
            NetworkError: If download fails due to network issues
            FileSystemError: If file cannot be saved
        """
        try:
            self.logger.info(f"Starting download for {self.url}")
            
            # Create destination directory if it doesn't exist
            self.destination.mkdir(parents=True, exist_ok=True)
            
            # Configure downloader
            obj = SmartDL(
                self.url,
                str(self.destination),
                threads=self.threads,
                progress_bar=False,
                timeout=30  # Increased from default
            )
            
            # Start download in thread
            thread = threading.Thread(target=self._download, args=(obj,), daemon=True)
            thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start download: {e}", exc_info=True)
            raise DownloaderError(f"Failed to start download: {str(e)}")
            
    def _download(self, obj: SmartDL) -> None:
        """
        Perform the actual download.
        
        Args:
            obj (SmartDL): SmartDL object
        
        Raises:
            NetworkError: If download fails due to network issues
            FileSystemError: If file cannot be saved
            CancellationError: If download is cancelled
        """
        try:
            # Store reference to current download
            self._current_download = obj
            
            # Set a longer timeout for slow connections
            obj.timeout = 30  # 30 seconds timeout
            
            self.start_time = time.time()
            self.state = DownloadState.DOWNLOADING
            
            # Start the download
            obj.start(blocking=False)
            
            # Monitor progress while downloading
            while not obj.isFinished() and not self._cancelled:
                try:
                    current_time = time.time()
                    downloaded = obj.get_dl_size()
                    total = obj.get_final_filesize()
                    speed_bytes = obj.get_speed(human=False)  # Get raw speed in bytes/s
                    speed_human = obj.get_speed(human=True)
                    progress = int(downloaded / total * 100) if total else 0
                    
                    # Update statistics
                    self.stats['timestamps'].append(current_time - self.start_time)
                    self.stats['speeds'].append(speed_bytes)
                    self.stats['progress'].append(progress)
                    self.stats['downloaded'].append(downloaded)
                    self.stats['peak_speed'] = max(self.stats['peak_speed'], speed_bytes)
                    self.stats['avg_speed'] = sum(self.stats['speeds']) / len(self.stats['speeds'])
                    self.stats['total_time'] = current_time - self.start_time
                    self.stats['total_size'] = total
                    
                    # Update progress
                    self.progress = progress
                    self.speed = speed_human
                    
                    # Call progress callback if set
                    if self._progress_callback:
                        dest_path = str(self.destination / obj.get_dest())
                        self._progress_callback(
                            self.download_id, progress, speed_human, dest_path, 
                            total, downloaded, self.stats, self.state
                        )
                        
                    time.sleep(0.1)  # Brief sleep to prevent high CPU usage
                    
                except Exception as e:
                    # Log error but continue monitoring
                    print(f"Error updating progress: {e}")
                    
            # Handle cancellation
            if self._cancelled:
                self.state = DownloadState.CANCELLED
                if self._progress_callback:
                    self._progress_callback(
                        self.download_id, self.progress, "", "", 
                        0, 0, self.stats, self.state
                    )
                return
                
            # Handle completion
            if obj.isFinished():
                if obj.isSuccessful():
                    self.state = DownloadState.COMPLETED
                    if self._progress_callback:
                        dest_path = str(self.destination / obj.get_dest())
                        self._progress_callback(
                            self.download_id, 100, "", dest_path, 
                            obj.get_final_filesize(), obj.get_final_filesize(),
                            self.stats, self.state
                        )
                    if self._completion_callback:
                        self._completion_callback(self.download_id)
                else:
                    self.state = DownloadState.ERROR
                    self.error_message = str(obj.get_errors()[0]) if obj.get_errors() else "Unknown error"
                    if self._progress_callback:
                        self._progress_callback(
                            self.download_id, self.progress, "", self.error_message,
                            0, 0, self.stats, self.state
                        )
                    
        except Exception as e:
            self.state = DownloadState.ERROR
            self.error_message = str(e)
            if self._progress_callback:
                self._progress_callback(
                    self.download_id, self.progress, "", str(e),
                    0, 0, self.stats, self.state
                )
    
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
