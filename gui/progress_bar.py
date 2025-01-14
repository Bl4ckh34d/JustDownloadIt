"""
Progress bar widget for JustDownloadIt.

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

import tkinter as tk
import customtkinter as ctk
from typing import Optional, Callable
import os
import subprocess
from pathlib import Path
from tkinter import messagebox
from utils.errors import DownloaderError
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from core.download_state import DownloadState

class ProgressBar(ctk.CTkFrame):
    """Progress bar widget with detailed statistics"""
    
    def __init__(self, master, download_id=None, cancel_callback=None, **kwargs):
        """Initialize progress bar"""
        super().__init__(master, **kwargs)
        
        self.download_id = download_id
        self.cancel_callback = cancel_callback
        self.progress = 0
        self.filepath = None
        self.expanded = False
        self.stats = None  # Initialize stats
        self.state = DownloadState.PENDING  # Add state tracking
        
        # Configure grid weights for proper expansion
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        # Main container (for animation)
        self.container = ctk.CTkFrame(self)
        self.container.grid(row=0, column=0, sticky="nsew")
        self.container.grid_columnconfigure(0, weight=1)
        self.container.grid_rowconfigure(0, weight=1)  # Basic frame
        self.container.grid_rowconfigure(1, weight=1)  # Detail frame
        
        # Basic info frame
        self.basic_frame = ctk.CTkFrame(self.container)
        self.basic_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.basic_frame.grid_columnconfigure(1, weight=1)  # Progress bar
        
        # Top row: Filename and buttons
        self.top_frame = ctk.CTkFrame(self.basic_frame)
        self.top_frame.grid(row=0, column=0, columnspan=4, sticky="ew", padx=5, pady=(5,0))
        self.top_frame.grid_columnconfigure(0, weight=1)
        
        # Title label (filename)
        self.title_label = ctk.CTkLabel(
            self.top_frame, text="", anchor="w"
        )
        self.title_label.grid(row=0, column=0, sticky="w")
        
        # Cancel/Open button
        self.action_button = ctk.CTkButton(
            self.top_frame, text="Cancel", width=60, height=25,
            command=self._on_button_click
        )
        self.action_button.grid(row=0, column=1, padx=5)
        
        # Close button (X)
        self.close_button = ctk.CTkButton(
            self.top_frame, text="×", width=25, height=25,
            command=self._on_close,
            fg_color="red", hover_color="darkred"
        )
        self.close_button.grid(row=0, column=2)
        
        # Bottom row: Progress bar and status
        # Progress bar
        self.progress_bar = ctk.CTkProgressBar(self.basic_frame)
        self.progress_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=5, pady=(5,0))
        self.progress_bar.set(0)
        
        # Status label
        self.status_label = ctk.CTkLabel(
            self.basic_frame, text="0%", anchor="w"
        )
        self.status_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=5)
        
        # Bind update_progress to ensure it's properly attached to the instance
        self._update_progress = self.update_progress
        
        # Detailed info frame (hidden by default)
        self.detail_frame = ctk.CTkFrame(self.container)
        
        # Import matplotlib and configure it for CTk
        plt.style.use('dark_background')
        
        # Create figure for the graph
        self.fig, self.ax = plt.subplots(figsize=(6, 3))
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.detail_frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        
        # Stats labels
        self.stats_frame = ctk.CTkFrame(self.detail_frame)
        self.stats_frame.pack(fill="x", padx=5, pady=5)
        
        self.peak_speed_label = ctk.CTkLabel(self.stats_frame, text="Peak Speed: -")
        self.peak_speed_label.pack(side="left", padx=5)
        
        self.avg_speed_label = ctk.CTkLabel(self.stats_frame, text="Avg Speed: -")
        self.avg_speed_label.pack(side="left", padx=5)
        
        self.total_time_label = ctk.CTkLabel(self.stats_frame, text="Total Time: -")
        self.total_time_label.pack(side="left", padx=5)
        
        # Add hover effect
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.configure(border_width=1, border_color=self.cget("fg_color"))
        
        # Make all frames and widgets clickable
        for widget in [self, self.container, self.basic_frame, self.title_label, 
                      self.progress_bar, self.status_label]:
            widget.bind("<ButtonRelease-1>", self._toggle_expansion)
            # For Windows, also bind to Button-1
            widget.bind("<Button-1>", lambda e: "break")
            
        # Make progress bar's internal widgets clickable
        self.progress_bar.bind("<ButtonRelease-1>", self._toggle_expansion)
        self.progress_bar.bind("<Button-1>", lambda e: "break")
        
        # Special handling for buttons to prevent expansion
        for button in [self.close_button, self.action_button]:
            button.bind("<Button-1>", lambda e: "break")  # Prevent event propagation
            button.bind("<ButtonRelease-1>", lambda e: "break")
            
    def _toggle_expansion(self, event=None):
        """Toggle between expanded and collapsed state"""
        if self.expanded:
            # Collapse
            self.detail_frame.grid_forget()
            self.expanded = False
        else:
            # Expand
            self.detail_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
            self.expanded = True
            if hasattr(self, 'stats') and self.stats:
                self._update_statistics(self.stats)
                self._update_graph()
                
    def _update_graph(self):
        """Update the graph with current statistics"""
        if not self.stats:
            return
            
        self.ax.clear()
        
        # Plot speed over time
        if self.stats['timestamps'] and self.stats['speeds']:
            # Convert speeds to MB/s for better readability
            speeds_mb = [s / (1024 * 1024) for s in self.stats['speeds']]
            self.ax.plot(self.stats['timestamps'], speeds_mb, 'b-', label='Speed (MB/s)')
            self.ax.set_xlabel('Time (s)')
            self.ax.set_ylabel('Speed (MB/s)')
            self.ax.grid(True)
            self.ax.legend()
            
        self.canvas.draw()
        
        # Update stats labels
        if self.stats.get('peak_speed'):
            self.peak_speed_label.configure(
                text=f"Peak: {self._format_speed(self.stats['peak_speed'])}/s"
            )
        if self.stats.get('avg_speed'):
            self.avg_speed_label.configure(
                text=f"Avg: {self._format_speed(self.stats['avg_speed'])}/s"
            )
        if self.stats.get('total_time'):
            self.total_time_label.configure(
                text=f"Time: {self._format_time(self.stats['total_time'])}"
            )
            
    def _format_speed(self, speed_bytes):
        """Format speed in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if speed_bytes < 1024:
                return f"{speed_bytes:.1f} {unit}"
            speed_bytes /= 1024
        return f"{speed_bytes:.1f} TB"
        
    def _format_time(self, seconds):
        """Format time in seconds to human readable format"""
        if seconds < 60:
            return f"{seconds:.1f}s"
        minutes = seconds / 60
        if minutes < 60:
            return f"{minutes:.1f}m"
        hours = minutes / 60
        return f"{hours:.1f}h"
        
    def _on_cancel(self):
        """
        Handle the cancel button click event.
        If download is in progress, calls the cancel callback.
        If download is complete, closes the progress bar.
        """
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
            
    def _on_close(self):
        """
        Handle the close button click event.
        Destroys the progress bar widget and removes it from the parent's tracking.
        """
        try:
            # First, cancel any ongoing download
            if self.cancel_callback and self.progress < 100:
                self.cancel_callback(self.download_id)
            
            # Clean up matplotlib resources
            if hasattr(self, 'fig') and self.fig:
                plt.close(self.fig)
            
            # Remove all widget bindings
            for widget in [self, self.container, self.basic_frame, self.title_label, 
                         self.progress_bar, self.status_label]:
                if widget.winfo_exists():
                    widget.unbind("<ButtonRelease-1>")
                    widget.unbind("<Button-1>")
            
            # Destroy the widget
            if self.winfo_exists():
                self.destroy()
                
        except Exception as e:
            print(f"Error closing progress bar: {e}")
            
    def set_filepath(self, filepath: str):
        """Set the filepath and update title"""
        if filepath and os.path.isabs(filepath):
            self.filepath = filepath
            self.title_label.configure(text=os.path.basename(filepath))

    def update_progress(self, text=None, progress=None, speed=None, downloaded_size=None, 
                       total_size=None, stats=None, state=None):
        """Update progress bar and status"""
        if progress is not None:
            self.progress = progress
            self.progress_bar.set(progress / 100.0)
            status_text = f"{progress:.1f}%"
            if speed:
                status_text += f" • {speed}/s"
            if total_size and downloaded_size:
                status_text += f" • {self._format_size(downloaded_size)}/{self._format_size(total_size)}"
            self.status_label.configure(text=status_text)
            
        if text and not self.title_label.cget("text"):
            # If we have a filepath, use that for the title
            if self.filepath:
                self.title_label.configure(text=os.path.basename(self.filepath))
            # Otherwise use the text as title
            else:
                self.title_label.configure(text=text)
            
        if stats:
            self.stats = stats
            if self.expanded:
                self._update_statistics(stats)
                self._update_graph()
                
        if state:
            self.state = state
            
        if state == DownloadState.COMPLETED or progress == 100:
            self.action_button.configure(text="Open", command=self._open_file)
            
    def _on_button_click(self):
        """Handle button click based on current state"""
        if self.state == DownloadState.COMPLETED:
            self._open_file()
        else:
            # Call the cancel callback if provided
            if self.cancel_callback:
                self.cancel_callback()
                
    def _open_file(self):
        """Open the downloaded file using the default system application"""
        try:
            print(f"Opening file with filepath: {self.filepath}")
            
            if not self.filepath or not os.path.isabs(self.filepath):
                print("Error: Invalid filepath")
                messagebox.showerror("Error", "Invalid file path")
                return
                
            print(f"File exists: {os.path.exists(self.filepath)}")
            if not os.path.exists(self.filepath):
                print(f"Error: File does not exist at path: {self.filepath}")
                messagebox.showerror("Error", f"File not found: {self.filepath}")
                return
                
            # Convert to absolute path and normalize slashes for Windows
            abs_path = os.path.abspath(self.filepath)
            print(f"Absolute path: {abs_path}")
            
            # Use the default system application to open the file
            if os.name == 'nt':  # Windows
                try:
                    print("Attempting to open with os.startfile")
                    os.startfile(abs_path)
                except Exception as e:
                    print(f"os.startfile failed: {e}")
                    print("Attempting to open with explorer.exe")
                    try:
                        subprocess.run(['explorer', abs_path], check=True)
                        print("Successfully opened with explorer.exe")
                    except Exception as e:
                        print(f"explorer.exe failed: {e}")
                        messagebox.showerror("Error", f"Could not open file: {e}")
            else:  # Linux/Mac
                subprocess.run(['xdg-open' if os.name == 'posix' else 'open', abs_path])
                
        except Exception as e:
            print(f"Error opening file: {e}")
            messagebox.showerror("Error", f"Could not open file: {e}")
            
    def _update_stats(self, stats: dict):
        """
        Update the statistics labels with new values.
        
        Args:
            stats (dict): Dictionary containing download statistics:
                - speed: Current download speed
                - eta: Estimated time remaining
                - progress: Download progress percentage
                - size: Total file size
                - downloaded: Amount downloaded so far
        """
        try:
            if stats.get('peak_speed'):
                self.peak_speed_label.configure(
                    text=f"Peak: {self._format_speed(stats['peak_speed'])}/s"
                )
            if stats.get('avg_speed'):
                self.avg_speed_label.configure(
                    text=f"Avg: {self._format_speed(stats['avg_speed'])}/s"
                )
            if stats.get('total_time'):
                self.total_time_label.configure(
                    text=f"Time: {self._format_time(stats['total_time'])}"
                )
        except Exception as e:
            print(f"Error updating statistics: {e}")
            
    def _format_size(self, size_bytes: float) -> str:
        """Format size in bytes to human readable format"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size_bytes < 1024:
                return f"{size_bytes:.1f} {unit}"
            size_bytes /= 1024
        return f"{size_bytes:.1f} TB"

    def set_cancel_callback(self, callback: Callable):
        """
        Set the callback function to be called when cancel button is clicked.
        
        Args:
            callback (Callable): Function to call when cancel button is clicked
        """
        self.cancel_callback = callback

    def _on_enter(self, event):
        """Handle mouse enter event"""
        self.configure(border_color="#ffffff")  # Pure white
        
    def _on_leave(self, event):
        """Handle mouse leave event"""
        self.configure(border_color=self.cget("fg_color"))  # Match frame color
