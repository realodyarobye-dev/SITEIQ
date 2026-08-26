"""Geometry used by the block analysis and every distance figure in the app."""
import math

EARTH_MI = 3958.8
FEET_PER_MILE = 5280.0


def haversine_mi(lat1, lon1, lat2, lon2):
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return EARTH_MI * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def feet(mi):
    return mi * FEET_PER_MILE


def bearing(lat1, lon1, lat2, lon2):
    """Compass bearing in degrees from point 1 to point 2."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dl = math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return (math.degrees(math.atan2(y, x)) + 360) % 360


def compass(deg):
    points = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
              "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    return points[int((deg + 11.25) % 360 // 22.5)]


def walk_minutes(mi):
    """NYC sidewalk pace, ~3.1 mph with lights. Rounded up to the half minute."""
    return max(1, int(round(mi / 3.1 * 60)))


def angle_delta(a, b):
    d = abs(a - b) % 360
    return d if d <= 180 else 360 - d


def same_street_axis(site_bearing_to, street_axis_deg, tolerance=32):
    """True if a neighbour sits along the street axis rather than across it."""
    d = angle_delta(site_bearing_to, street_axis_deg)
    return min(d, 180 - d) <= tolerance


def dominant_axis(points, lat, lon):
    """Estimate the street's compass axis from the spread of nearby storefronts.

    Retail on a NYC block lines up along the street, so the direction that most
    neighbours lie in is a decent proxy for which way the street runs.
    Returns degrees 0-180, or None when there is not enough evidence.
    """
    bearings = []
    for p in points:
        plat, plon = p.get("lat"), p.get("lon")
        if plat is None or plon is None:
            continue
        d = haversine_mi(lat, lon, plat, plon)
        if 0.005 < d < 0.06:
            bearings.append(bearing(lat, lon, plat, plon) % 180)
    if len(bearings) < 4:
        return None
    # Circular mean over a 180-degree space.
    s = sum(math.sin(math.radians(b * 2)) for b in bearings)
    c = sum(math.cos(math.radians(b * 2)) for b in bearings)
    if abs(s) < 1e-9 and abs(c) < 1e-9:
        return None
    return (math.degrees(math.atan2(s, c)) / 2) % 180


def bbox(lat, lon, radius_mi):
    dlat = radius_mi / 69.0
    dlon = radius_mi / (69.0 * max(0.2, math.cos(math.radians(lat))))
    return lat - dlat, lon - dlon, lat + dlat, lon + dlon
