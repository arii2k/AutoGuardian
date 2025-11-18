# services/scanner.py — Premium SaaS-ready AutoGuardian Email Scanner
import os
import json
import re
import sqlite3
import logging
import unicodedata
import asyncio
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from apscheduler.schedulers.background import BackgroundScheduler
from threading import Lock

# ---------------------------
# Service imports
# ---------------------------
from services.ai_ensemble import ensemble_score_with_reasons
from services.update_rules import update_rules
from services.memory_service import add_to_memory
from services.community_service import check_community_memory, update_community_memory
from services.behavior_detection import compute_user_behavior_scores, behavior_adjust_risk
from services.intent_extractor import extract_intent
from services.osint_enrichment import enrich as osint_enrich
from services.attachment_analyzer import analyze_attachments
from services.similarity_detector import detect_template_reuse
from services.similarity_index import compute_similarity
from services.local_nlp import local_nlp_score, train_from_history
from services.gmail_service import fetch_recent_emails

# ---------------------------
# Logging
# ---------------------------
logger = logging.getLogger("AutoGuardian.Scanner")
logger.setLevel(logging.INFO)
if not logger.handlers:
    fh = logging.FileHandler("app.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(fh)
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

# ---------------------------
# Paths & DB
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------
# Thread-safe JSON & DB lock
# ---------------------------
_db_lock = Lock()

def _safe_json(data):
    """Ensure AI details are valid JSON with numeric hybrid_score."""
    try:
        if isinstance(data, dict):
            if "hybrid_score" in data:
                data["hybrid_score"] = round(float(data.get("hybrid_score", 0.0)), 2)
        return json.dumps(data, ensure_ascii=False)
    except Exception as e:
        logger.warning(f"[scanner] JSON serialization failed: {e}")
        return json.dumps({"hybrid_score": 0.0})

def _save_scan_history_to_db(results, user_id: int, db_path: str = DB_PATH):
    """Insert scan results into DB, safe for multi-user SaaS."""
    with _db_lock:
        try:
            conn = sqlite3.connect(db_path)
            c = conn.cursor()
            for res in results:
                email = res.get("email", {})
                sender = email.get("From", "")
                subject = email.get("Subject", "")
                email_id = email.get("id", "")
                timestamp = email.get("Date") or res.get("timestamp") or datetime.now(timezone.utc).isoformat()
                score = int(res.get("score", 0))
                quarantine = int(bool(res.get("quarantine", False)))
                matched_rules = res.get("matched_rules", [])
                matched_rules_text = ", ".join(matched_rules) if isinstance(matched_rules, list) else str(matched_rules)
                ai_details_json = _safe_json(res.get("ai_details") or {"hybrid_score": 0.0})
                community_alert = "Known threat" if res.get("community_alert") else ""
                risk_level = res.get("risk_level", "Safe")

                c.execute("""
                    INSERT INTO scan_history (
                        email_id, timestamp, sender, subject, score,
                        matched_rules, memory_alert, community_alert,
                        quarantine, user_id, risk_level, ai_details
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    email_id, timestamp, sender, subject, score,
                    matched_rules_text, "", community_alert,
                    quarantine, user_id, risk_level, ai_details_json
                ))

                c.execute("""
                    INSERT INTO collective_metrics (
                        user_id, email_id, sender, subject,
                        score, risk_level, quarantine, timestamp, matched_rules
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    user_id, email_id, sender, subject, score,
                    risk_level, quarantine, timestamp, matched_rules_text
                ))

            conn.commit()
            conn.close()
            logger.info(f"[scanner] ✅ Saved {len(results)} scan results for user {user_id}.")
        except Exception as e:
            logger.error(f"[scanner] Failed to save scan results: {e}", exc_info=True)

# ---------------------------
# Advanced homoglyph / anomaly detection
# ---------------------------
def detect_homoglyph_attack(text):
    if not text:
        return False, ""
    normalized = unicodedata.normalize("NFKC", text)
    if normalized != text:
        return True, "Unicode normalization mismatch (possible disguised characters)"
    scripts = {"Latin": 0, "Cyrillic": 0, "Greek": 0}
    for ch in text:
        try:
            name = unicodedata.name(ch)
            for s in scripts:
                if s in name:
                    scripts[s] += 1
        except ValueError:
            continue
    if len([k for k, v in scripts.items() if v > 0]) > 1:
        return True, "Mixed scripts detected"
    if re.search(r"[\u200B-\u200F\u202A-\u202E]", text):
        return True, "Contains invisible direction characters"
    return False, ""

# ---------------------------
# Single email scan
# ---------------------------
async def _scan_single_email(email_obj, user_email, user_id):
    if not email_obj.get("Body"):
        email_obj["Body"] = email_obj.get("snippet", "") or "(no content)"

    subject = email_obj.get("Subject", "")
    sender = email_obj.get("From", "")
    loop = asyncio.get_event_loop()
    explanations = []
    quarantine = False

    homoglyph, reason = detect_homoglyph_attack(subject + " " + sender)
    if homoglyph:
        explanations.append(reason)

    with ThreadPoolExecutor() as pool:
        hybrid_score, reasons = await loop.run_in_executor(pool, ensemble_score_with_reasons, email_obj)
        nlp_score, nlp_exp = await loop.run_in_executor(pool, local_nlp_score, email_obj)
        hybrid_score = max(hybrid_score, nlp_score)
        explanations.extend(reasons)

        intent_info = await loop.run_in_executor(pool, extract_intent, email_obj)
        osint_info = await loop.run_in_executor(pool, osint_enrich, email_obj)
        attach_info = await loop.run_in_executor(pool, analyze_attachments, email_obj)
        sim_info = await loop.run_in_executor(pool, detect_template_reuse, email_obj)
        sim_results = await loop.run_in_executor(pool, compute_similarity, email_obj, 5)

        await loop.run_in_executor(pool, add_to_memory, email_obj, user_email, True)
        community_alert = await loop.run_in_executor(pool, check_community_memory, email_obj)
        await loop.run_in_executor(pool, update_community_memory, email_obj)

        behavior = await loop.run_in_executor(pool, compute_user_behavior_scores, user_id)
        risk_level = behavior_adjust_risk(
            "High" if hybrid_score > 65 else "Suspicious" if hybrid_score > 30 else "Safe",
            behavior.get("behavior_risk", 0)
        )

    if osint_info.get("verdict") == "malicious" or attach_info.get("verdict") == "malicious":
        quarantine = True
        risk_level = "High"

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "email": email_obj,
        "score": int(hybrid_score),
        "risk_level": risk_level,
        "quarantine": quarantine,
        "matched_rules": [],
        "ai_details": {"hybrid_score": float(hybrid_score), "ensemble_reasons": reasons},
        "intent": intent_info,
        "osint": osint_info,
        "similarity": sim_info,
        "similarity_index": {"matches": sim_results},
        "attachments": attach_info,
        "behavior": behavior,
        "explanations": explanations,
        "community_alert": community_alert,
        "local_nlp": nlp_exp,
    }

