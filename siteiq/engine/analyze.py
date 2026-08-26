"""The orchestrator.

Fetches every provider in parallel, assembles the full report, and records the
provenance of everything along the way. Any provider can fail without taking the
report down - the confidence score falls instead, which is the honest outcome.
"""
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

from ..config import CONCEPTS, HAS_GOOGLE, RADII_MILES, RADIUS_LABELS, SEARCH_RADIUS_M
from ..core import db
from ..core.geo import bearing, haversine_mi
from ..core.provenance import (INFERRED, MODELED, OBSERVED, UNAVAILABLE, USER,
                               VERIFIED, ConfidenceLedger, SourceRegistry)
from ..providers import census as census_provider
from ..providers import geocode as geocode_provider
from ..providers import google_places, nyc, overpass
from . import (block as block_engine, competitors as comp_engine,
               customers as customer_engine, dayparts as daypart_engine,
               generators as gen_engine, opportunities as opp_engine,
               rent as rent_engine, risks as risk_engine, sales as sales_engine,
               scoring as scoring_engine)
from .classify import CATEGORY_META, classify_osm

log = logging.getLogger("siteiq.analyze")

CHECKLIST = [
    "Stand on this corner for 15 minutes at 7:30am, 12:30pm, 6pm and 11pm. Count people. Count how many go into food stores.",
    "Buy something from the five strongest competitors. Look at their prepared food, their prices, their cleanliness and how many customers are in line.",
    "Ask three neighbouring shop owners how long they have been there and why the last tenant in your space left.",
    "Get the actual asking rent in writing, plus real estate taxes, CAM, insurance, escalation schedule, security deposit and personal guarantee terms.",
    "Confirm lease term and renewal options. Under ten years with no option is not enough to justify a serious buildout.",
    "Verify the certificate of occupancy allows your use, and check DOB for open violations on the building.",
    "Verify gas service and capacity, hood and exhaust, electrical service amperage, refrigeration, plumbing and grease trap. These are the buildout costs that destroy budgets.",
    "Check DOHMH inspection history for the address and for the business you may be acquiring.",
    "If buying an existing business, demand three years of sales tax filings, register Z-tapes, supplier invoices and payroll records. Never accept a verbal sales figure.",
    "Check where delivery drivers can legally stop, and where your own deliveries can unload without tickets.",
    "Photograph the storefront from 100 feet in each direction and from directly across the street. Check sightlines, scaffolding and signage rights.",
    "Search each delivery platform separately for your category at this address and count who already shows up in the top ten.",
    "Walk the block on a Saturday and a Sunday. Weekday-only demand is the most common way an operator overestimates a location.",
    "Confirm licences transfer or can be obtained: cigarette, lottery, beer and wine, sidewalk cafe, DCWP general vendor as applicable.",
]


