"""Quick script to generate CSV from a JSON seed file."""

from restaurant_scraper.scrapers.seed_data import load_from_json
from restaurant_scraper.exporters.csv_exporter import export_to_csv

restaurants = load_from_json("output/malahide_restaurants.json")
path = export_to_csv(restaurants, "output/malahide_dublin_ireland.csv", hubspot_format=True)
print(f"Exported {len(restaurants)} restaurants to {path}")
