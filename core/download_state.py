"""
Download state and progress tracking.

This module provides classes for tracking download state and progress.
"""

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional, Dict

class DownloadState(Enum):
    """Download states."""
    QUEUED = auto()
    DOWNLOADING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()

@dataclass
class DownloadProgress:
    """Download progress information."""
    progress: float
    speed: str = ""
    text: str = ""
    total_size: float = 0
    downloaded_size: float = 0
    stats: Optional[Dict] = None
    state: DownloadState = DownloadState.DOWNLOADING
    error: Optional[str] = None
    
    @property
    def is_complete(self) -> bool:
        """Check if download is complete."""
        return self.state == DownloadState.COMPLETED
        
    @property
    def is_error(self) -> bool:
        """Check if download has error."""
        return self.state == DownloadState.ERROR
        
    @property
    def is_cancelled(self) -> bool:
        """Check if download is cancelled."""
        return self.state == DownloadState.CANCELLED
        
    @property
    def display_color(self) -> str:
        """Get display color for current state."""
        colors = {
            DownloadState.QUEUED: '#95a5a6',      # Gray
            DownloadState.DOWNLOADING: '#4a90e2',  # Blue
            DownloadState.PAUSED: '#f1c40f',      # Yellow
            DownloadState.COMPLETED: '#2ecc71',    # Green
            DownloadState.ERROR: '#e74c3c',       # Red
            DownloadState.CANCELLED: '#95a5a6',    # Gray
        }
        return colors.get(self.state, '#95a5a6')  # Default to gray
