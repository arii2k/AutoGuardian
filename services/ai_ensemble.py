# services/ai_ensemble.py — Hybrid AI Ensemble for Phishing Detection
# (extended script coverage, collective weights, multilingual spoof detection)
import os
import sys
import re
import unicodedata
import logging

# Optional language detection (safe if not installed)
try:
    import langdetect
    _LANGDETECT_OK = True
except Exception:
    _LANGDETECT_OK = False

logger = logging.getLogger("AutoGuardian.AIEnsemble")
if not any(isinstance(h, logging.StreamHandler) for h in logger.handlers):
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
    logger.addHandler(ch)
logger.setLevel(logging.INFO)

# --------------------------------------------------------------------
# 🔧 Ensure ai_phishing/ai_detector.py is importable regardless of path
# --------------------------------------------------------------------
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICES_DIR = os.path.dirname(CURRENT_DIR)
BACKEND_DIR = os.path.dirname(SERVICES_DIR)
AI_DIR = os.path.join(SERVICES_DIR, "ai_phishing")

for path in [AI_DIR, SERVICES_DIR, BACKEND_DIR]:
    if path not in sys.path:
        sys.path.insert(0, path)

# ---------------------------
# Import detectors safely
# ---------------------------
detect_phishing = None
nlp_score_email = None
try:
    from services.ai_phishing.ai_detector import detect_phishing, nlp_score_email
    print("[ai_ensemble] ✅ Imported from services.ai_phishing.ai_detector")
except Exception as e:
    print(f"[ai_ensemble] ⚠️ Could not import from services.ai_phishing.ai_detector: {e}")
    try:
        from ai_phishing.ai_detector import detect_phishing, nlp_score_email
        print("[ai_ensemble] ✅ Imported from ai_phishing.ai_detector (fallback)")
    except Exception as e2:
        print(f"[ai_ensemble] ❌ Failed to import ai_detector: {e2}")
        detect_phishing = None
        nlp_score_email = None

# Local NLP (optional)
try:
    from services.local_nlp import local_nlp_score
    LOCAL_NLP_AVAILABLE = True
except Exception:
    LOCAL_NLP_AVAILABLE = False
    def local_nlp_score(_): return (0, "Unavailable")

# ---------------------------
# Collective weights (safe loader)
# ---------------------------
def _load_collective_weights_safe():
    """Return {'senders': {...}, 'rules': {...}} or empty dicts if unavailable."""
    try:
        from services.collective_ai import load_collective_weights
        w = load_collective_weights() or {}
        return {"senders": w.get("senders", {}) or {}, "rules": w.get("rules", {}) or {}}
    except Exception:
        try:
            path = os.path.join(SERVICES_DIR, "data", "collective_ai_weights.json")
            if os.path.exists(path):
                import json
                data = json.load(open(path, "r", encoding="utf-8"))
                return {"senders": data.get("senders", {}) or {}, "rules": data.get("rules", {}) or {}}
        except Exception:
            pass
    return {"senders": {}, "rules": {}}

# ---------------------------
# Weighted Hybrid Ensemble Config
# ---------------------------
WEIGHTS = {"zero_shot": 0.4, "transformer": 0.4, "local_nlp": 0.2}

