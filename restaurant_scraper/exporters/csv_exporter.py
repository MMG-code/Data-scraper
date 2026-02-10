"""Export restaurant data to CSV files (importable into HubSpot)."""

import csv
import logging
from pathlib import Path

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)

# Column order matching HubSpot company import format
CSV_COLUMNS = [
    "venue_name",
    "website",
    "phone_number",
    "email_address",
    "venue_address",
    "city",
    "state",
    "zip_code",
    "country",
    "venue_owner",
    "cuisine_type",
    "rating",
    "price_level",
    "facebook",
    "instagram",
    "twitter",
    "linkedin",
    "tiktok",
    "yelp_url",
    "hours_of_operation",
]

# HubSpot-friendly column names
HUBSPOT_HEADER_MAP = {
    "venue_name": "Company name",
    "website": "Company domain name",
    "phone_number": "Phone number",
    "email_address": "Email",
    "venue_address": "Street address",
    "city": "City",
    "state": "State/Region",
    "zip_code": "Postal code",
    "country": "Country/Region",
    "venue_owner": "Owner name",
    "cuisine_type": "Industry",
    "rating": "Rating",
    "price_level": "Price level",
    "facebook": "Facebook page",
    "instagram": "Instagram",
    "twitter": "Twitter handle",
    "linkedin": "LinkedIn page",
    "tiktok": "TikTok",
    "yelp_url": "Yelp URL",
    "hours_of_operation": "Hours of operation",
}


def export_to_csv(
    restaurants: list[Restaurant],
    output_path: str | Path,
    hubspot_format: bool = True,
) -> Path:
    """Export restaurants to a CSV file.

    Args:
        restaurants: List of Restaurant objects.
        output_path: Path for the output CSV file.
        hubspot_format: Use HubSpot-friendly column headers.

    Returns:
        Path to the written CSV file.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    headers = (
        [HUBSPOT_HEADER_MAP[c] for c in CSV_COLUMNS]
        if hubspot_format
        else CSV_COLUMNS
    )

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for r in restaurants:
            data = r.to_dict()
            row = [data.get(col, "") for col in CSV_COLUMNS]
            # Convert None to empty string
            row = ["" if v is None else v for v in row]
            writer.writerow(row)

    logger.info("Exported %d restaurants to %s", len(restaurants), output_path)
    return output_path
