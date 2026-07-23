"""Test wiki_tools/save_page.py handler."""
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


def test_save_page_calls_edit_page_by_name():
    from wiki_tools.save_page import save_page

    bot = MagicMock()
    result = save_page(bot, "TestPage", "content", "summary")
    bot.edit_page_by_name.assert_called_once_with("TestPage", "content", "summary")
    assert result["saved"] is True
