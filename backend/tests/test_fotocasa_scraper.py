"""Focused tests for Fotocasa zone routing."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from models.property import SearchFilters
from scrapers.fotocasa_scraper import FotocasaScraper


def test_fotocasa_search_uses_toyo_zone_slug() -> None:
    with patch("scrapers.fotocasa_scraper.cloudscraper.create_scraper"):
        scraper = FotocasaScraper()

    scraper._settings.MAX_PAGES = 1
    scraper._fetch = MagicMock(return_value="<html><body></body></html>")
    scraper._parse = MagicMock(return_value=[])

    filters = SearchFilters(city="almeria", district="Toyo", platforms=["fotocasa"])

    scraper.search(filters)

    called_url = scraper._fetch.call_args.args[0]
    assert "almeria/el-toyo-cabo-de-gata" in called_url
