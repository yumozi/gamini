"""macOS input backend using pyobjc-framework-Quartz (CGEventPost)."""

from __future__ import annotations

import asyncio
import functools
import logging
import time

from backend.input_controller import InputBackend
from backend.models import ActionType, GameAction, MouseButton

logger = logging.getLogger(__name__)

# macOS virtual keycode mapping (subset of common keys)
_KEYCODE_MAP: dict[str, int] = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C,
    "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11, "1": 0x12,
    "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17, "9": 0x19,
    "7": 0x1A, "8": 0x1C, "0": 0x1D, "o": 0x1F, "u": 0x20, "i": 0x22,
    "p": 0x23, "l": 0x25, "j": 0x26, "k": 0x28, "n": 0x2D, "m": 0x2E,
    "space": 0x31, "enter": 0x24, "return": 0x24, "tab": 0x30,
    "escape": 0x35, "esc": 0x35, "backspace": 0x33, "delete": 0x75,
    "shift": 0x38, "ctrl": 0x3B, "control": 0x3B, "alt": 0x3A,
    "option": 0x3A, "cmd": 0x37, "command": 0x37,
    "up": 0x7E, "down": 0x7D, "left": 0x7B, "right": 0x7C,
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60,
    "f6": 0x61, "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D,
    "f11": 0x67, "f12": 0x6F,
}


def _get_keycode(key_name: str) -> int:
    key_lower = key_name.lower()
    if key_lower in _KEYCODE_MAP:
        return _KEYCODE_MAP[key_lower]
    raise ValueError(f"Unknown key: {key_name}")


def _mouse_button_id(button: MouseButton) -> int:
    """Map button enum to CGMouseButton constant."""
    match button:
        case MouseButton.LEFT:
            return 0  # kCGMouseButtonLeft
        case MouseButton.RIGHT:
            return 1  # kCGMouseButtonRight
        case MouseButton.MIDDLE:
            return 2  # kCGMouseButtonCenter


class MacOSInputBackend(InputBackend):
    """macOS input via Quartz CGEventPost."""

    def __init__(self) -> None:
        # Import here so it only fails on non-macOS
        from Quartz import (
            CGEventCreateKeyboardEvent,
            CGEventCreateMouseEvent,
            CGEventPost,
            CGEventSetIntegerValueField,
            kCGEventLeftMouseDown,
            kCGEventLeftMouseUp,
            kCGEventMouseMoved,
            kCGEventRightMouseDown,
            kCGEventRightMouseUp,
            kCGHIDEventTap,
            kCGMouseEventClickState,
        )
        self._CGEventCreateKeyboardEvent = CGEventCreateKeyboardEvent
        self._CGEventCreateMouseEvent = CGEventCreateMouseEvent
        self._CGEventPost = CGEventPost
        self._CGEventSetIntegerValueField = CGEventSetIntegerValueField
        self._kCGHIDEventTap = kCGHIDEventTap
        self._kCGEventMouseMoved = kCGEventMouseMoved
        self._kCGEventLeftMouseDown = kCGEventLeftMouseDown
        self._kCGEventLeftMouseUp = kCGEventLeftMouseUp
        self._kCGEventRightMouseDown = kCGEventRightMouseDown
        self._kCGEventRightMouseUp = kCGEventRightMouseUp
        self._kCGMouseEventClickState = kCGMouseEventClickState

        self._mouse_pos = (0, 0)

    async def execute_action(self, action: GameAction) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, functools.partial(self._execute_sync, action))

    def _post_key_event(self, keycode: int, key_down: bool) -> None:
        event = self._CGEventCreateKeyboardEvent(None, keycode, key_down)
        self._CGEventPost(self._kCGHIDEventTap, event)

    def _post_mouse_event(self, event_type: int, point: tuple[float, float], button: int = 0) -> None:
        from Quartz import CGPoint
        pt = CGPoint(point[0], point[1])
        event = self._CGEventCreateMouseEvent(None, event_type, pt, button)
        self._CGEventPost(self._kCGHIDEventTap, event)

    def _execute_sync(self, action: GameAction) -> None:
        match action.action:
            case ActionType.KEY_PRESS:
                if not action.key:
                    return
                keycode = _get_keycode(action.key)
                duration = action.duration or 0.05
                self._post_key_event(keycode, True)
                if duration > 0:
                    time.sleep(duration)
                self._post_key_event(keycode, False)

            case ActionType.KEY_DOWN:
                if action.key:
                    self._post_key_event(_get_keycode(action.key), True)

            case ActionType.KEY_UP:
                if action.key:
                    self._post_key_event(_get_keycode(action.key), False)

            case ActionType.MOUSE_MOVE:
                if action.dx is not None or action.dy is not None:
                    x = self._mouse_pos[0] + (action.dx or 0)
                    y = self._mouse_pos[1] + (action.dy or 0)
                elif action.x is not None and action.y is not None:
                    x, y = action.x, action.y
                else:
                    return
                self._mouse_pos = (x, y)
                self._post_mouse_event(self._kCGEventMouseMoved, (x, y))

            case ActionType.MOUSE_CLICK:
                button = action.button or MouseButton.LEFT
                bid = _mouse_button_id(button)
                x = action.x if action.x is not None else self._mouse_pos[0]
                y = action.y if action.y is not None else self._mouse_pos[1]
                self._mouse_pos = (x, y)

                if button == MouseButton.LEFT:
                    down_type = self._kCGEventLeftMouseDown
                    up_type = self._kCGEventLeftMouseUp
                else:
                    down_type = self._kCGEventRightMouseDown
                    up_type = self._kCGEventRightMouseUp

                self._post_mouse_event(down_type, (x, y), bid)
                time.sleep(0.02)
                self._post_mouse_event(up_type, (x, y), bid)

            case ActionType.MOUSE_DOWN:
                button = action.button or MouseButton.LEFT
                bid = _mouse_button_id(button)
                point = self._mouse_pos
                if button == MouseButton.LEFT:
                    self._post_mouse_event(self._kCGEventLeftMouseDown, point, bid)
                else:
                    self._post_mouse_event(self._kCGEventRightMouseDown, point, bid)

            case ActionType.MOUSE_UP:
                button = action.button or MouseButton.LEFT
                bid = _mouse_button_id(button)
                point = self._mouse_pos
                if button == MouseButton.LEFT:
                    self._post_mouse_event(self._kCGEventLeftMouseUp, point, bid)
                else:
                    self._post_mouse_event(self._kCGEventRightMouseUp, point, bid)

            case ActionType.WAIT:
                if action.duration:
                    time.sleep(action.duration)
