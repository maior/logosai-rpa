"""Browser control — Chrome (primary) + Playwright (background)."""

import asyncio
from typing import Optional

from loguru import logger


class Browser:
    """Chrome browser control via AppleScript + optional Playwright."""

    def __init__(self):
        self._playwright = None
        self._pw_browser = None

    # ─── Chrome (Primary — user's actual browser) ────────

    async def open(self, url: str):
        """Open URL in user's Chrome."""
        from .platform.macos import chrome_url
        await asyncio.to_thread(chrome_url, url)
        await asyncio.sleep(1)  # Page load
        logger.info(f"Browser: opened {url}")

    async def new_tab(self, url: str = ""):
        """Open new Chrome tab."""
        from .platform.macos import chrome_new_tab
        await asyncio.to_thread(chrome_new_tab, url)

    async def get_url(self) -> str:
        """Get current tab URL."""
        from .platform.macos import chrome_get_url
        return await asyncio.to_thread(chrome_get_url)

    async def get_title(self) -> str:
        """Get current tab title."""
        from .platform.macos import chrome_get_title
        return await asyncio.to_thread(chrome_get_title)

    async def activate(self):
        """Bring Chrome to front."""
        from .platform.macos import activate_chrome
        await asyncio.to_thread(activate_chrome)

    async def js(self, code: str) -> str:
        """Execute JavaScript in active tab."""
        from .platform.macos import chrome_js_async
        return await chrome_js_async(code)

    async def wait_for_page_load(self, timeout: float = 10):
        """Wait for page to finish loading."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            state = await self.js("document.readyState")
            if state == "complete":
                return
            await asyncio.sleep(0.5)

    async def scroll_down(self, pixels: int = 500):
        """Scroll page down."""
        await self.js(f"window.scrollBy(0, {pixels})")

    async def scroll_up(self, pixels: int = 500):
        """Scroll page up."""
        await self.js(f"window.scrollBy(0, -{pixels})")

    # ─── Playwright (Background — headless parallel) ─────

    async def pw_launch(self, headless: bool = True):
        """Launch Playwright browser for background tasks."""
        try:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
            self._pw_browser = await self._playwright.chromium.launch(headless=headless)
            logger.info(f"Playwright launched (headless={headless})")
        except ImportError:
            logger.warning("Playwright not installed: pip install playwright")

    async def pw_page(self, url: str):
        """Open page in Playwright, return page object."""
        if not self._pw_browser:
            await self.pw_launch()
        if not self._pw_browser:
            return None
        page = await self._pw_browser.new_page()
        await page.goto(url, wait_until="networkidle")
        return page

    async def pw_close(self):
        """Close Playwright browser."""
        if self._pw_browser:
            await self._pw_browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._pw_browser = None
        self._playwright = None
