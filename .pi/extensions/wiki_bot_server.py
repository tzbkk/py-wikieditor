#!/usr/bin/env python3
"""wiki_bot_server.py — IPC server for Pi wiki tools.

JSON-RPC over stdin/stdout. One JSON line in → one JSON line out.
Holds a singleton FandomBot (lazy-init on first real method call).
"""
import sys
import os
import json
import argparse

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)


_bot = None


def get_bot():
    """Return the singleton FandomBot instance, creating it on first call."""
    global _bot
    if _bot is None:
        from fandom_bot import FandomBot
        _bot = FandomBot.get_bot()
    return _bot


def safe_error(e):
    """Redact sensitive data from *e*; fall back to truncated str()."""
    try:
        from fandom_bot import safe_error as _safe_error
        return _safe_error(e)
    except Exception:
        msg = str(e)
        return msg[:200] + '...' if len(msg) > 200 else msg


def _err(req_id, msg):
    """Build a standard error response dict."""
    return {"id": req_id, "ok": False, "error": msg}


# Lowercase substrings that indicate a login/session-related failure.
# Used by _edit_with_retry() to decide whether to reset the singleton and retry.
_LOGIN_ERROR_KEYWORDS = ("login", "session", "auth", "token", "unauthorized", "expired")


def _edit_with_retry(req_id, title, content, summary):
    """Edit a page by title; on login/session expiry, clear the cached bot
    singleton and retry exactly once.

    Non-login errors are re-raised so the caller (handle_request) can wrap them
    in a standard error response.
    """
    global _bot
    try:
        get_bot().edit_page_by_name(title, content, summary)
        return {"id": req_id, "ok": True, "result": {"title": title, "saved": True}}
    except Exception as e:
        err_str = str(e).lower()
        if any(kw in err_str for kw in _LOGIN_ERROR_KEYWORDS):
            # Drop the cached singleton so get_bot() re-creates it (re-login).
            _bot = None
            try:
                get_bot().edit_page_by_name(title, content, summary)
                return {"id": req_id, "ok": True,
                        "result": {"title": title, "saved": True, "retried": True}}
            except Exception as e2:
                return {"id": req_id, "ok": False, "error": safe_error(e2)}
        # Non-login error: re-raise so handle_request's outer try can wrap it.
        raise


def handle_request(req):
    """Dispatch one request dict → response dict. Never raises (see method_docs)."""
    req_id = req.get("id", "?")
    method = req.get("method", "")
    args = req.get("args", {}) or {}
    try:
        if method == "ping":
            return {"id": req_id, "ok": True, "result": "pong"}

        elif method == "check_exists":
            page_names = args.get("page_names")
            if not isinstance(page_names, list):
                return _err(req_id, "check_exists requires 'page_names' (list)")
            result = get_bot().check_exists(page_names)
            return {"id": req_id, "ok": True, "result": result}

        elif method == "read_page_text":
            page_name = args.get("page_name")
            if not isinstance(page_name, str):
                return _err(req_id, "read_page_text requires 'page_name' (string)")
            result = get_bot().read_page_text(page_name)
            return {"id": req_id, "ok": True, "result": result}

        elif method == "check_files_exist":
            filenames = args.get("filenames")
            if not isinstance(filenames, list):
                return _err(req_id, "check_files_exist requires 'filenames' (list)")
            result = get_bot().check_files_exist(filenames)
            return {"id": req_id, "ok": True, "result": result}

        elif method == "edit_page":
            title = args.get("title")
            content = args.get("content")
            if not isinstance(title, str) or not isinstance(content, str):
                return _err(req_id,
                            "edit_page requires 'title' (str) and 'content' (str)")
            summary = args.get("summary", "自动生成页面")
            return _edit_with_retry(req_id, title, content, summary)

        elif method == "get_category_members":
            cat_name = args.get("category_name")
            if not isinstance(cat_name, str):
                return _err(req_id,
                            "get_category_members requires 'category_name' (str)")
            pages = get_bot().get_category_members(cat_name)
            # fandom_bot annotates these as List[object]; they are mwclient
            # Page instances, so use getattr to satisfy the type checker.
            return {"id": req_id, "ok": True,
                    "result": [getattr(p, "name") for p in pages]}

        elif method == "get_template_embedded_pages":
            tpl_name = args.get("template_name")
            if not isinstance(tpl_name, str):
                return _err(req_id,
                            "get_template_embedded_pages requires 'template_name' (str)")
            pages = get_bot().get_template_embedded_pages(tpl_name)
            return {"id": req_id, "ok": True,
                    "result": [getattr(p, "name") for p in pages]}

        elif method == "convert_text":
            text = args.get("text")
            if not isinstance(text, str):
                return _err(req_id, "convert_text requires 'text' (str)")
            result = get_bot().convert_text(text)
            return {"id": req_id, "ok": True, "result": result}

        return {"id": req_id, "ok": False, "error": f"Unknown method: {method}"}
    except Exception as e:
        return {"id": req_id, "ok": False, "error": safe_error(e)}


