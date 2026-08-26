"""U.S. Census demographics.

Two important honesty rules are enforced here:

1. Tract totals are reported as tract totals, never relabelled as "population
   within half a mile".
2. Radius populations are derived from measured tract land area and density and
   are explicitly marked as derived estimates, not counts.
"""
import logging
import math

from ..core import cache
from ..core.http import get_json
from ..core.provenance import INFERRED, UNAVAILABLE, VERIFIED, Fact, fact, unknown

log = logging.getLogger("siteiq.census")

GEOCODER = "https://geocoding.geo.census.gov/geocoder/geographies/coordinates"
ACS_BASE = "https://api.census.gov/data/{year}/acs/acs5"
VINTAGES = [2023, 2022, 2021]

VARS = {
    "population": "B01003_001E",
    "households": "B11001_001E",
    "median_income": "B19013_001E",
    "median_age": "B01002_001E",
    "median_rent": "B25064_001E",
    "avg_household_size": "B25010_001E",
    "commute_total": "B08301_001E",
    "commute_transit": "B08301_010E",
    "commute_walk": "B08301_019E",
    "renter_occupied": "B25003_003E",
    "occupied_units": "B25003_001E",
    "inc_lt25k": "B19001_002E",
    "inc_25_50k": "B19001_006E",
    "inc_100_150k": "B19001_014E",
    "inc_150_200k": "B19001_016E",
    "inc_200k_plus": "B19001_017E",
    "inc_total": "B19001_001E",
}

SOURCE = "U.S. Census Bureau ACS 5-Year Estimates"


def _tract(lat, lon):
    data = get_json(GEOCODER, params={
        "x": lon, "y": lat, "benchmark": "Public_AR_Current",
        "vintage": "Current_Current", "format": "json",
    }, timeout=18)
    try:
        geos = data["result"]["geographies"]
        tracts = geos.get("Census Tracts") or geos.get("2020 Census Blocks")
        t = tracts[0]
        return {
            "state": t["STATE"], "county": t["COUNTY"], "tract": t["TRACT"],
            "name": t.get("NAME") or t.get("BASENAME"),
            "land_sq_m": float(t.get("AREALAND") or 0) or None,
            "geoid": t.get("GEOID"),
        }
    except (TypeError, KeyError, IndexError, ValueError):
        return None


def _acs(tract):
    names = ",".join(VARS.values())
    for year in VINTAGES:
        data = get_json(ACS_BASE.format(year=year), params={
            "get": names,
            "for": f"tract:{tract['tract']}",
            "in": f"state:{tract['state']} county:{tract['county']}",
        }, timeout=18)
        if data and len(data) > 1:
            row = dict(zip(data[0], data[1]))
            return {"year": year, "row": row}
    return None


def _num(row, key):
    raw = row.get(VARS[key])
    if raw in (None, "", "-666666666", "-999999999"):
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    return v


