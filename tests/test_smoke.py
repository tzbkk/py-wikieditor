"""Smoke tests verifying pytest infrastructure works"""


def test_mock_bot_exists(mock_bot):
    assert mock_bot is not None
    assert mock_bot.site is not None


def test_mock_page_factory(mock_page):
    page = mock_page(name="Test", exists=True, text="hello")
    assert page.name == "Test"
    assert page.exists is True
    assert page.text() == "hello"


def test_mock_site_pages_accessible(mock_site):
    assert mock_site.pages is not None
    assert mock_site.login is not None