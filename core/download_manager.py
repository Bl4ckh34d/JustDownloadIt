"""
Download manager for JustDownloadIt.

This module provides the DownloadManager class which manages all download operations.
It handles both regular downloads and YouTube downloads, providing a unified interface
for progress tracking and download management.

Features:
    - Multi-threaded downloads with configurable thread count
    - YouTube video downloads with quality selection
    - Progress tracking and callback system
    - Download cancellation and cleanup
    - Error handling and retry logic
    - Unified download ID generation
    - Active download tracking

Classes:
    DownloadManager: Main class that manages all download operations

Dependencies:
    - core.downloader: Base download functionality
    - core.youtube: YouTube download handling
    - core.config: Application configuration
    - core.download_state: Download state tracking
    - utils.errors: Error handling utilities
"""

from pathlib import Path
from typing import Optional, Callable, Dict, List, Union, Set
from queue import Queue
import threading
import re
import uuid
from urllib.error import URLError as BuiltinURLError
import logging

from utils.errors import (
    NetworkError, DownloaderError, URLError, 
    InvalidURLError, UnsupportedURLError, YouTubeError
)
from utils.url_utils import check_link_type, clean_url
from .config import Config
from .regular_downloader import Downloader
from .youtube_downloader import YouTubeDownloader
from .download_state import DownloadState, DownloadProgress

class DownloadTracker:
    """Tracks active downloads and their IDs."""
    
    def __init__(self):
        self._url_to_id: Dict[str, str] = {}
        self._active_downloads: Dict[str, Union[Downloader, YouTubeDownloader]] = {}
        
    def add_download(self, url: str, download_id: str, downloader: Union[Downloader, YouTubeDownloader]) -> None:
        """Add a new download and generate its ID."""
        self._url_to_id[url] = download_id
        self._active_downloads[download_id] = downloader
        
    def remove_download(self, download_id: str) -> None:
        """Remove a download from tracking."""
        if download_id in self._active_downloads:
            url = next((url for url, id_ in self._url_to_id.items() if id_ == download_id), None)
            if url:
                del self._url_to_id[url]
            del self._active_downloads[download_id]
            
    def get_downloader(self, download_id: str) -> Optional[Union[Downloader, YouTubeDownloader]]:
        """Get downloader instance by ID."""
        return self._active_downloads.get(download_id)
        
    def is_url_active(self, url: str) -> bool:
        """Check if URL is being downloaded."""
        return url in self._url_to_id
        
    def get_active_downloads(self) -> Set[str]:
        """Get all active download IDs."""
        return set(self._active_downloads.keys())
        
    def _generate_id(self, url: str) -> str:
        """Generate unique download ID."""
        base_id = str(uuid.uuid4())
        return f"{base_id}_yt" if check_link_type(url) == 'youtube' else base_id