def fetch(lat, lon):
    """Returns a demographics dict of Facts plus derived radius estimates."""
    def produce():
        tract = _tract(lat, lon)
        if not tract:
            return {"ok": False}
        acs = _acs(tract)
        if not acs:
            return {"ok": False, "tract": tract}
        return {"ok": True, "tract": tract, "year": acs["year"], "row": acs["row"]}

    raw = cache.cached("census", (round(lat, 5), round(lon, 5)), produce) or {"ok": False}

    if not raw.get("ok"):
        return {
            "available": False,
            "tract_name": None,
            "facts": {k: unknown(SOURCE) for k in
                      ("population", "households", "median_income", "median_age",
                       "median_rent", "avg_household_size", "density_sq_mi")},
            "radius_estimates": {},
            "transit_commute_share": unknown(SOURCE),
            "renter_share": unknown(SOURCE),
            "affluence": unknown(SOURCE),
            "income_mix": None,
            "vintage": None,
            "source": SOURCE,
        }

    row, tract, year = raw["row"], raw["tract"], raw["year"]
    src = f"{SOURCE} ({year})"

    pop = _num(row, "population")
    hh = _num(row, "households")
    land_sq_mi = (tract.get("land_sq_m") or 0) / 2_589_988.11
    density = (pop / land_sq_mi) if (pop and land_sq_mi > 0.0005) else None

    facts = {
        "population": fact(int(pop) if pop is not None else None, VERIFIED, src,
                           f"Census tract {tract.get('name') or tract.get('tract')} total."),
        "households": fact(int(hh) if hh is not None else None, VERIFIED, src, "Tract total."),
        "median_income": fact(int(_num(row, "median_income")) if _num(row, "median_income") else None,
                              VERIFIED, src, "Median household income for the tract."),
        "median_age": fact(_num(row, "median_age"), VERIFIED, src, "Tract median age."),
        "median_rent": fact(int(_num(row, "median_rent")) if _num(row, "median_rent") else None,
                            VERIFIED, src, "Median residential gross rent (not commercial rent)."),
        "avg_household_size": fact(_num(row, "avg_household_size"), VERIFIED, src, "Tract average."),
        "density_sq_mi": fact(int(density) if density else None, VERIFIED, src,
                              "Tract population divided by measured tract land area."),
    }

    # Radius estimates: honest derivation, clearly not a count.
    radius_estimates = {}
    if density:
        for r in (0.1, 0.25, 0.5):
            area = math.pi * r * r
            radius_estimates[r] = fact(
                int(density * area), INFERRED, "SiteIQ derivation from Census tract density",
                f"Estimated residents within {r} mi = tract density x circle area. "
                "Not a measured count; real blocks are not uniform.")
    else:
        for r in (0.1, 0.25, 0.5):
            radius_estimates[r] = unknown("SiteIQ derivation", "Tract density unavailable.")

    ct, cta, ctw = _num(row, "commute_total"), _num(row, "commute_transit"), _num(row, "commute_walk")
    transit_share = fact(round((cta + (ctw or 0)) / ct, 3) if ct and cta else None, VERIFIED, src,
                         "Share of workers commuting by transit or on foot. High values mean sidewalk traffic.")

    occ, rent_occ = _num(row, "occupied_units"), _num(row, "renter_occupied")
    renter_share = fact(round(rent_occ / occ, 3) if occ and rent_occ else None, VERIFIED, src,
                        "Renter-occupied share of housing units.")

    inc_total = _num(row, "inc_total")
    income_mix = None
    affluence = unknown(src)
    if inc_total and inc_total > 0:
        high = sum(x for x in (_num(row, "inc_100_150k"), _num(row, "inc_150_200k"),
                               _num(row, "inc_200k_plus")) if x)
        low = sum(x for x in (_num(row, "inc_lt25k"), _num(row, "inc_25_50k")) if x)
        income_mix = {
            "high_share": round(high / inc_total, 3),
            "low_share": round(low / inc_total, 3),
            "households": int(inc_total),
        }
        affluence = fact(round(high / inc_total, 3), VERIFIED, src,
                         "Share of households earning $100k+.")

    character = _character(density, facts["median_income"].value, renter_share.value)

    return {
        "available": True,
        "tract_name": tract.get("name") or tract.get("tract"),
        "tract_geoid": tract.get("geoid"),
        "tract_land_sq_mi": round(land_sq_mi, 4) if land_sq_mi else None,
        "vintage": year,
        "facts": facts,
        "radius_estimates": radius_estimates,
        "transit_commute_share": transit_share,
        "renter_share": renter_share,
        "affluence": affluence,
        "income_mix": income_mix,
        "character": character,
        "source": src,
    }


def _character(density, income, renter_share):
    if not density:
        return Fact(None, UNAVAILABLE, "SiteIQ", "Insufficient data.")
    if density > 90000:
        band = "Extremely dense high-rise residential"
    elif density > 50000:
        band = "Very dense urban residential"
    elif density > 25000:
        band = "Dense urban residential"
    elif density > 10000:
        band = "Moderately dense urban"
    else:
        band = "Lower-density residential"
    if income and income > 130000:
        band += ", high income"
    elif income and income < 55000:
        band += ", working class"
    if renter_share and renter_share > 0.75:
        band += ", renter dominated"
    return Fact(band, INFERRED, "SiteIQ read of Census tract measures",
                "Descriptive summary derived from verified Census values.")
