# services/auth.py — Authentication & Subscription Guard for AutoGuardian
# ----------------------------------------------------------------------
# - Secure user registration & login (Flask sessions)
# - JSON-first API for React
# - SQLite users table (Postgres-ready later)
# - Subscription plan updates via /auth/subscribe
# - Mock Paddle subscription workflow
# - Plan normalization + session updates
#
# Routes:
#   GET/POST  /auth/login
#   GET/POST  /auth/register
#   GET/POST  /auth/logout
#   GET/POST  /auth/subscribe
#   GET       /auth/mock_complete


from flask import (
    Blueprint,
    request,
    redirect,
    session,
    url_for,
    flash,
    jsonify,
)
from services.paddle_service import (
    ensure_subscription_active,
    create_mock_subscription,
    activate_mock_subscription,
    get_subscription_for,
)
import sqlite3
import os
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

auth_bp = Blueprint("auth", __name__, template_folder="../templates")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "data", "autoguardian.db")


# ---------------------------
# Plan normalization (UI-friendly)
# ---------------------------
def normalize_plan(plan: str) -> str:
    plan = (plan or "").lower()
    mapping = {
        "free": "Free",
        "starter-imap": "Starter",
        "pro": "Pro",
        "business": "Business",
        "enterprise": "Enterprise",
    }
    return mapping.get(plan, "Free")


# ---------------------------
# Dev test user (optional)
# ---------------------------
TEST_USER = {"email": "test@example.com", "password": "test123"}
ALLOW_TEST_USER = os.environ.get("ALLOW_TEST_USER", "0") == "1"


# ---------------------------
# DB helpers
# ---------------------------
def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_users_table():
    conn = _get_db()
    c = conn.cursor()
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT,
            email TEXT UNIQUE,
            password_hash TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def get_user_by_email(email: str):
    _ensure_users_table()
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT id, username, email, password_hash FROM users WHERE email=?", (email,))
    row = c.fetchone()
    conn.close()
    return row


def create_user(email: str, password: str):
    if not email or not password:
        return None, "Email and password are required."

    if len(password) < 8:
        return None, "Password must be at least 8 characters long."

    email = email.strip().lower()
    username = email.split("@")[0]

    existing = get_user_by_email(email)
    if existing:
        return None, "An account with this email already exists."

    try:
        conn = _get_db()
        c = conn.cursor()
        hashed = generate_password_hash(password)

        c.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (?, ?, ?)",
            (username, email, hashed),
        )

        conn.commit()
        user_id = c.lastrowid
        conn.close()
        return user_id, None

    except Exception as e:
        return None, f"Failed to create user: {e}"


# ---------------------------
# Session helpers
# ---------------------------
def _login_user(user_row, subscription_active: bool):
    session["user"] = {"email": user_row["email"], "username": user_row["username"]}
    session["user_id"] = int(user_row["id"])
    session["subscription_active"] = bool(subscription_active)


def _logout_user():
    session.pop("user", None)
    session.pop("user_id", None)
    session.pop("subscription_active", None)


# ---------------------------
# Registration (JSON-first)
# ---------------------------
@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return jsonify({"message": "Use POST JSON to register"}), 200

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()
    confirm = (data.get("confirm_password") or password).strip()

    if not email or not password or not confirm:
        return jsonify({"error": "Fill in all fields."}), 400

    if password != confirm:
        return jsonify({"error": "Passwords do not match."}), 400

    user_id, err = create_user(email, password)
    if err:
        return jsonify({"error": err}), 400

    sub = ensure_subscription_active(email)
    user_row = get_user_by_email(email)
    _login_user(user_row, subscription_active=sub.active)

    return jsonify({"ok": True, "user_id": user_id, "email": email}), 200


# ---------------------------
# Login (JSON-first)
# ---------------------------
@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return jsonify({"message": "Use POST JSON to login"}), 200

    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = (data.get("password") or "").strip()

    if not email or not password:
        return jsonify({"error": "Enter both email and password"}), 400

    user = get_user_by_email(email)

    if user and check_password_hash(user["password_hash"], password):
        sub = ensure_subscription_active(email)
        _login_user(user, subscription_active=sub.active)
        return jsonify({"ok": True, "user_id": int(user["id"]), "email": email}), 200

    if ALLOW_TEST_USER and email == TEST_USER["email"] and password == TEST_USER["password"]:
        existing = get_user_by_email(email)
        if not existing:
            create_user(email, password)
        user = get_user_by_email(email)
        sub = ensure_subscription_active(email)
        _login_user(user, subscription_active=sub.active)
        return jsonify({"ok": True, "user_id": int(user["id"]), "email": email}), 200

    return jsonify({"error": "Invalid email or password"}), 401


# ---------------------------
# Logout
# ---------------------------
@auth_bp.route("/logout", methods=["GET", "POST"])
def logout():
    _logout_user()
    return jsonify({"ok": True}), 200


# ---------------------------
# Subscribe (Pricing -> DB update)
# ---------------------------
@auth_bp.route("/subscribe", methods=["GET", "POST"])
def subscribe():
    # GET = redirect to React Pricing page
    if request.method == "GET":
        return redirect("http://127.0.0.1:3000/pricing")

    # POST = JSON update
    if "user_id" not in session:
        return jsonify({"error": "You must log in first"}), 401

    data = request.get_json(silent=True) or {}
    new_plan = (data.get("plan") or "").strip().lower()

    allowed = ["free", "starter-imap", "pro", "business", "enterprise"]
    if new_plan not in allowed:
        return jsonify({"error": "Invalid plan"}), 400

    user_id = session["user_id"]

    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT email FROM users WHERE id=?", (user_id,))
    row = c.fetchone()

    if not row:
        conn.close()
        return jsonify({"error": "User not found"}), 404

    email = row["email"]

    try:
        c.execute("UPDATE users SET plan=? WHERE id=?", (new_plan, user_id))
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({"error": f"Failed to update plan: {e}"}), 500

    conn.close()

    # Simulate Paddle subscription immediately
    try:
        sub = create_mock_subscription(email)
        activate_mock_subscription(email, sub.checkout_id)
        session["subscription_active"] = True
    except Exception:
        sub = ensure_subscription_active(email)
        session["subscription_active"] = bool(getattr(sub, "active", False))

    return jsonify(
        {
            "ok": True,
            "plan": normalize_plan(new_plan),
            "subscription_active": session["subscription_active"],
        }
    ), 200


# ---------------------------
# Mock Paddle completion
# ---------------------------
@auth_bp.route("/mock_complete", methods=["GET"])
def mock_complete():
    email = request.args.get("email", "").strip().lower()
    checkout_id = request.args.get("checkout_id")

    if not email:
        return "Missing email", 400

    logged_in = session.get("user")
    if logged_in:
        if logged_in.get("email") != email:
            flash("Logged-in user mismatch")
            return redirect(url_for("dashboard"))

    rec = activate_mock_subscription(email, checkout_id)
    if not rec:
        flash("Mock subscription failed")
        return redirect(url_for("auth.subscribe"))

    session["subscription_active"] = True
    flash("Subscription activated (mock)")
    return redirect(url_for("dashboard"))
