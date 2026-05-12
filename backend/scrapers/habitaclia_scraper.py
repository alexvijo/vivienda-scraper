# Habitaclia scraper - scrapes www.habitaclia.com

import re
import time

import cloudscraper
from bs4 import BeautifulSoup

from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper


class HabitacliaScraper(BaseScraper):
    platform = "habitaclia"
    base_url = "https://www.habitaclia.com"

    city_slugs = {
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

    def _fetch(self, url: str) -> str:
        """Fetch HTML with cloudscraper."""
        scraper = cloudscraper.create_scraper()
        resp = scraper.get(url, timeout=10)
        resp.encoding = "utf-8"
        return resp.text

    def search(self, filters: SearchFilters) -> list[Property]:
        city = filters.city.lower()
        slug = self.city_slugs.get(city, city)
        # Note: habitaclia does not support district filtering via URL

        properties = []
        pages = 0

        while pages < 3:
            # Build URL without district (not supported by portal)
            url = f"{self.base_url}/comprar-piso-en-{slug}.htm"
            if pages > 0:
                url += f"?pagina={pages + 1}"

            try:
                html = self._fetch(url)
                soup = BeautifulSoup(html, "lxml")

                articles = soup.find_all("article", class_="lnk-anuncio")
                if not articles:
                    break

                for article in articles:
                    try:
                        title_el = article.find("h2")
                        title = title_el.get_text(strip=True) if title_el else "Sin título"

                        link_el = article.find("a", class_="lnk-anuncio")
                        url = link_el["href"] if link_el and link_el.get("href") else ""
                        if not url.startswith("http"):
                            url = self.base_url + url

                        price_text = article.find("span", class_="precio")
                        price = None
                        if price_text:
                            price_str = re.sub(r"[^\d]", "", price_text.get_text())
                            price = int(price_str) if price_str else None

                        size_el = article.find("span", class_="m2")
                        size_m2 = None
                        if size_el:
                            size_str = re.sub(r"[^\d]", "", size_el.get_text())
                            size_m2 = int(size_str) if size_str else None

                        rooms_el = article.find("span", class_="hab")
                        rooms = None
                        if rooms_el:
                            rooms_str = re.sub(r"[^\d]", "", rooms_el.get_text())
                            rooms = int(rooms_str) if rooms_str else None

                        images = []
                        img_el = article.find("img")
                        if img_el and img_el.get("src"):
                            images.append(img_el["src"])

                        address = article.find("span", class_="zona")
                        address_text = address.get_text(strip=True) if address else None

                        if filters.price_max and price and price > filters.price_max:
                            continue
                        if filters.price_min and price and price < filters.price_min:
                            continue
                        if filters.rooms_min and rooms and rooms < filters.rooms_min:
                            continue
                        if filters.size_min and size_m2 and size_m2 < filters.size_min:
                            continue
                        if filters.size_max and size_m2 and size_m2 > filters.size_max:
                            continue

                        # Create property object first
                        prop_obj = Property(
                            id=url,
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

                        # Filter by district if provided (search in title, address, description)
                        if filters.district:
                            search_term = filters.district.lower()
                            searchable_text = " ".join([
                                prop_obj.title or "",
                                prop_obj.address or "",
                                prop_obj.description or "",
                                prop_obj.url or ""
                            ]).lower()
                            if search_term not in searchable_text:
                                continue

                        properties.append(prop_obj)
                    except Exception as e:
                        self.logger.debug(f"Error parsing property: {e}")
                        continue

                pages += 1
                time.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Error fetching page {pages + 1}: {e}")
                break

        return properties

