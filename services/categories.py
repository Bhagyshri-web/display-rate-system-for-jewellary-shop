"""Rate categories shown on the board. Ranges are sanity limits, not market predictions."""
_GOLD = dict(unit_en="per 10 gm", unit_mr="प्रति १० ग्रॅम", min=1_000, max=10_000_000)
CATEGORIES = [
    {"key": "gold24", "en": "24K Gold", "mr": "२४ कॅरेट सोने", **_GOLD},
    {"key": "gold22", "en": "22K Gold", "mr": "२२ कॅरेट सोने", "derive_from": "gold24", **_GOLD},
    {"key": "gold20", "en": "20K Gold", "mr": "२० कॅरेट सोने", "derive_from": "gold24", **_GOLD},
    {"key": "gold18", "en": "18K Gold", "mr": "१८ कॅरेट सोने", "derive_from": "gold24", **_GOLD},
    {"key": "silver", "en": "Silver", "mr": "चांदी", "unit_en": "per kg", "unit_mr": "प्रति किलो", "min": 1_000, "max": 10_000_000},
]
BY_KEY = {c["key"]: c for c in CATEGORIES}

# (calculation, purity %, margin in rupees). 22K, 20K and 18K are calculated as 24K rate x purity by default;
# purity is editable in the admin panel.
PRICING_DEFAULTS = {"gold24": ("direct", 100.0, 0.0), "gold22": ("purity", 91.6, 0.0),
                    "gold20": ("purity", 83.3, 0.0), "gold18": ("purity", 75.0, 0.0), "silver": ("direct", 100.0, 0.0)}
ROUND_CHOICES = (1, 5, 10, 50, 100)