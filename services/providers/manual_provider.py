"""Manual entry: rates typed by the shop owner in the admin panel."""
import math

from services.categories import BY_KEY
from .base import RateProvider, RateRecord


class ManualProvider(RateProvider):
    name = "manual"
    polled = False

    def fetch(self):
        return []   # nothing to pull; values arrive through submit()

    def submit(self, values: dict) -> list[RateRecord]:
        if not values:
            raise ValueError("Enter at least one rate.")
        records = []
        for key, v in values.items():
            cat = BY_KEY.get(key)
            if cat is None:
                raise ValueError(f"Unknown rate category: {key}")
            if not math.isfinite(v) or not (cat["min"] <= v <= cat["max"]):
                raise ValueError(f"{cat['en']}: value is outside the allowed range ({cat['min']:,}–{cat['max']:,}).")
            records.append(RateRecord(key, v))
        return records
