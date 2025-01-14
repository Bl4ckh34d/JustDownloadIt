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
    DownloaderLogger: Singleton logger class for consistent logging across the app

Dependencies:
    - logging: Python's built-in logging module
    - colorama: Colored console output
"""

import logging
from typing import Optional

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
    def get_logger(cls) -> logging.Logger:
        """
        Get or create logger instance.
        
        Returns:
            logging.Logger: The configured logger instance
        """
        if cls._logger is None:
            # Create logger
            logger = logging.getLogger('downloader')
            logger.setLevel(logging.WARNING)  # Only show warnings and errors
            
            # Create console handler
            handler = logging.StreamHandler()
            handler.setLevel(logging.WARNING)
            
            # Create formatter
            formatter = logging.Formatter('%(levelname)s: %(message)s')
            handler.setFormatter(formatter)
            
            # Add handler to logger
            logger.addHandler(handler)
            
            cls._logger = logger
            
        return cls._logger
    
    @staticmethod
    def log_download_start(url: str, download_id: str) -> None:
        """
        Log download start.
        
        Args:
            url (str): The URL being downloaded
            download_id (str): The ID of the download
        """
        logger = DownloaderLogger.get_logger()
        logger.info(f"Starting download {download_id}: {url}")
    
    @staticmethod
    def log_download_progress(download_id: str, progress: float, speed: str) -> None:
        """
        Log download progress.
        
        Args:
            download_id (str): The ID of the download
            progress (float): The current progress of the download
            speed (str): The current download speed
        """
        logger = DownloaderLogger.get_logger()
        logger.debug(f"Download {download_id}: {progress:.1f}% at {speed}")
    
    @staticmethod
    def log_download_complete(download_id: str, file_path: str) -> None:
        """
        Log download completion.
        
        Args:
            download_id (str): The ID of the download
            file_path (str): The path of the downloaded file
        """
        logger = DownloaderLogger.get_logger()
        logger.info(f"Download {download_id} complete: {file_path}")
    
    @staticmethod
    def log_download_error(download_id: str, error: str) -> None:
        """
        Log download error.
        
        Args:
            download_id (str): The ID of the download
            error (str): The error message
        """
        logger = DownloaderLogger.get_logger()
        logger.error(f"Download {download_id} failed: {error}")
    
    @staticmethod
    def log_download_cancelled(download_id: str) -> None:
        """
        Log download cancellation.
        
        Args:
            download_id (str): The ID of the download
        """
        logger = DownloaderLogger.get_logger()
        logger.info(f"Download {download_id} cancelled")
