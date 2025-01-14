"""
Main GUI application for JustDownloadIt.

This module contains the DownloaderApp class which manages the entire GUI application.
It handles user input, download management, and progress updates.

Key Components:
    - URL Input: Text area for entering download URLs
    - Download Settings: Thread count and format selection for YouTube
    - Progress Display: Shows download progress with speed and ETA
    - Download Management: Start, cancel, and clear downloads

Classes:
    DownloaderApp: Main application class that manages the GUI and downloads

Dependencies:
    - customtkinter: Modern themed tkinter widgets
    - core.download_manager: Backend download management
    - core.download_state: Download state tracking
    - core.config: Application configuration
    - gui.download_frame: Download progress display
"""

from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import logging
from queue import Queue, Empty
import threading
import re
from typing import Callable
import time
from datetime import datetime

from utils.url_utils import clean_url, check_link_type, parse_urls
from utils.errors import handle_download_error
from core.download_manager import DownloadManager
from core.download_state import DownloadState
from core.config import Config
from gui.download_frame import DownloadFrame

class DownloaderApp(ctk.CTk):
    """Main application window."""
    
    def __init__(self):
        super().__init__()
        
        self.title("JustDownloadIt")
        self.geometry("800x600")
        
        # Initialize logger
        self.logger = logging.getLogger(__name__)
        
        # Initialize download manager
        self.manager = DownloadManager()
        
        # Create main UI elements
        self._create_widgets()
        self._setup_layout()
        
    def _create_widgets(self):
        """Create all UI widgets."""
        # URL input section
        self.url_label = ctk.CTkLabel(self, text="Enter URLs (one per line):")
        self.url_input = ctk.CTkTextbox(self, height=100)
        self.url_input.bind('<KeyRelease>', self._on_url_input_change)
        
        # Action section (download button and target directory)
        self.action_frame = ctk.CTkFrame(self)
        
        # Download button
        self.download_button = ctk.CTkButton(
            self.action_frame,
            text="Start Download",
            command=self._on_download_click,
            width=120
        )
        
        # Target directory selection
        self.target_dir_label = ctk.CTkLabel(self.action_frame, text="Save to:")
        self.target_dir_entry = ctk.CTkEntry(self.action_frame, width=300)
        self.target_dir_entry.insert(0, str(Config.DOWNLOAD_DIR))
        self.target_dir_button = ctk.CTkButton(
            self.action_frame,
            text="Browse",
            width=60,
            command=self._select_target_dir
        )
        
        # Settings section
        self.settings_frame = ctk.CTkFrame(self)
        
        # Regular settings
        self.regular_settings = ctk.CTkFrame(self.settings_frame)
        
        # Thread count option
        self.threads_label = ctk.CTkLabel(self.regular_settings, text="Download Threads:")
        self.threads_var = tk.IntVar(value=4)
        self.threads_slider = ctk.CTkSlider(
            self.regular_settings,
            from_=1,
            to=32,
            number_of_steps=31,
            variable=self.threads_var,
            command=self._update_threads_label
        )
        self.threads_value_label = ctk.CTkLabel(self.regular_settings, text=str(self.threads_var.get()))
        
        # YouTube settings
        self.youtube_settings = ctk.CTkFrame(self.settings_frame)
        
        # Audio only mode
        self.audio_only_var = tk.BooleanVar(value=False)
        self.audio_only_check = ctk.CTkCheckBox(
            self.youtube_settings,
            text="Audio Only",
            variable=self.audio_only_var,
            command=self._on_audio_only_toggle
        )
        
        # Video quality settings
        self.video_quality_frame = ctk.CTkFrame(self.youtube_settings)
        self.video_quality_label = ctk.CTkLabel(self.video_quality_frame, text="Video Quality:")
        self.video_quality_var = tk.StringVar(value="720p")
        self.video_quality_menu = ctk.CTkOptionMenu(
            self.video_quality_frame,
            values=["2160p", "1440p", "1080p", "720p", "480p", "360p"],
            variable=self.video_quality_var
        )
        
        # Audio quality settings
        self.audio_quality_frame = ctk.CTkFrame(self.youtube_settings)
        self.audio_quality_label = ctk.CTkLabel(self.audio_quality_frame, text="Audio Quality:")
        self.audio_quality_var = tk.StringVar(value="160k")
        self.audio_quality_menu = ctk.CTkOptionMenu(
            self.audio_quality_frame,
            values=["160k", "128k", "70k", "50k"],
            variable=self.audio_quality_var
        )
        
        # Downloads frame for progress bars
        self.download_frame = DownloadFrame(self)
        
    def _setup_layout(self):
        """Setup widget layout."""
        # URL input section
        self.url_label.pack(padx=10, pady=(10, 0), anchor="w")
        self.url_input.pack(padx=10, pady=(5, 10), fill="x")
        
        # Action section
        self.action_frame.pack(padx=10, pady=5, fill="x")
        self.download_button.pack(side="left", padx=5)
        self.target_dir_label.pack(side="left", padx=5)
        self.target_dir_entry.pack(side="left", padx=5, fill="x", expand=True)
        self.target_dir_button.pack(side="left", padx=5)
        
        # Settings section (initially hidden)
        self.settings_frame.pack_forget()  # Start hidden
        
        # Regular settings
        self.regular_settings.pack(fill="x", padx=5, pady=5)
        self.threads_label.pack(side="left", padx=5)
        self.threads_slider.pack(side="left", padx=5, fill="x", expand=True)
        self.threads_value_label.pack(side="left", padx=5)
        
        # YouTube settings (initially hidden)
        self.youtube_settings.pack_forget()  # Start hidden
        self.audio_only_check.pack(side="left", padx=5)
        self.video_quality_frame.pack(side="left", padx=5)
        self.video_quality_label.pack(side="left", padx=5)
        self.video_quality_menu.pack(side="left", padx=5)
        self.audio_quality_frame.pack(side="left", padx=5)
        self.audio_quality_label.pack(side="left", padx=5)
        self.audio_quality_menu.pack(side="left", padx=5)
        
        # Downloads frame
        self.download_frame.pack(padx=10, pady=10, fill="both", expand=True)
        
    def _select_target_dir(self):
        """Open directory selection dialog."""
        dir_path = filedialog.askdirectory(
            initialdir=self.target_dir_entry.get()
        )
        if dir_path:
            self.target_dir_entry.delete(0, "end")
            self.target_dir_entry.insert(0, dir_path)
            
    def _get_target_path(self, url: str, title: str, index: int = 1) -> Path:
        """Generate target file path using template.
        
        Args:
            url (str): Download URL
            title (str): Original file title
            index (int): File index for duplicate handling
            
        Returns:
            Path: Target file path
        """
        # Get template and target directory
        template = "{title}"
        target_dir = Path(self.target_dir_entry.get())
        
        # Replace template variables
        filename = template.format(
            title=title,
            id=url.split('/')[-1],
            date=datetime.now().strftime("%Y%m%d"),
            index=index if index > 1 else ""
        )
        
        # Clean filename
        filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
        
        # Add extension based on URL type and settings
        if check_link_type(url) == 'youtube' and self.audio_only_var.get():
            filename += '.mp3'
        else:
            filename += '.mp4'
            
        # Handle duplicates
        target_path = target_dir / filename
        while target_path.exists():
            index += 1
            target_path = self._get_target_path(url, title, index)
            
        return target_path
        
    def _on_url_input_change(self, event=None):
        """Handle URL input changes."""
        urls = self.url_input.get("1.0", "end-1c").split()
        
        has_regular = False
        has_youtube = False
        
        for url in urls:
            if check_link_type(url) == 'youtube':
                has_youtube = True
            else:
                has_regular = True
                
        # Show/hide settings frame
        if has_regular or has_youtube:
            self.settings_frame.pack(padx=10, pady=5, fill="x", after=self.action_frame)
        else:
            self.settings_frame.pack_forget()
            
        # Show/hide YouTube settings
        if has_youtube:
            self.youtube_settings.pack(fill="x", padx=5, pady=5)
        else:
            self.youtube_settings.pack_forget()
            
        # Show/hide regular settings
        if has_regular:
            self.regular_settings.pack(fill="x", padx=5, pady=5)
        else:
            self.regular_settings.pack_forget()
            
    def _on_audio_only_toggle(self):
        """Handle audio only checkbox toggle."""
        if self.audio_only_var.get():
            self.video_quality_frame.pack_forget()
        else:
            # Re-add video quality after audio quality frame
            self.video_quality_frame.pack(side="left", padx=5, after=self.audio_quality_frame)
            
    def _on_download_click(self):
        """Handle download button click."""
        urls = self.url_input.get("1.0", "end-1c").split()
        if not urls:
            return
            
        # Start download for each URL
        for url in urls:
            url = clean_url(url)
            if not url:
                continue
                
            # Start download in separate thread
            thread = threading.Thread(
                target=self._download_url,
                args=(url,),
                daemon=True
            )
            thread.start()
            
    def _download_url(self, url: str):
        """Start downloading a URL"""
        try:
            download_id = self.manager.generate_download_id(url)
            
            # Add download to frame (it will create appropriate progress bar)
            self.download_frame.add_download(
                download_id=download_id,
                url=url,
                on_cancel=self.on_cancel,
                audio_only=self.audio_only_var.get() if check_link_type(url) == 'youtube' else False
            )
            
            # Get target directory
            target_dir = Path(self.target_dir_entry.get())
            if not target_dir.exists():
                target_dir.mkdir(parents=True)
            
            # Create progress callback that includes download_id
            def progress_callback(progress: float, speed: str = "", text: str = "",
                                total_size: float = 0, downloaded_size: float = 0,
                                stats: dict = None, state: DownloadState = DownloadState.DOWNLOADING,
                                **kwargs):
                # Store reference to outer self for audio_only_var access
                app = self
                
                # Create a state object with all required attributes
                class DownloadProgress:
                    def __init__(self):
                        self.state = state
                        # For audio-only YouTube downloads, treat it like a regular download
                        if check_link_type(url) == 'youtube' and app.audio_only_var.get():
                            self.progress = progress
                            self.speed = speed
                            self.text = text
                            self.downloaded_size = downloaded_size
                            self.total_size = total_size
                        # Handle video/audio components for YouTube video downloads
                        elif 'component' in kwargs:
                            if kwargs['component'] == 'video':
                                self.video_progress = progress
                                self.video_speed = speed
                                self.video_text = text
                                self.video_size = total_size
                                self.video_downloaded = downloaded_size
                                self.audio_progress = 0
                                self.audio_speed = "0 B/s"
                                self.audio_text = ""
                                self.audio_size = 0
                                self.audio_downloaded = 0
                            else:  # audio
                                self.audio_progress = progress
                                self.audio_speed = speed
                                self.audio_text = text
                                self.audio_size = total_size
                                self.audio_downloaded = downloaded_size
                                self.video_progress = 0
                                self.video_speed = "0 B/s"
                                self.video_text = ""
                                self.video_size = 0
                                self.video_downloaded = 0
                        else:
                            # Regular download
                            self.progress = progress
                            self.speed = speed
                            self.text = text
                            self.downloaded_size = downloaded_size
                            self.total_size = total_size
                
                self.on_progress(download_id, DownloadProgress())
            
            # Start download based on URL type
            if check_link_type(url) == 'youtube':
                self.manager.download_youtube(
                    url,
                    download_dir=target_dir,
                    quality=self.video_quality_var.get() if not self.audio_only_var.get() else None,
                    audio_quality=self.audio_quality_var.get(),
                    audio_only=self.audio_only_var.get(),
                    on_progress=progress_callback,
                    threads=self.threads_var.get()
                )
            else:
                self.manager.download(
                    url,
                    download_dir=target_dir,
                    on_progress=progress_callback,
                    threads=self.threads_var.get()
                )
                
        except Exception as e:
            self.logger.error(f"Error starting download: {e}")
            handle_download_error(e)
            
    def on_progress(self, download_id: str, state: DownloadState):
        """Handle download progress updates."""
        try:
            # Use the proper update_download method
            self.download_frame.update_download(download_id, state)
        except Exception as e:
            self.logger.error(f"Error updating progress: {e}")
            
    def on_cancel(self, download_id: str):
        """Handle download cancellation."""
        try:
            self.manager.cancel_download(download_id)
        except Exception as e:
            self.logger.error(f"Error cancelling download: {e}")
            handle_download_error(e)
            
    def _update_threads_label(self, value):
        """
        Update the threads value label.
        
        Args:
            value (float): New number of threads
        """
        # Convert float to int since we want whole numbers
        threads = int(float(value))
        self.threads_value_label.configure(text=str(threads))
        self.threads_var.set(threads)
        
    def run(self):
        """
        Start the GUI.
        Enters the main event loop.
        """
        self.mainloop()
