"""Turns raw OSM tags and Google types into the categories an operator
actually thinks in: who competes with me, who sends me customers, who is just
neighbourhood furniture."""

# category -> (display label, map colour, marker glyph)
CATEGORY_META = {
    "deli": ("Deli / Bodega", "#ff5a5a", "D"),
    "convenience": ("Convenience", "#ff8a3d", "C"),
    "supermarket": ("Supermarket", "#e0483d", "S"),
    "restaurant": ("Restaurant", "#ffb347", "R"),
    "fast_food": ("Fast food", "#ffcf5c", "F"),
    "coffee": ("Coffee / Cafe", "#c08457", "☕"),
    "bakery": ("Bakery", "#d8a35c", "B"),
    "smoke_shop": ("Smoke shop", "#9b7bd4", "K"),
    "pharmacy": ("Pharmacy", "#4fc3f7", "+"),
    "liquor": ("Liquor", "#b05fd6", "L"),
    "school": ("School", "#5ee0a0", "🎓"),
    "college": ("College", "#3fcf8e", "U"),
    "hospital": ("Hospital / clinic", "#66e0e0", "H"),
    "hotel": ("Hotel", "#7ea8ff", "🏨"),
    "gym": ("Gym", "#7ee081", "G"),
    "office": ("Office", "#98a9c9", "O"),
    "government": ("Government", "#8fa0bd", "GV"),
    "transit": ("Transit", "#5aa9ff", "T"),
    "bus": ("Bus stop", "#7fbfff", "b"),
    "nightlife": ("Bar / nightlife", "#ff7ad9", "N"),
    "park": ("Park", "#57c878", "P"),
    "attraction": ("Attraction", "#ffd479", "★"),
    "residential": ("Residential building", "#6b7a90", "▮"),
    "laundry": ("Laundry", "#93c5fd", "W"),
    "barber": ("Barber / salon", "#c4b5fd", "✂"),
    "retail": ("Other retail", "#8d9bb0", "•"),
    "service": ("Service business", "#7d8a9c", "•"),
    "other": ("Other", "#6a7686", "•"),
}

# Categories that generate walk-in demand rather than competing for it.
DEMAND_CATEGORIES = {
    "school", "college", "hospital", "hotel", "gym", "office", "government",
    "transit", "bus", "nightlife", "park", "attraction", "residential",
}

FOOD_CATEGORIES = {"deli", "convenience", "supermarket", "restaurant", "fast_food",
                   "coffee", "bakery"}


def classify_osm(p):
    shop = (p.get("shop") or "").lower()
    amenity = (p.get("amenity") or "").lower()
    tourism = (p.get("tourism") or "").lower()
    leisure = (p.get("leisure") or "").lower()
    office = (p.get("office") or "").lower()
    healthcare = (p.get("healthcare") or "").lower()
    railway = (p.get("railway") or "").lower()
    pt = (p.get("public_transport") or "").lower()
    highway = (p.get("highway") or "").lower()
    building = (p.get("building") or "").lower()

    if shop in ("deli",) or amenity == "deli":
        return "deli"
    if shop in ("convenience", "kiosk", "newsagent"):
        return "convenience"
    if shop in ("supermarket", "greengrocer", "grocery"):
        return "supermarket" if shop == "supermarket" else "convenience"
    if shop == "bakery":
        return "bakery"
    if shop in ("tobacco", "e-cigarette", "cannabis"):
        return "smoke_shop"
    if shop in ("chemist",) or amenity == "pharmacy" or healthcare == "pharmacy":
        return "pharmacy"
    if shop == "alcohol" or shop == "wine":
        return "liquor"
    if shop in ("laundry", "dry_cleaning"):
        return "laundry"
    if shop in ("hairdresser", "beauty", "barber"):
        return "barber"
    if amenity == "cafe" or shop == "coffee":
        return "coffee"
    if amenity == "fast_food":
        return "fast_food"
    if amenity == "restaurant" or amenity == "food_court":
        return "restaurant"
    if amenity in ("bar", "pub", "nightclub", "biergarten"):
        return "nightlife"
    if amenity in ("school", "kindergarten", "childcare"):
        return "school"
    if amenity in ("college", "university"):
        return "college"
    if amenity in ("hospital", "clinic", "doctors", "dentist") or healthcare in (
            "hospital", "clinic", "doctor", "centre"):
        return "hospital"
    if tourism in ("hotel", "hostel", "motel", "guest_house"):
        return "hotel"
    if tourism in ("attraction", "museum", "gallery", "viewpoint", "theme_park", "zoo"):
        return "attraction"
    if leisure in ("fitness_centre", "sports_centre", "gym"):
        return "gym"
    if leisure in ("park", "garden", "playground", "pitch", "dog_park"):
        return "park"
    if amenity in ("townhall", "courthouse", "police", "fire_station", "post_office", "library"):
        return "government"
    if office in ("government", "diplomatic"):
        return "government"
    if office:
        return "office"
    if railway in ("station", "subway_entrance", "tram_stop") or pt == "station":
        return "transit"
    if highway == "bus_stop" or pt in ("stop_position", "platform"):
        return "bus"
    if amenity in ("theatre", "cinema", "arts_centre", "casino"):
        return "attraction"
    if building in ("apartments", "residential", "dormitory"):
        return "residential"
    if building in ("office", "commercial"):
        return "office"
    if building in ("hotel",):
        return "hotel"
    if building in ("hospital",):
        return "hospital"
    if building in ("school", "university"):
        return "school"
    if shop:
        return "retail"
    if amenity in ("bank", "atm", "car_wash", "fuel", "veterinary"):
        return "service"
    return "other"


GOOGLE_TYPE_MAP = {
    "convenience_store": "convenience", "deli": "deli", "sandwich_shop": "deli",
    "grocery_store": "convenience", "supermarket": "supermarket",
    "cafe": "coffee", "coffee_shop": "coffee", "bakery": "bakery",
    "fast_food_restaurant": "fast_food", "meal_takeaway": "fast_food",
    "restaurant": "restaurant", "bar": "nightlife", "night_club": "nightlife",
    "pharmacy": "pharmacy", "drugstore": "pharmacy", "liquor_store": "liquor",
    "laundry": "laundry", "hair_salon": "barber", "barber_shop": "barber",
    "beauty_salon": "barber", "gym": "gym", "fitness_center": "gym",
    "hotel": "hotel", "lodging": "hotel", "hospital": "hospital", "school": "school",
    "university": "college", "park": "park", "subway_station": "transit",
    "transit_station": "transit", "train_station": "transit",
}


def classify_google(place):
    primary = (place.get("primary_type") or "").lower().replace(" ", "_")
    if primary in GOOGLE_TYPE_MAP:
        return GOOGLE_TYPE_MAP[primary]
    for t in place.get("types") or []:
        if t in GOOGLE_TYPE_MAP:
            return GOOGLE_TYPE_MAP[t]
    name = (place.get("name") or "").lower()
    if any(w in name for w in ("deli", "bodega", "grocery", "gourmet market")):
        return "deli"
    if "smoke" in name or "vape" in name:
        return "smoke_shop"
    return "retail"


def label(cat):
    return CATEGORY_META.get(cat, CATEGORY_META["other"])[0]


def colour(cat):
    return CATEGORY_META.get(cat, CATEGORY_META["other"])[1]


def glyph(cat):
    return CATEGORY_META.get(cat, CATEGORY_META["other"])[2]
