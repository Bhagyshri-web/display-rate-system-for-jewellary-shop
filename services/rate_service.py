"""Core rate logic: provider scheduling, validation, change detection, persistence, freshness."""
import math
import threading
import time

from database import db
from services.categories import BY_KEY, CATEGORIES, ROUND_CHOICES  # noqa: F401  (re-exported)

ALL_MODES = ("demo", "manual", "live")


def _fmt_time(ts):
    return time.strftime("%d %b %Y, %I:%M:%S %p", time.localtime(ts)) if ts else None


class RateService:
    def __init__(self, db_path, providers, hub):
        self.db_path, self.providers, self.hub = db_path, providers, hub
        self._lock = threading.Lock()
        self._next_attempt = 0.0
        self._fails = 0
        self._last_error = None

    def available_modes(self):
        return [m for m in ALL_MODES if m in self.providers and self.providers[m].available()]

    # ---- fetching ----
    def refresh_if_due(self):
        with self._lock:
            s = db.get_settings(self.db_path)
            provider = self.providers.get(s["mode"])
            if provider is None or not provider.polled:
                return
            now = time.time()
            if now < self._next_attempt:       # never request more often than allowed
                return
            interval = max(int(s["refresh_seconds"]), provider.min_interval)
            try:
                self._apply(provider.fetch(), provider.name)
                self._fails, self._last_error = 0, None
                self._next_attempt = now + interval
            except Exception as exc:
                self._fails += 1
                self._next_attempt = now + min(interval * 2 ** self._fails, 300)   # back off after failures
                if str(exc) != self._last_error:
                    db.log(self.db_path, "ERROR", f"{provider.name} fetch failed: {exc}")
                self._last_error = str(exc)

    def _apply(self, records, source):
        now, changed, rejected = time.time(), False, []
        with db.conn(self.db_path) as c:
            for rec in records:
                cat = BY_KEY.get(rec.key)
                if cat is None or not (cat["min"] <= rec.value <= cat["max"]):
                    rejected.append(f"{rec.key}={rec.value}")
                    continue
                old = c.execute("SELECT value FROM rates_current WHERE key=?", (rec.key,)).fetchone()["value"]
                if old is None or rec.value != old:
                    direction = "flat" if old is None else ("up" if rec.value > old else "down")
                    c.execute("UPDATE rates_current SET value=?, prev=?, direction=?, received_at=?, source=? WHERE key=?",
                              (rec.value, old, direction, now, source, rec.key))
                    if source != "demo":   # demo values are never kept as history
                        c.execute("INSERT INTO rate_history(key,value,source,at) VALUES(?,?,?,?)", (rec.key, rec.value, source, now))
                    changed = True
                else:
                    c.execute("UPDATE rates_current SET received_at=?, source=? WHERE key=?", (now, source, rec.key))
        if rejected:
            db.log(self.db_path, "WARNING", "Rejected invalid rates: " + ", ".join(rejected))
        if changed:
            self.hub.publish()
        return changed

    # ---- admin actions ----
    def set_manual(self, values):
        for k in values:
            if k in self._derived_keys():
                raise ValueError(f"{BY_KEY[k]['en']} is calculated from 24K. Change it under Pricing first.")
        records = self.providers["manual"].submit(values)
        self._apply(records, "manual")
        db.log(self.db_path, "INFO", "Manual rates saved: " + ", ".join(f"{r.key}={r.value:g}" for r in records))
        self.hub.publish()

    def update_settings(self, mode, refresh, ticker, notice):
        if mode not in self.available_modes():
            raise ValueError("That mode is not available.")
        with self._lock:
            old = db.get_settings(self.db_path)["mode"]
            if mode != old:
                with db.conn(self.db_path) as c:
                    c.execute("UPDATE rates_current SET value=NULL, prev=NULL, direction='flat', received_at=NULL, source=NULL")
                self._next_attempt, self._fails, self._last_error = 0.0, 0, None
                db.log(self.db_path, "INFO", f"Mode changed {old} -> {mode}; stored rates cleared")
            db.set_settings(self.db_path, {"mode": mode, "refresh_seconds": refresh, "ticker_text": ticker, "notice": notice})
        self.hub.publish()

    def set_enabled(self, keys):
        keys = set(keys) & set(BY_KEY)
        if not keys:
            raise ValueError("Keep at least one rate category enabled.")
        with db.conn(self.db_path) as c:
            for k in BY_KEY:
                c.execute("UPDATE categories SET enabled=? WHERE key=?", (int(k in keys), k))
        self.hub.publish()

    # ---- pricing: purity calculation and margin ----
    def _pricing(self):
        with db.conn(self.db_path) as c:
            return {r["key"]: dict(r) for r in c.execute("SELECT key,calc,purity,margin FROM pricing")}

    def _derived_keys(self):
        return {k for k, p in self._pricing().items() if p["calc"] == "purity" and BY_KEY[k].get("derive_from")}

    @staticmethod
    def _compute(raw, pricing, round_to):
        """Source rates -> board rates. Direct rate = source + margin.
        Calculated rate = (24K rate incl. its margin) x purity% + its own margin. Rounded last."""
        pre = {}
        for cat in CATEGORIES:
            p = pricing[cat["key"]]
            if not (cat.get("derive_from") and p["calc"] == "purity"):
                v = raw.get(cat["key"])
                pre[cat["key"]] = None if v is None else v + p["margin"]
        for cat in CATEGORIES:
            p = pricing[cat["key"]]
            if cat.get("derive_from") and p["calc"] == "purity":
                base = pre.get(cat["derive_from"])
                pre[cat["key"]] = None if base is None else base * p["purity"] / 100 + p["margin"]
        return {k: None if v is None else int(math.floor(v / round_to + 0.5) * round_to) for k, v in pre.items()}

    def _shown(self, rows, settings):
        pricing, round_to = self._pricing(), int(settings.get("round_to", "1"))
        now = self._compute({r["key"]: r["value"] for r in rows}, pricing, round_to)
        before = self._compute({r["key"]: r["prev"] for r in rows}, pricing, round_to)
        return now, before, pricing

    def update_pricing(self, items, round_to):
        if round_to not in ROUND_CHOICES:
            raise ValueError("Choose a valid rounding step.")
        old = self._pricing()
        clean = {}
        for key, it in items.items():
            cat = BY_KEY.get(key)
            if cat is None:
                raise ValueError(f"Unknown category: {key}")
            margin = it.get("margin", 0.0)
            if not math.isfinite(margin) or abs(margin) > 1_000_000:
                raise ValueError(f"{cat['en']}: margin must be a number between -10,00,000 and 10,00,000.")
            calc, purity = "direct", 100.0
            if cat.get("derive_from"):
                calc, purity = it.get("calc", "direct"), it.get("purity", 100.0)
                if calc not in ("direct", "purity"):
                    raise ValueError(f"{cat['en']}: unknown calculation.")
                if not math.isfinite(purity) or not (0 < purity <= 100):
                    raise ValueError(f"{cat['en']}: purity must be above 0 and at most 100.")
            clean[key] = (calc, purity, margin)
        with db.conn(self.db_path) as c:
            for key, (calc, purity, margin) in clean.items():
                c.execute("UPDATE pricing SET calc=?, purity=?, margin=? WHERE key=?", (calc, purity, margin, key))
                if old[key]["calc"] != calc:   # never reuse a stale source value after switching how a rate is found
                    c.execute("UPDATE rates_current SET value=NULL, prev=NULL, direction='flat', received_at=NULL, source=NULL WHERE key=?", (key,))
        db.set_settings(self.db_path, {"round_to": round_to})
        db.log(self.db_path, "INFO", "Pricing updated: " + ", ".join(f"{k}: {c}/{p:g}%/{m:+g}" for k, (c, p, m) in clean.items()) + f"; round to {round_to}")
        self.hub.publish()

    # ---- read models ----
    def _read(self):
        with db.conn(self.db_path) as c:
            return c.execute("SELECT c.key, c.enabled, r.value, r.prev, r.direction, r.received_at "
                             "FROM categories c JOIN rates_current r ON r.key=c.key ORDER BY c.sort").fetchall()

    def snapshot(self):
        s, rows, now = db.get_settings(self.db_path), self._read(), time.time()
        refresh, prov = int(s["refresh_seconds"]), self.providers.get(s["mode"])
        received = max((r["received_at"] for r in rows if r["received_at"]), default=None)
        if received is None or prov is None:
            status = "empty"
        elif not prov.polled:
            status = s["mode"]                     # manual rates stay until changed
        else:
            status = "stale" if now - received > max(refresh, prov.min_interval) * 3 else s["mode"]
        shown, before, _ = self._shown(rows, s)
        rates = []
        for r in rows:
            if not r["enabled"]:
                continue
            v, pv = shown[r["key"]], before[r["key"]]
            direction = "flat" if v is None or pv is None or v == pv else ("up" if v > pv else "down")
            rates.append({k: BY_KEY[r["key"]][k] for k in ("key", "en", "mr", "unit_en", "unit_mr")}
                         | {"value": v, "prev": pv, "direction": direction})
        return {"mode": s["mode"], "status": status, "received_at": received, "server_time": now,
                "refresh_seconds": refresh, "ticker": s["ticker_text"], "notice": s["notice"], "rates": rates}

    def admin_state(self):
        s, rows = db.get_settings(self.db_path), self._read()
        received = max((r["received_at"] for r in rows if r["received_at"]), default=None)
        shown, _, pricing = self._shown(rows, s)
        cats = [{**BY_KEY[r["key"]], "enabled": bool(r["enabled"]), "value": r["value"], "display": shown[r["key"]],
                 "calc": pricing[r["key"]]["calc"], "purity": pricing[r["key"]]["purity"], "margin": pricing[r["key"]]["margin"]}
                for r in rows]
        live = self.providers.get("live")
        return {"settings": s, "categories": cats, "last_update": _fmt_time(received), "last_error": self._last_error,
                "modes": self.available_modes(), "round_choices": ROUND_CHOICES,
                "live_status": live.status_text() if live else "Not installed"}
