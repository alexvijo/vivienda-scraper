"""
Pisos.com scraper using cloudscraper + BeautifulSoup.
Parses listing cards from HTML — no API key required.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time

import cloudscraper
from bs4 import BeautifulSoup, Tag

from config.settings import get_settings
from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.pisos.com"

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


class PisosScraper(BaseScraper):
    platform = "pisos"

    def __init__(self) -> None:
        self._settings = get_settings()
        self._scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    def search(self, filters: SearchFilters) -> list[Property]:
        properties: list[Property] = []
        city_slug = CITY_SLUGS.get(filters.city.lower(), filters.city.lower())
        district_slug = filters.district.lower().replace(" ", "-") if filters.district else None

        for page in range(1, self._settings.MAX_PAGES + 1):
            url = self._build_url(city_slug, district_slug, page)
            try:
                html = self._fetch(url)
            except Exception as exc:
                logger.warning("Pisos.com fetch error page %d: %s", page, exc)
                break

            page_props = self._parse(html, filters)
            if not page_props:
                break

            properties.extend(page_props)

            if len(page_props) < 25:
                break  # last page

            time.sleep(1.0)

        return properties

    # ------------------------------------------------------------------

    def _build_url(self, city_slug: str, district_slug: str | None, page: int) -> str:
        # Build location string: "distrito-ciudad" or just "ciudad"
        location = f"{district_slug}-{city_slug}" if district_slug else city_slug

        if page == 1:
            return f"{BASE_URL}/venta/pisos-{location}/"
        return f"{BASE_URL}/venta/pisos-{location}/{page}/"

    def _fetch(self, url: str) -> str:
        resp = self._scraper.get(url, timeout=self._settings.REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def _parse(self, html: str, filters: SearchFilters) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        cards = soup.select("div.ad-preview")
        properties: list[Property] = []

        for card in cards:
            try:
                prop = self._parse_card(card, filters.city)
                if prop is None:
                    continue
                # Client-side price filtering (server filter URL params are unreliable)
                if filters.price_max is not None and prop.price and prop.price > filters.price_max:
                    continue
                if filters.price_min is not None and prop.price and prop.price < filters.price_min:
                    continue
                if filters.rooms_min is not None and prop.rooms is not None and prop.rooms < filters.rooms_min:
                    continue
                if filters.size_min is not None and prop.size_m2 is not None and prop.size_m2 < filters.size_min:
                    continue
                if filters.size_max is not None and prop.size_m2 is not None and prop.size_m2 > filters.size_max:
                    continue
                properties.append(prop)
            except Exception as exc:
                logger.debug("Pisos.com parse error: %s", exc)

        return properties

    def _parse_card(self, card: Tag, city: str) -> Property | None:
        rel_href = card.get("data-lnk-href", "")
        if not rel_href:
            return None

        url = BASE_URL + rel_href
        ad_id = card.get("id", "")
        prop_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Title from img alt
        img_tag = card.select_one("img[alt]")
        title = img_tag["alt"].strip() if img_tag and img_tag.get("alt") else rel_href

        # Image
        images: list[str] = []
        if img_tag:
            src = img_tag.get("src") or img_tag.get("data-src") or ""
            if src and src.startswith("http"):
                images.append(src)

        # Flatten text tokens for regex extraction
        text = " | ".join(t.strip() for t in card.stripped_strings if t.strip())

        price = self._extract_price(text)
        rooms = self._extract_int(r"(\d+)\s*habs?\.?", text)
        bathrooms = self._extract_int(r"(\d+)\s*baños?", text)
        size_m2 = self._extract_float(r"(\d+(?:[.,]\d+)?)\s*m²", text)
        floor = self._extract_str(r"(\d+[aªº]?\s*planta)", text)
        address = self._extract_address(text, title)

        return Property(
            id=prop_id,
            title=title,
            price=price,
            size_m2=size_m2,
            rooms=rooms,
            bathrooms=bathrooms,
            floor=floor,
            address=address,
            city=city,
            url=url,
            platform=self.platform,
            images=images,
        )

    # ------------------------------------------------------------------
    # Regex helpers

    @staticmethod
    def _extract_price(text: str) -> float | None:
        m = re.search(r"([\d]{2,3}(?:[.,\s]\d{3})*)\s*€", text)
        if not m:
            return None
        raw = m.group(1).replace(".", "").replace(",", "").replace(" ", "")
        try:
            return float(raw)
        except ValueError:
            return None

    @staticmethod
    def _extract_int(pattern: str, text: str) -> int | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return int(m.group(1)) if m else None

    @staticmethod
    def _extract_float(pattern: str, text: str) -> float | None:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        return float(m.group(1).replace(",", "."))

    @staticmethod
    def _extract_str(pattern: str, text: str) -> str | None:
        m = re.search(pattern, text, re.IGNORECASE)
        return m.group(1).strip() if m else None

    @staticmethod
    def _extract_address(text: str, fallback: str) -> str:
        # Address usually appears as "Piso en <address>" or "Piso/Casa/Chalet en ..."
        m = re.search(r"(?:piso|casa|chalet|apartamento|ático|local)\s+en\s+(.+?)(?:\s*\|)", text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
        return fallback
