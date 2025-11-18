# services/update_rules.py — Premium SaaS-ready Phishing Rules Fetcher

import requests
import csv
import json
import os
from io import StringIO
from datetime import datetime, timezone, timedelta
import logging
from threading import Lock
from concurrent.futures import ThreadPoolExecutor, as_completed

# ---------------------------
# Paths
# ---------------------------
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

RULES_FILE = os.path.join(DATA_DIR, "rules.json")
LAST_FETCH_FILE = os.path.join(DATA_DIR, "last_fetch.json")

# ---------------------------
# Feeds
# ---------------------------
OPENPHISH_URL = "https://openphish.com/feed.txt"
URLHAUS_CSV = "https://urlhaus.abuse.ch/downloads/csv_online/"
PHISHTANK_URL = "https://data.phishtank.com/data/online-valid.csv"

DEFAULT_SCORE = 3

# ---------------------------
# Logging & locks
# ---------------------------
logger = logging.getLogger("AutoGuardian.update_rules")
logger.setLevel(logging.INFO)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)

_json_lock = Lock()

# ---------------------------
# Helper functions
# ---------------------------
def add_rule(rules_map, pattern, source, score=DEFAULT_SCORE, name=None):
    if not pattern:
        return
    key = pattern.strip()
    if key in rules_map:
        existing = rules_map[key]
        if score > existing.get("score", 0):
            existing["score"] = score
        if source not in existing.get("sources", []):
            existing["sources"].append(source)
    else:
        rules_map[key] = {
            "pattern": key,
            "score": score,
            "name": name or f"Threat from {source}",
            "sources": [source]
        }

def fetch_openphish():
    try:
        logger.info("🌐 Fetching OpenPhish feed...")
        r = requests.get(OPENPHISH_URL, timeout=15)
        r.raise_for_status()
        urls = [u.strip() for u in r.text.strip().splitlines() if u.strip()]
        logger.info(f"✅ OpenPhish fetched {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.warning(f"❌ OpenPhish fetch failed: {e}")
        return []

def fetch_urlhaus():
    try:
        logger.info("🌐 Fetching URLhaus feed...")
        r = requests.get(URLHAUS_CSV, timeout=30)
        r.raise_for_status()
        f = StringIO(r.text)
        reader = csv.reader(f)
        urls = []
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            candidate = next((col for col in row if col.startswith("http://") or col.startswith("https://")), None)
            if candidate:
                urls.append(candidate.strip())
        logger.info(f"✅ URLhaus fetched {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.warning(f"❌ URLhaus fetch failed: {e}")
        return []

def fetch_phishtank():
    try:
        logger.info("🌐 Fetching PhishTank feed...")
        r = requests.get(PHISHTANK_URL, timeout=30)
        r.raise_for_status()
        f = StringIO(r.text)
        reader = csv.reader(f)
        urls = []
        for row in reader:
            if not row or row[0].startswith("#"):
                continue
            candidate = row[1] if len(row) > 1 else ""
            if candidate.startswith("http://") or candidate.startswith("https://"):
                urls.append(candidate.strip())
        logger.info(f"✅ PhishTank fetched {len(urls)} URLs")
        return urls
    except Exception as e:
        logger.warning(f"❌ PhishTank fetch failed: {e}")
        return []

# ---------------------------
# Update rules with caching and concurrency
# ---------------------------
def update_rules(force=False, max_workers=3):
    """Fetch or refresh phishing rules with auto caching, thread-safe for SaaS."""
    rules_map = {}
    now = datetime.now(timezone.utc)
    last_fetch_info = {
        "openphish": None,
        "urlhaus": None,
        "phishtank": None,
        "total_rules": 0,
        "timestamp": now.isoformat()
    }

    # Use cache if fresh (<24h)
    if not force and os.path.exists(LAST_FETCH_FILE):
        try:
            with _json_lock:
                with open(LAST_FETCH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            last_time = datetime.fromisoformat(data.get("timestamp"))
            if now - last_time < timedelta(hours=24) and os.path.exists(RULES_FILE):
                logger.info(f"♻️ Using cached rules (last fetched {last_time.isoformat()})")
                return json.load(open(RULES_FILE, "r", encoding="utf-8")), data
        except Exception as e:
            logger.warning(f"⚠️ Cache read failed, fetching fresh: {e}")

    # Fetch concurrently
    fetch_funcs = [fetch_openphish, fetch_urlhaus, fetch_phishtank]
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_map = {executor.submit(f): f.__name__ for f in fetch_funcs}
        for fut in as_completed(future_map):
            try:
                res = fut.result()
                results.append(res)
            except Exception as e:
                logger.warning(f"❌ {future_map[fut]} failed: {e}")
                results.append([])

    openphish_urls, urlhaus_urls, phishtank_urls = results

    for u in openphish_urls:
        add_rule(rules_map, u, source="openphish", score=DEFAULT_SCORE + 1)
    for u in urlhaus_urls:
        add_rule(rules_map, u, source="urlhaus", score=DEFAULT_SCORE)
    for u in phishtank_urls:
        add_rule(rules_map, u, source="phishtank", score=DEFAULT_SCORE)

    rules_list = list(rules_map.values())
    total_rules = len(rules_list)

    last_fetch_info.update({
        "openphish": {"count": len(openphish_urls), "fetched_at": now.isoformat()},
        "urlhaus": {"count": len(urlhaus_urls), "fetched_at": now.isoformat()},
        "phishtank": {"count": len(phishtank_urls), "fetched_at": now.isoformat()},
        "total_rules": total_rules,
        "timestamp": now.isoformat()
    })

    # Save thread-safe
    try:
        with _json_lock:
            with open(RULES_FILE, "w", encoding="utf-8") as f:
                json.dump(rules_list, f, indent=2, ensure_ascii=False)
            with open(LAST_FETCH_FILE, "w", encoding="utf-8") as f:
                json.dump(last_fetch_info, f, indent=2, ensure_ascii=False)
        logger.info(f"💾 Saved {total_rules} rules to {RULES_FILE}")
    except Exception as e:
        logger.error(f"❌ Failed to save rules: {e}")

    return rules_list, last_fetch_info

# ---------------------------
# Get last fetch info
# ---------------------------
def get_last_fetch_info():
    if not os.path.exists(LAST_FETCH_FILE):
        return {}
    try:
        with _json_lock:
            with open(LAST_FETCH_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.warning(f"❌ Failed to load last_fetch.json: {e}")
        return {}

# ---------------------------
# Manual test
# ---------------------------
if __name__ == "__main__":
    rules, info = update_rules(force=True)
    print(f"Fetched {len(rules)} rules total.")
    print(json.dumps(info, indent=2))
