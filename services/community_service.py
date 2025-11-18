# services/community_service.py — Advanced Community Memory Service (weighted + decay + safe auto-update)
import os
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple

# --------------------------- Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

COMMUNITY_FILE = os.path.join(DATA_DIR, "community_memory.json")
WEIGHTS_FILE_FLAG = os.path.join(DATA_DIR, "collective_weights_last_run.txt")  # rate-limit flag

# Lazy imports (avoid hard dependency at import time)
def _load_collective_weights_safe() -> Dict[str, Dict[str, float]]:
    """
    Safe loader for collective weights: {'senders': {...}, 'rules': {...}}
    Falls back to empty dicts if file/tooling not available.
    """
    try:
        from services.collective_ai import load_collective_weights
        w = load_collective_weights() or {}
        return {
            "senders": w.get("senders", {}) or {},
            "rules": w.get("rules", {}) or {},
        }
    except Exception:
        # Fallback to raw file if available
        path = os.path.join(DATA_DIR, "collective_ai_weights.json")
        try:
            if os.path.exists(path):
                data = json.load(open(path, "r", encoding="utf-8"))
                return {
                    "senders": data.get("senders", {}) or {},
                    "rules": data.get("rules", {}) or {},
                }
        except Exception:
            pass
    return {"senders": {}, "rules": {}}

def _maybe_update_collective_weights(rate_limit_hours: int = 24) -> None:
    """
    Optional: rate-limited trigger to refresh collective weights.
    Safe no-op if trainer is unavailable.
    """
    try:
        last = None
        if os.path.exists(WEIGHTS_FILE_FLAG):
            try:
                last_str = open(WEIGHTS_FILE_FLAG, "r", encoding="utf-8").read().strip()
                last = datetime.fromisoformat(last_str)
            except Exception:
                last = None

        now = datetime.now(timezone.utc)
        if not last or (now - last) >= timedelta(hours=rate_limit_hours):
            try:
                from services.collective_trainer import update_collective_ai_weights
                update_collective_ai_weights()
                with open(WEIGHTS_FILE_FLAG, "w", encoding="utf-8") as f:
                    f.write(now.isoformat())
            except Exception:
                # Silent: training is optional / external
                pass
    except Exception:
        pass

# --------------------------- JSON helpers
def _load_json(path: str) -> List[Dict]:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def _save_json(path: str, data: List[Dict]):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[community_service] Failed to save JSON: {e}")

