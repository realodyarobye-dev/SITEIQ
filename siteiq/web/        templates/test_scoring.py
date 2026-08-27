from siteiq.engine import scoring as scoring_engine

STRONG_OPPORTUNITIES = {"items": [{"title": "Clear market gap", "strength": "HIGH",
                                   "signals": [], "action": ""}],
                        "count": 1, "best": {"title": "Clear market gap", "strength": "HIGH"}}
NO_OPPORTUNITIES = {"items": [], "count": 0, "best": None}


def _risks(has_critical, worst_title="Extreme competitive saturation"):
    critical = [{"title": worst_title, "severity": "CRITICAL", "detail": "", "action": ""}] \
        if has_critical else []
    return {
        "items": critical, "count": len(critical),
        "counts": {"CRITICAL": len(critical)},
        "worst": critical[0] if critical else None,
        "critical": critical,
        "has_critical": has_critical,
    }


def test_critical_risk_forces_pass_even_with_strong_fundamentals(
        generators_result, comp_summary_light, dayparts_result, demographics, block,
        customers_result, rent_assessment_ok, pnl_light, confidence_ok):
    risks = _risks(has_critical=True, worst_title="Extreme competitive saturation")
    result = scoring_engine.build(generators_result, comp_summary_light, dayparts_result,
                                  demographics, block, customers_result, rent_assessment_ok,
                                  pnl_light, STRONG_OPPORTUNITIES, risks, confidence_ok)
    assert result["verdict"] == "PASS"
    assert "extreme competitive saturation" in result["verdict_reason"].lower()


def test_conservative_loss_prevents_take_it_verdict(
        generators_result, comp_summary_light, dayparts_result, demographics, block,
        customers_result, rent_assessment_ok, confidence_ok):
    risks = _risks(has_critical=False)
    losing_pnl = {
        "by_scenario": {
            "Conservative": {"revenue": 40000, "profit": -1000, "margin_pct": -2.5,
                             "annual_profit": -12000, "labour_at_floor": False, "labour_pct": 22},
            "Realistic": {"revenue": 60000, "profit": 4000, "margin_pct": 6.6,
                         "annual_profit": 48000, "labour_at_floor": False, "labour_pct": 20},
            "Strong Operator": {"revenue": 75000, "profit": 9000, "margin_pct": 12.0,
                                "annual_profit": 108000, "labour_at_floor": False, "labour_pct": 18},
            "Elite Operator": {"revenue": 90000, "profit": 14000, "margin_pct": 15.5,
                               "annual_profit": 168000, "labour_at_floor": False, "labour_pct": 17},
        },
        "labour_floor": 6000, "hours_per_week": 100, "breakeven_daily": 2500, "assumptions": [],
    }
    result = scoring_engine.build(generators_result, comp_summary_light, dayparts_result,
                                  demographics, block, customers_result, rent_assessment_ok,
                                  losing_pnl, STRONG_OPPORTUNITIES, risks, confidence_ok)
    assert result["verdict"] not in ("TAKE IT", "STRONG")


def test_score_components_sum_to_a_plausible_total(
        generators_result, comp_summary_light, dayparts_result, demographics, block,
        customers_result, rent_assessment_ok, pnl_light, confidence_ok):
    risks = _risks(has_critical=False)
    result = scoring_engine.build(generators_result, comp_summary_light, dayparts_result,
                                  demographics, block, customers_result, rent_assessment_ok,
                                  pnl_light, NO_OPPORTUNITIES, risks, confidence_ok)
    assert 0 <= result["score"] <= 100
    assert len(result["components"]) == 6
    assert result["five_hundred_k"]["headline"]
