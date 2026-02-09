"""Window listing and focusing via pywinctl."""

from __future__ import annotations

import sys

import pywinctl


def list_windows() -> list[dict]:
    """List visible windows with non-empty titles.

    Returns:
        List of dicts with 'title' and 'geometry' (x, y, w, h).
    """
    seen: set[str] = set()
    results: list[dict] = []

    for win in pywinctl.getAllWindows():
        title = win.title.strip()
        if not title or title in seen:
            continue
        if not win.isVisible:
            continue

        seen.add(title)
        try:
            rect = win.box
            geometry = {"x": rect.left, "y": rect.top, "w": rect.width, "h": rect.height}
        except Exception:
            geometry = None

        results.append({"title": title, "geometry": geometry})

    results.sort(key=lambda w: w["title"].lower())
    return results


def get_window_geometry(title: str) -> dict | None:
    """Get window geometry (x, y, w, h) by title. Returns None if not found."""
    windows = pywinctl.getWindowsWithTitle(title)
    if not windows:
        return None
    try:
        rect = windows[0].box
        return {"x": rect.left, "y": rect.top, "w": rect.width, "h": rect.height}
    except Exception:
        return None


def get_screen_size() -> tuple[int, int]:
    """Get primary screen resolution."""
    if sys.platform == "win32":
        import ctypes
        user32 = ctypes.windll.user32
        user32.SetProcessDPIAware()
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)
    elif sys.platform == "darwin":
        try:
            from AppKit import NSScreen
            frame = NSScreen.mainScreen().frame()
            # Return point coordinates (not pixels) because macOS mouse
            # events (CGEventPost) operate in point space, not pixel space.
            return int(frame.size.width), int(frame.size.height)
        except Exception:
            pass
    return 1920, 1080  # fallback


def focus_window(title: str) -> bool:
    """Bring window with given title to foreground.

    Returns:
        True if window was found and focused.
    """
    windows = pywinctl.getWindowsWithTitle(title)
    if not windows:
        return False

    win = windows[0]
    try:
        if sys.platform == "darwin":
            # On macOS, pywinctl's activate() can cause windows to exit
            # maximized/full-window state. Use NSRunningApplication instead
            # which activates the *app* without manipulating window geometry.
            from AppKit import NSRunningApplication, NSApplicationActivateIgnoringOtherApps
            pid = win.getHandle()
            app = NSRunningApplication.runningApplicationWithProcessIdentifier_(pid)
            if app:
                app.activateWithOptions_(NSApplicationActivateIgnoringOtherApps)
                return True
            return False
        else:
            if win.isMinimized:
                win.restore()
            win.activate()
            return True
    except Exception:
        return False
