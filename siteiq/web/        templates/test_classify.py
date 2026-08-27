from siteiq.engine.classify import classify_google, classify_osm


def test_classify_osm_deli_shop():
    assert classify_osm({"shop": "deli"}) == "deli"


def test_classify_osm_hospital_amenity():
    assert classify_osm({"amenity": "hospital"}) == "hospital"


def test_classify_osm_unknown_tag_is_other():
    assert classify_osm({"amenity": "some_new_osm_tag_nobody_mapped_yet"}) == "other"


def test_classify_osm_shop_without_known_subtype_is_retail():
    assert classify_osm({"shop": "totally_novel_shop_type"}) == "retail"


def test_classify_google_convenience_store():
    place = {"primary_type": "convenience_store", "types": ["convenience_store", "store"],
             "name": "Test Corner Store"}
    assert classify_google(place) == "convenience"


def test_classify_google_falls_back_to_name_hint():
    place = {"primary_type": "point_of_interest", "types": ["point_of_interest"],
             "name": "Joe's Gourmet Deli"}
    assert classify_google(place) == "deli"
