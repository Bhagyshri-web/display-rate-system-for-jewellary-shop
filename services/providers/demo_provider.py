"""DEMO provider. Values are random sample data and are NOT market rates.
The display always shows a DEMO badge while this provider is active."""
import random
from .base import RateProvider, RateRecord

_DEMO_START = {"gold24": 100000.0, "gold22": 91000.0, "gold20": 83000.0, "gold18": 75000.0, "silver": 120000.0}
_STEP = {"gold24": 150, "gold22": 140, "gold20": 120, "gold18": 105, "silver": 400}


class DemoProvider(RateProvider):
    name = "demo"

    def __init__(self):
        self._values = dict(_DEMO_START)

    def fetch(self) -> list[RateRecord]:
        for key in self._values:
            if random.random() < 0.6:  # not every rate moves on every tick
                self._values[key] += random.choice([-1, 1]) * random.randint(1, 3) * _STEP[key] / 3
        return [RateRecord(k, round(v)) for k, v in self._values.items()]