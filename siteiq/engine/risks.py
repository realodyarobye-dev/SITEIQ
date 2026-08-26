"""Red flags.

Severity: LOW, MEDIUM, HIGH, CRITICAL. Data-quality problems are treated as real
risks and graded alongside commercial ones, because a confident report built on
thin data is itself a way to lose $500,000.
"""
from ..core.provenance import UNAVAILABLE

SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


def detect(concept, comp_summary, competitors, gen_strength, dayparts, demographics,
           block, customers, rent_info, rent_assessment, pnl, confidence, storefront_history):
    out = []

    def add(title, severity, detail, action=""):
        out.append({"title": title, "severity": severity, "detail": detail, "action": action})

    s = gen_strength
    density = demographics["facts"]["density_sq_mi"].value
    pressure = comp_summary.get("pressure", 0)
    strongest = comp_summary.get("strongest")

    # ---------------------------------------------------------- competition
    if pressure >= 9:
        add("Extreme competitive saturation", "CRITICAL",
            f"Competitive pressure index {pressure} within a quarter mile with "
            f"{comp_summary.get('direct_count', 0)} direct competitors and "
            f"{comp_summary.get('within_block', 0)} competing businesses within one block. "
            "This customer pool is already being fought over hard.",
            "Do not proceed on the assumption that you will simply be better. Identify exactly "
            "which competitor's customers you are taking and why they would switch.")
    elif pressure >= 6:
        add("Heavy competition", "HIGH",
            f"Pressure index {pressure} with {comp_summary.get('direct_count', 0)} direct "
            "competitors nearby. Volume will be split.",
            "Your differentiation needs to be specific and visible from the sidewalk.")

    if strongest and strongest.get("threat") == "VERY HIGH":
        add(f"Dominant incumbent: {strongest['name']}", "HIGH",
            strongest.get("why", ""),
            "Buy from them at three different dayparts. Count their customers for 15 minutes "
            "each time. If they are always busy, you are buying into their overflow, not their market.")

    if comp_summary.get("open_24h_count", 0) >= 2 and concept in ("deli", "deli_24h", "convenience"):
        add("Multiple 24-hour competitors already operating", "MEDIUM",
            f"{comp_summary['open_24h_count']} nearby competitors run 24 hours, so the overnight "
            "daypart is already covered.",
            "Staying open overnight will not be a differentiator here. Price the labour carefully.")

    # -------------------------------------------------------------- demand
    if density is not None and density < 12000:
        add("Low residential density", "HIGH" if density < 7000 else "MEDIUM",
            f"Census tract density is {density:,}/sq mi, which is thin for NYC street retail. "
            "The base of daily repeat customers is small.",
            "You will depend on commuters, workers or destination traffic rather than residents. "
            "Confirm those flows exist in person.")
    elif density is None:
        add("Residential density unknown", "MEDIUM",
            "Census data could not be resolved for this location, so the resident customer base "
            "could not be measured.",
            "Verify the population base manually before relying on the sales model.")

    total_pull = sum(s.values())
    if total_pull < 90:
        add("Weak demand generators", "HIGH",
            "Very few schools, offices, hospitals, hotels, transit stops or nightlife venues were "
            "mapped within range. Nothing nearby is manufacturing foot traffic.",
            "Stand on the corner at 8am, noon and 6pm and count people. If the sidewalk is empty, "
            "walk away regardless of what the rent looks like.")

    if block.get("storefront_count", 0) < 5:
        add("Isolated storefront with little adjacent retail", "HIGH",
            f"Only {block.get('storefront_count', 0)} mapped storefronts within about 240 feet. "
            "There is no retail strip pulling browsers past your door.",
            "Impulse traffic will be minimal. The store must be a destination people decide to "
            "visit, which is much harder for a deli or convenience store.")

    if not block.get("is_corner") and block.get("storefront_count", 0) < 12:
        add("Possible visibility limitation", "LOW",
            "Mid-block position on a block without a dense retail run. Storefront visibility and "
            "sightlines could not be verified from public data.",
            "Photograph the storefront from 100 feet in both directions and from across the street.")

    if s.get("transit", 0) < 15 and s.get("bus", 0) < 20:
        add("Limited transit access", "MEDIUM",
            "No significant subway or bus infrastructure mapped within capture range. Commuter "
            "flow, which is the most reliable NYC traffic source, is largely absent.",
            "Check whether customers arrive by car, and if so whether they can actually stop.")

    late = dayparts["summary"]["Late Night"]["score"]
    if late < 22 and concept == "deli_24h":
        add("Weak late-night demand for a 24-hour concept", "HIGH",
            f"Modeled late-night demand is only {late}/100. Overnight labour would likely cost "
            "more than the sales it generates.",
            "Reconsider 24-hour operation, or plan to trial it for 60 days and cut it if the "
            "numbers do not hold.")

    # ------------------------------------------------------- concentration
    conc = customers.get("concentration", {})
    if conc.get("level") == "CONCENTRATED":
        top = customers["ranked"][0]["label"] if customers.get("ranked") else "one group"
        add(f"Overdependence on {top.lower()}", "MEDIUM",
            conc.get("note", ""),
            "Model what happens to your weekly sales if that group's routine changes. If the "
            "answer is 'the store fails', that is your real risk.")

    # -------------------------------------------------------------- economics
    if rent_assessment["band"] == "UNSUSTAINABLE":
        add("Rent is unsustainable against modeled sales", "CRITICAL",
            f"Rent is {rent_assessment['rent_pct']}% of modeled realistic sales versus a healthy "
            f"{rent_assessment['healthy_pct']}% for this concept. Maximum supportable rent is "
            f"about ${rent_assessment['max_supportable_rent']:,}/month.",
            f"Negotiate down by roughly ${abs(rent_assessment['gap']):,}/month or walk.")
    elif rent_assessment["band"] == "HIGH":
        add("High occupancy cost", "HIGH",
            f"Rent is {rent_assessment['rent_pct']}% of modeled sales versus a healthy "
            f"{rent_assessment['healthy_pct']}%.",
            f"Target ${rent_assessment['max_supportable_rent']:,}/month, or secure free rent "
            "during buildout to compensate.")
    elif rent_assessment["band"] == "TIGHT":
        add("Occupancy cost above the comfortable range", "MEDIUM",
            f"Rent at {rent_assessment['rent_pct']}% of modeled sales leaves little margin for error.",
            "Negotiate. Even $500/month is $60,000 across a ten-year lease.")

    conservative = pnl["by_scenario"].get("Conservative", {})
    if conservative.get("profit", 0) <= 0:
        add("Loses money in the conservative case", "CRITICAL",
            f"At conservative sales of ${conservative.get('revenue', 0):,}/month this location "
            f"loses about ${abs(conservative.get('profit', 0)):,}/month after all operating costs. "
            "The deal only works if you hit the realistic case or better from the start.",
            "Either negotiate the rent down, cut the buildout, or pass. Do not sign a long lease "
            "on a plan that requires above-average performance to break even.")
    elif conservative.get("margin_pct", 0) < 4:
        add("Thin margin in the conservative case", "HIGH",
            f"Conservative case leaves only {conservative.get('margin_pct', 0)}% operating margin.",
            "There is no room for a bad quarter, a broken compressor or a rent escalation.")

    realistic = pnl["by_scenario"].get("Realistic", {})
    if realistic.get("labour_at_floor"):
        add("Labour cost driven by hours, not by sales", "MEDIUM",
            f"Covering your planned {pnl['hours_per_week']} hours a week costs about "
            f"${pnl['labour_floor']:,}/month regardless of how slow it gets. At modeled sales that "
            f"is {realistic.get('labour_pct', 0)}% of revenue.",
            "Either raise volume or shorten hours. Paying someone to stand in an empty store is "
            "the fastest way to lose a deli.")

    if pnl.get("breakeven_daily"):
        be = pnl["breakeven_daily"]
        realistic_daily = realistic.get("revenue", 0) / 30.4 if realistic.get("revenue") else 0
        if realistic_daily and be > realistic_daily * 0.88:
            add("Break-even is uncomfortably close to modeled sales", "HIGH",
                f"You need about ${be:,}/day to break even and the realistic model is only "
                f"${realistic_daily:,.0f}/day.",
                "This is a thin deal. It needs a rent concession to be worth the risk.")

    # ------------------------------------------------------------ location history
    if storefront_history and storefront_history.get("available"):
        tenants = storefront_history.get("tenants", [])
        short_lived = [t for t in tenants if t["span_years"] <= 2 and not t["appears_current"]]
        if len(tenants) >= 4 and len(short_lived) >= 3:
            add("This storefront churns tenants", "HIGH",
                f"NYC records show {len(tenants)} distinct businesses at this exact address, "
                f"{len(short_lived)} of which appear in records for two years or less. "
                "That pattern usually means something structural: bad visibility, a difficult "
                "landlord, a rent that nobody can carry, or a block that does not deliver traffic.",
                "Find the previous tenants and ask them directly why they left. This is the single "
                "highest-value phone call you can make before signing.")

    # ------------------------------------------------------------ data quality
    if confidence["score"] < 45:
        add("Low data confidence", "HIGH",
            f"Data confidence is only {confidence['score']}/100 with "
            f"{confidence['missing_count']} major inputs unavailable. Several conclusions in this "
            "report rest on modeling rather than observation.",
            "Treat this report as a screening tool only. Do substantially more field work before "
            "committing money.")
    elif confidence["score"] < 65:
        add("Moderate data gaps", "MEDIUM",
            f"Data confidence {confidence['score']}/100. Some inputs could not be verified.",
            "Check the Data Confidence section to see exactly which conclusions are weakest.")

    if comp_summary.get("review_coverage", 0) == 0 and comp_summary.get("total", 0) > 0:
        add("No competitor ratings or review data", "MEDIUM",
            "Competitors were identified from OpenStreetMap only, with no ratings, review counts, "
            "hours or photos. Their real strength is unknown.",
            "Adding a Google Maps API key would resolve this. Until then, competitor threat "
            "levels are based on category and distance alone.")

    if rent_info.get("estimated"):
        add("Rent is estimated, not actual", "HIGH",
            "You did not enter a rent, so every profit figure in this report is built on a modeled "
            "rent band that could easily be wrong by 50% in either direction.",
            "Get the actual asking rent and re-run this analysis. Nothing in the economics section "
            "is reliable until you do.")

    out.sort(key=lambda x: SEVERITY_ORDER.get(x["severity"], 4))

    counts = {}
    for r in out:
        counts[r["severity"]] = counts.get(r["severity"], 0) + 1

    return {
        "items": out,
        "count": len(out),
        "counts": counts,
        "worst": out[0] if out else None,
        "critical": [r for r in out if r["severity"] == "CRITICAL"],
        "has_critical": any(r["severity"] == "CRITICAL" for r in out),
    }
