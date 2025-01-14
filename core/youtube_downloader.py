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
import shutil

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import browser_cookie3 as browsercookie
except ImportError:
    browsercookie = None

from utils.errors import YouTubeError, InvalidURLError, DownloaderError, CookieError
from utils.logger import DownloaderLogger
from utils.file_utils import sanitize_filename, get_unique_filename
from utils.download_utils import format_size, validate_url
from .config import Config
from .regular_downloader import Downloader
from .download_state import DownloadState

def get_youtube_cookies():
    """
    Get YouTube cookies from browser.
    
    Returns:
        tuple: (http.cookiejar.CookieJar, str) - Cookie jar with YouTube cookies and browser name or (None, None) if not available
        
    Raises:
        CookieError: If there's an error accessing browser cookies
    """
    logger = DownloaderLogger.get_logger()
    
    if not browsercookie:
        logger.warning("browser-cookie3 not installed; cannot load YouTube cookies")
        return None, None
    
    # Try browsers in order of preference
    browsers_to_try = [
        ('chrome', browsercookie.chrome),
        ('firefox', browsercookie.firefox),
        ('chromium', browsercookie.chromium),
        ('opera', browsercookie.opera),
        ('edge', browsercookie.edge),
        ('brave', browsercookie.brave),
    ]
    
    errors = []
    for browser_name, browser_func in browsers_to_try:
        try:
            cookies = browser_func(domain_name='.youtube.com')
            if cookies:
                logger.info(f"Successfully loaded YouTube cookies from {browser_name.title()}")
                return cookies, browser_name
        except Exception as e:
            error_msg = str(e)
            errors.append((browser_name, error_msg))
            if "load NSS" in error_msg and browser_name == 'firefox':
                logger.debug(f"Firefox profile error: {error_msg}")
            elif "Encryption key" in error_msg and browser_name in ['chrome', 'chromium', 'edge', 'brave']:
                logger.debug(f"{browser_name.title()} keyring error: {error_msg}")
            else:
                logger.debug(f"Could not load {browser_name.title()} cookies: {error_msg}")
    
    # If we got here, no browser worked
    if errors:
        error_details = "\n".join(f"{browser}: {error}" for browser, error in errors)
        logger.warning(f"Could not load cookies from any browser:\n{error_details}")
    
    return None, None

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
        
        Raises:
            YouTubeError: If format extraction fails
        """
        try:
            # Try to get cookies first
            cookies_result, browser_name = None, None
            try:
                cookies_result, browser_name = get_youtube_cookies()
            except CookieError as e:
                self.logger.warning(f"Cookie loading failed: {e.context.message}")
        
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'extract_flat': False,
            }
            
            # Try with browser cookies if available
            if browser_name:
                ydl_opts['cookiesfrombrowser'] = (browser_name,)
        
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extract video info
                try:
                    info = ydl.extract_info(url, download=False)
                except Exception as e:
                    error_msg = str(e).lower()
                    if 'age-restricted' in error_msg:
                        if not browser_name:
                            # If age-restricted and no cookies, provide specific error
                            raise YouTubeError(
                                "This video is age-restricted and requires authentication. Please log into YouTube in your browser.",
                                video_id=url,
                                error_code="AGE_RESTRICTED"
                            )
                        else:
                            # If we have cookies but still can't access, the account might not be old enough
                            raise YouTubeError(
                                f"Age-restricted video not accessible with {browser_name.title()} cookies. Try a different browser or account.",
                                video_id=url,
                                error_code="AGE_RESTRICTED_AUTH_FAILED"
                            )
                    elif 'private video' in error_msg:
                        raise YouTubeError(
                            "This video is private. Make sure you're logged into an account with access.",
                            video_id=url,
                            error_code="PRIVATE_VIDEO"
                        )
                    elif 'sign in' in error_msg:
                        raise YouTubeError(
                            "This video requires authentication. Please log into YouTube in your browser.",
                            video_id=url,
                            error_code="AUTH_REQUIRED"
                        )
                    raise
            
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
            if isinstance(e, YouTubeError):
                raise
            raise YouTubeError(f"Failed to extract video formats: {str(e)}", video_id=url)

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
                self._download_stream(
                    url=url,
                    format_id=audio_format['format_id'],
                    target_path=output_path,
                    is_audio=True
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
            if isinstance(e, YouTubeError):
                raise
            video_id = url.split("v=")[-1] if "v=" in url else url
            raise YouTubeError(f"Error downloading YouTube video: {str(e)}", video_id=video_id)

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
            # Create temporary directory for downloads
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_dir_path = Path(temp_dir)
                self.logger.info(f"Created temporary directory for download: {temp_dir}")
                
                # Prepare download threads
                download_threads = []
                
                # Setup video download if needed
                actual_video_path = None
                if video_format:
                    # Use simple temporary names
                    video_temp_name = f"video_{self.download_id}.mp4"
                    actual_video_path = str(temp_dir_path / video_temp_name) if not video_path else video_path
                    self.logger.info(f"Starting video download to: {actual_video_path}")
                    self.logger.debug(f"Video format: {video_format.get('format_id')} - {video_format.get('ext')} - {video_format.get('height')}p")
                    video_thread = threading.Thread(
                        target=self._download_stream,
                        args=(self.url, video_format['format_id'], actual_video_path),
                        kwargs={'is_audio': False}
                    )
                    download_threads.append(video_thread)
                    video_thread.start()
                
                # Setup audio download if needed
                actual_audio_path = None
                if audio_format:
                    # Use simple temporary names
                    audio_temp_name = f"audio_{self.download_id}.m4a"
                    actual_audio_path = str(temp_dir_path / audio_temp_name) if not audio_path else audio_path
                    self.logger.info(f"Starting audio download to: {actual_audio_path}")
                    self.logger.debug(f"Audio format: {audio_format.get('format_id')} - {audio_format.get('ext')} - {audio_format.get('abr')}kbps")
                    audio_thread = threading.Thread(
                        target=self._download_stream,
                        args=(self.url, audio_format['format_id'], actual_audio_path),
                        kwargs={'is_audio': True}
                    )
                    download_threads.append(audio_thread)
                    audio_thread.start()
                
                # Wait for all downloads to complete
                for thread in download_threads:
                    thread.join()
                self.logger.info("All download threads completed")
                
                # If no output path specified, create one
                if not output_path:
                    filename = f"{sanitize_filename(self.video_title)}.{'mp3' if self.audio_only else 'mp4'}"
                    output_path = str(get_unique_filename(self.download_dir / filename))
                    self.logger.info(f"Generated output path: {output_path}")
                
                # If only downloading audio
                if self.audio_only and actual_audio_path and os.path.exists(actual_audio_path):
                    self.logger.info("Audio-only download - moving audio file to final destination")
                    # Just move audio file to output path
                    if os.path.exists(output_path):
                        self.logger.debug(f"Removing existing file at {output_path}")
                        os.remove(output_path)
                    shutil.move(actual_audio_path, output_path)
                    self.logger.info(f"Successfully moved audio file to: {output_path}")
                    return
                
                # Combine streams if we have both
                if (video_format and audio_format and actual_video_path and actual_audio_path and 
                    os.path.exists(actual_video_path) and os.path.exists(actual_audio_path)):
                    self.logger.info("Starting muxing process for video and audio streams")
                    self.logger.debug(f"Video file exists: {os.path.exists(actual_video_path)}, size: {os.path.getsize(actual_video_path)} bytes")
                    self.logger.debug(f"Audio file exists: {os.path.exists(actual_audio_path)}, size: {os.path.getsize(actual_audio_path)} bytes")
                    
                    # Create simple temp path for combined file
                    temp_combined = str(temp_dir_path / f"combined_{self.download_id}.mp4")
                    
                    # Add progress flag for FFmpeg
                    cmd = [
                        'ffmpeg', '-y',
                        '-i', actual_video_path,
                        '-i', actual_audio_path,
                        '-c:v', 'copy',  # Copy video codec
                        '-c:a', 'aac',   # Use AAC for audio
                        '-strict', 'experimental',
                        '-map', '0:v:0',  # Map first video stream from first input
                        '-map', '1:a:0',  # Map first audio stream from second input
                        '-stats',  # Print progress to stderr
                        temp_combined
                    ]
                    
                    self.logger.debug(f"FFmpeg command: {' '.join(cmd)}")
                    
                    process = subprocess.Popen(
                        cmd,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        bufsize=1,
                        universal_newlines=True,
                        creationflags=subprocess.CREATE_NO_WINDOW  # Hide console window
                    )
                    
                    # Read progress output
                    duration = None
                    frame_count = 0
                    last_progress_update = time.time()
                    
                    # First get duration from stderr
                    while True:
                        err_line = process.stderr.readline()
                        if not err_line:
                            break
                            
                        if 'Duration:' in err_line:
                            try:
                                # Parse duration in format Duration: 00:00:00.00
                                time_str = err_line.split('Duration: ')[1].split(',')[0].strip()
                                h, m, s = map(float, time_str.split(':'))
                                duration = h * 3600 + m * 60 + s
                                self.logger.info(f"Total duration to process: {duration:.2f} seconds")
                                break
                            except Exception as e:
                                self.logger.warning(f"Could not parse duration: {str(e)}")
                                break
                    
                    # Monitor stderr for progress
                    while process.poll() is None:
                        err_line = process.stderr.readline()
                        if not err_line:
                            continue
                            
                        err_line = err_line.strip()
                        if not err_line:
                            continue
                            
                        self.logger.debug(f"FFmpeg output: {err_line}")
                        
                        # Skip state lines
                        if err_line == "PROCESSING":
                            continue
                            
                        # Parse frame progress
                        if 'frame=' in err_line and 'time=' in err_line and 'speed=' in err_line:
                            try:
                                # Extract time in format HH:MM:SS.ms
                                time_str = err_line.split('time=')[1].split(' ')[0].strip()
                                if ':' in time_str:
                                    h, m, s = map(float, time_str.split(':'))
                                    time_processed = h * 3600 + m * 60 + s
                                    
                                    if duration and time_processed <= duration:
                                        progress = (time_processed / duration) * 100
                                        
                                        # Only update progress every 100ms to avoid GUI freezing
                                        current_time = time.time()
                                        if current_time - last_progress_update >= 0.1:
                                            # Extract speed
                                            speed = "N/A"
                                            try:
                                                speed = err_line.split('speed=')[1].split('x')[0].strip() + "x"
                                            except:
                                                pass
                                                
                                            self.logger.info(f"Muxing Progress: {progress:>6.1f}% | Time: {time_processed:>6.1f}/{duration:<6.1f}s | Speed: {speed}")
                                            
                                            # Update progress through callback
                                            if self.progress_callback:
                                                self.progress_callback(
                                                    progress=progress,
                                                    speed=speed,
                                                    text=f"Muxing: {progress:.1f}%",
                                                    total_size=100,
                                                    downloaded_size=progress,
                                                    stats=None,
                                                    state=DownloadState.PROCESSING,
                                                    component="muxing"
                                                )
                                            last_progress_update = current_time
                                            
                                # Also track frame count for progress estimation if duration is unknown
                                frame_str = err_line.split('frame=')[1].split(' ')[0].strip()
                                frame_count = int(frame_str)
                                
                            except Exception as e:
                                self.logger.debug(f"Could not parse progress from line: {err_line}")
                        
                        # Log any errors
                        elif 'error' in err_line.lower():
                            self.logger.error(f"FFmpeg error: {err_line}")
                    
                    # Get final status
                    returncode = process.wait()
                    if returncode != 0:
                        error_msg = process.stderr.read()
                        if isinstance(error_msg, bytes):
                            error_msg = error_msg.decode(errors='replace')
                        self.logger.error(f"FFmpeg error: {error_msg}")
                        raise YouTubeError(
                            f"Failed to combine streams. FFmpeg error code: {returncode}",
                            video_id=self.url.split('v=')[1]
                        )
                        
                    # Update progress to 100% when done
                    if self.progress_callback:
                        self.progress_callback(
                            progress=100,
                            speed="",
                            text="Muxing complete",
                            total_size=100,
                            downloaded_size=100,
                            stats=None,
                            state=DownloadState.COMPLETED,
                            component="muxing"
                        )
                    
                    # Verify the combined file exists and has size
                    if not os.path.exists(temp_combined):
                        self.logger.error("Combined file was not created by FFmpeg")
                        raise YouTubeError(
                            "Failed to create combined video file - file not found",
                            video_id=self.url.split('v=')[1]
                        )
                    
                    combined_size = os.path.getsize(temp_combined)
                    if combined_size == 0:
                        self.logger.error("Combined file was created but has zero size")
                        raise YouTubeError(
                            "Failed to create combined video file - file is empty",
                            video_id=self.url.split('v=')[1]
                        )
                        
                    self.logger.info(f"Successfully muxed video and audio. Combined file size: {combined_size} bytes")
                        
                    # Move combined file to final destination
                    if os.path.exists(output_path):
                        self.logger.debug(f"Removing existing file at {output_path}")
                        os.remove(output_path)
                    shutil.move(temp_combined, output_path)
                    self.logger.info(f"Successfully moved combined file to: {output_path}")
                    
                    # Clean up temporary files
                    try:
                        if os.path.exists(actual_video_path):
                            os.remove(actual_video_path)
                            self.logger.debug(f"Cleaned up temporary video file: {actual_video_path}")
                        if os.path.exists(actual_audio_path):
                            os.remove(actual_audio_path)
                            self.logger.debug(f"Cleaned up temporary audio file: {actual_audio_path}")
                    except Exception as e:
                        self.logger.warning(f"Error cleaning up temporary files: {str(e)}")
                    
                elif actual_video_path and os.path.exists(actual_video_path):
                    self.logger.info("Video-only download - moving video file to final destination")
                    # Just move video file to output path
                    if os.path.exists(output_path):
                        self.logger.debug(f"Removing existing file at {output_path}")
                        os.remove(output_path)
                    shutil.move(actual_video_path, output_path)
                    self.logger.info(f"Successfully moved video file to: {output_path}")
                else:
                    error_msg = "No valid video or audio files found after download"
                    self.logger.error(error_msg)
                    raise YouTubeError(
                        error_msg,
                        video_id=self.url.split('v=')[1]
                    )
                
        except Exception as e:
            self.logger.error(f"Error in download_video: {e}")
            if isinstance(e, YouTubeError):
                raise
            raise YouTubeError(str(e), video_id=self.url.split('v=')[1])

    def _download_stream(self, url: str, format_id: str, target_path: str, is_audio: bool = False) -> None:
        """
        Download a single stream (video or audio).
        
        Args:
            url: YouTube URL
            format_id: Format ID
            target_path: Path to save the stream
            is_audio: Whether this is an audio stream
        """
        try:
            self.logger.info(f"Starting download of {'audio' if is_audio else 'video'} stream to {target_path}")
            
            # Create progress hook
            def progress_hook(d):
                try:
                    if d['status'] not in ['downloading', 'finished']:
                        self.logger.debug(f"Progress hook status: {d['status']}")
                        return

                    # Get downloaded bytes and total bytes
                    downloaded = d.get('downloaded_bytes', 0)
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    
                    # Get download speed
                    speed = d.get('speed', 0)
                    if speed is None:
                        speed = 0
                    
                    # Calculate progress percentage
                    progress = (downloaded / total * 100) if total > 0 else 0
                    
                    # Format speed string
                    speed_str = f"{format_size(speed)}/s" if speed > 0 else ""
                    
                    # Call progress callback with component-specific progress
                    if self.progress_callback:
                        state = DownloadState.COMPLETED if d['status'] == 'finished' else DownloadState.DOWNLOADING
                        
                        self.logger.info(
                            f"Progress update for {'audio' if is_audio else 'video'}: "
                            f"{progress:.1f}% at {speed_str}"
                        )
                        
                        # For audio-only downloads, don't specify component
                        if self.audio_only:
                            self.progress_callback(
                                progress=progress,
                                speed=speed_str,
                                text=f"Downloading {self.video_title}",
                                total_size=total,
                                downloaded_size=downloaded,
                                stats=None,
                                state=state
                            )
                        else:
                            # For video downloads, specify component
                            self.progress_callback(
                                progress=progress,
                                speed=speed_str,
                                text=f"Downloading {self.video_title}",
                                total_size=total,
                                downloaded_size=downloaded,
                                stats=None,
                                state=state,
                                component="audio" if is_audio else "video"
                            )
                except Exception as e:
                    self.logger.error(f"Error in progress hook: {e}")

            # Download options
            ydl_opts = {
                'format': format_id,
                'outtmpl': target_path,
                'quiet': False,
                'progress_hooks': [progress_hook],
                'retries': 10,
                'fragment_retries': 10,
                'retry_sleep': lambda attempt: 2 ** (attempt - 1),
                'socket_timeout': 30,
                'http_chunk_size': 10 * 1024 * 1024,  # 10MB chunks
                'noprogress': False,
                'no_warnings': False,
                'verbose': True,
                'ignoreerrors': False,
                'nocheckcertificate': True,
                'geo_bypass': True,
                'geo_bypass_country': 'US',
                'cookiesfrombrowser': ('firefox',),
                'extractor_retries': 3,
                'file_access_retries': 3,
                'hls_prefer_native': True,
                'hls_use_mpegts': True,
                'external_downloader_args': ['--max-retries', '10']
            }

            # Download stream
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
        except Exception as e:
            self.logger.error(f"Error downloading stream: {e}")
            raise

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
