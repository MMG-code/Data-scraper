"""Google Places API scraper for restaurant data."""

import logging
import time

import requests

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)

NEARBY_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
TEXT_SEARCH_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"

PRICE_MAP = {0: "Free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}


class GooglePlacesScraper:
    """Scrape restaurant data using the Google Places API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()

    def search_restaurants(
        self,
        location: str,
        radius_meters: int = 5000,
        max_results: int = 60,
    ) -> list[Restaurant]:
        """Search for restaurants near a location string.

        Args:
            location: City, address, or "lat,lng" string.
            radius_meters: Search radius in meters (max 50000).
            max_results: Cap on total results (API pages in sets of 20).

        Returns:
            List of Restaurant objects with basic info filled in.
        """
        # If location looks like coordinates, use nearby search
        if self._is_coordinates(location):
            return self._nearby_search(location, radius_meters, max_results)
        return self._text_search(location, max_results)

    def _is_coordinates(self, location: str) -> bool:
        parts = location.split(",")
        if len(parts) != 2:
            return False
        try:
            float(parts[0].strip())
            float(parts[1].strip())
            return True
        except ValueError:
            return False

    def _text_search(self, query: str, max_results: int) -> list[Restaurant]:
        search_query = query
        if "restaurant" not in query.lower():
            search_query = f"restaurants in {query}"

        params = {
            "query": search_query,
            "type": "restaurant",
            "key": self.api_key,
        }

        return self._paginate_search(TEXT_SEARCH_URL, params, max_results)

    def _nearby_search(
        self, coords: str, radius: int, max_results: int
    ) -> list[Restaurant]:
        params = {
            "location": coords,
            "radius": radius,
            "type": "restaurant",
            "key": self.api_key,
        }

        return self._paginate_search(NEARBY_SEARCH_URL, params, max_results)

    def _paginate_search(
        self, url: str, params: dict, max_results: int
    ) -> list[Restaurant]:
        restaurants = []
        next_page_token = None

        while len(restaurants) < max_results:
            if next_page_token:
                params["pagetoken"] = next_page_token
                # Google requires a short delay before using page tokens
                time.sleep(2)

            resp = self.session.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()

            if data.get("status") not in ("OK", "ZERO_RESULTS"):
                logger.error("Google Places API error: %s", data.get("status"))
                logger.error("Error message: %s", data.get("error_message", ""))
                break

            for place in data.get("results", []):
                if len(restaurants) >= max_results:
                    break
                restaurants.append(self._parse_basic(place))

            next_page_token = data.get("next_page_token")
            if not next_page_token:
                break

        logger.info("Found %d restaurants from Google Places search", len(restaurants))
        return restaurants

    def enrich_restaurant(self, restaurant: Restaurant) -> Restaurant:
        """Fetch full details for a restaurant using its place_id."""
        if not restaurant.google_place_id:
            return restaurant

        params = {
            "place_id": restaurant.google_place_id,
            "fields": (
                "name,formatted_address,formatted_phone_number,"
                "website,url,rating,price_level,opening_hours,"
                "address_components,types"
            ),
            "key": self.api_key,
        }

        resp = self.session.get(DETAILS_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") != "OK":
            logger.warning(
                "Could not get details for %s: %s",
                restaurant.venue_name,
                data.get("status"),
            )
            return restaurant

        result = data["result"]
        restaurant.phone_number = result.get(
            "formatted_phone_number", restaurant.phone_number
        )
        restaurant.website = result.get("website", restaurant.website)
        restaurant.venue_address = result.get(
            "formatted_address", restaurant.venue_address
        )

        price = result.get("price_level")
        if price is not None:
            restaurant.price_level = PRICE_MAP.get(price, "")

        rating = result.get("rating")
        if rating is not None:
            restaurant.rating = rating

        hours = result.get("opening_hours", {}).get("weekday_text")
        if hours:
            restaurant.hours_of_operation = " | ".join(hours)

        self._parse_address_components(
            result.get("address_components", []), restaurant
        )

        return restaurant

    def _parse_basic(self, place: dict) -> Restaurant:
        return Restaurant(
            venue_name=place.get("name", ""),
            venue_address=place.get("vicinity", place.get("formatted_address", "")),
            rating=place.get("rating"),
            price_level=PRICE_MAP.get(place.get("price_level"), ""),
            google_place_id=place.get("place_id", ""),
            source="google_places",
        )

    def _parse_address_components(
        self, components: list[dict], restaurant: Restaurant
    ) -> None:
        for comp in components:
            types = comp.get("types", [])
            if "locality" in types:
                restaurant.city = comp["long_name"]
            elif "administrative_area_level_1" in types:
                restaurant.state = comp["short_name"]
            elif "postal_code" in types:
                restaurant.zip_code = comp["long_name"]
            elif "country" in types:
                restaurant.country = comp["long_name"]
