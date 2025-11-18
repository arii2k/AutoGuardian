# services/helpers.py — Premium SaaS-ready analytics & startup utilities
import sqlite3
import os
import json
from typing import List, Dict, Any
from collections import defaultdict, Counter
from datetime import datetime
from threading import Lock

# ---------------------------
# Base paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------
# Thread-safe DB & JSON lock
# ---------------------------
_db_lock = Lock()
_json_lock = Lock()

# ---------------------------
# Safe JSON parser
# ---------------------------
def _safe_json_parse(value: Any):
    """Safely parse JSON strings or return original value."""
    if not value:
        return {}
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value)
    except Exception:
        return {}

# ---------------------------
# 📨 User scan history
# ---------------------------
def get_scan_history(user_id: int, limit: int = 100) -> List[Dict]:
    """Return recent scan history for a user, formatted for SaaS dashboard."""
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT id, email_id, timestamp, sender, subject, score,
                   matched_rules, memory_alert, community_alert,
                   quarantine, risk_level, ai_details
            FROM scan_history
            WHERE user_id = ?
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (user_id, limit),
        )
        rows = []
        for r in c.fetchall():
            item = dict(r)
            item["email_from"] = item.pop("sender", "")
            item["email_subject"] = item.pop("subject", "")
            item["ai_details"] = _safe_json_parse(item.get("ai_details"))
            item["score"] = float(item.get("score") or 0)
            item["quarantine"] = int(item.get("quarantine") or 0)
            item["risk_level"] = item.get("risk_level") or "Safe"
            rows.append(item)
        conn.close()
    return rows

# ---------------------------
# 📊 Collective Analytics
# ---------------------------
def get_collective_analytics(limit: int = 50) -> Dict[str, List[Dict]]:
    """
    Return structured analytics for SaaS dashboard:
      - Top Risky Senders
      - Top Rules
      - High-Risk Trend
    """
    with _db_lock:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        c = conn.cursor()
        c.execute(
            """
            SELECT sender, subject, matched_rules, score, risk_level, timestamp
            FROM collective_metrics
            ORDER BY datetime(timestamp) DESC
            LIMIT ?
            """,
            (limit,),
        )
        records = [dict(r) for r in c.fetchall()]
        conn.close()

    sender_counts = Counter()
    rule_counts = Counter()
    high_risk_trend = defaultdict(int)

    for r in records:
        sender = r.get("sender") or "Unknown"
        risk = (r.get("risk_level") or "").lower()
        matched = r.get("matched_rules") or ""
        timestamp = r.get("timestamp") or ""

        if risk in ("high", "critical", "suspicious"):
            sender_counts[sender] += 1
            if timestamp:
                date = timestamp.split("T")[0] if "T" in timestamp else timestamp.split(" ")[0]
                high_risk_trend[date] += 1

        if matched:
            try:
                parsed = json.loads(matched) if matched.strip().startswith("[") else matched.split(",")
                if isinstance(parsed, list):
                    for rule in parsed:
                        rule_name = str(rule).strip()
                        if rule_name:
                            rule_counts[rule_name] += 1
                else:
                    for rule in str(parsed).split(","):
                        rule_name = rule.strip()
                        if rule_name:
                            rule_counts[rule_name] += 1
            except Exception:
                for rule in matched.split(","):
                    rule_name = rule.strip()
                    if rule_name:
                        rule_counts[rule_name] += 1

    top_senders = [{"sender": k, "count": v} for k, v in sender_counts.most_common(10)]
    top_rules = [{"rule": k, "count": v} for k, v in rule_counts.most_common(10)]
    high_risk_trend_sorted = sorted(high_risk_trend.items(), key=lambda x: x[0])

    return {
        "records": records,
        "top_senders": top_senders,
        "top_rules": top_rules,
        "high_risk_trend": high_risk_trend_sorted,
    }

# ---------------------------
# 💾 Scan persistence
# ---------------------------
def save_last_scan(emails: List[Dict]):
    """Save a JSON snapshot of the last scan, thread-safe."""
    with _json_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        path = os.path.join(DATA_DIR, "last_scan.json")
        json.dump(
            {
                "timestamp": emails[0].get("timestamp") if emails else "",
                "emails_scanned": len(emails),
                "emails": emails,
            },
            open(path, "w", encoding="utf-8"),
            indent=2,
        )

def load_last_scan() -> Dict:
    """Load last scan snapshot, thread-safe."""
    path = os.path.join(DATA_DIR, "last_scan.json")
    if not os.path.exists(path):
        return {}
    with _json_lock:
        return json.load(open(path, "r", encoding="utf-8"))

# ---------------------------
# 🚀 Startup tasks
# ---------------------------
try:
    from services.update_rules import update_rules
except Exception:
    def update_rules(): pass

try:
    from services.similarity_index import rebuild_index
except Exception:
    def rebuild_index(): pass

try:
    from services.collective_trainer import update_collective_ai_weights
except Exception:
    def update_collective_ai_weights(): pass

def run_startup_tasks():
    """
    Execute modules that normally do not run automatically.
    Suitable for SaaS multi-user startup.
    """
    try:
        update_rules()
        print("✅ update_rules executed")
    except Exception as e:
        print(f"❌ update_rules failed: {e}")

    try:
        rebuild_index()
        print("✅ rebuild_index executed")
    except Exception as e:
        print(f"❌ rebuild_index failed: {e}")

    try:
        update_collective_ai_weights()
        print("✅ update_collective_ai_weights executed")
    except Exception as e:
        print(f"❌ update_collective_ai_weights failed: {e}")
