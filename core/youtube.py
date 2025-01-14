"""
YouTube downloader implementation for JustDownloadIt.

This module provides YouTube-specific download functionality through the YouTubeDownloader class.
It handles both video and audio downloads with quality selection and format options.

Features:
    - Video quality selection (up to 4K)
    - Audio quality selection
    - Format selection (MP4, WebM)
    - Automatic stream selection based on quality preferences
    - Video and audio stream merging
    - Thumbnail download option
    - Cookie support for age-restricted videos

Classes:
    StreamInfo: Container for YouTube stream information
    YouTubeDownloader: YouTube-specific downloader implementation

Dependencies:
    - yt-dlp: YouTube download library
    - ffmpeg: Media processing for stream merging
    - core.downloader: Base download functionality
    - core.config: Application configuration
"""

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
    """
    Get YouTube cookies from browser.
    
    Returns:
        dict: Cookies for YouTube
    """
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
    """
    Information about a YouTube stream.
    
    Attributes:
        format_id (str): YouTube format ID
        ext (str): File extension (e.g., "mp4")
        height (Optional[int]): Video height
        fps (Optional[int]): Frames per second
        vcodec (str): Video codec
        acodec (str): Audio codec
        filesize (int): File size in bytes
        tbr (float): Total bitrate
        abr (Optional[float]): Audio bitrate
    """
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
        """
        Check if this is a video-only stream.
        
        Returns:
            bool: Whether this is a video-only stream
        """
        return self.vcodec != 'none' and self.acodec == 'none'
    
    @property
    def is_audio_only(self) -> bool:
        """
        Check if this is an audio-only stream.
        
        Returns:
            bool: Whether this is an audio-only stream
        """
        return self.vcodec == 'none' and self.acodec != 'none'
    
    @property
    def is_combined(self) -> bool:
        """
        Check if this is a combined video and audio stream.
        
        Returns:
            bool: Whether this is a combined stream
        """
        return self.vcodec != 'none' and self.acodec != 'none'

