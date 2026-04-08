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
    """Get screen resolution."""
    result = applescript('''
tell application "Finder"
    set screenBounds to bounds of window of desktop
    return (item 3 of screenBounds) & "," & (item 4 of screenBounds)
end tell''')
    try:
        parts = result.split(",")
        return int(parts[0].strip()), int(parts[1].strip())
    except Exception:
        return 1920, 1080


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
