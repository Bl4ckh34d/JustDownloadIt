from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import logging
import threading
from queue import Queue, Empty
import re
from typing import Dict, Optional
import uuid

from core.config import Config
from core.download_manager import DownloadManager
from utils.errors import (
    DownloaderError, NetworkError, URLError, 
    InvalidURLError, UnsupportedURLError, 
    handle_download_error
)
from utils.logger import DownloaderLogger
from .download_frame import DownloadFrame

class DownloaderApp:
    def __init__(self):
        """Initialize the application"""
        self.root = ctk.CTk()
        self.root.title("JustDownloadIt")
        self.root.geometry("800x400")  # Start with compact size, 800px width
        self.root.minsize(800, 400)  # Minimum size when no settings shown
        
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
        
        # YouTube options frame (hidden by default)
        self.youtube_frame = ctk.CTkFrame(self.options_frame)
        
        youtube_title = ctk.CTkLabel(self.youtube_frame, text="YouTube Options", font=("Arial", 12, "bold"))
        youtube_title.pack(anchor=tk.W, padx=5, pady=2)
        
        # YouTube quality dropdown
        self.selected_quality_var = tk.StringVar(value="1080p + 160k")
        
        # Quality dropdown frame
        self.quality_frame = ctk.CTkFrame(self.youtube_frame)
        self.youtube_quality_label = ctk.CTkLabel(self.quality_frame, text="Preferred Quality:")
        self.youtube_quality_label.pack(side=tk.LEFT, padx=5)
        self.youtube_quality_menu = ctk.CTkOptionMenu(
            self.quality_frame,
            values=[
                "2160p + 160k",  # 4K
                "1440p + 160k",  # 2K
                "1080p + 160k",  # Full HD
                "720p + 128k",   # HD
                "480p + 128k",   # SD
                "360p + 96k",    # Low
                "240p + 96k",    # Very Low
                "144p + 70k"     # Lowest
            ],
            variable=self.selected_quality_var,
            width=200
        )
        self.youtube_quality_menu.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        
        # Hide frame initially
        self.quality_frame.pack_forget()
        
        # Regular download options frame
        self.regular_frame = ctk.CTkFrame(self.options_frame)
        regular_title = ctk.CTkLabel(self.regular_frame, text="Regular Download Options", font=("Arial", 12, "bold"))
        regular_title.pack(anchor=tk.W, padx=5, pady=2)
        
        # Threads setting
        threads_frame = ctk.CTkFrame(self.regular_frame)
        threads_frame.pack(fill=tk.X, padx=5, pady=2)
        
        threads_label = ctk.CTkLabel(threads_frame, text="Threads:")
        threads_label.pack(side=tk.LEFT, padx=5)
        
        self.threads_slider = ctk.CTkSlider(
            threads_frame,
            from_=1,
            to=64,
            variable=self.threads_var,
            command=self._update_threads_label
        )
        self.threads_slider.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        
        self.threads_value_label = ctk.CTkLabel(threads_frame, text=str(self.threads_var.get()))
        self.threads_value_label.pack(side=tk.LEFT, padx=5)
        
        # Attempts setting
        attempts_frame = ctk.CTkFrame(self.regular_frame)
        attempts_frame.pack(fill=tk.X, padx=5, pady=2)
        
        attempts_label = ctk.CTkLabel(attempts_frame, text="Attempts:")
        attempts_label.pack(side=tk.LEFT, padx=5)
        
        self.attempts_entry = ctk.CTkEntry(attempts_frame, width=50, textvariable=self.attempts_var)
        self.attempts_entry.pack(side=tk.LEFT, padx=5)
        
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
        
    def _check_link_types(self, *args) -> str:
        """Check entered URLs and show/hide appropriate settings
        
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
        self.youtube_frame.pack_forget()
        self.regular_frame.pack_forget()
        self.options_frame.pack_forget()  # Hide options frame initially
        
        # Enable/disable download button based on URLs
        if not lines:
            self.download_button.configure(state="disabled")
            # Set compact size when no settings shown
            self.root.geometry("800x400")
            return 'regular'
            
        self.download_button.configure(state="normal")
        
        has_youtube = any(("youtube.com" in ln or "youtu.be" in ln) for ln in lines)
        has_regular = any(not ("youtube.com" in ln or "youtu.be" in ln) for ln in lines)
        
        # Show options frame and adjust window size if we have URLs
        if has_youtube or has_regular:
            self.options_frame.pack(fill=tk.BOTH, padx=5, pady=5)
            self.root.geometry("800x525")  # Expand for settings, maintain 800px width
        
        # Show frames based on URL types
        if has_youtube and has_regular:
            # Both frames - pack side by side with equal width
            self.youtube_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
            self.regular_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        elif has_youtube:
            # Only YouTube - center it
            self.youtube_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        elif has_regular:
            # Only Regular - center it
            self.regular_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        # Show appropriate YouTube dropdowns
        if has_youtube:
            self.quality_frame.pack(fill=tk.X, padx=5, pady=5)
            
        return 'youtube' if has_youtube else 'regular'
        
    def _parse_urls(self) -> list[str]:
        """Parse URLs from text input"""
        text = self.url_text.get("1.0", tk.END).strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]
        
    def _start_download(self):
        """Start downloading the URL"""
        try:
            # Get URLs from input
            urls = self._parse_urls()
            if not urls:
                messagebox.showwarning("Warning", "Please enter at least one URL")
                return
            
            # Start downloads in parallel
            for url in urls:
                # Clean and validate URL
                url = self._clean_url(url)
                
                if not url:
                    self.logger.warning("Empty URL after cleaning, skipping")
                    continue
                    
                if not url.startswith(('http://', 'https://')):
                    self.logger.warning(f"Unsupported URL protocol: {url}, skipping")
                    continue
                    
                # Check if URL is already being downloaded
                if url in self.active_urls:
                    self.logger.info(f"URL already downloading: {url}, skipping")
                    continue
                    
                # Add to active URLs
                self.active_urls.add(url)
                
                # Start download in a new thread
                thread = threading.Thread(target=self._download_url, args=(url,))
                thread.daemon = True
                thread.start()
                
        except Exception as e:
            self.logger.error(f"Error in start_download: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to start downloads: {str(e)}")
            
    def _clean_url(self, url: str) -> str:
        """Clean URL by removing log messages and invalid characters
        
        Args:
            url: Raw URL string
            
        Returns:
            Cleaned URL string
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
        
    def _download_url(self, url: str) -> None:
        """Start downloading a URL"""
        try:
            # Log after cleaning the URL
            self.logger.info(f"Starting download for URL: {url}")
            
            def on_progress(download_id: str, progress: float, speed: str, text: str, total_size: float = 0, downloaded_size: float = 0, remove: bool = False):
                """Progress callback"""
                try:
                    # Queue update for GUI thread
                    self.update_queue.put({
                        'download_id': download_id,
                        'progress': progress,
                        'speed': speed,
                        'text': text,
                        'total_size': total_size,
                        'downloaded_size': downloaded_size,
                        'remove': remove
                    })
                except Exception as e:
                    self.logger.error(f"Error in progress callback: {e}", exc_info=True)
            
            # Start download based on URL type
            if "youtube.com" in url or "youtu.be" in url:
                self.logger.info("Starting YouTube download")
                self.manager.download_youtube(
                    url=url,
                    preferred_quality=self.selected_quality_var.get(),
                    on_progress=on_progress,
                    threads=self.threads_var.get()
                )
            else:
                self.logger.info("Starting standard download")
                self.manager.download(
                    url=url,
                    on_progress=on_progress,
                    threads=self.threads_var.get()
                )
                
        except (InvalidURLError, UnsupportedURLError) as e:
            # Handle URL validation errors
            title, message = handle_download_error(e)
            messagebox.showerror(title, message)
            self.logger.warning(f"Invalid URL entered: {str(e)}")
            
        except NetworkError as e:
            # Handle network errors
            title, message = handle_download_error(e)
            messagebox.showerror(title, message)
            self.logger.error(f"Network error: {str(e)}")
            
        except Exception as e:
            # Handle unexpected errors
            title, message = handle_download_error(e)
            messagebox.showerror(title, message)
            self.logger.error(f"Unexpected error: {str(e)}", exc_info=True)
            
        finally:
            # Remove URL from active downloads
            self.active_urls.discard(url)

    def _process_update_queue(self):
        """Process updates from the update queue"""
        try:
            while True:
                try:
                    # Get next update
                    update = self.update_queue.get_nowait()
                    
                    download_id = update['download_id']
                    progress = update['progress']
                    speed = update['speed']
                    text = update['text']
                    total_size = update.get('total_size', 0)
                    downloaded_size = update.get('downloaded_size', 0)
                    remove = update.get('remove', False)
                    
                    # Handle YouTube download pairs
                    is_youtube = "_video" in download_id or "_audio" in download_id
                    if is_youtube:
                        base_id = download_id.replace("_video", "").replace("_audio", "")
                        video_id = f"{base_id}_video"
                        audio_id = f"{base_id}_audio"
                        
                        # Check if this is a removal request
                        if remove:
                            # Only remove both bars if both downloads are complete
                            video_bar = self.download_frame.progress_bars.get(video_id)
                            audio_bar = self.download_frame.progress_bars.get(audio_id)
                            
                            if video_bar and audio_bar:
                                video_progress = video_bar.progress_bar.get()
                                audio_progress = audio_bar.progress_bar.get()
                                
                                if video_progress >= 1.0 and audio_progress >= 1.0:
                                    # Both complete, remove both bars
                                    self.download_frame.remove_download(video_id)
                                    self.download_frame.remove_download(audio_id)
                        else:
                            # Regular progress update
                            self._do_gui_update(download_id, progress, speed, text, total_size=total_size, downloaded_size=downloaded_size)
                    else:
                        # Regular download
                        if remove or progress >= 100:
                            # Remove progress bar when complete
                            self.download_frame.remove_download(download_id)
                        else:
                            # Regular progress update
                            self._do_gui_update(download_id, progress, speed, text, total_size=total_size, downloaded_size=downloaded_size)
                    
                except Empty:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error processing update queue: {e}", exc_info=True)
            
        finally:
            # Schedule next update
            self.root.after(100, self._process_update_queue)

    def _do_gui_update(self, download_id: str, progress: float, speed: str, text: str, title: str = None, downloaded_size: int = 0, total_size: int = 0):
        """Perform actual GUI update in main thread"""
        try:
            # Add progress bar if it doesn't exist
            if download_id not in self.download_frame.progress_bars:
                self.logger.debug(f"Creating progress bar for {download_id}")
                display_name = text if text else download_id
                self.download_frame.add_download(
                    download_id=download_id,
                    display_name=display_name,
                    color="#007bff",  # Blue for downloads
                    on_cancel=lambda: self._cancel_download(download_id)
                )
            
            # Update progress bar
            self.logger.debug(f"Updating progress bar for {download_id}: {progress}% at {speed}")
            self.download_frame.update_progress(
                download_id, progress, speed, text,
                total_size, downloaded_size
            )
            
        except Exception as e:
            self.logger.error(f"Error updating GUI: {e}", exc_info=True)
            
    def _remove_youtube_progress_bars(self, video_id: str):
        """Remove both video and audio progress bars for a completed YouTube download"""
        try:
            self.download_frame.remove_download(video_id)  # Remove video bar
            self.download_frame.remove_download(f"{video_id}_audio")  # Remove audio bar
            
            # Hide download frame if no active downloads
            if not self.download_frame.progress_bars:
                self.download_frame.pack_forget()
                
        except Exception as e:
            self.logger.error(f"Failed to remove YouTube progress bars for {video_id}: {e}", exc_info=True)
            
    def _start_update_thread(self):
        """Start the update processing thread"""
        # Schedule the first update
        self.root.after(100, self._process_update_queue)
        
    def _on_closing(self):
        """Handle window closing event"""
        if self.manager.active_downloads:
            if messagebox.askokcancel("Quit", "There are active downloads. Cancel them and quit?"):
                self.shutdown()
        else:
            self.shutdown()
            
    def shutdown(self):
        """Gracefully shutdown the application"""
        self.logger.info("Initiating graceful shutdown...")
        
        # Set stop flag first
        self.stop_all_downloads = True
        
        # Stop the update queue processing
        try:
            self.update_queue.put(None)  # Sentinel value to stop processing
        except Exception as e:
            self.logger.error(f"Error stopping update queue: {e}")
        
        # Cancel all active downloads
        active_downloads = list(self.manager.active_downloads.keys())
        for download_id in active_downloads:
            try:
                self.logger.info(f"Cancelling download: {download_id}")
                self._cancel_download(download_id)
            except Exception as e:
                self.logger.error(f"Error cancelling download {download_id}: {e}")
        
        # Clear all GUI elements before destroying window
        try:
            if hasattr(self, 'download_frame'):
                for download_id in list(self.download_frame.progress_bars.keys()):
                    self.download_frame.remove_download(download_id)
        except Exception as e:
            self.logger.error(f"Error clearing download frame: {e}")
        
        # Wait briefly for downloads to cancel
        try:
            for _ in range(5):  # Wait up to 0.5 seconds
                if not self.manager.active_downloads:
                    break
                self.root.update()
                self.root.after(100)
        except Exception as e:
            self.logger.error(f"Error waiting for downloads to cancel: {e}")
        
        # Destroy the root window
        try:
            self.root.quit()
            self.root.destroy()
        except Exception as e:
            self.logger.error(f"Error destroying window: {e}")
        
        self.logger.info("Shutdown complete")
        
    def _update_threads_label(self, value):
        """Update the threads value label"""
        self.threads_value_label.configure(text=str(int(float(value))))

    def _print_log(self, message: str):
        """Print a message to the download frame log"""
        self.download_frame.add_log_message(message)

    def _cancel_download(self, download_id: str):
        """Cancel a specific download"""
        try:
            self.logger.info(f"Cancelling download: {download_id}")
            self.manager.cancel_download(download_id)
            
            # Remove from active URLs if standard download
            status = self.manager.get_download_status(download_id)
            if status and hasattr(status, 'url'):
                self.active_urls.discard(status.url)
                
        except Exception as e:
            self.logger.error(f"Error cancelling download {download_id}: {e}", exc_info=True)
            messagebox.showerror("Error", f"Failed to cancel download: {e}")

    def _change_folder(self):
        """Change download directory"""
        new_dir = filedialog.askdirectory(
            initialdir=str(self.download_dir),  # Use our project's downloads folder as starting point
            title="Select Download Folder"
        )
        if new_dir:
            self.download_dir = Path(new_dir)
            self.manager = DownloadManager(self.download_dir)
            self.folder_label.configure(text=f"Folder: {self.download_dir}")

    def run(self):
        """Start the GUI"""
        self.root.mainloop()
