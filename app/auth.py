"""Authentication and role-based access control.

Two ways to authenticate:
  1. Browser session (login page). Users live in the MongoDB `users` collection
     with salted password hashes and a role: "admin" or "viewer".
  2. API key in the `X-API-Key` header (for devices, scripts and the test suite).

Rules enforced for every /api/* request:
  - No credentials                      -> 401
  - Read (GET/HEAD/OPTIONS)             -> any logged-in user, or a valid API key
  - Write (POST/PUT/DELETE)             -> admin role, or a valid API key
  - Session-based writes also need the  -> X-Requested-With header (basic CSRF guard)
"""

import hmac
import time
from collections import defaultdict
from functools import wraps

from flask import current_app, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from db.connection import get_db

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
MAX_FAILED_LOGINS = 5
LOCKOUT_SECONDS = 300
_failed_logins = defaultdict(list)  # "ip:username" -> [timestamps]


def hash_password(password: str) -> str:
    return generate_password_hash(password)


def ensure_user(db, username: str, password: str, role: str = "viewer") -> bool:
    """Creates a user if it does not exist yet. Returns True when created."""
    if db.users.find_one({"username": username}):
        return False
    db.users.insert_one({"username": username, "passwordHash": hash_password(password), "role": role})
    return True


def _valid_api_key() -> bool:
    expected = current_app.config.get("API_KEY") or ""
    supplied = request.headers.get("X-API-Key", "")
    return bool(expected) and hmac.compare_digest(supplied, expected)


def _is_locked(key: str) -> bool:
    now = time.time()
    _failed_logins[key] = [t for t in _failed_logins[key] if now - t < LOCKOUT_SECONDS]
    return len(_failed_logins[key]) >= MAX_FAILED_LOGINS


def verify_login(username: str, password: str):
    """Returns (user_doc | None, error_message | None)."""
    key = f"{request.remote_addr}:{username.lower()}"
    if _is_locked(key):
        return None, "Too many failed attempts. Try again in a few minutes."
    user = get_db().users.find_one({"username": username})
    if user and check_password_hash(user["passwordHash"], password):
        _failed_logins.pop(key, None)
        return user, None
    _failed_logins[key].append(time.time())
    return None, "Incorrect username or password."


def api_guard():
    """before_request hook protecting every /api/ route."""
    if not request.path.startswith("/api/"):
        return None
    if request.method == "OPTIONS":
        return None

    if _valid_api_key():
        return None

    username = session.get("username")
    if not username:
        return jsonify({"error": "Authentication required. Log in or send a valid X-API-Key header."}), 401

    if request.method not in SAFE_METHODS:
        if session.get("role") != "admin":
            return jsonify({"error": "Forbidden: your role is read-only."}), 403
        if request.headers.get("X-Requested-With") != "dashboard":
            return jsonify({"error": "Missing X-Requested-With header."}), 403
    return None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("username"):
            return redirect(url_for("views.login", next=request.path))
        return view(*args, **kwargs)
    return wrapped
