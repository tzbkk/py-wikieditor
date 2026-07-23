#!/usr/bin/env python3
"""save_page.py — 保存 Wiki 页面。

透過 FandomBot.edit_page_by_name 將內容寫入指定頁面。
可獨立執行：從 stdin 讀一行 JSON 請求 `{"title","content","summary"?}`，
往 stdout 寫一行 JSON 回應 `{"title","saved"}`。
也可作為模組匯入，傳入已存在的 bot 實例。
"""
import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def save_page(bot, title, content, summary="自动生成页面"):
    """使用 bot 將 content 寫入 title 頁面。"""
    bot.edit_page_by_name(title, content, summary)
    return {"title": title, "saved": True}


if __name__ == "__main__":
    from fandom_bot import FandomBot

    req = json.loads(sys.stdin.read())
    bot = FandomBot.get_bot()
    result = save_page(
        bot,
        req["title"],
        req["content"],
        req.get("summary", "自动生成页面"),
    )
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
