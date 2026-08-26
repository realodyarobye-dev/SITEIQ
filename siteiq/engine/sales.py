"""Sales and profit model.

The old version computed a score and then multiplied it by a ticket size, which
produced numbers that looked precise and meant nothing. This version builds
sales from the bottom up:

    daily transactions = SUM over customer pools of
                         (estimated pool size x capture rate x competitive share)

then multiplies by a concept ticket, adds delivery separately, and runs a real
street-retail P&L on the result including third-party commission, card fees and
a labour floor based on the hours you actually plan to open.

Every pool size is an estimate and is shown to the operator as one. The point is
not that the number is right - it is that you can see every assumption and argue
with it.
"""
import math

from ..config import CARD_FEE, CARD_SHARE, CONCEPTS, DELIVERY_COMMISSION, FIXED_MONTHLY
from ..core.provenance import MODELED

# Pool size assumptions: how many people a "100/100" generator strength implies
# pass within capture range on a typical day. Deliberately conservative.
POOL_SIZE_AT_FULL = {
    "office": 2400, "transit": 7000, "hospital": 1600, "school": 900,
    "college": 2000, "hotel": 800, "nightlife": 900, "gym": 550,
    "government": 700, "attraction": 1400, "park": 900, "bus": 900,
}

# Capture rate = share of an exposed pool that transacts with you on a normal
# day, before competition. These are monopoly-case rates; competition cuts them.
CAPTURE = {
    "deli":       {"resident": 0.115, "office": 0.105, "transit": 0.022, "hospital": 0.10,
                   "school": 0.085, "college": 0.070, "hotel": 0.075, "nightlife": 0.045,
                   "gym": 0.070, "government": 0.090, "attraction": 0.020, "park": 0.022,
                   "bus": 0.020},
    "deli_24h":   {"resident": 0.130, "office": 0.100, "transit": 0.024, "hospital": 0.145,
                   "school": 0.080, "college": 0.090, "hotel": 0.095, "nightlife": 0.080,
                   "gym": 0.070, "government": 0.080, "attraction": 0.022, "park": 0.022,
                   "bus": 0.022},
    "convenience": {"resident": 0.075, "office": 0.055, "transit": 0.016, "hospital": 0.055,
                    "school": 0.075, "college": 0.055, "hotel": 0.055, "nightlife": 0.035,
                    "gym": 0.035, "government": 0.045, "attraction": 0.014, "park": 0.016,
                    "bus": 0.014},
    "gourmet_market": {"resident": 0.055, "office": 0.060, "transit": 0.010, "hospital": 0.035,
                       "school": 0.015, "college": 0.020, "hotel": 0.045, "nightlife": 0.010,
                       "gym": 0.040, "government": 0.040, "attraction": 0.012, "park": 0.014,
                       "bus": 0.008},
    "supermarket": {"resident": 0.075, "office": 0.020, "transit": 0.006, "hospital": 0.020,
                    "school": 0.010, "college": 0.020, "hotel": 0.010, "nightlife": 0.004,
                    "gym": 0.012, "government": 0.015, "attraction": 0.004, "park": 0.008,
                    "bus": 0.006},
    "cafe":       {"resident": 0.045, "office": 0.105, "transit": 0.018, "hospital": 0.065,
                   "school": 0.020, "college": 0.085, "hotel": 0.060, "nightlife": 0.008,
                   "gym": 0.055, "government": 0.075, "attraction": 0.018, "park": 0.020,
                   "bus": 0.012},
    "fast_casual": {"resident": 0.028, "office": 0.075, "transit": 0.010, "hospital": 0.055,
                    "school": 0.030, "college": 0.065, "hotel": 0.035, "nightlife": 0.030,
                    "gym": 0.030, "government": 0.060, "attraction": 0.016, "park": 0.012,
                    "bus": 0.008},
    "restaurant": {"resident": 0.016, "office": 0.035, "transit": 0.005, "hospital": 0.018,
                   "school": 0.004, "college": 0.028, "hotel": 0.055, "nightlife": 0.045,
                   "gym": 0.010, "government": 0.030, "attraction": 0.022, "park": 0.010,
                   "bus": 0.004},
    "smoke_shop": {"resident": 0.014, "office": 0.012, "transit": 0.005, "hospital": 0.006,
                   "school": 0.004, "college": 0.030, "hotel": 0.012, "nightlife": 0.038,
                   "gym": 0.004, "government": 0.008, "attraction": 0.006, "park": 0.008,
                   "bus": 0.005},
    "pharmacy":   {"resident": 0.028, "office": 0.020, "transit": 0.006, "hospital": 0.075,
                   "school": 0.008, "college": 0.014, "hotel": 0.020, "nightlife": 0.004,
                   "gym": 0.008, "government": 0.020, "attraction": 0.006, "park": 0.006,
                   "bus": 0.006},
    "laundromat": {"resident": 0.012, "office": 0.002, "transit": 0.001, "hospital": 0.004,
                   "school": 0.002, "college": 0.014, "hotel": 0.002, "nightlife": 0.001,
                   "gym": 0.003, "government": 0.002, "attraction": 0.001, "park": 0.002,
                   "bus": 0.002},
    "barber":     {"resident": 0.006, "office": 0.004, "transit": 0.001, "hospital": 0.003,
                   "school": 0.003, "college": 0.008, "hotel": 0.002, "nightlife": 0.002,
                   "gym": 0.006, "government": 0.003, "attraction": 0.001, "park": 0.002,
                   "bus": 0.001},
}

