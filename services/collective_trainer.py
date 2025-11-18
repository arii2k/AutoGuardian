# services/collective_trainer.py — Premium SaaS-level collective weights updater
import json
import sqlite3
import os
from collections import Counter
from datetime import datetime, timezone, timedelta
from threading import Lock

# ---------------------------
# Paths & Config
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
WEIGHTS_FILE = os.path.join(DATA_DIR, "collective_ai_weights.json")

# Lock for thread-safe writes
_weights_lock = Lock()

# ---------------------------
# Core weight update
# ---------------------------
def update_collective_ai_weights(user_id=None):
    """
    Recalculate adaptive sender/rule weights from collective_metrics.
    Supports multi-user SaaS (optional user_id filter).
    """
    if not os.path.exists(DB_PATH):
        print("❌ No database found, skipping weight update.")
        return {}

    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if user_id:
        c.execute("SELECT sender, matched_rules, risk_level FROM collective_metrics WHERE user_id=?", (user_id,))
    else:
        c.execute("SELECT sender, matched_rules, risk_level FROM collective_metrics")
    rows = c.fetchall()
    conn.close()

    sender_counter = Counter()
    rule_counter = Counter()

    for sender, rules, risk in rows:
        if not sender:
            continue

        # SaaS premium weighting scheme
        delta = 0
        if risk.lower() == "high":
            delta = 1.5
        elif risk.lower() == "medium":
            delta = 0.7
        elif risk.lower() == "low":
            delta = 0.1

        if delta:
            sender_counter[sender] += delta
            if rules:
                for rule in str(rules).split(","):
                    r = rule.strip()
                    if r:
                        rule_counter[r] += delta

    weights = {
        "senders": {s: round(1 + (count / 10), 2) for s, count in sender_counter.items()},
        "rules": {r: round(1 + (count / 20), 2) for r, count in rule_counter.items()},
        "last_updated": datetime.now(timezone.utc).isoformat()
    }

    # Thread-safe write
    with _weights_lock:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(weights, f, indent=2, ensure_ascii=False)

    print(f"✅ Updated {WEIGHTS_FILE} — {len(weights['senders'])} senders, {len(weights['rules'])} rules.")
    return weights

# ---------------------------
# Prune old metrics
# ---------------------------
def prune_collective_metrics(max_age_days: int = 365, user_id=None):
    """
    Delete collective_metrics rows older than max_age_days.
    Supports optional multi-user pruning.
    """
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=max_age_days)).isoformat()
    try:
        if user_id:
            c.execute("DELETE FROM collective_metrics WHERE timestamp < ? AND user_id=?", (cutoff, user_id))
        else:
            c.execute("DELETE FROM collective_metrics WHERE timestamp < ?", (cutoff,))
        removed = c.rowcount if c.rowcount else 0
        conn.commit()
    except Exception:
        removed = 0
    finally:
        conn.close()

    if removed:
        print(f"🧹 Pruned {removed} old rows from collective_metrics (>{max_age_days} days).")
    return removed

# ---------------------------
# Scheduler-friendly wrapper
# ---------------------------
def scheduled_collective_update(max_age_days: int = 365, user_id=None):
    """
    Call from scheduler or background task:
      - prune old rows (optional)
      - recompute weights (multi-user aware)
    """
    try:
        prune_collective_metrics(max_age_days=max_age_days, user_id=user_id)
    except Exception as e:
        print(f"⚠️ Prune failed: {e}")
    return update_collective_ai_weights(user_id=user_id)

# ---------------------------
# Incremental merge helper
# ---------------------------
def merge_new_metrics(new_metrics, user_id=None):
    """
    Accept new metrics batch (list of dicts) and merge them into DB safely.
    Each metric: {"email_id": str, "sender": str, "matched_rules": str, "score": float, "risk_level": str}
    """
    if not new_metrics:
        return
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        for metric in new_metrics:
            uid = user_id or metric.get("user_id", 1)
            c.execute("""
                INSERT INTO collective_metrics (user_id, email_id, sender, subject, score, risk_level, quarantine, timestamp, matched_rules)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                uid,
                metric.get("email_id"),
                metric.get("sender"),
                metric.get("subject", ""),
                metric.get("score", 0),
                metric.get("risk_level", "Safe"),
                metric.get("quarantine", 0),
                metric.get("timestamp") or datetime.now(timezone.utc).isoformat(),
                metric.get("matched_rules", "")
            ))
        conn.commit()
    except Exception as e:
        print(f"❌ Failed to merge new metrics: {e}")
    finally:
        conn.close()

# ---------------------------
# Self-test / CLI
# ---------------------------
if __name__ == "__main__":
    print("🚀 Running premium collective AI trainer self-test...")
    scheduled_collective_update()
