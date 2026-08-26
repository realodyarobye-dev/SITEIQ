"""OpenStreetMap via Overpass.

This is the backbone of the free tier: it maps the businesses, transit,
schools, hospitals, hotels, offices, parks and nightlife around a site with no
API key required. Overpass instances go down regularly, so we fail over across
mirrors and cache aggressively.
"""
import logging

from ..config import OVERPASS_ENDPOINTS, SEARCH_RADIUS_M
from ..core import cache
from ..core.http import post_json

log = logging.getLogger("siteiq.overpass")

# One query, everything we need. Restricted to tags that actually matter for
# street retail so the payload stays manageable.
QUERY_TEMPLATE = """[out:json][timeout:60];
(
  nwr(around:{r},{lat},{lon})[shop];
  nwr(around:{r},{lat},{lon})[amenity];
  nwr(around:{r},{lat},{lon})[office];
  nwr(around:{r},{lat},{lon})[tourism];
  nwr(around:{r},{lat},{lon})[leisure];
  nwr(around:{r},{lat},{lon})[healthcare];
  nwr(around:{r},{lat},{lon})[railway~"^(station|subway_entrance|tram_stop)$"];
  nwr(around:{r},{lat},{lon})[public_transport~"^(station|stop_position|platform)$"];
  nwr(around:{r},{lat},{lon})[highway=bus_stop];
  nwr(around:{r},{lat},{lon})[building~"^(apartments|residential|commercial|office|dormitory|retail|hotel|hospital|school|university)$"];
  nwr(around:{r},{lat},{lon})[landuse~"^(retail|commercial|residential)$"];
);
out tags center 1200;"""

# Streets near the site, used to work out which way the block runs and whether
# the corner is a real intersection.
STREET_QUERY = """[out:json][timeout:30];
way(around:{r},{lat},{lon})[highway~"^(primary|secondary|tertiary|residential|unclassified|living_street|pedestrian)$"];
out tags geom 200;"""


def _run(query):
    for endpoint in OVERPASS_ENDPOINTS:
        data = post_json(endpoint, data={"data": query}, timeout=60, retries=0,
                         headers={"Content-Type": "application/x-www-form-urlencoded"})
        if data and "elements" in data:
            return data["elements"]
        log.warning("overpass endpoint failed: %s", endpoint)
    return None


def fetch_pois(lat, lon, radius_m=SEARCH_RADIUS_M):
    def produce():
        q = QUERY_TEMPLATE.format(r=radius_m, lat=lat, lon=lon)
        elements = _run(q)
        if elements is None:
            return None
        return [_flatten(e) for e in elements if _flatten(e)]

    return cache.cached("overpass", ("pois", round(lat, 5), round(lon, 5), radius_m), produce) or []


def fetch_streets(lat, lon, radius_m=140):
    def produce():
        q = STREET_QUERY.format(r=radius_m, lat=lat, lon=lon)
        elements = _run(q)
        if elements is None:
            return None
        out = []
        for e in elements:
            geom = e.get("geometry") or []
            if len(geom) < 2:
                continue
            out.append({
                "name": (e.get("tags") or {}).get("name"),
                "highway": (e.get("tags") or {}).get("highway"),
                "oneway": (e.get("tags") or {}).get("oneway"),
                "lanes": (e.get("tags") or {}).get("lanes"),
                "geom": [[p["lat"], p["lon"]] for p in geom],
            })
        return out

    return cache.cached("overpass", ("streets", round(lat, 5), round(lon, 5), radius_m), produce) or []


def _flatten(e):
    tags = e.get("tags") or {}
    if not tags:
        return None
    lat = e.get("lat") or (e.get("center") or {}).get("lat")
    lon = e.get("lon") or (e.get("center") or {}).get("lon")
    if lat is None or lon is None:
        return None
    return {
        "osm_id": f"{e.get('type', 'n')}/{e.get('id')}",
        "lat": lat,
        "lon": lon,
        "name": tags.get("name"),
        "brand": tags.get("brand"),
        "operator": tags.get("operator"),
        "shop": tags.get("shop"),
        "amenity": tags.get("amenity"),
        "office": tags.get("office"),
        "tourism": tags.get("tourism"),
        "leisure": tags.get("leisure"),
        "healthcare": tags.get("healthcare"),
        "railway": tags.get("railway"),
        "public_transport": tags.get("public_transport"),
        "highway": tags.get("highway"),
        "building": tags.get("building"),
        "landuse": tags.get("landuse"),
        "cuisine": tags.get("cuisine"),
        "opening_hours": tags.get("opening_hours"),
        "start_date": tags.get("start_date"),
        "levels": tags.get("building:levels"),
        "housename": tags.get("name") or tags.get("addr:housename"),
        "housenumber": tags.get("addr:housenumber"),
        "street": tags.get("addr:street"),
        "website": tags.get("website"),
        "phone": tags.get("phone"),
        "wheelchair": tags.get("wheelchair"),
        "vacant": tags.get("disused:shop") or tags.get("was:shop") or tags.get("vacant"),
    }
