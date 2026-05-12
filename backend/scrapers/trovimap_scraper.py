# Trovimap scraper - combines div.listing__container (price/details) + JSON-LD (geo/address)

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

BASE_URL = "https://www.trovimap.com"

CITY_SLUGS: dict[str, str] = {
    "madrid": "Madrid",
    "barcelona": "Barcelona",
    "valencia": "Valencia",
    "sevilla": "Sevilla",
    "bilbao": "Bilbao",
    "zaragoza": "Zaragoza",
    "malaga": "Malaga",
    "alicante": "Alicante",
    "murcia": "Murcia",
    "almeria": "Almeria",
    "almería": "Almeria",
    "granada": "Granada",
    "cordoba": "Cordoba",
    "valladolid": "Valladolid",
    "vigo": "Vigo",
    "gijon": "Gijon",
    "vitoria": "Vitoria",
    "santander": "Santander",
    "pamplona": "Pamplona",
    "salamanca": "Salamanca",
}


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


class TrovimapScraper(BaseScraper):
    platform = "trovimap"

    def _fetch(self, url: str) -> str:
        scraper = cloudscraper.create_scraper(
            browser={"browser": "chrome", "platform": "windows", "mobile": False}
        )
        resp = scraper.get(url, timeout=15)
        resp.encoding = "utf-8"
        return resp.text

    def search(self, filters: SearchFilters) -> list[Property]:
        city = filters.city.lower()
        slug = CITY_SLUGS.get(city, city.capitalize())

        properties: list[Property] = []

        for page in range(1, 4):
            url = f"{BASE_URL}/venta/vivienda/{slug}"
            if page > 1:
                url += f"?page={page}"

            try:
                html = self._fetch(url)
                page_props = self._parse(html, filters)
                if not page_props:
                    break

                properties.extend(page_props)
                time.sleep(1.0)
            except Exception as e:
                logger.error("Error fetching trovimap page %d: %s", page, e)
                break

        return properties

    def _parse(self, html: str, filters: SearchFilters) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")

        # Build geo/address lookup from JSON-LD keyed by the @id (e.g. "349169-40765417")
        geo_by_id: dict[str, dict] = {}
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.get_text())
                if not isinstance(data, list):
                    continue
                for item in data:
                    if item.get("@type") not in (
                        "Apartment", "House", "SingleFamilyResidence",
                        "Residence", "RealEstateListing",
                    ):
                        continue
                    item_id = item.get("@id", "")
                    geo_by_id[item_id] = {
                        "lat": item.get("geo", {}).get("latitude"),
                        "lon": item.get("geo", {}).get("longitude"),
                        "locality": item.get("address", {}).get("addressLocality"),
                        "rooms": item.get("numberOfRooms"),
                        "name": item.get("name"),
                        "description": item.get("description"),
                    }
            except Exception:
                pass

        # Parse HTML cards
        cards = soup.select("div.listing__container")
        properties: list[Property] = []

        for card in cards:
            try:
                prop = self._parse_card(card, filters.city, geo_by_id)
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
                logger.debug("Error parsing trovimap card: %s", e)

        return properties

    def _parse_card(self, card, city: str, geo_by_id: dict) -> Property | None:
        link = card.find("a", href=re.compile(r"/inmueble/"))
        if not link:
            return None

        href = link["href"]
        prop_url = BASE_URL + href if href.startswith("/") else href
        prop_id = hashlib.md5(prop_url.encode()).hexdigest()[:12]

        # The @id in JSON-LD is the path segment after /inmueble/
        json_ld_id = href.split("/inmueble/")[-1].strip("/")
        geo_data = geo_by_id.get(json_ld_id, {})

        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        full_text = " | ".join(texts)

        # Price: first h4 with € sign
        price_h4 = card.find("h4")
        price = self._extract_price(price_h4.get_text() if price_h4 else full_text)

        # Size: "95 m²"
        size_m2 = self._extract_float(r"(\d+(?:[.,]\d+)?)\s*m²", full_text)

        # Rooms: geo_data has it from JSON-LD, fallback to HTML icon count
        rooms = geo_data.get("rooms")
        if rooms is None:
            # Trovimap shows rooms as a number right after the size
            m = re.search(r"m²\s*\|\s*(\d+)\s*\|", full_text)
            rooms = int(m.group(1)) if m else None

        # Title and description come from JSON-LD (most reliable)
        title = geo_data.get("name")
        description = geo_data.get("description")

        # Fallback: pick longest non-price text from HTML
        if not title:
            for t in texts:
                if (len(t) > 10 and "€" not in t and "m²" not in t
                        and "Contactar" not in t and "Compra" not in t
                        and "Agente" not in t):
                    title = t
                    break
        if not title:
            title = f"Propiedad en {city}"

        # Address from JSON-LD locality
        locality = geo_data.get("locality")
        address = locality or city

        # Image: cards use lazy-loading — real URL may be in data-src / data-lazy / data-original
        images: list[str] = []
        for img in card.find_all("img"):
            src = (
                img.get("data-src")
                or img.get("data-lazy")
                or img.get("data-original")
                or img.get("src", "")
            )
            if src and src.startswith("http") and "svg" not in src and not src.startswith("data:"):
                images.append(src)
                break

        has_elevator = bool(re.search(r"ascensor", full_text, re.IGNORECASE))
        has_parking = bool(re.search(r"garaje|parking", full_text, re.IGNORECASE))
        has_terrace = bool(re.search(r"terraza", full_text, re.IGNORECASE))

        return Property(
            id=prop_id,
            title=title,
            price=price,
            size_m2=size_m2,
            rooms=int(rooms) if rooms is not None else None,
            bathrooms=None,
            floor=None,
            address=address,
            district=locality,
            city=city,
            lat=geo_data.get("lat"),
            lon=geo_data.get("lon"),
            url=prop_url,
            platform=self.platform,
            images=images,
            description=description,
            has_elevator=has_elevator,
            has_parking=has_parking,
            has_terrace=has_terrace,
            is_new_development=None,
            published_at=None,
            scraped_at=self.now_iso(),
        )

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
    def _extract_float(pattern: str, text: str) -> float | None:
        m = re.search(pattern, text, re.IGNORECASE)
        if not m:
            return None
        return float(m.group(1).replace(",", "."))