# ---------------------------
# Batch async scan + retrain hook
# ---------------------------
async def scan_emails_async(emails, user_email="me@example.com", db_path=DB_PATH, user_id=1):
    if not emails:
        logger.info("[scanner] No emails to scan.")
        return []
    results = await asyncio.gather(*[
        _scan_single_email(e, user_email, user_id) for e in emails
    ])
    _save_scan_history_to_db(results, user_id, db_path)

    # Trigger incremental retraining
    try:
        conn = sqlite3.connect(db_path)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM scan_history")
        total_scans = c.fetchone()[0]
        conn.close()
        if total_scans % 50 == 0:
            logger.info("[scanner] 🔄 Retraining local NLP model from history...")
            train_from_history(min_samples=50)
    except Exception as e:
        logger.warning(f"[scanner] Retrain trigger failed: {e}")

    return results

# ---------------------------
# Manual rescan
# ---------------------------
def manual_rescan(user_id=1, user_email="me@example.com", db_path=DB_PATH, limit=20):
    try:
        emails = fetch_recent_emails(max_results=limit)
        if not emails:
            logger.info("[scanner] No new emails fetched for manual rescan.")
            return []
        logger.info(f"[scanner] Manual rescan started for {user_email} ({len(emails)} emails)")
        return asyncio.run(scan_emails_async(emails, user_email, db_path, user_id))
    except Exception as e:
        logger.exception(f"[scanner] Manual rescan failed: {e}")
        return []

# ---------------------------
# Scheduler
# ---------------------------
user_schedulers = {}
_scheduler_lock = Lock()

def start_auto_scan_scheduler(user_email="me@example.com", user_id=1, db_path=DB_PATH, interval=300):
    """Multi-user safe auto-scan scheduler with thread-safe start"""
    with _scheduler_lock:
        if user_id in user_schedulers:
            return user_schedulers[user_id]

        def job():
            try:
                logger.info(f"[scanner] 🔁 Auto-scan triggered for {user_email}")
                emails = fetch_recent_emails(max_results=25)
                if emails:
                    asyncio.run(scan_emails_async(emails, user_email, db_path, user_id))
            except Exception as e:
                logger.error(f"[scanner] Auto-scheduler error: {e}", exc_info=True)

        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(job, "interval", seconds=interval, id=f"auto_scan_{user_id}")
        scheduler.start()
        user_schedulers[user_id] = scheduler
        logger.info(f"[scanner] 🟢 Scheduler started for {user_email} (every {interval}s)")
        return scheduler
