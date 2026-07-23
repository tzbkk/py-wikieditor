#!/usr/bin/env python3
"""vision_server.py — 图片分析 CLI，调用 OpenAI 兼容视觉 API。

用法: python3 vision_server.py --image <path> [--prompt <text>]
输出结果到 stdout，错误到 stderr。
"""
import sys
import os
import json
import base64
import mimetypes
import argparse
from pathlib import Path

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(_REPO_ROOT) / ".env")
except ImportError:
    pass

API_KEY = os.environ.get("VISION_API_KEY", "")
API_BASE = os.environ.get("VISION_API_BASE", "https://api.openai.com/v1")
MODEL = os.environ.get("VISION_MODEL", "gpt-4o")
MAX_TOKENS = int(os.environ.get("VISION_MAX_TOKENS", "1000"))
MAX_FILE_SIZE = 20 * 1024 * 1024

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def analyze(image_path: str, prompt: str) -> str:
    p = Path(image_path).expanduser().resolve()
    if not p.exists():
        raise FileNotFoundError(f"文件不存在 — {image_path}")
    if p.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"不支持的格式 '{p.suffix}'，支持 {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )
    if p.stat().st_size > MAX_FILE_SIZE:
        raise ValueError(
            f"文件过大（{p.stat().st_size // 1024 // 1024}MB），"
            f"上限 {MAX_FILE_SIZE // 1024 // 1024}MB"
        )
    if not API_KEY:
        raise RuntimeError("未配置 VISION_API_KEY，请在 .env 中设置")

    with open(p, "rb") as f:
        image_data = base64.b64encode(f.read()).decode("utf-8")
    mime_type = mimetypes.guess_type(str(p))[0] or "image/jpeg"

    import requests

    resp = requests.post(
        f"{API_BASE}/chat/completions",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
        json={
            "model": MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{image_data}"
                            },
                        },
                    ],
                }
            ],
            "max_tokens": MAX_TOKENS,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()["choices"][0]["message"]["content"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="分析图片")
    parser.add_argument("--image", required=True, help="图片文件路径")
    parser.add_argument(
        "--prompt",
        default="详细描述这张图片的内容",
        help="分析指令",
    )
    args = parser.parse_args()

    try:
        result = analyze(args.image, args.prompt)
        print(result)
    except Exception as e:
        print(f"错误：{e}", file=sys.stderr)
        sys.exit(1)
