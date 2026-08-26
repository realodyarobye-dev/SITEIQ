"""Google Places (New) and Street View Static.

Optional. Without a key SiteIQ still produces a full report from OSM, Census and
NYC Open Data - it just loses ratings, review counts, opening hours, photos and
storefront imagery. Nothing here is ever fabricated when the key is missing.
"""
import logging
from concurrent.futures import ThreadPoolExecutor

from ..config import GOOGLE_MAPS_API_KEY, HAS_GOOGLE
from ..core import cache
from ..core.http import get_bytes, get_json, post_json

log = logging.getLogger("siteiq.google")

NEARBY = "https://places.googleapis.com/v1/places:searchNearby"
TEXT = "https://places.googleapis.com/v1/places:searchText"
STREETVIEW_META = "https://maps.googleapis.com/maps/api/streetview/metadata"
STREETVIEW_IMG = "https://maps.googleapis.com/maps/api/streetview"

FIELD_MASK = ",".join([
    "places.id", "places.displayName", "places.formattedAddress", "places.location",
    "places.rating", "places.userRatingCount", "places.currentOpeningHours",
    "places.regularOpeningHours", "places.primaryType", "places.primaryTypeDisplayName",
    "places.types", "places.photos", "places.googleMapsUri", "places.websiteUri",
    "places.nationalPhoneNumber", "places.priceLevel", "places.businessStatus",
    "places.editorialSummary",
])


def _headers():
    return {"X-Goog-Api-Key": GOOGLE_MAPS_API_KEY, "X-Goog-FieldMask": FIELD_MASK,
            "Content-Type": "application/json"}


def _nearby(lat, lon, types, radius_m, limit=20):
    body = {
        "includedTypes": types,
        "maxResultCount": min(20, limit),
        "rankPreference": "DISTANCE",
        "locationRestriction": {"circle": {
            "center": {"latitude": lat, "longitude": lon}, "radius": float(radius_m)}},
    }
    data = post_json(NEARBY, json=body, headers=_headers(), timeout=25)
    if data is None:
        return []
    if "error" in data:
        log.error("Places API error: %s", str(data.get("error", {}).get("message"))[:200])
        return []
    return data.get("places", []) or []


def _text(lat, lon, query, radius_m):
    body = {
        "textQuery": query,
        "maxResultCount": 20,
        "locationBias": {"circle": {
            "center": {"latitude": lat, "longitude": lon}, "radius": float(radius_m)}},
    }
    data = post_json(TEXT, json=body, headers=_headers(), timeout=25)
    if data is None or "error" in data:
        return []
    return data.get("places", []) or []


def search(lat, lon, type_groups, radius_m, text_queries=()):
    """Runs several Places queries in parallel and de-duplicates by place id."""
    if not HAS_GOOGLE:
        return []

    def produce():
        results = {}
        tasks = []
        with ThreadPoolExecutor(max_workers=6) as pool:
            for group in type_groups:
                tasks.append(pool.submit(_nearby, lat, lon, list(group), radius_m))
            for q in text_queries:
                tasks.append(pool.submit(_text, lat, lon, q, radius_m))
            for t in tasks:
                try:
                    for p in t.result() or []:
                        if p.get("id"):
                            results.setdefault(p["id"], p)
                except Exception as exc:  # noqa: BLE001
                    log.warning("places task failed: %s", exc)
        return list(results.values())

    return cache.cached("places", (round(lat, 5), round(lon, 5), radius_m,
                                   sorted(tuple(sorted(g)) for g in type_groups),
                                   sorted(text_queries)), produce) or []


