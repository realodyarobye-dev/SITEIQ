"""Central configuration. Everything tunable lives here or in environment variables.

No secrets are ever hard-coded. Every optional API degrades gracefully when its
key is absent.
"""
import os


def _env(name, default=""):
    return (os.getenv(name) or default).strip()


def _flag(name, default=False):
    v = _env(name).lower()
    if not v:
        return default
    return v in ("1", "true", "yes", "on")


def _int(name, default):
    try:
        return int(_env(name) or default)
    except ValueError:
        return default


# ---------------------------------------------------------------- app
APP_NAME = "SiteIQ"
APP_VERSION = "6.0"
SECRET_KEY = _env("SECRET_KEY", "siteiq-dev-key-change-me")
PORT = _int("PORT", 5000)

# Railway gives an ephemeral filesystem unless a volume is mounted at /data.
DATA_DIR = _env("SITEIQ_DATA_DIR", "/data" if os.path.isdir("/data") else os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"))
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "siteiq.db")

LOG_LEVEL = _env("LOG_LEVEL", "INFO").upper()

# ---------------------------------------------------------------- keys
GOOGLE_MAPS_API_KEY = _env("GOOGLE_MAPS_API_KEY")
NYC_APP_TOKEN = _env("NYC_APP_TOKEN")          # optional, raises Socrata rate limit
MAPBOX_TOKEN = _env("MAPBOX_TOKEN")            # optional, nicer basemap
CONTACT_EMAIL = _env("CONTACT_EMAIL", "siteiq-operator@example.com")  # Nominatim policy

HAS_GOOGLE = bool(GOOGLE_MAPS_API_KEY)

# ---------------------------------------------------------------- network
HTTP_TIMEOUT = _int("HTTP_TIMEOUT", 20)
HTTP_RETRIES = _int("HTTP_RETRIES", 2)
USER_AGENT = f"SiteIQ/{APP_VERSION} (retail site analysis; {CONTACT_EMAIL})"

CACHE_TTL = {
    "geocode": 60 * 60 * 24 * 90,
    "census": 60 * 60 * 24 * 30,
    "overpass": 60 * 60 * 24 * 14,
    "places": 60 * 60 * 24 * 7,
    "nyc": 60 * 60 * 24 * 14,
    "streetview": 60 * 60 * 24 * 30,
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://overpass.osm.ch/api/interpreter",
]

# NYC Open Data (Socrata) dataset identifiers. Overridable if NYC re-publishes.
NYC_DATASETS = {
    "restaurant_inspections": _env("NYC_DS_INSPECTIONS", "43nn-pn8j"),
    "legal_businesses": _env("NYC_DS_BUSINESSES", "w7w3-xahh"),
    "dob_permits": _env("NYC_DS_PERMITS", "ipu4-2q9a"),
    "pluto": _env("NYC_DS_PLUTO", "64uk-42ks"),
}
NYC_SOCRATA_HOST = "https://data.cityofnewyork.us"

# ---------------------------------------------------------------- radii
RADII_MILES = [0.05, 0.1, 0.25, 0.5, 1.0]
RADIUS_LABELS = {
    0.05: "Immediate block",
    0.1: "0.1 mile",
    0.25: "0.25 mile",
    0.5: "0.5 mile",
    1.0: "1 mile",
}
SEARCH_RADIUS_M = 1610  # 1 mile, the widest pull we make

