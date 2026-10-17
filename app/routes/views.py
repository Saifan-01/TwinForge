"""Dashboard views: login, logout and the main console."""

from flask import Blueprint, redirect, render_template, request, session, url_for

from app.auth import login_required, verify_login
from db.connection import get_db

bp = Blueprint("views", __name__)


@bp.route("/")
@login_required
def dashboard():
    """Renders the main Digital Twin console."""
    zones = list(get_db().zones.find({}, {"_id": 0}))
    return render_template(
        "dashboard.html",
        zones=zones,
        username=session["username"],
        role=session.get("role", "viewer"),
    )


@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user, error = verify_login(username, password)
        if user:
            session.clear()
            session.permanent = True
            session["username"] = user["username"]
            session["role"] = user.get("role", "viewer")
            nxt = request.args.get("next", "/")
            return redirect(nxt if nxt.startswith("/") and not nxt.startswith("//") else "/")
    return render_template("login.html", error=error), (401 if error else 200)


@bp.route("/logout", methods=["POST", "GET"])
def logout():
    session.clear()
    return redirect(url_for("views.login"))
