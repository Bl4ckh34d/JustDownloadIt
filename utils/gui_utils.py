"""
GUI utilities for JustDownloadIt.

This module provides common GUI utilities and widgets used across
the application's interface components.
"""

import tkinter as tk
from tkinter import messagebox
import customtkinter as ctk
from typing import Optional, Callable, Dict, Any
from pathlib import Path
import logging

from .progress import format_size, format_speed, format_time
from core.download_state import DownloadState

class WidgetState:
    """Base class for widget state management."""
    
    def __init__(self, **kwargs):
        self._state = {}
        self.set_state(**kwargs)
    
    def set_state(self, **kwargs) -> None:
        """Update widget state."""
        self._state.update(kwargs)
    
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value."""
        return self._state.get(key, default)

def show_error(title: str, message: str) -> None:
    """Show error message box.
    
    Args:
        title: Error title
        message: Error message
    """
    messagebox.showerror(title, message)

def show_warning(title: str, message: str) -> None:
    """Show warning message box.
    
    Args:
        title: Warning title
        message: Warning message
    """
    messagebox.showwarning(title, message)

def show_info(title: str, message: str) -> None:
    """Show info message box.
    
    Args:
        title: Info title
        message: Info message
    """
    messagebox.showinfo(title, message)

def ask_yes_no(title: str, message: str) -> bool:
    """Show yes/no dialog.
    
    Args:
        title: Dialog title
        message: Dialog message
        
    Returns:
        bool: True if user clicked Yes
    """
    return messagebox.askyesno(title, message)

def create_tooltip(widget: tk.Widget, text: str) -> None:
    """Create tooltip for widget.
    
    Args:
        widget: Target widget
        text: Tooltip text
    """
    def show_tooltip(event):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
        label = tk.Label(tooltip, text=text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1)
        label.pack()
        
        def hide_tooltip():
            tooltip.destroy()
        
        widget.tooltip = tooltip
        widget.bind('<Leave>', lambda e: hide_tooltip())
        tooltip.bind('<Leave>', lambda e: hide_tooltip())
    
    widget.bind('<Enter>', show_tooltip)

def format_download_status(state: DownloadState, progress: float = 0,
                         speed: Optional[float] = None,
                         total_size: Optional[int] = None,
                         downloaded_size: Optional[int] = None) -> Dict[str, str]:
    """Format download status for display.
    
    Args:
        state: Download state
        progress: Download progress (0-100)
        speed: Download speed in bytes/sec
        total_size: Total file size in bytes
        downloaded_size: Downloaded size in bytes
        
    Returns:
        Dict[str, str]: Formatted status strings
    """
    status_color = {
        DownloadState.QUEUED: "gray",
        DownloadState.INITIALIZING: "blue",
        DownloadState.DOWNLOADING: "blue",
        DownloadState.PROCESSING: "orange",
        DownloadState.COMPLETED: "green",
        DownloadState.ERROR: "red",
        DownloadState.CANCELLED: "red",
        DownloadState.PAUSED: "orange"
    }
    
    if total_size:
        size_text = f"{format_size(downloaded_size)}/{format_size(total_size)}"
    else:
        size_text = format_size(downloaded_size) if downloaded_size else "0 B"
    
    return {
        "color": status_color.get(state, "gray"),
        "progress_text": f"{progress:.1f}%",
        "speed_text": format_speed(speed) if speed else "0 B/s",
        "size_text": size_text,
        "state_text": state.name.title()
    }

def create_scrolled_frame(master: tk.Widget, **kwargs) -> ctk.CTkScrollableFrame:
    """Create scrollable frame.
    
    Args:
        master: Parent widget
        **kwargs: Additional arguments for CTkScrollableFrame
        
    Returns:
        CTkScrollableFrame: Scrollable frame
    """
    frame = ctk.CTkScrollableFrame(master, **kwargs)
    frame.pack(fill="both", expand=True, padx=5, pady=5)
    return frame

def create_button_with_icon(master: tk.Widget, text: str, command: Callable,
                          icon: Optional[str] = None, **kwargs) -> ctk.CTkButton:
    """Create button with optional icon.
    
    Args:
        master: Parent widget
        text: Button text
        command: Button command
        icon: Icon path (optional)
        **kwargs: Additional arguments for CTkButton
        
    Returns:
        CTkButton: Button widget
    """
    if icon:
        try:
            image = tk.PhotoImage(file=icon)
            kwargs["image"] = image
        except Exception as e:
            logging.warning(f"Failed to load button icon {icon}: {e}")
    
    button = ctk.CTkButton(master, text=text, command=command, **kwargs)
    return button
