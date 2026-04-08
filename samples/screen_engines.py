"""Sample: 3가지 화면 인식 엔진 비교 테스트.

현재 화면에서 지정한 텍스트를 3가지 엔진으로 찾고 속도/정확도 비교.

Usage:
    python samples/screen_engines.py "검색"
    python samples/screen_engines.py "로그인" --url https://naver.com
"""

import asyncio
import argparse
import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logosrpa import RPA


async def compare_engines(text: str, url: str = ""):
    rpa = RPA()

    if url:
        print(f"🌐 Opening: {url}")
        await rpa.browser.open(url)
        await asyncio.sleep(3)

    print(f"\n🔍 Finding: \"{text}\"")
    print("=" * 55)

    # Engine 1: Chrome JS
    t0 = time.time()
    r1 = await rpa.screen.find_by_chrome_js(text)
    t1 = time.time() - t0
    print(f"\n[Chrome JS]     {t1*1000:6.0f}ms | {len(r1)} found")
    for r in r1[:3]:
        cx, cy = r.center
        print(f"  → \"{r.text[:30]}\" at ({cx}, {cy})")

    # Engine 2: Apple Vision OCR
    t0 = time.time()
    r2 = await rpa.screen.find_by_apple_vision(text)
    t2 = time.time() - t0
    print(f"\n[Apple Vision]  {t2*1000:6.0f}ms | {len(r2)} found")
    for r in r2[:3]:
        cx, cy = r.center
        print(f"  → \"{r.text[:30]}\" at ({cx}, {cy})")

    # Engine 3: Gemini Vision
    t0 = time.time()
    r3 = await rpa.screen.find_by_gemini_vision(text)
    t3 = time.time() - t0
    print(f"\n[Gemini Vision] {t3*1000:6.0f}ms | {len(r3)} found")
    for r in r3[:3]:
        cx, cy = r.center
        print(f"  → \"{r.text[:30]}\" at ({cx}, {cy})")

    # Auto (통합)
    t0 = time.time()
    r4 = await rpa.screen.find(text)
    t4 = time.time() - t0
    engine = r4[0].source if r4 else "none"
    print(f"\n[Auto]          {t4*1000:6.0f}ms | {len(r4)} found (engine: {engine})")

    print(f"\n{'─' * 55}")
    print(f"  Winner: ", end="")
    times = {"Chrome JS": t1, "Apple Vision": t2, "Gemini Vision": t3}
    results = {"Chrome JS": len(r1), "Apple Vision": len(r2), "Gemini Vision": len(r3)}
    found = {k: v for k, v in results.items() if v > 0}
    if found:
        fastest = min(found, key=lambda k: times[k])
        print(f"{fastest} ({times[fastest]*1000:.0f}ms, {found[fastest]} results)")
    else:
        print("None found any results")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="3-Engine 화면 인식 비교")
    parser.add_argument("text", help="찾을 텍스트")
    parser.add_argument("--url", default="", help="먼저 열 URL")
    args = parser.parse_args()

    asyncio.run(compare_engines(args.text, args.url))
