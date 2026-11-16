"""Central configuration. Secrets come from environment variables, never from frontend code."""
import os
from pathlib import Path

BASE = Path(__file__).resolve().parent


def _load_env(path):
    """Read KEY=value lines from a local .env file (kept on the PC, never sent to the browser)."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip("\"'"))


_load_env(BASE / ".env")


class Config:
    DB_PATH = str(BASE / "database" / "rates.db")
    REFRESH_SECONDS = int(os.environ.get("REFRESH_SECONDS", "5"))   # default only; editable in admin
    TICKER_TEXT = os.environ.get(
        "TICKER_TEXT",
        "Welcome to Gayatri Jewellers  •  गायत्री ज्वेलर्समध्ये आपले स्वागत आहे  •  Rates are indicative and subject to change",
    )
    HOST = os.environ.get("HOST", "0.0.0.0")   # 0.0.0.0 lets a TV box on your Wi-Fi reach the PC
    PORT = int(os.environ.get("PORT", "5000"))
