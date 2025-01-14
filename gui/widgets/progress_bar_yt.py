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
        
        # Color constants
        self.DOWNLOAD_COLOR = "#1f538d"  # Blue
        self.MUXING_COLOR = "#2d9d3f"    # Green
        
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
            text="Downloading YouTube Video...",
            anchor="w",
            font=("Helvetica", 12)  
        )
        
        # Video progress frame
        self.video_frame = ctk.CTkFrame(self, fg_color="transparent")  
        
        # Video label
        self.video_label = ctk.CTkLabel(
            self.video_frame,
            text="Video:",
            width=45,  
            font=("Helvetica", 11)  
        )
        
        # Video progress container
        self.video_progress_frame = ctk.CTkFrame(self.video_frame, fg_color="transparent")  
        
        # Video progress bar
        self.video_progress = ctk.CTkProgressBar(
            self.video_progress_frame,
            height=6,  
            corner_radius=2  
        )
        self.video_progress.set(0)
        
        # Video progress percentage
        self.video_percent = ctk.CTkLabel(
            self.video_progress_frame,
            text="0%",
            width=35,  
            font=("Helvetica", 11)  
        )
        
        # Video info frame
        self.video_info_frame = ctk.CTkFrame(self.video_frame, fg_color="transparent")  
        
        # Video speed
        self.video_speed = ctk.CTkLabel(
            self.video_info_frame,
            text="0 B/s",
            anchor="w",
            font=("Helvetica", 10)  
        )
        
        # Video size
        self.video_size = ctk.CTkLabel(
            self.video_info_frame,
            text="0 MB / 0 MB",
            anchor="e",
            font=("Helvetica", 10)  
        )
        
        # Audio progress frame
        self.audio_frame = ctk.CTkFrame(self, fg_color="transparent")  
        
        # Audio label
        self.audio_label = ctk.CTkLabel(
            self.audio_frame,
            text="Audio:",
            width=45,  
            font=("Helvetica", 11)  
        )
        
        # Audio progress container
        self.audio_progress_frame = ctk.CTkFrame(self.audio_frame, fg_color="transparent")  
        
        # Audio progress bar
        self.audio_progress = ctk.CTkProgressBar(
            self.audio_progress_frame,
            height=6,  
            corner_radius=2  
        )
        self.audio_progress.set(0)
        
        # Audio progress percentage
        self.audio_percent = ctk.CTkLabel(
            self.audio_progress_frame,
            text="0%",
            width=35,  
            font=("Helvetica", 11)  
        )
        
        # Audio info frame
        self.audio_info_frame = ctk.CTkFrame(self.audio_frame, fg_color="transparent")  
        
        # Audio speed
        self.audio_speed = ctk.CTkLabel(
            self.audio_info_frame,
            text="0 B/s",
            anchor="w",
            font=("Helvetica", 10)  
        )
        
        # Audio size
        self.audio_size = ctk.CTkLabel(
            self.audio_info_frame,
            text="0 MB / 0 MB",
            anchor="e",
            font=("Helvetica", 10)  
        )
        
        # Control frame
        self.control_frame = ctk.CTkFrame(self, fg_color="transparent")  
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(
            self.control_frame,
            text="Cancel",
            command=self._on_cancel_click,
            width=50,  
            height=22,  
            font=("Helvetica", 11)  
        )
        
        # Close button
        self.close_button = ctk.CTkButton(
            self.control_frame,
            text="Close",
            command=self._on_close_click,
            width=50,  
            height=22,  
            font=("Helvetica", 11),  
            state="disabled"
        )
        
    def _setup_layout(self):
        """Setup widget layout."""
        # Title
        self.title_label.pack(fill="x", padx=6, pady=(4,2))  
        
        # Video frame
        self.video_frame.pack(fill="x", padx=6, pady=1)  
        self.video_label.pack(side="left")
        
        # Video progress
        self.video_progress_frame.pack(side="top", fill="x", pady=(0,1))  
        self.video_progress.pack(side="left", fill="x", expand=True, padx=(0,2))  
        self.video_percent.pack(side="right")
        
        # Video info
        self.video_info_frame.pack(side="top", fill="x")
        self.video_speed.pack(side="left")
        self.video_size.pack(side="right")
        
        # Audio frame
        self.audio_frame.pack(fill="x", padx=6, pady=1)  
        self.audio_label.pack(side="left")
        
        # Audio progress
        self.audio_progress_frame.pack(side="top", fill="x", pady=(0,1))  
        self.audio_progress.pack(side="left", fill="x", expand=True, padx=(0,2))  
        self.audio_percent.pack(side="right")
        
        # Audio info
        self.audio_info_frame.pack(side="top", fill="x")
        self.audio_speed.pack(side="left")
        self.audio_size.pack(side="right")
        
        # Control frame
        self.control_frame.pack(fill="x", padx=6, pady=(2,4))  
        self.cancel_button.pack(side="left", padx=2)  
        self.close_button.pack(side="left")
        
    def update_state(self, state: DownloadState):
        """Update progress bar state.
        
        Args:
            state (DownloadState): New download state
        """
        if state is None:
            return
            
        # Get component from state
        component = getattr(state, 'component', None)
        
        # Update progress based on component
        progress = getattr(state, 'progress', 0)
        speed = getattr(state, 'speed', "0 B/s")
        text = getattr(state, 'text', "")
        total_size = getattr(state, 'total_size', 0)
        downloaded_size = getattr(state, 'downloaded_size', 0)
        
        # Update progress bar
        self.update_progress(
            progress=progress,
            speed=speed,
            text=text,
            total_size=total_size,
            downloaded_size=downloaded_size,
            state=state.state,
            component=component
        )
        
    def update_progress(self, progress: float = None, speed: str = None, text: str = None,
                       total_size: int = None, downloaded_size: int = None,
                       stats: Dict = None, state: DownloadState = None,
                       component: str = None):
        """Update progress bar state.
        
        Args:
            progress (float, optional): Progress percentage (0-100)
            speed (str, optional): Download speed
            text (str, optional): Status text
            total_size (int, optional): Total file size
            downloaded_size (int, optional): Downloaded file size
            stats (dict, optional): Download statistics
            state (DownloadState, optional): Download state
            component (str, optional): Component being updated (video/audio/muxing)
        """
        if state is not None:
            self.state = state
            
        # Handle muxing state
        if component == "muxing":
            # Only hide audio components when muxing starts
            self.audio_frame.pack_forget()
            
            # Update video components for muxing
            self.video_label.configure(text="Status:")
            self.video_progress.configure(progress_color=self.MUXING_COLOR)  # Green for muxing
            self.video_progress.set(0)  # Reset progress for muxing
            
            if progress is not None:
                self.video_progress.set(progress / 100)
                self.video_percent.configure(text=f"{progress:.1f}%")
                
            # Update status text
            self.video_speed.configure(text="Combining video and audio...")
            self.video_size.configure(text="")  # Clear size during muxing
            
            # Update title
            self.title_label.configure(text="Muxing Video and Audio...")
            
            self.update_idletasks()  # Force widget update
            return
            
        # Regular video/audio progress updates
        if component in ["video", None]:
            # Show video components with original labels
            self.video_label.configure(text="Video:")
            self.video_progress.configure(progress_color=self.DOWNLOAD_COLOR)  # Blue for download
            if progress is not None:
                self.video_progress.set(progress / 100)
                self.video_percent.configure(text=f"{progress:.1f}%")
            if speed is not None:
                self.video_speed.configure(text=speed)
            if total_size is not None and downloaded_size is not None:
                total_mb = total_size / (1024 * 1024)
                downloaded_mb = downloaded_size / (1024 * 1024)
                self.video_size.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")
            self.title_label.configure(text="Downloading YouTube Video...")
            self.update_idletasks()  # Force widget update
                
        if component == "audio":
            # Always show audio components until muxing starts
            self.audio_frame.pack()
            if progress is not None:
                self.audio_progress.set(progress / 100)
                self.audio_percent.configure(text=f"{progress:.1f}%")
            if speed is not None:
                self.audio_speed.configure(text=speed)
            if total_size is not None and downloaded_size is not None:
                total_mb = total_size / (1024 * 1024)
                downloaded_mb = downloaded_size / (1024 * 1024)
                self.audio_size.configure(text=f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB")
            self.update_idletasks()  # Force widget update
            
    def _on_cancel_click(self):
        """Handle cancel button click."""
        if self.on_cancel and self.get_state('download_id'):
            self.on_cancel(self.get_state('download_id'))
            
    def _on_close_click(self):
        """Handle close button click."""
        if self.on_close:
            self.on_close()
