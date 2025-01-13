import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable
import os
from tkinter import messagebox
from utils.errors import DownloaderError

class ProgressBar(ctk.CTkFrame):
    """A progress bar widget that shows download progress, speed, and file size"""
    
    def __init__(self, master, download_id: str, text: str = "", cancel_callback: Callable = None):
        """Initialize progress bar frame"""
        super().__init__(master)
        
        self.download_id = download_id
        self.cancel_callback = cancel_callback
        self.progress = 0
        self.filepath = None  # Store filepath for opening later
        
        # Create main content frame
        self.content = ctk.CTkFrame(self)
        self.content.pack(fill=tk.X, expand=True, padx=5, pady=2)
        
        # Create top row with title and close button
        self.top_row = ctk.CTkFrame(self.content)
        self.top_row.pack(fill=tk.X, padx=5, pady=(2,0))
        
        # Title label (left-aligned)
        self.title_label = ctk.CTkLabel(self.top_row, text=self._truncate_title(text))
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Close button (right-aligned, small red X)
        self.close_button = ctk.CTkButton(self.top_row, text="×", width=20, height=20, 
                                        fg_color="red", hover_color="darkred",
                                        command=self._on_close)
        self.close_button.pack(side=tk.RIGHT, padx=(5,0))
        
        # Create bottom frame for progress info
        self.bottom_frame = ctk.CTkFrame(self.content)
        self.bottom_frame.pack(fill=tk.X, padx=5, pady=(0,2))
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.bottom_frame)
        self.progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0,5))
        self.progress_bar.set(0)
        
        # Right side frame for labels and button
        self.right_frame = ctk.CTkFrame(self.bottom_frame)
        self.right_frame.pack(side=tk.RIGHT)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(self.right_frame, text="0 MB/s")
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        # Size label
        self.size_label = ctk.CTkLabel(self.right_frame, text="0 MB")
        self.size_label.pack(side=tk.LEFT, padx=5)
        
        # Percent label
        self.percent_label = ctk.CTkLabel(self.right_frame, text="0%")
        self.percent_label.pack(side=tk.LEFT, padx=5)
        
        # Cancel/Open button (smaller)
        self.cancel_button = ctk.CTkButton(self.right_frame, text="Cancel", 
                                         command=self._on_cancel,
                                         width=60, height=25)  # Reduced size
        self.cancel_button.pack(side=tk.LEFT, padx=5)
        
    def _truncate_title(self, title: str, max_length: int = 120) -> str:
        """Truncate title to specified length"""
        if len(title) <= max_length:
            return title
        return title[:max_length-3] + "..."
        
    def _on_cancel(self):
        """Handle cancel button click"""
        try:
            if self.cancel_callback:
                # Disable the button immediately to prevent multiple clicks
                self.cancel_button.configure(state="disabled")
                # Call the cancel callback
                self.cancel_callback(self.download_id)
                # Destroy the progress bar after a short delay
                self.after(500, self.destroy)
        except Exception as e:
            print(f"Error in cancel callback: {e}")
            
    def _on_close(self):
        """Handle close button click"""
        try:
            if self.cancel_callback and self.progress < 100:
                # If download is in progress, cancel it
                self.cancel_callback(self.download_id)
            # Remove the progress bar after a short delay
            self.after(500, self.destroy)
        except Exception as e:
            print(f"Error in close: {e}")
            
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
                # Change cancel button to open
                self.cancel_button.configure(text="Open", command=self._on_open)
                # Store filepath from the text
                if text and "Saved to:" in text:
                    self.filepath = text.split("Saved to:", 1)[1].strip()
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
            
    def _on_open(self):
        """Open the downloaded file"""
        if self.filepath:
            try:
                os.startfile(self.filepath)
            except Exception as e:
                print(f"Error opening file: {e}")
                messagebox.showerror("Error", f"Could not open file: {e}")
                
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
