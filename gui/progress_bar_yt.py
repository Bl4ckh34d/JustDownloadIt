import tkinter as tk
import customtkinter as ctk
import os
from tkinter import messagebox
from typing import Callable

class YouTubeProgressBar(ctk.CTkFrame):
    """A custom progress bar widget for YouTube downloads with two stacked progress bars"""
    
    def __init__(self, master, download_id: str, text: str = "", cancel_callback: Callable = None):
        """Initialize progress bar frame"""
        super().__init__(master)
        
        self.download_id = download_id
        self.cancel_callback = cancel_callback
        self.video_progress = 0
        self.audio_progress = 0
        self.video_size = 0
        self.audio_size = 0
        self.filepath = None  # Store filepath for opening later
        
        # Create main content frame
        self.content = ctk.CTkFrame(self)
        self.content.pack(fill=tk.X, expand=True, padx=5, pady=2)
        
        # Create top row with title and close button
        self.top_row = ctk.CTkFrame(self.content)
        self.top_row.pack(fill=tk.X, padx=5, pady=(2,0))
        
        # Title label (left-aligned)
        self.title_label = ctk.CTkLabel(self.top_row, text=text)
        self.title_label.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Close button (right-aligned, small red X)
        self.close_button = ctk.CTkButton(self.top_row, text="×", width=20, height=20, 
                                        fg_color="red", hover_color="darkred",
                                        command=self._on_close)
        self.close_button.pack(side=tk.RIGHT, padx=(5,0))
        
        # Video section
        self.video_frame = ctk.CTkFrame(self.content)
        self.video_frame.pack(fill=tk.X, padx=5, pady=(0,2))
        
        self.video_label = ctk.CTkLabel(self.video_frame, text="Video")
        self.video_label.pack(side=tk.LEFT)
        
        self.video_bar = ctk.CTkProgressBar(self.video_frame)
        self.video_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.video_bar.set(0)
        
        self.video_speed = ctk.CTkLabel(self.video_frame, text="0 MB/s")
        self.video_speed.pack(side=tk.LEFT, padx=5)
        
        self.video_cancel = ctk.CTkButton(self.video_frame, text="Cancel", 
                                        command=lambda: self._on_cancel('video'),
                                        width=60, height=25)  # Reduced size
        self.video_cancel.pack(side=tk.LEFT, padx=5)
        
        # Audio section
        self.audio_frame = ctk.CTkFrame(self.content)
        self.audio_frame.pack(fill=tk.X, padx=5, pady=(0,2))
        
        self.audio_label = ctk.CTkLabel(self.audio_frame, text="Audio")
        self.audio_label.pack(side=tk.LEFT)
        
        self.audio_bar = ctk.CTkProgressBar(self.audio_frame)
        self.audio_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.audio_bar.set(0)
        
        self.audio_speed = ctk.CTkLabel(self.audio_frame, text="0 MB/s")
        self.audio_speed.pack(side=tk.LEFT, padx=5)
        
        self.audio_cancel = ctk.CTkButton(self.audio_frame, text="Cancel", 
                                        command=lambda: self._on_cancel('audio'),
                                        width=60, height=25)  # Reduced size
        self.audio_cancel.pack(side=tk.LEFT, padx=5)
        
    def set_cancel_callback(self, callback):
        """Set callback for cancel button"""
        self.cancel_callback = callback
        
    def destroy(self):
        """Override destroy to prevent premature removal"""
        if self.video_progress < 100 or self.audio_progress < 100:
            if self.cancel_callback:
                self.cancel_callback(self.download_id)
        super().destroy()
        
    def update(self, progress: float, speed: str = "", text: str = "", 
               total_size: float = 0, downloaded_size: float = 0):
        """Override parent update to prevent auto-removal
        
        This method is called by the parent class's update mechanism.
        We override it to do nothing since we handle updates through update_progress.
        """
        pass

    def update_progress(self, component: str, progress: float, speed: str = "", 
                       text: str = "", total_size: float = 0, downloaded_size: float = 0,
                       format_size: float = 0):
        """Update progress for video or audio component"""
        try:
            # If text indicates completion, ensure progress is 100%
            if text and "(Complete)" in text:
                progress = 100.0
                # Store filepath from the text
                if text and "Saved to:" in text:
                    self.filepath = text.split("Saved to:", 1)[1].strip()
                # Change cancel button to open
                if component == 'video':
                    self.video_cancel.configure(text="Open", command=lambda: self._on_open(self.filepath))
                else:
                    self.audio_cancel.configure(text="Open", command=lambda: self._on_open(self.filepath))
            
            # Otherwise clamp progress between 0-100
            progress = min(100, max(0, progress))
            
            # Update progress based on component
            if component == 'video':
                self.video_progress = progress
                self.video_size = format_size
                self.video_bar.set(progress / 100)
                if speed:
                    self.video_speed.configure(text=speed)
                if text:
                    self.video_label.configure(text=text)
            else:
                self.audio_progress = progress
                self.audio_size = format_size
                self.audio_bar.set(progress / 100)
                if speed:
                    self.audio_speed.configure(text=speed)
                if text:
                    self.audio_label.configure(text=text)
                    
            # Force update
            self.update_idletasks()
            
        except Exception as e:
            print(f"Error updating progress: {e}")
            
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
            
    def _on_cancel(self, component):
        """Handle cancel button click"""
        try:
            if self.cancel_callback:
                # Disable both buttons immediately to prevent multiple clicks
                self.video_cancel.configure(state="disabled")
                self.audio_cancel.configure(state="disabled")
                # Call the cancel callback
                self.cancel_callback(self.download_id)
                # Destroy the progress bar after a short delay
                self.after(500, self.destroy)
        except Exception as e:
            print(f"Error in cancel callback: {e}")
            
    def _on_open(self, filepath):
        """Open the downloaded file"""
        if filepath:
            try:
                os.startfile(filepath)
            except Exception as e:
                print(f"Error opening file: {e}")
                messagebox.showerror("Error", f"Could not open file: {e}")
                
    def _format_size(self, size: float) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
