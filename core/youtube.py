"""YouTube video downloader implementation"""

import os
import threading
import subprocess
import logging
import time
import uuid
import re
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass
import tempfile

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import browser_cookie3 as browsercookie
except ImportError:
    browsercookie = None

from utils.errors import YouTubeError, InvalidURLError, DownloaderError
from utils.logger import DownloaderLogger
from utils.file_utils import sanitize_filename
from .config import Config
from .downloader import Downloader

def get_youtube_cookies():
    """Get YouTube cookies from browser"""
    if not browsercookie:
        DownloaderLogger.get_logger().warning("browser-cookie3 not installed; cannot load YouTube cookies")
        return None
        
    cookies = None
    
    # Try Firefox first
    try:
        cookies = browsercookie.firefox(domain_name='.youtube.com')
        if cookies:
            DownloaderLogger.get_logger().info("Successfully loaded YouTube cookies from Firefox")
            return cookies
    except Exception as e:
        DownloaderLogger.get_logger().debug(f"Could not load Firefox cookies: {e}")
    
    # Try Chrome as fallback
    try:
        cookies = browsercookie.chrome(domain_name='.youtube.com')
        if cookies:
            DownloaderLogger.get_logger().info("Successfully loaded YouTube cookies from Chrome")
            return cookies
    except Exception as e:
        DownloaderLogger.get_logger().debug(f"Could not load Chrome cookies: {e}")
    
    if not cookies:
        DownloaderLogger.get_logger().warning("Could not load cookies from any browser")
    
    return cookies

@dataclass
class StreamInfo:
    """Information about a YouTube stream"""
    format_id: str
    ext: str
    height: Optional[int]
    fps: Optional[int]
    vcodec: str
    acodec: str
    filesize: int
    tbr: float
    abr: Optional[float] = None
    
    @property
    def is_video_only(self) -> bool:
        return self.vcodec != 'none' and self.acodec == 'none'
    
    @property
    def is_audio_only(self) -> bool:
        return self.vcodec == 'none' and self.acodec != 'none'
    
    @property
    def is_combined(self) -> bool:
        return self.vcodec != 'none' and self.acodec != 'none'

