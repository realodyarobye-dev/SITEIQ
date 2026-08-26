"""Rent.

There is no free public feed of NYC ground-floor retail asking rents. So when
the operator has not entered a rent, SiteIQ produces a deliberately wide modeled
band from the signals it does have, labels it clearly as a guess, and pushes
hard for the real number. A precise-looking fake rent would corrupt every
downstream profit figure in the report.
"""
from ..config import CONCEPTS
from ..core.provenance import MODELED, USER

# Very rough ground-floor asking rent bands, $/sq ft/year, by neighbourhood
# character. Wide on purpose.
BANDS = [
    (140000, 40000, (180, 420), "Prime high-income, high-density corridor"),
    (110000, 30000, (120, 300), "Strong high-income urban corridor"),
    (85000, 25000, (85, 200), "Solid middle-income dense urban"),
    (60000, 15000, (60, 145), "Working middle-income urban"),
    (0, 0, (40, 110), "Lower-density or lower-income corridor"),
]

# Occupancy cost as a share of sales - what a healthy store can carry.
HEALTHY_RENT_PCT = {
    "deli": 0.085, "deli_24h": 0.075, "convenience": 0.09, "gourmet_market": 0.09,
    "supermarket": 0.055, "cafe": 0.11, "fast_casual": 0.10, "restaurant": 0.09,
    "smoke_shop": 0.13, "pharmacy": 0.075, "laundromat": 0.13, "barber": 0.13,
}


def build(concept, inputs, demographics, generators, block):
    cfg = CONCEPTS.get(concept, CONCEPTS["deli"])
    sqft = inputs.get("sqft") or cfg["default_sqft"]

    if inputs.get("rent"):
        rent = float(inputs["rent"])
        return {
            "monthly_rent": rent,
            "annual_psf": round(rent * 12 / sqft) if sqft else None,
            "sqft": sqft,
            "sqft_estimated": not inputs.get("sqft"),
            "estimated": False,
            "evidence": USER,
            "source": "You entered this",
            "band": None,
            "note": f"Using your entered rent of ${rent:,.0f}/month"
                    + (f" over an assumed {sqft:,} sq ft." if not inputs.get("sqft")
                       else f" over {sqft:,} sq ft."),
        }

    income = demographics["facts"]["median_income"].value or 0
    density = demographics["facts"]["density_sq_mi"].value or 0

    low_psf, high_psf, character = 40, 110, BANDS[-1][3]
    for inc_cut, den_cut, (lo, hi), desc in BANDS:
        if income >= inc_cut and density >= den_cut:
            low_psf, high_psf, character = lo, hi, desc
            break

    # Transit and corner positions command a premium; dead blocks discount.
    pull = generators.get("total_pull", 0)
    adj = 1.0 + (pull - 40) / 260.0
    if block.get("is_corner"):
        adj *= 1.12
    if block.get("storefront_count", 0) < 5:
        adj *= 0.82
    adj = max(0.7, min(1.6, adj))

    low = low_psf * adj * sqft / 12
    high = high_psf * adj * sqft / 12
    mid = (low + high) / 2

    return {
        "monthly_rent": round(mid / 250) * 250,
        "annual_psf": round(mid * 12 / sqft) if sqft else None,
        "sqft": sqft,
        "sqft_estimated": not inputs.get("sqft"),
        "estimated": True,
        "evidence": MODELED,
        "source": "SiteIQ estimate from neighbourhood character",
        "band": {"low": int(round(low / 250) * 250), "high": int(round(high / 250) * 250),
                 "low_psf": int(low_psf * adj), "high_psf": int(high_psf * adj)},
        "note": (f"ESTIMATED rent only - you did not enter one. Modeled band is "
                 f"${round(low / 250) * 250:,.0f} to ${round(high / 250) * 250:,.0f} per month "
                 f"for an assumed {sqft:,} sq ft ({character.lower()}). This band is wide because "
                 "no free public dataset publishes NYC retail asking rents. Enter the real rent "
                 "and every profit number in this report becomes meaningful."),
    }


def assess(concept, rent_info, realistic_monthly_sales):
    """Rent as a share of sales, and whether that is survivable."""
    rent = rent_info["monthly_rent"]
    pct = rent / realistic_monthly_sales if realistic_monthly_sales else 0
    healthy = HEALTHY_RENT_PCT.get(concept, 0.09)

    if pct <= healthy * 0.75:
        band, verdict = "EXCELLENT", ("Occupancy cost is low for this concept. That is margin you "
                                      "keep and a cushion if sales disappoint.")
    elif pct <= healthy:
        band, verdict = "HEALTHY", "Occupancy cost sits inside the normal range for this concept."
    elif pct <= healthy * 1.35:
        band, verdict = "TIGHT", ("Rent is above the comfortable range. It works if you hit the "
                                  "realistic case, and hurts badly if you do not. Negotiate.")
    elif pct <= healthy * 1.9:
        band, verdict = "HIGH", ("Rent is high relative to modeled sales. This deal needs a lower "
                                 "rent, a rent-free buildout period, or higher volume than modeled.")
    else:
        band, verdict = "UNSUSTAINABLE", ("Rent would consume the business at modeled sales. Either "
                                          "the sales model is too low or this rent cannot be paid.")

    max_rent = realistic_monthly_sales * healthy
    return {
        "rent_pct": round(pct * 100, 1),
        "healthy_pct": round(healthy * 100, 1),
        "band": band,
        "verdict": verdict,
        "max_supportable_rent": int(round(max_rent / 100) * 100),
        "gap": int(round((rent - max_rent) / 100) * 100),
    }