POOL_LABELS = {
    "resident": "Neighbourhood residents", "office": "Office workers",
    "transit": "Transit commuters", "hospital": "Hospital staff and visitors",
    "school": "School students and parents", "college": "College students",
    "hotel": "Hotel guests", "nightlife": "Bar and nightlife traffic",
    "gym": "Gym members", "government": "Government offices",
    "attraction": "Attraction visitors", "park": "Park traffic", "bus": "Bus stop traffic",
}

SCENARIOS = {
    "Conservative": 0.76,
    "Realistic": 1.00,
    "Strong Operator": 1.26,
    "Elite Operator": 1.55,
}

SCENARIO_MEANING = {
    "Conservative": "Slow ramp, mediocre execution, or a competitor responding hard. Plan your "
                    "rent and debt so you survive at this number.",
    "Realistic": "A competent operator running the store properly with normal hours and a "
                 "normal product mix.",
    "Strong Operator": "You run it yourself, the food is good, the store is clean, hours are "
                       "long, and delivery is dialled in.",
    "Elite Operator": "Best-in-class: strong prepared food programme, real local reputation, "
                      "tight labour, full delivery coverage. Achievable but not the plan you "
                      "sign a 10-year lease on.",
}


def _capacity(concept, cfg, sqft, hours_mult, inputs):
    """How many transactions this store can physically serve in a day.

    Registers scale with floor area, and each register clears a realistic
    blended number of customers per open hour once peaks and dead hours are
    averaged together. This is what stops a location surrounded by demand from
    modeling to a number no deli has ever rung.
    """
    per_register_hour = {
        "deli": 16, "deli_24h": 15, "convenience": 14, "gourmet_market": 13,
        "supermarket": 18, "cafe": 26, "fast_casual": 20, "restaurant": 6,
        "smoke_shop": 14, "pharmacy": 12, "laundromat": 5, "barber": 2.2,
    }.get(concept, 15)
    sqft_per_register = {
        "deli": 750, "deli_24h": 750, "convenience": 700, "gourmet_market": 900,
        "supermarket": 1800, "cafe": 550, "fast_casual": 700, "restaurant": 900,
        "smoke_shop": 450, "pharmacy": 1100, "laundromat": 1200, "barber": 220,
    }.get(concept, 750)

    registers = max(1.0, sqft / sqft_per_register)
    hours_per_day = _hours_per_week(inputs.get("hours"), concept) / 7.0
    max_daily = registers * hours_per_day * per_register_hour

    return {
        "registers": round(registers, 1),
        "hours_per_day": round(hours_per_day, 1),
        "per_register_hour": per_register_hour,
        "max_daily": max(60.0, max_daily),
        "note": (f"About {registers:.1f} service positions in {int(sqft):,} sq ft, open "
                 f"{hours_per_day:.0f} hours a day, each clearing roughly {per_register_hour} "
                 "customers an hour once peaks and dead hours are averaged. That caps this store "
                 f"at roughly {max(60.0, max_daily):,.0f} transactions a day no matter how much "
                 "demand walks past."),
    }


