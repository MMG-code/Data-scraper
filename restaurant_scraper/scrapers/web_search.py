"""Web search-based scraper for restaurant data - no API keys required."""

import json
import logging
import re
import time
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)


class WebSearchScraper:
    """Scrape restaurant data using web search results and individual website visits.

    This scraper works without any API keys by searching the web for restaurant
    listings in a given location and then visiting each restaurant's website
    to gather contact details.
    """

    def __init__(self, timeout: int = 15):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    def search_restaurants(
        self,
        location: str,
        max_results: int = 30,
    ) -> list[Restaurant]:
        """Search for restaurants using web directory pages.

        Fetches restaurant listing pages (TripAdvisor, local directories,
        Michelin Guide, etc.) and extracts restaurant names and links.
        """
        restaurants: list[Restaurant] = []

        # Fetch data from multiple directory sources
        sources = [
            self._search_tripadvisor(location, max_results),
            self._search_michelin(location, max_results),
            self._search_directories(location, max_results),
        ]

        for source_results in sources:
            for r in source_results:
                if len(restaurants) >= max_results:
                    break
                # Deduplicate by name
                if not any(
                    r.venue_name.lower().strip() == existing.venue_name.lower().strip()
                    for existing in restaurants
                ):
                    restaurants.append(r)

        logger.info("Found %d restaurants via web search", len(restaurants))
        return restaurants[:max_results]

    def _search_tripadvisor(
        self, location: str, max_results: int
    ) -> list[Restaurant]:
        """Try to get restaurant listings from TripAdvisor."""
        restaurants = []
        try:
            # Use a search-engine-friendly URL
            query = f"site:tripadvisor.com restaurants {location}"
            resp = self._fetch_url(
                f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            )
            if not resp:
                return restaurants

            soup = BeautifulSoup(resp, "lxml")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "Restaurant_Review" in href and text and len(text) > 3:
                    restaurants.append(Restaurant(
                        venue_name=self._clean_name(text),
                        source="tripadvisor",
                    ))
                if len(restaurants) >= max_results:
                    break
        except Exception as exc:
            logger.debug("TripAdvisor search failed: %s", exc)

        return restaurants

    def _search_michelin(self, location: str, max_results: int) -> list[Restaurant]:
        """Try to get listings from the Michelin Guide."""
        restaurants = []
        try:
            query = f"site:guide.michelin.com restaurants {location}"
            resp = self._fetch_url(
                f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            )
            if not resp:
                return restaurants

            soup = BeautifulSoup(resp, "lxml")
            for link in soup.find_all("a", href=True):
                href = link.get("href", "")
                text = link.get_text(strip=True)
                if "/restaurant/" in href and text and len(text) > 3:
                    name = self._clean_name(text)
                    if name.lower() not in ("restaurant", "restaurants"):
                        restaurants.append(Restaurant(
                            venue_name=name,
                            source="michelin",
                        ))
                if len(restaurants) >= max_results:
                    break
        except Exception as exc:
            logger.debug("Michelin search failed: %s", exc)

        return restaurants

    def _search_directories(
        self, location: str, max_results: int
    ) -> list[Restaurant]:
        """Search DuckDuckGo for restaurant listings in the location."""
        restaurants = []
        try:
            query = f"restaurants in {location} phone email website"
            resp = self._fetch_url(
                f"https://html.duckduckgo.com/html/?q={requests.utils.quote(query)}"
            )
            if not resp:
                return restaurants

            soup = BeautifulSoup(resp, "lxml")
            # Extract result snippets
            for result in soup.find_all("div", class_="result"):
                title_el = result.find("a", class_="result__a")
                if not title_el:
                    continue

                title = title_el.get_text(strip=True)
                href = title_el.get("href", "")

                # Skip aggregator pages, keep individual restaurant sites
                domain = urlparse(href).netloc if href.startswith("http") else ""
                skip_domains = [
                    "tripadvisor", "yelp.com", "facebook.com", "instagram.com",
                    "google.com", "youtube.com", "twitter.com", "wikipedia.org",
                ]
                if any(skip in domain for skip in skip_domains):
                    continue

                if title and len(title) > 2:
                    r = Restaurant(
                        venue_name=self._clean_name(title),
                        website=href if href.startswith("http") else "",
                        source="web_search",
                    )
                    restaurants.append(r)

                if len(restaurants) >= max_results:
                    break
        except Exception as exc:
            logger.debug("Directory search failed: %s", exc)

        return restaurants

    def _fetch_url(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code == 200:
                return resp.text
        except requests.RequestException as exc:
            logger.debug("Failed to fetch %s: %s", url, exc)
        return None

    def _clean_name(self, text: str) -> str:
        """Clean up a restaurant name extracted from search results."""
        # Remove common suffixes from search result titles
        separators = [" - TripAdvisor", " - Michelin", " – ", " | ", " - a MICHELIN"]
        for sep in separators:
            if sep in text:
                text = text.split(sep)[0]
        return text.strip()