def analyse(address, concept, inputs=None, progress=None):
    """Full location analysis. Returns a report dict, or None if geocoding fails."""
    inputs = inputs or {}
    concept = concept if concept in CONCEPTS else "deli"
    cfg = CONCEPTS[concept]
    ledger = ConfidenceLedger()
    sources = SourceRegistry()
    p = progress or (lambda pct, step: None)

    # ------------------------------------------------------------- geocode
    p(5, "Locating the address")
    site = geocode_provider.geocode(address)
    if not site:
        return None
    sources.note(site["provider"], "Address geocoding", used_for="Coordinates and street parsing")
    ledger.add("Address geocoding", VERIFIED, site["provider"], 1.0)

    lat, lon = site["lat"], site["lon"]
    borough = site.get("borough_norm")

    # ---------------------------------------------- parallel provider fetch
    p(12, "Pulling map, census and city records")
    results = {}
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {
            "pois": pool.submit(overpass.fetch_pois, lat, lon, SEARCH_RADIUS_M),
            "streets": pool.submit(overpass.fetch_streets, lat, lon),
            "census": pool.submit(census_provider.fetch, lat, lon),
        }
        if HAS_GOOGLE:
            futures["google"] = pool.submit(
                google_places.search, lat, lon,
                [cfg["google_types"], ["restaurant", "cafe", "bakery"],
                 ["supermarket", "pharmacy", "liquor_store"]],
                800, (f"{cfg['label']} near {site['resolved'][:60]}",))
            futures["streetview"] = pool.submit(google_places.streetview_available, lat, lon)
        if borough:
            futures["storefront"] = pool.submit(
                nyc.storefront_history, site.get("house_number"), site.get("street"), borough)
            futures["pluto"] = pool.submit(nyc.building_records, lat, lon)
            futures["construction"] = pool.submit(nyc.construction, site.get("street"), borough)
            futures["block_records"] = pool.submit(nyc.block_business_records, lat, lon)
            futures["food_records"] = pool.submit(nyc.nearby_food_records, lat, lon)

        for name, fut in futures.items():
            try:
                results[name] = fut.result(timeout=90)
            except Exception as exc:  # noqa: BLE001
                log.error("provider %s failed: %s", name, exc)
                results[name] = None

    pois = results.get("pois") or []
    streets = results.get("streets") or []
    demographics = results.get("census") or census_provider.fetch(lat, lon)
    google_raw = results.get("google") or []
    storefront = results.get("storefront") or {"available": False, "tenants": []}
    pluto = results.get("pluto") or {"available": False}
    construction = results.get("construction") or {"available": False, "permits": []}
    block_records = results.get("block_records") or {"available": False, "records": []}
    food_records = results.get("food_records") or {"available": False, "businesses": []}
    streetview_meta = results.get("streetview")

    # ---------------------------------------------------------- provenance
    if pois:
        sources.note("OpenStreetMap / Overpass API", "Community-maintained map data",
                     "https://www.openstreetmap.org",
                     "Businesses, transit, schools, hospitals, parks, buildings")
        ledger.add("Surrounding businesses and places", VERIFIED, "OpenStreetMap", 1.2)
    else:
        ledger.add("Surrounding businesses and places", UNAVAILABLE, "OpenStreetMap", 1.2,
                   "Overpass returned no data. Competitive and demand analysis is severely limited.")

    if demographics.get("available"):
        sources.note("U.S. Census Bureau ACS", f"{demographics['vintage']} 5-year estimates",
                     "https://www.census.gov/programs-surveys/acs",
                     "Population, income, age, density, commuting, housing")
        ledger.add("Demographics", VERIFIED, demographics["source"], 1.0)
    else:
        ledger.add("Demographics", UNAVAILABLE, "U.S. Census ACS", 1.0,
                   "Census tract could not be resolved for this coordinate.")

    if HAS_GOOGLE and google_raw:
        sources.note("Google Places API", "Business listings, ratings, hours, photos",
                     "https://developers.google.com/maps",
                     "Competitor ratings, review counts, hours, photos, Maps links")
        ledger.add("Competitor ratings and review volume", OBSERVED, "Google Places API", 1.2)
    else:
        ledger.add("Competitor ratings and review volume", UNAVAILABLE, "Google Places API", 1.2,
                   "No Google Maps API key configured." if not HAS_GOOGLE
                   else "Google Places returned no results for this area.")

    if storefront.get("available"):
        sources.note("NYC Open Data", "DOHMH inspections and DCWP business licences",
                     "https://opendata.cityofnewyork.us",
                     "Storefront tenant history, business longevity")
        ledger.add("Storefront tenant history", VERIFIED, "NYC Open Data", 0.9)
    else:
        ledger.add("Storefront tenant history", UNAVAILABLE, "NYC Open Data", 0.9,
                   storefront.get("reason") or "No matching NYC records for this address.")

    if pluto.get("available"):
        sources.note("NYC Department of City Planning PLUTO", "Tax lot land use records",
                     "https://www.nyc.gov/site/planning/data-maps/open-data.page",
                     "Residential units, retail floor area, building age")
        ledger.add("Building and land use records", VERIFIED, "NYC PLUTO", 0.8)
    else:
        ledger.add("Building and land use records", UNAVAILABLE, "NYC PLUTO", 0.8)

    if construction.get("available"):
        sources.note("NYC Department of Buildings", "Permit issuance records",
                     "https://www.nyc.gov/site/buildings/index.page", "Construction activity")

    # ------------------------------------------------------------ analysis
    p(45, "Analysing the block")
    google_norm = [google_places.normalize(g, lat, lon) for g in google_raw]

    def longevity_lookup(name, clat, clon):
        if not borough or clat is None:
            return None
        try:
            return nyc.business_since(name, clat, clon)
        except Exception:  # noqa: BLE001
            return None

    block_info = block_engine.analyse(site, pois, streets, pluto, construction)
    block_info["records"] = block_records
    block_info["churn"] = _churn(food_records, block_records)

    p(58, "Profiling competitors")
    competitor_list = comp_engine.build(site, concept, google_norm, pois,
                                        longevity_lookup if borough else None)
    comp_summary = comp_engine.summarize(competitor_list, concept)
    comp_summary["cross_check"] = _cross_check(food_records, comp_summary)

    p(68, "Mapping demand generators")
    generators = gen_engine.build(site, concept, pois, pluto)
    gen_strength = generators["strength"]

    delivery_score = _delivery_score(demographics, gen_strength, block_info, concept)

    p(74, "Modeling dayparts and customers")
    residential_base = min(100, (demographics["facts"]["density_sq_mi"].value or 0) / 900)
    dayparts = daypart_engine.build(concept, gen_strength, residential_base)
    ledger.add("Daypart demand", MODELED, "SiteIQ model", 1.0,
               "Modeled from generator mix. Not measured foot traffic.")

    customers = customer_engine.build(concept, gen_strength, demographics, block_info, delivery_score)
    ledger.add("Customer profile", INFERRED, "SiteIQ model", 0.8)

    p(80, "Running the sales and profit model")
    rent_info = rent_engine.build(concept, inputs, demographics, generators, block_info)
    ledger.add("Rent", USER if not rent_info["estimated"] else MODELED, rent_info["source"], 1.1,
               rent_info["note"] if rent_info["estimated"] else "")

    calibration = db.calibration_factor(concept)
    sales = sales_engine.build(concept, inputs, gen_strength, demographics, comp_summary,
                               block_info, dayparts, delivery_score, calibration)
    ledger.add("Sales estimate", MODELED, "SiteIQ bottom-up model", 1.3,
               "Built from estimated customer pools and capture rates.")

    rent_assessment = rent_engine.assess(concept, rent_info,
                                         sales["scenarios"]["Realistic"]["monthly"])
    pnl = sales_engine.pnl(concept, sales["scenarios"], inputs, rent_info, sales["delivery"])
    ledger.add("Operating profit estimate", MODELED, "SiteIQ P&L model", 1.1)

    if streetview_meta:
        ledger.add("Storefront imagery", OBSERVED, "Google Street View Static API", 0.5,
                   f"Imagery captured {streetview_meta.get('date', 'unknown date')}.")
    else:
        ledger.add("Storefront imagery", UNAVAILABLE, "Google Street View", 0.5,
                   "No Google key configured." if not HAS_GOOGLE else "No Street View imagery here.")

    ledger.add("Pedestrian counts", UNAVAILABLE, "None connected", 0.7,
               "SiteIQ has no foot-traffic data source. All traffic figures are modeled.")

    p(88, "Finding opportunities and red flags")
    opportunities = opp_engine.detect(concept, comp_summary, competitor_list, gen_strength,
                                      dayparts, demographics, block_info, customers, delivery_score)
    confidence = ledger.to_dict()
    risks = risk_engine.detect(concept, comp_summary, competitor_list, gen_strength, dayparts,
                               demographics, block_info, customers, rent_info, rent_assessment,
                               pnl, confidence, storefront)

    scoring = scoring_engine.build(generators, comp_summary, dayparts, demographics, block_info,
                                   customers, rent_assessment, pnl, opportunities, risks, confidence)

    p(94, "Building the map")
    map_data = _map_data(site, pois, competitor_list, generators)
    radii = _radius_counts(site, pois)

    sources.note("SiteIQ model", "Proprietary scoring, sales and P&L models", "",
                 "Sales estimates, daypart scores, threat levels, verdict")

    report = {
        "id": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "address": address,
        "resolved_address": site["resolved"],
        "lat": lat, "lon": lon,
        "borough": borough,
        "on_street": block_info["streets"].get("on_street"),
        "cross_street": block_info["streets"].get("cross_street"),
        "concept": concept,
        "concept_label": cfg["label"],
        "inputs": inputs,
        "score": scoring["score"],
        "verdict": scoring["verdict"],
        "verdict_reason": scoring["verdict_reason"],
        "score_components": scoring["components"],
        "five_hundred_k": scoring["five_hundred_k"],
        "confidence": confidence,
        "sources": sources.to_list(),
        "demographics": _serialize_demo(demographics),
        "block": block_info,
        "storefront_history": storefront,
        "competitors": competitor_list,
        "competition": comp_summary,
        "generators": generators,
        "customers": customers,
        "dayparts": dayparts,
        "sales": sales,
        "rent": rent_info,
        "rent_assessment": rent_assessment,
        "pnl": pnl,
        "opportunities": opportunities,
        "risks": risks,
        "map": map_data,
        "radii": radii,
        "delivery_score": delivery_score,
        "streetview": streetview_meta,
        "google_enabled": HAS_GOOGLE,
        "nyc_data": bool(borough),
        "checklist": CHECKLIST,
        "category_meta": {k: {"label": v[0], "colour": v[1], "glyph": v[2]}
                          for k, v in CATEGORY_META.items()},
    }
    p(99, "Finishing up")
    return report


