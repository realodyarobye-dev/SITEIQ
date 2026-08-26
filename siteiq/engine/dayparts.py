"""Daypart intelligence.

These are MODELED scores, built from which demand generators sit nearby and how
those crowds behave. They are not measured foot traffic and the app says so
everywhere they appear. SiteIQ has no foot-traffic feed; pretending otherwise
would be the exact failure mode this product exists to avoid.
"""
from ..core.provenance import MODELED

WINDOWS = [
    ("6-9 AM", "early_am"),
    ("9-11 AM", "mid_am"),
    ("11 AM-2 PM", "lunch"),
    ("2-5 PM", "afternoon"),
    ("5-8 PM", "evening"),
    ("8-11 PM", "night"),
    ("11 PM-3 AM", "late_night"),
    ("3-6 AM", "overnight"),
]

# generator -> contribution to each window, weekday
WEEKDAY = {
    "transit":     {"early_am": 34, "mid_am": 10, "lunch": 12, "afternoon": 10, "evening": 30, "night": 9, "late_night": 4, "overnight": 2},
    "bus":         {"early_am": 14, "mid_am": 6, "lunch": 7, "afternoon": 8, "evening": 13, "night": 5, "late_night": 2, "overnight": 1},
    "office":      {"early_am": 26, "mid_am": 14, "lunch": 40, "afternoon": 16, "evening": 12, "night": 2, "late_night": 0, "overnight": 0},
    "school":      {"early_am": 26, "mid_am": 4, "lunch": 12, "afternoon": 30, "evening": 5, "night": 1, "late_night": 0, "overnight": 0},
    "college":     {"early_am": 10, "mid_am": 16, "lunch": 24, "afternoon": 20, "evening": 20, "night": 20, "late_night": 14, "overnight": 3},
    "hospital":    {"early_am": 22, "mid_am": 14, "lunch": 22, "afternoon": 16, "evening": 20, "night": 16, "late_night": 16, "overnight": 18},
    "hotel":       {"early_am": 16, "mid_am": 10, "lunch": 12, "afternoon": 10, "evening": 16, "night": 16, "late_night": 12, "overnight": 5},
    "nightlife":   {"early_am": 0, "mid_am": 0, "lunch": 3, "afternoon": 4, "evening": 16, "night": 30, "late_night": 38, "overnight": 12},
    "gym":         {"early_am": 18, "mid_am": 8, "lunch": 8, "afternoon": 8, "evening": 22, "night": 8, "late_night": 2, "overnight": 1},
    "government":  {"early_am": 14, "mid_am": 14, "lunch": 26, "afternoon": 14, "evening": 5, "night": 1, "late_night": 0, "overnight": 0},
    "attraction":  {"early_am": 4, "mid_am": 14, "lunch": 20, "afternoon": 20, "evening": 16, "night": 10, "late_night": 4, "overnight": 0},
    "park":        {"early_am": 8, "mid_am": 10, "lunch": 12, "afternoon": 16, "evening": 14, "night": 5, "late_night": 1, "overnight": 0},
    "residential": {"early_am": 16, "mid_am": 10, "lunch": 12, "afternoon": 14, "evening": 26, "night": 20, "late_night": 8, "overnight": 3},
}

# Weekend behaves very differently: no office, no school, more park/nightlife.
WEEKEND_MULT = {
    "transit": 0.55, "bus": 0.5, "office": 0.12, "school": 0.08, "college": 0.6,
    "hospital": 0.85, "hotel": 1.2, "nightlife": 1.35, "gym": 0.95, "government": 0.15,
    "attraction": 1.4, "park": 1.5, "residential": 1.15,
}

# Which windows a concept can actually monetise (and whether it is even open).
CONCEPT_FIT = {
    "deli":        {"early_am": 1.15, "mid_am": 0.9, "lunch": 1.2, "afternoon": 0.9, "evening": 1.0, "night": 0.8, "late_night": 0.5, "overnight": 0.2},
    "deli_24h":    {"early_am": 1.15, "mid_am": 0.9, "lunch": 1.15, "afternoon": 0.9, "evening": 1.0, "night": 1.0, "late_night": 1.15, "overnight": 1.0},
    "convenience": {"early_am": 1.0, "mid_am": 0.9, "lunch": 1.0, "afternoon": 1.0, "evening": 1.1, "night": 0.9, "late_night": 0.5, "overnight": 0.2},
    "gourmet_market": {"early_am": 0.8, "mid_am": 1.0, "lunch": 1.2, "afternoon": 1.0, "evening": 1.2, "night": 0.6, "late_night": 0.15, "overnight": 0.05},
    "supermarket": {"early_am": 0.5, "mid_am": 1.0, "lunch": 0.9, "afternoon": 1.1, "evening": 1.25, "night": 0.7, "late_night": 0.2, "overnight": 0.05},
    "cafe":        {"early_am": 1.5, "mid_am": 1.2, "lunch": 1.0, "afternoon": 0.8, "evening": 0.4, "night": 0.15, "late_night": 0.05, "overnight": 0.0},
    "fast_casual": {"early_am": 0.5, "mid_am": 0.7, "lunch": 1.6, "afternoon": 0.8, "evening": 1.2, "night": 0.7, "late_night": 0.3, "overnight": 0.05},
    "restaurant":  {"early_am": 0.15, "mid_am": 0.3, "lunch": 1.2, "afternoon": 0.6, "evening": 1.6, "night": 1.1, "late_night": 0.4, "overnight": 0.05},
    "smoke_shop":  {"early_am": 0.4, "mid_am": 0.8, "lunch": 1.0, "afternoon": 1.1, "evening": 1.2, "night": 1.2, "late_night": 0.8, "overnight": 0.1},
    "pharmacy":    {"early_am": 0.6, "mid_am": 1.2, "lunch": 1.1, "afternoon": 1.2, "evening": 1.1, "night": 0.5, "late_night": 0.1, "overnight": 0.05},
    "laundromat":  {"early_am": 0.7, "mid_am": 1.1, "lunch": 0.9, "afternoon": 1.0, "evening": 1.2, "night": 0.7, "late_night": 0.2, "overnight": 0.05},
    "barber":      {"early_am": 0.2, "mid_am": 1.0, "lunch": 1.0, "afternoon": 1.1, "evening": 1.2, "night": 0.5, "late_night": 0.05, "overnight": 0.0},
}

