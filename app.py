# app.py — AutoGuardian Backend (Enterprise, Hybrid Real-Time Gmail + Trusted Sender APIs)
# Fully integrated with helpers.py, startup tasks, scanner, Gmail push, PDF/CSV export, and trusted sender admin.

import os
import json
import sqlite3
import logging
import threading
import time
from datetime import datetime
from io import BytesIO

from dotenv import load_dotenv
load_dotenv()  # load .env file

from flask import (
    Flask,
    jsonify,
    render_template,
    request,
    session,
    redirect,
    url_for,
    send_file,
)
from flask_cors import CORS

# PDF exports
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib import colors

# ---------------------------
# Service imports
# ---------------------------
from services.ai_model import compute_threat_index
from services.gmail_service import (
    scan_and_label_gmail,
    fetch_recent_emails,
    start_user_auto_scan,
    manual_rescan,
    setup_gmail_watch,
    list_trusted_domains,
    add_trusted_domain,
    remove_trusted_domain,
)
from services.crypto_utils import encrypt_password, decrypt_password
from services.imap_service import scan_and_tag_imap
from services.helpers import get_scan_history, get_collective_analytics
from services.update_rules import get_last_fetch_info, update_rules
from services.paddle_service import get_subscription_for, ensure_subscription_active
from services.model_loader import load_models
from services.device_utils import get_device, optimize_torch_for_device
from services.similarity_index import rebuild_index
from services.scanner_runner import compute_collective_weights  # from scanner_runner.py


# ---------------------------
# Plan normalization helper
# ---------------------------
def normalize_plan(plan):
    """
    Convert backend plan codes ('free', 'pro', etc.)
    into frontend display names ('Free', 'Pro', etc.)
    """
    mapping = {
        "free": "Free",
        "starter": "Starter",
        "starter-imap": "Starter",
        "pro": "Pro",
        "business": "Business",
        "enterprise": "Enterprise",
    }
    if not plan:
        return "Free"
    return mapping.get(plan.lower(), "Free")


# ---------------------------
# Behavior detection
# ---------------------------
try:
    from services.behavior_detection import compute_user_behavior_scores, init_behavior_tables

    BEHAVIOR_ENABLED = True
except Exception as e:
    print(f"[app] ⚠️ Behavior module disabled: {e}")
    BEHAVIOR_ENABLED = False

    def init_behavior_tables(*_a, **_k):
        ...

    def compute_user_behavior_scores(*_a, **_k):
        return {"behavior_risk": 0.0}


# ---------------------------
# Logging setup
# ---------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "autoguardian.log")

logger = logging.getLogger("AutoGuardian")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.FileHandler) for h in logger.handlers):
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

# ---------------------------
# Device setup
# ---------------------------
DEVICE = get_device()
optimize_torch_for_device(DEVICE)

# ---------------------------
# Flask setup
# ---------------------------
app = Flask(__name__)
CORS(
    app,
    resources={r"/*": {"origins": ["http://localhost:3000", "http://127.0.0.1:3000"]}},
    supports_credentials=True,
)
app.secret_key = os.environ.get("FLASK_SECRET", "change_this_secret")

DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
REPORT_DIR = os.path.join(BASE_DIR, "reports")
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(REPORT_DIR, exist_ok=True)