# ---------------------------
# Unicode / Linguistic detectors  (expanded coverage)
# ---------------------------
_SCRIPT_KEYS = (
    # European
    "LATIN", "CYRILLIC", "GREEK",

    # Middle Eastern / Central Asian
    "ARABIC", "HEBREW", "ARMENIAN", "SYRIAC", "THAANA", "GEORGIAN",

    # South / Southeast Asian
    "DEVANAGARI", "BENGALI", "GURMUKHI", "GUJARATI", "ORIYA", "TAMIL", "TELUGU",
    "KANNADA", "MALAYALAM", "SINHALA", "THAI", "LAO", "TIBETAN", "MYANMAR", "KHMER",

    # East Asian
    "CJK", "HAN", "HIRAGANA", "KATAKANA", "HANGUL", "BOPOMOFO", "MONGOLIAN",

    # African & Indigenous scripts
    "ETHIOPIC", "NKO", "TIFINAGH", "CHEROKEE", "CANADIAN SYLLABICS",
    "OSAGE", "VAI", "MENDE", "BAMUM", "ADLAM",

    # Ancient / historic scripts (homoglyph sources)
    "RUNIC", "GLAGOLITIC", "OLD ITALIC", "LINEAR B", "CUNEIFORM",
    "PHOENICIAN", "OGHAM", "OLD PERSIAN", "EGYPTIAN HIEROGLYPH", "LYCIAN"
)

_INVISIBLE_CTRL_RE = re.compile(r"[\u200B-\u200F\u2060\u2066-\u2069]")
_BIDI_OVERRIDE_RE  = re.compile(r"[\u202A-\u202E]")
_EMOJI_RE = re.compile(r"[\U0001F000-\U0001FAFF\U0001F1E6-\U0001F1FF]")

def _count_scripts(text: str):
    counts = {k: 0 for k in _SCRIPT_KEYS}
    for ch in text:
        try:
            name = unicodedata.name(ch)
        except ValueError:
            continue
        for key in _SCRIPT_KEYS:
            if key in name:
                counts[key] += 1
                break
    return counts

def detect_mixed_scripts(text: str) -> tuple[bool, str]:
    """Detect multiple writing systems in one text."""
    if not text:
        return False, ""
    counts = _count_scripts(text)
    active = [k for k, v in counts.items() if v > 0]
    if len(active) > 1:
        return True, f"Mixed scripts detected: {', '.join(active)}"
    return False, ""

def detect_invisible_controls(text: str) -> tuple[bool, str]:
    """Detect hidden Unicode control characters or direction markers."""
    if not text:
        return False, ""
    if _INVISIBLE_CTRL_RE.search(text):
        return True, "Contains invisible Unicode control characters"
    if _BIDI_OVERRIDE_RE.search(text):
        return True, "Contains bidirectional override characters"
    return False, ""

def detect_emoji_spoofing(text: str) -> tuple[bool, str]:
    """Detect emojis or pictographs that might be used for spoofing."""
    if not text:
        return False, ""
    if _EMOJI_RE.search(text):
        return True, "Emoji or pictographic characters present (possible spoofing)"
    return False, ""

def detect_homoglyph_domain(sender: str) -> tuple[bool, str]:
    """Detect domains containing visually deceptive or mixed-script letters."""
    if not sender:
        return False, ""
    try:
        domain = sender.split("@", 1)[-1]
    except Exception:
        return False, ""
    nfkc = unicodedata.normalize("NFKC", domain)
    if nfkc != domain:
        return True, "Sender domain changes under Unicode normalization (homoglyph risk)"
    counts = _count_scripts(domain)
    if any(counts[k] for k in _SCRIPT_KEYS if k != "LATIN"):
        return True, "Non-Latin characters detected in sender domain (possible spoof)"
    return False, ""

def detect_language_mismatch(text: str, expected_lang: str = "en") -> tuple[bool, str]:
    """Detect if language differs from expected (requires langdetect)."""
    if not _LANGDETECT_OK or not text.strip():
        return False, ""
    try:
        detected = langdetect.detect(text)
        if detected and expected_lang and detected != expected_lang:
            return True, f"Language mismatch: expected '{expected_lang}', detected '{detected}'"
    except Exception:
        pass
    return False, ""

