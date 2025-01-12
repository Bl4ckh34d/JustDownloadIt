import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable
import logging

from ..utils.errors import DownloaderError
from ..utils.logger import DownloaderLogger

class DownloadProgressBar(ctk.CTkFrame):
    def __init__(self, master, download_id: str, display_name: str, color: str = "#007bff", on_cancel: Callable = None):
        """Initialize progress bar frame"""
        super().__init__(master)
        
        self.download_id = download_id
        self.display_name = display_name
        self.title = display_name  # Store original title
        self.on_cancel = on_cancel
        self.logger = DownloaderLogger.get_logger()
        
        # Configure grid weights
        self.grid_columnconfigure(0, weight=1)  # Progress bar expands
        self.grid_columnconfigure(1, weight=0)  # Speed label fixed width
        self.grid_columnconfigure(2, weight=0)  # Cancel button fixed width
        self.grid_columnconfigure(3, weight=0)  # Cancel button fixed width
        self.grid_columnconfigure(4, weight=0)  # Cancel button fixed width
        self.grid_columnconfigure(5, weight=0)  # Cancel button fixed width
        
        # Create name label (top row)
        truncated_name = self._truncate_name(display_name, max_length=128)  # Use first 128 chars of title
        self.name_label = ctk.CTkLabel(
            self,
            text=truncated_name,
            anchor="w",
            font=("Arial", 11),
            wraplength=600  # Allow wrapping for long titles
        )
        self.name_label.grid(row=0, column=0, columnspan=6, padx=(5, 5), pady=(5, 2), sticky="w")
        
        # Create progress bar (middle row)
        self.progress_bar = ctk.CTkProgressBar(
            self,
            width=200,
            height=15,
            progress_color=color,
            mode="determinate",
            corner_radius=5
        )
        self.progress_bar.set(0)
        self.progress_bar.grid(row=1, column=0, columnspan=6, padx=(5, 5), pady=(1, 1), sticky="ew")
        
        # Redesign progress bar layout for a more compact and symmetric appearance
        self.grid_columnconfigure(0, weight=1)  # Status label
        self.grid_columnconfigure(1, weight=1)  # Percentage label
        self.grid_columnconfigure(2, weight=1)  # Speed label
        self.grid_columnconfigure(3, weight=0)  # Cancel button

        # Adjust grid weights for symmetrical alignment
        self.grid_columnconfigure(0, weight=1)  # Status label
        self.grid_columnconfigure(1, weight=1)  # Percentage label
        self.grid_columnconfigure(2, weight=1)  # Speed label

        # Create status label (bottom row, left)
        self.status_label = ctk.CTkLabel(
            self,
            text="[ 0 MB / 0 MB ]",
            anchor="center",
            font=("Arial", 11)
        )
        self.status_label.grid(row=2, column=0, padx=(5, 5), pady=(1, 1), sticky="ew")

        # Create percentage label (bottom row, center)
        self.percentage_label = ctk.CTkLabel(
            self,
            text="000.0%",
            anchor="center",
            font=("Arial", 11)
        )
        self.percentage_label.grid(row=2, column=1, padx=(5, 5), pady=(1, 1), sticky="ew")

        # Create speed label (bottom row, right)
        self.speed_label = ctk.CTkLabel(
            self,
            text="0 MB/s",
            anchor="center",
            font=("Arial", 11)
        )
        self.speed_label.grid(row=2, column=2, padx=(5, 5), pady=(1, 1), sticky="ew")

        # Create cancel button (bottom row, far right)
        self.cancel_btn = ctk.CTkButton(
            self,
            text="✕",
            width=20,
            height=20,
            command=self._on_cancel,
            font=("Arial", 12, "bold"),
            fg_color="#dc3545",
            hover_color="#c82333"
        )
        self.cancel_btn.grid(row=2, column=3, padx=(5, 5), pady=(1, 1), sticky="e")
        
    def _truncate_name(self, name: str, max_length: int = 128) -> str:
        """Truncate name if longer than max_length characters"""
        return name[:max_length] + "..." if len(name) > max_length else name
        
    def _format_status(self, name: str, speed: str, percentage: float) -> str:
        """Format the status text with name, speed, and percentage"""
        return f"{name} {speed} {percentage:.1f}%"
        
    def _on_cancel(self):
        """Handle cancel button click"""
        if self.on_cancel:
            self.cancel_btn.configure(state="disabled")  # Disable button
            self.on_cancel()
            
    def update_progress(self, progress: float, speed: str = "", text: str = "", total_size: float = 0, downloaded_size: float = 0):
        """Update progress bar and status text"""
        try:
            # Update progress bar (ensure value between 0 and 1)
            progress_value = min(max(float(progress) / 100.0, 0.0), 1.0)
            self.progress_bar.set(progress_value)
            
            # Update percentage label with consistent formatting
            formatted_percentage = f"{progress:.1f}%"
            self.percentage_label.configure(text=formatted_percentage)

            # Hide speed label if progress is 100%, otherwise show speed
            if progress >= 100:
                self.speed_label.grid_remove()  # Hide the label
            else:
                self.speed_label.grid()  # Show the label
                self.speed_label.configure(text=speed if speed else "0 MB/s")
            
            # Convert sizes from bytes to MB and format the status text
            try:
                total_size = float(total_size)
                downloaded_size = float(downloaded_size)
                if total_size > 0 and downloaded_size >= 0:
                    downloaded_mb = downloaded_size / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    status_text = f"[ {downloaded_mb:.1f} MB / {total_mb:.1f} MB ]"
                else:
                    status_text = "[ 0.0 MB / 0.0 MB ]"
            except (ValueError, TypeError):
                status_text = "[ 0.0 MB / 0.0 MB ]"
                
            self.status_label.configure(text=status_text)
            
            # Update status text if provided
            if text:
                self.name_label.configure(text=self._truncate_name(text))
                
        except Exception as e:
            self.logger.error(f"Error updating progress: {e}", exc_info=True)
            # Don't re-raise, just log the error to avoid crashing the GUI
            
    def update_title(self, title: str):
        """Update the title/name of the progress bar
        
        Args:
            title: New title to display
        """
        try:
            # Format title based on download type
            display_title = f"{title} (Audio)" if "_audio" in self.download_id else title
            truncated_name = self._truncate_name(display_title, max_length=128)
            self.title = display_title  # Store full title
            self.name_label.configure(text=truncated_name)
            self.logger.debug(f"Updated title for {self.download_id} to: {truncated_name}")
        except Exception as e:
            self.logger.error(f"Failed to update title for {self.download_id}: {e}", exc_info=True)
            raise DownloaderError(f"Failed to update progress bar title: {e}") from e


