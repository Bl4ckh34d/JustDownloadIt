import logging
from pathlib import Path
from typing import Optional
from core.config import Config

class DownloaderLogger:
    _instance: Optional['DownloaderLogger'] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize_logger()
        return cls._instance
    
    def _initialize_logger(self):
        """Initialize the logger with file and console handlers"""
        self.logger = logging.getLogger('downloader')
        self.logger.setLevel(logging.DEBUG)
        
        # Create logs directory if it doesn't exist
        log_dir = Path(Config.LOG_FILE).parent
        log_dir.mkdir(exist_ok=True)
        
        # File handler - all logs
        file_handler = logging.FileHandler(Config.LOG_FILE)
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Console handler - info and above
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(console_handler)
    
    @classmethod
    def get_logger(cls) -> logging.Logger:
        """Get the logger instance"""
        if cls._instance is None:
            cls()
        return cls._instance.logger
    
    @staticmethod
    def log_download_start(url: str, download_id: str) -> None:
        """Log download start"""
        logger = DownloaderLogger.get_logger()
        logger.info(f"Starting download {download_id}: {url}")
    
    @staticmethod
    def log_download_progress(download_id: str, progress: float, speed: str) -> None:
        """Log download progress"""
        logger = DownloaderLogger.get_logger()
        logger.debug(f"Download {download_id}: {progress:.1f}% at {speed}")
    
    @staticmethod
    def log_download_complete(download_id: str, file_path: Path) -> None:
        """Log download completion"""
        logger = DownloaderLogger.get_logger()
        logger.info(f"Download {download_id} complete: {file_path}")
    
    @staticmethod
    def log_download_error(download_id: str, error: Exception) -> None:
        """Log download error"""
        logger = DownloaderLogger.get_logger()
        logger.error(f"Download {download_id} failed: {error}")
    
    @staticmethod
    def log_download_cancelled(download_id: str) -> None:
        """Log download cancellation"""
        logger = DownloaderLogger.get_logger()
        logger.info(f"Download {download_id} cancelled")
