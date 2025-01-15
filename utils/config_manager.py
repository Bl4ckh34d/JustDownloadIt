"""
Configuration management utilities for JustDownloadIt.

This module provides a thread-safe configuration manager with validation,
type checking, and dynamic reloading capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Union, Type, TypeVar
from dataclasses import dataclass, asdict, field
import threading
import os

from .concurrency import thread_safe_operation

T = TypeVar('T')

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
