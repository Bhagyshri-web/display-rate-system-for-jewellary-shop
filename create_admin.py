"""Create or reset the admin login:  python create_admin.py"""
import getpass

from config import Config
from database import db
from services import auth_service
from services.categories import CATEGORIES, PRICING_DEFAULTS

db.init_db(Config.DB_PATH, {}, [c["key"] for c in CATEGORIES], PRICING_DEFAULTS)
username = input("Admin username [admin]: ").strip() or "admin"
password = getpass.getpass("Password (min 8 characters): ")
if password != getpass.getpass("Repeat password: "):
    raise SystemExit("Passwords do not match.")
auth_service.create_admin(Config.DB_PATH, username, password)
print(f"Admin '{username}' saved. Sign in at http://localhost:{Config.PORT}/admin")
