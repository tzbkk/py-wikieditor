"""pytest fixtures for testing FandomBot without network calls"""
import pytest
from unittest.mock import MagicMock, PropertyMock
import sys
import os

# Ensure repo root is on path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def mock_site():
    """Mock mwclient.Site — supports .pages[name], .categories[name], .login(), .allpages(prefix=)"""
    site = MagicMock()
    # .pages[name] returns a mock page; configure per-test via mock_page factory
    site.pages = MagicMock()
    site.pages.__getitem__ = lambda self, key: MagicMock()  # Override per-test
    site.categories = MagicMock()
    site.login = MagicMock(return_value=None)
    site.allpages = MagicMock(return_value=iter([]))
    return site


@pytest.fixture
def mock_page():
    """Factory fixture — returns a function that creates configured mock pages"""
    def _make(name="TestPage", exists=True, text="test content"):
        page = MagicMock()
        page.name = name
        page.exists = exists
        page.text = MagicMock(return_value=text)
        page.edit = MagicMock()
        page.move = MagicMock()
        return page
    return _make


@pytest.fixture
def mock_bot(mock_site, monkeypatch):
    """FandomBot instance with mocked mwclient.Site — NO real network"""
    # Create env vars so _load_from_env doesn't fail
    monkeypatch.setenv("FANDOM_DOMAIN", "test.fandom.com")
    monkeypatch.setenv("FANDOM_USERNAME", "test@test")
    monkeypatch.setenv("FANDOM_PASSWORD", "testpass")
    monkeypatch.setenv("CONVERSION_MODE", "t2s")

    # Save original os.path.exists
    original_exists = os.path.exists

    # Mock os.path.exists to return False for .env and True for config.json
    def mock_exists(path):
        if path == '.env':
            return False
        if path == 'config.json':
            return True
        return original_exists(path)
    monkeypatch.setattr(os.path, 'exists', mock_exists)

    # Mock open() to return a file-like object for config.json
    import json
    mock_config = {
        'site': {'domain': 'test.fandom.com', 'path': '/'},
        'auth': {'username': 'test@test', 'password': 'testpass'},
        'conversion': {'mode': 't2s'}
    }
    from io import StringIO
    original_open = open

    def mock_open(path, *args, **kwargs):
        if path == 'config.json':
            return StringIO(json.dumps(mock_config))
        return original_open(path, *args, **kwargs)
    monkeypatch.setattr('builtins.open', mock_open)

    import mwclient
    monkeypatch.setattr(mwclient, "Site", lambda *args, **kwargs: mock_site)

    # Mock OpenCC to avoid needing real conversion config
    try:
        import fandom_bot
        monkeypatch.setattr(fandom_bot, "OpenCC", lambda mode: MagicMock())
    except ImportError:
        pass

    from fandom_bot import FandomBot
    bot = FandomBot()
    bot.site = mock_site
    return bot


@pytest.fixture
def isolated_env(tmp_path, monkeypatch):
    """Copy .env.example to temp dir, set test credentials"""
    monkeypatch.setenv("FANDOM_DOMAIN", "test.fandom.com")
    monkeypatch.setenv("FANDOM_USERNAME", "test@test")
    monkeypatch.setenv("FANDOM_PASSWORD", "testpass")
    monkeypatch.setenv("CONVERSION_MODE", "t2s")
    monkeypatch.chdir(tmp_path)
    return tmp_path