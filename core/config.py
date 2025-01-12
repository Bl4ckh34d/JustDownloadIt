from pathlib import Path
from typing import Dict, Any, List
import json

class Config:
    # Window settings
    WINDOW_WIDTH = 800  # Update window width to 800px
    WINDOW_MIN_HEIGHT = 400
    WINDOW_PADDING = 5
    
    # Download settings
    DEFAULT_THREADS = 4
    MAX_THREADS = 64
    DEFAULT_RETRY_ATTEMPTS = 3
    DOWNLOAD_CHUNK_SIZE = 8192
    WAIT_BETWEEN_RETRIES = 5  # seconds
    
    # YouTube specific settings
    YOUTUBE_VIDEO_QUALITIES = ['2160p', '1440p', '1080p', '720p', '480p', '360p', '240p', '144p']
    YOUTUBE_AUDIO_QUALITIES = ['160k', '128k', '96k', '70k', '50k', '48k']
    DEFAULT_VIDEO_QUALITY = '720p'
    DEFAULT_AUDIO_QUALITY = '128k'
    
    # Optional proxy settings
    PROXY = None  # Example: 'socks5://127.0.0.1:1080'
    
    # UI settings
    PROGRESS_THICKNESS = 10
    DOWNLOAD_FRAME_HEIGHT = 200
    MAX_FILENAME_LENGTH = 29
    
    # Colors
    YOUTUBE_COLOR = "#FF0000"
    REGULAR_COLOR = "#00FF00"
    ERROR_COLOR = "#FF0000"
    SUCCESS_COLOR = "#00FF00"
    
    # Paths
    BASE_DIR = Path(__file__).parent.parent
    TEMP_DIR = BASE_DIR / "temp"
    DOWNLOAD_DIR = BASE_DIR / "downloads"  # Downloads directory in project root
    
    # File patterns
    YOUTUBE_PATTERNS = [
        "youtube.com",
        "youtu.be",
        "youtube.com/shorts"
    ]
    
    # YouTube settings
    YOUTUBE_VIDEO_FORMATS = [
        "2160p (4K)",  # Format 313/401
        "1440p (2K)",  # Format 271/400
        "1080p (HD)",  # Format 137/248/399
        "720p",        # Format 136/247/398
        "480p",        # Format 135/244/397
        "360p",        # Format 134/243/396
        "240p",        # Format 133/242/395
        "144p"         # Format 160/278/394
    ]
    
    YOUTUBE_AUDIO_FORMATS = [
        "High (opus)",      # Format 251 (opus webm)
        "High (m4a)",       # Format 140 (m4a)
        "Medium (opus)",    # Format 250 (opus webm)
        "Medium (m4a)",     # Format 139 (m4a)
        "Low (opus)",       # Format 249 (opus webm)
        "Low (m4a)"         # Format 599 (m4a)
    ]
    
    YOUTUBE_COMBINED_FORMATS = [
        "Best available",   # Will pick highest resolution available
        "1080p",           # Format 137+251 (best video + best audio)
        "720p",            # Format 136+251
        "480p",            # Format 135+251
        "360p",            # Format 134+251 or Format 18 (already combined)
        "240p",            # Format 133+251
        "144p"             # Format 160+251
    ]
    
    # Format IDs for different quality levels
    YOUTUBE_FORMAT_IDS = {
        # Video formats (video-only)
        "2160p": ["313", "401"],
        "1440p": ["271", "400"],
        "1080p": ["137", "248", "399"],
        "720p": ["136", "247", "398"],
        "480p": ["135", "244", "397"],
        "360p": ["134", "243", "396"],
        "240p": ["133", "242", "395"],
        "144p": ["160", "278", "394"],
        
        # Audio formats
        "high_opus": ["251"],
        "high_m4a": ["140"],
        "medium_opus": ["250"],
        "medium_m4a": ["139"],
        "low_opus": ["249"],
        "low_m4a": ["599"]
    }
    
    # Quality rankings
    QUALITY_RANKS = {
        "high": 3,
        "medium": 2,
        "low": 1,
        "ultralow": 0
    }
    
    @classmethod
    def load_user_config(cls) -> None:
        """Load user configuration from config.json if it exists"""
        config_file = cls.BASE_DIR / "config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    user_config = json.load(f)
                for key, value in user_config.items():
                    if hasattr(cls, key):
                        setattr(cls, key, value)
            except Exception as e:
                print(f"Error loading config: {e}")
                
    @classmethod
    def save_user_config(cls) -> None:
        """Save current configuration to config.json"""
        config_file = cls.BASE_DIR / "config.json"
        try:
            config_dict = {
                key: value for key, value in cls.__dict__.items()
                if not key.startswith('_') and isinstance(value, (int, float, str, bool, list, dict))
            }
            with open(config_file, 'w') as f:
                json.dump(config_dict, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")
            
    @classmethod
    def to_dict(cls) -> Dict[str, Any]:
        """Convert configuration to dictionary"""
        return {
            key: value for key, value in cls.__dict__.items()
            if not key.startswith('_') and isinstance(value, (int, float, str, bool, list, dict))
        }
