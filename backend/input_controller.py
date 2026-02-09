"""Abstract input interface and platform factory."""

from __future__ import annotations

import asyncio
import logging
import sys
from abc import ABC, abstractmethod

from backend.models import ActionType, GameAction

logger = logging.getLogger(__name__)

# Max coordinate values for bounds checking
MAX_COORD = 65535
MAX_DURATION = 5.0


VALID_KEYS = {
    # Letters
    *"abcdefghijklmnopqrstuvwxyz",
    # Numbers
    *"0123456789",
    # Function keys
    *[f"f{i}" for i in range(1, 13)],
    # Modifiers
    "shift", "ctrl", "control", "alt", "option", "cmd", "command",
    # Navigation
    "up", "down", "left", "right",
    "space", "enter", "return", "tab", "escape", "esc",
    "backspace", "delete",
    # Misc
    "insert", "home", "end", "pageup", "pagedown",
    "capslock", "numlock", "scrolllock", "printscreen",
    # Punctuation
    "minus", "equals", "comma", "period", "slash",
    "semicolon", "quote", "backslash", "backquote",
    "bracketleft", "bracketright",
}


def _validate_action(action: GameAction) -> GameAction:
    """Bounds-check and sanitize an action."""
    if action.x is not None:
        action.x = max(0, min(action.x, MAX_COORD))
    if action.y is not None:
        action.y = max(0, min(action.y, MAX_COORD))
    if action.duration is not None:
        action.duration = max(0, min(action.duration, MAX_DURATION))
    if action.key is not None:
        action.key = action.key.lower().strip()
        if action.key not in VALID_KEYS:
            logger.warning(f"Unknown key name '{action.key}', skipping")
            action.key = None
    return action


class InputBackend(ABC):
    """Abstract base for platform-specific input."""

    @abstractmethod
    async def execute_action(self, action: GameAction) -> None:
        """Execute a single input action."""

    async def execute_actions(self, actions: list[GameAction], delay: float = 0.02) -> None:
        """Execute a list of actions with delay between them."""
        for action in actions:
            action = _validate_action(action)
            try:
                await self.execute_action(action)
            except Exception as e:
                logger.error(f"Failed to execute {action.action}: {e}")
            if delay > 0:
                await asyncio.sleep(delay)


def create_input_backend() -> InputBackend:
    """Create platform-appropriate input backend."""
    if sys.platform == "win32":
        from backend.input_windows import WindowsInputBackend
        return WindowsInputBackend()
    elif sys.platform == "darwin":
        from backend.input_macos import MacOSInputBackend
        return MacOSInputBackend()
    else:
        raise RuntimeError(f"Unsupported platform: {sys.platform}")
