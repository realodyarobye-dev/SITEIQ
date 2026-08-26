"""NYC Open Data (Socrata).

This is where SiteIQ gets things no map API can tell you:

  * How long a business has actually been operating (DCWP licence creation
    dates, first health inspection on record).
  * What used to occupy the storefront you are about to sign for (health
    inspection history at the same building + street).
  * Whether the block churns tenants or holds them.
  * How much residential and retail floor area really sits on the block (PLUTO).
  * Whether there is active construction that will help or hurt.

Everything is public, requested through the official API, and cached. No
scraping. No key required, though NYC_APP_TOKEN raises the rate limit.
"""
import logging
import re
from datetime import datetime, timezone

from ..config import NYC_APP_TOKEN, NYC_DATASETS, NYC_SOCRATA_HOST
from ..core import cache
from ..core.geo import bbox
from ..core.http import get_json

log = logging.getLogger("siteiq.nyc")

BOROUGH_CODE = {"Manhattan": "1", "Bronx": "2", "Brooklyn": "3", "Queens": "4", "Staten Island": "5"}
BOROUGH_DOB = {"Manhattan": "MANHATTAN", "Bronx": "BRONX", "Brooklyn": "BROOKLYN",
               "Queens": "QUEENS", "Staten Island": "STATEN ISLAND"}

SUFFIX = {
    "AVE": "AVENUE", "AV": "AVENUE", "ST": "STREET", "STR": "STREET", "RD": "ROAD",
    "BLVD": "BOULEVARD", "BLV": "BOULEVARD", "PL": "PLACE", "PKWY": "PARKWAY",
    "PKY": "PARKWAY", "DR": "DRIVE", "CT": "COURT", "LN": "LANE", "TER": "TERRACE",
    "SQ": "SQUARE", "HWY": "HIGHWAY", "EXPY": "EXPRESSWAY", "PLZ": "PLAZA",
}
DIRECTION = {"E": "EAST", "W": "WEST", "N": "NORTH", "S": "SOUTH"}


def normalize_street(street):
    """'W 34th St' -> 'WEST 34 STREET', matching NYC record conventions."""
    if not street:
        return None
    s = re.sub(r"[.,]", " ", street.upper())
    s = re.sub(r"\b(\d+)(ST|ND|RD|TH)\b", r"\1", s)
    words = [w for w in s.split() if w]
    out = []
    for i, w in enumerate(words):
        if i == 0 and w in DIRECTION:
            out.append(DIRECTION[w])
        elif i == len(words) - 1 and w in SUFFIX:
            out.append(SUFFIX[w])
        else:
            out.append(w)
    return " ".join(out)


def street_variants(street):
    """NYC datasets are inconsistent; try the most likely spellings."""
    base = normalize_street(street)
    if not base:
        return []
    variants = {base}
    for full, short in [("AVENUE", "AVE"), ("STREET", "ST"), ("BOULEVARD", "BLVD"),
                        ("PLACE", "PL"), ("ROAD", "RD"), ("PARKWAY", "PKWY")]:
        if base.endswith(" " + full):
            variants.add(base[: -len(full)] + short)
    return list(variants)


def _soql(dataset_key, params, bucket_parts):
    dataset = NYC_DATASETS.get(dataset_key)
    if not dataset:
        return None
    url = f"{NYC_SOCRATA_HOST}/resource/{dataset}.json"
    headers = {"X-App-Token": NYC_APP_TOKEN} if NYC_APP_TOKEN else {}

    def produce():
        data = get_json(url, params=params, headers=headers, timeout=25)
        if data is None or isinstance(data, dict):
            return None
        return data

    return cache.cached("nyc", (dataset_key, bucket_parts), produce)


def _esc(v):
    return str(v).replace("'", "''")


def _year(value):
    if not value:
        return None
    m = re.search(r"(19|20)\d{2}", str(value))
    return int(m.group(0)) if m else None


