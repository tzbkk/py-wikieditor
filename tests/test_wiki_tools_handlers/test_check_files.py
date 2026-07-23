"""Test wiki_tools/check_files.py handler.

NOTE: the module-level function is named ``check_files`` (it delegates to
``bot.check_files_exist``), so we import ``check_files`` here.
"""
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


def test_check_files_delegates():
    from wiki_tools.check_files import check_files

    bot = MagicMock()
    bot.check_files_exist.return_value = {"x.jpg": True}
    result = check_files(bot, ["x.jpg"])
    bot.check_files_exist.assert_called_once_with(["x.jpg"])
    assert result == {"x.jpg": True}
