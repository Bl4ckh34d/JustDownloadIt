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
from utils.file_utils import sanitize_filename, get_unique_filename
from .config import Config
from .regular_downloader import Downloader
from .download_state import DownloadState

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
        super().__init__(url, Path(download_dir), threads)
        self.url = url  # Store as instance variable
        self.download_dir = Path(download_dir)  # Store as Path object
        self.preferred_quality = preferred_quality
        self.audio_only = audio_only
        self.progress_callback = None
        self._stop_flag = False
        self._lock = threading.Lock()
        self.logger = DownloaderLogger.get_logger()
        self._completion_callback = None
        self.download_id = str(uuid.uuid4())  # Generate a unique download ID
        self.video_title = None
        
        # Parse quality into video and audio components
        quality_parts = preferred_quality.split(" + ")
        if len(quality_parts) != 2:
            raise YouTubeError(f"Invalid quality format: {preferred_quality}")
            
        self.video_quality = quality_parts[0] if not audio_only else None  # e.g., "1080p"
        self.audio_quality = quality_parts[1]  # e.g., "160k"
        
        # Create download directory if it doesn't exist
        self.download_dir.mkdir(parents=True, exist_ok=True)

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
        Extract available formats from YouTube URL.
        
        Args:
            url: YouTube URL
            
        Returns:
            tuple: (video_format, audio_format)
        """
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                info = ydl.extract_info(url, download=False)
                self.video_title = info.get('title', 'Unknown Title')
                
                # Get available formats
                formats = info.get('formats', [])
                
                # Find best audio format
                audio_format = None
                for f in formats:
                    if f.get('acodec', 'none') != 'none' and f.get('vcodec') == 'none':
                        if not audio_format or f.get('abr', 0) > audio_format.get('abr', 0):
                            audio_format = f
                
                if self.audio_only:
                    return None, audio_format
                    
                # Find best video format based on quality preference
                video_format = None
                target_height = int(self.video_quality.replace('p', '')) if self.video_quality != 'highest' else float('inf')
                
                for f in formats:
                    if f.get('vcodec', 'none') != 'none':
                        height = f.get('height', 0)
                        
                        # For highest quality, take highest resolution
                        if self.video_quality == 'highest':
                            if not video_format or height > video_format.get('height', 0):
                                video_format = f
                                 
                        # For specific quality, take closest without going over
                        else:
                            if height <= target_height:
                                if not video_format or height > video_format.get('height', 0):
                                    video_format = f
                
                return video_format, audio_format
                
        except Exception as e:
            raise YouTubeError(f"Failed to extract video formats: {e}")

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
            # Create temporary directory for intermediate files
            with tempfile.TemporaryDirectory() as temp_dir:
                # Create unique temp paths for video and audio
                temp_dir_path = Path(temp_dir)
                
                # Store actual paths after getting unique names
                actual_video_path = None
                actual_audio_path = None
                
                # Prepare download threads
                download_threads = []
                download_events = []
                
                # Setup video download if needed
                if video_format:
                    # Get unique name for video using download_id
                    video_temp_name = f"{self.video_title}_{self.download_id}_video.mp4"
                    actual_video_path = str(get_unique_filename(temp_dir_path / video_temp_name)) if not video_path else video_path
                    video_done = threading.Event()
                    video_thread = threading.Thread(
                        target=self.download_stream,
                        args=(video_format, actual_video_path),
                        kwargs={'is_audio': False}
                    )
                    download_threads.append(video_thread)
                    download_events.append(video_done)
                    video_thread.start()
                
                # Setup audio download if needed
                if audio_format:
                    # Get unique name for audio using download_id
                    audio_temp_name = f"{self.video_title}_{self.download_id}_audio.m4a"
                    actual_audio_path = str(get_unique_filename(temp_dir_path / audio_temp_name)) if not audio_path else audio_path
                    audio_done = threading.Event()
                    audio_thread = threading.Thread(
                        target=self.download_stream,
                        args=(audio_format, actual_audio_path),
                        kwargs={'is_audio': True}
                    )
                    download_threads.append(audio_thread)
                    download_events.append(audio_done)
                    audio_thread.start()
                
                # Wait for all downloads to complete
                for thread in download_threads:
                    thread.join()
                
                # If no output path specified, create one
                if not output_path:
                    filename = f"{sanitize_filename(self.video_title)}.{'mp3' if self.audio_only else 'mp4'}"
                    output_path = str(get_unique_filename(self.download_dir / filename))
                
                # If only downloading audio
                if self.audio_only and actual_audio_path:
                    # Just move audio file to output path
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(actual_audio_path, output_path)
                    return
                
                # Combine streams if we have both
                if video_format and audio_format and actual_video_path and actual_audio_path:
                    # Create unique temp path for combined file using download_id
                    combined_temp_name = f"{self.video_title}_{self.download_id}_combined.mp4"
                    temp_combined = str(get_unique_filename(temp_dir_path / combined_temp_name))
                    
                    # Combine video and audio using ffmpeg
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', actual_video_path,  # Use actual video path
                        '-i', actual_audio_path,  # Use actual audio path
                        '-c', 'copy',
                        temp_combined
                    ]
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE
                    )
                    
                    stdout, stderr = process.communicate()
                    
                    if process.returncode != 0:
                        raise YouTubeError(f"Failed to combine streams: {stderr.decode()}")
                        
                    # Move combined file to final destination
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(temp_combined, output_path)
                elif actual_video_path:
                    # Just move video file to output path
                    if os.path.exists(output_path):
                        os.remove(output_path)
                    os.rename(actual_video_path, output_path)
                    
        except Exception as e:
            raise YouTubeError(f"Failed to download video: {str(e)}")

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
                        state = DownloadState.DOWNLOADING if d['status'] == 'downloading' else DownloadState.COMPLETED
                        
                        # For audio-only downloads, don't specify component
                        if self.audio_only:
                            self.progress_callback(
                                progress=progress,
                                speed=speed_str,
                                text=f"Downloading {self.video_title}",
                                total_size=total,
                                downloaded_size=downloaded,
                                stats={
                                    'peak_speed': speed,
                                    'avg_speed': speed,
                                    'total_time': 0,
                                    'timestamps': [],
                                    'speeds': []
                                },
                                state=state
                            )
                        else:
                            # For video downloads, specify component
                            self.progress_callback(
                                progress=progress,
                                speed=speed_str,
                                text=f"Downloading {self.video_title} ({'audio' if is_audio else 'video'})",
                                total_size=total,
                                downloaded_size=downloaded,
                                stats={
                                    'peak_speed': speed,
                                    'avg_speed': speed,
                                    'total_time': 0,
                                    'timestamps': [],
                                    'speeds': []
                                },
                                state=state,
                                component="audio" if is_audio else "video"
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
                # For audio-only downloads, don't specify component
                if self.audio_only:
                    self.progress_callback(
                        progress=100.0,
                        speed="",
                        text=f"Download complete",
                        total_size=self._current_progress['total'],
                        downloaded_size=self._current_progress['total'],
                        stats=None,
                        state=DownloadState.COMPLETED
                    )
                else:
                    # For video downloads, specify component
                    self.progress_callback(
                        progress=100.0,
                        speed="",
                        text=f"{'Audio' if is_audio else 'Video'} download complete",
                        total_size=self._current_progress['total'],
                        downloaded_size=self._current_progress['total'],
                        stats=None,
                        state=DownloadState.COMPLETED,
                        component="audio" if is_audio else "video"
                    )
                
        except Exception as e:
            self.logger.error(f"Error in download_stream: {e}")
            video_id = extract_video_id(self.url) or "unknown"
            raise YouTubeError(f"Error downloading stream: {e}", video_id)

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
                    progress=progress,
                    speed=speed_str,
                    text=text,
                    total_size=total,
                    downloaded_size=downloaded,
                    stats={
                        'peak_speed': speed,
                        'avg_speed': speed,
                        'total_time': 0,
                        'timestamps': [],
                        'speeds': []
                    },
                    state=DownloadState.DOWNLOADING,
                    component="audio" if self.audio_only or is_audio else "video"
                )
                
            elif status == 'finished':
                self.progress_callback(
                    progress=100.0,
                    speed="",
                    text="Download complete",
                    total_size=format_size,
                    downloaded_size=format_size,
                    stats=None,
                    state=DownloadState.COMPLETED,
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
