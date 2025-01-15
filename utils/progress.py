"""
Progress tracking utilities for download operations.

This module provides standardized progress tracking and formatting
for both regular and YouTube downloads.
"""

from typing import Optional, Dict
from dataclasses import dataclass
import time

from .format_utils import format_size, format_speed, format_time

@dataclass
class ProgressStats:
    """Download progress statistics."""
    total_size: Optional[int] = None
    downloaded_size: Optional[int] = None
    speed: Optional[float] = None  # bytes per second
    eta: Optional[int] = None  # seconds
    progress: float = 0.0
    status: str = "initializing"

def format_progress(stats: ProgressStats) -> str:
    """Format progress information into a status message."""
    size_text = (f"{format_size(stats.downloaded_size)}/{format_size(stats.total_size)}"
                if stats.total_size else format_size(stats.downloaded_size))
    speed_text = format_speed(stats.speed)
    eta_text = format_time(stats.eta) if stats.eta else "unknown"
    
    return (f"Progress: {stats.progress:.1f}% | "
            f"Size: {size_text} | "
            f"Speed: {speed_text} | "
            f"ETA: {eta_text}")

class ProgressTracker:
    """Tracks download progress with speed calculation."""
    
    def __init__(self, total_size: Optional[int] = None):
        self.total_size = total_size
        self.downloaded_size = 0
        self.start_time = time.time()
        self.last_update_time = self.start_time
        self.last_downloaded_size = 0
        self.speed = 0.0
        self.smoothing_factor = 0.3  # For exponential moving average
    
    def update(self, downloaded_size: int) -> None:
        """Update progress and calculate statistics.
        
        Args:
            downloaded_size: Current downloaded size in bytes
        """
        current_time = time.time()
        time_delta = current_time - self.last_update_time
        
        if time_delta > 0:
            # Calculate instantaneous speed
            size_delta = downloaded_size - self.last_downloaded_size
            instant_speed = size_delta / time_delta
            
            # Update speed using exponential moving average
            if self.speed == 0:
                self.speed = instant_speed
            else:
                self.speed = (self.smoothing_factor * instant_speed + 
                            (1 - self.smoothing_factor) * self.speed)
        
        self.downloaded_size = downloaded_size
        self.last_downloaded_size = downloaded_size
        self.last_update_time = current_time
    
    def get_stats(self) -> ProgressStats:
        """Get current progress statistics.
        
        Returns:
            ProgressStats: Current progress stats
        """
        progress = (
            (self.downloaded_size / self.total_size * 100)
            if self.total_size else 0.0
        )
        
        eta = None
        if self.speed > 0 and self.total_size:
            remaining_size = self.total_size - self.downloaded_size
            eta = int(remaining_size / self.speed)
        
        return ProgressStats(
            total_size=self.total_size,
            downloaded_size=self.downloaded_size,
            speed=self.speed,
            eta=eta,
            progress=progress,
            status="downloading"
        )
