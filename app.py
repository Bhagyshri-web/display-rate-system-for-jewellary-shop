import logging
import os
import secrets
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask

from config import Config
from database import db
from routes import admin, api, display
from services import auth_service
from services.event_hub import EventHub
from services.poller import Poller
from services.categories import CATEGORIES, PRICING_DEFAULTS
from services.providers.demo_provider import DemoProvider
from services.providers.live_config import LiveConfig
from services.providers.live_provider import LiveProvider
from services.providers.manual_provider import ManualProvider
from services.rate_service import RateService

BASE = Path(__file__).resolve().parent


def _secret_key():
    if os.environ.get("SECRET_KEY"):
        return os.environ["SECRET_KEY"]
    path = BASE / "instance" / "secret.key"
    path.parent.mkdir(exist_ok=True)
    if not path.exists():
        path.write_text(secrets.token_hex(32))
    return path.read_text().strip()


def create_app(db_path=None, start_poller=True):
    (BASE / "logs").mkdir(exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                        handlers=[RotatingFileHandler(BASE / "logs" / "app.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"),
                                  logging.StreamHandler()])
    app = Flask(__name__)
    app.config.update(SECRET_KEY=_secret_key(), DB_PATH=str(db_path or Config.DB_PATH),
                      SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Lax",
                      PERMANENT_SESSION_LIFETIME=timedelta(hours=12))
    db.init_db(app.config["DB_PATH"], {"refresh_seconds": str(Config.REFRESH_SECONDS), "ticker_text": Config.TICKER_TEXT},
               [c["key"] for c in CATEGORIES], PRICING_DEFAULTS)
    app.hub = EventHub()
    app.rate_service = RateService(
        app.config["DB_PATH"],
        {"demo": DemoProvider(), "manual": ManualProvider(), "live": LiveProvider(LiveConfig.from_env())},
        app.hub)
    app.jinja_env.globals["csrf_token"] = auth_service.csrf_token
    for module in (display, api, admin):
        app.register_blueprint(module.bp)
    if start_poller:
        Poller(app.rate_service).start()
    return app


if __name__ == "__main__":
    create_app().run(host=Config.HOST, port=Config.PORT, threaded=True)
