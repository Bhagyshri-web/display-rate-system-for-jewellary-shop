from flask import Blueprint, current_app, flash, redirect, render_template, request, session, url_for

from database import db
from services import auth_service
from services.categories import CATEGORIES

bp = Blueprint("admin", __name__, url_prefix="/admin")


def _path():
    return current_app.config["DB_PATH"]


def _num(raw, default="0"):
    try:
        return float((raw or default).replace(",", "").replace("₹", "").replace("%", "").strip() or default)
    except ValueError:
        raise ValueError("Enter valid numbers only.")


def _back():
    return redirect(url_for("admin.dashboard"))


@bp.before_request
def _protect():
    if request.method == "POST":
        auth_service.check_csrf()


@bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        ip, user = request.remote_addr, request.form.get("username", "").strip()
        if auth_service.locked(ip):
            flash("Too many attempts. Wait a few minutes and try again.", "error")
        elif auth_service.verify(_path(), user, request.form.get("password", "")):
            session.clear()
            session["admin"], session.permanent = user, True
            db.log(_path(), "INFO", f"Admin login: {user}")
            return _back()
        else:
            auth_service.record_fail(ip)
            db.log(_path(), "WARNING", f"Failed admin login from {ip}")
            flash("Wrong username or password.", "error")
    return render_template("admin/login.html")


@bp.post("/logout")
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


@bp.get("/")
@auth_service.login_required
def dashboard():
    svc = current_app.rate_service
    return render_template("admin/dashboard.html", st=svc.admin_state(), snap=svc.snapshot(), logs=db.recent_logs(_path()))


@bp.post("/settings")
@auth_service.login_required
def settings():
    f = request.form
    try:
        refresh = min(60, max(3, int(f.get("refresh_seconds", "5"))))
        current_app.rate_service.update_settings(f.get("mode", ""), refresh, f.get("ticker_text", "")[:300], f.get("notice", "")[:120])
        flash("Settings saved.", "ok")
    except ValueError as e:
        flash(str(e) or "Refresh interval must be a number.", "error")
    return _back()


@bp.post("/categories")
@auth_service.login_required
def categories():
    try:
        current_app.rate_service.set_enabled(request.form.getlist("enabled"))
        flash("Categories saved.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return _back()


@bp.post("/rates")
@auth_service.login_required
def rates():
    svc = current_app.rate_service
    if db.get_settings(_path())["mode"] != "manual":
        flash("Switch to Manual mode before entering rates.", "error")
        return _back()
    values = {}
    try:
        for c in CATEGORIES:
            raw = request.form.get(c["key"], "").replace(",", "").strip()
            if raw:
                values[c["key"]] = float(raw)
        svc.set_manual(values)
        flash("Rates saved and sent to the TV.", "ok")
    except ValueError as e:
        flash(str(e) if values or "range" in str(e) else "Enter valid numbers only.", "error")
    return _back()


@bp.post("/pricing")
@auth_service.login_required
def pricing():
    f, items = request.form, {}
    try:
        for c in CATEGORIES:
            k = c["key"]
            items[k] = {"margin": _num(f.get(f"margin_{k}"))}
            if c.get("derive_from"):
                items[k].update(calc=f.get(f"calc_{k}", "direct"), purity=_num(f.get(f"purity_{k}"), "100"))
        current_app.rate_service.update_pricing(items, int(_num(f.get("round_to"), "1")))
        flash("Pricing saved.", "ok")
    except ValueError as e:
        flash(str(e), "error")
    return _back()
