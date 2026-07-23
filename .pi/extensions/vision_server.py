#!/usr/bin/env python3
"""vision_server.py — 图片分析 CLI，调用 OpenAI 兼容视觉 API。

用法: python3 vision_server.py --image <path> [--prompt <text>]
输出结果到 stdout，错误到 stderr。

配置优先级:
  1. .env 的 VISION_API_KEY / VISION_MODEL / VISION_API_BASE（显式覆盖）
  2. Pi 的 auth.json + models-store.json（自动读取，零配置）
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

MAX_FILE_SIZE = 20 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}

PI_AGENT_DIR = Path.home() / ".pi" / "agent"


def load_pi_vision_config() -> tuple[str | None, str | None, str | None]:
    settings_path = PI_AGENT_DIR / "settings.json"
    auth_path = PI_AGENT_DIR / "auth.json"
    store_path = PI_AGENT_DIR / "models-store.json"

    if not (settings_path.exists() and auth_path.exists() and store_path.exists()):
        return None, None, None

    settings = json.loads(settings_path.read_text(encoding="utf-8"))
    auth = json.loads(auth_path.read_text(encoding="utf-8"))
    store = json.loads(store_path.read_text(encoding="utf-8"))

    provider = settings.get("defaultProvider", "")
    provider_auth = auth.get(provider, {})
    api_key = provider_auth.get("key")

    provider_models = store.get(provider, {}).get("models", [])
    for m in provider_models:
        if "image" in m.get("input", []):
            return api_key, m.get("baseUrl"), m.get("id")

    return api_key, None, None


_pi_key, _pi_base, _pi_model = load_pi_vision_config()

API_KEY = os.environ.get("VISION_API_KEY", "") or _pi_key or ""
API_BASE = os.environ.get("VISION_API_BASE", "") or _pi_base or ""
MODEL = os.environ.get("VISION_MODEL", "") or _pi_model or ""
MAX_TOKENS = int(os.environ.get("VISION_MAX_TOKENS", "1000"))


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
        raise RuntimeError(
            "未找到 API Key。请在 .env 中设置 VISION_API_KEY，"
            "或通过 pi /login 登录后重试。"
        )
    if not MODEL:
        raise RuntimeError(
            "当前 Pi 提供商没有支持视觉的模型。"
            "请在 .env 中设置 VISION_MODEL 指定视觉模型。"
        )

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
