"""CLI interface for the restaurant data scraper."""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

import click
from dotenv import load_dotenv
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.table import Table

from restaurant_scraper.models import Restaurant
from restaurant_scraper.scrapers.google_places import GooglePlacesScraper
from restaurant_scraper.scrapers.website_scraper import WebsiteScraper
from restaurant_scraper.scrapers.yelp_scraper import YelpScraper
from restaurant_scraper.scrapers.web_search import WebSearchScraper
from restaurant_scraper.exporters.csv_exporter import export_to_csv
from restaurant_scraper.exporters.hubspot_api import HubSpotExporter

load_dotenv()
console = Console()


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


@click.group()
@click.option("--verbose", "-v", is_flag=True, help="Enable debug logging.")
def cli(verbose: bool) -> None:
    """Restaurant Data Scraper - Gather restaurant info for HubSpot."""
    setup_logging(verbose)


@cli.command()
@click.argument("location")
@click.option(
    "--source",
    "-s",
    type=click.Choice(["google", "yelp", "web", "both"]),
    default="google",
    help="Data source: google, yelp, web (no API key), or both (google+yelp).",
)
@click.option("--max-results", "-n", default=20, help="Max number of restaurants.")
@click.option("--radius", "-r", default=5000, help="Search radius in meters (Google only).")
@click.option("--enrich/--no-enrich", default=True, help="Scrape websites for extra data.")
@click.option(
    "--output", "-o", default=None,
    help="Output CSV file path. Defaults to output/<location>_<date>.csv.",
)
@click.option("--hubspot-push", is_flag=True, help="Push results to HubSpot API.")
@click.option(
    "--hubspot-format/--raw-format",
    default=True,
    help="Use HubSpot-friendly CSV column names.",
)
def scrape(
    location: str,
    source: str,
    max_results: int,
    radius: int,
    enrich: bool,
    output: str | None,
    hubspot_push: bool,
    hubspot_format: bool,
) -> None:
    """Scrape restaurant data for a LOCATION (city, address, or lat,lng).

    Examples:

        python -m restaurant_scraper scrape "San Francisco, CA"

        python -m restaurant_scraper scrape "Austin, TX" --source both -n 50

        python -m restaurant_scraper scrape "Chicago, IL" --hubspot-push
    """
    restaurants: list[Restaurant] = []

    # --- Search phase ---
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console,
    ) as progress:
        if source in ("google", "both"):
            api_key = os.getenv("GOOGLE_PLACES_API_KEY")
            if not api_key:
                console.print(
                    "[red]Error:[/] GOOGLE_PLACES_API_KEY not set. "
                    "Add it to your .env file or environment."
                )
                if source == "google":
                    sys.exit(1)
            else:
                task = progress.add_task("Searching Google Places...", total=None)
                google = GooglePlacesScraper(api_key)
                google_results = google.search_restaurants(
                    location, radius_meters=radius, max_results=max_results
                )
                restaurants.extend(google_results)
                progress.update(task, completed=True)

        if source in ("yelp", "both"):
            task = progress.add_task("Searching Yelp...", total=None)
            yelp = YelpScraper()
            yelp_results = yelp.search_restaurants(location, max_results=max_results)
            restaurants.extend(yelp_results)
            progress.update(task, completed=True)

        if source == "web":
            task = progress.add_task("Searching the web...", total=None)
            web = WebSearchScraper()
            web_results = web.search_restaurants(location, max_results=max_results)
            restaurants.extend(web_results)
            progress.update(task, completed=True)

    if not restaurants:
        console.print("[yellow]No restaurants found.[/] Try a different location or source.")
        sys.exit(0)

    console.print(f"\nFound [green]{len(restaurants)}[/] restaurants.\n")

    # --- Deduplicate by name ---
    restaurants = _deduplicate(restaurants)

    # --- Enrichment phase ---
    if enrich:
        # Enrich with Google Place details
        api_key = os.getenv("GOOGLE_PLACES_API_KEY")
        if api_key:
            google = GooglePlacesScraper(api_key)
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total}"),
                console=console,
            ) as progress:
                task = progress.add_task(
                    "Fetching Google Place details...", total=len(restaurants)
                )
                for r in restaurants:
                    if r.google_place_id:
                        google.enrich_restaurant(r)
                    progress.advance(task)

        # Enrich with website scraping
        ws = WebsiteScraper()
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            console=console,
        ) as progress:
            task = progress.add_task(
                "Scraping websites for contact info...", total=len(restaurants)
            )
            for r in restaurants:
                ws.enrich_restaurant(r)
                progress.advance(task)

    # --- Display results ---
    _display_results(restaurants)

    # --- Export CSV ---
    if output is None:
        safe_loc = location.replace(",", "").replace(" ", "_").lower()
        date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        output = f"output/{safe_loc}_{date_str}.csv"

    csv_path = export_to_csv(restaurants, output, hubspot_format=hubspot_format)
    console.print(f"\n[green]CSV exported to:[/] {csv_path}")

    # --- HubSpot push ---
    if hubspot_push:
        hs_key = os.getenv("HUBSPOT_API_KEY")
        if not hs_key:
            console.print(
                "[red]Error:[/] HUBSPOT_API_KEY not set. "
                "Add it to your .env file or environment."
            )
            sys.exit(1)

        hs = HubSpotExporter(hs_key)

        console.print("\nTesting HubSpot connection...")
        if not hs.test_connection():
            console.print("[red]Error:[/] Could not connect to HubSpot. Check your API key.")
            sys.exit(1)

        console.print("[green]Connected to HubSpot.[/]\n")

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("Pushing to HubSpot...", total=None)
            result = hs.push_restaurants(restaurants)
            progress.update(task, completed=True)

        console.print(
            f"\nHubSpot results: "
            f"[green]{result['created']} created[/], "
            f"[red]{result['failed']} failed[/]"
        )
        if result["errors"]:
            for err in result["errors"][:5]:
                console.print(f"  [red]•[/] {err}")