class DownloadManager:
    """Manages download operations."""
    
    def __init__(self, download_dir: Optional[Path] = None):
        """Initialize the download manager."""
        self.download_dir = Config.DOWNLOAD_DIR if download_dir is None else Path(download_dir)
        self.download_dir.mkdir(parents=True, exist_ok=True)
        
        self.tracker = DownloadTracker()
        self.download_queue = Queue()
        self.thread_pool = []
        self._stop_flag = False
        self.progress_callback = None
        self.logger = logging.getLogger(__name__)
        
    def start_download(self, url: str, **kwargs) -> str:
        """Start a new download.
        
        Args:
            url (str): URL to download
            **kwargs: Additional download options
            
        Returns:
            str: Download ID
        """
        try:
            # Generate download ID if not provided
            download_id = kwargs.pop('download_id', self.generate_download_id(url))
            
            # Get or create downloader
            downloader = kwargs.pop('downloader', None)
            if not downloader:
                # Create regular downloader for non-YouTube URLs
                downloader = Downloader(
                    url=url,
                    download_dir=self.download_dir,
                    threads=kwargs.pop('threads', Config.DEFAULT_THREADS)
                )
            
            # Set callbacks
            if 'progress_callback' in kwargs:
                downloader.set_progress_callback(kwargs['progress_callback'])
            
            # Store in tracker
            self.tracker.add_download(url, download_id, downloader)
            
            # Start download in a new thread
            thread = threading.Thread(
                target=downloader.start,
                name=f"download-{download_id}"
            )
            thread.daemon = True
            thread.start()
            self.thread_pool.append(thread)
            
            return download_id
            
        except Exception as e:
            self.logger.error(f"Error starting download: {e}")
            raise
        
    def cancel_download(self, download_id: str) -> None:
        """Cancel a download by ID."""
        downloader = self.tracker.get_downloader(download_id)
        if downloader:
            downloader.cancel()
            self.tracker.remove_download(download_id)
            
    def set_progress_callback(self, callback: Callable) -> None:
        """Set callback for progress updates."""
        self.progress_callback = callback
        
    def _handle_progress(self, download_id: str, progress: DownloadProgress) -> None:
        """Handle progress updates from downloaders."""
        if self.progress_callback:
            self.progress_callback(download_id, progress)
            
    def shutdown(self) -> None:
        """Shutdown the download manager."""
        self._stop_flag = True
        for download_id in self.tracker.get_active_downloads():
            self.cancel_download(download_id)
            
    def get_active_downloads(self) -> Set[str]:
        """Get set of active download IDs."""
        return self.tracker.get_active_downloads()
        
    def is_url_downloading(self, url: str) -> bool:
        """Check if a URL is currently being downloaded."""
        return self.tracker.is_url_active(url)
        
    def get_download_id_for_url(self, url: str) -> Optional[str]:
        """Get download ID for a URL if it exists."""
        return self.tracker._url_to_id.get(url)

    def get_download_status(self, download_id: str) -> Optional[Dict]:
        """Get the status of a download.
        
        Args:
            download_id (str): ID of the download
            
        Returns:
            Optional[Dict]: Dictionary containing download status information
                {
                    'status': str ('downloading', 'completed', 'error', 'cancelled'),
                    'display_name': str,
                    'color': str,
                    'error': Optional[str]
                }
        """
        if download_id not in self.tracker._active_downloads:
            return None
            
        downloader = self.tracker._active_downloads[download_id]
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
        """
        Handle download completion.
        
        Args:
            download_id (str): ID of completed download
        """
        # For YouTube downloads, only complete if both video and audio are done
        if "_video" in download_id or "_audio" in download_id:
            base_id = download_id.rsplit('_', 1)[0]
            if base_id in self.tracker._active_downloads:
                # Don't remove until both components are done
                return
        
        # Get the downloader before removing it
        downloader = self.tracker._active_downloads.get(download_id)
        if downloader and hasattr(downloader, '_progress_callback') and downloader._progress_callback:
            # Send one final progress update to ensure UI is updated
            downloader._progress_callback(
                download_id,
                100.0,
                "",
                "Download complete",
                0,
                0,
                None,
                DownloadState.COMPLETED  # Fixed: Pass the correct state
            )
                
        # Remove from active downloads
        self.tracker.remove_download(download_id)

    def _progress_callback(self, download_id: str, progress: float = None, speed: str = None,
                         text: str = None, total_size: int = None,
                         downloaded_size: int = None, stats: Dict = None,
                         state: DownloadState = None, component: str = None,
                         error: str = None):
        """Handle progress updates from downloaders."""
        try:
            # Update download state
            if not download_id:
                return
                
            self.logger.info(f"Progress update for {download_id}: {progress:.1f}% ({component})")
                
            # Forward progress to GUI callback if set
            if self.progress_callback:
                self.progress_callback(
                    download_id=download_id,
                    progress=progress,
                    speed=speed,
                    text=text,
                    total_size=total_size,
                    downloaded_size=downloaded_size,
                    stats=stats,
                    state=state,
                    component=component,
                    error=error
                )
        except Exception as e:
            self.logger.error(f"Error in progress callback: {e}")
            
    def cancel_all(self) -> None:
        """
        Cancel all active downloads.
        """
        self._stop_flag = True
        active_downloads = list(self.tracker.get_active_downloads())  # Create a copy of keys
        for download_id in active_downloads:
            self.cancel_download(download_id)
        self._stop_flag = False

    def generate_download_id(self, url: str) -> str:
        """Generate a unique download ID for a URL.
        
        If the URL is already being downloaded, returns its existing ID.
        Otherwise, generates a new unique ID.
        
        Args:
            url: URL to generate ID for
            
        Returns:
            str: Download ID
        """
        # Check if URL is already being downloaded
        existing_id = self.tracker._url_to_id.get(url)
        if existing_id:
            return existing_id
            
        # Generate new unique ID
        return str(uuid.uuid4())

    def download_youtube(self, url: str, quality: str = None, audio_quality: str = None,
                        audio_only: bool = False, threads: int = 4,
                        progress_callback: Callable = None) -> str:
        """Download a YouTube video.
        
        Args:
            url (str): YouTube URL
            quality (str, optional): Video quality. Defaults to None.
            audio_quality (str, optional): Audio quality. Defaults to None.
            audio_only (bool, optional): Download audio only. Defaults to False.
            threads (int, optional): Number of download threads. Defaults to 4.
            progress_callback (Callable, optional): Progress callback function. Defaults to None.
            
        Returns:
            str: Download ID
        """
        try:
            # Generate download ID
            download_id = self.generate_download_id(url)
            
            # Format preferred quality string
            quality = quality or "1080p"
            audio_quality = audio_quality or "160k"
            preferred_quality = f"{quality} + {audio_quality}"
            
            # Create YouTube downloader
            downloader = YouTubeDownloader(
                url=url,
                download_dir=str(self.download_dir),
                preferred_quality=preferred_quality,
                threads=threads,
                audio_only=audio_only
            )
            
            # Set callbacks
            if progress_callback:
                downloader.set_progress_callback(progress_callback)
            
            # Start download
            self.start_download(url, downloader=downloader)
            
            return download_id
            
        except Exception as e:
            self.logger.error(f"Error downloading YouTube video: {e}")
            raise
