"""
Idealista scraper.

Uses undetected-chromedriver (real Chrome) as fallback when the official API key
is not configured. Idealista deploys DataDome captcha which blocks all plain HTTP
clients and headless Playwright, but undetected-chromedriver bypasses it.

Priority:
  1. IDEALISTA_API_KEY + IDEALISTA_API_SECRET set → use official REST API (not yet impl.)
  2. Neither set → web scraping via undetected-chromedriver

To enable the official API:
    - Sign up at https://developers.idealista.com/
    - Set IDEALISTA_API_KEY and IDEALISTA_API_SECRET in backend/.env
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import time
import unicodedata
import subprocess

from bs4 import BeautifulSoup

from config.settings import get_settings
from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text.lower()).encode("ascii", "ignore").decode()


def _chrome_major_version() -> int | None:
    """Detect the major version of the system Chrome installation."""
    paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    for path in paths:
        try:
            out = subprocess.check_output(
                ["powershell", "-command", f"(Get-Item '{path}').VersionInfo.ProductMajorPart"],
                timeout=5,
            )
            return int(out.strip())
        except Exception:
            continue
    return None


# Idealista URL slug per city.
# Pattern for most cities: {city}-{province} (e.g. cuenca-cuenca, cadiz-cadiz).
# Exceptions: provincial capitals that share name with the province use just the city name,
# or have a special suffix like -municipio or -gasteiz.
CITY_SLUGS: dict[str, str] = {
    "madrid": "madrid",
    "barcelona": "barcelona",
    "valencia": "valencia",
    "sevilla": "sevilla",
    "bilbao": "bilbao",
    "zaragoza": "zaragoza",
    "malaga": "malaga",
    "málaga": "malaga",
    "alicante": "alicante",
    "murcia": "murcia",
    "almeria": "almeria-almeria",
    "almería": "almeria-almeria",
    "granada": "granada",
    "cordoba": "cordoba",
    "córdoba": "cordoba",
    "cadiz": "cadiz-cadiz",
    "cádiz": "cadiz-cadiz",
    "cuenca": "cuenca-cuenca",
    "toledo": "toledo-toledo",
    "guadalajara": "guadalajara-guadalajara",
    "albacete": "albacete-albacete",
    "ciudad real": "ciudad-real-ciudad-real",
    "huelva": "huelva-huelva",
    "jaen": "jaen-jaen",
    "jaén": "jaen-jaen",
    "burgos": "burgos-burgos",
    "leon": "leon-leon",
    "león": "leon-leon",
    "palencia": "palencia-palencia",
    "segovia": "segovia-segovia",
    "soria": "soria-soria",
    "zamora": "zamora-zamora",
    "avila": "avila-avila",
    "ávila": "avila-avila",
    "caceres": "caceres-caceres",
    "cáceres": "caceres-caceres",
    "badajoz": "badajoz-badajoz",
    "lugo": "lugo-lugo",
    "ourense": "ourense-ourense",
    "pontevedra": "pontevedra-pontevedra",
    "vigo": "vigo",
    "gijon": "gijon",
    "gijón": "gijon",
    "vitoria": "vitoria-gasteiz",
    "santander": "santander",
    "pamplona": "pamplona",
    "salamanca": "salamanca",
    "valladolid": "valladolid",
    "tarragona": "tarragona-tarragona",
    "lleida": "lleida-lleida",
    "girona": "girona-girona",
    "castellon": "castellon-de-la-plana-castellon",
    "castellón": "castellon-de-la-plana-castellon",
    "alicante": "alicante-alicante",
    "murcia": "murcia-murcia",
    "cartagena": "cartagena-murcia",
    "tenerife": "tenerife",
    "las palmas": "las-palmas-de-gran-canaria-palmas-las",
    "palma": "palma-de-mallorca-illes-balears",
    "logrono": "logrono-rioja-la",
    "logroño": "logrono-rioja-la",
    "huesca": "huesca-huesca",
    "teruel": "teruel-teruel",
}

DISTRICT_SLUGS: dict[str, str] = {
    "retamar": "almeria/retamar-aguadulce",
    "toyo": "almeria/el-toyo-cabo-de-gata",
    "aguadulce": "almeria/retamar-aguadulce",
    "cabo de gata": "almeria/el-toyo-cabo-de-gata",
    "el toyo": "almeria/el-toyo-cabo-de-gata",
}

BASE_URL = "https://www.idealista.com"

COOKIES_FILE = os.path.join(os.path.dirname(__file__), "..", "idealista_cookies.json")


def _load_saved_cookies() -> list[dict] | None:
    path = os.path.normpath(COOKIES_FILE)
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        logger.warning("Could not read idealista_cookies.json: %s", exc)
        return None


class IdealistaScraper(BaseScraper):
    platform = "idealista"

    def __init__(self) -> None:
        self._settings = get_settings()

    def is_available(self) -> bool:
        # Available via API key OR via web scraping (Chrome must be installed)
        if self._settings.IDEALISTA_API_KEY and self._settings.IDEALISTA_API_SECRET:
            return True
        return _chrome_major_version() is not None

    def search(self, filters: SearchFilters) -> list[Property]:
        if self._settings.IDEALISTA_API_KEY and self._settings.IDEALISTA_API_SECRET:
            # TODO: implement official API client
            return []
        return self._search_web(filters)

    def _search_web(self, filters: SearchFilters) -> list[Property]:
        try:
            import undetected_chromedriver as uc
        except ImportError:
            logger.error("undetected-chromedriver not installed. Run: pip install undetected-chromedriver setuptools")
            return []

        city_norm = _normalize(filters.city)
        # Fallback: most Spanish cities follow the {city}-{city} pattern on Idealista
        city_slug = CITY_SLUGS.get(city_norm, f"{city_norm}-{city_norm}")
        district_slug = DISTRICT_SLUGS.get(_normalize(filters.district or "").strip())
        search_slug = district_slug if district_slug else city_slug

        chrome_version = _chrome_major_version()
        options = uc.ChromeOptions()
        options.add_argument("--lang=es-ES")
        options.add_argument("--window-size=1366,768")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")

        saved_cookies = _load_saved_cookies() if self._settings.IDEALISTA_USE_PROFILE else None
        if saved_cookies:
            logger.info("Idealista: found %d saved cookies, will inject session", len(saved_cookies))

        properties: list[Property] = []
        driver = None
        try:
            kwargs: dict = {"options": options, "headless": False, "use_subprocess": True}
            if chrome_version:
                kwargs["version_main"] = chrome_version
            driver = uc.Chrome(**kwargs)

            # Navigate to home first so the domain is set, then inject cookies.
            driver.get(BASE_URL)
            time.sleep(3)
            self._dismiss_cookies(driver)

            if saved_cookies:
                for cookie in saved_cookies:
                    # UC requires cookies without 'expiry' key type mismatches
                    cookie.pop("sameSite", None)
                    try:
                        driver.add_cookie(cookie)
                    except Exception:
                        pass
                # Reload to activate the injected session
                driver.get(BASE_URL)
                time.sleep(3)
                self._dismiss_cookies(driver)
                logger.info("Idealista: session cookies injected")

            for page in range(1, self._settings.MAX_PAGES + 1):
                url = self._build_url(search_slug, filters, page)
                logger.debug("Idealista fetching: %s", url)
                driver.get(url)
                time.sleep(7)
                self._dismiss_cookies(driver)

                html = driver.page_source
                # If DataDome slider appeared, stop — avoid triggering more challenges
                if "desliza" in html.lower() or "captcha-delivery" in html.lower():
                    logger.warning("Idealista: DataDome slider detected, stopping")
                    break

                page_props = self._parse(html, filters.city)
                if not page_props:
                    break
                properties.extend(page_props)
                # Longer polite delay between pages to avoid rate-limiting
                time.sleep(4)

        except Exception as exc:
            logger.error("Idealista web scraper error: %s", exc)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass

        # Post-filter: price_min, rooms_min, size_min (not supported in Idealista URL)
        if filters.price_min is not None:
            properties = [p for p in properties if p.price is None or p.price >= filters.price_min]
        if filters.rooms_min is not None:
            properties = [p for p in properties if p.rooms is None or p.rooms >= filters.rooms_min]
        if filters.size_min is not None:
            properties = [p for p in properties if p.size_m2 is None or p.size_m2 >= filters.size_min]

        # Post-filter by district keyword if no direct slug was used
        if filters.district and not district_slug:
            term = _normalize(filters.district)
            properties = [
                p for p in properties
                if term in _normalize(" ".join([p.title or "", p.address or "", p.url or ""]))
            ]

        return properties

    def _dismiss_cookies(self, driver) -> None:
        """Click 'Rechazar' or 'Aceptar y continuar' on the Idealista cookie modal if present."""
        try:
            from selenium.webdriver.common.by import By
            from selenium.webdriver.support.ui import WebDriverWait
            from selenium.webdriver.support import expected_conditions as EC

            # Try "Rechazar" first (less tracking), fall back to "Aceptar y continuar"
            for text in ("Rechazar", "Aceptar y continuar"):
                try:
                    btn = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable(
                            (By.XPATH, f"//button[normalize-space()='{text}']")
                        )
                    )
                    btn.click()
                    time.sleep(1)
                    return
                except Exception:
                    continue
        except Exception as exc:
            logger.debug("Cookie dismiss skipped: %s", exc)

    def _build_url(self, slug: str, filters: SearchFilters, page: int) -> str:
        # Idealista only supports price_max in the URL path.
        # price_min, rooms_min, size_min are applied as post-scraping filters.
        path = f"/venta-viviendas/{slug}/"
        if filters.price_max is not None:
            path = f"/venta-viviendas/{slug}/con-precio-hasta_{int(filters.price_max)}/"
        if page > 1:
            path = path.rstrip("/") + f"/pagina-{page}.htm"
        return BASE_URL + path

    def _parse(self, html: str, city: str) -> list[Property]:
        soup = BeautifulSoup(html, "lxml")
        articles = soup.select("article.item")
        properties: list[Property] = []
        for art in articles:
            try:
                prop = self._parse_item(art, city)
                if prop:
                    properties.append(prop)
            except Exception as exc:
                logger.debug("Error parsing item: %s", exc)
        return properties

    def _parse_item(self, art: BeautifulSoup, city: str) -> Property | None:
        link = art.select_one("a.item-link")
        if not link:
            return None

        title = link.get_text(strip=True)
        relative_url = link.get("href", "")
        url = BASE_URL + relative_url if relative_url.startswith("/") else relative_url
        prop_id = hashlib.md5(url.encode()).hexdigest()[:12]

        price: float | None = None
        price_tag = art.select_one(".item-price")
        if price_tag:
            price = self._parse_number(price_tag.get_text(strip=True))

        rooms: int | None = None
        size_m2: float | None = None
        for detail in art.select(".item-detail"):
            text = detail.get_text(strip=True).lower()
            if "hab" in text:
                rooms = int(self._parse_number(text) or 0) or None
            elif "m²" in text or "m2" in text or "m�" in text:
                size_m2 = self._parse_number(text)

        images: list[str] = []
        img = art.select_one("img.item-multimedia-image") or art.select_one("picture img")
        if img:
            src = img.get("src") or img.get("data-src")
            if src and src.startswith("http"):
                images.append(src)

        address_tag = art.select_one(".item-detail-char .ellipsis")
        address = address_tag.get_text(strip=True) if address_tag else None

        return Property(
            id=prop_id,
            title=title,
            price=price,
            price_per_m2=price / size_m2 if price and size_m2 else None,
            size_m2=size_m2,
            rooms=rooms,
            bathrooms=None,
            floor=None,
            address=address,
            district=None,
            city=city,
            lat=None,
            lon=None,
            url=url,
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

    @staticmethod
    def _parse_number(text: str) -> float | None:
        # Idealista uses "." as thousands separator and "," as decimal (es-ES)
        # e.g. "174.900€" → 174900,  "1.200,50€" → 1200.50
        digits_only = re.sub(r"[^\d.,]", "", text)
        if "," in digits_only:
            # Remove thousands dots, replace decimal comma
            cleaned = digits_only.replace(".", "").replace(",", ".")
        else:
            # Only dots present → thousands separators, no decimal
            cleaned = digits_only.replace(".", "")
        try:
            return float(cleaned)
        except ValueError:
            return None
