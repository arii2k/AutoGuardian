# services/scanner_runner.py — Premium SaaS-ready AutoGuardian Scanner
import os
import logging
import atexit
import time
import json
import sqlite3
from datetime import datetime, timezone
from threading import Thread

from services.scanner import start_auto_scan_scheduler
from services.helpers import load_last_scan, save_last_scan
from services.device_utils import get_device, optimize_torch_for_device

# 🆕 Behavior-based detection (init + optional KPI logging)
try:
    from services.behavior_detection import init_behavior_tables, compute_user_behavior_scores
except Exception:
    def init_behavior_tables(*_a, **_k):
        pass
    def compute_user_behavior_scores(*_a, **_k):
        return {"risky_clicks_7d": 0, "risky_clicks_30d": 0, "total_clicks_30d": 0, "behavior_risk": 0.0}

# 🆕 Central trainer fallback
try:
    from services.collective_trainer import update_collective_ai_weights
except Exception:
    update_collective_ai_weights = None

# ---------------------------
# Logger Setup
# ---------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ScannerRunner")

# ---------------------------
# Device Setup
# ---------------------------
DEVICE = get_device()
optimize_torch_for_device(DEVICE)
logger.info(f"🧠 Device set to use: {DEVICE}")

# ---------------------------
# Data Directory
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
WEIGHTS_FILE = os.path.join(DATA_DIR, "collective_ai_weights.json")

# ---------------------------
# User Config (multi-user ready)
# ---------------------------
USERS = [
    {"email": "me@example.com", "id": 1},
    # add more users here for SaaS
]

# ---------------------------
# Initial Startup Scan
# ---------------------------
def initial_scan(user):
    """Load previous scan history to avoid duplicate scanning."""
    last_scan = load_last_scan()
    emails = last_scan.get("emails", [])
    user_emails = [e for e in emails if e.get("user_id") == user["id"]]
    logger.info(f"🔹 Initial scan setup for {user['email']}: {len(user_emails)} past emails loaded.")

# ---------------------------
# Compute & persist collective AI weights
# ---------------------------
def compute_collective_weights():
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()

        # Ensure table exists
        c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='collective_metrics'")
        if not c.fetchone():
            conn.close()
            logger.info("ℹ️ collective_metrics table not found; skipping weight computation.")
            return

        # Aggregate sender stats
        c.execute("""
            SELECT sender, AVG(score) AS avg_score, COUNT(*) AS cnt
            FROM collective_metrics
            WHERE sender IS NOT NULL AND sender <> ''
            GROUP BY sender
        """)
        sender_rows = c.fetchall()

        # Aggregate rule stats
        c.execute("""
            SELECT matched_rules, AVG(score) AS avg_score, COUNT(*) AS cnt
            FROM collective_metrics
            WHERE matched_rules IS NOT NULL AND matched_rules <> ''
            GROUP BY matched_rules
        """)
        rule_rows = c.fetchall()
        conn.close()

        sender_weights = {s: round(min(2.5, 1.0 + (float(avg or 0)/10.0) + (float(cnt or 0)/50.0)), 2)
                          for s, avg, cnt in sender_rows}

        rule_weights = {}
        for rules, avg, cnt in rule_rows:
            for r in (rules or "").split(","):
                r = r.strip()
                if not r: continue
                w = round(min(2.5, 1.0 + (float(avg or 0)/10.0) + (float(cnt or 0)/50.0)), 2)
                rule_weights[r] = max(w, rule_weights.get(r, 1.0))

        data = {"updated": datetime.now(timezone.utc).isoformat(), "senders": sender_weights, "rules": rule_weights}
        with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"✅ Collective AI weights updated — {len(sender_weights)} senders, {len(rule_weights)} rules.")
    except Exception as e:
        logger.error(f"❌ Failed to compute collective weights: {e}", exc_info=True)

# ---------------------------
# Background Runner
# ---------------------------
def start_user_runner(user):
    try:
        logger.info(f"🚀 Starting scanner runner for {user['email']}")

        # Behavior tables
        try:
            init_behavior_tables(DB_PATH)
            logger.info("🧭 Behavior tables initialized.")
        except Exception as e:
            logger.warning(f"⚠️ Could not initialize behavior tables: {e}")

        # Load previous scans
        initial_scan(user)

        # Start scheduler
        scheduler = start_auto_scan_scheduler(user_email=user["email"], user_id=user["id"], db_path=DB_PATH)
        atexit.register(lambda: scheduler.shutdown())
        logger.info(f"🟢 Auto scan scheduler started for {user['email']}.")

        # Schedule collective AI weights
        if update_collective_ai_weights:
            update_collective_ai_weights()
            scheduler.add_job(update_collective_ai_weights, "interval", hours=12, id=f"{user['id']}_collective_weights_job")
        else:
            compute_collective_weights()
            scheduler.add_job(compute_collective_weights, "interval", hours=12, id=f"{user['id']}_collective_weights_job_fallback")
        logger.info(f"🧠 Collective AI weight job scheduled for {user['email']}.")

        # Optional: behavior KPIs every 6h
        def log_behavior_kpis():
            try:
                kpis = compute_user_behavior_scores(user_id=user["id"])
                logger.info(
                    f"📊 Behavior KPIs {user['email']} — 7d risky: {kpis.get('risky_clicks_7d')} | "
                    f"30d risky: {kpis.get('risky_clicks_30d')} | 30d total: {kpis.get('total_clicks_30d')} | "
                    f"risk: {kpis.get('behavior_risk'):.3f}"
                )
            except Exception as e:
                logger.warning(f"⚠️ Behavior KPI computation failed: {e}")

        log_behavior_kpis()
        scheduler.add_job(log_behavior_kpis, "interval", hours=6, id=f"{user['id']}_behavior_kpis_job")

        # Keep alive
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info(f"✋ Scanner runner stopped for {user['email']}.")
    except Exception as e:
        logger.error(f"❌ Scanner runner crashed for {user['email']}.", exc_info=True)

# ---------------------------
# Multi-user runner start
# ---------------------------
if __name__ == "__main__":
    threads = []
    for user in USERS:
        t = Thread(target=start_user_runner, args=(user,), daemon=True)
        t.start()
        threads.append(t)
    for t in threads:
        t.join()
