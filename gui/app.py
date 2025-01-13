from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
import logging
import threading
from queue import Queue, Empty
import re
from typing import Dict, Optional, Callable
import uuid

from core.config import Config
from core.download_manager import DownloadManager
from utils.errors import (
    DownloaderError, NetworkError, URLError, 
    InvalidURLError, UnsupportedURLError, 
    handle_download_error
)
from utils.logger import DownloaderLogger
from .progress_bar_yt import YouTubeProgressBar
from .download_frame import DownloadFrame

class DownloaderApp:
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
        self.options_frame.pack_forget()  # Hide options frame initially
        
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
        
        # Show frames based on URL types
        self.regular_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
            
        return 'regular'
        
    def _parse_urls(self) -> list[str]:
        """Parse URLs from text input"""
        text = self.url_text.get("1.0", tk.END).strip()
        if not text:
            return []
        return [line.strip() for line in text.split('\n') if line.strip()]
        
    def _start_download(self):
        """Start downloading the URL"""
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
        
    def _download_url(self, url: str):
        """Start downloading a URL"""
        try:
            # Log after cleaning the URL
            self.logger.info(f"Starting download for URL: {url}")
            
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
            
    def on_progress(self, download_id: str, progress: float, speed: str = "", 
                   text: str = "", total_size: float = 0, downloaded_size: float = 0):
        """Progress callback for downloads"""
        try:
            self.update_queue.put({
                'download_id': download_id,
                'progress': progress,
                'speed': speed,
                'text': text,
                'total_size': total_size,
                'downloaded_size': downloaded_size
            })
        except Exception as e:
            self.logger.error(f"Error in progress callback: {e}", exc_info=True)
            
    def _process_update_queue(self):
        """Process updates from the update queue"""
        try:
            while True:
                try:
                    # Get update from queue
                    update = self.update_queue.get_nowait()
                    
                    # Extract update info
                    download_id = update['download_id']
                    progress = update['progress']
                    speed = update.get('speed', '')
                    text = update['text']
                    total_size = update.get('total_size', 0)
                    downloaded_size = update.get('downloaded_size', 0)
                    
                    # Update progress if bar exists
                    if download_id in self.download_frame.progress_bars:
                        self.download_frame.update_progress(
                            download_id=download_id,
                            progress=progress,
                            speed=speed,
                            text=text,
                            total_size=total_size,
                            downloaded_size=downloaded_size
                        )
                    else:
                        # Create new progress bar
                        progress_bar = self.download_frame.add_download(
                            download_id=download_id,
                            text=text if text else download_id,
                            cancel_callback=lambda did=download_id: self._cancel_download(did)
                        )
                        
                        if progress_bar is None:
                            self.logger.debug(f"Progress bar already exists for {download_id}")
                            continue
                    
                    # Remove completed downloads
                    if progress >= 100 and "(Complete)" in text:
                        # Give UI time to show 100% before removing
                        self.root.after(1000, lambda: self.download_frame.remove_download(download_id))
                    elif "Error" in text:
                        self.download_frame.remove_download(download_id)
                    
                except Empty:
                    break
                    
        except Exception as e:
            self.logger.error(f"Error processing update queue: {e}", exc_info=True)
            
        # Schedule next update
        self.root.after(50, self._process_update_queue)
        
    def _do_gui_update(self, download_id: str, progress: float, speed: str, text: str, title: str = None, downloaded_size: int = 0, total_size: int = 0):
        """Queue a GUI update to be processed by the update thread"""
        try:
            self.update_queue.put({
                'download_id': download_id,
                'progress': progress,
                'speed': speed,
                'text': text,
                'total_size': total_size,
                'downloaded_size': downloaded_size
            })
        except Exception as e:
            self.logger.error(f"Error queueing GUI update: {e}", exc_info=True)
            
    def _start_update_thread(self):
        """Start the update processing thread"""
        # Schedule the first update
        self.root.after(50, self._process_update_queue)  

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

class DownloadFrame(ctk.CTkScrollableFrame):
    """Frame to manage multiple download progress bars"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self.progress_bars = {}  # Store progress bars by download ID
        
    def add_download(self, download_id: str, text: str = "", cancel_callback: Callable = None) -> None:
        """Add a new download progress bar
        
        Args:
            download_id: Unique ID for the download
            text: Initial text to display
            cancel_callback: Callback function to cancel the download
        """
        try:
            if download_id in self.progress_bars:
                return
                
            # Create frame to hold progress bar and cancel button
            frame = ctk.CTkFrame(self)
            frame.pack(fill=tk.X, padx=5, pady=2)
            
            # Title label
            title_label = ctk.CTkLabel(frame, text=text, anchor="w")
            title_label.pack(side=tk.TOP, padx=5, pady=(5,0), fill=tk.X)
            
            # Progress bar
            progress_bar = ctk.CTkProgressBar(frame, height=15)
            progress_bar.set(0)
            progress_bar.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
            
            # Cancel button
            cancel_button = ctk.CTkButton(frame, text="Cancel", width=60, command=cancel_callback)
            cancel_button.pack(side=tk.RIGHT, padx=5)
            
            # Store references
            self.progress_bars[download_id] = {
                'frame': frame,
                'title': title_label,
                'progress': progress_bar,
                'cancel': cancel_button,
                'speed': None
            }
            
        except Exception as e:
            self.logger.error(f"Error adding download: {e}", exc_info=True)
            return None
        
    def update_progress(self, download_id: str, progress: float, speed: str = "", text: str = "",
                       total_size: float = 0, downloaded_size: float = 0) -> None:
        """Update progress for a download"""
        if download_id not in self.progress_bars:
            return
            
        progress_data = self.progress_bars[download_id]
        progress_data['progress'].set(progress / 100)
        if text:
            progress_data['title'].configure(text=text)
        if speed:
            if not progress_data['speed']:
                speed_label = ctk.CTkLabel(progress_data['frame'], text=speed, anchor="w")
                speed_label.pack(side=tk.LEFT, padx=5)
                progress_data['speed'] = speed_label
            else:
                progress_data['speed'].configure(text=speed)
                
    def remove_download(self, download_id: str) -> None:
        """Remove a download progress bar"""
        if download_id not in self.progress_bars:
            return
            
        # Remove regular progress bar
        progress_data = self.progress_bars[download_id]
        progress_data['frame'].destroy()
            
        del self.progress_bars[download_id]
