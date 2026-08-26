"""Address -> coordinates, with structured street parts we need later for
NYC record lookups (building number + street name)."""
import logging
import re

from ..config import GOOGLE_MAPS_API_KEY, HAS_GOOGLE
from ..core import cache
from ..core.http import get_json

log = logging.getLogger("siteiq.geocode")

NOMINATIM = "https://nominatim.openstreetmap.org/search"
GOOGLE_GEOCODE = "https://maps.googleapis.com/maps/api/geocode/json"

BOROUGH_HINTS = {
    "manhattan": "Manhattan", "new york, ny": "Manhattan", "new york county": "Manhattan",
    "brooklyn": "Brooklyn", "kings county": "Brooklyn",
    "queens": "Queens", "queens county": "Queens",
    "bronx": "Bronx", "bronx county": "Bronx",
    "staten island": "Staten Island", "richmond county": "Staten Island",
}


def _norm_query(address):
    a = " ".join(address.split())
    if "," not in a and not re.search(r"\b(ny|new york|brooklyn|queens|bronx|staten)\b", a, re.I):
        a += ", New York, NY"
    return a


def _nominatim(address):
    data = get_json(NOMINATIM, params={
        "q": address, "format": "jsonv2", "limit": 1, "addressdetails": 1,
        "countrycodes": "us",
    }, timeout=15)
    if not data:
        return None
    top = data[0]
    addr = top.get("address", {}) or {}
    return {
        "lat": float(top["lat"]),
        "lon": float(top["lon"]),
        "resolved": top.get("display_name", address),
        "house_number": addr.get("house_number"),
        "street": addr.get("road"),
        "city": addr.get("city") or addr.get("town") or addr.get("suburb"),
        "borough": addr.get("suburb") or addr.get("city_district") or addr.get("city"),
        "postcode": addr.get("postcode"),
        "state": addr.get("state"),
        "provider": "OpenStreetMap Nominatim",
    }


def _google(address):
    if not HAS_GOOGLE:
        return None
    data = get_json(GOOGLE_GEOCODE, params={"address": address, "key": GOOGLE_MAPS_API_KEY}, timeout=15)
    if not data or data.get("status") != "OK" or not data.get("results"):
        return None
    top = data["results"][0]
    loc = top["geometry"]["location"]
    parts = {c["types"][0]: c["long_name"] for c in top.get("address_components", []) if c.get("types")}
    return {
        "lat": loc["lat"],
        "lon": loc["lng"],
        "resolved": top.get("formatted_address", address),
        "house_number": parts.get("street_number"),
        "street": parts.get("route"),
        "city": parts.get("locality"),
        "borough": parts.get("sublocality_level_1") or parts.get("sublocality") or parts.get("locality"),
        "postcode": parts.get("postal_code"),
        "state": parts.get("administrative_area_level_1"),
        "provider": "Google Geocoding API",
    }


def geocode(address):
    """Returns a location dict or None. Google first when available (better on
    NYC unit/suite addresses), Nominatim otherwise and as fallback."""
    if not address or not address.strip():
        return None
    q = _norm_query(address)

    def produce():
        return _google(q) or _nominatim(q)

    result = cache.cached("geocode", (q, HAS_GOOGLE), produce)
    if not result:
        return None
    result["borough_norm"] = _borough(result)
    result["is_nyc"] = bool(result["borough_norm"])
    result["query"] = address
    return result


def _borough(loc):
    blob = " ".join(str(loc.get(k) or "") for k in ("resolved", "borough", "city")).lower()
    for hint, name in BOROUGH_HINTS.items():
        if hint in blob:
            return name
    return None
