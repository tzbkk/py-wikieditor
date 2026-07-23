#!/usr/bin/env python3
"""check_exists.py — 批次檢查頁面是否存在。

透過 FandomBot.check_exists 檢查一組頁面名稱。
可獨立執行：從 stdin 讀 JSON `{"titles": [...]}`，
往 stdout 寫 JSON `{title: bool, ...}`。
也可作為模組匯入。
"""
import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def check_exists(bot, titles):
    """委派給 bot.check_exists，回傳 {title: bool} 映射。"""
    return bot.check_exists(titles)


if __name__ == "__main__":
    from fandom_bot import FandomBot

    req = json.loads(sys.stdin.read())
    bot = FandomBot.get_bot()
    result = check_exists(bot, req["titles"])
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
