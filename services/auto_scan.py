# services/auto_scan.py — AutoGuardian Multi-User Async Auto-Scan Pipeline
# ----------------------------------------------------------------------
# Handles continuous background scanning for multiple users.
# Fully async + multi-threaded:
#  - Fetch Gmail emails concurrently
#  - Scan emails via scanner.py (AI, OSINT, attachments, similarity)
#  - Update Gmail labels automatically
#  - Store processed IDs and scan history
# ----------------------------------------------------------------------

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

from services.gmail_service import get_credentials, fetch_recent_emails, _ensure_label, modify_labels
from services.scanner import scan_emails_async, SCAN_HISTORY_FILE
from services.scanner import _load_json, _save_json

logger = logging.getLogger("AutoGuardian.AutoScan")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

user_schedulers = {}  # Holds scheduler instances per user
processed_ids_cache = {}  # Tracks processed IDs per user

# ---------------------------
# Async per-user scan
# ---------------------------
async def scan_user_emails(user_id, user_email, max_results=25):
    global processed_ids_cache

    if user_id not in processed_ids_cache:
        processed_ids_cache[user_id] = set()

    try:
        emails = fetch_recent_emails(max_results=max_results)
        new_emails = [e for e in emails if e.get("id") not in processed_ids_cache[user_id]]
        if not new_emails:
            logger.info(f"[{user_email}] No new emails to scan.")
            return

        logger.info(f"[{user_email}] Scanning {len(new_emails)} new emails…")
        results = await scan_emails_async(new_emails, user_email=user_email, db_path=None, user_id=user_id)

        # Update processed IDs
        new_ids = [r["email"]["id"] for r in results if r.get("email")]
        processed_ids_cache[user_id].update(new_ids)

        # Save updated IDs
        _save_json(f"data/processed_ids_user_{user_id}.json", list(processed_ids_cache[user_id]))

        # Update Gmail labels
        creds = get_credentials()
        service = creds  # We'll build Gmail service here
        # Labels: Safe, Suspicious, High Risk, Quarantine, Community
        label_ids = {
            "safe": _ensure_label(service, "AutoGuardian: Safe"),
            "medium": _ensure_label(service, "AutoGuardian: Suspicious"),
            "high": _ensure_label(service, "AutoGuardian: High Risk"),
            "quarantine": _ensure_label(service, "AutoGuardian: Quarantine"),
            "community": _ensure_label(service, "AutoGuardian: Community Alert"),
        }

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            tasks = []
            for res in results:
                msg_id = res["email"]["id"]
                risk = res.get("risk_level", "Safe")
                quarantine = bool(res.get("quarantine", False))
                community_alert = res.get("community_alert")

                add_labels = []
                remove_labels = [label_ids["safe"], label_ids["medium"], label_ids["high"],
                                 label_ids["quarantine"], label_ids["community"]]

                if risk == "Safe":
                    add_labels.append(label_ids["safe"])
                elif risk in ("Suspicious", "Medium"):
                    add_labels.append(label_ids["medium"])
                else:
                    add_labels.append(label_ids["high"])
                    quarantine = True

                if quarantine:
                    add_labels.append(label_ids["quarantine"])
                if community_alert:
                    add_labels.append(label_ids["community"])

                # Run label modification concurrently
                tasks.append(loop.run_in_executor(pool, modify_labels, service, msg_id, add_labels, remove_labels))

            await asyncio.gather(*tasks)

        logger.info(f"[{user_email}] Scan complete — {len(results)} emails processed.")

        # Save full scan history per user
        history_file = f"data/scan_history_user_{user_id}.json"
        existing_history = _load_json(history_file)
        existing_history.extend(results)
        _save_json(history_file, existing_history)

    except Exception as e:
        logger.error(f"[{user_email}] Async scan error: {e}", exc_info=True)

# ---------------------------
# Scheduler per user
# ---------------------------
def start_user_auto_scan(user_id, user_email, poll_interval=60):
    if user_id in user_schedulers:
        return user_schedulers[user_id]

    def job():
        asyncio.run(scan_user_emails(user_id, user_email))

    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(job, "interval", seconds=poll_interval, id=f"user_{user_id}_scan")
    scheduler.start()
    user_schedulers[user_id] = scheduler
    logger.info(f"🟢 Auto-scan scheduler started for {user_email} every {poll_interval}s")
    return scheduler

def stop_user_auto_scan(user_id):
    sch = user_schedulers.get(user_id)
    if sch:
        sch.shutdown()
        del user_schedulers[user_id]
        logger.info(f"✋ Auto-scan scheduler stopped for user {user_id}")
