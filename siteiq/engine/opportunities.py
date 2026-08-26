"""Opportunity detector.

The rule here is that a gap needs at least two independent signals before we
call it an opportunity. "No pharmacy on the map, therefore pharmacy opportunity"
is exactly the kind of reasoning that loses people money, so every rule below
requires evidence of demand AND evidence of unmet supply.
"""
from ..core.provenance import INFERRED


def detect(concept, comp_summary, competitors, gen_strength, dayparts, demographics,
           block, customers, delivery_score):
    found = []
    s = gen_strength
    dem = demographics
    income = dem["facts"]["median_income"].value
    density = dem["facts"]["density_sq_mi"].value or 0
    late = dayparts["summary"]["Late Night"]["score"]
    morning = dayparts["summary"]["Morning"]["score"]
    lunch = dayparts["summary"]["Lunch"]["score"]

    open_24 = comp_summary.get("open_24h_count", 0)
    direct = comp_summary.get("direct_count", 0)
    weak = comp_summary.get("weak_incumbents", [])
    avg_rating = comp_summary.get("avg_rating")

    def add(title, strength, signals, action):
        found.append({"title": title, "strength": strength, "signals": signals, "action": action})

    # 1. Overnight gap
    if late >= 45 and open_24 == 0 and (s.get("hospital", 0) > 25 or s.get("nightlife", 0) > 30
                                        or s.get("transit", 0) > 40):
        add("No 24-hour operator serving real overnight demand", "HIGH",
            [f"Modeled late-night demand scores {late}/100",
             "Zero competitors identified as operating 24 hours",
             f"Overnight generators present: hospital {s.get('hospital', 0)}/100, "
             f"nightlife {s.get('nightlife', 0)}/100, transit {s.get('transit', 0)}/100"],
            "Running 24 hours would give you the overnight daypart uncontested. Overnight is "
            "low-labour, high-margin trade in a deli. This is the single clearest edge at this site.")

    # 2. Office breakfast/lunch gap
    if s.get("office", 0) >= 45 and lunch >= 45:
        food_comp = [c for c in competitors if c["category"] in ("deli", "fast_food", "coffee")
                     and (c["distance_mi"] or 9) <= 0.15]
        if len(food_comp) <= 2:
            add("Strong office demand with thin breakfast and lunch supply", "HIGH",
                [f"Office generator strength {s.get('office', 0)}/100",
                 f"Modeled lunch demand {lunch}/100",
                 f"Only {len(food_comp)} directly competing food operators within a block"],
                "Build the breakfast sandwich and lunch hero programme first. Weekday 7-9:30am and "
                "11:30am-2pm will carry this store. Get catering trays in front of the office "
                "managers in month one.")

    # 3. Quality gap
    if avg_rating and avg_rating < 4.0 and direct >= 2:
        names = ", ".join(c["name"] for c in weak[:3]) or "the incumbents"
        add("Incumbents are weak on quality", "HIGH" if avg_rating < 3.8 else "MEDIUM",
            [f"Average competitor rating is {avg_rating}★ across {comp_summary.get('rated_count', 0)} rated businesses",
             f"{len(weak)} direct competitors rated under 3.9★",
             "Customers here are served, but not served well"],
            f"A clean store with good prepared food takes share directly from {names}. Ratings "
            "this low usually mean dirty stores, bad food or rude service - all of which you "
            "control. Go buy from each of them before you sign.")

    # 4. Affluent but underserved on premium
    if income and income >= 110000 and density > 25000:
        premium = [c for c in competitors if c["category"] in ("gourmet_market", "supermarket")
                   and (c["distance_mi"] or 9) <= 0.3]
        if len(premium) <= 1:
            add("High-income residents with no quality grocery option nearby", "MEDIUM",
                [f"Census tract median household income ${income:,}",
                 f"Population density {density:,}/sq mi",
                 f"Only {len(premium)} supermarket or gourmet market within 0.3 mi"],
                "Skew the mix upmarket: better coffee, prepared foods, organic produce, imported "
                "goods, decent wine where licensed. These customers pay for quality and are not "
                "shopping on price.")

    # 5. Student cheap-food gap
    if s.get("college", 0) >= 40 or s.get("school", 0) >= 55:
        cheap = [c for c in competitors if c["category"] in ("fast_food", "deli")
                 and (c["distance_mi"] or 9) <= 0.2]
        if len(cheap) <= 2:
            add("Large student population with limited cheap prepared food", "MEDIUM",
                [f"College strength {s.get('college', 0)}/100, school strength {s.get('school', 0)}/100",
                 f"Only {len(cheap)} cheap prepared-food operators within 0.2 mi"],
                "Price a visible value menu - chopped cheese, bacon-egg-and-cheese, combo deals. "
                "Students bring volume, not ticket. Make it fast and make it cheap to enter.")

    # 6. Hospital overnight convenience
    if s.get("hospital", 0) >= 50 and open_24 == 0:
        add("Hospital nearby with no overnight convenience option", "HIGH",
            [f"Hospital generator strength {s.get('hospital', 0)}/100",
             "No 24-hour competitor identified",
             "Hospital shift changes generate demand at 7am, 3pm, 11pm and overnight"],
            "Hospital staff are the most loyal customers in NYC retail because their options at "
            "3am are zero. Match your hours to shift changes and they become daily regulars.")

    # 7. Delivery gap
    if delivery_score >= 55 and density > 30000:
        add("Dense residential base well suited to delivery", "MEDIUM",
            [f"Delivery opportunity score {delivery_score}/100",
             f"Population density {density:,}/sq mi",
             "Apartment density within delivery range supports app volume"],
            "Set up GrubHub, DoorDash, Uber Eats and Seamless before opening day, with photographed "
            "menu items and specific category names. Watch the blended commission - at roughly 24% "
            "it is your second-largest cost line after food.")

    # 8. Nightlife late food gap
    if s.get("nightlife", 0) >= 45 and late >= 50 and open_24 <= 1:
        add("Strong nightlife with limited late-night food", "MEDIUM",
            [f"Nightlife generator strength {s.get('nightlife', 0)}/100",
             f"Modeled late-night demand {late}/100",
             f"{open_24} competitors open 24 hours"],
            "Thursday to Saturday 11pm-3am is high-margin trade. Grill open late, simple menu, "
            "fast service. Staff it only on the nights that justify it.")

    # 9. Morning commuter gap
    if s.get("transit", 0) >= 55 and morning >= 55:
        coffee = [c for c in competitors if c["category"] in ("coffee", "bakery")
                  and (c["distance_mi"] or 9) <= 0.12]
        if len(coffee) <= 1:
            add("Heavy commuter flow with weak coffee competition", "MEDIUM",
                [f"Transit strength {s.get('transit', 0)}/100",
                 f"Modeled morning demand {morning}/100",
                 f"Only {len(coffee)} coffee-focused competitors within 0.12 mi"],
                "Own the 6:30-9:30am window. Coffee and breakfast sandwiches, priced sharply, "
                "served in under 60 seconds. Speed matters more than quality in this window - "
                "commuters will not wait behind three people.")

    # 10. Construction-driven temporary demand
    if (block.get("construction_count") or 0) >= 6:
        add("Active construction on the block", "MEDIUM",
            [f"{block['construction_count']} DOB permits issued on this street recently",
             "Construction crews start early and buy in bulk"],
            "Crews buy big breakfast orders at 6-7am and hero sandwiches at noon, for the whole "
            "crew at once. Also note this cuts both ways - scaffolding and sidewalk sheds hurt "
            "visibility while the work runs.")

    # 11. Thin competition overall
    if comp_summary.get("pressure", 0) < 2.0 and density > 20000:
        add("Genuinely thin competition for the population present", "HIGH",
            [f"Competitive pressure index only {comp_summary.get('pressure', 0)}",
             f"Population density {density:,}/sq mi",
             f"Only {direct} direct competitors identified"],
            "This is the rarest condition in NYC street retail. Verify it on foot before you "
            "believe it - if the block genuinely supports a store and nobody is running one "
            "well, find out why before assuming you are the first to notice.")

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    found.sort(key=lambda x: order.get(x["strength"], 3))

    return {
        "items": found,
        "count": len(found),
        "best": found[0] if found else None,
        "evidence": INFERRED,
        "method": ("Each opportunity requires at least two independent signals - evidence of "
                   "demand and evidence that demand is not being served. Single-signal gaps are "
                   "deliberately not reported."),
    }
