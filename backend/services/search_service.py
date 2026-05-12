"""
Orchestrates scrapers, applies filters, and manages caching.

To add a new platform:
1. Implement the scraper in scrapers/<platform>_scraper.py
2. Import it below and add to AVAILABLE_SCRAPERS
"""

from __future__ import annotations

import logging

from models.property import Property, SearchFilters
from scrapers.idealista_scraper import IdealistaScraper
from scrapers.fotocasa_scraper import FotocasaScraper
from scrapers.pisos_scraper import PisosScraper
from scrapers.habitaclia_scraper import HabitacliaScraper
from scrapers.yaencontre_scraper import YaencontreScraper
from scrapers.trovimap_scraper import TrovimapScraper

from services.cache_service import CacheService

logger = logging.getLogger(__name__)

# Registry of active scrapers by platform name
AVAILABLE_SCRAPERS: dict[str, type] = {
    "idealista": IdealistaScraper,
    "fotocasa": FotocasaScraper,
    "pisos": PisosScraper,
    "habitaclia": HabitacliaScraper,
    "yaencontre": YaencontreScraper,
    "trovimap": TrovimapScraper,
}


class SearchService:
    def __init__(self) -> None:
        self._cache = CacheService()

    def search(self, filters: SearchFilters) -> tuple[list[Property], list[str]]:
        """Run search across requested platforms, using cache when available.

        Returns:
            Tuple of (properties list, list of platforms actually queried)
        """
        requested = [p for p in filters.platforms if p in AVAILABLE_SCRAPERS]
        if not requested:
            logger.warning("No available scrapers for platforms: %s", filters.platforms)
            return [], []

        cache_key = CacheService.make_key(
            {**filters.model_dump(), "platforms": sorted(requested)}
        )
        cached = self._cache.get(cache_key)
        if cached is not None:
            logger.info("Cache hit for key %s", cache_key[:8])
            return cached, requested

        properties: list[Property] = []
        queried: list[str] = []

        for platform in requested:
            scraper_cls = AVAILABLE_SCRAPERS[platform]
            scraper = scraper_cls()
            if not scraper.is_available():
                logger.warning("Scraper %s is not available (missing credentials?)", platform)
                continue
            try:
                results = scraper.search(filters)
                properties.extend(results)
                queried.append(platform)
                logger.info("Scraped %d properties from %s", len(results), platform)
            except Exception as exc:
                logger.error("Scraper %s failed: %s", platform, exc)

        # Deduplicate: prefer URL as key, fallback to (title, price, address)
        seen: set[str] = set()
        unique: list[Property] = []
        for prop in properties:
            key = prop.url or f"{prop.title}|{prop.price}|{prop.address}"
            if key not in seen:
                seen.add(key)
                unique.append(prop)
        properties = unique

        # Sort by price ascending (nulls last)
        properties.sort(key=lambda p: p.price if p.price is not None else float("inf"))

        if properties:
            self._cache.set(cache_key, properties)

        return properties, queried

    @staticmethod
    def available_platforms() -> list[dict]:
        return [
            {
                "key": platform,
                "name": platform.capitalize(),
                "available": AVAILABLE_SCRAPERS[platform]().is_available(),
            }
            for platform in AVAILABLE_SCRAPERS
        ]
