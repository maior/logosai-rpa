"""Screen recognition — 3-engine hybrid (Chrome JS + Apple Vision OCR + Gemini Vision)."""

import asyncio
import json
import os
import subprocess
import tempfile
from typing import Optional, Dict, Any, List, Tuple

from loguru import logger


class ScreenElement:
    """A recognized element on screen with position."""

    def __init__(self, text: str, x: int, y: int, width: int, height: int,
                 element_type: str = "text", confidence: float = 1.0, source: str = "unknown"):
        self.text = text
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.element_type = element_type  # text, button, input, link, image
        self.confidence = confidence
        self.source = source  # chrome_js, apple_vision, gemini

    @property
    def center(self) -> Tuple[int, int]:
        """Center point for clicking."""
        return self.x + self.width // 2, self.y + self.height // 2

    def __repr__(self):
        return f"<{self.element_type} '{self.text[:20]}' at ({self.x},{self.y}) [{self.source}]>"


class Screen:
    """Hybrid screen recognition engine.

    Priority:
    1. Chrome JS — fastest, precise for web elements
    2. Apple Vision OCR — any screen, good Korean support
    3. Gemini Vision — semantic understanding, slowest
    """

    def __init__(self, gemini_api_key: Optional[str] = None):
        self._gemini_key = gemini_api_key or os.getenv("GOOGLE_API_KEY", "")
        self._chrome_bounds = None

    # ─── Engine 1: Chrome JS ─────────────────────────────

    async def find_by_chrome_js(self, text: str, element_type: str = "any") -> List[ScreenElement]:
        """Find elements in Chrome by text content using JavaScript.

        Returns screen coordinates (not page coordinates).
        """
        from .platform.macos import chrome_js_async, get_chrome_window_bounds

        # Get Chrome window offset for coordinate conversion
        bounds = get_chrome_window_bounds()
        if not bounds:
            return []

        # Chrome toolbar height (approximate)
        toolbar_height = 85

        type_filter = {
            "button": "button, a, [role='button'], input[type='submit']",
            "input": "input, textarea, [contenteditable]",
            "link": "a",
            "any": "*",
        }.get(element_type, "*")

        js = f"""
        (() => {{
            const target = {json.dumps(text)};
            const selector = "{type_filter}";
            const results = [];
            const elements = document.querySelectorAll(selector);
            for (const el of elements) {{
                const t = el.textContent.trim();
                const ph = el.placeholder || '';
                const val = el.value || '';
                const ariaLabel = el.getAttribute('aria-label') || '';
                if (t.includes(target) || ph.includes(target) || val.includes(target) || ariaLabel.includes(target)) {{
                    const rect = el.getBoundingClientRect();
                    if (rect.width > 0 && rect.height > 0) {{
                        results.push({{
                            text: t.substring(0, 100),
                            x: Math.round(rect.left),
                            y: Math.round(rect.top),
                            width: Math.round(rect.width),
                            height: Math.round(rect.height),
                            tag: el.tagName.toLowerCase(),
                            type: el.type || '',
                            id: el.id || '',
                            className: (el.className || '').substring(0, 50)
                        }});
                    }}
                }}
            }}
            return JSON.stringify(results.slice(0, 20));
        }})()"""

        try:
            result = await chrome_js_async(js)
            if not result:
                return []
            items = json.loads(result)
            elements = []
            for item in items:
                # Convert page coords to screen coords
                screen_x = bounds["x"] + item["x"]
                screen_y = bounds["y"] + toolbar_height + item["y"]
                el_type = "button" if item["tag"] in ("button", "a") else "input" if item["tag"] == "input" else "text"
                elements.append(ScreenElement(
                    text=item["text"],
                    x=screen_x, y=screen_y,
                    width=item["width"], height=item["height"],
                    element_type=el_type,
                    confidence=1.0,
                    source="chrome_js",
                ))
            logger.debug(f"Chrome JS: found {len(elements)} elements for '{text}'")
            return elements
        except Exception as e:
            logger.debug(f"Chrome JS failed: {e}")
            return []

    # ─── Engine 2: Apple Vision OCR ──────────────────────

    async def find_by_apple_vision(self, text: str) -> List[ScreenElement]:
        """Find text on screen using macOS Vision framework OCR.

        Uses VNRecognizeTextRequest for accurate Korean+English text recognition.
        """
        from .platform.macos import screenshot_async

        img_path = await screenshot_async()
        if not img_path:
            return []

        # Use macOS Vision framework via Swift/Python bridge
        swift_code = f'''
import Cocoa
import Vision

let imgPath = "{img_path}"
guard let image = NSImage(contentsOfFile: imgPath),
      let cgImage = image.cgImage(forProposedRect: nil, context: nil, hints: nil) else {{
    print("[]")
    exit(0)
}}

let request = VNRecognizeTextRequest()
request.recognitionLevel = .accurate
request.recognitionLanguages = ["ko-KR", "en-US"]
request.usesLanguageCorrection = true

let handler = VNImageRequestHandler(cgImage: cgImage, options: [:])
try handler.perform([request])

var results: [[String: Any]] = []
let imgW = Double(cgImage.width)
let imgH = Double(cgImage.height)

if let observations = request.results {{
    for obs in observations {{
        let text = obs.topCandidates(1).first?.string ?? ""
        let box = obs.boundingBox
        // Vision coords: origin bottom-left, normalized 0-1
        // Convert to screen coords: origin top-left, pixels
        let x = Int(box.origin.x * imgW)
        let y = Int((1.0 - box.origin.y - box.height) * imgH)
        let w = Int(box.width * imgW)
        let h = Int(box.height * imgH)
        results.append(["text": text, "x": x, "y": y, "w": w, "h": h, "conf": obs.confidence])
    }}
}}

let target = "{text}"
let filtered = results.filter {{ ($0["text"] as? String ?? "").contains(target) }}
let jsonData = try! JSONSerialization.data(withJSONObject: filtered.isEmpty ? results : filtered)
print(String(data: jsonData, encoding: .utf8)!)
'''
        try:
            # Write Swift script
            script_path = os.path.join(tempfile.gettempdir(), "logosrpa_vision.swift")
            with open(script_path, "w") as f:
                f.write(swift_code)

            proc = await asyncio.create_subprocess_exec(
                "swift", script_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=10)
            output = stdout.decode().strip()

            if not output or output == "[]":
                # Fallback: use screencapture + textutil approach
                return await self._apple_vision_fallback(text, img_path)

            items = json.loads(output)
            elements = []
            for item in items:
                item_text = item.get("text", "")
                if text.lower() in item_text.lower():
                    elements.append(ScreenElement(
                        text=item_text,
                        x=item.get("x", 0), y=item.get("y", 0),
                        width=item.get("w", 0), height=item.get("h", 0),
                        element_type="text",
                        confidence=item.get("conf", 0.5),
                        source="apple_vision",
                    ))
            logger.debug(f"Apple Vision: found {len(elements)} for '{text}'")
            return elements

        except Exception as e:
            logger.debug(f"Apple Vision failed: {e}")
            return await self._apple_vision_fallback(text, img_path)

    async def _apple_vision_fallback(self, text: str, img_path: str) -> List[ScreenElement]:
        """Fallback: use macOS built-in `shortcuts` or `qlmanage` for basic OCR."""
        try:
            # Use screencapture + textutil as basic fallback
            proc = await asyncio.create_subprocess_exec(
                "/usr/bin/mdls", "-name", "kMDItemTextContent", img_path,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=5)
            # mdls doesn't do OCR on screenshots, but this is a placeholder
            return []
        except Exception:
            return []

    # ─── Engine 3: Gemini Vision ─────────────────────────

    async def find_by_gemini_vision(self, instruction: str, img_path: Optional[str] = None) -> List[ScreenElement]:
        """Find elements using Gemini Vision AI.

        Args:
            instruction: Natural language instruction (e.g., "검색 버튼", "출발지 입력란")
            img_path: Screenshot path (auto-capture if None)
        """
        if not self._gemini_key:
            logger.warning("Gemini Vision: no API key")
            return []

        if not img_path:
            from .platform.macos import screenshot_async
            img_path = await screenshot_async()
            if not img_path:
                return []

        try:
            from google import genai
            from google.genai import types
            import PIL.Image

            client = genai.Client(api_key=self._gemini_key)
            image = PIL.Image.open(img_path)
            img_w, img_h = image.size

            prompt = f"""Look at this screenshot and find: "{instruction}"

For each matching element, return its bounding box as JSON array:
[{{"text": "element text", "x": left_px, "y": top_px, "width": width_px, "height": height_px, "type": "button|input|text|link"}}]

The image is {img_w}x{img_h} pixels. Return pixel coordinates.
If nothing found, return [].
JSON only, no explanation."""

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[prompt, image],
                config=types.GenerateContentConfig(temperature=0.1, max_output_tokens=1000),
            )

            result_text = response.text.strip()
            # Extract JSON array
            import re
            match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if not match:
                return []

            items = json.loads(match.group())
            elements = []
            for item in items:
                elements.append(ScreenElement(
                    text=item.get("text", ""),
                    x=item.get("x", 0), y=item.get("y", 0),
                    width=item.get("width", 0), height=item.get("height", 0),
                    element_type=item.get("type", "text"),
                    confidence=0.8,
                    source="gemini",
                ))
            logger.debug(f"Gemini Vision: found {len(elements)} for '{instruction}'")
            return elements

        except Exception as e:
            logger.error(f"Gemini Vision failed: {e}")
            return []

    # ─── Unified API ─────────────────────────────────────

    async def find(self, text: str, element_type: str = "any", engine: str = "auto") -> List[ScreenElement]:
        """Find elements on screen — auto-selects best engine.

        Priority: chrome_js → apple_vision → gemini
        """
        if engine == "chrome_js" or engine == "auto":
            results = await self.find_by_chrome_js(text, element_type)
            if results:
                return results
            if engine == "chrome_js":
                return []

        if engine == "apple_vision" or engine == "auto":
            results = await self.find_by_apple_vision(text)
            if results:
                return results
            if engine == "apple_vision":
                return []

        if engine == "gemini" or engine == "auto":
            results = await self.find_by_gemini_vision(text)
            return results

        return []

    async def find_one(self, text: str, element_type: str = "any", engine: str = "auto") -> Optional[ScreenElement]:
        """Find first matching element."""
        results = await self.find(text, element_type, engine)
        return results[0] if results else None

    async def wait_for_text(self, text: str, timeout: float = 10, interval: float = 0.5, engine: str = "auto") -> Optional[ScreenElement]:
        """Wait until text appears on screen."""
        import time
        start = time.time()
        while time.time() - start < timeout:
            el = await self.find_one(text, engine=engine)
            if el:
                return el
            await asyncio.sleep(interval)
        logger.warning(f"wait_for_text timeout: '{text}' not found in {timeout}s")
        return None

    async def diagnose(self, intention: str, img_path: Optional[str] = None) -> Dict[str, Any]:
        """Diagnose why an action failed by analyzing the current screen.

        Called automatically when find/click/type fails.

        Args:
            intention: What the RPA was trying to do (e.g., "검색창에 '권형근' 입력")
            img_path: Screenshot path (auto-capture if None)

        Returns:
            {"status": "현재 화면 상태",
             "cause": "실패 원인",
             "recovery": [{"action": "click|type|hotkey|press|wait", "params": {...}}]}
        """
        if not self._gemini_key:
            return {"status": "unknown", "cause": "Gemini API key missing", "recovery": []}

        if not img_path:
            from .platform.macos import screenshot_async
            img_path = await screenshot_async()
            if not img_path:
                return {"status": "unknown", "cause": "Screenshot failed", "recovery": []}

        try:
            from google import genai
            from google.genai import types
            import PIL.Image

            client = genai.Client(api_key=self._gemini_key)
            image = PIL.Image.open(img_path)
            img_w, img_h = image.size

            prompt = f"""RPA 자동화 중 문제가 발생했습니다.

의도한 작업: "{intention}"

이 스크린샷을 분석하여 다음을 JSON으로 반환하세요:
{{
  "status": "현재 화면에 보이는 상태 (어떤 앱, 어떤 화면, 무엇이 보이는지)",
  "cause": "의도한 작업이 실패한 원인 (포커스 문제, 팝업, 잘못된 화면 등)",
  "recovery": [
    {{"action": "click", "x": 픽셀X, "y": 픽셀Y, "description": "어디를 클릭"}},
    {{"action": "type", "text": "입력할 텍스트", "description": "무엇을 입력"}},
    {{"action": "hotkey", "keys": ["command", "f"], "description": "단축키"}},
    {{"action": "press", "key": "enter", "description": "키 입력"}},
    {{"action": "wait", "seconds": 1, "description": "대기"}}
  ]
}}

이미지 크기: {img_w}x{img_h}. 클릭 좌표는 화면 픽셀 기준.
recovery는 문제 해결을 위한 단계별 액션 목록 (1-5개).
JSON만 반환, 설명 없이."""

            response = client.models.generate_content(
                model="gemini-2.5-flash-lite",
                contents=[prompt, image],
                config=types.GenerateContentConfig(temperature=0.2, max_output_tokens=1000),
            )

            import re
            match = re.search(r'\{.*\}', response.text, re.DOTALL)
            if match:
                result = json.loads(match.group())
                logger.info(f"🔍 Diagnose: status={result.get('status','')[:50]}, cause={result.get('cause','')[:50]}")
                return result

        except Exception as e:
            logger.error(f"Diagnose failed: {e}")

        return {"status": "unknown", "cause": str(e) if 'e' in dir() else "unknown", "recovery": []}

    async def read_all_text(self, engine: str = "apple_vision") -> str:
        """Read all visible text on screen."""
        elements = await self.find("", engine=engine)
        return "\n".join(el.text for el in elements)

    async def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> str:
        """Take screenshot, return path."""
        from .platform.macos import screenshot_async
        return await screenshot_async(region)
