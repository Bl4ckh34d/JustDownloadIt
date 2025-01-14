"""
Entry point for JustDownloadIt application.

This module initializes and runs the main application window.
It handles signal interrupts (Ctrl+C) for graceful shutdown.

Features:
    - Application initialization
    - Signal handling
    - Graceful shutdown

Functions:
    signal_handler: Handles Ctrl+C interrupts
    main: Creates and runs the application

Dependencies:
    - gui.app: Main application window
    - signal: Signal handling
"""

import signal
import sys
from gui.app import DownloaderApp

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nReceived Ctrl+C. Shutting down gracefully...")
    if 'app' in locals():
        app.shutdown()
    sys.exit(0)

def main():
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Create and run app
    app = DownloaderApp()
    try:
        app.run()
    except KeyboardInterrupt:
        print("\nReceived Ctrl+C. Shutting down gracefully...")
        app.shutdown()
        sys.exit(0)

if __name__ == '__main__':
    main()
