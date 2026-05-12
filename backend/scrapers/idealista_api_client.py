"""
Idealista Official API Client — PENDING API KEY

This module will replace IdealistaScraper once the official API key is obtained.

HOW TO ACTIVATE:
1. Request access at https://developers.idealista.com/
2. Once approved, set in your .env:
       IDEALISTA_API_KEY=<your_api_key>
       IDEALISTA_API_SECRET=<your_api_secret>
3. In backend/services/search_service.py, replace:
       from scrapers.idealista_scraper import IdealistaScraper
   with:
       from scrapers.idealista_api_client import IdealstaApiClient as IdealistaScraper

Reference implementation: https://github.com/yagueto/idealista-api
"""

from __future__ import annotations

import logging

from config.settings import get_settings
from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


class IdealstaApiClient(BaseScraper):
    """
    Wrapper around the official Idealista API.
    Requires IDEALISTA_API_KEY and IDEALISTA_API_SECRET environment variables.

    Based on yagueto/idealista-api (MIT):
        pip install git+https://github.com/yagueto/idealista-api.git
    """

    platform = "idealista"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_available(self) -> bool:
        return bool(self._settings.IDEALISTA_API_KEY and self._settings.IDEALISTA_API_SECRET)

    def search(self, filters: SearchFilters) -> list[Property]:
        if not self.is_available():
            raise RuntimeError(
                "Idealista API key not configured. "
                "Set IDEALISTA_API_KEY and IDEALISTA_API_SECRET in .env, "
                "or use IdealistaScraper (HTML scraping) instead."
            )

        # --- Activate when yagueto/idealista-api is installed ---
        # from idealista_api import Idealista, Search
        #
        # client = Idealista(
        #     api_key=self._settings.IDEALISTA_API_KEY,
        #     api_secret=self._settings.IDEALISTA_API_SECRET,
        # )
        # request = Search(
        #     country="es",
        #     location_id=_city_to_location_id(filters.city),
        #     property_type="homes",
        #     operation="sale",
        #     max_items=50,
        #     num_page=filters.page,
        #     max_price=filters.price_max,
        #     min_price=filters.price_min,
        #     min_rooms=filters.rooms_min,
        #     min_size=filters.size_min,
        # )
        # response = client.query(request)
        # return [_to_property(item) for item in response.element_list]

        raise NotImplementedError("Activate the API client block above once key is available.")
