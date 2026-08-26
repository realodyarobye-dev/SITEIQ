"""Demand generators: what physically puts people on this sidewalk.

Each generator gets a relevance score for THIS concept, plus a sentence saying
why it matters - a hospital matters to a 24-hour deli in a way it never matters
to a barber shop.
"""
from ..core.geo import feet, haversine_mi, walk_minutes
from ..core.provenance import INFERRED, VERIFIED
from .classify import DEMAND_CATEGORIES, classify_osm, label

# Base pull strength of each generator type, and how far its influence carries.
GENERATOR_POWER = {
    "transit": (100, 0.25),
    "hospital": (85, 0.35),
    "college": (80, 0.4),
    "office": (70, 0.25),
    "school": (65, 0.2),
    "hotel": (62, 0.25),
    "nightlife": (58, 0.2),
    "gym": (48, 0.18),
    "government": (55, 0.25),
    "attraction": (70, 0.35),
    "park": (42, 0.25),
    "bus": (38, 0.12),
    "residential": (45, 0.15),
}

# Multiplier by concept: how much this concept actually monetises that crowd.
RELEVANCE = {
    "deli":        {"transit": 1.15, "office": 1.2, "hospital": 1.15, "school": 1.05,
                    "college": 1.0, "hotel": 0.85, "nightlife": 0.85, "gym": 0.8,
                    "government": 1.0, "attraction": 0.7, "park": 0.75, "bus": 0.9,
                    "residential": 1.15},
    "deli_24h":    {"transit": 1.2, "office": 1.05, "hospital": 1.45, "school": 0.9,
                    "college": 1.15, "hotel": 1.15, "nightlife": 1.4, "gym": 0.8,
                    "government": 0.85, "attraction": 0.9, "park": 0.7, "bus": 0.95,
                    "residential": 1.15},
    "convenience": {"transit": 1.2, "office": 0.9, "hospital": 1.0, "school": 1.15,
                    "college": 1.05, "hotel": 0.9, "nightlife": 0.9, "gym": 0.75,
                    "government": 0.85, "attraction": 0.8, "park": 0.8, "bus": 1.0,
                    "residential": 1.2},
    "gourmet_market": {"transit": 0.85, "office": 1.15, "hospital": 0.9, "school": 0.7,
                       "college": 0.75, "hotel": 1.0, "nightlife": 0.6, "gym": 1.0,
                       "government": 0.8, "attraction": 0.8, "park": 0.85,
                       "bus": 0.6, "residential": 1.35},
    "supermarket": {"transit": 0.9, "office": 0.6, "hospital": 0.7, "school": 0.8,
                    "college": 0.8, "hotel": 0.4, "nightlife": 0.4, "gym": 0.6,
                    "government": 0.6, "attraction": 0.4, "park": 0.7, "bus": 0.8,
                    "residential": 1.6},
    "cafe":        {"transit": 1.25, "office": 1.45, "hospital": 1.05, "school": 0.8,
                    "college": 1.3, "hotel": 1.1, "nightlife": 0.5, "gym": 1.0,
                    "government": 1.1, "attraction": 0.9, "park": 0.95, "bus": 0.9,
                    "residential": 1.0},
    "fast_casual": {"transit": 1.1, "office": 1.4, "hospital": 1.15, "school": 0.95,
                    "college": 1.25, "hotel": 0.9, "nightlife": 0.95, "gym": 0.9,
                    "government": 1.1, "attraction": 0.9, "park": 0.8, "bus": 0.8,
                    "residential": 0.95},
    "restaurant":  {"transit": 0.95, "office": 1.15, "hospital": 0.8, "school": 0.6,
                    "college": 1.0, "hotel": 1.35, "nightlife": 1.25, "gym": 0.7,
                    "government": 0.85, "attraction": 1.25, "park": 0.9, "bus": 0.6,
                    "residential": 1.05},
    "smoke_shop":  {"transit": 1.1, "office": 0.85, "hospital": 0.6, "school": 0.5,
                    "college": 1.3, "hotel": 0.8, "nightlife": 1.35, "gym": 0.5,
                    "government": 0.6, "attraction": 0.7, "park": 0.7, "bus": 0.9,
                    "residential": 1.0},
    "pharmacy":    {"transit": 1.0, "office": 0.8, "hospital": 1.55, "school": 0.8,
                    "college": 0.8, "hotel": 0.7, "nightlife": 0.4, "gym": 0.6,
                    "government": 0.8, "attraction": 0.5, "park": 0.7, "bus": 0.9,
                    "residential": 1.35},
    "laundromat":  {"transit": 0.7, "office": 0.3, "hospital": 0.5, "school": 0.6,
                    "college": 1.15, "hotel": 0.3, "nightlife": 0.3, "gym": 0.5,
                    "government": 0.4, "attraction": 0.2, "park": 0.4, "bus": 0.7,
                    "residential": 1.8},
    "barber":      {"transit": 0.9, "office": 0.9, "hospital": 0.6, "school": 0.8,
                    "college": 1.0, "hotel": 0.5, "nightlife": 0.7, "gym": 0.9,
                    "government": 0.6, "attraction": 0.4, "park": 0.5, "bus": 0.8,
                    "residential": 1.5},
}

