# services/attachment_analyzer.py — AutoGuardian Attachment Analyzer
# ------------------------------------------------------------------
# Detects suspicious or malicious attachments via:
#  - File type heuristics (.exe, .vbs, .js, .iso, .zip, etc.)
#  - Hash-based VirusTotal lookups (optional)
#  - YARA or local pattern analysis (optional stub)
# Integrates with the main scanner and returns explainable verdicts.

import os
import re
import json
import hashlib
import mimetypes
from datetime import datetime, timezone
from typing import List, Dict, Any

import requests

# ------------------------------------------------------------------
# CONFIG
# ------------------------------------------------------------------
VT_API = os.environ.get("VT_API_KEY", "").strip()
ENABLE_YARA = False  # Future: optional local YARA engine

# Directory for caching / logs
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data", "attachments")
os.makedirs(DATA_DIR, exist_ok=True)

HASH_CACHE_FILE = os.path.join(DATA_DIR, "vt_hash_cache.json")


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------
def _load_json(path: str) -> dict:
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def _save_json(path: str, data: dict):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

def _hash_file(file_path: str) -> str:
    """Compute SHA256 hash of file."""
    h = hashlib.sha256()
    try:
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                h.update(chunk)
    except Exception:
        return ""
    return h.hexdigest()


# ------------------------------------------------------------------
# VirusTotal Lookup
# ------------------------------------------------------------------
def vt_lookup_filehash(file_hash: str) -> Dict[str, Any]:
    """Check a file hash on VirusTotal (if API key configured)."""
    if not VT_API:
        return {"source": "virustotal", "available": False, "hash": file_hash}

    try:
        url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
        r = requests.get(url, headers={"x-apikey": VT_API}, timeout=15)
        if r.status_code == 200:
            data = r.json().get("data", {}).get("attributes", {})
            stats = data.get("last_analysis_stats", {})
            mal = int(stats.get("malicious", 0))
            susp = int(stats.get("suspicious", 0))
            verdict = (
                "malicious" if mal >= 2 else
                "suspicious" if (mal + susp) >= 1 else
                "clean"
            )
            return {
                "source": "virustotal",
                "available": True,
                "hash": file_hash,
                "verdict": verdict,
                "stats": stats,
                "scan_date": data.get("last_analysis_date"),
            }
        elif r.status_code == 404:
            return {
                "source": "virustotal",
                "available": True,
                "hash": file_hash,
                "verdict": "unknown",
                "error": "Not found on VirusTotal"
            }
        else:
            return {
                "source": "virustotal",
                "available": True,
                "hash": file_hash,
                "verdict": "error",
                "error": f"HTTP {r.status_code}"
            }
    except Exception as e:
        return {
            "source": "virustotal",
            "available": True,
            "hash": file_hash,
            "verdict": "error",
            "error": str(e)[:200]
        }


# ------------------------------------------------------------------
# Heuristic Detection
# ------------------------------------------------------------------
SUSPICIOUS_EXTENSIONS = (
    ".exe", ".scr", ".js", ".vbs", ".bat", ".cmd", ".lnk", ".dll",
    ".ps1", ".iso", ".img", ".cab", ".zip", ".rar", ".7z"
)
BLOCKLIST_KEYWORDS = ("password", "invoice", "urgent", "login", "update")

def heuristic_analysis(file_path: str) -> Dict[str, Any]:
    name = os.path.basename(file_path)
    ext = os.path.splitext(name)[1].lower()
    mime, _ = mimetypes.guess_type(file_path)

    suspicious = ext in SUSPICIOUS_EXTENSIONS
    keyword_hit = any(k in name.lower() for k in BLOCKLIST_KEYWORDS)
    risk = 0

    if suspicious:
        risk += 60
    if keyword_hit:
        risk += 20

    verdict = "High" if risk >= 70 else "Suspicious" if risk >= 30 else "Safe"
    reasons = []
    if suspicious:
        reasons.append(f"Executable or compressed file type ({ext})")
    if keyword_hit:
        reasons.append(f"Filename contains sensitive keyword ({name})")

    return {
        "file": name,
        "ext": ext,
        "mime": mime or "unknown",
        "verdict": verdict,
        "reasons": reasons,
        "risk_score": risk
    }


# ------------------------------------------------------------------
# Attachment Analysis (Main Entry)
# ------------------------------------------------------------------
def analyze_attachments(email_obj: Dict[str, Any], attachment_dir: str = None) -> Dict[str, Any]:
    """
    Analyze attachments listed in email_obj['attachments'].
    Each attachment should have a 'path' or 'filename' field.
    Returns aggregated verdict and detailed list.
    """
    attachments = email_obj.get("attachments") or []
    if not attachments:
        return {"verdict": "none", "details": [], "keys_present": bool(VT_API)}

    vt_cache = _load_json(HASH_CACHE_FILE)
    results = []
    overall_verdict = "clean"

    for att in attachments:
        path = att.get("path") or ""
        filename = att.get("filename") or os.path.basename(path)
        local_result = heuristic_analysis(path)
        vt_result = {}
        vt_verdict = "unknown"

        # Hash + VirusTotal check (if available)
        if os.path.exists(path):
            file_hash = _hash_file(path)
            if file_hash:
                if file_hash in vt_cache:
                    vt_result = vt_cache[file_hash]
                else:
                    vt_result = vt_lookup_filehash(file_hash)
                    vt_cache[file_hash] = vt_result
                    _save_json(HASH_CACHE_FILE, vt_cache)
                vt_verdict = vt_result.get("verdict", "unknown")

        # Combine heuristic + VT results
        if vt_verdict in ("malicious", "suspicious"):
            combined_risk = "High" if vt_verdict == "malicious" else "Suspicious"
        else:
            combined_risk = local_result["verdict"]

        results.append({
            "filename": filename,
            "path": path,
            "local": local_result,
            "vt": vt_result,
            "combined_verdict": combined_risk
        })

        # Escalate global verdict
        if combined_risk == "High":
            overall_verdict = "malicious"
        elif combined_risk == "Suspicious" and overall_verdict != "malicious":
            overall_verdict = "suspicious"

    return {
        "verdict": overall_verdict,
        "details": results,
        "keys_present": bool(VT_API),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }


# ------------------------------------------------------------------
# Manual Test
# ------------------------------------------------------------------
if __name__ == "__main__":
    test_email = {
        "Subject": "Urgent invoice attached",
        "From": "attacker@fakebank.com",
        "attachments": [
            {"path": "sample.exe", "filename": "invoice_update.exe"},
            {"path": "document.zip", "filename": "document.zip"}
        ]
    }
    result = analyze_attachments(test_email)
    print(json.dumps(result, indent=2))