def normalize(p, lat, lon):
    """Google's payload -> SiteIQ's flat competitor shape."""
    from ..core.geo import haversine_mi
    loc = p.get("location") or {}
    plat, plon = loc.get("latitude"), loc.get("longitude")
    hours = p.get("regularOpeningHours") or {}
    current = p.get("currentOpeningHours") or {}
    descriptions = hours.get("weekdayDescriptions") or []
    return {
        "id": p.get("id"),
        "name": (p.get("displayName") or {}).get("text") or "Unnamed business",
        "address": p.get("formattedAddress"),
        "lat": plat, "lon": plon,
        "distance_mi": haversine_mi(lat, lon, plat, plon) if plat and plon else None,
        "rating": p.get("rating"),
        "reviews": p.get("userRatingCount") or 0,
        "primary_type": (p.get("primaryTypeDisplayName") or {}).get("text") or p.get("primaryType"),
        "types": p.get("types") or [],
        "photo": ((p.get("photos") or [{}])[0] or {}).get("name"),
        "photo_attribution": _attribution(p),
        "maps_uri": p.get("googleMapsUri"),
        "website": p.get("websiteUri"),
        "phone": p.get("nationalPhoneNumber"),
        "price_level": p.get("priceLevel"),
        "status": p.get("businessStatus"),
        "open_now": current.get("openNow"),
        "hours": descriptions,
        "open_24h": _is_24h(descriptions, hours),
        "summary": (p.get("editorialSummary") or {}).get("text"),
        "source": "Google Places API",
    }


def _attribution(p):
    photos = p.get("photos") or []
    if not photos:
        return None
    attrs = photos[0].get("authorAttributions") or []
    return attrs[0].get("displayName") if attrs else None


def _is_24h(descriptions, hours):
    text = " ".join(descriptions).lower()
    if "open 24 hours" in text:
        return True
    periods = hours.get("periods") or []
    if len(periods) == 1 and not periods[0].get("close"):
        return True
    return False


def photo_bytes(photo_name, max_width=900):
    """Fetch a Places photo. Returns bytes or None; never a placeholder image."""
    if not HAS_GOOGLE or not photo_name:
        return None
    if not photo_name.startswith("places/") or "/photos/" not in photo_name:
        log.warning("rejected suspicious photo name")
        return None
    meta = get_json(f"https://places.googleapis.com/v1/{photo_name}/media", params={
        "maxWidthPx": max_width, "skipHttpRedirect": "true", "key": GOOGLE_MAPS_API_KEY,
    }, timeout=15)
    if not meta or not meta.get("photoUri"):
        return None
    return get_bytes(meta["photoUri"], timeout=20)


def streetview(lat, lon, heading=None, size="640x400"):
    """Returns (bytes, metadata) or (None, None). We check metadata first so we
    never present a grey 'no imagery' tile as a storefront photo."""
    if not HAS_GOOGLE:
        return None, None

    def produce_meta():
        return get_json(STREETVIEW_META, params={
            "location": f"{lat},{lon}", "key": GOOGLE_MAPS_API_KEY, "radius": 40,
        }, timeout=12)

    meta = cache.cached("streetview", (round(lat, 6), round(lon, 6)), produce_meta)
    if not meta or meta.get("status") != "OK":
        return None, None
    params = {"location": f"{lat},{lon}", "size": size, "key": GOOGLE_MAPS_API_KEY,
              "fov": 80, "pitch": 8, "radius": 40, "return_error_code": "true"}
    if heading is not None:
        params["heading"] = int(heading)
    img = get_bytes(STREETVIEW_IMG, params=params, timeout=20)
    return img, {"date": meta.get("date"), "copyright": meta.get("copyright"),
                 "pano_id": meta.get("pano_id")}


def streetview_available(lat, lon):
    if not HAS_GOOGLE:
        return None
    meta = cache.cached("streetview", (round(lat, 6), round(lon, 6)), lambda: get_json(
        STREETVIEW_META, params={"location": f"{lat},{lon}", "key": GOOGLE_MAPS_API_KEY,
                                 "radius": 40}, timeout=12))
    if not meta or meta.get("status") != "OK":
        return None
    return {"date": meta.get("date"), "copyright": meta.get("copyright")}
