# services/osint_enrichment.py — OSINT reputation (VirusTotal / AbuseIPDB)
import os
import re
import json
import ipaddress
from typing import Dict, Any, List, Tuple
from urllib.parse import urlparse

import requests

VT_API = os.environ.get("VT_API_KEY", "").strip()
ABUSE_API = os.environ.get("ABUSEIPDB_API_KEY", "").strip()

URL_RE = re.compile(r"https?://[^\s)>\]\"']+", re.I)

def _unique(seq):
    seen = set()
    out = []
    for x in seq:
        if x and x not in seen:
            out.append(x); seen.add(x)
    return out

def _extract_domains_and_ips(text: str) -> Tuple[List[str], List[str]]:
    urls = URL_RE.findall(text or "")
    domains = []
    ips = []
    for u in urls:
        try:
            host = urlparse(u).netloc.split("@")[-1]
            host = host.split(":")[0]
            # IP?
            try:
                ipaddress.ip_address(host)
                ips.append(host)
            except ValueError:
                domains.append(host.lower())
        except Exception:
            pass
    return _unique(domains), _unique(ips)

def _vt_domain_report(domain: str) -> Dict[str, Any]:
    if not VT_API:
        return {"source": "virustotal", "domain": domain, "available": False}
    try:
        r = requests.get(
            f"https://www.virustotal.com/api/v3/domains/{domain}",
            headers={"x-apikey": VT_API},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json()
            cat = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
            mal = int(cat.get("malicious", 0)) + int(cat.get("suspicious", 0))
            verdict = "malicious" if mal >= 2 else ("suspicious" if mal == 1 else "clean")
            return {
                "source": "virustotal",
                "domain": domain,
                "available": True,
                "verdict": verdict,
                "stats": cat,
            }
        return {"source": "virustotal", "domain": domain, "available": True, "error": r.text[:200]}
    except Exception as e:
        return {"source": "virustotal", "domain": domain, "available": True, "error": str(e)[:200]}

def _abuse_ip_report(ip: str) -> Dict[str, Any]:
    if not ABUSE_API:
        return {"source": "abuseipdb", "ip": ip, "available": False}
    try:
        r = requests.get(
            "https://api.abuseipdb.com/api/v2/check",
            params={"ipAddress": ip, "maxAgeInDays": "90"},
            headers={"Key": ABUSE_API, "Accept": "application/json"},
            timeout=12,
        )
        if r.status_code == 200:
            data = r.json().get("data", {})
            score = int(data.get("abuseConfidenceScore", 0))
            verdict = "malicious" if score >= 75 else ("suspicious" if score >= 25 else "clean")
            return {
                "source": "abuseipdb",
                "ip": ip,
                "available": True,
                "verdict": verdict,
                "score": score,
                "totalReports": data.get("totalReports", 0),
            }
        return {"source": "abuseipdb", "ip": ip, "available": True, "error": r.text[:200]}
    except Exception as e:
        return {"source": "abuseipdb", "ip": ip, "available": True, "error": str(e)[:200]}

def enrich(email: Dict[str, Any]) -> Dict[str, Any]:
    """Extract domains/IPs from email and query OSINT (if keys present)."""
    subject = email.get("Subject", "") or ""
    body = email.get("Body", "") or ""
    joined = f"{subject}\n{body}"

    domains, ips = _extract_domains_and_ips(joined)
    domain_reports = [_vt_domain_report(d) for d in domains][:10]  # cap calls
    ip_reports = [_abuse_ip_report(i) for i in ips][:10]

    # Aggregate a coarse verdict
    verdict = "clean"
    if any(r.get("verdict") == "malicious" for r in domain_reports + ip_reports):
        verdict = "malicious"
    elif any(r.get("verdict") == "suspicious" for r in domain_reports + ip_reports):
        verdict = "suspicious"

    return {
        "verdict": verdict,
        "domains": domain_reports,
        "ips": ip_reports,
        "keys_present": bool(VT_API or ABUSE_API),
    }
