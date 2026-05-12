"""
Fotocasa scraper using cloudscraper + BeautifulSoup.
Parses article cards from server-rendered HTML — no API key required.
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

BASE_URL = "https://www.fotocasa.es"

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


class FotocasaScraper(BaseScraper):
    platform = "fotocasa"

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
                logger.warning("Fotocasa fetch error page %d: %s", page, exc)
                break

            page_props = self._parse(html, filters)
            if not page_props:
                break

            properties.extend(page_props)

            if len(page_props) < 20:
                break

            time.sleep(1.2)

        return properties

    # ------------------------------------------------------------------

    def _build_url(self, city_slug: str, filters: SearchFilters, page: int) -> str:
        # Note: fotocasa does not properly support district filtering
        # Using "todas-las-zonas" to fetch all zones, filtering is unreliable
        base = f"{BASE_URL}/es/comprar/viviendas/{city_slug}/todas-las-zonas/l"
        params: list[str] = []
        if filters.price_max is not None:
            params.append(f"maxPrice={int(filters.price_max)}")
        if filters.price_min is not None:
            params.append(f"minPrice={int(filters.price_min)}")
        if filters.rooms_min is not None:
            params.append(f"minRooms={filters.rooms_min}")
        if page > 1:
            params.append(f"page={page}")
        qs = ("?" + "&".join(params)) if params else ""
        return base + qs

    def _fetch(self, url: str) -> str:
        resp = self._scraper.get(url, timeout=self._settings.REQUEST_TIMEOUT)
        resp.raise_for_status()
        resp.encoding = "utf-8"
        return resp.text

    def _parse(self, html: str, filters: SearchFilters) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        # Articles with a link pointing to a property detail page
        articles = soup.select("article")
        properties: list[Property] = []

        for article in articles:
            try:
                prop = self._parse_article(article, filters.city)
                if prop is None:
                    continue
                # Client-side filtering for fields not supported in URL
                if filters.size_min and prop.size_m2 and prop.size_m2 < filters.size_min:
                    continue
                if filters.size_max and prop.size_m2 and prop.size_m2 > filters.size_max:
                    continue
                properties.append(prop)
            except Exception as exc:
                logger.debug("Fotocasa parse error: %s", exc)

        return properties

    def _parse_article(self, article: Tag, city: str) -> Property | None:
        # Must contain a link to a property detail page
        link_tag = article.find("a", href=re.compile(r"/es/comprar/"))
        if not link_tag:
            return None

        href = link_tag["href"]
        # Skip banners / agency links (they don't end with /d or a numeric id)
        if not re.search(r"(/d$|/\d+$|/\d+/d$)", href):
            return None
        url = BASE_URL + href if href.startswith("/") else href
        prop_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Flatten text for regex extraction
        text = " | ".join(t.strip() for t in article.stripped_strings if t.strip())

        price = self._extract_price(text)
        if price is None:
            return None  # skip promotions / non-property cards

        rooms = self._extract_int(r"(\d+)\s*hab", text)
        bathrooms = self._extract_int(r"(\d+)\s*baño", text)
        size_m2 = self._extract_float(r"(\d+(?:[.,]\d+)?)\s*m²", text)
        floor_raw = self._extract_str(r"(\d+[aªº]?\s*[Pp]lanta)", text)

        # Title: look for the link text or a heading
        heading = article.select_one("h2, h3, [class*=title], [class*=Title]")
        if heading:
            title = heading.get_text(strip=True)
        else:
            title = link_tag.get_text(strip=True) or url

        # Images
        images: list[str] = []
        img_tags = article.select("img[src]")
        for img in img_tags:
            src = img.get("src", "")
            if src.startswith("http") and not src.endswith(".svg"):
                images.append(src)
                break  # first image is enough

        # Location from href: /es/comprar/vivienda/{city-slug}/...
        location_match = re.search(r"/es/comprar/(?:vivienda|obra-nueva|piso|casa)/([^/]+)/", href)
        district = location_match.group(1).replace("-", " ").title() if location_match else None

        has_elevator = bool(re.search(r"ascensor", text, re.IGNORECASE))
        has_parking = bool(re.search(r"garaje|parking", text, re.IGNORECASE))
        has_terrace = bool(re.search(r"terraza", text, re.IGNORECASE))

        return Property(
            id=prop_id,
            title=title or f"Propiedad en {district or city}",
            price=price,
            size_m2=size_m2,
            rooms=rooms,
            bathrooms=bathrooms,
            floor=floor_raw,
            district=district,
            city=city,
            url=url,
            platform=self.platform,
            images=images,
            has_elevator=has_elevator,
            has_parking=has_parking,
            has_terrace=has_terrace,
        )

    # ------------------------------------------------------------------

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