def _get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------
# Database initialization
# ---------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Users table (auth system)
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
    # Ensure plan column exists (default: 'free')
    try:
        c.execute("PRAGMA table_info(users)")
        cols = [row[1] for row in c.fetchall()]
        if "plan" not in cols:
            c.execute("ALTER TABLE users ADD COLUMN plan TEXT DEFAULT 'free'")
            logger.info("✅ Added 'plan' column to users table.")
    except Exception as e:
        logger.warning(f"⚠️ Unable to ensure 'plan' column on users: {e}")

    # Scan history
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS scan_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email_id TEXT,
            timestamp TEXT,
            sender TEXT,
            subject TEXT,
            score INTEGER,
            matched_rules TEXT,
            memory_alert TEXT,
            community_alert TEXT,
            quarantine INTEGER DEFAULT 0,
            user_id INTEGER,
            risk_level TEXT DEFAULT 'Safe',
            ai_details TEXT
        )
    """
    )

    # Collective metrics
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS collective_metrics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email_id TEXT,
            sender TEXT,
            subject TEXT,
            score INTEGER,
            risk_level TEXT,
            quarantine INTEGER DEFAULT 0,
            timestamp TEXT,
            matched_rules TEXT
        )
    """
    )

    # User inbox configuration (IMAP inboxes)
    c.execute(
        """
        CREATE TABLE IF NOT EXISTS user_inboxes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            provider TEXT NOT NULL,         -- 'imap' or 'gmail' (future)
            imap_host TEXT,
            imap_username TEXT,
            imap_password TEXT,             -- stored encrypted via Fernet
            imap_port INTEGER,
            use_ssl INTEGER DEFAULT 1,
            status TEXT,
            last_scan TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """
    )
    # We do NOT enforce a unique index here to allow multiple inboxes per user by plan

    conn.commit()
    conn.close()

    try:
        init_behavior_tables(DB_PATH)
    except Exception as e:
        logger.warning(f"⚠️ Behavior table init failed: {e}")

    logger.info(
        "✅ Database initialized (users, scan_history, collective_metrics, user_inboxes)."
    )


# ---------------------------
# Inbox helpers
# ---------------------------
def get_inbox_for_user(user_id: int):
    """
    Return the first inbox for the user (used by Settings page),
    but we may have multiple inboxes in the future.
    """
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT * FROM user_inboxes WHERE user_id=? ORDER BY id LIMIT 1", (user_id,))
    row = c.fetchone()
    conn.close()
    return dict(row) if row else None


def count_inboxes_for_user(user_id: int) -> int:
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM user_inboxes WHERE user_id=?", (user_id,))
    count = c.fetchone()[0]
    conn.close()
    return int(count or 0)