# --------------------------------------------------------------------- helpers
def _serialize_demo(d):
    out = dict(d)
    out["facts"] = {k: v.to_dict() for k, v in d["facts"].items()}
    out["radius_estimates"] = {str(k): v.to_dict() for k, v in d.get("radius_estimates", {}).items()}
    for key in ("transit_commute_share", "renter_share", "affluence", "character"):
        val = d.get(key)
        if val is not None and hasattr(val, "to_dict"):
            out[key] = val.to_dict()
    return out


def _delivery_score(demographics, gen_strength, block, concept):
    density = demographics["facts"]["density_sq_mi"].value or 0
    units = (block.get("building") or {}).get("residential_units") or 0
    score = min(60, density / 1300) + min(25, units / 90)
    score += min(10, gen_strength.get("office", 0) / 10)
    score += min(8, gen_strength.get("college", 0) / 12)
    if concept in ("laundromat", "barber"):
        score *= 0.15
    elif concept in ("smoke_shop", "pharmacy"):
        score *= 0.55
    return round(min(100, score))


def _radius_counts(site, pois):
    lat, lon = site["lat"], site["lon"]
    out = []
    for r in RADII_MILES:
        inside = [p for p in pois if haversine_mi(lat, lon, p["lat"], p["lon"]) <= r]
        by_cat = {}
        for p in inside:
            cat = classify_osm(p)
            by_cat[cat] = by_cat.get(cat, 0) + 1
        out.append({
            "radius": r, "label": RADIUS_LABELS[r], "total": len(inside),
            "food": sum(by_cat.get(c, 0) for c in
                        ("deli", "convenience", "supermarket", "restaurant", "fast_food",
                         "coffee", "bakery")),
            "by_category": dict(sorted(by_cat.items(), key=lambda kv: -kv[1])),
        })
    return out