@cli.command(name="from-json")
@click.argument("json_file", type=click.Path(exists=True))
@click.option(
    "--output", "-o", default=None,
    help="Output CSV file path.",
)
@click.option(
    "--hubspot-format/--raw-format", default=True,
    help="Use HubSpot-friendly CSV column names.",
)
@click.option("--hubspot-push", is_flag=True, help="Push results to HubSpot API.")
def from_json(
    json_file: str, output: str | None, hubspot_format: bool, hubspot_push: bool
) -> None:
    """Load restaurant data from a JSON file and export to CSV.

    Example:

        python -m restaurant_scraper from-json output/malahide_restaurants.json
    """
    from restaurant_scraper.scrapers.seed_data import load_from_json

    restaurants = load_from_json(json_file)
    if not restaurants:
        console.print("[yellow]No restaurants found in JSON file.[/]")
        return

    console.print(f"Loaded [green]{len(restaurants)}[/] restaurants from {json_file}\n")
    _display_results(restaurants)

    if output is None:
        from pathlib import Path
        output = str(Path(json_file).with_suffix(".csv"))

    csv_path = export_to_csv(restaurants, output, hubspot_format=hubspot_format)
    console.print(f"\n[green]CSV exported to:[/] {csv_path}")

    if hubspot_push:
        hs_key = os.getenv("HUBSPOT_API_KEY")
        if not hs_key:
            console.print("[red]Error:[/] HUBSPOT_API_KEY not set.")
            return
        hs = HubSpotExporter(hs_key)
        result = hs.push_restaurants(restaurants)
        console.print(
            f"\nHubSpot: [green]{result['created']} created[/], "
            f"[red]{result['failed']} failed[/]"
        )


@cli.command()
def check_config() -> None:
    """Check which API keys are configured."""
    table = Table(title="Configuration Status")
    table.add_column("Service", style="bold")
    table.add_column("Status")
    table.add_column("Notes")

    google_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if google_key:
        table.add_row("Google Places API", "[green]Configured[/]", f"Key: {google_key[:8]}...")
    else:
        table.add_row("Google Places API", "[red]Not set[/]", "Set GOOGLE_PLACES_API_KEY in .env")

    hs_key = os.getenv("HUBSPOT_API_KEY")
    if hs_key:
        hs = HubSpotExporter(hs_key)
        connected = hs.test_connection()
        status = "[green]Connected[/]" if connected else "[yellow]Key set but connection failed[/]"
        table.add_row("HubSpot API", status, f"Key: {hs_key[:8]}...")
    else:
        table.add_row("HubSpot API", "[red]Not set[/]", "Set HUBSPOT_API_KEY in .env")

    table.add_row("Yelp Scraping", "[green]Available[/]", "No API key needed")
    table.add_row("Web Search", "[green]Available[/]", "No API key needed (--source web)")

    console.print(table)


def _deduplicate(restaurants: list[Restaurant]) -> list[Restaurant]:
    """Remove duplicate restaurants by normalized name."""
    seen: dict[str, Restaurant] = {}
    for r in restaurants:
        key = r.venue_name.lower().strip()
        if key in seen:
            seen[key].merge(r)
        else:
            seen[key] = r
    return list(seen.values())


def _display_results(restaurants: list[Restaurant]) -> None:
    """Print a summary table of results."""
    table = Table(title=f"Restaurant Results ({len(restaurants)} found)")
    table.add_column("#", style="dim", width=4)
    table.add_column("Name", style="bold", max_width=30)
    table.add_column("Phone", max_width=16)
    table.add_column("Email", max_width=28)
    table.add_column("Website", max_width=25)
    table.add_column("Owner", max_width=20)
    table.add_column("Rating", width=6)

    for i, r in enumerate(restaurants, 1):
        # Truncate website for display
        website = r.website
        if website and len(website) > 25:
            website = website[:22] + "..."

        table.add_row(
            str(i),
            r.venue_name,
            r.phone_number or "-",
            r.email_address or "-",
            website or "-",
            r.venue_owner or "-",
            str(r.rating) if r.rating else "-",
        )

    console.print(table)


def main() -> None:
    cli()
