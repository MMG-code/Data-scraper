"""Pre-built seed data loader.

When external HTTP access is restricted (firewalls, proxies, sandboxed
environments), this module can generate Restaurant objects from curated
seed data supplied as a list of dicts or a JSON file.
"""

import json
import logging
from pathlib import Path

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)


def load_from_dicts(records: list[dict]) -> list[Restaurant]:
    """Create Restaurant objects from a list of plain dicts."""
    restaurants = []
    for rec in records:
        r = Restaurant(**{k: v for k, v in rec.items() if k in Restaurant.__dataclass_fields__})
        restaurants.append(r)
    return restaurants


def load_from_json(path: str | Path) -> list[Restaurant]:
    """Load seed data from a JSON file."""
    path = Path(path)
    if not path.exists():
        logger.error("Seed file not found: %s", path)
        return []
    with open(path, encoding="utf-8") as f:
        records = json.load(f)
    return load_from_dicts(records)


def save_to_json(restaurants: list[Restaurant], path: str | Path) -> Path:
    """Save restaurant data to a JSON seed file for reuse."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    records = [r.to_dict() for r in restaurants]
    with open(path, "w", encoding="utf-8") as f:
        json.dump(records, f, indent=2, default=str)
    logger.info("Saved %d restaurants to %s", len(restaurants), path)
    return path