# ------------------------------------------------------------ storefront history
def storefront_history(house_number, street, borough):
    """Businesses recorded at this exact building + street over time.

    Returns prior and current tenants with the years they appear in public
    records. We never claim a business 'closed' - only what the records show.
    """
    if not house_number or not street or not borough:
        return {"available": False, "reason": "Street address could not be parsed to NYC record format.",
                "tenants": []}

    tenants = {}
    found_any = False

    for variant in street_variants(street):
        where = (f"building='{_esc(house_number)}' AND street='{_esc(variant)}' "
                 f"AND boro='{_esc(borough.upper())}'")
        rows = _soql("restaurant_inspections", {
            "$select": "dba, cuisine_description, inspection_date, camis",
            "$where": where, "$limit": 2000,
        }, ("storefront-dohmh", house_number, variant, borough))
        if rows:
            found_any = True
            for r in rows:
                name = (r.get("dba") or "").strip()
                if not name:
                    continue
                y = _year(r.get("inspection_date"))
                if not y or y < 1990:
                    continue
                t = tenants.setdefault(name.title(), {
                    "name": name.title(), "kind": r.get("cuisine_description") or "Food service",
                    "first_year": y, "last_year": y, "records": 0,
                    "source": "NYC DOHMH restaurant inspections"})
                t["first_year"] = min(t["first_year"], y)
                t["last_year"] = max(t["last_year"], y)
                t["records"] += 1

        # Licensed non-food businesses at the same address.
        rows = _soql("legal_businesses", {
            "$select": "business_name, industry, license_creation_date, license_status, lic_expir_dd",
            "$where": (f"address_building='{_esc(house_number)}' AND "
                       f"upper(address_street_name)='{_esc(variant)}'"),
            "$limit": 500,
        }, ("storefront-dcwp", house_number, variant))
        if rows:
            found_any = True
            for r in rows:
                name = (r.get("business_name") or "").strip()
                y = _year(r.get("license_creation_date"))
                if not name or not y:
                    continue
                t = tenants.setdefault(name.title(), {
                    "name": name.title(), "kind": (r.get("industry") or "Licensed business").title(),
                    "first_year": y, "last_year": _year(r.get("lic_expir_dd")) or y, "records": 1,
                    "source": "NYC DCWP legally operating businesses"})
                t["first_year"] = min(t["first_year"], y)
                t["last_year"] = max(t["last_year"], _year(r.get("lic_expir_dd")) or y)

        if found_any:
            break

    now_year = datetime.now(timezone.utc).year
    out = []
    for t in tenants.values():
        t["span_years"] = max(1, t["last_year"] - t["first_year"] + 1)
        t["appears_current"] = t["last_year"] >= now_year - 1
        out.append(t)
    out.sort(key=lambda x: (-x["last_year"], x["first_year"]))

    return {
        "available": bool(out),
        "reason": None if out else "No NYC business or inspection records matched this exact address.",
        "tenants": out,
        "distinct_tenants": len(out),
        "matched_street": normalize_street(street),
    }


# ------------------------------------------------------------ block longevity
def block_business_records(lat, lon, radius_mi=0.06):
    """Licensed businesses near the site with their licence creation years.

    Used to answer: does this block hold tenants, or does it churn?
    """
    lat1, lon1, lat2, lon2 = bbox(lat, lon, radius_mi)
    rows = _soql("legal_businesses", {
        "$select": "business_name, industry, license_creation_date, license_status, "
                   "address_building, address_street_name, latitude, longitude",
        "$where": (f"latitude > {lat1} AND latitude < {lat2} AND "
                   f"longitude > {lon1} AND longitude < {lon2}"),
        "$limit": 1000,
    }, ("block-dcwp", round(lat, 4), round(lon, 4), radius_mi))
    if not rows:
        return {"available": False, "records": []}

    records = []
    for r in rows:
        y = _year(r.get("license_creation_date"))
        if not y:
            continue
        records.append({
            "name": (r.get("business_name") or "").title(),
            "industry": (r.get("industry") or "").title(),
            "since": y,
            "status": (r.get("license_status") or "").title(),
            "address": f"{r.get('address_building') or ''} {(r.get('address_street_name') or '').title()}".strip(),
        })
    records.sort(key=lambda x: x["since"])
    return {"available": bool(records), "records": records}


def business_since(name, lat, lon, radius_mi=0.12):
    """Earliest public record year for a named business near a point.

    Returns None rather than guessing. Never invents an opening date.
    """
    if not name:
        return None
    lat1, lon1, lat2, lon2 = bbox(lat, lon, radius_mi)
    key = re.sub(r"[^A-Z0-9 ]", " ", name.upper()).strip()
    key = " ".join(key.split()[:3])
    if len(key) < 3:
        return None

    best = None
    rows = _soql("legal_businesses", {
        "$select": "business_name, license_creation_date, latitude, longitude",
        "$where": (f"latitude > {lat1} AND latitude < {lat2} AND longitude > {lon1} "
                   f"AND longitude < {lon2} AND upper(business_name) like '%{_esc(key)}%'"),
        "$limit": 50,
    }, ("since-dcwp", key, round(lat, 4), round(lon, 4)))
    for r in rows or []:
        y = _year(r.get("license_creation_date"))
        if y and (best is None or y < best[0]):
            best = (y, "NYC DCWP business licence record")

    rows = _soql("restaurant_inspections", {
        "$select": "dba, inspection_date, latitude, longitude",
        "$where": (f"latitude > {lat1} AND latitude < {lat2} AND longitude > {lon1} "
                   f"AND longitude < {lon2} AND upper(dba) like '%{_esc(key)}%'"),
        "$order": "inspection_date ASC", "$limit": 5,
    }, ("since-dohmh", key, round(lat, 4), round(lon, 4)))
    for r in rows or []:
        y = _year(r.get("inspection_date"))
        if y and y > 1990 and (best is None or y < best[0]):
            best = (y, "NYC DOHMH first health inspection on record")

    if not best:
        return None
    return {"year": best[0], "source": best[1],
            "statement": f"Confirmed operating since at least {best[0]}"}


