"""LogosRPA — Main RPA class combining all modules."""

import asyncio
from typing import Optional, Tuple

from loguru import logger

from .screen import Screen, ScreenElement
from .browser import Browser
from . import mouse
from . import keyboard


class RPA:
    """Desktop RPA engine.

    Combines screen recognition, browser control, mouse, and keyboard
    into a unified interface for AI agent automation.

    Usage:
        rpa = RPA()
        await rpa.browser.open("https://flight.naver.com")
        await rpa.find_and_click("검색")
        await rpa.find_and_type("출발지", "김포")
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self.screen = Screen(gemini_api_key=gemini_api_key)
        self.browser = Browser()
        self.mouse = mouse
        self.keyboard = keyboard

    # ─── High-Level Actions ──────────────────────────────

    async def find_and_click(self, text: str, element_type: str = "any",
                             engine: str = "auto", timeout: float = 5) -> bool:
        """Find element by text and click its center.

        Tries to find element within timeout, then clicks.
        Returns True if successful.
        """
        import time
        start = time.time()
        while time.time() - start < timeout:
            el = await self.screen.find_one(text, element_type=element_type, engine=engine)
            if el:
                cx, cy = el.center
                await mouse.click(cx, cy)
                logger.info(f"✅ Clicked '{text}' at ({cx}, {cy}) [{el.source}]")
                return True
            await asyncio.sleep(0.5)

        logger.warning(f"❌ find_and_click: '{text}' not found in {timeout}s")
        return False

    async def find_and_type(self, field_text: str, input_text: str,
                            engine: str = "auto", clear: bool = True) -> bool:
        """Find input field by text, click it, then type.

        Args:
            field_text: Text to identify the input field (label, placeholder)
            input_text: Text to type into the field
            clear: Clear existing content before typing
        """
        el = await self.screen.find_one(field_text, element_type="input", engine=engine)
        if not el:
            # Try finding by nearby text (label next to input)
            el = await self.screen.find_one(field_text, element_type="any", engine=engine)

        if el:
            cx, cy = el.center
            await mouse.click(cx, cy)
            await asyncio.sleep(0.2)
            if clear:
                await keyboard.clear_field()
                await asyncio.sleep(0.1)
            await keyboard.type_text(input_text)
            logger.info(f"✅ Typed '{input_text}' into '{field_text}' [{el.source}]")
            return True

        logger.warning(f"❌ find_and_type: field '{field_text}' not found")
        return False

    async def wait_and_click(self, text: str, timeout: float = 10, engine: str = "auto") -> bool:
        """Wait for element to appear, then click it."""
        el = await self.screen.wait_for_text(text, timeout=timeout, engine=engine)
        if el:
            cx, cy = el.center
            await mouse.click(cx, cy)
            logger.info(f"✅ Waited and clicked '{text}' at ({cx}, {cy})")
            return True
        return False

    async def click_at(self, x: int, y: int):
        """Click at specific coordinates."""
        await mouse.click(x, y)

    async def type_text(self, text: str):
        """Type text at current cursor position."""
        await keyboard.type_text(text)

    async def press(self, key: str):
        """Press a key."""
        await keyboard.press(key)

    async def hotkey(self, *keys: str):
        """Press key combination."""
        await keyboard.hotkey(*keys)

    async def wait(self, seconds: float):
        """Wait for specified seconds."""
        await asyncio.sleep(seconds)

    async def screenshot(self, path: Optional[str] = None) -> str:
        """Take screenshot."""
        img = await self.screen.screenshot()
        if path and img:
            import shutil
            shutil.copy(img, path)
            return path
        return img
