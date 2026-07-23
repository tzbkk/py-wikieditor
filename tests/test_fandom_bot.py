"""Unit tests for FandomBot — T1 new methods + edit_page retry logic."""
import pytest
from unittest.mock import MagicMock, patch, call


class TestEditPageRetry:
    def test_retry_then_success(self, mock_bot):
        """ratelimited on first attempt, success on second."""
        page = MagicMock()
        attempts = []
        def fake_edit(content, summary=None):
            attempts.append(summary)
            if len(attempts) < 2:
                raise Exception("API error: ratelimited")
        page.edit.side_effect = fake_edit
        with patch('fandom_bot.time.sleep') as mock_sleep:
            mock_bot.edit_page(page, "content", summary="test")
        assert len(attempts) == 2
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args_list[0] == call(60)

    def test_non_ratelimited_no_retry(self, mock_bot):
        page = MagicMock()
        page.edit.side_effect = Exception("some other error")
        with patch('fandom_bot.time.sleep'):
            with pytest.raises(Exception, match="some other error"):
                mock_bot.edit_page(page, "content")
        assert page.edit.call_count == 1


class TestEditPageExhausted:
    def test_three_attempts_ratelimited(self, mock_bot):
        page = MagicMock()
        page.edit.side_effect = Exception("ratelimited")
        with patch('fandom_bot.time.sleep'):
            with pytest.raises(Exception, match="ratelimited"):
                mock_bot.edit_page(page, "content")
        assert page.edit.call_count == 3


class TestCheckExists:
    def test_mixed(self, mock_bot, mock_page):
        pa = mock_page(name="A", exists=True)
        pb = mock_page(name="B", exists=False)
        mock_bot.site.pages.__getitem__ = lambda _, k: {"A": pa, "B": pb}[k]
        assert mock_bot.check_exists(["A", "B"]) == {"A": True, "B": False}

    def test_empty(self, mock_bot):
        assert mock_bot.check_exists([]) == {}


class TestReadPageText:
    def test_exists(self, mock_bot, mock_page):
        p = mock_page(name="T", exists=True, text="hello")
        mock_bot.site.pages.__getitem__ = lambda _, k: p
        assert mock_bot.read_page_text("T") == "hello"

    def test_not_exists(self, mock_bot, mock_page):
        p = mock_page(name="G", exists=False)
        mock_bot.site.pages.__getitem__ = lambda _, k: p
        assert mock_bot.read_page_text("G") is None


class TestCheckFilesExist:
    def test_auto_prefix(self, mock_bot, mock_page):
        p = mock_page(exists=True)
        mock_bot.site.pages.__getitem__ = lambda _, k: p
        assert mock_bot.check_files_exist(["test.jpg"]) == {"test.jpg": True}

    def test_already_prefixed(self, mock_bot, mock_page):
        p = mock_page(exists=True)
        mock_bot.site.pages.__getitem__ = lambda _, k: p
        assert mock_bot.check_files_exist(["File:x.png"]) == {"File:x.png": True}


class TestGetBotSingleton:
    def test_same_instance(self):
        import fandom_bot
        fandom_bot._BOT_INSTANCE = None
        try:
            with patch.object(fandom_bot.FandomBot, '__init__', return_value=None) as mi:
                b1 = fandom_bot.FandomBot.get_bot()
                b2 = fandom_bot.FandomBot.get_bot()
                assert b1 is b2
                assert mi.call_count == 1
        finally:
            fandom_bot._BOT_INSTANCE = None


class TestGetBotFailure:
    def test_not_cached(self):
        import fandom_bot
        fandom_bot._BOT_INSTANCE = None
        count = [0]
        def fail(self, *a, **kw):
            count[0] += 1
            raise ValueError("fail")
        try:
            with patch.object(fandom_bot.FandomBot, '__init__', fail):
                for _ in range(2):
                    with pytest.raises(ValueError):
                        fandom_bot.FandomBot.get_bot()
            assert count[0] == 2
            assert fandom_bot._BOT_INSTANCE is None
        finally:
            fandom_bot._BOT_INSTANCE = None


class TestEditPageByName:
    def test_wraps_get_page_and_edit(self, mock_bot, mock_page):
        p = mock_page(name="X", exists=True)
        mock_bot.site.pages.__getitem__ = lambda _, k: p
        with patch.object(mock_bot, 'edit_page') as me:
            mock_bot.edit_page_by_name("X", "content", "sum")
            me.assert_called_once_with(p, "content", "sum")