def method_docs():
    """Schema for every method exposed via handle_request()."""
    return {
        "methods": [
            {
                "name": "ping",
                "description": "Health check. Returns 'pong'.",
                "args": {},
                "returns": "string",
            },
            {
                "name": "check_exists",
                "description": "Batch-check whether each page name exists.",
                "args": {"page_names": "list[str]"},
                "returns": "dict[str, bool]",
            },
            {
                "name": "read_page_text",
                "description": "Read the raw wikitext of a page; null if missing.",
                "args": {"page_name": "str"},
                "returns": "str | null",
            },
            {
                "name": "check_files_exist",
                "description": "Batch-check File: namespace existence (auto-prefixed).",
                "args": {"filenames": "list[str]"},
                "returns": "dict[str, bool]",
            },
            {
                "name": "edit_page",
                "description": "Write content to a page; one retry on session/login error.",
                "args": {"title": "str", "content": "str", "summary?": "str"},
                "returns": "dict",
            },
            {
                "name": "get_category_members",
                "description": "List page names that are members of a category.",
                "args": {"category_name": "str"},
                "returns": "list[str]",
            },
            {
                "name": "get_template_embedded_pages",
                "description": "List page names that transclude a template.",
                "args": {"template_name": "str"},
                "returns": "list[str]",
            },
            {
                "name": "convert_text",
                "description": "Run Traditional→Simplified conversion on text.",
                "args": {"text": "str"},
                "returns": "str",
            },
        ],
    }


_MAX_INPUT_BYTES = 50 * 1024 * 1024


def _readline_limited(stream):
    """Read one line; reject lines over _MAX_INPUT_BYTES. Returns (line, err).

    (None, None) → EOF. (None, str) → oversize line.
    """
    line = stream.readline()
    if not line:
        return None, None
    if len(line) > _MAX_INPUT_BYTES:
        return None, f"Input line exceeds {_MAX_INPUT_BYTES} bytes"
    return line, None


def main():
    parser = argparse.ArgumentParser(description="Wiki Bot IPC Server")
    parser.add_argument("--check", action="store_true",
                        help="Self-check: print OK and exit 0")
    parser.add_argument("--method-docs", action="store_true",
                        help="Print method schemas as JSON and exit")
    args = parser.parse_args()

    if args.check:
        sys.stdout.write("OK\n")
        sys.stdout.flush()
        return

    if args.method_docs:
        sys.stdout.write(json.dumps(method_docs(), ensure_ascii=False) + "\n")
        sys.stdout.flush()
        return

    while True:
        line, size_err = _readline_limited(sys.stdin)
        if size_err is not None:
            resp = {"id": "?", "ok": False, "error": size_err}
        elif line is None:
            break
        else:
            line = line.strip()
            if not line:
                continue
            try:
                req = json.loads(line)
            except json.JSONDecodeError as e:
                resp = {"id": "?", "ok": False, "error": f"Invalid JSON: {e}"}
            else:
                if not isinstance(req, dict):
                    resp = {"id": "?", "ok": False,
                            "error": "Request must be a JSON object"}
                else:
                    resp = handle_request(req)
        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
