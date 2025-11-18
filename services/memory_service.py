# services/memory_service.py — Advanced Personal Memory Service
import os
import json
from datetime import datetime, timezone
from typing import Dict, List
from difflib import SequenceMatcher
from services.community_service import update_community_memory, get_community_score

# --------------------------- Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

MEMORY_FILE_TEMPLATE = os.path.join(DATA_DIR, "memory_{user}.json")

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
        print(f"[memory_service] Failed to save JSON: {e}")

def _user_memory_file(user_email: str) -> str:
    safe_name = user_email.replace("@", "_at_").replace(".", "_dot_")
    return MEMORY_FILE_TEMPLATE.format(user=safe_name)

def _email_signature(email_obj: Dict) -> str:
    """Generate a signature string for personal memory matching."""
    return f"{email_obj.get('From','')}|{email_obj.get('Subject','')}"

# --------------------------- Fuzzy matching helper
def _fuzzy_match(a: str, b: str) -> float:
    """Return similarity ratio between two strings (0.0–1.0)."""
    return SequenceMatcher(None, a, b).ratio()

# --------------------------- Personal Memory Functions
def find_similar(email_obj: Dict, user_email: str, threshold: float = 0.85) -> List[Dict]:
    """
    Return memory entries that are similar to this email using fuzzy matching.
    Threshold controls sensitivity.
    """
    memory_file = _user_memory_file(user_email)
    memory = _load_json(memory_file)
    signature = _email_signature(email_obj)
    similar_entries = []
    for entry in memory:
        mem_sig = entry.get("signature", "")
        if mem_sig == signature or _fuzzy_match(signature, mem_sig) >= threshold:
            similar_entries.append(entry)
    return similar_entries

def add_to_memory(email_obj: Dict, user_email: str, community: bool = True):
    """
    Add email to personal memory and optionally to community memory.
    Avoid duplicates using signature + fuzzy check.
    """
    memory_file = _user_memory_file(user_email)
    memory = _load_json(memory_file)
    signature = _email_signature(email_obj)
    now = datetime.now(timezone.utc).isoformat()

    # Check for duplicates with fuzzy match
    duplicate_found = False
    for entry in memory:
        if entry.get("signature") == signature or _fuzzy_match(entry.get("signature", ""), signature) >= 0.9:
            entry["last_seen"] = now
            entry["count"] = entry.get("count", 1) + 1
            duplicate_found = True
            break

    if not duplicate_found:
        memory.append({
            "signature": signature,
            "email": email_obj,
            "first_seen": now,
            "last_seen": now,
            "count": 1,
            "quarantine": email_obj.get("quarantine", False)
        })

    _save_json(memory_file, memory)

    # Add to community memory if requested
    if community:
        update_community_memory(email_obj)

def get_personal_score(email_obj: Dict, user_email: str) -> float:
    """
    Calculate risk score based on personal memory + community memory.
    Returns a float between 0.0 and 1.0.
    """
    similar_entries = find_similar(email_obj, user_email)
    score = 0.0
    for entry in similar_entries:
        entry_score = min(entry.get("count", 1) / 10.0, 1.0)
        if entry.get("quarantine", False):
            entry_score += 0.3  # increase weight for quarantined emails
        score = max(score, min(entry_score, 1.0))

    # Include community memory influence
    community_score = get_community_score(email_obj)
    final_score = min(score + community_score, 1.0)
    return final_score

def list_memory_alerts(user_email: str, limit: int = 50) -> List[Dict]:
    """
    Return the most recent personal memory alerts for this user.
    """
    memory_file = _user_memory_file(user_email)
    memory = _load_json(memory_file)
    sorted_memory = sorted(memory, key=lambda x: x.get("last_seen", ""), reverse=True)
    return sorted_memory[:limit]
