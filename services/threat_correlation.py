# services/threat_correlation.py
# -----------------------------------------------------------
# AutoGuardian Threat Correlation & Confidence Fusion Engine
# -----------------------------------------------------------
# Purpose:
#   - Correlates multiple detections (rules, AI signals, OSINT)
#   - Adjusts risk score dynamically
#   - Computes confidence tiers for explainability

import math
from typing import Dict, List, Tuple

# ---------------------------------------
# Threat correlation weights
# ---------------------------------------
CORRELATION_WEIGHTS = {
    "rules": 0.3,
    "ai": 0.4,
    "osint": 0.2,
    "behavior": 0.1
}

# Score normalization
def _normalize(score: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(0.0, min(1.0, (score - low) / (high - low)))


# ---------------------------------------
# Core correlation logic
# ---------------------------------------
def correlate_signals(
    rule_hits: List[str],
    ai_score: float,
    osint_verdict: str,
    behavior_risk: float
) -> Tuple[float, Dict[str, float], str]:
    """
    Fuse rule-based, AI, OSINT, and behavior signals into a unified risk score.

    Returns:
        - fused_score (float)
        - components (dict)
        - tier (str): "Low", "Medium", or "High" confidence
    """
    # Base normalizations
    ai_norm = _normalize(ai_score)
    beh_norm = min(1.0, behavior_risk)
    rule_norm = min(1.0, len(rule_hits) / 5.0)
    osint_norm = 1.0 if osint_verdict == "malicious" else (0.5 if osint_verdict == "suspicious" else 0.0)

    # Weighted fusion
    fused = (
        rule_norm * CORRELATION_WEIGHTS["rules"]
        + ai_norm * CORRELATION_WEIGHTS["ai"]
        + osint_norm * CORRELATION_WEIGHTS["osint"]
        + beh_norm * CORRELATION_WEIGHTS["behavior"]
    )

    # Confidence based on number of distinct strong signals
    strong_sources = sum([
        ai_norm > 0.7,
        osint_norm > 0.5,
        rule_norm > 0.5,
        beh_norm > 0.5
    ])

    if strong_sources >= 3:
        tier = "High"
    elif strong_sources == 2:
        tier = "Medium"
    else:
        tier = "Low"

    components = {
        "rule_component": round(rule_norm, 3),
        "ai_component": round(ai_norm, 3),
        "osint_component": round(osint_norm, 3),
        "behavior_component": round(beh_norm, 3),
        "weighted_fusion": round(fused, 3)
    }

    fused_score = round(fused * 100.0, 2)
    return fused_score, components, tier


# ---------------------------------------
# Adaptive rule weighting (self-learning)
# ---------------------------------------
def adapt_rule_weight(
    rule_stats: Dict[str, Dict[str, int]],
    decay: float = 0.9
) -> Dict[str, float]:
    """
    Adjusts rule weights based on performance statistics.
    rule_stats format:
        {
            "rule_pattern": {"true_hits": int, "false_hits": int}
        }
    Returns:
        { "rule_pattern": new_weight }
    """
    new_weights = {}
    for pattern, stats in rule_stats.items():
        true_hits = stats.get("true_hits", 0)
        false_hits = stats.get("false_hits", 0)
        confidence = (true_hits + 1) / (true_hits + false_hits + 2)
        # exponential decay to prevent overfitting
        new_weights[pattern] = round(decay * confidence, 3)
    return new_weights


# ---------------------------------------
# Example usage (for testing)
# ---------------------------------------
if __name__ == "__main__":
    fused, components, tier = correlate_signals(
        rule_hits=["paypal.com", "verify-account"],
        ai_score=78.5,
        osint_verdict="malicious",
        behavior_risk=0.4
    )
    print("Fused Score:", fused)
    print("Components:", components)
    print("Confidence Tier:", tier)

    print("\nAdaptive Weights Example:")
    test_stats = {
        "paypal.com": {"true_hits": 8, "false_hits": 2},
        "office365-login": {"true_hits": 3, "false_hits": 6}
    }
    print(adapt_rule_weight(test_stats))
