"""All provider-specific settings live here, read from environment variables (or the local .env file).
Nothing is pre-filled: the endpoint, interval and permission must come from you and the provider's terms."""
import os
from dataclasses import dataclass, field

from services.categories import BY_KEY


@dataclass(frozen=True)
class LiveConfig:
    provider_name: str
    url: str
    api_key: str
    min_interval: int            # the provider's permitted minimum seconds between requests
    permission_confirmed: bool   # you hold written permission or official API access
    row_map: dict                # category key -> which provider row to use (an ID, or the name without the date)
    value_column: int = 2        # which number on the row to use, counted from 1
    timeout: int = 10
    url_map: dict = field(default_factory=dict)   # optional own URL per category (e.g. silver on another feed)

    @classmethod
    def from_env(cls):
        e = os.environ.get

        def to_int(name, default):
            try:
                return int(e(name, str(default)) or default)
            except ValueError:
                return 0

        row_map = {k: e(f"LIVE_MAP_{k.upper()}", "").strip() for k in BY_KEY}
        return cls(provider_name=e("LIVE_PROVIDER_NAME", ""), url=e("LIVE_URL", ""), api_key=e("LIVE_API_KEY", ""),
                   min_interval=to_int("LIVE_MIN_INTERVAL_SECONDS", 0),
                   permission_confirmed=e("LIVE_PERMISSION_CONFIRMED", "").lower() == "yes",
                   row_map={k: v for k, v in row_map.items() if v}, value_column=to_int("LIVE_VALUE_COLUMN", 2),
                   url_map={k: e(f"LIVE_URL_{k.upper()}", "").strip() for k in BY_KEY if e(f"LIVE_URL_{k.upper()}", "").strip()})

    def url_for(self, key):
        return self.url_map.get(key) or self.url

    def missing(self):
        gaps = []
        if not self.permission_confirmed:
            gaps.append("LIVE_PERMISSION_CONFIRMED=yes (written permission or official API access)")
        if (not self.row_map and not self.url) or any(not self.url_for(k) for k in self.row_map):
            gaps.append("LIVE_URL (or LIVE_URL_<CATEGORY> for each mapped rate)")
        if self.min_interval <= 0:
            gaps.append("LIVE_MIN_INTERVAL_SECONDS (from the provider's terms)")
        if not self.row_map:
            gaps.append("at least one LIVE_MAP_<CATEGORY>, e.g. LIVE_MAP_GOLD24 (which row to use)")
        if self.value_column < 1:
            gaps.append("LIVE_VALUE_COLUMN (a number, 1 or more)")
        return gaps
