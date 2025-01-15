# JustDownloadIt

A powerful and modular download manager that supports both YouTube videos and regular file downloads.

## Features

- Unified handling of YouTube and regular downloads
- Batch download support with consistent naming
- Progress tracking with customized progress bars
- Modular design for easy extension
- Smart download management with resume capability
- Automatic format selection for YouTube downloads
- Thread-safe operations with proper concurrency management
- Comprehensive error handling and recovery
- Configurable download settings and preferences

## Project Structure

```
JustDownloadIt/
├── core/                   # Core download functionality
│   ├── config.py          # Configuration management
│   ├── download_manager.py # Download coordination
│   ├── download_state.py  # Download state tracking
│   ├── download_task.py   # Download task definition
│   ├── regular_downloader.py # Regular file downloads
│   └── youtube_downloader.py # YouTube video downloads
├── gui/                   # GUI components
│   ├── app.py            # Main application window
│   ├── download_frame.py # Download progress display
│   └── widgets/          # Custom GUI widgets
├── utils/                 # Utility modules
│   ├── concurrency.py    # Thread management
│   ├── config_manager.py # Config management
│   ├── download_utils.py # Download helpers
│   ├── errors.py        # Error handling
│   ├── file_utils.py    # File operations
│   ├── format_utils.py  # Format conversion
│   ├── gui_utils.py     # GUI helpers
│   ├── logger.py        # Logging system
│   ├── progress.py      # Progress tracking
│   ├── state_manager.py # State management
│   ├── theme_utils.py   # Theme management
│   └── url_utils.py     # URL processing
└── main.py              # Application entry point
```

## Module Overview

### Core Components

#### Download Management (`core/`)
- **download_manager.py**: Coordinates download operations, manages queues, and handles lifecycle
- **youtube_downloader.py**: YouTube-specific download implementation using yt-dlp
- **regular_downloader.py**: Generic file download implementation with resume support
- **download_state.py**: Download state definitions and transitions
- **download_task.py**: Download task representation and tracking
- **config.py**: Core configuration management

#### GUI Components (`gui/`)
- **app.py**: Main application window with download management interface
- **download_frame.py**: Download progress display and control panel
- **widgets/**: Custom GUI widgets for enhanced user experience

#### Utilities (`utils/`)

**Concurrency Management**
- **concurrency.py**: Thread-safe data structures and synchronization primitives
  - ThreadSafeDict: Thread-safe dictionary implementation
  - ThreadPool: Worker thread pool management
  - ResourceLock: Reentrant resource locking
  - StateManager: Thread-safe state tracking

**File Operations**
- **file_utils.py**: File system operations
  - Secure file operations with proper permissions
  - Atomic file operations
  - Path sanitization and validation
  - Temporary file management
  - File integrity verification

**Error Handling**
- **errors.py**: Comprehensive error handling system
  - Hierarchical exception system
  - Contextual error information
  - Standardized error reporting
  - Error recovery suggestions

**URL Processing**
- **url_utils.py**: URL validation and processing
  - URL cleaning and normalization
  - YouTube URL detection and parsing
  - Playlist extraction
  - URL validation

**Configuration**
- **config_manager.py**: Application configuration management
  - Thread-safe configuration access
  - Configuration persistence
  - Default settings management

**Progress Tracking**
- **progress.py**: Download progress monitoring
  - Progress calculation
  - Speed estimation
  - ETA calculation

**Additional Utilities**
- **format_utils.py**: Format conversion utilities
- **gui_utils.py**: GUI helper functions
- **logger.py**: Logging system configuration
- **theme_utils.py**: Theme management
- **state_manager.py**: Application state tracking

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
from core.download_manager import DownloadManager

# Initialize download manager
manager = DownloadManager()

# Add downloads
urls = [
    "https://www.youtube.com/watch?v=example",
    "https://example.com/file.zip"
]
download_ids = manager.add_downloads(urls)

# Track progress
def progress_callback(download_id, state):
    print(f"Download {download_id}: {state.progress:.1f}% at {state.speed}")

manager.set_progress_callback(progress_callback)
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
