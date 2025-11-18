# services/similarity_detector.py — template reuse / semantic similarity
import os
import json
from typing import Dict, Any, List, Tuple

from math import isfinite

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SK_OK = True
except Exception:
    SK_OK = False

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCAN_HISTORY = os.path.join(DATA_DIR, "scan_history.json")

def _load_history() -> List[Dict[str, Any]]:
    if not os.path.exists(SCAN_HISTORY):
        return []
    try:
        return json.load(open(SCAN_HISTORY, "r", encoding="utf-8"))
    except Exception:
        return []

def detect_template_reuse(email: Dict[str, Any], top_k: int = 1) -> Dict[str, Any]:
    """Return highest similarity vs past high-risk/quarantined emails."""
    if not SK_OK:
        return {"available": False, "reason": "sklearn not installed"}
    hist = _load_history()
    if not hist:
        return {"available": True, "top_match": None, "similarity": 0.0}

    corpus = []
    labels = []
    for r in hist:
        if r.get("risk_level") in ("High", "High Risk") or r.get("quarantine"):
            e = r.get("email", {})
            text = f"{e.get('Subject','')} || {e.get('Body','')}"
            corpus.append(text)
            labels.append((e.get("From"), e.get("Subject")))

    if not corpus:
        return {"available": True, "top_match": None, "similarity": 0.0}

    vec = TfidfVectorizer(max_features=8000, ngram_range=(1, 2), stop_words="english")
    X = vec.fit_transform(corpus + [f"{email.get('Subject','')} || {email.get('Body','')}"])
    sims = cosine_similarity(X[-1], X[:-1]).flatten()
    if sims.size == 0:
        return {"available": True, "top_match": None, "similarity": 0.0}

    idx = int(sims.argmax())
    sim = float(sims[idx])
    match = {"from": labels[idx][0], "subject": labels[idx][1]} if labels else None

    return {"available": True, "top_match": match, "similarity": round(sim, 3)}