def _map_data(site, pois, competitor_list, generators):
    lat, lon = site["lat"], site["lon"]
    markers = []
    for c in competitor_list[:60]:
        if c.get("lat") is None:
            continue
        markers.append({
            "lat": c["lat"], "lon": c["lon"], "name": c["name"], "category": c["category"],
            "kind": "competitor", "threat": c.get("threat"), "rank": c.get("rank"),
            "distance_mi": round(c["distance_mi"], 3) if c.get("distance_mi") else None,
            "rating": c.get("rating"), "reviews": c.get("reviews"),
        })
    seen = {(round(m["lat"], 6), round(m["lon"], 6)) for m in markers}
    for g in generators["items"][:60]:
        if g.get("lat") is None:
            continue
        k = (round(g["lat"], 6), round(g["lon"], 6))
        if k in seen:
            continue
        seen.add(k)
        markers.append({
            "lat": g["lat"], "lon": g["lon"], "name": g["name"], "category": g["category"],
            "kind": "generator", "relevance": g["relevance"],
            "distance_mi": g["distance_mi"],
        })
    # Fill in remaining context businesses so the map does not look empty.
    for p in pois:
        if len(markers) >= 220:
            break
        if not p.get("name"):
            continue
        k = (round(p["lat"], 6), round(p["lon"], 6))
        if k in seen:
            continue
        d = haversine_mi(lat, lon, p["lat"], p["lon"])
        if d > 0.35:
            continue
        seen.add(k)
        markers.append({"lat": p["lat"], "lon": p["lon"], "name": p["name"],
                        "category": classify_osm(p), "kind": "context",
                        "distance_mi": round(d, 3)})
    return {"center": [lat, lon], "markers": markers}


