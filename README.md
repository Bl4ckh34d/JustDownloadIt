# JustDownloadIt

A powerful and modular download manager that supports both YouTube videos and regular file downloads.

## Features

- Unified handling of YouTube and regular downloads
- Batch download support with consistent naming
- Progress tracking with customized progress bars
- Modular design for easy extension
- Smart download management with resume capability
- Automatic format selection for YouTube downloads

## Requirements

- Python 3.8+
- FFmpeg (for YouTube video processing)
- Required Python packages (see requirements.txt)

## Installation

1. Clone this repository
2. Install FFmpeg if not already installed
3. Install Python dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

```python
from pathlib import Path
from downloader import DownloadManager

# Initialize download manager
manager = DownloadManager(destination=Path("downloads"))

# Add downloads
urls = [
    "https://www.youtube.com/watch?v=example",
    "https://example.com/file.zip"
]
download_ids = manager.add_downloads(urls, base_name="batch1")

# Track progress
def progress_callback(download_id, progress, speed, text):
    print(f"{text}: {progress:.1f}% at {speed}")

manager.set_progress_callback(progress_callback)
```

## Architecture

The downloader is built with a modular architecture:

- `BaseDownloader`: Abstract base class defining the download interface
- `YouTubeDownloader`: Handles YouTube video downloads with yt-dlp
- `RegularDownloader`: Handles regular file downloads with pySmartDL
- `DownloadManager`: Coordinates downloads and manages their lifecycle

## License

This project is licensed under the MIT License - see the LICENSE file for details.
