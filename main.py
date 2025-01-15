"""
JustDownloadIt Application Entry Point.

This module serves as the main entry point for the JustDownloadIt application,
handling initialization, runtime management, and graceful shutdown procedures.

Key Responsibilities:
    - Application lifecycle management
    - Signal handling (SIGINT/SIGTERM)
    - Exception handling and logging
    - Resource cleanup on exit
    - GUI initialization
    - Configuration loading

Components:
    - Signal Handlers: Manage system signals for clean shutdown
    - Main Function: Application initialization and runtime
    - Exception Handlers: Global exception management
    - Resource Management: Ensure proper cleanup

Dependencies:
    - gui.app: Main application window
    - signal: System signal handling
    - sys: System-level operations

Usage:
    Run this module directly to start the application:
    $ python main.py
    
    The application can be terminated gracefully using Ctrl+C,
    which will trigger proper cleanup of all resources.
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
