import logging
import os
import secrets
from datetime import timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, request

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


def _add_security_headers(response):
    """Apply security headers to all responses."""
    # Prevent clickjacking
    response.headers["X-Frame-Options"] = "DENY"
    # Prevent MIME type sniffing
    response.headers["X-Content-Type-Options"] = "nosniff"
    # Enable XSS protection (legacy but harmless)
    response.headers["X-XSS-Protection"] = "1; mode=block"
    # Restrict referrer information
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Content Security Policy - restrictive but allows inline styles/scripts for display page
    if request.path.startswith("/admin"):
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
    else:
        # Display page needs inline script/style for live updates
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com; "
            "script-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'"
        )
    # Permissions Policy - restrict browser features
    response.headers["Permissions-Policy"] = (
        "accelerometer=(), camera=(), geolocation=(), gyroscope=(), "
        "magnetometer=(), microphone=(), payment=(), usb=()"
    )
    # HSTS - only enable in production with HTTPS
    # if not app.debug and request.is_secure:
    #     response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

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
    app.after_request(_add_security_headers)
    if start_poller:
        Poller(app.rate_service).start()
    return app


if __name__ == "__main__":
    create_app().run(host=Config.HOST, port=Config.PORT, threaded=True)