# ---------------------------------------------------------------- concepts
# Operator-grade economics. Ticket and margin figures are NYC street-retail
# planning assumptions, not measurements — they are labelled MODELED everywhere.
CONCEPTS = {
    "deli": {
        "label": "Deli / Bodega",
        "google_types": ["convenience_store", "deli", "sandwich_shop", "grocery_store"],
        "osm_direct": ["convenience", "deli", "grocery"],
        "osm_partial": ["fast_food", "cafe", "supermarket", "bakery"],
        "ticket": 11.5,
        "gross_margin": 0.36,
        "labor_pct": 0.21,
        "default_sqft": 1200,
        "prepared_food": True,
        "hours_default": "6am-11pm",
    },
    "deli_24h": {
        "label": "24-Hour Deli / Grill",
        "google_types": ["convenience_store", "deli", "sandwich_shop", "grocery_store"],
        "osm_direct": ["convenience", "deli", "grocery"],
        "osm_partial": ["fast_food", "cafe", "supermarket"],
        "ticket": 12.5,
        "gross_margin": 0.38,
        "labor_pct": 0.245,
        "default_sqft": 1400,
        "prepared_food": True,
        "hours_default": "24 hours",
    },
    "convenience": {
        "label": "Convenience Store",
        "google_types": ["convenience_store", "grocery_store"],
        "osm_direct": ["convenience", "kiosk"],
        "osm_partial": ["supermarket", "deli"],
        "ticket": 8.5,
        "gross_margin": 0.30,
        "labor_pct": 0.16,
        "default_sqft": 900,
        "prepared_food": False,
        "hours_default": "7am-11pm",
    },
    "gourmet_market": {
        "label": "Gourmet Market",
        "google_types": ["grocery_store", "supermarket", "deli"],
        "osm_direct": ["deli", "greengrocer", "convenience"],
        "osm_partial": ["supermarket", "bakery", "cafe"],
        "ticket": 22.0,
        "gross_margin": 0.40,
        "labor_pct": 0.24,
        "default_sqft": 2500,
        "prepared_food": True,
        "hours_default": "7am-10pm",
    },
    "supermarket": {
        "label": "Supermarket",
        "google_types": ["supermarket", "grocery_store"],
        "osm_direct": ["supermarket"],
        "osm_partial": ["convenience", "greengrocer"],
        "ticket": 38.0,
        "gross_margin": 0.27,
        "labor_pct": 0.14,
        "default_sqft": 8000,
        "prepared_food": False,
        "hours_default": "7am-10pm",
    },
    "cafe": {
        "label": "Cafe / Coffee",
        "google_types": ["cafe", "coffee_shop", "bakery"],
        "osm_direct": ["cafe", "coffee"],
        "osm_partial": ["bakery", "fast_food", "deli"],
        "ticket": 9.0,
        "gross_margin": 0.68,
        "labor_pct": 0.31,
        "default_sqft": 800,
        "prepared_food": True,
        "hours_default": "6am-7pm",
    },
    "fast_casual": {
        "label": "Fast Casual",
        "google_types": ["fast_food_restaurant", "sandwich_shop", "restaurant"],
        "osm_direct": ["fast_food"],
        "osm_partial": ["restaurant", "cafe", "deli"],
        "ticket": 17.0,
        "gross_margin": 0.68,
        "labor_pct": 0.29,
        "default_sqft": 1400,
        "prepared_food": True,
        "hours_default": "10am-10pm",
    },
    "restaurant": {
        "label": "Restaurant",
        "google_types": ["restaurant"],
        "osm_direct": ["restaurant"],
        "osm_partial": ["fast_food", "cafe", "bar"],
        "ticket": 42.0,
        "gross_margin": 0.70,
        "labor_pct": 0.33,
        "default_sqft": 2000,
        "prepared_food": True,
        "hours_default": "11am-11pm",
    },
    "smoke_shop": {
        "label": "Smoke Shop",
        "google_types": ["convenience_store", "store"],
        "osm_direct": ["tobacco", "e-cigarette"],
        "osm_partial": ["convenience"],
        "ticket": 24.0,
        "gross_margin": 0.42,
        "labor_pct": 0.13,
        "default_sqft": 600,
        "prepared_food": False,
        "hours_default": "9am-11pm",
    },
    "pharmacy": {
        "label": "Pharmacy",
        "google_types": ["pharmacy", "drugstore"],
        "osm_direct": ["pharmacy", "chemist"],
        "osm_partial": ["convenience", "supermarket"],
        "ticket": 31.0,
        "gross_margin": 0.24,
        "labor_pct": 0.15,
        "default_sqft": 2000,
        "prepared_food": False,
        "hours_default": "8am-9pm",
    },
    "laundromat": {
        "label": "Laundromat",
        "google_types": ["laundry"],
        "osm_direct": ["laundry", "dry_cleaning"],
        "osm_partial": [],
        "ticket": 16.0,
        "gross_margin": 0.62,
        "labor_pct": 0.16,
        "default_sqft": 1800,
        "prepared_food": False,
        "hours_default": "7am-10pm",
    },
    "barber": {
        "label": "Barber / Salon",
        "google_types": ["hair_salon", "barber_shop", "beauty_salon"],
        "osm_direct": ["hairdresser", "beauty"],
        "osm_partial": [],
        "ticket": 38.0,
        "gross_margin": 0.85,
        "labor_pct": 0.48,
        "default_sqft": 700,
        "prepared_food": False,
        "hours_default": "9am-8pm",
    },
}

DEFAULT_CONCEPT = "deli"

# Fixed monthly operating costs by concept, excluding rent and labor (MODELED).
FIXED_MONTHLY = {
    "deli": 4200, "deli_24h": 5400, "convenience": 2800, "gourmet_market": 6500,
    "supermarket": 14000, "cafe": 3400, "fast_casual": 4600, "restaurant": 7200,
    "smoke_shop": 1900, "pharmacy": 6200, "laundromat": 5200, "barber": 1800,
}

# Share of sales that typically arrives through third-party delivery apps,
# and the blended commission on those orders. Operator-tunable in the form.
DELIVERY_COMMISSION = 0.235
CARD_FEE = 0.026
CARD_SHARE = 0.72