class YouTubeDownloader(Downloader):
    """
    YouTube video downloader.
    
    Attributes:
        url (str): YouTube video URL
        download_dir (str): Download directory
        preferred_quality (str): Preferred quality (e.g., "1080p + 160k")
        threads (int): Number of threads to use
        audio_only (bool): If True, only download audio
    """
    
    def __init__(self, url: str, download_dir: str, preferred_quality: str = "1080p + 160k",
                 threads: int = Config.DEFAULT_THREADS, audio_only: bool = False):
        """
        Initialize YouTube downloader.
        
        Args:
            url: YouTube URL
            download_dir: Download directory
            preferred_quality: Preferred quality (e.g., "1080p + 160k")
            threads: Number of threads to use
            audio_only: If True, only download audio
        """
        super().__init__(url, download_dir, threads)
        self.url = url  # Store as instance variable
        self.download_dir = download_dir  # Store as instance variable
        self.preferred_quality = preferred_quality
        self.audio_only = audio_only
        self.progress_callback = None
        self._stop_flag = False
        self._lock = threading.Lock()
        self.logger = DownloaderLogger.get_logger()
        self._completion_callback = None
        self.download_id = str(uuid.uuid4())  # Generate a unique download ID
        
        # Parse quality into video and audio components
        quality_parts = preferred_quality.split(" + ")
        if len(quality_parts) != 2:
            raise YouTubeError(f"Invalid quality format: {preferred_quality}")
            
        self.video_quality = quality_parts[0] if not audio_only else None  # e.g., "1080p"
        self.audio_quality = quality_parts[1]  # e.g., "160k"

    def set_progress_callback(self, callback: Callable) -> None:
        """
        Set progress callback function.
        
        Args:
            callback: Function to call with progress updates
        """
        self.progress_callback = callback
        self.logger.debug(f"Progress callback set: {callback}")
        
    def set_completion_callback(self, callback: Callable) -> None:
        """
        Set completion callback function.
        
        Args:
            callback: Function to call when download is complete
        """
        self._completion_callback = callback
        self.logger.debug(f"Completion callback set: {callback}")
        
    def _extract_formats(self, url: str) -> tuple[Optional[dict], Optional[dict]]:
        """
        Extract video and audio formats from YouTube URL.
        
        Args:
            url (str): YouTube video URL
            
        Returns:
            tuple[Optional[dict], Optional[dict]]: Selected video and audio formats
            
        Raises:
            YouTubeError: If format extraction fails
        """
        try:
            # Extract available formats
            ydl = yt_dlp.YoutubeDL({'quiet': True})
            info = ydl.extract_info(url, download=False)
            formats = info.get('formats', [])
            
            # Filter formats
            video_formats = []
            audio_formats = []
            
            for f in formats:
                if f.get('vcodec') != 'none' and f.get('acodec') == 'none':
                    video_formats.append(f)
                elif f.get('acodec') != 'none' and f.get('vcodec') == 'none':
                    audio_formats.append(f)
                    
            if not video_formats and not audio_formats:
                raise YouTubeError("No suitable formats found")
                
            # Sort formats by quality
            video_formats.sort(key=lambda x: (x.get('height', 0) or 0, x.get('filesize', 0) or 0), reverse=True)
            audio_formats.sort(key=lambda x: (x.get('abr', 0) or 0, x.get('filesize', 0) or 0), reverse=True)
            
            # Handle audio-only downloads
            if self.audio_only:
                return None, self._select_audio_format(audio_formats)
                
            # Select video format based on quality preference
            video_format = None
            if self.video_quality is None or self.video_quality.lower() == 'highest':
                # Choose highest quality available
                video_format = video_formats[0] if video_formats else None
            else:
                # Try to match requested quality
                target_height = int(self.video_quality.rstrip('p'))
                # Find the closest match that doesn't exceed target
                closest_format = None
                min_diff = float('inf')
                for fmt in video_formats:
                    height = fmt.get('height', 0) or 0
                    if height <= target_height:
                        diff = target_height - height
                        if diff < min_diff:
                            min_diff = diff
                            closest_format = fmt
                video_format = closest_format or video_formats[-1]  # Use lowest if no match found
                
            # Select audio format
            audio_format = self._select_audio_format(audio_formats)
                
            return video_format, audio_format
            
        except Exception as e:
            raise YouTubeError(f"Failed to extract video formats: {str(e)}")

    def _select_audio_format(self, audio_formats: list) -> Optional[dict]:
        """
        Select the best audio format from available formats.
        
        Args:
            audio_formats (list): List of available audio formats
            
        Returns:
            Optional[dict]: Selected audio format or None if no suitable format found
        """
        if not audio_formats:
            return None
            
        # Prefer m4a format with highest bitrate
        m4a_formats = [f for f in audio_formats if f.get('ext') == 'm4a']
        if m4a_formats:
            return m4a_formats[0]  # Already sorted by bitrate
            
        # Otherwise use highest bitrate format
        return audio_formats[0]

    def _download(self, url: str, destination: str):
        """
        Download YouTube video.
        
        Args:
            url: YouTube URL
            destination: Download destination directory
        """
        try:
            # Extract available formats
            video_format, audio_format = self._extract_formats(url)
            
            # Generate unique output paths
            base_name = str(uuid.uuid4())
            output_path = os.path.join(destination, f"{base_name}_final.mp4")
            video_path = os.path.join(destination, f"{base_name}_video.mp4") if not self.audio_only else None
            audio_path = os.path.join(destination, f"{base_name}_audio.m4a")
            
            # Download streams
            if self.audio_only:
                # Audio only - download and convert directly
                self._download_video(
                    video_format=None,
                    audio_format=audio_format,
                    output_path=output_path,
                    audio_path=audio_path
                )
            else:
                # Video + Audio - download both and mux
                self._download_video(
                    video_format=video_format,
                    audio_format=audio_format,
                    output_path=output_path,
                    video_path=video_path,
                    audio_path=audio_path
                )
                
        except Exception as e:
            self.logger.error(f"Error downloading YouTube video: {e}")
            raise YouTubeError(f"Failed to download video: {e}")

    def _download_video(self, video_format: dict, audio_format: dict = None, output_path: str = None,
                   video_path: str = None, audio_path: str = None):
        """
        Download video and optionally audio streams.
        
        Args:
            video_format: Video format dictionary
            audio_format: Audio format dictionary (optional)
            output_path: Output path for combined video (optional)
            video_path: Output path for video stream (optional)
            audio_path: Output path for audio stream (optional)
        """
        try:
            # Create threads for video and audio downloads
            threads = []
            if video_format:
                video_thread = threading.Thread(
                    target=self.download_stream,
                    args=(video_format, video_path),
                    kwargs={'is_audio': False}
                )
                threads.append(video_thread)
                
            if audio_format:
                audio_thread = threading.Thread(
                    target=self.download_stream,
                    args=(audio_format, audio_path),
                    kwargs={'is_audio': True}
                )
                threads.append(audio_thread)
                
            # Start all download threads
            for thread in threads:
                thread.start()
                
            # Wait for all downloads to complete
            for thread in threads:
                thread.join()

            # Check if both files exist before merging
            if video_format and not os.path.exists(video_path):
                raise YouTubeError(f"Video file not found: {video_path}")
            if audio_format and not os.path.exists(audio_path):
                raise YouTubeError(f"Audio file not found: {audio_path}")

            # Merge video and audio if needed
            if audio_format and video_format:
                # Ensure output directory exists
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                
                # Run FFmpeg command
                try:
                    subprocess.run([
                        'ffmpeg', '-y',
                        '-i', video_path,
                        '-i', audio_path,
                        '-c', 'copy',
                        output_path
                    ], check=True, capture_output=True, text=True)
                except subprocess.CalledProcessError as e:
                    raise YouTubeError(f"FFmpeg error: {e.stderr or str(e)}")
                    
                # Clean up temporary files
                try:
                    os.remove(video_path)
                    os.remove(audio_path)
                except OSError as e:
                    self.logger.warning(f"Failed to clean up temporary files: {e}")
            elif video_format:
                # Just rename video file to final output
                os.rename(video_path, output_path)
            else:
                # Audio only - rename audio file to final output
                os.rename(audio_path, output_path)
                
        except Exception as e:
            raise YouTubeError(f"Error in download_video: {e}")

    def download_stream(self, format_info: dict, output_path: str, is_audio: bool = False) -> None:
        """
        Download a single stream (video or audio).
        
        Args:
            format_info: Format information dictionary from yt-dlp
            output_path: Path to save the stream
            is_audio: Whether this is an audio stream
        """
        try:
            self.logger.debug(f"Starting download of {'audio' if is_audio else 'video'} stream to {output_path}")
            
            # Store download progress state
            self._current_progress = {
                'downloaded': 0,
                'total': format_info.get('filesize', 0),
                'speed': 0,
                'status': 'downloading'
            }

            def progress_hook(d):
                try:
                    self.logger.debug(f"Progress hook called with status: {d['status']}")
                    # Update current progress with safe float conversion
                    speed = d.get('speed')
                    if speed is not None:
                        try:
                            speed = float(speed)
                        except (ValueError, TypeError):
                            speed = 0
                    else:
                        speed = 0
                        
                    downloaded = d.get('downloaded_bytes', 0)
                    if downloaded is not None:
                        try:
                            downloaded = float(downloaded)
                        except (ValueError, TypeError):
                            downloaded = 0
                            
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    if total is not None:
                        try:
                            total = float(total)
                        except (ValueError, TypeError):
                            total = 0

                    self._current_progress.update({
                        'downloaded': downloaded,
                        'total': total,
                        'speed': speed,
                        'status': d['status']
                    })
                    
                    # Calculate progress percentage
                    if total > 0:
                        progress = (downloaded / total) * 100
                    else:
                        progress = 0
                        
                    # Format speed string
                    speed_str = f"{self._format_size(speed)}/s" if speed else ""
                    
                    # Call progress callback with component-specific progress
                    if self.progress_callback:
                        self.progress_callback(
                            self.download_id,
                            progress,
                            DownloadState.DOWNLOADING if d['status'] == 'downloading' else DownloadState.FINISHED,
                            speed_str,
                            f"Downloading {'audio' if is_audio else 'video'}",
                            total,
                            downloaded,
                            stats={
                                'peak_speed': speed,
                                'avg_speed': speed,
                                'total_time': 0,
                                'timestamps': [],
                                'speeds': []
                            },
                            component="audio" if self.audio_only or is_audio else "video"
                        )
                        
                except Exception as e:
                    self.logger.error(f"Error in progress hook: {e}")

            ydl_opts = {
                'format': format_info['format_id'],
                'outtmpl': output_path,
                'quiet': True,
                'no_warnings': True,
                'progress_hooks': [progress_hook]
            }
            
            # Start download in a separate thread
            download_thread = threading.Thread(target=lambda: yt_dlp.YoutubeDL(ydl_opts).download([self.url]))
            download_thread.start()
            
            # Monitor progress in main thread
            while download_thread.is_alive() and not self._stop_flag:
                if self._current_progress['status'] == 'downloading':
                    downloaded = self._current_progress['downloaded']
                    total = self._current_progress['total']
                    speed = self._current_progress['speed']
                    
                    if total and downloaded:
                        self.logger.debug(f"Progress: {downloaded}/{total} at {speed}/s")
                
                time.sleep(0.1)  # Brief sleep to prevent high CPU usage
                
            # Wait for download thread to finish
            download_thread.join()
            self.logger.debug(f"Download thread finished for {'audio' if is_audio else 'video'} stream")
            
            # Send final progress update
            if self.progress_callback:
                self.progress_callback(
                    self.download_id,
                    100.0,
                    DownloadState.FINISHED,
                    "",
                    f"{'Audio' if is_audio else 'Video'} download complete",
                    self._current_progress['total'],
                    self._current_progress['total'],
                    stats=None,
                    component="audio" if self.audio_only or is_audio else "video"
                )
                
        except Exception as e:
            self.logger.error(f"Error in download_stream: {e}")
            raise YouTubeError(f"Error downloading stream: {e}")

    def _format_progress_hook(self, d: dict, id_: str, is_audio: bool = False, format_size: int = 0) -> None:
        """
        Format the progress hook data for the progress callback.
        
        Args:
            d: Progress hook data
            id_: Download ID
            is_audio: Whether this is an audio stream (optional)
            format_size: Total size of the format (optional)
        """
        if not self.progress_callback:
            return
            
        try:
            status = d['status']
            
            if status == 'downloading':
                downloaded = d.get('downloaded_bytes', 0)
                total = d.get('total_bytes') or d.get('total_bytes_estimate', format_size)
                speed = d.get('speed', 0)
                
                if total:
                    progress = (downloaded / total) * 100
                else:
                    progress = 0
                    
                speed_str = f"{self._format_size(speed)}/s" if speed else ""
                text = f"Downloading {self._format_size(downloaded)}/{self._format_size(total)}"
                
                self.progress_callback(
                    self.download_id,
                    progress,
                    DownloadState.DOWNLOADING,
                    speed_str,
                    text,
                    total,
                    downloaded,
                    stats={
                        'peak_speed': speed,
                        'avg_speed': speed,
                        'total_time': 0,
                        'timestamps': [],
                        'speeds': []
                    },
                    component="audio" if self.audio_only or is_audio else "video"
                )
                
            elif status == 'finished':
                self.progress_callback(
                    self.download_id,
                    100.0,
                    DownloadState.FINISHED,
                    "",
                    "Download complete",
                    format_size,
                    format_size,
                    stats=None,
                    component="audio" if self.audio_only or is_audio else "video"
                )
                
        except Exception as e:
            self.logger.error(f"Error in progress hook: {e}")

    def _format_size(self, size: float) -> str:
        """
        Format size in bytes to human readable string.
        
        Args:
            size: Size in bytes
        
        Returns:
            str: Formatted size string (e.g., "1.5 GB")
        """
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"

    def cancel(self):
        """
        Cancel the download.
        """
        with self._lock:
            self._stop_flag = True

    def start(self) -> None:
        """
        Start the download.
        """
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
