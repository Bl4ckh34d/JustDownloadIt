"""
Download frame for displaying active downloads.
"""

import customtkinter as ctk
import tkinter as tk
from typing import Dict, Optional, Callable
from core.download_state import DownloadState
from .widgets.progress_bar import ProgressBar
from .widgets.progress_bar_yt import YouTubeProgressBar
from utils.url_utils import check_link_type

class DownloadFrame(ctk.CTkScrollableFrame):
    """Frame for displaying active downloads."""
    
    def __init__(self, master, **kwargs):
        """Initialize download frame.
        
        Args:
            master: Parent widget
        """
        super().__init__(master, **kwargs)
        
        # Initialize state
        self._downloads = {}
        
    def add_download(self, download_id: str, url: str, 
                    on_cancel: Optional[Callable] = None,
                    on_close: Optional[Callable] = None,
                    audio_only: bool = False) -> None:
        """Add a new download to the frame.
        
        Args:
            download_id (str): Unique ID for the download
            url (str): URL being downloaded
            on_cancel (callable, optional): Callback when download is cancelled
            on_close (callable, optional): Callback when download is closed
            audio_only (bool, optional): Whether this is an audio-only download
        """
        # Create appropriate progress bar based on URL type and audio_only setting
        if check_link_type(url) == "youtube" and not audio_only:
            # Use YouTube progress bar for video downloads
            progress_bar = YouTubeProgressBar(
                self,
                download_id=download_id,
                on_cancel=on_cancel,
                on_close=lambda: self._on_close(download_id)
            )
        else:
            # Use regular progress bar for non-YouTube downloads and audio-only downloads
            progress_bar = ProgressBar(
                self,
                download_id=download_id,
                on_cancel=on_cancel,
                on_close=lambda: self._on_close(download_id)
            )
            
        # Store progress bar
        self._downloads[download_id] = progress_bar
        
        # Pack progress bar
        progress_bar.pack(fill="x", padx=5, pady=5)
        
    def update_download(self, download_id: str, state: DownloadState) -> None:
        """Update download progress.
        
        Args:
            download_id (str): Download ID to update
            state (DownloadState): New download state
        """
        if download_id in self._downloads:
            self._downloads[download_id].update_state(state)
            
    def _on_close(self, download_id: str) -> None:
        """Handle download close.
        
        Args:
            download_id (str): ID of download to close
        """
        if download_id in self._downloads:
            # Destroy progress bar
            self._downloads[download_id].destroy()
            # Remove from tracking
            del self._downloads[download_id]
