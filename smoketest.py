"""Offline end-to-end smoke test. Network is unavailable in this sandbox, so all
providers are stubbed with realistic synthetic payloads."""
import random
import sys

from siteiq.providers import census as census_p
from siteiq.providers import geocode as geocode_p
from siteiq.providers import google_places as gp
from siteiq.providers import nyc as nyc_p
from siteiq.providers import overpass as ov
from siteiq.core.provenance import VERIFIED, INFERRED, fact

random.seed(7)
LAT, LON = 40.7505, -73.9971

geocode_p.geocode = lambda a: {
    "lat": LAT, "lon": LON, "resolved": f"{a}, Manhattan, New York, NY 10001",
    "house_number": "352", "street": "9th Avenue", "city": "New York",
    "borough": "Manhattan", "postcode": "10001", "state": "New York",
    "provider": "OpenStreetMap Nominatim", "borough_norm": "Manhattan",
    "is_nyc": True, "query": a,
}

CATS = [
    ("convenience", "shop", "convenience"), ("deli", "shop", "deli"),
    ("restaurant", "amenity", "restaurant"), ("fast_food", "amenity", "fast_food"),
    ("cafe", "amenity", "cafe"), ("bar", "amenity", "bar"),
    ("school", "amenity", "school"), ("hospital", "amenity", "hospital"),
    ("hotel", "tourism", "hotel"), ("gym", "leisure", "fitness_centre"),
    ("office", "office", "company"), ("station", "railway", "station"),
    ("bus", "highway", "bus_stop"), ("park", "leisure", "park"),
    ("apartments", "building", "apartments"), ("pharmacy", "amenity", "pharmacy"),
    ("supermarket", "shop", "supermarket"), ("hairdresser", "shop", "hairdresser"),
]


def fake_pois(lat, lon, radius_m=1610):
    out = []
    for i in range(320):
        label, key, val = random.choice(CATS)
        d = random.random() ** 2 * 0.9
        ang = random.random() * 6.28318
        out.append({
            "osm_id": f"node/{i}", "lat": lat + d * 0.0145 * random.uniform(-1, 1),
            "lon": lon + d * 0.019 * random.uniform(-1, 1),
            "name": f"{label.title()} {i}", "brand": None, "operator": None,
            "shop": val if key == "shop" else None,
            "amenity": val if key == "amenity" else None,
            "office": val if key == "office" else None,
            "tourism": val if key == "tourism" else None,
            "leisure": val if key == "leisure" else None,
            "healthcare": None,
            "railway": val if key == "railway" else None,
            "public_transport": None,
            "highway": val if key == "highway" else None,
            "building": val if key == "building" else None,
            "landuse": None, "cuisine": None,
            "opening_hours": "24/7" if i % 29 == 0 else None,
            "start_date": "2011" if i % 41 == 0 else None,
            "levels": "12", "housenumber": str(300 + i), "street": "9th Avenue",
            "website": None, "phone": None, "wheelchair": None,
            "vacant": "convenience" if i % 97 == 0 else None,
        })
    return out


ov.fetch_pois = fake_pois
ov.fetch_streets = lambda lat, lon, radius_m=140: [
    {"name": "9th Avenue", "highway": "primary", "oneway": "yes", "lanes": "4",
     "geom": [[lat - 0.004, lon], [lat + 0.004, lon]]},
    {"name": "West 30th Street", "highway": "secondary", "oneway": "yes", "lanes": "2",
     "geom": [[lat, lon - 0.004], [lat, lon + 0.004]]},
]

census_p.fetch = lambda lat, lon: {
    "available": True, "tract_name": "Census Tract 97", "tract_geoid": "36061009700",
    "tract_land_sq_mi": 0.11, "vintage": 2023,
    "facts": {
        "population": fact(6420, VERIFIED, "ACS 2023", "Tract total."),
        "households": fact(3510, VERIFIED, "ACS 2023", ""),
        "median_income": fact(121400, VERIFIED, "ACS 2023", ""),
        "median_age": fact(36.4, VERIFIED, "ACS 2023", ""),
        "median_rent": fact(3120, VERIFIED, "ACS 2023", ""),
        "avg_household_size": fact(1.82, VERIFIED, "ACS 2023", ""),
        "density_sq_mi": fact(58363, VERIFIED, "ACS 2023", ""),
    },
    "radius_estimates": {
        0.1: fact(1833, INFERRED, "SiteIQ derivation", "density x area"),
        0.25: fact(11460, INFERRED, "SiteIQ derivation", "density x area"),
        0.5: fact(45838, INFERRED, "SiteIQ derivation", "density x area"),
    },
    "transit_commute_share": fact(0.71, VERIFIED, "ACS 2023", ""),
    "renter_share": fact(0.79, VERIFIED, "ACS 2023", ""),
    "affluence": fact(0.52, VERIFIED, "ACS 2023", ""),
    "income_mix": {"high_share": 0.52, "low_share": 0.21, "households": 3510},
    "character": fact("Very dense urban residential, high income, renter dominated",
                      INFERRED, "SiteIQ", ""),
    "source": "U.S. Census Bureau ACS 5-Year Estimates (2023)",
}

