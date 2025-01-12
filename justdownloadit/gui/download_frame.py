import tkinter as tk
import customtkinter as ctk
from typing import Dict, Callable
from .progress_bar import DownloadProgressBar
import logging

class DownloadFrame(ctk.CTkScrollableFrame):
    """Frame containing all download progress bars"""
    
    def __init__(self, master, *args, **kwargs):
        super().__init__(
            master,
            height=200,
            fg_color="transparent",
            corner_radius=0,
            *args,
            **kwargs
        )
        self.logger = logging.getLogger(__name__)
        
        # Dictionary to store progress bars
        self.progress_bars = {}
        
    def add_download(self, download_id: str, display_name: str, color: str, on_cancel: Callable):
        """Add a new download progress bar"""
        try:
            self.logger.debug(f"Adding progress bar for {download_id}: {display_name}")
            
            # Create new progress bar
            progress_bar = DownloadProgressBar(
                self,
                download_id=download_id,
                display_name=display_name,
                color=color,
                on_cancel=on_cancel
            )
            
            # Store progress bar
            self.progress_bars[download_id] = progress_bar
            
            # Pack progress bar
            progress_bar.pack(fill=tk.X, padx=5, pady=2)
            
            self.logger.debug(f"Progress bars after adding: {list(self.progress_bars.keys())}")
            
            # Force layout update
            self.update_idletasks()
            
        except Exception as e:
            self.logger.error(f"Failed to add progress bar for {download_id}: {e}", exc_info=True)
            
    def update_progress(self, download_id: str, progress: float, speed: str = "", text: str = "", downloaded_size: float = 0, total_size: float = 0):
        """Update progress for a specific download"""
        try:
            self.logger.debug(f"Updating progress for {download_id}: {progress}% at {speed}")
            
            if download_id in self.progress_bars:
                progress_bar = self.progress_bars[download_id]
                progress_bar.update_progress(progress, speed, text, downloaded_size, total_size)
            else:
                self.logger.warning(f"Progress bar not found for {download_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to update progress for {download_id}: {e}", exc_info=True)
            
    def update_title(self, download_id: str, title: str):
        """Update the title for a specific download"""
        try:
            self.logger.debug(f"Updating title for {download_id} to {title}")
            if download_id in self.progress_bars:
                progress_bar = self.progress_bars[download_id]
                progress_bar.update_title(title)
            else:
                self.logger.warning(f"Progress bar not found for {download_id}")
        except Exception as e:
            self.logger.error(f"Failed to update title for {download_id}: {e}", exc_info=True)
            
    def remove_download(self, download_id: str):
        """Remove a download progress bar"""
        try:
            self.logger.debug(f"Removing progress bar for {download_id}")
            
            if download_id in self.progress_bars:
                progress_bar = self.progress_bars[download_id]
                progress_bar.destroy()
                del self.progress_bars[download_id]
                self.logger.debug(f"Progress bars after removing: {list(self.progress_bars.keys())}")
            else:
                self.logger.warning(f"Progress bar not found for {download_id}")
                
        except Exception as e:
            self.logger.error(f"Failed to remove progress bar for {download_id}: {e}", exc_info=True)
            
    def clear_downloads(self):
        """Remove all download progress bars"""
        try:
            self.logger.debug("Clearing all progress bars")
            
            for download_id in list(self.progress_bars.keys()):
                self.remove_download(download_id)
                
        except Exception as e:
            self.logger.error(f"Failed to clear progress bars: {e}", exc_info=True)

    def clear_all_downloads(self):
        """Remove all download progress bars"""
        try:
            # Get a list of all download IDs first to avoid modifying dict during iteration
            download_ids = list(self.progress_bars.keys())
            for download_id in download_ids:
                self.remove_download(download_id)
        except Exception as e:
            self.logger.error(f"Error clearing downloads: {e}")
            raise
