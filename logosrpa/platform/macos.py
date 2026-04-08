"""macOS platform layer — AppleScript, Chrome JS, screenshots."""

import asyncio
import subprocess
import platform
import tempfile
import os
from typing import Optional, Dict, Any, List, Tuple

from loguru import logger


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def applescript(script: str, timeout: int = 15) -> str:
    """Run AppleScript and return result."""
    try:
        result = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True, text=True, timeout=timeout,
        )
        if result.returncode != 0 and result.stderr:
            logger.debug(f"AppleScript stderr: {result.stderr.strip()}")
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        logger.warning(f"AppleScript timeout ({timeout}s)")
        return ""
    except Exception as e:
        logger.error(f"AppleScript error: {e}")
        return ""


async def applescript_async(script: str, timeout: int = 15) -> str:
    """Run AppleScript asynchronously."""
    return await asyncio.to_thread(applescript, script, timeout)


def chrome_js(js_code: str, timeout: int = 10) -> str:
    """Execute JavaScript in Chrome's active tab and return result."""
    escaped = js_code.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n')
    script = f'''tell application "Google Chrome"
    set jsResult to execute active tab of front window javascript "{escaped}"
    return jsResult
end tell'''
    return applescript(script, timeout)


async def chrome_js_async(js_code: str, timeout: int = 10) -> str:
    """Execute JavaScript in Chrome's active tab asynchronously."""
    return await asyncio.to_thread(chrome_js, js_code, timeout)


def screenshot(region: Optional[Tuple[int, int, int, int]] = None) -> str:
    """Capture screenshot, return file path.

    Args:
        region: (x, y, width, height) or None for full screen
    """
    path = os.path.join(tempfile.gettempdir(), "logosrpa_screen.png")
    try:
        if region:
            x, y, w, h = region
            subprocess.run(
                ["screencapture", "-x", "-R", f"{x},{y},{w},{h}", path],
                timeout=5,
            )
        else:
            subprocess.run(["screencapture", "-x", path], timeout=5)
        return path
    except Exception as e:
        logger.error(f"Screenshot failed: {e}")
        return ""


async def screenshot_async(region: Optional[Tuple[int, int, int, int]] = None) -> str:
    """Capture screenshot asynchronously."""
    return await asyncio.to_thread(screenshot, region)


def get_screen_size() -> Tuple[int, int]:
    """Get logical screen resolution (pyautogui coordinates)."""
    try:
        import pyautogui
        return pyautogui.size()
    except Exception:
        return 1920, 1080


def get_retina_scale() -> float:
    """Get Retina scale factor (screenshot pixels / logical pixels)."""
    try:
        import pyautogui
        logical_w = pyautogui.size()[0]
        # Quick screencapture to check actual pixel size
        import tempfile
        path = os.path.join(tempfile.gettempdir(), "logosrpa_scale.png")
        subprocess.run(["screencapture", "-x", path], timeout=5, capture_output=True)
        from PIL import Image
        pixel_w = Image.open(path).size[0]
        return pixel_w / logical_w
    except Exception:
        return 2.0  # Default Retina


_RETINA_SCALE: Optional[float] = None


def retina_scale() -> float:
    """Cached Retina scale factor."""
    global _RETINA_SCALE
    if _RETINA_SCALE is None:
        _RETINA_SCALE = get_retina_scale()
    return _RETINA_SCALE


def get_app_window_bounds(app_name: str) -> Optional[Dict[str, int]]:
    """Get any app's window position and size (logical coordinates)."""
    result = applescript(f'''tell application "System Events"
    tell process "{app_name}"
        if (count of windows) = 0 then return ""
        set w to first window
        set p to position of w
        set s to size of w
        return (item 1 of p as string) & "|" & (item 2 of p as string) & "|" & (item 1 of s as string) & "|" & (item 2 of s as string)
    end tell
end tell''')
    try:
        if not result or "|" not in result:
            return None
        parts = [int(x) for x in result.split("|")]
        return {"x": parts[0], "y": parts[1], "width": parts[2], "height": parts[3]}
    except Exception:
        return None


def screenshot_app_window(app_name: str) -> Tuple[Optional[str], Optional[Dict[str, int]]]:
    """Capture screenshot of a specific app window only.

    Returns: (cropped_image_path, logical_bounds) or (None, None)
    """
    bounds = get_app_window_bounds(app_name)
    if not bounds:
        return None, None

    full_path = screenshot()
    if not full_path:
        return None, None

    try:
        from PIL import Image
        full = Image.open(full_path)
        scale = retina_scale()

        # Crop with Retina scaling
        x, y, w, h = bounds["x"], bounds["y"], bounds["width"], bounds["height"]
        crop_box = (int(x * scale), int(y * scale), int((x + w) * scale), int((y + h) * scale))
        cropped = full.crop(crop_box)

        crop_path = os.path.join(tempfile.gettempdir(), f"logosrpa_{app_name.lower()}.png")
        cropped.save(crop_path)
        return crop_path, bounds
    except Exception as e:
        logger.error(f"App window screenshot failed: {e}")
        return None, None


def ensure_app_frontmost(app_name: str, max_retries: int = 3) -> bool:
    """Ensure app is truly frontmost — Dock click + verify."""
    for attempt in range(max_retries):
        # Dock click
        applescript(f'''tell application "System Events"
    tell process "Dock"
        click UI element "{app_name}" of list 1
    end tell
end tell''')
        import time
        time.sleep(1)

        # Verify
        front = applescript('''tell application "System Events"
    return name of first application process whose frontmost is true
end tell''')

        if app_name.lower() in front.lower():
            return True
        logger.warning(f"App not frontmost (attempt {attempt+1}): expected={app_name}, got={front}")

    return False


def get_chrome_window_bounds() -> Optional[Dict[str, int]]:
    """Get Chrome window position and size."""
    result = applescript('''tell application "Google Chrome"
    set b to bounds of front window
    return (item 1 of b) & "," & (item 2 of b) & "," & (item 3 of b) & "," & (item 4 of b)
end tell''')
    try:
        parts = [int(x.strip()) for x in result.split(",")]
        return {"x": parts[0], "y": parts[1], "width": parts[2] - parts[0], "height": parts[3] - parts[1]}
    except Exception:
        return None


def activate_chrome():
    """Bring Chrome to front."""
    applescript('tell application "Google Chrome" to activate')


def chrome_url(url: str):
    """Navigate Chrome active tab to URL."""
    escaped = url.replace('"', '\\"')
    applescript(f'''tell application "Google Chrome"
    activate
    if (count of windows) = 0 then make new window
    set URL of active tab of front window to "{escaped}"
end tell''')


def chrome_new_tab(url: str = ""):
    """Open new Chrome tab."""
    escaped = url.replace('"', '\\"')
    if url:
        applescript(f'''tell application "Google Chrome"
    activate
    tell front window to make new tab with properties {{URL:"{escaped}"}}
end tell''')
    else:
        applescript('''tell application "Google Chrome"
    activate
    tell front window to make new tab
end tell''')


def chrome_get_url() -> str:
    """Get current Chrome tab URL."""
    return applescript('''tell application "Google Chrome"
    return URL of active tab of front window
end tell''')


def chrome_get_title() -> str:
    """Get current Chrome tab title."""
    return applescript('''tell application "Google Chrome"
    return title of active tab of front window
end tell''')
