"""FastAPI app with REST routes and WebSocket handler."""

from __future__ import annotations

import asyncio
import logging
import sys
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from backend.config import get_config, update_config
from backend.game_loop import GameLoop
from backend.models import LoopState, LoopStatus
from backend.window_manager import list_windows

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Emergency stop hotkey state
_emergency_stop_callbacks: list = []


def _fire_emergency_stop() -> None:
    """Invoke all registered emergency stop callbacks."""
    logger.warning("EMERGENCY STOP triggered")
    for cb in _emergency_stop_callbacks:
        try:
            cb()
        except Exception:
            pass


def _register_emergency_hotkey() -> None:
    """Register F12 as global emergency stop hotkey."""
    import threading

    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes

        def _hotkey_listener():
            user32 = ctypes.windll.user32
            MOD_NONE = 0
            VK_F12 = 0x7B
            HOTKEY_ID = 1

            user32.RegisterHotKey(None, HOTKEY_ID, MOD_NONE, VK_F12)
            try:
                msg = ctypes.wintypes.MSG()
                while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
                    if msg.message == 0x0312 and msg.wParam == HOTKEY_ID:  # WM_HOTKEY
                        _fire_emergency_stop()
            finally:
                user32.UnregisterHotKey(None, HOTKEY_ID)

        t = threading.Thread(target=_hotkey_listener, daemon=True)
        t.start()

    elif sys.platform == "darwin":
        try:
            from Quartz import (
                CGEventMaskBit,
                kCGEventKeyDown,
            )
            from AppKit import NSEvent

            def _macos_key_handler(event):
                # F12 keycode = 0x6F (111)
                if event.keyCode() == 0x6F:
                    _fire_emergency_stop()

            NSEvent.addGlobalMonitorForEventsMatchingMask_handler_(
                CGEventMaskBit(kCGEventKeyDown),
                _macos_key_handler,
            )
        except ImportError:
            logger.warning("Could not register macOS emergency hotkey (pyobjc not available)")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _register_emergency_hotkey()
    yield


app = FastAPI(title="Player AI", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


TEMP_DIR = Path(__file__).resolve().parent.parent / "temp"


@app.get("/api/video/{filename}")
async def get_video(filename: str):
    path = TEMP_DIR / filename
    if not path.exists() or not path.name.endswith(".mp4"):
        return {"error": "not found"}
    return FileResponse(
        path,
        media_type="video/mp4",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
    )


@app.get("/api/windows")
async def get_windows():
    loop = asyncio.get_event_loop()
    windows = await loop.run_in_executor(None, list_windows)
    return {"windows": windows}


@app.get("/api/config")
async def get_config_endpoint():
    config = get_config()
    data = config.model_dump()
    # Mask API key
    if data["gemini_api_key"]:
        key = data["gemini_api_key"]
        data["gemini_api_key"] = key[:4] + "..." + key[-4:] if len(key) > 8 else "***"
    return data


@app.post("/api/config")
async def update_config_endpoint(updates: dict):
    config = update_config(updates)
    return {"status": "ok"}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WebSocket client connected")

    game_loop: GameLoop | None = None
    loop_event = asyncio.get_event_loop()

    async def status_callback(status: LoopStatus):
        try:
            await ws.send_json({"type": "status", "data": status.model_dump(mode="json")})
        except Exception:
            pass

    # Emergency stop hook
    def emergency_stop():
        if game_loop and game_loop.is_running:
            asyncio.run_coroutine_threadsafe(game_loop.stop(), loop_event)

    _emergency_stop_callbacks.append(emergency_stop)

    try:
        while True:
            msg = await ws.receive_json()
            cmd = msg.get("command")

            if cmd == "start":
                if game_loop and game_loop.is_running:
                    await ws.send_json({"type": "error", "data": "Already running"})
                    continue

                config = get_config()
                if not config.gemini_api_key:
                    await ws.send_json({"type": "error", "data": "No Gemini API key configured"})
                    continue

                game_loop = GameLoop(status_callback)
                await game_loop.start()
                await ws.send_json({"type": "ack", "data": "started"})

            elif cmd == "stop":
                if game_loop and game_loop.is_running:
                    await game_loop.stop()
                    await ws.send_json({"type": "ack", "data": "stopped"})
                else:
                    await ws.send_json({"type": "ack", "data": "not running"})

            elif cmd == "config":
                data = msg.get("data", {})
                update_config(data)
                await ws.send_json({"type": "ack", "data": "config updated"})

            else:
                await ws.send_json({"type": "error", "data": f"Unknown command: {cmd}"})

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        if game_loop and game_loop.is_running:
            await game_loop.stop()
        if emergency_stop in _emergency_stop_callbacks:
            _emergency_stop_callbacks.remove(emergency_stop)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
