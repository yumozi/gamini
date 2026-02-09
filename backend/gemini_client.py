"""Gemini API client with structured output for gameplay analysis."""

from __future__ import annotations

import asyncio
import json
import logging
import math
from typing import Optional

from google import genai
from google.genai import types

from backend.models import AppConfig, GameActionResponse

logger = logging.getLogger(__name__)

_client: Optional[genai.Client] = None
_current_api_key: Optional[str] = None

SYSTEM_PROMPT = """\
You are a game-playing AI agent. You observe gameplay and decide what actions to take.

Analyze the video and respond with:
- Your reasoning: what you see and what you decided to do (keep it brief, one sentence max)
- A list of actions to execute (to ensure flow, it is usually better to sequence a number of actions)'

Strictly use the most recent video content as source of truth, do not hallucinate.

Available action types:
- key_press: Press and release a key (use 'key' field, optional 'duration' in seconds)
- key_down: Hold a key down (use 'key' field)
- key_up: Release a held key (use 'key' field)
- mouse_move: Move mouse to a target (use 'bbox' to specify the target location)
- mouse_click: Click mouse (use 'button': left/right/middle, use 'bbox' for target location)
- mouse_down: Press mouse button (use 'button')
- mouse_up: Release mouse button (use 'button')
- wait: Pause for 'duration' seconds

POSITIONING: For ALL mouse actions that need a target position, provide a 'bbox' field \
with [y_min, x_min, y_max, x_max] as a bounding box around the target element. \
Coordinates use a 0-1000 scale relative to the full video frame \
(0 = top/left edge, 1000 = bottom/right edge). \
Do NOT set 'x' or 'y' fields directly — they are computed from bbox automatically.

Common key names: w, a, s, d, space, shift, ctrl, alt, tab, escape, enter, up, down, left, right, 1-9, f1-f12
\
"""


def estimate_video_tokens(duration: float, fps: int, media_resolution: str) -> int:
    """Estimate input tokens for a video clip sent to Gemini.

    Based on Google's docs:
    - Low resolution: 66 tokens/frame
    - Default/medium/high: 258 tokens/frame
    - Audio: 32 tokens/second
    """
    frames = math.ceil(duration * fps)
    tokens_per_frame = 66 if media_resolution == "low" else 258
    audio_tokens = int(32 * duration)
    return frames * tokens_per_frame + audio_tokens


def _get_client(api_key: str) -> genai.Client:
    global _client, _current_api_key
    if _client is None or _current_api_key != api_key:
        _client = genai.Client(api_key=api_key)
        _current_api_key = api_key
    return _client


async def analyze_gameplay(
    video_bytes: bytes,
    config: AppConfig,
    retry_count: int = 2,
    screen_info: Optional[dict] = None,
    history: Optional[list[GameActionResponse]] = None,
) -> GameActionResponse:
    """Send video to Gemini and get structured action response.

    Args:
        video_bytes: MP4 video bytes.
        config: Current app configuration.
        retry_count: Max retries on rate-limit errors.
        screen_info: Dict with 'width' and 'height' of the capture area,
                     and optionally 'offset_x'/'offset_y' for window position.
        history: Last N GameActionResponses for context continuity.

    Returns:
        Parsed GameActionResponse.
    """
    client = _get_client(config.gemini_api_key)

    user_prompt = "Analyze this gameplay video and decide what actions to take."
    if history:
        prev = history[-1]
        parts = []
        for a in prev.actions:
            desc = a.action.value
            if a.key:
                desc += f"(key={a.key})"
            elif a.bbox:
                desc += f"(bbox={a.bbox})"
            elif a.button:
                desc += f"(button={a.button.value})"
            parts.append(desc)
        actions_str = ", ".join(parts) or "none"
        user_prompt += (
            f"\n\nPrevious action — Reasoning: {prev.reasoning[:150]} | Actions: {actions_str}"
            f"\nThe previous action was executed prior/during this video's recording. "
            f"The end of the video shows the result of that action and the most recent game state."
        )
    if config.game_context:
        user_prompt += f"\n\nGame context:\n{config.game_context}"

    contents = [
        types.Part(
            inline_data=types.Blob(data=video_bytes, mime_type="video/mp4"),
            video_metadata=types.VideoMetadata(fps=config.capture_fps),
        ),
        types.Part.from_text(text=user_prompt),
    ]

    media_res = (
        types.MediaResolution.MEDIA_RESOLUTION_LOW
        if config.media_resolution == "low"
        else types.MediaResolution.MEDIA_RESOLUTION_MEDIUM
    )

    gen_config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        temperature=config.temperature,
        response_mime_type="application/json",
        response_schema=GameActionResponse,
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        thinking_config=types.ThinkingConfig(thinking_level="low"),
        media_resolution=media_res,
    )

    video_kb = len(video_bytes) / 1024
    est_tokens = estimate_video_tokens(config.capture_duration, config.capture_fps, config.media_resolution)
    # Check MP4 validity: must start with ftyp box or mdat/moov
    header = video_bytes[:12] if len(video_bytes) >= 12 else video_bytes
    is_valid_mp4 = b"ftyp" in header or b"moov" in header or b"mdat" in header
    logger.info(
        f"Gemini request: model={config.model}, video={video_kb:.0f}KB, "
        f"fps={config.capture_fps}, res={config.media_resolution}, ~{est_tokens} video tokens, "
        f"valid_mp4={is_valid_mp4}, header={header[:12].hex()}, screen={screen_info}"
    )

    # Reject empty/corrupt video before wasting API calls
    if len(video_bytes) < 2048 or not is_valid_mp4:
        logger.error(f"Skipping Gemini call: video too small or invalid ({len(video_bytes)} bytes, valid={is_valid_mp4})")
        return GameActionResponse(reasoning="Capture failed: empty or corrupt video", actions=[])

    for attempt in range(retry_count + 1):
        try:
            import time as _time
            t0 = _time.monotonic()

            response = await asyncio.wait_for(
                client.aio.models.generate_content(
                    model=config.model,
                    contents=contents,
                    config=gen_config,
                ),
                timeout=20,
            )

            elapsed = _time.monotonic() - t0
            logger.info(f"Gemini responded in {elapsed:.1f}s")

            # Try parsed first (structured output)
            if response.parsed:
                logger.debug(f"Parsed response: {response.parsed}")
                return response.parsed

            # Fallback: manual JSON parse from text
            if response.text:
                logger.info(f"Falling back to text parse, text length={len(response.text)}")
                data = json.loads(response.text)
                return GameActionResponse(**data)

            logger.warning("Gemini returned empty response")
            return GameActionResponse(reasoning="No response from model", actions=[])

        except asyncio.TimeoutError:
            logger.error(f"Gemini API timed out after 20s (attempt {attempt + 1})")
            if attempt >= retry_count:
                return GameActionResponse(reasoning="API timeout", actions=[])

        except Exception as e:
            error_str = str(e)
            if "429" in error_str and attempt < retry_count:
                wait_time = 2 ** (attempt + 1)
                logger.warning(f"Rate limited, retrying in {wait_time}s (attempt {attempt + 1})")
                await asyncio.sleep(wait_time)
                continue

            logger.error(f"Gemini API error: {e}")
            if attempt >= retry_count:
                return GameActionResponse(
                    reasoning=f"API error: {error_str[:200]}",
                    actions=[],
                )

    return GameActionResponse(reasoning="Max retries exceeded", actions=[])
