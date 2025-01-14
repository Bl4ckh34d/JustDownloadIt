"""
Error handling utilities for JustDownloadIt.

This module provides custom exceptions and error handling functions used throughout the application.
It standardizes error handling and provides user-friendly error messages.

Features:
    - Custom exception hierarchy
    - Error context information
    - User-friendly error messages
    - Error recovery strategies
    - Error logging integration

Classes:
    DownloaderError: Base class for all downloader errors
    URLError: Base class for URL-related errors
    NetworkError: Network-related errors
    FileSystemError: File system errors
    YouTubeError: YouTube-specific errors
    CancellationError: Download cancellation errors
    CookieError: Cookie-related errors
"""

import logging
import tkinter.messagebox as messagebox
import urllib.error
from dataclasses import dataclass
from typing import Optional, Dict, Any
from .logger import DownloaderLogger

@dataclass
class ErrorContext:
    """Context information for errors."""
    
    error_type: str
    message: str
    details: Optional[str] = None
    recovery_hint: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class DownloaderError(Exception):
    """Base class for all downloader errors."""
    
    def __init__(self, message: str, context: Optional[ErrorContext] = None):
        super().__init__(message)
        self.context = context or ErrorContext(
            error_type=self.__class__.__name__,
            message=message
        )

class URLError(DownloaderError):
    """Base class for URL-related errors."""
    pass

class InvalidURLError(URLError):
    """Invalid URL format."""
    
    def __init__(self, url: str, reason: str = "Invalid URL format"):
        context = ErrorContext(
            error_type="Invalid URL",
            message=f"The URL '{url}' is not valid",
            details=reason,
            recovery_hint="Please check the URL and try again"
        )
        super().__init__(context.message, context)

class UnsupportedURLError(URLError):
    """Unsupported URL scheme."""
    
    def __init__(self, url: str, scheme: str):
        context = ErrorContext(
            error_type="Unsupported URL",
            message=f"The URL scheme '{scheme}' is not supported",
            details=f"URL: {url}",
            recovery_hint="Only HTTP(S) and YouTube URLs are supported"
        )
        super().__init__(context.message, context)

class NetworkError(DownloaderError):
    """Network-related errors."""
    
    def __init__(self, message: str, url: str, error_code: Optional[str] = None):
        context = ErrorContext(
            error_type="Network Error",
            message=message,
            details=f"URL: {url}",
            error_code=error_code,
            recovery_hint="Please check your internet connection and try again"
        )
        super().__init__(message, context)

class FileSystemError(DownloaderError):
    """File system operation errors."""
    
    def __init__(self, message: str, path: str, operation: str):
        context = ErrorContext(
            error_type="File System Error",
            message=message,
            details=f"Path: {path}\nOperation: {operation}",
            recovery_hint="Please check file permissions and available disk space"
        )
        super().__init__(message, context)

class YouTubeError(DownloaderError):
    """YouTube-specific errors."""
    
    def __init__(self, message: str, video_id: str, error_code: Optional[str] = None):
        context = ErrorContext(
            error_type="YouTube Error",
            message=message,
            details=f"Video ID: {video_id}",
            error_code=error_code,
            recovery_hint="The video might be private, age-restricted, or unavailable"
        )
        super().__init__(message, context)

class RetryExceededError(DownloaderError):
    """Maximum retry attempts exceeded."""
    
    def __init__(self, url: str, attempts: int):
        context = ErrorContext(
            error_type="Download Failed",
            message=f"Download failed after {attempts} attempts",
            details=f"URL: {url}",
            recovery_hint="Try again later or check your connection"
        )
        super().__init__(context.message, context)

class CancellationError(DownloaderError):
    """Download cancellation."""
    
    def __init__(self, download_id: str):
        context = ErrorContext(
            error_type="Download Cancelled",
            message=f"Download {download_id} was cancelled",
            recovery_hint="You can start the download again if needed"
        )
        super().__init__(context.message, context)

class CookieError(DownloaderError):
    """Cookie-related errors."""
    
    def __init__(self, message: str, browser: Optional[str] = None):
        context = ErrorContext(
            error_type="Cookie Error",
            message=message,
            details=f"Browser: {browser}" if browser else None,
            recovery_hint="Try logging into YouTube in your browser first or check browser permissions"
        )
        super().__init__(context.message, context)

def handle_download_error(error: Exception) -> None:
    """
    Handle download errors and show appropriate message to user.
    
    This function:
    1. Logs the error with context
    2. Shows a user-friendly message
    3. Provides recovery hints when possible
    
    Args:
        error (Exception): The error that occurred
    """
    logger = DownloaderLogger.get_logger()
    
    # Log the error with context
    if isinstance(error, DownloaderError):
        context = error.context
        logger.error(
            f"{context.error_type}: {context.message}",
            extra={
                'details': context.details,
                'error_code': context.error_code,
                'metadata': context.metadata
            },
            exc_info=True
        )
    else:
        logger.error(f"Unexpected error: {error}", exc_info=True)
    
    # Show user-friendly message
    if isinstance(error, InvalidURLError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, UnsupportedURLError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, NetworkError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, FileSystemError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, YouTubeError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, RetryExceededError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, CancellationError):
        messagebox.showinfo(error.context.error_type, error.context.message)
    elif isinstance(error, CookieError):
        messagebox.showerror(error.context.error_type, error.context.message)
    elif isinstance(error, urllib.error.URLError):
        messagebox.showerror(
            "Network Error",
            "Failed to connect. Please check your internet connection."
        )
    else:
        messagebox.showerror(
            "Error",
            f"An unexpected error occurred: {str(error)}"
        )