# ---------------------------
# Ensemble Scoring with Explanations
# ---------------------------
def ensemble_score_with_reasons(email_obj: dict, expected_lang: str = "en") -> tuple[float, list]:
    subject = email_obj.get("Subject", "") or ""
    body = email_obj.get("Body", "") or ""
    sender = email_obj.get("From", "") or ""
    matched_rules_raw = email_obj.get("matched_rules", "") or ""

    # normalize rules
    if isinstance(matched_rules_raw, list):
        matched_rules = [str(r).strip() for r in matched_rules_raw if str(r).strip()]
    elif isinstance(matched_rules_raw, str):
        matched_rules = [r.strip() for r in matched_rules_raw.split(",") if r.strip()]
    else:
        matched_rules = []

    zs_score = tr_score = local_score = 0.0
    reasons: list[str] = []

    # --- Zero-Shot
    if detect_phishing:
        try:
            zs_result = detect_phishing(subject, body, sender)
            zs_score = float(zs_result.get("score", 0.0))
        except Exception as e:
            logger.warning(f"[ensemble] Zero-Shot failed: {e}")

    # --- Transformer
    if nlp_score_email:
        try:
            tr_score, _, _ = nlp_score_email(email_obj)
            tr_score = float(tr_score or 0.0)
        except Exception as e:
            logger.warning(f"[ensemble] Transformer failed: {e}")

    # --- Local NLP
    if LOCAL_NLP_AVAILABLE:
        try:
            local_score, _ = local_nlp_score(email_obj)
            local_score = float(local_score or 0.0)
        except Exception as e:
            logger.warning(f"[ensemble] Local NLP failed: {e}")

    # Weighted mean
    hybrid = (
        zs_score * WEIGHTS["zero_shot"]
        + tr_score * WEIGHTS["transformer"]
        + local_score * WEIGHTS["local_nlp"]
    )

    # --- Linguistic & Unicode anomalies
    full_text = f"{subject} {body} {sender}"
    for detector in (detect_mixed_scripts, detect_invisible_controls, detect_emoji_spoofing):
        flag, msg = detector(full_text)
        if flag:
            reasons.append(msg)
            hybrid += 10

    homog, msg = detect_homoglyph_domain(sender)
    if homog:
        reasons.append(msg)
        hybrid += 15

    lang_mismatch, msg = detect_language_mismatch(full_text, expected_lang=expected_lang)
    if lang_mismatch:
        reasons.append(msg)
        hybrid += 10

    # --- Collective learning weights
    try:
        weights = _load_collective_weights_safe()
        sender_w = float(weights.get("senders", {}).get(sender, 1.0) or 1.0)
        rule_w = 1.0
        for r in matched_rules:
            w = float(weights.get("rules", {}).get(r, 1.0) or 1.0)
            if w > rule_w:
                rule_w = w

        collective_multiplier = min(max(sender_w, rule_w), 2.5)
        if collective_multiplier != 1.0:
            hybrid *= collective_multiplier
            applied = []
            if sender_w != 1.0:
                applied.append(f"sender×{sender_w:.2f}")
            if rule_w != 1.0:
                applied.append(f"rule×{rule_w:.2f}")
            reasons.append(f"Collective AI weight applied ({' & '.join(applied)}; cap 2.5).")
    except Exception as e:
        logger.warning(f"[ensemble] Failed to apply collective weights: {e}")

    # Normalize hybrid to percentage if models returned probabilities (0–1)
    if hybrid <= 1.0:
        hybrid *= 100.0

    # Clamp & round final score
    hybrid = round(min(max(hybrid, 0.0), 100.0), 2)

    # Log visible explanations
    if reasons:
        try:
            print(f"⚠️  [AI-Ensemble] Anomalies for <{sender}> / '{subject[:80]}':")
            for r in reasons:
                print(f"   • {r}")
        except Exception:
            pass
        logger.info("AI-Ensemble reasons: %s", "; ".join(reasons))

    return hybrid, reasons

def ensemble_score(email_obj: dict) -> float:
    score, reasons = ensemble_score_with_reasons(email_obj)
    try:
        email_obj.setdefault("_ensemble_reasons", reasons)
    except Exception:
        pass
    return score
