# services/trusted_senders.py — AutoGuardian Premium Trusted Sender AI Shield
# Hybrid DNS + AI trusted sender verification system
# --------------------------------------------------

import os
import re
import json
import idna
import dns.resolver
from functools import lru_cache
from typing import Optional, Dict
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_PATH = os.path.join(DATA_DIR, "trusted_cache.json")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------------------------------------------------------------
# 1️⃣ Normalize + basic whitelist
# ---------------------------------------------------------------------
LOCAL_WHITELIST = {
    "google.com",
    "gmail.com",
    "instagram.com",
    "facebook.com",
    "meta.com",
    "paypal.com",
    "apple.com",
    "icloud.com",
    "microsoft.com",
    "outlook.com",
    "office365.com",
    "amazon.com",
    "linkedin.com",
    "twitter.com",
    "x.com",
    "github.com",
    "netflix.com",
    "spotify.com",
    "youtube.com",
    "openai.com"
}

# ---------------------------------------------------------------------
# 2️⃣ Helpers
# ---------------------------------------------------------------------
def normalize_domain(domain: str) -> str:
    """Normalize Unicode / punycode domains to ASCII for comparison."""
    if not domain:
        return ""
    try:
        domain = domain.strip().lower()
        domain = re.sub(r"^www\.", "", domain)
        return idna.encode(domain).decode("ascii")
    except Exception:
        return domain.lower()


def load_cache() -> Dict:
    if os.path.exists(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH, "r", encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict):
    with open(CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(cache, f, indent=2)


# ---------------------------------------------------------------------
# 3️⃣ DMARC/SPF DNS verification
# ---------------------------------------------------------------------
@lru_cache(maxsize=256)
def verify_dmarc_spf(domain: str) -> bool:
    """Check DNS records for DMARC or SPF presence."""
    try:
        dmarc_record = f"_dmarc.{domain}"
        dns.resolver.resolve(dmarc_record, "TXT", lifetime=2)
        return True
    except Exception:
        pass

    try:
        records = dns.resolver.resolve(domain, "TXT", lifetime=2)
        for r in records:
            txt = r.to_text()
            if "v=spf1" in txt:
                return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------
# 4️⃣ Main trust verification logic
# ---------------------------------------------------------------------
def is_trusted_sender(email: str, plan: str = "Free") -> bool:
    """
    Verify if sender is a trusted domain.
    - Premium users: full DMARC + cache checks
    - Free users: only local whitelist
    """
    if not email or "@" not in email:
        return False

    domain = email.split("@")[-1]
    domain = normalize_domain(domain)

    # Load cached results
    cache = load_cache()
    cached = cache.get(domain)
    if cached and (datetime.now().timestamp() - cached.get("timestamp", 0)) < 30 * 86400:
        return cached.get("trusted", False)

    # Step 1: Local whitelist
    if domain in LOCAL_WHITELIST:
        trusted = True
    else:
        # Step 2: DNS verification (only for Pro/Enterprise)
        trusted = verify_dmarc_spf(domain) if plan.lower() in ("pro", "enterprise") else False

    # Step 3: Cache the result
    cache[domain] = {"trusted": trusted, "timestamp": datetime.now().timestamp()}
    save_cache(cache)

    return trusted


# ---------------------------------------------------------------------
# 5️⃣ Diagnostic utility
# ---------------------------------------------------------------------
def test_trusted_senders():
    test_emails = [
        "security@paypal.com",
        "support@apple.com",
        "no-reply@іnstagram.com",  # Cyrillic i
        "offers@outlook-login.com",
        "alerts@google.com"
    ]
    for e in test_emails:
        result = is_trusted_sender(e, plan="Pro")
        print(f"{e:35} → {'✅ Trusted' if result else '⚠️ Not Trusted'}")


if __name__ == "__main__":
    print("🔍 Testing Trusted Sender AI Shield...\n")
    test_trusted_senders()
