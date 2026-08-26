"""Overall score, verdict, and the one answer the operator actually came for.

The score is a weighted blend of six components, each shown separately so it can
be argued with. The verdict is deliberately not a pure function of the score:
a critical red flag or a loss-making conservative case overrides a high score,
because that is how a real operator thinks.
"""

WEIGHTS = {
    "demand": 0.28,
    "competition": 0.22,
    "economics": 0.22,
    "customer_base": 0.12,
    "block_quality": 0.10,
    "opportunity": 0.06,
}

COMPONENT_LABELS = {
    "demand": "Traffic and demand generators",
    "competition": "Competitive position",
    "economics": "Rent and profitability",
    "customer_base": "Customer base depth",
    "block_quality": "Block and storefront quality",
    "opportunity": "Unserved opportunity",
}


def build(generators, comp_summary, dayparts, demographics, block, customers,
          rent_assessment, pnl, opportunities, risks, confidence):
    c = {}
    notes = {}

    # ---- demand
    pull = generators.get("total_pull", 0)
    daypart_overall = dayparts["overall"]
    c["demand"] = min(100, pull * 0.6 + daypart_overall * 0.55)
    notes["demand"] = (f"Generator pull {pull}/100 and modeled all-day demand {daypart_overall}/100 "
                       f"across {len(generators.get('items', []))} mapped traffic sources.")

    # ---- competition (higher is better for you)
    pressure = comp_summary.get("pressure", 0)
    comp_score = max(5, 100 - pressure * 9)
    avg_rating = comp_summary.get("avg_rating")
    if avg_rating:
        comp_score += (4.2 - avg_rating) * 14
    if comp_summary.get("strongest") and comp_summary["strongest"].get("threat") == "VERY HIGH":
        comp_score -= 12
    c["competition"] = max(0, min(100, comp_score))
    notes["competition"] = (f"{comp_summary.get('direct_count', 0)} direct competitors, pressure "
                            f"index {pressure}, average incumbent rating "
                            f"{avg_rating if avg_rating else 'unknown'}.")

    # ---- economics
    band_scores = {"EXCELLENT": 95, "HEALTHY": 78, "TIGHT": 55, "HIGH": 32, "UNSUSTAINABLE": 8}
    econ = band_scores.get(rent_assessment["band"], 50)
    realistic = pnl["by_scenario"].get("Realistic", {})
    conservative = pnl["by_scenario"].get("Conservative", {})
    margin = realistic.get("margin_pct", 0)
    econ = econ * 0.55 + min(100, max(0, margin * 5.5)) * 0.45
    if conservative.get("profit", 0) <= 0:
        econ *= 0.62
    c["economics"] = max(0, min(100, econ))
    notes["economics"] = (f"Rent at {rent_assessment['rent_pct']}% of modeled sales "
                          f"({rent_assessment['band']}), realistic operating margin {margin}%.")

    # ---- customer base
    ranked = customers.get("ranked", [])
    depth = sum(r["score"] for r in ranked[:4]) / 4 if ranked else 0
    if customers.get("concentration", {}).get("level") == "DIVERSIFIED":
        depth *= 1.12
    elif customers.get("concentration", {}).get("level") == "CONCENTRATED":
        depth *= 0.86
    c["customer_base"] = min(100, depth)
    notes["customer_base"] = (f"{len(ranked)} meaningful customer groups, "
                              f"{customers.get('concentration', {}).get('level', 'unknown').lower()} mix.")

    # ---- block quality
    storefronts = block.get("storefront_count", 0)
    bq = min(100, storefronts * 3.4)
    if block.get("is_corner"):
        bq += 10
    if block.get("vacancy", {}).get("detected", 0) >= 3:
        bq -= 14
    c["block_quality"] = max(0, min(100, bq))
    notes["block_quality"] = (f"{storefronts} storefronts within about 240 feet"
                              + (", corner position" if block.get("is_corner") else ", mid-block")
                              + f", {block.get('vacancy', {}).get('detected', 0)} tagged vacancies.")

    # ---- opportunity
    strength_pts = {"HIGH": 30, "MEDIUM": 16, "LOW": 7}
    opp = sum(strength_pts.get(o["strength"], 5) for o in opportunities.get("items", [])[:4])
    c["opportunity"] = min(100, opp)
    notes["opportunity"] = f"{opportunities.get('count', 0)} multi-signal opportunities detected."

    raw = sum(c[k] * WEIGHTS[k] for k in WEIGHTS)

    # Penalties that a weighted average would otherwise wash out.
    penalty = 0
    penalty += 14 * len(risks.get("critical", []))
    penalty += 3 * risks.get("counts", {}).get("HIGH", 0)
    score = max(1, min(100, raw - penalty))

    components = [{
        "key": k, "label": COMPONENT_LABELS[k], "score": round(c[k]),
        "weight": WEIGHTS[k], "contribution": round(c[k] * WEIGHTS[k], 1), "note": notes[k],
    } for k in sorted(WEIGHTS, key=lambda x: -WEIGHTS[x])]

    verdict, verdict_reason = _verdict(score, risks, conservative, rent_assessment, confidence)
    answer = _500k(verdict, score, confidence, risks, opportunities, comp_summary,
                   rent_assessment, pnl, conservative)

    return {
        "score": round(score, 1),
        "raw_score": round(raw, 1),
        "penalty": round(penalty, 1),
        "components": components,
        "verdict": verdict,
        "verdict_reason": verdict_reason,
        "five_hundred_k": answer,
    }


