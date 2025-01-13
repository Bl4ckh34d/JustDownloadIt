import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable

from utils.errors import DownloaderError

class ProgressBar(ctk.CTkFrame):
    """A progress bar widget that shows download progress, speed, and file size"""
    
    def __init__(self, master, download_id: str, text: str, cancel_callback: Callable = None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.download_id = download_id
        self.display_name = self._truncate_title(text)
        self.title = self.display_name
        self.cancel_callback = cancel_callback
        self.progress = 0
        self.speed = ""
        self.total_size = 0
        self.downloaded_size = 0
        self._allow_destroy = False
        self._destroying = False
        
        # Top frame for title and cancel button
        self.top_frame = ctk.CTkFrame(self)
        self.top_frame.pack(fill=tk.X, padx=5, pady=(5,0))
        
        # Title label
        self.title_label = ctk.CTkLabel(self.top_frame, text=self.display_name, anchor="w")
        self.title_label.pack(side=tk.LEFT, padx=5, pady=2, fill=tk.X, expand=True)
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            self.top_frame,
            text="Cancel",
            width=60,
            command=self._on_cancel
        )
        self.cancel_button.pack(side=tk.RIGHT, padx=5, pady=2)
        
        # Bottom frame for progress, speed, and size info
        self.bottom_frame = ctk.CTkFrame(self)
        self.bottom_frame.pack(fill=tk.X, padx=5, pady=(0,5))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(
            self.bottom_frame,
            height=15,
            progress_color="#007bff",
            mode="determinate"
        )
        self.progress_bar.pack(fill=tk.X, padx=5, pady=(5,2), expand=True)
        self.progress_bar.set(0)
        
        # Info frame for speed and size
        self.info_frame = ctk.CTkFrame(self.bottom_frame)
        self.info_frame.pack(fill=tk.X, padx=5, pady=(0,5))
        
        # Progress percentage
        self.percent_label = ctk.CTkLabel(self.info_frame, text="0%", width=50)
        self.percent_label.pack(side=tk.LEFT, padx=5)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(self.info_frame, text="", width=100)
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        # Size info (e.g., "50 MB / 100 MB")
        self.size_label = ctk.CTkLabel(self.info_frame, text="", width=150)
        self.size_label.pack(side=tk.RIGHT, padx=5)
        
    def _truncate_title(self, title: str, max_length: int = 120) -> str:
        """Truncate title to specified length"""
        if len(title) <= max_length:
            return title
        return title[:max_length-3] + "..."
        
    def _on_cancel(self):
        """Handle cancel button click"""
        try:
            if self.cancel_callback:
                self.cancel_button.configure(state="disabled")
                self.cancel_callback()
        except Exception as e:
            print(f"Error in cancel callback: {e}")
            
    def _format_size(self, size_bytes: float) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"
            
    def update_progress(self, progress: float, speed: str = "", text: str = None,
                       total_size: float = None, downloaded_size: float = None):
        """Update progress bar and all labels"""
        try:
            # If text indicates completion, ensure progress is 100%
            if text and "(Complete)" in text:
                progress = 100.0
            else:
                # Otherwise clamp progress between 0-100
                progress = min(100, max(0, progress))
                
            self.progress = progress
            self.progress_bar.set(progress / 100)
            self.percent_label.configure(text=f"{progress:.1f}%")
            
            # Update speed if provided
            if speed:
                self.speed_label.configure(text=speed)
                
            # Update size info if provided
            if total_size is not None and downloaded_size is not None:
                size_text = f"{self._format_size(downloaded_size)} / {self._format_size(total_size)}"
                self.size_label.configure(text=size_text)
                
            # Update text/title if provided
            if text:
                self.title_label.configure(text=self._truncate_title(text))
                
            # Force update
            self.update_idletasks()
            
        except Exception as e:
            print(f"Error updating progress bar: {e}")
            
    def destroy(self):
        """Override destroy to handle cleanup"""
        try:
            if self._allow_destroy:
                super().destroy()
            self._destroying = True
        except Exception as e:
            print(f"Error destroying progress bar: {e}")
            
    def allow_destroy(self):
        """Allow the widget to be destroyed"""
        self._allow_destroy = True
        if self._destroying:
            try:
                super().destroy()
            except Exception as e:
                print(f"Error in allow_destroy: {e}")
                
class DownloadFrame(ctk.CTkFrame):
    """Frame to manage download progress bars"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.progress_bars = {}  # Store progress bars by download ID
        
    def add_download(self, download_id: str, text: str = "", cancel_callback: Callable = None):
        """Add a new download progress bar
        
        Args:
            download_id: Unique identifier for the download
            text: Text to display in the progress bar
            cancel_callback: Callback function when cancel is clicked
            
        Returns:
            The created progress bar or None if it already exists
        """
        # Don't create duplicate progress bars
        if download_id in self.progress_bars:
            return None
            
        # Create progress bar
        progress_bar = ProgressBar(
            master=self,
            download_id=download_id,
            text=text,
            cancel_callback=cancel_callback
        )
        progress_bar.pack(fill=tk.X, padx=5, pady=5)
        
        # Store progress bar
        self.progress_bars[download_id] = progress_bar
        return progress_bar
        
    def update_progress(self, download_id: str, progress: float, speed: str = "", 
                       text: str = None, total_size: float = None, downloaded_size: float = None):
        """Update progress bar and labels"""
        if download_id in self.progress_bars:
            progress_bar = self.progress_bars[download_id]
            progress_bar.update_progress(
                progress=progress,
                speed=speed,
                text=text,
                total_size=total_size,
                downloaded_size=downloaded_size
            )
            
    def remove_download(self, download_id: str):
        """Remove a download progress bar"""
        if download_id in self.progress_bars:
            progress_bar = self.progress_bars[download_id]
            progress_bar.destroy()
            del self.progress_bars[download_id]
