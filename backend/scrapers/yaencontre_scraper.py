# Yaencontre scraper - parses window.__INITIAL_STATE__ base64 JSON

import base64
import hashlib
import json
import logging
import re
import time
import unicodedata

import cloudscraper
from bs4 import BeautifulSoup

from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)

BASE_URL = "https://www.yaencontre.com"
IMAGE_BASE = "https://static.yaencontre.com/fotos/"

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
    "vitoria": "vitoria",
    "santander": "santander",
    "pamplona": "pamplona",
    "salamanca": "salamanca",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


class YaencontreScraper(BaseScraper):
    platform = "yaencontre"

    def _fetch(self, url: str) -> str:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        resp = scraper.get(url, timeout=15)
        resp.encoding = "utf-8"
        return resp.text

    def search(self, filters: SearchFilters) -> list[Property]:
        city = filters.city.lower()
        slug = CITY_SLUGS.get(city, city)

        properties: list[Property] = []

        for page in range(1, 4):
            url = f"{BASE_URL}/venta/pisos/{slug}"
            if page > 1:
                url += f"?page={page}"

            try:
                html = self._fetch(url)
                items = self._extract_items(html)
                if not items:
                    break

                for item_data in items:
                    try:
                        prop = self._parse_item(item_data, filters.city)
                        if prop is None:
                            continue

                        if filters.price_max and prop.price and prop.price > filters.price_max:
                            continue
                        if filters.price_min and prop.price and prop.price < filters.price_min:
                            continue
                        if filters.rooms_min and prop.rooms and prop.rooms < filters.rooms_min:
                            continue
                        if filters.size_min and prop.size_m2 and prop.size_m2 < filters.size_min:
                            continue
                        if filters.size_max and prop.size_m2 and prop.size_m2 > filters.size_max:
                            continue

                        if filters.district:
                            search_term = _normalize(filters.district)
                            searchable = _normalize(" ".join([
                                prop.title or "",
                                prop.address or "",
                                prop.district or "",
                                prop.description or "",
                                prop.url or "",
                            ]))
                            if search_term not in searchable:
                                continue

                        properties.append(prop)
                    except Exception as e:
                        logger.debug("Error parsing yaencontre item: %s", e)

                time.sleep(1.0)
            except Exception as e:
                logger.error("Error fetching yaencontre page %d: %s", page, e)
                break

        return properties

    def _extract_items(self, html: str) -> list[dict]:
        soup = BeautifulSoup(html, "lxml")
        for script in soup.find_all("script", src=False):
            txt = script.get_text()
            m = re.search(r"window\.__INITIAL_STATE__\s*=\s*JSON\.parse\(atob\([\"'](.*?)[\"']\)", txt)
            if not m:
                continue
            try:
                decoded = base64.b64decode(m.group(1)).decode("utf-8")
                data = json.loads(decoded)
                results = data.get("results", {})
                by_id = results.get("currentPageItems", {}).get("byId", {})
                sorted_ids = results.get("currentPageItems", {}).get("sortedItems", [])
                return [by_id[k] for k in sorted_ids if k in by_id]
            except Exception as e:
                logger.debug("Failed to decode yaencontre state: %s", e)
        return []

    def _parse_item(self, item_data: dict, city: str) -> Property | None:
        item = item_data.get("item", item_data)

        item_url = item.get("url")
        ref = item.get("reference") or item.get("id", "")
        if item_url:
            prop_url = BASE_URL + item_url if item_url.startswith("/") else item_url
        elif ref:
            prop_url = f"{BASE_URL}/inmueble/{ref}"
        else:
            return None

        prop_id = hashlib.md5(prop_url.encode()).hexdigest()[:12]
        title = item.get("title") or f"Propiedad en {city}"
        description = item.get("description")
        price = item.get("price")
        size_m2 = item.get("area")
        rooms = item.get("rooms")
        bathrooms = item.get("bathrooms")

        address_data = item.get("address", {})
        full_address = address_data.get("qualifiedName") or address_data.get("street")
        geo = address_data.get("geoLocation", {})
        lat = geo.get("lat")
        lon = geo.get("lon")

        # district = first part of qualifiedName (e.g. "Retamar, Almería, ...")
        district = None
        if full_address:
            parts = [p.strip() for p in full_address.split(",")]
            if parts:
                district = parts[0]

        # Images
        images: list[str] = []
        for img in item.get("images", []):
            slug = img.get("slug") or img.get("url", "")
            if slug:
                src = slug if slug.startswith("http") else IMAGE_BASE + slug
                images.append(src)
                if len(images) >= 3:
                    break

        price_per_m2 = item.get("squareMeterPrice")

        return Property(
            id=prop_id,
            title=title,
            price=float(price) if price is not None else None,
            price_per_m2=float(price_per_m2) if price_per_m2 is not None else None,
            size_m2=float(size_m2) if size_m2 is not None else None,
            rooms=int(rooms) if rooms is not None else None,
            bathrooms=int(bathrooms) if bathrooms is not None else None,
            floor=None,
            address=full_address,
            district=district,
            city=city,
            lat=lat,
            lon=lon,
            url=prop_url,
            platform=self.platform,
            images=images,
            description=description,
            has_elevator=None,
            has_parking=None,
            has_terrace=None,
            is_new_development=item.get("family") == "NEW_DEVELOPMENT",
            published_at=None,
            scraped_at=self.now_iso(),
        )
