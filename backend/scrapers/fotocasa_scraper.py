"""
Fotocasa scraper.

Fotocasa renders listings client-side, but embeds the first page of results as
a JSON object inside a <script> tag (the largest inline script on the page).
The array is at key "realEstates" and contains ~30 items per page.

URL structure:
  City only:  /es/comprar/viviendas/<city-slug>/todas-las-zonas/l
  With zone:  /es/comprar/viviendas/<city-slug>/<zone-slug>/l
  Page 2+:    ...?page=2&sortType=publicationDate
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import unicodedata

import cloudscraper
from bs4 import BeautifulSoup

from config.settings import get_settings
from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.fotocasa.es"

# city input -> Fotocasa municipality slug used in /es/comprar/viviendas/<slug>/
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
    "almeria": "almeria-capital",
    "almería": "almeria-capital",
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

# normalized district keyword -> Fotocasa zone slug (appended after city slug)
DISTRICT_SLUGS: dict[str, dict[str, str]] = {
    "retamar":    {"city": "almeria-capital", "zone": "retamar"},
    "aguadulce":  {"city": "almeria-capital", "zone": "retamar-aguadulce"},
    "toyo":       {"city": "almeria-capital", "zone": "el-toyo-cabo-de-gata"},
    "el toyo":    {"city": "almeria-capital", "zone": "el-toyo-cabo-de-gata"},
    "cabo de gata": {"city": "almeria-capital", "zone": "el-toyo-cabo-de-gata"},
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _extract_feature(features: list[dict], key: str) -> int | None:
    for f in features:
        if f.get("key") == key:
            v = f.get("value")
            return int(v) if v is not None else None
    return None


class FotocasaScraper(BaseScraper):
    platform = "fotocasa"

    def __init__(self) -> None:
        self._settings = get_settings()

    def _new_scraper(self):
        return cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )

    def search(self, filters: SearchFilters) -> list[Property]:
        city_slug = CITY_SLUGS.get(filters.city.lower(), filters.city.lower())
        zone_slug = None

        if filters.district:
            info = DISTRICT_SLUGS.get(_normalize(filters.district.strip()))
            if info:
                city_slug = info["city"]
                zone_slug = info["zone"]

        properties: list[Property] = []

        for page in range(1, self._settings.MAX_PAGES + 1):
            url = self._build_url(city_slug, zone_slug, filters, page)
            try:
                scraper = self._new_scraper()
                resp = scraper.get(url, timeout=self._settings.REQUEST_TIMEOUT)
                resp.raise_for_status()
                resp.encoding = "utf-8"
                html_text = resp.text
            except Exception as exc:
                logger.warning("Fotocasa fetch error page %d: %s", page, exc)
                break

            listings = self._extract_listings(html_text)
            if not listings:
                break

            for item in listings:
                try:
                    prop = self._parse_item(item, filters)
                    if prop:
                        properties.append(prop)
                except Exception as exc:
                    logger.debug("Fotocasa item parse error: %s", exc)

            if len(listings) < 20:
                break

            time.sleep(1.2)

        return properties

    def _build_url(self, city_slug: str, zone_slug: str | None, filters: SearchFilters, page: int) -> str:
        zone = zone_slug or "todas-las-zonas"
        base = f"{BASE_URL}/es/comprar/viviendas/{city_slug}/{zone}/l"
        params: list[str] = ["sortType=publicationDate"]
        if filters.price_min is not None:
            params.append(f"minPrice={int(filters.price_min)}")
        if filters.price_max is not None:
            params.append(f"maxPrice={int(filters.price_max)}")
        if filters.rooms_min is not None:
            params.append(f"minRooms={filters.rooms_min}")
        if page > 1:
            params.append(f"page={page}")
        return base + "?" + "&".join(params)

    def _extract_listings(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", src=False):
            txt = script.get_text()
            idx = txt.find('"realEstates":[{')
            if idx == -1:
                continue
            arr_start = idx + len('"realEstates":')
            depth = 0
            arr_end = arr_start
            for i, c in enumerate(txt[arr_start:], arr_start):
                if c == "[":
                    depth += 1
                elif c == "]":
                    depth -= 1
                    if depth == 0:
                        arr_end = i + 1
                        break
            try:
                return json.loads(txt[arr_start:arr_end])
            except Exception as exc:
                logger.debug("Fotocasa JSON parse error: %s", exc)
        return []

    def _parse_item(self, item: dict, filters: SearchFilters) -> Property | None:
        detail_path = item.get("detail", {}).get("es-ES", "")
        if not detail_path:
            return None
        url = BASE_URL + detail_path if detail_path.startswith("/") else detail_path
        # Strip tracking params
        url = re.sub(r"\?.*$", "", url)
        prop_id = hashlib.md5(url.encode()).hexdigest()[:12]

        # Price: "650.000 €" -> 650000.0
        price_raw = str(item.get("rawPrice") or item.get("price") or "")
        price = self._parse_price(price_raw)

        features = item.get("features", [])
        rooms = _extract_feature(features, "rooms")
        bathrooms = _extract_feature(features, "bathrooms")
        size_m2 = _extract_feature(features, "surface")
        floor_val = _extract_feature(features, "floor")
        floor = str(floor_val) if floor_val else None

        # Address fields
        addr = item.get("address", {})
        district = addr.get("district") or item.get("location")
        municipality = (addr.get("municipality") or addr.get("city") or "").strip()
        full_address = ", ".join(filter(None, [item.get("location"), municipality]))

        # Coordinates
        coords = item.get("coordinates") or {}
        lat = coords.get("latitude") if isinstance(coords, dict) else None
        lon = coords.get("longitude") if isinstance(coords, dict) else None

        # Images
        images = [
            m["src"] for m in item.get("multimedia", [])
            if m.get("type") == "image" and m.get("src")
        ][:3]

        # Title from location + type
        building_type = item.get("buildingType") or item.get("buildingSubtype") or "Propiedad"
        location_txt = item.get("location") or municipality or filters.city
        title = f"{building_type} en {location_txt}"

        # Client-side filters
        if filters.price_max and price and price > filters.price_max:
            return None
        if filters.price_min and price and price < filters.price_min:
            return None
        if filters.rooms_min and rooms and rooms < filters.rooms_min:
            return None
        if filters.size_min and size_m2 and size_m2 < filters.size_min:
            return None
        if filters.size_max and size_m2 and size_m2 > filters.size_max:
            return None

        # District text filter (when zone slug not used)
        if filters.district:
            search_term = _normalize(filters.district)
            searchable = _normalize(" ".join(filter(None, [
                title, full_address, district or "", item.get("description") or "", url
            ])))
            if search_term not in searchable:
                return None

        return Property(
            id=prop_id,
            title=title,
            price=price,
            size_m2=float(size_m2) if size_m2 else None,
            rooms=rooms,
            bathrooms=bathrooms,
            floor=floor,
            address=full_address or None,
            district=district,
            city=filters.city,
            lat=lat,
            lon=lon,
            url=url,
            platform=self.platform,
            images=images,
            description=(item.get("description") or "")[:500] or None,
            has_elevator=self._has_feature(features, "elevator"),
            has_parking=self._has_feature(features, "parking"),
            has_terrace=self._has_feature(features, "terrace"),
            is_new_development=bool(item.get("isNewConstruction")),
            published_at=None,
            scraped_at=self.now_iso(),
        )

    @staticmethod
    def _parse_price(raw: str) -> float | None:
        if not raw:
            return None
        # rawPrice may be a number already
        try:
            return float(raw)
        except (ValueError, TypeError):
            pass
        # "650.000 €" or "650,000 €"
        m = re.search(r"([\d]{2,}(?:[.,\s]\d{3})*)", str(raw))
        if not m:
            return None
        cleaned = m.group(1).replace(".", "").replace(",", "").replace(" ", "")
        try:
            return float(cleaned)
        except ValueError:
            return None

    @staticmethod
    def _has_feature(features: list[dict], key: str) -> bool | None:
        keys = {f.get("key") for f in features}
        if key in keys:
            return True
        return None
