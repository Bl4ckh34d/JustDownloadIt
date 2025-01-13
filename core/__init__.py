"""Core functionality for JustDownloadIt"""

from .downloader import Downloader
from .youtube import YouTubeDownloader

__all__ = ['Downloader', 'YouTubeDownloader']