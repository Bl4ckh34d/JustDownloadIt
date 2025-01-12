"""Download implementations for different types of downloads"""

from .downloader import Downloader
from .youtube import YouTubeDownloader

__all__ = ['Downloader', 'YouTubeDownloader']
