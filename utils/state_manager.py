"""
State management utilities for download operations.

This module provides thread-safe state management for downloads, including
progress tracking, callback management, and state transitions.
"""

from typing import Dict, Optional, Callable, Any
from dataclasses import dataclass
from enum import Enum, auto
import threading
import logging

from .concurrency import ThreadSafeDict, thread_safe_operation

class DownloadState(Enum):
    """Possible states for a download."""
    QUEUED = auto()
    INITIALIZING = auto()
    DOWNLOADING = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()
    PAUSED = auto()

@dataclass
class DownloadProgress:
    """Download progress information."""
    progress: float = 0.0
    speed: str = ""
    text: str = ""
    total_size: Optional[int] = None
    downloaded_size: Optional[int] = None
    state: DownloadState = DownloadState.QUEUED
    component: str = ""
    error: Optional[str] = None

class StateManager:
    """Manages download states and progress tracking."""
    
    def __init__(self):
        self._states = ThreadSafeDict[DownloadState]()
        self._progress = ThreadSafeDict[DownloadProgress]()
        self._callbacks = ThreadSafeDict[Callable]()
        self._metadata = ThreadSafeDict[Dict]()
        self._lock = threading.RLock()
        self.logger = logging.getLogger(__name__)
    
    def register_download(self, download_id: str, callback: Optional[Callable] = None) -> None:
        """Register a new download with initial state."""
        with thread_safe_operation(self._lock):
            self._states.set(download_id, DownloadState.QUEUED)
            self._progress.set(download_id, DownloadProgress())
            if callback:
                self._callbacks.set(download_id, callback)
    
    def update_state(self, download_id: str, state: DownloadState) -> None:
        """Update the state of a download."""
        with thread_safe_operation(self._lock):
            self._states.set(download_id, state)
            progress = self._progress.get(download_id)
            if progress:
                progress.state = state
                self._notify_progress(download_id, progress)
    
    def update_progress(self, download_id: str, **kwargs) -> None:
        """Update download progress information."""
        with thread_safe_operation(self._lock):
            progress = self._progress.get(download_id)
            if progress:
                for key, value in kwargs.items():
                    if hasattr(progress, key):
                        setattr(progress, key, value)
                self._notify_progress(download_id, progress)
    
    def _notify_progress(self, download_id: str, progress: DownloadProgress) -> None:
        """Notify callback of progress update."""
        callback = self._callbacks.get(download_id)
        if callback:
            try:
                callback(download_id, progress)
            except Exception as e:
                self.logger.error(f"Error in progress callback for {download_id}: {e}")
    
    def get_state(self, download_id: str) -> Optional[DownloadState]:
        """Get the current state of a download."""
        return self._states.get(download_id)
    
    def get_progress(self, download_id: str) -> Optional[DownloadProgress]:
        """Get the current progress of a download."""
        return self._progress.get(download_id)
    
    def set_metadata(self, download_id: str, key: str, value: Any) -> None:
        """Set metadata for a download."""
        meta = self._metadata.get(download_id, {})
        meta[key] = value
        self._metadata.set(download_id, meta)
    
    def get_metadata(self, download_id: str, key: str) -> Optional[Any]:
        """Get metadata for a download."""
        meta = self._metadata.get(download_id, {})
        return meta.get(key)
    
    def remove_download(self, download_id: str) -> None:
        """Remove all data for a download."""
        with thread_safe_operation(self._lock):
            self._states.pop(download_id, None)
            self._progress.pop(download_id, None)
            self._callbacks.pop(download_id, None)
            self._metadata.pop(download_id, None)
    
    def clear_all(self) -> None:
        """Clear all download states and progress information."""
        with thread_safe_operation(self._lock):
            self._states.clear()
            self._progress.clear()
            self._callbacks.clear()
            self._metadata.clear()
