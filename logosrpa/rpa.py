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

    # ─── Recovery Engine ────────────────────────────────

    async def _execute_recovery(self, recovery_steps: list) -> bool:
        """Execute recovery steps from diagnose()."""
        for step in recovery_steps:
            action = step.get("action", "")
            desc = step.get("description", "")
            try:
                if action == "click":
                    x, y = step.get("x", 0), step.get("y", 0)
                    if x and y:
                        await mouse.click(x, y)
                        logger.info(f"  🔧 Recovery click ({x},{y}): {desc}")
                elif action == "type":
                    text = step.get("text", "")
                    if text:
                        await keyboard.type_text(text)
                        logger.info(f"  🔧 Recovery type: {desc}")
                elif action == "hotkey":
                    keys = step.get("keys", [])
                    if keys:
                        await keyboard.hotkey(*keys)
                        logger.info(f"  🔧 Recovery hotkey {'+'.join(keys)}: {desc}")
                elif action == "press":
                    key = step.get("key", "")
                    if key:
                        await keyboard.press(key)
                        logger.info(f"  🔧 Recovery press {key}: {desc}")
                elif action == "wait":
                    secs = step.get("seconds", 1)
                    await asyncio.sleep(secs)
                await asyncio.sleep(0.3)
            except Exception as e:
                logger.warning(f"  🔧 Recovery step failed: {e}")
        return True

    # ─── High-Level Actions (with auto-diagnose) ─────

    async def find_and_click(self, text: str, element_type: str = "any",
                             engine: str = "auto", timeout: float = 5,
                             max_retries: int = 2) -> bool:
        """Find element by text and click its center.

        On failure: auto-diagnose with Vision → recover → retry.
        """
        import time

        for attempt in range(1 + max_retries):
            start = time.time()
            while time.time() - start < timeout:
                el = await self.screen.find_one(text, element_type=element_type, engine=engine)
                if el:
                    cx, cy = el.center
                    await mouse.click(cx, cy)
                    logger.info(f"✅ Clicked '{text}' at ({cx}, {cy}) [{el.source}]")
                    return True
                await asyncio.sleep(0.5)

            # 실패 → 진단 (마지막 시도가 아닐 때만)
            if attempt < max_retries:
                logger.warning(f"⚠️ find_and_click('{text}') failed, diagnosing... (attempt {attempt+1})")
                diagnosis = await self.screen.diagnose(f"'{text}' 요소를 찾아 클릭하려 함")
                cause = diagnosis.get("cause", "unknown")
                recovery = diagnosis.get("recovery", [])
                logger.info(f"  📋 Cause: {cause}")

                if recovery:
                    await self._execute_recovery(recovery)
                    await asyncio.sleep(0.5)
                    continue
            break

        logger.warning(f"❌ find_and_click: '{text}' not found after {max_retries+1} attempts")
        return False

    async def find_and_type(self, field_text: str, input_text: str,
                            engine: str = "auto", clear: bool = True,
                            max_retries: int = 2) -> bool:
        """Find input field by text, click it, then type.

        On failure: auto-diagnose → recover → retry.
        """
        for attempt in range(1 + max_retries):
            el = await self.screen.find_one(field_text, element_type="input", engine=engine)
            if not el:
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

            # 실패 → 진단
            if attempt < max_retries:
                logger.warning(f"⚠️ find_and_type('{field_text}') failed, diagnosing...")
                diagnosis = await self.screen.diagnose(f"'{field_text}' 입력란을 찾아 '{input_text}' 입력하려 함")
                recovery = diagnosis.get("recovery", [])
                if recovery:
                    await self._execute_recovery(recovery)
                    continue
            break

        logger.warning(f"❌ find_and_type: '{field_text}' not found")
        return False

    async def wait_and_click(self, text: str, timeout: float = 10, engine: str = "auto") -> bool:
        """Wait for element to appear, then click it."""
        el = await self.screen.wait_for_text(text, timeout=timeout, engine=engine)
        if el:
            cx, cy = el.center
            await mouse.click(cx, cy)
            logger.info(f"✅ Waited and clicked '{text}' at ({cx}, {cy})")
            return True

        # 타임아웃 → 진단
        logger.warning(f"⚠️ wait_and_click('{text}') timeout, diagnosing...")
        diagnosis = await self.screen.diagnose(f"'{text}'가 화면에 나타나기를 기다렸으나 {timeout}초 초과")
        recovery = diagnosis.get("recovery", [])
        if recovery:
            await self._execute_recovery(recovery)
            # 한번 더 시도
            el = await self.screen.find_one(text, engine=engine)
            if el:
                await mouse.click(*el.center)
                return True

        return False

    # ─── App Control ─────────────────────────────────────

    async def open_app(self, app_name: str):
        """Open/activate a macOS application — like clicking the Dock icon.

        Priority:
        1. Dock icon click (most human-like, brings window to front)
        2. AppleScript activate (fallback)
        3. `open -a` (last resort)
        """
        from .platform.macos import applescript_async
        import subprocess

        # Method 1: Dock 아이콘 클릭 (사람처럼)
        try:
            result = await applescript_async(f'''
tell application "System Events"
    tell process "Dock"
        click UI element "{app_name}" of list 1
    end tell
end tell''')
            if result and "UI element" in result:
                await asyncio.sleep(1.5)
                logger.info(f"✅ App opened via Dock click: {app_name}")
                return True
        except Exception:
            pass

        # Method 2: AppleScript activate
        await applescript_async(f'tell application "{app_name}" to activate')
        await asyncio.sleep(1)

        front = await self.get_frontmost_app()
        if app_name.lower() in front.lower():
            logger.info(f"✅ App activated: {app_name}")
            return True

        # Method 3: open -a
        try:
            subprocess.Popen(["open", "-a", app_name])
            await asyncio.sleep(2)
            logger.info(f"✅ App opened: {app_name}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to open {app_name}: {e}")
            return False

    async def get_frontmost_app(self) -> str:
        """Get the name of the frontmost application."""
        from .platform.macos import applescript_async
        return await applescript_async("""
            tell application "System Events"
                return name of first application process whose frontmost is true
            end tell
        """)

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
