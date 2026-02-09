"""Core capture -> infer -> act loop."""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Awaitable, Callable, Optional

from backend.capture import VIDEO_MAX_WIDTH, capture_screen, finish_capture, start_capture_session
from backend.config import get_config
from backend.gemini_client import analyze_gameplay
from backend.input_controller import InputBackend, create_input_backend
from backend.models import GameActionResponse, LoopState, LoopStatus
from backend.window_manager import focus_window, get_screen_size, get_window_geometry

logger = logging.getLogger(__name__)

StatusCallback = Callable[[LoopStatus], Awaitable[None]]

TEMP_DIR = Path(__file__).resolve().parent.parent / "temp"
TEMP_DIR.mkdir(exist_ok=True)


class GameLoop:
    """Manages the capture -> Gemini -> act loop."""

    def __init__(self, status_callback: StatusCallback) -> None:
        self._status_callback = status_callback
        self._task: Optional[asyncio.Task] = None
        self._input: Optional[InputBackend] = None
        self._iteration = 0
        self._state = LoopState.IDLE
        self._history: list[GameActionResponse] = []
        self._last_fps: float = 0.0

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.is_running:
            return

        # Clean up old debug videos from previous runs
        for old in TEMP_DIR.glob("iter_*.mp4"):
            try:
                old.unlink()
            except OSError:
                pass

        self._input = create_input_backend()
        self._iteration = 0
        self._state = LoopState.RUNNING
        await self._push_status(LoopStatus(state=LoopState.RUNNING, iteration=0))
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if not self.is_running:
            return

        self._state = LoopState.STOPPING
        await self._push_status(LoopStatus(state=LoopState.STOPPING, iteration=self._iteration))

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._state = LoopState.IDLE
        await self._push_status(LoopStatus(state=LoopState.IDLE, iteration=self._iteration))

    @staticmethod
    def _save_video(iteration: int, video_bytes: bytes) -> str:
        """Save video to temp/ and return the URL path."""
        path = TEMP_DIR / f"iter_{iteration:04d}.mp4"
        path.write_bytes(video_bytes)
        logger.info(f"Saved debug video: {path.name} ({len(video_bytes) // 1024}KB)")
        return f"/api/video/{path.name}"

    def _get_screen_info(self, config) -> dict:
        """Get real screen dims + scaled video dims for coordinate mapping."""
        if config.target_window:
            geom = get_window_geometry(config.target_window)
            if geom:
                real_w, real_h = geom["w"], geom["h"]
                scale = min(VIDEO_MAX_WIDTH / real_w, 1.0)
                # -2 in ffmpeg means round to nearest even
                vid_w = int(real_w * scale) & ~1
                vid_h = int(real_h * scale) & ~1
                return {
                    "width": real_w,
                    "height": real_h,
                    "video_width": vid_w,
                    "video_height": vid_h,
                    "offset_x": geom["x"],
                    "offset_y": geom["y"],
                }
        sw, sh = get_screen_size()
        scale = min(VIDEO_MAX_WIDTH / sw, 1.0)
        vid_w = int(sw * scale) & ~1
        vid_h = int(sh * scale) & ~1
        return {"width": sw, "height": sh, "video_width": vid_w, "video_height": vid_h}


    def _scale_actions(self, response: GameActionResponse, screen_info: dict) -> None:
        """Convert bbox (0-1000 normalized) → real screen x, y in-place."""
        if not response.actions:
            return
        real_w = screen_info["width"]
        real_h = screen_info["height"]
        off_x = screen_info.get("offset_x", 0)
        off_y = screen_info.get("offset_y", 0)

        for a in response.actions:
            if a.bbox and len(a.bbox) == 4:
                y_min, x_min, y_max, x_max = a.bbox
                # Center of bounding box, scaled from 0-1000 → real screen coords
                a.x = int(((x_min + x_max) / 2 / 1000) * real_w) + off_x
                a.y = int(((y_min + y_max) / 2 / 1000) * real_h) + off_y

    async def _loop(self) -> None:
        """Pipelined loop:

        1. (iter 1 only) Fixed-duration capture for the initial video.
        2. Start background recording + send video to LLM (in parallel).
        3. LLM responds → execute actions (recording continues).
        4. Wait for remaining capture_duration if needed.
        5. Stop recording, trim to last capture_duration → this becomes
           the video for the next iteration (its tail includes action results).
        """
        session = None
        try:
            config = get_config()

            # Brief delay so the user can switch to the game window
            await asyncio.sleep(1.0)

            # ── First iteration: simple fixed-duration capture ──
            window_rect = None
            if config.target_window:
                focus_window(config.target_window)
                await asyncio.sleep(0.05)
                window_rect = get_window_geometry(config.target_window)
            video_bytes = await capture_screen(
                duration=config.capture_duration,
                fps=config.capture_fps,
                target_window=config.target_window,
                window_rect=window_rect,
            )

            while self._state == LoopState.RUNNING:
                self._iteration += 1
                iter_start = time.monotonic()
                config = get_config()

                status = LoopStatus(
                    state=LoopState.RUNNING,
                    iteration=self._iteration,
                    fps=self._last_fps,
                )

                try:
                    screen_info = self._get_screen_info(config)
                    window_rect = get_window_geometry(config.target_window) if config.target_window else None

                    # 1. Save the video we're about to send (for debug)
                    video_url = self._save_video(self._iteration, video_bytes)

                    # 2. Start recording NOW (runs during LLM call + action exec)
                    session = await start_capture_session(
                        config.capture_fps, config.target_window, window_rect,
                    )

                    # 3. Send current video to Gemini (recording runs in parallel)
                    response = await analyze_gameplay(
                        video_bytes, config,
                        screen_info=screen_info,
                        history=self._history,
                    )

                    # 3. Scale coordinates from video → real screen space
                    self._scale_actions(response, screen_info)

                    # 4. Push status immediately so frontend shows reasoning/actions
                    #    before they execute (not after the whole iteration finishes).
                    status.reasoning = response.reasoning
                    status.actions = response.actions
                    status.video_url = video_url
                    await self._push_status(status)

                    # 5. Execute actions (recording continues, capturing results)
                    if response.actions:
                        if config.target_window:
                            focus_window(config.target_window)
                            await asyncio.sleep(0.05)
                        await self._input.execute_actions(
                            response.actions,
                            delay=config.action_delay,
                        )

                    # 6. Wait for remaining capture time so video is at least
                    #    capture_duration long and includes action results
                    remaining = config.capture_duration - session.elapsed
                    if remaining > 0:
                        await asyncio.sleep(remaining)

                    # 7. Stop recording, trim to last capture_duration seconds
                    video_bytes = await finish_capture(session, config.capture_duration)
                    session = None

                    # 8. Update history (last 1 response)
                    self._history = [response]

                    # 9. Compute iterations/sec for the frontend display (sent in next iteration's push)
                    elapsed = time.monotonic() - iter_start
                    self._last_fps = 1.0 / elapsed if elapsed > 0 else 0

                except asyncio.CancelledError:
                    if session:
                        session.kill()
                        session = None
                    raise
                except Exception as e:
                    logger.error(f"Loop iteration {self._iteration} error: {e}", exc_info=True)
                    status.error = str(e)[:300]
                    # Clean up failed session
                    if session:
                        session.kill()
                        session = None
                    # Re-capture a fresh video for the next iteration
                    try:
                        err_rect = get_window_geometry(config.target_window) if config.target_window else None
                        video_bytes = await capture_screen(
                            duration=config.capture_duration,
                            fps=config.capture_fps,
                            target_window=config.target_window,
                            window_rect=err_rect,
                        )
                    except Exception:
                        pass

                # Push error status (success path already pushed reasoning earlier,
                # so clear it to avoid duplicate entries in the frontend)
                if status.error:
                    status.reasoning = ""
                    status.actions = []
                    await self._push_status(status)

        except asyncio.CancelledError:
            logger.info("Game loop cancelled")
        except Exception as e:
            logger.error(f"Game loop fatal error: {e}", exc_info=True)
            await self._push_status(LoopStatus(
                state=LoopState.ERROR,
                iteration=self._iteration,
                error=str(e)[:300],
            ))
        finally:
            if session:
                session.kill()
            self._state = LoopState.IDLE

    async def _push_status(self, status: LoopStatus) -> None:
        try:
            await self._status_callback(status)
        except Exception as e:
            logger.error(f"Status callback error: {e}")
