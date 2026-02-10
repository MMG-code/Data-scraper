# Restaurant Data Scraper

Gather restaurant business information and export it to HubSpot. Collects venue name, website, social media, phone number, email, address, owner, and more.

## Data Collected

| Field | Source |
|-------|--------|
| Venue name | Google Places, Yelp |
| Website | Google Places, Yelp |
| Phone number | Google Places, Yelp, Website |
| Email address | Website scraping |
| Venue address | Google Places, Yelp |
| Venue owner | Website scraping |
| Social media (FB, IG, X, LinkedIn, TikTok) | Website scraping |
| Rating & price level | Google Places, Yelp |
| Hours of operation | Google Places |
| Cuisine type | Google Places |

## Setup

```bash
# Clone and install
git clone <repo-url>
cd Data-scraper
pip install -r requirements.txt

# Configure API keys
cp .env.example .env
# Edit .env with your keys
```

### API Keys

- **Google Places API** (recommended): Get a key from [Google Cloud Console](https://console.cloud.google.com/apis/credentials). Enable the "Places API".
- **HubSpot API** (optional, for direct push): Get a private app access token from HubSpot Settings > Integrations > Private Apps.
- **Yelp**: No API key needed (uses web scraping).

## Usage

```bash
# Search Google Places for restaurants in a city
python -m restaurant_scraper scrape "San Francisco, CA"

# Search Yelp instead
python -m restaurant_scraper scrape "Austin, TX" --source yelp

# Search both sources, get up to 50 results
python -m restaurant_scraper scrape "Chicago, IL" --source both -n 50

# Export with raw column names (not HubSpot format)
python -m restaurant_scraper scrape "Miami, FL" --raw-format

# Skip website enrichment (faster, less data)
python -m restaurant_scraper scrape "Denver, CO" --no-enrich

# Push directly to HubSpot
python -m restaurant_scraper scrape "Seattle, WA" --hubspot-push

# Save to a specific file
python -m restaurant_scraper scrape "Portland, OR" -o my_leads.csv

# Check which API keys are configured
python -m restaurant_scraper check-config
```

## Output

Results are saved as CSV files in the `output/` directory by default. The CSV uses HubSpot-compatible column names so you can import directly:

1. Go to HubSpot > Contacts > Companies > Import
2. Select "File from computer"
3. Upload the CSV
4. Map columns (most will auto-map)

## Project Structure

```
restaurant_scraper/
  __init__.py
  __main__.py          # Entry point
  cli.py               # CLI commands
  models.py            # Restaurant data model
  scrapers/
    google_places.py   # Google Places API
    website_scraper.py # Scrape restaurant websites
    yelp_scraper.py    # Yelp web scraper
  exporters/
    csv_exporter.py    # CSV export (HubSpot-ready)
    hubspot_api.py     # Direct HubSpot API push
```
