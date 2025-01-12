"""YouTube video downloader implementation"""

import os
import threading
import subprocess
import logging
import time
import uuid
from pathlib import Path
from typing import Optional, Callable
from dataclasses import dataclass

try:
    import yt_dlp
except ImportError:
    yt_dlp = None

try:
    import browser_cookie3 as browsercookie
except ImportError:
    browsercookie = None

from .downloader import Downloader
from ..config import Config
from ...utils.errors import YouTubeError, InvalidURLError, DownloaderError
from ...utils.logger import DownloaderLogger

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
        
    def _get_best_format(self, formats: list, target_height: int = None, target_abr: int = None) -> dict:
        """Get best matching format based on height or audio bitrate"""
        if not formats:
            raise YouTubeError("No formats available")
            
        # Log available formats for debugging
        DownloaderLogger.get_logger().debug("Available formats:")
        for f in formats:
            DownloaderLogger.get_logger().debug(f"Format {f.get('format_id')}: height={f.get('height')}, abr={f.get('abr')}, "
                          f"vcodec={f.get('vcodec')}, acodec={f.get('acodec')}")
                          
        if target_height:  # Video format
            # Filter for video-only streams
            video_formats = [f for f in formats if 
                f.get('vcodec') != 'none' and 
                f.get('acodec') == 'none' and  # Video only
                f.get('height') is not None]
            
            if not video_formats:
                raise YouTubeError("No suitable video formats found")
                
            # Sort by height and choose closest match
            video_formats.sort(key=lambda x: abs(x.get('height', 0) - target_height))
            chosen = video_formats[0]
            
            DownloaderLogger.get_logger().info(f"Selected video format: {chosen.get('format_id')} "
                         f"(height: {chosen.get('height')}p, vcodec: {chosen.get('vcodec')})")
            return chosen
            
        elif target_abr:  # Audio format
            # Filter for audio-only streams
            audio_formats = [f for f in formats if 
                f.get('acodec') != 'none' and 
                f.get('vcodec') == 'none' and  # Audio only
                f.get('abr') is not None]
            
            if not audio_formats:
                raise YouTubeError("No suitable audio formats found")
                
            # Sort by bitrate and choose closest match
            audio_formats.sort(key=lambda x: abs(x.get('abr', 0) - target_abr))
            chosen = audio_formats[0]
            
            DownloaderLogger.get_logger().info(f"Selected audio format: {chosen.get('format_id')} "
                         f"(bitrate: {chosen.get('abr')}k, acodec: {chosen.get('acodec')})")
            return chosen
            
        raise YouTubeError("Must specify either target_height or target_abr")
        
    def _merge_files(self, video_path: str, audio_path: str, output_path: str) -> None:
        """Merge video and audio files using ffmpeg
        
        Args:
            video_path: Path to video file
            audio_path: Path to audio file
            output_path: Path to output file
        """
        try:
            # Use ffmpeg to merge files
            command = [
                'ffmpeg',
                '-i', video_path,
                '-i', audio_path,
                '-c:v', 'copy',
                '-c:a', 'aac',
                output_path,
                '-y'
            ]
            
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise YouTubeError(f"FFmpeg error: {stderr.decode()}")
                
        except subprocess.CalledProcessError as e:
            raise YouTubeError(f"Failed to merge video and audio: {str(e)}")
            
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
            video_id = f"{url}_video"
            audio_id = f"{url}_audio"
            
            # Initialize progress for both streams
            if self.progress_callback:
                self.progress_callback(
                    download_id=video_id,
                    progress=0.0,
                    speed="0 KB/s",
                    text="Getting video info...",
                    total_size=0,
                    downloaded_size=0
                )
                self.progress_callback(
                    download_id=audio_id,
                    progress=0.0,
                    speed="0 KB/s",
                    text="Getting video info...",
                    total_size=0,
                    downloaded_size=0
                )
                
            # Get cookies
            cookies = get_youtube_cookies()
            
            # Extract video info
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': 'bestvideo+bestaudio/best',  # Request separate streams
                'format_sort': ['res:1080', 'ext:mp4:m4a'],
                'merge_output_format': 'mp4'
            }
            
            # Only add cookies if successfully loaded
            if cookies:
                ydl_opts['cookiefile'] = None  # Don't use cookie file
                ydl_opts['cookiesfrombrowser'] = ('firefox',)  # Try Firefox first
            
            try:
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
            except Exception as e:
                if cookies:
                    # If Firefox cookies failed, try Chrome
                    ydl_opts['cookiesfrombrowser'] = ('chrome',)
                    try:
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                    except Exception as e2:
                        # If both failed, try without cookies
                        self.logger.warning(f"Failed with both Firefox and Chrome cookies, trying without cookies: {e2}")
                        ydl_opts.pop('cookiesfrombrowser', None)
                        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                            info = ydl.extract_info(url, download=False)
                else:
                    # No cookies available, try without
                    ydl_opts.pop('cookiesfrombrowser', None)
                    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                        info = ydl.extract_info(url, download=False)

            # Get video title
            video_title = info.get('title', 'Unknown Title')
            
            # Update progress bars with video title
            if self.progress_callback:
                self.progress_callback(
                    download_id=video_id,
                    progress=0.0,
                    speed="0 KB/s",
                    text=f"{video_title} (Video)",
                    total_size=0,
                    downloaded_size=0
                )
                self.progress_callback(
                    download_id=audio_id,
                    progress=0.0,
                    speed="0 KB/s",
                    text=f"{video_title} (Audio)",
                    total_size=0,
                    downloaded_size=0
                )
            
            # Parse quality preferences
            target_height = int(self.video_quality.replace('p', ''))
            target_abr = int(self.audio_quality.replace('k', ''))
            
            # Get available formats
            formats = info.get('formats', [])
            
            # Find best video and audio formats matching preferences
            video_format = None
            audio_format = None
            
            # Find best video format (closest to target height)
            video_formats = [f for f in formats if f.get('vcodec') != 'none' and f.get('acodec') == 'none']
            if video_formats:
                video_formats.sort(key=lambda f: abs(f.get('height', 0) - target_height))
                video_format = video_formats[0]
            
            # Find best audio format (closest to target bitrate)
            audio_formats = [f for f in formats if f.get('vcodec') == 'none' and f.get('acodec') != 'none']
            if audio_formats:
                audio_formats.sort(key=lambda f: abs(f.get('abr', 0) - target_abr))
                audio_format = audio_formats[0]
            
            if not video_format or not audio_format:
                raise YouTubeError("Could not find suitable video and audio formats")
            
            # Create unique temporary filenames
            video_path = os.path.join(destination, f"video_temp_{uuid.uuid4()}.mp4")
            audio_path = os.path.join(destination, f"audio_temp_{uuid.uuid4()}.m4a")
            output_path = os.path.join(destination, f"{info['title']}_{info['id']}.mp4")
            
            # Download video and audio in parallel
            video_thread = threading.Thread(
                target=self._download_format,
                args=(url, video_format, video_path, video_id)
            )
            audio_thread = threading.Thread(
                target=self._download_format,
                args=(url, audio_format, audio_path, audio_id)
            )
            
            video_thread.start()
            audio_thread.start()
            
            # Wait for both downloads to complete
            video_thread.join()
            audio_thread.join()
            
            if self._stop_flag:
                # Clean up temp files if cancelled
                for path in [video_path, audio_path]:
                    if os.path.exists(path):
                        os.remove(path)
                return
            
            # Remove progress bars for video and audio
            if self.progress_callback:
                self.progress_callback(
                    download_id=video_id,
                    progress=100.0,
                    speed="",
                    text="Video download complete",
                    total_size=0,
                    downloaded_size=0,
                    remove=True  # Signal to remove this progress bar
                )
                self.progress_callback(
                    download_id=audio_id,
                    progress=100.0,
                    speed="",
                    text="Audio download complete",
                    total_size=0,
                    downloaded_size=0,
                    remove=True  # Signal to remove this progress bar
                )
                
                # Create progress bar for merging
                merge_id = f"{url}_merge"
                self.progress_callback(
                    download_id=merge_id,
                    progress=0.0,
                    speed="",
                    text="Merging video and audio...",
                    total_size=0,
                    downloaded_size=0
                )
            
            # Use ffmpeg to merge video and audio
            cmd = [
                'ffmpeg', '-y',
                '-i', video_path,
                '-i', audio_path,
                '-c', 'copy',
                output_path
            ]
            
            subprocess.run(cmd, check=True, capture_output=True)
            
            # Clean up temp files
            os.remove(video_path)
            os.remove(audio_path)
            
            # Complete and remove merge progress bar
            if self.progress_callback:
                self.progress_callback(
                    download_id=merge_id,
                    progress=100.0,
                    speed="",
                    text="Download complete!",
                    total_size=0,
                    downloaded_size=0,
                    remove=True  # Signal to remove this progress bar
                )
                
        except Exception as e:
            self.logger.error(f"YouTube download failed: {e}", exc_info=True)
            # Clean up any temp files
            for path in [video_path, audio_path]:
                if os.path.exists(path):
                    os.remove(path)
            # Remove progress bars on error
            if self.progress_callback:
                for stream_id in [video_id, audio_id]:
                    self.progress_callback(
                        download_id=stream_id,
                        progress=0.0,
                        speed="",
                        text=f"Download failed: {str(e)}",
                        total_size=0,
                        downloaded_size=0,
                        remove=True  # Signal to remove these progress bars
                    )
            raise YouTubeError(f"Download failed: {str(e)}")

    def _download_format(self, url: str, format_info: dict, output_path: str, download_id: str):
        """Download a specific format"""
        try:
            ydl_opts = {
                'quiet': True,
                'no_warnings': True,
                'format': format_info['format_id'],
                'outtmpl': output_path,
                'progress_hooks': [
                    lambda d: self._format_progress_hook(d, download_id)
                ]
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
                
        except Exception as e:
            self.logger.error(f"Failed to download {download_id}: {e}")
            raise

    def _format_progress_hook(self, d: dict, download_id: str):
        """Progress hook for format download"""
        if d['status'] == 'downloading' and self.progress_callback:
            total = d.get('total_bytes', 0) or d.get('total_bytes_estimate', 0)
            downloaded = d.get('downloaded_bytes', 0)
            speed = d.get('speed', 0)
            
            if total and speed:
                progress = (downloaded / total) * 100
                speed_str = f"{speed/1024/1024:.2f} MB/s" if speed and progress < 100 else ""  # Hide speed if complete
                
                # Keep the same title, just update progress
                stream_type = "(Video)" if "_video" in download_id else "(Audio)"
                current_title = d.get('info_dict', {}).get('title', 'Unknown Title')
                
                # Update progress for this specific stream
                self.progress_callback(
                    download_id=download_id,
                    progress=progress,
                    speed=speed_str,
                    text=f"{current_title} {stream_type}",  # No need to truncate, progress bar will handle it
                    total_size=total,
                    downloaded_size=downloaded
                )
                
    def cancel(self):
        """Cancel the download"""
        with self._lock:
            self._stop_flag = True
