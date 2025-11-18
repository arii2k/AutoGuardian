# services/imap_service.py — AutoGuardian IMAP Service
# ----------------------------------------------------
# Generic IMAP connector for AutoGuardian:
# - TLS 1.2+ connection
# - Fetch recent emails from any IMAP inbox
# - Normalize to Gmail-like dict format
# - Send through existing scan_emails_async pipeline
# - Apply risk-based flags + quarantine folder
# - Auto-learn trusted senders from Sent folder
# - Near real-time scanning via background listener
#
# Usage (example):
#   from services.imap_service import scan_and_tag_imap, start_imap_realtime_listener
#   scan_and_tag_imap(
#       host="imap.example.com",
#       username="user@example.com",
#       password="APP_PASSWORD",
#       user_email="user@example.com",
#       user_id=1,
#   )

import os
import ssl
import json
import logging
import imaplib
import email
import threading
import time
from email.header import decode_header, make_header
from email.utils import parseaddr, parsedate_to_datetime
from datetime import datetime, timedelta

from services.trusted_senders import normalize_domain, load_cache, save_cache

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
PROCESSED_FILE = os.path.join(DATA_DIR, "processed_imap_ids.json")

# ---------- Logging ----------
logger = logging.getLogger("AutoGuardian.IMAP")
logger.setLevel(logging.INFO)
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

# ---------- TLS Context ----------
ssl_context = ssl.create_default_context()
ssl_context.minimum_version = ssl.TLSVersion.TLSv1_2

# ---------- Helpers: processed IDs per IMAP account ----------
def _account_key(host: str, username: str) -> str:
    return f"{username}@{host}"

def _load_processed_ids(account_key: str):
    if not os.path.exists(PROCESSED_FILE):
        return set()
    try:
        data = json.load(open(PROCESSED_FILE, "r", encoding="utf-8"))
        return set(data.get(account_key, []))
    except Exception:
        return set()

def _save_processed_ids(account_key: str, ids):
    try:
        data = {}
        if os.path.exists(PROCESSED_FILE):
            try:
                data = json.load(open(PROCESSED_FILE, "r", encoding="utf-8"))
            except Exception:
                data = {}
        data[account_key] = sorted(list(ids))
        json.dump(data, open(PROCESSED_FILE, "w", encoding="utf-8"), indent=2)
    except Exception as e:
        logger.warning(f"processed_imap_ids save failed: {e}")

# ---------- Helpers: parsing ----------
def _decode_header_value(val: str) -> str:
    if not val:
        return ""
    try:
        return str(make_header(decode_header(val)))
    except Exception:
        return val

def _normalize_sender(raw: str) -> str:
    name, addr = parseaddr(raw or "")
    return addr or raw or "unknown@unknown"

def _extract_body(msg: email.message.Message) -> str:
    """
    Extract concatenated text/plain + text/html parts.
    """
    parts = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True) or b""
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="ignore"))
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True) or b""
            charset = msg.get_content_charset() or "utf-8"
            parts.append(payload.decode(charset, errors="ignore"))
        except Exception:
            pass
    return "\n".join(parts)

def _parse_date(date_header: str | None) -> str:
    if not date_header:
        return datetime.utcnow().isoformat()
    try:
        dt = parsedate_to_datetime(date_header)
        if not dt.tzinfo:
            return dt.isoformat()
        return dt.astimezone().isoformat()
    except Exception:
        return datetime.utcnow().isoformat()

# ---------- IMAP connection ----------
def _connect_imap(host: str, username: str, password: str, port: int = 993, use_ssl: bool = True):
    try:
        if use_ssl:
            imap = imaplib.IMAP4_SSL(host, port, ssl_context=ssl_context)
        else:
            imap = imaplib.IMAP4(host, port)
            imap.starttls(ssl_context)
        imap.login(username, password)
        logger.info(f"🔐 IMAP login OK for {username} @ {host}")
        return imap
    except Exception as e:
        logger.error(f"❌ IMAP connection failed for {username}@{host}: {e}")
        raise

