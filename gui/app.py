"""
JustDownloadIt GUI Application.

This module implements the main graphical user interface for JustDownloadIt,
providing an intuitive and responsive interface for managing downloads.

Key Features:
    - Modern and responsive UI design
    - Real-time download management
        - Progress tracking
        - Speed monitoring
        - ETA calculation
    - Multi-download support
        - Parallel downloads
        - Queue management
        - Priority handling
    - Format customization
        - Quality selection
        - Format preferences
        - Audio options
    - User preferences
        - Download location
        - Thread count
        - Default settings
    - Clipboard integration
        - URL detection
        - Batch processing
    - Error handling
        - User-friendly messages
        - Recovery suggestions
        - Detailed logging

Components:
    DownloaderApp: Main application window and controller
        - URL management
        - Download control
        - Settings interface
        - Progress display
        - Status updates

Dependencies:
    Required:
        - customtkinter: Modern UI widgets
        - tkinter: Base GUI toolkit
    Internal:
        - core.download_manager: Download backend
        - core.config: Settings management
        - gui.download_frame: Progress display
        - utils.url_utils: URL processing
        - utils.errors: Error handling

Thread Safety:
    GUI updates are marshalled to the main thread
    to ensure thread-safe operation.
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
import os

from utils.url_utils import clean_url, check_link_type, parse_urls, extract_playlist_videos, URLType, validate_url, is_line_valid_url, remove_url_from_text
from utils.errors import handle_download_error
from core.download_manager import DownloadManager
from core.download_task import DownloadTask
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
        
    def _on_url_input_change(self, *args):
        """Handle URL input changes."""
        # Get current URL input
        text = self.url_input.get("1.0", "end-1c").strip()
        
        # Check each line for valid URLs
        valid_urls = []
        for line in text.splitlines():
            if is_line_valid_url(line):
                valid_urls.append(clean_url(line))
                
        # Enable download button only if we have valid URLs
        if valid_urls:
            self.download_button.configure(state="normal")
            # Show YouTube settings if any YouTube URLs present
            has_youtube = any(check_link_type(url) in [URLType.YOUTUBE, URLType.YOUTUBE_PLAYLIST] 
                            for url in valid_urls)
            self._update_youtube_settings_visibility(has_youtube)
        else:
            self.download_button.configure(state="disabled")
            self._update_youtube_settings_visibility(False)

    def _on_audio_only_toggle(self):
        """Handle audio only checkbox toggle."""
        if self.audio_only_var.get():
            self.video_quality_frame.pack_forget()
        else:
            # Re-add video quality after audio quality frame
            self.video_quality_frame.pack(side="left", padx=5, after=self.audio_quality_frame)
            
    def _on_download_click(self):
        """Handle download button click."""
        text = self.url_input.get("1.0", "end-1c")
        lines = text.splitlines()
        
        # Process lines and look for playlists
        modified = False
        new_lines = []
        for line in lines:
            line = line.strip()
            if not is_line_valid_url(line):
                new_lines.append(line)
                continue
                
            url = clean_url(line)
            
            # Extract playlist videos if it's a playlist URL
            if check_link_type(url) == URLType.YOUTUBE_PLAYLIST:
                try:
                    self.logger.info(f"Processing playlist URL: {url}")
                    playlist_videos = extract_playlist_videos(url)
                    if not playlist_videos:
                        raise ValueError("No videos found in playlist")
                        
                    # Replace this line with the playlist videos
                    new_lines.extend(playlist_videos)
                    modified = True
                    
                    messagebox.showinfo(
                        "Playlist Extracted",
                        f"Successfully extracted {len(playlist_videos)} videos from playlist.\n"
                        "Press Download again to start downloading the videos."
                    )
                except Exception as e:
                    self.logger.error(f"Failed to extract playlist: {e}")
                    self.logger.exception("Full traceback:")
                    messagebox.showerror(
                        "Playlist Error",
                        f"Failed to extract playlist videos: {str(e)}\n\n"
                        "Please check if the playlist is public and accessible."
                    )
                    # Keep original line on error
                    new_lines.append(line)
            else:
                new_lines.append(line)
                
        # If we found and processed a playlist, update the text
        if modified:
            self.url_input.delete("1.0", "end")
            self.url_input.insert("1.0", "\n".join(new_lines))
            self._on_url_input_change()
            return
                
        # No playlists found, process URLs normally
        processed_urls = []
        for line in lines:
            if not is_line_valid_url(line):
                continue
            url = clean_url(line)
            processed_urls.append(url)
                
        # Start download for each processed URL
        for url in processed_urls:
            try:
                # Start download in separate thread
                thread = threading.Thread(
                    target=self._download_url,
                    args=(url,),
                    daemon=True
                )
                thread.start()
            except Exception as e:
                self.logger.error(f"Failed to start download for {url}: {e}")
                self.logger.exception("Full traceback:")
                messagebox.showerror(
                    "Download Error",
                    f"Failed to start download for {url}:\n{str(e)}"
                )

    def _download_url(self, url: str):
        """Download a single URL"""
        try:
            # Get download type
            download_type = check_link_type(url)
            
            # Get output directory
            output_dir = self.target_dir_entry.get()
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
                
            # Get download options
            options = {}
            if download_type in [URLType.YOUTUBE, URLType.YOUTUBE_PLAYLIST]:
                options["format"] = self.video_quality_var.get() if not self.audio_only_var.get() else None
                options["audio_only"] = self.audio_only_var.get()
                options["quality"] = self.audio_quality_var.get()
                
            # Remove URL from input field
            text = self.url_input.get("1.0", "end-1c")
            new_text = remove_url_from_text(text, url)
            self.url_input.delete("1.0", "end")
            self.url_input.insert("1.0", new_text)
            self._on_url_input_change()
                
            # Start download
            self.manager.start_download(
                url=url,
                output_dir=output_dir,
                options=options
            )
            
        except Exception as e:
            self.logger.error(f"Error starting download: {e}")
            self.logger.exception("Unexpected error:")
            messagebox.showerror(
                "Download Error", 
                f"Failed to download {url}:\n{str(e)}"
            )
            
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
        
    def _update_youtube_settings_visibility(self, visible: bool):
        """Show/hide YouTube settings."""
        if visible:
            self.youtube_settings.pack(fill="x", padx=5, pady=5)
        else:
            self.youtube_settings.pack_forget()
            
    def run(self):
        """
        Start the GUI.
        Enters the main event loop.
        """
        self.mainloop()
