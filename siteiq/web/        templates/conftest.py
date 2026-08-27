"""Shared fixtures for the engine test suite.

These build minimal but realistic inputs in the exact shape the engine modules
consume internally (raw Fact-based demographics, not the serialized dicts the
web layer sends to templates). No network access anywhere in this suite.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from siteiq.core.provenance import VERIFIED, fact, unknown


@pytest.fixture
def site():
    return {"lat": 40.7505, "lon": -73.9971, "resolved": "352 9th Ave, Manhattan, NY"}


@pytest.fixture
def demographics():
    return {
        "available": True,
        "tract_name": "Census Tract 97",
        "facts": {
            "population": fact(6420, VERIFIED, "ACS"),
            "households": fact(3510, VERIFIED, "ACS"),
            "median_income": fact(95000, VERIFIED, "ACS"),
            "median_age": fact(35.0, VERIFIED, "ACS"),
            "median_rent": fact(2800, VERIFIED, "ACS"),
            "avg_household_size": fact(1.9, VERIFIED, "ACS"),
            "density_sq_mi": fact(48000, VERIFIED, "ACS"),
        },
        "radius_estimates": {0.25: fact(9000, VERIFIED, "SiteIQ derivation")},
        "transit_commute_share": fact(0.6, VERIFIED, "ACS"),
        "renter_share": fact(0.7, VERIFIED, "ACS"),
        "affluence": fact(0.4, VERIFIED, "ACS"),
        "income_mix": {"high_share": 0.4, "low_share": 0.2, "households": 3510},
        "character": fact("Dense urban residential", VERIFIED, "SiteIQ"),
        "source": "U.S. Census Bureau ACS",
    }


@pytest.fixture
def demographics_unavailable():
    return {
        "available": False,
        "tract_name": None,
        "facts": {k: unknown("ACS") for k in
                  ("population", "households", "median_income", "median_age",
                   "median_rent", "avg_household_size", "density_sq_mi")},
        "radius_estimates": {},
        "transit_commute_share": unknown("ACS"),
        "renter_share": unknown("ACS"),
        "affluence": unknown("ACS"),
        "income_mix": None,
        "source": "U.S. Census ACS",
    }


@pytest.fixture
def block():
    return {
        "is_corner": False,
        "storefront_count": 14,
        "food_neighbours": 5,
        "construction_count": 0,
        "vacancy": {"detected": 0, "items": [], "note": ""},
        "building": {"available": False},
        "churn": {"available": False},
        "retail_continuity": ("Active retail block", "Steady storefront activity."),
    }


@pytest.fixture
def gen_strength():
    return {"transit": 60, "office": 40, "hospital": 0, "school": 20, "college": 0,
            "hotel": 0, "nightlife": 10, "gym": 15, "government": 0, "attraction": 0,
            "park": 10, "bus": 30, "residential": 50}


@pytest.fixture
def dayparts_result(gen_strength):
    from siteiq.engine import dayparts as daypart_engine
    return daypart_engine.build("deli", gen_strength, residential_base=40)


@pytest.fixture
def generators_result(site, gen_strength):
    from siteiq.engine import generators as gen_engine
    # Build a light set of OSM points consistent with gen_strength categories.
    pois = []
    cats = [("school", "amenity", "school"), ("hospital", "amenity", "hospital"),
            ("company", "office", "company"), ("station", "railway", "station")]
    for i, (name, key, val) in enumerate(cats):
        pois.append({
            "lat": site["lat"] + 0.001 * (i + 1), "lon": site["lon"] + 0.001 * (i + 1),
            "name": f"{name.title()} {i}", "shop": None,
            "amenity": val if key == "amenity" else None,
            "office": val if key == "office" else None, "tourism": None, "leisure": None,
            "healthcare": None, "railway": val if key == "railway" else None,
            "public_transport": None, "highway": None, "building": None,
        })
    return gen_engine.build(site, "deli", pois, {"available": False})


@pytest.fixture
def customers_result(demographics, block, gen_strength):
    from siteiq.engine import customers as customer_engine
    return customer_engine.build("deli", gen_strength, demographics, block, delivery_score=40)


@pytest.fixture
def empty_competitors():
    return []


@pytest.fixture
def comp_summary_light(empty_competitors):
    from siteiq.engine import competitors as comp_engine
    return comp_engine.summarize(empty_competitors, "deli")


@pytest.fixture
def rent_info_ok():
    return {"monthly_rent": 8000, "estimated": False, "sqft": 1200, "sqft_estimated": False,
            "annual_psf": 80, "band": None, "note": "", "source": "You entered this"}


@pytest.fixture
def rent_assessment_ok():
    return {"rent_pct": 7.0, "healthy_pct": 8.5, "band": "HEALTHY",
            "verdict": "Occupancy cost is normal.", "max_supportable_rent": 9500, "gap": 0}


@pytest.fixture
def pnl_light():
    return {
        "by_scenario": {
            "Conservative": {"revenue": 60000, "profit": 3000, "margin_pct": 5.0,
                             "annual_profit": 36000, "labour_at_floor": False, "labour_pct": 20},
            "Realistic": {"revenue": 90000, "profit": 9000, "margin_pct": 10.0,
                         "annual_profit": 108000, "labour_at_floor": False, "labour_pct": 20},
            "Strong Operator": {"revenue": 115000, "profit": 15000, "margin_pct": 13.0,
                                "annual_profit": 180000, "labour_at_floor": False, "labour_pct": 18},
            "Elite Operator": {"revenue": 140000, "profit": 22000, "margin_pct": 15.7,
                               "annual_profit": 264000, "labour_at_floor": False, "labour_pct": 17},
        },
        "labour_floor": 6000, "hours_per_week": 119, "breakeven_daily": 2200,
        "assumptions": [],
    }


@pytest.fixture
def confidence_ok():
    return {"score": 72, "entries": [], "missing_count": 1}


@pytest.fixture
def confidence_low():
    return {"score": 30, "entries": [], "missing_count": 6}
