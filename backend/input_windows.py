"""Windows input backend using pydirectinput-rgx (DirectInput scan codes)."""

from __future__ import annotations

import asyncio
import functools
import logging

import pydirectinput

from backend.input_controller import InputBackend
from backend.models import ActionType, GameAction, MouseButton

logger = logging.getLogger(__name__)

# Disable pydirectinput's default pause between actions (we handle our own)
pydirectinput.PAUSE = 0.0


class WindowsInputBackend(InputBackend):
    """Windows input via pydirectinput-rgx."""

    async def execute_action(self, action: GameAction) -> None:
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, functools.partial(self._execute_sync, action))

    def _execute_sync(self, action: GameAction) -> None:
        match action.action:
            case ActionType.KEY_PRESS:
                if not action.key:
                    return
                duration = action.duration or 0.05
                pydirectinput.keyDown(action.key)
                if duration > 0:
                    import time
                    time.sleep(duration)
                pydirectinput.keyUp(action.key)

            case ActionType.KEY_DOWN:
                if action.key:
                    pydirectinput.keyDown(action.key)

            case ActionType.KEY_UP:
                if action.key:
                    pydirectinput.keyUp(action.key)

            case ActionType.MOUSE_MOVE:
                if action.dx is not None or action.dy is not None:
                    pydirectinput.moveRel(
                        action.dx or 0,
                        action.dy or 0,
                        relative=True,
                    )
                elif action.x is not None and action.y is not None:
                    pydirectinput.moveTo(action.x, action.y)

            case ActionType.MOUSE_CLICK:
                button = (action.button or MouseButton.LEFT).value
                kwargs: dict = {"button": button}
                if action.x is not None and action.y is not None:
                    kwargs["x"] = action.x
                    kwargs["y"] = action.y
                pydirectinput.click(**kwargs)

            case ActionType.MOUSE_DOWN:
                button = (action.button or MouseButton.LEFT).value
                pydirectinput.mouseDown(button=button)

            case ActionType.MOUSE_UP:
                button = (action.button or MouseButton.LEFT).value
                pydirectinput.mouseUp(button=button)

            case ActionType.WAIT:
                if action.duration:
                    import time
                    time.sleep(action.duration)
