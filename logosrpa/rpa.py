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
                             max_retries: int = 2, app: str = "") -> bool:
        """Find element by text and click its center.

        Args:
            app: If set, search within this app's window only (crop + coordinate transform)
        On failure: auto-diagnose with Vision → recover → retry.
        """
        import time

        for attempt in range(1 + max_retries):
            # 앱 윈도우 기반 검색
            if app:
                el = await self._find_in_app_window(text, app)
                if el:
                    await mouse.click(*el.center)
                    logger.info(f"✅ Clicked '{text}' at {el.center} [app:{app}]")
                    return True
            else:
                start = time.time()
                while time.time() - start < timeout:
                    el = await self.screen.find_one(text, element_type=element_type, engine=engine)
                    if el:
                        cx, cy = el.center
                        await mouse.click(cx, cy)
                        logger.info(f"✅ Clicked '{text}' at ({cx}, {cy}) [{el.source}]")
                        return True
                    await asyncio.sleep(0.5)

            # 실패 → 진단
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

    async def _find_in_app_window(self, text: str, app_name: str) -> Optional[ScreenElement]:
        """Find element within a specific app's window using Gemini Vision.

        Crops the app window, sends to Gemini, converts coordinates back to screen.
        """
        from .platform.macos import screenshot_app_window, retina_scale
        import json, re, os

        crop_path, bounds = screenshot_app_window(app_name)
        if not crop_path or not bounds:
            return None

        try:
            from google import genai
            from google.genai import types
            import PIL.Image

            client = genai.Client(api_key=self.screen._gemini_key or os.getenv("GOOGLE_API_KEY", ""))
            image = PIL.Image.open(crop_path)
            iw, ih = image.size

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[
                    f'이 {app_name} 앱 스크린샷에서 "{text}" 항목의 위치를 찾아줘.\n'
                    f'이미지 크기: {iw}x{ih} 픽셀.\n'
                    f'해당 항목의 중앙 좌표를 반환: {{"x": 픽셀X, "y": 픽셀Y}}\n'
                    'JSON만, 설명 없이.',
                    image,
                ],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=200),
            )

            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                coords = json.loads(match.group())
                scale = retina_scale()
                # 크롭 이미지 좌표 → 스크린 논리 좌표
                screen_x = bounds["x"] + int(coords["x"] / scale)
                screen_y = bounds["y"] + int(coords["y"] / scale)
                logger.debug(f"  App window: crop({coords['x']},{coords['y']}) / scale={scale} + offset({bounds['x']},{bounds['y']}) → screen({screen_x},{screen_y})")
                return ScreenElement(
                    text=text, x=screen_x - 10, y=screen_y - 10,
                    width=20, height=20,
                    element_type="text", confidence=0.8, source=f"gemini_app:{app_name}",
                )
        except Exception as e:
            logger.error(f"_find_in_app_window failed: {e}")
        return None

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

    async def open_app(self, app_name: str) -> bool:
        """Open/activate app and VERIFY it's frontmost.

        Dock click + frontmost check. Retries if not in front.
        """
        from .platform.macos import ensure_app_frontmost

        success = await asyncio.to_thread(ensure_app_frontmost, app_name)
        if success:
            logger.info(f"✅ App frontmost: {app_name}")
            # 윈도우 클릭으로 키보드 포커스 확보
            from .platform.macos import get_app_window_bounds
            bounds = get_app_window_bounds(app_name)
            if bounds:
                cx = bounds["x"] + bounds["width"] // 2
                cy = bounds["y"] + 30  # 타이틀바 아래
                await mouse.click(cx, cy)
                await asyncio.sleep(0.3)
                logger.debug(f"  Window focus click: ({cx}, {cy})")
            return True

        logger.error(f"❌ Failed to bring {app_name} to front")
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
