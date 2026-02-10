"""Yelp scraper for restaurant data (web scraping, no API key required)."""

import logging
import re
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)

YELP_SEARCH_URL = "https://www.yelp.com/search"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}


class YelpScraper:
    """Scrape restaurant info from Yelp search results."""

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def search_restaurants(
        self,
        location: str,
        max_results: int = 30,
    ) -> list[Restaurant]:
        """Search Yelp for restaurants in a location.

        Args:
            location: City or area to search.
            max_results: Maximum number of results.

        Returns:
            List of Restaurant objects.
        """
        restaurants: list[Restaurant] = []
        start = 0

        while len(restaurants) < max_results:
            params = {
                "find_desc": "Restaurants",
                "find_loc": location,
                "start": start,
            }

            try:
                resp = self.session.get(
                    YELP_SEARCH_URL, params=params, timeout=self.timeout
                )
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Yelp search failed: %s", exc)
                break

            soup = BeautifulSoup(resp.text, "lxml")
            results = self._parse_search_results(soup)

            if not results:
                break

            for r in results:
                if len(restaurants) >= max_results:
                    break
                restaurants.append(r)

            start += 10

        logger.info("Found %d restaurants from Yelp search", len(restaurants))
        return restaurants

    def enrich_restaurant(self, restaurant: Restaurant) -> Restaurant:
        """Fetch a Yelp business page to extract additional details."""
        if not restaurant.yelp_url:
            return restaurant

        try:
            resp = self.session.get(
                restaurant.yelp_url, timeout=self.timeout
            )
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.warning("Could not fetch Yelp page for %s: %s",
                           restaurant.venue_name, exc)
            return restaurant

        soup = BeautifulSoup(resp.text, "lxml")
        self._extract_details(soup, restaurant)
        return restaurant

    def _parse_search_results(self, soup: BeautifulSoup) -> list[Restaurant]:
        restaurants = []

        # Yelp wraps each search result in divs with data attributes or specific patterns
        # Look for business listing containers with links to /biz/ pages
        biz_links = soup.find_all("a", href=re.compile(r"^/biz/[^?]+"))
        seen_urls = set()

        for link in biz_links:
            href = link.get("href", "")
            biz_path = href.split("?")[0]
            if biz_path in seen_urls:
                continue

            name = link.get_text(strip=True)
            if not name or len(name) < 2 or len(name) > 100:
                continue

            seen_urls.add(biz_path)
            yelp_url = f"https://www.yelp.com{biz_path}"

            restaurant = Restaurant(
                venue_name=name,
                yelp_url=yelp_url,
                source="yelp",
            )
            restaurants.append(restaurant)

        return restaurants

    def _extract_details(self, soup: BeautifulSoup, restaurant: Restaurant) -> None:
        # Phone number
        if not restaurant.phone_number:
            phone_pattern = re.compile(
                r"\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
            )
            phone_el = soup.find("p", string=phone_pattern)
            if phone_el:
                match = phone_pattern.search(phone_el.get_text())
                if match:
                    restaurant.phone_number = match.group(0)

        # Address
        if not restaurant.venue_address:
            address_el = soup.find("address")
            if address_el:
                restaurant.venue_address = address_el.get_text(
                    separator=", ", strip=True
                )

        # Website link
        if not restaurant.website:
            biz_website = soup.find("a", href=re.compile(r"biz_redir"))
            if biz_website:
                redirect_url = biz_website.get("href", "")
                # Extract the actual URL from Yelp's redirect
                url_match = re.search(r"url=([^&]+)", redirect_url)
                if url_match:
                    from urllib.parse import unquote
                    restaurant.website = unquote(url_match.group(1))
                else:
                    link_text = biz_website.get_text(strip=True)
                    if "." in link_text and " " not in link_text:
                        restaurant.website = link_text

        # Rating
        if restaurant.rating is None:
            rating_el = soup.find("span", string=re.compile(r"^\d\.\d$"))
            if rating_el:
                try:
                    restaurant.rating = float(rating_el.get_text(strip=True))
                except ValueError:
                    pass

        # Price level
        if not restaurant.price_level:
            price_el = soup.find("span", string=re.compile(r"^[\$]{1,4}$"))
            if price_el:
                restaurant.price_level = price_el.get_text(strip=True)
