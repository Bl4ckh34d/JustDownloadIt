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

from core.download_manager import DownloadManager
from core.download_state import DownloadState
from core.config import Config
from core.youtube import StreamInfo
from gui.download_frame import DownloadFrame  # Import DownloadFrame from its own module

class DownloaderApp:
    """Main application class"""
    
    def __init__(self):
        """Initialize the application"""
        self.root = ctk.CTk()
        self.root.title("JustDownloadIt")
        self.root.geometry("800x600")  # Increased height from 400 to 600
        self.root.minsize(800, 600)  # Increased min height from 400 to 600
        
        # Initialize variables
        self.stop_all_downloads = False
        self.active_urls = set()
        self.update_queue = Queue()
        self.logger = logging.getLogger(__name__)
        
        # Load user configuration
        Config.load_user_config()
        
        # Set download directory
        self.download_dir = Config.DOWNLOAD_DIR
        self.download_dir.mkdir(parents=True, exist_ok=True)
        self.logger.info(f"Download directory set to: {self.download_dir.absolute()}")
        
        # Initialize download manager with project's downloads folder
        self.manager = DownloadManager(self.download_dir)
        
        # Initialize GUI root first
        self.main_frame = ctk.CTkFrame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Initialize SmartDL variables
        self.active_downloads = []  # Track download objects
        
        # Initialize download variables (after root creation)
        self.threads_var = tk.IntVar(value=Config.DEFAULT_THREADS)
        self.attempts_var = tk.IntVar(value=Config.DEFAULT_RETRY_ATTEMPTS)
        
        # Settings variables
        self.progress_thickness = 5  # Default progress bar thickness
        
        # Create download frame
        self.download_frame = DownloadFrame(self.main_frame)  
        self.download_frame.configure(height=200, width=Config.WINDOW_WIDTH - 20)  # Set initial size
        
        # Setup rest of GUI
        self._setup_gui()
        
        # Pack download frame after GUI setup
        self.download_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5, side=tk.BOTTOM)
        
        # Start update processing
        self._start_update_thread()
        
        # Set up window close handler
        self.root.protocol("WM_DELETE_WINDOW", self._on_closing)
        
    def _setup_gui(self):
        """
        Set up the main GUI components.
        Creates input fields, buttons, and settings panels.
        """
        # URL input frame at top
        self.url_frame = ctk.CTkFrame(self.main_frame)
        self.url_frame.pack(fill=tk.X, padx=5, pady=5)
        
        url_label = ctk.CTkLabel(self.url_frame, text="Enter URLs (one per line):")
        url_label.pack(anchor=tk.W, padx=5, pady=2)
        
        self.url_text = ctk.CTkTextbox(self.url_frame, height=100)
        self.url_text.pack(fill=tk.X, padx=5, pady=2)
        self.url_text.bind("<KeyRelease>", self._check_link_types)
        
        # Options frame in middle
        self.options_frame = ctk.CTkFrame(self.main_frame)
        
        # Regular download options frame
        self.regular_frame = ctk.CTkFrame(self.options_frame)
        regular_title = ctk.CTkLabel(self.regular_frame, text="Regular Download Options", font=("Arial", 12, "bold"))
        regular_title.pack(anchor=tk.W, padx=5, pady=2)
        
        # Threads and attempts in same frame
        settings_frame = ctk.CTkFrame(self.regular_frame)
        settings_frame.pack(fill=tk.X, padx=5, pady=2)
        
        # Threads
        threads_label = ctk.CTkLabel(settings_frame, text="Threads:")
        threads_label.pack(side=tk.LEFT, padx=5)
        
        self.threads_slider = ctk.CTkSlider(
            settings_frame,
            from_=1,
            to=64,
            variable=self.threads_var,
            command=self._update_threads_label
        )
        self.threads_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.threads_value_label = ctk.CTkLabel(settings_frame, text=str(self.threads_var.get()))
        self.threads_value_label.pack(side=tk.LEFT, padx=5)
        
        # Attempts (now in same frame)
        attempts_label = ctk.CTkLabel(settings_frame, text="Attempts:")
        attempts_label.pack(side=tk.LEFT, padx=5)
        
        self.attempts_entry = ctk.CTkEntry(settings_frame, width=50, textvariable=self.attempts_var)
        self.attempts_entry.pack(side=tk.LEFT, padx=5)

        # YouTube download options frame
        self.youtube_frame = ctk.CTkFrame(self.options_frame)
        youtube_title = ctk.CTkLabel(self.youtube_frame, text="YouTube Download Options", font=("Arial", 12, "bold"))
        youtube_title.pack(anchor=tk.W, padx=5, pady=2)

        # YouTube settings frame
        yt_settings_frame = ctk.CTkFrame(self.youtube_frame)
        yt_settings_frame.pack(fill=tk.X, padx=5, pady=2)

        # Video quality options
        quality_label = ctk.CTkLabel(yt_settings_frame, text="Video Quality:")
        quality_label.pack(side=tk.LEFT, padx=5)

        self.quality_var = tk.StringVar(value="highest")
        quality_options = ["highest", "1080p", "720p", "480p", "360p", "240p", "144p"]
        self.quality_menu = ctk.CTkOptionMenu(
            yt_settings_frame,
            variable=self.quality_var,
            values=quality_options
        )
        self.quality_menu.pack(side=tk.LEFT, padx=5)

        # Audio only checkbox
        self.audio_only_var = tk.BooleanVar(value=False)
        self.audio_only_cb = ctk.CTkCheckBox(
            yt_settings_frame,
            text="Audio Only",
            variable=self.audio_only_var,
            command=self._toggle_quality_menu
        )
        self.audio_only_cb.pack(side=tk.LEFT, padx=20)

        # Audio quality options
        audio_quality_label = ctk.CTkLabel(yt_settings_frame, text="Audio Quality:")
        audio_quality_label.pack(side=tk.LEFT, padx=5)

        self.audio_quality_var = tk.StringVar(value="best")
        audio_quality_options = ["best", "high", "medium", "low"]
        self.audio_quality_menu = ctk.CTkOptionMenu(
            yt_settings_frame,
            variable=self.audio_quality_var,
            values=audio_quality_options
        )
        self.audio_quality_menu.pack(side=tk.LEFT, padx=5)
        
        # Button frame
        self.button_frame = ctk.CTkFrame(self.main_frame)
        self.button_frame.pack(fill=tk.X, padx=5, pady=5)
        
        # Create download button
        self.download_button = ctk.CTkButton(
            self.button_frame,
            text="Download", 
            command=self._start_download,
            state="disabled"  # Start disabled
        )
        self.download_button.pack(side=tk.LEFT, padx=5)
        
        # Create folder button
        self.folder_btn = ctk.CTkButton(
            self.button_frame, 
            text="Change Folder", 
            command=self._change_folder
        )
        self.folder_btn.pack(side=tk.LEFT, padx=5)
        
        # Current folder label
        self.folder_label = ctk.CTkLabel(self.button_frame, text=f"Folder: {self.download_dir}")
        self.folder_label.pack(side=tk.LEFT, padx=5)
        
        # Initialize the GUI state
        self._check_link_types()
        
    def _check_link_types(self, *args):
        """
        Check entered URLs and show/hide appropriate settings.
        
        Returns:
            str: 'youtube' if YouTube URL, 'regular' otherwise
        """
        if isinstance(args[0], str) if args else False:
            # Called with a single URL
            url = args[0]
            return 'youtube' if ('youtube.com' in url or 'youtu.be' in url) else 'regular'
            
        # Called to update GUI
        lines = self._parse_urls()
        
        # Hide all frames initially
        self.options_frame.pack_forget()  # Hide options frame initially
        self.regular_frame.pack_forget()
        self.youtube_frame.pack_forget()
        
        # Enable/disable download button based on URLs
        if not lines:
            self.download_button.configure(state="disabled")
            # Set compact size when no settings shown
            self.root.geometry("800x600")
            return 'regular'
            
        self.download_button.configure(state="normal")
        
        # Show options frame and adjust window size if we have URLs
        self.options_frame.pack(fill=tk.BOTH, padx=5, pady=5)
        self.root.geometry("800x725")  # Expand for settings, maintain 800px width
        
        # Check if any URL is a YouTube URL
        has_youtube = any('youtube.com' in url.lower() or 'youtu.be' in url.lower() for url in lines)
        has_regular = any(not ('youtube.com' in url.lower() or 'youtu.be' in url.lower()) for url in lines)
        
        # Show frames based on URL types
        if has_youtube:
            self.youtube_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        if has_regular:
            self.regular_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        # Return the appropriate type for single URL handling
        return 'youtube' if has_youtube else 'regular'
        
    def _parse_urls(self):
        """
        Parse URLs from text input.
        
        Returns:
            list[str]: List of cleaned URLs
        """
        text = self.url_text.get("1.0", tk.END).strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]
        
    def _start_download(self):
        """
        Start downloading all entered URLs.
        """
        try:
            # Get current text and lines
            current_text = self.url_text.get("1.0", tk.END)
            all_lines = [line.strip() for line in current_text.splitlines() if line.strip()]
            if not all_lines:
                messagebox.showwarning("Warning", "Please enter at least one URL")
                return
                
            remaining_lines = []
            failed_urls = set()  # Use set to avoid duplicates
            
            # Process each line exactly once
            for line in all_lines:
                url = self._clean_url(line)
                
                # Skip empty URLs
                if not url:
                    remaining_lines.append(line)
                    continue
                    
                # Skip invalid protocols
                if not url.startswith(('http://', 'https://')):
                    remaining_lines.append(line)
                    failed_urls.add(url)
                    continue
                    
                # Skip already downloading URLs
                if url in self.active_urls:
                    remaining_lines.append(line)
                    continue
                    
                # Try to start the download
                try:
                    # Start download in a new thread
                    thread = threading.Thread(target=self._download_url, args=(url,))
                    thread.daemon = True
                    thread.start()
                    
                    # Only add to active URLs if thread started successfully
                    self.active_urls.add(url)
                except Exception as e:
                    self.logger.error(f"Failed to start download for {url}: {e}")
                    failed_urls.add(url)
                    remaining_lines.append(line)
            
            # Update text widget with remaining lines
            self.url_text.delete("1.0", tk.END)
            if remaining_lines:
                self.url_text.insert("1.0", "\n".join(remaining_lines) + "\n")
                
            # Show message if any URLs failed
            if failed_urls:
                failed_msg = "Failed to start downloads for the following URLs:\n" + "\n".join(failed_urls)
                messagebox.showwarning("Warning", failed_msg)
                
        except Exception as e:
            self.logger.error(f"Error in start_download: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to start downloads: {str(e)}")
        
    def _clean_url(self, url: str):
        """
        Clean URL by removing log messages and invalid characters.
        
        Args:
            url (str): Raw URL string
        
        Returns:
            str: Cleaned URL string
        """
        if not url:
            return ""
            
        # Split by common log patterns and take the last part
        url = url.split("INFO:")[-1]
        url = url.split("ERROR:")[-1]
        url = url.split("WARNING:")[-1]
        url = url.split("DEBUG:")[-1]
        
        # Find the last occurrence of http:// or https://
        if "http://" in url or "https://" in url:
            last_http = max(url.rfind("http://"), url.rfind("https://"))
            if last_http >= 0:
                url = url[last_http:]
                # Take only up to the next whitespace or newline
                if ' ' in url:
                    url = url.split()[0]
                if '\n' in url:
                    url = url.split('\n')[0]
        
        return url.strip()
        
    def _download_url(self, url: str):
        """
        Start downloading a URL.
        
        Args:
            url (str): URL to download
        """
        try:
            # Log after cleaning the URL
            self.logger.info(f"Starting download for URL: {url}")
            
            if 'youtube.com' in url.lower() or 'youtu.be' in url.lower():
                self._download_youtube(url, url)
            else:
                # Start regular download
                self.manager.download(
                    url=url,
                    on_progress=self.on_progress,
                    threads=self.threads_var.get()
                )
            
        except (InvalidURLError, UnsupportedURLError, NetworkError) as e:
            self.logger.error(f"Error downloading {url}: {e}", exc_info=True)
            handle_download_error(e)
            # Remove from active URLs on error
            self.active_urls.discard(url)
            
    def _download_youtube(self, url, download_id):
        """Handle YouTube download"""
        try:
            # Get options from GUI
            audio_only = self.audio_only_var.get()
            quality = self.quality_var.get() if not audio_only else None
            audio_quality = self.audio_quality_var.get()
            
            # Create progress bar
            self.download_frame.add_download(
                download_id=download_id,
                is_youtube=True,  # Use is_youtube instead of download_type
                is_audio=audio_only  # Use is_audio instead of audio_only
            )
            
            # Start download in separate thread
            thread = threading.Thread(
                target=self.manager.download_youtube,
                args=(url, download_id),
                kwargs={
                    'quality': quality,
                    'audio_quality': audio_quality,
                    'audio_only': audio_only,
                    'on_progress': lambda *args, **kwargs: self._do_gui_update(
                        download_id,
                        *args,
                        is_youtube=True,
                        is_audio=audio_only,
                        **kwargs
                    ),
                    'threads': self.threads_var.get()
                }
            )
            thread.daemon = True
            thread.start()
            
        except Exception as e:
            print(f"Error starting YouTube download: {e}")
            self.download_frame.remove_download(download_id)
            
    def on_progress(self, download_id: str, progress: float, speed: str = "", 
                   text: str = "", total_size: float = 0, downloaded_size: float = 0,
                   stats: dict = None, state: DownloadState = DownloadState.DOWNLOADING,
                   is_youtube: bool = False, is_audio: bool = False, component: str = None):
        """
        Progress callback for downloads.
        
        Args:
            download_id (str): ID of the download
            progress (float): Download progress percentage (0-100)
            speed (str, optional): Current download speed. Defaults to ""
            text (str, optional): Text to display. Defaults to ""
            total_size (float, optional): Total file size in bytes. Defaults to 0
            downloaded_size (float, optional): Downloaded size in bytes. Defaults to 0
            stats (dict, optional): Dictionary of download statistics. Defaults to None
            state (DownloadState, optional): Current download state. Defaults to DownloadState.DOWNLOADING
            is_youtube (bool, optional): Whether this is a YouTube download. Defaults to False
            is_audio (bool, optional): Whether this is an audio-only download. Defaults to False
            component (str, optional): For YouTube downloads, specifies "video" or "audio". Defaults to None
        """
        try:
            # Queue update to be processed by update thread
            self._do_gui_update(
                download_id=download_id,
                progress=progress,
                speed=speed,
                text=text,
                downloaded_size=downloaded_size,
                total_size=total_size,
                stats=stats,
                state=state,
                is_youtube=is_youtube,
                is_audio=is_audio,
                component=component
            )
        except Exception as e:
            self.logger.error(f"Error in progress callback: {e}")
            
    def on_cancel(self, download_id: str) -> None:
        """
        Handle download cancellation.
        
        Args:
            download_id (str): ID of the download to cancel
        """
        self._cancel_download(download_id)
        
    def _do_gui_update(self, download_id: str, progress: float, speed: str, text: str, 
                      title: str = None, downloaded_size: int = 0, total_size: int = 0,
                      stats: dict = None, state: DownloadState = DownloadState.DOWNLOADING,
                      is_youtube: bool = False, is_audio: bool = False, component: str = None):
        """
        Queue a GUI update to be processed by the update thread.
        
        Args:
            download_id (str): ID of the download
            progress (float): Download progress percentage (0-100)
            speed (str): Current download speed
            text (str): Text to display
            title (str, optional): Title to display. Defaults to None
            downloaded_size (int, optional): Downloaded size in bytes. Defaults to 0
            total_size (int, optional): Total file size in bytes. Defaults to 0
            stats (dict, optional): Dictionary of download statistics. Defaults to None
            state (DownloadState, optional): Current download state. Defaults to DownloadState.DOWNLOADING
            is_youtube (bool, optional): Whether this is a YouTube download. Defaults to False
            is_audio (bool, optional): Whether this is an audio-only download. Defaults to False
            component (str, optional): For YouTube downloads, specifies "video" or "audio". Defaults to None
        """
        self.update_queue.put({
            'download_id': download_id,
            'progress': progress,
            'speed': speed,
            'text': text,
            'title': title,
            'downloaded_size': downloaded_size,
            'total_size': total_size,
            'stats': stats,
            'state': state,
            'is_youtube': is_youtube,
            'is_audio': is_audio,
            'component': component
        })
        
    def _process_update_queue(self):
        """Process updates from the download queue"""
        while True:
            try:
                update = self.update_queue.get_nowait()
                download_id = update['download_id']
                progress = update['progress']
                speed = update.get('speed', '')
                text = update.get('text', '')
                title = update.get('title')
                total_size = update.get('total_size', 0)
                downloaded_size = update.get('downloaded_size', 0)
                stats = update.get('stats', {})
                state = update.get('state', DownloadState.PENDING)
                is_youtube = update.get('is_youtube', False)
                is_audio = update.get('is_audio', False)
                component = update.get('component')
                
                try:
                    if download_id not in self.download_frame.progress_bars:
                        # Add new progress bar if not exists
                        self.download_frame.add_download(
                            download_id=download_id,
                            is_youtube=is_youtube,
                            is_audio=is_audio
                        )
                        
                    # Update progress
                    if is_youtube:
                        self.download_frame.update_progress(
                            download_id=download_id,
                            text=text,
                            progress=progress,
                            component=component,
                            stats=stats,
                            speed=speed,
                            downloaded_size=downloaded_size,
                            total_size=total_size,
                            state=state
                        )
                    else:
                        self.download_frame.update_progress(
                            download_id=download_id,
                            text=text,
                            progress=progress,
                            speed=speed,
                            downloaded_size=downloaded_size,
                            total_size=total_size,
                            state=state
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error updating progress: {e}")
                    
            except Empty:
                break
                
            except Exception as e:
                self.logger.error(f"Error processing update: {e}")
                continue
                
        # Schedule next update check
        self.root.after(100, self._process_update_queue)
        
    def _start_update_thread(self):
        """
        Start the update processing thread.
        Creates a daemon thread to process GUI updates.
        """
        # Schedule the first update
        self.root.after(100, self._process_update_queue)  

    def _on_closing(self):
        """
        Handle window closing event.
        Cancels all downloads and shuts down the application.
        """
        try:
            # Cancel all active downloads
            self.stop_all_downloads = True
            for download_id in list(self.download_frame.progress_bars.keys()):
                if download_id in self.active_urls:
                    self._cancel_download(download_id)
            
            # Wait briefly for downloads to cancel
            self.root.after(100)
            
            # Clean up download frame
            if hasattr(self, 'download_frame'):
                for progress_bar in list(self.download_frame.progress_bars.values()):
                    if progress_bar.winfo_exists():
                        progress_bar.destroy()
                self.download_frame.progress_bars.clear()
                
                for youtube_bar in list(self.download_frame.youtube_bars.values()):
                    if youtube_bar.winfo_exists():
                        youtube_bar.destroy()
                self.download_frame.youtube_bars.clear()
            
            # Save any configuration changes
            Config.save_user_config()
            
            # Destroy the root window
            if self.root.winfo_exists():
                self.root.quit()
                self.root.destroy()
                
        except Exception as e:
            print(f"Error during shutdown: {e}")
            # Force quit even if there was an error
            if self.root.winfo_exists():
                self.root.quit()
                self.root.destroy()
        
    def _update_threads_label(self, value):
        """
        Update the threads value label.
        
        Args:
            value (int): New number of threads
        """
        self.threads_value_label.configure(text=str(int(float(value))))

    def _print_log(self, message: str):
        """
        Print a message to the download frame log.
        
        Args:
            message (str): Message to print
        """
        self.download_frame.add_log_message(message)

    def _cancel_download(self, download_id: str):
        """
        Cancel a specific download.
        
        Args:
            download_id (str): ID of download to cancel
        """
        try:
            # Cancel in download manager
            self.manager.cancel_download(download_id)
            
            # Remove from active URLs
            self.active_urls.discard(download_id)
            
            # Remove progress bar
            self.download_frame.remove_download(download_id)
            
        except Exception as e:
            self.logger.error(f"Error canceling download {download_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to cancel download: {e}")

    def _change_folder(self):
        """
        Change download directory.
        Opens a folder selection dialog.
        """
        new_dir = filedialog.askdirectory(
            initialdir=str(self.download_dir),  # Use our project's downloads folder as starting point
            title="Select Download Folder"
        )
        if new_dir:
            # Update download directory
            self.download_dir = Path(new_dir)
            self.download_dir.mkdir(parents=True, exist_ok=True)
            
            # Update download manager
            self.manager = DownloadManager(self.download_dir)
            
            # Update folder label
            self.folder_label.configure(text=f"Folder: {self.download_dir}")
            
            # Update active progress bars with new file paths
            for download_id, progress_bar in self.download_frame.progress_bars.items():
                # For regular downloads, download_id is the filename
                filename = Path(download_id).name
                new_filepath = str(self.download_dir / filename)
                progress_bar.set_filepath(new_filepath)
                
            # Update YouTube progress bars
            for download_id, youtube_bar in self.download_frame.youtube_bars.items():
                if youtube_bar.filepath:
                    filename = Path(youtube_bar.filepath).name
                    new_filepath = str(self.download_dir / filename)
                    youtube_bar.set_filepath(new_filepath)
            
            # Save configuration
            Config.DOWNLOAD_DIR = self.download_dir
            Config.save_user_config()
            
    def _toggle_quality_menu(self):
        """Toggle video quality menu based on audio only checkbox"""
        if self.audio_only_var.get():
            self.quality_menu.configure(state="disabled")
            self.audio_quality_menu.configure(state="normal")
        else:
            self.quality_menu.configure(state="normal")
            self.audio_quality_menu.configure(state="normal")

    def run(self):
        """
        Start the GUI.
        Enters the main event loop.
        """
        self.root.mainloop()
