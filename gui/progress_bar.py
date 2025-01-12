import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable

from utils.errors import DownloaderError

class ProgressBar(ctk.CTkFrame):
    """A basic progress bar widget for downloads"""
    
    def __init__(self, master, download_id: str, display_name: str, color: str = "#007bff", on_cancel: Callable = None, **kwargs):
        super().__init__(master, **kwargs)
        
        self.download_id = download_id
        self.display_name = display_name
        self.title = display_name  # Store original title
        self.on_cancel = on_cancel
        
        # Create main label frame
        self.label_frame = ctk.CTkFrame(self)
        self.label_frame.pack(fill=tk.X, padx=5, pady=(5,0))
        
        # Progress label (shows filename/status)
        self.label = ctk.CTkLabel(self.label_frame, text="", anchor="w", width=250)
        self.label.pack(side=tk.LEFT, padx=5)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(self.label_frame, text="", width=150)
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(self.label_frame, text="✕", width=20, height=20, font=("Arial", 12, "bold"), fg_color="#dc3545", hover_color="#c82333")
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # Progress bar
        self.progress_frame = ctk.CTkFrame(self)
        self.progress_frame.pack(fill=tk.X, padx=5, pady=5)
        
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, width=200, height=15, progress_color=color, mode="determinate", corner_radius=5)
        self.progress_bar.pack(fill=tk.X, padx=5, expand=True)
        self.progress_bar.set(0)
        
        self.set_cancel_callback(self._on_cancel)
        
    def _on_cancel(self):
        """Handle cancel button click"""
        if self.on_cancel:
            self.cancel_button.configure(state="disabled")  # Disable button
            self.on_cancel()
            
    def set_cancel_callback(self, callback):
        """Set callback for cancel button"""
        self.cancel_button.configure(command=callback)
        
    def update(self, progress: float, speed: str = "", text: str = "", 
               total_size: int = 0, downloaded_size: int = 0):
        """Update progress bar state
        
        Args:
            progress: Progress percentage (0-100)
            speed: Download speed string
            text: Status text
            total_size: Total file size in bytes
            downloaded_size: Downloaded size in bytes
        """
        try:
            # Update progress bar
            progress_value = min(max(float(progress) / 100.0, 0.0), 1.0)
            self.progress_bar.set(progress_value)
            
            # Update status text
            status = text
            if total_size > 0:
                downloaded_str = self._format_size(downloaded_size)
                total_str = self._format_size(total_size)
                status += f" ({progress:.1f}% - {downloaded_str}/{total_str})"
            self.label.configure(text=status)
            
            # Update speed
            if speed:
                self.speed_label.configure(text=speed)
                
        except Exception as e:
            # Don't re-raise, just ignore the error to avoid crashing the GUI
            print()
            
    def _format_size(self, size: float) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
        
    def update_title(self, title: str):
        """Update the title/name of the progress bar
        
        Args:
            title: New title to display
        """
        try:
            # Format title based on download type
            display_title = f"{title} (Audio)" if "_audio" in self.download_id else title
            self.title = display_title  # Store full title
            self.label.configure(text=display_title)
        except Exception as e:
            # Don't re-raise, just ignore the error to avoid crashing the GUI
            print()


class DownloadFrame(ctk.CTkFrame):
    def __init__(self, master, progress_thickness=5, **kwargs):
        super().__init__(master, **kwargs)
        
        self.progress_thickness = progress_thickness
        self.progress_bars = {}
        self.next_bar_id = 0
        
    def add_download(self, download_id: str, display_name: str, color: str, on_cancel: Callable):
        """Add a new download progress bar"""
        try:
            # Create progress bar with cancel callback
            progress_bar = ProgressBar(
                self,
                download_id=download_id,
                display_name=display_name,
                color=color,
                on_cancel=lambda: self._on_cancel(download_id)
            )
            progress_bar.pack(fill=tk.X, padx=5, pady=2)
            
            # Store progress bar
            self.progress_bars[download_id] = progress_bar
            self.next_bar_id += 1
            
        except Exception as e:
            # Don't re-raise, just ignore the error to avoid crashing the GUI
            print()
            
    def _on_cancel(self, download_id: str):
        """Handle cancel button click"""
        try:
            if hasattr(self.master, '_cancel_download'):
                self.master._cancel_download(download_id)
        except Exception as e:
            # Don't re-raise, just ignore the error to avoid crashing the GUI
            print()
            
    def update_progress(self, download_id: str, progress: float, speed: str = "", text: str = "", total_size: float = 0, downloaded_size: float = 0):
        """Update progress bar and labels"""
        if download_id in self.progress_bars:
            self.progress_bars[download_id].update(progress, speed, text, total_size, downloaded_size)
            
    def update_title(self, download_id: str, title: str):
        """Update the title of a progress bar
        
        Args:
            download_id: ID of the download progress bar to update
            title: New title to display
        """
        if download_id in self.progress_bars:
            try:
                self.progress_bars[download_id].update_title(title)
            except Exception as e:
                # Don't re-raise, just ignore the error to avoid crashing the GUI
                print()
                
    def remove_download(self, download_id: str):
        """Remove a download progress bar"""
        if download_id in self.progress_bars:
            self.progress_bars[download_id].destroy()
            del self.progress_bars[download_id]
