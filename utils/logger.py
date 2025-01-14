"""
Logging utilities for JustDownloadIt.

This module provides logging functionality for the application with different log levels
and handlers. It supports both file and console logging with customizable formats.

Features:
    - Console logging with colored output
    - File logging with rotation
    - Different log levels (DEBUG, INFO, WARNING, ERROR)
    - Custom log formats with timestamps
    - Singleton logger instance

Classes:
    LoggerConfig: Configuration for the logger
    DownloaderLogger: Singleton logger class for consistent logging across the app

Dependencies:
    - logging: Python's built-in logging module
    - colorama: Colored console output
"""

import logging
import logging.handlers
import os
from pathlib import Path
from datetime import datetime
from typing import Optional
from colorama import init, Fore, Style

# Initialize colorama for Windows support
init()

class LoggerConfig:
    """Configuration for the logger."""
    
    # Log levels
    CONSOLE_LEVEL = logging.INFO
    FILE_LEVEL = logging.DEBUG
    
    # Log formats
    CONSOLE_FORMAT = '%(levelname)s: %(message)s'
    FILE_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # File settings
    LOG_DIR = Path('logs')
    MAX_BYTES = 5 * 1024 * 1024  # 5MB
    BACKUP_COUNT = 5

class DownloaderLogger:
    """
    Singleton logger class for JustDownloadIt.
    
    This class ensures that only one logger instance is created and used
    throughout the application. It provides both console and file logging
    with different formats and colors for better readability.
    
    Attributes:
        _logger (logging.Logger): The actual logger object
    """
    
    _logger: Optional[logging.Logger] = None
    
    @classmethod
    def get_logger(cls, name: str = 'downloader') -> logging.Logger:
        """
        Get or create logger instance.
        
        Args:
            name (str): Logger name, defaults to 'downloader'
            
        Returns:
            logging.Logger: The configured logger instance
        """
        if cls._logger is None:
            # Create logger
            logger = logging.getLogger(name)
            logger.setLevel(logging.DEBUG)
            
            # Ensure log directory exists
            LoggerConfig.LOG_DIR.mkdir(parents=True, exist_ok=True)
            
            # Create console handler with colors
            console = logging.StreamHandler()
            console.setLevel(LoggerConfig.CONSOLE_LEVEL)
            
            class ColorFormatter(logging.Formatter):
                """Formatter that adds colors to log levels"""
                
                COLORS = {
                    'DEBUG': Fore.CYAN,
                    'INFO': Fore.GREEN,
                    'WARNING': Fore.YELLOW,
                    'ERROR': Fore.RED,
                    'CRITICAL': Fore.RED + Style.BRIGHT
                }
                
                def format(self, record):
                    if record.levelname in self.COLORS:
                        record.levelname = f"{self.COLORS[record.levelname]}{record.levelname}{Style.RESET_ALL}"
                    return super().format(record)
            
            # Create console formatter
            console_formatter = ColorFormatter(LoggerConfig.CONSOLE_FORMAT)
            console.setFormatter(console_formatter)
            
            # Create file handler with rotation
            log_file = LoggerConfig.LOG_DIR / f"{name}.log"
            file_handler = logging.handlers.RotatingFileHandler(
                log_file,
                maxBytes=LoggerConfig.MAX_BYTES,
                backupCount=LoggerConfig.BACKUP_COUNT
            )
            file_handler.setLevel(LoggerConfig.FILE_LEVEL)
            
            # Create file formatter
            file_formatter = logging.Formatter(LoggerConfig.FILE_FORMAT)
            file_handler.setFormatter(file_formatter)
            
            # Add handlers to logger
            logger.addHandler(console)
            logger.addHandler(file_handler)
            
            cls._logger = logger
            
        return cls._logger
    
    @staticmethod
    def log_download_start(url: str, download_id: str) -> None:
        """Log download start."""
        logger = DownloaderLogger.get_logger()
        logger.info(f"Starting download {download_id}: {url}")
    
    @staticmethod
    def log_download_progress(download_id: str, progress: float, speed: str) -> None:
        """Log download progress."""
        logger = DownloaderLogger.get_logger()
        logger.debug(f"Download {download_id}: {progress:.1f}% at {speed}")
    
    @staticmethod
    def log_download_complete(download_id: str, file_path: str) -> None:
        """Log download completion."""
        logger = DownloaderLogger.get_logger()
        logger.info(f"Download {download_id} complete: {file_path}")
    
    @staticmethod
    def log_download_error(download_id: str, error: Exception) -> None:
        """Log download error."""
        logger = DownloaderLogger.get_logger()
        logger.error(f"Download {download_id} failed: {error}", exc_info=True)
    
    @staticmethod
    def log_download_cancelled(download_id: str) -> None:
        """Log download cancellation."""
        logger = DownloaderLogger.get_logger()
        logger.warning(f"Download {download_id} cancelled")
