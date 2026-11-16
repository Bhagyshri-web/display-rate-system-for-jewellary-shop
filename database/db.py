"""SQLite helpers. One short-lived connection per operation keeps threads safe."""
import logging
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

SCHEMA = Path(__file__).with_name("schema.sql")
DEFAULT_SETTINGS = {"mode": "demo", "refresh_seconds": "5", "ticker_text": "", "notice": "", "round_to": "1"}


@contextmanager
def conn(path):
    c = sqlite3.connect(path, timeout=10)
    c.row_factory = sqlite3.Row
    try:
        yield c
        c.commit()
    except Exception:
        c.rollback()
        raise
    finally:
        c.close()


def init_db(path, defaults, category_keys, pricing_defaults=None):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with conn(path) as c:
        c.execute("PRAGMA journal_mode=WAL")
        c.executescript(SCHEMA.read_text(encoding="utf-8"))
        for k, v in {**DEFAULT_SETTINGS, **defaults}.items():
            c.execute("INSERT OR IGNORE INTO settings(key,value) VALUES(?,?)", (k, v))
        for i, key in enumerate(category_keys):
            c.execute("INSERT OR IGNORE INTO categories(key,enabled,sort) VALUES(?,1,?)", (key, i))
            c.execute("UPDATE categories SET sort=? WHERE key=?", (i, key))   # keep board order when a category is added
            c.execute("INSERT OR IGNORE INTO rates_current(key) VALUES(?)", (key,))
            calc, purity, margin = (pricing_defaults or {}).get(key, ("direct", 100.0, 0.0))
            c.execute("INSERT OR IGNORE INTO pricing(key,calc,purity,margin) VALUES(?,?,?,?)", (key, calc, purity, margin))


def get_settings(path):
    with conn(path) as c:
        return {r["key"]: r["value"] for r in c.execute("SELECT key,value FROM settings")}


def set_settings(path, values):
    with conn(path) as c:
        for k, v in values.items():
            c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (k, str(v)))


def log(path, level, message):
    logging.getLogger("rates").log(getattr(logging, level), message)
    with conn(path) as c:
        c.execute("INSERT INTO event_log(at,level,message) VALUES(?,?,?)", (time.time(), level, message))
        c.execute("DELETE FROM event_log WHERE id <= (SELECT MAX(id) FROM event_log) - 1000")


def recent_logs(path, n=15):
    with conn(path) as c:
        rows = c.execute("SELECT at,level,message FROM event_log ORDER BY id DESC LIMIT ?", (n,)).fetchall()
    return [{"time": time.strftime("%d %b %H:%M:%S", time.localtime(r["at"])), "level": r["level"], "message": r["message"]} for r in rows]