# --------------------------- Utilities (decay, signatures, pruning)
def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def _parse_iso(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return datetime.now(timezone.utc)

def _email_signature(email_obj: Dict) -> str:
    """Generate a simple unique signature for an email (From|Subject)."""
    return f"{email_obj.get('From','')}|{email_obj.get('Subject','')}"

def _decayed_count(count: int, last_seen_iso: str, half_life_days: int = 60) -> float:
    """
    Exponential decay so older community sightings lose influence.
    decayed = count * 0.5 ** (days / half_life)
    """
    try:
        last_seen = _parse_iso(last_seen_iso)
        days = max(0.0, (datetime.now(timezone.utc) - last_seen).days)
        if half_life_days <= 0:
            return float(count)
        factor = 0.5 ** (days / float(half_life_days))
        return float(count) * float(factor)
    except Exception:
        return float(count)

def prune_community_memory(max_age_days: int = 180, max_records: int = 50000) -> Tuple[int, int]:
    """
    Prune very old records and enforce soft size limit.
    Returns (removed_by_age, removed_by_size).
    """
    mem = _load_json(COMMUNITY_FILE)
    if not mem:
        return (0, 0)

    now = datetime.now(timezone.utc)
    # Remove by age
    fresh = []
    removed_age = 0
    for m in mem:
        last_seen = _parse_iso(m.get("last_seen", _now_iso()))
        if (now - last_seen).days <= max_age_days:
            fresh.append(m)
        else:
            removed_age += 1

    # Enforce soft size limit (keep most recent)
    removed_size = 0
    if len(fresh) > max_records:
        fresh.sort(key=lambda x: x.get("last_seen", ""), reverse=True)
        removed_size = len(fresh) - max_records
        fresh = fresh[:max_records]

    if removed_age or removed_size:
        _save_json(COMMUNITY_FILE, fresh)

    return (removed_age, removed_size)

# --------------------------- Community Memory Functions
def update_community_memory(email_obj: Dict, *, auto_update_weights: bool = True):
    """
    Add or update a scanned email in community memory.
    Tracks:
      - Signature
      - Count of occurrences (with timestamp)
      - First seen / last seen timestamps
      - Optional quarantine alerts
    Optionally triggers a (rate-limited) collective weight refresh.
    """
    community_memory = _load_json(COMMUNITY_FILE)
    signature = _email_signature(email_obj)
    now = _now_iso()

    found = False
    for item in community_memory:
        if item.get("signature") == signature:
            item["count"] = item.get("count", 1) + 1
            item["last_seen"] = now
            # propagate quarantine flag if present
            if email_obj.get("quarantine", False):
                item["quarantine"] = True
            found = True
            break

    if not found:
        community_memory.append({
            "signature": signature,
            "email": email_obj,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "quarantine": email_obj.get("quarantine", False)
        })

    _save_json(COMMUNITY_FILE, community_memory)

    # Optional: prune + refresh weights (rate-limited)
    try:
        prune_community_memory()
    except Exception:
        pass

    if auto_update_weights:
        _maybe_update_collective_weights(rate_limit_hours=24)

def check_community_memory(email_obj: Dict) -> bool:
    """
    Check if the email exists in community memory.
    Returns True if a match is found, else False.
    """
    community_memory = _load_json(COMMUNITY_FILE)
    signature = _email_signature(email_obj)
    for item in community_memory:
        if item.get("signature") == signature:
            return True
    return False

def get_community_score(email_obj: Dict) -> float:
    """
    Calculate a risk score contribution from community memory.
    Returns a value between 0 and 1.

    Sources:
      - Community recurrence (decayed by time)
      - Quarantine boost
      - Adaptive weights:
          * sender weights from collective_ai_weights.json
          * rule weights (if email_obj['matched_rules'] present)
    """
    community_memory = _load_json(COMMUNITY_FILE)
    signature = _email_signature(email_obj)

    # Base from community memory
    base_score = 0.0
    for item in community_memory:
        if item.get("signature") == signature:
            # Decay based on how long ago it was seen
            decayed = _decayed_count(
                count=int(item.get("count", 1)),
                last_seen_iso=item.get("last_seen", _now_iso()),
                half_life_days=60,
            )
            # Normalize: each ~10 decayed sightings ~= 1.0 before boosts/weights
            base_score = min(decayed / 10.0, 1.0)
            if item.get("quarantine", False):
                base_score += 0.3
            break

    # Adaptive weights (sender + rules)
    weights = _load_collective_weights_safe()
    sender = email_obj.get("From", "") or ""
    sender_w = 1.0
    if sender:
        sender_w = float(weights.get("senders", {}).get(sender, 1.0) or 1.0)

    rule_w = 1.0
    try:
        matched_rules = email_obj.get("matched_rules", "") or ""
        if isinstance(matched_rules, list):
            rules_list = matched_rules
        else:
            rules_list = [r.strip() for r in str(matched_rules).split(",") if r.strip()]
        for r in rules_list:
            w = float(weights.get("rules", {}).get(r, 1.0) or 1.0)
            # Use the strongest applicable rule weight
            if w > rule_w:
                rule_w = w
    except Exception:
        pass

    # Apply weights (capped to avoid runaway)
    weight_multiplier = min(max(sender_w, rule_w), 2.5)
    scored = base_score * weight_multiplier

    # Final clamp to [0,1]
    return max(0.0, min(scored, 1.0))

def list_community_alerts(limit: int = 50) -> List[Dict]:
    """
    Return a list of the most recent community memory alerts.
    Useful for dashboards or analytics.
    """
    community_memory = _load_json(COMMUNITY_FILE)
    sorted_alerts = sorted(community_memory, key=lambda x: x.get("last_seen", ""), reverse=True)
    return sorted_alerts[:limit]
