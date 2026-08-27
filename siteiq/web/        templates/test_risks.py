from siteiq.engine import risks as risk_engine

STOREFRONT_HISTORY_NONE = {"available": False, "reason": "No records matched.", "tenants": []}


def test_unsustainable_rent_and_conservative_loss_is_critical(
        demographics, block, dayparts_result, customers_result, gen_strength, comp_summary_light,
        confidence_ok):
    rent_info = {"monthly_rent": 40000, "estimated": False}
    rent_assessment = {"rent_pct": 55.0, "healthy_pct": 8.5, "band": "UNSUSTAINABLE",
                       "verdict": "Rent would consume the business.", "max_supportable_rent": 6000,
                       "gap": -34000}
    pnl = {
        "by_scenario": {
            "Conservative": {"revenue": 40000, "profit": -8000, "margin_pct": -20.0,
                             "labour_at_floor": False, "labour_pct": 25},
            "Realistic": {"revenue": 55000, "profit": -3000, "margin_pct": -5.4,
                         "labour_at_floor": False, "labour_pct": 22},
        },
        "breakeven_daily": 3000,
    }
    result = risk_engine.detect("deli", comp_summary_light, [], gen_strength, dayparts_result,
                                demographics, block, customers_result, rent_info, rent_assessment,
                                pnl, confidence_ok, STOREFRONT_HISTORY_NONE)
    assert result["has_critical"] is True
    titles = [r["title"] for r in result["critical"]]
    assert any("rent" in t.lower() or "money" in t.lower() for t in titles)


def test_healthy_deal_has_no_critical_flags(
        demographics, block, dayparts_result, customers_result, gen_strength, comp_summary_light,
        confidence_ok, rent_info_ok, rent_assessment_ok, pnl_light):
    result = risk_engine.detect("deli", comp_summary_light, [], gen_strength, dayparts_result,
                                demographics, block, customers_result, rent_info_ok,
                                rent_assessment_ok, pnl_light, confidence_ok,
                                STOREFRONT_HISTORY_NONE)
    assert result["has_critical"] is False


def test_low_confidence_produces_a_data_quality_flag(
        demographics, block, dayparts_result, customers_result, gen_strength, comp_summary_light,
        rent_info_ok, rent_assessment_ok, pnl_light, confidence_low):
    result = risk_engine.detect("deli", comp_summary_light, [], gen_strength, dayparts_result,
                                demographics, block, customers_result, rent_info_ok,
                                rent_assessment_ok, pnl_light, confidence_low,
                                STOREFRONT_HISTORY_NONE)
    titles = [r["title"] for r in result["items"]]
    assert any("confidence" in t.lower() for t in titles)


def test_estimated_rent_is_flagged_as_a_risk(
        demographics, block, dayparts_result, customers_result, gen_strength, comp_summary_light,
        rent_assessment_ok, pnl_light, confidence_ok):
    estimated_rent = {"monthly_rent": 8000, "estimated": True}
    result = risk_engine.detect("deli", comp_summary_light, [], gen_strength, dayparts_result,
                                demographics, block, customers_result, estimated_rent,
                                rent_assessment_ok, pnl_light, confidence_ok,
                                STOREFRONT_HISTORY_NONE)
    titles = [r["title"] for r in result["items"]]
    assert any("rent is estimated" in t.lower() for t in titles)
