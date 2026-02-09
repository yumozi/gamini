"""Screen capture via ffmpeg subprocess."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import sys
import tempfile
import threading
import time
from functools import partial
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Max width ffmpeg scales video to
VIDEO_MAX_WIDTH = 1280


def _build_input_args(
    fps: int,
    target_window: Optional[str],
    window_rect: Optional[dict] = None,
) -> list[str]:
    """Platform-specific input arguments for ffmpeg."""
    args: list[str] = []
    if sys.platform == "win32":
        args += ["-f", "gdigrab", "-framerate", str(fps)]
        # Limit real-time buffer to reduce stale frames at startup
        args += ["-rtbufsize", "100M"]
        if window_rect and window_rect.get("w", 0) > 0 and window_rect.get("h", 0) > 0:
            # Desktop-region capture instead of title= mode.
            # gdigrab title= uses GetDC(hwnd)+BitBlt which reads the window's
            # GDI surface — DirectX/OpenGL games do NOT update it, so it
            # returns a stale frame (often the startup screen from ages ago).
            # Desktop capture goes through the DWM compositor which always has
            # the current composited frame including DirectX content.
            args += [
                "-offset_x", str(window_rect["x"]),
                "-offset_y", str(window_rect["y"]),
                "-video_size", f"{window_rect['w']}x{window_rect['h']}",
                "-i", "desktop",
            ]
        elif target_window:
            args += ["-i", f"title={target_window}"]
        else:
            args += ["-i", "desktop"]
    elif sys.platform == "darwin":
        # avfoundation only accepts native device framerates (e.g. 30fps),
        # not arbitrary values like 5fps. Capture at 30fps and let the
        # output -vf fps filter downsample to the desired rate.
        args += ["-f", "avfoundation", "-framerate", "30", "-i", "1:none"]
    else:
        args += ["-f", "x11grab", "-framerate", str(fps), "-i", ":0.0"]
    return args


def _output_args(output_path: str, fragmented: bool = False, fps: int = 15) -> list[str]:
    """Encoding / output arguments.

    Args:
        fragmented: If True, use fragmented MP4 so the file is always
                    valid even if ffmpeg is killed mid-write.
        fps: Framerate, used to set keyframe interval for fragmented mode.
    """
    # On macOS, avfoundation captures at 30fps regardless of desired fps,
    # so we add an fps filter to downsample to the target rate.
    vf_filters = f"scale='min({VIDEO_MAX_WIDTH},iw)':-2"
    if sys.platform == "darwin":
        vf_filters = f"fps={fps}," + vf_filters
    args = [
        "-vf", vf_filters,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-crf", "30",
        "-pix_fmt", "yuv420p",
    ]
    if fragmented:
        # Keyframe every 1 second — this controls fragment size.
        # Without this, x264 defaults to ~250 frames between keyframes,
        # meaning NO fragments get written for short recordings.
        args += ["-g", str(fps)]
        # Fragmented MP4: moov atom written upfront, data in self-contained
        # fragments. File is playable even if the process is killed.
        args += ["-movflags", "frag_keyframe+empty_moov+default_base_moof"]
        # Flush packets to disk immediately so we don't lose data on kill
        args += ["-flush_packets", "1"]
    args.append(output_path)
    return args


def _safe_unlink(path: Path) -> None:
    """Delete a file, retrying briefly on Windows file-lock errors."""
    for attempt in range(5):
        try:
            path.unlink(missing_ok=True)
            return
        except PermissionError:
            if attempt < 4:
                time.sleep(0.2)
            else:
                logger.warning(f"Could not delete {path} (file locked)")


# ── Fixed-duration capture (used for first iteration) ──────────────────────

async def capture_screen(
    duration: float = 1.5,
    fps: int = 15,
    target_window: Optional[str] = None,
    window_rect: Optional[dict] = None,
) -> bytes:
    """Capture a fixed-duration screen video and return MP4 bytes."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None,
        partial(_capture_sync, duration, fps, target_window, window_rect),
    )


def _capture_sync(
    duration: float,
    fps: int,
    target_window: Optional[str],
    window_rect: Optional[dict] = None,
) -> bytes:
    """Synchronous fixed-duration ffmpeg capture."""
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()

    try:
        cmd = ["ffmpeg", "-y"] + _build_input_args(fps, target_window, window_rect)
        cmd += ["-t", str(duration)] + _output_args(str(tmp_path))

        result = subprocess.run(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            timeout=duration + 10,
        )

        if result.returncode != 0:
            err_msg = result.stderr.decode(errors="replace")[-500:]
            if target_window or window_rect:
                logger.warning(f"Window capture failed, falling back to full desktop")
                cmd = ["ffmpeg", "-y"] + _build_input_args(fps, None, None)
                cmd += ["-t", str(duration)] + _output_args(str(tmp_path))
                result = subprocess.run(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    timeout=duration + 10,
                )
                if result.returncode != 0:
                    err_msg = result.stderr.decode(errors="replace")[-500:]
                    raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {err_msg}")
            else:
                raise RuntimeError(f"ffmpeg failed (code {result.returncode}): {err_msg}")

        data = tmp_path.read_bytes()
        if len(data) < 2048:
            raise RuntimeError(f"ffmpeg captured no frames ({len(data)} bytes, likely empty MP4 container)")
        return data
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"ffmpeg capture timed out after {duration + 10}s")
    finally:
        _safe_unlink(tmp_path)


