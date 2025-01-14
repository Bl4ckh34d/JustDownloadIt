"""Core functionality for JustDownloadIt"""

from .regular_downloader import Downloader
from .youtube_downloader import YouTubeDownloader

__all__ = ['Downloader', 'YouTubeDownloader']