def _churn(food_records, block_records):
    """Does this block hold businesses or chew them up? Uses NYC records only."""
    if not food_records.get("available"):
        return {"available": False,
                "note": "NYC business records unavailable for this location."}
    businesses = food_records["businesses"]
    if len(businesses) < 6:
        return {"available": False,
                "note": f"Only {len(businesses)} food businesses on record nearby - too few to "
                        "judge turnover."}
    active = [b for b in businesses if b["active"]]
    closed = [b for b in businesses if not b["active"]]
    long_lived = [b for b in active if b["tenure"] >= 8]
    short_closed = [b for b in closed if b["tenure"] <= 2]

    churn_rate = len(closed) / len(businesses)
    stability = len(long_lived) / max(1, len(active))

    if churn_rate > 0.55 and stability < 0.25:
        verdict = ("HIGH TURNOVER", "Records show a lot of food businesses appearing and "
                                    "disappearing here with few long survivors. Treat this block "
                                    "with real caution.")
    elif stability >= 0.45:
        verdict = ("STABLE", "A meaningful share of the food businesses here have been operating "
                             "for eight years or more. Blocks that hold tenants usually do so for "
                             "a reason.")
    else:
        verdict = ("NORMAL", "Turnover looks typical for NYC street retail.")

    oldest = sorted(active, key=lambda b: b["first_year"])[:6]
    return {
        "available": True,
        "total_on_record": len(businesses),
        "currently_active": len(active),
        "no_longer_active": len(closed),
        "long_lived": len(long_lived),
        "short_lived_closures": len(short_closed),
        "churn_rate": round(churn_rate * 100),
        "verdict": verdict[0],
        "note": verdict[1],
        "oldest_neighbours": [{"name": b["name"], "since": b["first_year"],
                               "years": b["tenure"], "address": b["address"]} for b in oldest],
        "source": "NYC DOHMH restaurant inspection records",
        "caveat": ("Absence from recent records suggests a business is no longer operating, but "
                   "it is not proof of closure. Food businesses only."),
    }


def _cross_check(food_records, comp_summary):
    if not food_records.get("available"):
        return None
    active = len([b for b in food_records["businesses"] if b["active"]])
    return {
        "nyc_active_food_businesses": active,
        "mapped_competitors": comp_summary.get("total", 0),
        "note": (f"NYC health department records show {active} active food businesses within "
                 f"{food_records.get('radius_mi', 0.25)} mi, against {comp_summary.get('total', 0)} "
                 "competitors identified from map and listing data. Large gaps mean the map data "
                 "is incomplete, not that the businesses do not exist."),
    }