def upsert_imap_inbox(
    user_id: int, host: str, username: str, password: str, port: int, use_ssl: bool
):
    """
    Insert a new IMAP inbox for this user.
    Password is now encrypted using Fernet.
    """
    encrypted_pw = encrypt_password(password)

    conn = _get_db()
    c = conn.cursor()
    c.execute(
        """
        INSERT INTO user_inboxes (
            user_id, provider, imap_host, imap_username,
            imap_password, imap_port, use_ssl, status, last_scan
        ) VALUES (?, 'imap', ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            user_id,
            host.strip(),
            username.strip(),
            encrypted_pw,     # <-- store encrypted version
            int(port),
            1 if use_ssl else 0,
            "connected",
            None,
        ),
    )
    conn.commit()
    conn.close()


def update_inbox_last_scan(user_id: int, status: str = "ok"):
    conn = _get_db()
    c = conn.cursor()
    c.execute(
        """
        UPDATE user_inboxes
        SET last_scan=?, status=?
        WHERE user_id=? AND id = (
            SELECT id FROM user_inboxes WHERE user_id=? ORDER BY id LIMIT 1
        )
        """,
        (datetime.utcnow().isoformat(), status, user_id, user_id),
    )
    conn.commit()
    conn.close()


def disconnect_inbox(user_id: int):
    conn = _get_db()
    c = conn.cursor()
    c.execute("DELETE FROM user_inboxes WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()


def get_user_plan(user_id: int) -> str:
    """
    Return the user's plan string, defaulting to 'free' if missing.
    Plan values for Option A:
      - free
      - starter
      - pro
      - business
      - enterprise
    """
    conn = _get_db()
    c = conn.cursor()
    c.execute("SELECT plan FROM users WHERE id=?", (user_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return "free"
    plan = row["plan"] if isinstance(row, sqlite3.Row) else row[0]
    return (plan or "free").lower()


# Plan -> IMAP inbox limits (Option A)
PLAN_INBOX_LIMITS = {
    "free": 0,
    "starter": 1,
    "pro": 2,
    "business": 5,
    "enterprise": 999,
}


# ---------------------------
# Auth blueprint
# ---------------------------
from services.auth import auth_bp

app.register_blueprint(auth_bp, url_prefix="/auth")


# ---------------------------
# Startup Tasks (run once at app startup)
# ---------------------------
def run_startup_tasks():
    """
    Run all modules that don't execute automatically.
    """
    try:
        logger.info("🚀 Running startup tasks...")

        # 1️⃣ Update rules
        try:
            update_rules()
            logger.info("✅ update_rules completed")
        except Exception as e:
            logger.warning(f"⚠️ update_rules failed: {e}")

        # 2️⃣ Rebuild similarity index (pass recent emails)
        try:
            emails_to_index = fetch_recent_emails(max_results=50)
            if emails_to_index:
                rebuild_index(emails_to_index)
                logger.info("✅ rebuild_index completed")
            else:
                logger.info("ℹ️ No emails to index for rebuild_index")
        except Exception as e:
            logger.warning(f"⚠️ rebuild_index failed: {e}")

        # 3️⃣ Compute collective AI weights
        try:
            compute_collective_weights()
            logger.info("✅ compute_collective_weights completed")
        except Exception as e:
            logger.warning(f"⚠️ compute_collective_weights failed: {e}")

    except Exception as e:
        logger.exception(f"Startup tasks failed: {e}")


# ---------------------------
# Routes
# ---------------------------
@app.route("/")
def index():
    return (
        redirect(url_for("dashboard"))
        if "user_id" in session
        else redirect(url_for("auth.login"))
    )


@app.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    user_id = session.get("user_id", 1)
    history = get_scan_history(user_id) or []
    collective_stats = get_collective_analytics() or []
    last_rules_fetch = get_last_fetch_info()

    threat_index = compute_threat_index(scan_results=history, device=DEVICE)
    # subscription: use logged-in email when wired; placeholder for now
    paddle_sub = get_subscription_for("me@example.com")
    behavior_summary = (
        compute_user_behavior_scores(user_id)
        if BEHAVIOR_ENABLED
        else {"behavior_risk": 0.0}
    )

    return render_template(
        "dashboard.html",
        scan_history=history,
        collective_stats=collective_stats,
        last_rules_fetch=last_rules_fetch,
        threat_index=threat_index,
        paddle_sub=paddle_sub,
        behavior=behavior_summary,
    )


# ---------------------------
# Dashboard API (AI + Behavior)
# ---------------------------
@app.route("/api/dashboard-data")
def api_dashboard_data():
    try:
        user_id = session.get("user_id", 1)
        history = get_scan_history(user_id=user_id, limit=200)
        collective_stats = get_collective_analytics(limit=50)

        ai_scores = []
        for e in history:
            ai_details = e.get("ai_details")
            if ai_details:
                try:
                    ai_json = (
                        json.loads(ai_details)
                        if isinstance(ai_details, str)
                        else ai_details
                    )
                    s = float(ai_json.get("hybrid_score", 0))
                    if s > 0:
                        ai_scores.append(s)
                except Exception as err:
                    logger.warning(f"[dashboard-data] AI parse error: {err}")

        threat_index = round(sum(ai_scores) / len(ai_scores), 2) if ai_scores else 0.0
        threat_index = min(max(threat_index, 0), 100)

        behavior = {"behavior_risk": 0.0}
        if BEHAVIOR_ENABLED:
            behavior = compute_user_behavior_scores(user_id) or {}
            val = float(behavior.get("behavior_risk", 0.0))
            if val <= 1.0:
                val *= 100
            behavior["behavior_risk"] = round(min(max(val, 0), 100), 2)

        payload = {
            "recent_scans": history,
            "collective_stats": {
                "threat_index": threat_index,
                "records": collective_stats.get("records", []),
                "top_senders": collective_stats.get("top_senders", []),
                "top_rules": collective_stats.get("top_rules", []),
                "high_risk_trend": collective_stats.get("high_risk_trend", []),
            },
            "behavior": behavior,
        }

        logger.info(
            f"[API] threat_index={threat_index}%, behavior={behavior['behavior_risk']}%"
        )
        return jsonify(payload), 200

    except Exception as e:
        logger.exception("dashboard-data error")
        return jsonify({"error": str(e)}), 500


# ---------------------------
# Current user API (/api/me)
# ---------------------------
@app.route("/api/me", methods=["GET"])
def api_me():
    """
    Return current logged-in user info + plan + subscription + inbox status.
    Matches Settings.js expectations.
    """
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = session["user_id"]

    conn = _get_db()
    c = conn.cursor()
    c.execute(
        "SELECT id, username, email, created_at, plan FROM users WHERE id=?",
        (user_id,),
    )
    row = c.fetchone()
    conn.close()

    if not row:
        return jsonify({"error": "User not found"}), 404

    email = row["email"]
    plan = (row["plan"] or "free").lower()
    created_at = row["created_at"]

    inbox = get_inbox_for_user(user_id)
    if inbox:
        inbox_payload = {
            "connected": True,
            "provider": inbox.get("provider"),
            "email_address": inbox.get("imap_username") or "",
            "status": inbox.get("status") or "unknown",
            "last_scan": inbox.get("last_scan"),
        }
    else:
        inbox_payload = {
            "connected": False,
            "provider": None,
            "email_address": "",
            "status": "disconnected",
            "last_scan": None,
        }

    # Subscription (mock / Paddle)
    sub = get_subscription_for(email)
    sub_active = bool(getattr(sub, "active", False)) if sub else False

    return jsonify(
        {
            "id": row["id"],
            "username": row["username"],
            "email": email,
            "plan": normalize_plan(plan),
            "subscription_active": sub_active,
            "joined": created_at,
            "inbox": inbox_payload,
        }
    )


# ---------------------------
# Inbox API (Settings page)
# ---------------------------
@app.route("/api/inbox-status", methods=["GET"])
def api_inbox_status():
    """
    Returns current inbox status for the logged-in user.
    """
    if "user_id" not in session:
        return jsonify(
            {
                "connected": False,
                "provider": None,
                "email_address": "",
                "status": "not_authenticated",
                "last_scan": None,
            }
        ), 401

    user_id = session["user_id"]
    inbox = get_inbox_for_user(user_id)
    if not inbox:
        return jsonify(
            {
                "connected": False,
                "provider": None,
                "email_address": "",
                "status": "disconnected",
                "last_scan": None,
            }
        )

    return jsonify(
        {
            "connected": True,
            "provider": inbox.get("provider"),
            "email_address": inbox.get("imap_username") or "",
            "status": inbox.get("status") or "unknown",
            "last_scan": inbox.get("last_scan"),
        }
    )


@app.route("/api/link-imap", methods=["POST"])
def api_link_imap():
    """
    Connect an IMAP inbox and trigger an initial scan.
    Restricted by user plan (Option A: free/starter/pro/business/enterprise).
    """
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401

    user_id = session["user_id"]
    data = request.get_json() or {}

    host = (data.get("host") or "").strip()
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    port = int(data.get("port") or 993)
    use_ssl = bool(data.get("use_ssl", True))

    if not host or not username or not password:
        return jsonify({"error": "Missing host/username/password"}), 400

    # Plan-based access control for IMAP
    plan = get_user_plan(user_id)  # already lowercased
    max_inboxes = PLAN_INBOX_LIMITS.get(plan, 0)

    if max_inboxes <= 0:
        return (
            jsonify(
                {
                    "error": "Your current plan does not allow IMAP inboxes. Please upgrade your plan.",
                    "plan": plan,
                }
            ),
            403,
        )

    current_count = count_inboxes_for_user(user_id)
    if current_count >= max_inboxes:
        return (
            jsonify(
                {
                    "error": f"Plan '{plan}' allows only {max_inboxes} inbox(es).",
                    "plan": plan,
                    "current_inboxes": current_count,
                    "max_inboxes": max_inboxes,
                }
            ),
            403,
        )

    # Create new IMAP inbox row (stores encrypted password)
    upsert_imap_inbox(user_id, host, username, password, port, use_ssl)

    try:
        # For the very first scan we still have plaintext password from the request.
        # Later background jobs will read from DB and use decrypt_password().
        results = scan_and_tag_imap(
            host=host,
            username=username,
            password=password,  # plaintext from client
            user_email=username,
            user_id=user_id,
            folder="INBOX",
            port=port,
            use_ssl=use_ssl,
            force=False,
        )

        update_inbox_last_scan(user_id, status="ok")
        return jsonify({"ok": True, "scanned": len(results)}), 200

    except Exception as e:
        logger.exception("IMAP link/scan failed")
        update_inbox_last_scan(user_id, status=f"error: {e}")
        return jsonify({"error": f"IMAP scan failed: {e}"}), 500


@app.route("/api/disconnect-inbox", methods=["POST"])
def api_disconnect_inbox():
    if "user_id" not in session:
        return jsonify({"error": "Not authenticated"}), 401
    user_id = session["user_id"]
    disconnect_inbox(user_id)
    return jsonify({"ok": True})


# ---------------------------
# Trusted Sender Admin API
# ---------------------------
@app.get("/api/trusted/list")
def api_trusted_list():
    try:
        cache = list_trusted_domains()
        out = [{"domain": k, **v} for k, v in cache.items()]
        return jsonify({"trusted": out}), 200
    except Exception as e:
        logger.exception("trusted list failed")
        return jsonify({"error": str(e)}), 500


@app.post("/api/trusted/add")
def api_trusted_add():
    try:
        data = request.get_json(force=True) or {}
        domain = data.get("domain") or (
            data.get("email", "").split("@")[-1] if data.get("email") else ""
        )
        if not domain:
            return jsonify({"error": "domain or email required"}), 400
        ok = add_trusted_domain(domain, source="manual")
        return jsonify({"ok": bool(ok)}), 200
    except Exception as e:
        logger.exception("trusted add failed")
        return jsonify({"error": str(e)}), 500


@app.post("/api/trusted/remove")
def api_trusted_remove():
    try:
        data = request.get_json(force=True) or {}
        domain = data.get("domain") or (
            data.get("email", "").split("@")[-1] if data.get("email") else ""
        )
        if not domain:
            return jsonify({"error": "domain or email required"}), 400
        ok = remove_trusted_domain(domain)
        return jsonify({"ok": bool(ok)}), 200
    except Exception as e:
        logger.exception("trusted remove failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------
# PDF/CSV Export
# ---------------------------
def generate_pdf_report(filename=None):
    try:
        data = get_collective_analytics(limit=50)
        records = data.get("records", [])
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer)
        styles = getSampleStyleSheet()
        story = []

        story.append(
            Paragraph("<b>AutoGuardian AI — Monthly Report</b>", styles["Title"])
        )
        story.append(Spacer(1, 12))
        story.append(
            Paragraph(
                "Generated on "
                + datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                styles["Normal"],
            )
        )
        story.append(Spacer(1, 18))

        if not records:
            story.append(Paragraph("No collective data found.", styles["Normal"]))
        else:
            headers = list(records[0].keys())
            rows = [headers] + [
                [str(r.get(h, "")) for h in headers] for r in records
            ]
            table = Table(rows, repeatRows=1)
            table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e3a8a")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                    ]
                )
            )
            story.append(table)

        doc.build(story)
        pdf = buffer.getvalue()
        buffer.close()

        if filename:
            with open(os.path.join(REPORT_DIR, filename), "wb") as f:
                f.write(pdf)
        return pdf
    except Exception as e:
        logger.exception("PDF generation failed")
        return None


@app.route("/api/export-pdf", methods=["GET", "POST"])
def export_pdf():
    pdf = generate_pdf_report()
    if not pdf:
        return jsonify({"error": "Failed to create PDF"}), 500
    return send_file(
        BytesIO(pdf),
        as_attachment=True,
        download_name="AutoGuardian_Report.pdf",
        mimetype="application/pdf",
    )


@app.route("/api/export-csv")
def export_csv():
    try:
        data = get_collective_analytics(limit=200)
        records = data.get("records", [])
        if not records:
            return jsonify({"error": "No data"}), 404
        headers = list(records[0].keys())
        csv_lines = [",".join(headers)]
        for r in records:
            csv_lines.append(",".join(json.dumps(r.get(h, "")) for h in headers))
        csv_data = "\n".join(csv_lines).encode("utf-8")
        return send_file(
            BytesIO(csv_data),
            as_attachment=True,
            download_name="collective_report.csv",
            mimetype="text/csv",
        )
    except Exception as e:
        logger.exception("CSV export failed")
        return jsonify({"error": "CSV export failed"}), 500


# ---------------------------
# Monthly auto-report (PDF)
# ---------------------------
def monthly_report_worker():
    while True:
        now = datetime.now()
        if now.day == 1 and now.hour == 0:
            filename = f"AutoGuardian_Report_{now.strftime('%Y_%m')}.pdf"
            _ = generate_pdf_report(filename)
            logger.info(f"📅 Monthly report generated: {filename}")
            time.sleep(86400)
        else:
            time.sleep(3600)


threading.Thread(target=monthly_report_worker, daemon=True).start()


# ---------------------------
# Gmail Push Webhook (real-time)
# ---------------------------
@app.route("/gmail/notify", methods=["POST"])
def gmail_notify():
    try:
        payload = request.get_json(silent=True) or {}
        logger.info(f"📩 Gmail push notification received: {payload}")

        threading.Thread(
            target=scan_and_label_gmail,
            kwargs={"max_results": 5, "user_email": "me@example.com", "user_id": 1},
            daemon=True,
        ).start()
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.exception("Gmail push notification failed")
        return jsonify({"error": str(e)}), 500


# ---------------------------
# Rescan endpoints
# ---------------------------
_rescan_lock = threading.Lock()
_rescan_thread = None


def _run_rescan_thread():
    try:
        logger.info("🔄 Rescan started (thread-safe)")
        manual_rescan(user_id=1, user_email="me@example.com", limit=10)
        logger.info("✅ Rescan finished.")
    except Exception as e:
        logger.exception("Rescan failed")


@app.post("/api/rescan")
def api_rescan():
    global _rescan_thread
    with _rescan_lock:
        if _rescan_thread and _rescan_thread.is_alive():
            return jsonify({"ok": True, "status": "already-running"}), 202
        _rescan_thread = threading.Thread(target=_run_rescan_thread, daemon=True)
        _rescan_thread.start()
    return jsonify({"ok": True, "status": "started"}), 202


@app.post("/rescan")
def rescan_alias():
    return api_rescan()


# ---------------------------
# Main
# ---------------------------
if __name__ == "__main__":
    init_db()
    run_startup_tasks()  # ⚡ Run modules that don't auto-execute
    try:
        load_models(device=DEVICE)
        logger.info("🤖 AI models preloaded successfully.")
    except Exception as e:
        logger.warning(f"⚠️ Model preload failed: {e}")

    # For now, auto-scan for a default Gmail account (dev)
    start_user_auto_scan(user_id=1, user_email="me@example.com", poll_interval=120)

    try:
        setup_gmail_watch("me@example.com")
    except Exception as e:
        logger.warning(f"⚠️ Gmail push setup failed: {e}")

    logger.info("🚀 AutoGuardian backend (hybrid real-time) started.")
    app.run(debug=True, host="127.0.0.1", port=5000)
