import tkinter as tk
import customtkinter as ctk
import os
import subprocess
from tkinter import messagebox
from typing import Callable
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from core.download_state import DownloadState

class YouTubeProgressBar(ctk.CTkFrame):
    """Custom progress bar for YouTube downloads"""
    
    def __init__(self, master, download_id=None, cancel_callback=None, audio_only=False, **kwargs):
        super().__init__(master=master, **kwargs)
        
        self.download_id = download_id
        self.cancel_callback = cancel_callback
        self.video_progress = 0
        self.audio_progress = 0
        self.combined_progress = 0
        self.expanded = False
        self.video_filepath = None
        self.audio_filepath = None
        self.audio_only = audio_only
        
        # Configure grid weights for proper expansion
        self.grid_columnconfigure(0, weight=1)
        
        # Main container (for animation)
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(1, weight=1)  # For detail frame expansion
        
        # Basic info frame
        self.basic_frame = ctk.CTkFrame(self.container)
        self.basic_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.basic_frame.grid_columnconfigure(1, weight=1)
        
        # Title label
        self.title_label = ctk.CTkLabel(
            self.basic_frame, text="", anchor="w"
        )
        self.title_label.grid(row=0, column=0, columnspan=3, sticky="w", padx=5)
        
        # Cancel/Open button
        self.action_button = ctk.CTkButton(
            self.basic_frame, text="Cancel", width=60, height=25,
            command=self._on_cancel
        )
        self.action_button.grid(row=0, column=3, padx=5, pady=5)
        
        # Close button (X)
        self.close_button = ctk.CTkButton(
            self.basic_frame, text="×", width=25, height=25,
            command=self._on_close,
            fg_color="red", hover_color="darkred"
        )
        self.close_button.grid(row=0, column=4, padx=(0, 5), pady=5)
        
        if not audio_only:
            # Video progress
            self.video_label = ctk.CTkLabel(
                self.basic_frame, text="Video:", anchor="w"
            )
            self.video_label.grid(row=1, column=0, sticky="w", padx=5)
            
            self.video_progress_bar = ctk.CTkProgressBar(self.basic_frame)
            self.video_progress_bar.grid(row=1, column=1, columnspan=3, sticky="ew", padx=5)
            self.video_progress_bar.set(0)
            
            self.video_status = ctk.CTkLabel(
                self.basic_frame, text="0%", anchor="w"
            )
            self.video_status.grid(row=1, column=4, sticky="w", padx=5)
        
        # Audio progress
        audio_row = 2 if not audio_only else 1
        self.audio_label = ctk.CTkLabel(
            self.basic_frame, text="Audio:" if not audio_only else "Progress:", anchor="w"
        )
        self.audio_label.grid(row=audio_row, column=0, sticky="w", padx=5)
        
        self.audio_progress_bar = ctk.CTkProgressBar(self.basic_frame)
        self.audio_progress_bar.grid(row=audio_row, column=1, columnspan=3, sticky="ew", padx=5)
        self.audio_progress_bar.set(0)
        
        self.audio_status = ctk.CTkLabel(
            self.basic_frame, text="0%", anchor="w"
        )
        self.audio_status.grid(row=audio_row, column=4, sticky="w", padx=5)
        
        # Make all frames and widgets clickable
        for widget in [self, self.container, self.basic_frame, self.title_label,
                      self.video_label if not audio_only else None, self.audio_label,
                      self.video_status if not audio_only else None, self.audio_status]:
            if widget:  # Check for None
                widget.bind("<ButtonRelease-1>", self._toggle_expansion)
                # For Windows, also bind to Button-1
                widget.bind("<Button-1>", lambda e: "break")
            
        # Special handling for buttons to prevent expansion
        for button in [self.close_button, self.action_button]:
            button.bind("<Button-1>", lambda e: "break")  # Prevent event propagation
            button.bind("<ButtonRelease-1>", lambda e: "break")
            
        # Detailed info frame (hidden by default)
        self.detail_frame = ctk.CTkFrame(self.container)
        self.container.grid_rowconfigure(1, weight=1)  # Give row 1 weight for expansion
        
        # Import matplotlib and configure it for CTk
        plt.style.use('dark_background')
        
        # Initialize figure variables
        self.fig = None
        self.ax1 = None
        self.ax2 = None
        self.canvas = None
        
        # Stats labels
        self.stats_frame = ctk.CTkFrame(self.detail_frame)
        self.stats_frame.pack(fill="x", padx=5, pady=5)
        
        # Video stats
        if not audio_only:
            self.video_stats_frame = ctk.CTkFrame(self.stats_frame)
            self.video_stats_frame.pack(fill="x", padx=5, pady=2)
            
            ctk.CTkLabel(self.video_stats_frame, text="Video:").pack(side="left", padx=5)
            self.video_peak_speed = ctk.CTkLabel(self.video_stats_frame, text="Peak: -")
            self.video_peak_speed.pack(side="left", padx=5)
            self.video_avg_speed = ctk.CTkLabel(self.video_stats_frame, text="Avg: -")
            self.video_avg_speed.pack(side="left", padx=5)
            self.video_time = ctk.CTkLabel(self.video_stats_frame, text="Time: -")
            self.video_time.pack(side="left", padx=5)
        
        # Audio stats
        self.audio_stats_frame = ctk.CTkFrame(self.stats_frame)
        self.audio_stats_frame.pack(fill="x", padx=5, pady=2)
        
        ctk.CTkLabel(self.audio_stats_frame, text="Audio:").pack(side="left", padx=5)
        self.audio_peak_speed = ctk.CTkLabel(self.audio_stats_frame, text="Peak: -")
        self.audio_peak_speed.pack(side="left", padx=5)
        self.audio_avg_speed = ctk.CTkLabel(self.audio_stats_frame, text="Avg: -")
        self.audio_avg_speed.pack(side="left", padx=5)
        self.audio_time = ctk.CTkLabel(self.audio_stats_frame, text="Time: -")
        self.audio_time.pack(side="left", padx=5)
        
        # Configure grid
        self.grid_columnconfigure(0, weight=1)
        self.container.grid_columnconfigure(0, weight=1)
        self.basic_frame.grid_columnconfigure(2, weight=1)
        
        # Store download statistics
        self.video_stats = None
        self.audio_stats = None
        
        # Add hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.configure(border_width=1, border_color=self.cget("fg_color"))
        
    def _toggle_expansion(self, event=None):
        """Toggle the expansion of the progress bar to show/hide details"""
        print(f"YouTube progress bar toggle expansion called. Current state: {self.expanded}")
        self.expanded = not self.expanded
        print(f"New state: {self.expanded}")
        
        if self.expanded:
            # Create matplotlib figure if not exists
            if self.fig is None:
                self.fig, (self.ax1, self.ax2) = plt.subplots(2, 1, figsize=(6, 4))
                self.canvas = FigureCanvasTkAgg(self.fig, master=self.detail_frame)
                self.canvas.get_tk_widget().pack(fill="both", expand=True)
            
            # Show detail frame
            self.detail_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        else:
            # Hide detail frame
            self.detail_frame.grid_forget()
            
    def _update_graphs(self):
        """Update both video and audio graphs"""
        try:
            if not self.expanded or not self.fig:
                return

            self.ax1.clear()
            self.ax2.clear()

            # Plot video speed if not audio only
            if not self.audio_only and self.video_stats and 'timestamps' in self.video_stats and 'speeds' in self.video_stats:
                speeds_mb = [s / (1024 * 1024) for s in self.video_stats['speeds']]
                self.ax1.plot(self.video_stats['timestamps'], speeds_mb, 'b-', label='Video Speed (MB/s)')
                self.ax1.set_ylabel('Speed (MB/s)')
                self.ax1.grid(True)
                self.ax1.legend()

            # Plot audio speed
            if self.audio_stats and 'timestamps' in self.audio_stats and 'speeds' in self.audio_stats:
                speeds_mb = [s / (1024 * 1024) for s in self.audio_stats['speeds']]
                if self.audio_only:
                    # If audio only, use the first graph
                    self.ax1.plot(self.audio_stats['timestamps'], speeds_mb, 'g-', label='Audio Speed (MB/s)')
                    self.ax1.set_ylabel('Speed (MB/s)')
                    self.ax1.grid(True)
                    self.ax1.legend()
                else:
                    # If both video and audio, use the second graph
                    self.ax2.plot(self.audio_stats['timestamps'], speeds_mb, 'g-', label='Audio Speed (MB/s)')
                    self.ax2.set_xlabel('Time (s)')
                    self.ax2.set_ylabel('Speed (MB/s)')
                    self.ax2.grid(True)
                    self.ax2.legend()

            self.canvas.draw()

        except Exception as e:
            print(f"Error updating graphs: {e}")
            
    def update_progress(self, text=None, progress=None, component=None, filepath=None, stats=None, speed=None, downloaded_size=None, total_size=None, state=None):
        """Update progress bar and status"""
        try:
            print(f"YouTube progress bar update called: progress={progress}, component={component}")
            # Initialize progress values if not set
            if not hasattr(self, 'video_progress'):
                self.video_progress = 0
            if not hasattr(self, 'audio_progress'):
                self.audio_progress = 0
            
            if component == "video" and not self.audio_only:
                print(f"Updating video progress: {progress}")
                if progress is not None:
                    self.video_progress = progress
                    self.video_progress_bar.set(progress / 100.0)
                    status_text = f"{progress:.1f}%"
                    if speed:
                        status_text += f" • {speed}/s"
                    if total_size and downloaded_size:
                        status_text += f" • {self._format_size(downloaded_size)}/{self._format_size(total_size)}"
                    self.video_status.configure(text=status_text)
                if filepath:
                    self.video_filepath = filepath
                if stats:
                    self.video_stats = stats
                    if self.expanded:
                        self._update_video_statistics(stats)
                        self._update_graphs()

            elif component == "audio":
                print(f"Updating audio progress: {progress}")
                if progress is not None:
                    self.audio_progress = progress
                    self.audio_progress_bar.set(progress / 100.0)
                    status_text = f"{progress:.1f}%"
                    if speed:
                        status_text += f" • {speed}/s"
                    if total_size and downloaded_size:
                        status_text += f" • {self._format_size(downloaded_size)}/{self._format_size(total_size)}"
                    self.audio_status.configure(text=status_text)
                if filepath:
                    self.audio_filepath = filepath
                if stats:
                    self.audio_stats = stats
                    if self.expanded:
                        self._update_audio_statistics(stats)
                        self._update_graphs()

            # Update title if provided
            if text and not self.title_label.cget("text"):
                print(f"Setting title to: {text}")
                truncated_title = self._truncate_title(text)
                self.title_label.configure(text=truncated_title)

            # Calculate combined progress
            if self.audio_only:
                self.combined_progress = self.audio_progress
            else:
                # If video is done but audio isn't started, count video as 100%
                video_progress = 100 if self.video_progress >= 100 else self.video_progress
                # If audio is done but video isn't started, count audio as 100%
                audio_progress = 100 if self.audio_progress >= 100 else self.audio_progress
                self.combined_progress = (video_progress + audio_progress) / 2
            
            print(f"Combined progress: {self.combined_progress}")
            
            # Update button state if download is complete
            if self.combined_progress >= 100:
                print("Download complete, updating button")
                self.action_button.configure(
                    text="Open", 
                    command=lambda: self._open_file(self.audio_filepath if self.audio_only else self.video_filepath)
                )

        except Exception as e:
            print(f"Error updating progress: {e}")
            
    def _open_file(self, filepath):
        """Open the downloaded file"""
        if not filepath or not os.path.exists(filepath):
            messagebox.showerror("Error", "File not found")
            return
            
        try:
            if os.name == 'nt':  # Windows
                os.startfile(filepath)
            else:  # Linux/Mac
                subprocess.run(['xdg-open' if os.name == 'posix' else 'open', filepath])
        except Exception as e:
            messagebox.showerror("Error", f"Failed to open file: {str(e)}")
            
    def _update_video_statistics(self, stats: dict):
        """Update video statistics display"""
        try:
            if stats.get('peak_speed'):
                self.video_peak_speed.configure(
                    text=f"Peak: {self._format_speed(stats['peak_speed'])}/s"
                )
            if stats.get('avg_speed'):
                self.video_avg_speed.configure(
                    text=f"Avg: {self._format_speed(stats['avg_speed'])}/s"
                )
            if stats.get('total_time'):
                self.video_time.configure(
                    text=f"Time: {self._format_time(stats['total_time'])}"
                )
        except Exception as e:
            print(f"Error updating video statistics: {e}")
            
    def _update_audio_statistics(self, stats: dict):
        """Update audio statistics display"""
        try:
            if stats.get('peak_speed'):
                self.audio_peak_speed.configure(
                    text=f"Peak: {self._format_speed(stats['peak_speed'])}/s"
                )
            if stats.get('avg_speed'):
                self.audio_avg_speed.configure(
                    text=f"Avg: {self._format_speed(stats['avg_speed'])}/s"
                )
            if stats.get('total_time'):
                self.audio_time.configure(
                    text=f"Time: {self._format_time(stats['total_time'])}"
                )
        except Exception as e:
            print(f"Error updating audio statistics: {e}")
            
    def _format_speed(self, speed):
        """Format speed in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if speed < 1024:
                return f"{speed:.1f}{unit}"
            speed /= 1024
        return f"{speed:.1f}TB"
        
    def _format_time(self, time):
        """Format time in seconds to human readable string"""
        minutes, seconds = divmod(time, 60)
        hours, minutes = divmod(minutes, 60)
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
        
    def _truncate_title(self, title: str, max_length: int = 120) -> str:
        """Truncate title if longer than max_length"""
        if len(title) > max_length:
            return title[:max_length] + "..."
        return title
        
    def _on_close(self):
        """Handle close button click"""
        try:
            if self.cancel_callback and (self.video_progress < 100 or self.audio_progress < 100):
                # If either download is in progress, cancel it
                self.cancel_callback(self.download_id)
            # Remove the progress bar after a short delay
            self.after(500, self.destroy)
        except Exception as e:
            print(f"Error in close: {e}")
            
    def _on_cancel(self):
        """Handle cancel button click"""
        try:
            if self.cancel_callback:
                # Disable the button immediately to prevent multiple clicks
                self.action_button.configure(state="disabled")
                # Call the cancel callback
                self.cancel_callback(self.download_id)
                # Destroy the progress bar after a short delay
                self.after(500, self.destroy)
        except Exception as e:
            print(f"Error in cancel callback: {e}")
            
    def _format_size(self, size_bytes):
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def _on_enter(self, event):
        """Handle mouse enter event"""
        self.configure(border_color="#ffffff")  # Pure white
        
    def _on_leave(self, event):
        """Handle mouse leave event"""
        self.configure(border_color=self.cget("fg_color"))  # Match frame color
