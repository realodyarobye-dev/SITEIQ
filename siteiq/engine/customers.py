"""Customer profile.

Ranks the customer groups likely to actually walk through the door, based on the
demand generators and demographics present, and says what each group buys and
what they are worth. Modeled, and labelled as such.
"""
from ..core.provenance import INFERRED

GROUPS = {
    "residents": {
        "label": "Neighbourhood residents",
        "buys": "Milk, eggs, bread, coffee, sandwiches, beer, cigarettes, household basics. "
                "The daily-repeat customer who decides whether you survive.",
        "value": "Highest lifetime value. Lower ticket, highest frequency.",
    },
    "office_workers": {
        "label": "Office workers",
        "buys": "Breakfast sandwiches and coffee 7-9:30am, lunch 11:30am-2pm, energy drinks and "
                "snacks all afternoon. Best ticket in the store on weekdays.",
        "value": "High value Monday-Friday. Disappears entirely on weekends and holidays.",
    },
    "students": {
        "label": "Students",
        "buys": "Chips, candy, soda, energy drinks, cheap heroes, chopped cheese. High volume, "
                "low ticket, heavy at 7:45am and 3pm.",
        "value": "Medium value. Volume without margin unless you push prepared food.",
    },
    "hospital_staff": {
        "label": "Hospital and clinic staff",
        "buys": "Coffee, prepared food, grab-and-go meals at shift changes including overnight. "
                "They spend real money and come back every single shift.",
        "value": "Very high value if you are open when their shift ends.",
    },
    "patients_visitors": {
        "label": "Patients and hospital visitors",
        "buys": "Water, snacks, flowers, cards, phone chargers, quick meals during long waits.",
        "value": "Medium value, low frequency, price-insensitive.",
    },
    "commuters": {
        "label": "Transit commuters",
        "buys": "Coffee, breakfast sandwich, gum, water, lottery, phone top-ups. Speed is the "
                "entire product - they will not wait behind three people.",
        "value": "High value at peak hours. You must be fast or you lose them permanently.",
    },
    "tourists": {
        "label": "Tourists and hotel guests",
        "buys": "Water, snacks, souvenirs, beer, umbrellas, phone chargers. No price resistance.",
        "value": "High margin, seasonal, unpredictable.",
    },
    "nightlife": {
        "label": "Nightlife customers",
        "buys": "Late-night food, cigarettes, drinks, aspirin. Thursday-Saturday 11pm-3am.",
        "value": "High margin but concentrated in three nights and needs overnight staffing.",
    },
    "construction": {
        "label": "Construction crews",
        "buys": "Big breakfast orders 6-7am, bulk coffee, hero sandwiches at noon, Gatorade. "
                "They buy for the whole crew - the biggest single tickets you will ring.",
        "value": "Very high value while the job runs. Temporary by definition.",
    },
    "delivery": {
        "label": "Delivery customers",
        "buys": "Whatever your menu offers, ordered from apartments within about a mile.",
        "value": "Real volume, but platform commission takes roughly a quarter of it.",
    },
    "families": {
        "label": "Families",
        "buys": "Groceries, snacks, prepared dinners, weekend items. Larger baskets.",
        "value": "Good ticket, weekend-weighted.",
    },
    "affluent": {
        "label": "High-income residents",
        "buys": "Premium coffee, prepared foods, imported goods, organic produce, wine. "
                "They will pay more for quality and presentation.",
        "value": "Best margin available if the store looks and smells right.",
    },
    "gym_goers": {
        "label": "Gym members",
        "buys": "Protein drinks, bars, water, salads, smoothies. Early morning and 6-8pm.",
        "value": "Medium value, very habitual.",
    },
    "government_workers": {
        "label": "Government / municipal workers",
        "buys": "Coffee, lunch, snacks on a strict weekday schedule.",
        "value": "Medium-high value, extremely predictable.",
    },
}


def build(concept, gen_strength, demographics, block, delivery_score):
    s = gen_strength
    dem = demographics
    scores = {}

    density = dem["facts"]["density_sq_mi"].value or 0
    income = dem["facts"]["median_income"].value or 0
    med_age = dem["facts"]["median_age"].value or 0
    units = (block.get("building") or {}).get("residential_units") or 0

    scores["residents"] = min(100, 25 + density / 900 + units / 30)
    scores["office_workers"] = min(100, s.get("office", 0) * 0.95 + s.get("government", 0) * 0.3)
    scores["students"] = min(100, s.get("school", 0) * 0.75 + s.get("college", 0) * 0.9)
    scores["hospital_staff"] = min(100, s.get("hospital", 0) * 1.0)
    scores["patients_visitors"] = min(100, s.get("hospital", 0) * 0.6)
    scores["commuters"] = min(100, s.get("transit", 0) * 0.95 + s.get("bus", 0) * 0.4)
    scores["tourists"] = min(100, s.get("hotel", 0) * 0.85 + s.get("attraction", 0) * 0.7)
    scores["nightlife"] = min(100, s.get("nightlife", 0) * 0.95)
    scores["construction"] = min(100, (block.get("construction_count") or 0) * 6)
    scores["delivery"] = min(100, delivery_score)
    scores["families"] = min(100, (density / 1400) + (35 if 33 <= med_age <= 45 else 10))
    scores["affluent"] = min(100, max(0, (income - 85000) / 900)) if income else 0
    scores["gym_goers"] = min(100, s.get("gym", 0) * 0.85)
    scores["government_workers"] = min(100, s.get("government", 0) * 0.8)

    ranked = []
    for key, score in sorted(scores.items(), key=lambda kv: -kv[1]):
        if score < 12:
            continue
        meta = GROUPS[key]
        ranked.append({
            "key": key,
            "label": meta["label"],
            "score": round(score),
            "tier": _tier(score),
            "buys": meta["buys"],
            "value": meta["value"],
        })

    concentration = _concentration([r["score"] for r in ranked])
    return {
        "ranked": ranked[:9],
        "all_scores": {k: round(v) for k, v in scores.items()},
        "concentration": concentration,
        "evidence": INFERRED,
        "method": ("Modeled from mapped demand generators and Census tract measures. "
                   "These are the groups most likely to walk in, not a survey of who does."),
    }


def _tier(score):
    if score >= 70:
        return "HIGH VALUE"
    if score >= 45:
        return "MEDIUM VALUE"
    return "SECONDARY"


def _concentration(scores):
    """How dependent the site is on a single customer group."""
    if not scores:
        return {"level": "UNKNOWN", "note": "Not enough signal to judge customer mix."}
    top = scores[0]
    rest = sum(scores[1:4])
    if rest == 0 or top / max(1, rest) > 1.3:
        return {"level": "CONCENTRATED",
                "note": "One customer group dominates. If that group's routine changes - a school "
                        "calendar, an office lease, a construction job ending - your sales move with it."}
    if len(scores) >= 4 and scores[3] > 40:
        return {"level": "DIVERSIFIED",
                "note": "Several independent customer groups. This is what lets a store hold up "
                        "through seasons, holidays and weekends."}
    return {"level": "MODERATE",
            "note": "A workable mix, though two or three groups carry most of the volume."}
