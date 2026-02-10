"""Data models for restaurant information."""

from dataclasses import dataclass, field, asdict
from typing import Optional


@dataclass
class Restaurant:
    """Represents a restaurant's business information."""

    venue_name: str = ""
    website: str = ""
    phone_number: str = ""
    email_address: str = ""
    venue_address: str = ""
    city: str = ""
    state: str = ""
    zip_code: str = ""
    country: str = ""
    venue_owner: str = ""
    cuisine_type: str = ""
    rating: Optional[float] = None
    price_level: str = ""
    facebook: str = ""
    instagram: str = ""
    twitter: str = ""
    linkedin: str = ""
    tiktok: str = ""
    yelp_url: str = ""
    google_place_id: str = ""
    hours_of_operation: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def merge(self, other: "Restaurant") -> None:
        """Merge non-empty fields from another Restaurant into this one."""
        for fld in self.__dataclass_fields__:
            other_val = getattr(other, fld)
            current_val = getattr(self, fld)
            if other_val and not current_val:
                setattr(self, fld, other_val)

    @property
    def full_address(self) -> str:
        parts = [self.venue_address, self.city, self.state, self.zip_code, self.country]
        return ", ".join(p for p in parts if p)

    def hubspot_contact_dict(self) -> dict:
        """Format data for HubSpot company import."""
        return {
            "name": self.venue_name,
            "domain": self.website,
            "phone": self.phone_number,
            "address": self.venue_address,
            "city": self.city,
            "state": self.state,
            "zip": self.zip_code,
            "country": self.country,
            "description": self.cuisine_type,
            "website": self.website,
            "facebook_company_page": self.facebook,
            "twitterhandle": self.twitter,
            "linkedin_company_page": self.linkedin,
            "owner_name": self.venue_owner,
            "email": self.email_address,
            "instagram": self.instagram,
            "tiktok": self.tiktok,
            "yelp_url": self.yelp_url,
            "rating": self.rating,
            "price_level": self.price_level,
            "hours_of_operation": self.hours_of_operation,
        }
