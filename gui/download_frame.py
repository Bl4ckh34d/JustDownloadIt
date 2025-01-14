"""
Download progress display frame for JustDownloadIt.

This module provides the DownloadFrame class which manages multiple download progress bars.
It handles both regular downloads and YouTube downloads with their specific progress displays.

Features:
    - Progress bar management for multiple simultaneous downloads
    - Support for YouTube downloads with separate video/audio progress
    - Cancel/Clear functionality for each download
    - Dynamic progress updates with speed and ETA

Classes:
    DownloadFrame: Scrollable frame that manages multiple progress bars

Dependencies:
    - customtkinter: Modern themed tkinter widgets
    - core.download_state: Download state tracking
    - gui.progress_bar: Individual progress bar widget
    - gui.progress_bar_yt: YouTube-specific progress bar widget
"""

from core.download_state import DownloadState
import customtkinter as ctk
import os
from typing import Callable, Optional
from .progress_bar import ProgressBar
from .progress_bar_yt import YouTubeProgressBar

class DownloadFrame(ctk.CTkScrollableFrame):
    """Frame to hold download progress bars"""
    
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            height=200,
            fg_color="transparent",
            corner_radius=0,
            **kwargs
        )
        
        # Dictionary to store regular progress bars
        self.progress_bars = {}
        # Dictionary to store YouTube progress bars by base URL
        self.youtube_bars = {}
        
    def add_download(self, download_id: str, download_type: str = "regular", audio_only: bool = False, 
                    is_youtube: bool = False, is_audio: bool = False) -> Optional[ProgressBar]:
        """
        Add a new download progress bar.
        
        Args:
            download_id: Unique identifier for the download
            download_type: Type of download ("regular" or "youtube")
            audio_only: Whether this is an audio-only download
            is_youtube: Whether this is a YouTube download
            is_audio: Whether this is an audio stream
            
        Returns:
            ProgressBar: The created progress bar, or None if already exists
        """
        if download_id in self.progress_bars or download_id in self.youtube_bars:
            return None
            
        # Create cancel callback that calls the app's cancel method
        def cancel_callback(*args):
            if hasattr(self, 'on_cancel'):
                self.on_cancel(download_id)
                
        # Handle both parameter styles
        is_youtube = is_youtube or download_type == "youtube"
        is_audio = is_audio or audio_only
            
        if is_youtube:
            youtube_bar = YouTubeProgressBar(
                self, 
                download_id=download_id,
                cancel_callback=cancel_callback,
                audio_only=is_audio
            )
            self.youtube_bars[download_id] = youtube_bar
            youtube_bar.pack(fill="x", padx=5, pady=2)
            return youtube_bar
        else:
            progress_bar = ProgressBar(
                self, 
                download_id=download_id,
                cancel_callback=cancel_callback
            )
            progress_bar.pack(fill="x", padx=5, pady=5)
            self.progress_bars[download_id] = progress_bar
            return progress_bar
            
    def update_progress(self, download_id: str, progress: float, state: DownloadState, 
                       speed: str = "", text: str = "", total_size: float = 0, 
                       downloaded_size: float = 0, stats: dict = None,
                       component: str = None) -> None:
        """
        Update the progress of a download.
        
        Args:
            download_id (str): ID of the download to update
            progress (float): Current progress (0-100)
            state (DownloadState): Current download state
            speed (str, optional): Current download speed. Defaults to "".
            text (str, optional): Text to display. Defaults to "".
            total_size (float, optional): Total file size in bytes. Defaults to 0.
            downloaded_size (float, optional): Downloaded size in bytes. Defaults to 0.
            stats (dict, optional): Dictionary of download statistics. Defaults to None.
            component (str, optional): For YouTube downloads, specifies "video" or "audio". Defaults to None.
        """
        print(f"Update progress called for download_id: {download_id}, progress: {progress}, component: {component}")
        print(f"Progress bars: {list(self.progress_bars.keys())}")
        print(f"YouTube bars: {list(self.youtube_bars.keys())}")
        
        if download_id in self.progress_bars:
            print(f"Updating regular progress bar for {download_id}")
            progress_bar = self.progress_bars[download_id]
            try:
                # Set filepath only if it's a valid absolute path
                if text and os.path.isabs(text):
                    progress_bar.set_filepath(text)
                
                progress_bar._update_progress(
                    progress=progress,
                    speed=speed,
                    text="Download complete" if state == DownloadState.COMPLETED else text,
                    total_size=total_size,
                    downloaded_size=downloaded_size,
                    stats=stats,
                    state=state
                )
            except Exception as e:
                print(f"Error updating progress: {e}")
                
        elif download_id in self.youtube_bars:
            print(f"Updating YouTube progress bar for {download_id} ({component})")
            youtube_bar = self.youtube_bars[download_id]
            try:
                youtube_bar.update_progress(
                    text=text,
                    progress=progress,
                    component=component,
                    speed=speed,
                    downloaded_size=downloaded_size,
                    total_size=total_size,
                    stats=stats
                )
                
                # Update state if needed
                if state == DownloadState.COMPLETED:
                    youtube_bar.action_button.configure(
                        text="Open",
                        command=lambda: youtube_bar._open_file(text if os.path.isabs(text) else None)
                    )
                
            except Exception as e:
                print(f"Error updating progress: {e}")
                
    def remove_download(self, download_id: str) -> None:
        """
        Remove a download progress bar from the frame.
        
        Args:
            download_id (str): ID of the download to remove
        """
        try:
            # For YouTube downloads, check both dictionaries
            if download_id in self.youtube_bars:
                progress_bar = self.youtube_bars[download_id]
                
                # Remove all component mappings
                for component_id, base_id in list(self.progress_bars.items()):
                    if base_id == download_id:
                        del self.progress_bars[component_id]
                
                # Remove the progress bar
                progress_bar.pack_forget()
                progress_bar.destroy()
                del self.youtube_bars[download_id]
                
            elif download_id in self.progress_bars:
                progress_bar = self.progress_bars[download_id]
                progress_bar.pack_forget()
                progress_bar.destroy()
                del self.progress_bars[download_id]
            else:
                print(f"No progress bar found for {download_id}")
                
        except Exception as e:
            print(f"Error clearing download frame: {str(e)}")