WHY = {
    "transit": "Subway and rail entrances put a repeating wave of commuters past the door every weekday morning and evening. This is the single most reliable NYC traffic source.",
    "bus": "Bus stops create short waiting periods directly outside - good for drinks, snacks and coffee.",
    "office": "Office workers buy breakfast and lunch five days a week and stop dead on weekends. Strong weekday ticket, weak Sunday.",
    "hospital": "Hospitals run 24 hours. Staff shift changes create demand at hours nothing else does, including overnight, and they are fiercely loyal to whoever is open.",
    "school": "Schools deliver a sharp morning drop-off rush and a 3pm snack rush. Low ticket, very high frequency, and parents come with them.",
    "college": "Students buy cheap prepared food, drinks and snacks at all hours, and drive late-night volume during term. Expect a summer dip.",
    "hotel": "Hotel guests buy water, snacks, breakfast and late-night convenience items, and they do not price-compare.",
    "nightlife": "Bars and clubs generate late-night food and drink demand, concentrated Thursday to Saturday.",
    "gym": "Gym members buy drinks, protein and light food on the way in and out, peaking early morning and after work.",
    "government": "Government offices bring steady weekday staff and visitor traffic, usually with a hard weekday-only pattern.",
    "attraction": "Visitor attractions add discretionary spend and weekend traffic that residential blocks do not get.",
    "park": "Parks add weekend and warm-weather traffic - drinks, ice, snacks - and are seasonal.",
    "residential": "Residential density is the base load. It is what keeps you alive on a rainy Tuesday when nothing else is moving.",
}


def build(site, concept, pois, pluto=None):
    lat, lon = site["lat"], site["lon"]
    relevance = RELEVANCE.get(concept, RELEVANCE["deli"])
    out = []
    counts = {}

    for p in pois:
        cat = classify_osm(p)
        if cat not in DEMAND_CATEGORIES:
            continue
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        power, reach = GENERATOR_POWER.get(cat, (30, 0.2))
        if d > reach * 2.6:
            continue
        counts[cat] = counts.get(cat, 0) + 1
        decay = max(0.0, 1 - (d / (reach * 2.6)) ** 1.4)
        score = power * decay * relevance.get(cat, 1.0)
        if score < 4:
            continue
        name = p.get("name")
        if not name and cat not in ("bus", "residential"):
            continue
        out.append({
            "name": name or ("Bus stop" if cat == "bus" else "Residential building"),
            "category": cat, "category_label": label(cat),
            "distance_mi": round(d, 3), "distance_ft": int(feet(d)),
            "walk_minutes": walk_minutes(d),
            "lat": p["lat"], "lon": p["lon"],
            "relevance": round(min(100, score)),
            "why": WHY.get(cat, "Adds general pedestrian activity nearby."),
            "evidence": VERIFIED, "source": "OpenStreetMap",
        })

    # Named large residential buildings from PLUTO are stronger evidence than
    # OSM building tags, so add them where available.
    if pluto and pluto.get("available"):
        for b in pluto.get("large_residential_buildings", [])[:5]:
            out.append({
                "name": f"{b['address']} ({b['units']} units, {b['floors']} floors)",
                "category": "residential", "category_label": "Large residential building",
                "distance_mi": 0.03, "distance_ft": 160, "walk_minutes": 1,
                "lat": None, "lon": None,
                "relevance": min(100, 30 + b["units"] // 6),
                "why": WHY["residential"],
                "evidence": VERIFIED, "source": "NYC PLUTO tax-lot records",
            })

    out.sort(key=lambda x: -x["relevance"])
    deduped, seen = [], set()
    for g in out:
        k = (g["name"].lower()[:26], g["category"])
        if k in seen:
            continue
        seen.add(k)
        deduped.append(g)

    strength = {}
    for cat in GENERATOR_POWER:
        items = [g for g in deduped if g["category"] == cat]
        strength[cat] = min(100, round(sum(g["relevance"] for g in items[:6]) * 0.55)) if items else 0

    return {
        "items": deduped[:40],
        "top": deduped[:10],
        "counts": counts,
        "strength": strength,
        "total_pull": round(min(100, sum(g["relevance"] for g in deduped[:18]) / 9), 1),
        "evidence": VERIFIED,
    }
