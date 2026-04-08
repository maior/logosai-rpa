"""Mouse control — click, move, drag, scroll."""

import asyncio
from typing import Optional, Tuple

import pyautogui
from loguru import logger

# Safety: disable pyautogui failsafe (move to corner = abort)
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0.1  # 100ms pause between actions


async def move(x: int, y: int, duration: float = 0.3):
    """Move mouse to position."""
    await asyncio.to_thread(pyautogui.moveTo, x, y, duration=duration)


async def click(x: Optional[int] = None, y: Optional[int] = None, button: str = "left"):
    """Click at position (or current position if x,y not given)."""
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.click, x, y, button=button)
        logger.debug(f"Click ({button}) at ({x}, {y})")
    else:
        await asyncio.to_thread(pyautogui.click, button=button)
        logger.debug(f"Click ({button}) at current position")


async def double_click(x: Optional[int] = None, y: Optional[int] = None):
    """Double click."""
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.doubleClick, x, y)
    else:
        await asyncio.to_thread(pyautogui.doubleClick)


async def right_click(x: Optional[int] = None, y: Optional[int] = None):
    """Right click."""
    await click(x, y, button="right")


async def drag(start: Tuple[int, int], end: Tuple[int, int], duration: float = 0.5):
    """Drag from start to end."""
    await asyncio.to_thread(pyautogui.moveTo, start[0], start[1])
    await asyncio.to_thread(
        pyautogui.drag,
        end[0] - start[0], end[1] - start[1],
        duration=duration,
    )


async def scroll(amount: int, x: Optional[int] = None, y: Optional[int] = None):
    """Scroll (positive=up, negative=down)."""
    if x is not None and y is not None:
        await asyncio.to_thread(pyautogui.scroll, amount, x=x, y=y)
    else:
        await asyncio.to_thread(pyautogui.scroll, amount)
    logger.debug(f"Scroll {amount}")


def get_position() -> Tuple[int, int]:
    """Get current mouse position."""
    pos = pyautogui.position()
    return pos.x, pos.y