SUMMARY_MAP = {
    "Morning": ["early_am", "mid_am"],
    "Lunch": ["lunch"],
    "Afternoon": ["afternoon"],
    "Dinner": ["evening"],
    "Late Night": ["night", "late_night", "overnight"],
}

DRIVERS = {
    "transit": "commuter flow from nearby transit",
    "bus": "bus stop waiting traffic",
    "office": "office workers",
    "school": "school drop-off and dismissal",
    "college": "students",
    "hospital": "hospital shift changes",
    "hotel": "hotel guests",
    "nightlife": "bar and club traffic",
    "gym": "gym members",
    "government": "government office staff",
    "attraction": "visitors to nearby attractions",
    "park": "park traffic",
    "residential": "residents in the surrounding buildings",
}


def build(concept, gen_strength, residential_base=0):
    fit = CONCEPT_FIT.get(concept, CONCEPT_FIT["deli"])
    strength = dict(gen_strength)
    strength["residential"] = max(strength.get("residential", 0), residential_base)

    weekday, weekend, drivers = {}, {}, {}
    for _, key in WINDOWS:
        wd = wk = 0.0
        contrib = []
        for gen, profile in WEEKDAY.items():
            s = strength.get(gen, 0)
            if s <= 0:
                continue
            base = (s / 100.0) * profile[key]
            wd += base
            wk += base * WEEKEND_MULT.get(gen, 1.0)
            if base > 1.5:
                contrib.append((base, gen))
        f = fit[key]
        weekday[key] = round(min(100, wd * f * 1.35))
        weekend[key] = round(min(100, wk * f * 1.35))
        contrib.sort(reverse=True)
        drivers[key] = [DRIVERS[g] for _, g in contrib[:3]]

    windows = []
    for label, key in WINDOWS:
        wd, wk = weekday[key], weekend[key]
        windows.append({
            "label": label, "key": key,
            "weekday": wd, "weekend": wk,
            "score": round(wd * 5 / 7 + wk * 2 / 7),
            "drivers": drivers[key],
            "note": _note(label, wd, wk, drivers[key], concept, key),
        })

    summary = {}
    for name, keys in SUMMARY_MAP.items():
        wd = round(sum(weekday[k] for k in keys) / len(keys))
        wk = round(sum(weekend[k] for k in keys) / len(keys))
        summary[name] = {"weekday": wd, "weekend": wk,
                         "score": round(wd * 5 / 7 + wk * 2 / 7)}

    peak = max(windows, key=lambda w: w["weekday"])
    trough = min(windows, key=lambda w: w["weekday"])
    overall = round(sum(w["score"] for w in windows) / len(windows))
    spread = max(w["score"] for w in windows) - min(w["score"] for w in windows)

    return {
        "windows": windows,
        "summary": summary,
        "overall": overall,
        "peak": peak,
        "trough": trough,
        "spread": spread,
        "shape": _shape(summary, spread),
        "evidence": MODELED,
        "disclaimer": ("MODELED, not measured. SiteIQ has no pedestrian counter. These scores "
                       "come from the mix of demand generators nearby and how those crowds "
                       "typically behave. Verify by standing on the corner and counting."),
    }


def _note(label, wd, wk, drivers, concept, key):
    if wd < 12 and wk < 12:
        return f"Little modeled demand in {label}. Staffing this window may cost more than it returns."
    src = ", ".join(drivers) if drivers else "general neighbourhood activity"
    base = f"Demand in {label} comes mainly from {src}."
    if wk > wd * 1.3:
        base += " Notably stronger on weekends."
    elif wd > wk * 1.5:
        base += " Weekday-driven; expect this window to go quiet Saturday and Sunday."
    if key in ("late_night", "overnight") and wd > 40 and concept not in ("deli_24h",):
        base += " There is modeled overnight demand here that your planned hours would not capture."
    return base


def _shape(summary, spread):
    ranked = sorted(summary.items(), key=lambda kv: -kv[1]["score"])
    top = ranked[0][0]
    if spread > 55:
        return (f"Spiky, {top}-dominated",
                f"Sales will be concentrated in {top.lower()}. Staffing and prep must be built "
                "around that peak, and the slow hours will feel painful.")
    if spread < 25:
        return ("Flat all-day trade",
                "Demand is spread across the day. Easier to staff, steadier cash, less dependent "
                "on any one crowd.")
    return (f"Balanced with a {top.lower()} peak",
            f"A normal street-retail pattern with {top.lower()} carrying the day.")
