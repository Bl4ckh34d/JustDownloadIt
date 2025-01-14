"""
GUI utilities for JustDownloadIt.

This module provides common utility functions used by GUI components.
"""

import tkinter as tk
from typing import Optional, Callable, Any, Dict
import customtkinter as ctk
from pathlib import Path

def create_tooltip(widget: tk.Widget, text: str) -> None:
    """Create a tooltip for a widget.
    
    Args:
        widget: Widget to add tooltip to
        text: Tooltip text
    """
    def show_tooltip(event=None):
        tooltip = tk.Toplevel()
        tooltip.wm_overrideredirect(True)
        tooltip.wm_geometry(f"+{event.x_root+10}+{event.y_root+10}")
        
        label = tk.Label(tooltip, text=text, justify='left',
                        background="#ffffe0", relief='solid', borderwidth=1)
        label.pack()
        
        def hide_tooltip():
            tooltip.destroy()
            
        tooltip.bind('<Leave>', lambda e: hide_tooltip())
        widget.bind('<Leave>', lambda e: hide_tooltip())
        
    widget.bind('<Enter>', show_tooltip)

def create_scrollable_frame(master: Any, **kwargs) -> ctk.CTkScrollableFrame:
    """Create a scrollable frame with consistent styling.
    
    Args:
        master: Parent widget
        **kwargs: Additional arguments for CTkScrollableFrame
        
    Returns:
        CTkScrollableFrame: Configured scrollable frame
    """
    return ctk.CTkScrollableFrame(
        master,
        fg_color="transparent",
        corner_radius=0,
        **kwargs
    )

def create_button(master: Any, text: str, command: Callable, 
                 width: int = 120, **kwargs) -> ctk.CTkButton:
    """Create a button with consistent styling.
    
    Args:
        master: Parent widget
        text: Button text
        command: Button command
        width: Button width
        **kwargs: Additional arguments for CTkButton
        
    Returns:
        CTkButton: Configured button
    """
    return ctk.CTkButton(
        master,
        text=text,
        command=command,
        width=width,
        **kwargs
    )

def create_entry(master: Any, width: int = 300, **kwargs) -> ctk.CTkEntry:
    """Create an entry with consistent styling.
    
    Args:
        master: Parent widget
        width: Entry width
        **kwargs: Additional arguments for CTkEntry
        
    Returns:
        CTkEntry: Configured entry
    """
    return ctk.CTkEntry(
        master,
        width=width,
        **kwargs
    )

def create_label(master: Any, text: str, **kwargs) -> ctk.CTkLabel:
    """Create a label with consistent styling.
    
    Args:
        master: Parent widget
        text: Label text
        **kwargs: Additional arguments for CTkLabel
        
    Returns:
        CTkLabel: Configured label
    """
    return ctk.CTkLabel(
        master,
        text=text,
        **kwargs
    )

def create_checkbox(master: Any, text: str, variable: tk.BooleanVar,
                   command: Optional[Callable] = None, **kwargs) -> ctk.CTkCheckBox:
    """Create a checkbox with consistent styling.
    
    Args:
        master: Parent widget
        text: Checkbox text
        variable: Variable to bind to
        command: Command to execute on toggle
        **kwargs: Additional arguments for CTkCheckBox
        
    Returns:
        CTkCheckBox: Configured checkbox
    """
    return ctk.CTkCheckBox(
        master,
        text=text,
        variable=variable,
        command=command,
        **kwargs
    )

def create_option_menu(master: Any, values: list, variable: tk.StringVar,
                      **kwargs) -> ctk.CTkOptionMenu:
    """Create an option menu with consistent styling.
    
    Args:
        master: Parent widget
        values: List of values
        variable: Variable to bind to
        **kwargs: Additional arguments for CTkOptionMenu
        
    Returns:
        CTkOptionMenu: Configured option menu
    """
    return ctk.CTkOptionMenu(
        master,
        values=values,
        variable=variable,
        **kwargs
    )

def create_slider(master: Any, from_: float, to: float,
                 variable: tk.Variable, command: Optional[Callable] = None,
                 **kwargs) -> ctk.CTkSlider:
    """Create a slider with consistent styling.
    
    Args:
        master: Parent widget
        from_: Minimum value
        to: Maximum value
        variable: Variable to bind to
        command: Command to execute on value change
        **kwargs: Additional arguments for CTkSlider
        
    Returns:
        CTkSlider: Configured slider
    """
    return ctk.CTkSlider(
        master,
        from_=from_,
        to=to,
        variable=variable,
        command=command,
        **kwargs
    )

def show_error(title: str, message: str) -> None:
    """Show an error message box.
    
    Args:
        title: Error title
        message: Error message
    """
    tk.messagebox.showerror(title, message)

def show_warning(title: str, message: str) -> None:
    """Show a warning message box.
    
    Args:
        title: Warning title
        message: Warning message
    """
    tk.messagebox.showwarning(title, message)

def show_info(title: str, message: str) -> None:
    """Show an info message box.
    
    Args:
        title: Info title
        message: Info message
    """
    tk.messagebox.showinfo(title, message)

def ask_directory(title: str = "Select Directory",
                 initialdir: Optional[Path] = None) -> Optional[str]:
    """Show directory selection dialog.
    
    Args:
        title: Dialog title
        initialdir: Initial directory
        
    Returns:
        str: Selected directory path or None if cancelled
    """
    return tk.filedialog.askdirectory(
        title=title,
        initialdir=initialdir
    )
