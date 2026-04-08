"""Sample: 카카오톡으로 메시지 보내기 — 자동 진단/복구 포함.

Usage:
    python samples/kakaotalk_message.py
    python samples/kakaotalk_message.py --to "권형근" --msg "안녕하세요"
"""

import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logosrpa import RPA
from logosrpa.platform.macos import applescript


async def send_kakaotalk(recipient: str = "권형근", message: str = "안녕"):
    rpa = RPA()

    print(f"💬 카카오톡: {recipient}에게 '{message}'")
    print("=" * 50)

    # 1. 카카오톡 열기 (Dock 클릭)
    print("\n[1] 카카오톡 열기...")
    await rpa.open_app("KakaoTalk")
    await asyncio.sleep(1)

    # 2. 윈도우 포커스 (윈도우 클릭)
    print("[2] 윈도우 포커스...")
    info = applescript('''
tell application "System Events"
    tell process "KakaoTalk"
        set w to first window
        set p to position of w
        set s to size of w
        return (item 1 of p as string) & "|" & (item 2 of p as string) & "|" & (item 1 of s as string) & "|" & (item 2 of s as string)
    end tell
end tell
''')
    if info and "|" in info:
        wx, wy, ww, wh = [int(x) for x in info.split("|")]
        await rpa.mouse.click(wx + ww // 2, wy + 50)
        await asyncio.sleep(0.5)

    # 3. 검색 (Cmd+F) — 실패 시 자동 진단
    print("[3] 검색창 열기 (Cmd+F)...")
    await rpa.hotkey("command", "f")
    await asyncio.sleep(0.8)

    # 4. 이름 입력
    print(f"[4] '{recipient}' 입력...")
    await rpa.keyboard.type_text(recipient)
    await asyncio.sleep(2)

    # 5. 검색 결과에서 채팅방 클릭 — 자동 진단/복구 포함
    print(f"[5] '{recipient}' 채팅방 클릭...")
    clicked = await rpa.find_and_click(recipient, timeout=3, max_retries=2)

    if not clicked:
        print("   ⚠️ 자동 진단으로도 실패 — Esc 후 재시도")
        await rpa.press("escape")
        await asyncio.sleep(0.5)
        return False

    await asyncio.sleep(1)

    # 6. 메시지 입력 + 전송
    print(f"[6] 메시지 전송: '{message}'")
    await rpa.keyboard.type_text(message)
    await asyncio.sleep(0.3)
    await rpa.press("enter")
    await asyncio.sleep(1)

    # 7. 확인
    await rpa.screenshot("/tmp/kakaotalk_final.png")
    print(f"\n✅ 완료! 📸 /tmp/kakaotalk_final.png")
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="카카오톡 메시지 전송")
    parser.add_argument("--to", default="권형근", help="수신자 이름")
    parser.add_argument("--msg", default="안녕", help="메시지 내용")
    args = parser.parse_args()

    asyncio.run(send_kakaotalk(args.to, args.msg))
