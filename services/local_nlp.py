# services/local_nlp.py — Advanced Local NLP + Community Integration + Collective Learning (upgraded)
import os
import re
import string
import json
import sqlite3
import joblib
from datetime import datetime
from typing import Dict, Tuple, List, Optional

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import VotingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from services.community_service import get_community_score
from services.memory_service import find_similar

# --------------------------- Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
MODEL_PATH = os.path.join(DATA_DIR, "local_nlp_model.pkl")
VECTORIZER_PATH = os.path.join(DATA_DIR, "vectorizer.pkl")
SCAN_HISTORY_FILE = os.path.join(DATA_DIR, "scan_history.json")
DB_PATH = os.path.join(DATA_DIR, "autoguardian.db")
WEIGHTS_JSON = os.path.join(DATA_DIR, "collective_ai_weights.json")

# --------------------------- Model load (lazy, safe)
try:
    ensemble_model: VotingClassifier = joblib.load(MODEL_PATH)
    vectorizer: TfidfVectorizer = joblib.load(VECTORIZER_PATH)
except Exception:
    ensemble_model = None
    vectorizer = None

# --------------------------- Utils
def _load_collective_weights_safe() -> Dict[str, Dict[str, float]]:
    try:
        from services.collective_ai import load_collective_weights
        w = load_collective_weights() or {}
        return {
            "senders": w.get("senders", {}) or {},
            "rules": w.get("rules", {}) or {},
        }
    except Exception:
        try:
            if os.path.exists(WEIGHTS_JSON):
                data = json.load(open(WEIGHTS_JSON, "r", encoding="utf-8"))
                return {"senders": data.get("senders", {}) or {}, "rules": data.get("rules", {}) or {}}
        except Exception:
            pass
    return {"senders": {}, "rules": {}}

def _clamp(x: float, lo: float, hi: float) -> float:
    return hi if x > hi else (lo if x < lo else x)

# --------------------------- Preprocessing
def preprocess_email(text: str) -> str:
    """Normalize and clean email content for NLP model."""
    text = (text or "").lower()
    text = re.sub(r"<.*?>", " ", text)            # Remove HTML
    text = re.sub(r"https?://\S+", " ", text)     # Remove URLs
    text = re.sub(r"\S+@\S+", " ", text)          # Remove email addresses
    text = re.sub(rf"[{re.escape(string.punctuation)}]", " ", text)  # Remove punctuation
    text = re.sub(r"\s+", " ", text).strip()      # Normalize whitespace
    return text

# --------------------------- Training (manual programmatic)
def train_local_model(emails: List[str], labels: List[int]):
    """
    Train a VotingClassifier on TF-IDF features of emails.
    Integrates LogisticRegression + RandomForest.
    """
    global ensemble_model, vectorizer
    if not emails or not labels:
        print("⚠️ local_nlp.train_local_model: no data provided")
        return

    if len(set(labels)) < 2:
        # To avoid single-class failures
        print("⚠️ local_nlp.train_local_model: only one class present; adding synthetic negatives/positives")
        synth_phish = [
            "urgent action required verify your account",
            "your password has expired click to reset",
            "win a prize click to claim",
        ]
        synth_safe = [
            "weekly newsletter update",
            "team meeting agenda",
            "invoice attached for your records",
        ]
        # Heuristic to balance classes
        if 1 in labels:
            emails += synth_safe
            labels += [0] * len(synth_safe)
        else:
            emails += synth_phish
            labels += [1] * len(synth_phish)

    preprocessed = [preprocess_email(e) for e in emails]
    vectorizer = TfidfVectorizer(max_features=15000, ngram_range=(1, 3), analyzer="word")
    X = vectorizer.fit_transform(preprocessed)

    lr = LogisticRegression(max_iter=2000, solver="liblinear", random_state=42)
    rf = RandomForestClassifier(n_estimators=200, random_state=42)

    ensemble_model = VotingClassifier(
        estimators=[("lr", lr), ("rf", rf)],
        voting="soft"
    )
    ensemble_model.fit(X, labels)

    os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
    joblib.dump(ensemble_model, MODEL_PATH)
    joblib.dump(vectorizer, VECTORIZER_PATH)

    print(f"✅ Local NLP model trained at {datetime.utcnow().isoformat()} with {len(emails)} samples")

