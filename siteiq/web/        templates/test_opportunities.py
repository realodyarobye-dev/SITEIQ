from siteiq.engine import dayparts as daypart_engine
from siteiq.engine import opportunities as opp_engine

# Strong overnight demand signal (hospital + nightlife + transit), used to test
# the "no 24-hour operator" opportunity rule, which requires BOTH a demand
# signal AND zero verified 24-hour competitors before it fires.
STRONG_OVERNIGHT_GEN_STRENGTH = {
    "transit": 70, "office": 10, "hospital": 90, "school": 0, "college": 0,
    "hotel": 10, "nightlife": 80, "gym": 0, "government": 0, "attraction": 0,
    "park": 0, "bus": 20, "residential": 50,
}


def _dayparts():
    return daypart_engine.build("deli_24h", STRONG_OVERNIGHT_GEN_STRENGTH, residential_base=50)


def test_overnight_gap_fires_when_no_24h_competitor_exists(demographics, block, customers_result):
    comp_summary = {"open_24h_count": 0, "direct_count": 2, "weak_incumbents": [], "avg_rating": 4.0}
    result = opp_engine.detect("deli_24h", comp_summary, [], STRONG_OVERNIGHT_GEN_STRENGTH,
                               _dayparts(), demographics, block, customers_result,
                               delivery_score=30)
    titles = [o["title"] for o in result["items"]]
    assert any("24-hour" in t for t in titles)


def test_overnight_gap_does_not_fire_when_a_24h_competitor_already_exists(
        demographics, block, customers_result):
    """This is the two-signal gating check: the same strong demand signal as
    above must NOT trigger the opportunity once a competitor already covers
    the overnight window. A single signal (demand alone) is not enough."""
    comp_summary = {"open_24h_count": 1, "direct_count": 2, "weak_incumbents": [], "avg_rating": 4.0}
    result = opp_engine.detect("deli_24h", comp_summary, [], STRONG_OVERNIGHT_GEN_STRENGTH,
                               _dayparts(), demographics, block, customers_result,
                               delivery_score=30)
    titles = [o["title"] for o in result["items"]]
    assert not any("24-hour" in t for t in titles)


def test_no_signals_yields_no_opportunities(demographics_unavailable, block, customers_result):
    flat_gen_strength = {k: 0 for k in STRONG_OVERNIGHT_GEN_STRENGTH}
    dp = daypart_engine.build("deli", flat_gen_strength, residential_base=0)
    comp_summary = {"open_24h_count": 0, "direct_count": 0, "weak_incumbents": [], "avg_rating": None}
    result = opp_engine.detect("deli", comp_summary, [], flat_gen_strength, dp,
                               demographics_unavailable, block, customers_result,
                               delivery_score=0)
    assert result["items"] == []
    assert result["best"] is None