def build(concept, inputs, gen_strength, demographics, comp_summary, block, dayparts,
          delivery_score, calibration=(1.0, 0)):
    cfg = CONCEPTS.get(concept, CONCEPTS["deli"])
    capture = CAPTURE.get(concept, CAPTURE["deli"])

    # ---------------------------------------------------------- pool sizes
    pools = {}

    residents = _resident_pool(demographics, block)
    pools["resident"] = residents

    for gen, full in POOL_SIZE_AT_FULL.items():
        s = gen_strength.get(gen, 0)
        if s <= 0:
            continue
        pools[gen] = {"size": int(full * (s / 100.0)),
                      "basis": f"Modeled from mapped {gen} generators nearby (strength {s}/100)."}

    # ------------------------------------------------- competitive share factor
    pressure = comp_summary.get("pressure", 0)
    share_factor = 3.0 / (3.0 + pressure)

    # A weak incumbent field means you take more than the raw count implies.
    avg_rating = comp_summary.get("avg_rating")
    if avg_rating:
        share_factor *= max(0.82, min(1.22, 1 + (4.2 - avg_rating) * 0.16))

    # ---------------------------------------------------------- transactions
    lines = []
    total_tx = 0.0
    for key, pool in pools.items():
        rate = capture.get(key, 0)
        if rate <= 0 or not pool["size"]:
            continue
        tx = pool["size"] * rate * share_factor
        if tx < 0.5:
            continue
        total_tx += tx
        lines.append({
            "pool": key,
            "label": POOL_LABELS.get(key, key.title()),
            "pool_size": pool["size"],
            "capture_pct": round(rate * 100, 2),
            "effective_pct": round(rate * share_factor * 100, 2),
            "transactions": round(tx, 1),
            "basis": pool["basis"],
        })
    lines.sort(key=lambda x: -x["transactions"])

    # ----------------------------------------------------------- modifiers
    modifiers = []

    sqft = inputs.get("sqft") or cfg["default_sqft"]
    size_mult = min(1.30, max(0.78, (sqft / cfg["default_sqft"]) ** 0.28))
    modifiers.append(_mod("Store size", size_mult,
                          f"{int(sqft):,} sq ft vs a {cfg['default_sqft']:,} sq ft typical store "
                          f"for this concept. Bigger helps, but not proportionally."))

    hours_mult, hours_desc = _hours_multiplier(concept, inputs.get("hours"), dayparts)
    modifiers.append(_mod("Operating hours", hours_mult, hours_desc))

    corner_mult = 1.07 if block.get("is_corner") else 1.0
    modifiers.append(_mod("Corner position", corner_mult,
                          "Corner locations get two sidewalks of exposure and better visibility."
                          if block.get("is_corner") else
                          "Mid-block position. No corner exposure premium."))

    cont_count = block.get("storefront_count", 0)
    if cont_count >= 20:
        cont_mult, cont_desc = 1.09, "Continuous retail strip - people already walk this block to shop."
    elif cont_count >= 10:
        cont_mult, cont_desc = 1.03, "Active retail block with steady storefront presence."
    elif cont_count >= 4:
        cont_mult, cont_desc = 0.96, "Patchy retail. Less browsing traffic passing your door."
    else:
        cont_mult, cont_desc = 0.86, ("Very few adjacent storefronts. You will be a destination, "
                                      "not an impulse stop. This is a real drag on walk-in volume.")
    modifiers.append(_mod("Retail continuity", cont_mult, cont_desc))

    income = demographics["facts"]["median_income"].value
    if income:
        inc_mult = min(1.16, max(0.88, 0.88 + (income - 45000) / 420000))
        modifiers.append(_mod("Local income", inc_mult,
                              f"Median household income {income:,} in the Census tract affects "
                              "basket size more than visit count."))

    transit_share = demographics.get("transit_commute_share")
    if transit_share is not None and getattr(transit_share, "value", None):
        ts = transit_share.value
        ts_mult = min(1.12, max(0.94, 0.94 + (ts - 0.45) * 0.4))
        modifiers.append(_mod("Walk / transit commuting", ts_mult,
                              f"{ts * 100:.0f}% of local workers commute by transit or on foot - "
                              "they pass storefronts instead of driving past them."))

    mult = 1.0
    for m in modifiers:
        mult *= m["multiplier"]

    cal_factor, cal_n = calibration
    if cal_n:
        modifiers.append(_mod("Your own store calibration", cal_factor,
                              f"Adjusted using {cal_n} of your actual store"
                              f"{'s' if cal_n > 1 else ''} where you entered real sales."))
        mult *= cal_factor

    walkin_tx_raw = total_tx * mult

    # ------------------------------------------------- physical capacity
    # A store cannot serve infinite people. One counter, a finite number of
    # registers and a finite grill cap what any location can ring in a day.
    # Demand above capacity is lost to the queue, not banked.
    capacity = _capacity(concept, cfg, sqft, hours_mult, inputs)
    walkin_tx = capacity["max_daily"] * (1 - math.exp(-walkin_tx_raw / capacity["max_daily"]))
    capacity["raw_demand"] = round(walkin_tx_raw)
    capacity["served"] = round(walkin_tx)
    capacity["utilisation"] = round(100 * walkin_tx / capacity["max_daily"])
    capacity["constrained"] = walkin_tx_raw > capacity["max_daily"] * 0.7

    ticket = cfg["ticket"]
    walkin_sales = walkin_tx * ticket

    # ------------------------------------------------------------- delivery
    delivery = _delivery(concept, cfg, delivery_score, demographics, share_factor, inputs)
    realistic = walkin_sales + delivery["daily_sales"]

    # Sanity floor: any operating store in NYC does some volume.
    realistic = max(realistic, 380 if concept in ("barber", "smoke_shop", "laundromat") else 750)

    scenarios = {}
    for name, factor in SCENARIOS.items():
        daily = realistic * factor
        scenarios[name] = {
            "daily": int(round(daily / 25) * 25),
            "weekly": int(round(daily * 7 / 100) * 100),
            "monthly": int(round(daily * 30.4 / 500) * 500),
            "annual": int(round(daily * 365 / 1000) * 1000),
            "meaning": SCENARIO_MEANING[name],
            "factor": factor,
        }

    drivers = _drivers(lines, modifiers, share_factor, comp_summary, delivery)
    if capacity["constrained"]:
        drivers["down"].insert(0, {
            "factor": "Physical store capacity",
            "effect": f"caps sales at ~{capacity['max_daily']:,.0f} transactions/day",
            "detail": capacity["note"] + " Demand above that is lost to the queue. A bigger "
                      "space, more registers or longer hours is the only way to sell more here.",
        })

    return {
        "scenarios": scenarios,
        "realistic_daily": scenarios["Realistic"]["daily"],
        "transaction_lines": lines,
        "base_transactions": round(total_tx, 1),
        "adjusted_transactions": round(walkin_tx, 1),
        "capacity": capacity,
        "ticket": ticket,
        "share_factor": round(share_factor, 3),
        "competitive_note": (
            f"Competitive pressure index {pressure} within a quarter mile reduces raw capture to "
            f"{share_factor * 100:.0f}% of its uncontested level."),
        "modifiers": modifiers,
        "total_modifier": round(mult, 3),
        "delivery": delivery,
        "drivers_up": drivers["up"],
        "drivers_down": drivers["down"],
        "calibrated": bool(cal_n),
        "calibration_n": cal_n,
        "evidence": MODELED,
        "disclaimer": ("ESTIMATE. Every figure above is modeled from public data, not measured "
                       "sales. Pool sizes are approximations. Treat the Conservative case as your "
                       "planning number and verify with the seller's actual register tapes, "
                       "supplier invoices and sales tax filings before you sign anything."),
    }


