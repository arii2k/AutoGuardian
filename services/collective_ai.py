# services/collective_ai.py — AI-weighted Collective Learning Engine
import sqlite3
import json
import os
from datetime import datetime, timezone

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
WEIGHTS_FILE = os.path.join(DATA_DIR, "collective_ai_weights.json")

def compute_collective_weights():
    """
    Compute adaptive weights for risky senders and rules from the collective_metrics table.
    Higher frequency and higher average score = higher influence.
    """
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()

    # Aggregate sender risk statistics
    c.execute("""
        SELECT sender, AVG(score) AS avg_score, COUNT(*) AS cnt
        FROM collective_metrics
        WHERE sender IS NOT NULL AND sender <> ''
        GROUP BY sender
    """)
    sender_rows = c.fetchall()

    # Aggregate rule risk statistics
    c.execute("""
        SELECT matched_rules, AVG(score), COUNT(*)
        FROM collective_metrics
        WHERE matched_rules IS NOT NULL AND matched_rules <> ''
        GROUP BY matched_rules
    """)
    rule_rows = c.fetchall()
    conn.close()

    sender_weights = {}
    for sender, avg, cnt in sender_rows:
        # Weight grows with both score and frequency, capped at ×2.5
        weight = round(min(2.5, 1.0 + (avg / 10.0) + (cnt / 50.0)), 2)
        sender_weights[sender] = weight

    rule_weights = {}
    for rules, avg, cnt in rule_rows:
        for rule in (rules or "").split(","):
            rule = rule.strip()
            if not rule:
                continue
            weight = round(min(2.5, 1.0 + (avg / 10.0) + (cnt / 50.0)), 2)
            rule_weights[rule] = max(weight, rule_weights.get(rule, 1.0))

    weights = {
        "updated": datetime.now(timezone.utc).isoformat(),
        "senders": sender_weights,
        "rules": rule_weights,
    }

    with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
        json.dump(weights, f, indent=2, ensure_ascii=False)

    print(f"✅ Collective AI weights updated — {len(sender_weights)} senders, {len(rule_weights)} rules.")
    return weights


def load_collective_weights():
    """Return weights dict if file exists, else empty structure."""
    if not os.path.exists(WEIGHTS_FILE):
        return {"senders": {}, "rules": {}}
    try:
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return {
                "senders": data.get("senders", {}),
                "rules": data.get("rules", {}),
            }
    except Exception:
        return {"senders": {}, "rules": {}}