# ── Stoppable capture session (used for pipelined iterations) ──────────────

class CaptureSession:
    """An ongoing ffmpeg recording that can be stopped on demand and trimmed.

    Uses fragmented MP4 so the file is always valid, even if ffmpeg is
    killed mid-write. This avoids the Windows issue where sending 'q' to
    ffmpeg's stdin doesn't work (gdigrab blocks stdin reads).
    """

    def __init__(self, fps: int, target_window: Optional[str], window_rect: Optional[dict] = None) -> None:
        self._fps = fps
        self._tmp_path, self._proc = self._start(fps, target_window, window_rect)
        self._start_time = time.monotonic()

        # Check if ffmpeg died immediately (e.g. window not found)
        time.sleep(0.3)
        if self._proc.poll() is not None:
            stderr = self._proc.stderr.read().decode(errors="replace")
            if target_window or window_rect:
                logger.warning(f"Window capture failed, falling back to full desktop")
                _safe_unlink(self._tmp_path)
                self._tmp_path, self._proc = self._start(fps, None, None)
                self._start_time = time.monotonic()
                time.sleep(0.3)
                if self._proc.poll() is not None:
                    stderr2 = self._proc.stderr.read().decode(errors="replace")
                    _safe_unlink(self._tmp_path)
                    raise RuntimeError(f"ffmpeg desktop fallback failed: {stderr2[-300:]}")
            else:
                _safe_unlink(self._tmp_path)
                raise RuntimeError(f"ffmpeg failed to start: {stderr[-300:]}")

        # Drain stderr in a background thread to prevent pipe buffer deadlock.
        # ffmpeg writes progress to stderr; if the pipe fills (~64KB) ffmpeg
        # blocks and stops encoding, producing zero frames.
        threading.Thread(
            target=lambda p: p.stderr.read(), args=(self._proc,), daemon=True,
        ).start()

    @staticmethod
    def _start(fps: int, target_window: Optional[str], window_rect: Optional[dict] = None) -> tuple[Path, subprocess.Popen]:
        tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        tmp_path = Path(tmp.name)
        tmp.close()

        # Fragmented MP4 + no -t → records until killed
        cmd = ["ffmpeg", "-y"] + _build_input_args(fps, target_window, window_rect)
        cmd += _output_args(str(tmp_path), fragmented=True, fps=fps)

        proc = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        return tmp_path, proc

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self._start_time

    def stop_and_get(self, target_duration: float) -> bytes:
        """Stop recording, trim to last *target_duration* seconds, return bytes."""
        self._stop_ffmpeg()
        recorded = self.elapsed

        try:
            raw = self._tmp_path.read_bytes()
            if len(raw) < 2048:
                raise RuntimeError(f"ffmpeg captured no frames ({len(raw)} bytes, likely empty MP4 container)")

            logger.info(f"Session recorded {recorded:.1f}s, {len(raw)//1024}KB")

            # Only trim if we recorded significantly more than needed
            if recorded > target_duration + 0.5:
                trimmed = self._trim(target_duration)
                if trimmed:
                    logger.info(
                        f"Trimmed {recorded:.1f}s recording to last {target_duration}s "
                        f"({len(raw)//1024}KB → {len(trimmed)//1024}KB)"
                    )
                    return trimmed
                logger.warning("Trim failed, using full recording")

            return raw
        finally:
            _safe_unlink(self._tmp_path)

    def kill(self) -> None:
        """Force-stop the recording (used on cancellation)."""
        self._stop_ffmpeg()
        _safe_unlink(self._tmp_path)

    def _stop_ffmpeg(self) -> None:
        """Stop ffmpeg. Uses terminate() since fragmented MP4 is always valid."""
        if self._proc.poll() is not None:
            return
        self._proc.terminate()
        try:
            self._proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            self._proc.wait()
        # Small delay for Windows to release file handle
        time.sleep(0.1)

    def _trim(self, duration: float) -> Optional[bytes]:
        """Trim recording to the last *duration* seconds.

        Re-muxes the fragmented MP4 into a standard MP4 that Gemini
        definitely accepts.
        """
        out_tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
        out_path = Path(out_tmp.name)
        out_tmp.close()

        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-sseof", f"-{duration}",
                    "-i", str(self._tmp_path),
                    "-c:v", "libx264", "-preset", "ultrafast",
                    "-crf", "30", "-pix_fmt", "yuv420p",
                    str(out_path),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
            )
            if result.returncode == 0 and out_path.stat().st_size > 100:
                return out_path.read_bytes()
            err = result.stderr.decode(errors="replace")[-200:]
            logger.warning(f"Trim failed (code {result.returncode}): {err}")
            return None
        except Exception as e:
            logger.warning(f"Trim exception: {e}")
            return None
        finally:
            _safe_unlink(out_path)


# Async wrappers for CaptureSession

async def start_capture_session(
    fps: int, target_window: Optional[str], window_rect: Optional[dict] = None,
) -> CaptureSession:
    """Start a background capture session (runs in thread executor)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(CaptureSession, fps, target_window, window_rect),
    )


async def finish_capture(session: CaptureSession, target_duration: float) -> bytes:
    """Stop the capture session and return trimmed video bytes."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, partial(session.stop_and_get, target_duration),
    )
