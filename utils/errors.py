"""
Error handling utilities for JustDownloadIt.

This module provides custom exceptions and error handling functions used throughout the application.
It standardizes error handling and provides user-friendly error messages.

Exceptions:
    DownloaderError: Base exception for all downloader errors
    InvalidURLError: Invalid URL format or scheme
    UnsupportedURLError: URL scheme not supported
    NetworkError: Network-related errors
    FileSystemError: File system operation errors
    YouTubeError: YouTube-specific errors
    CancellationError: Download cancellation errors

Functions:
    handle_download_error: Convert various exceptions to appropriate downloader errors

Dependencies:
    - logging: Error logging
"""

import logging

class DownloaderError(Exception):
    """Base class for downloader exceptions"""
    pass

class URLError(DownloaderError):
    """Raised when there's an issue with the URL"""
    pass

class InvalidURLError(URLError):
    """Raised when a URL is malformed or not properly formatted"""
    pass

class UnsupportedURLError(URLError):
    """Raised when a URL scheme is not supported"""
    pass

class NetworkError(DownloaderError):
    """Raised when there's a network-related issue"""
    pass

class FileSystemError(DownloaderError):
    """Raised when there's a file system related issue"""
    pass

class YouTubeError(DownloaderError):
    """Raised when there's an issue with YouTube downloads"""
    pass

class RetryExceededError(DownloaderError):
    """Raised when max retry attempts are exceeded"""
    pass

class CancellationError(DownloaderError):
    """Raised when a download is cancelled"""
    pass

def handle_download_error(error: Exception) -> tuple[str, str]:
    """
    Handle download errors and return appropriate error messages.
    
    Args:
        error (Exception): The exception that occurred during download
        
    Returns:
        tuple[str, str]: A tuple containing (error type, error message)
            - error type: Short description of the error type (e.g., "Network Error")
            - error message: Detailed error message for display to user
    """
    if isinstance(error, InvalidURLError):
        return "Invalid URL", str(error)
    elif isinstance(error, UnsupportedURLError):
        return "Unsupported URL", str(error)
    elif isinstance(error, URLError):
        return "Invalid URL", str(error)
    elif isinstance(error, NetworkError):
        return "Network Error", str(error)
    elif isinstance(error, FileSystemError):
        return "File System Error", str(error)
    elif isinstance(error, YouTubeError):
        return "YouTube Error", str(error)
    elif isinstance(error, RetryExceededError):
        return "Download Failed", str(error)
    elif isinstance(error, CancellationError):
        return "Download Cancelled", str(error)
    elif isinstance(error, urllib.error.URLError):
        return "Invalid URL", "The URL format is not valid. Please enter a valid HTTP/HTTPS URL."
    else:
        return "Error", f"An unexpected error occurred: {str(error)}"
