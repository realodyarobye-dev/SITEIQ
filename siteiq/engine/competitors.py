"""Competitor intelligence.

Threat is not one number. A 24-hour bodega two doors down threatens a deli in a
completely different way than a sit-down restaurant with 2,000 reviews. So each
competitor is scored on three axes an operator actually feels - prepared food,
convenience/grab-and-go, and delivery - then rolled into an overall threat with
an explanation in plain language.
"""
import logging

from ..config import CONCEPTS
from ..core.geo import haversine_mi, walk_minutes
from ..core.provenance import INFERRED, OBSERVED, UNAVAILABLE, VERIFIED
from .classify import classify_google, classify_osm, label

log = logging.getLogger("siteiq.competitors")

THREAT_BANDS = [(78, "VERY HIGH"), (58, "HIGH"), (35, "MEDIUM"), (0, "LOW")]

# How much each nearby category competes with each concept, 0-1.
OVERLAP = {
    "deli": {"deli": 1.0, "convenience": 0.8, "supermarket": 0.55, "fast_food": 0.5,
             "coffee": 0.35, "bakery": 0.3, "restaurant": 0.2, "smoke_shop": 0.15},
    "deli_24h": {"deli": 1.0, "convenience": 0.85, "supermarket": 0.5, "fast_food": 0.6,
                 "coffee": 0.35, "bakery": 0.25, "restaurant": 0.25, "smoke_shop": 0.2},
    "convenience": {"convenience": 1.0, "deli": 0.85, "supermarket": 0.6, "pharmacy": 0.4,
                    "smoke_shop": 0.3, "fast_food": 0.2},
    "gourmet_market": {"supermarket": 0.9, "deli": 0.8, "convenience": 0.5, "bakery": 0.4,
                       "coffee": 0.3, "restaurant": 0.3},
    "supermarket": {"supermarket": 1.0, "deli": 0.4, "convenience": 0.4, "gourmet_market": 0.8},
    "cafe": {"coffee": 1.0, "bakery": 0.7, "deli": 0.45, "fast_food": 0.3, "convenience": 0.2},
    "fast_casual": {"fast_food": 1.0, "restaurant": 0.6, "deli": 0.55, "coffee": 0.2},
    "restaurant": {"restaurant": 1.0, "fast_food": 0.5, "deli": 0.2},
    "smoke_shop": {"smoke_shop": 1.0, "convenience": 0.4, "deli": 0.3, "liquor": 0.2},
    "pharmacy": {"pharmacy": 1.0, "supermarket": 0.3, "convenience": 0.25},
    "laundromat": {"laundry": 1.0},
    "barber": {"barber": 1.0},
}


def build(site, concept, google_places, osm_pois, longevity_lookup=None):
    """Returns a ranked list of competitor dicts with threat analysis."""
    lat, lon = site["lat"], site["lon"]
    overlap = OVERLAP.get(concept, OVERLAP["deli"])
    seen_names = {}
    out = []

    for g in google_places:
        cat = classify_google(g)
        weight = overlap.get(cat, 0)
        if weight < 0.15:
            continue
        if g.get("status") and g["status"] != "OPERATIONAL":
            continue
        d = g.get("distance_mi")
        if d is None or d > 0.5:
            continue
        rec = _from_google(g, cat, weight)
        out.append(rec)
        seen_names[_norm(rec["name"])] = rec

    # OSM fills gaps where Google is absent or the key is missing.
    for p in osm_pois:
        cat = classify_osm(p)
        weight = overlap.get(cat, 0)
        if weight < 0.15 or not p.get("name"):
            continue
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d > 0.5:
            continue
        key = _norm(p["name"])
        if key in seen_names:
            existing = seen_names[key]
            if not existing.get("hours_text") and p.get("opening_hours"):
                existing["hours_text"] = p["opening_hours"]
                if "24/7" in p["opening_hours"]:
                    existing["open_24h"] = True
            continue
        rec = _from_osm(p, cat, weight, d)
        out.append(rec)
        seen_names[key] = rec

    for rec in out:
        rec["walk_minutes"] = walk_minutes(rec["distance_mi"]) if rec["distance_mi"] else None
        if longevity_lookup:
            hist = longevity_lookup(rec["name"], rec.get("lat"), rec.get("lon"))
            if hist:
                rec["since"] = hist
        _score(rec, concept)

    out.sort(key=lambda r: (-r["threat_score"], r["distance_mi"] or 9))
    for i, rec in enumerate(out, 1):
        rec["rank"] = i
    return out