# ------------------------------------------------------------------- building
def building_records(lat, lon, radius_mi=0.05):
    """MapPLUTO tax-lot records around the site: residential units, retail area,
    year built, floors. The most reliable 'how many people live on this block'
    signal available."""
    lat1, lon1, lat2, lon2 = bbox(lat, lon, radius_mi)
    rows = _soql("pluto", {
        "$select": "address, bldgclass, yearbuilt, numfloors, unitsres, unitstotal, "
                   "retailarea, officearea, comarea, resarea, bldgarea, lotarea, latitude, longitude",
        "$where": (f"latitude > {lat1} AND latitude < {lat2} AND "
                   f"longitude > {lon1} AND longitude < {lon2}"),
        "$limit": 400,
    }, ("pluto", round(lat, 4), round(lon, 4), radius_mi))
    if not rows:
        return {"available": False}

    def n(r, k):
        try:
            return float(r.get(k) or 0)
        except (TypeError, ValueError):
            return 0.0

    units_res = sum(n(r, "unitsres") for r in rows)
    retail_area = sum(n(r, "retailarea") for r in rows)
    office_area = sum(n(r, "officearea") for r in rows)
    res_area = sum(n(r, "resarea") for r in rows)
    years = [int(n(r, "yearbuilt")) for r in rows if n(r, "yearbuilt") > 1800]
    floors = [n(r, "numfloors") for r in rows if n(r, "numfloors") > 0]
    tall = [r for r in rows if n(r, "numfloors") >= 12 and n(r, "unitsres") >= 40]

    return {
        "available": True,
        "lots": len(rows),
        "residential_units": int(units_res),
        "retail_sqft": int(retail_area),
        "office_sqft": int(office_area),
        "residential_sqft": int(res_area),
        "median_year_built": sorted(years)[len(years) // 2] if years else None,
        "avg_floors": round(sum(floors) / len(floors), 1) if floors else None,
        "large_residential_buildings": sorted(
            [{"address": (r.get("address") or "").title(), "units": int(n(r, "unitsres")),
              "floors": int(n(r, "numfloors"))} for r in tall],
            key=lambda x: -x["units"])[:8],
        "source": "NYC Department of City Planning PLUTO",
        "radius_mi": radius_mi,
    }


# --------------------------------------------------------------- construction
def construction(street, borough, months=30):
    """Recent DOB permits on the same street. Construction means both future
    demand and present disruption, so we surface it either way."""
    if not street or not borough:
        return {"available": False, "permits": []}
    cutoff = datetime.now(timezone.utc).year - max(1, months // 12)
    boro = BOROUGH_DOB.get(borough)
    if not boro:
        return {"available": False, "permits": []}
    for variant in street_variants(street):
        rows = _soql("dob_permits", {
            "$select": "house__, street_name, job_type, permit_type, issuance_date, "
                       "permittee_s_business_name, work_type",
            "$where": (f"upper(street_name)='{_esc(variant)}' AND borough='{_esc(boro)}'"),
            "$order": "issuance_date DESC", "$limit": 400,
        }, ("dob", variant, boro))
        if rows:
            permits = []
            for r in rows:
                y = _year(r.get("issuance_date"))
                if not y or y < cutoff:
                    continue
                permits.append({
                    "address": f"{r.get('house__') or ''} {(r.get('street_name') or '').title()}".strip(),
                    "type": (r.get("job_type") or r.get("permit_type") or "Permit"),
                    "year": y,
                    "contractor": (r.get("permittee_s_business_name") or "").title() or None,
                })
            return {"available": True, "permits": permits[:40], "count": len(permits),
                    "source": "NYC DOB permit issuance"}
    return {"available": False, "permits": []}


# ------------------------------------------------------ food-service density
def nearby_food_records(lat, lon, radius_mi=0.25):
    """Distinct food businesses on record nearby, with first-seen years.
    Gives an independent read on competitor count and neighbourhood stability
    that does not depend on Google."""
    lat1, lon1, lat2, lon2 = bbox(lat, lon, radius_mi)
    rows = _soql("restaurant_inspections", {
        "$select": "camis, dba, cuisine_description, inspection_date, building, street, grade",
        "$where": (f"latitude > {lat1} AND latitude < {lat2} AND "
                   f"longitude > {lon1} AND longitude < {lon2}"),
        "$limit": 5000,
    }, ("food-dohmh", round(lat, 4), round(lon, 4), radius_mi))
    if not rows:
        return {"available": False, "businesses": []}
    by_id = {}
    for r in rows:
        cid = r.get("camis")
        y = _year(r.get("inspection_date"))
        if not cid or not y or y < 1990:
            continue
        b = by_id.setdefault(cid, {
            "name": (r.get("dba") or "").title(),
            "cuisine": r.get("cuisine_description"),
            "first_year": y, "last_year": y,
            "address": f"{r.get('building') or ''} {(r.get('street') or '').title()}".strip(),
        })
        b["first_year"] = min(b["first_year"], y)
        b["last_year"] = max(b["last_year"], y)
    now_year = datetime.now(timezone.utc).year
    businesses = []
    for b in by_id.values():
        b["active"] = b["last_year"] >= now_year - 1
        b["tenure"] = b["last_year"] - b["first_year"] + 1
        businesses.append(b)
    return {"available": True, "businesses": businesses,
            "source": "NYC DOHMH restaurant inspections", "radius_mi": radius_mi}
