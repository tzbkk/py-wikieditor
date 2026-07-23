"""Unit tests for wiki_bot_server.py handle_request dispatch.

Tests handle_request() directly by importing it; mocks get_bot() so no
real FandomBot / .env / network is required.
"""
import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

# Add .pi/extensions to path so we can import wiki_bot_server
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(__file__)), ".pi", "extensions"
    ),
)


class TestPing:
    def test_returns_pong(self):
        from wiki_bot_server import handle_request

        resp = handle_request({"id": "t1", "method": "ping", "args": {}})
        assert resp["id"] == "t1"
        assert resp["ok"] is True
        assert resp["result"] == "pong"


class TestUnknownMethod:
    def test_returns_error(self):
        from wiki_bot_server import handle_request

        resp = handle_request({"id": "t2", "method": "nonexistent", "args": {}})
        assert resp["ok"] is False
        assert "Unknown method" in resp["error"]


class TestCheckExists:
    def test_dispatches_to_bot(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.check_exists.return_value = {"A": True, "B": False}
        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request(
                {
                    "id": "t",
                    "method": "check_exists",
                    "args": {"page_names": ["A", "B"]},
                }
            )
        assert resp["ok"] is True
        assert resp["result"] == {"A": True, "B": False}
        mock_bot.check_exists.assert_called_once_with(["A", "B"])

    def test_missing_arg(self):
        from wiki_bot_server import handle_request

        resp = handle_request({"id": "t", "method": "check_exists", "args": {}})
        assert resp["ok"] is False
        assert "page_names" in resp["error"]


class TestEditPage:
    def test_dispatches(self):
        from wiki_bot_server import handle_request

        mock_bot = MagicMock()
        mock_bot.edit_page_by_name.return_value = None
        with patch("wiki_bot_server.get_bot", return_value=mock_bot):
            resp = handle_request(
                {
                    "id": "t",
                    "method": "edit_page",
                    "args": {"title": "X", "content": "Y"},
                }
            )
        assert resp["ok"] is True
        mock_bot.edit_page_by_name.assert_called_once()

    def test_missing_args(self):
        from wiki_bot_server import handle_request

        resp = handle_request(
            {"id": "t", "method": "edit_page", "args": {"title": "X"}}
        )
        assert resp["ok"] is False


class TestMethodDocs:
    def test_valid_json(self):
        from wiki_bot_server import method_docs

        docs = method_docs()
        json.dumps(docs)
        names = [m["name"] for m in docs["methods"]]
        assert "ping" in names
        assert len(names) >= 8


class TestValidationErrors:
    """All methods validate required args."""

    @pytest.mark.parametrize(
        "method,args,expected_field",
        [
            ("check_exists", {}, "page_names"),
            ("read_page_text", {}, "page_name"),
            ("check_files_exist", {}, "filenames"),
            ("edit_page", {"title": "X"}, "content"),
            ("convert_text", {}, "text"),
        ],
    )
    def test_missing_required_arg(self, method, args, expected_field):
        from wiki_bot_server import handle_request

        resp = handle_request({"id": "t", "method": method, "args": args})
        assert resp["ok"] is False
        assert expected_field in resp["error"]
