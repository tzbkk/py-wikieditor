"""End-to-end integration tests for wiki_bot_server.

Verifies the full dispatch chain: handle_request → get_bot → FandomBot method.
The FandomBot boundary is mocked (via patch on wiki_bot_server.get_bot) so no
real mwclient / network is exercised; we are testing the dispatch wiring,
argument forwarding, response shaping, and retry logic.
"""
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

_EXTENSIONS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    ".pi",
    "extensions",
)
if _EXTENSIONS_DIR not in sys.path:
    sys.path.insert(0, _EXTENSIONS_DIR)


@pytest.fixture(autouse=True)
def _reset_bot_singleton():
    """Clear wiki_bot_server._bot before AND after each test so the
    module-level singleton never leaks state between cases (especially
    important for _edit_with_retry which can null it on login errors)."""
    import wiki_bot_server
    saved = wiki_bot_server._bot
    wiki_bot_server._bot = None
    yield
    wiki_bot_server._bot = saved


class TestEndToEnd:

    def test_check_exists_e2e(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.check_exists.return_value = {"MainPage": True, "MissingPage": False}

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-1",
                "method": "check_exists",
                "args": {"page_names": ["MainPage", "MissingPage"]},
            })

        assert resp["id"] == "e2e-1"
        assert resp["ok"] is True
        assert resp["result"] == {"MainPage": True, "MissingPage": False}
        mock_bot.check_exists.assert_called_once_with(["MainPage", "MissingPage"])

    def test_edit_page_e2e(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.edit_page_by_name.return_value = None

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-2",
                "method": "edit_page",
                "args": {"title": "TestPage", "content": "Hello", "summary": "test edit"},
            })

        assert resp["ok"] is True
        assert resp["result"] == {"title": "TestPage", "saved": True}
        mock_bot.edit_page_by_name.assert_called_once_with(
            "TestPage", "Hello", "test edit"
        )

    def test_edit_page_uses_default_summary_when_omitted(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-default-summary",
                "method": "edit_page",
                "args": {"title": "X", "content": "Y"},
            })

        assert resp["ok"] is True
        mock_bot.edit_page_by_name.assert_called_once_with(
            "X", "Y", "自动生成页面"
        )

    def test_edit_page_retries_once_on_login_error(self):
        """_edit_with_retry drops the cached bot and retries when the
        error message contains a login-keyword."""
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.edit_page_by_name.side_effect = [
            RuntimeError("login expired"),
            None,
        ]
        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-retry",
                "method": "edit_page",
                "args": {"title": "X", "content": "Y"},
            })

        assert resp["ok"] is True
        assert resp["result"]["saved"] is True
        assert resp["result"].get("retried") is True
        assert mock_bot.edit_page_by_name.call_count == 2

    def test_edit_page_does_not_retry_on_non_login_error(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.edit_page_by_name.side_effect = RuntimeError("wiki down")
        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-no-retry",
                "method": "edit_page",
                "args": {"title": "X", "content": "Y"},
            })

        assert resp["ok"] is False
        assert "wiki down" in resp["error"]
        mock_bot.edit_page_by_name.assert_called_once()

    def test_convert_text_e2e(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.convert_text.return_value = "简体中文"

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-3",
                "method": "convert_text",
                "args": {"text": "繁體中文"},
            })

        assert resp["ok"] is True
        assert resp["result"] == "简体中文"
        mock_bot.convert_text.assert_called_once_with("繁體中文")

    def test_get_category_members_e2e(self):
        from wiki_bot_server import handle_request

        page_a = MagicMock()
        page_a.name = "PageA"
        page_b = MagicMock()
        page_b.name = "PageB"
        mock_bot = MagicMock()
        mock_bot.get_category_members.return_value = [page_a, page_b]

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-4",
                "method": "get_category_members",
                "args": {"category_name": "TestCat"},
            })

        assert resp["ok"] is True
        assert resp["result"] == ["PageA", "PageB"]
        mock_bot.get_category_members.assert_called_once_with("TestCat")

    def test_get_template_embedded_pages_e2e(self):
        from wiki_bot_server import handle_request

        page_x = MagicMock()
        page_x.name = "PageX"
        mock_bot = MagicMock()
        mock_bot.get_template_embedded_pages.return_value = [page_x]

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-tpl",
                "method": "get_template_embedded_pages",
                "args": {"template_name": "Template:Infobox"},
            })

        assert resp["ok"] is True
        assert resp["result"] == ["PageX"]
        mock_bot.get_template_embedded_pages.assert_called_once_with("Template:Infobox")

    def test_read_page_text_e2e(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.read_page_text.return_value = "wikitext body"

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-read",
                "method": "read_page_text",
                "args": {"page_name": "Foo"},
            })

        assert resp["ok"] is True
        assert resp["result"] == "wikitext body"
        mock_bot.read_page_text.assert_called_once_with("Foo")

    def test_check_files_exist_e2e(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.check_files_exist.return_value = {"a.png": True}

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-files",
                "method": "check_files_exist",
                "args": {"filenames": ["a.png"]},
            })

        assert resp["ok"] is True
        assert resp["result"] == {"a.png": True}
        mock_bot.check_files_exist.assert_called_once_with(["a.png"])

    def test_error_doesnt_crash(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.check_exists.side_effect = RuntimeError("wiki down")

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-5",
                "method": "check_exists",
                "args": {"page_names": ["X"]},
            })

        assert resp["ok"] is False
        assert "wiki down" in resp["error"]
        assert resp["id"] == "e2e-5"

    def test_safe_error_redacts_session_tokens(self):
        """safe_error should redact token/session/cookie substrings
        before they reach the wire as the 'error' field."""
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.read_page_text.side_effect = RuntimeError(
            "fetch failed token=ABCSECRET session=XYZ"
        )

        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request({
                "id": "e2e-redact",
                "method": "read_page_text",
                "args": {"page_name": "X"},
            })

        assert resp["ok"] is False
        assert "ABCSECRET" not in resp["error"]
        assert "XYZ" not in resp["error"]
        assert "[REDACTED]" in resp["error"]
