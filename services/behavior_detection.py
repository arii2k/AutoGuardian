# services/behavior_detection.py
# --------------------------------------
# AutoGuardian Behavior-Based Detection
# --------------------------------------
# Tracks link clicks and risky actions to adjust user risk dynamically.
# Works with your existing SQLite database (autoguardian.db).

import os
import sqlite3
import json
from urllib.parse import urlparse

# Path to shared database
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DB = os.path.join(BASE_DIR, "data", "autoguardian.db")

# ---------------------------
# Table Schemas
# ---------------------------
SCHEMA = {
    "behavior_log": """
        CREATE TABLE IF NOT EXISTS behavior_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            email_id TEXT,
            url TEXT NOT NULL,
            domain TEXT NOT NULL,
            risk_hint TEXT,
            action TEXT NOT NULL,           -- 'click', 'blocked', 'warning_ack'
            user_agent TEXT,
            ip TEXT,
            extra TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """,
    "behavior_user_stats": """
        CREATE TABLE IF NOT EXISTS behavior_user_stats (
            user_id INTEGER PRIMARY KEY,
            risky_clicks_7d INTEGER NOT NULL DEFAULT 0,
            risky_clicks_30d INTEGER NOT NULL DEFAULT 0,
            total_clicks_30d INTEGER NOT NULL DEFAULT 0,
            last_updated TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
    """
}

# ---------------------------
# DB Utilities
# ---------------------------
def _connect(db_path: str = DEFAULT_DB):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_behavior_tables(db_path: str = DEFAULT_DB):
    """Ensure behavior tables exist (safe to call repeatedly)."""
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        for ddl in SCHEMA.values():
            cur.execute(ddl)
        conn.commit()
        print("✅ Behavior tables initialized or verified.")
    finally:
        conn.close()


def _domain_from_url(url: str) -> str:
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""


# ---------------------------
# Logging
# ---------------------------
def log_behavior_event(
    user_id: int,
    url: str,
    action: str,
    email_id: str = None,
    risk_hint: str = None,
    user_agent: str = None,
    ip: str = None,
    extra: dict | None = None,
    db_path: str = DEFAULT_DB
):
    """Insert a behavior event (click, blocked, etc.)."""
    if not url:
        return
    try:
        init_behavior_tables(db_path)
        domain = _domain_from_url(url)
        payload = json.dumps(extra or {}, ensure_ascii=False)
        conn = _connect(db_path)
        conn.execute(
            """
            INSERT INTO behavior_log (user_id, email_id, url, domain, risk_hint, action, user_agent, ip, extra)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (user_id, email_id, url, domain, risk_hint, action, user_agent, ip, payload)
        )
        conn.commit()
    except Exception as e:
        print(f"[behavior_detection] ⚠️ Failed to log event: {e}")
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ---------------------------
# Behavior Scoring
# ---------------------------
def compute_user_behavior_scores(user_id: int, db_path: str = DEFAULT_DB) -> dict:
    """Compute user's behavior KPIs and normalized risk score (0–100)."""
    try:
        init_behavior_tables(db_path)
        conn = _connect(db_path)
        cur = conn.cursor()

        # Risky clicks (7d)
        cur.execute(
            """
            SELECT COUNT(*) FROM behavior_log
            WHERE user_id=? AND action='click'
              AND risk_hint IN ('High','High Risk','Suspicious','Malicious')
              AND created_at >= datetime('now','-7 days')
            """,
            (user_id,)
        )
        risky_7d = cur.fetchone()[0]

        # Risky clicks (30d)
        cur.execute(
            """
            SELECT COUNT(*) FROM behavior_log
            WHERE user_id=? AND action='click'
              AND risk_hint IN ('High','High Risk','Suspicious','Malicious')
              AND created_at >= datetime('now','-30 days')
            """,
            (user_id,)
        )
        risky_30d = cur.fetchone()[0]

        # Total clicks (30d)
        cur.execute(
            """
            SELECT COUNT(*) FROM behavior_log
            WHERE user_id=? AND action='click'
              AND created_at >= datetime('now','-30 days')
            """,
            (user_id,)
        )
        total_30d = cur.fetchone()[0]

        # Update summary stats
        cur.execute(
            """
            INSERT INTO behavior_user_stats (user_id, risky_clicks_7d, risky_clicks_30d, total_clicks_30d, last_updated)
            VALUES (?,?,?,?,CURRENT_TIMESTAMP)
            ON CONFLICT(user_id) DO UPDATE SET
                risky_clicks_7d=excluded.risky_clicks_7d,
                risky_clicks_30d=excluded.risky_clicks_30d,
                total_clicks_30d=excluded.total_clicks_30d,
                last_updated=CURRENT_TIMESTAMP
            """,
            (user_id, risky_7d, risky_30d, total_30d)
        )
        conn.commit()
        conn.close()

        # Normalize score (recent risky clicks weigh more)
        raw_score = risky_7d * 0.2 + risky_30d * 0.05
        pct_score = min(100.0, round(raw_score * 100, 1))

        return {
            "risky_clicks_7d": risky_7d,
            "risky_clicks_30d": risky_30d,
            "total_clicks_30d": total_30d,
            "behavior_risk": pct_score
        }

    except Exception as e:
        print(f"[behavior_detection] ⚠️ Behavior scoring failed: {e}")
        return {
            "risky_clicks_7d": 0,
            "risky_clicks_30d": 0,
            "total_clicks_30d": 0,
            "behavior_risk": 0.0
        }


def behavior_adjust_risk(base_risk_level: str, behavior_score: float) -> str:
    """Map behavior_score (0–100) to a new risk level."""
    ladder = ["Safe", "Suspicious", "High"]
    try:
        idx = ladder.index("Suspicious" if base_risk_level == "Medium" else base_risk_level)
    except ValueError:
        idx = 0

    bump = 0
    if behavior_score >= 70:   # percent scale
        bump = 2
    elif behavior_score >= 40:
        bump = 1

    new_idx = max(0, min(len(ladder) - 1, idx + bump))
    return ladder[new_idx]


# -------------------------------------------------------------------
# ✅ Optional: Simulation helper for testing dashboard (non-zero %)
# -------------------------------------------------------------------
def seed_behavior_demo_data(db_path: str = DEFAULT_DB, user_id: int = 1):
    """Insert fake behavior log entries so the dashboard can display nonzero risk."""
    try:
        init_behavior_tables(db_path)
        conn = _connect(db_path)
        cur = conn.cursor()

        # Insert 5 risky clicks (past week)
        for _ in range(5):
            cur.execute(
                """
                INSERT INTO behavior_log (user_id, url, domain, risk_hint, action)
                VALUES (?, ?, ?, ?, 'click')
                """,
                (user_id, "https://phishy.example.com", "phishy.example.com", "High"),
            )

        # Insert 10 safe clicks (past month)
        for _ in range(10):
            cur.execute(
                """
                INSERT INTO behavior_log (user_id, url, domain, risk_hint, action)
                VALUES (?, ?, ?, ?, 'click')
                """,
                (user_id, "https://normal.site.com", "normal.site.com", "Safe"),
            )

        conn.commit()
        conn.close()
        print("✅ Demo behavior data seeded successfully.")
    except Exception as e:
        print(f"[behavior_detection] ⚠️ Demo seeding failed: {e}")
