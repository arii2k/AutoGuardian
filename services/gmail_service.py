# services/gmail_service.py — AutoGuardian Gmail Service (Enterprise Hybrid Real-Time + Trusted Senders)
# -----------------------------------------------------------------------------------------------------
# Gmail OAuth, TLS 1.2+, safe fetch, scan & label, processed_ids tracking,
# trusted-sender integration (with override rules), manual rescan, background scheduler,
# Gmail push watch (real-time), auto-learn from Sent mail correspondents.

import os, json, base64, logging, ssl, warnings, time
from email.utils import parseaddr
from datetime import datetime, timedelta
from collections import Counter

import requests
from google.auth.transport.requests import Request, AuthorizedSession
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from apscheduler.schedulers.background import BackgroundScheduler
import sqlite3

# Trusted senders module (your premium shield)
from services.trusted_senders import (
    is_trusted_sender,
    normalize_domain,
    load_cache,
    save_cache,
)

# (Kept for compatibility with your codebase)
from services.attachment_analyzer import analyze_attachments  # noqa
from services.similarity_index import add_email_to_index, compute_similarity  # noqa

# -------------------- TLS + Logging --------------------
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
os.environ["OAUTHLIB_RELAX_TOKEN_SCOPE"] = "1"

ssl_context = ssl.create_default_context()
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2
ssl_context.set_ciphers("ECDHE+AESGCM:!aNULL:!eNULL:!MD5:!3DES")

warnings.filterwarnings("ignore", message=".*SSL.*")

logger = logging.getLogger("AutoGuardian.Gmail")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

# -------------------- Paths & Config --------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
TOKEN_FILE = os.path.join(BASE_DIR, "token.json")
CREDENTIALS_FILE = os.path.join(BASE_DIR, "credentials.json")
PROCESSED_FILE = os.path.join(DATA_DIR, "processed_ids.json")

SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

# Gmail Push Watch topic (Google Pub/Sub)
# Set via env var GMAIL_WATCH_TOPIC="projects/<GCP_PROJECT>/topics/<TOPIC>"
GMAIL_WATCH_TOPIC = os.environ.get(
    "GMAIL_WATCH_TOPIC",
    "projects/YOUR_PROJECT_ID/topics/autoguardian-gmail"  # replace or set env var
)

# Enterprise behavior
ENTERPRISE_PLAN = "Enterprise"
AUTO_LEARN_MIN_CONTACTS = 5          # domains contacted >=5 times in 30d become trusted
TRUST_OVERRIDE_MAX_SCORE = 80        # AI hybrid_score below this can be overridden to Safe
TRUST_BLOCK_RULE_KEYWORDS = ("Malware", "Phishing", "Credential", "Ransom", "Exploit")

# -------------------- Helpers --------------------
def _load_processed_ids():
    if os.path.exists(PROCESSED_FILE):
        try:
            return set(json.load(open(PROCESSED_FILE, "r", encoding="utf-8")))
        except Exception:
            return set()
    return set()

def _save_processed_ids(ids):
    try:
        json.dump(sorted(list(ids)), open(PROCESSED_FILE, "w", encoding="utf-8"), indent=2)
    except Exception as e:
        logger.warning(f"processed_ids save failed: {e}")

def _normalize_sender(headers: dict) -> str:
    raw = headers.get("From") or headers.get("Return-Path") or ""
    _, addr = parseaddr(raw)
    return addr or raw or "unknown@unknown"

def _walk_parts(payload) -> str:
    """
    Best-effort extraction of text content (handles nested parts).
    """
    text = ""
    if not payload:
        return text

    mime = payload.get("mimeType", "")
    body = payload.get("body", {})
    data = body.get("data")

    if "multipart" in mime and "parts" in payload:
        for p in payload["parts"]:
            text += _walk_parts(p)
    else:
        # include both text/plain and text/html bodies
        if data:
            try:
                decoded = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
                text += decoded
            except Exception:
                pass
    return text

