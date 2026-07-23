#!/usr/bin/env python3
"""check_files.py — 批次檢查 File: 命名空間的檔案是否存在。

透過 FandomBot.check_files_exist 檢查一組檔名（會自動補 File: 前綴）。
可獨立執行：從 stdin 讀 JSON `{"filenames": [...]}`，
往 stdout 寫 JSON `{filename: bool, ...}`。
也可作為模組匯入。
"""
import sys
import os
import json

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


def check_files(bot, filenames):
    """委派給 bot.check_files_exist，回傳 {filename: bool} 映射。"""
    return bot.check_files_exist(filenames)


if __name__ == "__main__":
    from fandom_bot import FandomBot

    req = json.loads(sys.stdin.read())
    bot = FandomBot.get_bot()
    result = check_files(bot, req["filenames"])
    sys.stdout.write(json.dumps(result, ensure_ascii=False) + "\n")
    sys.stdout.flush()