def _verdict(score, risks, conservative, rent_assessment, confidence):
    if risks.get("has_critical"):
        crit = risks["critical"][0]["title"]
        return "PASS", (f"A critical red flag overrides the score: {crit.lower()}. "
                        "Fix that condition or walk away.")
    if conservative.get("profit", 0) <= 0:
        return "NEGOTIATE", ("The location screens acceptably but loses money if sales come in at "
                             "the conservative case. The deal only works at a lower rent.")
    if score >= 82 and rent_assessment["band"] in ("EXCELLENT", "HEALTHY") and confidence["score"] >= 60:
        return "TAKE IT", ("Strong demand, manageable competition and occupancy cost that leaves "
                           "real margin. Verify on foot, then move quickly.")
    if score >= 70:
        return "STRONG", ("Good fundamentals. Worth serious diligence and a competitive offer, "
                          "with normal negotiation on terms.")
    if score >= 56:
        return "NEGOTIATE", ("Workable, but only at the right rent and terms. The economics are "
                             "not comfortable enough to accept the asking price as offered.")
    if score >= 42:
        return "MAYBE", ("Marginal. This one depends heavily on execution and on things this "
                         "report cannot see. Only proceed if field work is clearly positive.")
    return "PASS", ("The fundamentals do not support the risk. Demand, competition or economics "
                    "are working against you here.")


def _500k(verdict, score, confidence, risks, opportunities, comp_summary,
          rent_assessment, pnl, conservative):
    realistic = pnl["by_scenario"].get("Realistic", {})
    annual = realistic.get("annual_profit", 0)

    if verdict == "TAKE IT":
        headline = "YES - I would put $500K here, after I walked the block myself."
    elif verdict == "STRONG":
        headline = "PROBABLY YES - I would put $500K here if the field checks confirm the numbers."
    elif verdict == "NEGOTIATE":
        headline = "ONLY AT THE RIGHT PRICE - I would not put $500K here on these terms."
    elif verdict == "MAYBE":
        headline = "NOT YET - I would need to see this block with my own eyes before risking $500K."
    else:
        headline = "NO - I would not put $500K here."

    parts = []
    if annual > 0:
        parts.append(f"At the realistic case this location models to about ${annual:,} a year in "
                     f"operating profit before debt service, owner salary and taxes")
        if annual > 0:
            years = 500000 / annual if annual else 0
            if years < 30:
                parts.append(f"which would return $500,000 in roughly {years:.1f} years if the "
                             "model holds")
    else:
        parts.append("At the realistic case this location does not model to a positive operating "
                     "profit")

    if conservative.get("profit", 0) <= 0:
        parts.append("and it loses money in the conservative case, which is the number you should "
                     "actually plan around")

    if opportunities.get("best"):
        parts.append(f"The clearest edge is that {opportunities['best']['title'].lower()}")
    if risks.get("worst"):
        parts.append(f"The thing most likely to kill it is {risks['worst']['title'].lower()}")

    if confidence["score"] < 60:
        parts.append(f"Data confidence is only {confidence['score']}/100, so treat all of this as "
                     "a screening opinion rather than a conclusion")

    explanation = ". ".join(parts) + "."
    return {"headline": headline, "explanation": explanation,
            "annual_profit_realistic": annual,
            "annual_profit_conservative": conservative.get("annual_profit", 0)}