nyc_p.storefront_history = lambda hn, st, boro: {
    "available": True, "reason": None, "matched_street": "9 AVENUE",
    "distinct_tenants": 4,
    "tenants": [
        {"name": "Hudson Gourmet Deli", "kind": "Delicatessen", "first_year": 2019,
         "last_year": 2026, "records": 14, "source": "NYC DOHMH", "span_years": 8,
         "appears_current": True},
        {"name": "Ninth Ave Juice Bar", "kind": "Juice/Smoothies", "first_year": 2016,
         "last_year": 2018, "records": 4, "source": "NYC DOHMH", "span_years": 3,
         "appears_current": False},
        {"name": "Casa Taco", "kind": "Mexican", "first_year": 2014, "last_year": 2015,
         "records": 3, "source": "NYC DOHMH", "span_years": 2, "appears_current": False},
        {"name": "Corner Bagel Cafe", "kind": "Bagels", "first_year": 2009,
         "last_year": 2013, "records": 9, "source": "NYC DOHMH", "span_years": 5,
         "appears_current": False},
    ],
}
nyc_p.building_records = lambda lat, lon, radius_mi=0.05: {
    "available": True, "lots": 34, "residential_units": 1840, "retail_sqft": 62000,
    "office_sqft": 210000, "residential_sqft": 1400000, "median_year_built": 1962,
    "avg_floors": 14.2,
    "large_residential_buildings": [
        {"address": "360 W 31St Street", "units": 420, "floors": 32},
        {"address": "410 9Th Avenue", "units": 288, "floors": 24},
    ],
    "source": "NYC Department of City Planning PLUTO", "radius_mi": 0.05,
}
nyc_p.construction = lambda street, boro, months=30: {
    "available": True, "count": 9, "source": "NYC DOB permit issuance",
    "permits": [{"address": f"{330 + i} 9Th Avenue", "type": "A2", "year": 2025,
                 "contractor": "Acme Builders"} for i in range(9)],
}
nyc_p.block_business_records = lambda lat, lon, radius_mi=0.06: {
    "available": True,
    "records": [{"name": f"Business {i}", "industry": "Grocery-Retail", "since": 2005 + i % 18,
                 "status": "Active", "address": f"{300+i} 9Th Avenue"} for i in range(40)],
}
nyc_p.nearby_food_records = lambda lat, lon, radius_mi=0.25: {
    "available": True, "source": "NYC DOHMH restaurant inspections", "radius_mi": 0.25,
    "businesses": [{"name": f"Food Spot {i}", "cuisine": "American",
                    "first_year": 2004 + (i % 20), "last_year": 2026 if i % 3 else 2018,
                    "address": f"{300+i} 9Th Avenue", "active": bool(i % 3),
                    "tenure": (2026 if i % 3 else 2018) - (2004 + (i % 20)) + 1}
                   for i in range(46)],
}
nyc_p.business_since = lambda name, lat, lon, radius_mi=0.12: (
    {"year": 2013, "source": "NYC DCWP business licence record",
     "statement": "Confirmed operating since at least 2013"} if hash(name) % 3 == 0 else None)

gp.streetview_available = lambda lat, lon: None
gp.search = lambda *a, **k: []


def run():
    from siteiq.engine.analyze import analyse
    from siteiq.engine import compare as cmp_engine
    from siteiq.exports import pdf as pdf_export
    from siteiq.exports import pptx_export, comparison_pdf
    from siteiq.core import db

    db.init()
    steps = []
    r = analyse("352 9th Ave, New York, NY", "deli_24h",
                {"rent": 12000, "sqft": 1500, "hours": "24 hours"},
                lambda p, s: steps.append((int(p), s)))
    assert r, "analysis returned None"
    print(f"OK analyse: score={r['score']} verdict={r['verdict']} "
          f"confidence={r['confidence']['score']}")
    print(f"   sales realistic ${r['sales']['scenarios']['Realistic']['daily']:,}/day, "
          f"profit ${r['pnl']['by_scenario']['Realistic']['profit']:,}/mo "
          f"({r['pnl']['by_scenario']['Realistic']['margin_pct']}%)")
    print(f"   breakeven ${r['pnl']['breakeven_daily']:,}/day  rent {r['rent_assessment']['rent_pct']}%")
    print(f"   competitors={r['competition']['total']} direct={r['competition']['direct_count']} "
          f"generators={len(r['generators']['items'])} markers={len(r['map']['markers'])}")
    print(f"   opportunities={r['opportunities']['count']} risks={r['risks']['count']} "
          f"churn={r['block']['churn'].get('verdict')}")
    print(f"   progress steps={len(steps)}")

    rid = db.save_report(r)
    loaded = db.load_report(rid)
    assert loaded and loaded["score"] == r["score"]
    print("OK persistence round-trip")

    data = pdf_export.build(loaded)
    open("/tmp/test.pdf", "wb").write(data)
    print(f"OK pdf: {len(data):,} bytes")

    data = pptx_export.build(loaded)
    open("/tmp/test.pptx", "wb").write(data)
    print(f"OK pptx: {len(data):,} bytes")

    comp = cmp_engine.run(["352 9th Ave, New York, NY", "1420 3rd Ave, New York, NY",
                           "88 Court St, Brooklyn, NY"], "deli",
                          {}, lambda p, s: None)
    print(f"OK compare: {comp['count']} rows, winner={comp['winner']['row']['address']}")
    open("/tmp/cmp.pdf", "wb").write(comparison_pdf.build(comp))
    open("/tmp/cmp.pptx", "wb").write(pptx_export.build_comparison(comp))
    print("OK comparison exports")

    return rid, db.save_comparison(comp)


if __name__ == "__main__":
    try:
        rid, cid = run()
        print(f"\nSMOKE TEST PASSED  report={rid} comparison={cid}")
    except Exception:
        import traceback
        traceback.print_exc()
        sys.exit(1)
