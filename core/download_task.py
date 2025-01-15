"""
Download task definition.

This module provides the DownloadTask class for representing download tasks.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional
import uuid
import multiprocessing
import multiprocessing.managers
from pathlib import Path

@dataclass
class DownloadTask:
    """Represents a download task with its configuration.
    
    Args:
        url (str): URL to download
        output_dir (str): Directory to save downloaded file
        options (Dict, optional): Additional download options. Defaults to None.
        download_id (str, optional): Unique ID for the download. Generated if not provided.
    """
    url: str
    output_dir: str
    options: Dict = field(default_factory=lambda: {})
    download_id: Optional[str] = field(default_factory=lambda: str(uuid.uuid4()))
    _lock: multiprocessing.Lock = field(default_factory=multiprocessing.Lock, init=False, repr=False)
    
    def __post_init__(self):
        """Initialize process-safe fields."""
        # Convert options to a Manager dict for process safety if needed
        if multiprocessing.current_process().name != 'MainProcess':
            manager = multiprocessing.managers.SyncManager()
            manager.start()
            self.options = manager.dict(self.options or {})
            
    def update_option(self, key: str, value: any) -> None:
        """Update an option in a process-safe way.
        
        Args:
            key: Option key to update
            value: New value for the option
        """
        with self._lock:
            self.options[key] = value
            
    def get_option(self, key: str, default: any = None) -> any:
        """Get an option value in a process-safe way.
        
        Args:
            key: Option key to get
            default: Default value if key doesn't exist
            
        Returns:
            Option value or default
        """
        with self._lock:
            return self.options.get(key, default)
