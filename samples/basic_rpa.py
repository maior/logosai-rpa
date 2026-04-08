"""Sample: LogosRPA 기본 사용법.

Usage:
    python samples/basic_rpa.py
"""

import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logosrpa import RPA


async def main():
    rpa = RPA()

    # ─── 1. 브라우저 열기 ───
    print("1️⃣  브라우저 열기")
    await rpa.browser.open("https://www.google.com")
    await asyncio.sleep(2)

    title = await rpa.browser.get_title()
    print(f"   Title: {title}")

    # ─── 2. 화면에서 텍스트 찾기 (3가지 엔진) ───
    print("\n2️⃣  화면 인식 테스트")

    # Engine 1: Chrome JS
    results = await rpa.screen.find_by_chrome_js("Google")
    print(f"   Chrome JS: {len(results)} results")

    # Engine 2: Apple Vision OCR
    results = await rpa.screen.find_by_apple_vision("Google")
    print(f"   Apple Vision: {len(results)} results")

    # Engine 3: Gemini Vision
    results = await rpa.screen.find_by_gemini_vision("검색 입력란")
    print(f"   Gemini Vision: {len(results)} results")

    # ─── 3. 검색어 입력 ───
    print("\n3️⃣  검색어 입력")
    await rpa.find_and_click("Google 검색", timeout=3)
    await asyncio.sleep(0.5)

    # 검색창에 입력
    await rpa.keyboard.type_text("LogosAI framework")
    await asyncio.sleep(1)
    await rpa.keyboard.press("enter")
    await asyncio.sleep(2)

    title = await rpa.browser.get_title()
    print(f"   검색 결과: {title}")

    # ─── 4. 스크린샷 ───
    print("\n4️⃣  스크린샷 저장")
    path = await rpa.screenshot("/tmp/logosrpa_basic_test.png")
    print(f"   📸 {path}")

    print("\n✅ 기본 테스트 완료!")


if __name__ == "__main__":
    asyncio.run(main())