def _mod(name, multiplier, note):
    return {"name": name, "multiplier": round(multiplier, 3),
            "effect_pct": round((multiplier - 1) * 100, 1), "note": note}


def _resident_pool(demographics, block):
    """Residents within capture range, cross-checked between Census and PLUTO."""
    est = demographics.get("radius_estimates", {}).get(0.25)
    census_pop = est.value if est is not None and getattr(est, "known", False) else None

    pluto = block.get("building") or {}
    hh_size = demographics["facts"]["avg_household_size"].value or 2.3
    pluto_pop = None
    if pluto.get("available") and pluto.get("residential_units"):
        # PLUTO radius is small (about 0.05 mi); scale to 0.25 mi by area ratio,
        # damped because density falls off away from the corridor.
        ratio = (0.25 / max(0.01, pluto.get("radius_mi", 0.05))) ** 2
        pluto_pop = pluto["residential_units"] * hh_size * min(ratio, 18) * 0.55

    if census_pop and pluto_pop:
        size = int((census_pop * 0.6) + (pluto_pop * 0.4))
        basis = ("Blend of Census tract density projected to a 0.25 mi circle and NYC PLUTO "
                 "residential unit counts on the surrounding lots.")
    elif census_pop:
        size = int(census_pop)
        basis = "Census tract density projected to a 0.25 mi circle. Estimate, not a count."
    elif pluto_pop:
        size = int(pluto_pop)
        basis = "Derived from NYC PLUTO residential unit counts on surrounding tax lots."
    else:
        size = 0
        basis = "No residential population data available for this location."
    return {"size": size, "basis": basis}


