"""Keyboard control — typing, hotkeys, special keys."""

import asyncio
import subprocess
import platform

import pyautogui
from loguru import logger


async def type_text(text: str, interval: float = 0.02):
    """Type text character by character.

    For Korean text on macOS, uses AppleScript clipboard method
    since pyautogui doesn't support Korean input directly.
    """
    has_korean = any('\uac00' <= c <= '\ud7a3' or '\u3131' <= c <= '\u3163' for c in text)

    if has_korean and platform.system() == "Darwin":
        await _type_korean_mac(text)
    else:
        await asyncio.to_thread(pyautogui.typewrite, text, interval=interval)
    logger.debug(f"Typed: {text[:30]}{'...' if len(text) > 30 else ''}")


async def _type_korean_mac(text: str):
    """Type Korean text on macOS via clipboard."""
    # Save current clipboard
    try:
        old_clip = subprocess.run(["pbpaste"], capture_output=True, text=True, timeout=3).stdout
    except Exception:
        old_clip = ""

    # Set clipboard to text
    proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
    proc.communicate(text.encode("utf-8"))

    # Paste
    await asyncio.to_thread(pyautogui.hotkey, "command", "v")
    await asyncio.sleep(0.1)

    # Restore clipboard
    if old_clip:
        proc = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
        proc.communicate(old_clip.encode("utf-8"))


async def press(key: str):
    """Press a single key (enter, tab, escape, backspace, etc.)."""
    await asyncio.to_thread(pyautogui.press, key)
    logger.debug(f"Press: {key}")


async def hotkey(*keys: str):
    """Press key combination (e.g., hotkey('command', 'a'))."""
    await asyncio.to_thread(pyautogui.hotkey, *keys)
    logger.debug(f"Hotkey: {'+'.join(keys)}")


async def select_all():
    """Select all text (Cmd+A)."""
    await hotkey("command", "a")


async def copy():
    """Copy selection (Cmd+C)."""
    await hotkey("command", "c")


async def paste():
    """Paste clipboard (Cmd+V)."""
    await hotkey("command", "v")


async def undo():
    """Undo (Cmd+Z)."""
    await hotkey("command", "z")


async def clear_field():
    """Select all + delete (clear input field)."""
    await select_all()
    await asyncio.sleep(0.05)
    await press("backspace")
