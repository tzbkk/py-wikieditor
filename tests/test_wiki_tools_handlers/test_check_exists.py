"""Test wiki_tools/check_exists.py handler."""
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


def test_check_exists_delegates():
    from wiki_tools.check_exists import check_exists

    bot = MagicMock()
    bot.check_exists.return_value = {"A": True}
    result = check_exists(bot, ["A"])
    bot.check_exists.assert_called_once_with(["A"])
    assert result == {"A": True}