def _hours_multiplier(concept, hours_text, dayparts):
    late = dayparts["summary"]["Late Night"]["score"]
    text = (hours_text or "").lower()
    if "24" in text:
        return (1.0 + late / 420.0,
                f"Open 24 hours. Modeled late-night demand here scores {late}/100, and staying "
                "open captures it. Overnight is also where a deli earns its highest margins.")
    if concept == "deli_24h":
        return (1.0 + late / 420.0,
                f"24-hour concept. Late-night demand scores {late}/100 in the model.")
    if late > 55:
        return (0.93, f"Late-night demand scores {late}/100 but your planned hours do not cover "
                      "it. You are leaving a real daypart to whoever stays open.")
    return (1.0, "Standard hours cover the dayparts that carry demand at this location.")


def _delivery(concept, cfg, delivery_score, demographics, share_factor, inputs):
    """Delivery is modeled separately because its economics are different -
    higher ticket, but a quarter of it goes to the platform."""
    if not cfg["prepared_food"] and concept not in ("convenience", "gourmet_market"):
        return {"applicable": False, "daily_orders": 0, "daily_sales": 0,
                "note": "Third-party delivery is not a meaningful channel for this concept."}

    density = demographics["facts"]["density_sq_mi"].value or 0
    base = (delivery_score / 100.0) * 55 * share_factor
    base *= min(1.5, max(0.5, density / 45000)) if density else 0.8
    orders = max(0, base)
    ticket = cfg["ticket"] * (1.55 if cfg["prepared_food"] else 1.35)
    gross = orders * ticket
    commission = inputs.get("delivery_commission") or DELIVERY_COMMISSION

    return {
        "applicable": True,
        "daily_orders": round(orders),
        "delivery_ticket": round(ticket, 2),
        "daily_sales": round(gross),
        "monthly_sales": round(gross * 30.4),
        "commission_rate": commission,
        "monthly_commission": round(gross * 30.4 * commission),
        "monthly_net": round(gross * 30.4 * (1 - commission)),
        "score": delivery_score,
        "note": (f"Modeled at {round(orders)} orders/day at roughly ${ticket:.2f} each. "
                 f"At {commission * 100:.1f}% blended platform commission you keep about "
                 f"${gross * 30.4 * (1 - commission):,.0f}/month of ${gross * 30.4:,.0f} in "
                 "delivery gross. Commission is the difference between delivery being growth "
                 "and delivery being volume you pay for."),
    }


def _drivers(lines, modifiers, share_factor, comp_summary, delivery):
    up, down = [], []
    total = sum(l["transactions"] for l in lines) or 1
    for l in lines[:4]:
        pct = l["transactions"] / total * 100
        if pct >= 8:
            up.append({"factor": l["label"],
                       "effect": f"+{pct:.0f}% of modeled walk-in volume",
                       "detail": l["basis"]})
    if delivery.get("applicable") and delivery.get("daily_orders", 0) > 8:
        up.append({"factor": "Delivery channel",
                   "effect": f"+${delivery['daily_sales']:,}/day modeled",
                   "detail": delivery["note"]})

    for m in modifiers:
        if m["effect_pct"] >= 3:
            up.append({"factor": m["name"], "effect": f"+{m['effect_pct']:.0f}%", "detail": m["note"]})
        elif m["effect_pct"] <= -3:
            down.append({"factor": m["name"], "effect": f"{m['effect_pct']:.0f}%", "detail": m["note"]})

    if share_factor < 0.55:
        down.append({
            "factor": "Competitive pressure",
            "effect": f"-{(1 - share_factor) * 100:.0f}% vs an uncontested location",
            "detail": (f"{comp_summary.get('direct_count', 0)} direct competitors and "
                       f"{comp_summary.get('within_block', 0)} businesses within a block are "
                       "splitting the same customer pool."),
        })
    strongest = comp_summary.get("strongest")
    if strongest and strongest.get("threat") in ("HIGH", "VERY HIGH"):
        down.append({"factor": f"Incumbent: {strongest['name']}",
                     "effect": f"{strongest['threat']} threat",
                     "detail": strongest.get("why", "")})

    return {"up": up[:7], "down": down[:7]}


