"""
Progress bar widget for downloads.

This module provides the ProgressBar class which displays download progress with statistics.
It includes a progress bar, speed indicator, and control buttons.

Features:
    - Visual progress indication
    - Download speed and ETA display
    - Cancel/Open button
    - File size and downloaded size display
    - Error state indication
    - Graph display for speed history

Classes:
    ProgressBar: Custom progress bar widget with statistics

Dependencies:
    - customtkinter: Modern themed tkinter widgets
    - core.download_state: Download state tracking
"""

import customtkinter as ctk
from typing import Optional, Callable
from .base_widget import BaseWidget
from core.download_state import DownloadState

class ProgressBar(BaseWidget):
    """Progress bar widget with detailed statistics"""
    
    def __init__(self, master, download_id: str = None, 
                 on_cancel: Optional[Callable] = None, 
                 on_close: Optional[Callable] = None, **kwargs):
        """Initialize progress bar.
        
        Args:
            master: Parent widget
            download_id (str, optional): Download ID
            on_cancel (callable, optional): Callback when download is cancelled
            on_close (callable, optional): Callback when progress bar is closed
        """
        super().__init__(master, **kwargs)
        
        # Store callbacks
        self.on_cancel = on_cancel
        self.on_close = on_close
        
        # Initialize state
        self.set_state(
            download_id=download_id,
            progress=0,
            speed="0 B/s",
            text="",
            total_size=0,
            downloaded_size=0,
            state=DownloadState.QUEUED
        )
        
        # Create widgets
        self._create_widgets()
        self._setup_layout()
        
    def _create_widgets(self):
        """Create all widgets."""
        # Title label
        self.title_label = ctk.CTkLabel(
            self,
            text="Downloading...",
            anchor="w",
            font=("Helvetica", 12, "bold")
        )
        
        # Progress frame
        self.progress_frame = ctk.CTkFrame(self)
        
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame)
        self.progress_bar.set(0)
        
        # Progress percentage
        self.progress_percent = ctk.CTkLabel(
            self.progress_frame,
            text="0%",
            width=50
        )
        
        # Info frame
        self.info_frame = ctk.CTkFrame(self)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(
            self.info_frame,
            text="0 B/s",
            anchor="w"
        )
        
        # Size label
        self.size_label = ctk.CTkLabel(
            self.info_frame,
            text="0 MB / 0 MB",
            anchor="e"
        )
        
        # Control frame
        self.control_frame = ctk.CTkFrame(self)
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            self.control_frame,
            text="Cancel",
            command=self._on_cancel_click,
            width=60
        )
        
        # Close button
        self.close_button = ctk.CTkButton(
            self.control_frame,
            text="Close",
            command=self._on_close_click,
            width=60,
            state="disabled"
        )
        
    def _setup_layout(self):
        """Setup widget layout."""
        # Title
        self.title_label.pack(fill="x", padx=10, pady=(10,5))
        
        # Progress frame
        self.progress_frame.pack(fill="x", padx=10, pady=5)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.progress_percent.pack(side="right")
        
        # Info frame
        self.info_frame.pack(fill="x", padx=10, pady=5)
        self.speed_label.pack(side="left")
        self.size_label.pack(side="right")
        
        # Control frame
        self.control_frame.pack(fill="x", padx=10, pady=(5,10))
        self.cancel_button.pack(side="left", padx=5)
        self.close_button.pack(side="left")
        
    def update_state(self, state: DownloadState):
        """Update progress bar state.
        
        Args:
            state (DownloadState): New download state
        """
        # Update internal state
        self.set_state(
            progress=state.progress,
            speed=state.speed,
            text=state.text,
            downloaded_size=state.downloaded_size,
            total_size=state.total_size,
            state=state.state
        )
        
        # Update progress
        self.progress_bar.set(state.progress / 100)
        self.progress_percent.configure(text=f"{state.progress:.1f}%")
        
        # Update title (extract filename from path)
        if state.text:
            filename = state.text.split('/')[-1] if '/' in state.text else state.text
            self.title_label.configure(text=filename)
        
        # Update size info
        if state.total_size > 0:
            downloaded_mb = state.downloaded_size / (1024 * 1024)
            total_mb = state.total_size / (1024 * 1024)
            self.size_label.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")
        
        # Update speed
        self.speed_label.configure(text=state.speed)
        
        # Update buttons based on state
        if state.state in [DownloadState.COMPLETED, DownloadState.CANCELLED, DownloadState.ERROR]:
            self.cancel_button.configure(state="disabled")
            self.close_button.configure(state="normal")
            
    def _on_cancel_click(self):
        """Handle cancel button click."""
        if self.on_cancel and self.get_state('download_id'):
            self.on_cancel(self.get_state('download_id'))
            
    def _on_close_click(self):
        """Handle close button click."""
        if self.on_close:
            self.on_close()
