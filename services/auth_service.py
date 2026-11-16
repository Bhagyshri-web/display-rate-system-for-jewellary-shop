"""Admin authentication: password hashing, login throttling, CSRF protection."""
import functools
import secrets
import time

from flask import abort, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from database import db

MAX_FAILS, WINDOW = 5, 300          # 5 wrong attempts per 5 minutes per address
_fails = {}


def locked(ip):
    recent = [t for t in _fails.get(ip, []) if time.time() - t < WINDOW]
    _fails[ip] = recent
    return len(recent) >= MAX_FAILS


def record_fail(ip):
    _fails.setdefault(ip, []).append(time.time())


def verify(db_path, username, password):
    with db.conn(db_path) as c:
        row = c.execute("SELECT password_hash FROM admin_users WHERE username=?", (username,)).fetchone()
    return row is not None and check_password_hash(row["password_hash"], password)


def create_admin(db_path, username, password):
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters.")
    with db.conn(db_path) as c:
        c.execute("INSERT INTO admin_users(username,password_hash) VALUES(?,?) "
                  "ON CONFLICT(username) DO UPDATE SET password_hash=excluded.password_hash",
                  (username, generate_password_hash(password)))


def login_required(view):
    @functools.wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("admin"):
            return redirect(url_for("admin.login"))
        return view(*args, **kwargs)
    return wrapped


def csrf_token():
    if "csrf" not in session:
        session["csrf"] = secrets.token_hex(16)
    return session["csrf"]


def check_csrf():
    sent, expected = request.form.get("csrf", ""), session.get("csrf", "")
    if not expected or not secrets.compare_digest(sent.encode(), expected.encode()):
        abort(400)
