import signal
import sys
from gui.app import DownloaderApp
import logging

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\nReceived Ctrl+C. Shutting down gracefully...")
    if 'app' in locals():
        app.shutdown()
    sys.exit(0)

def main():
    # Set up signal handler for Ctrl+C
    signal.signal(signal.SIGINT, signal_handler)
    
    # Initialize logging
    logging.basicConfig(level=logging.INFO)
    
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
