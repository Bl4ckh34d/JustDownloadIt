import tkinter as tk
import customtkinter as ctk

class YouTubeProgressBar(ctk.CTkFrame):
    """A custom progress bar widget for YouTube downloads with two stacked progress bars"""
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        
        # Store format sizes
        self.video_size = 0
        self.audio_size = 0
        self.total_size = 0
        
        # Track completion status
        self.video_completed = False
        self.audio_completed = False
        
        # Track progress
        self.video_progress = 0
        self.audio_progress = 0
        
        # Prevent auto-removal
        self._allow_destroy = False
        self._destroying = False
        
        # Create main label frame
        self.label_frame = ctk.CTkFrame(self)
        self.label_frame.pack(fill=tk.X, padx=5, pady=(5,0))
        
        # Create status label
        self.label = ctk.CTkLabel(self.label_frame, text="Starting download...", anchor="w")
        self.label.pack(side=tk.LEFT, padx=5, pady=5)
        
        # Speed label
        self.speed_label = ctk.CTkLabel(self.label_frame, text="", width=150)
        self.speed_label.pack(side=tk.LEFT, padx=5)
        
        # Cancel button
        self.cancel_button = ctk.CTkButton(self.label_frame, text="Cancel", width=60)
        self.cancel_button.pack(side=tk.RIGHT, padx=5)
        
        # Create video progress frame
        self.video_frame = ctk.CTkFrame(self)
        self.video_frame.pack(fill=tk.X, padx=5)
        
        # Create video label and speed
        self.video_label = ctk.CTkLabel(self.video_frame, text="Video:", anchor="w", width=100)
        self.video_label.pack(side=tk.LEFT, padx=5)
        
        self.video_speed = ctk.CTkLabel(self.video_frame, text="", anchor="e", width=100)
        self.video_speed.pack(side=tk.RIGHT, padx=5)
        
        # Create video progress bar
        self.video_bar = ctk.CTkProgressBar(self.video_frame)
        self.video_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.video_bar.set(0)
        
        # Create audio progress frame
        self.audio_frame = ctk.CTkFrame(self)
        self.audio_frame.pack(fill=tk.X, padx=5, pady=(0,5))
        
        # Create audio label and speed
        self.audio_label = ctk.CTkLabel(self.audio_frame, text="Audio:", anchor="w", width=100)
        self.audio_label.pack(side=tk.LEFT, padx=5)
        
        self.audio_speed = ctk.CTkLabel(self.audio_frame, text="", anchor="e", width=100)
        self.audio_speed.pack(side=tk.RIGHT, padx=5)
        
        # Create audio progress bar
        self.audio_bar = ctk.CTkProgressBar(self.audio_frame)
        self.audio_bar.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        self.audio_bar.set(0)

    def set_cancel_callback(self, callback):
        """Set callback for cancel button"""
        self.cancel_button.configure(command=callback)
        
    def destroy(self):
        """Override destroy to prevent premature removal"""
        if self._destroying:
            return
            
        print("DEBUG: YouTubeProgressBar.destroy called")
        if not self._allow_destroy:
            print("DEBUG: Attempted to destroy YouTubeProgressBar without both components complete")
            print(f"DEBUG: Audio completed: {self.audio_completed}, Video completed: {self.video_completed}")
            return False
                
        self._destroying = True
        print("DEBUG: Proceeding with YouTubeProgressBar destruction")
        super().destroy()
        return True
        
    def update(self, progress: float, speed: str = "", text: str = "", 
               total_size: float = 0, downloaded_size: float = 0):
        """Override parent update to prevent auto-removal
        
        This method is called by the parent class's update mechanism.
        We override it to do nothing since we handle updates through update_progress.
        """
        print(f"DEBUG: YouTubeProgressBar update called with progress={progress}")
        # Intentionally do nothing to prevent auto-removal
        pass

    def update_progress(self, component: str, progress: float, speed: str = "", 
                       text: str = "", total_size: float = 0, downloaded_size: float = 0,
                       format_size: float = 0):
        """Update progress for video or audio component
        
        Args:
            component: Either 'video' or 'audio'
            progress: Progress percentage (0-100)
            speed: Download speed string
            text: Status text
            total_size: Total size in bytes
            downloaded_size: Downloaded size in bytes
            format_size: Total size of this format in bytes
        """
        print(f"DEBUG: update_progress called for {component} with progress={progress}")
        
        # Check if component is already completed
        if component == "audio" and self.audio_completed:
            print(f"DEBUG: Audio already completed, ignoring update")
            return
        elif component == "video" and self.video_completed:
            print(f"DEBUG: Video already completed, ignoring update")
            return
        
        # Update the appropriate progress bar
        if component == "audio":
            self.audio_bar.set(progress / 100)
            if progress == 100:
                print("DEBUG: Audio component reached 100%")
                self.audio_completed = True
                self.audio_speed.configure(text="Complete")
        else:  # video
            self.video_bar.set(progress / 100)
            if progress == 100:
                print("DEBUG: Video component reached 100%")
                self.video_completed = True
                self.video_speed.configure(text="Complete")
                
        # Update label text
        if text and not (self.video_completed and self.audio_completed):
            self.label.configure(text=text)
            
        # Update speed text only if component not completed
        if speed:
            if component == "video" and not self.video_completed:
                self.video_speed.configure(text=speed)
            elif component == "audio" and not self.audio_completed:
                self.audio_speed.configure(text=speed)
            
        # Log completion status
        if progress == 100:
            print(f"DEBUG: {component} completed. Audio: {self.audio_completed}, Video: {self.video_completed}")
            
        # Check if both components are complete
        if self.video_completed and self.audio_completed and not self._allow_destroy:
            print("DEBUG: Both components complete, allowing destroy")
            self.label.configure(text="Download complete")
            self._allow_destroy = True

    def _format_size(self, size: float) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
