# Trovimap scraper - scrapes www.trovimap.com

import re
import time

import cloudscraper
from bs4 import BeautifulSoup

from models.property import Property, SearchFilters
from scrapers.base_scraper import BaseScraper


class TrovimapScraper(BaseScraper):
    platform = "trovimap"
    base_url = "https://www.trovimap.com"

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

        properties = []
        pages = 0

        while pages < 3:
            url = f"{self.base_url}/buscar/vivienda/{slug}"
            if pages > 0:
                url += f"?page={pages + 1}"

            try:
                html = self._fetch(url)
                soup = BeautifulSoup(html, "lxml")

                # Trovimap uses article or div.property containers
                items = soup.find_all(["article", "div"], class_=re.compile(r"property|listing|item"))
                if not items:
                    break

                for item in items:
                    try:
                        link = item.find("a", href=re.compile(r"/propiedad/|/vivienda/"))
                        if not link or not link.get("href"):
                            continue

                        url = link["href"]
                        if not url.startswith("http"):
                            url = self.base_url + url

                        title = item.find("h2") or item.find("h3")
                        title_text = title.get_text(strip=True) if title else "Sin título"

                        # Extract price
                        price_el = item.find("span", class_=re.compile(r"price|precio"))
                        if not price_el:
                            price_el = item.find(string=re.compile(r"€"))
                        price = None
                        if price_el:
                            price_str = re.sub(r"[^\d]", "", price_el.get_text())
                            price = int(price_str) if price_str else None

                        if filters.price_max and price and price > filters.price_max:
                            continue
                        if filters.price_min and price and price < filters.price_min:
                            continue

                        properties.append(
                            Property(
                                id=url,
                                title=title_text,
                                price=price,
                                price_per_m2=None,
                                size_m2=None,
                                rooms=None,
                                bathrooms=None,
                                floor=None,
                                address=None,
                                district=None,
                                city=filters.city,
                                lat=None,
                                lon=None,
                                url=url,
                                platform=self.platform,
                                images=[],
                                description=None,
                                has_elevator=None,
                                has_parking=None,
                                has_terrace=None,
                                is_new_development=None,
                                published_at=None,
                                scraped_at=self.now_iso(),
                            )
                        )
                    except Exception as e:
                        self.logger.debug(f"Error parsing property: {e}")
                        continue

                pages += 1
                time.sleep(1.0)
            except Exception as e:
                self.logger.error(f"Error fetching page {pages + 1}: {e}")
                break

        return properties
