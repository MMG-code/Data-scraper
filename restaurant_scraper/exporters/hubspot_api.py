"""Push restaurant data directly to HubSpot via API."""

import logging
import time

import requests

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)

HUBSPOT_COMPANIES_URL = "https://api.hubapi.com/crm/v3/objects/companies"


class HubSpotExporter:
    """Export restaurant data to HubSpot as company records."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        })

    def push_restaurants(
        self,
        restaurants: list[Restaurant],
        batch_size: int = 10,
    ) -> dict:
        """Create company records in HubSpot for each restaurant.

        Args:
            restaurants: List of Restaurant objects.
            batch_size: Number of records to send per batch request.

        Returns:
            Summary dict with counts of created, failed, and skipped records.
        """
        results = {"created": 0, "failed": 0, "errors": []}

        # Use batch create endpoint for efficiency
        for i in range(0, len(restaurants), batch_size):
            batch = restaurants[i : i + batch_size]
            batch_result = self._create_batch(batch)
            results["created"] += batch_result["created"]
            results["failed"] += batch_result["failed"]
            results["errors"].extend(batch_result["errors"])

            # Rate limiting: avoid hitting HubSpot's 100 requests/10s limit
            if i + batch_size < len(restaurants):
                time.sleep(0.5)

        logger.info(
            "HubSpot push complete: %d created, %d failed",
            results["created"],
            results["failed"],
        )
        return results

    def _create_batch(self, restaurants: list[Restaurant]) -> dict:
        """Send a batch of restaurant records to HubSpot."""
        inputs = []
        for r in restaurants:
            properties = {
                "name": r.venue_name,
                "domain": self._extract_domain(r.website),
                "phone": r.phone_number,
                "address": r.venue_address,
                "city": r.city,
                "state": r.state,
                "zip": r.zip_code,
                "country": r.country,
                "website": r.website,
                "description": f"Cuisine: {r.cuisine_type}" if r.cuisine_type else "",
                "industry": "RESTAURANT",
            }
            # Only include non-empty properties
            properties = {k: v for k, v in properties.items() if v}
            inputs.append({"properties": properties})

        payload = {"inputs": inputs}
        batch_url = f"{HUBSPOT_COMPANIES_URL}/batch/create"

        result = {"created": 0, "failed": 0, "errors": []}

        try:
            resp = self.session.post(batch_url, json=payload, timeout=30)
            if resp.status_code == 201:
                data = resp.json()
                result["created"] = len(data.get("results", []))
            elif resp.status_code == 207:
                # Partial success
                data = resp.json()
                result["created"] = len(data.get("results", []))
                result["failed"] = len(data.get("errors", []))
                for err in data.get("errors", []):
                    result["errors"].append(err.get("message", str(err)))
            else:
                result["failed"] = len(restaurants)
                error_msg = resp.text[:200]
                result["errors"].append(
                    f"HTTP {resp.status_code}: {error_msg}"
                )
                logger.error("HubSpot batch create failed: %s", error_msg)
        except requests.RequestException as exc:
            result["failed"] = len(restaurants)
            result["errors"].append(str(exc))
            logger.error("HubSpot API request failed: %s", exc)

        return result

    def _extract_domain(self, website: str) -> str:
        if not website:
            return ""
        from urllib.parse import urlparse

        parsed = urlparse(
            website if website.startswith("http") else f"https://{website}"
        )
        return parsed.netloc.replace("www.", "")

    def test_connection(self) -> bool:
        """Verify the HubSpot API key is valid."""
        try:
            resp = self.session.get(
                HUBSPOT_COMPANIES_URL,
                params={"limit": 1},
                timeout=10,
            )
            return resp.status_code == 200
        except requests.RequestException:
            return False
