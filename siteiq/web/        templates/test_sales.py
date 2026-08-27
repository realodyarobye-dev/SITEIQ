from siteiq.engine import sales as sales_engine


def test_scenarios_are_strictly_ordered(demographics, block, dayparts_result, comp_summary_light):
    gen_strength = {"transit": 50, "office": 30, "hospital": 0, "school": 10, "college": 0,
                    "hotel": 0, "nightlife": 5, "gym": 10, "government": 0, "attraction": 0,
                    "park": 5, "bus": 20, "residential": 40}
    result = sales_engine.build("deli", {"rent": 8000, "sqft": 1200}, gen_strength, demographics,
                                comp_summary_light, block, dayparts_result, delivery_score=30)
    s = result["scenarios"]
    assert s["Conservative"]["daily"] < s["Realistic"]["daily"]
    assert s["Realistic"]["daily"] < s["Strong Operator"]["daily"]
    assert s["Strong Operator"]["daily"] < s["Elite Operator"]["daily"]


def test_capacity_ceiling_caps_extreme_demand(demographics, block, comp_summary_light):
    """This is the core fix over the original app, which had no upper bound at
    all and could model a small deli to tens of thousands of dollars a day.
    Feed the model an unrealistically enormous demand signal and confirm the
    physical store-capacity ceiling actually holds it down."""
    from siteiq.engine import dayparts as daypart_engine

    maxed_strength = {k: 100 for k in
                      ("transit", "office", "hospital", "school", "college", "hotel",
                       "nightlife", "gym", "government", "attraction", "park", "bus",
                       "residential")}
    huge_demo = dict(demographics)
    huge_demo["facts"] = dict(demographics["facts"])
    from siteiq.core.provenance import VERIFIED, fact
    huge_demo["facts"]["density_sq_mi"] = fact(400000, VERIFIED, "test")
    huge_demo["radius_estimates"] = {0.25: fact(400000, VERIFIED, "test")}

    dp = daypart_engine.build("deli_24h", maxed_strength, residential_base=100)
    small_store = dict(block)
    small_store["storefront_count"] = 25

    result = sales_engine.build("deli_24h", {"rent": 12000, "sqft": 700, "hours": "24 hours"},
                                maxed_strength, huge_demo, comp_summary_light, small_store, dp,
                                delivery_score=100)

    cap = result["capacity"]
    assert cap["served"] <= cap["max_daily"] * 1.01
    assert cap["constrained"] is True
    # The realistic daily sales figure must stay bounded by ticket x capacity,
    # not run away with the raw demand signal.
    ticket = result["ticket"]
    assert result["realistic_daily"] <= cap["max_daily"] * ticket * 1.65 + 1


def test_calibration_shifts_the_estimate(demographics, block, dayparts_result, comp_summary_light):
    gen_strength = {"transit": 50, "office": 30, "hospital": 0, "school": 10, "college": 0,
                    "hotel": 0, "nightlife": 5, "gym": 10, "government": 0, "attraction": 0,
                    "park": 5, "bus": 20, "residential": 40}
    inputs = {"rent": 8000, "sqft": 1200}
    baseline = sales_engine.build("deli", inputs, gen_strength, demographics, comp_summary_light,
                                  block, dayparts_result, delivery_score=30, calibration=(1.0, 0))
    calibrated = sales_engine.build("deli", inputs, gen_strength, demographics, comp_summary_light,
                                    block, dayparts_result, delivery_score=30, calibration=(1.4, 3))
    assert calibrated["realistic_daily"] > baseline["realistic_daily"]
    assert calibrated["calibrated"] is True
    assert calibrated["calibration_n"] == 3


def test_pnl_conservative_can_lose_money_when_rent_is_too_high(demographics, block,
                                                                dayparts_result,
                                                                comp_summary_light):
    gen_strength = {"transit": 10, "office": 5, "hospital": 0, "school": 0, "college": 0,
                    "hotel": 0, "nightlife": 0, "gym": 0, "government": 0, "attraction": 0,
                    "park": 0, "bus": 5, "residential": 10}
    thin_demo = dict(demographics)
    thin_demo["facts"] = dict(demographics["facts"])
    from siteiq.core.provenance import VERIFIED, fact
    thin_demo["facts"]["density_sq_mi"] = fact(4000, VERIFIED, "test")

    result = sales_engine.build("deli", {"rent": 30000, "sqft": 1200}, gen_strength, thin_demo,
                                comp_summary_light, block, dayparts_result, delivery_score=10)
    pnl = sales_engine.pnl("deli", result["scenarios"], {"rent": 30000, "sqft": 1200},
                           {"monthly_rent": 30000}, result["delivery"])
    assert pnl["by_scenario"]["Conservative"]["profit"] < pnl["by_scenario"]["Elite Operator"]["profit"]