def _norm(name):
    return "".join(ch for ch in (name or "").lower() if ch.isalnum())[:22]


def _from_google(g, cat, weight):
    return {
        "name": g["name"], "category": cat, "category_label": label(cat),
        "overlap": weight, "distance_mi": g.get("distance_mi"),
        "lat": g.get("lat"), "lon": g.get("lon"), "address": g.get("address"),
        "rating": g.get("rating"), "reviews": g.get("reviews") or 0,
        "photo": g.get("photo"), "photo_attribution": g.get("photo_attribution"),
        "maps_uri": g.get("maps_uri"), "website": g.get("website"), "phone": g.get("phone"),
        "price_level": _price(g.get("price_level")), "open_now": g.get("open_now"),
        "open_24h": g.get("open_24h"), "hours": g.get("hours") or [],
        "hours_text": "; ".join(g.get("hours") or []) or None,
        "summary": g.get("summary"),
        "evidence": OBSERVED, "source": "Google Places API",
        "since": None,
    }


def _from_osm(p, cat, weight, d):
    hours = p.get("opening_hours")
    return {
        "name": p["name"], "category": cat, "category_label": label(cat),
        "overlap": weight, "distance_mi": d, "lat": p["lat"], "lon": p["lon"],
        "address": " ".join(x for x in [p.get("housenumber"), p.get("street")] if x) or None,
        "rating": None, "reviews": 0, "photo": None, "photo_attribution": None,
        "maps_uri": f"https://www.openstreetmap.org/{p.get('osm_id', '')}",
        "website": p.get("website"), "phone": p.get("phone"), "price_level": None,
        "open_now": None, "open_24h": bool(hours and "24/7" in hours),
        "hours": [hours] if hours else [], "hours_text": hours, "summary": None,
        "evidence": VERIFIED, "source": "OpenStreetMap",
        "since": {"year": int(p["start_date"][:4]), "source": "OpenStreetMap start_date tag",
                  "statement": f"Confirmed operating since at least {p['start_date'][:4]}"}
        if (p.get("start_date") or "")[:4].isdigit() else None,
    }


def _price(level):
    return {"PRICE_LEVEL_FREE": "Free", "PRICE_LEVEL_INEXPENSIVE": "$",
            "PRICE_LEVEL_MODERATE": "$$", "PRICE_LEVEL_EXPENSIVE": "$$$",
            "PRICE_LEVEL_VERY_EXPENSIVE": "$$$$"}.get(level)


def _score(rec, concept):
    """Three threat axes plus an overall score, each with a written reason."""
    cfg = CONCEPTS.get(concept, CONCEPTS["deli"])
    d = rec["distance_mi"] or 0.5
    reviews = rec.get("reviews") or 0
    rating = rec.get("rating")
    cat = rec["category"]

    # Proximity: a competitor 200 feet away is a different animal at 0.4 mi.
    if d <= 0.04:
        prox = 1.0
    elif d <= 0.1:
        prox = 0.85
    elif d <= 0.2:
        prox = 0.6
    elif d <= 0.35:
        prox = 0.38
    else:
        prox = 0.2

    # Strength from review volume and quality. Reviews are the only public proxy
    # for traffic we have; we say so rather than pretending it is foot traffic.
    if reviews >= 1500:
        vol = 1.0
    elif reviews >= 600:
        vol = 0.85
    elif reviews >= 250:
        vol = 0.68
    elif reviews >= 80:
        vol = 0.5
    elif reviews >= 20:
        vol = 0.33
    elif reviews > 0:
        vol = 0.2
    else:
        vol = 0.28  # unknown, not zero

    quality = 0.5
    if rating:
        quality = max(0.15, min(1.0, (rating - 2.6) / 1.9))
    strength = 0.62 * vol + 0.38 * quality

    prepared = _axis(cat in ("deli", "fast_food", "restaurant", "coffee", "bakery", "gourmet_market"),
                     strength, prox, rec["overlap"])
    convenience = _axis(cat in ("deli", "convenience", "supermarket", "pharmacy", "smoke_shop"),
                        strength, prox, rec["overlap"])
    delivery = _axis(cat in ("deli", "fast_food", "restaurant", "convenience", "coffee"),
                     strength * (1.0 if reviews > 150 else 0.75), max(prox, 0.55), rec["overlap"])

    if not cfg["prepared_food"]:
        prepared *= 0.4

    overall = 100 * rec["overlap"] * (0.46 * strength + 0.42 * prox + 0.12 * (1 if rec.get("open_24h") else 0.3))
    if rec.get("open_24h"):
        overall *= 1.12
    if rec.get("since") and rec["since"].get("year", 9999) <= 2015:
        overall *= 1.08
    overall = round(min(100, overall), 1)

    rec.update({
        "threat_score": overall,
        "threat": _band(overall),
        "prepared_food_threat": _band(prepared),
        "convenience_threat": _band(convenience),
        "delivery_threat": _band(delivery),
        "strength_index": round(strength * 100),
        "why": _why(rec, cat, d, reviews, rating, overall),
    })