class YouTubeDownloader(Downloader):
    """YouTube video downloader"""
    
    def __init__(self, url: str, download_dir: str, preferred_quality: str = "1080p + 160k",
                 threads: int = Config.DEFAULT_THREADS):
        """Initialize YouTube downloader
        
        Args:
            url: YouTube URL
            download_dir: Download directory
            preferred_quality: Preferred quality (e.g., "1080p + 160k")
            threads: Number of threads to use
        """
        super().__init__(url, download_dir, threads)
        self.url = url  # Store as instance variable
        self.download_dir = download_dir  # Store as instance variable
        self.preferred_quality = preferred_quality
        self.progress_callback = None
        self._stop_flag = False
        self._lock = threading.Lock()
        self.logger = DownloaderLogger.get_logger()
        self._completion_callback = None
        
        # Parse quality into video and audio components
        quality_parts = preferred_quality.split(" + ")
        if len(quality_parts) != 2:
            raise YouTubeError(f"Invalid quality format: {preferred_quality}")
            
        self.video_quality = quality_parts[0]  # e.g., "1080p"
        self.audio_quality = quality_parts[1]  # e.g., "160k"

    def set_progress_callback(self, callback: Callable) -> None:
        """Set progress callback function
        
        Args:
            callback: Function to call with progress updates
        """
        self.progress_callback = callback
        self.logger.debug(f"Progress callback set: {callback}")
        
    def set_completion_callback(self, callback: Callable) -> None:
        """Set completion callback function
        
        Args:
            callback: Function to call when download is complete
        """
        self._completion_callback = callback
        self.logger.debug(f"Completion callback set: {callback}")
        
    def _extract_formats(self, url: str) -> tuple:
        """Extract available formats for video
        
        Args:
            url: Video URL
            
        Returns:
            Tuple of (video_format, audio_format)
        """
        # Configure yt-dlp options
        ydl_opts = {
            'quiet': True,
            'no_warnings': True,
            'extract_flat': False,  # Changed to False to get full format info
            'format': 'best',  # Default format to ensure we can extract info
            'cookiesfrombrowser': ('firefox',),
        }
        
        try:
            # Extract video info
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=False)
                formats = info['formats']
                
                # Log available formats for debugging
                self.logger.debug("Available formats:")
                for fmt in formats:
                    self.logger.debug(f"Format {fmt.get('format_id')}: {fmt.get('height')}p - {fmt.get('vcodec')}/{fmt.get('acodec')}")
                
                # Get video-only formats
                video_formats = [f for f in formats 
                               if f.get('vcodec', 'none') != 'none' 
                               and f.get('acodec', 'none') == 'none'
                               and f.get('height') is not None]
                
                # Get audio-only formats
                audio_formats = [f for f in formats
                               if f.get('acodec', 'none') != 'none'
                               and f.get('vcodec', 'none') == 'none']
                
                if not video_formats:
                    raise YouTubeError("No video-only formats found")
                if not audio_formats:
                    raise YouTubeError("No audio-only formats found")
                
                # Sort video formats by height
                video_formats.sort(key=lambda x: x.get('height', 0), reverse=True)
                
                # Find best video format close to preferred height
                preferred_height = int(self.video_quality.replace('p', ''))
                best_video = None
                for fmt in video_formats:
                    height = fmt.get('height', 0)
                    if height >= preferred_height * 0.8:  # Accept 80% of preferred height
                        best_video = fmt
                        break
                
                # If no format found above threshold, take highest available
                if not best_video:
                    best_video = video_formats[0]
                
                # Sort audio formats by bitrate
                audio_formats.sort(key=lambda x: float(x.get('abr', 0)), reverse=True)
                
                # Prefer m4a audio format if available
                best_audio = None
                for fmt in audio_formats:
                    if fmt.get('ext', '') == 'm4a':
                        best_audio = fmt
                        break
                
                # If no m4a found, take highest bitrate
                if not best_audio:
                    best_audio = audio_formats[0]
                
                self.logger.info(f"Selected video format: {best_video['format_id']} ({best_video.get('height', 0)}p)")
                self.logger.info(f"Selected audio format: {best_audio['format_id']} ({best_audio.get('abr', 0)}k)")
                
                return best_video, best_audio
                
        except Exception as e:
            raise YouTubeError(f"Failed to extract video formats: {str(e)}")

    def _download_video(self, video_format: dict, audio_format: dict = None, output_path: str = None, video_path: str = None, audio_path: str = None) -> None:
        """Download video and optionally audio streams"""
        try:
            # Create temporary paths if not provided
            if not video_path:
                video_path = f"{output_path}.video.mp4"
            if audio_format and not audio_path:
                audio_path = f"{output_path}.audio.m4a"
            
            # Track completion
            video_complete = False
            audio_complete = False
            download_lock = threading.Lock()
            
            # Base options for both video and audio
            base_opts = {
                'retries': 10,
                'fragment_retries': 10,
                'retry_sleep_functions': {'http': lambda n: 5},
                'ignoreerrors': False,
                'quiet': True,
                'no_warnings': True,
                'cookiesfrombrowser': ('firefox',),
                'http_headers': {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }
            }
            
            # Function to check completion and call callback
            def check_completion():
                nonlocal video_complete, audio_complete
                with download_lock:
                    if (video_complete and audio_complete) or (video_complete and not audio_format):
                        if self._completion_callback:
                            self._completion_callback(self.url)
            
            # Function to download a format
            def download_stream(format_dict, output_file, is_audio=False):
                opts = base_opts.copy()
                opts.update({
                    'format': format_dict['format_id'],
                    'outtmpl': {'default': output_file},
                    'progress_hooks': [lambda d: self._format_progress_hook(
                        d, 
                        f"{self.url}_{'audio' if is_audio else 'video'}", 
                        is_audio,
                        format_dict.get('filesize', 0)
                    )],
                    'extract_flat': True  # Avoid re-extracting format info
                })
                
                with yt_dlp.YoutubeDL(opts) as ydl:
                    try:
                        ydl.download([self.url])
                        nonlocal video_complete, audio_complete
                        with download_lock:
                            if is_audio:
                                audio_complete = True
                            else:
                                video_complete = True
                        # Check completion after updating status
                        check_completion()
                    except Exception as e:
                        self.logger.error(f"Error downloading {'audio' if is_audio else 'video'}: {str(e)}")
                        raise
            
            # Start video download thread
            self.logger.info("Starting video download...")
            video_thread = threading.Thread(
                target=download_stream, 
                args=(video_format, video_path, False)
            )
            video_thread.start()
            
            # Start audio download thread if needed
            audio_thread = None
            if audio_format:
                audio_thread = threading.Thread(
                    target=download_stream, 
                    args=(audio_format, audio_path, True)
                )
                audio_thread.start()
            
            # Wait for downloads to complete
            video_thread.join()
            if audio_thread:
                audio_thread.join()
            
            # Merge if both video and audio were downloaded
            if audio_format:
                self.logger.info("Merging video and audio...")
                if os.path.exists(video_path) and os.path.exists(audio_path):
                    merge_opts = base_opts.copy()
                    merge_opts.update({
                        'format': 'merged',
                        'outtmpl': {'default': output_path},
                        'merge_output_format': 'mp4'
                    })
                    
                    with yt_dlp.YoutubeDL(merge_opts) as ydl:
                        ydl.download(['-'])
                        
                    # Clean up temporary files
                    try:
                        os.remove(video_path)
                        os.remove(audio_path)
                    except Exception as e:
                        self.logger.warning(f"Failed to clean up temporary files: {e}")
                else:
                    raise YouTubeError("Video or audio file missing after download")
            
            # Only call completion callback when both components are done
            if self._completion_callback and (video_complete and (not audio_format or audio_complete)):
                self._completion_callback(self.url)
                
            self.logger.info("Download completed successfully")
                    
        except Exception as e:
            self.logger.error(f"Failed to download video: {str(e)}")
            raise YouTubeError(f"Failed to download video: {str(e)}")

    def _format_size(self, size: float) -> str:
        """Format size in bytes to human readable string"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def _format_progress_hook(self, d: dict, id_: str, is_audio: bool = False, format_size: int = 0) -> None:
        """Format the progress hook data for the progress callback"""
        try:
            if d['status'] == 'downloading':
                total = float(d.get('total_bytes', 0)) or float(d.get('total_bytes_estimate', 0))
                downloaded = float(d.get('downloaded_bytes', 0))
                speed = float(d.get('speed', 0))
                
                if total and downloaded:
                    progress = (downloaded / total) * 100
                    speed_str = f"{self._format_size(speed)}/s" if speed else ""
                    text = f"Downloading {self._format_size(downloaded)}/{self._format_size(total)}"
                    
                    if self.progress_callback:
                        self.progress_callback(
                            id_,
                            progress,
                            speed_str,
                            text,
                            total,
                            downloaded,
                            is_youtube=True,
                            is_audio=is_audio
                        )
                        
            elif d['status'] == 'finished':
                # Send 100% progress
                if self.progress_callback:
                    self.progress_callback(
                        id_,
                        100.0,
                        "",
                        "Download complete",
                        format_size,
                        format_size,
                        is_youtube=True,
                        is_audio=is_audio
                    )
                
        except Exception as e:
            self.logger.error(f"Error in progress hook: {str(e)}")

    def cancel(self):
        """Cancel the download"""
        with self._lock:
            self._stop_flag = True

    def start(self) -> None:
        """Start the download"""
        try:
            if not yt_dlp:
                raise YouTubeError("yt-dlp not installed")
                
            # Create download thread
            download_thread = threading.Thread(
                target=self._download,
                args=(self.url, self.download_dir)
            )
            download_thread.daemon = True
            download_thread.start()
            
        except Exception as e:
            raise YouTubeError(f"Failed to start download: {str(e)}")

    def _download(self, url: str, destination: str) -> None:
        """Download YouTube video
        
        Args:
            url: YouTube URL
            destination: Download destination directory
        """
        try:
            # Get cookies
            cookies = get_youtube_cookies()
            
            # Extract video info
            video_format, audio_format = self._extract_formats(url)
            
            self.logger.info(f"Selected video format: {video_format.get('format_id')} ({video_format.get('height', 0)}p)")
            self.logger.info(f"Selected audio format: {audio_format.get('format_id')} ({audio_format.get('abr', 0)}k)")
            
            # Create unique temporary filenames
            with tempfile.TemporaryDirectory() as temp_dir:
                video_path = os.path.join(temp_dir, "video")
                audio_path = os.path.join(temp_dir, "audio") if audio_format else None
                
                # Get sanitized output filename
                output_filename = sanitize_filename(video_format.get('title', 'Unknown Title'))
                if not output_filename:
                    output_filename = 'video'
                output_path = os.path.join(destination, f"{output_filename}.mp4")
                
                self._download_video(video_format, audio_format, output_path, video_path, audio_path)
                
                # Call completion callback if set
                if self._completion_callback:
                    self._completion_callback(self.url)
                
        except Exception as e:
            self.logger.error(f"YouTube download failed: {e}", exc_info=True)
            # Log error and notify progress callback
            self.logger.error(f"YouTube download failed: {str(e)}")
            
            if self.progress_callback:
                self.progress_callback(
                    download_id=f"{self.url}_video",
                    progress=0,
                    speed="",
                    text=f"Error: {str(e)}",
                    total_size=0,
                    downloaded_size=0,
                    is_youtube=True,
                    is_audio=False
                )
                
                if audio_format:
                    self.progress_callback(
                        download_id=f"{self.url}_audio",
                        progress=0,
                        speed="",
                        text=f"Error: {str(e)}",
                        total_size=0,
                        downloaded_size=0,
                        is_youtube=True,
                        is_audio=True
                    )
                    
            raise YouTubeError(f"Download failed: {str(e)}")
