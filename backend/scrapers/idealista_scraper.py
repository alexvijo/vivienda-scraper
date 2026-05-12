"""
Idealista scraper using cloudscraper + BeautifulSoup.

NOTE: This scraper works without an API key by parsing Idealista's HTML.
When the official API key is available, switch to idealista_api_client.py instead.

Usage of the official API (once key is obtained):
    - Sign up at https://developers.idealista.com/
    - Set env vars: IDEALISTA_API_KEY and IDEALISTA_API_SECRET
    - Import IdealstaApiClient from idealista_api_client.py and use it in search_service.py
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from urllib.parse import urlencode

import cloudscraper
from bs4 import BeautifulSoup

from config.settings import get_settings
from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

CITY_SLUGS: dict[str, str] = {
    "madrid": "madrid",
    "barcelona": "barcelona",
    "valencia": "valencia",
    "sevilla": "sevilla",
    "bilbao": "bilbao",
    "zaragoza": "zaragoza",
    "malaga": "malaga",
    "alicante": "alicante",
    "murcia": "murcia",
    "almeria": "almeria",
    "almería": "almeria",
    "granada": "granada",
    "cordoba": "cordoba",
    "valladolid": "valladolid",
    "vigo": "vigo",
    "gijon": "gijon",
    "vitoria": "vitoria-gasteiz",
    "santander": "santander",
    "pamplona": "pamplona",
    "salamanca": "salamanca",
}

BASE_URL = "https://www.idealista.com"


class IdealistaScraper(BaseScraper):
    platform = "idealista"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    def search(self, filters: SearchFilters) -> list[Property]:
        properties: list[Property] = []
        city_slug = CITY_SLUGS.get(filters.city.lower(), filters.city.lower())

        for page in range(1, self._settings.MAX_PAGES + 1):
            url = self._build_url(city_slug, filters, page)
            try:
                html = self._fetch(url)
            except Exception as exc:
                logger.warning("Idealista fetch error page %d: %s", page, exc)
                break

            page_props = self._parse(html, filters.city)
            if not page_props:
                break

            properties.extend(page_props)
            time.sleep(1.5)  # polite delay

        return properties

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_url(self, city_slug: str, filters: SearchFilters, page: int) -> str:
        path = f"/venta-viviendas/{city_slug}/"
        params: dict[str, str] = {}

        if filters.price_max is not None:
            params["preciomax"] = str(int(filters.price_max))
        if filters.price_min is not None:
            params["preciomin"] = str(int(filters.price_min))
        if filters.rooms_min is not None:
            params["habitaciones"] = str(filters.rooms_min)
        if filters.size_min is not None:
            params["superficiemin"] = str(int(filters.size_min))
        if filters.size_max is not None:
            params["superficiemax"] = str(int(filters.size_max))

        if page > 1:
            path = path.rstrip("/") + f"/pagina-{page}.htm"
        else:
            path = path.rstrip("/") + ".htm"

        qs = ("?" + urlencode(params)) if params else ""
        return BASE_URL + path + qs

    def _fetch(self, url: str) -> str:
        resp = self._scraper.get(url, timeout=self._settings.REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp.text

    def _parse(self, html: str, city: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        items = soup.select("article.item")
        properties: list[Property] = []

        for item in items:
            try:
                prop = self._parse_item(item, city)
                if prop:
                    properties.append(prop)
            except Exception as exc:
                logger.debug("Error parsing item: %s", exc)

        return properties

    def _parse_item(self, item: BeautifulSoup, city: str) -> Property | None:
        # Title & URL
        title_tag = item.select_one("a.item-link")
        if not title_tag:
            return None
        title = title_tag.get_text(strip=True)
        relative_url = title_tag.get("href", "")
        url = BASE_URL + relative_url if relative_url.startswith("/") else relative_url

        # Generate stable ID from URL
        prop_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Price
        price = None
        price_tag = item.select_one(".item-price")
        if price_tag:
            price_text = price_tag.get_text(strip=True)
            price = self._parse_number(price_text)

        # Details (rooms, size)
        rooms: int | None = None
        size_m2: float | None = None
        detail_items = item.select(".item-detail")
        for detail in detail_items:
            text = detail.get_text(strip=True).lower()
            if "hab" in text:
                rooms = int(self._parse_number(text) or 0) or None
            elif "m²" in text or "m2" in text:
                size_m2 = self._parse_number(text)

        # Image
        images: list[str] = []
        img = item.select_one("img.item-multimedia")
        if img:
            src = img.get("src") or img.get("data-src")
            if src:
                images.append(src)

        # Address / district
        address_tag = item.select_one(".item-detail-char .ellipsis") or item.select_one(
            "[class*='item-address']"
        )
        address = address_tag.get_text(strip=True) if address_tag else None

        return Property(
            id=prop_id,
            title=title,
            price=price,
            size_m2=size_m2,
            rooms=rooms,
            address=address,
            city=city,
            url=url,
            platform=self.platform,
            images=images,
        )

    @staticmethod
    def _parse_number(text: str) -> float | None:
        cleaned = re.sub(r"[^\d,.]", "", text).replace(",", ".")
        # Remove trailing dots
        cleaned = cleaned.strip(".")
        try:
            return float(cleaned)
        except ValueError:
            return None
