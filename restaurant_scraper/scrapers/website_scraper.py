"""Scrape restaurant websites for contact info, social media, and owner details."""

import logging
import re
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from restaurant_scraper.models import Restaurant

logger = logging.getLogger(__name__)

EMAIL_RE = re.compile(
    r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
)

PHONE_RE = re.compile(
    r"(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"
)

SOCIAL_PATTERNS = {
    "facebook": re.compile(r"https?://(?:www\.)?facebook\.com/[^\s\"'<>]+", re.I),
    "instagram": re.compile(r"https?://(?:www\.)?instagram\.com/[^\s\"'<>]+", re.I),
    "twitter": re.compile(
        r"https?://(?:www\.)?(?:twitter|x)\.com/[^\s\"'<>]+", re.I
    ),
    "linkedin": re.compile(r"https?://(?:www\.)?linkedin\.com/[^\s\"'<>]+", re.I),
    "tiktok": re.compile(r"https?://(?:www\.)?tiktok\.com/@[^\s\"'<>]+", re.I),
    "yelp_url": re.compile(r"https?://(?:www\.)?yelp\.com/biz/[^\s\"'<>]+", re.I),
}

OWNER_KEYWORDS = [
    "owner",
    "founder",
    "proprietor",
    "chef-owner",
    "chef/owner",
    "managing partner",
    "general manager",
]

# Pages most likely to contain contact / about info
SUBPAGES = ["contact", "about", "about-us", "contact-us", "our-story", "team"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
}


class WebsiteScraper:
    """Scrape a restaurant's own website for emails, socials, and owner info."""

    def __init__(self, timeout: int = 12):
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def enrich_restaurant(self, restaurant: Restaurant) -> Restaurant:
        """Scrape the restaurant's website and fill missing fields."""
        if not restaurant.website:
            return restaurant

        base_url = restaurant.website
        if not base_url.startswith("http"):
            base_url = "https://" + base_url

        pages_html = self._fetch_pages(base_url)
        if not pages_html:
            logger.warning("Could not fetch any pages for %s", base_url)
            return restaurant

        all_text = ""
        all_html = ""
        for html in pages_html:
            all_html += html + "\n"
            soup = BeautifulSoup(html, "lxml")
            all_text += soup.get_text(separator=" ", strip=True) + "\n"

        if not restaurant.email_address:
            restaurant.email_address = self._extract_email(all_text, all_html, base_url)

        if not restaurant.phone_number:
            restaurant.phone_number = self._extract_phone(all_text)

        self._extract_socials(all_html, restaurant)
        self._extract_owner(all_text, restaurant)

        return restaurant

    def _fetch_pages(self, base_url: str) -> list[str]:
        pages = []

        # Fetch main page
        html = self._get(base_url)
        if html:
            pages.append(html)

        # Try common subpages
        for slug in SUBPAGES:
            url = urljoin(base_url.rstrip("/") + "/", slug)
            sub_html = self._get(url)
            if sub_html:
                pages.append(sub_html)

        return pages

    def _get(self, url: str) -> str | None:
        try:
            resp = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            if resp.status_code == 200 and "text/html" in resp.headers.get(
                "content-type", ""
            ):
                return resp.text
        except requests.RequestException as exc:
            logger.debug("Failed to fetch %s: %s", url, exc)
        return None

    def _extract_email(self, text: str, html: str, base_url: str) -> str:
        domain = urlparse(base_url).netloc.replace("www.", "")

        # Prefer mailto: links
        soup = BeautifulSoup(html, "lxml")
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            if href.startswith("mailto:"):
                email = href.replace("mailto:", "").split("?")[0].strip()
                if EMAIL_RE.match(email):
                    return email

        # Fall back to regex, prefer emails matching the restaurant's domain
        all_emails = EMAIL_RE.findall(text + " " + html)
        # Filter out common false positives
        filtered = [
            e
            for e in all_emails
            if not e.endswith((".png", ".jpg", ".gif", ".svg", ".webp"))
        ]

        domain_emails = [e for e in filtered if domain in e]
        if domain_emails:
            return domain_emails[0]
        if filtered:
            return filtered[0]
        return ""

    def _extract_phone(self, text: str) -> str:
        phones = PHONE_RE.findall(text)
        if phones:
            return phones[0].strip()
        return ""

    def _extract_socials(self, html: str, restaurant: Restaurant) -> None:
        for field_name, pattern in SOCIAL_PATTERNS.items():
            if getattr(restaurant, field_name):
                continue
            match = pattern.search(html)
            if match:
                url = match.group(0).rstrip("\"'>/),.")
                setattr(restaurant, field_name, url)

    def _extract_owner(self, text: str, restaurant: Restaurant) -> None:
        if restaurant.venue_owner:
            return

        for keyword in OWNER_KEYWORDS:
            # Pattern: "Owner: John Smith" or "Owner - John Smith" or "Owner John Smith"
            pattern = re.compile(
                rf"{keyword}\s*[:\-–—]?\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)",
                re.IGNORECASE,
            )
            match = pattern.search(text)
            if match:
                restaurant.venue_owner = match.group(1).strip()
                return
