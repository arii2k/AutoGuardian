# services/intent_extractor.py — lightweight phishing intent & tactics extractor
import re
from typing import Dict, Any, List

# Simple phrase banks (extendable)
INTENT_PATTERNS = {
    "credential_harvest": [
        r"(verify|confirm|validate).{0,20}(account|password|login)",
        r"single[- ]sign[- ]on|sso",
        r"(mfa|2fa).{0,20}(reset|disable|re[- ]enroll)"
    ],
    "payment_fraud": [
        r"(invoice|payment|wire|bank).{0,20}(due|overdue|failed|problem)",
        r"(gift\s?card|crypto|bitcoin)"
    ],
    "malware_delivery": [
        r"(download|install|attachment).{0,20}(update|patch|viewer|driver)",
        r"\.(cab|js|vbs|scr|exe|iso|img)(\b|$)"
    ],
    "support_impersonation": [
        r"(it|help ?desk|security|support).{0,10}(team|desk|dept)",
        r"(microsoft|google|apple|adobe|paypal|bank|dhl|ups)"
    ],
    "urgency_coercion": [
        r"(urgent|immediately|now|24\s?hours|final notice|last warning|suspend(ed)?)",
        r"(compromised|suspicious activity|unusual login)"
    ],
}

TACTIC_LABELS = {
    "credential_harvest": ["Fake login", "Password reset bait"],
    "payment_fraud": ["Invoice scam", "Advance-fee"],
    "malware_delivery": ["Attachment malware", "Drive-by download"],
    "support_impersonation": ["Brand impersonation", "Internal IT spoof"],
    "urgency_coercion": ["Urgency", "Fear / pressure"],
}

def _score_matches(text: str) -> Dict[str, int]:
    scores = {k: 0 for k in INTENT_PATTERNS.keys()}
    low = text.lower()
    for intent, patterns in INTENT_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, low, flags=re.I):
                scores[intent] += 1
    return scores

def extract_intent(email: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact explainability payload."""
    subject = email.get("Subject", "") or ""
    body = email.get("Body", "") or ""
    joined = f"{subject}\n{body}"

    scores = _score_matches(joined)
    # Choose primary & secondary intents
    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    intents: List[str] = [k for k, v in ranked if v > 0][:2]

    tactics = []
    for it in intents:
        tactics.extend(TACTIC_LABELS.get(it, []))

    confidence = min(1.0, (ranked[0][1] / 3.0) if ranked and ranked[0][1] else 0.0)
    return {
        "primary_intent": intents[0] if intents else "unknown",
        "secondary_intent": intents[1] if len(intents) > 1 else None,
        "tactics": tactics[:3],
        "confidence": round(confidence, 2),
        "signals": scores,
    }