# ---------- Fetch recent emails ----------
def fetch_recent_emails_imap(
    host: str,
    username: str,
    password: str,
    days: int = 2,
    max_results: int = 25,
    folder: str = "INBOX",
    port: int = 993,
    use_ssl: bool = True,
):
    """
    Fetch recent emails from an IMAP folder and normalize to:
    { "id", "Subject", "From", "Date", "Body" }
    where id is the IMAP UID (string).
    """
    imap = _connect_imap(host, username, password, port=port, use_ssl=use_ssl)
    try:
        typ, _ = imap.select(folder, readonly=True)
        if typ != "OK":
            logger.error(f"❌ IMAP select failed on {folder}")
            return []

        since = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")
        typ, data = imap.uid("search", None, f'(SINCE {since})')
        if typ != "OK":
            logger.error("❌ IMAP search failed")
            return []

        uids = data[0].split()
        if not uids:
            logger.info("📭 No IMAP messages found.")
            return []

        # take the most recent N
        uids = uids[-max_results:]

        emails = []
        for uid in uids:
            typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
            if typ != "OK" or not msg_data or msg_data[0] is None:
                continue
            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            subject = _decode_header_value(msg.get("Subject", ""))
            sender = _normalize_sender(msg.get("From", ""))
            date_val = _parse_date(msg.get("Date"))
            body = _extract_body(msg)

            emails.append(
                {
                    "id": uid.decode(),  # keep UID as string
                    "Subject": subject,
                    "From": sender,
                    "Date": date_val,
                    "Body": body,
                }
            )

        logger.info(f"📨 Fetched {len(emails)} emails from IMAP {folder}")
        return emails
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass

# ---------- Apply IMAP flags + Quarantine based on risk ----------
def _apply_risk_flags(
    host: str,
    username: str,
    password: str,
    results: list[dict],
    folder: str = "INBOX",
    port: int = 993,
    use_ssl: bool = True,
    quarantine_folder: str = "AutoGuardian-Quarantine",
):
    """
    Risk-driven IMAP actions:
    - Suspicious/Medium -> \Flagged
    - High/Quarantine   -> move to AutoGuardian-Quarantine (and mark deleted in INBOX)
    """
    if not results:
        return

    try:
        imap = _connect_imap(host, username, password, port=port, use_ssl=use_ssl)
    except Exception:
        return

    try:
        typ, _ = imap.select(folder)
        if typ != "OK":
            logger.warning(f"IMAP select failed for flagging on {folder}")
            return

        # Ensure quarantine folder exists (no error if already exists)
        try:
            imap.create(quarantine_folder)
        except Exception:
            pass

        for r in results:
            try:
                email_obj = r.get("email", {})
                uid = email_obj.get("id")
                if not uid:
                    continue

                risk = r.get("risk_level", "Safe")

                if risk in ("Suspicious", "Medium"):
                    imap.uid("store", uid, "+FLAGS", r"(\Flagged)")

                elif risk in ("High", "Quarantine"):
                    # Copy to quarantine folder, mark deleted in INBOX
                    imap.uid("copy", uid, quarantine_folder)
                    imap.uid("store", uid, "+FLAGS", r"(\Deleted)")
                    imap.expunge()
                    logger.info(f"🚫 IMAP: moved UID {uid} to {quarantine_folder}")

            except Exception as e:
                logger.warning(f"IMAP risk flag failed: {e}")

    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass

# ---------- Auto-learn trusted senders from IMAP Sent ----------
def learn_trusted_from_imap_sent(
    host: str,
    username: str,
    password: str,
    days: int = 30,
    min_contacts: int = 5,
    sent_folder: str = "Sent",
    port: int = 993,
    use_ssl: bool = True,
):
    """
    Analyze IMAP Sent folder: frequently-contacted domains (>= min_contacts)
    become auto-trusted, mirroring Gmail auto-learn behavior.
    """
    try:
        imap = _connect_imap(host, username, password, port=port, use_ssl=use_ssl)

        typ, _ = imap.select(sent_folder, readonly=True)
        if typ != "OK":
            logger.warning("IMAP: cannot open Sent folder for auto-learn")
            return 0

        since = (datetime.utcnow() - timedelta(days=days)).strftime("%d-%b-%Y")
        typ, data = imap.uid("search", None, f'(SINCE {since})')
        if typ != "OK":
            return 0

        uids = data[0].split()
        if not uids:
            return 0

        counts: dict[str, int] = {}

        for uid in uids:
            try:
                typ, msg_data = imap.uid("fetch", uid, "(RFC822)")
                if typ != "OK" or not msg_data or msg_data[0] is None:
                    continue
                raw = msg_data[0][1]
                msg = email.message_from_bytes(raw)

                to_val = msg.get("To", "")
                for piece in to_val.split(","):
                    _, addr = parseaddr(piece)
                    if "@" in addr:
                        dom = normalize_domain(addr.split("@")[-1])
                        if dom:
                            counts[dom] = counts.get(dom, 0) + 1
            except Exception:
                continue

        cache = load_cache()
        added = 0

        for dom, cnt in counts.items():
            if cnt >= min_contacts:
                if not cache.get(dom, {}).get("trusted", False):
                    cache[dom] = {
                        "trusted": True,
                        "timestamp": datetime.now().timestamp(),
                        "source": "imap-auto-learn",
                    }
                    added += 1

        if added:
            save_cache(cache)
            logger.info(f"🤝 IMAP auto-learn added {added} trusted domains")

        return added

    except Exception as e:
        logger.warning(f"IMAP auto-learn failed: {e}")
        return 0
    finally:
        try:
            imap.close()
        except Exception:
            pass
        try:
            imap.logout()
        except Exception:
            pass

