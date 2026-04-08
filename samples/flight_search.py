"""Sample: 네이버 항공권 검색 — LogosRPA 활용 예제.

Usage:
    python samples/flight_search.py
    python samples/flight_search.py --from GMP --to CJU --date 20260415
"""

import asyncio
import argparse
import re
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logosrpa import RPA


async def search_flights(departure: str = "GMP", arrival: str = "CJU", date: str = ""):
    """네이버 항공에서 항공편 검색."""
    rpa = RPA()

    # 날짜 기본값: 가장 가까운 금요일
    if not date:
        from datetime import datetime, timedelta
        today = datetime.now()
        days_ahead = (4 - today.weekday()) % 7 or 7
        date = (today + timedelta(days=days_ahead)).strftime("%Y%m%d")

    url = f"https://flight.naver.com/flights/domestic/{departure}-{arrival}-{date}?adult=1&fareType=Y"
    print(f"🔍 {departure} → {arrival} | {date[:4]}-{date[4:6]}-{date[6:]}")

    # 1. URL로 검색 조건 설정
    await rpa.browser.open(url)
    await asyncio.sleep(3)

    # 2. 팝업 제거
    await rpa.browser.js("""
        document.querySelectorAll('[data-testid="ad-popup"], [class*=Popup], [class*=popup]')
            .forEach(e => e.remove());
    """)

    # 3. 검색 클릭
    await rpa.find_and_click("검색", element_type="button", timeout=5)
    await asyncio.sleep(2)

    # 4. 결과 대기
    for i in range(10):
        await asyncio.sleep(2)
        body = await rpa.browser.js("document.body.innerText")
        prices = re.findall(r'[\d,]+원', body)
        if len(prices) >= 3:
            break
        if "검색된 항공편이 없습니다" in body:
            print("❌ 항공편 없음")
            return []

    # 5. 데이터 추출
    body = await rpa.browser.js("document.body.innerText")
    airlines = {'대한항공', '아시아나항공', '제주항공', '진에어', '티웨이항공', '에어부산', '에어서울', '이스타항공'}
    lines = body.split('\n')

    flights = []
    for i, line in enumerate(lines):
        for a in airlines:
            if a == line.strip():
                ctx = '\n'.join(lines[i:i+10])
                times = re.findall(r'(\d{1,2}:\d{2})', ctx)
                prices = re.findall(r'([\d,]+)원', ctx)
                dur = re.findall(r'(\d+시간\s*\d*분?)', ctx)
                flights.append({
                    "airline": a,
                    "departure": times[0] if times else "?",
                    "arrival": times[1] if len(times) > 1 else "?",
                    "duration": dur[0] if dur else "?",
                    "price": f"{prices[0]}원" if prices else "?",
                })
                break

    # 중복 제거
    seen = set()
    unique = [f for f in flights if not (f"{f['airline']}_{f['departure']}" in seen or seen.add(f"{f['airline']}_{f['departure']}"))]

    # 출력
    print(f"\n{'─' * 55}")
    print(f"  총 {len(unique)}개 항공편\n")
    for i, f in enumerate(unique):
        print(f"  [{i+1:2d}] {f['airline']:8s}  {f['departure']} → {f['arrival']}  ({f['duration']})  💰 {f['price']}")

    return unique


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="네이버 항공권 검색")
    parser.add_argument("--from", dest="dep", default="GMP", help="출발 공항 (default: GMP)")
    parser.add_argument("--to", dest="arr", default="CJU", help="도착 공항 (default: CJU)")
    parser.add_argument("--date", default="", help="날짜 YYYYMMDD (default: 다음 금요일)")
    args = parser.parse_args()

    asyncio.run(search_flights(args.dep, args.arr, args.date))
