from enum import Enum, auto

class DownloadState(Enum):
    """Enum representing the state of a download"""
    PENDING = auto()
    DOWNLOADING = auto()
    COMPLETED = auto()
    ERROR = auto()
    CANCELLED = auto()
