from flask import Blueprint, render_template

bp = Blueprint("display", __name__)


@bp.get("/")
def tv():
    return render_template("display.html")