# --------------------------------------------------------------------- P&L
def pnl(concept, scenarios, inputs, rent_info, delivery):
    """Monthly operating P&L for each scenario. This is the section that decides
    whether a location is a business or an expensive hobby."""
    cfg = CONCEPTS.get(concept, CONCEPTS["deli"])
    rent = rent_info["monthly_rent"]
    fixed = FIXED_MONTHLY.get(concept, 4000)
    hours_per_week = _hours_per_week(inputs.get("hours"), concept)
    wage = inputs.get("wage") or 18.5
    staff = 1.7 if concept in ("deli", "deli_24h", "gourmet_market", "restaurant") else 1.25
    labour_floor = hours_per_week * 4.33 * wage * staff

    out = {}
    for name, s in scenarios.items():
        revenue = s["monthly"]
        delivery_rev = min(revenue * 0.45, delivery.get("monthly_sales", 0) * s["factor"]) if delivery.get("applicable") else 0
        instore_rev = revenue - delivery_rev

        cogs = revenue * (1 - cfg["gross_margin"])
        labour = max(labour_floor, revenue * cfg["labor_pct"])
        commission = delivery_rev * (delivery.get("commission_rate") or DELIVERY_COMMISSION)
        card = instore_rev * CARD_SHARE * CARD_FEE
        total_costs = cogs + labour + commission + card + rent + fixed
        profit = revenue - total_costs

        out[name] = {
            "revenue": int(revenue),
            "delivery_revenue": int(delivery_rev),
            "cogs": int(cogs),
            "cogs_pct": round(100 * cogs / revenue, 1) if revenue else 0,
            "labour": int(labour),
            "labour_pct": round(100 * labour / revenue, 1) if revenue else 0,
            "labour_at_floor": labour <= labour_floor + 1,
            "delivery_commission": int(commission),
            "card_fees": int(card),
            "rent": int(rent),
            "rent_pct": round(100 * rent / revenue, 1) if revenue else 0,
            "fixed": int(fixed),
            "profit": int(profit),
            "margin_pct": round(100 * profit / revenue, 1) if revenue else 0,
            "annual_profit": int(profit * 12),
        }

    breakeven = _breakeven(cfg, rent, fixed, labour_floor, delivery)
    return {
        "by_scenario": out,
        "labour_floor": int(labour_floor),
        "hours_per_week": hours_per_week,
        "wage_assumption": wage,
        "breakeven_daily": breakeven,
        "assumptions": [
            f"Gross margin {cfg['gross_margin'] * 100:.0f}% (MODELED for {cfg['label']}).",
            f"Labour the greater of {cfg['labor_pct'] * 100:.0f}% of sales or "
            f"${labour_floor:,.0f}/month to physically cover {hours_per_week} hours a week "
            f"at ${wage:.2f}/hr.",
            f"Third-party delivery commission {(delivery.get('commission_rate') or DELIVERY_COMMISSION) * 100:.1f}% "
            "on delivery revenue only.",
            f"Card processing {CARD_FEE * 100:.1f}% on {CARD_SHARE * 100:.0f}% of in-store sales.",
            f"Other fixed costs ${fixed:,}/month: utilities, insurance, permits, alarm, "
            "waste, repairs, accounting, POS.",
            "Excludes debt service, buildout amortisation, owner salary and taxes.",
        ],
        "evidence": MODELED,
    }


def _hours_per_week(hours_text, concept):
    text = (hours_text or "").lower()
    if "24" in text or concept == "deli_24h":
        return 168
    cfg = CONCEPTS.get(concept, CONCEPTS["deli"])
    default = cfg["hours_default"]
    try:
        start, end = default.replace("am", "").replace("pm", "").split("-")
        span = 12  # fallback
    except ValueError:
        span = 14
    spans = {"deli": 17, "convenience": 16, "gourmet_market": 15, "supermarket": 15,
             "cafe": 13, "fast_casual": 12, "restaurant": 12, "smoke_shop": 14,
             "pharmacy": 13, "laundromat": 15, "barber": 11}
    return spans.get(concept, 14) * 7


def _breakeven(cfg, rent, fixed, labour_floor, delivery):
    """Daily sales needed to cover costs, solving for the labour floor."""
    gm = cfg["gross_margin"]
    variable = (1 - gm) + cfg["labor_pct"] + CARD_SHARE * CARD_FEE
    fixed_total = rent + fixed
    if variable >= 1:
        return None
    monthly_pct = fixed_total / (1 - variable)
    variable_floor = (1 - gm) + CARD_SHARE * CARD_FEE
    monthly_floor = (fixed_total + labour_floor) / (1 - variable_floor)
    monthly = max(monthly_pct, monthly_floor)
    return int(round(monthly / 30.4 / 25) * 25)
