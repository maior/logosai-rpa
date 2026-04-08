# LogosRPA

[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

**Desktop RPA for AI agents — browser automation, screen recognition, keyboard/mouse control.**

LogosRPA automates your desktop through your actual Chrome browser, not a separate automation browser. It sees what you see, clicks where you'd click, and types what you'd type — making it undetectable by anti-bot systems and compatible with your existing login sessions.

```bash
pip install logos-rpa
```

## Why LogosRPA?

| | LogosRPA | Selenium | Playwright | PyAutoGUI |
|---|---------|----------|------------|-----------|
| **Uses your real browser** | ✅ Your Chrome | ❌ Separate | ❌ Separate | N/A |
| **Login sessions** | ✅ Already logged in | ❌ New session | ❌ New session | ✅ |
| **Anti-bot detection** | ✅ Real user | ❌ Detected | ❌ Detected | ✅ |
| **Screen recognition** | ✅ 3-engine hybrid | ❌ | ❌ | ❌ |
| **Korean text** | ✅ Native | △ | △ | ❌ |
| **AI-powered** | ✅ Gemini Vision | ❌ | ❌ | ❌ |
| **Works with any app** | ✅ Chrome + native | ❌ Browser only | ❌ Browser only | ✅ But blind |

## Quick Start

### Basic — Open, Find, Click, Type

```python
import asyncio
from logosrpa import RPA

async def main():
    rpa = RPA()

    # Open a website in your Chrome
    await rpa.browser.open("https://www.google.com")

    # Find "Google 검색" button and click it
    await rpa.find_and_click("Google 검색")

    # Type text (Korean supported)
    await rpa.keyboard.type_text("LogosAI framework")
    await rpa.keyboard.press("enter")

    # Take screenshot
    await rpa.screenshot("/tmp/result.png")

asyncio.run(main())
```

### Flight Search — Real-World Example

```python
import asyncio
from logosrpa import RPA

async def search_flights():
    rpa = RPA()

    # Navigate directly via URL
    await rpa.browser.open("https://flight.naver.com/flights/domestic/GMP-CJU-20260410?adult=1&fareType=Y")
    await asyncio.sleep(3)

    # Click search button (auto-detected on screen)
    await rpa.find_and_click("검색")
    await asyncio.sleep(3)

    # Extract results from page
    body = await rpa.browser.js("document.body.innerText")
    print(body)  # Contains airline, times, prices

asyncio.run(search_flights())
```

## 3-Engine Screen Recognition

LogosRPA uses three recognition engines in a priority chain:

```
find("검색") → Chrome JS (fast) → Apple Vision OCR (any screen) → Gemini Vision (smart)
```

| Engine | Speed | Scope | Best For |
|--------|-------|-------|----------|
| **Chrome JS** | ~100ms | Chrome web elements | Buttons, inputs, links in web pages |
| **Apple Vision OCR** | ~500ms | Any screen content | Text on any app, native UI |
| **Gemini Vision** | ~3s | Semantic understanding | "Find the cheapest option", complex layouts |

### Use Specific Engine

```python
# Auto (tries all engines in priority order)
element = await rpa.screen.find_one("검색")

# Force specific engine
element = await rpa.screen.find_one("검색", engine="chrome_js")
element = await rpa.screen.find_one("검색", engine="apple_vision")
element = await rpa.screen.find_one("검색", engine="gemini")

# Wait for text to appear
element = await rpa.screen.wait_for_text("검색 결과", timeout=10)
```

### Compare Engines

```bash
python samples/screen_engines.py "검색" --url https://flight.naver.com
```

## API Reference

### RPA (Main Class)

```python
rpa = RPA()

# High-level actions
await rpa.find_and_click("텍스트")           # Find element by text → click
await rpa.find_and_type("입력란", "내용")      # Find input → type
await rpa.wait_and_click("텍스트", timeout=10) # Wait for element → click
await rpa.screenshot("/tmp/screen.png")       # Capture screenshot
```

### Browser

```python
await rpa.browser.open("https://...")         # Navigate Chrome
await rpa.browser.new_tab("https://...")      # New tab
await rpa.browser.js("document.title")        # Execute JavaScript
await rpa.browser.get_title()                 # Current tab title
await rpa.browser.get_url()                   # Current tab URL
await rpa.browser.scroll_down(500)            # Scroll page
await rpa.browser.activate()                  # Bring Chrome to front

# Playwright (background/parallel)
page = await rpa.browser.pw_page("https://...") # Headless page
await rpa.browser.pw_close()
```

### Screen

```python
# Find elements
elements = await rpa.screen.find("검색")               # Auto engine
element = await rpa.screen.find_one("검색")             # First match
element = await rpa.screen.wait_for_text("완료", timeout=10)

# Each element has:
element.text       # "검색"
element.x, element.y, element.width, element.height
element.center     # (cx, cy) — click point
element.source     # "chrome_js" | "apple_vision" | "gemini"
element.confidence # 0.0 ~ 1.0
```

### Mouse

```python
await rpa.mouse.click(x, y)                  # Left click
await rpa.mouse.double_click(x, y)            # Double click
await rpa.mouse.right_click(x, y)             # Right click
await rpa.mouse.move(x, y, duration=0.3)      # Move cursor
await rpa.mouse.scroll(-3)                    # Scroll down
await rpa.mouse.drag((x1,y1), (x2,y2))       # Drag
```

### Keyboard

```python
await rpa.keyboard.type_text("한글도 됩니다")   # Type (Korean via clipboard)
await rpa.keyboard.press("enter")             # Single key
await rpa.keyboard.hotkey("command", "c")     # Key combination
await rpa.keyboard.select_all()               # Cmd+A
await rpa.keyboard.copy()                     # Cmd+C
await rpa.keyboard.paste()                    # Cmd+V
await rpa.keyboard.clear_field()              # Select all + delete
```

## Samples

| File | Description |
|------|-------------|
| [basic_rpa.py](samples/basic_rpa.py) | Basic usage — open, find, click, type, screenshot |
| [flight_search.py](samples/flight_search.py) | Flight search on Naver Air — real-world RPA |
| [screen_engines.py](samples/screen_engines.py) | Compare 3 screen recognition engines |

```bash
python samples/basic_rpa.py
python samples/flight_search.py --from GMP --to CJU
python samples/screen_engines.py "검색" --url https://flight.naver.com
```

## Architecture

```
logosrpa/
├── rpa.py              # Main class — unified API
├── browser.py          # Chrome (AppleScript) + Playwright (background)
├── screen.py           # 3-engine hybrid recognition
├── mouse.py            # pyautogui mouse control
├── keyboard.py         # Keyboard input (Korean clipboard method)
└── platform/
    └── macos.py        # AppleScript, Chrome JS, screenshots
```

## Requirements

- **macOS** (Linux support planned)
- **Python 3.11+**
- **Google Chrome**
- **pyautogui**, **Pillow** (auto-installed)
- **google-genai** (optional, for Gemini Vision): `pip install logos-rpa[vision]`
- **playwright** (optional, for background): `pip install logos-rpa[playwright]`

## Related

- [logosai](https://github.com/maior/logosai-framework) — AI Agent Framework
- [logosai-ontology](https://github.com/maior/logosai-ontology) — Multi-Agent Orchestration
- [logosai-api](https://github.com/maior/logosai-api) — FastAPI Backend

## License

[MIT](LICENSE) — Copyright (c) 2023-2026 LogosAI
