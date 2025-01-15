"""
Concurrency and state management utilities.

This module provides thread-safe data structures, synchronization primitives,
and state management for concurrent operations. It ensures thread safety and
provides a consistent interface for managing application state.

Components:
    - Thread-safe Data Structures:
        - ThreadSafeDict: Thread-safe dictionary
        - ProcessSafeCounter: Process-safe counter
        
    - Thread Management:
        - ThreadPool: Worker thread pool
        - ResourceLock: Reentrant resource lock
        
    - State Management:
        - StateManager: Thread-safe state tracking
        - DownloadProgress: Progress tracking
        
    - Configuration Management:
        - ConfigManager: Thread-safe configuration manager
        - DownloadConfig: Download-related configuration
        - YouTubeConfig: YouTube-specific configuration
        - AppConfig: Application configuration
"""

import threading
from typing import TypeVar, Generic, Dict, Optional, Any, Callable
from queue import Queue
import logging
from contextlib import contextmanager
from dataclasses import dataclass, asdict, field
import json
from pathlib import Path

T = TypeVar('T')

class ThreadSafeDict(Generic[T]):
    """Thread-safe dictionary implementation."""
    
    def __init__(self):
        self._dict: Dict[str, T] = {}
        self._lock = threading.RLock()
    
    def get(self, key: str, default: Optional[T] = None) -> Optional[T]:
        with self._lock:
            return self._dict.get(key, default)
    
    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._dict[key] = value
    
    def pop(self, key: str, default: Optional[T] = None) -> Optional[T]:
        with self._lock:
            return self._dict.pop(key, default)
    
    def clear(self) -> None:
        with self._lock:
            self._dict.clear()
    
    def items(self):
        with self._lock:
            return list(self._dict.items())

class ThreadPool:
    """Manages a pool of worker threads."""
    
    def __init__(self, num_threads: int = 4):
        self.tasks = Queue()
        self.workers = []
        self._stop_flag = threading.Event()
        self.logger = logging.getLogger(__name__)
        
        for _ in range(num_threads):
            worker = threading.Thread(target=self._worker_loop)
            worker.daemon = True
            worker.start()
            self.workers.append(worker)
    
    def _worker_loop(self):
        while not self._stop_flag.is_set():
            try:
                task = self.tasks.get(timeout=1.0)
                if task is None:
                    break
                func, args, kwargs = task
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    self.logger.error(f"Error in worker thread: {e}")
                finally:
                    self.tasks.task_done()
            except:
                continue
    
    def submit(self, func, *args, **kwargs):
        """Submit a task to the thread pool."""
        if not self._stop_flag.is_set():
            self.tasks.put((func, args, kwargs))
    
    def shutdown(self, wait: bool = True):
        """Shutdown the thread pool."""
        self._stop_flag.set()
        if wait:
            for _ in self.workers:
                self.tasks.put(None)
            for worker in self.workers:
                worker.join()
        self.workers.clear()

class ResourceLock:
    """Reentrant resource lock for managing shared resources."""
    
    def __init__(self):
        self._lock = threading.RLock()
        self._owner = None
        self._count = 0
    
    def acquire(self, blocking: bool = True) -> bool:
        """Acquire the lock.
        
        Args:
            blocking: Whether to block until lock is acquired
            
        Returns:
            bool: True if lock was acquired
        """
        current = threading.current_thread().ident
        if current == self._owner:
            self._count += 1
            return True
            
        if self._lock.acquire(blocking=blocking):
            self._owner = current
            self._count = 1
            return True
        return False
    
    def release(self) -> None:
        """Release the lock."""
        if threading.current_thread().ident != self._owner:
            raise RuntimeError("Cannot release un-owned lock")
            
        self._count -= 1
        if self._count == 0:
            self._owner = None
            self._lock.release()
    
    def locked(self) -> bool:
        """Check if lock is held."""
        return self._lock._is_owned()
    
    def __call__(self):
        """Context manager interface."""
        return self

@contextmanager
def thread_safe_operation(lock: threading.Lock):
    """Context manager for thread-safe operations."""
    lock.acquire()
    try:
        yield
    finally:
        lock.release()

class ProcessSafeCounter:
    """Process-safe counter implementation."""
    
    def __init__(self, initial: int = 0):
        self._value = initial
        self._lock = threading.Lock()
    
    def increment(self) -> int:
        """Increment counter."""
        with self._lock:
            self._value += 1
            return self._value
    
    def decrement(self) -> int:
        """Decrement counter."""
        with self._lock:
            self._value -= 1
            return self._value
    
    def get(self) -> int:
        """Get current value."""
        with self._lock:
            return self._value
    
    def set(self, value: int) -> None:
        """Set counter value."""
        with self._lock:
            self._value = value

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
        meta = self._metadata.get(download_id)
        return meta.get(key) if meta else None
    
    def remove_download(self, download_id: str) -> None:
        """Remove all data for a download."""
        with thread_safe_operation(self._lock):
            self._states.pop(download_id, None)
            self._progress.pop(download_id, None)
            self._callbacks.pop(download_id, None)
            self._metadata.pop(download_id, None)

