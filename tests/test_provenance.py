from siteiq.core.provenance import (INFERRED, MODELED, UNAVAILABLE, VERIFIED,
                                    ConfidenceLedger, fact, unknown)


def test_fact_with_value_is_known():
    f = fact(42, VERIFIED, "U.S. Census ACS")
    assert f.known is True
    assert f.label == "Confirmed fact"
    assert f.or_else(0) == 42


def test_fact_none_value_becomes_unavailable():
    # This is the specific bug the original app had: missing data silently
    # became a default number. A None value must never produce a confidence
    # tier that looks like real evidence.
    f = fact(None, VERIFIED, "U.S. Census ACS")
    assert f.confidence == UNAVAILABLE
    assert f.known is False
    assert f.or_else(3000) == 3000


def test_unknown_helper_is_unavailable():
    f = unknown("Google Places")
    assert f.confidence == UNAVAILABLE
    assert f.value is None


def test_confidence_ledger_score_is_weighted_average():
    ledger = ConfidenceLedger()
    ledger.add("Demographics", VERIFIED, "ACS", weight=1.0)
    ledger.add("Sales estimate", MODELED, "SiteIQ model", weight=1.0)
    ledger.add("Foot traffic", UNAVAILABLE, "None connected", weight=1.0)
    score = ledger.score()
    # VERIFIED=1.0, MODELED=0.55, UNAVAILABLE=0.0 -> mean 0.5166... -> 52
    assert 45 <= score <= 58


def test_confidence_ledger_missing_lists_only_unavailable():
    ledger = ConfidenceLedger()
    ledger.add("A", VERIFIED, "src")
    ledger.add("B", UNAVAILABLE, "src")
    ledger.add("C", INFERRED, "src")
    missing = ledger.missing()
    assert len(missing) == 1
    assert missing[0]["topic"] == "B"


def test_confidence_ledger_empty_is_zero():
    assert ConfidenceLedger().score() == 0