# ---------- Main: Scan + Tag IMAP ----------
def scan_and_tag_imap(
    host: str,
    username: str,
    password: str,
    user_email: str,
    user_id: int,
    days: int = 2,
    max_results: int = 25,
    folder: str = "INBOX",
    port: int = 993,
    use_ssl: bool = True,
    force: bool = False,
):
    """
    Fetch IMAP emails, scan with AI, and apply IMAP flags/quarantine.
    Mirrors scan_and_label_gmail() but for generic IMAP.
    """
    from services.scanner import scan_emails_async
    # reuse trusted override logic from Gmail service
    from services.gmail_service import _apply_trusted_override

    logger.info(
        f"⚙️ IMAP scan started for {user_email} "
        f"({username}@{host}, folder={folder}, force={force})"
    )

    emails = fetch_recent_emails_imap(
        host=host,
        username=username,
        password=password,
        days=days,
        max_results=max_results,
        folder=folder,
        port=port,
        use_ssl=use_ssl,
    )
    if not emails:
        return []

    account_key = _account_key(host, username)
    processed = set() if force else _load_processed_ids(account_key)
    new_emails = emails if force else [e for e in emails if e["id"] not in processed]

    if not new_emails:
        logger.info("No unseen IMAP emails (use force=True to rescan).")
        return []

    logger.info(f"🔍 Scanning {len(new_emails)} IMAP emails for {user_email} (force={force})")

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

    # Apply trusted override just like Gmail
    results = [_apply_trusted_override(r) for r in results]

    # Apply IMAP flags + quarantine based on risk
    _apply_risk_flags(
        host=host,
        username=username,
        password=password,
        results=results,
        folder=folder,
        port=port,
        use_ssl=use_ssl,
    )

    if not force:
        for r in results:
            email_obj = r.get("email", {})
            eid = email_obj.get("id")
            if eid:
                processed.add(eid)
        _save_processed_ids(account_key, processed)

    logger.info(f"✅ IMAP scan complete — {len(results)} emails processed (force={force}).")
    return results

# ---------- Near real-time IMAP listener (IDLE-style via polling) ----------
def _realtime_listener(
    host: str,
    username: str,
    password: str,
    user_email: str,
    user_id: int,
    folder: str = "INBOX",
    port: int = 993,
    use_ssl: bool = True,
    interval: int = 60,
):
    """
    Near real-time IMAP listener:
    - Runs scan_and_tag_imap() in a loop every `interval` seconds.
    - This approximates IDLE-like behavior for providers without a clean IDLE API.
    """
    logger.info(
        f"🕒 IMAP realtime listener started for {user_email} "
        f"({username}@{host}, folder={folder}, every {interval}s)"
    )
    while True:
        try:
            scan_and_tag_imap(
                host=host,
                username=username,
                password=password,
                user_email=user_email,
                user_id=user_id,
                folder=folder,
                port=port,
                use_ssl=use_ssl,
            )
        except Exception as e:
            logger.warning(f"IMAP realtime listener error: {e}")
        time.sleep(interval)

def start_imap_realtime_listener(
    host: str,
    username: str,
    password: str,
    user_email: str,
    user_id: int,
    folder: str = "INBOX",
    port: int = 993,
    use_ssl: bool = True,
    interval: int = 60,
):
    """
    Start IMAP near real-time listener in a background thread.
    This gives push-like behavior similar to Gmail watch.
    """
    th = threading.Thread(
        target=_realtime_listener,
        args=(host, username, password, user_email, user_id, folder, port, use_ssl, interval),
        daemon=True,
    )
    th.start()
    logger.info(f"🟢 IMAP realtime thread started for {user_email}")
    return th
