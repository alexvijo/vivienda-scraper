# Habitaclia scraper

import re
import time
import unicodedata

import cloudscraper
from bs4 import BeautifulSoup

from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


class HabitacliaScraper(BaseScraper):
    platform = "habitaclia"
    base_url = "https://www.habitaclia.com"

    def is_available(self) -> bool:
        return True

    # (city_normalized, province_slug) — used to build area URL
    city_slugs = {
        "madrid":     ("madrid",     "madrid"),
        "barcelona":  ("barcelona",  "barcelona"),
        "valencia":   ("valencia",   "valencia"),
        "sevilla":    ("sevilla",    "sevilla"),
        "bilbao":     ("bilbao",     "vizcaya"),
        "zaragoza":   ("zaragoza",   "zaragoza"),
        "malaga":     ("malaga",     "malaga"),
        "alicante":   ("alicante",   "alicante"),
        "murcia":     ("murcia",     "murcia"),
        "almeria":    ("almeria",    "almeria"),
        "almería":    ("almeria",    "almeria"),
        "granada":    ("granada",    "granada"),
        "cordoba":    ("cordoba",    "cordoba"),
        "valladolid": ("valladolid", "valladolid"),
        "vigo":       ("vigo",       "pontevedra"),
        "gijon":      ("gijon",      "asturias"),
        "vitoria":    ("vitoria",    "alava"),
        "santander":  ("santander",  "cantabria"),
        "pamplona":   ("pamplona",   "navarra"),
        "salamanca":  ("salamanca",  "salamanca"),
    }

    def _build_url(self, city: str, page: int) -> str:
        key = _normalize(city)
        city_slug, province_slug = self.city_slugs.get(key, (key, key))
        base = f"{self.base_url}/comprar-vivienda-en-area_de_{city_slug}/provincia_{province_slug}/selarea.htm"
        if page > 1:
            return base + f"?pagina={page}"
        return base

    def _fetch(self, url: str) -> str:
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=15)
        resp.encoding = "utf-8"
        return resp.text

    def search(self, filters: SearchFilters) -> list[Property]:
        city = filters.city.strip()
        properties = []

        for page in range(1, 4):
            page_url = self._build_url(city, page)
            self.logger.debug("Habitaclia fetching: %s", page_url)

            try:
                html = self._fetch(page_url)
                soup = BeautifulSoup(html, "lxml")

                # Try multiple article selectors — Habitaclia changes markup occasionally
                articles = (
                    soup.find_all("article", class_="lnk-anuncio") or
                    soup.find_all("article") or
                    soup.find_all("li", class_="js-list-item")
                )
                if not articles:
                    self.logger.debug("Habitaclia: no articles on page %d", page)
                    break

                for article in articles:
                    try:
                        prop = self._parse_article(article, filters)
                        if prop:
                            properties.append(prop)
                    except Exception as e:
                        self.logger.debug("Error parsing Habitaclia property: %s", e)

                time.sleep(1.0)
            except Exception as e:
                self.logger.error("Habitaclia error on page %d: %s", page, e)
                break

        return properties

    def _parse_article(self, article, filters: SearchFilters) -> Property | None:
        # Title
        title_el = article.find("h2") or article.find("h3")
        title = title_el.get_text(strip=True) if title_el else "Sin título"

        # URL
        link_el = article.find("a", href=True)
        prop_url = link_el["href"] if link_el else ""
        if prop_url and not prop_url.startswith("http"):
            prop_url = self.base_url + prop_url
        if not prop_url:
            return None

        # Price — try several class names
        price = None
        for cls in ("precio", "price", "prop-price"):
            price_el = article.find(class_=cls)
            if price_el:
                price_str = re.sub(r"[^\d]", "", price_el.get_text())
                price = int(price_str) if price_str else None
                break

        # Size
        size_m2 = None
        for cls in ("m2", "size", "prop-size"):
            size_el = article.find(class_=cls)
            if size_el:
                size_str = re.sub(r"[^\d]", "", size_el.get_text())
                size_m2 = int(size_str) if size_str else None
                break

        # Rooms
        rooms = None
        for cls in ("hab", "rooms", "prop-rooms"):
            rooms_el = article.find(class_=cls)
            if rooms_el:
                rooms_str = re.sub(r"[^\d]", "", rooms_el.get_text())
                rooms = int(rooms_str) if rooms_str else None
                break

        # Image
        images = []
        img_el = article.find("img")
        if img_el:
            src = img_el.get("data-src") or img_el.get("src") or ""
            if src and not src.startswith("data:"):
                images.append(src)

        # Address
        address_el = article.find(class_=re.compile(r"zona|address|location"))
        address_text = address_el.get_text(strip=True) if address_el else None

        # Price filters
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

        prop_obj = Property(
            id=prop_url,
            title=title,
            price=price,
            price_per_m2=price / size_m2 if price and size_m2 else None,
            size_m2=size_m2,
            rooms=rooms,
            bathrooms=None,
            floor=None,
            address=address_text,
            district=None,
            city=filters.city,
            lat=None,
            lon=None,
            url=prop_url,
            platform=self.platform,
            images=images,
            description=None,
            has_elevator=None,
            has_parking=None,
            has_terrace=None,
            is_new_development=None,
            published_at=None,
            scraped_at=self.now_iso(),
        )

        # Keyword filter
        if filters.keyword:
            search_term = _normalize(filters.keyword)
            searchable = _normalize(" ".join([
                prop_obj.title or "",
                prop_obj.address or "",
                prop_obj.description or "",
                prop_obj.url or "",
            ]))
            if search_term not in searchable:
                return None

        return prop_obj
