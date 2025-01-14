"""YouTube-specific progress bar widget."""

import customtkinter as ctk
from typing import Optional, Callable, Dict
from .base_widget import BaseWidget
from .progress_bar import ProgressBar
from core.download_state import DownloadState

class YouTubeProgressBar(BaseWidget):
    """Progress bar for YouTube downloads with video/audio components"""
    
    def __init__(self, master, download_id: str = None,
                 on_cancel: Optional[Callable] = None,
                 on_close: Optional[Callable] = None, **kwargs):
        """Initialize YouTube progress bar.
        
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
            video_progress=0,
            audio_progress=0,
            video_speed="0 B/s",
            audio_speed="0 B/s",
            video_text="",
            audio_text="",
            video_size=0,
            audio_size=0,
            state=DownloadState.PENDING
        )
        
        # Create widgets
        self._create_widgets()
        self._setup_layout()
        
    def _create_widgets(self):
        """Create all widgets."""
        # Title label
        self.title_label = ctk.CTkLabel(
            self,
            text="Downloading YouTube Video...",
            anchor="w",
            font=("Helvetica", 12, "bold")
        )
        
        # Video progress frame
        self.video_frame = ctk.CTkFrame(self)
        
        # Video label
        self.video_label = ctk.CTkLabel(
            self.video_frame,
            text="Video:",
            width=50
        )
        
        # Video progress container
        self.video_progress_frame = ctk.CTkFrame(self.video_frame)
        
        # Video progress bar
        self.video_progress = ctk.CTkProgressBar(self.video_progress_frame)
        self.video_progress.set(0)
        
        # Video progress percentage
        self.video_percent = ctk.CTkLabel(
            self.video_progress_frame,
            text="0%",
            width=50
        )
        
        # Video info frame
        self.video_info_frame = ctk.CTkFrame(self.video_frame)
        
        # Video speed
        self.video_speed = ctk.CTkLabel(
            self.video_info_frame,
            text="0 B/s",
            anchor="w"
        )
        
        # Video size
        self.video_size = ctk.CTkLabel(
            self.video_info_frame,
            text="0 MB / 0 MB",
            anchor="e"
        )
        
        # Audio progress frame
        self.audio_frame = ctk.CTkFrame(self)
        
        # Audio label
        self.audio_label = ctk.CTkLabel(
            self.audio_frame,
            text="Audio:",
            width=50
        )
        
        # Audio progress container
        self.audio_progress_frame = ctk.CTkFrame(self.audio_frame)
        
        # Audio progress bar
        self.audio_progress = ctk.CTkProgressBar(self.audio_progress_frame)
        self.audio_progress.set(0)
        
        # Audio progress percentage
        self.audio_percent = ctk.CTkLabel(
            self.audio_progress_frame,
            text="0%",
            width=50
        )
        
        # Audio info frame
        self.audio_info_frame = ctk.CTkFrame(self.audio_frame)
        
        # Audio speed
        self.audio_speed = ctk.CTkLabel(
            self.audio_info_frame,
            text="0 B/s",
            anchor="w"
        )
        
        # Audio size
        self.audio_size = ctk.CTkLabel(
            self.audio_info_frame,
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
        
        # Video frame
        self.video_frame.pack(fill="x", padx=10, pady=5)
        self.video_label.pack(side="left")
        
        # Video progress
        self.video_progress_frame.pack(side="top", fill="x", pady=(0,5))
        self.video_progress.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.video_percent.pack(side="right")
        
        # Video info
        self.video_info_frame.pack(side="top", fill="x")
        self.video_speed.pack(side="left")
        self.video_size.pack(side="right")
        
        # Audio frame
        self.audio_frame.pack(fill="x", padx=10, pady=5)
        self.audio_label.pack(side="left")
        
        # Audio progress
        self.audio_progress_frame.pack(side="top", fill="x", pady=(0,5))
        self.audio_progress.pack(side="left", fill="x", expand=True, padx=(0,5))
        self.audio_percent.pack(side="right")
        
        # Audio info
        self.audio_info_frame.pack(side="top", fill="x")
        self.audio_speed.pack(side="left")
        self.audio_size.pack(side="right")
        
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
            state=state.state,
            video_progress=state.video_progress if hasattr(state, 'video_progress') else 0,
            audio_progress=state.audio_progress if hasattr(state, 'audio_progress') else 0,
            video_speed=state.video_speed if hasattr(state, 'video_speed') else "0 B/s",
            audio_speed=state.audio_speed if hasattr(state, 'audio_speed') else "0 B/s",
            video_text=state.video_text if hasattr(state, 'video_text') else "",
            audio_text=state.audio_text if hasattr(state, 'audio_text') else "",
            video_size=state.video_size if hasattr(state, 'video_size') else 0,
            audio_size=state.audio_size if hasattr(state, 'audio_size') else 0
        )
        
        # Update title (show video title)
        if hasattr(state, 'video_text') and state.video_text:
            title = state.video_text.replace("Downloading ", "")  # Remove "Downloading " prefix
            self.title_label.configure(text=title)
        
        # Update video progress
        if hasattr(state, 'video_progress'):
            self.video_progress.set(state.video_progress / 100)
            self.video_percent.configure(text=f"{state.video_progress:.1f}%")
            
            # Update video size
            if state.video_size > 0:
                downloaded_mb = state.video_downloaded / (1024 * 1024)
                total_mb = state.video_size / (1024 * 1024)
                self.video_size.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")
            
            # Update video speed
            self.video_speed.configure(text=state.video_speed)
            
        # Update audio progress
        if hasattr(state, 'audio_progress'):
            self.audio_progress.set(state.audio_progress / 100)
            self.audio_percent.configure(text=f"{state.audio_progress:.1f}%")
            
            # Update audio size
            if state.audio_size > 0:
                downloaded_mb = state.audio_downloaded / (1024 * 1024)
                total_mb = state.audio_size / (1024 * 1024)
                self.audio_size.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")
            
            # Update audio speed
            self.audio_speed.configure(text=state.audio_speed)
        
        # Update buttons based on state
        if state.state in [DownloadState.COMPLETED, DownloadState.CANCELLED, DownloadState.ERROR]:
            self.cancel_button.configure(state="disabled")
            self.close_button.configure(state="normal")
            
        # Handle audio-only downloads
        if not hasattr(state, 'video_progress') or state.video_progress == 0:
            self.video_frame.configure(fg_color="gray30")  # Grey out video frame
            self.video_progress.configure(progress_color="gray50")  # Grey out progress bar
            
    def _on_cancel_click(self):
        """Handle cancel button click."""
        if self.on_cancel and self.get_state('download_id'):
            self.on_cancel(self.get_state('download_id'))
            
    def _on_close_click(self):
        """Handle close button click."""
        if self.on_close:
            self.on_close()
