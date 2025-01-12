import customtkinter as ctk
from .progress_bar import ProgressBar
from .progress_bar_yt import YouTubeProgressBar

class DownloadFrame(ctk.CTkScrollableFrame):
    """Frame to hold download progress bars"""
    
    def __init__(self, master, **kwargs):
        super().__init__(
            master,
            height=200,
            fg_color="transparent",
            corner_radius=0,
            **kwargs
        )
        
        # Dictionary to store regular progress bars
        self.progress_bars = {}
        # Dictionary to store YouTube progress bars by base URL
        self.youtube_bars = {}
        
    def add_download(self, download_id: str, text: str = "", is_youtube: bool = False, is_audio: bool = False) -> None:
        """Add a new download progress bar
        
        Args:
            download_id: Unique ID for this download
            text: Initial text to display
            is_youtube: Whether this is a YouTube download
            is_audio: Whether this is an audio stream (for YouTube)
        """
        print(f"\nDEBUG: add_download called with:")
        print(f"  download_id: {download_id}")
        print(f"  is_youtube: {is_youtube}")
        print(f"  is_audio: {is_audio}")
        print(f"  Current progress_bars: {list(self.progress_bars.keys())}")
        print(f"  Current youtube_bars: {list(self.youtube_bars.keys())}")
        
        if is_youtube:
            # For YouTube downloads, use base ID without _video/_audio suffix
            base_id = download_id.rsplit('_', 1)[0]
            print(f"  Using base_id: {base_id}")
            
            # Only create YouTube progress bar for video component and if it doesn't exist
            if not is_audio:
                if base_id not in self.youtube_bars:
                    print(f"  Creating new YouTube progress bar for {base_id}")
                    progress_bar = YouTubeProgressBar(self)
                    progress_bar.pack(fill="x", padx=5, pady=2)
                    self.youtube_bars[base_id] = progress_bar
                    
                    # Set cancel callback
                    if hasattr(self.master, 'on_cancel'):
                        progress_bar.set_cancel_callback(lambda: self.master.on_cancel(base_id))
                    else:
                        print("  Master widget does not have on_cancel method")
                    
                    # Update initial text
                    if text:
                        progress_bar.label.configure(text=text)
                else:
                    print(f"  YouTube progress bar already exists for {base_id}")
                    # Get existing progress bar and check if it's still valid
                    progress_bar = self.youtube_bars[base_id]
                    if not progress_bar.winfo_exists():
                        print(f"  Progress bar widget no longer exists, removing from dictionary")
                        del self.youtube_bars[base_id]
                        return
                        
            # Map component ID to base URL for lookups
            self.progress_bars[download_id] = base_id
            print(f"  Added mapping: {download_id} -> {base_id}")
            print(f"  Updated progress_bars: {list(self.progress_bars.keys())}")
            
        else:
            # Regular download - check if we already have this download
            if download_id not in self.progress_bars:
                print(f"  Creating new regular progress bar for {download_id}")
                progress_bar = ProgressBar(self)
                progress_bar.pack(fill="x", padx=5, pady=2)
                self.progress_bars[download_id] = progress_bar
                
                # Set cancel callback
                if hasattr(self.master, 'on_cancel'):
                    progress_bar.set_cancel_callback(lambda: self.master.on_cancel(download_id))
                else:
                    print("  Master widget does not have on_cancel method")
                
                # Update initial text
                if text:
                    progress_bar.label.configure(text=text)
            else:
                print(f"  Regular progress bar already exists for {download_id}")
                
    def update_progress(self, download_id: str, progress: float, speed: str = "", 
                       text: str = "", total_size: int = 0, downloaded_size: int = 0,
                       is_youtube: bool = False, is_audio: bool = False) -> None:
        """Update progress for a download"""
        print(f"\nDEBUG: update_progress called with:")
        print(f"  download_id: {download_id}")
        print(f"  progress: {progress}")
        print(f"  is_youtube: {is_youtube}")
        print(f"  is_audio: {is_audio}")
        print(f"  Current progress_bars: {list(self.progress_bars.keys())}")
        print(f"  Current youtube_bars: {list(self.youtube_bars.keys())}")
        
        if is_youtube:
            # Get base ID from progress_bars mapping
            if download_id not in self.progress_bars:
                print(f"  No mapping found for YouTube component {download_id}")
                return
                
            base_id = self.progress_bars[download_id]
            print(f"  Found base_id: {base_id}")
            
            if base_id in self.youtube_bars:
                progress_bar = self.youtube_bars[base_id]
                if isinstance(progress_bar, YouTubeProgressBar):
                    print(f"  Updating YouTube progress bar for {base_id}")
                    
                    # Let YouTubeProgressBar handle completion status
                    progress_bar.update_progress(
                        "audio" if is_audio else "video",
                        progress,
                        speed=speed,
                        text=text,
                        total_size=total_size,
                        downloaded_size=downloaded_size,
                        format_size=total_size
                    )
                    
                    # Check if both components are complete
                    if progress_bar._allow_destroy:
                        print("  Both components complete, scheduling removal")
                        self.after(1000, lambda: self.remove_download(base_id))
                else:
                    print(f"  Progress bar for {base_id} is not a YouTubeProgressBar")
            else:
                print(f"  No progress bar found for {base_id}")
        else:
            # Regular download
            if download_id in self.progress_bars:
                progress_bar = self.progress_bars[download_id]
                if not isinstance(progress_bar, YouTubeProgressBar):
                    progress_bar.update(progress, speed, text, total_size, downloaded_size)
                    if progress == 100:
                        print(f"  Regular download complete, scheduling removal of {download_id}")
                        self.after(1000, lambda: self.remove_download(download_id))
            else:
                print(f"  No progress bar found for {download_id}")
                
    def remove_download(self, download_id: str) -> None:
        """Remove a download progress bar"""
        try:
            print(f"DEBUG: remove_download called for {download_id}")
            
            # For YouTube downloads, check both dictionaries
            if download_id in self.youtube_bars:
                print(f"DEBUG: Removing YouTube progress bar for {download_id}")
                progress_bar = self.youtube_bars[download_id]
                
                # Remove all component mappings
                for component_id, base_id in list(self.progress_bars.items()):
                    if base_id == download_id:
                        del self.progress_bars[component_id]
                
                # Remove the progress bar
                progress_bar.pack_forget()
                progress_bar.destroy()
                del self.youtube_bars[download_id]
                
            elif download_id in self.progress_bars:
                print(f"DEBUG: Removing regular progress bar for {download_id}")
                progress_bar = self.progress_bars[download_id]
                progress_bar.pack_forget()
                progress_bar.destroy()
                del self.progress_bars[download_id]
            else:
                print(f"DEBUG: No progress bar found for {download_id}")
                
        except Exception as e:
            print(f"Error clearing download frame: {str(e)}")
