"""Flask web application for the Restaurant Data Scraper."""

import csv
import io
import json
import logging
import os
import re
import time
from datetime import datetime
from urllib.parse import quote_plus, unquote, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, Response, session

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")
app.secret_key = os.urandom(24)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Google Places API helpers
# ---------------------------------------------------------------------------
GOOGLE_TEXT_SEARCH = "https://maps.googleapis.com/maps/api/place/textsearch/json"
GOOGLE_DETAILS = "https://maps.googleapis.com/maps/api/place/details/json"
PRICE_MAP = {0: "Free", 1: "$", 2: "$$", 3: "$$$", 4: "$$$$"}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}

# Social media patterns for website scraping
SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
    "twitter": re.compile(r"https?://(?:www\.)?(?:twitter|x)\.com/[^\s\"'<>]+", re.I),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s\"'<>]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[^\s\"'<>]+", re.I),
}

EMAIL_RE = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")
PHONE_RE = re.compile(
    r"(?:\+353|0)[\s\-]?\(?\d{1,2}\)?[\s\-]?\d{3,4}[\s\-]?\d{3,4}"
)

OWNER_KEYWORDS = [
    "owner", "founder", "proprietor", "chef-owner", "chef/owner",
    "managing partner", "general manager",
]

SUBPAGES = ["contact", "about", "about-us", "contact-us", "our-story", "team"]


