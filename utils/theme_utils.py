"""
Theme and styling utilities for GUI components.

This module provides consistent theming and styling across
the application's interface.
"""

import customtkinter as ctk
from typing import Dict, Any
from dataclasses import dataclass
from enum import Enum

class ColorScheme:
    """Color scheme constants."""
    PRIMARY = "#1f538d"      # Blue
    SECONDARY = "#2d9d3f"    # Green
    ERROR = "#e74c3c"        # Red
    WARNING = "#f39c12"      # Orange
    SUCCESS = "#27ae60"      # Green
    INFO = "#3498db"         # Light Blue
    BACKGROUND = "#2b2b2b"   # Dark Gray
    FOREGROUND = "#ffffff"   # White
    DISABLED = "#7f8c8d"     # Gray

@dataclass
class ThemeSettings:
    """Theme settings for widgets."""
    font_family: str = "Helvetica"
    title_size: int = 12
    text_size: int = 11
    small_text_size: int = 10
    corner_radius: int = 6
    button_height: int = 28
    progress_height: int = 6
    widget_padding: int = 5
    frame_padding: int = 10

class Theme:
    """Theme manager for consistent styling."""
    
    def __init__(self):
        self.colors = ColorScheme
        self.settings = ThemeSettings()
    
    def configure_window(self, window: ctk.CTk) -> None:
        """Configure main window appearance.
        
        Args:
            window: Window to configure
        """
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")
        
        window.configure(fg_color=self.colors.BACKGROUND)
    
    def get_button_style(self, button_type: str = "default") -> Dict[str, Any]:
        """Get button style configuration.
        
        Args:
            button_type: Type of button (default, primary, danger)
            
        Returns:
            Dict[str, Any]: Button style configuration
        """
        base_style = {
            "font": (self.settings.font_family, self.settings.text_size),
            "corner_radius": self.settings.corner_radius,
            "height": self.settings.button_height,
        }
        
        styles = {
            "default": {
                "fg_color": self.colors.PRIMARY,
                "hover_color": self.colors.INFO,
            },
            "primary": {
                "fg_color": self.colors.SECONDARY,
                "hover_color": self.colors.SUCCESS,
            },
            "danger": {
                "fg_color": self.colors.ERROR,
                "hover_color": self.colors.WARNING,
            }
        }
        
        return {**base_style, **styles.get(button_type, styles["default"])}
    
    def get_progress_style(self, progress_type: str = "default") -> Dict[str, Any]:
        """Get progress bar style configuration.
        
        Args:
            progress_type: Type of progress bar (default, youtube)
            
        Returns:
            Dict[str, Any]: Progress bar style configuration
        """
        base_style = {
            "height": self.settings.progress_height,
            "corner_radius": self.settings.corner_radius // 2,
            "border_width": 0,
        }
        
        styles = {
            "default": {
                "progress_color": self.colors.PRIMARY,
                "fg_color": self.colors.BACKGROUND,
            },
            "youtube": {
                "progress_color": self.colors.SECONDARY,
                "fg_color": self.colors.BACKGROUND,
            }
        }
        
        return {**base_style, **styles.get(progress_type, styles["default"])}
    
    def get_label_style(self, label_type: str = "default") -> Dict[str, Any]:
        """Get label style configuration.
        
        Args:
            label_type: Type of label (default, title, small)
            
        Returns:
            Dict[str, Any]: Label style configuration
        """
        styles = {
            "default": {
                "font": (self.settings.font_family, self.settings.text_size),
                "text_color": self.colors.FOREGROUND,
            },
            "title": {
                "font": (self.settings.font_family, self.settings.title_size, "bold"),
                "text_color": self.colors.FOREGROUND,
            },
            "small": {
                "font": (self.settings.font_family, self.settings.small_text_size),
                "text_color": self.colors.FOREGROUND,
            }
        }
        
        return styles.get(label_type, styles["default"])
    
    def get_frame_style(self, frame_type: str = "default") -> Dict[str, Any]:
        """Get frame style configuration.
        
        Args:
            frame_type: Type of frame (default, transparent)
            
        Returns:
            Dict[str, Any]: Frame style configuration
        """
        styles = {
            "default": {
                "fg_color": self.colors.BACKGROUND,
                "corner_radius": self.settings.corner_radius,
            },
            "transparent": {
                "fg_color": "transparent",
                "corner_radius": 0,
            }
        }
        
        return styles.get(frame_type, styles["default"])

# Global theme instance
theme = Theme()
