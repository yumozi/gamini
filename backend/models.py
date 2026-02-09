"""Pydantic models shared across all layers."""

from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    KEY_PRESS = "key_press"
    KEY_DOWN = "key_down"
    KEY_UP = "key_up"
    MOUSE_MOVE = "mouse_move"
    MOUSE_CLICK = "mouse_click"
    MOUSE_DOWN = "mouse_down"
    MOUSE_UP = "mouse_up"
    WAIT = "wait"


class MouseButton(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    MIDDLE = "middle"


class GameAction(BaseModel):
    """A single input action to execute."""

    action: ActionType
    key: Optional[str] = Field(None, description="Key name for key_press/key_down/key_up (e.g. 'w', 'space', 'shift')")
    bbox: Optional[list[int]] = Field(None, description="Bounding box [y_min, x_min, y_max, x_max] in 0-1000 normalized coords for mouse target position")
    x: Optional[int] = Field(None, description="Screen X pixel coord (computed from bbox by code, do not set)")
    y: Optional[int] = Field(None, description="Screen Y pixel coord (computed from bbox by code, do not set)")
    dx: Optional[int] = Field(None, description="Relative X movement for mouse_move")
    dy: Optional[int] = Field(None, description="Relative Y movement for mouse_move")
    button: Optional[MouseButton] = Field(None, description="Mouse button for click actions")
    duration: Optional[float] = Field(None, description="Duration in seconds for key_press or wait", ge=0, le=5.0)


class GameActionResponse(BaseModel):
    """What Gemini returns - passed as response_schema for structured output."""

    reasoning: str = Field(description="Brief description of what the AI sees and why it chose these actions")
    actions: list[GameAction] = Field(default_factory=list, description="List of actions to execute in order")


class LoopState(str, Enum):
    IDLE = "idle"
    RUNNING = "running"
    ERROR = "error"
    STOPPING = "stopping"


class LoopStatus(BaseModel):
    """Status pushed to frontend each iteration."""

    state: LoopState = LoopState.IDLE
    iteration: int = 0
    reasoning: str = ""
    actions: list[GameAction] = Field(default_factory=list)
    fps: float = 0.0
    error: Optional[str] = None
    video_url: Optional[str] = None


class AppConfig(BaseModel):
    """All runtime settings."""

    gemini_api_key: str = ""
    model: str = "gemini-3-flash-preview"
    capture_duration: float = Field(1.5, ge=0.5, le=5.0)
    capture_fps: int = Field(5, ge=1, le=10)
    game_context: str = ""
    target_window: Optional[str] = None  # None = full screen
    temperature: float = Field(1.0, ge=0.0, le=1.0)
    media_resolution: str = Field("low", description="Gemini media resolution: 'low' or 'default'")
    action_delay: float = Field(0.02, ge=0.0, le=1.0, description="Min seconds between actions")