class DownloadFrame(ctk.CTkFrame):
    def __init__(self, master, progress_thickness=5, **kwargs):
        super().__init__(master, **kwargs)
        
        self.progress_thickness = progress_thickness
        self.progress_bars = {}
        self.next_bar_id = 0
        self.logger = DownloaderLogger.get_logger()
        
    def add_download(self, download_id: str, display_name: str, color: str, on_cancel: Callable):
        """Add a new download progress bar"""
        try:
            # Create progress bar with cancel callback
            progress_bar = DownloadProgressBar(
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
            self.logger.error(f"Failed to add download progress bar: {e}", exc_info=True)
            
    def _on_cancel(self, download_id: str):
        """Handle cancel button click"""
        try:
            if hasattr(self.master, '_cancel_download'):
                self.master._cancel_download(download_id)
        except Exception as e:
            self.logger.error(f"Failed to cancel download: {e}", exc_info=True)
            
    def update_progress(self, download_id: str, progress: float, speed: str = "", text: str = "", total_size: float = 0, downloaded_size: float = 0):
        """Update progress bar and labels"""
        if download_id in self.progress_bars:
            self.progress_bars[download_id].update_progress(progress, speed, text, total_size, downloaded_size)
            
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
                self.logger.error(f"Failed to update title for {download_id}: {e}", exc_info=True)
                
    def remove_download(self, download_id: str):
        """Remove a download progress bar"""
        if download_id in self.progress_bars:
            self.progress_bars[download_id].destroy()
            del self.progress_bars[download_id]