def google_search(location: str, api_key: str, max_results: int = 60):
    """Search Google Places for restaurants."""
    restaurants = []
    query = f"restaurants in {location}"
    params = {"query": query, "type": "restaurant", "key": api_key}
    next_page_token = None

    while len(restaurants) < max_results:
        if next_page_token:
            params["pagetoken"] = next_page_token
            time.sleep(2)

        resp = requests.get(GOOGLE_TEXT_SEARCH, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        if data.get("status") not in ("OK", "ZERO_RESULTS"):
            logger.error("Google API error: %s - %s",
                         data.get("status"), data.get("error_message", ""))
            break

        for place in data.get("results", []):
            if len(restaurants) >= max_results:
                break
            restaurants.append({
                "venue_name": place.get("name", ""),
                "venue_address": place.get("formatted_address", ""),
                "rating": place.get("rating"),
                "price_level": PRICE_MAP.get(place.get("price_level"), ""),
                "place_id": place.get("place_id", ""),
            })

        next_page_token = data.get("next_page_token")
        if not next_page_token:
            break

    return restaurants


def google_place_details(place_id: str, api_key: str) -> dict:
    """Get full details for a Google Place."""
    params = {
        "place_id": place_id,
        "fields": (
            "name,formatted_address,formatted_phone_number,"
            "website,rating,price_level,opening_hours,"
            "address_components"
        ),
        "key": api_key,
    }
    resp = requests.get(GOOGLE_DETAILS, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    if data.get("status") != "OK":
        return {}

    result = data["result"]
    details = {
        "phone_number": result.get("formatted_phone_number", ""),
        "website": result.get("website", ""),
        "venue_address": result.get("formatted_address", ""),
        "price_level": PRICE_MAP.get(result.get("price_level"), ""),
        "rating": result.get("rating"),
    }

    hours = result.get("opening_hours", {}).get("weekday_text")
    if hours:
        details["hours_of_operation"] = " | ".join(hours)

    for comp in result.get("address_components", []):
        types = comp.get("types", [])
        if "locality" in types:
            details["city"] = comp["long_name"]
        elif "administrative_area_level_1" in types:
            details["state"] = comp.get("short_name", comp["long_name"])
        elif "postal_code" in types:
            details["zip_code"] = comp["long_name"]
        elif "country" in types:
            details["country"] = comp["long_name"]

    return details


def scrape_website(url: str) -> dict:
    """Scrape a restaurant website for email, socials, owner."""
    if not url:
        return {}

    base_url = url if url.startswith("http") else f"https://{url}"
    sess = requests.Session()
    sess.headers.update(HEADERS)
    info = {
        "email_address": "",
        "facebook": "",
        "instagram": "",
        "twitter": "",
        "linkedin": "",
        "tiktok": "",
        "venue_owner": "",
    }

    all_html = ""
    all_text = ""

    # Fetch main page + common subpages
    urls_to_try = [base_url] + [
        f"{base_url.rstrip('/')}/{slug}" for slug in SUBPAGES
    ]

    for page_url in urls_to_try:
        try:
            resp = sess.get(page_url, timeout=10, allow_redirects=True)
            if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
                all_html += resp.text + "\n"
                soup = BeautifulSoup(resp.text, "lxml")
                all_text += soup.get_text(separator=" ", strip=True) + "\n"
        except requests.RequestException:
            continue

    if not all_html:
        return info

    # Email - prefer mailto links
    soup = BeautifulSoup(all_html, "lxml")
    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if href.startswith("mailto:"):
            email = href.replace("mailto:", "").split("?")[0].strip()
            if EMAIL_RE.match(email):
                info["email_address"] = email
                break

    if not info["email_address"]:
        domain = urlparse(base_url).netloc.replace("www.", "")
        all_emails = EMAIL_RE.findall(all_text + " " + all_html)
        filtered = [e for e in all_emails
                     if not e.endswith((".png", ".jpg", ".gif", ".svg", ".webp"))]
        domain_emails = [e for e in filtered if domain in e]
        if domain_emails:
            info["email_address"] = domain_emails[0]
        elif filtered:
            info["email_address"] = filtered[0]

    # Socials
    for field_name, pattern in SOCIAL_PATTERNS.items():
        match = pattern.search(all_html)
        if match:
            info[field_name] = match.group(0).rstrip("\"'>/),.")

    # Owner
    for keyword in OWNER_KEYWORDS:
        pat = re.compile(
            rf"{keyword}\s*[:\-–—]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
            re.IGNORECASE,
        )
        match = pat.search(all_text)
        if match:
            info["venue_owner"] = match.group(1).strip()
            break

    return info


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    return render_template("index.html", has_api_key=bool(api_key))


@app.route("/api/search", methods=["POST"])
def api_search():
    """Search for restaurants and return JSON results."""
    data = request.get_json()
    location = data.get("location", "").strip()
    max_results = min(int(data.get("max_results", 20)), 60)
    enrich = data.get("enrich", True)

    api_key = os.getenv("GOOGLE_PLACES_API_KEY", "")
    if not api_key:
        return jsonify({"error": "GOOGLE_PLACES_API_KEY not configured. Add it to your .env file."}), 400

    if not location:
        return jsonify({"error": "Location is required."}), 400

    try:
        # Search Google Places
        results = google_search(location, api_key, max_results)

        if not results:
            return jsonify({"error": f"No restaurants found in '{location}'."}), 404

        # Enrich with Place Details
        for r in results:
            if r.get("place_id"):
                details = google_place_details(r["place_id"], api_key)
                r.update({k: v for k, v in details.items() if v})

        # Enrich with website scraping
        if enrich:
            for r in results:
                if r.get("website"):
                    try:
                        site_info = scrape_website(r["website"])
                        r.update({k: v for k, v in site_info.items() if v})
                    except Exception as exc:
                        logger.debug("Website scrape failed for %s: %s",
                                     r.get("venue_name"), exc)

        # Clean up internal fields
        for r in results:
            r.pop("place_id", None)
            # Set defaults for missing fields
            for field in ["email_address", "phone_number", "website",
                          "venue_owner", "facebook", "instagram", "twitter",
                          "linkedin", "tiktok", "city", "state", "zip_code",
                          "country", "hours_of_operation", "cuisine_type"]:
                r.setdefault(field, "")

        # Store in session for CSV download
        session["last_results"] = results
        session["last_location"] = location

        return jsonify({"restaurants": results, "count": len(results)})

    except requests.RequestException as exc:
        return jsonify({"error": f"API request failed: {str(exc)}"}), 500


@app.route("/api/download-csv")
def download_csv():
    """Download the last search results as a HubSpot-ready CSV."""
    results = session.get("last_results", [])
    location = session.get("last_location", "export")

    if not results:
        return jsonify({"error": "No results to download. Run a search first."}), 400

    columns = [
        ("Company name", "venue_name"),
        ("Company domain name", "website"),
        ("Phone number", "phone_number"),
        ("Email", "email_address"),
        ("Street address", "venue_address"),
        ("City", "city"),
        ("State/Region", "state"),
        ("Postal code", "zip_code"),
        ("Country/Region", "country"),
        ("Owner name", "venue_owner"),
        ("Industry", "cuisine_type"),
        ("Rating", "rating"),
        ("Price level", "price_level"),
        ("Facebook page", "facebook"),
        ("Instagram", "instagram"),
        ("Twitter handle", "twitter"),
        ("LinkedIn page", "linkedin"),
        ("TikTok", "tiktok"),
        ("Hours of operation", "hours_of_operation"),
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([col[0] for col in columns])

    for r in results:
        row = [r.get(col[1], "") or "" for col in columns]
        writer.writerow(row)

    safe_loc = location.replace(",", "").replace(" ", "_").lower()
    filename = f"restaurants_{safe_loc}_{datetime.now().strftime('%Y%m%d')}.csv"

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/api/save-key", methods=["POST"])
def save_key():
    """Save a Google API key to the .env file."""
    data = request.get_json()
    key = data.get("api_key", "").strip()

    if not key:
        return jsonify({"error": "API key is required."}), 400

    env_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env")

    # Read existing .env or create new
    lines = []
    key_found = False
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            for line in f:
                if line.startswith("GOOGLE_PLACES_API_KEY="):
                    lines.append(f"GOOGLE_PLACES_API_KEY={key}\n")
                    key_found = True
                else:
                    lines.append(line)

    if not key_found:
        lines.append(f"GOOGLE_PLACES_API_KEY={key}\n")

    with open(env_path, "w") as f:
        f.writelines(lines)

    os.environ["GOOGLE_PLACES_API_KEY"] = key
    return jsonify({"success": True})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"\n  Restaurant Data Scraper is running!")
    print(f"  Open your browser to: http://localhost:{port}\n")
    app.run(host="0.0.0.0", port=port, debug=True)