# --------------------------- Auto-train helper from history (JSON + optional DB)
def train_from_history(min_samples: int = 50) -> bool:
    """
    Train from scan_history.json and, if available, augment with collective_metrics in SQLite.
    Returns True if a model was (re)trained.
    """
    emails: List[str] = []
    labels: List[int] = []

    # JSON scan history (optional)
    try:
        if os.path.exists(SCAN_HISTORY_FILE):
            hist = json.load(open(SCAN_HISTORY_FILE, "r", encoding="utf-8"))
            for item in hist:
                e = item.get("email", {})
                txt = f"{e.get('From','')} {e.get('Subject','')} {e.get('Body','')}"
                emails.append(txt)
                risk = item.get("risk_level", "Safe")
                labels.append(1 if str(risk).lower().startswith("high") else 0)
    except Exception as e:
        print(f"⚠️ local_nlp.train_from_history: failed reading scan_history.json: {e}")

    # SQLite collective_metrics (optional)
    try:
        if os.path.exists(DB_PATH):
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT sender, subject, score, risk_level FROM collective_metrics")
            rows = c.fetchall()
            conn.close()
            for sender, subject, score, rlevel in rows:
                emails.append(f"{sender or ''} {subject or ''}")
                if rlevel:
                    labels.append(1 if str(rlevel).lower().startswith("high") else 0)
                else:
                    labels.append(1 if (score or 0) >= 7 else 0)
    except Exception as e:
        print(f"⚠️ local_nlp.train_from_history: failed reading DB: {e}")

    if len(emails) < min_samples:
        print(f"⚠️ local_nlp.train_from_history: only {len(emails)} samples (<{min_samples}), training anyway with augmentation")
    train_local_model(emails, labels)
    return True

# --------------------------- Scoring
def local_nlp_score(email_obj: Dict) -> Tuple[float, Dict]:
    """
    Score a single email object.
    Returns a numeric score (0..100) and a detailed explanation dictionary.
    Integrates:
      - TF-IDF + VotingClassifier (probability->0..100)
      - Community risk (already decayed/weighted inside community_service)
      - Memory similarity boost
      - Adaptive collective weights (sender/rule) multiplier
    """
    if ensemble_model is None or vectorizer is None:
        return 0.0, {"score": 0.0, "risk_level": "Safe", "details": "Model not trained"}

    # Combine key fields
    content = f"{email_obj.get('From','')} {email_obj.get('Subject','')} {email_obj.get('Body','')}"
    content = preprocess_email(content)
    X = vectorizer.transform([content])

    # Base probability from local model
    prob = float(ensemble_model.predict_proba(X)[0][1])  # phishing probability [0..1]
    score = round(prob * 100.0, 2)  # normalize to 0..100, consistent with ensemble

    # Community risk integration (already 0..1 with decay + weights)
    community_risk = float(get_community_score(email_obj) or 0.0)
    score += community_risk * 5.0

    # Memory similarity / collective learning
    # Use user email if available; fall back to sender (keeps behavior stable)
    user_key = email_obj.get("user_email") or email_obj.get("From", "")
    similar_entries = find_similar(email_obj, user_key)
    memory_boost = min(len(similar_entries), 5)
    score += memory_boost * 3.0

    # Adaptive collective weights (sender + strongest rule)
    weights = _load_collective_weights_safe()
    sender = email_obj.get("From", "") or ""
    sender_w = float(weights.get("senders", {}).get(sender, 1.0) or 1.0)

    rule_w = 1.0
    matched_rules_raw = email_obj.get("matched_rules", "") or ""
    try:
        if isinstance(matched_rules_raw, list):
            rules_list = [str(r).strip() for r in matched_rules_raw if str(r).strip()]
        else:
            rules_list = [r.strip() for r in str(matched_rules_raw).split(",") if r.strip()]
        for r in rules_list:
            w = float(weights.get("rules", {}).get(r, 1.0) or 1.0)
            if w > rule_w:
                rule_w = w
    except Exception:
        pass

    collective_multiplier = min(max(sender_w, rule_w), 2.5)  # cap runaway
    adjusted = score * collective_multiplier

    # Final clamp
    score = _clamp(adjusted, 0.0, 100.0)

    # Determine risk level on consistent thresholds
    if score < 20:
        risk_level = "Safe"
    elif score < 60:
        risk_level = "Suspicious"
    else:
        risk_level = "High Risk"

    explanation = {
        "score": score,
        "risk_level": risk_level,
        "probability": prob,
        "community_risk": community_risk,
        "memory_boost": memory_boost,
        "num_similar_memory": len(similar_entries),
        "collective_multiplier": round(collective_multiplier, 2),
        "top_features": vectorizer.get_feature_names_out()[:10].tolist() if hasattr(vectorizer, "get_feature_names_out") else [],
        "details": "VotingClassifier (Logistic + RF) on TF-IDF uni+bi+tri-grams + community + memory boost + collective weights"
    }
    return score, explanation

# --------------------------- Batch scoring helper
def local_nlp_batch(emails: List[Dict]) -> List[Dict]:
    """Score multiple emails and attach detailed NLP scoring info."""
    results = []
    for email in emails:
        score, details = local_nlp_score(email)
        results.append({
            "email_id": email.get("id"),
            "score": score,
            "risk_level": details["risk_level"],
            "nlp_details": details
        })
    return results
