"""THE BLOCK.

The section that should read like somebody walked the sidewalk. We work out
which way the street runs from the geometry of nearby streets, then sort the
neighbouring businesses into what is to your left, to your right, across the
street, and on the corner.

Everything here is geometry over public map data, so it is labelled INFERRED,
not observed. It replaces a site visit for triage - never for a signature.
"""
import logging

from ..core.geo import (angle_delta, bearing, compass, dominant_axis, feet,
                        haversine_mi, walk_minutes)
from ..core.provenance import INFERRED, UNAVAILABLE, VERIFIED
from .classify import CATEGORY_META, classify_osm, label

log = logging.getLogger("siteiq.block")

BLOCK_RADIUS_MI = 0.045   # about 240 feet, roughly a NYC short block face
CORNER_RADIUS_MI = 0.035


def analyse(site, pois, streets, building_records=None, construction=None):
    lat, lon = site["lat"], site["lon"]

    neighbours = []
    for p in pois:
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d > BLOCK_RADIUS_MI or not p.get("name"):
            continue
        cat = classify_osm(p)
        if cat in ("other",):
            continue
        b = bearing(lat, lon, p["lat"], p["lon"])
        neighbours.append({
            "name": p["name"], "category": cat, "category_label": label(cat),
            "distance_ft": int(feet(d)), "distance_mi": d,
            "bearing": round(b), "compass": compass(b),
            "lat": p["lat"], "lon": p["lon"],
            "address": " ".join(x for x in [p.get("housenumber"), p.get("street")] if x) or None,
            "hours": p.get("opening_hours"),
        })
    neighbours.sort(key=lambda x: x["distance_ft"])

    axis = dominant_axis(pois, lat, lon)
    street_info = _streets(streets, lat, lon)
    if axis is None and street_info["primary_axis"] is not None:
        axis = street_info["primary_axis"]

    left, right, across, same_block, corner = [], [], [], [], []
    if axis is not None:
        for n in neighbours:
            delta = angle_delta(n["bearing"], axis)
            along = min(delta, 180 - delta) <= 34
            if along:
                same_block.append(n)
                forward = angle_delta(n["bearing"], axis) <= 90
                (right if forward else left).append(n)
            else:
                across.append(n)
    else:
        same_block = neighbours[:]

    for n in neighbours:
        if n["distance_mi"] <= CORNER_RADIUS_MI and street_info["intersection_nearby"]:
            corner.append(n)

    vacancy = _vacancy_signal(pois, lat, lon)

    entrances = {
        "transit": [n for n in neighbours if n["category"] in ("transit", "bus")],
        "residential": _residential_entrances(pois, lat, lon),
        "office": [n for n in neighbours if n["category"] == "office"],
        "schools": [n for n in neighbours if n["category"] in ("school", "college")],
    }

    active_construction = []
    if construction and construction.get("available"):
        active_construction = construction.get("permits", [])[:8]

    return {
        "street_axis_deg": round(axis) if axis is not None else None,
        "street_axis_desc": _axis_desc(axis),
        "streets": street_info,
        "neighbours": neighbours[:40],
        "immediate_left": left[:6],
        "immediate_right": right[:6],
        "across_street": across[:10],
        "same_block": same_block[:20],
        "corner_businesses": corner[:8],
        "is_corner": street_info["intersection_nearby"],
        "storefront_count": len(neighbours),
        "food_neighbours": len([n for n in neighbours if n["category"] in
                                ("deli", "convenience", "restaurant", "fast_food", "coffee",
                                 "bakery", "supermarket")]),
        "vacancy": vacancy,
        "entrances": entrances,
        "construction": active_construction,
        "construction_count": construction.get("count", 0) if construction else 0,
        "building": building_records or {"available": False},
        "retail_continuity": _continuity(len(neighbours)),
        "evidence": INFERRED if axis is not None else VERIFIED,
        "method": ("Street axis inferred from the alignment of mapped storefronts and road "
                   "geometry. Left/right/across is a computed estimate, not a survey."),
        "walk_note": "Everything listed here is within about a 1-minute walk of the door.",
    }


def _streets(streets, lat, lon):
    named = []
    seen = set()
    for s in streets or []:
        if not s.get("name") or s["name"] in seen:
            continue
        seen.add(s["name"])
        pts = s.get("geom") or []
        if len(pts) < 2:
            continue
        nearest = min(haversine_mi(lat, lon, p[0], p[1]) for p in pts)
        ax = bearing(pts[0][0], pts[0][1], pts[-1][0], pts[-1][1]) % 180
        named.append({"name": s["name"], "distance_ft": int(feet(nearest)), "axis": round(ax),
                      "oneway": s.get("oneway"), "lanes": s.get("lanes")})
    named.sort(key=lambda x: x["distance_ft"])

    intersection = False
    if len(named) >= 2:
        a, b = named[0]["axis"], named[1]["axis"]
        d = angle_delta(a, b)
        intersection = min(d, 180 - d) > 45 and named[1]["distance_ft"] < 190

    return {
        "on_street": named[0]["name"] if named else None,
        "cross_street": named[1]["name"] if len(named) > 1 else None,
        "nearby": named[:5],
        "primary_axis": named[0]["axis"] if named else None,
        "intersection_nearby": intersection,
        "multilane": any((n.get("lanes") or "0").isdigit() and int(n["lanes"]) >= 4 for n in named[:2]),
    }


def _axis_desc(axis):
    if axis is None:
        return "Street orientation could not be established from map data."
    if axis < 25 or axis > 155:
        return "The street runs roughly north-south."
    if 65 < axis < 115:
        return "The street runs roughly east-west."
    return f"The street runs on a {compass(axis)}-{compass((axis + 180) % 360)} diagonal."


def _vacancy_signal(pois, lat, lon):
    """OSM tags disused:shop / was:shop are the only legitimate vacancy signal
    available for free. Absence of a tag is NOT evidence of vacancy."""
    hits = []
    for p in pois:
        if not p.get("vacant"):
            continue
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d <= 0.08:
            hits.append({"name": p.get("name") or "Unnamed storefront",
                         "distance_ft": int(feet(d)), "former_use": p.get("vacant")})
    return {
        "detected": len(hits),
        "items": hits[:6],
        "evidence": VERIFIED if hits else UNAVAILABLE,
        "note": ("Vacancies are only detected where a mapper has tagged a former shop. "
                 "Zero detected does not mean zero vacant - walk the block."),
    }


def _residential_entrances(pois, lat, lon):
    out = []
    for p in pois:
        if (p.get("building") or "") not in ("apartments", "residential", "dormitory"):
            continue
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d > 0.06:
            continue
        out.append({"name": p.get("name") or "Residential building",
                    "distance_ft": int(feet(d)),
                    "floors": p.get("levels"),
                    "category": "residential", "category_label": "Residential building",
                    "compass": compass(bearing(lat, lon, p["lat"], p["lon"]))})
    out.sort(key=lambda x: x["distance_ft"])
    return out[:8]


def _continuity(count):
    if count >= 22:
        return ("Continuous retail strip", "Storefronts run in an unbroken line here. "
                "Pedestrians already walk this block to shop.")
    if count >= 12:
        return ("Active retail block", "A real retail block with steady storefront activity.")
    if count >= 5:
        return ("Mixed / patchy retail", "Retail is present but broken up. Foot traffic will be "
                "driven by specific anchors rather than browsing.")
    return ("Isolated storefront", "Very few mapped storefronts adjacent. You will be a "
            "destination, not an impulse stop. This is a serious consideration.")
