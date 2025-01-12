from pathlib import Path
from typing import Optional, Callable, List, Tuple
import uuid
import threading
import time
import logging
from pySmartDL import SmartDL
import re
from urllib.parse import urlparse

from ..config import Config
from ...utils.errors import (
    NetworkError, DownloaderError, CancellationError, 
    FileSystemError, InvalidURLError, UnsupportedURLError
)

class DownloaderLogger:
    @staticmethod
    def get_logger():
        logger = logging.getLogger(__name__)
        logger.setLevel(logging.INFO)
        return logger

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
        self.status = "pending"
        self.error_message = None
        self.completed = False
        self._progress_callback = None
        self._cancelled = False
        self._lock = threading.Lock()
        self.logger = DownloaderLogger.get_logger()
        
    def _validate_url(self, url: str) -> None:
        """Validate URL format and scheme
        
        Args:
            url: URL to validate
            
        Raises:
            InvalidURLError: If URL format is invalid
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
        """Set progress callback function"""
        self._progress_callback = callback
    
    def start(self) -> None:
        """Start the download"""
        try:
            self.logger.info(f"Starting download for {self.url}")
            
            # Create destination directory if it doesn't exist
            self.destination.mkdir(parents=True, exist_ok=True)
            
            # Configure downloader
            obj = SmartDL(
                self.url,
                str(self.destination),
                threads=self.threads,
                progress_bar=False
            )
            
            # Start download in thread
            thread = threading.Thread(target=self._download, args=(obj,), daemon=True)
            thread.start()
            
        except Exception as e:
            self.logger.error(f"Failed to start download: {e}", exc_info=True)
            raise DownloaderError(f"Failed to start download: {str(e)}")
            
    def _download(self, obj: SmartDL) -> None:
        """Internal download method"""
        try:
            # Start download non-blocking
            obj.start(blocking=False)
            
            # Monitor progress
            while not obj.isFinished():
                if self._cancelled:
                    obj.stop()
                    raise CancellationError("Download cancelled by user")
                
                if obj.get_errors():
                    raise NetworkError(f"Download failed: {obj.get_errors()}")
                
                # Update progress
                if self._progress_callback:
                    progress = obj.get_progress() * 100  # Convert to percentage
                    speed = obj.get_speed(human=False)  # Get raw speed in bytes/s
                    speed_str = f"{speed/1024/1024:.2f} MB/s" if speed else ""  # Format speed with 2 decimal places
                    downloaded = obj.get_dl_size()
                    total = obj.get_final_filesize()
                    
                    # Get filename from URL and headers
                    dest_path = Path(obj.get_dest())  # Convert string path to Path object
                    filename = dest_path.name  # Get just the filename
                    if not filename:
                        filename = "download"
                    
                    self._progress_callback(
                        self.download_id,
                        progress,
                        speed_str,
                        filename,  # No need to truncate, progress bar will handle it
                        total,
                        downloaded
                    )
                
                time.sleep(0.1)
            
            # Check for errors
            if obj.isSuccessful():
                self.completed = True
                if self._progress_callback:
                    dest_path = Path(obj.get_dest())
                    filename = dest_path.name
                    if not filename:
                        filename = "download"
                    self._progress_callback(
                        self.download_id,
                        100,
                        "",  # Empty speed string when complete
                        f"{filename} (Complete!)",  # No need to truncate, progress bar will handle it
                        0,
                        0
                    )
            else:
                raise NetworkError(f"Download failed: {obj.get_errors()}")
                
        except Exception as e:
            self.error_message = str(e)
            if self._progress_callback:
                self._progress_callback(
                    self.download_id,
                    0,
                    "",
                    f"Download failed: {str(e)}",
                    0,
                    0
                )
            raise
            
    def cancel(self) -> None:
        """Cancel the download"""
        with self._lock:
            if not self._cancelled:
                self._cancelled = True
                self.logger.info(f"Cancelling download for {self.url}")
                
                # Update progress callback
                if self._progress_callback:
                    self._progress_callback(self.download_id, 0, "", "Download cancelled", 0, 0)
                    
                # Clean up any partial downloads
                try:
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
            self._progress_callback(self.download_id, progress, speed, "")
            
    def _set_finished(self) -> None:
        """Set finished state"""
        self.status = "finished"
        self.completed = True
        
        if self._progress_callback:
            self._progress_callback(self.download_id, 100, "", "Download complete", 0, 0)
