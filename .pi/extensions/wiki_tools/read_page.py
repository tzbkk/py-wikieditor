#!/usr/bin/env python3
"""read_page.py — 讀取 Wiki 頁面原始文字。

透過 FandomBot.read_page_text 讀取頁面；不存在時回傳 None。
可獨立執行：從 stdin 讀 JSON `{"title": "..."}`，
往 stdout 寫 JSON `{"title": ..., "text": str|null}`。
也可作為模組匯入。
"""
import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def read_page(bot, title):
    """讀取單一頁面文字；回傳 {"title": title, "text": str|None}。"""
    text = bot.read_page_text(title)
    return {"title": title, "text": text}


if __name__ == "__main__":
    from fandom_bot import FandomBot

    req = json.loads(sys.stdin.read())
    bot = FandomBot.get_bot()
    result = read_page(bot, req["title"])
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
