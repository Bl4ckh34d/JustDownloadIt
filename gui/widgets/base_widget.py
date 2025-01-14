"""Base widget class for custom widgets."""

import customtkinter as ctk
from typing import Optional, Callable, Any, Dict

class BaseWidget(ctk.CTkFrame):
    """Base class for custom widgets.
    
    This class provides common functionality for all custom widgets:
    - Event handling
    - State management
    - Styling
    - Logging
    
    Attributes:
        _events (Dict[str, list]): Event handlers for each event type
        _state (Dict[str, Any]): Widget state
    """
    
    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._events = {}
        self._state = {}
        
    def on(self, event: str, handler: Callable) -> None:
        """Add an event handler.
        
        Args:
            event (str): Event type to handle
            handler (callable): Function to call when event occurs
        """
        if event not in self._events:
            self._events[event] = []
        self._events[event].append(handler)
        
    def off(self, event: str, handler: Optional[Callable] = None) -> None:
        """Remove an event handler.
        
        Args:
            event (str): Event type to remove handler from
            handler (callable, optional): Handler to remove. If None, removes all handlers
        """
        if event in self._events:
            if handler is None:
                self._events[event] = []
            else:
                self._events[event] = [h for h in self._events[event] if h != handler]
                
    def trigger(self, event: str, *args, **kwargs) -> None:
        """Trigger an event.
        
        Args:
            event (str): Event type to trigger
            *args: Positional arguments to pass to handlers
            **kwargs: Keyword arguments to pass to handlers
        """
        if event in self._events:
            for handler in self._events[event]:
                handler(*args, **kwargs)
                
    def set_state(self, **kwargs) -> None:
        """Update widget state.
        
        Args:
            **kwargs: State values to update
        """
        self._state.update(kwargs)
        self.trigger('state_change', self._state)
        
    def get_state(self, key: str, default: Any = None) -> Any:
        """Get state value.
        
        Args:
            key (str): State key to get
            default: Default value if key not found
            
        Returns:
            Value for key or default
        """
        return self._state.get(key, default)
        
    def clear_state(self) -> None:
        """Clear all state."""
        self._state.clear()
        self.trigger('state_change', self._state)