@dataclass
class DownloadConfig:
    """Download-related configuration."""
    max_concurrent_downloads: int = 4
    chunk_size: int = 8192
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5
    user_agent: str = "JustDownloadIt/1.0"
    
    def validate(self) -> None:
        """Validate configuration values."""
        assert self.max_concurrent_downloads > 0, "max_concurrent_downloads must be positive"
        assert self.chunk_size > 0, "chunk_size must be positive"
        assert self.timeout > 0, "timeout must be positive"
        assert self.retry_attempts >= 0, "retry_attempts must be non-negative"
        assert self.retry_delay >= 0, "retry_delay must be non-negative"

@dataclass
class YouTubeConfig:
    """YouTube-specific configuration."""
    default_format: str = "best"
    prefer_mp4: bool = True
    extract_audio: bool = False
    audio_format: str = "mp3"
    audio_quality: str = "192"
    embed_thumbnail: bool = True
    
    def validate(self) -> None:
        """Validate configuration values."""
        valid_audio_formats = ["mp3", "m4a", "wav", "flac"]
        assert self.audio_format in valid_audio_formats, f"audio_format must be one of {valid_audio_formats}"
        assert self.audio_quality.isdigit(), "audio_quality must be a number"

@dataclass
class AppConfig:
    """Application configuration."""
    download_dir: Path = field(default_factory=lambda: Path.home() / "Downloads")
    temp_dir: Path = field(default_factory=lambda: Path.home() / ".justdownloadit" / "temp")
    log_dir: Path = field(default_factory=lambda: Path.home() / ".justdownloadit" / "logs")
    max_log_size: int = 10 * 1024 * 1024  # 10MB
    max_log_files: int = 5
    debug_mode: bool = False
    
    def validate(self) -> None:
        """Validate configuration values."""
        assert self.max_log_size > 0, "max_log_size must be positive"
        assert self.max_log_files > 0, "max_log_files must be positive"

class ConfigManager:
    """Thread-safe configuration manager."""
    
    _instance = None
    _lock = threading.RLock()
    
    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
            return cls._instance
    
    def __init__(self):
        if not hasattr(self, '_initialized'):
            self._config_file = Path.home() / ".justdownloadit" / "config.json"
            self._download_config = DownloadConfig()
            self._youtube_config = YouTubeConfig()
            self._app_config = AppConfig()
            self.logger = logging.getLogger(__name__)
            self._initialized = True
            self._load_config()
    
    def _load_config(self) -> None:
        """Load configuration from file."""
        with thread_safe_operation(self._lock):
            if self._config_file.exists():
                try:
                    config_data = json.loads(self._config_file.read_text())
                    self._update_config(config_data)
                except Exception as e:
                    self.logger.error(f"Error loading config: {e}")
                    self._save_config()  # Save default config
            else:
                self._save_config()  # Create default config file
    
    def _save_config(self) -> None:
        """Save configuration to file."""
        with thread_safe_operation(self._lock):
            config_data = {
                "download": asdict(self._download_config),
                "youtube": asdict(self._youtube_config),
                "app": asdict(self._app_config)
            }
            
            # Convert Path objects to strings
            config_data["app"]["download_dir"] = str(self._app_config.download_dir)
            config_data["app"]["temp_dir"] = str(self._app_config.temp_dir)
            config_data["app"]["log_dir"] = str(self._app_config.log_dir)
            
            try:
                self._config_file.parent.mkdir(parents=True, exist_ok=True)
                self._config_file.write_text(json.dumps(config_data, indent=4))
            except Exception as e:
                self.logger.error(f"Error saving config: {e}")
    
    def _update_config(self, config_data: Dict[str, Any]) -> None:
        """Update configuration from dictionary."""
        if "download" in config_data:
            self._download_config = DownloadConfig(**config_data["download"])
        if "youtube" in config_data:
            self._youtube_config = YouTubeConfig(**config_data["youtube"])
        if "app" in config_data:
            app_data = config_data["app"]
            # Convert string paths to Path objects
            app_data["download_dir"] = Path(app_data["download_dir"])
            app_data["temp_dir"] = Path(app_data["temp_dir"])
            app_data["log_dir"] = Path(app_data["log_dir"])
            self._app_config = AppConfig(**app_data)
    
    @property
    def download(self) -> DownloadConfig:
        """Get download configuration."""
        return self._download_config
    
    @property
    def youtube(self) -> YouTubeConfig:
        """Get YouTube configuration."""
        return self._youtube_config
    
    @property
    def app(self) -> AppConfig:
        """Get application configuration."""
        return self._app_config
    
    def validate(self) -> None:
        """Validate all configuration settings."""
        with thread_safe_operation(self._lock):
            try:
                self._download_config.validate()
                self._youtube_config.validate()
                self._app_config.validate()
            except AssertionError as e:
                self.logger.error(f"Configuration validation failed: {e}")
                raise
    
    def reload(self) -> None:
        """Reload configuration from file."""
        self._load_config()
        self.validate()
    
    def save(self) -> None:
        """Save current configuration to file."""
        self.validate()
        self._save_config()
    
    def reset_to_defaults(self) -> None:
        """Reset configuration to default values."""
        with thread_safe_operation(self._lock):
            self._download_config = DownloadConfig()
            self._youtube_config = YouTubeConfig()
            self._app_config = AppConfig()
            self._save_config()
