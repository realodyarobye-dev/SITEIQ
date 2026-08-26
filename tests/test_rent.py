from siteiq.engine import rent as rent_engine


def test_user_entered_rent_is_authoritative(demographics, block, generators_result):
    result = rent_engine.build("deli", {"rent": 9000}, demographics, generators_result, block)
    assert result["monthly_rent"] == 9000
    assert result["estimated"] is False
    assert result["band"] is None


def test_missing_rent_produces_a_labeled_band(demographics, block, generators_result):
    # This is the honesty check: SiteIQ must never invent a precise rent
    # figure. It must produce a wide band and say so.
    result = rent_engine.build("deli", {}, demographics, generators_result, block)
    assert result["estimated"] is True
    assert result["band"]["low"] < result["band"]["high"]
    assert "ESTIMATED" in result["note"]


def test_assess_flags_unsustainable_rent():
    rent_info = {"monthly_rent": 40000}
    assessment = rent_engine.assess("deli", rent_info, realistic_monthly_sales=60000)
    assert assessment["band"] in ("HIGH", "UNSUSTAINABLE")
    assert assessment["rent_pct"] > assessment["healthy_pct"]


def test_assess_flags_excellent_rent():
    rent_info = {"monthly_rent": 2000}
    assessment = rent_engine.assess("deli", rent_info, realistic_monthly_sales=90000)
    assert assessment["band"] == "EXCELLENT"
