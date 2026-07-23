"""Test wiki_tools/read_page.py handler."""
import os
import sys
from unittest.mock import MagicMock

sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
        ".pi",
        "extensions",
    ),
)


def test_read_page_returns_text():
    from wiki_tools.read_page import read_page

    bot = MagicMock()
    bot.read_page_text.return_value = "hello"
    result = read_page(bot, "Test")
    bot.read_page_text.assert_called_once_with("Test")
    assert result["text"] == "hello"
