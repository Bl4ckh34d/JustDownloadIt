from pathlib import Path
from typing import Optional, Callable, Dict, List, Union
from queue import Queue
import threading
import re
from urllib.error import URLError as BuiltinURLError

from utils.errors import (
    NetworkError, DownloaderError, URLError, 
    InvalidURLError, UnsupportedURLError, YouTubeError
)
from .config import Config
from .downloader import Downloader
from .youtube import YouTubeDownloader

class DownloadManager:
    def __init__(self, download_dir: Optional[Path] = None):
        """Initialize the download manager
        
        Args:
            download_dir: Directory to save downloads to. If None, uses default downloads directory
        """
        # Set download directory
        self.download_dir = Config.DOWNLOAD_DIR if download_dir is None else download_dir
        
        # Create downloads directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.active_downloads: Dict[str, Union[Downloader, YouTubeDownloader]] = {}
        self.download_queue = Queue()
        self.thread_pool = []
        self._stop_flag = False
    
    def download(self, url: str, on_progress: Optional[Callable] = None, threads: int = 4) -> None:
        """Start a new download
        
        Args:
            url: URL to download
            on_progress: Optional progress callback
            threads: Number of threads to use for download
            
        Raises:
            InvalidURLError: If URL is invalid
            NetworkError: If network error occurs
        """
        try:
            # Clean URL before creating downloader
            url = url.strip() if url else ""
            if not url:
                raise InvalidURLError("URL cannot be empty")
                
            # Create downloader
            downloader = Downloader(url, self.download_dir, threads=min(threads, Config.MAX_THREADS))
            
            # Set progress callback if provided
            if on_progress:
                downloader.set_progress_callback(on_progress)
                
            # Set completion callback
            downloader.set_completion_callback(self._on_download_complete)
                
            # Store download object
            self.active_downloads[url] = downloader
            
            # Start download
            downloader.start()
            
        except InvalidURLError as e:
            raise
            
        except UnsupportedURLError as e:
            raise
            
        except BuiltinURLError as e:
            error_msg = "Invalid URL format"
            raise InvalidURLError(error_msg)
            
        except Exception as e:
            error_msg = f"Failed to start download: {str(e)}"
            raise NetworkError(error_msg)
    
    def download_youtube(self, url: str, preferred_quality: str, 
                       on_progress: Optional[Callable] = None,
                       threads: int = Config.DEFAULT_THREADS) -> None:
        """Start a YouTube download
        
        Args:
            url: YouTube URL
            preferred_quality: Preferred video quality
            on_progress: Optional progress callback
            threads: Number of threads to use for download
            
        Raises:
            InvalidURLError: If URL is invalid
            YouTubeError: If YouTube download fails
        """
        try:
            # Clean URL before creating downloader
            url = url.strip() if url else ""
            if not url:
                raise InvalidURLError("URL cannot be empty")
                
            # Create YouTube downloader
            downloader = YouTubeDownloader(
                url, 
                self.download_dir,
                preferred_quality=preferred_quality,
                threads=min(threads, Config.MAX_THREADS)
            )
            
            # Set progress callback if provided
            if on_progress:
                downloader.set_progress_callback(on_progress)
                
            # Set completion callback
            downloader.set_completion_callback(self._on_download_complete)
                
            # Store download object
            self.active_downloads[url] = downloader
            
            # Start download
            downloader.start()
            
        except InvalidURLError as e:
            raise
            
        except YouTubeError as e:
            raise
            
        except Exception as e:
            error_msg = f"Failed to start YouTube download: {str(e)}"
            raise YouTubeError(error_msg)

    def cancel_download(self, download_id: str) -> None:
        """Cancel a download by its ID"""
        try:
            downloader = self.active_downloads.get(download_id)
            if not downloader:
                return
                
            # Cancel the download
            downloader.cancel()
            
            # Remove from active downloads immediately
            self.active_downloads.pop(download_id, None)
            
            # Notify UI that download is cancelled
            if hasattr(downloader, 'progress_callback') and downloader.progress_callback:
                try:
                    downloader.progress_callback(download_id, 0, "", "Download cancelled")
                except Exception as e:
                    pass
                
        except Exception as e:
            raise DownloaderError(f"Failed to cancel download: {e}")

    def cancel_all(self) -> None:
        """Cancel all active downloads"""
        self._stop_flag = True
        active_downloads = list(self.active_downloads.keys())  # Create a copy of keys
        for download_id in active_downloads:
            self.cancel_download(download_id)
        self._stop_flag = False

    def get_download_status(self, download_id: str) -> Optional[Dict]:
        """Get the status of a download
        
        Args:
            download_id: ID of the download
            
        Returns:
            Optional[Dict]: Dictionary containing download status information
                {
                    'status': str ('downloading', 'completed', 'error', 'cancelled'),
                    'display_name': str,
                    'color': str,
                    'error': Optional[str]
                }
        """
        if download_id not in self.active_downloads:
            return None
            
        downloader = self.active_downloads[download_id]
        display_name = downloader.url if hasattr(downloader, 'url') else str(download_id)
        
        # Default status
        status = {
            'status': downloader.status if hasattr(downloader, 'status') else 'downloading',
            'display_name': display_name,
            'color': '#4a90e2',  # Default blue color
            'error': None
        }
        
        # Check for error
        if hasattr(downloader, 'error_message') and downloader.error_message:
            status['status'] = 'error'
            status['error'] = downloader.error_message
            status['color'] = '#e74c3c'  # Red for error
            
        # Check for completion
        elif hasattr(downloader, 'completed') and downloader.completed:
            status['status'] = 'completed'
            status['color'] = '#2ecc71'  # Green for completed
            
        # Check for cancellation
        elif hasattr(downloader, '_cancelled') and downloader._cancelled:
            status['status'] = 'cancelled'
            status['color'] = '#95a5a6'  # Gray for cancelled
            
        return status

    def _on_download_complete(self, download_id: str) -> None:
        """Handle download completion
        
        Args:
            download_id: ID of the completed download
        """
        # For YouTube downloads, only complete if both video and audio are done
        if "_video" in download_id or "_audio" in download_id:
            base_id = download_id.rsplit('_', 1)[0]
            if base_id in self.active_downloads:
                # Don't remove until both components are done
                return
                
        # Remove from active downloads
        self.active_downloads.pop(download_id, None)

    def _progress_callback(self, download_id: str, progress: float, speed: str = "", 
                         text: str = "", total_size: int = 0, downloaded_size: int = 0,
                         is_youtube: bool = False, is_audio: bool = False) -> None:
        """Progress callback for downloads"""
        if self.progress_callback:
            self.progress_callback(
                download_id, 
                progress, 
                speed, 
                text, 
                total_size, 
                downloaded_size,
                is_youtube=is_youtube,
                is_audio=is_audio
            )
