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
        self._completion_callback = None
        
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
    
    def set_completion_callback(self, callback: Callable[[str], None]) -> None:
        """Set completion callback function
        
        Args:
            callback: Function to call when download completes, takes download_id as argument
        """
        self._completion_callback = callback
    
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
            # Set a longer timeout for slow connections
            obj.timeout = 30  # 30 seconds timeout
            
            # Start the download
            obj.start(blocking=False)
            
            # Monitor progress
            while not obj.isFinished() and not self._cancelled:
                try:
                    downloaded = obj.get_dl_size()
                    total = obj.get_final_filesize()
                    speed = obj.get_speed(human=True)
                    
                    if self._progress_callback:
                        self._progress_callback(
                            self.download_id,
                            int(downloaded / total * 100) if total else 0,
                            speed,
                            Path(obj.get_dest()).name,
                            downloaded,
                            total if total else downloaded
                        )
                except Exception as e:
                    self.logger.error(f"Error updating progress: {e}")
                
                time.sleep(0.1)
            
            # Wait for download to finish
            try:
                obj.wait()
            except Exception as e:
                self.logger.error(f"Error waiting for download: {e}")
                raise
                
            # Check final status
            if not self._cancelled and obj.isSuccessful():
                self.completed = True
                if self._progress_callback:
                    dest_path = Path(obj.get_dest())
                    filename = dest_path.name
                    if not filename:
                        filename = "download"
                    filename = sanitize_filename(filename)
                    self._progress_callback(
                        self.download_id,
                        100,
                        "",
                        f"{filename} (Complete!)",
                        obj.get_final_filesize(),
                        obj.get_final_filesize()
                    )
                    
                # Call completion callback if set
                if self._completion_callback:
                    self._completion_callback(self.download_id)
            else:
                # Handle cancellation or failure
                if self._cancelled:
                    self.logger.info(f"Download cancelled: {self.url}")
                else:
                    error_msg = obj.get_errors()[0] if obj.get_errors() else "Unknown error"
                    self.logger.error(f"Download failed: {error_msg}")
                    if self._progress_callback:
                        self._progress_callback(
                            self.download_id,
                            0,
                            "",
                            f"Error: {error_msg}",
                            0,
                            0
                        )
                        
                # Clean up any partial downloads
                try:
                    download_dir = Path(obj.get_dest()).parent
                    partial_pattern = f"{Path(obj.get_dest()).name}.*"
                    for partial_file in download_dir.glob(partial_pattern):
                        try:
                            partial_file.unlink()
                        except Exception as e:
                            self.logger.error(f"Error cleaning up {partial_file}: {e}")
                except Exception as e:
                    self.logger.error(f"Error during cleanup: {e}")
                    
        except Exception as e:
            self.logger.error(f"Download error: {e}", exc_info=True)
            if self._progress_callback:
                self._progress_callback(
                    self.download_id,
                    0,
                    "",
                    f"Error: {str(e)}",
                    0,
                    0
                )
            # Clean up any partial downloads on error
            try:
                download_dir = Path(obj.get_dest()).parent
                partial_pattern = f"{Path(obj.get_dest()).name}.*"
                for partial_file in download_dir.glob(partial_pattern):
                    try:
                        partial_file.unlink()
                    except Exception as e:
                        self.logger.error(f"Error cleaning up {partial_file}: {e}")
            except Exception as e:
                self.logger.error(f"Error during cleanup: {e}")
    
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
