from siteiq.engine.competitors import _band, build, summarize


def _google_competitor(name, distance_mi, rating, reviews, lat, lon, open_24h=False):
    return {
        "id": name, "name": name, "address": None, "lat": lat, "lon": lon,
        "distance_mi": distance_mi, "rating": rating, "reviews": reviews,
        "primary_type": "convenience_store", "types": ["convenience_store"],
        "photo": None, "photo_attribution": None, "maps_uri": None, "website": None,
        "phone": None, "price_level": None, "status": "OPERATIONAL", "open_now": True,
        "hours": [], "open_24h": open_24h, "summary": None, "source": "Google Places API",
    }


def test_band_thresholds():
    assert _band(90) == "VERY HIGH"
    assert _band(70) == "HIGH"
    assert _band(45) == "MEDIUM"
    assert _band(10) == "LOW"


def test_closer_stronger_competitor_ranks_first(site):
    lat, lon = site["lat"], site["lon"]
    weak_far = _google_competitor("Weak Far Store", 0.45, 3.4, 12, lat + 0.006, lon + 0.006)
    strong_near = _google_competitor("Strong Near Store", 0.03, 4.8, 2200, lat + 0.0003, lon,
                                     open_24h=True)
    ranked = build(site, "deli", [weak_far, strong_near], [])
    assert ranked[0]["name"] == "Strong Near Store"
    assert ranked[0]["threat_score"] > ranked[1]["threat_score"]
    assert ranked[0]["threat"] in ("HIGH", "VERY HIGH")


def test_non_overlapping_category_is_excluded(site):
    # A barber shop should not show up as a competitor for a deli search.
    lat, lon = site["lat"], site["lon"]
    barber = {
        "id": "b1", "name": "Cuts NYC", "address": None, "lat": lat + 0.001, "lon": lon,
        "distance_mi": 0.02, "rating": 4.9, "reviews": 500, "primary_type": "barber_shop",
        "types": ["barber_shop"], "photo": None, "photo_attribution": None, "maps_uri": None,
        "website": None, "phone": None, "price_level": None, "status": "OPERATIONAL",
        "open_now": True, "hours": [], "open_24h": False, "summary": None,
        "source": "Google Places API",
    }
    ranked = build(site, "deli", [barber], [])
    assert ranked == []


def test_summarize_counts_and_saturation(site):
    lat, lon = site["lat"], site["lon"]
    comps = build(site, "deli", [
        _google_competitor("A", 0.05, 4.5, 800, lat + 0.0007, lon),
        _google_competitor("B", 0.08, 4.2, 300, lat + 0.001, lon),
        _google_competitor("C", 0.4, 3.9, 50, lat + 0.006, lon),
    ], [])
    summary = summarize(comps, "deli")
    assert summary["total"] == 3
    assert summary["within_block"] >= 1
    assert summary["strongest"]["name"] in ("A", "B")


def test_summarize_empty_is_thin_competition():
    summary = summarize([], "deli")
    assert summary["total"] == 0
    assert summary["saturation_label"] == "Thin competition"
    assert summary["strongest"] is None