def _override_risk_in_db(email_id: str, new_level: str, append_rule: str | None = None):
    """Persist an override back into scan_history & collective_metrics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        # Helper to append matched_rules text
        def _update_table(table):
            cur.execute(f"SELECT matched_rules FROM {table} WHERE email_id=?", (email_id,))
            row = cur.fetchone()
            existing = (row[0] or "") if row else ""
            if append_rule:
                if existing:
                    existing = f"{existing}, {append_rule}"
                else:
                    existing = append_rule
            cur.execute(
                f"UPDATE {table} SET risk_level=?, matched_rules=? WHERE email_id=?",
                (new_level, existing, email_id),
            )
        _update_table("scan_history")
        _update_table("collective_metrics")
        conn.commit()
        conn.close()
        logger.info(f"🔧 DB override applied: {email_id} -> {new_level} (+{append_rule or 'no-tag'})")
    except Exception as e:
        logger.warning(f"DB override failed for {email_id}: {e}")

# -------------------- Gmail OAuth --------------------
def get_credentials():
    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
    return creds

# -------------------- Gmail Client --------------------
def _gmail_service(creds):
    """Return Gmail API client with a hardened TLS session adapter."""
    try:
        asession = AuthorizedSession(creds)
        asession.configure_mtls_channel(ssl_context)  # TLS 1.2+
        logger.info("🔐 Gmail client initialized with secure AuthorizedSession")
        service = build("gmail", "v1", credentials=creds, cache_discovery=False)
        return service
    except Exception as e:
        logger.error(f"❌ Gmail client init failed: {e}")
        raise

# -------------------- Fetch Logic --------------------
def _fetch_message(service, msg_id, retries=2):
    for attempt in range(retries + 1):
        try:
            msg = service.users().messages().get(
                userId="me", id=msg_id, format="full"
            ).execute()
            headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
            return {
                "id": msg_id,
                "Subject": headers.get("Subject", ""),
                "From": _normalize_sender(headers),
                "Date": headers.get("Date", datetime.utcnow().isoformat()),
                "Body": _walk_parts(msg.get("payload", {})),
            }
        except HttpError as he:
            if getattr(he, "resp", None) and he.resp.status in [403, 429, 500, 502, 503]:
                logger.warning(f"⚠️ HTTP retry {attempt+1}/{retries} for {msg_id}: {he}")
                time.sleep(1)
            else:
                logger.error(f"❌ HTTP error for {msg_id}: {he}")
                break
        except Exception as e:
            logger.warning(f"⚠️ Fetch retry {attempt+1}/{retries} for {msg_id}: {e}")
            time.sleep(1)
    logger.error(f"❌ Failed to fetch {msg_id}")
    return None

def fetch_recent_emails(max_results=25):
    """
    Fetch recent messages (last 2 days) from INBOX.
    """
    logger.info("⚙️ Gmail fetch started…")
    creds = get_credentials()
    service = _gmail_service(creds)
    results = service.users().messages().list(
        userId="me", q="in:inbox newer_than:2d", maxResults=max_results
    ).execute()
    ids = [m["id"] for m in results.get("messages", [])]
    if not ids:
        logger.info("📭 No new messages found.")
        return []
    emails = []
    for i in ids:
        msg = _fetch_message(service, i)
        if msg:
            emails.append(msg)
    logger.info(f"📨 Fetched {len(emails)} emails from Gmail")
    return emails

# -------------------- Labels --------------------
def _ensure_label(service, name):
    labels = service.users().labels().list(userId="me").execute().get("labels", [])
    for l in labels:
        if l["name"] == name:
            return l["id"]
    body = {"name": name, "labelListVisibility": "labelShow", "messageListVisibility": "show"}
    lab = service.users().labels().create(userId="me", body=body).execute()
    logger.info(f"🏷️ Created label: {name}")
    return lab["id"]

def modify_labels(service, msg_id, add_labels):
    try:
        if not add_labels:
            return
        service.users().messages().modify(
            userId="me", id=msg_id, body={"addLabelIds": add_labels}
        ).execute()
        logger.info(f"✅ Labeled {msg_id}")
    except Exception as e:
        logger.error(f"❌ Labeling failed for {msg_id}: {e}")

# -------------------- Auto-learn trusted domains from Sent --------------------
def learn_trusted_from_sent(window_days: int = 30, min_contacts: int = AUTO_LEARN_MIN_CONTACTS):
    """
    Enterprise feature: look at Sent messages, count recipient domains,
    and automatically trust domains frequently contacted.
    """
    try:
        creds = get_credentials()
        service = _gmail_service(creds)
        query = f"in:sent newer_than:{window_days}d"
        results = service.users().messages().list(userId="me", q=query, maxResults=200).execute()
        ids = [m["id"] for m in results.get("messages", [])]
        if not ids:
            return 0

        counts = Counter()
        for mid in ids:
            try:
                msg = service.users().messages().get(userId="me", id=mid, format="metadata", metadataHeaders=["To"]).execute()
                headers = {h["name"]: h["value"] for h in msg.get("payload", {}).get("headers", [])}
                to_val = headers.get("To", "")
                for piece in to_val.split(","):
                    _, addr = parseaddr(piece)
                    if "@" in addr:
                        dom = normalize_domain(addr.split("@")[-1])
                        if dom:
                            counts[dom] += 1
            except Exception:
                pass

        cache = load_cache()
        added = 0
        for dom, cnt in counts.items():
            if cnt >= min_contacts:
                if not cache.get(dom, {}).get("trusted", False):
                    cache[dom] = {"trusted": True, "timestamp": datetime.now().timestamp(), "source": "auto-learn"}
                    added += 1
        if added:
            save_cache(cache)
            logger.info(f"🤝 Auto-learn trusted domains added: {added}")
        return added
    except Exception as e:
        logger.warning(f"Auto-learn trusted domains failed: {e}")
        return 0

# -------------------- Scan + Label (Enterprise trusted override) --------------------
def _apply_trusted_override(result_item: dict) -> dict:
    """
    Post-scan override: if sender is trusted, downgrade to Safe unless
    rules show clear malicious indicators or score is very high.
    """
    try:
        email = result_item.get("email", {})  # scanner returns {"email": {...}, ...}
        email_id = email.get("id")
        sender = email.get("From", "")
        domain = normalize_domain(sender.split("@")[-1]) if "@" in sender else ""

        # Only Enterprise enables trusted override
        if not is_trusted_sender(sender, plan=ENTERPRISE_PLAN):
            return result_item

        # Gather AI/match details
        ai = result_item.get("ai_details", {}) or {}
        score = float(ai.get("hybrid_score", 0))
        matched = (result_item.get("matched_rules") or "")

        def has_block_rules():
            txt = matched.lower()
            return any(k.lower() in txt for k in TRUST_BLOCK_RULE_KEYWORDS)

        if score < TRUST_OVERRIDE_MAX_SCORE and not has_block_rules():
            # Override to Safe
            result_item["risk_level"] = "Safe"
            if matched:
                result_item["matched_rules"] = f"{matched}, TrustedSenderOverride"
            else:
                result_item["matched_rules"] = "TrustedSenderOverride"
            # Persist override to DB for this email_id
            if email_id:
                _override_risk_in_db(email_id, "Safe", "TrustedSenderOverride")
            logger.info(f"🟢 Trusted override applied to {sender} (score={score})")
        else:
            logger.info(f"⚠️ Trusted sender {sender} retained risk (score={score}, rules={matched})")
        return result_item
    except Exception as e:
        logger.warning(f"Trusted override failed: {e}")
        return result_item

def scan_and_label_gmail(max_results=25, user_email="me@example.com", user_id=1, force=False):
    """
    Fetch Gmail, scan with AI, label, and save to DB.
    If force=True, ignore processed_ids.json (rescan even already seen emails).
    """
    from services.scanner import scan_emails_async

    creds = get_credentials()
    service = _gmail_service(creds)
    emails = fetch_recent_emails(max_results)
    if not emails:
        return []

    processed = set() if force else _load_processed_ids()
    new_emails = emails if force else [e for e in emails if e["id"] not in processed]

    if not new_emails:
        logger.info("No unseen emails (use force=True to rescan).")
        return []

    logger.info(f"🔍 Scanning {len(new_emails)} emails for {user_email} (force={force})")

    # async scan
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    results = loop.run_until_complete(
        scan_emails_async(
            new_emails,
            user_email=user_email,
            db_path=DB_PATH,
            user_id=user_id,
        )
    )

    # Enterprise: apply trusted override after scan (so we still detect real phish)
    results = [_apply_trusted_override(r) for r in results]

    # map labels to risk
    label_map = {
        "Safe": _ensure_label(service, "AutoGuardian: Safe"),
        "Suspicious": _ensure_label(service, "AutoGuardian: Suspicious"),
        "High": _ensure_label(service, "AutoGuardian: High Risk"),
        "Quarantine": _ensure_label(service, "AutoGuardian: Quarantine"),
    }

    for r in results:
        try:
            risk = r.get("risk_level", "Safe")
            labels = []
            if risk == "Safe":
                labels.append(label_map["Safe"])
            elif risk in ("Suspicious", "Medium"):
                labels.append(label_map["Suspicious"])
            else:
                labels.append(label_map["High"])
                labels.append(label_map["Quarantine"])

            modify_labels(service, r["email"]["id"], labels)
            if not force:
                processed.add(r["email"]["id"])
        except Exception as e:
            logger.error(f"❌ Labeling failed: {e}")

    if not force:
        _save_processed_ids(processed)

    logger.info(f"✅ Scan complete — {len(results)} emails labeled (force={force}).")
    return results

# -------------------- Manual Rescan --------------------
def manual_rescan(user_email="me@example.com", user_id=1, limit=25, force=False):
    logger.info(f"🔁 Manual rescan triggered for {user_email} (force={force})")
    return scan_and_label_gmail(max_results=limit, user_email=user_email, user_id=user_id, force=force)

# -------------------- Real-Time Gmail Push (Watch) --------------------
def setup_gmail_watch(user_email="me@example.com"):
    """
    Enable Gmail push notifications via Google Pub/Sub.
    Requires:
      - Pub/Sub topic
      - Gmail API enabled
      - Service account with Pub/Sub permissions
    Set env GMAIL_WATCH_TOPIC to the full topic path.
    """
    if not GMAIL_WATCH_TOPIC or "YOUR_PROJECT_ID" in GMAIL_WATCH_TOPIC:
        logger.warning("⚠️ GMAIL_WATCH_TOPIC not configured; skipping watch setup.")
        return None

    creds = get_credentials()
    service = _gmail_service(creds)
    try:
        request = {
            "labelIds": ["INBOX"],
            "topicName": GMAIL_WATCH_TOPIC,
        }
        response = service.users().watch(userId="me", body=request).execute()
        logger.info(f"🔔 Gmail watch setup OK. Expiration: {response.get('expiration')}")
        return response
    except Exception as e:
        logger.error(f"❌ Gmail watch setup failed: {e}")
        return None

def stop_gmail_watch():
    try:
        creds = get_credentials()
        service = _gmail_service(creds)
        service.users().stop(userId="me").execute()
        logger.info("🛑 Gmail watch stopped.")
        return True
    except Exception as e:
        logger.warning(f"Stop watch failed: {e}")
        return False

def renew_gmail_watch_daily():
    """Gmail watch expires (typically < 7 days). Call this daily to renew."""
    setup_gmail_watch("me@example.com")

# -------------------- Background Scheduler (fallback + renew watch + auto-learn) --------------------
user_schedulers = {}

def start_user_auto_scan(user_id, user_email, poll_interval=120):
    """
    Start fallback scheduler to scan periodically (default every 2 minutes),
    auto-renew the Gmail watch daily, and auto-learn trusted senders daily.
    """
    if user_id in user_schedulers:
        return user_schedulers[user_id]

    def job_scan():
        try:
            scan_and_label_gmail(user_email=user_email, user_id=user_id)
        except Exception as e:
            logger.error(f"Auto-scan error: {e}")

    def job_renew_watch():
        try:
            renew_gmail_watch_daily()
        except Exception as e:
            logger.error(f"Watch renew error: {e}")

    def job_auto_learn():
        try:
            learn_trusted_from_sent()
        except Exception as e:
            logger.error(f"Auto-learn error: {e}")

    sched = BackgroundScheduler(daemon=True)
    sched.add_job(job_scan, "interval", seconds=poll_interval, id=f"user_{user_id}_scan")
    sched.add_job(job_renew_watch, "interval", days=1, id="gmail_watch_renew")
    sched.add_job(job_auto_learn, "interval", days=1, id="trusted_auto_learn")
    sched.start()

    user_schedulers[user_id] = sched
    logger.info(f"🟢 Scheduler started for {user_email} (interval={poll_interval}s)")
    return sched

# -------------------- Trusted sender admin helpers (used by app.py) --------------------
def list_trusted_domains():
    """Return dict of trusted domains cached (domain -> meta)."""
    return load_cache()

def add_trusted_domain(domain: str, source: str = "manual"):
    domain = normalize_domain(domain or "")
    if not domain:
        return False
    cache = load_cache()
    cache[domain] = {"trusted": True, "timestamp": datetime.now().timestamp(), "source": source}
    save_cache(cache)
    return True

def remove_trusted_domain(domain: str):
    domain = normalize_domain(domain or "")
    if not domain:
        return False
    cache = load_cache()
    if domain in cache:
        del cache[domain]
        save_cache(cache)
        return True
    return False
