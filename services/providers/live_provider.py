"""Live provider adapter for the Safari Bullions style text feed.

The response is plain text, one row per line:   <ID> <NAME ...> <number> <number> <number> <number>
Rows are read from the right (trailing numbers or "-"), so names containing spaces and digits are safe.
The adapter stays disabled until LiveConfig is complete, including LIVE_PERMISSION_CONFIRMED=yes."""
import re
import time
from dataclasses import dataclass

from .base import ProviderError, ProviderNotReady, RateProvider, RateRecord
from .live_config import LiveConfig

PARSER_READY = True
MAX_RESPONSE_BYTES = 1_000_000
_NUM = re.compile(r"^-?\d+(?:\.\d+)?$")
_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")


@dataclass(frozen=True)
class Row:
    id: str
    name: str
    values: tuple


def parse_rows(raw: str) -> list[Row]:
    if "<html" in raw[:300].lower():
        raise ProviderError("Unexpected HTML response instead of rate text")
    rows = []
    for line in raw.splitlines():
        toks = line.split()
        if len(toks) < 3 or not toks[0].isdigit():
            continue
        i = len(toks)
        while i > 1 and (_NUM.match(toks[i - 1]) or toks[i - 1] == "-"):
            i -= 1
        name, values = " ".join(toks[1:i]), tuple(toks[i:])
        if name and values:
            rows.append(Row(toks[0], name, values))
    return rows


def _norm(text):
    return " ".join(text.upper().split())


def find_row(rows, match):
    if match.isdigit():
        hits = [r for r in rows if r.id == match]
    else:
        m = _norm(match)
        hits = [r for r in rows if m in (_norm(r.name), _norm(_TRAILING_PAREN.sub("", r.name)))]
    if len(hits) != 1:
        raise ProviderError(f"Expected exactly one row for '{match}', found {len(hits)}")
    return hits[0]


class LiveProvider(RateProvider):
    name = "live"

    def __init__(self, config: LiveConfig):
        self.config = config
        self.min_interval = config.min_interval

    def available(self):
        return PARSER_READY and not self.config.missing()

    def status_text(self):
        gaps = self.config.missing()
        if gaps:
            return "Not configured. Missing: " + "; ".join(gaps)
        return "Ready" if PARSER_READY else "Parser not enabled"

    def fetch(self) -> list[RateRecord]:
        if not self.available():
            raise ProviderNotReady(self.status_text())
        if self.config.api_key:
            raise ProviderNotReady("API key supplied, but the provider's authentication method is not implemented")
        by_url = {}                                  # each distinct feed is downloaded once per cycle
        for key in self.config.row_map:
            by_url.setdefault(self.config.url_for(key), []).append(key)
        records = []
        for url, keys in by_url.items():             # all-or-nothing: if any feed fails, no rate is refreshed
            records += self.parse(self._download(url), keys)
        return records

    def _download(self, url: str) -> str:
        import requests
        if url.endswith("_="):                 # the page's own cache-busting parameter
            url += str(int(time.time() * 1000))
        try:
            resp = requests.get(url, timeout=self.config.timeout, headers={"User-Agent": "GayatriRateBoard/1.0"})
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise ProviderError(f"Request failed: {exc}") from exc
        if len(resp.content) > MAX_RESPONSE_BYTES:
            raise ProviderError("Response unexpectedly large; ignored")
        return resp.text

    def parse(self, raw: str, keys=None) -> list[RateRecord]:
        rows = parse_rows(raw)
        if not rows:
            raise ProviderError("No rate rows found in the response")
        col, records = self.config.value_column, []
        for key in (keys or list(self.config.row_map)):
            row = find_row(rows, self.config.row_map[key])
            if col > len(row.values) or not _NUM.match(row.values[col - 1]):
                raise ProviderError(f"Row '{row.name}' has no price in column {col}")
            records.append(RateRecord(key, float(row.values[col - 1])))
        return records