def _axis(applies, strength, prox, overlap):
    if not applies:
        return 12 * overlap
    return min(100, 100 * overlap * (0.55 * strength + 0.45 * prox))


def _band(score):
    for cutoff, name in THREAT_BANDS:
        if score >= cutoff:
            return name
    return "LOW"


def _why(rec, cat, d, reviews, rating, overall):
    bits = []
    ft = int(d * 5280)
    if d <= 0.05:
        bits.append(f"Roughly {ft} feet away - same pedestrian flow as your door")
    elif d <= 0.15:
        bits.append(f"{d:.2f} mi away, a {walk_minutes(d)}-minute walk")
    else:
        bits.append(f"{d:.2f} mi away")

    if reviews >= 600:
        bits.append(f"heavy review volume ({reviews:,}) indicating a well-known, high-traffic operator")
    elif reviews >= 150:
        bits.append(f"solid neighbourhood recognition ({reviews:,} reviews)")
    elif reviews > 0:
        bits.append(f"modest public profile ({reviews:,} reviews)")
    else:
        bits.append("no public review data available, so its real strength is unverified")

    if rating and rating >= 4.5:
        bits.append(f"strong {rating}★ rating")
    elif rating and rating <= 3.7:
        bits.append(f"weak {rating}★ rating - a quality gap you can attack")

    if rec.get("open_24h"):
        bits.append("operates 24 hours, which locks up the overnight daypart")
    if rec.get("since"):
        bits.append(rec["since"]["statement"].lower())
    if rec.get("price_level"):
        bits.append(f"price level {rec['price_level']}")

    verdict = {
        "VERY HIGH": "This is a genuine obstacle. Assume they hold the block unless you clearly beat them on food, hours or service.",
        "HIGH": "A real competitor. You need a specific reason customers switch.",
        "MEDIUM": "Competes for some of your business but does not own the corner.",
        "LOW": "Minor overlap. Not a reason to walk away from the deal.",
    }[_band(overall)]
    return ". ".join(b[0].upper() + b[1:] for b in bits) + ". " + verdict


def summarize(competitors, concept):
    """Aggregate competitive picture used by scoring, opportunities and risks."""
    direct = [c for c in competitors if c["overlap"] >= 0.75]
    close = [c for c in competitors if (c["distance_mi"] or 9) <= 0.15]
    strongest = competitors[0] if competitors else None

    with_reviews = [c for c in competitors if c.get("reviews")]
    avg_rating = None
    rated = [c["rating"] for c in competitors if c.get("rating")]
    if rated:
        avg_rating = round(sum(rated) / len(rated), 2)

    open_24 = [c for c in competitors if c.get("open_24h")]
    weak = [c for c in competitors if c.get("rating") and c["rating"] < 3.9 and c["overlap"] >= 0.7]

    # Saturation: weighted competitor pressure inside a quarter mile.
    pressure = sum(c["overlap"] * (1.0 if (c["distance_mi"] or 1) <= 0.1 else 0.5)
                   for c in competitors if (c["distance_mi"] or 9) <= 0.25)

    return {
        "total": len(competitors),
        "direct_count": len(direct),
        "within_block": len(close),
        "strongest": strongest,
        "top": competitors[:12],
        "avg_rating": avg_rating,
        "rated_count": len(rated),
        "review_coverage": len(with_reviews),
        "open_24h_count": len(open_24),
        "open_24h": open_24[:5],
        "weak_incumbents": weak[:5],
        "pressure": round(pressure, 2),
        "saturation_label": _saturation(pressure),
        "evidence": OBSERVED if with_reviews else (VERIFIED if competitors else UNAVAILABLE),
    }


def _saturation(pressure):
    if pressure >= 9:
        return "Extremely saturated"
    if pressure >= 6:
        return "Heavily competitive"
    if pressure >= 3.5:
        return "Normally competitive"
    if pressure >= 1.5:
        return "Lightly competitive"
    return "Thin competition"
